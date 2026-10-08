import re
import json
import html as _html
try:
    import requests as _requests
except Exception:
    _requests = None


class Spider:
    def __init__(self):
        self.site = "https://830556.iseseav101.buzz"
        self.name = "iSese影库"
        self.header = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 13; SM-S9080) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Referer": self.site,
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        self.s = self.session = self.sess = _requests.Session() if _requests else None
        self._extend = {}
        self._home = None

    def getDependence(self):
        return []

    def manualVideoCheck(self):
        return False

    def isVideoFormat(self, url):
        if not url:
            return False
        u = str(url).lower()
        return u.endswith((".m3u8", ".mp4", ".flv", ".mkv", ".ts", ".avi")) or "m3u8" in u

    def destroy(self):
        pass

    def action(self, action):
        return {}

    def _get(self, url, referer=None):
        h = dict(self.header)
        if referer:
            h["Referer"] = referer
        if self.s is not None:
            try:
                r = self.s.get(url, headers=h, timeout=12, allow_redirects=True, verify=False)
                if r.status_code < 400:
                    return r.text
            except Exception:
                pass
        try:
            import urllib.request
            import ssl
            req = urllib.request.Request(url, headers=h)
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(req, timeout=12, context=ctx) as resp:
                return resp.read().decode("utf-8", "ignore")
        except Exception:
            return ""

    def _u(self, u):
        if not u:
            return u
        u = u.strip()
        if u.startswith("//"):
            return "https:" + u
        if u.startswith("http"):
            return u
        if u.startswith("/"):
            m = re.match(r"(https?://[^/]+)", self.site)
            return (m.group(1) if m else self.site) + u
        return self.site.rstrip("/") + "/" + u.lstrip("/")

    def _extract_player(self, html):
        start = html.find('var player_aaaa=')
        if start == -1:
            start = html.find('var player_aaaa =')
        if start == -1:
            return None
        start = html.find('{', start)
        if start == -1:
            return None
        brace_count = 0
        in_string = False
        escape = False
        for i in range(start, len(html)):
            ch = html[i]
            if escape:
                escape = False
                continue
            if ch == '\\':
                escape = True
                continue
            if ch == '"' and not in_string:
                in_string = True
            elif ch == '"' and in_string:
                in_string = False
            elif ch == '{' and not in_string:
                brace_count += 1
            elif ch == '}' and not in_string:
                brace_count -= 1
                if brace_count == 0:
                    try:
                        return json.loads(html[start:i+1])
                    except Exception:
                        return None
        return None

    def _cats(self):
        if self._home is None:
            self._home = self._get(self.site)
        html = self._home
        out = []
        seen = set()
        pat1 = r'<a[^>]+href="(/aise/index\.php/vod/type/id/(\d+)\.html)"[^>]*>.*?<span[^>]*class="name"[^>]*>([^<]+)</span>'
        for m in re.finditer(pat1, html, re.S):
            href, cid, name = m.group(1), m.group(2), _html.unescape(m.group(3).strip())
            if not name or name in seen or any(w in name for w in ("首页","登录","注册","会员","充值","APP","下载","搜索","排行","最新","热门","专题","资讯","留言","求片","全部")):
                continue
            seen.add(name)
            out.append({"type_id": self._u(href), "type_name": name})
        if not out:
            pat2 = r'<a[^>]+href="(/aise/index\.php/vod/type/id/(\d+)\.html)"[^>]*>([^<]{1,12})</a>'
            for m in re.finditer(pat2, html, re.S):
                href, cid, name = m.group(1), m.group(2), _html.unescape(m.group(3).strip())
                if not name or name in seen or any(w in name for w in ("首页","登录","注册","会员","充值","APP","下载","搜索","排行","最新","热门","专题","资讯","留言","求片","全部")):
                    continue
                seen.add(name)
                out.append({"type_id": self._u(href), "type_name": name})
        if not out:
            fallback = [("26", "国产乱伦"), ("27", "网曝黑料"), ("28", "自拍偷拍"), ("29", "国产传媒"),
                       ("30", "国产精品"), ("31", "探花精品"), ("32", "网红主播"), ("33", "AI换脸"),
                       ("34", "同性恋"), ("35", "3D动漫"), ("36", "欧美精品"), ("37", "韩国主播")]
            for cid, cname in fallback:
                if cname not in seen:
                    seen.add(cname)
                    out.append({"type_id": self.site + "/aise/index.php/vod/type/id/%s.html" % cid, "type_name": cname})
        return out

    def _items(self, html, skip=0):
        out = []
        seen = set()
        if not html:
            return out

        def _extract(block_html):
            _out = []
            for bm in re.finditer(r'<li[^>]*>([\s\S]{20,5000}?)</li>', block_html, re.S):
                block = bm.group(1)
                hm = re.search(r'href="(/aise/index\.php/vod/play/id/\d+/sid/\d+/nid/\d+\.html)"', block)
                if not hm:
                    hm = re.search(r'href="(/aise/index\.php/vod/play/[^"]+)"', block)
                    if not hm:
                        continue
                vid = self._u(hm.group(1))
                pic = ""
                im = re.search(r'<img[^>]+data-original="([^"]+)"', block)
                if im:
                    pic = self._u(im.group(1))
                else:
                    im = re.search(r'<img[^>]+src="([^"]+)"', block)
                    if im:
                        pic = self._u(im.group(1))
                title = ""
                tm = re.search(r'<h5[^>]*>.*?<a[^>]*>([^<]{2,120})</a>.*?</h5>', block, re.S)
                if tm:
                    title = _html.unescape(tm.group(1)).strip()
                else:
                    tm = re.search(r'(?:title|alt)="([^"]{2,120})"', block)
                    if tm:
                        title = _html.unescape(tm.group(1)).strip()
                if not title:
                    continue
                if vid in seen:
                    continue
                seen.add(vid)
                remarks = ""
                rm = re.search(r'<p[^>]*class="vodtitle"[^>]*>([\s\S]{2,200}?)</p>', block, re.S)
                if rm:
                    remarks = re.sub(r"<[^>]+>", "", rm.group(1)).strip()
                    remarks = remarks.replace("\n", " ").replace("\t", " ")
                    remarks = " ".join(remarks.split())
                _out.append({
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": remarks,
                })
            return _out

        if skip > 0:
            ul_matches = list(re.finditer(r'<ul[^>]*>[\s\S]*?</ul>', html, re.S))
            has_video_ul = False
            for um in ul_matches:
                ul_html = um.group(0)
                if re.search(r'/aise/index\.php/vod/play/', ul_html):
                    has_video_ul = True
                    block_results = _extract(ul_html)
                    if len(block_results) > skip:
                        out.extend(block_results[skip:])
            if not has_video_ul:
                out = _extract(html)[skip:]
        else:
            out = _extract(html)

        return out

    def init(self, extend=""):
        self._extend = {}
        if isinstance(extend, dict):
            self._extend = extend
        elif isinstance(extend, str) and extend.strip():
            try:
                e = json.loads(extend)
                if isinstance(e, dict):
                    self._extend = e
            except Exception:
                pass

    def homeContent(self, filter=None):
        cats = self._cats()
        html = self._home if self._home is not None else self._get(self.site)
        vod_list = self._items(html, skip=6)
        return {"class": cats, "list": vod_list}

    def homeVideoContent(self):
        if self._home is None:
            self._home = self._get(self.site)
        return {"list": self._items(self._home)}

    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        url = str(tid)
        if "type/id/" in url:
            if url.endswith(".html"):
                base = url.rsplit(".html", 1)[0]
                url = base + "/page/%d.html" % pg
            elif "/page/" in url:
                url = re.sub(r"/page/\d+\.html", "/page/%d.html" % pg, url)
            else:
                url = url.rstrip("/") + "/page/%d.html" % pg
        else:
            url = self.site + "/aise/index.php/vod/type/id/%s/page/%d.html" % (tid, pg)
        html = self._get(url)
        if not html:
            return {"list": [], "page": pg, "pagecount": 1, "limit": 24, "total": 0}
        vod_list = self._items(html, skip=6)
        pagecount = 1
        total = len(vod_list)
        m = re.search(r'共\s*(\d+)\s*页', html)
        if not m:
            m = re.search(r'pagecount[=:]\s*(\d+)', html, re.S)
        if not m:
            m = re.search(r'totalpage[=:]\s*(\d+)', html, re.S)
        if m:
            pagecount = int(m.group(1))
        else:
            pages = re.findall(r'/page/(\d+)\.html', html)
            if pages:
                pagecount = max(int(p) for p in pages)
        return {"list": vod_list, "page": pg, "pagecount": pagecount, "limit": 24, "total": total}

    def detailContent(self, ids):
        vid = ids
        if isinstance(ids, (list, tuple)):
            vid = ids[0] if ids else ""
        vid = str(vid).strip()
        if not vid:
            return {"list": []}
        url = self._u(vid)
        html = self._get(url)
        if not html:
            return {"list": []}
        title = ""
        pic = ""
        desc = ""
        play_from = self.name
        play_url = ""
        pdata = self._extract_player(html)
        if pdata:
            vdata = pdata.get("vod_data", {})
            title = vdata.get("vod_name", "")
            desc = vdata.get("vod_class", "")
        if not title:
            tm = re.search(r'<title[^>]*>([^<]{2,60})</title>', html)
            if tm:
                title = _html.unescape(tm.group(1)).strip().replace("在线播放--iSeseAV影库", "").replace("--iSeseAV影库", "").replace(" - iSeseAV影库", "")
        if not pic:
            pats = (r'<img[^>]+data-original="([^"]+)"', r'<img[^>]+src="([^"]+)"', r'<img[^>]+data-poster="([^"]+)"')
            for pat in pats:
                im = re.search(pat, html)
                if im:
                    pic = self._u(im.group(1))
                    break
        if not desc:
            dm = re.search(r'<div[^>]*class="[^"]*(content|desc|intro|summary)[^"]*"[^>]*>([\s\S]{10,500}?)</div>', html, re.S)
            if dm:
                desc = re.sub(r"<[^>]+>", "", dm.group(2)).strip()
        # 始终返回播放页URL，让playerContent解析真实地址
        play_url = "第1集$%s" % vid
        return {"list": [{"vod_id": vid, "vod_name": title, "vod_pic": pic,
                          "vod_content": desc, "vod_play_from": play_from,
                          "vod_play_url": play_url}]}

    def searchContent(self, key, quick=False, pg="1"):
        try:
            from urllib.parse import quote
            url = self.site + "/aise/index.php/vod/search.html?wd=" + quote(str(key))
            if int(pg) > 1:
                url += "&page=" + str(pg)
        except Exception:
            return {"list": []}
        html = self._get(url)
        if not html:
            return {"list": []}
        return {"list": self._items(html)}

    def playerContent(self, flag, ids, vipFlags=None):
        url = ids
        if isinstance(ids, (list, tuple)):
            url = ids[0] if ids else ""
        url = str(url or "").strip()
        if not url:
            return {"parse": 0, "url": "", "header": dict(self.header)}
        if not url.startswith("http"):
            url = self._u(url)
        if self.isVideoFormat(url):
            return {"parse": 0, "url": url, "header": dict(self.header)}
        html = self._get(url, referer=self.site)
        if not html:
            return {"parse": 0, "url": "", "header": dict(self.header)}
        found = ""
        pdata = self._extract_player(html)
        if pdata:
            found = pdata.get("url", "")
            if not found:
                found = pdata.get("link", "")
            if not found:
                found = pdata.get("video", "")
        if not found:
            m = re.search(r'(https?://[^\s"\'\\]+\.m3u8[^\s"\'\\]*)', html)
            if m:
                found = m.group(1)
        if not found:
            m = re.search(r'(https?://[^\s"\'\\]+\.mp4[^\s"\'\\]*)', html)
            if m:
                found = m.group(1)
        if not found:
            return {"parse": 0, "url": "", "header": dict(self.header)}
        found = found.strip().replace("\\/", "/")
        if found.startswith("//"):
            found = "https:" + found
        elif not found.startswith("http"):
            found = self._u(found)
        return {"parse": 0, "url": found, "header": dict(self.header)}

    def localProxy(self, param):
        u = param.get("url", "") if isinstance(param, dict) else ""
        if not u:
            return [403, "text/plain", b"", None]
        h = dict(self.header)
        if self.s is not None:
            try:
                r = self.s.get(u, headers=h, timeout=15, verify=False)
                return [200, r.headers.get("Content-Type", "application/octet-stream"), r.content, None]
            except Exception:
                pass
        try:
            import urllib.request
            import ssl
            req = urllib.request.Request(u, headers=h)
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
                return [200, resp.headers.get("Content-Type", "application/octet-stream"), resp.read(), None]
        except Exception:
            return [403, "text/plain", b"", None]
