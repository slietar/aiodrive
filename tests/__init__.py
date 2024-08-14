import asyncio
from unittest import IsolatedAsyncioTestCase

from aiotoolbox import Pool


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
