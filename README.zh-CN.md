# auto-download

一个简单、高效、通用的 Python 多线程下载库。

## 安装

```bash
pip install autoDownload
```

## 使用方法

### 基本使用

#### 在程序中

```python
import autoDownload

taskConfig = autoDownload.TaskConfig(
    url='https://example.com/', # 下载链接
    file='example.zip', # 保存路径
    method='GET', # 下载方法，默认为 'GET'
    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.142.86 Safari/537.36'}, # 下载请求头，默认为空字典
    **kwargs
)

# 它会阻塞当前线程直到任务完成
autoDownload.request(taskConfig)

# 它将返回一个可等待对象（参见 https://docs.python.org/3.13/library/asyncio-task.html#awaitables），在异步编程中有用
autoDownload.asyncRequest(taskConfig)

# 它将不会返回任何内容，当任务完成时，回调函数将被调用。这在函数式编程中有用
autoDownload.callbackRequest(taskConfig, callback)
```

#### 在命令行中

```bash
auto-download [-h] [-f FILE] [-m MAX] [-r RETRY] [-H HEADER] Url
```

更多信息，请参阅：

```bash
auto-download -h
```

### 高级使用

#### 自定义任务等待方式

```python

# 它将返回一个 TaskResult 对象。
res = autoDownload.rawRequest(taskConfig)

# res.event 是一个 threading.Event 对象，可用于等待任务完成。
res.event.wait()

# res.ok 是一个bool值，指示任务是否成功。
if res.ok:
    # res.task 是一个 autoDownload.download.Task 对象，是任务的主要控制器。
    print(f"Task{res.task.identity} 成功完成！")

else:
    # res.err 是一个 TaskError 对象，指示失败的原因。
    raise res.err
```

#### 自定义线程池或适配器

```python

# 您可以自定义线程池或适配器中的几乎所有内容
adapter = autoDownload.adapters.Adapter()
pool = autoDownload.pools.Pool(maxThread=10, adapter=adapter)
unit = autoDownload.unit.Unit(pool)

unit.request(taskConfig)
```

#### 在命令行中显示下载进度

```python
progress = autoDownload.progress.DownloadProgress(
    task1, task2, task3,
    showTotal=True, # 显示总进度
    showParts=True, # 显示每个部分的进度
    showMerge=True, # 显示合并进度
)
with progress:
    while True:
        progress.refresh()
        time.sleep(0.5)
```

## 许可证

该项目根据 [Mulan Public License 2.0](./LICENSE) 发布。
