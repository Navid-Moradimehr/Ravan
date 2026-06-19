from __future__ import annotations

import asyncio
import random

from pymodbus.datastore import ModbusSequentialDataBlock, ModbusServerContext, ModbusSlaveContext
from pymodbus.server import StartAsyncTcpServer


async def update_registers(context: ModbusServerContext) -> None:
    while True:
        values = [
            int(random.gauss(48, 5) * 10),
            int(random.gauss(3, 1) * 100),
            int(random.gauss(6.2, 0.4) * 10),
        ]
        context[1].setValues(3, 0, values)
        await asyncio.sleep(1)


async def main() -> None:
    store = ModbusSlaveContext(hr=ModbusSequentialDataBlock(0, [0] * 100))
    context = ModbusServerContext(slaves={1: store}, single=False)
    updater = asyncio.create_task(update_registers(context))
    try:
        await StartAsyncTcpServer(context=context, address=("0.0.0.0", 5020))
    finally:
        updater.cancel()


if __name__ == "__main__":
    asyncio.run(main())
