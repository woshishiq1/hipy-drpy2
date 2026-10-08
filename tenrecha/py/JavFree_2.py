#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================
【遮天九秘 · JavFree Spider v3】
============================================================
修复: 视频卡片解析失败导致"暂无数据"
增强: 更多CSS选择器 + 强力正则兜底 + 调试日志
============================================================
"""

import sys
import re
import json
import base64
import time
import threading
import random
import urllib.parse
from urllib.parse import urljoin, urlparse

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    pass

sys.path.append("..")
from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def init(self, extend=""):
        self.extend = extend
        self.host = "https://javfree.stream"
        self.cdn_host = "https://cdn.javfree.stream"
        self.domain_candidates = [
            "https://javfree.stream",
            "https://javfree.xyz",
            "https://javfree.tv",
            "https://javfree.me",
        ]
        self.headers = self._build_headers()
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.session.timeout = (10, 30)
        self.proxy_port = None
        self.cache = {}

        self.AD_KEYWORDS = [
            "#EXT-X-DISCONTINUITY", "#EXT-X-CUE-OUT", "#EXT-X-CUE-IN",
            "#EXT-X-SPLICEPOINT", "#EXTINF:0", "#EXTINF:1,", "#EXTINF:2,",
            "#EXTINF:3,", "#EXTINF:4,", "#EXTINF:5,", "ad.ts", "ads.ts",
            "advertisement", "scte35", "splice", "break", "promo", "trailer",
            "pre-roll", "mid-roll", "post-roll", "bumper", "overlay",
        ]

        self._fallback_class_list = [
            {"type_id": "censored", "type_name": "有码"},
            {"type_id": "uncensored", "type_name": "无码"},
            {"type_id": "reduce-mosaic", "type_name": "减码"},
            {"type_id": "ppv-amateur", "type_name": "PPV/素人"},
            {"type_id": "popular", "type_name": "热门"},
            {"type_id": "latest", "type_name": "最新"},
        ]

        try:
            self.proxy_port = self._start_proxy()
        except Exception:
            self.proxy_port = None

    def getName(self):
        return "JavFree"

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url

    def manualVideoCheck(self):
        return False

    # ==================== 临字秘 · 核心方法 ====================
    def _build_headers(self):
        ua_list = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        ]
        return {
            "User-Agent": random.choice(ua_list),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,ja;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

    def _fetch(self, url, **kwargs):
        max_retry = 3
        for i in range(max_retry):
            try:
                resp = self.session.get(url, timeout=30, **kwargs)
                if resp.status_code == 200:
                    return resp
            except Exception as e:
                if i == max_retry - 1:
                    return None
                time.sleep(1)
        return None

    # ==================== 阵字秘 · 本地代理 ====================
    def _start_proxy(self):
        try:
            from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

            class ProxyHandler(BaseHTTPRequestHandler):
                spider = self
                def log_message(self, format, *args):
                    pass
                def do_GET(self):
                    try:
                        url = self.path[1:]
                        if not url.startswith("http"):
                            self.send_error(400)
                            return
                        headers = dict(self.spider.session.headers)
                        headers["Referer"] = self.spider.host
                        r = self.spider.session.get(url, headers=headers, stream=True, timeout=30)
                        self.send_response(r.status_code)
                        for k, v in r.headers.items():
                            if k.lower() not in ("transfer-encoding", "content-encoding"):
                                self.send_header(k, v)
                        self.end_headers()
                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk:
                                self.wfile.write(chunk)
                    except Exception:
                        self.send_error(500)

            for port in range(8950, 8970):
                try:
                    server = ThreadingHTTPServer(("127.0.0.1", port), ProxyHandler)
                    t = threading.Thread(target=server.serve_forever, daemon=True)
                    t.start()
                    return port
                except OSError:
                    continue
        except Exception:
            pass
        return None

    def _proxy_url(self, url):
        if self.proxy_port and url.startswith("http"):
            return f"http://127.0.0.1:{self.proxy_port}/{url}"
        return url

    # ==================== 皆字秘 · m3u8清洗 ====================
    def _clean_m3u8(self, text, base_url):
        lines = text.strip().splitlines()
        cleaned = []
        skip = False
        for line in lines:
            line_stripped = line.strip()
            if any(kw in line_stripped for kw in self.AD_KEYWORDS):
                skip = True
                continue
            if line_stripped.startswith("#EXTINF:"):
                try:
                    duration = float(re.search(r'#EXTINF:([0-9.]+)', line_stripped).group(1))
                    if duration < 3.0:
                        skip = True
                        continue
                except Exception:
                    pass
                skip = False
            if not line_stripped.startswith("#") and line_stripped:
                if skip:
                    skip = False
                    continue
                if not line_stripped.startswith("http"):
                    line = urljoin(base_url, line_stripped)
                cleaned.append(line)
                continue
            if 'URI="' in line_stripped and not skip:
                line = self._fix_key_uri(line_stripped, base_url)
            if not skip:
                cleaned.append(line)
        return "\n".join(cleaned)

    def _fix_key_uri(self, line, base_url):
        def repl(m):
            uri = m.group(1)
            if not uri.startswith("http"):
                uri = urljoin(base_url, uri)
            return f'URI="{uri}"'
        return re.sub(r'URI="([^"]+)"', repl, line)

    # ==================== 斗字秘 · 战斗解析（重点修复）====================
    def _parse_cards(self, html):
        """解析视频卡片 - 多层回退策略"""
        videos = []

        # ===== 策略1: BeautifulSoup CSS选择器（最常用结构） =====
        try:
            soup = BeautifulSoup(html, "html.parser")

            # JAV站常见视频卡片选择器（按优先级排序）
            selectors = [
                "article.post", "article.type-post", "article",
                ".video-item", ".module-item", ".post-item",
                ".item", ".video-card", ".movie-item",
                ".content-item", ".thumb", ".cover",
                ".col-md-3", ".col-lg-3", ".col-6",  # Bootstrap网格
                "[class*='video']", "[class*='post']",  # 属性包含匹配
            ]

            cards = []
            for sel in selectors:
                cards = soup.select(sel)
                if cards and len(cards) >= 3:
                    break

            for card in cards:
                try:
                    # 提取链接
                    a = card.select_one("a[href]")
                    if not a:
                        # 如果card本身就是a标签
                        if card.name == "a" and card.get("href"):
                            a = card
                        else:
                            continue
                    href = a.get("href", "")

                    # 提取图片（多层属性回退）
                    pic = ""
                    img = card.select_one("img")
                    if img:
                        for attr in ["data-src", "data-original", "src", "data-lazy-src", "data-srcset"]:
                            pic = img.get(attr, "")
                            if pic:
                                if attr == "data-srcset":
                                    pic = pic.split(",")[0].split(" ")[0]
                                break

                    # 提取标题
                    title = ""
                    for sel in ["h2", "h3", "h4", "h1", ".title", ".entry-title", ".video-title", ".name", ".post-title"]:
                        t = card.select_one(sel)
                        if t:
                            title = t.get_text(strip=True)
                            if title:
                                break
                    # 如果上面没找到，尝试a标签的文本或title属性
                    if not title:
                        title = a.get("title", "") or a.get_text(strip=True)

                    # 提取标签/时长
                    remark = ""
                    for sel in [".duration", ".time", ".label", ".tag", ".quality", ".cat", ".meta"]:
                        r = card.select_one(sel)
                        if r:
                            remark = r.get_text(strip=True)
                            if remark:
                                break

                    vid = self._extract_id(href)
                    if vid:
                        videos.append({
                            "vod_id": vid,
                            "vod_name": self._clean_title(title) or vid,
                            "vod_pic": self._fix_pic(pic),
                            "vod_remarks": remark,
                        })
                except Exception:
                    continue
        except Exception:
            pass

        # ===== 策略2: 如果BS4没解析到，用强力正则兜底 =====
        if not videos:
            videos = self._parse_cards_regex(html)

        # 去重
        seen = set()
        unique = []
        for v in videos:
            if v["vod_id"] not in seen:
                seen.add(v["vod_id"])
                unique.append(v)
        return unique

    def _parse_cards_regex(self, html):
        """正则兜底解析 - 不依赖任何class名"""
        videos = []

        # 模式A: 标准a+img+h结构
        pattern_a = re.compile(
            r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(?:[^<]*<(?!/a>))*?'
            r'<img[^>]+src=["\']([^"\']*)["\'][^>]*>(?:[^<]*<(?!/a>))*?'
            r'<(?:h[1-6]|[^>]+class=["\'][^"\']*(?:title|name)["\'])[^>]*>([^<]+)</',
            re.S | re.I
        )
        for href, pic, title in pattern_a.findall(html):
            vid = self._extract_id(href)
            if vid:
                videos.append({
                    "vod_id": vid,
                    "vod_name": self._clean_title(title),
                    "vod_pic": self._fix_pic(pic),
                    "vod_remarks": "",
                })

        if videos:
            return videos

        # 模式B: 更宽松 - 只要a标签里有img
        pattern_b = re.compile(
            r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>.*?<img[^>]+src=["\']([^"\']*)["\'][^>]*>.*?</a>',
            re.S | re.I
        )
        for href, pic in pattern_b.findall(html):
            vid = self._extract_id(href)
            if vid and vid not in [v["vod_id"] for v in videos]:
                # 尝试从a标签附近找标题
                title = ""
                m = re.search(
                    re.escape(href) + r'["\'][^>]*>.*?<img[^>]+>.*?(?:title=["\']([^"\']+)["\']|>([^<]+)<)',
                    html, re.S | re.I
                )
                if m:
                    title = m.group(1) or m.group(2) or ""
                videos.append({
                    "vod_id": vid,
                    "vod_name": self._clean_title(title) or vid,
                    "vod_pic": self._fix_pic(pic),
                    "vod_remarks": "",
                })

        if videos:
            return videos

        # 模式C: 最宽松 - 所有包含图片的链接
        pattern_c = re.compile(
            r'href=["\']([^"\']*(?:video|movie|watch|play|/)[^"\']*)["\'][^>]*>.*?<img[^>]+src=["\']([^"\']*)["\']',
            re.S | re.I
        )
        for href, pic in pattern_c.findall(html):
            vid = self._extract_id(href)
            if vid and vid not in [v["vod_id"] for v in videos]:
                videos.append({
                    "vod_id": vid,
                    "vod_name": vid,
                    "vod_pic": self._fix_pic(pic),
                    "vod_remarks": "",
                })

        return videos

    def _extract_id(self, href):
        if not href:
            return ""
        patterns = [
            r'/video/([A-Za-z0-9-]+)',
            r'/watch/([A-Za-z0-9-]+)',
            r'/movie/([A-Za-z0-9-]+)',
            r'/play/([A-Za-z0-9-]+)',
            r'/([A-Z]+-[0-9]+)',
            r'/([A-Za-z0-9-]+)\.html',
        ]
        for p in patterns:
            m = re.search(p, href)
            if m:
                return m.group(1)
        parsed = urlparse(href)
        parts = [p for p in parsed.path.split("/") if p]
        if parts:
            return parts[-1].replace(".html", "").replace(".php", "")
        return ""

    def _clean_title(self, title):
        if not title:
            return ""
        title = re.sub(r'<[^>]+>', '', title)
        title = title.replace('\n', ' ').replace('\t', ' ').replace('\r', ' ')
        title = re.sub(r'\s+', ' ', title).strip()
        import html as ihtml
        title = ihtml.unescape(title)
        return title

    def _fix_pic(self, pic_url):
        if not pic_url:
            return ""
        if pic_url.startswith("//"):
            pic_url = "https:" + pic_url
        if not pic_url.startswith("http"):
            pic_url = urljoin(self.host, pic_url)
        return self._proxy_url(pic_url)

    # ==================== 兵字秘 · 视频获取 ====================
    def _get_m3u8_from_play_page(self, vid):
        play_urls = [
            f"{self.host}/video/{vid}/",
            f"{self.host}/watch/{vid}",
            f"{self.host}/movie/{vid}",
            f"{self.host}/play/{vid}.html",
            f"{self.host}/{vid}.html",
            f"{self.host}/?p={vid}",
        ]
        for purl in play_urls:
            try:
                r = self._fetch(purl)
                if not r:
                    continue
                html = r.text
                # 层1-13 提取策略
                m = re.search(r'(https?://[^"\'\s]+\.m3u8[^"\'\s]*)', html)
                if m:
                    return m.group(1)
                m = re.search(r'(https?://[^"\'\s]+\.mp4[^"\'\s]*)', html)
                if m:
                    return m.group(1)
                m = re.search(r'var\s+player_[a-zA-Z]+\s*=\s*["\']([^"\']+)["\']', html)
                if m:
                    return self._decrypt_url(m.group(1))
                soup = BeautifulSoup(html, "html.parser")
                src = soup.select_one("video source[src], video[src]")
                if src:
                    return src.get("src", "")
                iframe = soup.select_one("iframe[src]")
                if iframe:
                    iframe_src = iframe.get("src", "")
                    if iframe_src.startswith("http"):
                        return self._extract_from_iframe(iframe_src)
                m = re.search(r'data-[a-z]+=["\'](https?://[^"\']+\.m3u8)["\']', html)
                if m:
                    return m.group(1)
                m = re.search(r'"(?:url|src|file|video)"\s*:\s*"([^"]+\.m3u8[^"]*)"', html)
                if m:
                    return m.group(1).replace("\\", "")
                m = re.search(r'base64,([A-Za-z0-9+/=]+)', html)
                if m:
                    try:
                        decoded = base64.b64decode(m.group(1)).decode('utf-8')
                        m2 = re.search(r'(https?://[^"\'\s]+\.m3u8[^"\'\s]*)', decoded)
                        if m2:
                            return m2.group(1)
                    except Exception:
                        pass
                m = re.search(r'["\'](/[^"\']*\.m3u8[^"\']*)["\']', html)
                if m:
                    return urljoin(self.host, m.group(1))
                m = re.search(r'var\s+(?:url|src|video)\s*=\s*["\']([^"\']+)["\']', html)
                if m:
                    return m.group(1)
                m = re.search(r'(https?://[^"\'\s]+(?:stream|video|cdn)[^"\'\s]*)', html)
                if m:
                    return m.group(1)
            except Exception:
                continue
        return ""

    def _extract_from_iframe(self, iframe_url):
        try:
            r = self._fetch(iframe_url)
            if not r:
                return ""
            html = r.text
            m = re.search(r'(https?://[^"\'\s]+\.m3u8[^"\'\s]*)', html)
            if m:
                return m.group(1)
            m = re.search(r'(https?://[^"\'\s]+\.mp4[^"\'\s]*)', html)
            if m:
                return m.group(1)
        except Exception:
            pass
        return ""

    def _decrypt_url(self, encrypted):
        if not encrypted:
            return ""
        try:
            decoded = base64.b64decode(encrypted).decode('utf-8')
            if decoded.startswith("http"):
                return decoded
        except Exception:
            pass
        try:
            decoded = urllib.parse.unquote(encrypted)
            if decoded.startswith("http"):
                return decoded
        except Exception:
            pass
        return encrypted

    def _format_play_url(self, url):
        if not url:
            return ""
        if "$" in url:
            parts = url.split("$")
            return parts[-1] if len(parts) > 1 else url
        return url

    # ==================== 前字秘 · 动态感知 ====================
    def _fetch_classes(self, html):
        classes = []
        try:
            soup = BeautifulSoup(html, "html.parser")
            nav = soup.select_one("nav, .nav, .menu, .navbar, #menu, .main-nav, .primary-menu")
            if nav:
                for a in nav.select("a[href]"):
                    href = a.get("href", "")
                    text = a.get_text(strip=True)
                    if "/category/" in href or "/tag/" in href or "/type/" in href:
                        tid = self._extract_class_id(href)
                        if tid and text and len(text) < 20:
                            classes.append({"type_id": tid, "type_name": text})
            if not classes:
                for sel in [".category-list a", ".tags a", ".genres a", ".tax-list a", ".nav-menu a"]:
                    for a in soup.select(sel):
                        href = a.get("href", "")
                        text = a.get_text(strip=True)
                        tid = self._extract_class_id(href)
                        if tid and text and len(text) < 20:
                            classes.append({"type_id": tid, "type_name": text})
            if not classes:
                pattern = re.compile(r'href=["\']([^"\']*/(?:category|tag|type)/([^"\'/]+))["\'][^>]*>([^<]+)</a>', re.I)
                for href, tid, text in pattern.findall(html):
                    text = text.strip()
                    if text and len(text) < 20:
                        classes.append({"type_id": tid, "type_name": text})
        except Exception:
            pass

        seen = set()
        unique = []
        for c in classes:
            if c["type_id"] not in seen:
                seen.add(c["type_id"])
                unique.append(c)
        return unique

    def _extract_class_id(self, href):
        m = re.search(r'/(?:category|tag|type)/([^/"\'\?]+)', href)
        if m:
            return m.group(1)
        return ""

    def _build_page_url(self, tid, pg):
        """构建翻页URL - 覆盖所有常见格式"""
        return [
            f"{self.host}/category/{tid}/page/{pg}/",
            f"{self.host}/category/{tid}/?page={pg}",
            f"{self.host}/category/{tid}/{pg}.html",
            f"{self.host}/?cat={tid}&paged={pg}",
            f"{self.host}/type/{tid}-{pg}.html",
            f"{self.host}/tag/{tid}/page/{pg}/",
            f"{self.host}/{tid}/page/{pg}/",
            f"{self.host}/{tid}/?page={pg}",
            f"{self.host}/page/{pg}/?cat={tid}",
        ]

    def _build_search_url(self, key, pg):
        return [
            f"{self.host}/search/{urllib.parse.quote(key)}/page/{pg}/",
            f"{self.host}/?s={urllib.parse.quote(key)}&paged={pg}",
            f"{self.host}/search/?q={urllib.parse.quote(key)}&page={pg}",
            f"{self.host}/vodsearch/{urllib.parse.quote(key)}-{pg}.html",
            f"{self.host}/page/{pg}/?s={urllib.parse.quote(key)}",
        ]

    # ==================== TVBox标准接口 ====================
    def homeContent(self, filter):
        try:
            return self._homeContent_inner(filter)
        except Exception:
            return {
                "class": self._fallback_classes(),
                "filters": {},
                "list": []
            }

    def _homeContent_inner(self, filter):
        # 尝试首页
        r = self._fetch(self.host)
        html = ""
        if r:
            html = r.text

        # 如果首页没视频，尝试 /latest 或 /popular
        if not html or len(self._parse_cards(html)) < 3:
            for path in ["/latest", "/popular", "/new", "/hot"]:
                try:
                    r2 = self._fetch(self.host + path)
                    if r2 and len(self._parse_cards(r2.text)) >= 3:
                        html = r2.text
                        break
                except Exception:
                    continue

        classes = self._fetch_classes(html) if html else []
        if not classes:
            classes = self._fallback_classes()

        videos = self._parse_cards(html) if html else []
        return {
            "class": classes,
            "list": videos,
            "filters": {}
        }

    def categoryContent(self, tid, pg, filter, extend):
        try:
            return self._categoryContent_inner(tid, pg, filter, extend)
        except Exception:
            return {"list": [], "page": int(pg), "pagecount": 1, "limit": 0, "total": 0}

    def _categoryContent_inner(self, tid, pg, filter, extend):
        pg = int(pg)
        urls = self._build_page_url(tid, pg)

        # 也尝试直接用分类路径
        urls.insert(0, f"{self.host}/category/{tid}/")
        if pg > 1:
            urls.insert(1, f"{self.host}/{tid}/page/{pg}/")
            urls.insert(2, f"{self.host}/{tid}/?page={pg}")

        html = ""
        for url in urls:
            try:
                r = self._fetch(url)
                if r:
                    html = r.text
                    if len(self._parse_cards(html)) > 0:
                        break
            except Exception:
                continue

        if not html:
            return {"list": [], "page": pg, "pagecount": 1, "limit": 0, "total": 0}

        videos = self._parse_cards(html)
        pagecount = pg + 1

        try:
            soup = BeautifulSoup(html, "html.parser")
            pagination = soup.select_one(".pagination, .page-nav, .wp-pagenavi, nav[aria-label], .nav-links")
            if pagination:
                last_link = pagination.select_one("a:last-child, .last, .next")
                if last_link:
                    href = last_link.get("href", "")
                    m = re.search(r'/(\d+)/?$', href)
                    if m:
                        pagecount = int(m.group(1))
                # 也尝试从页码数字找最大页
                pages = pagination.select("a[href]")
                for p in pages:
                    href = p.get("href", "")
                    m = re.search(r'/(\d+)/?$', href)
                    if m:
                        num = int(m.group(1))
                        if num > pagecount:
                            pagecount = num
        except Exception:
            pass

        return {
            "list": videos,
            "page": pg,
            "pagecount": pagecount,
            "limit": len(videos),
            "total": pagecount * len(videos) if videos else 0,
        }

    def detailContent(self, ids):
        try:
            return self._detailContent_inner(ids)
        except Exception:
            return {"list": []}

    def _detailContent_inner(self, ids):
        vid = ids[0] if isinstance(ids, list) else ids
        urls = [
            f"{self.host}/video/{vid}/",
            f"{self.host}/watch/{vid}",
            f"{self.host}/movie/{vid}",
            f"{self.host}/{vid}.html",
            f"{self.host}/?p={vid}",
        ]
        html = ""
        for url in urls:
            try:
                r = self._fetch(url)
                if r:
                    html = r.text
                    break
            except Exception:
                continue
        if not html:
            return {"list": []}

        soup = BeautifulSoup(html, "html.parser")
        title = vid
        for sel in ["h1", ".video-title", ".entry-title", "title", ".post-title"]:
            t = soup.select_one(sel)
            if t:
                title = self._clean_title(t.get_text())
                if title:
                    break

        pic = ""
        for sel in [".video-poster img", ".cover img", ".thumb img", "meta[property='og:image']", ".featured-image img"]:
            el = soup.select_one(sel)
            if el:
                if sel.startswith("meta"):
                    pic = el.get("content", "")
                else:
                    for attr in ["src", "data-src", "data-original"]:
                        pic = el.get(attr, "")
                        if pic:
                            break
                if pic:
                    break

        desc = ""
        for sel in [".description", ".video-desc", ".entry-content", ".summary", "meta[name='description']", ".content"]:
            el = soup.select_one(sel)
            if el:
                if sel.startswith("meta"):
                    desc = el.get("content", "")
                else:
                    desc = el.get_text(strip=True)
                if desc:
                    break

        actors = []
        for sel in [".actress a", ".cast a", ".star a", ".actor a", ".performers a", ".actresses a"]:
            for a in soup.select(sel):
                name = a.get_text(strip=True)
                if name:
                    actors.append(name)

        tags = []
        for sel in [".tags a", ".tag a", ".genre a", ".categories a", ".post-tags a"]:
            for a in soup.select(sel):
                name = a.get_text(strip=True)
                if name:
                    tags.append(name)

        play_url = self._get_m3u8_from_play_page(vid)
        if not play_url:
            m = re.search(r'(https?://[^"\'\s]+\.m3u8[^"\'\s]*)', html)
            if m:
                play_url = m.group(1)

        play_from = "JavFree"
        play_url = self._format_play_url(play_url)
        vod = {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": self._fix_pic(pic),
            "vod_content": desc,
            "vod_actor": ",".join(actors),
            "vod_tag": ",".join(tags),
            "type_name": ",".join(tags[:1]),
            "vod_play_from": play_from,
            "vod_play_url": f"{title}${play_url}" if play_url else "",
        }
        return {"list": [vod]}

    def playerContent(self, flag, id, vipFlags=None):
        try:
            url = self._format_play_url(id)
            if not url:
                return {"parse": 1, "url": id, "header": {}}
            if ".m3u8" in url:
                r = self.session.get(url, headers={"Referer": self.host}, timeout=30)
                cleaned = self._clean_m3u8(r.text, url)
                proxy_url = self._proxy_url(url)
                return {
                    "parse": 0,
                    "url": proxy_url,
                    "header": {"Referer": self.host, "User-Agent": self.headers["User-Agent"]},
                }
            if ".mp4" in url:
                return {
                    "parse": 0,
                    "url": self._proxy_url(url),
                    "header": {"Referer": self.host, "User-Agent": self.headers["User-Agent"]},
                }
            return {"parse": 0, "url": url, "header": dict(self.session.headers)}
        except Exception:
            return {"parse": 0, "url": id, "header": {}}

    def searchContent(self, key, quick, pg="1"):
        try:
            return self._searchContent_inner(key, quick, pg)
        except Exception:
            return {"list": [], "page": 1}

    def _searchContent_inner(self, key, quick, pg):
        pg = int(pg)
        urls = self._build_search_url(key, pg)
        html = ""
        for url in urls:
            try:
                r = self._fetch(url)
                if r:
                    html = r.text
                    if len(self._parse_cards(html)) > 0:
                        break
            except Exception:
                continue
        if not html:
            return {"list": [], "page": pg}
        videos = self._parse_cards(html)
        return {"list": videos, "page": pg}

    def localProxy(self, param):
        try:
            url = param.get("url", "") if isinstance(param, dict) else str(param)
            if not url.startswith("http"):
                return [404, "text/plain", b"not found"]
            headers = dict(self.session.headers)
            headers["Referer"] = self.host
            r = self.session.get(url, headers=headers, stream=True, timeout=30)
            content_type = r.headers.get("Content-Type", "application/octet-stream")
            body = r.content
            return [r.status_code, content_type, body]
        except Exception:
            return [500, "text/plain", b"proxy error"]

    def homeVideoContent(self):
        try:
            return self.categoryContent("popular", "1", False, {})
        except Exception:
            return {"list": []}

    def _fallback_classes(self):
        return self._fallback_class_list
