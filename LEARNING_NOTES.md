# DouyinLiveRecorder 学习笔记

这个分支的目标不是改功能，而是把项目结构和关键模块加上学习型注释，方便顺着代码读。

## 推荐阅读顺序

1. `LEARNING_NOTES.md`：先看整体地图，别一头扎进大文件里迷路。
2. `demo.py`：单个平台解析函数的最小测试入口。
3. `src/__init__.py`：理解项目启动时如何定位 JS 脚本和 Node 环境。
4. `src/logger.py`：理解日志怎么分流到控制台、错误日志、播放地址日志。
5. `ffmpeg_install.py`：理解为什么录制离不开 ffmpeg，以及项目如何自动检查/安装。
6. `src/proxy.py`：理解系统代理检测逻辑。
7. `src/room.py`：理解抖音房间 ID、sec_user_id、web_rid、X-Bogus 的关系。
8. `src/utils.py`：理解通用工具函数，比如代理处理、URL 参数解析、文件遍历、emoji 清理。
9. `src/initializer.py`：理解 Node.js 自动检查/安装逻辑。
10. `main.py`：最后看主流程。它体量大，建议按函数块读，不要从第一行硬啃到最后一行。

## 项目主链路

```text
读取配置/直播间列表
        ↓
判断平台和直播间状态
        ↓
解析真实直播流地址
        ↓
调用 ffmpeg 或直接下载流
        ↓
保存文件、分段、转码、推送通知、循环监控
```

对应到代码，大致是：

- `main.py`：调度中心，负责读配置、循环监控、启动录制线程、调用 ffmpeg、处理停止和清理。
- `src/spider.py`：平台页面/API 请求，负责拿到原始直播间数据。
- `src/stream.py`：从原始数据里挑出可录制的直播流地址。
- `ffmpeg_install.py`：保证录制工具 ffmpeg 可用。
- `msg_push.py`：直播状态推送，比如钉钉、邮箱、Telegram、Bark 等。

## main.py 怎么读

`main.py` 很大，别按小说读，按模块读：

### 1. 全局变量区

开头定义了大量全局变量，例如：

- `recording`：当前正在录制的直播名称集合。
- `running_list`：正在运行监控/录制的 URL。
- `url_comments`：被注释掉的 URL。
- `config_file` / `url_config_file`：配置文件路径。
- `default_path`：默认下载目录。

这类变量是整个脚本的共享状态。优点是写起来直接，缺点是流程复杂后容易互相影响。

### 2. 显示状态与文件更新

重点看：

- `display_info()`：循环刷新控制台，展示监控数量、录制数量、错误数等。
- `update_file()`：修改配置文件中的某一行。
- `delete_line()`：从配置文件删除某一行。

这部分主要是运行状态可视化和配置文件维护。

### 3. ffmpeg 相关处理

重点看：

- `get_startup_info()`：Windows 下隐藏子进程窗口。
- `segment_video()`：用 ffmpeg 分段。
- `converts_mp4()`：转成 MP4。
- `converts_m4a()`：提取音频。
- `check_subprocess()`：启动并监控 ffmpeg 录制进程。

这里是录制器真正落地成文件的地方。只要理解 ffmpeg 命令数组怎么拼，就能看懂一大半。

### 4. 直播解析和录制主循环

重点看：

- `start_record()`：主战场。它根据 URL 判断平台，然后调用 `spider` 和 `stream` 里的函数拿直播流地址，再启动录制。
- `select_source_url()`：抖音/TikTok 优先 FLV，特殊情况回退 HLS。
- `direct_download_stream()`：不用 ffmpeg，直接用 HTTP 下载流。

`start_record()` 很长，但结构其实是重复的：

```text
if 是抖音:
    调抖音解析函数
elif 是快手:
    调快手解析函数
elif 是 B 站:
    调 B 站解析函数
...
```

它看起来像森林，其实是一排岔路牌。

### 5. 推送和清理

重点看：

- `push_message()`：按配置把开播/状态消息推到不同平台。
- `clear_record_info()`：录制停止后清理内存里的状态。

这部分的目标是别让状态脏掉。直播录制这种循环程序，最怕状态不清，时间一长就开始玄学。

## 你学习时可以盯住这几个关键词

- `asyncio.run(...)`：把异步函数放到同步流程里执行。
- `threading.Thread(...)`：每个直播间/转码/字幕生成都可能单独开线程。
- `subprocess.Popen(...)`：启动 ffmpeg 这种外部命令。
- `httpx.AsyncClient(...)`：异步请求网页/API。
- `configparser`：读取 ini 配置。
- `recording` / `running_list` / `url_comments`：录制状态管理三件套。

## 目前这个分支已加注释的文件

- `src/__init__.py`
- `src/logger.py`
- `src/proxy.py`
- `ffmpeg_install.py`
- `demo.py`
- `src/room.py`
- `LEARNING_NOTES.md`

## 后续继续加注释的建议

如果继续深入，下一步建议分批处理：

1. `main.py`：只给核心函数加注释，不要给每一行都加，否则会变成注释墙。
2. `src/spider.py`：按平台拆，比如先只注释抖音和快手。
3. `src/stream.py`：注释“从 JSON 数据里取流地址”的逻辑。
4. `config/config.ini`：给配置项加说明，最适合新手理解项目行为。
