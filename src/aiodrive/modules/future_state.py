import asyncio
import contextlib
from asyncio import Future
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal, Optional, cast


@dataclass(kw_only=True, slots=True)
class FutureState[T]:
    exception: Optional[BaseException] = None
    result: T = cast(T, None)  # noqa: RUF009
    status: Literal["cancelled", "exception", "pending", "success"]

    def apply(self):
        match self.status:
            case "cancelled":
                raise asyncio.CancelledError from None
            case "exception":
                assert self.exception is not None
                raise self.exception from None
            case "pending":
                raise RuntimeError("Future is still pending")
            case "success":
                return self.result

    def transfer(self, future: Future[T], /):
        assert not future.done()

        match self.status:
            case "cancelled":
                future.cancel()
            case "exception":
                assert self.exception is not None
                future.set_exception(self.exception)
            case "pending":
                pass
            case "success":
                future.set_result(self.result)

    def transfer_threadsafe(self, future: Future[T], /):
        future.get_loop().call_soon_threadsafe(self.transfer, future)

    @classmethod
    def new_cancelled(cls):
        return cls(status="cancelled")

    @classmethod
    def new_failed(cls, exception: BaseException, /):
        return cls(exception=exception, status="exception")

    @classmethod
    def new_pending(cls):
        return cls(status="pending")

    @classmethod
    def new_success(cls, result: T, /):
        return cls(result=result, status="success")

    @contextlib.contextmanager
    def absorb_context(cls, /, result: T = None):
        state = cls.new_pending()

        try:
            yield state
        except asyncio.CancelledError:
            state.status = "cancelled"
        except Exception as e:
            state.status = "exception"
            state.exception = e
        else:
            state.status = "success"
            state.result = result

    @classmethod
    def absorb_future(cls, future: Future[T], /):
        if not future.done():
            return cls.new_pending()

        if future.cancelled():
            return cls.new_cancelled()

        if (exception := future.exception()) is not None:
            return cls.new_failed(exception)

        return cls.new_success(future.result())

    @classmethod
    async def absorb_awaitable(cls, awaitable: Awaitable[T], /):
        try:
            result = await awaitable
        except asyncio.CancelledError:
            return cls.new_cancelled()
        except BaseException as e:
            return cls.new_failed(e)
        else:
            return cls.new_success(result)

    @classmethod
    def absorb_lambda(cls, func: Callable[[], T], /):
        try:
            result = func()
        except BaseException as e:
            return cls.new_failed(e)
        else:
            return cls.new_success(result)


__all__ = [
    'FutureState',
]
