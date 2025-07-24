import asyncio
from asyncio import Future
from pprint import pprint
import sys
import traceback
from types import TracebackType
from typing import Optional, TypeVar
from venv import create

from .pool import Pool


def create_trace(start_depth: int = 0):
  # return None
  tb = None
  depth = (start_depth + 2)

  while True:
    try:
      frame = sys._getframe(depth)
      depth += 1
    except ValueError:
      break

    tb = TracebackType(tb, frame, frame.f_lasti, frame.f_lineno)

  return tb


def slice_tb(tb: TracebackType, size: int):
  tbs = []

  current_tb = tb

  while current_tb:
    tbs.append(current_tb)
    current_tb = current_tb.tb_next

  print(tbs)



if __name__ == "_main__":
  async def fn():
    # await asyncio.sleep(1)
    print(Pool.try_current().format(ancestors='all'))
    # raise Exception("Hello")

  async def fn2():
    await asyncio.sleep(0.01)

  async def fn_wrapper():
    # await fn()

    async with Pool.open('D') as pool:
      pool.spawn(fn2(), depth=5)
      pool.spawn(fn2())
      pool.spawn(fn())

  async def main():
    async with Pool.open('A') as pool:
      print(Pool.try_current())

      async with Pool.open('B') as pool:
        print(Pool.try_current())
        await asyncio.sleep(0.1)

        async with Pool.open('C') as pool:
          print(Pool.try_current())
          await asyncio.sleep(0.1)
          pool.spawn(fn_wrapper())

        print(Pool.try_current())

      print(Pool.try_current())

  try:
    asyncio.run(main())
  except KeyboardInterrupt:
    pass

# if __name__ == "__main__":
#   async def fn():
#     raise Exception("Hello")

#   async def fn_wrapper():
#     await asyncio.create_task(fn())

#   def add_fn(pool):
#     pool.start_soon(fn_wrapper())

#   async def main():
#     try:
#       async with Pool.open() as pool:
#         add_fn(pool)
#     except Exception:
#       traceback.print_exc()

#   try:
#     asyncio.run(main())
#   except KeyboardInterrupt:
#     pass


if __name__ == "_main__":
  async def fn():
    raise Exception("Hi")

  def create_task(coro):
    call_trace = create_trace()

    # print(traceback.print_tb(call_trace))
    # sys.exit()

    async def wrapper():
      try:
        return await coro
      except Exception as e:
        # x = create_trace()
        # traceback.print_tb(x)

        # raise
        # slice_tb(e.__traceback__, 3)
        # call_trace.tb_next = e.__traceback__
        e.__traceback__.tb_next.tb_next = call_trace
        raise e.with_traceback(e.__traceback__)

    return asyncio.create_task(wrapper())

  async def main():
    t = create_task(fn())
    await t

  # async def main():
  #   async with Pool.open("Outer pool") as pool:
  #     pool.start_soon(fn())

  try:
    asyncio.run(main())
  except KeyboardInterrupt:
    pass

  # def a():
  #   raise Exception("Hello")

  # def b():
  #   a()

  # x = create_trace()

  # def c():
  #   try:
  #     b()
  #   except Exception as e:
  #     # x = traceback.extract_tb()
  #     # print(x)

  #     # trace = traceback.extract_tb(e.__traceback__)
  #     # pprint(trace[1:])
  #     # x = traceback.StackSummary.from_list(trace[1:])

  #     # raise e.with_traceback(e.__traceback__.tb_next if e.__traceback__ else None)
  #     raise e.with_traceback(x)

  #     # raise e.with_traceback(e.__traceback__) from None

  # c()


if __name__ == "__main__":
  T = TypeVar('T')

  def unwrap(value: Optional[T]) -> T:
    assert value is not None
    return value

  async def fn1():

    unwrap(Pool.try_current()).spawn(fn2())
    # await asyncio.sleep(1.1)

  async def fn2():
    await asyncio.sleep(0.1)
    print(unwrap(Pool.try_current()).format(ancestors='all'))

  async def main():
    async with Pool.open() as pool:
      pool.spawn(fn1())

  asyncio.run(main())
