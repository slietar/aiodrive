# ruff: noqa: ANN001, ANN002

import asyncio
from dataclasses import dataclass
import heapq
from asyncio import AbstractEventLoop, BaseEventLoop, Future, TimerHandle
from threading import Lock, Thread
import threading
import time
import traceback
from typing import Optional, override


class ThreadEventLoop(BaseEventLoop):
    # @override
    # def close(self):
    #     pass
    pass


@dataclass(slots=True)
class Job:
    thread: Thread

class EventSimulatorLoop(asyncio.AbstractEventLoop):
    '''A simple event-driven simulator, using async/await'''

    def __init__(self):
        self._running = False
        self._immediate = []
        self._scheduled = []
        self._exc = None

        # self._jobs = []
        self._lock = Lock()
        self._timer_handles = dict[TimerHandle, threading.Event]()

    @override
    def get_debug(self):
        # A silly hangover from the way asyncio is written
        return False

    @override
    def time(self):
        return time.time()

    # Methods for running the event loop.
    # For a real asyncio system you need to worry a lot more about running+closed.
    # For a simple simulator, we completely control the passage of time, so most of
    # these functions are trivial.
    #
    # I've split the pending events into _immediate and _scheduled.
    # I could put them all in _scheduled; but if there are lots of
    # _immediate calls there's no need for them to clutter up the heap.

    @override
    def run_forever(self):
        asyncio._set_running_loop(self)
        self._running = True

        # while (self._immediate or self._scheduled) and self._running:
        #     if self._immediate:
        #         h = self._immediate[0]
        #         self._immediate = self._immediate[1:]
        #     else:
        #         h = heapq.heappop(self._scheduled)
        #         self._time = h._when
        #         h._scheduled = False   # just for asyncio.TimerHandle debugging?
        #     if not h._cancelled:
        #         h._run()
        #     if self._exc is not None:
        #         raise self._exc

        time.sleep(2)

    @override
    def run_until_complete(self, future):
        def _run_until_complete_cb(fut: asyncio.Future):
            if not fut.cancelled():
                exc = fut.exception()
                if isinstance(exc, (SystemExit, KeyboardInterrupt)):
                    # Issue #22429: run_forever() already finished, no need to
                    # stop it.
                    return

            self.stop()

        new_task = not asyncio.isfuture(future)
        future = asyncio.ensure_future(future, loop=self)

        # if new_task:
        #     # An exception is raised if the future didn't complete, so there
        #     # is no need to log the "destroy pending task" message
        #     future._log_destroy_pending = False

        future.add_done_callback(_run_until_complete_cb)

        try:
            self.run_forever()
        except:
            if new_task and future.done() and not future.cancelled():
                # The coroutine raised a BaseException. Consume the exception
                # to not log a warning, the caller doesn't have access to the
                # local task.
                future.exception()
            raise
        finally:
            future.remove_done_callback(_run_until_complete_cb)
        if not future.done():
            raise RuntimeError('Event loop stopped before Future completed.')

        return future.result()


    @override
    def is_running(self):
        return self._running

    @override
    def is_closed(self):
        return not self._running

    @override
    def stop(self):
        asyncio._set_running_loop(None)
        self._running = False

    @override
    def close(self):
        asyncio._set_running_loop(None)
        self._running = False

    @override
    async def shutdown_asyncgens(self):
        pass

    @override
    async def shutdown_default_executor(self, timeout = None):
        pass

    @override
    def call_exception_handler(self, context):
        # If there is any exception in a callback, this method gets called.
        # I'll store the exception in self._exc, so that the main simulation loop picks it up.
        self._exc = context.get('exception', None)


    # Methods for scheduling jobs.
    #
    # If the job is a coroutine, the end-user should call asyncio.ensure_future(coro()).
    # The asyncio machinery will invoke loop.create_task(). Asyncio will then
    # run the coroutine in pieces, breaking it apart at async/await points, and every time it
    # will construct an appropriate callback and call loop.call_soon(cb).
    #
    # If the job is a plain function, the end-user should call one of the loop.call_*()
    # methods directly.

    @override
    def call_soon(self, callback, *args, context = None):
        h = asyncio.Handle(callback, args, self)
        self._immediate.append(h)
        return h

    @override
    def call_later(self, delay, callback, *args, context = None):
        if delay < 0:
            raise Exception("Can't schedule in the past")

        handle = TimerHandle(self.time() + delay, callback, args, loop=self)
        event = threading.Event()

        self._timer_handles[handle] = event

        async def run():
            event.wait(delay)
            handle._run()

        asyncio.create_task(run())  # noqa: RUF006

        return handle

    # Called by TimerHandle.cancel()
    def _timer_handle_cancelled(self, handle: TimerHandle):
        # print("Cancelled timer handle")
        self._timer_handles[handle].set()
        del self._timer_handles[handle]

    @override
    def call_at(self, when, callback, *args, context = None):
        # if when < self._time:
        #     raise Exception("Can't schedule in the past")
        # h = asyncio.TimerHandle(when, callback, args, self)
        # heapq.heappush(self._scheduled, h)
        # # h._scheduled = True  # perhaps just for debugging in asyncio.TimerHandle?

        # return h
        # raise NotImplementedError
        return self.call_later(when - self.time(), callback, *args, context=context)

    @override
    def create_task(self, coro, *, name = None, context = None): # type: ignore
        # # Since this is a simulator, I'll run a plain simulated-time event loop, and
        # # if there are any exceptions inside any coroutine I'll pass them on to the
        # # event loop, so it can halt and print them out. To achieve this, I need the
        # # exception to be caught in "async mode" i.e. by a coroutine, and then
        # # use self._exc to pass it on to "regular execution mode".
        # async def wrapper():
        #     try:
        #         await coro
        #     except Exception as e:
        #         print("Wrapped exception")
        #         self._exc = e

        # return asyncio.Task(wrapper(), loop=self)

        # thread = Thread(target=target)
        # thread.start()

        # self._jobs.append(Job(
        #     thread=thread,
        # ))

        task = EventSimulatorTask(coro, loop=self, name=(name or coro.__name__))
        return task

    @override
    def create_future(self):
        # Not sure why this is here rather than in AbstractEventLoop.
        return asyncio.Future(loop=self)


class EventSimulatorTask(Future):
    def __init__(self, coro, *, loop: EventSimulatorLoop, name: str):
        super().__init__(loop=loop)

        def target():
            asyncio._set_running_loop(loop)

            current_future: Optional[Future] = None

            while True:
                try:
                    with loop._lock:
                        if (current_future is None) or current_future.done():
                            # TODO: Probably replace coro.send(None) with coro.send(current_future.result())
                            current_future = coro.send(None)
                except StopIteration as e:
                    self.set_result(e.value)
                    break
                except BaseException as e:
                    print("Exception in coroutine:", e)
                    traceback.print_exc()
                    self.set_exception(e)
                    break

        thread = Thread(name=name, target=target)
        thread.start()



async def a():
    print("Hello from a")
    await asyncio.sleep(1)
    print("Goodbye from a")
    return 14

async def b():
    print("Hello from b")
    await asyncio.sleep(1.2)
    print("Goodbye from b")

async def main():
    # x = await asyncio.create_task(a())
    # print("a returned", x)
    asyncio.create_task(a())
    asyncio.create_task(b())
    await asyncio.sleep(0.2)
    print("Starting simulation")

# asyncio.run(main(), loop_factory=ThreadEventLoop)
asyncio.run(main(), loop_factory=EventSimulatorLoop)
