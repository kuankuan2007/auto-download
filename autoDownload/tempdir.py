import abc
import pathlib
import threading
import random
import time
import hashlib
import tempfile
import shutil
from . import download


class TempDirBase(abc.ABC):
    @abc.abstractmethod
    def getPath(self, identity: str) -> pathlib.Path:
        pass

    @abc.abstractmethod
    def clear(self) -> None:
        pass


class DefaultTempDir(TempDirBase):
    __root: pathlib.Path

    def __init__(self, task: "download.Task"):
        self.__root = (
            pathlib.Path(tempfile.gettempdir())
            / "auto-downloads"
            / hashlib.md5(
                f"{time.time_ns()}-{threading.get_ident()}-{random.random()}-{task.id}".encode()
            ).hexdigest()
        )
        self.__root.mkdir(parents=True, exist_ok=True)

    def getPath(self, identity: str) -> pathlib.Path:
        return self.__root / identity

    def clear(self) -> None:
        if self.__root.exists():
            try:
                shutil.rmtree(self.__root)
            except Exception:
                pass
