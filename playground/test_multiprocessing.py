import asyncio
from signal import Signals

import aiodrive


async def a(x: float):
    global state

    if "state" not in globals():
        state = 0

    print(f"Sleeping {x}")
    await asyncio.sleep(x)

    state += x
    print(f"Slept {x} {state}")

    return x

async def main():
    try:
        with aiodrive.handle_signal(Signals.SIGINT):
            async with aiodrive.MultiprocessingProcess() as proc:
                print(
                    await aiodrive.gather(
                        proc.spawn(a, .5),
                        proc.spawn(a, 1),
                        proc.spawn(a, 2),
                    ),
                )

                # print("Result", await proc.spawn(a, 1))
    except* aiodrive.SignalHandledException:
        print("Operation cancelled by user.")


if __name__ == "__main__":
    aiodrive.run(main())
