#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
蜜云视频 TVBox / 影视仓 / py-drpy 源

适配站点：
    https://xn--0810-3cc-i30mr40izsbt77d4ir52ihu1g.zilitv64.cfd/

页面结构：
    首页/分类：/?m=list&u={分类}&k={子类}&p={页码}
    搜索：/?m=search&u={分类}&k={关键词}&p={页码}
    全站搜索：/?m=searchall&k={关键词}&p={页码}
    详情播放：/?m=play&u={分类}&k={视频ID}
    播放器：/player/index.php/{分类}/{视频ID}

说明：
    - 分类、列表、详情均按用户提供的源码结构编写；
    - playerContent 支持从播放器页多层提取 m3u8/mp4；
    - 如果外部传入的 id 已经是真实 m3u8/mp4，会直接返回；
    - 不内置任何敏感数据，播放令牌以目标站实时返回为准。
"""

import html
import json
import re
import time
from urllib import parse

try:
    import requests
except Exception:
    requests = None

try:
    from bs4 import BeautifulSoup
except Exception:
    BeautifulSoup = None

try:
    from base.spider import Spider as SpiderBase
except Exception:
    class SpiderBase(object):
        pass


class Spider(SpiderBase):
    siteUrl = "https://xn--0810-3cc-i30mr40izsbt77d4ir52ihu1g.zilitv64.cfd"
    siteName = "蜜云视频"

    # 兜底分类。homeContent 会优先从首页 nav 解析，失败时使用这里。
    DEFAULT_CLASSES = [
        {"type_id": "sh", "type_name": "雄狮"},
        {"type_id": "jp", "type_name": "精品"},
        {"type_id": "Hsck", "type_name": "Hsck"},
        {"type_id": "xnxx", "type_name": "Xnxx"},
        {"type_id": "xvs", "type_name": "Xvideos"},
        {"type_id": "p91", "type_name": "91国产"},
        {"type_id": "p91404", "type_name": "9109"},
        {"type_id": "javbus", "type_name": "JavB(种)"},
        {"type_id": "javdb", "type_name": "JavD(种)"},
        {"type_id": "javxx", "type_name": "Javtt"},
        {"type_id": "supjav", "type_name": "Javpp"},
        {"type_id": "zblive", "type_name": "ZB直播"},
        {"type_id": "18av", "type_name": "18AV"},
    ]

    SUB_CATEGORIES = {
        "p91": [
            ("", "全部"),
            ("latest", "最近更新"),
            ("hd", "高清视频"),
            ("recent-favorite", "最近加精"),
            ("hot-list", "当前最热"),
            ("recent-rating", "最近得分"),
            ("nonpaid", "非付费"),
            ("ori", "91原创"),
            ("long-list", "10分钟以上"),
            ("longer-list", "20分钟以上"),
            ("top-list", "本月最热"),
        ],
        "xvs": [
            ("index", "最近更新"),
            ("channels_list", "热门频道"),
            ("pornstars_list", "明星合集"),
            ("month_list", "月份榜单"),
        ],
    }

    UA = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )

    def getName(self):
        return self.siteName

    def init(self, extend=""):
        if isinstance(extend, dict):
            url = extend.get("siteUrl") or extend.get("url")
            if url:
                self.siteUrl = url.rstrip("/")
        elif isinstance(extend, str) and extend.startswith("http"):
            self.siteUrl = extend.rstrip("/")

    def homeContent(self, filter=False):
        classes = []
        html_text = self._fetch_text(self.siteUrl + "/")
        if html_text:
            classes = self._parse_classes(html_text)
        if not classes:
            classes = list(self.DEFAULT_CLASSES)

        result = {"class": classes}
        if filter:
            result["filters"] = self._build_filters(classes)
        return result

    def homeVideoContent(self):
        html_text = self._fetch_text(self.siteUrl + "/")
        return {"list": self._parse_cards(html_text)[:24] if html_text else []}

    def categoryContent(self, tid, pg, filter, extend):
        pg = str(pg or "1")
        tid = str(tid or "p91")
        key = ""
        if isinstance(extend, dict):
            key = extend.get("k") or extend.get("cate") or extend.get("type") or ""

        params = {"m": "list", "u": tid}
        if key:
            params["k"] = key
        if pg != "1":
            params["p"] = pg
        url = self.siteUrl + "/?" + parse.urlencode(params)

        html_text = self._fetch_text(url)
        videos = self._parse_cards(html_text) if html_text else []
        pagecount = self._parse_pagecount(html_text) if html_text else int(pg)
        return {
            "list": videos,
            "page": int(pg) if str(pg).isdigit() else 1,
            "pagecount": pagecount,
            "limit": len(videos) or 24,
            "total": pagecount * (len(videos) or 24),
        }

    def detailContent(self, ids):
        raw_id = ids[0] if isinstance(ids, list) and ids else ids
        detail_url, u, k = self._normalize_detail_id(raw_id)
        html_text = self._fetch_text(detail_url)

        title = ""
        pic = ""
        desc = ""
        iframe = ""
        related = []
        if html_text:
            title = self._first_match(html_text, [
                r'<h1[^>]*class=["\'][^"\']*dr001-title[^"\']*["\'][^>]*>(.*?)</h1>',
                r"<title>(.*?)</title>",
            ])
            title = self._clean_text(title).replace(" - 蜜云视频", "")
            pic = self._first_match(html_text, [
                r"toggleFavorite\([^)]*?['\"](https?://[^'\"]+)['\"]",
                r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
                r'<img[^>]+class=["\'][^"\']*thumb-img[^"\']*["\'][^>]+src=["\']([^"\']+)["\']',
            ])
            iframe = self._first_match(html_text, [
                r'<iframe[^>]+id=["\']player["\'][^>]+src=["\']([^"\']+)["\']',
                r'<iframe[^>]+src=["\']([^"\']*?/player/[^"\']+)["\']',
            ])
            related = self._parse_cards(html_text)[:12]

        if not title:
            title = str(k or raw_id or "视频")
        if iframe:
            play_id = self._absolute_url(html.unescape(iframe))
        elif u and k:
            play_id = f"{u}|{k}"
        else:
            play_id = str(raw_id or "")

        vod = {
            "vod_id": self._make_detail_id(u, k, detail_url),
            "vod_name": title,
            "vod_pic": self._absolute_url(pic),
            "type_name": u or "",
            "vod_year": "",
            "vod_area": "",
            "vod_remarks": "",
            "vod_actor": "",
            "vod_director": "",
            "vod_content": desc or title,
            "vod_play_from": "蜜云",
            "vod_play_url": "在线播放$" + play_id,
        }
        if related:
            vod["vod_rels"] = related
        return {"list": [vod]}

    def playerContent(self, flag, id, vipFlags):
        raw = html.unescape(str(id or "")).strip()
        embedded_media = self._extract_player_path_media(raw)
        if embedded_media:
            return self._player_result(embedded_media)
        if "|" in raw:
            u, k = raw.split("|", 1)
            if self._is_media_url(k):
                return self._player_result(k)
        if self._is_media_url(raw):
            return self._player_result(raw)

        candidate_urls = []
        if raw.startswith("/"):
            candidate_urls.append(self._absolute_url(raw))
        elif raw.startswith("http"):
            candidate_urls.append(raw)
        elif "|" in raw:
            u, k = raw.split("|", 1)
            candidate_urls.append(f"{self.siteUrl}/player/index.php/{parse.quote(u)}/{parse.quote(k, safe='')}")
        else:
            detail_url, u, k = self._normalize_detail_id(raw)
            if u and k:
                candidate_urls.append(f"{self.siteUrl}/player/index.php/{parse.quote(u)}/{parse.quote(k, safe='')}")
            candidate_urls.append(detail_url)

        visited = set()
        media_url = ""
        for url in candidate_urls:
            media_url = self._resolve_player_url(url, visited=visited)
            if media_url:
                break

        if not media_url:
            media_url = raw
        return self._player_result(media_url)

    def searchContent(self, key, quick, pg="1"):
        pg = str(pg or "1")
        kw = str(key or "")
        params = {"m": "searchall", "k": kw}
        if pg != "1":
            params["p"] = pg
        url = self.siteUrl + "/?" + parse.urlencode(params)
        html_text = self._fetch_text(url)
        videos = self._parse_cards(html_text) if html_text else []
        pagecount = self._parse_pagecount(html_text) if html_text else int(pg)
        return {
            "list": videos,
            "page": int(pg) if str(pg).isdigit() else 1,
            "pagecount": pagecount,
            "limit": len(videos) or 24,
            "total": pagecount * (len(videos) or 24),
        }

    def localProxy(self, param):
        return [404, "text/plain", "Not Found"]

    # 兼容部分 TVBox/影视仓引擎的方法名
    def isVideoFormat(self, url):
        return self._is_media_url(url)

    def manualVideoCheck(self):
        return False

    # ---------- 解析工具 ----------

    def _headers(self, referer=None):
        return {
            "User-Agent": self.UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": referer or (self.siteUrl + "/"),
            "Connection": "keep-alive",
        }

    def _fetch_text(self, url, referer=None, timeout=12):
        if not requests:
            return ""
        try:
            resp = requests.get(
                url,
                headers=self._headers(referer),
                timeout=timeout,
                allow_redirects=True,
                verify=False,
            )
            resp.encoding = resp.apparent_encoding or "utf-8"
            if resp.status_code >= 400:
                return ""
            return resp.text
        except Exception:
            return ""

    def _parse_classes(self, html_text):
        soup = self._soup(html_text)
        if not soup:
            return []
        classes = []
        seen = set()
        for a in soup.select("nav.header-nav a[href*='m=list'][href*='u=']"):
            href = html.unescape(a.get("href") or "")
            qs = parse.parse_qs(parse.urlparse(href).query)
            tid = (qs.get("u") or [""])[0]
            name = self._clean_text(a.get_text(" "))
            if tid and tid not in seen and name:
                seen.add(tid)
                classes.append({"type_id": tid, "type_name": name})
        return classes

    def _build_filters(self, classes):
        filters = {}
        known = {c["type_id"] for c in classes}
        for tid, items in self.SUB_CATEGORIES.items():
            if tid in known or not known:
                filters[tid] = [{
                    "key": "k",
                    "name": "分类",
                    "value": [{"n": name, "v": val} for val, name in items],
                }]
        return filters

    def _parse_cards(self, html_text):
        soup = self._soup(html_text)
        if not soup:
            return []

        videos = []
        seen = set()
        for a in soup.select("a.video-card[href*='m=play'][href*='u='][href*='k=']"):
            href = html.unescape(a.get("href") or "")
            detail_url, u, k = self._normalize_detail_id(href)
            if not u or not k:
                continue
            vod_id = self._make_detail_id(u, k, detail_url)
            if vod_id in seen:
                continue
            seen.add(vod_id)

            img = a.select_one("img")
            title = ""
            pic = ""
            if img:
                title = img.get("alt") or ""
                pic = img.get("data-src") or img.get("data-original") or img.get("src") or ""
            title_node = a.select_one(".video-title")
            if title_node:
                title = title or title_node.get_text(" ")
            time_node = a.select_one(".video-time")
            remark = self._clean_text(time_node.get_text(" ")) if time_node else ""

            title = self._clean_text(title) or k
            videos.append({
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": self._absolute_url(pic),
                "vod_remarks": remark,
            })
        return videos

    def _parse_pagecount(self, html_text):
        text = html.unescape(html_text or "")
        patterns = [
            r"第\s*\d+\s*/\s*(\d+)\s*页",
            r'data-total=["\'](\d+)["\']',
            r"[?&]p=(\d+)[^\"'>]*[\"'][^>]*>\s*末页",
        ]
        nums = []
        for pattern in patterns:
            nums.extend(int(x) for x in re.findall(pattern, text) if str(x).isdigit())
        if nums:
            return max(nums)
        return 1

    def _resolve_player_url(self, url, visited=None, depth=0):
        if not url or depth > 5:
            return ""
        url = self._absolute_url(url)
        embedded_media = self._extract_player_path_media(url)
        if embedded_media:
            return embedded_media
        if self._is_media_url(url):
            return url
        visited = visited or set()
        if url in visited:
            return ""
        visited.add(url)

        html_text = self._fetch_text(url, referer=self.siteUrl + "/")
        if not html_text:
            return ""
        html_text = html.unescape(html_text).replace("\\/", "/")

        media = self._extract_media(html_text)
        if media:
            return self._absolute_url(media)

        iframe = self._first_match(html_text, [
            r'<iframe[^>]+src=["\']([^"\']+)["\']',
            r'<source[^>]+src=["\']([^"\']+)["\']',
            r'<video[^>]+src=["\']([^"\']+)["\']',
        ])
        if iframe:
            return self._resolve_player_url(iframe, visited=visited, depth=depth + 1)
        return ""

    def _extract_media(self, text):
        patterns = [
            r'(https?://[^"\'<>\s]+?\.m3u8[^"\'<>\s]*)',
            r'(https?://[^"\'<>\s]+?\.mp4[^"\'<>\s]*)',
            r'["\']url["\']\s*:\s*["\']([^"\']+\.(?:m3u8|mp4)[^"\']*)["\']',
            r'["\']src["\']\s*:\s*["\']([^"\']+\.(?:m3u8|mp4)[^"\']*)["\']',
            r'player_aaaa\s*=\s*["\']([^"\']+\.(?:m3u8|mp4)[^"\']*)["\']',
            r'var\s+url\s*=\s*["\']([^"\']+\.(?:m3u8|mp4)[^"\']*)["\']',
            r'atob\(["\']([A-Za-z0-9+/=]+)["\']\)',
        ]
        for pattern in patterns:
            m = re.search(pattern, text, re.I | re.S)
            if not m:
                continue
            value = m.group(1).strip()
            if pattern.startswith("atob"):
                try:
                    import base64
                    value = base64.b64decode(value).decode("utf-8", "ignore")
                except Exception:
                    continue
            if self._is_media_url(value):
                return value
        return ""

    def _normalize_detail_id(self, raw):
        raw = html.unescape(str(raw or "")).strip()
        if raw.startswith("http"):
            url = raw
        elif raw.startswith("/"):
            url = self._absolute_url(raw)
        elif "|" in raw:
            u, k = raw.split("|", 1)
            url = f"{self.siteUrl}/?m=play&u={parse.quote(u)}&k={parse.quote(k, safe='')}"
            return url, u, k
        else:
            url = self.siteUrl + "/?" + raw.lstrip("?")

        parsed = parse.urlparse(url)
        qs = parse.parse_qs(parsed.query)
        u = (qs.get("u") or [""])[0]
        k = (qs.get("k") or [""])[0]

        m = re.search(r"/player/index\.php/([^/?#]+)/([^/?#]+)", parsed.path)
        if m:
            u = parse.unquote(m.group(1))
            k = parse.unquote(m.group(2))
            url = f"{self.siteUrl}/?m=play&u={parse.quote(u)}&k={parse.quote(k, safe='')}"

        return url, u, k

    def _make_detail_id(self, u, k, fallback_url=""):
        if u and k:
            return f"{u}|{k}"
        return fallback_url or ""

    def _extract_player_path_media(self, url):
        """提取 /player/index.php/{分类}/{URL编码媒体地址} 里的真实 m3u8/mp4。"""
        url = html.unescape(str(url or "")).strip()
        if not url:
            return ""
        parsed = parse.urlparse(self._absolute_url(url) if url.startswith("/") else url)
        m = re.search(r"/player/index\.php/([^/?#]+)/([^?#]+)", parsed.path)
        if not m:
            return ""
        encoded = m.group(2)
        decoded = parse.unquote(encoded).replace("\\/", "/")
        if parsed.query and "?" not in decoded:
            decoded = decoded + "?" + parsed.query
        return decoded if self._is_media_url(decoded) else ""

    def _absolute_url(self, url):
        url = html.unescape(str(url or "")).strip()
        if not url:
            return ""
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("http"):
            return url
        return parse.urljoin(self.siteUrl + "/", url)

    def _is_media_url(self, url):
        value = parse.unquote(str(url or "")).replace("\\/", "/")
        return bool(re.search(r"\.(m3u8|mp4)(?:\?|$|[&#])", value, re.I))

    def _player_result(self, url):
        header = {
            "User-Agent": self.UA,
            "Referer": self.siteUrl + "/",
        }
        return {
            "parse": 0 if self._is_media_url(url) else 1,
            "playUrl": "",
            "url": url,
            "header": header,
        }

    def _first_match(self, text, patterns):
        for pattern in patterns:
            m = re.search(pattern, text or "", re.I | re.S)
            if m:
                return m.group(1)
        return ""

    def _clean_text(self, value):
        value = re.sub(r"<[^>]+>", " ", str(value or ""))
        value = html.unescape(value)
        value = re.sub(r"\s+", " ", value)
        return value.strip()

    def _soup(self, html_text):
        if not BeautifulSoup or not html_text:
            return None
        return BeautifulSoup(html_text, "html.parser")


if __name__ == "__main__":
    sp = Spider()
    print(json.dumps(sp.homeContent(filter=True), ensure_ascii=False, indent=2))
