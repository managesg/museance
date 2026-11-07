"""ICS dialect for the Court: a Modbus TCP bench with the same interface as court.court.Bench.

URL form modbus://127.0.0.1:<port>. Steps: hr:<addr>=<int>, coil:<addr>=<0|1>, wait:<ms>, tick:<n>.
Observe: hr:<a> | ir:<a> | coil:<a> | di:<a>, comma-separated. One item -> bare value ("250");
several -> "hr0=40,coil3=1". Rejected writes (exception/connection drop) are observations kept in
bench.events, never crashes. Every run (re)launches the controller from `launch` = {url: [argv]}.
"""
from __future__ import annotations

import re
import socket
import subprocess
import time
from urllib.parse import urlparse

from court.steps import StepError

LAUNCH_DEADLINE_S = 10.0
_INT = re.compile(r"^-?\d{1,6}$")


def _addr(s: str, what: str) -> int:
    if not re.fullmatch(r"\d{1,5}", s) or int(s) > 65535:
        raise StepError(f"bad {what} address {s!r}")
    return int(s)


def parse_step(step: str, clock_reg: int | None = None) -> tuple[str, int, int]:
    """-> (kind, a, b). kinds: hr/coil (addr, value), wait (ms, 0), tick (clock_reg, n)."""
    kind, sep, rest = step.partition(":")
    if not sep:
        raise StepError(f"bad step {step!r}")
    if kind in ("hr", "coil"):
        a, eq, v = rest.partition("=")
        if not eq or not _INT.match(v):
            raise StepError(f"bad {kind} step {step!r}, want {kind}:<addr>=<int>")
        addr, val = _addr(a, kind), int(v)
        if kind == "coil" and val not in (0, 1):
            raise StepError(f"bad coil step {step!r}, value must be 0 or 1")
        if kind == "hr" and not 0 <= val <= 65535:
            raise StepError(f"bad hr step {step!r}, value must be 0..65535")
        return kind, addr, val
    if kind in ("wait", "tick"):
        if not re.fullmatch(r"\d{1,6}", rest):
            raise StepError(f"bad {kind} step {step!r}, want {kind}:<int>")
        n = int(rest)
        if kind == "wait":
            return "wait", n, 0
        if clock_reg is None:
            raise StepError("tick step needs a configured clock register")
        if n > 65535:
            raise StepError(f"tick {n} exceeds 65535")
        return "tick", clock_reg, n
    raise StepError(f"unknown step kind {kind!r} in {step!r}")


def parse_observe(observe: str) -> list[tuple[str, int]]:
    items = []
    for part in observe.split(","):
        kind, sep, a = part.strip().partition(":")
        if not sep or kind not in ("hr", "ir", "coil", "di"):
            raise StepError(f"bad observe item {part!r}, want hr|ir|coil|di:<addr>")
        items.append((kind, _addr(a, kind)))
    return items


def _host_port(url: str) -> tuple[str, int]:
    u = urlparse(url)
    if u.scheme != "modbus" or not u.hostname or not u.port:
        raise StepError(f"bad url {url!r}, want modbus://127.0.0.1:<port>")
    return u.hostname, u.port


class ModbusBench:
    def __init__(self, launch: dict | None = None, clock_reg: int | None = None):
        self.launch = launch or {}
        self.clock_reg = clock_reg
        self.events: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return None

    def run(self, url: str, steps: list[str], observe: str) -> str:
        parsed = [parse_step(s, self.clock_reg) for s in steps]  # contract bugs raise before launching
        items = parse_observe(observe)
        host, port = _host_port(url)
        self.events = []
        proc = None
        if url in self.launch:
            proc = subprocess.Popen(self.launch[url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            err = self._wait_port(host, port, proc)
            if err:
                return f"ERROR:load {url} {err}"
            return self._session(host, port, parsed, items)
        finally:
            if proc is not None:
                proc.kill()
                proc.wait()

    @staticmethod
    def _wait_port(host, port, proc) -> str:
        end = time.monotonic() + LAUNCH_DEADLINE_S
        while time.monotonic() < end:
            if proc is not None and proc.poll() is not None:
                return f"controller exited with {proc.returncode}"
            try:
                with socket.create_connection((host, port), timeout=0.5):
                    return ""
            except OSError:
                time.sleep(0.1)
        return f"port not open after {LAUNCH_DEADLINE_S:.0f}s"

    def _session(self, host, port, parsed, items) -> str:
        from pymodbus.client import ModbusTcpClient
        client = ModbusTcpClient(host, port=port, timeout=3, retries=0)
        if not client.connect():
            return f"ERROR:load modbus://{host}:{port} connect failed"
        try:
            for kind, a, b in parsed:
                if kind == "wait":
                    time.sleep(a / 1000)
                    continue
                try:
                    if kind == "coil":
                        r = client.write_coil(a, bool(b))
                    else:  # hr and tick
                        r = client.write_register(a, b)
                    if r.isError():
                        self.events.append(f"rejected {kind}:{a}={b} {r}")
                except Exception as e:  # connection drop is an observation too
                    self.events.append(f"dropped {kind}:{a}={b} {type(e).__name__}")
                    client.close()
                    client.connect()
            out = []
            for kind, a in items:
                try:
                    fn = {"hr": client.read_holding_registers, "ir": client.read_input_registers,
                          "coil": client.read_coils, "di": client.read_discrete_inputs}[kind]
                    r = fn(a, count=1)
                    if r.isError():
                        return f"ERROR:observe {kind}:{a} {r}"
                    v = int(r.registers[0]) if kind in ("hr", "ir") else int(bool(r.bits[0]))
                except Exception as e:
                    return f"ERROR:observe {kind}:{a} {type(e).__name__}"
                out.append((f"{kind}{a}", v))
            return str(out[0][1]) if len(out) == 1 else ",".join(f"{k}={v}" for k, v in out)
        finally:
            client.close()


def judge_modbus(claims, attacks, original_url, revival_url, out_dir, launch=None, clock_reg=None, clock=None):
    from court.court import judge
    bench = ModbusBench(launch=launch, clock_reg=clock_reg)
    return judge(claims, attacks, original_url, revival_url, out_dir, clock=clock, bench=bench, workers=1)
