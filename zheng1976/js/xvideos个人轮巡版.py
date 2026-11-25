# -*- coding: utf-8 -*-
import json
import re
import ssl
import sys
import time
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, sys.path[0] + "/../")
try:
    from base.spider import Spider as BaseSpider
except Exception:
    BaseSpider = object


class Spider(BaseSpider):

    UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    UA2 = "Mozilla/5.0 (Linux; Android 13; SM-S9010) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36"

    STATIC_HOSTS = [
        "https://www.xvideos.com",
        "https://fr.xvideos.com",
        "https://it.xvideos.com",
        "https://de.xvideos.com",
        "https://www.xvideos.es",
        "https://www.xvideos-india.com",
        "https://www.xv-ru.com",
        "https://www.xvideos-ar.com",
        "https://xxxx.xvideos.com",
    ]

    POOL_TTL = 1800

    def init(self, extend=""):
        self._host = ""
        self._host_ts = 0.0
        self._host_via_proxy = False
        self._bad_hosts = set()

    def getName(self):
        return "Xvideos"

    def isVideoFormat(self, url):
        u = str(url or "").lower()
        return any(x in u for x in (".m3u8", ".mp4", ".flv", ".m4v", ".mov", ".ts"))

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def homeVideoContent(self):
        return {"list": self._videos(self._html("/"))}

    def _ctx(self):
        c = ssl.create_default_context()
        c.check_hostname = False
        c.verify_mode = ssl.CERT_NONE
        return c

    def _req_get(self, url, timeout=15, ua=0, direct=True, referer=None):
        h = {
            "User-Agent": self.UA if ua % 2 == 0 else self.UA2,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": referer or (self._host + "/" if self._host else "https://www.xvideos.com/"),
        }
        try:
            h["Referer"] = h["Referer"] if h["Referer"].startswith("http") else "https://www.xvideos.com/"
        except Exception:
            pass
        req = urllib.request.Request(url, headers=h)
        hs = [urllib.request.HTTPSHandler(context=self._ctx())]
        if direct:
            hs.append(urllib.request.ProxyHandler({}))
        opener = urllib.request.build_opener(*hs)
        return opener.open(req, timeout=timeout).read().decode("utf-8", errors="ignore")

    def _get(self, url, timeout=15, retries=3, direct=True, referer=None):
        for i in range(max(1, retries)):
            try:
                d = self._req_get(url, timeout=timeout, ua=i, direct=direct, referer=referer)
                if d and len(d) > 800:
                    return d
            except Exception:
                time.sleep(0.8 if i == 0 else 1.6)
        return ""

    def _alive(self, html):
        if not html:
            return False
        return html.count("thumb-block") >= 5 or html.count("/video.") >= 5

    def _extract_hosts(self):
        found = []
        for seed in self.STATIC_HOSTS[:3]:
            try:
                h = self._req_get(seed + "/", timeout=10, direct=True)
            except Exception:
                continue
            if not h:
                continue
            for d in re.findall(r'href="https?://([a-z0-9.-]+\.xvideos[a-z0-9.-]*\.[a-z]{2,})/"', h):
                u = "https://" + d
                if u not in found and u not in self._bad_hosts:
                    found.append(u)
            break
        for s in self.STATIC_HOSTS:
            if s not in found and s not in self._bad_hosts:
                found.append(s)
        return found[:12]

    def _probe(self):
        self._host_ts = time.time()
        cands = self._extract_hosts()
        try:
            with ThreadPoolExecutor(max_workers=min(8, len(cands))) as ex:
                futs = {}
                for b in cands:
                    futs[ex.submit(self._get, b + "/", 10, 1, True)] = b
                for f in as_completed(futs, timeout=25):
                    try:
                        body = f.result()
                    except Exception:
                        body = ""
                    if self._alive(body):
                        self._host = futs[f]
                        self._host_via_proxy = False
                        return self._host
                    else:
                        self._bad_hosts.add(futs[f])
        except Exception:
            pass
        try:
            with ThreadPoolExecutor(max_workers=min(8, len(cands))) as ex:
                futs = {}
                for b in cands:
                    if b in self._bad_hosts:
                        continue
                    futs[ex.submit(self._get, b + "/", 10, 1, False)] = b
                for f in as_completed(futs, timeout=25):
                    try:
                        body = f.result()
                    except Exception:
                        body = ""
                    if self._alive(body):
                        self._host = futs[f]
                        self._host_via_proxy = True
                        return self._host
        except Exception:
            pass
        self._host = self.STATIC_HOSTS[0]
        self._host_via_proxy = False
        return self._host

    def _pool(self):
        if self._host and (time.time() - self._host_ts) < self.POOL_TTL:
            return self._host
        return self._probe()

    def _dead(self):
        self._host = ""
        self._host_ts = 0.0

    def _html(self, path, retries=3):
        for attempt in range(2):
            base = self._pool()
            url = base + path if path.startswith("/") else path
            direct = not self._host_via_proxy
            h = self._get(url, 15, retries, direct=direct)
            if h and self._alive(h):
                return h
            if h and ("/video." in h or "setVideo" in h):
                return h
            if attempt == 0:
                self._bad_hosts.add(base)
                self._dead()
        return ""

    CATEGORIES = [
        ("all", "全部", ""),
        ("amateur", "素人实拍", "/c/Amateur-65"),
        ("asian", "亚洲", "/c/Asian_Woman-32"),
        ("latina", "拉丁", "/c/Latina-16"),
        ("black", "黑人", "/c/Black_Woman-30"),
        ("indian", "印度", "/c/Indian-89"),
        ("arab", "阿拉伯", "/c/Arab-159"),
        ("milf", "少妇", "/c/Milf-19"),
        ("mature", "熟女", "/c/Mature-38"),
        ("teen", "年轻", "/c/Teen-13"),
        ("lesbian", "女女", "/c/Lesbian-26"),
        ("bigtits", "波大", "/c/Big_Tits-23"),
        ("bigass", "翘臀", "/c/Big_Ass-24"),
        ("bbw", "肥腰", "/c/bbw-51"),
        ("ass", "臀部", "/c/Ass-14"),
        ("bigcock", "巨大", "/c/Big_Cock-34"),
        ("blonde", "金发", "/c/Blonde-20"),
        ("brunette", "黑发", "/c/Brunette-25"),
        ("redhead", "红发", "/c/Redhead-31"),
        ("anal", "后庭", "/c/Anal-12"),
        ("blowjob", "口活", "/c/Blowjob-15"),
        ("creampie", "内射", "/c/Creampie-40"),
        ("cumshot", "射颜", "/c/Cumshot-18"),
        ("squirting", "喷涌", "/c/Squirting-56"),
        ("gapes", "深喉", "/c/Gapes-167"),
        ("fisting", "拳头", "/c/Fisting-165"),
        ("gangbang", "群战", "/c/Gangbang-69"),
        ("interracial", "混搭", "/c/Interracial-27"),
        ("bisexual", "双性", "/c/Bi_Sexual-62"),
        ("cuckold", "绿帽", "/c/Cuckold-237"),
        ("femdom", "女王", "/c/Femdom-235"),
        ("solo", "自助", "/c/Solo_and_Masturbation-33"),
        ("oiled", "油光", "/c/Oiled-22"),
        ("stockings", "长袜", "/c/Stockings-28"),
        ("lingerie", "贴身", "/c/Lingerie-83"),
        ("family", "家庭", "/c/Fucked_Up_Family-81"),
        ("camporn", " cam直播", "/c/Cam_Porn-58"),
        ("asmr", "ASMR", "/c/ASMR-229"),
        ("ai", "AI生成", "/c/AI-239"),
    ]

    FILTERS = [
        {"key": "s", "name": "排序", "init": "", "value": [
            {"n": "相关", "v": ""},
            {"n": "上传日期", "v": "uploaddate"},
            {"n": "高评分", "v": "rating"},
            {"n": "长度", "v": "length"},
            {"n": "观看量", "v": "views"},
        ]},
        {"key": "m", "name": "时间", "init": "", "value": [
            {"n": "全部", "v": ""},
            {"n": "近3天", "v": "today"},
            {"n": "本周", "v": "week"},
            {"n": "本月", "v": "month"},
            {"n": "近3月", "v": "3month"},
            {"n": "近6月", "v": "6month"},
        ]},
        {"key": "d", "name": "时长", "init": "", "value": [
            {"n": "不限", "v": ""},
            {"n": "1-3分钟", "v": "1-3min"},
            {"n": "3-10分钟", "v": "3-10min"},
            {"n": "10-20分钟", "v": "10-20min"},
            {"n": "20分钟以上", "v": "20min_more"},
        ]},
        {"key": "q", "name": "画质", "init": "", "value": [
            {"n": "不限", "v": ""},
            {"n": "HD", "v": "hd"},
            {"n": "1080P", "v": "1080P"},
        ]},
    ]

    def homeContent(self, filter):
        self._pool()
        result = {"class": [], "filters": {}}
        for cid, cname, path in self.CATEGORIES:
            result["class"].append({"type_id": cid, "type_name": cname})
            result["filters"][cid] = (list(self.FILTERS) if path else [])
        return result

    def _list_url(self, tid, pg, extend=None):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        if pg < 1:
            pg = 1
        ext = extend if isinstance(extend, dict) else {}
        slug = ""
        for cid, cname, path in self.CATEGORIES:
            if cid == str(tid):
                slug = path[3:] if path.startswith("/c/") else ""
                break
        if not slug and str(tid) in ("all", "", "0"):
            return "/new/%d" % (pg - 1) if pg > 1 else "/"
        segs = []
        for k in ("s", "m", "d", "q"):
            v = str(ext.get(k, "") or "")
            if v:
                segs.append("%s:%s" % (k, v))
        if not slug:
            kw = urllib.parse.quote(str(tid))
            return "/?k=" + kw + ("&p=%d" % (pg - 1) if pg > 1 else "")
        base = "/c/"
        if segs:
            base += "/".join(segs) + "/"
        return base + slug + ("/%d" % (pg - 1) if pg > 1 else "")

    def _blocks(self, html):
        if not html:
            return []
        i = html.find('id="content"')
        seg = html[i:] if i > 0 else html
        p = re.split(r'<div[^>]*class="[^"]*thumb-block[^"]*"', seg)
        return p[1:] if len(p) > 1 else []

    def _clean(self, s):
        if not s:
            return ""
        s = re.sub(r"<[^>]+>", "", str(s))
        for a, b in (("&amp;", "&"), ("&#039;", "'"), ("&#39;", "'"), ("&quot;", '"'),
                     ("&ndash;", "-"), ("&mdash;", "-"), ("&rsquo;", "'"), ("&nbsp;", " ")):
            s = s.replace(a, b)
        return re.sub(r"\s+", " ", s).strip()

    def _block_item(self, b):
        try:
            m = re.search(r'href="(/video\.[^"]+)"', b)
            if not m:
                return None
            href = m.group(1)
            mt = re.search(r'<a[^>]*title="([^"]*)"', b)
            if mt:
                name = self._clean(mt.group(1))
            else:
                mt2 = re.search(r'<p[^>]*class="title"[^>]*>.*?<a[^>]*>(.*?)</a>', b, re.S)
                name = self._clean(re.split(r"<span", mt2.group(1), 1)[0]) if mt2 else ""
            if not name:
                return None
            mp = re.search(r'data-src="(https?://[^"]+)"', b)
            if not mp:
                mp = re.search(r'src="(https?://[^"]+)"', b)
            pic = mp.group(1) if mp else ""
            md = re.search(r'class="duration"[^>]*>(.*?)</span>', b, re.S)
            dur = self._clean(md.group(1)) if md else ""
            mq = re.search(r'class="video-hd-mark"[^>]*>(.*?)</span>', b, re.S)
            qual = self._clean(mq.group(1)) if mq else ""
            mv = re.search(r'class="nb-views"[^>]*>(.*?)</', b, re.S)
            views = self._clean(mv.group(1)) if mv else ""
            rem = " ".join(x for x in (qual or dur, views + "次" if views else "") if x)
            return {"vod_id": href, "vod_name": name, "vod_pic": pic, "vod_remarks": rem}
        except Exception:
            return None

    def _videos(self, html):
        out, seen = [], set()
        for b in self._blocks(html):
            it = self._block_item(b)
            if it and it["vod_id"] not in seen:
                seen.add(it["vod_id"])
                out.append(it)
        return out

    def _last_page(self, html, cur):
        best = cur
        for n in re.findall(r'href="/c/[^"]*/(\d+)"', html or ""):
            try:
                v = int(n) + 1
                if v > best:
                    best = v
            except Exception:
                pass
        for n in re.findall(r'class="last-page"[^>]*>\s*(\d+)', html or ""):
            try:
                if int(n) > best:
                    best = int(n)
            except Exception:
                pass
        return best if best >= cur else cur + 1

    def categoryContent(self, tid, pg, filter, extend):
        tid = str(tid) if tid is not None else "all"
        try:
            pg = intval = int(pg)
        except Exception:
            pg = intval = 1
        html = self._html(self._list_url(tid, pg, extend))
        vods = self._videos(html)
        if not vods:
            self._dead()
            html = self._html(self._list_url(tid, pg, extend))
            vods = self._videos(html)
        if not vods:
            return {"list": [], "page": pg, "pagecount": pg, "limit": 0, "total": 0}
        return {"list": vods, "page": pg, "pagecount": self._last_page(html, pg), "limit": len(vods), "total": len(vods) * pg}

    def searchContent(self, key, quick, pg="1"):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        if pg < 1:
            pg = 1
        html = self._html("/?k=" + urllib.parse.quote(str(key)) + ("&p=%d" % (pg - 1) if pg > 1 else ""))
        vods = self._videos(html)
        if not vods and pg > 1:
            return {"list": [], "page": pg, "pagecount": pg, "limit": 0, "total": 0}
        return {"list": vods, "page": pg, "pagecount": self._last_page(html, pg), "limit": len(vods), "total": len(vods) * pg}

    def _hls_variants(self, master_url):
        out = []
        try:
            txt = self._req_get(master_url, timeout=12)
        except Exception:
            return out
        if "#EXTM3U" not in txt:
            return out
        base = master_url.rsplit("/", 1)[0] + "/"
        lines = txt.splitlines()
        i = 0
        while i < len(lines):
            ln = lines[i].strip()
            if ln.startswith("#EXT-X-STREAM-INF"):
                name = ""
                res = ""
                m = re.search(r'NAME="([^"]+)"', ln)
                if m:
                    name = m.group(1)
                m2 = re.search(r'RESOLUTION=(\d+)x(\d+)', ln)
                if m2:
                    res = m2.group(2) + "p"
                j = i + 1
                while j < len(lines) and not lines[j].strip():
                    j += 1
                if j < len(lines):
                    u = lines[j].strip()
                    if u and not u.startswith("#"):
                        full = u if u.startswith("http") else base + u
                        lbl = "HLS-" + (name or res or ("q%d" % (len(out) + 1)))
                        out.append((lbl, full))
                i = j + 1
            else:
                i += 1
        return out

    def detailContent(self, ids):
        vids = ids if isinstance(ids, (list, tuple)) else [ids]
        out = []
        for vid in vids:
            vid = str(vid)
            if vid.startswith("/video."):
                html = self._html(vid)
            elif vid.startswith("video."):
                html = self._html("/" + vid)
            else:
                html = self._html("/video." + vid)
            if not html:
                self._dead()
                html = self._html(vid if vid.startswith("/") else "/" + vid)
            if not html:
                continue
            tm = re.search(r"<title>(.*?)</title>", html, re.S)
            name = self._clean(tm.group(1)) if tm else ""
            name = re.sub(r"\s*[-|]\s*XVIDEOS.*$", "", name, flags=re.I)
            pm = re.search(r'og:image"\s+content="([^"]+)"', html)
            pic = pm.group(1) if pm else ""
            dm = re.search(r'name="description"\s+content="([^"]*)"', html)
            desc = self._clean(dm.group(1)) if dm else ""
            lines = []
            mh = re.search(r"setVideoHLS\(\s*'([^']+)'", html) or re.search(r'setVideoHLS\(\s*"([^"]+)"', html)
            if mh:
                mu = mh.group(1).replace("\\/", "/")
                for lbl, u in self._hls_variants(mu):
                    lines.append((lbl, u))
                if not any(l[0].startswith("HLS-") for l in lines):
                    lines.append(("HLS", mu))
            for fn in ("setVideoUrlHigh", "setVideoUrlLow"):
                mm = re.search(fn + r"\(\s*'([^']+)'", html) or re.search(fn + r'\(\s*"([^"]+)"', html)
                if not mm:
                    continue
                u = mm.group(1).replace("\\/", "/")
                res = re.search(r"video_(\d+)p", u)
                lbl = ("MP4-" + res.group(1) + "P") if res else ("MP4-高清" if fn.endswith("High") else "MP4-标清")
                if u not in [x[1] for x in lines]:
                    lines.append((lbl, u))
            if not lines:
                hm = re.search(r"(https?://[^\"'<>\s]+\.m3u8[^\"'<>\s]*)", html)
                if hm:
                    lines.append(("HLS", hm.group(1).replace("\\/", "/")))
            if not lines:
                continue
            seen = set()
            uniq = []
            for lbl, u in lines:
                if u in seen:
                    continue
                seen.add(u)
                uniq.append((lbl, u))
            lines = uniq
            marks = []
            mdur = re.search(r'property="og:video:duration"\s+content="(\d+)"', html)
            if mdur:
                sec = int(mdur.group(1))
                marks.append("%d:%02d" % (sec // 60, sec % 60))
            top = re.search(r'class="video-hd-mark"[^>]*>([^<]+)<', html)
            if top:
                marks.append(self._clean(top.group(1)))
            out.append({
                "vod_id": vid,
                "vod_name": name,
                "vod_pic": pic,
                "vod_content": desc,
                "vod_remarks": " | ".join(marks),
                "vod_play_from": "$$$".join(l[0] for l in lines),
                "vod_play_url": "$$$".join("播放$%s" % l[1] for l in lines),
            })
        return {"list": out} if out else {"list": []}

    def playerContent(self, flag, id, vipFlags):
        raw = str(id)
        if "$$$" in raw:
            raw = raw.split("$$$")[0]
        url = raw.split("$")[-1] if "$" in raw else raw
        url = url.replace("\\/", "/")
        hdr = {"Referer": (self._host or "https://www.xvideos.com") + "/", "User-Agent": self.UA}
        if ".mp4" in url:
            hdr["Accept-Encoding"] = "empty"
        return {"parse": 0, "url": url, "jx": 0, "header": json.dumps(hdr)}

    def localProxy(self, param):
        return [200, "video/mp4", b"", json.dumps({"Cache-Control": "no-cache"})]

    def proxy(self, param):
        return b""
