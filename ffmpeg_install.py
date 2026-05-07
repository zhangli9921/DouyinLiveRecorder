# -*- coding: utf-8 -*-

"""
Author: Hmily
GitHub: https://github.com/ihmily
Copyright (c) 2024 by Hmily, All Rights Reserved.

学习提示：
这个文件只负责一件事：确认 ffmpeg 是否能用；不能用时，尝试按系统自动安装。
直播录制真正依赖的是 ffmpeg 命令行工具，Python 代码只是负责生成命令、启动进程、观察结果。
"""

import os
import re
import subprocess
import sys
import platform
import zipfile
from pathlib import Path
import requests
from tqdm import tqdm
from src.logger import logger

# 当前系统名称：Windows / Linux / Darwin(macOS)。后面会根据它选择安装方式。
current_platform = platform.system()

# 程序启动目录。打包成 exe 后，sys.argv[0] 仍然能帮助定位程序所在目录。
execute_dir = os.path.split(os.path.realpath(sys.argv[0]))[0]

# 保存原始 PATH，后面会把项目内 ffmpeg 目录拼到前面。
current_env_path = os.environ.get('PATH')

# Windows 自动下载后，ffmpeg 会被解压到这个目录。
ffmpeg_path = os.path.join(execute_dir, 'ffmpeg')


def unzip_file(zip_path: str | Path, extract_to: str | Path, delete: bool = True) -> None:
    """解压 zip 文件，可选解压后删除源 zip。"""

    if not os.path.exists(extract_to):
        os.makedirs(extract_to)

    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)

    if delete and os.path.exists(zip_path):
        os.remove(zip_path)


def get_lanzou_download_link(url: str, password: str | None = None) -> str | None:
    """从蓝奏云分享页解析真实下载地址。

    注意：这类网盘页面结构变化后，正则可能失效；所以这里必须包 try/except。
    """

    try:
        # 模拟浏览器请求，减少被网盘页面拒绝的概率。
        headers = {
            'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
            'Origin': 'https://wweb.lanzouv.com',
            'Referer': 'https://wweb.lanzouv.com/iXncv0dly6mh',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0',
        }
        response = requests.get(url, headers=headers)

        # 页面里会生成一个 sign 字段，后续 AJAX 请求需要它。
        sign = re.search("var skdklds = '(.*?)';", response.text).group(1)
        data = {
            'action': 'downprocess',
            'sign': sign,
            'p': password,
            'kd': '1',
        }
        response = requests.post('https://wweb.lanzouv.com/ajaxm.php', headers=headers, data=data)
        json_data = response.json()

        # ajax 返回 dom + url，拼成临时下载地址，再请求一次拿最终跳转后的 URL。
        download_url = json_data['dom'] + "/file/" + json_data['url']
        response = requests.get(download_url, headers=headers)
        return response.url
    except Exception as e:
        logger.error(f"Failed to obtain ffmpeg download address. {e}")


def install_ffmpeg_windows():
    """Windows 下自动下载并解压项目内置 ffmpeg。"""

    try:
        logger.warning("ffmpeg is not installed.")
        logger.debug("Installing the latest version of ffmpeg for Windows...")
        ffmpeg_url = get_lanzou_download_link('https://wweb.lanzouv.com/iHAc22ly3r3g', 'eots')
        if ffmpeg_url:
            full_file_name = 'ffmpeg_latest_build_20250124.zip'
            version = 'v20250124'
            zip_file_path = Path(execute_dir) / full_file_name
            if Path(zip_file_path).exists():
                logger.debug("ffmpeg installation file already exists, start install...")
            else:
                # stream=True 表示边下载边写文件，不把整个压缩包一次性塞进内存。
                response = requests.get(ffmpeg_url, stream=True)
                total_size = int(response.headers.get('Content-Length', 0))
                block_size = 1024

                # tqdm 是进度条库，纯粹为了让用户看到下载进度。
                with tqdm(total=total_size, unit="B", unit_scale=True,
                          ncols=100, desc=f'Downloading ffmpeg ({version})') as t:
                    with open(zip_file_path, 'wb') as f:
                        for data in response.iter_content(block_size):
                            t.update(len(data))
                            f.write(data)

            unzip_file(zip_file_path, execute_dir)

            # 临时修改当前进程 PATH，让下面的 subprocess.run 能找到 ffmpeg。
            os.environ['PATH'] = ffmpeg_path + os.pathsep + current_env_path
            result = subprocess.run(["ffmpeg", "-version"], capture_output=True)
            if result.returncode == 0:
                logger.debug('ffmpeg installation was successful')
            else:
                logger.error('ffmpeg installation failed. Please manually install ffmpeg by yourself')
            return True
        else:
            logger.error("Please manually install ffmpeg by yourself")
    except Exception as e:
        logger.error(f"type: {type(e).__name__}, ffmpeg installation failed {e}")


def install_ffmpeg_mac():
    """macOS 下使用 Homebrew 安装 ffmpeg。"""

    logger.warning("ffmpeg is not installed.")
    logger.debug("Installing the stable version of ffmpeg for macOS...")
    try:
        result = subprocess.run(["brew", "install", "ffmpeg"], capture_output=True)
        if result.returncode == 0:
            logger.debug('ffmpeg installation was successful. Restart for changes to take effect.')
            return True
        else:
            logger.error("ffmpeg installation failed")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to install ffmpeg using Homebrew. {e}")
        logger.error("Please install ffmpeg manually or check your Homebrew installation.")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")


def install_ffmpeg_linux():
    """Linux 下优先尝试 yum，失败后再尝试 apt。"""

    is_RHS = True

    try:
        logger.warning("ffmpeg is not installed.")
        logger.debug("Trying to install the stable version of ffmpeg")

        # yum 常见于 CentOS/RHEL 系。
        result = subprocess.run(['yum', '-y', 'update'], capture_output=True)
        if result.returncode != 0:
            logger.error("Failed to update package lists using yum.")
            return False

        result = subprocess.run(['yum', 'install', '-y', 'ffmpeg'], capture_output=True)
        if result.returncode == 0:
            logger.debug("ffmpeg installation was successful using yum. Restart for changes to take effect.")
            return True
        logger.error(result.stderr.decode('utf-8').strip())
    except FileNotFoundError:
        # 没有 yum，大概率是 Debian/Ubuntu 系，继续尝试 apt。
        logger.debug("yum command not found, trying to install using apt...")
        is_RHS = False
    except Exception as e:
        logger.error(f"An error occurred while trying to install ffmpeg using yum: {e}")

    if not is_RHS:
        try:
            logger.debug("Trying to install the stable version of ffmpeg for Linux using apt...")
            result = subprocess.run(['apt', 'update'], capture_output=True)
            if result.returncode != 0:
                logger.error("Failed to update package lists using apt")
                return False

            result = subprocess.run(['apt', 'install', '-y', 'ffmpeg'], capture_output=True)
            if result.returncode == 0:
                logger.debug("ffmpeg installation was successful using apt. Restart for changes to take effect.")
                return True
            else:
                logger.error(result.stderr.decode('utf-8').strip())
        except FileNotFoundError:
            logger.error("apt command not found, unable to install ffmpeg. Please manually install ffmpeg by yourself")
        except Exception as e:
            logger.error(f"An error occurred while trying to install ffmpeg using apt: {e}")
    logger.error("Manual installation of ffmpeg is required. Please manually install ffmpeg by yourself.")
    return False


def install_ffmpeg() -> bool:
    """按操作系统分发到对应安装函数。"""

    if current_platform == "Windows":
        return install_ffmpeg_windows()
    elif current_platform == "Linux":
        return install_ffmpeg_linux()
    elif current_platform == "Darwin":
        return install_ffmpeg_mac()
    else:
        logger.debug(f"ffmpeg auto installation is not supported on this platform: {current_platform}. "
                     f"Please install ffmpeg manually.")
    return False


def ensure_ffmpeg_installed(func):
    """装饰器：执行被装饰函数前，先确保 ffmpeg 可用。"""

    def wrapper(*args, **kwargs):
        try:
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True)
            version = result.stdout.strip()
            if result.returncode == 0 and version:
                return func(*args, **kwargs)
        except FileNotFoundError:
            pass
        return False

    def wrapped_func(*args, **kwargs):
        # 这里 Python 3.7 前后逻辑一致，保留判断可能是历史兼容遗留。
        if sys.version_info >= (3, 7):
            res = wrapper(*args, **kwargs)
        else:
            res = wrapper(*args, **kwargs)
        if not res:
            install_ffmpeg()
            res = wrapper(*args, **kwargs)

        if not res:
            raise RuntimeError("ffmpeg is not installed.")

        return func(*args, **kwargs)

    return wrapped_func


def check_ffmpeg_installed() -> bool:
    """只检查 ffmpeg，不尝试安装。"""

    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True)
        version = result.stdout.strip()
        if result.returncode == 0 and version:
            return True
    except FileNotFoundError:
        pass
    except OSError as e:
        print(f"OSError occurred: {e}. ffmpeg may not be installed correctly or is not available in the system PATH.")
        print("Please delete the ffmpeg and try to download and install again.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    return False


def check_ffmpeg() -> bool:
    """项目启动时调用：没有 ffmpeg 就自动安装，有则直接返回 True。"""

    if not check_ffmpeg_installed():
        return install_ffmpeg()
    return True
