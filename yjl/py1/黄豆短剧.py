#!/usr/bin/python
# -*- coding: utf-8 -*-
import gzip
import hashlib
import hmac
import json
import os
import re
import socket
import ssl
import time
import uuid
import requests
from urllib.parse import quote, unquote, parse_qsl, urljoin, urlparse

try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider:
        pass

_DOH_SERVERS = (
    "https://doh.pub/dns-query?name=%s&type=A",
    "https://dns.alidns.com/resolve?name=%s&type=A",
    "https://dns.google/resolve?name=%s&type=A",
    "https://cloudflare-dns.com/dns-query?name=%s&type=A",
)
_DOH_HOSTS = {"doh.pub", "dns.alidns.com", "dns.google", "cloudflare-dns.com"}
_FALLBACK_IPS = {"lzlukvca.cc": "104.21.12.21", "d3rorc0p4i1kyz.cloudfront.net": "52.222.206.47", "d2uz9pk0dgek0p.cloudfront.net": "18.64.16.48"}
_IP_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")
_doh_cache = {}
_orig_getaddrinfo = socket.getaddrinfo

def _verify(host, ip, port):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(8)
        s.connect((ip, port))
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ss = ctx.wrap_socket(s, server_hostname=host)
        ss.settimeout(8)
        ss.sendall(b"GET / HTTP/1.1\r\nHost: " + host.encode() + b"\r\nConnection: close\r\nUser-Agent: Mozilla/5.0\r\n\r\n")
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = ss.recv(512)
            if not chunk:
                break
            head += chunk
        ss.close()
        return head.startswith(b"HTTP/")
    except Exception:
        return False

def _doh_resolve(host, port=443):
    ip = _doh_cache.get(host)
    if ip:
        return ip
    cands = []
    for srv in _DOH_SERVERS:
        try:
            r = requests.get(srv % host, headers={"Accept": "application/dns-json"}, timeout=6, verify=False)
            for a in r.json().get("Answer", []):
                if a.get("type") == 1 and _IP_RE.match(a.get("data", "")):
                    cands.append(a["data"])
        except Exception:
            continue
    try:
        for r in _orig_getaddrinfo(host, port):
            if r[0] == socket.AF_INET and _IP_RE.match(r[4][0]):
                cands.append(r[4][0])
    except Exception:
        pass
    fb = _FALLBACK_IPS.get(host, "")
    if fb and fb not in cands:
        cands.append(fb)
    seen = []
    for c in cands:
        if c not in seen:
            seen.append(c)
    for c in seen:
        if _verify(host, c, port):
            _doh_cache[host] = c
            return c
    return ""

def _pinned_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    if isinstance(host, str) and host not in _DOH_HOSTS:
        pnum = int(port) if isinstance(port, int) else 443
        ip = _doh_resolve(host, pnum)
        if ip:
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port))]
    return _orig_getaddrinfo(host, port, family, type, proto, flags)

socket.getaddrinfo = _pinned_getaddrinfo

class _AESCBC:
    @staticmethod
    def encrypt(data, key, iv):
        try:
            from Crypto.Cipher import AES
            return AES.new(key, AES.MODE_CBC, iv).encrypt(_AESCBC.pad(data))
        except Exception:
            from cryptography.hazmat.backends import default_backend
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            enc = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend()).encryptor()
            return enc.update(_AESCBC.pad(data)) + enc.finalize()

    @staticmethod
    def decrypt(data, key, iv):
        try:
            from Crypto.Cipher import AES
            plain = AES.new(key, AES.MODE_CBC, iv).decrypt(data)
        except Exception:
            from cryptography.hazmat.backends import default_backend
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            dec = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend()).decryptor()
            plain = dec.update(data) + dec.finalize()
        return _AESCBC.unpad(plain)

    @staticmethod
    def pad(data):
        n = 16 - len(data) % 16
        return data + bytes([n]) * n

    @staticmethod
    def unpad(data):
        n = data[-1] if data else 0
        return data[:-n] if 1 <= n <= 16 else data

class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://lzlukvca.cc"
        self.api = self.host + "/api"
        self.name = "黄豆短剧"
        self.platform_key = "7961beb44246e3012ce228d6b5ced05a"
        self.version = "2.0.0"
        self.device_type = "web"
        self.session_id = uuid.uuid4().hex
        self.device_id = self.session_id
        self.token = ""
        self.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36", "Accept": "*/*", "Origin": self.host, "Referer": self.host + "/home", "Content-Type": "application/octet-stream"}
        self.media_header = {"User-Agent": self.headers["User-Agent"], "Referer": self.host + "/home", "Origin": self.host}
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.class_cache = None
        self.filter_cache = {}

    def init(self, extend=""):
        if extend:
            try:
                cfg = json.loads(extend)
                self.host = (cfg.get("site") or cfg.get("url") or self.host).rstrip("/")
                self.api = self.host + "/api"
                self.token = cfg.get("token", self.token)
                self.headers["Origin"] = self.host
                self.headers["Referer"] = self.host + "/home"
                self.session.headers.update(self.headers)
                fb = cfg.get("fallback")
                if isinstance(fb, dict):
                    _FALLBACK_IPS.update({str(k): str(v) for k, v in fb.items()})
                    _doh_cache.clear()
            except Exception:
                None

    def getName(self):
        return self.name

    def fix_url(self, url):
        if not url:
            return ""
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return self.host + url
        return url

    def homeContent(self, filter):
        data = self._api("/drama/list", {"page": "1", "page_size": "18"})
        classes = self._classes()
        return {"class": classes, "filters": self._filters(classes), "list": [self._vod(x) for x in self._list(data)], "parse": 0, "jx": 0}

    def categoryContent(self, tid, pg, filter, extend):
        extend = extend or {}
        if tid == "yuandou":
            data = self._api("/drama/navBlock", {"code": "yuandou", "tab": "recommend", "page": str(pg)})
            items = self._nav_items(data)
        else:
            req = {"page": str(pg), "page_size": "18"}
            if tid and tid not in ("all", "recommend"):
                tabs = self._nav_filter(tid)
                idx = self._int(extend.get("sub"), 0)
                sub = tabs[idx] if tabs and 0 <= idx < len(tabs) else {}
                flt = sub.get("filter", {}) if isinstance(sub, dict) else {}
                req["cat_id"] = flt.get("cat_id", "")
                if flt.get("tag_id"):
                    req["tag_id"] = flt.get("tag_id", "")
                req["order"] = flt.get("order", "") or extend.get("order", "")
            elif extend.get("order"):
                req["order"] = extend.get("order")
            if extend.get("update_status"):
                req["update_status"] = extend.get("update_status")
            data = self._api("/drama/list", req)
            items = self._list(data)
        return {"page": int(pg), "pagecount": int(pg) if len(items) < 18 else int(pg) + 1, "limit": 18, "total": 99999, "list": [self._vod(x) for x in items], "parse": 0, "jx": 0}

    def detailContent(self, ids):
        vid = str(ids[0]).replace("rp_", "")
        obj = self._api("/drama/detail", {"id": vid})
        data = obj.get("data", obj) if isinstance(obj, dict) else {}
        if not isinstance(data, dict):
            return {"list": []}
        data = self._unlock(data)
        vod_id = self._sid(data.get("id") or data.get("drama_id") or vid)
        name = data.get("name") or data.get("title") or data.get("t") or vod_id
        eps = data.get("episodes") if isinstance(data.get("episodes"), list) else []
        count = self._int(data.get("episode_count") or data.get("free_episodes"), len(eps) or 1)
        play = []
        if eps:
            for i, ep in enumerate(eps, 1):
                seq = ep.get("seq") or ep.get("episode") or ep.get("ep") or i
                play.append("%s$%s|%s" % (ep.get("name") or ep.get("title") or "第%s集" % seq, vod_id, seq))
        else:
            play = ["第%s集$%s|%s" % (i, vod_id, i) for i in range(1, count + 1)]
        vod = {"vod_id": vod_id, "vod_name": name, "vod_pic": self._pic(data), "type_name": data.get("category") or data.get("type") or "", "vod_year": "", "vod_area": "", "vod_remarks": data.get("update_label") or "全%s集" % count, "vod_actor": "", "vod_director": "", "vod_content": data.get("description") or data.get("summary") or name, "vod_play_from": self.name, "vod_play_url": "#".join(play)}
        return {"list": [vod], "parse": 0, "jx": 0}

    def searchContent(self, key, quick, pg="1"):
        data = self._api("/drama/list", {"page": str(pg), "page_size": "18", "keywords": str(key)})
        items = self._list(data)
        return {"page": int(pg), "pagecount": int(pg) if len(items) < 18 else int(pg) + 1, "limit": 18, "total": 99999, "list": [self._vod(x) for x in items], "parse": 0, "jx": 0}

    def playerContent(self, flag, id, vipFlags):
        s = str(id)
        if s.startswith("proxy?") or s.startswith("/proxy?") or s.startswith("/local/") or s.startswith("local://") or s.startswith("http://127.0.0.1"):
            p = self._param(s)
            inner = unquote(p.get("url", ""))
            if inner.startswith("http://") or inner.startswith("https://"):
                vid, seq = "", "1"
            else:
                vid, seq = self._split(inner)
        else:
            vid, seq = self._split(s)
        if not vid:
            return {"parse": 0, "playUrl": "", "url": s, "jx": 0, "header": json.dumps(self.media_header)}
        obj = self._api("/drama/play", {"id": vid, "seq": str(seq)}, True)
        data = obj.get("data", {}) if isinstance(obj, dict) else {}
        url = data.get("m3u8") or data.get("url") or self._hls(vid, seq)
        try:
            text = self._media_get(url).content.decode("utf-8", "ignore")
            if "#EXTM3U" in text:
                import base64
                return {"parse": 0, "playUrl": "", "url": "data:application/vnd.apple.mpegurl;base64," + base64.b64encode(text.encode("utf-8")).decode("ascii"), "jx": 0, "header": ""}
        except Exception:
            pass
        return {"parse": 0, "playUrl": "", "url": self._proxy_url("m3u8", url), "jx": 0, "header": json.dumps(self.media_header)}

    def localProxy(self, param):
        p = self._param(param)
        if p.get("do") != "py":
            return None
        typ = p.get("type", "")
        u = unquote(p.get("url", ""))
        if not u:
            return None
        if typ == "m3u8":
            if not (u.startswith("http://") or u.startswith("https://")):
                vid, seq = self._split(u)
                obj = self._api("/drama/play", {"id": vid, "seq": str(seq)}, True)
                data = obj.get("data", {}) if isinstance(obj, dict) else {}
                u = data.get("m3u8") or data.get("url") or self._hls(vid, seq)
            return [["Content-Type: application/vnd.apple.mpegurl"], self._proxy_m3u8(u)]
        if typ == "key":
            try:
                body = self._media_get(u).content
            except Exception:
                body = b""
            return [["Content-Type: application/octet-stream"], body]
        if typ == "ts":
            try:
                body = self._media_get(u).content
            except Exception:
                body = b""
            return [["Content-Type: video/mp2t"], body]
        return None

    def _proxy_url(self, typ, url):
        return "proxy?do=py&type=%s&url=%s" % (typ, quote(url, safe=""))

    def _proxy_m3u8(self, url):
        try:
            text = self._media_get(url).content.decode("utf-8", "ignore")
        except Exception:
            return b"#EXTM3U\n"
        out = []
        for ln in text.splitlines():
            s = ln.strip()
            if not s:
                out.append(ln)
                continue
            if s.startswith("#"):
                if s.startswith("#EXT-X-KEY:"):
                    m = re.search(r'URI="([^"]+)"', s)
                    if m:
                        s = s.replace(m.group(1), self._proxy_url("key", urljoin(url, m.group(1))))
                out.append(s)
                continue
            u = urljoin(url, s)
            typ = "m3u8" if (u.endswith(".m3u8") or "playlist" in u.lower()) else "ts"
            out.append(self._proxy_url(typ, u))
        return "\n".join(out).encode("utf-8")

    def _media_get(self, url):
        last = None
        for _ in range(3):
            try:
                r = self.session.get(url, headers=self.media_header, timeout=15, verify=False)
                r.raise_for_status()
                return r
            except Exception as e:
                last = e
                h = urlparse(url).hostname
                if h:
                    _doh_cache.pop(h, None)
                time.sleep(0.5)
        raise last

    def _param(self, param):
        if isinstance(param, dict):
            return param
        s = str(param)
        for pre in ("/proxy?", "/local/", "proxy?", "local://", "/proxy", "proxy", "local"):
            if s.startswith(pre):
                s = s[len(pre):]
                break
        if s.startswith("?"):
            s = s[1:]
        if "?" in s:
            s = s.split("?", 1)[-1]
        try:
            j = json.loads(s)
            if isinstance(j, dict):
                return {str(k): str(v) for k, v in j.items()}
        except Exception:
            pass
        return {k: v for k, v in parse_qsl(s)}

    def _api(self, path, data=None, silent=False, max_retry=3):
        path = "/" + path.lstrip("/")
        last_err = None
        for attempt in range(max_retry):
            try:
                rid = str(uuid.uuid4())
                key = self._key(rid)
                iv = os.urandom(16)
                raw = json.dumps({"token": self.token or "", "deviceId": self.device_id, "data": data or {}}, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                body = iv + _AESCBC.encrypt(gzip.compress(raw), key, iv)
                ts = int(time.time())
                sign = hashlib.sha256(("Dart|%s|%s|%s|%s" % (self.session_id, rid, ts, path)).encode("utf-8")).hexdigest() + "-" + str(ts)
                h = dict(self.headers)
                h.update({"version": self.version, "deviceType": self.device_type, "time": str(ts), "sign": sign, "requestId": rid, "sessionId": self.session_id, "deviceBrand": "", "deviceModel": "", "systemName": "", "systemVersion": ""})
                r = self.session.post(self.api + path, data=body, headers=h, timeout=20, verify=False)
                r.raise_for_status()
                result = self._decode(r.content, rid)
                if result or attempt == max_retry - 1:
                    return result
            except Exception as e:
                last_err = e
            if attempt < max_retry - 1:
                time.sleep(1 + attempt)
        return {}

    def _key(self, rid):
        return hmac.new(self.platform_key.encode("utf-8"), bytes.fromhex(str(rid).replace("-", "")), hashlib.sha256).digest()

    def _decode(self, blob, rid):
        if not blob or len(blob) < 32 or (len(blob) - 16) % 16 != 0:
            try:
                return json.loads(blob.decode("utf-8"))
            except Exception:
                return {}
        plain = _AESCBC.decrypt(blob[16:], self._key(rid), blob[:16])
        if plain[:2] == b"\x1f\x8b":
            plain = gzip.decompress(plain)
        return json.loads(plain.decode("utf-8"))

    _FALLBACK_CLASSES = [
        {"type_id": "all", "type_name": "全部短剧(兜底)"},
        {"type_id": "huangdouyuanchuang", "type_name": "黄豆原创(兜底)"},
        {"type_id": "mogai", "type_name": "魔改短剧(兜底)"},
        {"type_id": "aiman", "type_name": "AI漫剧(兜底)"},
        {"type_id": "dongman", "type_name": "动漫(兜底)"},
        {"type_id": "cabian", "type_name": "擦边短剧(兜底)"},
        {"type_id": "xianzhe", "type_name": "贤者(兜底)"},
        {"type_id": "heiliao", "type_name": "黑料(兜底)"},
        {"type_id": "chuanmei", "type_name": "传媒(兜底)"},
        {"type_id": "oumei", "type_name": "欧美(兜底)"},
        {"type_id": "zhenren", "type_name": "真人短剧(兜底)"},
        {"type_id": "yuandou", "type_name": "圆豆专区(兜底)"},
    ]

    def _cache_file(self):
        try:
            d = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".huangdou_cache")
            os.makedirs(d, exist_ok=True)
            return os.path.join(d, "classes.json")
        except Exception:
            return ""

    def _load_cache(self, key):
        try:
            f = self._cache_file()
            if f and os.path.exists(f):
                with open(f, "r", encoding="utf-8") as fp:
                    obj = json.load(fp)
                return obj.get(key)
        except Exception:
            pass
        return None

    def _save_cache(self, key, value):
        try:
            f = self._cache_file()
            if f:
                obj = {}
                if os.path.exists(f):
                    try:
                        with open(f, "r", encoding="utf-8") as fp:
                            obj = json.load(fp)
                    except Exception:
                        pass
                obj[key] = value
                obj["_time_" + key] = int(time.time())
                with open(f, "w", encoding="utf-8") as fp:
                    json.dump(obj, fp, ensure_ascii=False)
        except Exception:
            pass

    def _classes(self):
        if self.class_cache:
            return self.class_cache
        arr = [{"type_id": "all", "type_name": "全部短剧"}]
        data = self._api("/drama/navList", {})
        items = self._list(data.get("data", data) if isinstance(data, dict) else data)
        if items:
            for item in items:
                tid = str(item.get("code") or item.get("id") or item.get("cat_id") or "")
                name = item.get("name") or item.get("title") or tid
                if tid and name:
                    arr.append({"type_id": tid, "type_name": name})
            self.class_cache = arr
            self._save_cache("classes", arr)
        else:
            cached = self._load_cache("classes")
            if cached and isinstance(cached, list) and len(cached) > 1:
                arr = [dict(c) for c in cached]
                arr[0]["type_name"] = arr[0].get("type_name", "") + "(缓存)"
                for i in range(1, len(arr)):
                    if "(" not in arr[i].get("type_name", ""):
                        arr[i]["type_name"] = arr[i]["type_name"] + "(缓存)"
            else:
                arr = [dict(c) for c in self._FALLBACK_CLASSES]
        return arr

    def _filters(self, classes):
        common = [{"key": "order", "name": "排序", "value": [{"n": "默认", "v": ""}, {"n": "最新", "v": "new"}, {"n": "最热", "v": "hot"}]}, {"key": "update_status", "name": "状态", "value": [{"n": "全部", "v": ""}, {"n": "连载", "v": "0"}, {"n": "完结", "v": "1"}]}]
        fs = {}
        for c in classes:
            tid = c["type_id"]
            tabs = self._nav_filter(tid) if tid not in ("all", "yuandou") else []
            fs[tid] = ([{"key": "sub", "name": "子分类", "value": [{"n": t.get("name", "默认"), "v": str(i)} for i, t in enumerate(tabs)]}] if tabs else []) + common
        return fs

    def _nav_filter(self, code):
        if code not in self.filter_cache:
            data = self._api("/drama/navFilter", {"code": str(code)})
            self.filter_cache[code] = self._list(data.get("data", data) if isinstance(data, dict) else data)
        return self.filter_cache.get(code, [])

    def _list(self, data):
        if isinstance(data, list):
            return data
        if not isinstance(data, dict):
            return []
        if isinstance(data.get("list"), list):
            return data["list"]
        if isinstance(data.get("items"), list):
            return data["items"]
        if isinstance(data.get("data"), list):
            return data["data"]
        if isinstance(data.get("data"), dict):
            return self._list(data["data"])
        return []

    def _nav_items(self, data):
        blocks = self._list(data.get("data", data) if isinstance(data, dict) else data)
        items = []
        for b in blocks:
            if isinstance(b, dict) and isinstance(b.get("items"), list):
                items += b.get("items")
            elif isinstance(b, dict) and (b.get("id") or b.get("drama_id")):
                items.append(b)
        return items

    def _vod(self, item):
        item = item or {}
        vid = self._sid(item.get("id") or item.get("drama_id") or "")
        remarks = item.get("update_label") or item.get("corner") or ("全%s集" % item.get("episode_count") if item.get("episode_count") else "")
        return {"vod_id": vid, "vod_name": item.get("name") or item.get("title") or item.get("t") or vid, "vod_pic": self._pic(item), "vod_remarks": remarks}

    def _pic(self, item):
        return item.get("img_y") or item.get("img_x") or item.get("img") or item.get("cover") or item.get("pic") or ""

    def _unlock(self, d):
        eps = d.get("episodes")
        if isinstance(eps, list):
            for ep in eps:
                if isinstance(ep, dict):
                    ep["is_buy"] = True
                    ep["type"] = "free"
                    ep["price"] = 0
                    ep["methods"] = []
        d.update({"pay_type": "free", "money": 0, "episode_price": 0, "points_price": 0, "can_vip_watch": True, "is_buy_whole": True, "vip_episodes": [], "coin_episodes": [], "points_episodes": []})
        return d

    def _sid(self, x):
        return str(x or "").replace("rp_", "")

    def _split(self, x):
        p = str(x).split("|", 1)
        return self._sid(p[0]), p[1] if len(p) > 1 and p[1] else "1"

    def _hls(self, vid, seq):
        return "%s/api/drama/hls/%s/%s/play.m3u8?line=free" % (self.host, self._sid(vid), seq)

    def _int(self, x, d=0):
        try:
            return int(x)
        except Exception:
            return d
