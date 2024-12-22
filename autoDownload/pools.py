import threading
import typing
from . import adapters, download


class DownloadThread(threading.Thread):
    event: threading.Event
    pool: "Pool"

    def __init__(self, pool: "Pool"):
        super().__init__(daemon=True)
        self.pool = pool
        self.event = threading.Event()
        self.event.set()

    def run(self):
        while True:
            part = self.pool.getPart()
            if part is None:
                self.event.clear()
                self.event.wait(timeout=2)
                if not self.event.is_set():
                    return
                continue
            part.do(self.pool.adapter)


class Pool(object):
    threadPool: typing.List[DownloadThread]
    adapter: adapters.Adapter
    maxThread: int
    _partList: typing.List[download.Part]
    partListVisitLock: threading.Lock = threading.Lock()
    threadPoolVisitLock: threading.Lock = threading.Lock()
    runningTask: typing.List[download.Task]

    def __init__(
        self, maxThread: int = 10, adapter: adapters.Adapter = adapters.Adapter()
    ):
        self.maxThread = maxThread
        self.adapter = adapter
        self.threadPool = []
        self._partList = []
        self.runningTask = []

    def request(self, part: download.Part):

        self._addPart(part)
        flag = False
        self.threadPoolVisitLock.acquire()
        
        for thread in [i for i in self.threadPool]:
            if not thread.is_alive():
                self.threadPool.remove(thread)

        for thread in self.threadPool:
            if not thread.event.is_set():
                thread.event.set()
                flag = True
                break
            

        if not flag:
            if len(self.threadPool) < self.maxThread:
                thread = DownloadThread(self)
                self.threadPool.append(thread)
                thread.start()
                flag = True

        self.threadPoolVisitLock.release()

    def _addPart(self, part: download.Part):
        self.partListVisitLock.acquire()
        self._partList.append(part)
        self.partListVisitLock.release()

    def searchNewPart(self):
        for task in self.runningTask:
            if task.searchToSplit(True):
                break

    def getPart(self):
        self.partListVisitLock.acquire()

        part: download.Part | None = None
        
        if len(self._partList) > 0:
            part = self._partList.pop(0)

        if part is None:
            self.searchNewPart()
        self.partListVisitLock.release()

        return part

    def restNum(self):
        return self.maxThread - len(self._partList) + len(self.threadPool)
