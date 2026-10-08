# -*- coding: utf-8 -*-
import sys, re, json
from urllib.parse import quote, unquote
from html import unescape

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

HOST = "https://82729mka.jzac401.vip:8751"
PIC = "https://wstgpic.bdpsjp.com"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
CATEGORIES = {"10": "国产", "11": "传媒", "12": "日韩", "14": "无码", "15": "欧美", "16": "动漫", "18": "主播", "19": "同性", "20": "三级", "21": "黑白"}
_DEC = {'e': 'P', 'w': 'D', 'T': 'y', '+': 'J', 'l': '!', 't': 'L', 'E': 'E', '@': '2', 'd': 'a', 'b': '%', 'q': 'l', 'X': 'v', '~': 'R', '5': 'r', '&': 'X', 'C': 'j', ']': 'F', 'a': ')', '^': 'm', ',': '~', '}': '1', 'x': 'C', 'c': '(', 'G': '@', 'h': 'h', '.': '*', 'L': 's', '=': ',', 'p': 'g', 'I': 'Q', '1': '7', '_': 'u', 'K': '6', 'F': 't', '2': 'n', '8': '=', 'k': 'G', 'Z': ']', ')': 'b', 'P': '}', 'B': 'U', 'S': 'k', '6': 'i', 'g': ':', 'N': 'N', 'i': 'S', '%': '+', '-': 'Y', '?': '|', '4': 'z', '*': '-', '3': '^', '[': '{', '(': 'c', 'u': 'B', 'y': 'M', 'U': 'Z', 'H': '[', 'z': 'K', '9': 'H', '7': 'f', 'R': 'x', 'v': '&', '!': ';', 'M': '_', 'Q': '9', 'Y': 'e', 'o': '4', 'r': 'A', 'm': '.', 'O': 'o', 'V': 'W', 'J': 'p', 'f': 'd', ':': 'q', '{': '8', 'W': 'I', 'j': '?', 'n': '5', 's': '3', '|': 'T', 'A': 'V', 'D': 'w', ';': 'O'}

def _dec(s):
    return unescape(''.join(_DEC.get(c, c) for c in (s or '')))

def _pic(serial):
    return f"http://127.0.0.1:9978/proxy?do=juzi&serial={quote(serial or '')}"

class Spider(Spider):
    def init(self, extend=""):
        self.headers = {"User-Agent": UA, "Referer": HOST + "/"}

    def homeContent(self, filter=False):
        return {"class": [{"type_id": k, "type_name": v} for k, v in CATEGORIES.items()], "list": []}

    def homeVideoContent(self):
        try:
            r = self.fetch(HOST + "/index.json?260211&", headers=self.headers, timeout=15000)
            j = json.loads(r.text if hasattr(r, 'text') else str(r))
            out = []
            for c in (j.get('index_videos') or {}).values():
                if isinstance(c, dict):
                    out.extend(c.get('videos') or [])
            return {"list": self._items(out)}
        except:
            return {"list": []}

    def categoryContent(self, tid, pg=1, filter=False, extend=""):
        try:
            pn = max(int(str(pg)), 1)
        except:
            pn = 1
        cat = str(tid)
        if cat not in CATEGORIES:
            cat = "10"
        try:
            r = self.fetch(f"{HOST}/type/{cat}_{pn}.json?260211&", headers=self.headers, timeout=30000)
            j = json.loads(r.text if hasattr(r, 'text') else str(r))
            d = j.get('data') or {}
            return {"page": pn, "pagecount": int(d.get('page_count') or 1), "limit": len(d.get('videos') or []), "total": 0, "list": self._items(d.get('videos') or [])}
        except:
            return {"page": pn, "pagecount": 1, "limit": 14, "total": 0, "list": []}

    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, list) and ids else str(ids)
        m = re.search(r'(\d+)', str(vid))
        vid = m.group(1) if m else ""
        if not vid:
            return {"list": []}
        try:
            r = self.fetch(f"{HOST}/video/{vid}.json?260211&", headers=self.headers, timeout=30000)
            j = json.loads(r.text if hasattr(r, 'text') else str(r))
        except:
            return {"list": []}
        v = j.get('video') or {}
        d = {
            "vod_id": vid, "vod_name": _dec(v.get('title')),
            "vod_pic": _pic(v.get('serial_number')),
            "vod_year": (str(v.get('date') or '')[:4]), "vod_area": "",
            "vod_class": ", ".join(v.get('labels') or [])[:100],
            "vod_director": "", "vod_actor": "", "vod_content": "",
            "vod_remarks": f"{v.get('read_number')}·{v.get('second')}s",
            "vod_play_from": "橘子",
            "vod_play_url": f"{vid}${PIC}/m3u8/{v.get('serial_number')}/index_domain.m3u8?260211"
        }
        return {"list": [d]}

    def searchContent(self, key, quick=False, pg="1"):
        try:
            r = self.fetch(f"{HOST}/search.json?search={quote(key)}", headers=self.headers, timeout=30000)
            j = json.loads(r.text if hasattr(r, 'text') else str(r))
            return {"list": self._items(j.get('videos') or []), "page": 1}
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
            r = self.fetch(f"{HOST}/video/{m.group(1)}.json?260211&", headers=self.headers, timeout=30000)
            j = json.loads(r.text if hasattr(r, 'text') else str(r))
            s = (j.get('video') or {}).get('serial_number')
            return {"url": f"{PIC}/m3u8/{s}/index_domain.m3u8?260211"} if s else {"url": ""}
        except:
            return {"url": ""}

    def localProxy(self, param):
        serial = ''
        for a in (param or '').split('&'):
            if a.startswith('serial='):
                serial = unquote(a[7:])
        if not serial:
            return None
        try:
            r = self.fetch(f"{PIC}/pic/{serial}/thumbnail.css", headers=self.headers, timeout=15000)
            raw = r.content if hasattr(r, 'content') else r.read()
            if not raw:
                return None
            dec = bytes(b ^ 0x88 for b in raw)
            if hasattr(self, 'setContentType'):
                self.setContentType('image/webp')
            return dec
        except:
            return None

    def _pagecount(self, html, current_page=1):
        return 1

    def _items(self, videos):
        items, seen = [], set()
        for v in videos:
            if not isinstance(v, dict):
                continue
            vid = str(v.get('id') or '')
            if not vid or vid in seen:
                continue
            seen.add(vid)
            items.append({
                "vod_id": vid,
                "vod_name": _dec(v.get('title'))[:50],
                "vod_pic": _pic(v.get('serial_number')),
                "vod_remarks": f"{v.get('read_number')}·{v.get('second')}",
            })
        return items
