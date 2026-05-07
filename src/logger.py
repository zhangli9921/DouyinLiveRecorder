# -*- coding: utf-8 -*-
"""日志模块。

学习提示：
- 这个项目用 loguru 统一管理日志，而不是到处 print。
- 这里配置了三类输出：控制台、错误/调试日志文件、直播流地址日志文件。
- `enqueue=True` 适合多线程场景，会把日志写入放入队列，减少线程之间抢写日志文件的问题。
"""

import os
import sys
from loguru import logger

# loguru 默认自带一个 stderr 输出；先移除，避免日志重复打印。
logger.remove()

# 控制台日志格式：时间是绿色，日志等级和消息按等级着色。
custom_format = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> - <level>{message}</level>"

# 第一组输出：打印到终端，方便运行时观察状态。
logger.add(
    sink=sys.stderr,
    format=custom_format,
    level="DEBUG",
    colorize=True,
    enqueue=True
)

# 项目运行目录，用来拼接 logs 目录。
script_path = os.path.split(os.path.realpath(sys.argv[0]))[0]

# 第二组输出：保存 DEBUG/WARNING/ERROR 等非 INFO 日志，主要用于排查错误。
logger.add(
    f"{script_path}/logs/streamget.log",
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
    # 过滤掉 INFO，只保留调试和异常类日志。
    filter=lambda i: i["level"].name != "INFO",
    serialize=False,
    enqueue=True,
    retention=1,
    rotation="300 KB",
    encoding='utf-8'
)

# 第三组输出：只保存 INFO 日志。项目里通常把解析到的直播流地址写到这里。
logger.add(
    f"{script_path}/logs/PlayURL.log",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {message}",
    # 只接收 INFO，跟 streamget.log 分开，查播放地址更干净。
    filter=lambda i: i["level"].name == "INFO",
    serialize=False,
    enqueue=True,
    retention=1,
    rotation="300 KB",
    encoding='utf-8'
)
