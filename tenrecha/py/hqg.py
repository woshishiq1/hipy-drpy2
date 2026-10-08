# -*- coding: utf-8 -*-
import sys, re
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

HOST = "https://hqg.ndmt3.life"
BASE = "/cn/home/web"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
CATEGORIES = {"20": "日韩", "21": "偷拍", "22": "无码", "23": "自拍", "24": "巨乳", "25": "华人", "26": "嫩模", "27": "剧情", "28": "动漫"}

class Spider(Spider):
    def init(self, extend=""):
        self.headers = {"User-Agent": UA, "Referer": HOST + "/"}

    def homeContent(self, filter=False):
        return {"class": [{"type_id": k, "type_name": v} for k, v in CATEGORIES.items()], "list": []}

    def homeVideoContent(self):
        try:
            r = self.fetch(HOST + BASE + "/", headers=self.headers, timeout=15000)
            return {"list": self._items(r.text if hasattr(r, 'text') else str(r))}
        except:
            return {"list": []}

    def categoryContent(self, tid, pg=1, filter=False, extend=""):
        try:
            pn = max(int(str(pg)), 1)
        except:
            pn = 1
        cat = str(tid)
        if cat not in CATEGORIES:
            cat = "20"
        try:
            r = self.fetch(f"{HOST}{BASE}/index.php/vod/type/id/{cat}/page/{pn}.html", headers=self.headers, timeout=30000)
            h = r.text if hasattr(r, 'text') else str(r)
            items = self._items(h)
            pcs = [int(x) for x in re.findall(r'/vod/type/id/' + cat + r'/page/(\d+)\.html', h) if x.isdigit()]
            pc = max(pcs) if pcs else 1
            return {"page": pn, "pagecount": pc, "limit": len(items), "total": 0, "list": items}
        except:
            return {"page": pn, "pagecount": 1, "limit": 0, "total": 0, "list": []}

    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, list) and ids else str(ids)
        m = re.search(r'(\d+)', str(vid))
        vid = m.group(1) if m else ""
        if not vid:
            return {"list": []}
        try:
            r = self.fetch(f"{HOST}{BASE}/index.php/vod/play/id/{vid}/sid/1/nid/1.html", headers=self.headers, timeout=30000)
            h = r.text if hasattr(r, 'text') else str(r)
        except:
            return {"list": []}
        d = {
            "vod_id": vid, "vod_name": "", "vod_pic": "", "vod_year": "",
            "vod_area": "", "vod_class": "", "vod_director": "", "vod_actor": "",
            "vod_content": "", "vod_remarks": "", "vod_play_from": "高清", "vod_play_url": ""
        }
        tn = re.search(r'<title>([^<]+)</title>', h)
        if tn:
            d["vod_name"] = re.sub(r'\s*第\d+集$', '', tn.group(1).split('-')[0].replace("在线播放", "").strip())
        pm = re.search(r'player_data\s*=\s*(\{[^;]+\})', h)
        if pm:
            pu = re.search(r'"url"\s*:\s*"([^"]+)"', pm.group(1))
            if pu:
                d["vod_play_url"] = "1$" + pu.group(1).replace('\\/', '/')
        im = re.search(r'<img[^>]+src="(https?://[^"]+/upload/vod/[^"]+)"', h)
        if im:
            d["vod_pic"] = im.group(1)
        return {"list": [d]}

    def searchContent(self, key, quick=False, pg="1"):
        try:
            r = self.fetch(f"{HOST}{BASE}/index.php/vod/search.html?wd={quote(key)}", headers=self.headers, timeout=30000)
            return {"list": self._items(r.text if hasattr(r, 'text') else str(r)), "page": 1}
        except:
            return {"list": []}

    def playerContent(self, flag, id, vipFlags=None):
        url = str(id) if id else str(flag)
        if url.startswith('http'):
            return {"url": url}
        m = re.search(r'(\d+)', url)
        if not m:
            return {"url": ""}
        try:
            r = self.fetch(f"{HOST}{BASE}/index.php/vod/play/id/{m.group(1)}/sid/1/nid/1.html", headers=self.headers, timeout=30000)
            h = r.text if hasattr(r, 'text') else str(r)
            pm = re.search(r'player_data\s*=\s*(\{[^;]+\})', h)
            if pm:
                pu = re.search(r'"url"\s*:\s*"([^"]+)"', pm.group(1))
                if pu:
                    return {"url": pu.group(1).replace('\\/', '/')}
        except:
            pass
        return {"url": ""}

    def localProxy(self, param):
        return None

    def _pagecount(self, html, current_page=1):
        return 1

    def _items(self, html):
        items, seen = [], set()
        pat = re.finditer(r'<a href="([^"]*/vod/play/id/(\d+)/sid/\d+/nid/\d+\.html)"[^>]*class="videoListStyle"([\s\S]*?)</a>', html)
        for m in pat:
            vid = m.group(2)
            if vid in seen:
                continue
            seg = m.group(3)
            name = re.search(r'class="title">([^<]+)</p>', seg)
            img = re.search(r'<img[^>]+src="(https?://[^"]+)"', seg)
            cnt = re.search(r'class="one">([^<]+)</p>', seg)
            tag = re.search(r'class="three">([^<]+)</p>', seg)
            rm = (cnt.group(1).strip() if cnt else "") + ("·" + tag.group(1).strip() if tag else "")
            seen.add(vid)
            items.append({
                "vod_id": vid,
                "vod_name": (name.group(1).strip() if name else "")[:50],
                "vod_pic": img.group(1) if img else "",
                "vod_remarks": rm[:20],
            })
        return items