"""Evaluate the fixed regression set against a revival; never load the original."""
import sys
import argparse
import ctypes
import ctypes.util
import errno
from html.parser import HTMLParser
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent.parent


class RevivalDocument(HTMLParser):
    """Parse markup as data before it enters the JavaScript sandbox."""
    VOID = set("area base br col embed hr img input link meta param source track wbr".split())

    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.elements = {}
        self.scripts = []
        self.stack = []
        self.script = None
        self.feed(html)
        self.close()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script":
            if "src" in attrs or attrs.get("type", "").lower() == "module":
                raise ValueError("Expected classic inline scripts")
            self.script = [] if attrs.get("type", "").lower() in ("", "text/javascript", "application/javascript") else None
        node = None
        if attrs.get("id") and attrs["id"] not in self.elements:
            node = {"id": attrs["id"], "text": ""}
            self.elements[attrs["id"]] = node
        if tag not in self.VOID:
            self.stack.append((tag, node))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag == "script" and self.script is not None:
            self.scripts.append("".join(self.script))
            self.script = None
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        if self.stack and self.stack[-1][0] == "script":
            if self.script is not None:
                self.script.append(data)
            return
        if any(tag == "style" for tag, _ in self.stack):
            return
        for _, node in self.stack:
            if node is not None:
                node["text"] += data

    def payload(self):
        if not self.scripts:
            raise ValueError("Expected classic inline scripts")
        return {"elements": list(self.elements.values()), "scripts": self.scripts}


def deny_network():
    """Fail closed: Linux seccomp blocks networking even after a VM escape."""
    name = ctypes.util.find_library("seccomp")
    if not name:
        raise RuntimeError("libseccomp is required to sandbox generated JavaScript")
    lib = ctypes.CDLL(name, use_errno=True)
    lib.seccomp_init.argtypes = [ctypes.c_uint32]
    lib.seccomp_init.restype = ctypes.c_void_p
    lib.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    lib.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint]
    lib.seccomp_load.argtypes = [ctypes.c_void_p]
    lib.seccomp_release.argtypes = [ctypes.c_void_p]
    ctx = lib.seccomp_init(0x7FFF0000)  # SCMP_ACT_ALLOW
    if not ctx:
        raise RuntimeError("Cannot initialize network sandbox")
    try:
        for syscall in (b"socket", b"socketpair", b"connect", b"bind", b"listen", b"accept", b"accept4"):
            number = lib.seccomp_syscall_resolve_name(syscall)
            if number >= 0 and lib.seccomp_rule_add(ctx, 0x00050000 | errno.EPERM, number, 0):
                raise RuntimeError("Cannot deny networking syscall")
        if lib.seccomp_load(ctx):
            raise RuntimeError("Cannot load network sandbox")
    finally:
        lib.seccomp_release(ctx)


def check_revival(html_path, checks_path=ROOT / "eval/regression/app1-fixture.json"):
    html_path, checks_path = Path(html_path).resolve(), Path(checks_path).resolve()
    for path in (html_path, checks_path):
        if not path.is_file():
            raise FileNotFoundError(f"Missing evaluation input: {path}")
    runner = Path(__file__).with_name("run_revival.js").resolve()
    document = RevivalDocument(html_path.read_text(encoding="utf-8")).payload()
    # Node permissions restrict file access and prohibit subprocesses/native addons.
    # seccomp provides the network boundary; vm alone is not a security boundary.
    command = ["node", "--permission", *(f"--allow-fs-read={p}" for p in (runner, checks_path)),
               "--disable-proto=throw", "--max-old-space-size=128", str(runner), str(checks_path)]
    result = subprocess.run(command, input=json.dumps(document), capture_output=True, text=True,
                            timeout=60, **({} if sys.platform == "win32" else {"preexec_fn": deny_network}))
    # shortcut: no seccomp on Windows, so the network is not blocked there; score untrusted revivals on Linux (the box).
    if result.returncode:
        raise RuntimeError(f"Node evaluator exited {result.returncode}: {result.stderr[-3000:]}")
    observations = json.loads(result.stdout)
    data = json.loads(checks_path.read_text(encoding="utf-8"))
    rows = data if isinstance(data, list) else data["good"] + data["traps"]
    passed = 0
    failed = []
    for row in rows:
        got = observations[row["id"]]
        ok = "error" not in got and got.get("observed") == row["expect"]
        passed += ok
        if not ok:
            failed.append(row["id"])
        detail = got.get("error", repr(got.get("observed")))
        print(f"{'PASS' if ok else 'FAIL'} {row['id']}: expected {row['expect']!r}, got {detail}")
    print(f"Total: {passed}/{len(rows)} passed")
    print("Failed checks: " + (", ".join(failed) or "none"))
    return 0 if not failed else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html", nargs="?", help="revival index.html")
    parser.add_argument("--html", "--revival", dest="html_option")
    parser.add_argument("--checks", default=str(ROOT / "eval/regression/app1-fixture.json"))
    args = parser.parse_args()
    target = args.html_option or args.html
    if not target:
        parser.error("provide a revival HTML path")
    try:
        return check_revival(target, args.checks)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        parser.exit(2, f"Evaluation failed: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
