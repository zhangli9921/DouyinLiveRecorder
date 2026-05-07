# -*- encoding: utf-8 -*-

"""
Author: Hmily
GitHub:https://github.com/ihmily
Date: 2023-07-17 23:52:05
Update: 2025-02-04 04:57:00
Copyright (c) 2023 by Hmily, All Rights Reserved.

学习提示：
这个文件主要服务抖音房间信息解析，负责把分享链接、用户页、房间 ID 等信息转换成后续接口可用的参数。
你可以把它理解成“进入直播间前的寻路模块”：先找 room_id/sec_user_id，再通过接口拿 web_rid。
"""

import re
import urllib.parse
import execjs
import httpx
import urllib.request
from . import JS_SCRIPT_PATH, utils

# 构造一个“不走代理”的 urllib opener。某些请求如果被系统代理影响，可能导致跳转或解析异常。
no_proxy_handler = urllib.request.ProxyHandler({})
opener = urllib.request.build_opener(no_proxy_handler)


class UnsupportedUrlError(Exception):
    """当前函数不支持传入链接形态时抛出的异常。"""

    pass


# 移动端请求头。抖音部分分享页在移动 UA 下更容易返回目标跳转信息。
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Linux; Android 11; SAMSUNG SM-G973U) AppleWebKit/537.36 (KHTML, like Gecko) '
                  'SamsungBrowser/14.2 Chrome/87.0.4280.141 Mobile Safari/537.36',
    'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
    'Cookie': 's_v_web_id=verify_lk07kv74_QZYCUApD_xhiB_405x_Ax51_GYO9bUIyZQVf'
}

# PC 端请求头。某些接口/页面需要 PC UA 和 Cookie 才能正常返回。
HEADERS_PC = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0',
        'Cookie': 'sessionid=7494ae59ae06784454373ce25761e864; __ac_nonce=0670497840077ee4c9eb2; '
                  '__ac_signature=_02B4Z6wo00f012DZczQAAIDCJJBb3EjnINdg-XeAAL8-db;  '
                  's_v_web_id=verify_m1ztgtjj_vuHnMLZD_iwZ9_4YO4_BdN1_7wLP3pyqXsf2; '
    }


async def get_xbogus(url: str, headers: dict | None = None) -> str:
    """计算抖音 Web 接口需要的 X-Bogus 参数。

    X-Bogus 是抖音 Web 请求里的签名参数。这里没有用 Python 重写算法，而是读取 javascript/x-bogus.js，
    通过 execjs 调用 JS 里的 sign 函数。
    """

    # 如果调用方没有给 User-Agent，就使用默认移动端 headers。
    if not headers or 'user-agent' not in (k.lower() for k in headers):
        headers = HEADERS

    # X-Bogus 通常基于 query string 和 User-Agent 计算。
    query = urllib.parse.urlparse(url).query
    xbogus = execjs.compile(open(f'{JS_SCRIPT_PATH}/x-bogus.js').read()).call(
        'sign', query, headers.get("User-Agent", "user-agent"))
    return xbogus


async def get_sec_user_id(url: str, proxy_addr: str | None = None, headers: dict | None = None) -> tuple | None:
    """从抖音分享/跳转链接中提取 room_id 和 sec_user_id。

    返回：
    - room_id：直播房间相关 ID。
    - sec_user_id：用户安全 ID，后续请求用户/房间接口会用到。
    """

    if not headers or all(k.lower() not in ['user-agent', 'cookie'] for k in headers):
        headers = HEADERS

    try:
        proxy_addr = utils.handle_proxy_addr(proxy_addr)
        async with httpx.AsyncClient(proxy=proxy_addr, timeout=15) as client:
            # follow_redirects=True 很关键：短链真正的信息通常藏在跳转后的 URL 里。
            response = await client.get(url, headers=headers, follow_redirects=True)
            redirect_url = response.url
            if 'reflow/' in str(redirect_url):
                match = re.search(r'sec_user_id=([\w_\-]+)&', str(redirect_url))
                if match:
                    sec_user_id = match.group(1)
                    room_id = str(redirect_url).split('?')[0].rsplit('/', maxsplit=1)[1]
                    return room_id, sec_user_id
                else:
                    raise RuntimeError("Could not find sec_user_id in the URL.")
            else:
                raise UnsupportedUrlError("The redirect URL does not contain 'reflow/'.")
    except UnsupportedUrlError as e:
        raise e
    except Exception as e:
        raise RuntimeError(f"An error occurred: {e}")


async def get_unique_id(url: str, proxy_addr: str | None = None, headers: dict | None = None) -> str | None:
    """获取抖音号 unique_id。

    它先跟随跳转拿到 sec_user_id，再请求 share/user 页面，从页面文本里提取 unique_id。
    """

    if not headers or all(k.lower() not in ['user-agent', 'cookie'] for k in headers):
        headers = HEADERS

    try:
        proxy_addr = utils.handle_proxy_addr(proxy_addr)
        async with httpx.AsyncClient(proxy=proxy_addr, timeout=15) as client:
            response = await client.get(url, headers=headers, follow_redirects=True)
            redirect_url = str(response.url)
            if 'reflow/' in str(redirect_url):
                raise UnsupportedUrlError("Unsupported URL")

            # 非 reflow 链接时，URL 最后一段常常就是 sec_user_id。
            sec_user_id = redirect_url.split('?')[0].rsplit('/', maxsplit=1)[1]

            # 这里设置 Cookie 是为了让 iesdouyin 分享页返回包含 unique_id 的页面内容。
            headers['Cookie'] = ('ttwid=1%7C4ejCkU2bKY76IySQENJwvGhg1IQZrgGEupSyTKKfuyk%7C1740470403%7Cbc9a'
                                 'd2ee341f1a162f9e27f4641778030d1ae91e31f9df6553a8f2efa3bdb7b4; __ac_nonce=06'
                                 '83e59f3009cc48fbab0; __ac_signature=_02B4Z6wo00f01mG6waQAAIDB9JUCzFb6.TZhmsU'
                                 'AAPBf34; __ac_referer=__ac_blank')
            user_page_response = await client.get(f'https://www.iesdouyin.com/share/user/{sec_user_id}',
                                                headers=headers, follow_redirects=True)
            matches = re.findall(r'unique_id":"(.*?)","verification_type', user_page_response.text)
            if matches:
                # 如果页面里出现多个匹配，取最后一个，沿用原项目逻辑。
                unique_id = matches[-1]
                return unique_id
            else:
                raise RuntimeError("Could not find unique_id in the response.")
    except UnsupportedUrlError as e:
        raise e
    except Exception as e:
        raise RuntimeError(f"An error occurred: {e}")


async def get_live_room_id(room_id: str, sec_user_id: str, proxy_addr: str | None = None, params: dict | None = None,
                           headers: dict | None = None) -> str:
    """通过 room_id + sec_user_id 请求抖音接口，拿到 web_rid。

    web_rid 是 Web 直播间地址里常见的房间标识，后续可用于定位直播间真实页面。
    """

    if not headers or all(k.lower() not in ['user-agent', 'cookie'] for k in headers):
        headers = HEADERS

    if not params:
        # 这些参数是抖音 reflow/info 接口需要的基础参数。
        params = {
            "verifyFp": "verify_lk07kv74_QZYCUApD_xhiB_405x_Ax51_GYO9bUIyZQVf",
            "type_id": "0",
            "live_id": "1",
            "room_id": room_id,
            "sec_user_id": sec_user_id,
            "app_id": "1128",
            "msToken": "wrqzbEaTlsxt52-vxyZo_mIoL0RjNi1ZdDe7gzEGMUTVh_HvmbLLkQrA_1HKVOa2C6gkxb6IiY6TY2z8enAkPEwGq--gM"
                       "-me3Yudck2ailla5Q4osnYIHxd9dI4WtQ==",
        }

    api = f'https://webcast.amemv.com/webcast/room/reflow/info/?{urllib.parse.urlencode(params)}'

    # 接口需要 X-Bogus 签名，否则可能返回失败或空数据。
    xbogus = await get_xbogus(api)
    api = api + "&X-Bogus=" + xbogus

    try:
        proxy_addr = utils.handle_proxy_addr(proxy_addr)
        async with httpx.AsyncClient(proxy=proxy_addr,
                                     timeout=15) as client:
            response = await client.get(api, headers=headers)
            response.raise_for_status()
            json_data = response.json()
            return json_data['data']['room']['owner']['web_rid']
    except httpx.HTTPStatusError as e:
        print(f"HTTP status error occurred: {e.response.status_code}")
        raise
    except Exception as e:
        print(f"An exception occurred during get_live_room_id: {e}")
        raise


if __name__ == '__main__':
    # 注意：下面两个函数是 async 函数，直接这样调用会得到协程对象。
    # 真正单独运行测试时，应使用 asyncio.run(get_sec_user_id(room_url)) 这种写法。
    room_url = "https://v.douyin.com/iQLgKSj/"
    _room_id, sec_uid = get_sec_user_id(room_url)
    web_rid = get_live_room_id(_room_id, sec_uid)
    print("return web_rid:", web_rid)
