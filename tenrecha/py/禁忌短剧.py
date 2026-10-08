# -*- coding: utf-8 -*-
"""
TVBox Spider · 禁忌短剧（jinji.video）

站点类型：Next.js SSR + 自研加密接口（AES-128-CBC / HMAC-SHA256 / gzip）
解析路线：纯接口解析（不走网页抓取）
  · 列表 / 分类  POST /api/search/movie      {board_id|nav_id, page, page_size, order}
  · 详情/剧集     POST /api/movie/detail     {id} → links[].items[] 每集自带 m3u8
  · 搜索          POST /api/search/movie     {keyword, page, page_size}
  · 播放          GET  /ysapi/m3u8/p/xxxx.m3u8（m3u8 直链，AES-128 分片，播放器原生支持）

加密协议（复现自站点前端请求层）：
  key      = HMAC-SHA256(key="7961beb44246e3012ce228d6b5ced05a", msg=bytes.fromhex(uuid4))
  body     = AES-CBC(iv=random16, key, gzip(json)) → iv + ciphertext
  headers  = content-type: application/octet-stream / version / deviceType / time / requestId
  响应      = 同样算法反向解密

播放口径（实测，v2 修正）：
  · free 条目：详情接口逐集给完整 m3u8（实测 ENDLIST 完整片、AES 密钥+全分片可拉）
  · vip  条目：站点只发试看源（实测 m3u8 仅 1~3 个分片、约 10~20 秒），
    详情接口逐集地址为空，试看地址只出现在 play_links / playback_v2 里。
    → 本版本把试看单独拆成一条线路并标名「VIP试看」，不再冒充正片（旧版本会把
      试看地址当成第1集丢给播放器，表现就是"打开只播十几秒"）。

依赖：零第三方依赖（纯标准库；AES 为本文件内置纯 Python 实现，兼容 Jython 老环境）

extend 参数（可选，| 分隔，顺序不敏感）：
  "https://镜像域名"                 自定义域名（第一个 http 段）
  "https://镜像域名|https://反代地址" 自定义域名 + 反代（第二个 http 段）
  "token:xxxx"                       站点账号 token（有账号时带上，站点自行鉴权）
  "cookie:k=v; k2=v2"                自定义 Cookie
"""

import sys
import os
import re
import json
import time
import gzip
import hmac
import hashlib
import random

# ---------------------------------------------------------------- 兼容层
_PY2 = sys.version_info[0] < 3

try:
    import requests
    _HAS_REQUESTS = True
except Exception:
    _HAS_REQUESTS = False

if _PY2:  # pragma: no cover
    import urllib2 as _urlreq
    from urllib import quote as _urlquote
    from io import BytesIO as _BytesIO
else:
    import urllib.request as _urlreq
    import urllib.error as _urlerr
    from urllib.parse import quote as _urlquote
    from io import BytesIO as _BytesIO

try:
    from base.spider import Spider as _BaseSpider
except Exception:
    class _BaseSpider(object):
        """TVBox base.spider 缺失时的本地兜底基类"""


# ---------------------------------------------------------------- 纯 Python AES
_AES_SBOX = [
    0x63, 0x7c, 0x77, 0x7b, 0xf2, 0x6b, 0x6f, 0xc5, 0x30, 0x01, 0x67, 0x2b, 0xfe, 0xd7, 0xab, 0x76,
    0xca, 0x82, 0xc9, 0x7d, 0xfa, 0x59, 0x47, 0xf0, 0xad, 0xd4, 0xa2, 0xaf, 0x9c, 0xa4, 0x72, 0xc0,
    0xb7, 0xfd, 0x93, 0x26, 0x36, 0x3f, 0xf7, 0xcc, 0x34, 0xa5, 0xe5, 0xf1, 0x71, 0xd8, 0x31, 0x15,
    0x04, 0xc7, 0x23, 0xc3, 0x18, 0x96, 0x05, 0x9a, 0x07, 0x12, 0x80, 0xe2, 0xeb, 0x27, 0xb2, 0x75,
    0x09, 0x83, 0x2c, 0x1a, 0x1b, 0x6e, 0x5a, 0xa0, 0x52, 0x3b, 0xd6, 0xb3, 0x29, 0xe3, 0x2f, 0x84,
    0x53, 0xd1, 0x00, 0xed, 0x20, 0xfc, 0xb1, 0x5b, 0x6a, 0xcb, 0xbe, 0x39, 0x4a, 0x4c, 0x58, 0xcf,
    0xd0, 0xef, 0xaa, 0xfb, 0x43, 0x4d, 0x33, 0x85, 0x45, 0xf9, 0x02, 0x7f, 0x50, 0x3c, 0x9f, 0xa8,
    0x51, 0xa3, 0x40, 0x8f, 0x92, 0x9d, 0x38, 0xf5, 0xbc, 0xb6, 0xda, 0x21, 0x10, 0xff, 0xf3, 0xd2,
    0xcd, 0x0c, 0x13, 0xec, 0x5f, 0x97, 0x44, 0x17, 0xc4, 0xa7, 0x7e, 0x3d, 0x64, 0x5d, 0x19, 0x73,
    0x60, 0x81, 0x4f, 0xdc, 0x22, 0x2a, 0x90, 0x88, 0x46, 0xee, 0xb8, 0x14, 0xde, 0x5e, 0x0b, 0xdb,
    0xe0, 0x32, 0x3a, 0x0a, 0x49, 0x06, 0x24, 0x5c, 0xc2, 0xd3, 0xac, 0x62, 0x91, 0x95, 0xe4, 0x79,
    0xe7, 0xc8, 0x37, 0x6d, 0x8d, 0xd5, 0x4e, 0xa9, 0x6c, 0x56, 0xf4, 0xea, 0x65, 0x7a, 0xae, 0x08,
    0xba, 0x78, 0x25, 0x2e, 0x1c, 0xa6, 0xb4, 0xc6, 0xe8, 0xdd, 0x74, 0x1f, 0x4b, 0xbd, 0x8b, 0x8a,
    0x70, 0x3e, 0xb5, 0x66, 0x48, 0x03, 0xf6, 0x0e, 0x61, 0x35, 0x57, 0xb9, 0x86, 0xc1, 0x1d, 0x9e,
    0xe1, 0xf8, 0x98, 0x11, 0x69, 0xd9, 0x8e, 0x94, 0x9b, 0x1e, 0x87, 0xe9, 0xce, 0x55, 0x28, 0xdf,
    0x8c, 0xa1, 0x89, 0x0d, 0xbf, 0xe6, 0x42, 0x68, 0x41, 0x99, 0x2d, 0x0f, 0xb0, 0x54, 0xbb, 0x16,
]
_AES_INV_SBOX = [0] * 256
for _i, _v in enumerate(_AES_SBOX):
    _AES_INV_SBOX[_v] = _i
_AES_RCON = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1b, 0x36, 0x6c, 0xd8, 0xab, 0x4d]


def _aes_xtime(a):
    a <<= 1
    if a & 0x100:
        a = (a ^ 0x1b) & 0xff
    return a


def _aes_mul(a, b):
    r = 0
    while b:
        if b & 1:
            r ^= a
        a = _aes_xtime(a)
        b >>= 1
    return r & 0xff


def _aes_expand_key(key):
    key = list(bytearray(key))
    nk = len(key) // 4
    nr = nk + 6
    w = [key[4 * i:4 * i + 4] for i in range(nk)]
    for i in range(nk, 4 * (nr + 1)):
        t = list(w[i - 1])
        if i % nk == 0:
            t = t[1:] + t[:1]
            t = [_AES_SBOX[x] for x in t]
            t[0] ^= _AES_RCON[i // nk - 1]
        elif nk > 6 and i % nk == 4:
            t = [_AES_SBOX[x] for x in t]
        w.append([w[i - nk][j] ^ t[j] for j in range(4)])
    return w, nr


def _aes_add_key(s, w, rnd):
    for c in range(4):
        for r in range(4):
            s[r][c] ^= w[rnd * 4 + c][r]


def _aes_enc_block(block, w, nr):
    s = [[block[r + 4 * c] for c in range(4)] for r in range(4)]
    _aes_add_key(s, w, 0)
    for rnd in range(1, nr + 1):
        for r in range(4):
            for c in range(4):
                s[r][c] = _AES_SBOX[s[r][c]]
        for r in range(1, 4):
            s[r] = s[r][r:] + s[r][:r]
        if rnd != nr:
            for c in range(4):
                a = [s[r][c] for r in range(4)]
                s[0][c] = _aes_mul(a[0], 2) ^ _aes_mul(a[1], 3) ^ a[2] ^ a[3]
                s[1][c] = a[0] ^ _aes_mul(a[1], 2) ^ _aes_mul(a[2], 3) ^ a[3]
                s[2][c] = a[0] ^ a[1] ^ _aes_mul(a[2], 2) ^ _aes_mul(a[3], 3)
                s[3][c] = _aes_mul(a[0], 3) ^ a[1] ^ a[2] ^ _aes_mul(a[3], 2)
        _aes_add_key(s, w, rnd)
    return [s[r][c] for c in range(4) for r in range(4)]


def _aes_dec_block(block, w, nr):
    s = [[block[r + 4 * c] for c in range(4)] for r in range(4)]
    _aes_add_key(s, w, nr)
    for rnd in range(nr - 1, -1, -1):
        for r in range(1, 4):
            s[r] = s[r][-r:] + s[r][:-r]
        for r in range(4):
            for c in range(4):
                s[r][c] = _AES_INV_SBOX[s[r][c]]
        _aes_add_key(s, w, rnd)
        if rnd != 0:
            for c in range(4):
                a = [s[r][c] for r in range(4)]
                s[0][c] = _aes_mul(a[0], 14) ^ _aes_mul(a[1], 11) ^ _aes_mul(a[2], 13) ^ _aes_mul(a[3], 9)
                s[1][c] = _aes_mul(a[0], 9) ^ _aes_mul(a[1], 14) ^ _aes_mul(a[2], 11) ^ _aes_mul(a[3], 13)
                s[2][c] = _aes_mul(a[0], 13) ^ _aes_mul(a[1], 9) ^ _aes_mul(a[2], 14) ^ _aes_mul(a[3], 11)
                s[3][c] = _aes_mul(a[0], 11) ^ _aes_mul(a[1], 13) ^ _aes_mul(a[2], 9) ^ _aes_mul(a[3], 14)
    return [s[r][c] for c in range(4) for r in range(4)]


class _AES(object):
    """AES-CBC（128/192/256），纯 Python，只实现本站所需的 CBC"""

    def __init__(self, key):
        self.w, self.nr = _aes_expand_key(key)

    def _blocks_enc(self, data):
        out = []
        for i in range(0, len(data), 16):
            out.extend(_aes_enc_block(list(bytearray(data[i:i + 16])), self.w, self.nr))
        return out

    def _blocks_dec(self, data):
        out = []
        for i in range(0, len(data), 16):
            out.extend(_aes_dec_block(list(bytearray(data[i:i + 16])), self.w, self.nr))
        return out

    @staticmethod
    def _pad(data):
        n = 16 - len(data) % 16
        return bytes(bytearray(data)) + bytes(bytearray([n] * n))

    @staticmethod
    def _unpad(data):
        data = bytes(bytearray(data))
        if not data:
            return data
        n = bytearray(data)[-1]
        if n < 1 or n > 16 or n > len(data):
            return data
        return data[:-n]

    def cbc_encrypt(self, data, iv):
        data = self._pad(data)
        prev = bytes(bytearray(iv))
        out = []
        for i in range(0, len(data), 16):
            blk = bytes(bytearray([data[i + j] ^ prev[j] for j in range(16)]))
            prev = bytes(bytearray(self._blocks_enc(blk)))
            out.append(prev)
        return b"".join(out)

    def cbc_decrypt(self, data, iv):
        data = bytes(bytearray(data))
        prev = bytes(bytearray(iv))
        out = []
        for i in range(0, len(data), 16):
            blk = data[i:i + 16]
            dec = bytes(bytearray(self._blocks_dec(blk)))
            out.append(bytes(bytearray([dec[j] ^ prev[j] for j in range(16)])))
            prev = blk
        return self._unpad(b"".join(out))


# ---------------------------------------------------------------- 工具函数
def _gz(data):
    """gzip 压缩（站点前端用 CompressionStream('gzip')）"""
    try:
        return gzip.compress(data)
    except Exception:
        buf = _BytesIO()
        f = gzip.GzipFile(fileobj=buf, mode="wb")
        f.write(data)
        f.close()
        return buf.getvalue()


def _un_gz(data):
    try:
        return gzip.decompress(data)
    except Exception:
        buf = _BytesIO(data)
        return gzip.GzipFile(fileobj=buf, mode="rb").read()


def _rand_hex(n):
    """随机 n 字节的 hex 串（兼容 py2/Jython：str 无 .hex()）"""
    try:
        raw = os.urandom(n)
    except Exception:
        return "".join(["%02x" % random.randint(0, 255) for _ in range(n)])
    if hasattr(raw, "hex"):
        return raw.hex()
    return "".join(["%02x" % ord(c) for c in raw])


def _uuid4():
    h = _rand_hex(16)
    return "%s-%s-%s-%s-%s" % (h[0:8], h[8:12], h[12:16], h[16:20], h[20:32])


_SENSITIVE_KEYS = ("token", "deviceid", "device_id", "sessionid", "sign", "apikey", "api_key",
                   "secret", "password", "authorization", "cookie", "requestid")


def _mask(text):
    """脱敏：任何日志/异常里出现的密钥、令牌、长串签名一律打码"""
    s = text if isinstance(text, str) else str(text)
    for k in _SENSITIVE_KEYS:
        s = re.sub(r"(?i)(%s[\"']?\s*[:=]\s*[\"']?)([^\"',&\s}]{4,})" % k,
                   lambda m: m.group(1) + m.group(2)[:4] + "****", s)
    s = re.sub(r"(?i)([0-9a-f]{24,})", lambda m: m.group(1)[:6] + "****", s)
    return s


# ---------------------------------------------------------------- 站点常量
DEFAULT_SITE = "https://jinji.video"
BACKUP_SITES = ["https://sagj.tv"]
DEFAULT_PROXY = ""            # CF 反代地址；留空=直连（本站实测可直连，200）
API_WEB_KEY = "7961beb44246e3012ce228d6b5ced05a"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

# 分类表（实测自站点导航 nav_id / board_id）
CATEGORIES = [
    ("rec", "⭐ 推荐", {"order": "new"}),
    ("free", "✅ 免费专区", {"pay_type": "free"}),
    ("new", "🆕 最新", {"board_id": "short", "order": "new"}),
    ("nav4", "短剧", {"nav_id": 4}),
    ("nav9", "成人短剧", {"nav_id": 9}),
    ("nav7", "漫剧", {"nav_id": 7}),
    ("nav8", "韩漫", {"nav_id": 8}),
    ("nav11", "二次元", {"nav_id": 11}),
    ("nav12", "BL专区", {"nav_id": 12}),
    ("nav5", "抖阴", {"nav_id": 5}),
    ("nav16", "糖心VLOG", {"nav_id": 16}),
    ("nav15", "AI魔改", {"nav_id": 15}),
    ("nav13", "短视频", {"nav_id": 13}),
]

_CAT_CONF = dict([(c[0], c[2]) for c in CATEGORIES])

_ORDERS = [{"n": "最新", "v": "new"}, {"n": "最热", "v": "hot"},
           {"n": "播放最多", "v": "click"}, {"n": "收藏最多", "v": "favorite"}]

# 未成年条目直接剔除，不采集不写入
_MINOR_MARKERS = ("未成年", "幼女", "幼齿", "萝莉", "小学生", "中学生", "初中生", "高中生",
                  "儿童", "女童", "童女", "幼儿园", "小学", "初中", "高中", "中学",
                  "小朋友", "幼童")


class Spider(_BaseSpider):

    # ------------------------------------------------ 基础
    def getName(self, *args):
        return "禁忌短剧"

    def init(self, extend="", *args, **kwargs):
        ext = (extend or "").strip()
        parts = [p.strip() for p in ext.split("|") if p.strip()] if ext else []
        hosts = [p for p in parts if p.startswith("http")]
        host = hosts[0] if hosts else DEFAULT_SITE
        proxy = hosts[1] if len(hosts) > 1 else DEFAULT_PROXY
        token = ""
        cookie = ""
        for p in parts:
            low = p.lower()
            if low.startswith("token:"):
                token = p.split(":", 1)[1].strip()
            elif low.startswith("cookie:"):
                cookie = p.split(":", 1)[1].strip()

        self.extend = ext
        self.rawSite = host.rstrip("/")          # 用户/默认给的原始域名
        self.siteUrl = self.rawSite              # 实际请求用的域名（可被反代/切镜像改写）
        self.proxy = proxy.rstrip("/")           # 非空时所有请求走该反代
        self.deviceId = _rand_hex(16)
        self.token = token                       # 站点账号 token（可选）
        self.timeout = 15
        self.debug = False
        self._host_idx = 0
        self._ep_cache = {}                      # m3u8 url -> (drama_id, episode_id, kind)
        self._pg_seen = {}                       # tid -> 已出过的 vod_id 集合（翻页到底判定）
        self.header = {
            "User-Agent": UA,
            "Referer": self.rawSite + "/",
            "Origin": self.rawSite,
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        if cookie:
            self.header["Cookie"] = cookie
        return self

    def isVideoFormat(self, url, *args):
        try:
            u = (url or "").lower()
            return ".m3u8" in u or ".mp4" in u or "/ysapi/m3u8/" in u
        except Exception:
            return False

    def manualVideoCheck(self, *args):
        return False

    def action(self, action, *args):
        return {"msg": "ok"}

    def destroy(self, *args):
        return None

    # ------------------------------------------------ 网络层
    def _log(self, *a):
        if self.debug:
            try:
                print("[jinji] " + _mask(" ".join([str(x) for x in a])))
            except Exception:
                pass

    def _request(self, url, data=None, headers=None, method="POST", raw=False):
        h = dict(self.header)
        if headers:
            h.update(headers)
        last = None
        for _ in range(2):
            try:
                if _HAS_REQUESTS:
                    args = {"headers": h, "timeout": self.timeout}
                    if method == "POST":
                        r = requests.post(url, data=data, **args)
                    else:
                        r = requests.get(url, **args)
                    if raw:
                        return r.content
                    return r.text
                req = _urlreq.Request(url, data=data, headers=h)
                if method != "POST":
                    req.get_method = lambda: "GET"
                resp = _urlreq.urlopen(req, timeout=self.timeout)
                body = resp.read()
                if raw:
                    return body
                if _PY2:
                    return body
                return body.decode("utf-8", "ignore")
            except Exception as e:
                last = e
                self._log("request fail:", _mask(str(e)), url)
                if self._switch_host():
                    url = self._redo_url(url)
        if last:
            raise last
        return "" if not raw else b""

    def _switch_host(self):
        """主域名失败时切备用镜像（反代优先）"""
        if self.proxy:
            return False
        pool = BACKUP_SITES
        if self._host_idx >= len(pool):
            return False
        self._host_idx += 1
        self.siteUrl = pool[self._host_idx - 1].rstrip("/")
        self._log("switch host ->", self.siteUrl)
        return True

    def _redo_url(self, old):
        return old.replace(self.rawSite, self.siteUrl)

    def _fix_url(self, url):
        """相对地址补全；配置了反代则整体走反代（铁律15：按 host 改写，不动业务参数）"""
        if not url:
            return ""
        u = url.strip()
        if u.startswith("//"):
            u = "https:" + u
        elif not u.startswith("http"):
            u = self.siteUrl + "/" + u.lstrip("/")
        if self.proxy:
            if "%s" in self.proxy:
                return self.proxy.replace("%s", u)
            return self.proxy.rstrip("/") + "/" + u
        return u

    # ------------------------------------------------ 加密接口
    def _api_key(self, request_id):
        raw = bytes(bytearray.fromhex(request_id.replace("-", "")))
        return hmac.new(API_WEB_KEY.encode("utf-8"), raw, hashlib.sha256).digest()

    def _encrypt(self, obj, request_id):
        plain = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        iv = bytes(bytearray.fromhex(_rand_hex(16)))
        return iv + _AES(self._api_key(request_id)).cbc_encrypt(_gz(plain), iv)

    def _decrypt(self, blob, request_id):
        blob = bytes(bytearray(blob))
        if blob[:1] in (b"{", b"["):
            try:
                return json.loads(blob.decode("utf-8"))
            except Exception:
                pass
        if len(blob) < 32:
            raise ValueError("payload too short")
        plain = _AES(self._api_key(request_id)).cbc_decrypt(blob[16:], blob[:16])
        plain = _un_gz(plain)
        if not _PY2:
            plain = plain.decode("utf-8", "ignore")
        return json.loads(plain)

    def _api(self, path, body=None, method="POST"):
        url = self.siteUrl + "/api" + path
        if method == "GET":
            txt = self._request(url, method="GET")
            if isinstance(txt, bytes):
                txt = txt.decode("utf-8", "ignore")
            return json.loads(txt)
        request_id = _uuid4()
        payload = {
            "deviceId": self.deviceId,
            "token": self.token,
            "domain": self.rawSite.replace("https://", "").replace("http://", "").split("/")[0],
            "shareCode": "",
            "channel": "web",
            "ip": "",
            "data": body or {},
        }
        blob = self._encrypt(payload, request_id)
        headers = {
            "content-type": "application/octet-stream",
            "version": "1.0.0",
            "deviceType": "web",
            "time": str(int(time.time())),
            "requestId": request_id,
        }
        raw = self._request(url, data=blob, headers=headers, method="POST", raw=True)
        if _PY2 and isinstance(raw, str):
            raw = bytes(bytearray(raw))
        return self._decrypt(raw, request_id)

    # ------------------------------------------------ 列表 -> 卡片
    def _cat_body(self, tid, pg, extend):
        body = {"page": int(pg or 1), "page_size": 12}
        tid = (tid or "rec").strip()
        conf = _CAT_CONF.get(tid) or {}
        for k in ("board_id", "pay_type"):
            if conf.get(k):
                body[k] = conf[k]
        if tid.startswith("nav") and tid[3:].isdigit():
            body["nav_id"] = int(tid[3:])
        elif conf.get("nav_id"):
            body["nav_id"] = conf["nav_id"]
        if tid == "free":
            body["pay_type"] = "free"
        if conf.get("order"):
            body["order"] = conf["order"]
        if extend:
            if isinstance(extend, dict):
                if extend.get("order"):
                    body["order"] = extend["order"]
                if extend.get("pay_type"):
                    body["pay_type"] = extend["pay_type"]
            elif isinstance(extend, str):
                m = re.search(r"order=([a-z]+)", extend)
                if m:
                    body["order"] = m.group(1)
                if "pay_type=free" in extend or "free=1" in extend:
                    body["pay_type"] = "free"
        return body

    def _is_minor(self, item):
        """未成年条目一律剔除（铁律13）"""
        blob = "%s %s %s" % (item.get("name", ""), item.get("category", ""),
                             " ".join([t.get("name", "") for t in (item.get("tags") or [])
                                       if isinstance(t, dict)]))
        for k in _MINOR_MARKERS:
            if k in blob:
                return True
        return False

    def _vod(self, item):
        try:
            vid = item.get("id") or item.get("drama_id") or item.get("video_id") or ""
            if not vid:
                return None
            if item.get("type") in ("ad", "app"):
                return None
            if self._is_minor(item):
                self._log("skip minor:", item.get("name"))
                return None
            pic = item.get("img_x_source") or item.get("img") or item.get("img_x") or ""
            remark = item.get("episode_total") or item.get("duration") or ""
            try:
                et = int(item.get("episode_total") or 0)
                remark = ("全%d集" % et) if et > 1 else (item.get("duration") or "正片")
            except Exception:
                pass
            # 卡片上直接标出能不能完整播（站点 vip 条目只给十几秒试看）
            pay = str(item.get("pay_type") or "").lower()
            locked = (str(item.get("is_locked") or "") == "y"
                      or str(item.get("status") or "") == "locked"
                      or item.get("can_watch") is False)
            if pay == "free" and not locked:
                remark = remark + " · 可播"
            elif pay != "free" or locked:
                remark = remark + " · VIP试看"
            return {
                "vod_id": vid,
                "vod_name": item.get("name") or "",
                "vod_pic": pic,
                "vod_remarks": remark,
                "vod_year": (item.get("upload_date") or item.get("time_label") or "")[:10],
                "vod_area": item.get("content_type_name") or "",
                "vod_actor": "",
                "vod_director": item.get("category") or "",
                "vod_content": item.get("description") or item.get("name") or "",
            }
        except Exception:
            return None

    def _list_of(self, data):
        items = (data or {}).get("items")
        if not isinstance(items, list):
            items = (data or {}).get("data") or []
        out = []
        for it in items:
            if not isinstance(it, dict):
                continue
            v = self._vod(it)
            if v:
                out.append(v)
        return out

    # ------------------------------------------------ 内容接口
    def homeContent(self, filter=False, *args):
        classes = []
        for tid, name, _ in CATEGORIES:
            classes.append({"type_id": tid, "type_name": name})
        filters = {}
        for tid, _, conf in CATEGORIES:
            filters[tid] = [{"key": "order", "name": "排序", "value": _ORDERS}]
            if not conf:
                filters[tid] = []
        data = {"class": classes, "filters": filters}
        try:
            resp = self._api("/search/movie", self._cat_body("rec", 1, None))
            data["list"] = self._list_of(resp.get("data"))
        except Exception as e:
            self._log("home fail", _mask(str(e)))
            data["list"] = []
        return data

    def homeVideoContent(self, *args):
        try:
            resp = self._api("/search/movie", self._cat_body("rec", 1, None))
            return {"list": self._list_of(resp.get("data"))}
        except Exception as e:
            self._log("homeVideo fail", _mask(str(e)))
            return {"list": []}

    def categoryContent(self, tid, pg, filter=False, extend=None, *args):
        page = int(pg or 1)
        items = []
        total = 0
        pagecount = page
        try:
            resp = self._api("/search/movie", self._cat_body(tid, page, extend))
            d = resp.get("data") or {}
            items = self._list_of(d)
            # 站点到底后会回卷到第 1 页（total / last_page 都是假的，实测不写死）
            # 用"这一页的 id 是否全都出过"来判定结束
            seen = self._pg_seen.setdefault(tid, set())
            ids = [x.get("vod_id") for x in items if x.get("vod_id")]
            fresh = [i for i in ids if i not in seen]
            if page > 1 and items and not fresh:
                self._log("category end(回卷):", tid, page)
                return {"page": page, "pagecount": page, "limit": 12, "total": 0, "list": []}
            seen.update(ids)
            total = len(items)
            pagecount = page + 1 if items else page
        except Exception as e:
            self._log("category fail", tid, _mask(str(e)))
        return {"page": page, "pagecount": pagecount, "limit": 12, "total": total, "list": items}

    def detailContent(self, ids, *args):
        vid = ids[0] if isinstance(ids, (list, tuple)) else ids
        vid = str(vid).strip()
        try:
            resp = self._api("/movie/detail", {"id": vid})
            d = resp.get("data") or {}
            if not d:
                return {"list": []}

            episodes = []          # 可完整播放的集
            preview = []           # 站点只给试看的源
            seen = set()
            for grp in (d.get("links") or []):
                for ep in (grp.get("items") or []):
                    url = ep.get("m3u8_url") or ep.get("hevc_m3u8_url") or ""
                    if not url:
                        continue
                    # 锁定集就算带着地址也不算可播（站点偶尔会塞试看地址进来）
                    locked = (str(ep.get("is_locked") or "") == "y"
                              or str(ep.get("status") or "") == "locked"
                              or ep.get("can_watch") is False)
                    if locked:
                        continue
                    name = ep.get("name") or ("第%s集" % ep.get("episode_no", ""))
                    full = self._fix_url(url)
                    if full in seen:
                        continue
                    seen.add(full)
                    episodes.append((name, full))
                    self._cache_ep(url, vid, ep.get("episode_id") or ep.get("id") or "")

            # 试看源只在 play_links 里，且整部剧共用一个十几秒的片段
            for pl in (d.get("play_links") or []):
                url = pl.get("preview_m3u8_url") or pl.get("m3u8_url") or ""
                if not url:
                    continue
                full = self._fix_url(url)
                if full in seen:
                    continue
                seen.add(full)
                nm = (pl.get("name") or "线路") + "试看"
                preview.append((nm, full))

            lines = []
            if episodes:
                lines.append(("✅ 可播", episodes))
            elif preview:
                # 整部剧一集可播的都没有时才给试看线，免得有正片还掺一条十几秒的
                lines.append(("⏱ 试看片段(非正片)", preview))
            if not lines:
                # 连试看都没有时给一条明确提示，避免详情页空白
                lines.append(("⚠️ 暂无可用源", [("本站未放出播放地址", self.rawSite + "/")]))

            et = str(d.get("episode_total") or "")
            remark = ("全%s集" % et) if et and et != "1" else (d.get("duration") or "正片")
            pay = str(d.get("pay_type") or "")
            if episodes:
                remark = remark + "·可播"
            elif pay and pay != "free":
                remark = remark + "·VIP试看"

            desc = d.get("description") or d.get("name") or ""
            if not episodes and preview:
                desc = ("【本站为付费站点，该条目只放出试看片段（十几秒，不是正片）；"
                        "「✅ 免费专区」里的条目可完整播放】\n") + desc

            vod = {
                "vod_id": vid,
                "vod_name": d.get("name") or "",
                "vod_pic": d.get("img_x_source") or d.get("img") or "",
                "vod_remarks": remark,
                "vod_year": (d.get("upload_date") or "")[:10],
                "vod_area": d.get("content_type_name") or "",
                "vod_actor": " ".join([a.get("nickname", "") for a in (d.get("actors") or [])
                                       if isinstance(a, dict)]),
                "vod_director": d.get("cat_name") or "",
                "vod_content": desc,
                "vod_play_from": "$$$".join([n for n, _ in lines]),
                "vod_play_url": "$$$".join(["#".join(["%s$%s" % (n, u) for n, u in eps])
                                            for _, eps in lines]),
            }
            return {"list": [vod]}
        except Exception as e:
            self._log("detail fail", vid, _mask(str(e)))
            return {"list": []}

    def searchContent(self, key, quick=False, pg="1", *args):
        result = {"list": []}
        try:
            resp = self._api("/search/movie",
                             {"keyword": key, "page": int(pg or 1), "page_size": 12})
            result["list"] = self._list_of(resp.get("data"))
        except Exception as e:
            self._log("search fail", _mask(str(e)))
        return result

    # ------------------------------------------------ 播放
    def _cache_ep(self, url, drama_id, episode_id):
        """记住 m3u8 地址对应的剧/集，播放时好重取最新签名"""
        try:
            if len(self._ep_cache) > 500:
                self._ep_cache = {}
            self._ep_cache[str(url)] = (str(drama_id), str(episode_id))
        except Exception:
            pass

    def _fresh_url(self, drama_id, episode_id):
        """重取详情拿该集最新地址（站点 m3u8 带时效签名）；失败返回空串"""
        if not drama_id:
            return ""
        try:
            d = (self._api("/movie/detail", {"id": drama_id}).get("data") or {})
            for grp in (d.get("links") or []):
                for ep in (grp.get("items") or []):
                    eid = str(ep.get("episode_id") or ep.get("id") or "")
                    if episode_id and eid != str(episode_id):
                        continue          # 必须精确对上那一集，宁可退回原地址也不串集
                    u = ep.get("m3u8_url") or ep.get("hevc_m3u8_url") or ""
                    if u:
                        return self._fix_url(u)
        except Exception as e:
            self._log("refresh fail", _mask(str(e)))
        return ""

    def playerContent(self, flag, id, vipFlags=None, *args):
        url = self._fix_url(id)
        header = {
            "User-Agent": UA,
            "Referer": self.rawSite + "/",
            "Origin": self.rawSite,
        }
        # 取到过对应剧集就刷新一次地址，挂了签名/换域名也不会一晚上就播不动
        info = self._ep_cache.get(str(id)) or self._ep_cache.get(url)
        if info:
            fresh = self._fresh_url(info[0], info[1])
            if fresh:
                url = fresh
        return {"parse": 0, "jx": 0, "url": url, "header": header}

    # ------------------------------------------------ m3u8 清洗 / 本地代理
    def _is_ad_segment(self, url, dur=0.0, prev_dur=0.0, next_dur=0.0):
        """只砍强特征广告：/ad/ 类路径 + 被长段夹住的 ≤0.2s 空帧（不按时长硬删）"""
        low = (url or "").lower()
        for pat in ("/ad/", "/ads/", "/adv/", "/advert", "/gg/", "/guanggao", "ad_", "-ad-"):
            if pat in low:
                return True
        if 0 < dur <= 0.2 and prev_dur >= 1.0 and next_dur >= 1.0:
            return True
        return False

    def _abs(self, url, base):
        if not url:
            return url
        if url.startswith("http"):
            return url
        if url.startswith("//"):
            return "https:" + url
        m = re.match(r"^(https?://[^/]+)", base or "")
        host = m.group(1) if m else self.siteUrl
        if url.startswith("/"):
            return host + url
        path = (base or "").split("?")[0]
        path = path[:path.rfind("/") + 1] if "/" in path[8:] else host + "/"
        return path + url

    def _clean_m3u8(self, text, base=""):
        """过滤广告分片 + 补全相对地址；分广告两遍扫描（先量时长再决定删不删）"""
        if not text or "#EXTM3U" not in text:
            return text
        lines = [ln.rstrip("\r") for ln in text.split("\n")]
        segs = []
        out_head = []
        i = 0
        while i < len(lines):
            ln = lines[i]
            if ln.startswith("#EXTINF:"):
                dur = 0.0
                try:
                    dur = float(ln.split(":", 1)[1].split(",")[0])
                except Exception:
                    dur = 0.0
                extinf = [ln]
                i += 1
                while i < len(lines) and lines[i].startswith("#") and not lines[i].startswith("#EXTINF:"):
                    extinf.append(lines[i])
                    i += 1
                uri = ""
                if i < len(lines) and lines[i] and not lines[i].startswith("#"):
                    uri = lines[i].strip()
                    i += 1
                segs.append({"dur": dur, "extinf": extinf, "uri": uri})
                continue
            out_head.append(ln)
            i += 1
        body = []
        for idx, s in enumerate(segs):
            prev_d = segs[idx - 1]["dur"] if idx > 0 else 0.0
            next_d = segs[idx + 1]["dur"] if idx + 1 < len(segs) else 0.0
            if s["uri"] and self._is_ad_segment(s["uri"], s["dur"], prev_d, next_d):
                continue
            body.extend(s["extinf"])
            if s["uri"]:
                body.append(self._abs(s["uri"], base))
        return "\n".join(out_head + body) + "\n"

    def localProxy(self, param, *args):
        """本地代理：拉取 m3u8 并清洗广告分片后回吐（非空壳实现）"""
        try:
            url = ""
            if isinstance(param, dict):
                url = param.get("url") or ""
            elif isinstance(param, str):
                m = re.search(r"(?:^|&)url=([^&]+)", param)
                url = m.group(1) if m else param
                try:
                    from urllib.parse import unquote as _unq  # py3
                except Exception:
                    from urllib import unquote as _unq       # py2
                url = _unq(url)
            if not url:
                return [400, "text/plain", "missing url"]
            headers = {"User-Agent": UA, "Referer": self.rawSite + "/"}
            body = self._request(url, headers=headers, method="GET", raw=True)
            if isinstance(body, bytes):
                text = body.decode("utf-8", "ignore")
            else:
                text = body
            if "#EXTM3U" in text:
                return [200, "application/vnd.apple.mpegurl", self._clean_m3u8(text, url)]
            return [200, "application/octet-stream", body]
        except Exception as e:
            self._log("localProxy fail", _mask(str(e)))
            return [500, "text/plain", "proxy error"]
