import contextlib
from threading import Lock
from typing import Callable


@contextlib.contextmanager
def ResourceFactory[T](generate: Callable[[], T], /):
    instance = ResourceFactoryInstance(generate)
    yield instance
    assert len(instance._unused_resources) == len(instance._resources)

class ResourceFactoryInstance[T]:
    def __init__(self, generate: Callable[[], T], /):
        self._generate = generate
        self._resources = dict[int, T]()
        self._unused_resources = set[int]()
        self._lock = Lock()

    def __enter__(self):
        with self._lock:
            if self._unused_resources:
                resource_id = self._unused_resources.pop()
            else:
                resource_id = len(self._resources)
                self._resources[resource_id] = self._generate()

            return self._resources[resource_id]

    def __exit__(self, exc_type, exc_value, traceback):
        with self._lock:
            # TODO: Problem here, how to we known which resource is unused
            self._unused_resources.add(0)


# async def example():
#     with ResourceFactory(lambda: 3) as factory:
#         with factory as obj:
#             use(obj)
