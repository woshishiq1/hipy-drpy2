#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
撸状元 - lzytv.cfd Spider
站点: https://xn--b33a.lzytv.cfd/vod/index.php
"""
import re, json, base64, html as html_mod
from urllib.parse import quote, unquote, urljoin

try:
    import requests
    import urllib3
    urllib3.disable_warnings()
except ImportError:
    requests = None

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        def init(self, extend=""): self.extend = extend
        def homeContent(self, filter): return {"class": [], "filters": {}}
        def homeVideoContent(self): return {"list": []}
        def categoryContent(self, tid, pg, filter, extend):
            return {"list": [], "page": 1, "pagecount": 1, "limit": 24, "total": 0}
        def detailContent(self, ids): return {"list": []}
        def playerContent(self, flag, id, vipFlags=None):
            return {"parse": 0, "playUrl": "", "url": "", "header": {}}
        def searchContent(self, key, quick, pg="1"):
            return {"list": [], "page": 1, "pagecount": 1, "limit": 24, "total": 0}
        def isVideoFormat(self, url): return False
        def manualVideoCheck(self): return False
        def localProxy(self, param): return [404, "text/plain", b""]


def _page(pg):
    try:
        v = int(str(pg or "").strip())
        return v if v > 0 else 1
    except Exception:
        return 1


def fix_url(url, host):
    if not url:
        return ""
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return urljoin(host, url)
    if url.startswith("http"):
        return url
    return urljoin(host, url)


class Spider(BaseSpider):
    def __init__(self):
        super().__init__()
        self.host = "https://xn--b33a.lzytv.cfd"
        self.base = self.host + "/vod/index.php"
        self.name = "撸状元"
        self.sourceKey = "lzytv"
        self.s = requests.Session() if requests else None
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.base,
        }
        if self.s:
            self.s.headers.update(self.headers)
            self.s.verify = False
        self.timeout = 15
        # 分类映射
        self.classes = [
            {"type_id": "10082", "type_name": "国产"},
            {"type_id": "10083", "type_name": "传媒"},
            {"type_id": "10084", "type_name": "黑料"},
            {"type_id": "10085", "type_name": "欧美"},
            {"type_id": "10086", "type_name": "动漫"},
            {"type_id": "10087", "type_name": "有码"},
            {"type_id": "10088", "type_name": "无码"},
            {"type_id": "10089", "type_name": "字幕"},
            {"type_id": "10090", "type_name": "巨乳美乳"},
            {"type_id": "10091", "type_name": "人妻熟女"},
            {"type_id": "10092", "type_name": "强奸乱伦"},
            {"type_id": "10093", "type_name": "制服丝袜"},
        ]

    def init(self, extend=""):
        if not extend:
            return
        try:
            cfg = json.loads(extend) if isinstance(extend, str) else extend
            if isinstance(cfg, dict):
                h = cfg.get("host") or cfg.get("HOST") or ""
                if h:
                    self.host = h.rstrip("/")
                    self.base = self.host + "/vod/index.php"
        except Exception:
            pass

    def getName(self): return self.name
    def getDependence(self): return []
    def homeLayout(self): return 0
    def getHomeContent(self, f=False): return self.homeContent(f)
    def destroy(self):
        try:
            if self.s: self.s.close()
        except Exception:
            pass
    def isVideoFormat(self, u):
        return any(x in str(u).lower() for x in [".m3u8", ".mp4", ".m4v", ".flv", ".webm", ".ts"])
    def manualVideoCheck(self): return False
    def localProxy(self, param): return [404, "text/plain", b""]

    def _fetch(self, url):
        if not self.s:
            return ""
        merged = dict(self.headers)
        merged["Referer"] = self.base
        try:
            r = self.s.get(url, headers=merged, timeout=self.timeout)
            if r.status_code == 200:
                try:
                    r.encoding = r.apparent_encoding or "utf-8"
                except Exception:
                    r.encoding = "utf-8"
                return r.text
        except Exception:
            pass
        return ""

    def homeContent(self, filter):
        return {"class": self.classes, "filters": {}}

    def homeVideoContent(self):
        """首页即列表，直接用首页html"""
        return self.categoryContent("0", "1", False, {})

    def categoryContent(self, tid, pg, filter, extend):
        page = _page(pg)
        result = {"list": [], "page": page, "pagecount": 1, "limit": 24, "total": 0}

        if tid == "0":
            # 首页
            url = self.base
        else:
            url = f"{self.base}?class={tid}&page={page}"
        html = self._fetch(url)
        if not html:
            return result

        # 解析 thumb-item 卡片
        # <a class="thumb-item__link" href="...?detail={id}">
        # <img class="lazyload" src="..." original="真实图片URL">
        # <h2 class="thumb-item__title">标题</h2>
        items = re.findall(
            r'<div class="thumb-item[^"]*"[^>]*>.*?'
            r'<a[^>]*href="[^"]*detail=(\d+)"[^>]*>.*?'
            r'<img[^>]*original="([^"]*)"[^>]*>.*?'
            r'thumb-item__title[^>]*>([^<]+)</h2>',
            html, re.S
        )

        seen = set()
        for vid, pic, title in items:
            if vid in seen:
                continue
            seen.add(vid)
            result["list"].append({
                "vod_id": vid,
                "vod_name": html_mod.unescape(title.strip()),
                "vod_pic": fix_url(pic, self.host),
            })

        # 分页（class="fyym" 格式）
        pp = re.findall(r'href="[^"]*page=(\d+)[^"]*"[^>]*>(\d+)</a>', html)
        if not pp:
            pp = re.findall(r'href="[^"]*page=(\d+)[^"]*"[^>]*>(\d+)', html)
        if pp:
            max_p = max(int(n) for _, n in pp)
            result["pagecount"] = max_p

        return result

    def detailContent(self, ids):
        raw_ids = ids if isinstance(ids, (list, tuple)) else [ids]
        vid = str(raw_ids[0] if raw_ids else "").strip()
        if not vid:
            return {"list": []}
        result = {"list": []}
        html = self._fetch(f"{self.base}?detail={vid}")
        if not html:
            return result

        # 标题
        title = ""
        tm = re.search(r"<h1[^>]*>([^<]+)</h1>", html)
        if tm:
            title = html_mod.unescape(tm.group(1).strip())
        if not title:
            tm2 = re.search(r'<title>([^<]+)</title>', html)
            if tm2:
                title = html_mod.unescape(tm2.group(1).strip())

        # 封面
        pic = ""
        pm = re.search(r'<img[^>]*class="[^"]*cover[^"]*"[^>]*src="([^"]*)"', html)
        if not pm:
            pm = re.search(r'<img[^>]+src="([^"]+\.(?:jpg|png|webp))"', html)
        if pm:
            pic = fix_url(pm.group(1), self.host)

        # 提取 m3u8 播放地址
        m3u8_urls = re.findall(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html)

        if m3u8_urls:
            play_from_list = ["默认"]
            ep_parts = []
            for i, url in enumerate(m3u8_urls[:1]):
                ep_parts.append(f"播放${url}")
            play_url_list = ["#".join(ep_parts)]
        else:
            play_from_list = ["默认"]
            play_url_list = [f"正片${vid}"]

        result["list"].append({
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic,
            "vod_play_from": "$$$".join(play_from_list),
            "vod_play_url": "$$$".join(play_url_list),
        })
        return result

    def playerContent(self, flag, id, vipFlags=None):
        result = {"parse": 0, "playUrl": "", "url": "", "header": {}}
        pid = str(id or "").strip()
        if not pid:
            return result

        if self.isVideoFormat(pid):
            result["url"] = pid
            result["header"] = {
                "User-Agent": self.headers.get("User-Agent", ""),
                "Referer": self.base
            }
            return result

        # 去详情页取m3u8
        html = self._fetch(f"{self.base}?detail={pid}")
        if html:
            mm = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html)
            if mm:
                result["url"] = mm.group(1)
                result["header"] = {
                    "User-Agent": self.headers.get("User-Agent", ""),
                    "Referer": self.base
                }
                return result

        result["url"] = pid
        return result

    def searchContent(self, key, quick, pg="1"):
        page = _page(pg)
        result = {"list": [], "page": page, "pagecount": 1, "limit": 24, "total": 0}

        html = self._fetch(f"{self.base}?wd={quote(key)}&page={page}")
        if not html:
            return result

        items = re.findall(
            r'<div class="thumb-item[^"]*"[^>]*>.*?'
            r'<a[^>]*href="[^"]*detail=(\d+)"[^>]*>.*?'
            r'<img[^>]*original="([^"]*)"[^>]*>.*?'
            r'thumb-item__title[^>]*>([^<]+)</h2>',
            html, re.S
        )

        seen = set()
        for vid, pic, title in items:
            if vid in seen:
                continue
            seen.add(vid)
            result["list"].append({
                "vod_id": vid,
                "vod_name": html_mod.unescape(title.strip()),
                "vod_pic": fix_url(pic, self.host),
            })

        pp = re.findall(r'href="[^"]*page=(\d+)[^"]*"[^>]*>(\d+)</a>', html)
        if not pp:
            pp = re.findall(r'href="[^"]*page=(\d+)[^"]*"[^>]*>(\d+)', html)
        if pp:
            result["pagecount"] = max(int(n) for _, n in pp)

        return result
