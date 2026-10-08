# -*- coding: utf-8 -*-
import sys
import re
import json
import time
import requests
from urllib.parse import quote

sys.path.append('..')
try:
    from base.spider import Spider
except ImportError:
    class Spider:
        def fetch(self, url, headers=None, **kw):
            import requests as rq
            kw.pop('timeout', None)
            r = rq.get(url, headers=headers, timeout=15, **kw)
            r.encoding = 'utf-8'
            return r

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
HOSTS = ["https://www.fullhd.to", "https://www.fullhd.xxx"]
HOST = HOSTS[0]
_CATS = None
_SKIP = {'vr-virtual-reality', 'danish', 'iranian', 'shemale-3p', 'shemale-fuck', 'partner-show', 'shemale-threesome', 'chinese'}


class Spider(Spider):
    def init(self, extend=""):
        global HOST, _CATS
        _CATS = None
        self._sess = None
        self._pinfo = None
        ext = (extend or '').strip()
        if ext.startswith('http'):
            HOST = ext.rstrip('/')
            return
        for d in HOSTS:
            try:
                r = self.fetch(d + '/zh/', headers={"User-Agent": UA}, timeout=10000)
                u = getattr(r, 'url', '') or ''
                m = re.match(r'(https?://[^/]+)', u)
                if m:
                    HOST = m.group(1).rstrip('/')
                    return
                if getattr(r, 'status_code', 0) == 200:
                    HOST = d
                    return
            except:
                pass
        HOST = HOSTS[0]

    def _cats(self):
        global _CATS
        if _CATS:
            return _CATS
        try:
            r = self.fetch(f"{HOST}/zh/categories/", headers={"User-Agent": UA}, timeout=20000)
            h = r.text if hasattr(r, 'text') else str(r)
            cats, seen = [], set()
            for m in re.finditer(r'href="[^"]*/zh/categories/([a-z0-9-]+)/"[^>]*title="([^"]+)"', h):
                s, n = m.group(1), m.group(2).strip()
                if s in seen or s in _SKIP:
                    continue
                seen.add(s)
                if n.count('（') > n.count('）'):
                    n = n.split('（')[0].strip()
                if n.count('(') > n.count(')'):
                    n = n.split('(')[0].strip()
                if re.search(r'[\u3040-\u30ff]', n):
                    n = s.replace('-', ' ').title()
                if n:
                    cats.append({"type_id": s, "type_name": n})
            _CATS = cats[:40] or [{"type_id": "latest-updates", "type_name": "最新更新"}]
        except:
            _CATS = [{"type_id": "latest-updates", "type_name": "最新更新"}]
        return _CATS

    def homeContent(self, filter=False):
        return {"class": self._cats(), "list": []}

    def homeVideoContent(self):
        try:
            r = self.fetch(f"{HOST}/zh/latest-updates/", headers={"User-Agent": UA}, timeout=30000)
            h = r.text if hasattr(r, 'text') else str(r)
            return {"list": self._items(h)}
        except:
            return {"list": []}

    def categoryContent(self, tid, pg=1, filter=False, extend=""):
        pn = 1
        try:
            pn = max(int(str(pg)), 1)
        except:
            pass
        try:
            url = f"{HOST}/zh/categories/{tid}/" if pn <= 1 else f"{HOST}/zh/categories/{tid}/{pn}/"
            r = self.fetch(url, headers={"User-Agent": UA}, timeout=30000)
            h = r.text if hasattr(r, 'text') else str(r)
            items = self._items(h)
            return {
                "page": pn,
                "pagecount": self._pagecount(h, pn),
                "limit": 24,
                "total": len(items),
                "list": items
            }
        except:
            return {"page": pn, "pagecount": 1, "limit": 24, "total": 0, "list": []}

    def detailContent(self, ids):
        vid = str(ids[0] if isinstance(ids, list) else ids)
        m = re.search(r'(\d+)', vid)
        if not m:
            return {"list": []}
        vid = m.group(1)
        try:
            if self._sess is None:
                self._sess = requests.Session()
                self._sess.headers.update({"User-Agent": UA})
            r = self._sess.get(f"{HOST}/zh/videos/{vid}/x/", headers={"User-Agent": UA}, timeout=30000)
            h = r.text if hasattr(r, 'text') else str(r)
            srcs = re.findall(r"<source src='([^']+)'[^>]*label=\"([^\"]+)\"", h)
            if srcs:
                ck = '; '.join(f"{k}={v}" for k, v in self._sess.cookies.items())
                self._pinfo = (vid, srcs, ck, time.time())
        except:
            return {"list": []}
        h1 = re.search(r'<h1[^>]*>(.*?)</h1>', h, re.S)
        name = re.sub(r'<[^>]+>', '', h1.group(1)).strip() if h1 else ""
        name = re.sub(r'\s*/\s*\d{2}\.\d{2}\.\d{4}\s*$', '', name).strip()
        srcs = re.findall(r"<source src='([^']+)'[^>]*label=\"([^\"]+)\"", h)
        if not srcs or not name:
            return {"list": []}
        srcs = [(u, '1080p' if l == '2160p' else l) for u, l in srcs]
        srcs.sort(key=lambda x: -(int(re.sub(r'\D', '', x[1]) or 0)))
        desc = re.search(r'property="og:description" content="([^"]+)"', h)
        content = desc.group(1) if desc else ""
        actors = []
        dm = re.search(r'由\s*([^。]+?)\s*主演', content)
        if dm:
            actors = [a.strip() for a in re.split(r'\s*(?:和|与|、|,)\s*', dm.group(1)) if a.strip()]
        tags = re.findall(r'<meta property="video:tag" content="([^"]+)"', h)[:10]
        dur = re.search(r'video:duration" content="(\d+)"', h)
        mins, secs = divmod(int(dur.group(1)) if dur else 0, 60)
        durstr = f"{mins:02d}:{secs:02d}"
        pic = re.search(r'property="og:image" content="([^"]+)"', h)
        vod = {
            "vod_id": vid, "vod_name": name[:80],
            "vod_pic": pic.group(1) if pic else "",
            "vod_year": "", "vod_area": "",
            "vod_class": ",".join(tags),
            "vod_director": "", "vod_actor": ",".join(actors),
            "vod_content": content,
            "vod_remarks": f"{durstr} {srcs[0][1]}",
            "vod_play_from": "$$$".join(l for _, l in srcs),
            "vod_play_url": "$$$".join(f"第1集${u}" for u, _ in srcs)
        }
        return {"list": [vod]}

    def searchContent(self, key, quick=False, pg="1"):
        pn = 1
        try:
            pn = max(int(str(pg)), 1)
        except:
            pass
        try:
            url = f"{HOST}/zh/search/{quote(key)}/" if pn <= 1 else f"{HOST}/zh/search/{quote(key)}/{pn}/"
            r = self.fetch(url, headers={"User-Agent": UA}, timeout=30000)
            h = r.text if hasattr(r, 'text') else str(r)
            return {"list": self._items(h)}
        except:
            return {"list": []}

    def playerContent(self, flag, id, vipFlags=None):
        u = str(id) if id else str(flag)
        if not u.startswith('http'):
            return {"url": ""}
        m = re.search(r'/(\d+)_\d+m\.mp4/', u) or re.search(r'/zh/videos/(\d+)/', u)
        vid = m.group(1) if m else ''
        try:
            if self._sess is None:
                self._sess = requests.Session()
                self._sess.headers.update({"User-Agent": UA})
            pinfo = self._pinfo
            if not pinfo or pinfo[0] != vid or (pinfo[3] and (time.time() - pinfo[3]) > 60):
                try:
                    r = self._sess.get(f"{HOST}/zh/videos/{vid}/x/", timeout=20000)
                    h = r.text if hasattr(r, 'text') else str(r)
                    srcs = re.findall(r"<source src='([^']+)'[^>]*label=\"([^\"]+)\"", h)
                    if srcs:
                        ck = '; '.join(f"{k}={v}" for k, v in self._sess.cookies.items())
                        self._pinfo = (vid, srcs, ck, time.time())
                        pinfo = self._pinfo
                except:
                    pass
            if pinfo and pinfo[0] == vid:
                url = u
                for su, lab in pinfo[1]:
                    if ('1080p' if lab == '2160p' else lab) == flag:
                        url = su
                        break
                return {"parse": 0, "url": url, "header": {"Cookie": pinfo[2]}}
        except:
            pass
        return {"url": u}

    def localProxy(self, param):
        return []

    def _pagecount(self, html, current_page=1):
        m = re.search(r'class="last"><a href="[^"]*?/(\d+)/"', html)
        if m:
            return int(m.group(1))
        pages = re.findall(r'<li class="page"><a href="[^"]*?/(\d+)/"', html)
        max_page = current_page
        for p in pages:
            try:
                n = int(p)
                if n > max_page:
                    max_page = n
            except:
                pass
        if re.search(r'class="next"', html) and max_page <= current_page + 5:
            max_page = current_page + 5
        return max_page

    def _items(self, html):
        if '找不到网页' in html or 'Page not Found' in html:
            return []
        items, seen = [], set()
        starts = [m.start() for m in re.finditer(r'<div class="item">', html)]
        for i, st in enumerate(starts):
            en = starts[i + 1] if i + 1 < len(starts) else len(html)
            blk = html[st:en]
            m = re.search(r'<a href="[^"]*/zh/videos/(\d+)/[^"]*"[^>]*title="([^"]*)"', blk)
            if not m:
                continue
            vid, name = m.group(1), m.group(2).strip()
            if not vid or not name or vid in seen:
                continue
            seen.add(vid)
            pic = re.search(r'(?:data-src|src)="(https://img[^"]+)"', blk)
            dur = re.search(r'class="duration"[^>]*>([^<]+)<', blk)
            q = re.search(r'class="quality"[^>]*>([^<]+)<', blk)
            d = dur.group(1).strip() if dur else ""
            tm = re.search(r'(\d+:\d+)', d)
            rem = (q.group(1).strip() if q else "") + (" " + (tm.group(1) if tm else d) if d else "")
            items.append({
                "vod_id": vid,
                "vod_name": name[:60],
                "vod_pic": pic.group(1) if pic else "",
                "vod_remarks": rem.strip(),
            })
        return items