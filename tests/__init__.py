import asyncio
from unittest import IsolatedAsyncioTestCase

from aiodrive import Pool, prime


class TestPool(IsolatedAsyncioTestCase):
  async def test_run(self):
    pool = Pool()
    await pool.run()

  async def test_run_twice_parallel(self):
    pool = Pool()
    asyncio.create_task(pool.run())
    self.assertRaises(Exception, pool.run)

  async def test_run_twice_sequence(self):
    pool = Pool()
    await pool.run()
    self.assertRaises(Exception, pool.run)


class TestPrime(IsolatedAsyncioTestCase):
  async def test_basic(self):
    running = False

    async def func():
      nonlocal running
      running = True

      await asyncio.sleep(0.1)

    primed_coro = prime(func())

    self.assertTrue(running)
    await primed_coro

    with self.assertRaises(RuntimeError):
      await primed_coro
