# -*- coding: utf-8 -*-
import sys
import re
import json
from urllib.parse import urljoin, quote

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

HOST = "https://avgood.com"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

CATEGORIES = {
    "664": "在线视频", "665": "91精选", "511": "有码", "512": "无码", "513": "欧美",
    "804": "麻豆传媒", "673": "三级伦理", "675": "亚洲无码", "676": "亚洲有码",
    "682": "中文字幕", "760": "精品推荐", "761": "国产色情", "762": "主播直播",
    "766": "巨乳美乳", "767": "人妻熟女", "770": "萝莉少女", "776": "日本精品",
    "779": "台湾辣妹", "780": "韩国御姐", "743": "韩国精品", "723": "福利姬",
    "724": "主播大秀", "786": "91探花", "787": "网红流出", "704": "动漫",
    "679": "动漫卡通", "714": "美女写真", "520": "字幕", "521": "高清", "523": "特别福利"
}


class Spider(Spider):
    def init(self, extend=""):
        global HOST
        try:
            r = self.fetch(HOST, headers={"User-Agent": UA}, timeout=15000)
            if hasattr(r, 'url') and r.url and r.url != HOST.rstrip("/"):
                HOST = r.url.rstrip("/")
        except:
            pass

    def homeContent(self, filter=False):
        r = {"class": [], "list": []}
        for k, v in CATEGORIES.items():
            r["class"].append({"type_id": k, "type_name": v})
        return r

    def homeVideoContent(self):
        try:
            r = self.fetch(f"{HOST}/c/664/", headers={"User-Agent": UA}, timeout=30000)
            html = r.text if hasattr(r, 'text') else str(r)
            return {"list": self._items(html)}
        except:
            return {"list": []}

    def categoryContent(self, tid, pg=1, filter=False, extend=""):
        pn = 1
        try:
            pn = max(int(str(pg)), 1)
        except:
            pass
        try:
            url = f"{HOST}/c/{tid}/" if pn <= 1 else f"{HOST}/c/{tid}/{pn}/"
            r = self.fetch(url, headers={"User-Agent": UA}, timeout=30000)
            html = r.text if hasattr(r, 'text') else str(r)
            items = self._items(html)
            return {
                "page": pn,
                "pagecount": self._pagecount(html, pn),
                "limit": 24,
                "total": len(items),
                "list": items
            }
        except:
            return {"page": pn, "pagecount": 1, "limit": 24, "total": 0, "list": []}

    def detailContent(self, ids):
        if isinstance(ids, list):
            vid = ids[0] if ids else ""
        else:
            vid = str(ids) if ids else ""
        m = re.search(r'(\d+)', str(vid))
        vid = m.group(1) if m else ""
        if not vid:
            return {"list": []}
        try:
            r = self.fetch(f"{HOST}/c/{vid}.html", headers={"User-Agent": UA}, timeout=30000)
            h = r.text if hasattr(r, 'text') else str(r)
        except:
            return {"list": []}

        d = {
            "vod_id": vid, "vod_name": "", "vod_pic": "", "vod_year": "",
            "vod_area": "", "vod_class": "", "vod_director": "", "vod_actor": "",
            "vod_content": "", "vod_remarks": "", "vod_play_from": "", "vod_play_url": ""
        }

        tn = re.search(r'<title>(.*?)</title>', h)
        if tn:
            d["vod_name"] = tn.group(1).split("_")[0].strip()

        p = re.search(r'desc-img-box" href="(https?://[^"]+\.(?:jpg|jpeg|png|webp))"', h, re.I)
        if not p:
            p = re.search(r'(?:data-original|src)="(https?://[^"]+\.(?:jpg|jpeg|png|webp))"', h, re.I)
        if not p:
            pp = re.search(r'desc-img-box" href="([^"]+)"', h)
            if pp:
                p = pp
        if p:
            d["vod_pic"] = p.group(1) if p.group(1).startswith("http") else urljoin(HOST, p.group(1))

        cm = re.search(r'<span class="header">类别：</span>([^<]+)<', h)
        if cm:
            d["vod_class"] = cm.group(1).strip()
        rm = re.search(r'<span class="header">时长：</span>([^<]+)<', h)
        if rm:
            d["vod_remarks"] = rm.group(1).strip()

        desc_m = re.search(r'内容简介</h4>([\s\S]*?)</div>\s*</div>\s*</div>', h)
        if desc_m:
            d["vod_content"] = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', desc_m.group(1))).strip()[:500]

        d["vod_play_from"] = "avgood"
        d["vod_play_url"] = f"在线播放${urljoin(HOST, f'/c/{vid}.html')}"
        pid = re.search(r'<iframe[^>]*class="video-iframe"[^>]*src="([^"]+)"', h)
        if not pid:
            mags = re.findall(r'<a class="magnet-link"[^>]*href="(magnet:[^"]+)"[^>]*>\s*<span class="magnet-text">([^<]*)</span>', h)
            if mags:
                sizes = re.findall(r'magnet-size">([^<]*)<', h)
                froms, urls = [], []
                parts = []
                for i, (url, name) in enumerate(mags[:10]):
                    nm = re.sub(r'[$#|]', ' ', name.strip())[:30]
                    if nm.startswith("magnet:"):
                        mh = re.search(r'btih:([0-9A-Fa-f]{40})', url)
                        nm = mh.group(1)[-8:].upper() if mh else nm[:20]
                    if i < len(sizes) and sizes[i].strip():
                        nm += f' [{sizes[i].strip()}]'
                    if '&dn=' in url:
                        base, dn = url.split('&dn=', 1)
                        url = base + '&dn=' + quote(dn)
                    parts.append(f"{nm}${url}")
                froms.append("磁力")
                urls.append("#".join(parts))
                tr = re.search(r'href="([^"]+\.torrent)"', h)
                if tr:
                    froms.append("种子")
                    urls.append(f"种子下载${urljoin(HOST, tr.group(1))}")
                d["vod_play_from"] = "$$$".join(froms)
                d["vod_play_url"] = "$$$".join(urls)
        return {"list": [d]}

    def searchContent(self, key, quick=False, pg="1"):
        try:
            url = f"{HOST}/c/s/?q={quote(key)}"
            r = self.fetch(url, headers={"User-Agent": UA}, timeout=30000)
            html = r.text if hasattr(r, 'text') else str(r)
            return {"list": self._items(html)}
        except:
            return {"list": []}

    def playerContent(self, flag, id, vipFlags=None):
        url = str(id) if id else str(flag)
        if url.startswith("magnet:"):
            return {"url": url}
        if url.endswith(".torrent"):
            return {"url": url}
        if url.startswith("http") and (".m3u8" in url or ".mp4" in url):
            return {"url": url}
        if url.startswith("http"):
            full_url = url
        else:
            if not url.startswith("/"):
                url = "/" + url
            full_url = urljoin(HOST, url)
        try:
            r = self.fetch(full_url, headers={"User-Agent": UA}, timeout=30000)
            h = r.text if hasattr(r, 'text') else str(r)
        except:
            return {"url": ""}
        pid = re.search(r'<iframe[^>]*class="video-iframe"[^>]*src="([^"]+)"', h)
        if not pid:
            return {"url": ""}
        src = pid.group(1)
        if not src.startswith("http"):
            src = urljoin(HOST, src)
        try:
            r = self.fetch(src, headers={"User-Agent": UA}, timeout=15000)
            play_url = r.url if hasattr(r, 'url') and r.url else src
        except:
            play_url = src
        try:
            r = self.fetch(play_url, headers={"User-Agent": UA}, timeout=30000)
            ph = r.text if hasattr(r, 'text') else str(r)
        except:
            return {"url": ""}
        m = re.search(r'ajax_url\s*=\s*([^\s;]+)', ph)
        if not m:
            return {"url": ""}
        ajax = m.group(1).strip().strip("'\"")
        if not ajax.startswith("http"):
            ajax = urljoin(HOST, ajax)
        try:
            r = self.fetch(ajax, headers={"User-Agent": UA}, timeout=30000)
            data = r.text if hasattr(r, 'text') else str(r)
            d = json.loads(data)
            play_url = d.get("playlink", "")
            if play_url:
                play_url = play_url.replace("\\/", "/")
                if play_url.startswith("/"):
                    play_url = urljoin(HOST, play_url)
                return {"url": play_url}
        except:
            pass
        return {"url": ""}

    def localProxy(self, param):
        pass

    def _pagecount(self, html, current_page=1):
        m = re.search(r'page-total">(\d+)<', html)
        if m:
            return int(m.group(1))
        pages = re.findall(r'href="/c/\d+/(\d+)/"', html)
        max_page = current_page
        for p in pages:
            try:
                n = int(p)
                if n > max_page:
                    max_page = n
            except:
                pass
        has_next = re.search(r'class="page-btn page-next"', html)
        if has_next and max_page <= current_page + 5:
            max_page = current_page + 5
        return max_page

    def _items(self, html):
        items, seen = [], set()
        for m in re.finditer(r'<a class="card" href="/c/(\d+)\.html">(.*?)</a>', html, re.S):
            vid = m.group(1)
            if vid in seen:
                continue
            block = m.group(2)
            nm = re.search(r'<h3 class="card-title">\s*<b>(.*?)</b>', block, re.S)
            name = re.sub(r'<[^>]+>', '', nm.group(1)).strip() if nm else ""
            if not name or len(name) > 100:
                continue
            cover = re.search(r'data-original="([^"]+)"', block)
            pic = cover.group(1) if cover else ""
            if pic and pic.startswith("/"):
                pic = urljoin(HOST, pic)
            tags = re.findall(r'class="tag tag-category"[^>]*>([^<]*)<', block)
            remark = ",".join(t.strip() for t in tags)
            if "今日新种" in block:
                remark = (remark + " 新种").strip()
            du = re.search(r'\[(\d+:\d+)\]', name)
            if du:
                remark = (remark + " " + du.group(1)).strip()
            seen.add(vid)
            items.append({
                "vod_id": vid,
                "vod_name": name[:50],
                "vod_pic": pic,
                "vod_remarks": remark,
            })
        if not items:
            for m in re.finditer(r'<div class="result-card">(.*?)</div>\s*</div>', html, re.S):
                block = m.group(1)
                link = re.search(r'href="/c/(\d+)\.html"', block)
                if not link:
                    continue
                vid = link.group(1)
                if vid in seen:
                    continue
                nm = re.search(r'<h3 class="result-title">\s*<a[^>]*>(.*?)</a>', block, re.S)
                name = re.sub(r'<[^>]+>', '', nm.group(1)).strip() if nm else ""
                if not name or len(name) > 100:
                    continue
                cover = re.search(r'<img src="([^"]+)"', block)
                pic = cover.group(1) if cover else ""
                if pic and pic.startswith("/"):
                    pic = urljoin(HOST, pic)
                date = re.search(r'result-date">([^<]*)<', block)
                remark = date.group(1).strip() if date else ""
                seen.add(vid)
                items.append({
                    "vod_id": vid,
                    "vod_name": name[:50],
                    "vod_pic": pic,
                    "vod_remarks": remark,
                })
        return items