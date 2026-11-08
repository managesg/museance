# ICS dialect: Modbus TCP court

The same deterministic `rule()`/`judge()`/Bailiff/ledger, with a Modbus bench (`court/ics.py`,
`ModbusBench`) instead of the browser. No AI. URLs look like `modbus://127.0.0.1:<port>`; every run
launches a fresh controller process from the `launch` mapping `{url: argv}`, waits for the port (10 s), runs
the steps, reads the observe, kills it.

## Run

```
pip install pymodbus
python court/ics/make_sample.py                          # regenerates court/ics/sample_run/
python -m pytest -q court/tests/test_ics.py -p no:asyncio
```

```python
from court.ics import judge_modbus
judge_modbus(claims, attacks, "modbus://127.0.0.1:5020", "modbus://127.0.0.1:5021", "runs/coldroom",
             launch={url: [argv...]}, clock_reg=2)
```

Steps: `hr:<addr>=<int>`, `coil:<addr>=<0|1>`, `wait:<ms>`, `tick:<n>` (writes n to the clock register).
A rejected write is recorded in `bench.events`, not a crash. Observe: `hr|ir|coil|di:<addr>`, comma-separated
-> `hr0=40,coil3=1` (a single item returns the bare value).

## Cold room register map (test controller `court/tests/ics/legacy_cold_room.py`)

| Address | Meaning |
|---|---|
| hr0 | temperature x10 (sensor, written by the test) |
| hr1 | setpoint x10, default 40 |
| hr2 | clock advance, simulated seconds (no wall clock) |
| hr9 | unlock register, `--hardened` only (PIN 4242) |
| coil0 | compressor on when temp > setpoint + 10 |
| coil1 | defrost, every 6 h of simulated time for 20 min |
| coil2 | high-temp alarm, temp > setpoint + 40 for >= 600 s |

Original: no auth, anyone can write the setpoint. `--hardened`: same control logic, setpoint writes need
hr9=4242 first and the value must be 0..80.

## Claims (sample_run, app id `coldroom`)

cr01 compressor on above setpoint; cr02 off near setpoint; cr03 no alarm at 599 s; cr04 alarm at 600 s;
cr05 defrost at 6 h; cr06 defrost ends at 6 h 20 min. Attacks: `sec-setpoint`, `sec-setpoint-range`,
`sec-wrong-pin`.

## Measured result (this run)

- Original vs hardened: 6/6 control claims LOCKED, match=True, 0 flaky.
- 3/3 security attacks diverge (match=False, 0 flaky): the original accepts hr1=250 / 500 / 100 from any
  client; the hardened build keeps hr1=40 (and, in `sec-setpoint`, still raises the alarm at
  coil2=1 because the setpoint was not moved).
- Tests: `court/tests/test_ics.py` 4 passed in 81.7 s.
