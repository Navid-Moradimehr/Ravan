from __future__ import annotations

import asyncio
import random

from asyncua import Server


async def main() -> None:
    server = Server()
    await server.init()
    server.set_endpoint("opc.tcp://0.0.0.0:4840/freeopcua/server/")
    namespace = await server.register_namespace("urn:local-stream-engine:opcua-sim")
    objects = server.nodes.objects
    pump = await objects.add_object(namespace, "Pump-01")
    temperature = await pump.add_variable(f"ns={namespace};s=Pump-01.Temperature", "Temperature", 48.0)
    vibration = await pump.add_variable(f"ns={namespace};s=Pump-01.Vibration", "Vibration", 3.0)
    pressure = await pump.add_variable(f"ns={namespace};s=Pump-01.Pressure", "Pressure", 6.2)
    for node in (temperature, vibration, pressure):
        await node.set_writable()

    async with server:
        while True:
            await temperature.write_value(round(random.gauss(48, 5), 2))
            await vibration.write_value(round(random.gauss(3, 1), 2))
            await pressure.write_value(round(random.gauss(6.2, 0.4), 2))
            await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
