"""src 包初始化入口。

学习提示：
- Python 导入 `src` 包时，会先执行这个文件。
- 这里主要做两件事：定位 JavaScript 解密脚本目录；把内置 node 目录加入 PATH。
- 最后一行 `check_node()` 会检查 Node.js 环境，因为部分平台签名算法需要执行 JS。
"""

import os
import sys
from pathlib import Path
from .initializer import check_node

# 当前文件的绝对路径，例如：.../src/__init__.py
current_file_path = Path(__file__).resolve()

# src 目录路径，后续拼接 javascript 子目录会用到。
current_dir = current_file_path.parent

# JS_SCRIPT_PATH 会被 room.py、spider.py 等模块引用，用来读取 x-bogus、签名等 JS 文件。
JS_SCRIPT_PATH = current_dir / 'javascript'

# sys.argv[0] 通常是启动脚本路径；这里取项目运行目录，保证打包/直接运行时都能定位资源。
execute_dir = os.path.split(os.path.realpath(sys.argv[0]))[0]

# 项目可能自带 node 目录，把它拼进 PATH 后，子进程就能直接调用 node。
node_execute_dir = Path(execute_dir) / 'node'

# 保存系统原来的 PATH，避免覆盖用户已有环境变量。
current_env_path = os.environ.get('PATH')

# 将项目 node 目录放到 PATH 最前面：优先使用项目内 node，其次才用系统 node。
os.environ['PATH'] = str(node_execute_dir) + os.pathsep + current_env_path

# 导入包时立即检查 Node.js 是否可用；如果不可用，initializer 里会尝试安装或提示。
check_node()
