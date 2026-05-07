"""系统代理检测模块。

学习提示：
- 直播平台有些在国内外网络环境下表现不同，所以录制器需要知道当前系统是否启用了代理。
- Windows 代理信息来自注册表；Linux/macOS 常见代理信息来自环境变量。
- 这里只负责“发现代理”，真正使用代理请求直播平台的逻辑在 spider/stream/main 等模块里。
"""

import os
import sys
from enum import Enum, auto
from dataclasses import dataclass, field
from .utils import logger


class ProxyType(Enum):
    """代理协议类型枚举。

    当前文件里没有大量使用这个枚举，但它表达了项目支持的代理类型边界：HTTP、HTTPS、SOCKS。
    """

    HTTP = auto()
    HTTPS = auto()
    SOCKS = auto()


@dataclass(frozen=True)
class ProxyInfo:
    """代理地址数据结构。

    frozen=True 表示创建后不可修改，避免运行中代理地址被意外改写。
    """

    ip: str = field(default="", repr=True)
    port: str = field(default="", repr=True)

    def __post_init__(self):
        """对象创建后的校验逻辑。

        dataclass 会先自动赋值，然后调用 __post_init__；这里确保 ip/port 要么都为空，要么都有效。
        """

        # 只填 IP 或只填端口都没有意义，所以直接拒绝。
        if (self.ip and not self.port) or (not self.ip and self.port):
            raise ValueError("IP or port cannot be empty")

        # 端口必须是 1-65535 的数字，这是 TCP/UDP 端口的合法范围。
        if (self.ip and self.port) and (not self.port.isdigit() or not (1 <= int(self.port) <= 65535)):
            raise ValueError("Port must be a digit between 1 and 65535")


class ProxyDetector:
    """跨平台代理检测器。

    对外主要暴露两个方法：
    - get_proxy_info(): 返回代理 IP 和端口。
    - is_proxy_enabled(): 返回系统代理是否开启。
    """

    def __init__(self):
        # Windows 的系统代理配置在注册表里；非 Windows 则走环境变量。
        if sys.platform.startswith('win'):
            import winreg
            self.winreg = winreg
            self.__path = r'Software\Microsoft\Windows\CurrentVersion\Internet Settings'
            with winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER) as key_user:
                self.__INTERNET_SETTINGS = winreg.OpenKeyEx(key_user, self.__path, 0, winreg.KEY_ALL_ACCESS)
        else:
            self.__is_windows = False

    def get_proxy_info(self) -> ProxyInfo:
        """根据当前操作系统选择对应的代理读取方式。"""

        if sys.platform.startswith('win'):
            ip, port = self._get_proxy_info_windows()
        else:
            ip, port = self._get_proxy_info_linux()
        return ProxyInfo(ip, port)

    def is_proxy_enabled(self) -> bool:
        """判断系统层面是否开启代理。"""

        if sys.platform.startswith('win'):
            return self._is_proxy_enabled_windows()
        else:
            return self._is_proxy_enabled_linux()

    def _get_proxy_info_windows(self) -> tuple[str, str]:
        """读取 Windows 注册表中的 ProxyServer。"""

        ip, port = "", ""
        if self._is_proxy_enabled_windows():
            try:
                ip_port = self.winreg.QueryValueEx(self.__INTERNET_SETTINGS, "ProxyServer")[0]
                if ip_port:
                    # 常见格式是 127.0.0.1:7890。
                    ip, port = ip_port.split(":")
            except FileNotFoundError as err:
                logger.warning("No proxy information found: " + str(err))
            except Exception as err:
                logger.error("An error occurred: " + str(err))
        else:
            logger.debug("No proxy is enabled on the system")
        return ip, port

    def _is_proxy_enabled_windows(self) -> bool:
        """读取 Windows ProxyEnable 开关；1 表示启用。"""

        try:
            if self.winreg.QueryValueEx(self.__INTERNET_SETTINGS, "ProxyEnable")[0] == 1:
                return True
        except FileNotFoundError as err:
            print("No proxy information found: " + str(err))
        except Exception as err:
            print("An error occurred: " + str(err))
        return False

    @staticmethod
    def _get_proxy_info_linux() -> tuple[str, str]:
        """读取 Linux/macOS 常见环境变量代理配置。

        例如：http_proxy=http://127.0.0.1:7890。
        注意：这里按冒号 split，复杂代理 URL 可能需要更严谨的解析。
        """

        proxies = {
            'http': os.getenv('http_proxy'),
            'https': os.getenv('https_proxy'),
            'ftp': os.getenv('ftp_proxy')
        }
        ip = port = ""
        for proto, proxy in proxies.items():
            if proxy:
                ip, port = proxy.split(':')
                break
        return ip, port

    def _is_proxy_enabled_linux(self) -> bool:
        """非 Windows 下，只要环境变量里能读到代理字段，就认为代理启用。"""

        proxies = self._get_proxy_info_linux()
        return any(proxy != '' for proxy in proxies)
