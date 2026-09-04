# -*- coding: utf-8 -*-
# 欢迎来到有料视频！牢记回家地址：  yltv.live
# 1.编辑任意邮件至邮箱获取最新下载地址youliao1688@gmail.com(地址找回)
import base64
import hashlib
import json
import time

try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider(object):
        pass

try:
    import requests
except Exception:
    requests = None

import urllib.request
import urllib.parse


class _AES(object):
    @staticmethod
    def dec(data, key, iv):
        try:
            from Crypto.Cipher import AES
            return _AES.unpad(AES.new(key, AES.MODE_CBC, iv).decrypt(data))
        except Exception:
            pass
        try:
            from Cryptodome.Cipher import AES
            return _AES.unpad(AES.new(key, AES.MODE_CBC, iv).decrypt(data))
        except Exception:
            pass
        try:
            from cryptography.hazmat.backends import default_backend
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            d = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend()).decryptor()
            return _AES.unpad(d.update(data) + d.finalize())
        except Exception:
            pass
        try:
            import pyaes
            out = b""
            c = pyaes.AESModeOfOperationCBC(key, iv=iv)
            for i in range(0, len(data) - 15, 16):
                out += c.decrypt(data[i:i + 16])
            return _AES.unpad(out)
        except Exception:
            return b""

    @staticmethod
    def unpad(d):
        n = d[-1] if d else 0
        return d[:-n] if 1 <= n <= 16 else d


class Spider(BaseSpider):
    SALT = "a2ef62227536ab01"
    KEY = b"ec5279154d05ac2c"
    IV = b"515cd1587d7cfbdd"
    INIT_HOSTS = ["https://web.al.ctqhnw.com/api", "https://xginit.ylapi3321.com/api",
                  "https://init.qn.ctqhnw.com/api", "https://init.qn.nwglda.com/api",
                  "https://xginit.ylapi1688.com/api", "https://h5init.qn.pnwkult.com/api",
                  "https://init.al.pnwkult.com/api", "https://init.youliao88.com/api",
                  "https://h5init.m.nbajkbq.com/api", "https://h5init.qn.nbajkbq.com/api",
                  "https://h5init.al.pnwkult.com/api"]
    CHANNEL = "1031"
    UA = "Mozilla/5.0 (Linux; Android 12; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
    ORIGIN = "https://0zq6w.shddlcd.cn"
    PROXY = "https://py.fzcrym.link:1314"
    API_PROXY = PROXY + "/yl_api"
    IMG_KEY = hashlib.sha256(b"sdkvgl2hj92h23h923h").digest()
    NEW = "n_new"
    LIB = "n_lib"
    YL = "n_yl"
    YL_SUBS = [{"n": "黑料", "v": "gossip"}, {"n": "漫画", "v": "comic"}, {"n": "小说", "v": "novel"}, {"n": "电台", "v": "radio"}]
    LIVE = "n_live"

    def init(self, extend=""):
        self.api = ""
        self.token = ""
        self.uid = ""
        self.viaproxy = False
        self.cate2 = {}
        self.plans = {}
        self.libs = []
        self.yl_cc = []
        self.yl_nc = []
        self.live_conf = []
        self.lives = []
        self._live_pool = {}
        self.live_api = ""
        self._boot()
        return self

    def getName(self):
        return "有料"

    def isVideoFormat(self, url):
        u = str(url or "")
        if u.startswith(("novel://", "pics://")):
            return False
        return ".m3u8" in u or u.endswith(".mp4") or u.endswith(".mp3") or u.endswith(".m4a")

    def manualVideoCheck(self):
        return False

    def destroy(self):
        return

    def _sign(self, path, t):
        return hashlib.md5(("%s?time=%s&%s" % (path, t, self.SALT)).encode()).hexdigest().lower()

    def _dec(self, text):
        try:
            p = _AES.dec(base64.b64decode(text), self.KEY, self.IV)
            if p:
                return json.loads(p.decode("utf-8", "ignore"))
        except Exception:
            pass
        try:
            return json.loads(text)
        except Exception:
            return {}

    def _post(self, base, path, data=None, auth=True):
        t = int(time.time())
        p = urllib.parse.urlparse(base + path).path
        h = {"time": str(t), "sign": self._sign(p, t), "Content-Type": "application/x-www-form-urlencoded",
             "User-Agent": self.UA, "Origin": self.ORIGIN, "Referer": self.ORIGIN + "/"}
        if auth and self.token and self.uid:
            h["uid"] = str(self.uid)
            h["token"] = self.token
            h["Access-Token"] = self.token
        body = urllib.parse.urlencode(data or {}).encode()
        try:
            if requests:
                return self._dec(requests.post(base + path, data=body, headers=h, timeout=20).text)
            return self._dec(urllib.request.urlopen(urllib.request.Request(base + path, data=body, headers=h), timeout=20).read().decode("utf-8", "ignore"))
        except Exception:
            return {}

    def _boot(self):
        if self.api:
            return True
        for host in self.INIT_HOSTS:
            r = self._post(host, "/player/do_init_h5", {"system": 3, "channel": self.CHANNEL, "new_live": 1}, False)
            d = r.get("data") if isinstance(r, dict) else None
            if isinstance(d, dict) and d.get("api_url"):
                self.api = d["api_url"].rstrip("/") + "/api"
                pi = d.get("player_info") or {}
                self.token = pi.get("token") or ""
                self.uid = pi.get("uid") or ""
                self.viaproxy = False
                self.live_conf = d.get("live_conf") or []
                self._merge_hosts(d.get("api_backup"))
                return True
        return self._boot_proxy()

    def _merge_hosts(self, backup):
        extra = []
        for x in str(backup or "").split(","):
            x = x.strip().rstrip("/")
            if not x:
                continue
            if not x.endswith("/api"):
                x += "/api"
            extra.append(x)
        if extra:
            seen = set(extra)
            self.INIT_HOSTS = extra + [h for h in self.INIT_HOSTS if h not in seen]

    def _boot_proxy(self):
        r = self._proxy("/player/do_init_h5", {"system": 3, "channel": self.CHANNEL, "new_live": 1})
        d = r.get("data") if isinstance(r, dict) else None
        if isinstance(d, dict) and d.get("api_url"):
            self.api = d["api_url"].rstrip("/") + "/api"
            pi = d.get("player_info") or {}
            self.token = pi.get("token") or ""
            self.uid = pi.get("uid") or ""
            self.viaproxy = True
            self.live_conf = d.get("live_conf") or []
            self._merge_hosts(d.get("api_backup"))
            return True
        return False

    def _proxy(self, path, data=None):
        url = "%s?p=%s&d=%s" % (self.API_PROXY, urllib.parse.quote(path, safe=""),
                                urllib.parse.quote(json.dumps(data or {}, ensure_ascii=False), safe=""))
        h = {"User-Agent": self.UA}
        try:
            if requests:
                return json.loads(requests.get(url, headers=h, timeout=25).text)
            return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=25).read().decode("utf-8", "ignore"))
        except Exception:
            return {}

    def _ok(self, r):
        return isinstance(r, dict) and (r.get("code") == 1 or r.get("data"))

    def _call(self, path, data=None):
        if not self._boot():
            return {}
        payload = dict(data or {})
        if "is_h5" not in payload:
            payload["is_h5"] = 1
        if self.viaproxy:
            r = self._proxy(path, payload)
            return r if isinstance(r, dict) else {}
        r = self._post(self.api, path, payload)
        if isinstance(r, dict) and r.get("code") == 3:
            self.api = ""
            if self._boot():
                r = self._post(self.api, path, payload) if not self.viaproxy else self._proxy(path, payload)
        if not self._ok(r):
            hosts = ([self.live_api] if self.live_api else []) + [h for h in self.INIT_HOSTS if h != self.live_api]
            for host in hosts:
                if not host:
                    continue
                rr = self._post(host, path, payload)
                if self._ok(rr):
                    self.live_api = host
                    return rr
            r = self._proxy(path, payload)
            if isinstance(r, dict) and r.get("code") == 1:
                self.viaproxy = True
        return r if isinstance(r, dict) else {}

    def _full(self, url):
        u = str(url or "")
        if ".m3u8" not in u:
            return u
        name = u[u.rfind("/") + 1:].split("?")[0]
        if name.startswith("index"):
            i = u.rfind("/")
            return u[:i + 1] + "index.m3u8" if i > 0 else u
        return u

    def _live_h(self):
        return {
            "User-Agent": self.UA,
            "Referer": "https://stripchat.com/",
            "Origin": "https://stripchat.com",
            "Accept": "*/*",
        }

    def _hdr_ext(self):
        return json.dumps(self._live_h())

    def _hls_swap(self, media, tag):
        u = str(media or "")
        i = u.rfind("/")
        if i < 0:
            return ""
        name = u[i + 1:]
        ident = name.split("_")[0].split(".")[0]
        if not ident:
            return ""
        return u[:i + 1] + ident + "_" + tag + ".m3u8"

    def _hls_ok(self, url):
        t = self._fetch_text(url, self._live_h(), 8)
        return t if t and "#EXTINF" in t else ""

    def _hls_levels(self, url):
        u = str(url or "").strip()
        if not u.startswith("http"):
            return []
        found, sample = {}, ""
        txt = self._fetch_text(u, self._live_h(), 8)
        if not txt:
            return [("直播", u)]
        if "#EXTINF" in txt and "#EXT-X-STREAM-INF" not in txt:
            for tag in ("480p", "720p", "1080p", "240p"):
                if "_" + tag in u:
                    found[tag] = u
                    sample = u
                    break
            if not found:
                return [("直播", u)]
        else:
            lines = txt.replace("\r", "").split("\n")
            for i, line in enumerate(lines):
                if not line.startswith("#EXT-X-STREAM-INF:"):
                    continue
                nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
                if not nxt or nxt.startswith("#"):
                    continue
                su = self._abs(u[:u.rfind("/")], nxt)
                name = line.split('NAME="', 1)[1].split('"', 1)[0] if 'NAME="' in line else ""
                for tag in ("480p", "720p", "1080p", "240p"):
                    if tag in name or "_" + tag in su:
                        found[tag] = su
                        sample = su
        if sample:
            miss = [tag for tag in ("480p", "720p", "1080p") if tag not in found]

            def _one(tag):
                cand = self._hls_swap(sample, tag)
                return tag, cand if cand and self._hls_ok(cand) else ""

            if miss:
                try:
                    from concurrent.futures import ThreadPoolExecutor
                    with ThreadPoolExecutor(max_workers=min(3, len(miss))) as ex:
                        for tag, cand in ex.map(_one, miss):
                            if cand:
                                found[tag] = cand
                except Exception:
                    for tag in miss:
                        _, cand = _one(tag)
                        if cand:
                            found[tag] = cand
        order = ("480p", "720p", "1080p", "240p")
        out = [(tag, found[tag]) for tag in order if tag in found]
        return out or [("直播", u)]

    def _pick_hls(self, url):
        u = str(url or "")
        for tag in ("480p", "720p", "240p", "1080p"):
            if "_" + tag in u:
                return u
        lv = self._hls_levels(url)
        pref = dict(lv)
        for tag in ("480p", "720p", "240p", "1080p"):
            if tag in pref:
                return pref[tag]
        return lv[0][1] if lv else url

    def _num(self, n):
        try:
            v = float(n)
            return "%.1fw" % (v / 10000) if v >= 10000 else str(int(v))
        except Exception:
            return str(n)

    def _abs(self, base, u):
        u = str(u or "").strip()
        if not u:
            return ""
        if u.startswith("//"):
            return "https:" + u
        if u.startswith("http"):
            return u
        b = str(base or "").rstrip("/")
        if u.startswith("/"):
            return b + u if b else u
        return (b + "/" + u) if b else u

    def _proxy_url(self):
        try:
            u = str(self.getProxyUrl() or "")
            if u:
                return u
        except Exception:
            pass
        try:
            u = str(self.getProxy(True) or "")
            if u:
                return u
        except Exception:
            pass
        return "http://127.0.0.1:9978/proxy?do=py"

    def _img(self, u):
        u = str(u or "").strip()
        if not u:
            return ""
        if u.startswith("//"):
            u = "https:" + u
        if not u.startswith("http"):
            return u
        if "qgtp." not in u:
            return u
        pu = self._proxy_url()
        sep = "&" if "?" in pu else "?"
        return "%s%syl=img&url=%s" % (pu, sep, urllib.parse.quote(u, safe=""))

    def _pics(self, imgs, base=""):
        urls = []
        for x in imgs or []:
            u = self._img(self._abs(base, x))
            if u:
                urls.append(u)
        return "pics://%s" % "&&".join(urls) if urls else ""

    def _dec_txt(self, text):
        try:
            p = _AES.dec(base64.b64decode(str(text or "").strip()), self.KEY, self.IV)
            if p:
                t = p.decode("utf-8", "ignore")
                if t:
                    return t
        except Exception:
            pass
        return str(text or "")

    def _dec_img(self, blob):
        if not blob:
            return b"", "image/jpeg"
        if blob[:3] == b"\xff\xd8\xff":
            return blob, "image/jpeg"
        if blob[:8] == b"\x89PNG\r\n\x1a\n":
            return blob, "image/png"
        if blob[:4] == b"GIF8":
            return blob, "image/gif"
        try:
            t = blob.decode("utf-8", "ignore").replace(" ", "").replace("\n", "").replace("\r", "")
            raw = base64.b64decode(t)
            if len(raw) < 2:
                return blob, "image/jpeg"
            n, key = raw[0], self.IMG_KEY
            out = bytes(((b - n) ^ key[i % 32]) & 255 for i, b in enumerate(raw[1:]))
            if out[:8] == b"\x89PNG\r\n\x1a\n":
                return out, "image/png"
            if out[:4] == b"GIF8":
                return out, "image/gif"
            if len(out) > 12 and out[8:12] == b"WEBP":
                return out, "image/webp"
            return out, "image/jpeg"
        except Exception:
            return blob, "image/jpeg"

    def _fetch_bytes(self, url):
        u = str(url or "").strip()
        if not u.startswith("http"):
            return b""
        h = {"User-Agent": self.UA, "Referer": self.ORIGIN + "/", "Accept": "*/*"}
        try:
            if requests:
                return requests.get(u, headers=h, timeout=20).content
            return urllib.request.urlopen(urllib.request.Request(u, headers=h), timeout=20).read()
        except Exception:
            return b""

    def _vod(self, it):
        vid = it.get("video_id") or it.get("id") or ""
        name = it.get("title") or it.get("video_title") or it.get("name") or ""
        pic = it.get("img") or it.get("video_img") or it.get("cover") or it.get("icon") or ""
        rem = str(it.get("video_time") or it.get("time") or "")
        pn = it.get("play_num") or it.get("video_play_num")
        if pn:
            rem = ("%s %s" % (rem, self._num(pn))).strip()
        return {"vod_id": str(vid), "vod_name": str(name), "vod_pic": self._img(pic), "vod_remarks": rem}

    def _pic_raw(self, it):
        return str(it.get("img") or it.get("cover") or it.get("image") or it.get("image_url") or it.get("icon") or it.get("pic") or "")

    def _yl_vod(self, it, kind):
        if kind == "g":
            vid = "g_%s" % (it.get("post_id") or it.get("id") or "")
            rem = str(it.get("create_time") or it.get("created_at") or it.get("video_time") or "")
            pn = it.get("views") or it.get("view_num") or it.get("play_num")
            if pn:
                rem = ("%s %s" % (rem, self._num(pn))).strip()
        elif kind == "c":
            vid = "c_%s" % (it.get("comic_id") or it.get("id") or "")
            rem = str(it.get("num") or it.get("score") or it.get("cate_name") or "")
        elif kind == "n":
            vid = "n_%s" % (it.get("novel_id") or it.get("id") or "")
            rem = str(it.get("num") or it.get("cate_name") or it.get("tags") or "")
        else:
            vid = "r_%s" % (it.get("novel_id") or it.get("id") or "")
            rem = str(it.get("num") or it.get("cate_name") or it.get("tags") or "")
        name = it.get("title") or it.get("name") or ""
        return {"vod_id": str(vid), "vod_name": str(name), "vod_pic": self._img(self._pic_raw(it)), "vod_remarks": rem}

    def _yl_map(self, items, kind):
        seen, out = set(), []
        for it in items:
            if not isinstance(it, dict):
                continue
            try:
                v = self._yl_vod(it, kind)
            except Exception:
                continue
            if not v["vod_id"] or v["vod_id"].endswith("_") or not v["vod_name"] or v["vod_id"] in seen:
                continue
            seen.add(v["vod_id"])
            out.append(v)
        return out

    def _yl_ready(self, items, kind, pg, limit):
        vl = self._yl_map(items, kind)
        pc = pg + 1 if len(vl) >= limit else pg
        return {"list": vl, "page": pg, "pagecount": pc, "limit": limit, "total": pc * limit}

    def _as_list(self, v):
        if isinstance(v, list):
            return [x for x in v if x]
        if isinstance(v, str) and v.strip():
            return [v.strip()]
        return []

    def _data_list(self, r):
        d = r.get("data") if isinstance(r, dict) else r
        if isinstance(d, list):
            return d
        if isinstance(d, dict):
            for k in ("list", "data", "items", "rows"):
                if isinstance(d.get(k), list):
                    return d[k]
        return self._pick(d)

    def _pick(self, obj):
        if isinstance(obj, list):
            return obj
        if not isinstance(obj, dict):
            return []
        for k in ("list", "data", "items", "rows", "video_list", "library_list"):
            v = obj.get(k)
            if isinstance(v, list):
                return v
            if isinstance(v, dict):
                r = self._pick(v)
                if r:
                    return r
        return []

    def _flat(self, arr):
        out = []
        for x in arr:
            if isinstance(x, dict) and isinstance(x.get("list"), list):
                out += x["list"]
            elif isinstance(x, dict):
                out.append(x)
        return out

    def _dedup(self, items):
        seen, out = set(), []
        for it in items:
            if not isinstance(it, dict):
                continue
            try:
                v = self._vod(it)
            except Exception:
                continue
            if not v["vod_id"] or not v["vod_name"] or v["vod_id"] in seen:
                continue
            seen.add(v["vod_id"])
            out.append(v)
        return out

    def homeContent(self, filter):
        d = self._call("/video/index", {}).get("data") or {}
        extra = [{"type_id": self.YL, "type_name": "有料"}, {"type_id": self.LIVE, "type_name": "直播"}]
        cls = [{"type_id": self.NEW, "type_name": "最新"}]
        placed = False
        for c in (d.get("cate_list") or []):
            if not c.get("cate_id"):
                continue
            name = str(c.get("name") or c["cate_id"])
            if name == "推荐":
                continue
            if not placed and "17岁" in name:
                cls.extend(extra)
                placed = True
            cls.append({"type_id": str(c["cate_id"]), "type_name": name})
        if not placed:
            cls.extend(extra)
        cls.append({"type_id": self.LIB, "type_name": "片库"})
        vl = []
        for b in (d.get("recommend_list") or []):
            vl += b.get("list") or []
        return {"class": cls, "filters": self._filters(cls), "list": self._dedup(vl)}

    def _filters(self, cls):
        f = {}
        lg = self._libs()
        if lg:
            f[self.LIB] = [{"key": "lib", "name": "片库", "value": lg}]
        f[self.YL] = [{"key": "yl", "name": "子类", "value": list(self.YL_SUBS)}]
        f[self.LIVE] = [{"key": "live", "name": "子类", "value": self._live_subs()}]
        for c in cls:
            tid = c["type_id"]
            if tid in (self.NEW, self.LIB, self.YL, self.LIVE):
                continue
            subs = self._subs(tid)
            if not subs:
                continue
            f[tid] = [{"key": "cate2", "name": "子类",
                       "value": [{"n": "全部", "v": ""}] + [{"n": str(s.get("name") or ""), "v": str(s.get("id"))} for s in subs if s.get("id")]}]
        return f

    def _subs(self, tid):
        if tid in self.cate2:
            return self.cate2[tid]
        r = self._call("/video/cate2", {"cate_id": tid})
        subs = r.get("data") if isinstance(r.get("data"), list) else []
        if not subs:
            subs = (self._call("/video/cate_list", {"cate_id": tid, "page": 1}).get("data") or {}).get("cate2_list") or []
        self.cate2[tid] = subs
        return subs

    def _plan(self, tid):
        if tid in self.plans:
            return self.plans[tid]
        plan = []
        for s in self._subs(tid):
            sid = s.get("id")
            if not sid:
                continue
            try:
                cnt = int(s.get("video_count") or 0)
            except Exception:
                cnt = 0
            pages = (cnt + 19) // 20 if cnt else 30
            for p in range(1, pages + 1):
                plan.append((str(sid), p))
        self.plans[tid] = plan
        return plan

    def _libs(self):
        if self.libs:
            return self.libs
        d = self._call("/video/video_library_list", {"page": 1}).get("data") or {}
        out = [{"n": "全部", "v": ""}]
        for g in (d.get("library_list") or []):
            gn = str(g.get("name") or "")
            for it in (g.get("list") or []):
                if it.get("library_id"):
                    out.append({"n": "%s·%s" % (gn, it.get("name") or ""), "v": str(it["library_id"])})
        self.libs = out if len(out) > 1 else []
        return self.libs

    def homeVideoContent(self):
        return {"list": self.homeContent(False)["list"]}

    def _batch(self, jobs):
        out = []
        if not jobs:
            return out
        try:
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=min(8, len(jobs))) as ex:
                for r in ex.map(lambda j: self._pick(self._call("/video/cate2_list", {"cate2_id": j[0], "page": j[1]}).get("data")), jobs):
                    out += r
        except Exception:
            for j in jobs:
                out += self._pick(self._call("/video/cate2_list", {"cate2_id": j[0], "page": j[1]}).get("data"))
        return out

    def _yl_groups(self, path, cache_attr):
        cached = getattr(self, cache_attr, None)
        if cached:
            return cached
        d = self._call(path, {"page": 1, "page_size": 50, "list_size": 20}).get("data")
        groups = d if isinstance(d, list) else self._pick(d)
        groups = [g for g in (groups or []) if isinstance(g, dict)]
        setattr(self, cache_attr, groups)
        return groups

    def _yl_page(self, ch, pg):
        pg = max(int(pg or 1), 1)
        if ch == "gossip":
            return self._yl_ready(self._data_list(self._call("/post/post_list", {"page": pg, "page_size": 12, "type": 2})), "g", pg, 12)
        if ch == "radio":
            return self._yl_ready(self._data_list(self._call("/novel/novel_list", {"type": 2, "page": pg, "page_size": 20})), "r", pg, 20)
        if ch == "comic":
            groups = self._yl_groups("/comic/comic_index", "yl_cc")
            if pg == 1:
                return self._yl_ready(self._flat(groups), "c", pg, 40)
            cid = ""
            for g in groups:
                if g.get("cate_id"):
                    cid = g.get("cate_id")
                    break
            payload = {"page": pg, "page_size": 20}
            if cid:
                payload["cate_id"] = cid
            return self._yl_ready(self._data_list(self._call("/comic/comic_cate_list", payload)), "c", pg, 20)
        groups = self._yl_groups("/novel/novel_index", "yl_nc")
        if pg == 1:
            return self._yl_ready(self._flat(groups), "n", pg, 40)
        cid = ""
        for g in groups:
            if g.get("cate_id"):
                cid = g.get("cate_id")
                break
        if cid:
            return self._yl_ready(self._data_list(self._call("/novel/novel_cate_list", {"cate_id": cid, "page": pg, "page_size": 20})), "n", pg, 20)
        return self._yl_ready(self._data_list(self._call("/novel/novel_list", {"type": 1, "page": pg, "page_size": 20})), "n", pg, 20)

    def _live_subs(self):
        if self.lives:
            return self.lives
        out = []
        r = self._call("/live/live_index", {"page": 1, "page_size": 20, "new_live": 1})
        for c in ((r.get("data") or {}).get("cate") or []):
            if c.get("cate_id"):
                out.append({"n": str(c.get("name") or c["cate_id"]), "v": "sm_%s" % c["cate_id"]})
        if not out:
            out.append({"n": "SM", "v": "sm_14"})
        self._boot()
        for c in (self.live_conf or []):
            n = str(c.get("name") or "").strip()
            u = str(c.get("url") or "").strip()
            if n and u:
                out.append({"n": n, "v": u})
        self.lives = out
        return out

    def _live_fetch(self, url):
        if url in self._live_pool:
            return self._live_pool[url]
        items = []
        try:
            txt = self._fetch_text(url)
            if txt:
                d = self._dec(txt)
                data = d.get("data") if isinstance(d, dict) else None
                if isinstance(data, list):
                    items = [x for x in data if isinstance(x, dict) and x.get("username")]
        except Exception:
            pass
        self._live_pool[url] = items
        return items

    def _live_sm(self, cid, pg):
        pg = max(int(pg or 1), 1)
        items = []
        try:
            r = self._call("/live/live_index", {"cate_id": cid, "page": pg, "page_size": 20, "new_live": 1})
            for c in ((r.get("data") or {}).get("cate") or []):
                if str(c.get("cate_id")) == str(cid):
                    items = c.get("list") or []
                    break
        except Exception:
            pass
        vl = []
        for it in items:
            if not isinstance(it, dict) or it.get("is_ad"):
                continue
            vid = it.get("video_id")
            name = it.get("author")
            if not vid or not name:
                continue
            on = it.get("online_number")
            vl.append({"vod_id": "l_%s" % vid, "vod_name": str(name),
                       "vod_pic": self._img(str(it.get("img") or it.get("author_img") or "")),
                       "vod_remarks": ("%s人在线" % self._num(on)) if on else ""})
        pc = pg + 1 if len(items) >= 20 else pg
        return {"list": vl, "page": pg, "pagecount": max(pc, pg), "limit": 20, "total": pc * 20}

    def _live_ext(self, url, pg):
        pg = max(int(pg or 1), 1)
        items = self._live_fetch(url)
        limit = 40
        total = len(items)
        pc = max((total + limit - 1) // limit, 1) if total else 1
        seg = items[(pg - 1) * limit:pg * limit] if total else []
        vl = []
        for it in seg:
            hls = str(it.get("hlsPlaylist") or "").strip()
            if not hls:
                continue
            name = str(it.get("username") or "")
            if not name:
                continue
            pic = str(it.get("preview") or it.get("avatar") or "")
            on = it.get("members")
            q = urllib.parse.quote(hls, safe="")
            if pic:
                q = "%s::%s" % (q, urllib.parse.quote(pic, safe=""))
            vl.append({"vod_id": "z_%s" % q,
                       "vod_name": name,
                       "vod_pic": self._img(pic),
                       "vod_remarks": ("%s人在线" % self._num(on)) if on else ""})
        return {"list": vl, "page": pg, "pagecount": pc, "limit": limit, "total": total}

    def categoryContent(self, tid, pg, filter, extend):
        pg = max(int(pg or 1), 1)
        ext = extend or {}
        if tid == self.NEW:
            items = self._pick(self._call("/video/new_update_list", {"page": pg}).get("data"))
            return self._page(items, pg, 12)
        if tid == self.LIB:
            lid = str(ext.get("lib") or "")
            if lid:
                return self._sub_page(lid, pg)
            items = (self._call("/video/video_library_list", {"page": pg}).get("data") or {}).get("list") or []
            return self._page(items, pg, 20)
        if tid == self.YL:
            return self._yl_page(str(ext.get("yl") or "gossip").strip() or "gossip", pg)
        if tid == self.LIVE:
            lv = str(ext.get("live") or "").strip()
            if lv.startswith("sm_"):
                return self._live_sm(lv[3:], pg)
            if lv:
                return self._live_ext(lv, pg)
            subs = self._live_subs()
            first = subs[0].get("v") if subs else "sm_14"
            if str(first).startswith("sm_"):
                return self._live_sm(str(first)[3:], pg)
            return self._live_ext(str(first), pg)
        c2 = str(ext.get("cate2") or "").strip()
        if c2:
            return self._sub_page(c2, pg)
        plan = self._plan(tid)
        if not plan:
            items = self._flat((self._call("/video/cate_list", {"cate_id": tid, "page": pg}).get("data") or {}).get("list") or [])
            return self._page(items, pg, 42)
        per = 2
        total = len(plan)
        pc = max((total + per - 1) // per, 1)
        jobs = plan[(pg - 1) * per:pg * per]
        vl = self._dedup(self._batch(jobs))
        return {"list": vl, "page": pg, "pagecount": pc, "limit": 40, "total": total * 20}

    def _sub_page(self, sid, pg):
        items = self._pick(self._call("/video/cate2_list", {"cate2_id": sid, "page": pg}).get("data"))
        cnt = 0
        for subs in self.cate2.values():
            for s in subs:
                if str(s.get("id")) == str(sid):
                    try:
                        cnt = int(s.get("video_count") or 0)
                    except Exception:
                        cnt = 0
        if not cnt:
            info = (self._call("/video/cate2_list", {"cate2_id": sid, "page": 1}).get("data") or {}).get("cate2_info") or {}
            try:
                cnt = int(info.get("count") or 0)
            except Exception:
                cnt = 0
        vl = self._dedup(items)
        pc = (cnt + 19) // 20 if cnt else (pg + 1 if len(vl) >= 20 else pg)
        return {"list": vl, "page": pg, "pagecount": max(pc, pg), "limit": 20, "total": cnt or pc * 20}

    def _page(self, items, pg, limit):
        vl = self._dedup(items)
        pc = pg + 1 if len(vl) >= limit else pg
        return {"list": vl, "page": pg, "pagecount": pc, "limit": limit, "total": pc * limit}

    def searchContent(self, key, quick, pg="1"):
        pg = int(pg or 1)
        items = self._pick(self._call("/video/search_list", {"keyword": key, "page": pg}).get("data"))
        if not items and pg == 1:
            items = self._pick(self._call("/video/search_video_library", {"keyword": key, "page": pg}).get("data"))
        vl = self._dedup(items)
        extra = []
        if pg == 1:
            extra += self._yl_map(self._data_list(self._call("/post/post_search", {"keyword": key, "page": 1, "page_size": 8})), "g")
            extra += self._yl_map(self._data_list(self._call("/comic/comic_search", {"keyword": key, "page": 1, "page_size": 8})), "c")
            extra += self._yl_map(self._data_list(self._call("/novel/novel_search", {"keyword": key, "page": 1, "page_size": 8})), "n")
        seen = {x["vod_id"] for x in vl}
        for x in extra:
            if x["vod_id"] not in seen:
                seen.add(x["vod_id"])
                vl.append(x)
        return {"list": vl, "page": pg, "pagecount": pg + 1 if len(vl) >= 8 else pg, "limit": 10, "total": (pg + 1) * 10}

    def _chap_id(self, ch):
        return str(ch.get("chapter_id") or ch.get("id") or "")

    def _chap_name(self, ch, i, unit="话"):
        return str(ch.get("title") or ch.get("name") or ch.get("chapter_title") or ("第%s%s" % (ch.get("chapter_nums") or ch.get("num") or i, unit)))

    def _play_chaps(self, chapters, prefix, oid, unit="话"):
        urls = []
        for i, ch in enumerate(chapters or [], 1):
            if not isinstance(ch, dict):
                continue
            cid = self._chap_id(ch)
            if not cid:
                continue
            urls.append("%s$%s_%s_%s" % (self._chap_name(ch, i, unit), prefix, oid, cid))
        return "#".join(urls)

    def _yl_detail_gossip(self, pid):
        r = self._call("/post/post_info", {"post_id": pid, "uid": self.uid})
        d = r.get("data") or {}
        info = d.get("post_info") or {}
        if not info:
            return {"list": []}
        imgs = self._as_list(info.get("imgs"))
        videos = self._as_list(info.get("video_url"))
        urls = []
        if videos:
            urls = ["播放%s$%s" % (i + 1 if len(videos) > 1 else "", v) for i, v in enumerate(videos)]
        if imgs:
            urls.append("图集$%s" % self._pics(imgs))
        if not urls:
            urls = ["播放$g_%s" % pid]
        tags = info.get("tags")
        if isinstance(tags, list):
            tags = ",".join(str(t.get("name") or t) for t in tags)
        vod = {"vod_id": "g_%s" % pid, "vod_name": str(info.get("title") or ""), "vod_pic": self._img(self._pic_raw(info) or (imgs[0] if imgs else "")),
               "type_name": "黑料", "vod_remarks": str(info.get("create_time") or ""),
               "vod_year": "", "vod_area": "", "vod_actor": "", "vod_director": "",
               "vod_content": str(info.get("desc") or info.get("content") or tags or ""),
               "vod_play_from": "黑料", "vod_play_url": "#".join(urls)}
        return {"list": [vod]}

    def _yl_detail_comic(self, cid):
        r = self._call("/comic/comic_info", {"comic_id": cid, "uid": self.uid})
        d = r.get("data") or {}
        info = d.get("comic_info") or {}
        chaps = d.get("chapter_list") or []
        if not info and not chaps:
            return {"list": []}
        play = self._play_chaps(chaps, "cch", cid, "话")
        vod = {"vod_id": "c_%s" % cid, "vod_name": str(info.get("title") or ""), "vod_pic": self._img(self._pic_raw(info)),
               "type_name": str(info.get("cate_name") or "漫画"), "vod_remarks": str(info.get("num") or ""),
               "vod_year": "", "vod_area": "", "vod_actor": "", "vod_director": "",
               "vod_content": str(info.get("desc") or info.get("content") or ""),
               "vod_play_from": "漫画", "vod_play_url": play or ("阅读$cch_%s_" % cid),
               "vod_tag": "image"}
        return {"list": [vod]}

    def _yl_detail_book(self, nid, radio=False):
        payload = {"novel_id": nid, "uid": self.uid}
        if radio:
            payload["type"] = 2
        r = self._call("/novel/novel_info", payload)
        d = r.get("data") or {}
        info = d.get("novel_info") or {}
        chaps = d.get("chapter_list") or []
        if not info and not chaps:
            return {"list": []}
        kind, name, unit, prefix = ("r", "电台", "集", "rch") if radio else ("n", "小说", "章", "nch")
        play = self._play_chaps(chaps, prefix, nid, unit)
        vod = {"vod_id": "%s_%s" % (kind, nid), "vod_name": str(info.get("title") or ""), "vod_pic": self._img(self._pic_raw(info)),
               "type_name": str(info.get("cate_name") or name), "vod_remarks": str(info.get("num") or ""),
               "vod_year": "", "vod_area": "", "vod_actor": "", "vod_director": "",
               "vod_content": str(info.get("desc") or info.get("content") or ""),
               "vod_play_from": name, "vod_play_url": play or ("阅读$%s_%s_" % (prefix, nid))}
        if not radio:
            vod["vod_tag"] = "text"
        return {"list": [vod]}

    def _yl_detail_live(self, vid):
        r = self._call("/live/live_info", {"video_id": vid, "uid": self.uid, "new_live": 1})
        d = r.get("data") or {}
        vi = d.get("video_info") or {}
        url = str(vi.get("url") or "")
        if not url:
            return {"list": []}
        on = vi.get("online_number")
        vod = {"vod_id": "l_%s" % vid, "vod_name": str(vi.get("author") or "直播"),
               "vod_pic": self._img(str(vi.get("img") or vi.get("author_img") or "")),
               "type_name": "直播", "vod_remarks": ("%s人在线" % self._num(on)) if on else "",
               "vod_year": "", "vod_area": "", "vod_actor": "", "vod_director": "",
               "vod_content": str(vi.get("author") or ""),
               "vod_play_from": "直播", "vod_play_url": "播放$" + url}
        return {"list": [vod]}

    def detailContent(self, ids):
        vid = str(ids[0]) if ids else ""
        if vid.startswith("z_"):
            raw = vid[2:]
            pic = ""
            if "::" in raw:
                raw, pic = raw.split("::", 1)
                pic = urllib.parse.unquote(pic)
            levels = self._hls_levels(urllib.parse.unquote(raw))
            froms = [n for n, _u in levels]
            urls = ["播放$" + u for _n, u in levels]
            vod = {"vod_id": vid, "vod_name": "直播", "vod_pic": self._img(pic),
                   "type_name": "直播", "vod_remarks": "",
                   "vod_year": "", "vod_area": "", "vod_actor": "", "vod_director": "",
                   "vod_content": "直播源",
                   "vod_play_from": "$$$".join(froms) or "直播",
                   "vod_play_url": "$$$".join(urls)}
            return {"list": [vod]}
        if vid.startswith("l_"):
            return self._yl_detail_live(vid[2:])
        if vid.startswith("g_"):
            return self._yl_detail_gossip(vid[2:])
        if vid.startswith("c_"):
            return self._yl_detail_comic(vid[2:])
        if vid.startswith("n_"):
            return self._yl_detail_book(vid[2:], False)
        if vid.startswith("r_"):
            return self._yl_detail_book(vid[2:], True)
        vi = {}
        for path in ("/video/video_info", "/video/video_info_v3"):
            r = self._call(path, {"video_id": vid, "uid": self.uid, "is_h5": 1})
            if r.get("code") == 1:
                cand = (r.get("data") or {}).get("video_info") or {}
                if cand.get("url") or cand.get("video_line"):
                    vi = cand
                    break
        if not vi:
            return {"list": []}
        lines = [x for x in (vi.get("video_line") or []) if x.get("url")]
        if not lines and vi.get("url"):
            lines = [{"name": "线路1", "url": vi["url"]}]
        froms = [str(l.get("name") or ("线路%d" % (i + 1))) for i, l in enumerate(lines)]
        urls = ["播放$" + str(l["url"]) for l in lines]
        tags = vi.get("tags")
        if isinstance(tags, list):
            tags = ",".join(str(t.get("name") or "") for t in tags if isinstance(t, dict))
        c2 = vi.get("cate2") or {}
        vod = {"vod_id": vid, "vod_name": str(vi.get("title") or ""), "vod_pic": self._img(vi.get("img")),
               "type_name": str(c2.get("name") or (tags or "")), "vod_remarks": str(vi.get("video_time") or ""),
               "vod_year": "", "vod_area": "", "vod_actor": "", "vod_director": "",
               "vod_content": "播放 %s ｜ 时长 %s ｜ %s" % (self._num(vi.get("play_num") or 0), vi.get("video_time") or "", tags or ""),
               "vod_play_from": "$$$".join(froms) or "线路1", "vod_play_url": "$$$".join(urls)}
        return {"list": [vod]}

    def _fetch_text(self, url, headers=None, timeout=20):
        u = str(url or "").strip()
        if not u.startswith("http"):
            return ""
        h = {"User-Agent": self.UA, "Referer": self.ORIGIN + "/"}
        if headers:
            h.update(headers)
        try:
            if requests:
                return requests.get(u, headers=h, timeout=timeout).text
            return urllib.request.urlopen(urllib.request.Request(u, headers=h), timeout=timeout).read().decode("utf-8", "ignore")
        except Exception:
            return ""

    def _hdr(self):
        return json.dumps({"User-Agent": self.UA, "Referer": self.ORIGIN + "/"})

    def _play_comic(self, chid):
        r = self._call("/comic/comic_chapter_info", {"chapter_id": chid, "uid": self.uid, "is_h5": 1})
        d = r.get("data") or {}
        imgs = self._as_list(d.get("imgs"))
        url = str(d.get("url") or ((d.get("player") or {}).get("url") if isinstance(d.get("player"), dict) else "") or "")
        pics = self._pics(imgs, url)
        if pics:
            return {"parse": 0, "url": pics, "header": ""}
        if url:
            return {"parse": 0, "url": url, "header": self._hdr()}
        return {"parse": 0, "url": "", "header": ""}

    def _novel_text(self, chid, radio=False):
        payload = {"chapter_id": chid, "uid": self.uid, "is_h5": 1}
        if radio:
            payload["type"] = 2
        r = self._call("/novel/novel_chapter_info", payload)
        d = r.get("data") or {}
        player = d.get("player") if isinstance(d.get("player"), dict) else {}
        url = str(d.get("url") or player.get("url") or "")
        if radio:
            return "", url
        text = str(d.get("content") or "")
        if not text and url and not self.isVideoFormat(url):
            text = self._dec_txt(self._fetch_text(url))
        elif text:
            text = self._dec_txt(text)
        return text, url

    def _play_novel(self, chid, radio=False, title=""):
        text, url = self._novel_text(chid, radio)
        if radio:
            return {"parse": 0, "url": url, "header": self._hdr()}
        if text:
            payload = json.dumps({"title": title or "阅读", "content": text}, ensure_ascii=False)
            return {"parse": 0, "url": "novel://" + payload, "header": ""}
        if url:
            return {"parse": 0, "url": url, "header": self._hdr()}
        return {"parse": 0, "url": "", "header": ""}

    def playerContent(self, flag, id, vipFlags):
        s = str(id or "")
        if s.startswith(("novel://", "pics://")):
            return {"parse": 0, "url": s, "header": ""}
        if s.startswith("cch_"):
            parts = s.split("_", 2)
            return self._play_comic(parts[2] if len(parts) > 2 else "")
        if s.startswith("nch_"):
            parts = s.split("_", 2)
            return self._play_novel(parts[2] if len(parts) > 2 else "", False, str(flag or "阅读"))
        if s.startswith("rch_"):
            parts = s.split("_", 2)
            return self._play_novel(parts[2] if len(parts) > 2 else "", True)
        if s.startswith("g_"):
            r = self._call("/post/post_info", {"post_id": s[2:], "uid": self.uid})
            info = (r.get("data") or {}).get("post_info") or {}
            videos = self._as_list(info.get("video_url"))
            if videos:
                return {"parse": 0, "playUrl": "", "url": self._full(videos[0]), "header": self._hdr()}
            imgs = self._as_list(info.get("imgs"))
            pics = self._pics(imgs)
            if pics:
                return {"parse": 0, "url": pics, "header": ""}
        if s.startswith("http") and ("growcdnssedge.com" in s or "media-hls." in s):
            return {"parse": 0, "url": self._pick_hls(s), "header": self._hdr_ext()}
        return {"parse": 0, "playUrl": "", "url": self._full(s), "header": self._hdr()}

    def localProxy(self, param):
        kv = param if isinstance(param, dict) else {}
        if not kv and isinstance(param, str) and param:
            try:
                for seg in str(param).split("&"):
                    if "=" in seg:
                        k, v = seg.split("=", 1)
                        kv[k] = v
            except Exception:
                kv = {}
        act = str(kv.get("yl") or kv.get("type") or "")
        if act in ("img", "ylimg"):
            u = urllib.parse.unquote(str(kv.get("url") or kv.get("u") or ""))
            raw = self._fetch_bytes(u)
            img, mt = self._dec_img(raw)
            return [200, mt, img]
        return [200, "text/plain", ""]
