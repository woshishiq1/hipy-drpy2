# -*- coding: utf-8 -*-
import re
import os
import json
import time
import gzip
import zlib
import ssl
import urllib.request
import urllib.parse
import urllib.error

try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider(object):
        def __init__(self):
            self.extend = {}


JUVE = ("萝莉", "幼女", "童", "未成年", "teen", "loli", "schoolgirl", "孩童",
        "稚子", "玉蕊", "豆蔻", "小学生", "初中生", "幼齿", "童颜", "一年级", "初二", "初三")

CATS = (
    ("20", "国产自拍"), ("21", "制服丝袜"), ("22", "强奸乱伦"), ("23", "教师学生"),
    ("24", "素人系列"), ("25", "人妻熟女"), ("26", "日韩无码"), ("27", "日韩有码"),
    ("28", "中文字幕"), ("29", "欧美风情"), ("30", "经典伦理"), ("31", "卡通动漫"),
)

SITE = "https://imnttc.bxm7.monster"
PUB = "https://amp.abc90.com/217/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"


def _juv(text):
    if not text:
        return False
    low = text.lower()
    for k in JUVE:
        if k.lower() in low:
            return True
    return False


class Spider(BaseSpider):

    def __init__(self):
        super(Spider, self).__init__()
        self.extend = {}
        self.base = SITE
        self.baseUrl = SITE
        self.HOST = SITE
        self.header = {"User-Agent": UA,
                       "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                       "Accept-Language": "zh-CN,zh;q=0.9",
                       "Accept-Encoding": "gzip, deflate"}
        self.classList = [{"type_id": i, "type_name": n} for i, n in CATS]
        self.filters = {i: {} for i, _ in CATS}
        self._pics = {}
        self._pc = {}
        self._spc = {}
        self._dead = set()
        self._heal_ts = 0.0
        self._hosts = set()
        self.multi_host = True
        self.max_lines = 3
        self.session = None
        self.ctx = ssl.create_default_context()
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE
        try:
            self.ctx.set_ciphers("DEFAULT@SECLEVEL=1")
        except Exception:
            pass
        self.img_proxy = False

    def init(self, extend=""):
        cfg = {}
        if isinstance(extend, dict):
            cfg = extend
        elif isinstance(extend, str) and extend.strip():
            try:
                cfg = json.loads(extend)
            except Exception:
                cfg = {}
        self.extend = cfg
        if cfg.get("url"):
            self._setbase(str(cfg["url"]).rstrip("/"))
        if cfg.get("imgProxy") or cfg.get("img_proxy"):
            self.img_proxy = True
        if cfg.get("multiHost", 1):
            self.multi_host = True
        try:
            self.max_lines = max(1, min(6, int(cfg.get("maxLines", 3))))
        except Exception:
            self.max_lines = 3
        self._load_disk()

    def _setbase(self, b):
        self.base = b
        self.baseUrl = b
        self.HOST = b

    def _cache_path(self):
        for d in ("/data/data/tv.emu/files", "/storage/emulated/0", os.path.expanduser("~"), "/tmp"):
            try:
                if os.path.isdir(d) and os.access(d, os.W_OK):
                    return os.path.join(d, ".bxm_cache.json")
            except Exception:
                continue
        return "/tmp/.bxm_cache.json"

    def _load_disk(self):
        try:
            with open(self._cache_path(), "r") as f:
                j = json.load(f)
            if j.get("base") and j.get("ts", 0) > time.time() - 86400:
                self._setbase(j["base"])
            if isinstance(j.get("pc"), dict):
                self._pc.update(j["pc"])
            if isinstance(j.get("spc"), dict):
                self._spc.update({str(k): int(v) for k, v in j["spc"].items()})
            if isinstance(j.get("pics"), dict):
                for k, v in list(j["pics"].items())[-1500:]:
                    self._pics[k] = v
        except Exception:
            pass

    def _save_disk(self):
        try:
            pics = dict(list(self._pics.items())[-1500:])
            with open(self._cache_path(), "w") as f:
                json.dump({"base": self.base, "ts": time.time(), "pc": self._pc, "spc": self._spc, "pics": pics}, f)
        except Exception:
            pass

    def _http(self, url, ref=None, to=15):
        hd = dict(self.header)
        hd["Referer"] = ref if ref else (self.base + "/")
        req = urllib.request.Request(url, headers=hd)
        try:
            resp = urllib.request.urlopen(req, timeout=to, context=self.ctx)
            raw = resp.read()
            enc = (resp.headers.get("Content-Encoding") or "").lower()
            if resp.getcode() != 200:
                return ""
        except urllib.error.HTTPError as e:
            if e.code != 404:
                try:
                    raw = e.read()
                except Exception:
                    return ""
            else:
                return ""
        except Exception:
            return ""
        if not raw:
            return ""
        if raw[:2] == b"\x1f\x8b" or "gzip" in enc:
            try:
                raw = gzip.decompress(raw)
            except Exception:
                try:
                    raw = zlib.decompress(raw, 47)
                except Exception:
                    pass
        elif "deflate" in enc:
            try:
                raw = zlib.decompress(raw)
            except Exception:
                try:
                    raw = zlib.decompress(raw, -zlib.MAX_WBITS)
                except Exception:
                    pass
        return raw.decode("utf-8", "replace")

    def _probe(self, b, to=10):
        if not b.startswith("http") or b in self._dead:
            return False
        html = self._http(b + "/vodtype/20.html", ref=b + "/", to=to)
        return len(self._cards(html)[0]) >= 10

    def _heal(self):
        self._dead.add(self.base)
        pub = self._http(PUB, ref=self.base + "/", to=12)
        cands = []
        for m in re.findall(r'https?://[A-Za-z0-9._-]+(?:/[A-Za-z0-9_-]{1,12})?/?', pub or ""):
            b = re.sub(r'/(bxm|217|vip|av|hm|cc)/?$', '', m).rstrip("/")
            if not b or b in cands or b in self._dead:
                continue
            if "abc90" in b or "cctv" in b or "ccb" in b:
                continue
            cands.append(b)
        if SITE not in cands:
            cands.insert(0, SITE)
        for b in cands[:4]:
            if self._probe(b):
                self._setbase(b)
                self._heal_ts = time.time()
                self._save_disk()
                return True
        return False

    def _get(self, path, ref=None, to=15):
        html = self._http(self.base + path, ref=ref, to=to)
        if html:
            return html
        if time.time() - self._heal_ts > 300:
            if self._heal():
                return self._http(self.base + path, ref=ref, to=to)
        elif self.base != SITE and self._probe(SITE):
            self._setbase(SITE)
            return self._http(self.base + path, ref=ref, to=to)
        return ""

    def _clean(self, t):
        if not t:
            return ""
        t = re.sub(r"<[^>]+>", "", t)
        t = (t.replace("&quot;", '"').replace("&amp;", "&").replace("&lt;", "<")
              .replace("&gt;", ">").replace("&#39;", "'").replace("&nbsp;", " "))
        t = re.sub(r"\s+", " ", t)
        return t.strip()

    def _pic(self, url):
        if not url:
            return ""
        u = url.strip()
        if u.startswith("//"):
            u = "https:" + u
        if not u.startswith("http"):
            return ""
        if self.img_proxy:
            try:
                return self.getProxyUrl() + "?do=img&url=" + urllib.parse.quote(u)
            except Exception:
                return u
        return u

    def _alts(self, u, n):
        if not self.multi_host or n <= 0:
            return []
        mh = re.match(r"https?://([^/]+)(/.+)", u)
        if not mh:
            return []
        h0, path = mh.group(1), mh.group(2)
        out = []
        for h in sorted(self._hosts):
            if h == h0:
                continue
            c = "https://%s%s" % (h, path)
            if c not in out:
                out.append(c)
            if len(out) >= n:
                break
        return out

    def _cut(self, html):
        for mk in ('class="prev pagegbk"', "猜你喜欢", "相关推荐", "热门推荐", "尾页", "<footer"):
            i = html.find(mk)
            if i > 2000:
                html = html[:i]
        return html

    def _cards(self, html):
        if not html:
            return [], {}
        body = self._cut(html)
        vids, info = [], {}
        for tag in re.findall(r'<a\s+class="video-pic[^"]*"[^>]*>', body):
            mv = re.search(r'href="/(\d+)\.html"', tag)
            if not mv:
                continue
            vid = mv.group(1)
            mp = re.search(r'(?:data-original|data-src|src)="(https?://[^"]+)"', tag)
            mt = re.search(r'title="([^"]*)"', tag)
            pic = mp.group(1) if mp else ""
            title = self._clean(mt.group(1)) if mt else ""
            if vid not in info:
                vids.append(vid)
                info[vid] = {"pic": "", "name": "", "time": ""}
            if pic:
                info[vid]["pic"] = pic
                mh = re.match(r"https?://([^/]+)", pic)
                if mh:
                    self._hosts.add(mh.group(1))
            if title and not info[vid]["name"]:
                info[vid]["name"] = title
        for mt in re.finditer(r'<h\d[^>]*>\s*<a href="/(\d+)\.html"[^>]*title="([^"]{3,})"[^>]*>', body):
            vid, title = mt.group(1), self._clean(mt.group(2))
            if vid in info and not info[vid]["name"]:
                info[vid]["name"] = title
        for mt in re.finditer(r'<a href="/(\d+)\.html"[^>]*title="([^"]{3,})"[^>]*>\s*[^<]{3,}<', body):
            vid, title = mt.group(1), self._clean(mt.group(2))
            if vid in info and not info[vid]["name"]:
                info[vid]["name"] = title
        for mt in re.finditer(r'href="/(\d+)\.html"(?:(?!</li>).){0,700}?class="subtitle text-time[^"]*">([^<]+)<', body, re.S):
            vid, tm = mt.group(1), mt.group(2).strip()
            if vid in info and not info[vid]["time"]:
                info[vid]["time"] = tm
        return vids, info

    def _build(self, vids, info, seen=None):
        out = []
        for vid in vids:
            d = info.get(vid) or {}
            name = d.get("name", "")
            pic = d.get("pic", "")
            if not name and not pic:
                continue
            if name and _juv(name):
                continue
            if not name:
                continue
            if seen is not None:
                if vid in seen:
                    continue
                seen.add(vid)
            pic = self._pic(pic)
            if pic:
                self._pics[vid] = pic
                if len(self._pics) > 3000:
                    self._pics.pop(next(iter(self._pics)))
            tm = d.get("time", "")
            out.append({"vod_id": vid, "vod_name": name, "vod_pic": pic,
                        "vod_remarks": tm})
        return out

    def _tail(self, html, pattern, pg):
        nums = [int(x) for x in re.findall(pattern, html or "") if x.isdigit()]
        if not nums:
            return pg
        m = max(nums)
        return m if m >= pg else pg

    def homeContent(self, filter=None):
        return {"class": self.classList, "filters": self.filters}

    def homeVideoContent(self):
        return {"list": []}

    def categoryContent(self, tid, pg, filter=None, extend=None):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        tid = re.sub(r"[^0-9]", "", str(tid))
        path = "/vodtype/%s.html" % tid if pg <= 1 else "/vodtype/%s-%d.html" % (tid, pg)
        html = self._get(path)
        vids, info = self._cards(html)
        lst = self._build(vids, info)
        pc = self._tail(html, r'/vodtype/%s-(\d+)\.html' % re.escape(tid), pg)
        if not lst:
            pc = pg
        if pc > 1:
            old = self._pc.get(tid, 0)
            if pc > old:
                self._pc[tid] = pc
                self._save_disk()
        return {"page": pg, "pagecount": max(pc, pg), "limit": 72,
                "total": max(pc, pg) * 72, "list": lst}

    def detailContent(self, ids):
        if isinstance(ids, str):
            ids = [ids]
        if isinstance(ids, dict):
            ids = [ids.get("ids") or ids.get("id")]
        out = []
        for raw in ids or []:
            vid = re.sub(r"[^0-9]", "", str(raw))
            if not vid:
                continue
            html = self._get("/%s.html" % vid)
            if not html or len(html) < 2000:
                continue
            name = ""
            tm = re.search(r"<title>(.*?)</title>", html, re.S)
            if tm:
                name = self._clean(tm.group(1))
                name = re.sub(r"\s*[-–—]\s*鲍鲜膜\s*$", "", name)
                name = re.sub(r"^(正在播放|在线播放)[:：]\s*", "", name)
            if not name or _juv(name):
                continue
            plays = []
            seen = set()
            for u in re.findall(r"(?:const\s+)?rawUrl\s*=\s*['\"]([^'\"]+)['\"]", html):
                u = u.strip()
                if u.startswith("http") and u not in seen and not _juv(u):
                    seen.add(u)
                    plays.append(u)
            if not plays:
                for u in re.findall(r"['\"](https?://[^'\"<>\s]+\.m3u8[^'\"<>\s]*)['\"]", html):
                    if u not in seen and not _juv(u):
                        seen.add(u)
                        plays.append(u)
            if not plays:
                continue
            pic = self._pics.get(vid, "")
            if not pic:
                pm = re.search(r'property="og:image"[^>]+content="([^"]+)"', html)
                if pm:
                    pic = self._pic(pm.group(1))
            names, urls = [], []
            for i, u in enumerate(plays):
                mh = re.match(r"https?://([^/]+)", u)
                if mh:
                    self._hosts.add(mh.group(1))
                tag = "正片" if len(plays) == 1 else "第%d集" % (i + 1)
                names.append("鲍鲜膜")
                urls.append(tag + "$" + u)
                if self.multi_host and len(plays) == 1:
                    for alt in self._alts(u, self.max_lines - len(urls)):
                        names.append("鲍鲜膜线路%d" % len(names))
                        urls.append(tag + "$" + alt)
                if len(urls) >= self.max_lines:
                    break
            out.append({
                "vod_id": vid,
                "vod_name": name,
                "vod_pic": pic,
                "vod_content": name,
                "vod_remarks": "",
                "vod_actor": "",
                "vod_director": "",
                "vod_year": "",
                "vod_area": "",
                "vod_tag": "",
                "vod_play_from": "$$$".join(names),
                "vod_play_url": "$$$".join(urls),
            })
        return {"list": out}

    def searchContent(self, key, quick=None, pg=None):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        kw = (key or "").strip()
        if not kw:
            return {"page": 1, "pagecount": 1, "limit": 0, "total": 0, "list": []}
        ekw = urllib.parse.quote(kw)
        path = "/s/%s/index.html" % ekw if pg <= 1 else "/s/%s/page/%d.html" % (ekw, pg)
        html = self._get(path, ref=self.base + "/")
        if not html and pg > 1:
            html = self._get("/s/index.html?wd=%s&page=%d" % (ekw, pg), ref=self.base + "/")
        vids, info = self._cards(html)
        seen = set()
        lst = self._build(vids, info, seen)
        pc = self._tail(html, r'/s/%s/page/(\d+)\.html' % re.escape(ekw), pg)
        if not lst:
            pc = pg
        k = "s:" + kw
        cached = self._spc.get(k, 0)
        if cached and pc < cached:
            pc = cached
        if pc > cached:
            self._spc[k] = pc
        return {"page": pg, "pagecount": max(pc, pg), "limit": 72,
                "total": max(pc, pg) * 72, "list": lst}

    def playerContent(self, flag, id, vipFlags=None):
        url = str(id or "").strip()
        if url.startswith("http"):
            return {"parse": 0, "jx": 0, "playUrl": "", "url": url,
                    "header": json.dumps({"User-Agent": UA,
                                          "Referer": self.base + "/",
                                          "Origin": self.base})}
        return {"parse": 1, "jx": 0, "url": url, "header": ""}

    def isVideoFormat(self, url):
        u = str(url or "").lower()
        return any(e in u for e in (".m3u8", ".mp4", ".flv", ".ts"))

    def manualVideoCheck(self):
        return False

    def getName(self):
        return "鲍鲜膜"

    def getApp(self):
        return "鲍鲜膜"

    def isManualVideo(self):
        return False

    def getDependence(self):
        return ""

    def destroy(self):
        if self.session:
            try:
                self.session.close()
            except Exception:
                pass
            self.session = None

    def localProxy(self, param):
        if isinstance(param, dict):
            do = param.get("do", "")
            url = param.get("url", "")
        else:
            q = urllib.parse.parse_qs(str(param or "").lstrip("?"))
            do = (q.get("do") or [""])[0]
            url = urllib.parse.unquote((q.get("url") or [""])[0])
        if not url.startswith("http"):
            return [404, "text/plain", b""]
        try:
            hd = dict(self.header)
            hd["Referer"] = self.base + "/"
            hd.pop("Accept-Encoding", None)
            data, ctype, ok = self._fetch_alt(url, hd)
            if not ok:
                return [404, "text/plain", b""]
            if ".m3u8" in url and ".m3u8" not in (ctype or ""):
                ctype = "application/vnd.apple.mpegurl"
            if not ctype:
                ctype = "image/jpeg" if "m3u8" not in url else "application/vnd.apple.mpegurl"
            return [200, ctype, data]
        except Exception:
            return [404, "text/plain", b""]

    def _fetch_alt(self, url, hd):
        for u in [url] + self._alts(url, min(3, len(self._hosts))):
            try:
                req = urllib.request.Request(u, headers=dict(hd))
                resp = urllib.request.urlopen(req, timeout=18, context=self.ctx)
                return resp.read(), (resp.headers.get("Content-Type") or ""), True
            except Exception:
                continue
        return b"", "", False
