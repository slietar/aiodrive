import asyncio
import contextlib
from asyncio import Future
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal, Optional, cast


@dataclass(kw_only=True, slots=True)
class FutureState[T]:
    """
    A primitive for storing a future's state.
    """

    exception: Optional[BaseException] = None
    result: T = cast(T, None)  # noqa: RUF009
    status: Literal["cancelled", "exception", "pending", "success"]

    def apply(self):
        """
        Apply the stored state, that is, act as if a future with the same state
        had just been awaited.

        Raises
        ------
        RuntimeError
            If the status is `"pending"`.
        """

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
        """
        Transfer the stored state to the given future.

        Parameters
        ----------
        future
            The future to transfer the state to.
        """

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
        """
        Transfer the stored state to the given future in a thread-safe manner.

        Parameters
        ----------
        future
            The future to transfer the state to.
        """

        future.get_loop().call_soon_threadsafe(self.transfer, future)

    @classmethod
    def new_cancelled(cls):
        """
        Create a new instance representing a cancelled future.

        Returns
        -------
        FutureState[T]
        """

        return cls(status="cancelled")

    @classmethod
    def new_failed(cls, exception: BaseException, /):
        """
        Create a new instance representing a future that failed with the given
        exception.

        Parameters
        ----------
        exception
            The exception the future failed with.

        Returns
        -------
        FutureState[T]
        """
        return cls(exception=exception, status="exception")

    @classmethod
    def new_pending(cls):
        """
        Create a new instance representing a pending future.

        Returns
        -------
        FutureState[T]
        """
        return cls(status="pending")

    @classmethod
    def new_success(cls, result: T, /):
        """
        Create a new instance representing a successfully completed future.

        Parameters
        ----------
        result
            The result of the future.

        Returns
        -------
        FutureState[T]
        """
        return cls(result=result, status="success")

    @contextlib.contextmanager
    def absorb_context(cls, /, result: T = cast(Any, None)):
        """
        Create a context manager that absorbs the outcome of the context block
        into a new instance.

        Parameters
        ----------
        result
            The result to store if the context block completes successfully.

        Returns
        -------
        AbstractContextManager[FutureState[T]]
        """

        state = cls.new_pending()

        try:
            yield state
        except asyncio.CancelledError:
            state.status = "cancelled"
        except BaseException as e:
            state.status = "exception"
            state.exception = e
        else:
            state.status = "success"
            state.result = result

    @classmethod
    def absorb_future(cls, future: Future[T], /):
        """
        Create a new instance by absorbing the state of the given future.

        Parameters
        ----------
        future
            The future to absorb the state from.

        Returns
        -------
        FutureState[T]
        """

        if not future.done():
            return cls.new_pending()

        if future.cancelled():
            return cls.new_cancelled()

        if (exception := future.exception()) is not None:
            return cls.new_failed(exception)

        return cls.new_success(future.result())

    @classmethod
    async def absorb_awaitable(cls, awaitable: Awaitable[T], /):
        """
        Create a new instance by absorbing the state of the given awaitable.

        Parameters
        ----------
        awaitable
            The awaitable to absorb the state from.

        Returns
        -------
        FutureState[T]
        """

        try:
            result = await awaitable
        except asyncio.CancelledError:
            return cls.new_cancelled()
        except BaseException as e:
            return cls.new_failed(e)
        else:
            return cls.new_success(result)

    @classmethod
    def absorb_lambda[**P](cls, func: Callable[P, T], *args: P.args, **kwargs: P.kwargs):
        """
        Create a new instance by absorbing the outcome of calling the given
        function with the provided arguments.

        Parameters
        ----------
        func
            The function to call.
        *args
            Positional arguments to pass to the function.
        **kwargs
            Keyword arguments to pass to the function.

        Returns
        -------
        FutureState[T]
        """

        try:
            result = func(*args, **kwargs)
        except asyncio.CancelledError:
            return cls.new_cancelled()
        except BaseException as e:
            return cls.new_failed(e)
        else:
            return cls.new_success(result)


__all__ = [
    "FutureState",
]
