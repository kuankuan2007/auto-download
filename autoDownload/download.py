from dataclasses import dataclass, field
from pathlib import Path
import typing
from . import pools, adapters, progress, tempdir
import io
import math
import threading
from exceptiongroup import ExceptionGroup

_nowTaskIndexLock = threading.Lock()
_nowTaskIndex = 0

StatusChecker = typing.Callable[["Part", adapters.Response], None | Exception]

RequestMethod = typing.Literal[
    "GET", "POST", "PUT", "DELETE", "OPTIONS", "TRACE", "PATCH"
]

IO_PART_SIZE = 1024 * 4  # 4kb


class TrashBufferedWriter(io.BufferedWriter):
    """
    A BufferedWriter that discards all data written to it.
    """

    def __init__(self):
        super().__init__(io.BytesIO())  # type: ignore

    def write(self, b):
        return len(b)

    def flush(self) -> None:
        pass

    def close(self) -> None:
        pass


def defaultStatusIsAccepted(_part: "Part", res: adapters.Response) -> None | Exception:
    try:
        res.raise_for_status()
        return None
    except Exception as e:
        return e


@dataclass
class TaskConfig:
    url: str  # the url to download
    file: str | Path
    method: RequestMethod = "GET"
    headers: dict[str, str] = field(default_factory=dict)
    retry: int | None = 3
    timeout: int | typing.Tuple[int, int] | None = (10, 3)
    minimumChunkSize: int = 1024 * 1024 * 4  # 4mb
    params: dict[str, str] | None = None
    data: typing.Any = None
    allow_redirects: bool = True
    proxies: typing.Any = None
    verify: bool = True
    cert: str | None = None
    statusIsAccepted: StatusChecker = defaultStatusIsAccepted
    tryResult: "TryResult | None" = None
    tempDirFactory: typing.Callable[["Task"], tempdir.TempDirBase] = (
        tempdir.DefaultTempDir
    )


@dataclass
class PartRequestConfig:
    method: str
    url: str
    params: dict[str, str] | None
    data: typing.Any
    timeout: int | typing.Tuple[int, int] | None
    allow_redirects: bool
    proxies: typing.Any
    verify: bool
    cert: str | None = None
    headers: dict[str, str | None] = field(default_factory=dict)

    @staticmethod
    def fromTask(task: "Task", part: "Part"):
        return PartRequestConfig(
            method=task.config.method,
            url=task.config.url,
            params=task.config.params,
            data=task.config.data,
            headers={
                **task.config.headers,
                "Range": (
                    f"bytes={part.start}-{part.start+part.total}"
                    if part.total
                    else None
                ),
            },
            timeout=task.config.timeout,
            allow_redirects=task.config.allow_redirects,
            proxies=task.config.proxies,
            verify=task.config.verify,
            cert=task.config.cert,
        )


class Part:
    _start: int
    _total: int | None
    _isHeader: bool
    _task: "Task"
    _progress: "progress.Progress"
    _res: adapters.Response | None = None
    _writer: io.BufferedWriter
    downloadThread: threading.Thread | None = None
    retryNum: int

    def __init__(self, start: int, total: int | None, task: "Task", retryNum: int = 0):
        self._start = start
        self._total = total
        self._task = task
        self._progress = progress.Progress(
            now=0, total=total, parent=self._task._progress
        )
        self._writer = self._getWriter()
        self.retryNum = retryNum

    def _getWriter(self) -> io.BufferedWriter:
        return self.task.getWriter(self.identity)

    def request(self, adapter: adapters.Adapter, config: PartRequestConfig):
        return adapter.request(
            method=config.method,
            url=config.url,
            params=config.params,
            data=config.data,
            headers=config.headers,
            timeout=config.timeout,
            allow_redirects=config.allow_redirects,
            proxies=config.proxies,
            stream=True,
            verify=config.verify,
            cert=config.cert,
        )

    def do(self, adapter: adapters.Adapter):
        self.downloadThread = threading.current_thread()
        try:
            config = self._task.config
            self._res = self.request(
                adapter, PartRequestConfig.fromTask(self._task, self)
            )

            isAccepted = config.statusIsAccepted(self, self._res)
            if isAccepted is not None:
                raise isAccepted

            with self._writer as f:
                for chunk in self._res.iter_content(IO_PART_SIZE):
                    f.write(chunk)
                    self._progress.update(len(chunk))
                    if (
                        self._total is not None
                        and self._progress.now >= self._total
                        or self.task.cancelFlag
                    ):
                        self._res.close()
                        break
        except Exception as e:
            self._writer.close()
            try:
                raise PartDownloadFailError(self, 0) from e
            except PartDownloadFailError as err:
                self.onError(err)
        else:
            self._writer.close()
            self.progress.finish()
            self.onFinish()

    def onError(self, err: "PartDownloadFailError"):
        self.task.onPartError(self, err)

    def onFinish(self):
        self.progress.finish()
        self.task.onPartFinish(self)

    def split(self, place: int):
        if self.total is None:
            raise Exception("Cannot split a non-rangeable part")
        if place >= self.total:
            return Part(self.start + self.total, 0, self.task)
        newPart = Part(
            self._start + place,
            self.total - place,
            self.task,
        )
        self._total = place
        self._progress.setTotal(place)
        return newPart

    @property
    def start(self):
        return self._start

    @property
    def total(self):
        return self._total

    @property
    def task(self):
        return self._task

    @property
    def progress(self):
        return self._progress

    def __str__(self) -> str:
        return f"Part<{self.start}-len:{self.total}>"

    def __repr__(self) -> str:
        return self.__str__()

    @property
    def identity(self) -> str:
        return str(self.start)

    def retry(self):
        self.progress.cancel()
        return Part(self.start, self.total, self.task, retryNum=self.retryNum + 1)


class TryConnectPart(Part):
    def __init__(self, task: "Task"):
        super().__init__(0, None, task)

    def _getWriter(self) -> io.BufferedWriter:
        return TrashBufferedWriter()

    def split(self, place: int):
        raise RuntimeError("Cannot split a try connect part")

    @property
    def identity(self) -> str:
        return "TryConnect"

    def request(self, adapter: adapters.Adapter, config: PartRequestConfig):
        config.method = "head"
        return super().request(adapter, config)

    def onFinish(self):
        assert self._res
        self.progress.finish()
        self.task.onTryRequest(self._res)

    def __str__(self) -> str:
        return f"<TryConnectPart of {self.task}>"

    def __repr__(self) -> str:
        return self.__str__()


class TaskError(Exception):
    pass


class PartDownloadFailError(Exception):
    """
    Exception raised when a part fails to download.
    """

    def __init__(self, part: Part, retryNum: int):
        self.part = part
        self.retryNum = retryNum

    def __str__(self):
        return f"The {self.part} was failed after {self.retryNum} retries."

    def __repr__(self):
        return self.__str__()


class TaskDownloadFailError(ExceptionGroup, TaskError):
    @staticmethod
    def getMessage(task: "Task"):
        return f"The task({task}) was failed cased by the following errors"

    def __new__(cls, task: "Task", errList: typing.List[PartDownloadFailError]):
        return super().__new__(cls, TaskDownloadFailError.getMessage(task), errList)

    def __init__(self, task: "Task", errList: typing.List[PartDownloadFailError]):
        self.task = task
        self.errList = errList
        super().__init__(TaskDownloadFailError.getMessage(task), errList)


class TaskMergeFailError(TaskError):
    def __init__(self, task: "Task", s: str):
        self.task = task
        super().__init__(f"The task({task}) was failed to merge: {s}")


@dataclass
class TryResult:
    length: int | None


@dataclass
class TaskResult:
    event: threading.Event
    ok: bool
    err: None | TaskError
    task: "Task"


class Task:
    config: TaskConfig
    _pool: "pools.Pool | None " = None
    _partList: typing.List[Part]
    _tryResult: TryResult | None
    _progress: "progress.Progress"
    _mergeProgress: "progress.Progress | None" = None

    _errList: typing.List[PartDownloadFailError]
    __multiTreadStartedFlag: bool = False
    _taskResult: TaskResult
    _splitLock: threading.Lock
    id: int
    cancelFlag: bool = False
    _tempDir: tempdir.TempDirBase

    def __init__(self, taskConfig: TaskConfig):
        global _nowTaskIndex
        self.config = taskConfig
        self._tryResult = taskConfig.tryResult
        if taskConfig.tryResult:
            self._progress = progress.Progress(now=0, total=taskConfig.tryResult.length)
        else:
            self._progress = progress.Progress(now=0, total=None)
        self._partList = []
        self._errList = []
        self._taskResult = TaskResult(
            event=threading.Event(), ok=False, err=None, task=self
        )
        self._splitLock = threading.Lock()

        _nowTaskIndexLock.acquire()
        self.id = _nowTaskIndex
        _nowTaskIndex += 1
        _nowTaskIndexLock.release()

        self._tempDir = taskConfig.tempDirFactory(self)

    def start(self, pool: "pools.Pool"):
        if self._pool:
            return self._taskResult
        pool.runningTask.append(self)
        self._pool = pool
        if self._tryResult is None:
            self.__tryRequest()
        else:
            self.__start()
        self._taskResult.event.clear()
        return self._taskResult

    def __tryRequest(self):
        self.addPart(TryConnectPart(self))

    def downloadSpeedListener(self, prog: progress.Progress):
        assert self._pool
        if self.__multiTreadStartedFlag:
            return
        if self._tryResult is None or self._tryResult.length is None:
            return
        if len(prog.history) < 5:
            return
        remainTime = prog.remainTime
        if remainTime is None:
            return
        self.__multiTreadStartedFlag = True

        self._splitLock.acquire()
        partNum = math.floor(
            min(
                max(
                    self._tryResult.length / self.config.minimumChunkSize,
                    remainTime / 20,
                ),
                self._pool.maxThread,
            )
        )

        if partNum:
            partSize = (prog.remain or 0) // partNum

            lastPart = self._partList[-1]
            for _i in range(partNum - 1):
                lastPart = lastPart.split(
                    lastPart.progress.now + partSize,
                )
                self.addPart(lastPart)
        self._splitLock.release()

    def __start(self):
        if self._tryResult is None:
            raise Exception("Try result is None")
        self.addPart(
            Part(
                0,
                self._tryResult.length,
                self,
            )
        )
        self._progress.addListener(self.downloadSpeedListener)

    def addPart(self, part: Part):
        assert self._pool
        if part.total == 0:
            return
        self._pool.request(part)
        self._partList.append(part)

    def onPartError(self, part: Part, err: PartDownloadFailError):

        self._errList.append(err)
        if part.progress.now > 0 and part.total is not None:
            newPart = part.split(part.progress.now)
            part.progress.finish()
            self.addPart(newPart)
            return

        if self.config.retry is None or err.retryNum < self.config.retry:
            self._retryPart(part)
        else:
            self._downloadFail()

    def _retryPart(self, part: Part):
        newPart = part.retry()
        self._partList.remove(part)
        self.addPart(newPart)

    def _downloadFail(self):
        self.cancelFlag = True
        self._fail(TaskDownloadFailError(self, self._errList))

    def _end(self):
        assert self._pool
        self._pool.runningTask.remove(self)
        self._taskResult.event.set()
        self._tempDir.clear()

    def _fail(self, err: TaskError):
        self._taskResult.ok = False
        self._taskResult.err = err
        self._end()

    def _finish(self):
        self._taskResult.ok = True
        self._taskResult.err = None
        self._end()

    def searchToSplit(self, hasRest: bool):
        if (
            not hasRest
            or self._tryResult is None
            or self._tryResult.length is None
            or self.progress.remainTime is None
            or self.progress.remainTime < 5
        ):
            return False
        self._splitLock.acquire()
        for i in self._partList:
            if (
                i.progress.remain is not None
                and i.progress.remain > self.config.minimumChunkSize * 2
            ):
                place = i.progress.now + (i.progress.remain // 2)
                part = i.split(place)
                self.addPart(part)
                return True
        self._splitLock.release()
        return False

    def onPartFinish(self, _part: Part):
        assert self._tryResult
        assert self._pool

        if (
            all(i.progress.statue == "Fulfilled" for i in self._partList)
            or self.progress.statue == "Fulfilled"
        ):
            self._progress.finish()
            if self._tryResult.length:
                self._merge()
            else:
                self._finish()

    def getSavePath(self, identity: str):
        if not self._tryResult or not self._tryResult.length:
            return Path(self.config.file)
        return self._tempDir.getPath(identity)

    def getWriter(self, identity: str):
        return open(self.getSavePath(identity), "wb")

    def onTryRequest(self, res: adapters.Response):
        length: int | None = None
        rangeable: bool = False
        if res.headers.get("Content-Length"):
            try:
                length = int(res.headers.get("Content-Length"))  # type: ignore
            except Exception:
                pass
        if res.headers.get("Content-Range") != "none" and length:
            rangeable = True

        self._tryResult = TryResult(length if rangeable else None)
        self._progress.setTotal(length)
        self.__start()

    def _merge(self):
        try:
            assert self.progress.statue == "Fulfilled"
            assert self._tryResult and self._tryResult.length is not None
            self._mergeProgress = progress.Progress(now=0, total=self._tryResult.length)
            listPart = [i for i in self._partList if not isinstance(i, TryConnectPart)]
            listPart.sort(key=lambda i: i.start)
            with open(self.config.file, "wb") as saveFile:
                redundant = 0
                for i in listPart:
                    with open(
                        self.getSavePath(str(i.identity)), "rb"
                    ) as f:
                        f.seek(0, redundant)
                        total = redundant
                        redundant = 0
                        while True:
                            data = f.read(
                                IO_PART_SIZE
                                if i.total is None
                                else min(IO_PART_SIZE, i.total - total)
                            )
                            if not data:
                                break
                            self._mergeProgress.update(len(data))
                            saveFile.write(data)
                            total += len(data)
                            if i.total is not None and total >= i.total:
                                break
                    if i.total is not None and total >= i.total:
                        redundant = total - i.total
                    elif i.total is not None and total > i.total:
                        raise Exception(
                            f"The {i} saved {total} bytes in the file, but it needs to be at least {i.total} bytes"
                        )
        except Exception as e:
            try:
                raise TaskMergeFailError(self, str(e)) from e
            except TaskMergeFailError as err:
                self._fail(err)
        else:
            self._mergeProgress.finish()
            self._finish()

    @property
    def partList(self):
        return self._partList

    @property
    def progress(self):
        return self._progress

    @property
    def mergeProgress(self):
        return self._mergeProgress

    def __str__(self) -> str:
        return f"Task<{self.config.url}>"

    def __repr__(self) -> str:
        return f"Task<{self.config.url}, savePath={self.config.file}, progress={self.progress}>"
