#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
══════════════════════════════════════════════════════════════════
moovie.c2v2.com — TVBox Spider v2.0
生成器: 遮天法 2.0 (RealmAutoRouter) → 浏览器实地分析重写
目标:  https://moovie.c2v2.com/
防御: CloudFlare（curl_cffi chrome131 指纹模拟绕过）
══════════════════════════════════════════════════════════════════

站点结构（浏览器实地分析 + 实测修正）:
  - 本站是 HTMX 单页应用。列表/搜索/详情均为「服务端渲染片段」，必须用
    HX-Request 等 HTMX 头请求，否则只回空壳（loading 骨架）→ 解析为空。
  - 发现页:  GET /discover?type=movie  (HX) → .movie-grid.discover-grid > .movie-card
  - 搜索API: GET /api/htmx/search?kw=...      (HX) → .search-result-card
  - 豆瓣卡:  GET /api/htmx/douban-card?kw=... (HX) → .dbc-card
  - 分类tab:  movie / tv / show / cartoon（走 /discover?type=）
  - 播放源:  详情用 kw 反查 /api/htmx/search 拿到 /play/<源>/<vod>?douban_id=
  - 播放页:  GET /play/<源>/<vod>?douban_id= （普通GET，不带HX）→ 服务端渲染
             initPlayer('...', '<真实m3u8>', {...})；带 HX 头反而 404。

PeekPro 兼容:
  - 双引擎策略：curl_cffi(chrome131指纹) / 标准 requests(PeekPro 接管 TLS)
  - curl_cffi 必须安装，否则回退到普通 requests 被 CloudFlare 拦截 → demo 兜底
  - 列表/搜索用完整 HTMX 头；播放页用普通浏览器头（UA/Accept/Accept-Language）

══════════════════════════════════════════════════════════════════
"""

import sys
import os
import re
import json
import time
import threading
import random
from urllib import parse
import urllib3

# 双引擎：curl_cffi 穿透 CloudFlare（本机/测试环境），标准 requests（PeekPro 接管网络层）
try:
    from curl_cffi import requests as requests
    HAS_CURL_CFFI = True
except ImportError:
    import requests
    HAS_CURL_CFFI = False

from bs4 import BeautifulSoup

urllib3.disable_warnings()


# ══════════════════════════════════════════════════════════════
# Moovie Spider — 浏览器实地分析重写 v2.0
# ══════════════════════════════════════════════════════════════


class MoovieSpider:
    """
    moovie.c2v2.com 专用爬虫

    CloudFlare 防护下的影视资源站，PeekPro 本地浏览器上下文负责穿透，
    spider 层专注 DOM 解析与 TVBox 标准数据格式输出。
    """

    SITE_URL = "https://moovie.c2v2.com"

    # ─── 分类定义（与 /discover 四个 tab 对齐）───
    DISCOVER_TYPES = {
        "movie": "热门电影",
        "tv": "热门剧集",
        "show": "热门综艺",
        "cartoon": "日本动画",
    }

    # ─── PeekPro 兜底 demo：站点完全不可达时使用 ───
    DEMO_LIST = [
        {
            "vod_id": "demo_1",
            "vod_name": "示例影片 — 网络暂时无法连接",
            "vod_pic": "",
            "vod_remarks": "不可达",
        },
        {
            "vod_id": "demo_2",
            "vod_name": "请检查 PeekPro 网络代理配置",
            "vod_pic": "",
            "vod_remarks": "Demo",
        },
        {
            "vod_id": "demo_3",
            "vod_name": "moovie.c2v2.com 爬虫 v2.0",
            "vod_pic": "",
            "vod_remarks": "兜底",
        },
    ]

    def __init__(self):
        self.siteUrl = self.SITE_URL
        self._local = threading.local()
        self._ua_pool = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        ]

    # ══════════════════════════════════════════════════════════
    # 源天书 · HTTP 引擎
    # ══════════════════════════════════════════════════════════

    @property
    def session(self) -> requests.Session:
        if not hasattr(self._local, "session"):
            self._local.session = requests.Session()
        return self._local.session

    def _random_ua(self) -> str:
        return random.choice(self._ua_pool)

    def _base_headers(self) -> dict:
        """
        完整浏览器头（与成功范例一致）。只发 UA 反而更像爬虫；
        真正触发 CloudFlare 的是 TLS 指纹，要靠 curl_cffi 模拟，而非靠砍请求头。
        """
        return {
            "User-Agent": self._random_ua(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
                      "image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

    def fetch(self, url: str, referer: str = "", timeout: int = 15,
              htmx: bool = False, hx_target: str = "",
              hx_current: str = "") -> str:
        """
        统一请求入口。

        关键：本站是 HTMX 单页应用。列表/搜索/详情等「内容接口」必须用 HTMX 头
        （HX-Request: true + HX-Target + HX-Current-URL）请求，否则服务端只回
        18721 字节的空壳 HTML（loading 骨架），解析结果为空 → demo 兜底。

        播放页 /play/<源>/<vod> 则必须「不带」HX 头用普通 GET，服务端才会把
        真实 m3u8 渲染进 HTML（带 HX 头会被当成不存在的片段路由返回 404）。
        """
        headers = self._base_headers()
        if referer:
            headers["Referer"] = referer
        if htmx:
            headers["HX-Request"] = "true"
            if hx_target:
                headers["HX-Target"] = hx_target
            headers["HX-Current-URL"] = hx_current or url
            if not referer:
                headers["Referer"] = self.siteUrl + "/"

        try:
            if HAS_CURL_CFFI:
                resp = requests.get(
                    url, headers=headers, timeout=timeout, allow_redirects=True,
                    impersonate="chrome131", verify=False
                )
            else:
                resp = self.session.get(
                    url, headers=headers, timeout=timeout, allow_redirects=True,
                    verify=False
                )
            # curl_cffi 的 Response 没有 apparent_encoding；标准 requests 有。
            # 用 getattr 兼容两者，避免出现 AttributeError 导致整次 fetch 失败。
            enc = getattr(resp, "apparent_encoding", None)
            if enc:
                try:
                    resp.encoding = enc
                except Exception:
                    pass
            return resp.text
        except Exception as e:
            print(
                f"[moovie_spider fetch error] url={url} "
                f"error={type(e).__name__}: {e}",
                file=sys.stderr,
            )
            return ""

    def fix_url(self, url: str) -> str:
        if not url:
            return ""
        if url.startswith("http"):
            return url
        if url.startswith("//"):
            return f"https:{url}"
        if url.startswith("/"):
            return f"{self.siteUrl.rstrip('/')}{url}"
        return f"{self.siteUrl.rstrip('/')}/{url}"

    @staticmethod
    def clean_title(title: str) -> str:
        import html as _html

        t = _html.unescape(title or "")
        t = re.sub(r"<[^>]+>", "", t)
        return t.strip()

    # ══════════════════════════════════════════════════════════
    # TVBox 标准接口
    # ══════════════════════════════════════════════════════════

    def homeContent(self, filter: bool = False) -> dict:
        """
        首页 — 发现页「热门电影」分类。

        DOM: .movie-grid.discover-grid > .movie-card
          ├── a[href="/search?kw=...&doubanId=..."]
          ├── .movie-poster > img[src="/api/proxy/image/..."]
          ├── .movie-title (h3)
          └── .movie-rating (可选)
        """
        if filter:
            return self._home_filter()

        classes = [
            {"type_name": name, "type_id": tid}
            for tid, name in self.DISCOVER_TYPES.items()
        ]

        html = self.fetch(
            f"{self.siteUrl}/discover/movie",
            htmx=True, hx_target="#discover-content",
            hx_current=f"{self.siteUrl}/discover",
        )
        if not html:
            return {"class": classes, "list": self.DEMO_LIST, "filters": {}}

        soup = BeautifulSoup(html, "html.parser")
        videos = self._parse_movie_cards(soup)

        if not videos:
            videos = self.DEMO_LIST

        return {"class": classes, "list": videos, "filters": {}}

    def _home_filter(self) -> dict:
        """filter=True：返回筛选配置。站点无复杂筛选，仅返回分类 + 示例列表。"""
        classes = [
            {"type_name": name, "type_id": tid}
            for tid, name in self.DISCOVER_TYPES.items()
        ]
        return {"class": classes, "list": self.DEMO_LIST, "filters": {}}

    def homeVideoContent(self) -> dict:
        """按分类加载：/discover?type={type_id}"""
        classes = [
            {"type_name": name, "type_id": tid}
            for tid, name in self.DISCOVER_TYPES.items()
        ]
        html = self.fetch(
            f"{self.siteUrl}/discover?type=movie",
            htmx=True, hx_target="#discover-content",
            hx_current=f"{self.siteUrl}/discover",
        )
        if not html:
            return {"class": classes, "list": self.DEMO_LIST, "filters": {}}
        soup = BeautifulSoup(html, "html.parser")
        videos = self._parse_movie_cards(soup)
        if not videos:
            videos = self.DEMO_LIST
        return {"class": classes, "list": videos, "filters": {}}

    # ══════════════════════════════════════════════════════════
    # 通用 .movie-card 解析（发现页 / 分类）
    # ══════════════════════════════════════════════════════════

    def _parse_movie_cards(self, soup: BeautifulSoup) -> list:
        """解析 .movie-grid > .movie-card 列表"""
        cards = soup.select(".movie-grid .movie-card")
        if not cards:
            cards = soup.select(".movie-card")
        videos = []
        for card in cards:
            link = card.find("a", href=True)
            if not link:
                continue

            href = link.get("href", "")
            douban_id = ""
            kw = ""
            if "doubanId=" in href or "kw=" in href:
                parsed = parse.parse_qs(parse.urlparse(href).query)
                douban_id = parsed.get("doubanId", [""])[0]
                kw = parsed.get("kw", [""])[0]

            # vod_id 优先用影片名(kw)，详情页靠它反查所有播放源；
            # 兜底 doubanId / href。
            vod_id = kw if kw else (douban_id if douban_id else href)

            # 标题: .movie-title
            title_el = card.select_one(".movie-title")
            vod_name = self.clean_title(
                title_el.get_text(strip=True)
                if title_el
                else (title_el.get("title", "") if title_el else kw)
            )

            # 封面: .movie-poster img
            img_el = card.select_one(".movie-poster img")
            vod_pic = ""
            if img_el:
                vod_pic = self.fix_url(
                    img_el.get("src") or img_el.get("data-src", "")
                )

            # 评分: .movie-rating
            rating_el = card.select_one(".movie-rating")
            vod_remarks = (
                rating_el.get_text(strip=True) if rating_el else ""
            )

            if vod_name:
                videos.append({
                    "vod_id": vod_id,
                    "vod_name": vod_name,
                    "vod_pic": vod_pic,
                    "vod_remarks": vod_remarks,
                })
        return videos

    # ══════════════════════════════════════════════════════════
    # categoryContent — 搜索 + 分页
    # ══════════════════════════════════════════════════════════

    def categoryContent(self, tid: str, pg: str = "1",
                        filter: bool = False, extend: dict = None) -> dict:
        """
        分类列表。

        - tid ∈ {movie,tv,show,cartoon}：走发现页 /discover?type=<tid>（HTMX 片段）。
        - 其它 tid（自定义关键词）：走搜索 /api/htmx/search?kw=<tid>（HTMX 片段）。
        """
        page = int(pg) if pg else 1

        if tid in self.DISCOVER_TYPES:
            html = self.fetch(
                f"{self.siteUrl}/discover/{tid}",
                htmx=True, hx_target="#discover-content",
                hx_current=f"{self.siteUrl}/discover",
            )
            soup = BeautifulSoup(html, "html.parser") if html else None
            videos = self._parse_movie_cards(soup) if soup else []
        else:
            keyword = parse.unquote(tid) if tid else tid
            html = self.fetch(
                f"{self.siteUrl}/api/htmx/search?kw={parse.quote(keyword)}",
                htmx=True, hx_target="#search-results-container",
                hx_current=f"{self.siteUrl}/search?kw={parse.quote(keyword)}",
            )
            soup = BeautifulSoup(html, "html.parser") if html else None
            videos = self._parse_search_cards(soup) if soup else []

        if not videos:
            videos = self.DEMO_LIST

        return {
            "list": videos,
            "page": page,
            "pagecount": 1,
            "limit": len(videos),
            "total": len(videos),
        }

    def _search_with_pagination(self, keyword: str, page: int = 1) -> tuple:
        """
        搜索 + 分页。

        第一页加载完整搜索页 /search?kw=...，解析卡片 + 页数；
        后续页调用 /api/htmx/search?kw={}&page={} 获取 HTML 片段。
        返回 (videos, pagecount, total)。
        """
        videos = []

        if page == 1:
            url = f"{self.siteUrl}/search?kw={parse.quote(keyword)}"
        else:
            url = f"{self.siteUrl}/api/htmx/search?kw={parse.quote(keyword)}&page={page}"

        html = self.fetch(url, referer=f"{self.siteUrl}/search?kw={parse.quote(keyword)}")
        if not html:
            return videos, 1, 0

        soup = BeautifulSoup(html, "html.parser")

        # 解析两种卡片
        videos = self._parse_search_cards(soup)

        # 分页按钮: button.pagination-btn
        page_btns = soup.select("button.pagination-btn")
        total_page = 1
        for btn in page_btns:
            text = btn.get_text(strip=True)
            try:
                n = int(text)
                total_page = max(total_page, n)
            except ValueError:
                pass
        # 取 hx-get 中的 page 参数最大值
        for btn in page_btns:
            hx_get = btn.get("hx-get", "")
            if "page=" in hx_get:
                parsed = parse.parse_qs(parse.urlparse(hx_get).query)
                p = int(parsed.get("page", ["1"])[0])
                total_page = max(total_page, p)

        total = total_page * len(videos) if videos else 0
        return videos, total_page, total

    def _parse_search_cards(self, soup: BeautifulSoup) -> list:
        """
        解析搜索结果页两种卡片:
          - .dbc-card（豆瓣收录）
          - .search-result-card（普通资源）
        """
        videos = []

        # ─── 豆瓣收录卡片 .dbc-card ───
        for card in soup.select(".dbc-card"):
            href = card.get("href", "")
            # 提取 douban_id: /movie/{douban_id}
            douban_id = ""
            m = re.search(r"/movie/(\d+)", href)
            if m:
                douban_id = m.group(1)

            title_el = card.select_one(".dbc-title")
            year_el = card.select_one(".dbc-year")
            img_el = card.select_one(".dbc-poster img")
            rating_el = card.select_one(".dbc-rating-val")
            tags_el = card.select(".dbc-tag")
            summary_el = card.select_one(".dbc-summary")

            vod_name = self.clean_title(
                title_el.get_text(strip=True) if title_el else ""
            )
            year = year_el.get_text(strip=True) if year_el else ""
            vod_pic = self.fix_url(img_el.get("src", "")) if img_el else ""
            rating = rating_el.get_text(strip=True) if rating_el else ""
            tags = " ".join(t.get_text(strip=True) for t in tags_el)
            summary = summary_el.get_text(" ", strip=True) if summary_el else ""

            # 备注组合
            parts = []
            if year:
                parts.append(year)
            if rating:
                parts.append(rating)
            if tags:
                parts.append(tags)
            vod_remarks = " / ".join(parts)

            if vod_name:
                videos.append({
                    "vod_id": douban_id or href,
                    "vod_name": f"{vod_name} {year}".strip() if year else vod_name,
                    "vod_pic": vod_pic,
                    "vod_remarks": vod_remarks,
                    "vod_content": summary,
                    "type_name": tags,
                })

        # ─── 普通资源卡片 .search-result-card ───
        for card in soup.select(".search-result-card"):
            href = card.get("href", "")
            # /play/{name}/{vod_id}?douban_id=...
            douban_id = ""
            parsed_qs = parse.parse_qs(parse.urlparse(href).query)
            douban_id = parsed_qs.get("douban_id", [""])[0]

            title_el = card.select_one(".card-title")
            year_el = card.select_one(".card-year")
            region_el = card.select_one(".card-region")
            type_el = card.select_one(".card-type")
            img_el = card.select_one(".card-poster img")
            remarks_el = card.select_one(".card-remarks")
            badge_el = card.select_one(".card-badge")
            director_el = card.select_one(".card-director")

            vod_name = self.clean_title(
                title_el.get_text(strip=True) if title_el else ""
            )
            vod_pic = ""
            if img_el:
                vod_pic = self.fix_url(
                    img_el.get("src") or img_el.get("data-src", "")
                )

            # 备注
            parts = []
            if year_el:
                parts.append(year_el.get_text(strip=True))
            if type_el:
                parts.append(type_el.get_text(strip=True))
            if badge_el:
                parts.append(badge_el.get_text(strip=True))
            if remarks_el:
                parts.append(remarks_el.get_text(strip=True))
            vod_remarks = " / ".join(parts) if parts else ""

            if vod_name:
                videos.append({
                    "vod_id": vod_name or douban_id or href,
                    "vod_name": vod_name,
                    "vod_pic": vod_pic,
                    "vod_remarks": vod_remarks,
                    "vod_director": (
                        director_el.get_text(strip=True)
                        if director_el
                        else ""
                    ),
                })

        return videos

    # ══════════════════════════════════════════════════════════
    # detailContent — 详情页
    # ══════════════════════════════════════════════════════════

    def detailContent(self, ids: list) -> dict:
        """
        详情页。

        列表项 vod_id 存的是「影片名(kw)」。这里用 kw 调
        /api/htmx/search?kw=<kw>（HTMX 片段）拿到该片全部
        /play/<源>/<vod>?douban_id= 播放源，构建 TVBox 标准 play_from/play_url。

        兼容：vod_id 也可能是纯数字 douban_id 或直接的 /play/... 路径。
        """
        vid = ids[0] if ids else ""
        if not vid:
            return {"list": [self._empty_vod(vid)]}

        if vid.startswith("http") or "/play/" in vid or "/movie/" in vid:
            if "/play/" in vid:
                return self._detail_from_play_path(vid)
            # /movie/<id> 或 http：抽片名再反查
            html = self.fetch(self.fix_url(vid))
            kw = self._extract_title_from_html(html) if html else ""
        elif re.match(r"^\d+$", vid):
            html = self.fetch(f"{self.siteUrl}/movie/{vid}")
            kw = self._extract_title_from_html(html) if html else ""
        else:
            kw = parse.unquote(vid)

        if not kw:
            return {"list": [self._empty_vod(vid)]}

        search_html = self.fetch(
            f"{self.siteUrl}/api/htmx/search?kw={parse.quote(kw)}",
            htmx=True, hx_target="#search-results-container",
            hx_current=f"{self.siteUrl}/search?kw={parse.quote(kw)}",
        )
        dbc_html = self.fetch(
            f"{self.siteUrl}/api/htmx/douban-card?kw={parse.quote(kw)}",
            htmx=True, hx_target="#douban-card-container",
            hx_current=f"{self.siteUrl}/search?kw={parse.quote(kw)}",
        )
        return self._build_detail(vid, kw, search_html, dbc_html)

    @staticmethod
    def _extract_title_from_html(html: str) -> str:
        """从详情页抽片名（用于 douban_id 反查）。"""
        if not html:
            return ""
        soup = BeautifulSoup(html, "html.parser")
        el = (
            soup.select_one(".dbc-title")
            or soup.select_one("h1")
            or soup.select_one(".movie-title")
            or soup.select_one(".play-title")
        )
        if el:
            return el.get_text(strip=True)
        for tag in soup.find_all(["h1", "h2", "h3"]):
            t = tag.get_text(strip=True)
            if t:
                return t
        return ""

    def _detail_from_play_path(self, vid: str) -> dict:
        """vod_id 直接是 /play/... 路径时，构造单源详情。"""
        full = self.fix_url(vid)
        source = ""
        m = re.search(r"/play/([^/]+)/", full)
        if m:
            source = parse.unquote(m.group(1))
        vod_name = source or "未知"
        return {
            "list": [{
                "vod_id": vid,
                "vod_name": vod_name,
                "vod_pic": "",
                "vod_content": "",
                "vod_remarks": "",
                "vod_play_from": source or "默认源",
                "vod_play_url": f"正片${full}",
                "type_name": "",
                "vod_director": "",
                "vod_actor": "",
                "vod_area": "",
                "vod_lang": "",
                "vod_year": "",
            }]
        }

    @staticmethod
    def _extract_episodes(phtml: str):
        """从播放页 JS 中提取 episodeList（电视剧多集 / 电影单集「正片」）。"""
        if not phtml:
            return []
        m = re.search(r"episodeList\s*=\s*(\[.*?\]);", phtml, re.S)
        if not m:
            return []
        try:
            arr = json.loads(m.group(1))
        except Exception:
            return []
        out = []
        if isinstance(arr, list):
            for e in arr:
                if isinstance(e, dict) and e.get("url"):
                    out.append((e.get("title") or "正片", e.get("url")))
        return out

    def _build_detail(self, vid: str, kw: str, search_html: str, dbc_html: str) -> dict:
        """用 /api/htmx/search 的 /play/... 链接构建 TVBox 详情。"""
        play_from_list = []
        play_url_list = []  # 每个源一组 episode 字符串

        if search_html:
            soup = BeautifulSoup(search_html, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a.get("href", "")
                if "/play/" not in href:
                    continue
                full = self.fix_url(href)
                m = re.search(r"/play/([^/]+)/([^/?#]+)", full)
                source = parse.unquote(m.group(1)) if m else f"源{len(play_from_list) + 1}"
                if source in play_from_list:
                    continue
                play_from_list.append(source)
                # 取播放页，提取 episodeList（电视剧多集 / 电影单集「正片」）
                phtml = self.fetch(full)  # 普通 GET，不带 HX
                eps = self._extract_episodes(phtml)
                if eps:
                    play_url_list.append([f"{t}${self.fix_url(u)}" for t, u in eps])
                else:
                    play_url_list.append([f"正片${full}"])

        # 封面 / 简介 / 标题（来自豆瓣卡片片段）
        vod_pic = ""
        vod_content = ""
        vod_name = kw or "未知"
        vod_remarks = ""
        if dbc_html:
            dsoup = BeautifulSoup(dbc_html, "html.parser")
            img_el = dsoup.select_one(".dbc-poster img")
            if img_el:
                vod_pic = self.fix_url(img_el.get("src", ""))
            sum_el = dsoup.select_one(".dbc-summary")
            if sum_el:
                vod_content = sum_el.get_text(" ", strip=True)
            t_el = dsoup.select_one(".dbc-title")
            if t_el:
                vod_name = self.clean_title(t_el.get_text(strip=True)) or vod_name

        if not play_from_list:
            return {"list": [self._empty_vod(vid)]}

        return {
            "list": [{
                "vod_id": vid,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_content": vod_content,
                "vod_remarks": vod_remarks,
                "vod_play_from": "$$$".join(play_from_list),
                "vod_play_url": "$$$".join(
                    "#".join(eps) for eps in play_url_list
                ),
                "type_name": "",
                "vod_director": "",
                "vod_actor": "",
                "vod_area": "",
                "vod_lang": "",
                "vod_year": "",
            }]
        }

    def _parse_dbc_detail(self, dbc, vid: str, soup) -> dict:
        """解析豆瓣详情页"""
        title_el = (
            soup.select_one(".dbc-title")
            or dbc.select_one("h1")
            or dbc.select_one(".title")
        )
        img_el = soup.select_one(".dbc-poster img") or dbc.select_one("img")
        summary_el = soup.select_one(".dbc-summary") or dbc.select_one(".summary")
        rating_el = soup.select_one(".dbc-rating-val")
        year_el = soup.select_one(".dbc-year")
        tags_el = soup.select(".dbc-tag")

        vod_name = self.clean_title(title_el.get_text(strip=True)) if title_el else ""
        vod_pic = self.fix_url(img_el.get("src", "")) if img_el else ""
        vod_content = (
            summary_el.get_text("\n", strip=True) if summary_el else ""
        )
        vod_remarks = (
            f"{year_el.get_text(strip=True)} / {rating_el.get_text(strip=True)}"
            if year_el and rating_el
            else (year_el.get_text(strip=True) if year_el else "")
        )

        # 播放列表：资源卡片 .search-result-card
        play_from_list = []
        play_url_list = []
        for card in soup.select(".search-result-card"):
            source_el = card.select_one(".source-item")
            title_el = card.select_one(".card-title")
            href = card.get("href", "")

            source_name = (
                source_el.get_text(strip=True)
                if source_el
                else f"源{len(play_from_list) + 1}"
            )
            ep_title = (
                title_el.get_text(strip=True)
                if title_el
                else source_name
            )
            play_url = self.fix_url(href) if href else ""

            if source_name not in play_from_list:
                play_from_list.append(source_name)
                play_url_list.append([f"{ep_title}${play_url}"])
            else:
                idx = play_from_list.index(source_name)
                play_url_list[idx].append(f"{ep_title}${play_url}")

        return {
            "list": [{
                "vod_id": vid,
                "vod_name": vod_name or "未知",
                "vod_pic": vod_pic,
                "vod_content": vod_content,
                "vod_remarks": vod_remarks,
                "vod_play_from": "$$$".join(play_from_list) if play_from_list else "默认源",
                "vod_play_url": "$$$".join(
                    "#".join(eps) for eps in play_url_list
                ) if play_url_list else "",
                "type_name": "",
                "vod_director": "",
                "vod_actor": "",
                "vod_area": "",
                "vod_lang": "",
                "vod_year": "",
            }]
        }

    def _parse_play_detail(self, soup, vid: str, url: str) -> dict:
        """解析普通播放页"""
        title_el = soup.select_one("h1, h2, .card-title, .play-title")
        img_el = soup.select_one(".card-poster img, .play-poster img")
        remarks_el = soup.select_one(".card-remarks, .card-badge")
        source_el = soup.select_one(".source-item.active, .source-item")

        vod_name = self.clean_title(title_el.get_text(strip=True)) if title_el else vid
        vod_pic = self.fix_url(img_el.get("src", "")) if img_el else ""
        vod_remarks = remarks_el.get_text(strip=True) if remarks_el else ""

        source_name = source_el.get_text(strip=True) if source_el else "默认源"
        play_url = url

        return {
            "list": [{
                "vod_id": vid,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_remarks": vod_remarks,
                "vod_content": "",
                "vod_play_from": source_name,
                "vod_play_url": f"{vod_name}${play_url}",
                "type_name": "",
                "vod_director": "",
                "vod_actor": "",
                "vod_area": "",
                "vod_lang": "",
                "vod_year": "",
            }]
        }

    @staticmethod
    def _empty_vod(vid: str) -> dict:
        return {
            "vod_id": vid,
            "vod_name": "加载失败",
            "vod_pic": "",
            "vod_remarks": "",
            "vod_content": "",
            "vod_play_from": "默认源",
            "vod_play_url": "",
            "type_name": "",
            "vod_director": "",
            "vod_actor": "",
            "vod_area": "",
            "vod_lang": "",
            "vod_year": "",
        }

    # ══════════════════════════════════════════════════════════
    # playerContent — 播放解析
    # ══════════════════════════════════════════════════════════

    def playerContent(self, flag: str, id: str, vipFlags: str) -> dict:
        """从播放页提取 m3u8/mp4 直链。"""
        # 直链直接返回
        if id.startswith("http") and any(
            ext in id.lower()
            for ext in [".m3u8", ".mp4", ".flv", ".mkv", ".ts", ".avi"]
        ):
            return {"parse": 0, "url": id, "header": ""}

        if not id.startswith("http"):
            id = f"{self.siteUrl.rstrip('/')}/{id.lstrip('/')}"

        # 播放页必须「不带」HX 头用普通 GET，服务端才会渲染真实 m3u8
        html = self.fetch(id)
        if not html:
            return {"parse": 1, "url": id, "header": ""}

        # 服务端把 m3u8 写进 initPlayer('...', '<url>', {...})，且对 / 做了 \/ 转义
        html = html.replace("\\/", "/")

        extract_layers = [
            (lambda h: re.search(r"initPlayer\(\s*'[^']*'\s*,\s*'([^']+)'\s*,", h), "initPlayer"),
            (lambda h: re.search(r'src="([^"]+\.m3u8[^"]*)"', h), "m3u8"),
            (lambda h: re.search(r"src='([^']+\.m3u8[^']*)'", h), "m3u8'"),
            (lambda h: re.search(r'src="([^"]+\.mp4[^"]*)"', h), "mp4"),
            (lambda h: re.search(r"url\s*:\s*['\"]([^'\"]+\.m3u8[^'\"]*)", h), "js"),
            (lambda h: re.search(r'"url"\s*:\s*"([^"]+\.m3u8[^"]*)"', h), "json"),
            (lambda h: re.search(r'<video[^>]+src=["\']([^"\']+)["\']', h), "video"),
            (lambda h: re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', h), "iframe"),
        ]

        for extractor, _ in extract_layers:
            m = extractor(html)
            if m:
                real_url = m.group(1).strip()
                if not real_url.startswith("http"):
                    real_url = self.fix_url(real_url)
                return {
                    "parse": 0,
                    "url": real_url,
                    "header": f"Referer={self.siteUrl}/",
                }

        return {"parse": 1, "url": id, "header": ""}

    # ══════════════════════════════════════════════════════════
    # searchContent — 搜索入口
    # ══════════════════════════════════════════════════════════

    def searchContent(self, key: str, quick: str = "", pg: str = "1") -> dict:
        """
        搜索 — GET /api/htmx/search?kw={key}（HTMX 片段），解析 .search-result-card。
        注意：必须带 HX 头，否则 /api/htmx/* 直接 404。
        """
        page = int(pg) if pg else 1
        kw = parse.unquote(key) if key else key

        url = f"{self.siteUrl}/api/htmx/search?kw={parse.quote(kw)}"
        html = self.fetch(
            url, htmx=True, hx_target="#search-results-container",
            hx_current=f"{self.siteUrl}/search?kw={parse.quote(kw)}",
        )
        if not html:
            return {"list": self.DEMO_LIST, "page": page, "pagecount": 1}

        soup = BeautifulSoup(html, "html.parser")
        videos = self._parse_search_cards(soup)

        if not videos:
            videos = self.DEMO_LIST

        return {"list": videos, "page": page, "pagecount": 1}

    # ══════════════════════════════════════════════════════════
    # 工具接口
    # ══════════════════════════════════════════════════════════

    def localProxy(self, param: dict) -> list:
        return [404, "text/plain", "moovie spider 不提供本地代理"]

    def init(self, extend: str = "") -> bool:
        return True


# ══════════════════════════════════════════════════════════════
# drpy / TVBox / PeekPro 框架要求顶层类名为 Spider
# 用「真正的子类」而非别名，确保两种加载方式都能命中：
#   - getattr(module, "Spider")       -> 模块级属性名就是 Spider
#   - obj.__name__ == "Spider"        -> 类名本身就是 Spider
# ══════════════════════════════════════════════════════════════

class Spider(MoovieSpider):
    """PeekPro / TVBox 标准入口（顶层 Spider 类）"""
    pass


# ══════════════════════════════════════════════════════════════
# 测试 & CLI
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="moovie.c2v2.com — TVBox Spider v2.0 (PeekPro)"
    )
    parser.add_argument("--home", action="store_true", help="测试 homeContent")
    parser.add_argument(
        "--category", default=None, help="测试 categoryContent (type_id)"
    )
    parser.add_argument(
        "--detail", default=None, help="测试 detailContent (vod_id)"
    )
    parser.add_argument(
        "--player", default=None, help="测试 playerContent (play_url)"
    )
    parser.add_argument(
        "--search", default=None, help="测试 searchContent (keyword)"
    )
    parser.add_argument("--all", action="store_true", help="运行全部测试")
    args = parser.parse_args()

    spider = Spider()

    if args.all or args.home:
        print(">>> [homeContent]")
        result = spider.homeContent()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print()

    if args.all or args.category:
        tid = args.category or "movie"
        print(f">>> [categoryContent] type_id={tid}")
        result = spider.categoryContent(tid=tid, pg="1")
        print(f"    共 {len(result.get('list', []))} 条, {result.get('pagecount', 1)} 页")
        for v in result.get("list", [])[:3]:
            print(f"    - {v.get('vod_name', '?')[:40]}")
        print()

    if args.all or args.detail:
        vid = args.detail or "demo_1"
        print(f">>> [detailContent] id={vid}")
        result = spider.detailContent([vid])
        vod = result.get("list", [{}])[0]
        print(f"    片名: {vod.get('vod_name', '?')}")
        print(f"    播放源: {vod.get('vod_play_from', '?')}")
        print()

    if args.all or args.player:
        pid = args.player or "https://moovie.c2v2.com/play/test-1.html"
        print(f">>> [playerContent] url={pid}")
        result = spider.playerContent(flag="", id=pid, vipFlags="")
        print(f"    parse={result.get('parse')} url={result.get('url', '')[:80]}")
        print()

    if args.all or args.search:
        kw = args.search or "小丑"
        print(f">>> [searchContent] key={kw}")
        result = spider.searchContent(key=kw)
        print(f"    共 {len(result.get('list', []))} 条, {result.get('pagecount', 1)} 页")
        for v in result.get("list", [])[:3]:
            print(f"    - {v.get('vod_name', '?')[:40]}")
        print()

    if not any(
        [args.home, args.category, args.detail, args.player, args.search, args.all]
    ):
        print("moovie.c2v2.com Spider v2.0 就绪（PeekPro 兼容）")
        print(f"  站点: {spider.siteUrl}")
        print(f"  分类: {list(spider.DISCOVER_TYPES.keys())}")
        print(f"  网络: PeekPro 浏览器上下文负责 CloudFlare 穿透")
        print()
        print("用法:")
        print("  python moovie_spider.py --all            # 运行全部测试")
        print("  python moovie_spider.py --home           # 测试首页")
        print("  python moovie_spider.py --search 小丑     # 搜索测试")
        print("  python moovie_spider.py --category tv    # 分类测试")
