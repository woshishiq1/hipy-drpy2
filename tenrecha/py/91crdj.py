# -*- coding: utf-8 -*-
# @tvbox-source
r"""
91成人短剧 (https://91crdj.com) —— TVBox / dr_py / webhome 单文件爬虫源  v2
====================================================================
v2 修复清单（2026-09-13 实测）
--------------------------------------------------------------------
1) 【详情页没有封面】根因：详情页 og:image 指向 expose.eisees.com，
   实测 HTTP 200 但 body = 0 字节（空图）。真实海报在
   <img class="p-img" data-src="https://pic.zdmhyg.cn/...">。
   修法：封面取值顺序改为  img.p-img[data-src] → data-original →
   data-echo → src(排除 base64 占位图) → og:image，并拉黑 eisees 域。
2) 【封面 URL 每次都变 → 图片缓存全 miss】pic.zdmhyg.cn 的图带
   ?auth_key=<ts>-0-0-<md5>，两小时过期且每次请求都不同。实测去掉
   该参数后 5/5 张图依然 200 正常返回（59952/77056/78048/138752/
   114320 字节）。修法：剥掉 auth/sign/token 类一次性签名参数，
   URL 变稳定 → 命中 TVBox 图片缓存，回访秒开。
3) 【详情页慢】旧版 detailContent 发 2~3 次请求：
   先抓 /{ch}/{id}-temp/（404/抖动即空）→ 读 canonical → 再抓一次
   → 没集数再抓播放页。修法：vod_id 里直接带完整路径
   （格式 "channel|/channel/id-slug/"），详情 1 次请求直达。
   浏览→播放 总请求 5 次 → 3 次。
4) 【搜索结果整条丢失】漫画/小说链接形如 /manhua/96/（无 slug），
   旧正则 /(\d+)- 要求必须带 '-'，匹配不到就 continue 丢弃整条。
   修法：_split_path 同时兼容带 slug 与不带 slug。
5) 【站点抖动即白屏】实测会 WinError 10054 强制断连。修法：
   超时 15s→10s，失败快速重试 1 次；详情抓不到时用列表阶段缓存的
   条目兜底，保证有封面有播放地址。

· 路由：列表 /{channel}/ 与 /{channel}/page/{N}/，详情 /{channel}/{id}-{slug}/，
        播放 /{channel}/{id}-{slug}/{ep}/，搜索 /search/?q={kw}&page={N}
· 反爬：无验证门控，正常 UA 即可；但同 IP 高频会断连，注意重试与间隔。
· TVBox 配置：{"key":"91crdj","name":"91成人短剧","type":3,"api":"py://91crdj.py"}
"""

from __future__ import print_function

import re
import json
import time
import zlib

# ---- 三级 BaseSpider 导入 ----
try:
    from base.spider import Spider as BaseSpider
except Exception:
    try:
        from base.spider import BaseSpider
    except Exception:
        class BaseSpider(object):
            pass

# ---- 网络库双版本导入（仅标准库，零第三方依赖） ----
try:
    from urllib.request import (Request, build_opener, HTTPCookieProcessor,
                                HTTPSHandler, urlopen)
    from urllib.parse import urlencode, quote, unquote, urljoin, parse_qsl, urlparse
except Exception:
    from urllib2 import Request, build_opener, HTTPCookieProcessor, HTTPSHandler, urlopen
    from urllib import urlencode, quote, unquote
    from urlparse import urljoin, parse_qsl, urlparse

try:
    import ssl as _ssl
except Exception:
    _ssl = None

try:
    import threading as _threading
    _LOCK = _threading.Lock()
except Exception:
    _threading = None
    _LOCK = None

# ---- 封面 AES 解密（该站图片是密文，浏览器端由 crypto-worker 解出）----
# crypto-worker.js: media_key/media_iv 为下划线分隔的 ASCII 码，CBC + NoPadding
IMG_KEY = "".join(chr(int(x)) for x in
                  "102_53_100_57_54_53_100_102_55_53_51_51_54_50_55_48".split("_"))
IMG_IV = "".join(chr(int(x)) for x in
                 "57_55_98_54_48_51_57_52_97_98_99_50_102_98_101_49".split("_"))
IMG_PROXY = 1                       # 0 = 直接返回密文 URL（壳子不支持代理时用）
PROXY_BASE = "http://127.0.0.1:9978"  # dr_py 默认代理端口，可用 extend 覆盖
_PIC_CACHE = {}                     # 图片URL -> 解密后字节
_PIC_CACHE_MAX = 80

# ==================== 模块级常量 ====================

NAME = "91成人短剧"
HOST = "https://91crdj.com"
BASE = HOST
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")
TIMEOUT = 8           # 抖动时别白等（原 15s）
RETRY = 1             # 连接被强制断开时快速重试 1 次
MIN_GAP = 0.2         # 同 IP 高频会 10054 断连，做最小间隔节流
REFERER = HOST + "/"

_CUR_HOST = HOST
_CACHE = {}
_ITEM_POOL = {}       # vod_id -> {name,pic,remarks}  详情页兜底用
_TTL_LIST = 300
_TTL_DETAIL = 1800
_TTL_PLAY = 120       # m3u8 直链带短时签名，只做极短缓存
_OPENER = None

DEFAULT_CLASSES = [
    {"type_id": "duanju", "type_name": "成人短剧"},
    {"type_id": "manju", "type_name": "成人漫剧"},
    {"type_id": "zhenrenju", "type_name": "真人剧"},
    {"type_id": "shipin", "type_name": "成人视频"},
    {"type_id": "manhua", "type_name": "成人漫画"},
    {"type_id": "xiaoshuo", "type_name": "成人小说"},
]
_TYPE_NAME = dict((c["type_id"], c["type_name"]) for c in DEFAULT_CLASSES)
_VALID = dict((c["type_id"], 1) for c in DEFAULT_CLASSES)

# ---- 封面相关 ----
# 占位图 / 无效图特征
_BAD_PIC = ("data:", "base64,", "load.gif", "loading.gif", "placeholder",
            "default.png", "nopic", "no-pic", "spacer.gif", "blank.gif",
            "logo", "eisees")   # eisees = 实测返回 0 字节的空图域
# 需要剥掉的一次性签名参数（剥掉后 URL 稳定，可命中图片缓存）
_AUTH_KEYS = ("auth_key", "authkey", "auth", "sign", "signature", "token",
              "expires", "expire", "e", "t", "ts", "time", "oss", "x-oss")
# 封面属性取值优先级
_PIC_ATTRS = ("data-original", "data-src", "data-echo", "data-lazy-src",
              "data-url", "data-thumb")

_RE_CARD = re.compile(r'<a class="card"', re.I)
_RE_HREF = re.compile(r'href="([^"]+)"')
_RE_TRACK_NAME = re.compile(r'data-track-item-name="([^"]*)"')
_RE_ALT = re.compile(r'\balt="([^"]*)"')
_RE_TITLE = re.compile(r'\btitle="([^"]*)"')
_RE_PTITLE = re.compile(r'<span class="p-title[^"]*">(.*?)</span>', re.S)
_RE_BADGE = re.compile(r'<span class="badge[^"]*">(.*?)</span>', re.S)
_RE_EPSFLAG = re.compile(r'<span class="eps-flag[^"]*">(.*?)</span>', re.S)
_RE_PIMG = re.compile(r'<img class="p-img"[^>]*>', re.I)
_RE_SRC = re.compile(r'(?<![-\w.])src\s*=\s*"([^"]+)"')
_RE_H1 = re.compile(r'<h1[^>]*>(.*?)</h1>', re.S)
_RE_EPGRID = re.compile(r'<div class="ep-grid">(.*?)</div>', re.S)
_RE_EP_A = re.compile(r'href="([^"]+)"[^>]*>\s*(\d+)\s*</a>')
_RE_OGIMG = re.compile(r'<meta[^>]*og:image[^>]*content="([^"]+)"', re.I)
_RE_OGDESC = re.compile(r'<meta[^>]*og:description[^>]*content="([^"]*)"', re.I)
_RE_METADESC = re.compile(r'<meta[^>]*name="description"[^>]*content="([^"]*)"', re.I)
_RE_TIME = re.compile(r'<time[^>]*>(\d{4})', re.I)
_RE_CANON = re.compile(r'rel="canonical"\s+href="([^"]+)"', re.I)
_RE_PAGE = re.compile(r'/page/(\d+)/')
_RE_PAGEDATA = re.compile(r'data-(?:max|total)[_-]page="(\d+)"', re.I)
_RE_CURRENT = re.compile(r'"current"\s*:\s*\{[^{}]*"src"\s*:\s*"([^"]+)"')
_RE_ANYM3U8 = re.compile(r'(https?://[^\'"\s<>]+?\.m3u8[^\'"\s<>]*)')


# ==================== 基础工具 ====================

def _strip(s):
    try:
        s = re.sub(r"<[^>]+>", "", s or "")
        s = re.sub(r"\s+", " ", s)
        return s.strip()
    except Exception:
        return ""


def _txt(s):
    s = _strip(s)
    s = (s.replace("&amp;", "&").replace("&quot;", '"').replace("&#39;", "'")
          .replace("&lt;", "<").replace("&gt;", ">").replace("&nbsp;", " "))
    return s.strip()


def _q(s):
    if s is None:
        return ""
    try:
        if isinstance(s, type(u"")):
            s = s.encode("utf-8")
    except Exception:
        pass
    try:
        return quote(s, safe="")
    except Exception:
        return str(s)


def _abs_url(u):
    if not u:
        return ""
    u = str(u).strip()
    if u.find("://") >= 0:
        return u
    if u.startswith("//"):
        return "https:" + u
    try:
        return urljoin(_CUR_HOST + "/", u.lstrip("/"))
    except Exception:
        return _CUR_HOST + "/" + u.lstrip("/")


def _split_path(href):
    """从 /{channel}/{id}-{slug}/ 或 /{channel}/{id}/ 解析 (channel, path)。

    漫画/小说链接没有 slug（形如 /manhua/96/），旧版正则要求 '-' 导致
    整条被丢弃，这里一并兼容。
    """
    if not href:
        return "", ""
    try:
        p = urlparse(href).path or href
    except Exception:
        p = href
    if not p.startswith("/"):
        p = "/" + p
    seg = [s for s in p.split("/") if s]
    if len(seg) < 2 or not seg[1]:
        return "", ""
    return seg[0], "/" + seg[0] + "/" + seg[1] + "/"


def _strip_auth(u):
    """剥掉 auth_key/sign/token 等一次性签名参数，让图片 URL 保持稳定。"""
    i = u.find("?")
    if i < 0:
        return u
    base, qs = u[:i], u[i + 1:]
    keep = []
    for part in qs.split("&"):
        if not part:
            continue
        k = part.split("=", 1)[0].strip().lower()
        if k in _AUTH_KEYS:
            continue
        keep.append(part)
    return base + ("?" + "&".join(keep) if keep else "")


def _clean_pic(u):
    """归一化封面：补全协议 → 拉黑占位图/空图域 → 剥签名参数。"""
    if not u:
        return ""
    u = str(u).strip().strip('"').strip("'")
    if not u:
        return ""
    low = u.lower()
    for bad in _BAD_PIC:
        if bad in low:
            return ""
    if "://" not in u and not u.startswith("//"):
        u = _abs_url(u)
    elif u.startswith("//"):
        u = "https:" + u
    return _strip_auth(u)


def _pick_pic(block):
    """在一个 HTML 片段里按优先级找封面。"""
    if not block:
        return ""
    for attr in _PIC_ATTRS:
        m = re.search(attr + r'\s*=\s*"([^"]+)"', block, re.I)
        if m:
            p = _clean_pic(m.group(1))
            if p:
                return p
    m = _RE_SRC.search(block)          # 负向后顾，避免匹配到 data-src
    if m:
        p = _clean_pic(m.group(1))
        if p:
            return p
    return ""


def _cache_get(key, ttl):
    item = _CACHE.get(key)
    if item and (time.time() - item[0]) < ttl:
        return item[1]
    return None


def _cache_set(key, value):
    try:
        if len(_CACHE) > 400:
            now = time.time()
            for k in list(_CACHE.keys()):
                try:
                    if now - _CACHE[k][0] > 3600:
                        del _CACHE[k]
                except Exception:
                    pass
        _CACHE[key] = (time.time(), value)
    except Exception:
        pass


def _pool_put(vid, name, pic, remarks):
    try:
        if len(_ITEM_POOL) > 800:
            _ITEM_POOL.clear()
        _ITEM_POOL[vid] = {"name": name, "pic": pic, "remarks": remarks}
    except Exception:
        pass


# ==================== 纯标准库 AES-128-CBC 解密 ====================
# 该站封面是 AES 密文（浏览器端由 crypto-worker.js 解出），TVBox 端必须自己解。
# 只用标准库：S 盒由 GF(2^8) 求逆+仿射变换生成，T 表只算一次，解 60KB 约 0.1~0.5s。
_AES_SBOX = [0] * 256
_AES_INV = [0] * 256
_AES_READY = [0]


def _aes_mul(a, b):
    p = 0
    for _ in range(8):
        if b & 1:
            p ^= a
        b >>= 1
        a <<= 1
        if a & 0x100:
            a ^= 0x11B
    return p & 0xFF


def _aes_gf_inv(a):
    if a == 0:
        return 0
    r, base, e = 1, a, 254
    while e:
        if e & 1:
            r = _aes_mul(r, base)
        base = _aes_mul(base, base)
        e >>= 1
    return r


def _aes_init():
    if _AES_READY[0]:
        return
    for x in range(256):
        inv = _aes_gf_inv(x)
        s = 0
        for i in range(8):
            b = (((inv >> i) & 1) ^ ((inv >> ((i + 4) % 8)) & 1)
                 ^ ((inv >> ((i + 5) % 8)) & 1) ^ ((inv >> ((i + 6) % 8)) & 1)
                 ^ ((inv >> ((i + 7) % 8)) & 1) ^ ((0x63 >> i) & 1))
            s |= b << i
        _AES_SBOX[x] = s
    for i, v in enumerate(_AES_SBOX):
        _AES_INV[v] = i
    _AES_READY[0] = 1


_AES_RCON = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1B, 0x36]


def _aes_expand(key16):
    w = [list(key16[i * 4:i * 4 + 4]) for i in range(4)]
    for i in range(4, 44):
        t = list(w[i - 1])
        if i % 4 == 0:
            t = t[1:] + t[:1]
            t = [_AES_SBOX[x] for x in t]
            t[0] ^= _AES_RCON[i // 4 - 1]
        w.append([w[i - 4][j] ^ t[j] for j in range(4)])
    return w


def _aes_tables():
    """逆 MixColumns T 表：TD_r[x] = 列第 r 字节为 x 时对 4 个输出行的贡献"""
    g = dict((m, [_aes_mul(x, m) for x in range(256)]) for m in (9, 11, 13, 14))

    def td(coefs):
        t = [0] * 256
        for x in range(256):
            y = _AES_INV[x]
            t[x] = ((g[coefs[0]][y] << 24) | (g[coefs[1]][y] << 16)
                    | (g[coefs[2]][y] << 8) | g[coefs[3]][y])
        return t
    # InvMixColumns 矩阵 M 的各列系数
    return (td((0x0E, 0x09, 0x0D, 0x0B)), td((0x0B, 0x0E, 0x09, 0x0D)),
            td((0x0D, 0x0B, 0x0E, 0x09)), td((0x09, 0x0D, 0x0B, 0x0E)))


_AES_T = [None]


def _aes_round_keys(key16):
    w = _aes_expand(key16)
    g = dict((m, [_aes_mul(x, m) for x in range(256)]) for m in (9, 11, 13, 14))
    rk = []
    for rd in range(11):
        cols = []
        for c in range(4):
            b = w[rd * 4 + c]
            cols.append((b[0] << 24) | (b[1] << 16) | (b[2] << 8) | b[3])
        rk.append(cols)
    dw = [rk[0]]
    for rd in range(1, 10):   # 等价逆密码：中间轮密钥要过一遍 InvMixColumns
        cols = []
        for c in range(4):
            a0, a1, a2, a3 = w[rd * 4 + c]
            cols.append(((g[14][a0] ^ g[11][a1] ^ g[13][a2] ^ g[9][a3]) << 24)
                        | ((g[9][a0] ^ g[14][a1] ^ g[11][a2] ^ g[13][a3]) << 16)
                        | ((g[13][a0] ^ g[9][a1] ^ g[14][a2] ^ g[11][a3]) << 8)
                        | (g[11][a0] ^ g[13][a1] ^ g[9][a2] ^ g[14][a3]))
        dw.append(cols)
    dw.append(rk[10])
    return w, dw


def _aes128_cbc_decrypt(data, key16, iv16):
    """AES-128-CBC NoPadding 解密，纯标准库。"""
    _aes_init()
    if _AES_T[0] is None:
        _AES_T[0] = _aes_tables()
    TD0, TD1, TD2, TD3 = _AES_T[0]
    w, dwk = _aes_round_keys(key16)
    rk0 = w[0] + w[1] + w[2] + w[3]
    out = bytearray(len(data))
    prev = [iv16[0] << 24 | iv16[1] << 16 | iv16[2] << 8 | iv16[3],
            iv16[4] << 24 | iv16[5] << 16 | iv16[6] << 8 | iv16[7],
            iv16[8] << 24 | iv16[9] << 16 | iv16[10] << 8 | iv16[11],
            iv16[12] << 24 | iv16[13] << 16 | iv16[14] << 8 | iv16[15]]
    n = len(data) // 16
    off = 0
    for _ in range(n):
        s = list(data[off:off + 16])
        st = [0, 0, 0, 0]
        for c in range(4):   # 初始 AddRoundKey（未做 InvShiftRows，取原始列）
            st[c] = ((s[4 * c] << 24) | (s[4 * c + 1] << 16)
                     | (s[4 * c + 2] << 8) | s[4 * c + 3]) ^ dwk[10][c]
        for rd in range(9, 0, -1):   # 解密自第 9 轮倒推
            rk = dwk[rd]
            ns = [0, 0, 0, 0]
            for c in range(4):
                ns[c] = (TD0[(st[c] >> 24) & 0xFF]
                         ^ TD1[(st[(c - 1) % 4] >> 16) & 0xFF]
                         ^ TD2[(st[(c - 2) % 4] >> 8) & 0xFF]
                         ^ TD3[st[(c - 3) % 4] & 0xFF] ^ rk[c])
            st = ns
        res = [0] * 16
        for c in range(4):   # 末轮：InvShiftRows + InvSubBytes + AddRoundKey(0)
            for r in range(4):
                b = (st[(c - r) % 4] >> (24 - 8 * r)) & 0xFF
                res[r + 4 * c] = _AES_INV[b] ^ rk0[r + 4 * c]
        for c in range(4):   # CBC 异或前一密文块
            x = (res[4 * c] << 24 | res[4 * c + 1] << 16
                 | res[4 * c + 2] << 8 | res[4 * c + 3]) ^ prev[c]
            out[off + 4 * c] = (x >> 24) & 0xFF
            out[off + 4 * c + 1] = (x >> 16) & 0xFF
            out[off + 4 * c + 2] = (x >> 8) & 0xFF
            out[off + 4 * c + 3] = x & 0xFF
        prev = [s[0] << 24 | s[1] << 16 | s[2] << 8 | s[3],
                s[4] << 24 | s[5] << 16 | s[6] << 8 | s[7],
                s[8] << 24 | s[9] << 16 | s[10] << 8 | s[11],
                s[12] << 24 | s[13] << 16 | s[14] << 8 | s[15]]
        off += 16
    return bytes(out)


def _aes_dec_image(raw):
    """解密封面；顺手剥掉有效的 PKCS7 填充（JS 端 NoPadding 会留着）"""
    if len(raw) < 32 or len(raw) % 16:
        return raw
    try:
        pt = _aes128_cbc_decrypt(raw, IMG_KEY.encode("utf-8"), IMG_IV.encode("utf-8"))
    except Exception:
        return raw
    if pt[:3] == b"\xff\xd8\xff" or pt[:8] == b"\x89PNG\r\n\x1a\n" \
            or (pt[:4] == b"RIFF" and pt[8:12] == b"WEBP"):
        n = pt[-1]
        if 1 <= n <= 16 and len(pt) >= n and pt[-n:] == bytes(bytearray([n] * n)):
            pt = pt[:-n]
        return pt
    return raw       # 解出来不是图，按原样返回


def _is_img_host(u):
    return ("pic.zdmhyg.cn" in u) or ("eisees.com" in u)


def _pic_proxy_url(u):
    """把密文封面地址包成本地代理地址，由 localProxy 解密后回图"""
    if not u:
        return ""
    if not IMG_PROXY or u.find("/proxy?") >= 0:
        return u
    try:
        return PROXY_BASE + "/proxy?do=py&url=" + _q(u)
    except Exception:
        return u


def _pic_cache_get(u):
    return _PIC_CACHE.get(u)


def _pic_cache_put(u, data):
    try:
        if len(_PIC_CACHE) > _PIC_CACHE_MAX:
            _PIC_CACHE.clear()
        _PIC_CACHE[u] = data
    except Exception:
        pass


# ==================== HTTP 层 ====================

def _get_opener():
    global _OPENER
    if _OPENER is None:
        try:
            handlers = []
            if _ssl is not None:
                try:
                    handlers.append(HTTPSHandler(context=_ssl._create_unverified_context()))
                except Exception:
                    pass
            _OPENER = build_opener(*handlers)
        except Exception:
            _OPENER = build_opener()
    return _OPENER


_LAST_REQ = [0.0]


def _throttle():
    """最小请求间隔。该站同 IP 高频会直接 RST 断连（WinError 10054），
    与其断连后再花 8s 超时重试，不如主动让出 0.2s。"""
    if _LOCK is None:
        return
    try:
        _LOCK.acquire()
        gap = time.time() - _LAST_REQ[0]
        if 0 < gap < MIN_GAP:
            time.sleep(MIN_GAP - gap)
        _LAST_REQ[0] = time.time()
    except Exception:
        pass
    finally:
        try:
            _LOCK.release()
        except Exception:
            pass


def _decompress(raw):
    try:
        if raw[:2] == b"\x1f\x8b" or (raw and raw[0] == 0x78):
            return zlib.decompress(raw, 47)
    except Exception:
        pass
    return raw


def _decode(raw):
    for enc in ("utf-8", "gb18030", "gbk"):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode("utf-8", "replace")


def _http_get(url, referer="", retry=RETRY, timeout=TIMEOUT):
    """带退避重试的 GET。该站会不定时 RST 断连/限流，重试比干等有用。"""
    if not url:
        return ""
    headers = {
        "User-Agent": UA,
        "Referer": referer or REFERER,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Accept-Encoding": "gzip, deflate",
    }
    for attempt in range(retry + 1):
        try:
            _throttle()
            resp = _get_opener().open(Request(url, headers=headers), timeout=timeout)
            return _decode(_decompress(resp.read()))
        except Exception:
            if attempt >= retry:
                break
            try:
                time.sleep(0.4 * (attempt + 1))
            except Exception:
                pass
    return ""


def _http_get_raw(url, referer="", retry=RETRY, timeout=TIMEOUT):
    """二进制版 GET（图片是密文，不能按文本解码）"""
    if not url:
        return b""
    headers = {"User-Agent": UA, "Referer": referer or REFERER,
               "Accept": "*/*", "Accept-Encoding": "gzip, deflate"}
    for attempt in range(retry + 1):
        try:
            _throttle()
            resp = _get_opener().open(Request(url, headers=headers), timeout=timeout)
            return _decompress(resp.read())
        except Exception:
            if attempt >= retry:
                break
            try:
                time.sleep(0.4 * (attempt + 1))
            except Exception:
                pass
    return b""


def _get_html_cached(url, ckey, ttl, referer=""):
    html = _cache_get(ckey, ttl)
    if html:
        return html
    html = _http_get(url, referer=referer)
    if html:
        _cache_set(ckey, html)
    return html or ""


# ==================== 路由构造 ====================

def _u_list(channel, pg=1):
    if pg <= 1:
        return _CUR_HOST + "/" + channel + "/"
    return _CUR_HOST + "/" + channel + "/page/" + str(int(pg)) + "/"


def _u_search(q, pg=1):
    if pg <= 1:
        return _CUR_HOST + "/search/?q=" + _q(q)
    return _CUR_HOST + "/search/?q=" + _q(q) + "&page=" + str(int(pg))


# ==================== 页面解析 ====================

def _parse_cards(html, channel_hint=""):
    """单次扫描解析 a.card 卡片（不再为每张卡切 1200 字符跑 5 个正则）。"""
    vods = []
    if not html:
        return vods
    starts = [m.start() for m in _RE_CARD.finditer(html)]
    total = len(starts)
    for i, st in enumerate(starts):
        end = starts[i + 1] if i + 1 < total else len(html)
        block = html[st:end]
        cut = block.find("</a>")
        if cut > 0:
            block = block[:cut]

        hm = _RE_HREF.search(block)
        if not hm:
            continue
        channel, path = _split_path(hm.group(1))
        if not path:
            continue
        if channel not in _VALID and channel_hint:
            channel = channel_hint

        # 片名：data-track-item-name → alt → title → span.p-title
        name = ""
        for rx in (_RE_TRACK_NAME, _RE_ALT, _RE_TITLE):
            m = rx.search(block)
            if m:
                name = _txt(m.group(1))
                if name:
                    break
        if not name:
            m = _RE_PTITLE.search(block)
            if m:
                name = _txt(m.group(1))
        if not name:
            continue

        pic = _pick_pic(block)

        remarks = ""
        m = _RE_BADGE.search(block)
        if m:
            remarks = _txt(m.group(1))
        if not remarks:
            m = _RE_EPSFLAG.search(block)
            if m:
                remarks = _txt(m.group(1))

        vid = channel + "|" + path
        _pool_put(vid, name, pic, remarks)
        vods.append({
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": _pic_proxy_url(pic),
            "vod_remarks": remarks,
        })

    # 去重（同一 id 可能重复出现）
    seen = {}
    out = []
    for v in vods:
        k = v["vod_id"]
        if k in seen:
            continue
        seen[k] = 1
        out.append(v)
    return out


def _parse_max_page(html):
    if not html:
        return 1
    mx = 1
    for m in _RE_PAGE.finditer(html):
        try:
            v = int(m.group(1))
            if v > mx:
                mx = v
        except Exception:
            pass
    for m in _RE_PAGEDATA.finditer(html):
        try:
            v = int(m.group(1))
            if v > mx:
                mx = v
        except Exception:
            pass
    return mx


def _parse_detail(html, vid, channel="", path=""):
    """详情页解析。封面优先取 img.p-img 的 data-src（真正有内容的图），
    og:image 只当兜底 —— 该站 og:image 指向的域实测返回 0 字节。"""
    result = {"vid": vid, "name": "", "pic": "", "channel": channel,
              "path": path, "episodes": [], "content": "", "year": "",
              "type_name": _TYPE_NAME.get(channel, channel)}
    if not html:
        return result

    m = _RE_H1.search(html)
    if m:
        result["name"] = _txt(m.group(1))

    # 封面：详情页主海报
    m = _RE_PIMG.search(html)
    if m:
        result["pic"] = _pick_pic(m.group(0))
    if not result["pic"]:
        head = html[:6000]
        idx = head.find("detail-poster")
        seg = head[idx:idx + 1200] if idx > 0 else head
        result["pic"] = _pick_pic(seg)
    if not result["pic"]:
        m = _RE_OGIMG.search(html)
        if m:
            result["pic"] = _clean_pic(m.group(1))

    # 选集
    m = _RE_EPGRID.search(html)
    if m:
        for em in _RE_EP_A.finditer(m.group(1)):
            result["episodes"].append({
                "ep": int(em.group(2)),
                "url": _abs_url(em.group(1)),
            })
    if not result["episodes"] and path:
        result["episodes"] = [{"ep": 1, "url": _abs_url(path + "1/")}]

    m = _RE_OGDESC.search(html) or _RE_METADESC.search(html)
    if m:
        result["content"] = _txt(m.group(1))
    m = _RE_TIME.search(html)
    if m:
        result["year"] = m.group(1)
    return result


def _parse_play(html):
    """播放页：从 script JSON 提取 m3u8 直链（签名参数必须保留）。"""
    if not html:
        return ""
    m = _RE_CURRENT.search(html)
    if not m:
        m = _RE_ANYM3U8.search(html)
    if not m:
        return ""
    return m.group(1).replace("\\/", "/").replace("\\u0026", "&")


# ==================== Spider 主类 ====================

class Spider(BaseSpider):

    name = NAME
    site_url = BASE
    base_url = BASE
    searchable = 1
    quickSearch = 1
    filterable = 0
    changeable = 1

    def __init__(self):
        self._host = _CUR_HOST

    def init(self, extend=""):
        """init 内绝不联网：壳子加载期任何挂起都会让整份爬虫进不去。"""
        global _CUR_HOST, PROXY_BASE, IMG_PROXY
        ext = (extend or "").strip().strip("/")
        if ext and ext.find(".") > 0 and ext != "py" and ext.find("=") < 0:
            if ext.find("://") < 0:
                ext = "https://" + ext
            _CUR_HOST = ext
            self._host = ext
            _CACHE.clear()
        # extend 支持 proxy=http://host:port / imgproxy=0
        for kv in (extend or "").split(","):
            if "=" not in kv:
                continue
            k, v = kv.split("=", 1)
            k = k.strip().lower()
            v = v.strip()
            if k == "proxy" and v:
                PROXY_BASE = v.rstrip("/")
            elif k == "imgproxy":
                IMG_PROXY = 1 if v.strip().lower() in ("1", "true", "on", "yes") else 0
            elif k == "host" and v:
                if v.find("://") < 0:
                    v = "https://" + v
                _CUR_HOST = v
                self._host = v
                _CACHE.clear()
        return "OK"

    # ---------- home ----------
    def homeContent(self, filter=False):
        html = _get_html_cached(_u_list("duanju", 1), "home", _TTL_LIST)
        return {"class": list(DEFAULT_CLASSES), "filters": {},
                "list": _parse_cards(html, "duanju")}

    def homeVideoContent(self):
        html = _get_html_cached(_u_list("duanju", 1), "home", _TTL_LIST)
        return {"list": _parse_cards(html, "duanju")}

    # ---------- category ----------
    def categoryContent(self, tid, pg, filter=False, extend=None):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        if pg < 1:
            pg = 1
        tid = str(tid or "duanju")
        if tid not in _VALID:
            tid = "duanju"
        html = _get_html_cached(_u_list(tid, pg), "cat:%s:%d" % (tid, pg),
                                _TTL_LIST, referer=_CUR_HOST + "/" + tid + "/")
        vods = _parse_cards(html, tid)
        max_page = _parse_max_page(html)
        if pg > 1 and pg > max_page:
            vods = []
        return {
            "list": vods, "page": pg, "pagecount": max_page,
            "limit": len(vods) or 24, "total": max_page * 24,
            "parse": 0, "jx": 0,
        }

    # ---------- detail ----------
    def detailContent(self, ids):
        try:
            did = ids[0] if isinstance(ids, list) else ids
        except Exception:
            did = None
        did = str(did or "").strip()
        if not did:
            return {"list": [], "parse": 0, "jx": 0}

        channel, path = "", ""
        if "|" in did:                       # v2 格式：channel|/channel/id-slug/
            channel, path = did.split("|", 1)
        elif "_" in did:                     # v1 旧格式：channel_vid
            channel, vid = did.split("_", 1)
            path = "/" + channel + "/" + vid + "-"

        pool = _ITEM_POOL.get(did) or {}
        pick = _TYPE_NAME.get(channel, channel)

        d = _cache_get("detail:" + did, _TTL_DETAIL)
        if d is None:
            url = _abs_url(path)
            html = _http_get(url, referer=_CUR_HOST + "/" + (channel or "") + "/")
            if html and path.endswith("-"):   # 旧格式：跟 canonical 纠正一次
                m = _RE_CANON.search(html)
                if m:
                    real = m.group(1).rstrip("/") + "/"
                    if real != url:
                        html = _http_get(real)
            d = _parse_detail(html, did, channel, path)
            if d and (d.get("name") or d.get("pic")):
                _cache_set("detail:" + did, d)

        # 详情抓空时用列表缓存兜底，保证仍有封面与播放地址
        if (not d) or (not d.get("name") and not d.get("pic")):
            if not pool:
                return {"list": [], "parse": 0, "jx": 0}
            d = {"vid": did, "name": pool.get("name") or "", "pic": pool.get("pic") or "",
                 "channel": channel, "path": path, "content": "", "year": "",
                 "type_name": pick,
                 "episodes": ([{"ep": 1, "url": _abs_url(path + "1/")}]
                              if path else [])}

        if not d.get("pic"):
            d["pic"] = pool.get("pic") or ""
        if not d.get("name"):
            d["name"] = pool.get("name") or did
        if not d.get("episodes") and path:
            d["episodes"] = [{"ep": 1, "url": _abs_url(path + "1/")}]
        if not d.get("episodes"):
            return {"list": [], "parse": 0, "jx": 0}

        multi = len(d["episodes"]) > 1
        ep_strs = []
        for ep in d["episodes"]:
            nm = ("第%d集" % ep["ep"]) if multi else "立即播放"
            ep_strs.append("%s$%s" % (nm, ep["url"]))

        vod = {
            "vod_id": did,
            "vod_name": d.get("name") or did,
            "vod_pic": _pic_proxy_url(d.get("pic") or ""),
            "type_name": d.get("type_name") or pick,
            "vod_year": d.get("year") or "",
            "vod_area": "",
            "vod_remarks": pool.get("remarks") or "",
            "vod_actor": "",
            "vod_director": "",
            "vod_content": d.get("content") or "",
            "vod_play_from": NAME,
            "vod_play_url": "#".join(ep_strs),
        }
        return {"list": [vod], "parse": 0, "jx": 0}

    # ---------- search ----------
    def searchContent(self, key, quick=False, pg="1"):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        if pg < 1:
            pg = 1
        empty = {"list": [], "page": pg, "pagecount": 0,
                 "limit": 0, "total": 0, "parse": 0, "jx": 0}
        key = str(key or "").strip()
        if not key:
            return empty
        html = _get_html_cached(_u_search(key, pg), "search:%s:%d" % (key, pg),
                                _TTL_LIST)
        vods = _parse_cards(html)
        if not vods:
            return empty
        max_page = _parse_max_page(html)
        if pg > 1 and pg > max_page:
            vods = []
        return {
            "list": vods, "page": pg, "pagecount": max_page,
            "limit": len(vods), "total": max_page * len(vods),
            "parse": 0, "jx": 0,
        }

    # ---------- player ----------
    def playerContent(self, flag="", id="", vipFlags=None):
        try:
            if not id and isinstance(flag, str) and flag.find("$") >= 0:
                id = flag
        except Exception:
            pass
        url = str(id or "")
        if url.find("$") >= 0:
            url = url.split("$")[-1]
        if not url:
            return {"parse": 0, "url": "", "header": "", "jx": 0}
        header_str = json.dumps({"User-Agent": UA, "Referer": _CUR_HOST + "/"})

        if url.find(".m3u8") >= 0 or url.find(".mp4") >= 0:
            return {"parse": 0, "url": url, "jx": 0, "header": header_str}
        if url.startswith("http"):
            m3u8 = _cache_get("play:" + url, _TTL_PLAY)
            if not m3u8:
                # 播放是最终环节，多试一次；站点限流时第一次常被 RST
                m3u8 = _parse_play(_http_get(url, retry=2))
                if m3u8:
                    _cache_set("play:" + url, m3u8)
            if m3u8:
                return {"parse": 0, "url": m3u8, "jx": 0, "header": header_str}
        return {"parse": 1, "url": url, "jx": 0}

    # ---------- localProxy ----------
    def localProxy(self, param):
        try:
            if isinstance(param, dict):
                d = param
            else:
                s = str(param or "").strip()
                while s[:1] == "/":
                    s = s[1:]
                i = s.find("://")
                if i >= 0:
                    s = s[i + 3:]
                d = dict(parse_qsl(s))
            url = d.get("url") or ""
            try:
                url = unquote(url.strip())
            except Exception:
                pass
            if not url:
                return [500, "text/plain", b"localProxy: empty url"]
            referer = str(d.get("referer") or (_CUR_HOST + "/"))

            # ---- 封面：密文图片，取回后本地解密再回给壳子 ----
            typ = str(d.get("type") or "").lower()
            if typ in ("img", "image", "pic") or _is_img_host(url):
                cached = _pic_cache_get(url)
                if cached is None:
                    try:
                        req = Request(url, headers={
                            "User-Agent": UA, "Referer": referer, "Accept": "*/*"})
                        raw = _decompress(_get_opener().open(
                            req, timeout=TIMEOUT).read())
                    except Exception as e:
                        return [502, "text/plain",
                                ("pic fetch error: %s" % e).encode("utf-8")]
                    cached = _aes_dec_image(raw)
                    _pic_cache_put(url, cached)
                ctype = "image/jpeg"
                low = url.split("?")[0].lower()
                if low.endswith(".png"):
                    ctype = "image/png"
                elif low.endswith(".webp"):
                    ctype = "image/webp"
                elif low.endswith(".gif"):
                    ctype = "image/gif"
                return [200, ctype, cached]

            req = Request(url, headers={
                "User-Agent": UA, "Referer": referer, "Accept": "*/*"})
            raw = _decompress(_get_opener().open(req, timeout=TIMEOUT).read())
            ctype = "application/octet-stream"
            if url.find(".m3u8") >= 0:
                ctype = "application/vnd.apple.mpegurl"
                out = []
                for line in _decode(raw).splitlines():
                    t = line.strip()
                    if t and not t.startswith("#"):
                        try:
                            t = urljoin(url, t)
                        except Exception:
                            pass
                    out.append(t)
                raw = "\n".join(out).encode("utf-8")
            return [200, ctype, raw]
        except Exception as e:
            return [502, "text/plain", ("Proxy Error: %s" % e).encode("utf-8")]

    # ---------- 短名别名 ----------
    def home(self, filter=False):
        return self.homeContent(filter)

    def homeVideo(self):
        return self.homeVideoContent()

    def category(self, tid, pg, filter=False, extend=None):
        return self.categoryContent(tid, pg, filter, extend)

    def detail(self, ids):
        return self.detailContent(ids)

    def search(self, key, quick=False, pg="1"):
        return self.searchContent(key, quick, pg)

    def player(self, flag="", id="", vipFlags=None):
        return self.playerContent(flag, id, vipFlags)

    def isVideoFormat(self, url):
        try:
            url = str(url or "").split("?")[0].lower()
            for ext in (".m3u8", ".mp4", ".flv", ".avi", ".mkv", ".ts", ".mov"):
                if url.endswith(ext):
                    return 1
        except Exception:
            pass
        return 0

    def manualVideoCheck(self):
        return 0

    def getDependence(self):
        return []

    def action(self, action):
        return ""

    def destroy(self):
        try:
            _CACHE.clear()
        except Exception:
            pass


# ==================== 模块级双入口 ====================

_sp = None


def _get():
    global _sp
    if _sp is None:
        _sp = Spider()
    return _sp


def init(extend=""):
    return _get().init(extend)


def homeContent(filter=False):
    return _get().homeContent(filter)


def homeVideoContent():
    return _get().homeVideoContent()


def categoryContent(tid, pg, filter=False, extend=None):
    return _get().categoryContent(tid, pg, filter, extend)


def detailContent(ids):
    return _get().detailContent(ids)


def searchContent(key, quick=False, pg="1"):
    return _get().searchContent(key, quick, pg)


def playerContent(flag="", id="", vipFlags=None):
    return _get().playerContent(flag, id, vipFlags)


def localProxy(param):
    return _get().localProxy(param)


def getName():
    return NAME


def isVideoFormat(url):
    return _get().isVideoFormat(url)


def manualVideoCheck():
    return _get().manualVideoCheck()


def destroy():
    return _get().destroy()


# ==================== 自检测试块 ====================

if __name__ == "__main__":
    import sys

    stat = {"ok": 0, "fail": 0}

    def chk(label, cond, extra=""):
        if cond:
            stat["ok"] += 1
            print("  [OK]   %-30s %s" % (label, extra))
        else:
            stat["fail"] += 1
            print("  [FAIL] %-30s %s" % (label, extra))
        return cond

    # ---------- 离线夹具：不联网也能验证核心修复 ----------
    print("[离线] 封面与路径解析夹具")
    fixture_card = ('<a class="card" href="https://91crdj.com/duanju/1337-bababuzaijia/" '
                    'data-track-item-name="爸爸不在家">'
                    '<div class="poster">'
                    '<img class="p-img" alt="爸爸不在家" '
                    'src="data:image/gif;base64,R0lGODlhAQABAAAAAC" '
                    'data-src="https://pic.zdmhyg.cn/x/1.jpeg?auth_key=1789286668-0-0-abc">'
                    '<span class="badge new">新剧</span></div></a>')
    fx = _parse_cards(fixture_card, "duanju")
    chk("卡片解析出 1 条", len(fx) == 1, str(len(fx)))
    chk("封面剥掉 auth_key",
        _clean_pic("https://pic.zdmhyg.cn/x/1.jpeg?auth_key=1789286668-0-0-abc")
        == "https://pic.zdmhyg.cn/x/1.jpeg",
        _clean_pic("https://pic.zdmhyg.cn/x/1.jpeg?auth_key=1789286668-0-0-abc"))
    chk("卡片 vod_pic 指向本地代理",
        fx and fx[0]["vod_pic"].find("/proxy?do=py&url=") > 0
        and _q("https://pic.zdmhyg.cn/x/1.jpeg") in fx[0]["vod_pic"],
        fx[0]["vod_pic"][:70] if fx else "")
    chk("封面不含 0 字节空图域",
        fx and "eisees" not in fx[0]["vod_pic"])
    chk("vod_id 带完整路径",
        fx and fx[0]["vod_id"] == "duanju|/duanju/1337-bababuzaijia/",
        fx[0]["vod_id"] if fx else "")

    # 无 slug 链接（漫画/小说）——旧版会整条丢弃
    chk("无 slug 路径解析",
        _split_path("https://91crdj.com/manhua/96/") == ("manhua", "/manhua/96/"),
        str(_split_path("https://91crdj.com/manhua/96/")))
    chk("base64 占位图被丢弃",
        _clean_pic("data:image/gif;base64,R0lGODlhAQABAAAAAC") == "")
    chk("空图域 eisees 被拉黑",
        _clean_pic("https://expose.eisees.com/a.jpeg?auth=1") == "")

    # ---------- 离线夹具：封面 AES 解密 ----------
    print("[离线] 封面 AES 解密")
    def binascii_hex(bs):
        try:
            import binascii as _ba
            return _ba.hexlify(bs).decode()
        except Exception:
            return repr(bs)
    chk("IMG_KEY 推导", IMG_KEY == "f5d965df75336270", IMG_KEY)
    chk("IMG_IV 推导", IMG_IV == "97b60394abc2fbe1", IMG_IV)
    # FIPS-197 官方 AES-128 向量
    _k = bytes(bytearray.fromhex("2b7e151628aed2a6abf7158809cf4f3c"))
    _pt = bytes(bytearray.fromhex("3243f6a8885a308d313198a2e0370734"))
    _ct = bytes(bytearray.fromhex("3925841d02dc09fbdc118597196a0b32"))
    chk("AES-128 FIPS-197 解密",
        _aes128_cbc_decrypt(_ct, _k, bytes(16)) == _pt)
    chk("AES 输出长度守恒",
        len(_aes128_cbc_decrypt(_ct * 2, _k, bytes(16))) == 32)
    # 真实封面首两块密文（实测抓自 pic.zdmhyg.cn），必须解出 JPEG 魔数
    _rc = bytes(bytearray.fromhex(
        "093de3b1fc4af46ff223ac4c8bdb076a"
        "d026ab04341678e3bfe1859e5795472c"))
    chk("站内封面首块解出 JFIF",
        _aes128_cbc_decrypt(_rc, IMG_KEY.encode("utf-8"),
                            IMG_IV.encode("utf-8"))[:12]
        == bytes(bytearray.fromhex("ffd8ffe000104a4649460001")))
    chk("_aes_dec_image 走通并出 JPEG",
        _aes_dec_image(_rc)[:3] == b"\xff\xd8\xff",
        binascii_hex(_aes_dec_image(_rc)[:3]))
    chk("封面代理 URL 生成",
        _pic_proxy_url("https://pic.zdmhyg.cn/a.jpeg").find("/proxy?do=py&url=") > 0,
        _pic_proxy_url("https://pic.zdmhyg.cn/a.jpeg"))
    chk("_is_img_host 识别",
        _is_img_host("https://pic.zdmhyg.cn/a.jpeg") is True
        and _is_img_host("https://91crdj.com/x/") is False)


    # 详情页封面优先级：p-img 优先于 og:image
    fx_detail = ('<meta property="og:image" content="https://expose.eisees.com/a.jpeg?auth=1" />'
                 '<h1 class="detail-title">爸爸不在家</h1>'
                 '<img class="p-img" src="data:image/gif;base64,xx" '
                 'data-src="https://pic.zdmhyg.cn/x/1.jpeg?auth_key=1-0-0-a">'
                 '<div class="ep-grid">'
                 '<a href="https://91crdj.com/duanju/1337-bababuzaijia/1/">1</a>'
                 '<a href="https://91crdj.com/duanju/1337-bababuzaijia/2/">2</a></div>')
    fd = _parse_detail(fx_detail, "duanju|/duanju/1337-bababuzaijia/",
                       "duanju", "/duanju/1337-bababuzaijia/")
    chk("详情封面取 p-img 而非 og:image",
        fd["pic"] == "https://pic.zdmhyg.cn/x/1.jpeg", fd["pic"])
    chk("详情片名", fd["name"] == "爸爸不在家", fd["name"])
    chk("详情选集 2 集", len(fd["episodes"]) == 2, str(len(fd["episodes"])))

    # ---------- 在线冒烟 ----------
    print("[在线] 冒烟测试")
    sp = Spider()
    chk("init", sp.init("") == "OK")

    # 首页：站点限流时最多重试 3 轮（每轮退避）
    hc, lst = {}, []
    for i in range(3):
        hc = sp.homeContent()
        lst = hc.get("list") or []
        if lst:
            break
        try:
            time.sleep(4 * (i + 1))
        except Exception:
            pass
    t_home = 0.0

    chk("homeContent 分类", len(hc.get("class") or []) > 1)
    chk("homeContent 列表", len(lst) > 0, "推荐=%d" % len(lst))
    chk("首页封面全有", len(lst) > 0 and all(v.get("vod_pic") for v in lst),
        "%d/%d" % (sum(1 for v in lst if v.get("vod_pic")), len(lst)))

    # 真实封面：抓密文 -> 本地解密 -> 必须是合法 JPEG
    if lst and lst[0].get("vod_pic"):
        _p = lst[0]["vod_pic"]
        _ru = _p.split("url=")[-1]
        try:
            _ru = unquote(_ru)
        except Exception:
            pass
        _b = _http_get_raw(_ru)
        _d = _aes_dec_image(_b)
        chk("封面密文可解密",
            len(_b) > 1000 and _d[:3] == b"\xff\xd8\xff",
            "密文%d -> 明文%d 字节" % (len(_b), len(_d)))
        chk("vop_pic 已指向本地代理", _p.find("/proxy?do=py&url=") > 0,
            _p[:60])

    if lst:
        time.sleep(1.5)
        t0 = time.time()
        dc = sp.detailContent([lst[0]["vod_id"]])
        t_detail = time.time() - t0
        vod = (dc.get("list") or [{}])[0]
        chk("detail 片名", bool(vod.get("vod_name")), vod.get("vod_name"))
        chk("detail 封面非空", str(vod.get("vod_pic", "")).startswith("http"),
            str(vod.get("vod_pic"))[:60])
        chk("detail 封面非 eisees", "eisees" not in str(vod.get("vod_pic", "")))
        chk("detail 播放地址", "$" in str(vod.get("vod_play_url", "")),
            "%.2fs" % t_detail)
        chk("详情单次请求 < 6s", t_detail < 6.0, "%.2fs" % t_detail)

        # 逐集验证播放直链（真实用户点击节奏）
        for e in str(vod.get("vod_play_url", "")).split("#"):
            if "$" not in e:
                continue
            nm, pid = e.split("$", 1)
            time.sleep(1.2)
            pc = sp.playerContent(NAME, pid)
            chk("player %s 直链" % nm,
                pc.get("parse") == 0 and str(pc.get("url", "")).find(".m3u8") > 0,
                str(pc.get("url"))[:55])

    chk("category 越界页截断", sp.categoryContent("duanju", 99999)["list"] == [])
    chk("searchContent 空词", sp.searchContent("")["list"] == [])
    chk("detailContent([])", sp.detailContent([]) == {"list": [], "parse": 0, "jx": 0})
    chk("playerContent 空参", sp.playerContent("", "")["url"] == "")
    chk("localProxy 空参 500", sp.localProxy({"url": ""})[0] == 500)

    print("-" * 62)
    print("结果: %d 通过 / %d 失败" % (stat["ok"], stat["fail"]))
    sys.exit(0 if stat["fail"] == 0 else 1)
