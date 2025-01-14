from .pools import Pool
from .unit import Unit, TaskCallback
from .download import TaskConfig, TaskResult
from .adapters import Adapter

defaultPools = Pool()
defaultUnit = Unit(defaultPools)


def rawRequest(taskConfig: TaskConfig) -> TaskResult:
    return defaultUnit.rawRequest(taskConfig)


def request(taskConfig: TaskConfig) -> None:
    return defaultUnit.request(taskConfig)


def callbackRequest(
    taskConfig: TaskConfig,
    callback: TaskCallback,
) -> None:
    return defaultUnit.callbackRequest(taskConfig, callback)


def asyncRequest(taskConfig: TaskConfig):
    return defaultUnit.asyncRequest(taskConfig)


__all__ = [
    "rawRequest",
    "request",
    "callbackRequest",
    "asyncRequest",
    "Adapter",
    "Pool",
    "Unit",
    "TaskCallback",
    "TaskConfig",
    "TaskResult",
]

__version__ = "0.1.1"
