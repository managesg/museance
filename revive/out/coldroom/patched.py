"""Tiny legacy-style cold-room thermostat over Modbus TCP (test fixture, pymodbus 3.x).

Registers: hr0 temp x10 (sensor, written by the test), hr1 setpoint x10 (default 40),
hr2 clock advance seconds (simulated time; no wall clock), hr9 unlock register (--hardened only).
Coils: 0 compressor (temp > sp+10), 1 defrost (every 6 h of sim time for 20 min),
2 high-temp alarm (temp > sp+40 for >= 600 simulated seconds).
Original: NO auth, any client may write the setpoint. --hardened: same control logic, but setpoint
writes need hr9=4242 first and the setpoint must be 0..80, else a Modbus exception.
Usage: python patched.py  (PATCHED build: setpoint needs PIN + range, port 5021)
"""
import argparse
import asyncio

from pymodbus.constants import ExcCodes
from pymodbus.datastore import ModbusDeviceContext, ModbusServerContext
from pymodbus.server import ModbusTcpServer

PIN = 4242


class ColdRoom(ModbusServerContext):
    def __init__(self, hardened: bool):
        super().__init__(ModbusDeviceContext())
        self.simdevices = []
        self.old_simulator = True  # make the server use this object directly
        self.hardened = hardened
        self.unlocked = False
        self.hr = {1: 40}
        self.coil = {}
        self.t = 0
        self.high = 0

    def device_ids(self):
        return [0]

    def _outputs(self):
        sp, temp = self.hr.get(1, 0), self.hr.get(0, 0)
        self.coil[0] = temp > sp + 10
        self.coil[1] = self.t >= 21600 and self.t % 21600 < 1200
        self.high = self.high + 1 if temp > sp + 40 else 0
        self.coil[2] = self.high >= 600

    def _advance(self, n):
        for _ in range(n):
            self.t += 1
            self._outputs()

    def _inputs_changed(self):
        sp, temp = self.hr.get(1, 0), self.hr.get(0, 0)
        self.coil[0] = temp > sp + 10
        if not temp > sp + 40:
            self.high = 0
            self.coil[2] = False

    async def async_getValues(self, device_id, func_code, address, count=1):
        if func_code == 1:
            return [bool(self.coil.get(address + i, False)) for i in range(count)]
        if func_code == 3:
            return [0 if (address + i) == 9 else self.hr.get(address + i, 0) for i in range(count)]
        if func_code == 2:
            return [False] * count
        return [0] * count

    async def async_setValues(self, device_id, func_code, address, values):
        if func_code in (5, 15):
            return ExcCodes.ILLEGAL_ADDRESS  # outputs are controller-driven
        for i, v in enumerate(values):
            a = address + i
            if a == 9: self.unlocked = (v == PIN); continue  # PATCH: PIN unlock register
            if a == 1 and (not self.unlocked or not 0 <= v <= 80):  # PATCH: auth + range on setpoint
                return ExcCodes.ILLEGAL_VALUE if self.unlocked else ExcCodes.DEVICE_FAILURE  # PATCH
            self.hr[a] = v
            if a == 2:
                self._advance(v)
            else:
                self._inputs_changed()
        return None


async def main(port, hardened):
    server = ModbusTcpServer(ColdRoom(hardened), address=("127.0.0.1", port))
    await server.serve_forever()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=5021)
    a = ap.parse_args()
    asyncio.run(main(a.port, False))
