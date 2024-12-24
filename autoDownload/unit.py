from . import download
import typing
from . import pools
import threading
import asyncio

TaskCallback = typing.Callable[[download.TaskResult], None]


class TaskControlThread(threading.Thread):
    taskConfig: download.TaskConfig
    result: download.TaskResult
    unit: "Unit"
    callback: TaskCallback

    def __init__(
        self,
        unit: "Unit",
        taskConfig: download.TaskConfig,
        callback: TaskCallback,
        daemon: bool = False,
    ) -> None:
        super().__init__(name="TaskControlThread", daemon=daemon)
        self.taskConfig = taskConfig
        self.unit = unit
        self.callback = callback

    def run(self) -> None:
        self.result = self.unit.rawRequest(self.taskConfig)
        self.result.event.wait()
        self.callback(self.result)


class Unit(object):
    __pool: pools.Pool

    def __init__(self, pool: pools.Pool) -> None:
        self.__pool = pool

    def rawRequest(self, taskConfig: download.TaskConfig):
        task = download.Task(taskConfig)
        return task.start(self.__pool)

    def request(self, taskConfig: download.TaskConfig):
        res = self.rawRequest(taskConfig)
        res.event.wait()
        if not res.ok:
            raise res.err or RuntimeError("The download task was failed.")
        return

    async def asyncRequest(
        self, taskConfig: download.TaskConfig
    ) -> typing.Awaitable[None]:
        event = asyncio.Event()
        result: download.TaskResult | None = None

        def callback(res: download.TaskResult):
            nonlocal result
            event.set()
            result = res

        self.callbackRequest(taskConfig, callback)
        
        await event.wait()
        
        assert result is not None
        if result.ok:
            return
        raise result.err or RuntimeError("The download task was failed.")

    def callbackRequest(
        self,
        taskConfig: download.TaskConfig,
        callback: TaskCallback,
        daemon: bool = False,
    ) -> None:
        TaskControlThread(self, taskConfig, callback, daemon).start()
