# -*- coding: utf-8 -*-
# HDefPorn Spider for TVBox / 影视仓
# 目标站: https://hdefporn.com/
# 结构: 非标 tube + Video.js + 签名 CDN (mp4 / m3u8)
# 适配: 分类浏览 + 详情实时提取播放地址

import re
import json
from urllib.parse import quote, urljoin, urlparse

try:
    import requests
except ImportError:
    requests = None

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        def init(self, extend=""): pass
        def homeContent(self, filter): pass
        def homeVideoContent(self): pass
        def categoryContent(self, tid, pg, filter, extend): pass
        def detailContent(self, ids): pass
        def playerContent(self, flag, id, vipFlags=None): pass
        def searchContent(self, key, quick, pg="1"): pass
        def isVideoFormat(self, url): pass
        def manualVideoCheck(self): pass
        def localProxy(self, param): pass


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://hdefporn.com"
        self.name = "HDefPorn"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
            "Referer": self.host + "/",
            "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "Upgrade-Insecure-Requests": "1",
        }
        self.s = None
        if requests:
            self.s = requests.Session()
            self.s.headers.update(self.headers)
            self.s.verify = False

        # 常用分类（来自 /categories/ 页面）
        self.classes = [
            {"type_name": "最新", "type_id": "latest"},
            {"type_name": "Teen", "type_id": "teen"},
            {"type_name": "Babe", "type_id": "babe"},
            {"type_name": "Hardcore", "type_id": "hardcore"},
            {"type_name": "Blowjob", "type_id": "blowjob"},
            {"type_name": "Anal", "type_id": "anal"},
            {"type_name": "Milf", "type_id": "milf"},
            {"type_name": "Lesbian", "type_id": "lesbian"},
            {"type_name": "Amateur", "type_id": "amateur"},
            {"type_name": "POV", "type_id": "pov"},
            {"type_name": "Creampie", "type_id": "creampie"},
            {"type_name": "Blonde", "type_id": "blonde"},
            {"type_name": "Brunette", "type_id": "brunette"},
            {"type_name": "Big Boobs", "type_id": "big-boobs"},
            {"type_name": "Threesome", "type_id": "threesome"},
            {"type_name": "Interracial", "type_id": "interracial"},
        ]

    def init(self, extend=""):
        if extend and extend.startswith("http"):
            self.host = extend.rstrip("/")
            self.headers["Referer"] = self.host + "/"
            if self.s:
                self.s.headers.update(self.headers)

    def getName(self):
        return self.name

    def isVideoFormat(self, url):
        if not url:
            return False
        return any(x in url.lower() for x in [".m3u8", ".mp4", ".flv", ".ts"])

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return [200, "video/MP2T", b"", {}]

    def _fetch(self, url, retry=2):
        if not self.s:
            return ""
        for _ in range(retry):
            try:
                r = self.s.get(url, timeout=15, headers=self.headers)
                if r.status_code == 200:
                    r.encoding = "utf-8"
                    return r.text
            except Exception:
                pass
        return ""

    def _fix_url(self, url):
        if not url:
            return ""
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return urljoin(self.host, url)
        if url.startswith("http"):
            return url
        return urljoin(self.host, "/" + url)

    def _clean(self, text):
        if not text:
            return ""
        text = re.sub(r"<[^>]+>", "", str(text))
        return re.sub(r"\s+", " ", text).strip()

    def _parse_list(self, html):
        """解析列表页，提取视频卡片"""
        videos = []
        # 匹配: <div class="pic-wrap" data-vid="94167"><a href="/i/94167/xxx" class="pic"><img ... data-src="..." alt="标题">
        pattern = re.compile(
            r'<div\s+class="pic-wrap"[^>]*data-vid="(\d+)"[^>]*>\s*'
            r'<a\s+href="(/i/\d+/[^"]+)"[^>]*class="pic"[^>]*>\s*'
            r'<img[^>]*(?:data-src|src)="([^"]+)"[^>]*alt="([^"]*)"',
            re.I | re.S
        )
        for m in pattern.finditer(html):
            vid, href, pic, title = m.groups()
            title = self._clean(title) or f"Video {vid}"
            pic = self._fix_url(pic)
            # 过滤占位图
            if "bg-212x120" in pic or not pic:
                pic = self._fix_url(f"/media/video_thumbs/{vid}.jpg")
            videos.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": ""
            })
        # 兜底：只靠 data-vid + href
        if not videos:
            for m in re.finditer(r'data-vid="(\d+)"[^>]*>.*?href="(/i/\d+/[^"]+)"', html, re.S):
                vid, href = m.groups()
                title = re.search(rf'data-vid="{vid}"[^>]*>.*?alt="([^"]*)"', html, re.S)
                title = self._clean(title.group(1)) if title else f"Video {vid}"
                pic = self._fix_url(f"/media/video_thumbs/{vid}.jpg")
                videos.append({
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": ""
                })
        return videos

    def homeContent(self, filter):
        return {
            "class": self.classes,
            "filters": {}
        }

    def homeVideoContent(self):
        return self.categoryContent("latest", "1", False, {})

    def categoryContent(self, tid, pg, filter, extend):
        result = {
            "list": [],
            "page": int(pg) if str(pg).isdigit() else 1,
            "pagecount": 999,
            "limit": 24,
            "total": 0
        }
        try:
            pg = int(pg) if str(pg).isdigit() else 1
            if tid == "latest" or not tid:
                url = self.host + "/" if pg <= 1 else f"{self.host}/page/{pg}"
                # 首页无标准分页，直接用首页
                if pg > 1:
                    # 尝试常见分页形式，失败则回退首页
                    html = self._fetch(f"{self.host}/page/{pg}")
                    if not html or "pic-wrap" not in html:
                        html = self._fetch(self.host + "/")
                else:
                    html = self._fetch(self.host + "/")
            else:
                # /category/{slug} 或 /category/{slug}/{page}
                if pg <= 1:
                    url = f"{self.host}/category/{tid}"
                else:
                    url = f"{self.host}/category/{tid}/{pg}"
                html = self._fetch(url)

            if not html:
                return result

            videos = self._parse_list(html)
            result["list"] = videos
            result["total"] = len(videos) * result["pagecount"]

            # 尝试提取最大页码
            pages = re.findall(rf'/category/{re.escape(tid)}/(\d+)', html)
            if pages:
                try:
                    result["pagecount"] = max(int(p) for p in pages)
                except Exception:
                    pass
        except Exception as e:
            print(f"[{self.name}] categoryContent error: {e}")
        return result

    def detailContent(self, ids):
        result = {"list": []}
        try:
            vid = ids[0] if isinstance(ids, list) else ids
            # 先尝试直接构造详情页（slug 可省略，部分站支持）
            # 实际需要完整 /i/{id}/{slug}，但很多站只认 id 也能跳
            # 这里先用列表缓存的方式，或直接用 id 拼一个通用路径
            html = ""
            # 优先尝试常见路径
            candidates = [
                f"{self.host}/i/{vid}",
                f"{self.host}/i/{vid}/video",
            ]
            # 如果 vid 本身是完整路径
            if str(vid).startswith("http") or str(vid).startswith("/i/"):
                candidates = [self._fix_url(str(vid))]

            for u in candidates:
                html = self._fetch(u)
                if html and ("video-js" in html or "video1" in html or "tubecdn" in html):
                    break

            # 如果还是空，尝试从首页/分类里找真实 href
            if not html or "video-js" not in html:
                # 退而求其次：用 id 构造最简路径
                html = self._fetch(f"{self.host}/i/{vid}")

            if not html:
                return result

            # 标题
            title = re.search(r'<title>([^<]+)</title>', html, re.I)
            title = self._clean(title.group(1).replace(" - HD Porn", "").replace(" - HDef Porn", "")) if title else f"Video {vid}"

            # 封面
            pic = re.search(r'og:image["\']?\s+content=["\']([^"\']+)', html, re.I)
            if not pic:
                pic = re.search(r'twitter:image[^>]+content=["\']([^"\']+)', html, re.I)
            pic = self._fix_url(pic.group(1)) if pic else self._fix_url(f"/media/video_thumbs/{vid}.jpg")

            # 提取播放地址（核心）
            play_url = self._extract_play(html, vid)

            if play_url:
                result["list"].append({
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_content": "",
                    "vod_play_from": "HDefPorn",
                    "vod_play_url": f"正片${play_url}"
                })
            else:
                # 即使没解析到直链，也返回详情，让 playerContent 再试一次
                result["list"].append({
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_play_from": "HDefPorn",
                    "vod_play_url": f"正片${self.host}/i/{vid}"
                })
        except Exception as e:
            print(f"[{self.name}] detailContent error: {e}")
        return result

    def _extract_play(self, html, vid=""):
        """从详情页提取 mp4 / m3u8 播放地址"""
        # 1. 优先 m3u8（HLS）
        m = re.search(r'src:\s*["\'](https?://[^"\']+master\.m3u8[^"\']*)["\']', html)
        if m:
            return m.group(1)

        m = re.search(r'(https?://[^"\'\s]+/hls/[^"\'\s]+master\.m3u8)', html)
        if m:
            return m.group(1)

        # 2. mp4 直链
        m = re.search(r'src:\s*["\'](https?://[^"\']+\.mp4[^"\']*)["\']', html)
        if m:
            return m.group(1)

        m = re.search(r'(https?://[^"\'\s]+/mp4/[^"\'\s]+\.mp4)', html)
        if m:
            return m.group(1)

        # 3. 通用视频地址
        m = re.search(r'(https?://hd\d*\.tubecdn\.net/[^"\'\s]+)', html)
        if m:
            return m.group(1)

        # 4. video 标签 source
        m = re.search(r'<source[^>]+src=["\']([^"\']+)["\']', html, re.I)
        if m:
            return m.group(1)

        return ""

    def playerContent(self, flag, id, vipFlags=None):
        result = {
            "parse": 0,
            "url": "",
            "header": json.dumps({
                "User-Agent": self.headers["User-Agent"],
                "Referer": self.host + "/",
                "Origin": self.host
            })
        }
        try:
            # 已经是直链
            if self.isVideoFormat(id):
                result["url"] = id
                return result

            # id 可能是详情页 url 或纯数字 id
            if id.startswith("http"):
                html = self._fetch(id)
            else:
                html = self._fetch(f"{self.host}/i/{id}")

            if html:
                play = self._extract_play(html, id)
                if play:
                    result["url"] = play
                    return result

            # 最后兜底：把原 id 返回（可能是已提取的地址）
            result["url"] = id
        except Exception as e:
            print(f"[{self.name}] playerContent error: {e}")
            result["url"] = id
        return result

    def searchContent(self, key, quick, pg="1"):
        """搜索：站点 typeahead 较封闭，做有限支持"""
        result = {"list": [], "page": 1, "pagecount": 1, "limit": 24, "total": 0}
        try:
            # 尝试用分类页 + 关键词过滤的方式（弱搜索）
            # 或者直接返回空，避免报错
            # 这里做一次简单尝试：把关键词当 category 试一次
            slug = re.sub(r'[^a-z0-9\-]', '-', key.lower()).strip('-')
            if slug:
                html = self._fetch(f"{self.host}/category/{slug}")
                if html and "pic-wrap" in html:
                    videos = self._parse_list(html)
                    result["list"] = videos
                    result["total"] = len(videos)
        except Exception as e:
            print(f"[{self.name}] searchContent error: {e}")
        return result
