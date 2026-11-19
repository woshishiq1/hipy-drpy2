#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import json
import base64
import gzip
import zlib
import ssl
import uuid
import hashlib
import urllib.request
import urllib.parse
import urllib.error
import http.cookiejar
from urllib.parse import quote, unquote, urlparse

try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider(object):
        def getCache(self, key):
            return None

        def setCache(self, key, value):
            return "fail"

        def delCache(self, key):
            return "fail"

        def getProxyUrl(self):
            return "http://127.0.0.1:9978/proxy?do=py"


def format_remarks(brand, meta):
    clean_meta = str(meta or "").strip()
    clean_meta = re.sub(r"[\r\n\t]+", " ", clean_meta).strip()
    if clean_meta:
        return "%s | %s" % (brand, clean_meta)
    return brand


_SBOX = []
_INV_SBOX = [0] * 256


def _build_sbox():
    global _SBOX, _INV_SBOX
    if _SBOX:
        return
    sbox = [0] * 256

    def rotl(x, n):
        return ((x << n) | (x >> (8 - n))) & 0xff

    p = 1
    q = 1
    while True:
        p = (p ^ ((p << 1) & 0xff) ^ (0x1b if (p & 0x80) else 0)) & 0xff
        q ^= (q << 1) & 0xff
        q ^= (q << 2) & 0xff
        q ^= (q << 4) & 0xff
        q ^= (0x09 if (q & 0x80) else 0) & 0xff
        sbox[p] = (q ^ rotl(q, 1) ^ rotl(q, 2) ^ rotl(q, 3) ^ rotl(q, 4) ^ 0x63) & 0xff
        if p == 1:
            break
    sbox[0] = 0x63
    inv = [0] * 256
    for i, v in enumerate(sbox):
        inv[v] = i
    _SBOX = sbox
    _INV_SBOX = inv


_build_sbox()
_RCON = (0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1b, 0x36)


def _aes_expand_key(key):
    w = list(key)
    i = 16
    while i < 176:
        t = w[i - 4:i]
        if i % 16 == 0:
            t = [_SBOX[t[1]] ^ _RCON[i // 16 - 1], _SBOX[t[2]], _SBOX[t[3]], _SBOX[t[0]]]
        for j in range(4):
            w.append(w[i - 16 + j] ^ t[j])
        i += 4
    return w


def _aes_gmul(a, b):
    r = 0
    while b > 0:
        if b & 1:
            r ^= a
        a = ((a << 1) & 0xff) ^ (0x1b if (a & 0x80) else 0)
        b >>= 1
    return r


# 预计算 GF(2^8) 乘法表，纯 Python 回退路径提速 5~8 倍
def _build_mul_tables():
    def gmul(a, b):
        r = 0
        while b > 0:
            if b & 1:
                r ^= a
            a = ((a << 1) & 0xff) ^ (0x1b if (a & 0x80) else 0)
            b >>= 1
        return r
    return ([gmul(i, 9) for i in range(256)],
            [gmul(i, 11) for i in range(256)],
            [gmul(i, 13) for i in range(256)],
            [gmul(i, 14) for i in range(256)])

_MUL9, _MUL11, _MUL13, _MUL14 = _build_mul_tables()

# 优先使用 C 实现的 AES，没有则回退纯 Python
try:
    from Crypto.Cipher import AES as _PyCryptoAES
    _HAS_PYCRYPTO = True
except Exception:
    _PyCryptoAES = None
    _HAS_PYCRYPTO = False

try:
    from cryptography.hazmat.primitives.ciphers import (
        Cipher as _CryCipher, algorithms as _CryAlg, modes as _CryModes
    )
    _HAS_CRYPTOGRAPHY = True
except Exception:
    _CryCipher = _CryAlg = _CryModes = None
    _HAS_CRYPTOGRAPHY = False


def _aes_decrypt_block(block, w):
    s = list(block)

    def add_rk(rnd):
        off = rnd * 16
        for k in range(16):
            s[k] ^= w[off + k]

    def inv_shift():
        t = list(s)
        for row in range(4):
            for col in range(4):
                s[row + 4 * col] = t[row + 4 * ((col - row) % 4)]

    def inv_sub():
        inv = _INV_SBOX
        for k in range(16):
            s[k] = inv[s[k]]

    def inv_mix():
        # 用预计算乘法表替代逐位 gmul
        for col in range(4):
            i = 4 * col
            a0, a1, a2, a3 = s[i], s[i + 1], s[i + 2], s[i + 3]
            s[i]     = _MUL14[a0] ^ _MUL11[a1] ^ _MUL13[a2] ^ _MUL9[a3]
            s[i + 1] = _MUL9[a0]  ^ _MUL14[a1] ^ _MUL11[a2] ^ _MUL13[a3]
            s[i + 2] = _MUL13[a0] ^ _MUL9[a1]  ^ _MUL14[a2] ^ _MUL11[a3]
            s[i + 3] = _MUL11[a0] ^ _MUL13[a1] ^ _MUL9[a2]  ^ _MUL14[a3]

    add_rk(10)
    for rnd in range(9, 0, -1):
        inv_shift()
        inv_sub()
        add_rk(rnd)
        inv_mix()
    inv_shift()
    inv_sub()
    add_rk(0)
    return s


class FastAesCbc(object):
    def __init__(self, key, iv):
        self.key = bytes(key)
        self.iv_bytes = bytes(iv)
        self.rk = _aes_expand_key(list(key))
        self.iv = list(iv)

    @staticmethod
    def _unpad(out):
        if out:
            pad = out[-1]
            if 1 <= pad <= 16 and pad <= len(out) and bytes(out[-pad:]) == bytes([pad]) * pad:
                return bytes(out[:-pad])
        return bytes(out)

    def decrypt(self, data):
        if not data or len(data) % 16 != 0:
            return b""
        # 1) pycryptodome（C 实现，最快）
        if _HAS_PYCRYPTO:
            try:
                c = _PyCryptoAES.new(self.key, _PyCryptoAES.MODE_CBC, self.iv_bytes)
                return self._unpad(c.decrypt(bytes(data)))
            except Exception:
                pass
        # 2) cryptography（C 实现）
        if _HAS_CRYPTOGRAPHY:
            try:
                dec = _CryCipher(
                    _CryAlg.AES(self.key),
                    _CryModes.CBC(self.iv_bytes)
                ).decryptor()
                return self._unpad(dec.update(bytes(data)) + dec.finalize())
            except Exception:
                pass
        # 3) 纯 Python 查表回退
        out = bytearray()
        prev = self.iv
        for off in range(0, len(data), 16):
            blk = list(data[off:off + 16])
            dec = _aes_decrypt_block(blk, self.rk)
            for i in range(16):
                out.append(dec[i] ^ prev[i])
            prev = blk
        return self._unpad(out)


class Spider(BaseSpider):
    def __init__(self):
        super(Spider, self).__init__()
        self.siteName = "草莓视频"
        self.host = "https://scor.t2j8l5ixcm.cc"
        self.staticBase = "https://cmsta.uitxn.cn"
        self.imgFallback = "https://cmvpic.uitxn.cn"
        self.proxyBase = "http://127.0.0.1:9978/proxy?do=py"
        self.platform = "9"
        self._ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
        self.brandActor = "🦋 TG群: @tvshare23"
        self.brandDirector = "🦋 蝴蝶影视"
        self.tgGroup = "https://t.me/tvshare23"
        self.options = {}
        self._uuid = str(uuid.uuid4())
        self._aes = FastAesCbc(b"NHboMHZerxFQ401E", b"i7JeCEIMVrj2W9xN")
        self.ctx = ssl.create_default_context()
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE
        self.cj = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cj),
            urllib.request.HTTPSHandler(context=self.ctx)
        )
        self.sortOpts = [
            {"n": "今日更新", "v": "1"},
            {"n": "推荐", "v": "2"},
            {"n": "日榜", "v": "3"},
            {"n": "周榜", "v": "4"},
            {"n": "月榜", "v": "5"}
        ]
        self.tree = [
            (51, "国产", [(156, "乱伦"), (152, "偷情"), (191, "剧情"), (144, "偷拍"), (145, "自拍"), (151, "直播"), (153, "探花"), (154, "强奸"), (155, "迷奸")]),
            (76, "日韩", [(169, "中字"), (171, "无码"), (194, "乱伦"), (193, "人妻"), (183, "群交"), (170, "OL"), (196, "偷情")]),
            (127, "欧美", [(176, "黑白配"), (185, "剧情"), (178, "中字"), (182, "SM"), (186, "自拍"), (177, "男同"), (181, "女同")]),
            (93, "吃瓜", []),
            (60, "传媒", [(146, "麻豆"), (147, "天美"), (148, "91"), (157, "星空"), (158, "精东"), (159, "蜜桃"), (160, "SWAG"), (187, "果冻"), (188, "糖心"), (190, "萝莉社"), (192, "扣扣"), (195, "皇家")]),
            (137, "AI视频", []),
            (83, "动漫", [(172, "中字"), (173, "有码"), (174, "无码"), (189, "3D")]),
            (71, "综艺", []),
            (198, "解说", []),
            (197, "VR", []),
            (199, "伦理", []),
            (200, "猎奇", []),
            (201, "福利姬", [])
        ]

    def init(self, extend=""):
        if isinstance(extend, dict):
            self.options = extend
        elif extend:
            try:
                self.options = json.loads(extend)
            except Exception:
                self.options = {}
        custom = str(self.options.get("host") or "").strip()
        if custom.startswith("http"):
            self.host = custom.rstrip("/")
        return True

    def getName(self):
        return self.siteName

    def _proxy_prefix(self):
        try:
            u = self.getProxyUrl()
            if u and str(u).startswith("http"):
                return str(u)
        except Exception:
            pass
        return self.proxyBase

    def _channel_code(self):
        h = re.sub(r"^https?://", "", self.host)
        first = h.split("/")[0].split(".")[0] or ""
        if first == "www":
            return ""
        return first[:4]

    def _fetch(self, url, headers, timeout=5, retry=2):
        for attempt in range(retry):
            try:
                req = urllib.request.Request(url, headers=headers)
                with self.opener.open(req, timeout=timeout) as resp:
                    raw = resp.read()
                    enc = ""
                    try:
                        enc = resp.headers.get("Content-Encoding", "") or ""
                    except Exception:
                        enc = ""
                    if raw.startswith(b"\x1f\x8b") or enc == "gzip":
                        raw = gzip.decompress(raw)
                    elif enc == "deflate":
                        try:
                            raw = zlib.decompress(raw)
                        except Exception:
                            raw = zlib.decompress(raw, -zlib.MAX_WBITS)
                    return resp.getcode(), raw
            except urllib.error.HTTPError as e:
                try:
                    return e.code, e.read() if e.fp else b""
                except Exception:
                    return e.code, b""
            except Exception:
                if attempt < retry - 1:
                    continue
                return 0, b""
        return 0, b""

    def _api_headers(self):
        return {
            "User-Agent": self._ua,
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/x-www-form-urlencoded",
            "platform": self.platform,
            "Channel-Code": self._channel_code(),
            "uuid": self._uuid,
            "Referer": self.host + "/",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive"
        }

    def _decrypt_json(self, raw):
        try:
            text = raw.decode("utf-8", "replace").strip()
            if not text:
                return None
            # 已经是明文 JSON 就直接解析，省一次 AES
            if text[0] in "{[":
                try:
                    return json.loads(text)
                except Exception:
                    pass
            plain = self._aes.decrypt(base64.b64decode(text))
            if not plain:
                return None
            return json.loads(plain.decode("utf-8", "replace"))
        except Exception:
            return None

    def _api(self, path):
        code, raw = self._fetch(self.host + path, self._api_headers())
        if code != 200:
            return None
        return self._decrypt_json(raw)

    def _static(self, path):
        code, raw = self._fetch(self.staticBase + path, {
            "User-Agent": self._ua,
            "Referer": self.host + "/",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive"
        })
        if code != 200:
            return None
        return self._decrypt_json(raw)

    def _clean_title(self, t):
        s = str(t or "").replace("\ufeff", "")
        return s.strip()

    def _fmt_dur(self, sec):
        try:
            n = int(sec)
        except Exception:
            return ""
        if n <= 0:
            return ""
        h = n // 3600
        m = (n % 3600) // 60
        s = n % 60
        if h > 0:
            return "%d:%02d:%02d" % (h, m, s)
        return "%02d:%02d" % (m, s)

    def _pic(self, domain, rel_path):
        if not rel_path:
            return ""
        rel = str(rel_path).strip()
        if rel.startswith("http"):
            full = rel
        else:
            base = (domain or self.imgFallback).rstrip("/")
            if not rel.startswith("/"):
                rel = "/" + rel
            full = base + rel
        prefix = self._proxy_prefix()
        sep = "&" if "?" in prefix else "?"
        return "%s%stype=img&url=%s" % (prefix, sep, quote(full, safe=""))

    def _sync_img_domain(self, obj):
        if not isinstance(obj, dict):
            return self.imgFallback
        dom = obj.get("imgDomain")
        if not dom and isinstance(obj.get("sourceInfoVO"), dict):
            dom = obj["sourceInfoVO"].get("imgDomain")
        if dom and str(dom).startswith("http"):
            self.imgFallback = str(dom).rstrip("/")
        return self.imgFallback

    def _cards(self, records, img_domain=None):
        cards = []
        if not isinstance(records, list):
            return cards
        dom = img_domain or self.imgFallback
        for r in records:
            if not isinstance(r, dict) or not r.get("viewKey"):
                continue
            item_dom = r.get("imgDomain") or dom
            cards.append({
                "vod_id": str(r["viewKey"]),
                "vod_name": self._clean_title(r.get("title")),
                "vod_pic": self._pic(item_dom, r.get("poster")),
                "vod_remarks": format_remarks("蝴蝶影视", self._fmt_dur(r.get("duration"))),
                "style": {"type": "rect", "ratio": 1.78}
            })
        return cards

    def _list_result(self, data, page):
        if not isinstance(data, dict):
            return {"list": [], "page": page, "pagecount": page, "limit": 18, "total": 0}
        dom = self._sync_img_domain(data)
        cards = self._cards(data.get("records"), dom)
        try:
            pc = int(data.get("pageCount") or page)
        except Exception:
            pc = page
        try:
            total = int(data.get("total") or 0)
        except Exception:
            total = 0
        return {"list": cards, "page": page, "pagecount": pc, "limit": 18, "total": total}

    def homeContent(self, filter):
        classes = [{"type_id": "featured", "type_name": "精选"}]
        for cid, name, kids in self.tree:
            classes.append({"type_id": str(cid), "type_name": name})
        classes.append({"type_id": "short", "type_name": "短视频"})
        result = {"class": classes}
        if filter:
            filters = {}
            filters["featured"] = [
                {"key": "sort", "name": "排序", "init": "2", "value": self.sortOpts}
            ]
            for cid, name, kids in self.tree:
                groups = []
                if kids:
                    opts = [{"n": "全部", "v": ""}]
                    for kid, kname in kids:
                        opts.append({"n": kname, "v": str(kid)})
                    groups.append({"key": "sub", "name": "子分类", "init": "", "value": opts})
                groups.append({"key": "sort", "name": "排序", "init": "1", "value": self.sortOpts})
                filters[str(cid)] = groups
            result["filters"] = filters
        return result

    def homeVideoContent(self):
        data = self._static("/static/common/home_data_9.js")
        if isinstance(data, dict) and isinstance(data.get("recommendList"), list):
            dom = self._sync_img_domain(data)
            return {"list": self._cards(data.get("recommendList"), dom)}
        data = self._api("/app/movie/getList?page=1&pageSize=18&sort=2")
        if isinstance(data, dict):
            dom = self._sync_img_domain(data)
            return {"list": self._cards(data.get("records"), dom)}
        return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = int(pg)
        except Exception:
            page = 1
        if page < 1:
            page = 1
        ext = extend if isinstance(extend, dict) else {}
        tid = str(tid or "featured")
        if tid == "short":
            data = self._api("/app/movie/getShortVideoList?page=%d&pageSize=18" % page)
            return self._list_result(data, page)
        if tid == "featured":
            sort = str(ext.get("sort") or "2")
            data = self._api("/app/movie/getList?page=%d&pageSize=18&sort=%s" % (page, quote(sort, safe="")))
            return self._list_result(data, page)
        cid = tid
        sub = str(ext.get("sub") or "")
        if sub:
            cid = sub
        sort = str(ext.get("sort") or "1")
        data = self._api("/app/movie/getList?page=%d&pageSize=18&cid=%s&sort=%s" % (page, quote(cid, safe=""), quote(sort, safe="")))
        return self._list_result(data, page)

    def searchContent(self, key, quick, pg="1"):
        try:
            page = int(pg)
        except Exception:
            page = 1
        if page < 1:
            page = 1
        kw = str(key or "").strip()
        if not kw:
            return {"list": [], "page": page, "pagecount": page, "limit": 18, "total": 0}
        data = self._api("/app/movie/getList?keyword=%s&page=%d&pageSize=18" % (quote(kw, safe=""), page))
        return self._list_result(data, page)

    def detailContent(self, ids):
        raw_id = ids[0] if isinstance(ids, (list, tuple)) else str(ids)
        vk = str(raw_id or "").split("@@@")[0].strip()
        if not vk:
            return {"list": []}
        resp = self._api("/app/movie/getDetail?viewKey=%s" % quote(vk, safe=""))
        d = (resp or {}).get("data") if isinstance(resp, dict) else None
        if not isinstance(d, dict):
            return {"list": []}
        title = self._clean_title(d.get("title"))
        tags = []
        if d.get("tags"):
            for t in str(d.get("tags")).split(","):
                t = t.strip()
                if t:
                    tags.append(t)
        img_domain = self._sync_img_domain(d)
        pic = self._pic(img_domain, d.get("posterOriginal") or d.get("poster"))

        episodes = []
        episodes.append("%s$%s@@@%s" % ("正片", vk, title))
        rel = self._api("/app/movie/getDetailRelationList?viewKey=%s&page=1&pageSize=18" % quote(vk, safe=""))
        if isinstance(rel, dict) and isinstance(rel.get("records"), list):
            for rec in rel.get("records"):
                if not isinstance(rec, dict) or not rec.get("viewKey"):
                    continue
                rvk = str(rec.get("viewKey"))
                if rvk == vk:
                    continue
                rtitle = self._clean_title(rec.get("title")) or "推荐视频"
                ep_name = rtitle.replace("$", "").replace("#", "").replace("@", "")
                episodes.append("%s$%s@@@%s" % (ep_name, rvk, rtitle))

        vod = {
            "vod_id": vk,
            "vod_name": title,
            "vod_pic": pic,
            "vod_bg": pic,
            "vod_background": pic,
            "vod_banner": pic,
            "vod_actor": self.brandActor,
            "vod_director": self.brandDirector,
            "vod_remarks": format_remarks("蝴蝶影视", self._fmt_dur(d.get("duration"))),
            "vod_content": "🦋 蝴蝶影视专线加速播放 | 官方TG交流群：@tvshare23 | 4K高清原生极速画质",
            "vod_play_from": "蝴蝶专线",
            "vod_play_url": "#".join(episodes)
        }
        if tags:
            vod["vod_tag"] = ",".join(tags)
        rd = str(d.get("releaseDate") or "")
        if len(rd) >= 4:
            vod["vod_year"] = rd[:4]
        return {"list": [vod]}

    def playerContent(self, flag, id, vipFlags):
        raw = str(id or "").strip()
        parts = raw.split("@@@")
        vk = parts[0].strip()
        ep_title = parts[1].strip() if len(parts) > 1 else ""
        headers = {
            "User-Agent": self._ua,
            "Referer": self.host + "/",
            "Origin": self.host
        }
        if not vk:
            return {"parse": 0, "jx": 0, "url": "", "header": headers}
        resp = self._api("/app/movie/getPlayUrl?viewKey=%s" % quote(vk, safe=""))
        data = (resp or {}).get("data") if isinstance(resp, dict) else None
        if not isinstance(data, dict):
            return {"parse": 0, "jx": 0, "url": "", "header": headers}
        play_url = str(data.get("playUrl") or "")
        if not play_url:
            return {"parse": 0, "jx": 0, "url": "", "header": headers}
        domain = self.imgFallback
        infos = data.get("sourceInfoListVO")
        if isinstance(infos, list) and infos and isinstance(infos[0], dict) and infos[0].get("playDomain"):
            domain = str(infos[0].get("playDomain")).rstrip("/")
        if play_url.startswith("http"):
            full = play_url
        else:
            full = domain + play_url
        result = {"parse": 0, "jx": 0, "url": full, "header": headers}
        if ep_title:
            result["desc"] = ep_title
        return result

    def _sniff_mime(self, data):
        if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            return "image/webp"
        if len(data) >= 3 and data[:3] == b"\xff\xd8\xff":
            return "image/jpeg"
        if len(data) >= 4 and data[:4] == b"\x89PNG":
            return "image/png"
        if len(data) >= 4 and data[:4] == b"GIF8":
            return "image/gif"
        return ""

    def _put_img_cache(self, key, data):
        # 单图超过 512KB 不缓存，避免撑爆 TVBox 的 cache
        if not data or len(data) > 512 * 1024:
            return
        try:
            self.setCache(key, base64.b64encode(data).decode("ascii"))
        except Exception:
            pass

    def localProxy(self, params):
        try:
            p = params if isinstance(params, dict) else {}
            target = str(p.get("url") or "")
            # 只有 TVBox 没解码时才 unquote，避免二次解码破坏 URL
            if "%" in target and not target.startswith("http"):
                target = unquote(target)
            parsed = urlparse(target)
            if parsed.scheme not in ("http", "https") or not parsed.hostname:
                return [403, "text/plain; charset=utf-8", "url not allowed"]

            cache_key = "pyimg_" + hashlib.md5(target.encode("utf-8", "ignore")).hexdigest()
            cached = None
            try:
                cached = self.getCache(cache_key)
            except Exception:
                cached = None
            if cached:
                try:
                    raw = base64.b64decode(cached)
                    mime = self._sniff_mime(raw)
                    if mime:
                        return [200, mime, raw]
                except Exception:
                    pass

            # 图片请求：超时 5 秒、不重试，避免慢请求拖住列表
            code, raw = self._fetch(target, {
                "User-Agent": self._ua,
                "Referer": self.host + "/",
                "Accept-Encoding": "identity",
                "Connection": "keep-alive"
            }, timeout=5, retry=1)
            if code != 200 or not raw:
                return [502, "text/plain; charset=utf-8", "upstream error"]
            if len(raw) > 20 * 1024 * 1024:
                return [413, "text/plain; charset=utf-8", "too large"]

            mime = self._sniff_mime(raw)
            if mime:
                self._put_img_cache(cache_key, raw)
                return [200, mime, raw]

            plain = self._aes.decrypt(raw)
            if plain:
                mime = self._sniff_mime(plain)
                if mime:
                    self._put_img_cache(cache_key, plain)
                    return [200, mime, plain]
            return [415, "text/plain; charset=utf-8", "unknown image data"]
        except Exception:
            return [500, "text/plain; charset=utf-8", "proxy error"]

    def action(self, action):
        return {"msg": "ok"}

    def liveContent(self):
        return ""

    def isVideoFormat(self, url):
        low = str(url or "").lower()
        return (".m3u8" in low) or (".mp4" in low)

    def manualVideoCheck(self):
        return False

    def destroy(self):
        self.options = {}