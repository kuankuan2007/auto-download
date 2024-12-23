import tkinter as tk
from tkinter import ttk
from . import download


class PartProgress(tk.Canvas):
    _task: download.Task
    _refreshPerSecond: int
    _showPartStartLine: bool

    def __init__(
        self,
        task: download.Task,
        *args,
        refreshPerSecond=2,
        showPartStartLine: bool = True,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self._task = task
        self._refreshPerSecond = refreshPerSecond
        self._showPartStartLine = showPartStartLine
        self.after(0, self.update)

    def update(self):
        self.after(1000 // self._refreshPerSecond, self.update)
        if self._task.progress.total is None:
            return
        width = self.winfo_width()
        height = self.winfo_height()

        scale = width / self._task.progress.total

        for part in self._task.partList:
            if part.total == None:
                continue
            self.create_rectangle(
                part.start * scale,
                1,
                (part.start + part.progress.now) * scale,
                height - 1,
                fill="green",
                width=0,
            )
            if self._showPartStartLine:
                self.create_line(
                    part.start * scale,
                    1,
                    part.start * scale,
                    height - 1,
                    fill="black",
                    width=1,
                )


class DownloadProgress(tk.Frame):
    _partProg: tk.Canvas
    _prog: ttk.Progressbar
    _progLabel: tk.Label
    _percentLabel: tk.Label
    _speedLabel: tk.Label
    _speedText: tk.StringVar
    _percentText: tk.StringVar
    _progText: tk.StringVar

    def __init__(
        self,
        task: download.Task,
        master=None,
        length=300,
        labelArgs: dict | None = None,
        progArgs: dict | None = None,
        partProgressArgs: dict | None = None,
        **kwargs
    ):
        super().__init__(
            master,
            **{
                "border": 1,
                "borderwidth": 1,
                "relief": "solid",
                "padx": 5,
                "pady": 5,
                **kwargs,
            }
        )

        self._length = length

        self.task = task

        self._speedText = tk.StringVar(self, value="0B/s")
        self._percentText = tk.StringVar(self, value="0%")
        self._progText = tk.StringVar(self, value="0/Unknown")

        self._prog = ttk.Progressbar(
            self,
            **{
                "orient": "horizontal",
                "length": self._length,
                "mode": "indeterminate",
                **(progArgs or {}),
            }
        )
        self._prog.start()

        self._prog.grid(row=0, column=0, sticky="nsew", columnspan=3)

        self._partProg = PartProgress(
            task,
            self,
            background="white",
            border=1,
            relief="solid",
            **{
                "width": self._length,
                "height": 20,
                **(partProgressArgs or {}),
            }
        )
        self._partProg.grid(row=1, column=0, sticky="nsew", columnspan=3)

        self._progLabel = tk.Label(
            self,
            **{
                "textvariable": self._progText,
                "font": ("Arial", 10),
                "justify": "left",
                **(labelArgs or {}),
            }
        )
        self._progLabel.grid(row=2, column=0, sticky="nw")
        self._percentLabel = tk.Label(
            self,
            **{
                "textvariable": self._percentText,
                "font": ("Arial", 10),
                "justify": "right",
                **(labelArgs or {}),
            }
        )
        self._percentLabel.grid(row=2, column=1, sticky="ne")
        self._speedLabel = tk.Label(
            self,
            **{
                "textvariable": self._speedText,
                "font": ("Arial", 10),
                "justify": "center",
                **(labelArgs or {}),
            }
        )
        self._speedLabel.grid(row=2, column=2, sticky="ne")

        task.progress.addListener(self.progListener)

    def progListener(self, prog: download.progress.Progress):

        self._speedText.set(self.task.progress.shower.speed)
        self._progText.set(self.task.progress.shower.prog)
        self._percentText.set(self.task.progress.shower.percent)

        if prog.total is None:
            self._prog.configure(mode="indeterminate")
            return
        self._prog.configure(mode="determinate", maximum=prog.total, value=prog.now)

        self.update()
