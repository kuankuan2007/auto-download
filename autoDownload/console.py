import urllib.parse
import rich.console as _console
import rich.progress as _progress
from .download import Task as DownloadTask
from .progress import FIELDS_INIT
import typing
import json
import urllib
import pathlib
from . import TaskConfig, unit, pools
import time


class DownloadProgress(_progress.Progress):
    _tracedList: typing.List[DownloadTask]
    _partToTaskMap: typing.Dict[str, _progress.TaskID]
    showTotal: bool
    showParts: bool
    showMerge: bool

    def __init__(
        self,
        *tasks: DownloadTask,
        showTotal: bool = True,
        showParts: bool = True,
        showMerge: bool = True,
        console: _console.Console | None = None,
        auto_refresh: bool = True,
        refresh_per_second: float = 3,
        speed_estimate_period: float = 30,
        transient: bool = False,
        redirect_stdout: bool = True,
        redirect_stderr: bool = True,
        get_time: typing.Callable[[], float] | None = None,
        disable: bool = False,
        expand: bool = False,
    ) -> None:
        self._tracedList = list(tasks)
        self._partToTaskMap = {}
        self.showTotal = showTotal
        self.showParts = showParts
        self.showMerge = showMerge
        super().__init__(
            *[
                _progress.TextColumn(
                    "[progress.description]{task.description}",
                ),
                _progress.BarColumn(),
                _progress.TextColumn("{task.fields[_now]}", justify="right"),
                _progress.TextColumn("/"),
                _progress.TextColumn("{task.fields[_total]}", justify="left"),
                _progress.TextColumn(
                    "{task.fields[_percent]}", style="blue", justify="right"
                ),
                _progress.TextColumn("{task.fields[_speed]}", style="green"),
                _progress.TextColumn("{task.fields[_remainTime]}", style="yellow"),
                _progress.TextColumn("{task.fields[_statue]}"),
            ],
            console=console,
            auto_refresh=auto_refresh,
            refresh_per_second=refresh_per_second,
            speed_estimate_period=speed_estimate_period,
            transient=transient,
            redirect_stdout=redirect_stdout,
            redirect_stderr=redirect_stderr,
            get_time=get_time,
            disable=disable,
            expand=expand,
        )
        if auto_refresh:
            self.refresh()

    def traceTask(self, task: DownloadTask):
        self._tracedList.append(task)

    def untraceTask(self, task: DownloadTask):
        self._tracedList.remove(task)

    def _getTaskID(self, string: str) -> _progress.TaskID:
        if string not in self._partToTaskMap:
            self._partToTaskMap[string] = self.add_task(
                description=string, **FIELDS_INIT, start=True, total=None
            )
        return self._partToTaskMap[string]

    def add_task(
        self,
        description: str,
        start: bool = True,
        total: float | None = 100,
        completed: int = 0,
        visible: bool = True,
        **fields: typing.Any,
    ) -> _progress.TaskID:
        with self._lock:
            task = _progress.Task(
                self._task_index,
                description,
                total,
                completed,
                visible=visible,
                fields=fields,
                _get_time=self.get_time,
                _lock=self._lock,
            )
            self._tasks[self._task_index] = task
            if start:
                self.start_task(self._task_index)
            new_task_index = self._task_index
            self._task_index = _progress.TaskID(int(self._task_index) + 1)
        # self.refresh()  # We disabled the auto refresh for each task-adding operation.
        return new_task_index

    def refresh(self) -> None:
        for task in self._tracedList:
            self.update(
                self._getTaskID(f"Task-{task.id}"),
                description=f"Download-{task.id}",
                total=task.progress.total,
                completed=task.progress.now,
                visible=self.showTotal,
                advance=None,
                refresh=False,
                **task.progress.fields,
            )
            if task.mergeProgress:
                self.update(
                    self._getTaskID(f"Merge-{task.id}"),
                    description=f"Merge-{task.id}",
                    total=task.mergeProgress.total,
                    completed=task.mergeProgress.now,
                    visible=self.showMerge,
                    advance=None,
                    refresh=False,
                    **task.mergeProgress.fields,
                )
            for index, part in enumerate([i for i in task.partList]):
                self.update(
                    self._getTaskID(f"Part-{task.id}-{part.identity}"),
                    description=f"Part-{task.id}-{index}",
                    total=part.progress.total,
                    completed=part.progress.now,
                    visible=self.showParts,
                    advance=None,
                    refresh=False,
                    **part.progress.fields,
                )
        return super().refresh()


def terminal():
    import argparse

    console = _console.Console()
    argparser = argparse.ArgumentParser()
    argparser.add_argument("Url", help="The URL of the file")
    argparser.add_argument(
        "-f", "--file", type=str, default="", help="The path of the file to save"
    )
    argparser.add_argument(
        "-m",
        "--max",
        type=int,
        default=10,
        help="The max number of threads to download. It has to be greater than 0",
    )
    argparser.add_argument(
        "-r",
        "--retry",
        type=int,
        default=3,
        help="Max retry times. If it's less than 0, it means infinity",
    )
    argparser.add_argument(
        "-H", "--header", type=str, default="{}", help="Header of the requests"
    )
    args = argparser.parse_args()
    headers: dict
    url: urllib.parse.ParseResult = urllib.parse.urlparse(args.Url, scheme="http")
    file: pathlib.Path
    maxThread: int = args.max if args.max > 0 else 10
    retry: int | None = args.retry if args.retry >= 0 else None
    try:
        headers = json.loads(args.header)
        assert type(headers) == dict
    except Exception:
        console.print("[yellow]Header should be a dict[/yellow]")
        return
    if args.file == "":
        _file = url.path.split("/")[-1]
    else:
        _file = args.file
    if _file == "":
        console.print(
            "[yellow]Can not get the name of the file by URL. Please set it by '-f' or '--file' manually[/yellow]"
        )
        return
    file = pathlib.Path(_file)
    _unit = unit.Unit(pools.Pool(maxThread))
    result = _unit.rawRequest(
        TaskConfig(
            url=url.geturl(),
            file=file,
            retry=retry,
            headers=headers,
        )
    )
    prog = DownloadProgress(result.task, auto_refresh=True)
    with prog:
        while not result.event.is_set():
            prog.refresh()
            time.sleep(0.1)

    if result.ok:
        console.print("[green]Download successfully[/green]")
        console.print("The file was saved at:", str(file.absolute()))
    else:
        try:
            raise result.err or RuntimeError("Unknown error")
        except Exception:
            console.print_exception()
        console.print("[red]Failed to download[/red]")
