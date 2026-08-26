#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
123AV.FUN TVBox Spider 源
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
站点结构:
- 首页: /  → 视频列表, 每页约100个
- 分页: /page-{n}
- 详情: /detail/{id}-{slug} → JSON-LD contentUrl 直链 m3u8
- 搜索: /search?keyword={关键词}
- 排序: /publish-time/sort-desc, /view-count/sort-desc 等
- 播放: JSON-LD 直链 m3u8, 无防盗链
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import re, json, urllib.request, urllib.parse, ssl

BASE_URL = "https://123av.fun"
UA = "Mozilla/5.0 (Linux; Android 12; Pixel 6) AppleWebKit/537.36"

# 一级分类用排序方式
TYPE_MAP = {
    "publish-time": "最新发布",
    "view-count": "最多播放",
    "comment-count": "最多评论",
    "favorite-count": "最多收藏",
}

# 网络
_has_cs = False
try:
    import cloudscraper
    _scraper = cloudscraper.create_scraper(browser={'browser':'chrome','platform':'android','desktop':False})
    _has_cs = True
except Exception:
    pass

def _get(url, timeout=20):
    if _has_cs:
        try:
            resp = _scraper.get(url, timeout=timeout, headers={
                "User-Agent": UA, "Accept": "text/html,*/*;q=0.8", "Referer": BASE_URL + "/",
            })
            return resp.text
        except Exception:
            pass
    try:
        ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*;q=0.8", "Referer": BASE_URL + "/"})
        resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
        return resp.read().decode("utf-8", errors="replace")
    except Exception:
        return ""

def _fetch_page(path): return _get(BASE_URL + path)

def _extract_vod_cards(html):
    """提取视频卡片: data-* 属性"""
    items = []; seen = set()
    for m in re.finditer(r'<a[^>]*href="/detail/(\d+)[^"]*"[^>]*>(.*?)</a>', html, re.DOTALL):
        vid = m.group(1)
        if vid in seen: continue
        seen.add(vid)
        inner = m.group(2)
        # 标题: 从 xwya-video alt 取
        name = ""
        alt = re.search(r'alt="([^"]+)"', inner)
        if alt: name = alt.group(1)
        if not name:
            text = re.sub(r'<[^>]+>', '', inner).strip()
            text = re.sub(r'\s+', ' ', text)
            name = text[:40]
        # 图片: data-poster
        pic = ""
        poster = re.search(r'data-poster="([^"]+)"', inner)
        if poster: pic = poster.group(1)
        if not pic:
            img = re.search(r'poster="([^"]+)"', inner)
            if img: pic = img.group(1)
        items.append({"id": vid, "name": name, "pic": pic})
    return items

def _extract_detail(html):
    info = {}
    m = re.search(r'"contentUrl"\s*:\s*"([^"]+)"', html)
    if m: info["play_url"] = m.group(1)
    m = re.search(r'"thumbnailUrl"\s*:\s*"([^"]+)"', html)
    if m: info["pic"] = m.group(1)
    m = re.search(r'"name"\s*:\s*"([^"]+)"', html)
    if m: info["name"] = m.group(1)
    if not info.get("name"):
        m = re.search(r'<title>([^<]+)</title>', html)
        if m: info["name"] = m.group(1).replace(" - 123AV.FUN", "").strip()
    return info

def _norm_ids(ids):
    if ids is None: return []
    if isinstance(ids, str):
        try: p = json.loads(ids); return [str(x) for x in p] if isinstance(p, list) else [ids.strip()]
        except: pass
        return [ids.strip()]
    if isinstance(ids, (list, tuple)): return [str(i) for i in ids]
    return [str(ids)]

class Spider:
    def getDependence(self): return []
    def init(self, extend=""):
        self.extend = {}
        if extend:
            try: self.extend = json.loads(extend) if isinstance(extend, str) else dict(extend)
            except: pass
    def getName(self): return "123AV"

    def homeContent(self, filter=None):
        return {"class": [{"type_id": tid, "type_name": name} for tid, name in TYPE_MAP.items()], "filters": {}}

    def homeVideoContent(self):
        html = _fetch_page("/")
        items = _extract_vod_cards(html)
        return {"list": [{"vod_id": it["id"], "vod_name": it["name"], "vod_pic": it.get("pic",""), "type_name":"", "vod_remarks":""} for it in items[:50]]}

    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        pg = int(pg) if pg else 1
        sort = str(tid)
        if pg <= 1:
            path = f"/{sort}/sort-desc"
        else:
            path = f"/page-{pg}"
        html = _fetch_page(path)
        items = _extract_vod_cards(html)
        # 检测是否有下一页
        has_next = f'page-{pg+1}' in html
        pagecount = pg + 1 if has_next else pg
        return {
            "list": [{"vod_id": it["id"], "vod_name": it["name"], "vod_pic": it.get("pic",""), "type_name": "", "vod_remarks": ""} for it in items],
            "page": pg, "pagecount": pagecount, "limit": 50, "total": 0,
        }

    def detailContent(self, ids):
        ids = _norm_ids(ids)
        if not ids: return {"list": []}
        vid = ids[0]
        # /detail/{id} 自动重定向到完整 URL
        html = _fetch_page(f"/detail/{vid}")
        if not html: return {"list": []}
        info = _extract_detail(html)
        return {"list": [{
            "vod_id": vid, "vod_name": info.get("name", "未知"),
            "vod_pic": info.get("pic", ""),
            "type_name": "", "vod_year": "", "vod_area": "", "vod_remarks": "",
            "vod_actor": "", "vod_director": "", "vod_content": "",
            "vod_play_from": "在线播放", "vod_play_url": f"正片${vid}",
        }]}

    def searchContent(self, key, quick=False, pg=1):
        try:
            kw = urllib.parse.quote(str(key))
            html = _fetch_page(f"/search?keyword={kw}")
            items = _extract_vod_cards(html)
            return {"list": [{"vod_id": it["id"], "vod_name": it["name"], "vod_pic": it.get("pic",""), "type_name": "", "vod_remarks": ""} for it in items[:20]]}
        except Exception:
            return {"list": []}

    def playerContent(self, flag, ids, vipFlags=None):
        vid = str(ids).split("@")[0]
        html = _fetch_page(f"/detail/{vid}")
        if not html: return {"parse": 0, "playUrl": "", "header": {}}
        play_url = ""
        m = re.search(r'"contentUrl"\s*:\s*"([^"]+)"', html)
        if m: play_url = m.group(1)
        return {"parse": 0, "playUrl": play_url, "header": {"User-Agent": UA, "Referer": BASE_URL + "/"}}

    def localProxy(self, param): return [200, "text/plain", b"", {}]
    def action(self, action): return {"code": 200, "content": "", "type": "text/plain"}
    def manualVideoCheck(self): return True
    def destroy(self): pass

# 测试
if __name__ == "__main__":
    sp = Spider(); sp.init()
    print("=" * 50)
    print(f"名称: {sp.getName()}")
    r = sp.homeContent()
    print(f"  class: {len(r['class'])}")
    r = sp.homeVideoContent()
    print(f"  home列表: {len(r['list'])}")
    if r['list']: print(f"  首项: {r['list'][0]['vod_name'][:20]} id={r['list'][0]['vod_id']}")
    r = sp.categoryContent("publish-time")
    print(f"  category: {len(r['list'])} pagecount={r['pagecount']}")
    r = sp.searchContent("自慰")
    print(f"  搜索: {len(r['list'])} 项")
    print("✅ 测试完成")