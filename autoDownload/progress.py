import typing
import time
from dataclasses import dataclass
import datetime

UNITS = ["B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"]


def setUnit(var: int | float):
    i = 0
    while var > 1024 * 1.5 and i < len(UNITS) - 1:
        var /= 1024
        i += 1
    return f"{var:.1f}{UNITS[i]}"


@dataclass
class _History:
    time: float
    advance: int


ProgressListener = typing.Callable[["Progress"], None]


class ProgressShowInfo(object):
    progress: "Progress"

    def __init__(self, progress: "Progress"):
        self.progress = progress

    @property
    def speed(self):
        return f"{setUnit(self.progress.speed)}/s"

    @property
    def remain(self):
        remain = self.progress.remain
        return setUnit(remain) if remain is not None else "Unknown"

    @property
    def percent(self):
        percent = self.progress.percent
        return f"{percent * 100:.2f}%" if percent is not None else "Unknown"

    @property
    def remainTime(self):
        remainTime = self.progress.remainTime
        if remainTime is None:
            return "Unknown"
        if remainTime == 0:
            return "-"
        return str(datetime.timedelta(seconds=remainTime)).split(".")[0]

    @property
    def now(self):
        return setUnit(self.progress.now)

    @property
    def total(self):
        total = self.progress.total
        return setUnit(total) if total is not None else "Unknown"

    @property
    def prog(self):
        return f"{self.now}/{self.total}"

    @property
    def statue(self):
        return self.progress.statue


class Progress(object):
    _total: int | None = 0
    _now: int = 0
    _history: typing.List[_History]
    _parent: "Progress | None"
    _statue: typing.Literal["Pending", "Fulfilled", "Cancelled"] = "Pending"
    _listeners: typing.List[ProgressListener]
    shower: ProgressShowInfo

    def __init__(self, total: int | None, now: int, parent: "Progress | None" = None):
        self._total = total
        self._now = now
        self._parent = parent
        self.shower = ProgressShowInfo(self)
        self._history=[]
        self._listeners=[]

    def update(
        self,
        advance: int | None = None,
        now: int | None = None,
    ):
        if now is not None:
            advance = now - self._now
        if advance is not None:
            if self._total is not None and self._total <= self._now + advance:
                advance = self.remain
                self.__finish()
            self._now += advance or 0
            self._history.append(_History(time=time.time(), advance=advance or 0))
            if self._parent:
                self._parent.update(advance=advance)
            self.callListeners()

    def addListener(self, listener: ProgressListener):
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    def callListeners(self):
        for listener in self._listeners:
            listener(self)

    def setTotal(self, total: int | None):
        if total and self._total and total < self._total and self._now > total:
            self.update(total - self._now)
            self.finish()
        self._total = total
        self.callListeners()

    @property
    def total(self):
        return self._total

    @property
    def now(self):
        return self._now

    @property
    def speed(self) -> float:
        while len(self._history) and time.time() - self._history[0].time > 1:  # 1s
            self._history.pop(0)
        if len(self._history) < 1:
            return 0
        return sum(h.advance for h in self._history)

    @property
    def percent(self):
        if self._statue == "Fulfilled":
            return 1
        elif self._statue == "Cancelled":
            return 0
        return self._now / self._total if self._total else None

    @property
    def remain(self):
        if self._statue != "Pending":
            return 0
        return self._total - self._now if self._total else None

    @property
    def remainTime(self):
        if self._statue != "Pending":
            return 0
        return self.remain / self.speed if self.speed and self.remain else None

    @property
    def parent(self):
        return self._parent

    @property
    def history(self):
        return self._history

    @property
    def statue(self):
        return self._statue

    def __finish(self):
        self._statue = "Fulfilled"
        self.callListeners()

    def finish(self):
        if self._statue != "Pending":
            return
        if self._total is not None and self._now != self._total:
            self.update(self.remain)
        self.__finish()

    def cancel(self):
        if self._statue != "Pending":
            return
        self.update(now=0)
        self._statue = "Cancelled"
        self.callListeners()

    def __str__(self) -> str:
        return f"Progress<{self.now}/{self.total}>"

    def __repr__(self) -> str:
        return self.__str__()

    @property
    def fields(self):
        return {
            "_now": self.shower.now,
            "_total": self.shower.total,
            "_speed": self.shower.speed,
            "_remainTime": self.shower.remainTime,
            "_percent": self.shower.percent,
            "_statue": self.shower.statue,
        }


FIELDS_INIT: typing.Dict[str, typing.Any] = {
    "_now": "0",
    "_total": "Unknown",
    "_speed": "Unknown",
    "_remainTime": "Unknown",
    "_percent": "Unknown",
    "_statue": "Pending",
}
