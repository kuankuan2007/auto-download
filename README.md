# auto-download

A simple, efficient, general-purpose Python multithreaded download library.

## Installation

```bash
pip install autoDownload
```

## Usage

### Basic Usage

#### In Program

```python
import autoDownload

taskConfig = autoDownload.TaskConfig(
    url='https://example.com/', # download url
    file='example.zip', # save path
    method='GET', # download method, default is 'GET'
    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.142.86 Safari/537.36'}, # download headers, default is {}
    **kwargs
)

# It will block the current thread until it completes
autoDownload.request(taskConfig)

# It will return an awaitable object (see https://docs.python.org/3.13/library/asyncio-task.html#awaitables), which is useful in asynchronous programming
autoDownload.asyncRequest(taskConfig)

# It will return nothing, and when it completes, the callback function will be called. This is useful in functional programming
autoDownload.callbackRequest(taskConfig, callback)

```

#### In Command Line

```bash
auto-download [-h] [-f FILE] [-m MAX] [-r RETRY] [-H HEADER] Url
```

For more information, see:

```bash
auto-download -h
```

### Advanced Usage

#### Customize how tasks are waiting

```python

# It will return a TaskResult object.
res=autoDownload.rawRequest(taskConfig)

# res.event is a threading.Event object, which can be used to wait for the task to complete.
res.event.wait()

# res.ok is a bool object, which indicates whether the task was successful.
if res.ok:
    # res.task is a autoDownload.download.Task object, which is the main controller for the task.
    print(f"Task{res.task.identity} completed successfully!")

else:
    # res.err is a TaskError object, which indicates the reason for the failure.
    raise res.err

```

### Customize the threading pool or the adapter

```python

# You can customize almost everything in the threading pool or the adapter
adapter=autoDownload.adapters.Adapter()
pool=autoDownload.pools.Pool(maxThread=10, adapter=adapter)
unit=autoDownload.unit.Unit(pool)

unit.request(taskConfig)
```

### Show the progress of the download in the command line

```python
progress=autoDownload.progress.DownloadProgress(
    task1, task2, task3,
    showTotal=True, # show the total progress
    showParts=True, # show the progress of each part
    showMerge=True, # show the progress of the merge
)
with progress:
    while True:
        progress.refresh()
        time.sleep(0.5)
```

## License

The Project is released under the [Mulan Public License 2.0](./LICENSE).
