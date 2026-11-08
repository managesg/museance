# Cold-room controller: ORIGINAL vs PATCHED (P4)

Modeled on the Danfoss refrigeration controllers involved in the Oct/Nov 2026 EU supermarket attacks; **not vendor code**. Modbus TCP on 127.0.0.1, simulated clock.

- `original.py` (port 5020): no auth, anyone can write the setpoint (hr1) or the clock.
- `patched.py` (port 5021): identical control logic plus the 3-line patch in `PATCH.diff`: setpoint writes need the PIN in hr9 and a value in 0..80, else a Modbus exception.

Run (needs `pymodbus`): `python revive/out/coldroom/original.py` and `python revive/out/coldroom/patched.py`, then point P1's court (`court/ics/README.md`) at 127.0.0.1:5020 vs 127.0.0.1:5021.
