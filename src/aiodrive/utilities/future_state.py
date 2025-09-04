from asyncio import Future
from dataclasses import dataclass
from typing import Literal, Optional


@dataclass(kw_only=True, slots=True)
class FutureState[T]:
    exception: Optional[BaseException] = None
    result: Optional[T] = None
    status: Literal["cancelled", "exception", "pending", "success"]

    def digest(self, future: Future[T], /):
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
                assert self.result is not None

    @classmethod
    def new_cancelled(cls):
        return cls(status="cancelled")

    @classmethod
    def new_failed(cls, exception: BaseException):
        return cls(exception=exception, status="exception")

    @classmethod
    def new_pending(cls):
        return cls(status="pending")

    @classmethod
    def new_success(cls, result: T):
        return cls(result=result, status="success")

    @classmethod
    def absorb(cls, future: Future[T], /):
        if not future.done():
            return cls.new_pending()

        if future.cancelled():
            return cls.new_cancelled()

        if (exception := future.exception()) is not None:
            return cls.new_failed(exception)

        return cls.new_success(future.result())
