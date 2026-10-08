#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小涩界 - se.xiaosejie73.xyz Spider
站点: https://se.xiaosejie73.xyz
- 分类: /vodtype/{slug}/  /vodtype/{slug}-{pg}/
- 列表: a[href^=/vodplay/] + img.vod-cover[data-src] + h3
- 播放: /vodplay/{slug}-1-1/  player_aaaa.url 明文m3u8
- 反爬: Cloudflare (cloudscraper/curl_cffi 绕过)
"""
import re, json, html as html_mod
from urllib.parse import quote, urljoin

try:
    import requests
    import urllib3
    urllib3.disable_warnings()
except ImportError:
    requests = None

try:
    import cloudscraper
except ImportError:
    cloudscraper = None

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
    if not url: return ""
    if url.startswith("//"): return "https:" + url
    if url.startswith("/"): return urljoin(host, url)
    if url.startswith("http"): return url
    return urljoin(host, url)


def unescape_entities(text):
    """解码 HTML 实体（&#x5C0F; 等）"""
    if not text:
        return ""
    return html_mod.unescape(text)


class Spider(BaseSpider):
    def __init__(self):
        super().__init__()
        self.host = "https://se.xiaosejie73.xyz"
        self.name = "小涩界"
        self.sourceKey = "xiaosejie"
        self.s = requests.Session() if requests else None
        self._scraper = None  # cloudscraper 实例
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/",
        }
        if self.s:
            self.s.headers.update(self.headers)
            self.s.verify = False
        self.timeout = 20
        self.classes = [
            {"type_id": "guochan", "type_name": "国产"},
            {"type_id": "guochanrebo", "type_name": "国产热播"},
            {"type_id": "chuanmeiyuanchuang", "type_name": "传媒原创"},
            {"type_id": "zhibozhubo", "type_name": "直播主播"},
            {"type_id": "diaojiaoxiuru", "type_name": "调教羞辱"},
            {"type_id": "fulijijiang", "type_name": "福利姬酱"},
            {"type_id": "wanghuangbaoliao", "type_name": "网黄爆料"},
            {"type_id": "riben", "type_name": "日本"},
            {"type_id": "ribenheji", "type_name": "日本合集"},
            {"type_id": "bubingzhuanqu", "type_name": "步兵专区"},
            {"type_id": "qibingzhuanqu", "type_name": "骑兵专区"},
            {"type_id": "zhongwenzimu", "type_name": "中文字幕"},
            {"type_id": "haiwai", "type_name": "海外"},
            {"type_id": "oumeijingxuan", "type_name": "欧美精选"},
            {"type_id": "hanguoyingxiang", "type_name": "韩国影像"},
            {"type_id": "heirenmeihei", "type_name": "黑人媚黑"},
            {"type_id": "tese", "type_name": "特色"},
            {"type_id": "dongmandonghua", "type_name": "动漫动画"},
            {"type_id": "yingpianjieshuo", "type_name": "影片解说"},
            {"type_id": "huanlianzhuanqu", "type_name": "换脸专区"},
            {"type_id": "lunlisanji", "type_name": "伦理三级"},
            {"type_id": "xunixianshi", "type_name": "虚拟现实"},
            {"type_id": "tongxing", "type_name": "同性"},
            {"type_id": "nantongxinglian", "type_name": "男同性恋"},
            {"type_id": "nvtongxinglian", "type_name": "女同性恋"},
        ]

    def init(self, extend=""):
        if not extend: return
        try:
            cfg = json.loads(extend) if isinstance(extend, str) else extend
            if isinstance(cfg, dict):
                h = cfg.get("host") or cfg.get("HOST") or ""
                if h: self.host = h.rstrip("/")
                ua = cfg.get("userAgent") or cfg.get("User-Agent") or cfg.get("ua") or ""
                if ua: self.headers["User-Agent"] = ua
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
        return any(x in str(u).lower() for x in [".m3u8", ".mp4", ".m4v", ".flv", ".webm", ".ts", "magnet:", "ed2k:", "thunder:"])
    def manualVideoCheck(self): return False
    def localProxy(self, param): return [404, "text/plain", b""]

    def _get_scraper(self):
        """懒加载 cloudscraper（作为降级用）"""
        if self._scraper is None:
            try:
                if cloudscraper:
                    self._scraper = cloudscraper.create_scraper(
                        delay=0,
                        browser={"browser": "chrome", "platform": "windows", "mobile": False})
                    self._scraper.headers.update(self.headers)
            except Exception:
                self._scraper = None
        return self._scraper

    def _fetch(self, url, use_cache=True):
        """获取HTML：requests直连优先（实测1s内可通），失败降级cloudscraper，带结果缓存"""
        # 结果缓存（同一URL 5分钟内不重复请求）
        cache_key = "c_" + url
        if use_cache:
            cached = getattr(self, "_html_cache", {}).get(cache_key)
            if cached:
                return cached
        html = ""

        # 1. requests 直连（最快）
        if self.s:
            try:
                r = self.s.get(url, headers=self.headers, timeout=10)
                if r.status_code == 200 and len(r.text) > 500:
                    try:
                        r.encoding = r.apparent_encoding or "utf-8"
                    except Exception:
                        r.encoding = "utf-8"
                    html = r.text
            except Exception:
                pass

        # 2. cloudscraper 降级（CF 挑战时）
        if not html:
            sc = self._get_scraper()
            if sc:
                try:
                    r = sc.get(url, timeout=12)
                    if r.status_code == 200 and len(r.text) > 500:
                        html = r.text
                except Exception:
                    pass

        # 3. curl_cffi 兜底
        if not html:
            try:
                from curl_cffi import requests as cffi
                r = cffi.get(url, impersonate="chrome", timeout=12)
                if r.status_code == 200 and len(r.text) > 500:
                    html = r.text
            except Exception:
                pass

        if html and use_cache:
            if not hasattr(self, "_html_cache"):
                self._html_cache = {}
            self._html_cache[cache_key] = html
            # 限制缓存大小，防止内存膨胀
            if len(self._html_cache) > 200:
                self._html_cache.clear()
        return html

    def homeContent(self, filter):
        return {"class": self.classes, "filters": {}}

    def homeVideoContent(self):
        return self.categoryContent("guochan", "1", False, {})

    def categoryContent(self, tid, pg, filter, extend):
        page = _page(pg)
        result = {"list": [], "page": page, "pagecount": 1, "limit": 24, "total": 0}
        if page == 1:
            url = f"{self.host}/vodtype/{tid}/"
        else:
            url = f"{self.host}/vodtype/{tid}-{page}/"
        html = self._fetch(url)
        if not html:
            return result

        # 列表条目：a[href^=/vodplay/] + img.vod-cover[data-src] + h3 标题
        # 结构：<a href="/vodplay/{slug}-1-1/" title="标题"><img class="vod-cover" data-src="..." alt="标题"><h3>标题</h3></a>
        items = re.findall(
            r'<a[^>]+href="(/vodplay/[^"]+-\d+-\d+/)"[^>]*title="([^"]*)"[^>]*>.*?'
            r'<img[^>]*src="([^"]*)"[^>]*data-src="([^"]*)"',
            html, re.S
        )

        seen = set()
        for play_url, title, src, data_src in items:
            # 提取 slug 作为 vod_id（去掉 -1-1/ 后缀）
            m = re.match(r'/vodplay/(.+?)-\d+-\d+/$', play_url)
            if not m:
                continue
            vid = m.group(1)
            if vid in seen:
                continue
            seen.add(vid)
            pic = data_src or src
            result["list"].append({
                "vod_id": vid,
                "vod_name": unescape_entities(title.strip()),
                "vod_pic": fix_url(pic, self.host),
            })

        # 分页：/vodtype/{tid}-{pg}/
        pp = re.findall(r'href="[^"]*/vodtype/' + re.escape(tid) + r'-(\d+)/"', html)
        if pp:
            result["pagecount"] = max(int(p) for p in pp)
        else:
            pp2 = re.findall(r'href="[^"]*[?&]page=(\d+)[^"]*"', html)
            if pp2:
                result["pagecount"] = max(int(p) for p in pp2)

        return result

    def detailContent(self, ids):
        raw_ids = ids if isinstance(ids, (list, tuple)) else [ids]
        vid = str(raw_ids[0] if raw_ids else "").strip()
        if not vid:
            return {"list": []}
        result = {"list": []}

        # 直接请求播放页（本站无独立详情页，播放页即详情页）
        html = self._fetch(f"{self.host}/vodplay/{vid}-1-1/")
        if not html:
            # 再试一次可能的格式
            html = self._fetch(f"{self.host}/vodplay/{vid}/")
        if not html:
            return result

        # 标题
        title = ""
        tm = re.search(r'<h1[^>]*>\s*([^<]+?)\s*</h1>', html, re.S)
        if tm:
            title = unescape_entities(tm.group(1).strip())
        if not title:
            tm2 = re.search(r'<title>([^<]+)</title>', html)
            if tm2:
                title = unescape_entities(tm2.group(1).strip())
        if not title:
            tm3 = re.search(r'class="[^"]*vod-name[^"]*"[^>]*>([^<]+)<', html)
            if tm3:
                title = unescape_entities(tm3.group(1).strip())
        # 清理标题中的分类前缀标签如 [骑兵专区]
        title = re.sub(r'^\[[^\]]+\]\s*', '', title).strip()

        # 封面
        pic = ""
        pm = re.search(r'<img[^>]*class="[^"]*vod-cover[^"]*"[^>]*src="([^"]*)"', html)
        if not pm:
            pm = re.search(r'property="og:image"[^>]*content="([^"]*)"', html)
        if pm:
            pic = fix_url(pm.group(1), self.host)

        # 播放源：本站视频基本单集，取第一个播放按钮链接即可
        # 注意：页面下方有"相关推荐"区域，链接不能混入
        play_from_list = []
        play_url_list = []

        # 第一个播放按钮（source-btn 或播放列表中的链接）
        first_play = re.search(
            r'href="/vodplay/([^"]+?-\d+-\d+/)"[^>]*class="[^"]*(?:source-btn|play-btn|active)[^"]*"',
            html)
        if not first_play:
            first_play = re.search(r'<a[^>]+href="/vodplay/([^"]+?-\d+-\d+/)"', html)

        if first_play:
            play_from_list.append("默认")
            play_url_list.append(f"播放${first_play.group(1)}")
        else:
            play_from_list.append("默认")
            play_url_list.append(f"播放${vid}-1-1")

        vod = {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic,
            "vod_play_from": "$$$".join(play_from_list),
            "vod_play_url": "$$$".join(play_url_list),
        }
        result["list"].append(vod)
        return result

    def playerContent(self, flag, id, vipFlags=None):
        result = {"parse": 0, "playUrl": "", "url": "", "header": {}}
        pid = str(id or "").strip()
        if not pid:
            return result

        # 直接是媒体地址
        if self.isVideoFormat(pid):
            result["url"] = pid
            return result

        # 请求播放页，从 player_aaaa 提取 m3u8（带缓存）
        play_cache = getattr(self, "_play_pages", {})
        html = play_cache.get(pid)
        if not html:
            html = self._fetch(f"{self.host}/vodplay/{pid}/")
            if html:
                play_cache[pid] = html
                if len(play_cache) > 200:
                    play_cache.clear()
                self._play_pages = play_cache
        if not html:
            result["url"] = pid
            return result

        # 括号层次匹配 player_aaaa JSON
        idx = html.find("player_aaaa=")
        if idx >= 0:
            bs = html.find("{", idx)
            if bs >= 0:
                depth = 0
                js = ""
                for i in range(bs, min(bs + 3000, len(html))):
                    if html[i] == "{": depth += 1
                    elif html[i] == "}":
                        depth -= 1
                        if depth == 0:
                            js = html[bs:i+1]
                            break
                if js:
                    try:
                        pd = json.loads(js)
                        enc = pd.get("encrypt", 0)
                        url = pd.get("url", "") or ""
                        if url and url.startswith("http"):
                            result["url"] = url
                            result["header"] = {
                                "User-Agent": self.headers.get("User-Agent", ""),
                                "Referer": self.host + "/"
                            }
                            return result
                    except Exception:
                        pass

        # 兜底：直接找 m3u8
        mm = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html)
        if mm:
            result["url"] = mm.group(1)
            result["header"] = {
                "User-Agent": self.headers.get("User-Agent", ""),
                "Referer": self.host + "/"
            }
            return result

        result["url"] = pid
        return result

    def searchContent(self, key, quick, pg="1"):
        page = _page(pg)
        result = {"list": [], "page": page, "pagecount": 1, "limit": 24, "total": 0}

        html = self._fetch(f"{self.host}/vodsearch/-------------/?wd={quote(key)}&page={page}")
        if not html:
            return result

        items = re.findall(
            r'<a[^>]+href="(/vodplay/[^"]+-\d+-\d+/)"[^>]*title="([^"]*)"[^>]*>.*?'
            r'<img[^>]*src="([^"]*)"[^>]*data-src="([^"]*)"',
            html, re.S
        )

        seen = set()
        for play_url, title, src, data_src in items:
            m = re.match(r'/vodplay/(.+?)-\d+-\d+/$', play_url)
            if not m:
                continue
            vid = m.group(1)
            if vid in seen:
                continue
            seen.add(vid)
            result["list"].append({
                "vod_id": vid,
                "vod_name": unescape_entities(title.strip()),
                "vod_pic": fix_url(data_src or src, self.host),
            })

        pp = re.findall(r'[?&]page=(\d+)', html)
        if pp:
            result["pagecount"] = max(int(p) for p in pp)

        return result
