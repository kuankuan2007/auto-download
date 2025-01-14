import urllib.parse
import rich.console as _console
import json
import urllib
import pathlib
from . import TaskConfig, unit, pools, __version__
import time
from .console import DownloadProgress


def main():
    """
    Main function to handle the download process using command-line arguments.

    Parses command-line arguments for the URL of the file to download, the file
    path to save the download, the maximum number of download threads, the
    maximum number of retry attempts, and the request headers. Validates and
    processes these inputs, initiates the download using a multi-threaded
    approach, and provides a progress display. Handles errors and exceptions
    during the download process and outputs the result to the console.
    """

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
    argparser.add_argument(
        "-v", "--version", action="version", version=f"autoDownload {__version__}"
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


if __name__ == "__main__":
    main()
