# -*- coding: utf-8 -*-
"""
快活林 - 四壳通用Python Spider
站点: https://xkb.khl4.xyz
"""

import re, json, urllib.request, urllib.parse, urllib.error

try:
    from base.spider import Spider
except Exception:
    class Spider:
        def __init__(self): self.extend = {}
        def init(self, extend): self.extend = extend if isinstance(extend, dict) else {}
        def isVideoFormat(self, url): return any(url.lower().endswith(ext) for ext in ['.m3u8','.mp4','.flv','.ts'])
        def homeContent(self, filter): return {}
        def categoryContent(self, tid, pg, filter, extend): return {}
        def detailContent(self, ids): return {}
        def searchContent(self, key, quick, pg): return {}
        def playerContent(self, flag, id, vipFlags): return {}
        def localProxy(self, param): return [404, "text/plain", ""]
        def getDependence(self): return ""
        def destroy(self): pass

class Spider(Spider):
    domain = "https://xkb.khl4.xyz"
    siteName = "快活林"
    CATEGORIES = [("20","亚洲情色"),("21","制服师生"),("22","卡通动漫"),("23","三级伦理"),("24","强奸乱伦"),("25","偷拍自拍"),("26","中文字幕"),("27","欧美性爱"),("28","人妻熟女"),("29","无码专区")]
    UA_CHROME = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    
    def __init__(self):
        super().__init__()
        self.extend = {}
    
    def init(self, extend=""):
        if isinstance(extend, dict): self.extend = extend
        elif isinstance(extend, str) and extend.strip():
            try: self.extend = json.loads(extend)
            except: self.extend = {}
        else: self.extend = {}
    
    def getDependence(self): return ""
    def destroy(self): pass
    
    def _fetch(self, url, timeout=20):
        headers = {"User-Agent": self.UA_CHROME, "Referer": self.domain + "/"}
        try:
            req = urllib.request.Request(url, headers=headers)
            resp = urllib.request.urlopen(req, timeout=timeout)
            return resp.read().decode("utf-8", errors="replace")
        except: return ""
    
    def _strip_tags(self, html):
        return re.sub(r"<[^>]+>", "", html).strip() if html else ""
    
    def _parse_list(self, html):
        videos = []
        seen = set()
        
        # 找所有article标签
        articles = re.findall(r'<article[^>]*>(.*?)</article>', html, re.S)
        for art in articles:
            m = re.search(r'href="/(\d+)\.html"', art)
            if not m: continue
            vid = m.group(1)
            if vid in seen or len(vid) < 5: continue
            seen.add(vid)
            
            # 标题
            name = ""
            t = re.search(r'<h4><a[^>]*>(.*?)</a></h4>', art, re.S)
            if t:
                name = re.sub(r'<[^>]+>', '', t.group(1)).strip()
            if not name or len(name) < 2: continue
            
            # 封面
            pic = ""
            p = re.search(r'<img[^>]*src="([^"]+\.(?:jpg|jpeg|png))"', art)
            if p: pic = p.group(1)
            
            videos.append({"vod_id": vid, "vod_name": name, "vod_pic": pic, "vod_remarks": ""})
        
        return videos

    def homeContent(self, filter=False):
        return {"class": [{"type_id": c[0], "type_name": c[1]} for c in self.CATEGORIES], "filters": {}}
    
    def categoryContent(self, tid, pg, filter=False, extend=None):
        pg = int(pg) if pg else 1
        url = f"{self.domain}/vodtype/{tid}.html"
        if pg > 1: url = f"{self.domain}/vodtype/{tid}-{pg}.html"
        html = self._fetch(url)
        videos = self._parse_list(html)
        return {"page": pg, "pagecount": pg, "limit": 30, "total": len(videos), "list": videos}
    
    def detailContent(self, ids):
        if isinstance(ids, str): ids = [ids]
        if not isinstance(ids, (list, tuple)): ids = [str(ids)]
        result = []
        for vid in ids:
            try:
                vid = str(vid).strip()
                html = self._fetch(f"{self.domain}/{vid}.html")
                if not html: continue
                m3u8 = ""
                m = re.search(r'(?:const|let|var)\s+rawUrl\s*=\s*[\'"]([^\'"]+)[\'"]', html, re.I)
                if m: m3u8 = m.group(1)
                if not m3u8:
                    for x in re.findall(r'https?://[^\s"\'\\]+\.m3u8[^\s"\'\\]*', html):
                        if 'sharer' not in x and 'balecao' not in x: m3u8 = x; break
                if not m3u8: continue
                name = f"视频{vid}"
                t = re.search(r'<title>(.*?)</title>', html, re.S)
                if t:
                    name = self._strip_tags(t.group(1))
                    name = re.sub(r'^.*?-', '', name).strip()
                pic = ""
                p = re.search(r'(?:data-original|data-src|src)="([^"]+\.(?:jpg|jpeg|png))"', html)
                if p: pic = p.group(1)
                result.append({"vod_id": vid, "vod_name": name, "vod_pic": pic, "vod_remarks": self.siteName, "vod_actor": "", "vod_director": "", "vod_content": "", "vod_year": "", "vod_area": "", "vod_tags": "", "vod_douban_score": "", "vod_play_from": self.siteName, "vod_play_url": f"第1集${m3u8}"})
            except: continue
        return {"list": result}
    
    def searchContent(self, key, quick=False, pg=1):
        return {"page": pg, "pagecount": 0, "limit": 30, "total": 0, "list": []}
    
    def playerContent(self, flag, id, vipFlags=None):
        return {"parse": 0, "jx": 0, "url": id, "header": {"User-Agent": self.UA_CHROME}}
    
    def localProxy(self, param):
        if not param or "do" not in param: return [404, "text/plain", ""]
        if param.get("do") == "ck":
            try:
                req = urllib.request.Request(param.get("url",""), headers={"User-Agent": self.UA_CHROME})
                resp = urllib.request.urlopen(req, timeout=15)
                return [200, resp.headers.get("Content-Type","image/jpeg"), resp.read()]
            except: pass
        return [404, "text/plain", ""]

if __name__ == "__main__":
    sp = Spider()
    sp.init("{}")
    print("="*60)
    print(f"{sp.siteName} Spider 自测")
    print("="*60)
    print(f"\n[1] homeContent: 分类数={len(sp.CATEGORIES)}")
    for c in sp.CATEGORIES: print(f"  {c[0]:5s}  {c[1]}")
    print(f"\n[2] categoryContent (id={sp.CATEGORIES[0][0]}, page=1):")
    cat = sp.categoryContent(sp.CATEGORIES[0][0], 1)
    print(f"  视频数: {len(cat.get('list', []))}")
    for v in cat.get("list", [])[:2]: print(f"    {v['vod_id']}: {v['vod_name'][:40]}")
    if cat.get("list"):
        d = sp.detailContent([cat["list"][0]["vod_id"]])
        if d.get("list"):
            print(f"\n[3] detailContent:")
            print(f"  标题: {d['list'][0]['vod_name'][:50]}")
            print(f"  播放: {d['list'][0]['vod_play_url'][:100]}")
    print("\n自测完成!")
