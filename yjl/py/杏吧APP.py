# -*- coding: utf-8 -*-
#SEO https://xb1818.tv  邮箱：xingba357@gmail.com
#TG：https://t.me/xingba018
"""XB 联网版 TVBox Python Spider（单文件）。

仅供账号持有人在已获授权的环境中测试。文件内包含私有设备登录资料，
请勿公开上传、转发或提交到公开仓库。
"""
from __future__ import annotations

import gzip
import hashlib
import hmac
import json
import os
import secrets
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import quote, urljoin, urlparse

sys.path.append('..')

try:
    import requests
except ImportError:
    requests = None

try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
except ImportError:
    Cipher = algorithms = modes = None

try:
    from Crypto.Cipher import AES as CryptoAES
except ImportError:
    CryptoAES = None

try:
    from base.spider import Spider as _BaseSpider
except ImportError:
    class _BaseSpider:
        pass

# Android 9+ 的 TVBox 壳通常默认禁止明文 HTTP；该接口已验证支持 HTTPS。
BASE_URL = "https://api.lijglfyv.com"
HMAC_KEY = b"829d2b252450da23"
SIGN_KEY = "cd271bb945844572818ba0bda1b59e85"
BLOCK = 16
TIMEOUT = 15
DEFAULT_SECTION_ID = "16"
DEFAULT_FILTER = {
    "tag_id": "568,577,569,618,681,682,656,679,644,634,680,689",
    "order": "click",
    "ad_code": "app_data_list",
    "position": "normal",
}
HEADERS = {
    "Accept-Encoding": "gzip",
    "Content-Type": "application/x-www-form-urlencoded",
    "User-Agent": "Dart/3.6 (dart:io)",
    "version": "7.0.6",
    "systemname": "Android",
    "systemversion": "12",
    "devicebrand": "HONOR",
    "devicemodel": "TFY-AN00",
    "devicetype": "android",
    "supporthevc": "1",
}
PLAY_HEADERS = {"User-Agent": "ExoPlayer", "Referer": "http://www.qq.com"}

# __PRIVATE_LOGIN_BODY__
PRIVATE_LOGIN_BODY: dict[str, Any] = {'token': '', 'deviceId': '25abf12fdd60cc88', 'data': {'line_code': 'ch3', 'channel_code': '', 'share_code': '', 'clipboard_text': '# -*- coding: utf-8 -*-\nimport sys, re, json, urllib.parse\nsys.path.append(\'..\')\ntry:\n    from base.spider import Spider as _B\nexcept ImportError:\n    class _B: pass\ntry:\n    import requests\nexcept ImportError:\n    requests = None\n\nH = "https://dag29jmgma1g.site"\nU = "Mozilla/5.0 (Linux; Android 12; TFY-AN00 Build/HONORTFY-AN00; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/92.0.4515.105 Mobile Safari/537.36 uni-app Html5Plus/1.0 (Immersed/33.0)"\n\nclass Spider(_B):\n    def init(self, e=""):\n        self.s = requests.Session()\n        self.s.headers.update({\n            "User-Agent": U, \n            "Accept-Encoding": "gzip",\n            "Content-Type": "application/x-www-form-urlencoded"\n        })\n        self.token = ""\n        self._register()\n\n    def getName(self):\n        return "萝莉岛"\n\n    def isVideoFormat(self, u):\n        return ".m3u8" in u or ".mp4" in u or "preview" in u\n\n    def manualVideoCheck(self):\n        return False\n\n    def _register(self):\n        """注册/获取设备的交互 Token"""\n        url = H + "/api/newreg.php"\n        data = {"device": "android", "ntoken": "", "channel_code": "vbtQg9D8"}\n        try:\n            r = self.s.post(url, data=data, timeout=10).json()\n            self.token = r.get("user", {}).get("token", "")\n        except Exception as e:\n            print(\'[REGISTER]\', e)\n\n    def homeContent(self, filter=False):\n        """获取主分类及其对应的筛选条件"""\n        url = H + "/api/setapp.php"\n        try:\n            r = self.s.get(url, timeout=10).json()\n            classes = []\n            filters = {}\n            \n            # API 将分类拆分在 vodtab 和 vodtaban (暗黑) 两个数组中，这里将其合并\n            tabs = r.get("vodtab", []) + r.get("vodtaban", [])\n            for tab in tabs:\n                tid = tab.get("type_id")\n                classes.append({\n                    "type_id": tid,\n                    "type_name": tab.get("type_name")\n                })\n                tags = tab.get("vodtags", [])\n                if tags:\n                    tag_values = [{"n": "全部", "v": ""}]\n                    for tag in tags:\n                        tag_values.append({"n": tag.get("name"), "v": tag.get("name")})\n                    filters[tid] = [{"key": "class", "name": "标签", "value": tag_values}]\n            \n            return {"class": classes, "filters": filters if filter else {}}\n        except Exception as e:\n            print(\'[HOME]\', e)\n            return {"class": [], "filters": {}}\n\n    def homeVideoContent(self):\n        return {"list": []}\n\n    def categoryContent(self, tid, pg=1, filter=False, extend=None):\n        """获取分类子列表"""\n        if not extend: extend = {}\n        url = H + "/api/vlist.php"\n        \n        # 抓包显示 num 为 0，通常代表 offset(偏移量)。结合返回结果固定30条推算，offset = (页码 - 1) * 30\n        num = (int(pg) - 1) * 30\n        payload = {\n            "num": str(num),\n            "pid": str(tid),\n            "area": "全部",\n            "vodclass": extend.get("class", ""),\n            "vodyear": "全部",\n            "sort": "1",\n            "token": self.token\n        }\n        try:\n            r = self.s.post(url, data=payload, timeout=10).json()\n            videos = []\n            for item in r.get("list", []):\n                videos.append({\n                    "vod_id": str(item.get("vod_id", "")),\n                    "vod_name": item.get("vod_name", ""),\n                    "vod_pic": item.get("vod_pic", ""),\n                    "vod_remarks": item.get("vod_class", "") or item.get("vod_remarks", "")\n                })\n            return {"list": videos, "page": pg}\n        except Exception as e:\n            print(\'[CATEGORY]\', e)\n            return {"list": []}\n\n    def detailContent(self, ids):\n        """获取视频详情及播放链接"""\n        url = H + "/api/Get_vod_list.php"\n        payload = {\n            "id": str(ids[0]),\n            "token": self.token,\n            "channel": ""\n        }\n        try:\n            r = self.s.post(url, data=payload, timeout=10).json()\n            data = r.get("data", {})\n            \n            # API 抓包中直接包含了 TVBox 兼容格式的 vod_play_url (如："正片$https://...m3u8")\n            play_url = data.get("vod_play_url", "")\n            if not play_url:\n                # 兼容未登录或无权限的情况，回退至试看预览链接\n                play_url = "预览$" + data.get("preview_url", "")\n\n            video = {\n                "vod_id": str(data.get("vod_id", ids[0])),\n                "vod_name": data.get("vod_name", ""),\n                "vod_pic": data.get("vod_pic", ""),\n                "vod_remarks": data.get("vod_remarks", ""),\n                "vod_content": data.get("vod_blurb", "暂无简介"),\n                "vod_play_from": "萝莉岛",\n                "vod_play_url": play_url\n            }\n            return {"list": [video]}\n        except Exception as e:\n            print(\'[DETAIL]\', e)\n            return {"list": []}\n\n    def playerContent(self, flag, id, vipFlags=None):\n        """播放器直连"""\n        return {\n            "parse": 0,\n            "url": id,\n            "header": json.dumps({"User-Agent": U})\n        }\n\n    def searchContent(self, key, quick=False, pg=1):\n        """由于未提供搜索接口的抓包记录，预留空返回值避免TVBox请求报错"""\n        return {"list": []}\n\n    def localProxy(self, param):\n        pass', 'device_info': {'name': 'hy0001', 'sdk': '31', 'version': '12', 'board': 'TFY', 'device': 'HNTFY-M', 'manufacturer': 'HONOR', 'model': 'TFY-AN00', 'product': 'TFY-AN00', 'isPhysicalDevice': 'true'}}}


def _sign(session_id: str, request_id: str, timestamp: str, path: str, host: str) -> str:
    raw = f"{SIGN_KEY}|{session_id}|{request_id}|{timestamp}|{host}{path}"
    return f"{hashlib.md5(raw.encode()).hexdigest()}-{timestamp}"


def _key(request_id: str) -> bytes:
    raw = bytes.fromhex(request_id.replace("-", ""))
    if len(raw) != BLOCK:
        raise ValueError("requestId 必须是 16 字节 UUID")
    return hmac.new(HMAC_KEY, raw, hashlib.sha256).digest()


def _pad(data: bytes) -> bytes:
    n = BLOCK - len(data) % BLOCK
    return data + bytes([n]) * n


def _unpad(data: bytes) -> bytes:
    if not data:
        raise ValueError("空密文")
    n = data[-1]
    if not 1 <= n <= BLOCK or data[-n:] != bytes([n]) * n:
        raise ValueError("PKCS#7 padding 错误")
    return data[:-n]


def _aes(data: bytes, key: bytes, iv: bytes, decrypt: bool = False) -> bytes:
    if CryptoAES is not None:
        cipher = CryptoAES.new(key, CryptoAES.MODE_CBC, iv)
        return cipher.decrypt(data) if decrypt else cipher.encrypt(data)
    if Cipher is not None:
        op = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor() if decrypt else Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
        return op.update(data) + op.finalize()
    # 某些 TVBox Python 环境没有 cryptography，回退系统 openssl。
    command = ["openssl", "enc", "-aes-256-cbc", "-K", key.hex(), "-iv", iv.hex(), "-nopad"]
    if decrypt:
        command.append("-d")
    proc = subprocess.run(command, input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode:
        raise RuntimeError("需要 cryptography 包或 openssl: " + proc.stderr.decode(errors="replace"))
    return proc.stdout


def _encode(data: Mapping[str, Any], request_id: str) -> bytes:
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode()
    packed = gzip.compress(raw, mtime=0)
    iv = os.urandom(BLOCK)
    return iv + _aes(_pad(packed), _key(request_id), iv)


def _decode(data: bytes, request_id: str) -> Mapping[str, Any]:
    if len(data) < 32 or len(data) % BLOCK:
        raise ValueError("响应密文长度错误")
    iv = data[:BLOCK]
    packed = _unpad(_aes(data[BLOCK:], _key(request_id), iv, True))
    obj = json.loads(gzip.decompress(packed))
    if not isinstance(obj, Mapping):
        raise ValueError("响应 JSON 不是对象")
    return obj


class _Client:
    def __init__(self, base_url: str = BASE_URL, timeout: float = TIMEOUT):
        if requests is None:
            raise RuntimeError("此 Spider 需要 requests")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.http = requests.Session()
        self.session_id = uuid.uuid4().hex
        self.login_body = dict(PRIVATE_LOGIN_BODY)
        self.device_id = str(self.login_body.get("deviceId", ""))
        self.token = ""

    def system_info(self) -> Mapping[str, Any]:
        return self.request("/system/info", None)

    def _url(self, path: str) -> str:
        if path.startswith(("http://", "https://")):
            return path
        path = path if path.startswith("/xbapi/") else "/xbapi/" + path.lstrip("/")
        return urljoin(self.base_url + "/", path.lstrip("/"))

    def _once(self, path: str, body: Mapping[str, Any]) -> Mapping[str, Any]:
        request_id = str(uuid.uuid4())
        timestamp = str(int(time.time()))
        url = self._url(path)
        parsed = urlparse(url)
        headers = dict(HEADERS)
        headers.update({
            "requestId": request_id,
            "time": timestamp,
            "sessionid": self.session_id,
            "sign": _sign(self.session_id, request_id, timestamp, parsed.path, parsed.hostname or ""),
        })
        response = self.http.post(url, data=_encode(body, request_id), headers=headers, timeout=self.timeout)
        response.raise_for_status()
        return _decode(response.content, request_id)

    @staticmethod
    def _expired(response: Mapping[str, Any]) -> bool:
        if str(response.get("errorCode", "")) in {"401", "403"}:
            return True
        message = str(response.get("error", response.get("message", ""))).lower()
        return "token" in message and any(x in message for x in ("invalid", "expired", "login", "失效", "登录"))

    def login(self) -> Mapping[str, Any]:
        if not self.login_body:
            raise RuntimeError("单文件中的 PRIVATE_LOGIN_BODY 未填充")
        response = self._once("/login/device", self.login_body)
        data = response.get("data")
        if not isinstance(data, Mapping) or not data.get("token") or data.get("user_id") is None:
            raise RuntimeError("设备登录失败: " + str(response.get("error", response.get("status", "unknown"))))
        self.token = f"{data['token']}_{data['user_id']}"
        return response

    def request(self, path: str, data: Any) -> Mapping[str, Any]:
        if not self.token:
            self.login()
        body = {"token": self.token, "deviceId": self.device_id, "data": data}
        response = self._once(path, body)
        if self._expired(response):
            self.login()
            body["token"] = self.token
            response = self._once(path, body)
        return response


class Spider(_BaseSpider):
    def init(self, extend: str = ""):
        self.extend = {}
        if extend:
            try:
                self.extend = json.loads(extend) if extend.lstrip().startswith("{") else json.loads(Path(extend).read_text())
            except Exception as exc:
                print("[XB:init] extend 解析失败，使用内置配置:", exc)
        self.client = _Client(
            str(self.extend.get("base_url", BASE_URL)),
            float(self.extend.get("timeout", TIMEOUT)),
        )
        self.section_id = str(self.extend.get("section_id", DEFAULT_SECTION_ID))
        self.home_filter = dict(DEFAULT_FILTER)
        self.navs = []
        self.nav_by_id = {}
        self.img_key = ""
        self._filters_cache = None
        self._home_cache = None

    @staticmethod
    def _error(where, exc):
        message = ("%s: %s" % (where, exc))[:180]
        print("[XB]", message)
        return {"vod_id": "__xb_error__", "vod_name": "XB加载失败", "vod_pic": "", "vod_remarks": message}

    def getName(self):
        return "XB-VIP"

    def isVideoFormat(self, url):
        return ".m3u8" in str(url).lower() or ".mp4" in str(url).lower()

    def manualVideoCheck(self):
        return False

    @staticmethod
    def _items(response):
        data = response.get("data", {}) if isinstance(response, Mapping) else {}
        rows = data.get("data", []) if isinstance(data, Mapping) else []
        return rows if isinstance(rows, list) else []

    def _cover(self, url):
        url = str(url or "")
        if not url or not url.lower().split("?", 1)[0].endswith(".bnc"):
            return url
        try:
            base = self.getProxyUrl()
            return base + ("&" if "?" in base else "?") + "do=py&type=xb_cover&url=" + quote(url, safe="")
        except Exception:
            return ""

    def _video(self, item):
        return {
            "vod_id": str(item.get("id", "")),
            "vod_name": str(item.get("name", "")),
            "vod_pic": self._cover(item.get("img", "")),
            "vod_remarks": str(item.get("duration") or item.get("category") or item.get("pay_type") or ""),
        }

    @staticmethod
    def _page(response, page, videos):
        data = response.get("data", {}) if isinstance(response, Mapping) else {}
        if not isinstance(data, Mapping):
            data = {}
        return {
            "page": int(data.get("current_page", page) or page),
            "pagecount": int(data.get("last_page", page) or page),
            "limit": int(data.get("page_size", len(videos)) or len(videos)),
            "total": int(data.get("total", len(videos)) or len(videos)),
            "list": videos,
        }

    def _nav(self, nav_id):
        return self.client.request("/movie/navFilter", {"id": str(nav_id)})

    def _load_navigation(self):
        if self.navs:
            return self.navs
        info = self.client.system_info()
        data = info.get("data", {}) if isinstance(info, Mapping) else {}
        if not isinstance(data, Mapping):
            raise RuntimeError("system/info 未返回 data")
        self.img_key = str(data.get("img_key", ""))
        navs = data.get("normal_nav", [])
        if not isinstance(navs, list) or not navs:
            raise RuntimeError("system/info 未返回 normal_nav")
        self.navs = [x for x in navs if isinstance(x, Mapping) and x.get("id") and x.get("name")]
        self.nav_by_id = {str(x["id"]): dict(x) for x in self.navs}
        return self.navs

    def homeContent(self, filter=False):
        try:
            navs = self._load_navigation()
        except Exception as exc:
            message = self._error("homeContent", exc)["vod_remarks"]
            return {"class": [{"type_id": "__xb_error__", "type_name": message}], "filters": {}}
        classes = [{"type_id": str(x["id"]), "type_name": str(x["name"])} for x in navs]
        if filter and self._filters_cache is not None:
            return {"class": classes, "filters": self._filters_cache}
        filters = {}
        if filter:
            for nav in navs:
                nid = str(nav["id"])
                presets, tags = nav.get("filters", []), []
                try:
                    live = self._nav(nid).get("data", {})
                    if isinstance(live, Mapping):
                        tags = live.get("tags", [])
                        presets = live.get("filters") or presets
                except Exception as exc:
                    print("[XB:navFilter:%s] %s" % (nid, exc))
                groups = []
                tag_values = [{"n": "全部", "v": ""}]
                tag_values += [{"n": str(x.get("name", "")), "v": str(x.get("id", ""))}
                               for x in tags if isinstance(x, Mapping) and x.get("id") and x.get("name")]
                if len(tag_values) > 1:
                    groups.append({"key": "tag_id", "name": "子分类", "value": tag_values})
                orders, seen = [], set()
                for entry in presets if isinstance(presets, list) else []:
                    f = entry.get("filter", {}) if isinstance(entry, Mapping) else {}
                    value = str(f.get("order", "")) if isinstance(f, Mapping) else ""
                    if value and value not in seen:
                        seen.add(value)
                        orders.append({"n": str(entry.get("name") or value), "v": value})
                if orders:
                    groups.append({"key": "order", "name": "排序", "value": orders})
                if groups:
                    filters[nid] = groups
            self._filters_cache = filters
        return {"class": classes, "filters": filters}

    def homeVideoContent(self):
        if self._home_cache is not None:
            return self._home_cache
        try:
            response = self.client.request("/movie/navBlock", {"id": "1"})
            blocks = response.get("data", []) if isinstance(response, Mapping) else []
            videos, seen = [], set()
            for block in blocks if isinstance(blocks, list) else []:
                for item in block.get("items", []) if isinstance(block, Mapping) else []:
                    mid = str(item.get("id", "")) if isinstance(item, Mapping) else ""
                    if mid and mid not in seen and item.get("img"):
                        seen.add(mid)
                        videos.append(self._video(item))
            self._home_cache = {"list": videos}
            return self._home_cache
        except Exception as exc:
            return {"list": [self._error("homeVideoContent", exc)]}

    def categoryContent(self, tid, pg="1", filter=False, extend=None):
        page = max(1, int(pg))
        if not self.nav_by_id:
            self._load_navigation()
        nav = self.nav_by_id.get(str(tid), {})
        presets = nav.get("filters", []) if isinstance(nav, Mapping) else []
        payload = {"ad_code": "app_data_list", "position": "normal"}
        if presets and isinstance(presets[0], Mapping) and isinstance(presets[0].get("filter"), Mapping):
            payload.update(presets[0]["filter"])
        payload["page"] = page
        if extend:
            if extend.get("tag_id"):
                payload["tag_id"] = str(extend["tag_id"])
            if extend.get("order"):
                payload["order"] = str(extend["order"])
        if str(tid) == "1" and page == 1 and not (extend and any(extend.values())):
            videos = self.homeVideoContent()["list"]
            return {"page": 1, "pagecount": 1, "limit": len(videos), "total": len(videos), "list": videos}
        response = self.client.request("/search/movie", payload)
        return self._page(response, page, [self._video(x) for x in self._items(response)])

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        movie_id = str(ids[0])
        response = self.client.request("/movie/detail", {"id": movie_id, "lid": ""})
        data = response.get("data", {})
        if not isinstance(data, Mapping):
            return {"list": []}
        sources, lines = [], []
        for index, source in enumerate(data.get("play_links", []) or [], 1):
            if not isinstance(source, Mapping):
                continue
            url = str(source.get("m3u8_url_h265") or source.get("m3u8_url") or "")
            if not url:
                continue
            if url.startswith("/"):
                url = urljoin(self.client.base_url + "/", url.lstrip("/"))
            sources.append(str(source.get("name") or "线路%d" % index).replace("$$$", ""))
            lines.append("正片$" + url)
        video = self._video(data)
        video.update({
            "vod_id": str(data.get("id", movie_id)),
            "vod_content": str(data.get("description", "")),
            "vod_actor": " / ".join(str(x.get("name", "")) for x in (data.get("actors") or []) if isinstance(x, Mapping)),
            "vod_play_from": "$$$".join(sources),
            "vod_play_url": "$$$".join(lines),
        })
        return {"list": [video]}

    def searchContent(self, key, quick=False, pg="1"):
        page = max(1, int(pg))
        try:
            response = self.client.request("/search/movie", {"keywords": str(key), "page": page})
            needle = str(key).casefold()
            rows = [x for x in self._items(response) if needle in str(x.get("name", "")).casefold()]
            return self._page(response, page, [self._video(x) for x in rows])
        except Exception as exc:
            return {"page": page, "pagecount": 1, "limit": 0, "total": 0, "list": [self._error("searchContent", exc)]}

    def playerContent(self, flag, id, vipFlags=None):
        return {"parse": 0, "playUrl": "", "url": id, "header": PLAY_HEADERS}

    def localProxy(self, param):
        try:
            if str(param.get("type", "")) != "xb_cover":
                return [404, "text/plain", "not found"]
            url = str(param.get("url", ""))
            if not url.startswith(("http://", "https://")):
                raise ValueError("invalid cover URL")
            if not self.img_key:
                self._load_navigation()
            key = self.img_key.encode()
            if len(key) not in (16, 24, 32):
                raise ValueError("invalid img_key")
            response = self.client.http.get(url, headers={"Referer": "https://www.baidu.com"}, timeout=self.client.timeout)
            response.raise_for_status()
            encrypted = response.content
            if not encrypted or len(encrypted) % BLOCK:
                raise ValueError("invalid encrypted cover length")
            if CryptoAES is not None:
                plain = CryptoAES.new(key, CryptoAES.MODE_ECB).decrypt(encrypted)
            elif Cipher is not None:
                op = Cipher(algorithms.AES(key), modes.ECB()).decryptor()
                plain = op.update(encrypted) + op.finalize()
            else:
                command = ["openssl", "enc", "-d", "-aes-%d-ecb" % (len(key) * 8), "-K", key.hex(), "-nopad"]
                proc = subprocess.run(command, input=encrypted, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if proc.returncode:
                    raise RuntimeError(proc.stderr.decode(errors="replace"))
                plain = proc.stdout
            plain = _unpad(plain)
            if plain.startswith(b"\xff\xd8\xff"):
                mime = "image/jpeg"
            elif plain.startswith(b"\x89PNG\r\n\x1a\n"):
                mime = "image/png"
            elif plain.startswith(b"RIFF") and plain[8:12] == b"WEBP":
                mime = "image/webp"
            else:
                raise ValueError("decrypted cover is not an image")
            return [200, mime, plain]
        except Exception as exc:
            print("[XB:cover]", exc)
            return [500, "text/plain", ("cover error: %s" % exc).encode()]

    def destroy(self):
        close = getattr(getattr(self, "client", None), "http", None)
        if close is not None:
            close.close()
