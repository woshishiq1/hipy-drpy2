import re
import json
import time
import html as _html

try:
    import requests as _requests
except Exception:
    _requests = None

class Spider:
    def getName(self):
        return self.name

    def __init__(self, t4_api="", **kwargs):
        self.t4_api = t4_api or kwargs.get("t4_api", "")
        self.site = "https://xrpm.eu.cc"
        self.name = "向上影院"
        self.header = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 13; SM-S9080) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Referer": self.site,
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        self.s = self.session = self.sess = _requests.Session() if _requests else None
        
        self.extend = []
        self._extend = {}
        self._home = None
        self._category_tree = None
        self._category_cache = {}
        self._filter_cache = {}
        self._preset_cats = []

    

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

    def localProxy(self, param):
        u = param.get("url", "") if isinstance(param, dict) else ""
        if not u:
            return [403, "text/plain", b"", {}]
        h = dict(self.header)
        if self.s is not None:
            try:
                r = self.s.get(u, headers=h, timeout=15)
                return [200, r.headers.get("Content-Type", "application/octet-stream"), r.content, dict(r.headers)]
            except Exception:
                pass
        try:
            import urllib.request
            req = urllib.request.Request(u, headers=h)
            with urllib.request.urlopen(req, timeout=15) as resp:
                return [200, resp.headers.get("Content-Type", "application/octet-stream"), resp.read(), dict(resp.headers)]
        except Exception:
            return [403, "text/plain", b"", {}]

    

    def _get(self, url, referer=None):
        h = dict(self.header)
        if referer:
            h["Referer"] = referer
        if self.s is not None:
            try:
                r = self.s.get(url, headers=h, timeout=15, allow_redirects=True)
                if r.status_code < 400:
                    return r.text
            except Exception:
                pass
        try:
            import urllib.request
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.read().decode("utf-8", "ignore")
        except Exception:
            return ""

    def _u(self, u):
        if not u:
            return u
        u = _html_unescape(str(u)).strip().replace('\\/', '/')
        if u.startswith("//"):
            return "https:" + u
        if u.startswith("http"):
            return u
        if u.startswith("/"):
            m = re.match(r"(https?://[^/]+)", self.site)
            return (m.group(1) if m else self.site) + u
        return self.site.rstrip("/") + "/" + u.lstrip("/")

    def _normalize_pic(self, value):
        
        u = self._u(value)
        host_map = {
            "viptulz.com": "img.lzipic.com",
            "img.lzzyimg.com": "img.lzipic.com",
        }
        try:
            from urllib.parse import urlsplit, urlunsplit
            p = urlsplit(u)
            if p.netloc.lower() in host_map:
                u = urlunsplit((p.scheme, host_map[p.netloc.lower()], p.path, p.query, p.fragment))
        except Exception:
            pass
        return u

    def _clean_text(self, value):
        value = _html_unescape(str(value or ""))
        value = re.sub(r"<br\\s*/?>", " ", value, flags=re.I)
        value = re.sub(r"<[^>]+>", " ", value)
        return re.sub(r"\\s+", " ", value).strip(" \\t\\r\\n：:")

    def _page(self, pg):
        try:
            pg = int(pg)
            return pg if pg > 0 else 1
        except Exception:
            return 1

    

    def init(self, extend=""):
        
        self.extend = extend if extend is not None else []
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
        if self._extend.get("host"):
            self.site = self._extend["host"].rstrip("/")

    def homeContent(self, filter=None):
        html = self._get(self.site)
        self._home = html
        cats, filters = self._parse_category_tree(html)
        
        
        missing = [c["type_id"] for c in cats if c["type_id"] not in self._filter_cache]
        if missing:
            try:
                from concurrent.futures import ThreadPoolExecutor
                with ThreadPoolExecutor(max_workers=min(6, len(missing))) as pool:
                    pages = list(pool.map(lambda t: (t, self._get(self._build_category_url(t, 1))), missing))
                for tid, page_html in pages:
                    self._filter_cache[tid] = self._parse_page_filters(page_html, tid)
            except Exception:
                pass
        for tid, parsed in self._filter_cache.items():
            if parsed:
                filters[tid] = parsed
        self._category_tree = (cats, filters)
        vod_list = self._extract_list(html)
        out = {"class": cats or self._preset_cats, "list": vod_list}
        if filters:
            out["filters"] = filters
        return out

    def homeVideoContent(self):
        if self._home is None:
            self._home = self._get(self.site)
        return {"list": self._extract_list(self._home)}

    def homeVodContent(self):
        return self.homeVideoContent()

    def _parse_category_tree(self, html):

        cats, filters, seen = [], {}, set()
        if not html:
            return cats, filters
        menu = re.search(r'<ul class="hl-menus clearfix">([\s\S]*?)</ul>', html, re.S)
        if not menu:
            return cats, filters
        nodes = re.findall(r'<li\b[^>]*class="([^"]*)"[^>]*>([\s\S]*?)</li>', menu.group(1), re.S)
        for index, (classes, body) in enumerate(nodes):
            if "hl-menus-item" not in classes:
                continue
            parent = re.search(r'href="/vodtype/(\d+)\.html"[^>]*>[\s\S]*?<span>([^<]+)</span>', body, re.S)
            if not parent:
                continue
            tid, name = parent.group(1), self._clean_text(parent.group(2))
            if tid in seen:
                continue
            seen.add(tid)
            cats.append({"type_id": tid, "type_name": name})
            child = nodes[index + 1][1] if index + 1 < len(nodes) and "hl-type-child" in nodes[index + 1][0] else ""
            options = [{"n": "全部", "v": tid}]
            for cm in re.finditer(r'href="/vodtype/(\d+)\.html"[^>]*>([^<]+)</a>', child, re.S):
                cid, cname = cm.group(1), self._clean_text(cm.group(2))
                if cid and cid != tid:
                    options.append({"n": cname, "v": cid})
            
            if len(options) > 1:
                filters[tid] = [{"key": "type", "name": "分类", "value": options}]
        return cats, filters

    def _parse_page_filters(self, html, tid):

        if not html:
            return []
        start = html.find('<div class="hl-filter-all clearfix">')
        if start < 0:
            return []
        end = html.find('<div class="container">', start)
        root = html[start:end] if end > start else html[start:]
        rows = []
        keys = {"分类": "type", "类型": "class", "地区": "area", "年份": "year", "语言": "lang", "版本": "version", "资源": "resource", "字母": "letter"}
        row_pattern = (r'<div class="hl-filter-item hl-filter-text[^>]*>\s*<span>([^<]+)</span>[\s\S]*?</div>'
                       r'\s*<ul class="hl-filter-list[^>]*>([\s\S]*?)</ul>')
        for raw_name, option_html in re.findall(row_pattern, root, re.S):
            name = self._clean_text(raw_name)
            key = keys.get(name)
            if not key:
                continue
            values = [{"n": "全部", "v": ""}]
            seen = set()
            for am in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>([\s\S]*?)</a>', option_html, re.S):
                href, label = am.group(1), self._clean_text(am.group(2))
                if not label or label == "全部" or href.startswith("javascript:"):
                    continue
                value = self._filter_value_from_href(key, href)
                if value and value not in seen:
                    seen.add(value)
                    values.append({"n": label, "v": value})
            if len(values) > 1:
                rows.append({"key": key, "name": name, "value": values})
        return rows

    def _filter_value_from_href(self, key, href):
        from urllib.parse import unquote
        path = unquote(href)
        if key == "type":
            m = re.search(r'/vodshow/(\d+)-', path)
            return m.group(1) if m else ""
        if key == "version":
            m = re.search(r'/version/([^/.]+)', path)
            return m.group(1) if m else ""
        tail = path.rsplit('/vodshow/', 1)[-1].split('.html', 1)[0]
        
        patterns = {
            "area": r'^\d+-([^\-]+)-',
            "class": r'^\d+---([^\-]+)-',
            "lang": r'^\d+----([^\-]+)-',
            "letter": r'^\d+-----([^\-]+)-',
            "resource": r'^\d+-{9}([^\-]+)--',
            "year": r'^\d+-{11}(\d{4})$',
        }
        m = re.search(patterns.get(key, r'$^'), tail)
        return m.group(1) if m else ""

    def _build_category_url(self, tid, pg, extend=None):
        ext = extend if isinstance(extend, dict) else {}
        area = ext.get("area", "") or ""
        by = ext.get("by", "") or ""
        kind = ext.get("class", "") or ""
        lang = ext.get("lang", "") or ""
        letter = ext.get("letter", "") or ""
        resource = ext.get("resource", "") or ""
        year = ext.get("year", "") or ""
        page = str(pg) if pg and int(pg) > 1 else ""
        
        fields = [str(tid), area, by, kind, lang, letter, "", "", page, resource, "", year]
        base = self.site + "/vodshow/" + "-".join(fields) + ".html"
        version = ext.get("version", "") or ""
        return base[:-5] + "/version/" + version + ".html" if version else base

    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        pg = self._page(pg)
        ext = extend if isinstance(extend, dict) else {}
        target_tid = str(ext.get("type") or tid)
        cache_key = (target_tid, pg, tuple(sorted((str(k), str(v)) for k, v in ext.items())))
        cached = self._category_cache.get(cache_key)
        if cached and time.monotonic() - cached[0] < 180:
            return cached[1]

        url = self._build_category_url(target_tid, pg, ext)
        html = self._get(url)
        if not html:
            fallback = "%s/vodtype/%s.html" % (self.site, target_tid) if pg == 1 else "%s/vodtype/%s-%d.html" % (self.site, target_tid, pg)
            html = self._get(fallback)
        if not html:
            return {"list": [], "page": pg, "pagecount": pg, "limit": 24, "total": 0}
        vod_list = self._extract_list(html)

        
        result = {"list": vod_list, "page": pg, "pagecount": pg + 1 if len(vod_list) >= 24 else pg, "limit": 24, "total": 0}
        self._category_cache[cache_key] = (time.monotonic(), result)
        return result

    

    def detailContent(self, ids):
        vid = ids
        if isinstance(ids, (list, tuple)):
            vid = ids[0] if ids else ""
        vid = str(vid).strip()

        
        if vid.startswith(self.site):
            vid = vid[len(self.site):]
        m = re.search(r'/xq/(\d+)\.html', vid)
        if m:
            vid = m.group(1)
        vid = re.sub(r'\.html$', '', vid)
        vid = re.sub(r'^/xq/', '', vid)

        url = "%s/xq/%s.html" % (self.site, vid)
        html = self._get(url)
        if not html:
            return {"list": []}

        
        title = ""
        tm = re.search(r'<h[12][^>]+class="[^"]*hl-dc-title[^"]*"[^>]*>(.*?)</h[12]>', html, re.S)
        if tm:
            title = self._clean_text(tm.group(1))
        if not title:
            tm = re.search(r'<title[^>]*>([^<]{2,120})</title>', html)
            if tm:
                title = _html_unescape(tm.group(1)).strip()
                title = re.sub(r'^《([^》]+)》.*$', r'\1', title)
                title = title.replace("免费在线观看", "").replace("高清完整版资源", "").replace("- 向上影院", "").strip()

        
        pic = ""
        im = re.search(r'<span class="hl-item-thumb[^"]*"[^>]+data-original="([^"]+)"', html, re.S) or \
             re.search(r'property="og:image" content="([^"]+)"', html) or \
             re.search(r'<img[^>]+class="[^"]*pic[^"]*"[^>]+src="([^"]+)"', html, re.S)
        if im:
            pic = self._normalize_pic(im.group(1))

        
        desc = ""
        
        dm = re.search(r'<div[^>]+class="[^\"]*\bhl-rb-content\b[^\"]*"[^>]*>([\s\S]*?)(?=<div[^>]+class="[^\"]*\bhl-rb-relvod\b)', html, re.S)
        if dm:
            block = dm.group(1)
            bm = re.search(r'<b[^>]*>[\s\S]*?</b>\s*<br\s*/?>\s*<p[^>]*>([\s\S]*?)</p>', block, re.I)
            if bm:
                desc = self._clean_text(bm.group(1))
            else:
                paragraphs = re.findall(r'<p[^>]*>([\s\S]*?)</p>', block, re.I)
                ignored = ('片名', '名称拼音', '关键词', '电影类别', '类别', '发行年份', '首映地区', '导演', '演员', '更新时间', '总集数')
                body = [self._clean_text(p) for p in paragraphs]
                body = [p for p in body if p and not p.startswith(ignored)]
                desc = body[0] if body else ''
        if not desc:
            dm = re.search(r'property="og:description"\s+content="([^"]+)"', html)
            if dm:
                desc = self._clean_text(dm.group(1))

        
        def meta_value(label):
            mm = re.search(r'<li[^>]*>\s*<em[^>]*>\s*' + label + r'\s*[：:]\s*</em>([\s\S]*?)</li>', html, re.S)
            if not mm:
                return ""
            return self._clean_text(re.sub(r'<i[^>]*>[\s\S]*?</i>', '/', mm.group(1)))

        def intro_value(label):
            mm = re.search(r'<p>\s*' + label + r'\s*[：:]\s*([^<]*)</p>', html, re.S)
            return self._clean_text(mm.group(1)) if mm else ""

        year = meta_value(r'年份') or intro_value(r'发行年份')
        area = meta_value(r'地区') or intro_value(r'首映地区')
        actor = meta_value(r'主演') or intro_value(r'演员')
        director = meta_value(r'导演') or intro_value(r'导演')
        remarks = meta_value(r'状态')
        type_name = meta_value(r'类型')

        
        sources = []

        
        src_names = []
        for sm in re.finditer(r'<div class="hl-plays-from[^"]*"[^>]*>([\s\S]*?)</div>', html):
            seg = sm.group(1)
            for nm in re.finditer(r'<a[^>]+alt="([^"]+)"[^>]*>[\s\S]*?</a>', seg):
                n = nm.group(1).strip()
                if n:
                    src_names.append(n)
            if not src_names:
                for nm in re.finditer(r'>([^<]+)<', seg):
                    n = nm.group(1).strip()
                    if n and n not in ("", " ", "&nbsp;"):
                        src_names.append(n)

        
        play_boxes = re.findall(r'<ul class="hl-plays-list[^"]*"[^>]*>([\s\S]*?)</ul>', html)

        if play_boxes:
            for i, box in enumerate(play_boxes):
                src_name = src_names[i] if i < len(src_names) else ("播放%d" % (i + 1))
                eps = []
                seen = set()
                for pm in re.finditer(r'<a href="(/bf/\d+-\d+-\d+\.html)"[^>]*>(?:<em[^>]*>[^<]*</em>)?([^<]+)</a>', box):
                    h, n = pm.group(1), pm.group(2).strip()
                    if not h or not n:
                        continue
                    if (h, n) in seen:
                        continue
                    seen.add((h, n))
                    eps.append("%s$%s" % (n, self._u(h)))
                if eps:
                    sources.append((src_name, eps))

        
        if not sources:
            eps = []
            seen = set()
            for pm in re.finditer(r'<a href="(/bf/\d+-\d+-\d+\.html)"[^>]*>(?:<em[^>]*>[^<]*</em>)?([^<]+)</a>', html):
                h, n = pm.group(1), pm.group(2).strip()
                if (h, n) in seen:
                    continue
                seen.add((h, n))
                eps.append("%s$%s" % (n, self._u(h)))
            if eps:
                sources.append(("播放", eps))

        
        valid_sources = []
        for source_name, episodes in sources:
            clean_eps = []
            for episode in episodes:
                if "$" not in episode:
                    continue
                ep_name, ep_url = episode.rsplit("$", 1)
                if ep_name.strip() and ep_url.startswith(("http://", "https://")):
                    clean_eps.append(ep_name.strip() + "$" + ep_url.strip())
            if source_name.strip() and clean_eps:
                valid_sources.append((source_name.strip(), clean_eps))

        play_from = [s[0] for s in valid_sources]
        play_url = ["#".join(s[1]) for s in valid_sources]
        from_text = "$$$".join(play_from)
        url_text = "$$$".join(play_url)
        if from_text and len(play_from) != len(play_url):
            return {"list": []}

        vod = {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic,
            "type_name": type_name,
            "vod_remarks": remarks,
            "vod_year": year,
            "vod_area": area,
            "vod_actor": actor,
            "vod_director": director,
            "vod_content": desc,
            "vod_play_from": from_text,
            "vod_play_url": url_text,
        }
        
        if not vod["vod_id"] or not vod["vod_name"]:
            return {"list": []}
        return {"list": [vod]}

    

    def searchContent(self, key, quick=False, pg="1"):
        try:
            from urllib.parse import quote
            url = "%s/vodsearch/-------------.html?wd=%s" % (self.site, quote(str(key)))
        except Exception:
            return {"list": []}
        html = self._get(url)
        if not html:
            return {"list": []}
        return {"list": self._extract_list(html)}

    

    def playerContent(self, flag, ids, vipFlags=None):
        url = ids
        if isinstance(ids, (list, tuple)):
            url = ids[0] if ids else ""
        url = str(url or "").strip()
        if not url:
            return {"parse": 0, "playUrl": "", "url": "", "header": dict(self.header)}

        
        if self.isVideoFormat(url):
            return {"parse": 0, "playUrl": "", "url": url, "header": dict(self.header)}

        play_url = self._u(url) if not url.startswith("http") else url
        html = self._get(play_url, referer=self.site)
        if not html:
            return {"parse": 0, "playUrl": "", "url": "", "header": dict(self.header)}

        
        player = {}
        m = re.search(r'var\s+player_aaaa\s*=\s*({.*?})\s*(?:;\s*)?</script>', html, re.S)
        if m:
            try:
                player = json.loads(m.group(1).replace('\\/', '/'))
            except Exception:
                player = {}
        found = str(player.get("url") or "").strip()
        encrypt = str(player.get("encrypt") or "0")
        if found and encrypt == "1":
            try:
                from urllib.parse import unquote
                found = unquote(found)
            except Exception:
                pass
        if found and encrypt == "2":
            try:
                import base64
                from urllib.parse import unquote
                found = unquote(base64.b64decode(found).decode("utf-8"))
            except Exception:
                found = ""
        if found:
            found = _html_unescape(found).replace('\\/', '/')
            if found.startswith("//"):
                found = "https:" + found
            if found.startswith(("http://", "https://")):
                h = dict(self.header)
                h["Referer"] = play_url
                return {"parse": 0, "playUrl": "", "url": found, "header": h}

        
        return {"parse": 1, "playUrl": "", "url": play_url, "header": dict(self.header)}

    

    def _extract_list(self, html):

        out = []
        seen = set()
        for m in re.finditer(r'<li class="hl-list-item[^"]*">([\s\S]*?)</li>', html):
            block = m.group(1)
            href = re.search(r'href="(/xq/\d+\.html)"', block)
            if not href:
                continue
            vid = href.group(1).replace("/xq/", "").replace(".html", "")
            if vid in seen:
                continue
            seen.add(vid)

            title = ""
            tm = re.search(r'title="([^"]+)"', block)
            if tm:
                title = _html_unescape(tm.group(1)).strip()

            pic = ""
            pm = re.search(r'data-original="([^"]+)"', block) or \
                 re.search(r'data-src="([^"]+)"', block) or \
                 re.search(r'src="([^"]+)"', block)
            if pm:
                pic = self._normalize_pic(pm.group(1))

            remark = ""
            rm = re.search(r'<span class="[^"]*remarks[^"]*"[^>]*>([^<]+)</span>', block) or \
                 re.search(r'<span class="hl-lc-1[^"]*"[^>]*>([^<]+)</span>', block)
            if rm:
                remark = _html_unescape(rm.group(1)).strip()

            out.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remark,
            })
        return out

def _html_unescape(s):
    return _html.unescape(s) if s else s