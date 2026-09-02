# -*- coding: utf-8 -*-
# wxty.php 转 Python —— 上海看看新闻(五星体育/东方卫视等)直播 TVBox Spider
# 链路：签名API(getLiveUrl) -> RSA公钥解密(live_address) -> 递归扁平化M3U8
import base64
import binascii
import hashlib
import json
import random
import re
import string
import sys
import time
import urllib.parse

import requests
import urllib3

urllib3.disable_warnings()

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        def init(self, extend=""):
            pass

        def getName(self):
            return "上海看看"

        def isVideoFormat(self, url):
            return False

        def manualVideoCheck(self):
            return False

        def destroy(self):
            pass

        def localProxy(self, param):
            return None

        def homeContent(self, filter):
            return {"class": [], "list": [], "filters": {}}

        def homeVideoContent(self):
            return {"list": []}

        def categoryContent(self, tid, pg, filter, extend):
            return {"list": [], "page": int(pg or 1), "pagecount": 1, "limit": 0, "total": 0}

        def detailContent(self, ids):
            return {"list": []}

        def searchContent(self, key, quick, pg="1"):
            return {"list": [], "page": int(pg or 1)}

        def playerContent(self, flag, id, vipFlags):
            return {"parse": 0, "url": id or "", "header": {}}


PUB_KEY = (
    "-----BEGIN PUBLIC KEY-----\n"
    "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDP5hzPUW5RFeE2xBT1ERB3hHZI\n"
    "Votn/qatWhgc1eZof09qKjElFN6Nma461ZAwGpX4aezKP8Adh4WJj4u2O54xCXDt\n"
    "wzKRqZO2oNZkuNmF2Va8kLgiEQAAcxYc8JgTN+uQQNpsep4n/o1sArTJooZIF17E\n"
    "tSqSgXDcJ7yDj5rc7wIDAQAB\n"
    "-----END PUBLIC KEY-----"
)
SIGN_SECRET = "28c8edde3d61a0411511d3b1866f0636"
VERSION = "2.42.21"
API = "https://kapi.kankanews.com/content/pc/tv/channel/detail"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/116.0.5845.97 Safari/537.36 SE 2.X MetaSr 1.0"
)
LIVE_URL_CACHE_TTL = 600
CHANNELS = [
    {"id": "dfws", "channel_id": 1, "name": "东方卫视"},
    {"id": "shxwzh", "channel_id": 2, "name": "上海新闻综合"},
    {"id": "shds", "channel_id": 4, "name": "上海都市"},
    {"id": "dycj", "channel_id": 5, "name": "第一财经"},
    {"id": "hhxd", "channel_id": 9, "name": "哈哈炫动"},
    {"id": "wxty", "channel_id": 10, "name": "五星体育"},
    {"id": "mdy", "channel_id": 11, "name": "上海魔都眼"},
    {"id": "jsrw", "channel_id": 12, "name": "上海新纪实"},
]
CHMAP = {c["id"]: c for c in CHANNELS}


# ---------- RSA 公钥"解密"（PKCS#1 v1.5，与原 PHP rsaDecrypt 等价） ----------
def _rsa_der_integers(der):
    """原样移植 PHP rsaAsn1Integers：扫描 DER 中的 INTEGER 序列。"""
    ints = []
    i = 0
    ln = len(der)
    while i + 2 < ln:
        if der[i] != 0x02:
            i += 1
            continue
        l = der[i + 1]
        start = i + 2
        if l & 0x80:
            n = l & 0x7F
            l = 0
            for j in range(n):
                l = (l << 8) | der[start + j]
            start += n
        if start + l <= ln:
            ints.append(binascii.hexlify(der[start:start + l].lstrip(b"\x00")).decode())
            i = start + l
        else:
            i += 1
    return ints


_N_HEX = None
_E_HEX = None


def _rsa_init():
    global _N_HEX, _E_HEX
    if _N_HEX is not None:
        return
    der = base64.b64decode(re.sub(r"-----[^-]+-----|\s+", "", PUB_KEY))
    ints = _rsa_der_integers(der)
    _N_HEX, _E_HEX = ints[0], ints[1]


def _rsa_pub_decrypt_chunk(chunk_bin):
    """单块 128 字节 RSA 公钥解密（m = c^e mod n），返回 PKCS#1 v1.5 剥离后的数据。"""
    _rsa_init()
    n = int(_N_HEX, 16)
    e = int(_E_HEX, 16)
    c = int.from_bytes(chunk_bin, "big")
    m = pow(c, e, n)
    block = m.to_bytes(128, "big")
    if block[0] != 0 or block[1] != 1:
        return b""
    j = 2
    while j < 128 and block[j] == 0xFF:
        j += 1
    if j >= 128 or block[j] != 0:
        return b""
    return block[j + 1:]


def rsa_decrypt(b64str):
    """base64 密文 -> RSA 公钥解密 -> utf-8 字符串。"""
    try:
        enc = base64.b64decode(b64str)
    except Exception:
        return ""
    out = b""
    for i in range(0, len(enc) - 127, 128):
        out += _rsa_pub_decrypt_chunk(enc[i:i + 128])
    try:
        return out.decode("utf-8")
    except Exception:
        return ""


# ---------- 签名 / API ----------
def _gen_nonce(length=8):
    return "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(length))


def _gen_uuid(length=21):
    return "".join(random.choice(string.ascii_lowercase + string.digits + "-_") for _ in range(length))


def _sign(channel_id, nonce, t):
    sign_str = (
        f"Api-Version=v1&channel_id={channel_id}&nonce={nonce}"
        f"&platform=pc&timestamp={t}&version={VERSION}&{SIGN_SECRET}"
    )
    return hashlib.md5(hashlib.md5(sign_str.encode()).hexdigest().encode()).hexdigest()


class Spider(BaseSpider):
    name = "上海看看"

    def getName(self):
        return self.name

    def init(self, extend=""):
        ext = {}
        if extend:
            try:
                ext = json.loads(extend) if str(extend).strip().startswith("{") else {}
            except Exception:
                ext = {}
        self.client_ip = ext.get("clientIp") or "114.114.114.114"
        self.api = ext.get("api") or API
        self.headers = {
            "Api-Version": "v1",
            "Platform": "pc",
            "Version": VERSION,
            "Origin": "https://live.kankanews.com",
            "Referer": "https://live.kankanews.com/",
            "User-Agent": UA,
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        self.cache = {}

    def _fetch_live_addr(self, channel_id):
        """调用签名 API 获取 RSA 密文 live_address。"""
        t = int(time.time())
        nonce = _gen_nonce()
        uuid = _gen_uuid()
        sign = _sign(channel_id, nonce, t)
        h = dict(self.headers)
        h.update({
            "Nonce": nonce,
            "M-Uuid": uuid,
            "Timestamp": str(t),
            "Sign": sign,
            "X-Forwarded-For": self.client_ip,
            "Client-Ip": self.client_ip,
        })
        url = f"{self.api}?channel_id={channel_id}"
        body = self._http_get(url, headers=h)
        if not body:
            return ""
        try:
            data = json.loads(body)
        except Exception:
            return ""
        result = data.get("result") or {}
        return result.get("live_address") or ""

    def _http_get(self, url, headers=None, timeout=15):
        try:
            rsp = requests.get(url, headers=headers, timeout=timeout, verify=False)
            rsp.encoding = "utf-8"
            return rsp.text or ""
        except Exception:
            return ""

    def get_live_url(self, channel_id, force_refresh=False):
        """返回签名授权的原始 m3u8 播放地址（token 已内嵌，播放器可直接请求）。"""
        key = f"live:{channel_id}"
        if not force_refresh and key in self.cache:
            cached = self.cache[key]
            if time.time() - cached[1] < LIVE_URL_CACHE_TTL:
                return cached[0]
        addr = self._fetch_live_addr(channel_id)
        if not addr:
            return ""
        live_url = rsa_decrypt(addr)
        if not live_url:
            return ""
        if live_url:
            self.cache[key] = (live_url, time.time())
        return live_url

    # ---------- M3U8 扁平化（移植 PHP getFlatM3u8） ----------
    def _fetch_text(self, url):
        return self._http_get(url, headers=self.headers)

    @staticmethod
    def _to_absolute(base, relative):
        if re.match(r"^https?://", relative, re.I):
            return relative
        parts = urllib.parse.urlparse(base)
        base_dir = urllib.parse.urljoin(base, ".")  # 保留目录
        if relative.startswith("/"):
            return f"{parts.scheme}://{parts.netloc}{relative}"
        return urllib.parse.urljoin(base_dir, relative)

    def _flatten_m3u8(self, url, depth=0):
        """把 master playlist 递归展开为第一个可用 media playlist（绝对地址）。"""
        if depth > 5:
            return ""
        content = self._fetch_text(url)
        if not content:
            return ""
        lines = content.split("\n")
        out = []
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if "#EXT-X-STREAM-INF" in line:
                i += 1
                if i >= len(lines):
                    break
                sub = lines[i].strip()
                if not sub or sub.startswith("#"):
                    continue
                abs_sub = self._to_absolute(url, sub)
                sub_content = self._flatten_m3u8(abs_sub, depth + 1)
                if sub_content:
                    return sub_content
            elif line.startswith("#EXTINF:"):
                out.append(line)
                i += 1
                if i >= len(lines):
                    break
                ts = lines[i].strip()
                if ts and not ts.startswith("#"):
                    out.append(self._to_absolute(url, ts))
                else:
                    out.append(ts)
            else:
                # 重写 URI="..." 为绝对地址
                line = re.sub(
                    r'URI="([^"]+)"',
                    lambda m: f'URI="{self._to_absolute(url, m.group(1))}"',
                    line,
                    flags=re.I,
                )
                out.append(line)
            i += 1
        return "\n".join(out)

    # ---------- TVBox 五接口 ----------
    def homeContent(self, filter):
        classes = [{"type_id": c["id"], "type_name": c["name"]} for c in CHANNELS]
        lst = []
        for c in CHANNELS:
            url = self.get_live_url(c["channel_id"])
            if url:
                lst.append({
                    "vod_id": c["id"],
                    "vod_name": c["name"],
                    "vod_pic": "",
                    "vod_remarks": "直播",
                })
        return {"class": classes, "list": lst, "filters": {}}

    def homeVideoContent(self):
        return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        c = CHMAP.get(str(tid))
        if not c:
            return {"list": [], "page": int(pg or 1), "pagecount": 1, "limit": 0, "total": 0}
        url = self.get_live_url(c["channel_id"])
        lst = [{"vod_id": c["id"], "vod_name": c["name"], "vod_pic": "", "vod_remarks": "直播"}] if url else []
        return {"list": lst, "page": int(pg or 1), "pagecount": 1, "limit": 1, "total": 1}

    def detailContent(self, ids):
        cid = ids[0]
        c = CHMAP.get(cid)
        if not c:
            c = next((x for x in CHANNELS if cid == str(x["channel_id"])), None)
        if not c:
            return {"list": []}
        url = self.get_live_url(c["channel_id"], force_refresh=True)
        if not url:
            return {"list": []}
        vod = {
            "vod_id": c["id"],
            "vod_name": c["name"],
            "vod_pic": "",
            "vod_remarks": "直播",
            "vod_content": c["name"],
            "vod_play_from": "看看直播",
            "vod_play_url": f"{c['name']}${url}",
        }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        match = [c for c in CHANNELS if key in c["name"]]
        lst = []
        for c in match:
            url = self.get_live_url(c["channel_id"])
            if url:
                lst.append({"vod_id": c["id"], "vod_name": c["name"], "vod_pic": "", "vod_remarks": "直播"})
        return {"list": lst, "page": int(pg or 1)}

    def playerContent(self, flag, id, vipFlags):
        return {
            "parse": 0,
            "url": id or "",
            "header": {"User-Agent": UA, "Referer": "https://live.kankanews.com/"},
        }

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return None

    def destroy(self):
        pass