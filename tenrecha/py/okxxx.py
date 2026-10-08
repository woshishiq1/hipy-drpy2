#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
══════════════════════════════════════════════════════════════════
okxxx 播放器规则脚本 — TVBox / drpy 爬虫源（自包含单文件版）
══════════════════════════════════════════════════════════════════

【适配站点】
  https://okxxx.art （成人视频站，/enter 为年龄确认页，带 cookie 直接访问即可绕过）

【核心能力】
  - 视频列表解析（首页 / 50 分类 / 搜索）
  - 视频详情提取（标题、缩略图、多清晰度播放地址）
  - 播放地址提取：详情页 <source> 直链 mp4，优先 720p 最高清
  - 多分类支持：/sites/ 下 50 个频道分类

【依赖安装】
    pip install requests beautifulsoup4

【命令行用法】
    python okxxx.py                          # 自检模式
    python okxxx.py --test-home              # 测试首页
    python okxxx.py --test-category          # 测试分类
    python okxxx.py --test-detail            # 测试详情
    python okxxx.py --test-search            # 测试搜索
    python okxxx.py --test-player            # 测试播放

作者：File Agent
版本：1.0.0
══════════════════════════════════════════════════════════════════
"""

import sys
import os
import re
import json
import time
import random
from urllib import parse
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup


# ══════════════════════════════════════════════════════════════
# 站点配置
# ══════════════════════════════════════════════════════════════
SITE_URL = "https://okxxx.art"

# 年龄确认 cookie（绕过 /enter 确认页）
AUTH_COOKIE = {"x-index-auth": "authed"}

# 分类映射: TVBox type_id -> 站点 slug（50 个频道，取自 /channels/）
CATEGORY_MAP = {
    "brazzers": "Brazzers",
    "naughty-america": "Naughty America",
    "realitykings": "Reality Kings",
    "bangbros": "Bang Bros",
    "nubiles-porn": "Nubiles Porn",
    "bang": "Bang!",
    "blacked-com": "Blacked.Com",
    "scoreland": "Scoreland",
    "adult-prime": "Adult Prime",
    "teamskeet": "Team Skeet",
    "sexmex": "SexMex",
    "mylf": "MYLF",
    "adulttime": "Adult Time",
    "familystrokes": "Family Strokes",
    "babes-com": "Babes.Com",
    "private": "Private",
    "czech-av": "Czech AV",
    "public-agent": "Public Agent",
    "porn-cz": "Porn CZ",
    "swappz": "Swappz",
    "dogfart-network": "Dogfart Network",
    "sexyhub": "Sexy Hub",
    "evil-angel": "Evil Angel",
    "dirty-flix": "Dirty Flix",
    "clubseventeen": "Club Sweethearts",
    "mofos": "Mofos",
    "dorcel-club": "Dorcel Club",
    "backroom-casting-couch": "Backroom Casting Couch",
    "perfect-gonzo": "Perfect Gonzo",
    "18-videoz": "18 VideoZ",
    "teenmegaworld": "Teen Mega World",
    "inka-sex": "Inka Sex",
    "wankz": "Wankz",
    "mom-lover": "Mom Lover",
    "bang-bus": "Bang Bus",
    "jav-hd": "Jav HD",
    "tugpass": "Tug Pass",
    "all-pornsites-pass-xxx": "All Pornsites Pass XXX",
    "cum4k": "Cum4K",
    "pervz": "Pervz",
    "devil-s-film": "Devil's Film",
    "atk-girlfriends": "ATK Girlfriends",
    "pure-taboo": "Pure Taboo",
    "ddf-network": "DDF Network",
    "mature-nl": "Mature NL",
    "karups": "Karups",
    "puba": "Puba",
    "hot-guys-fuck": "Hot Guys Fuck",
    "hot-wife-xxx": "Hot Wife XXX",
    "av-69": "AV 69",
}

# 分类列表（TVBox homeContent 返回格式）
HOME_CLASS = [
    {"type_name": name, "type_id": slug}
    for slug, name in CATEGORY_MAP.items()
]


# ══════════════════════════════════════════════════════════════
# UA 池
# ══════════════════════════════════════════════════════════════
UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/18.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_2 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 Chrome/131.0.0.0 Mobile Safari/537.36",
]


# ══════════════════════════════════════════════════════════════
# 基础工具类
# ══════════════════════════════════════════════════════════════
class BaseSpider:
    """基础爬虫——封装 HTTP 请求与通用工具方法"""

    def __init__(self):
        self.siteUrl = SITE_URL
        self.session = requests.Session()

    # ── HTTP 请求 ──

    def _random_ua(self) -> str:
        return random.choice(UA_POOL)

    def _build_headers(self, referer: str = None) -> Dict:
        h = {
            "User-Agent": self._random_ua(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",  # 排除 br（Brotli），requests 原生不支持
            "DNT": "1",
            "Connection": "keep-alive",
        }
        if referer:
            h["Referer"] = referer
        return h

    def fetch(self, url: str, referer: str = None, timeout: int = 15) -> str:
        """GET 请求，返回响应文本（自动携带年龄确认 cookie）"""
        headers = self._build_headers(referer)
        try:
            resp = self.session.get(url, headers=headers, cookies=AUTH_COOKIE,
                                    timeout=timeout, allow_redirects=True)
            resp.encoding = resp.apparent_encoding or "utf-8"
            return resp.text
        except Exception as e:
            print(f"[Fetch Error] {url}: {e}", file=sys.stderr)
            return ""

    # ── 工具方法 ──

    @staticmethod
    def fix_url(url: str, base: str) -> str:
        """补全相对路径为完整 URL"""
        if not url:
            return ""
        if url.startswith("http"):
            return url
        if url.startswith("//"):
            return f"https:{url}"
        if url.startswith("/"):
            return f"{base.rstrip('/')}{url}"
        return f"{base.rstrip('/')}/{url}"

    @staticmethod
    def clean_title(title: str) -> str:
        """清洗标题：HTML 实体解码 + 去除标签 + 去首尾空白"""
        import html as _html
        t = _html.unescape(title or "")
        t = re.sub(r"<[^>]+>", "", t)
        t = re.sub(r"\s+", " ", t)
        return t.strip()


# ══════════════════════════════════════════════════════════════
# 解析引擎
# ══════════════════════════════════════════════════════════════
class Parser:
    """页面解析器——从 HTML 中提取结构化数据"""

    # ── 列表解析 ──

    @staticmethod
    def parse_video_list(html: str, base_url: str) -> List[Dict]:
        """
        从首页 / 分类 / 搜索结果中提取视频卡片列表。

        站点 HTML 结构:
            div.item.thumb-bl-video > div.thumb > a[href="/video/{id}/"]
              ├─ title="标题" data-preview-custom="预览mp4"
              └─ img.thumb.lazy-load[data-original="封面图URL"]

        返回格式: [{"vod_id": str, "vod_name": str, "vod_pic": str}, ...]
        """
        soup = BeautifulSoup(html, "html.parser")
        videos = []
        seen = set()

        for a_tag in soup.select("a[href*='/video/']"):
            href = a_tag.get("href", "").strip()
            if not href or href in seen:
                continue
            seen.add(href)

            # 标题：优先 a 标签 title 属性，兜底 img alt
            title = a_tag.get("title", "").strip()
            if not title:
                img = a_tag.find("img")
                if img:
                    title = img.get("alt", "").strip()
            title = BaseSpider.clean_title(title) if title else "未知标题"

            # 封面图：img[data-original]（懒加载真实地址）
            pic = ""
            img = a_tag.find("img", class_="lazy-load")
            if img:
                pic = img.get("data-original", "") or img.get("src", "")
            pic = BaseSpider.fix_url(pic, base_url)

            videos.append({
                "vod_id": href,
                "vod_name": title,
                "vod_pic": pic,
            })

        return videos

    # ── 详情解析 ──

    @staticmethod
    def parse_video_detail(html: str, vod_id: str, base_url: str) -> Dict:
        """
        从视频播放页中提取详情信息。

        提取内容:
          - 标题: <meta property="og:title">
          - 缩略图: <video poster="...">
          - 播放源: <source src="...mp4"> 直链（360p/480p/720p，取最高清）
        """
        soup = BeautifulSoup(html, "html.parser")

        # 标题: og:title
        title = ""
        og = soup.find("meta", attrs={"property": "og:title"})
        if og and og.get("content"):
            title = og["content"].strip()
        if not title:
            title_tag = soup.find("title")
            if title_tag:
                title = title_tag.get_text(strip=True)
        title = BaseSpider.clean_title(title) if title else "未知标题"

        # 缩略图（从 video poster 属性）
        pic = ""
        video_tag = soup.find("video")
        if video_tag:
            poster = video_tag.get("poster", "")
            pic = BaseSpider.fix_url(poster, base_url) if poster else ""

        # 播放源提取（取最高清直链）
        best_url = Parser._extract_best_source(html)

        # 构建播放列表
        episodes = []
        if best_url:
            episodes.append(f"正片${best_url}")
        else:
            episodes.append(f"正片${BaseSpider.fix_url(vod_id, base_url)}")

        return {
            "vod_id": vod_id,
            "vod_name": title,
            "vod_pic": pic,
            "vod_play_from": "okxxx源",
            "vod_play_url": "#".join(episodes),
        }

    # ── 播放地址解析 ──

    @staticmethod
    def _extract_best_source(html: str) -> str:
        """
        从详情页 <source> 标签提取最高清直链 mp4。

        站点 HTML 结构:
            <source src="https://okxxx.art/get_file/13/{hash}/{id}/{id}_720p.mp4/"
                    type="video/mp4" title="720p" label="720p" class="video_720p">

        清晰度: 360p / 480p(无后缀) / 720p，取最高清（720p 优先）。
        过滤 preview 预览源（data-preview-custom 中的 _preview360p.mp4）。
        """
        sources = re.findall(
            r'<source\s+src="([^"]+)"[^>]*title="([^"]*)"',
            html,
            flags=re.IGNORECASE,
        )

        best = None
        best_rank = -1
        rank_map = {"360p": 1, "480p": 2, "720p": 3, "1080p": 4}

        for src, title in sources:
            src = src.strip()
            # 过滤 preview 预览源
            if "preview" in src.lower() or "preview" in title.lower():
                continue
            if not (".mp4" in src or ".m3u8" in src):
                continue
            # 按清晰度排名取最高
            rank = 0
            for key, r in rank_map.items():
                if key in title.lower() or key in src.lower():
                    rank = max(rank, r)
            if rank > best_rank:
                best_rank = rank
                best = src

        return best or ""

    # ── 播放地址解析（playerContent 兜底） ──

    @staticmethod
    def parse_player(html: str) -> str:
        """从播放页 HTML 提取最终 mp4 地址（playerContent 兜底用）"""
        return Parser._extract_best_source(html)


# ══════════════════════════════════════════════════════════════
# TVBox Spider 主体
# ══════════════════════════════════════════════════════════════
class Spider(BaseSpider):
    """
    okxxx 播放器规则 —— TVBox 标准入口。

    实现 TVBox 六大铁律接口:
      homeContent / categoryContent / detailContent / playerContent / searchContent
    """

    def __init__(self):
        super().__init__()
        self.parser = Parser()

    # ──────────────────────────────────────────────
    # homeContent: 返回分类列表
    # ──────────────────────────────────────────────
    def homeContent(self, filter: bool = False) -> Dict:
        """
        返回站点分类列表（50 个频道）。

        TVBox 格式: {"class": [{"type_name": str, "type_id": str}, ...]}
        """
        return {"class": HOME_CLASS}

    # ──────────────────────────────────────────────
    # categoryContent: 分类视频列表
    # ──────────────────────────────────────────────
    def categoryContent(self, tid: str, pg: str = "1",
                        filter: bool = False,
                        extend: Dict = None) -> Dict:
        """
        获取指定分类下的视频列表。

        参数:
          tid: 分类 ID（站点 slug，如 brazzers）
          pg:  页码（1 为首页，2+ 为 /sites/{slug}/{pg}/）

        返回: {"list": [...], "page": int, "pagecount": int, "limit": int, "total": int}
        """
        if pg == "1":
            url = f"{self.siteUrl}/sites/{tid}/"
        else:
            url = f"{self.siteUrl}/sites/{tid}/{pg}/"
        html = self.fetch(url, referer=self.siteUrl)

        if not html:
            return {"list": [], "page": int(pg), "pagecount": 0, "limit": 0, "total": 0}

        videos = self.parser.parse_video_list(html, self.siteUrl)

        return {
            "list": videos,
            "page": int(pg),
            "pagecount": 9999,
            "limit": len(videos),
            "total": 9999 * max(len(videos), 1),
        }

    # ──────────────────────────────────────────────
    # detailContent: 视频详情
    # ──────────────────────────────────────────────
    def detailContent(self, ids: List[str]) -> Dict:
        """
        获取视频详情（标题、缩略图、播放地址）。

        参数:
          ids: 视频 ID 列表（从列表页提取的 vod_id，即 /video/{id}/）

        返回: {"list": [{vod_id, vod_name, vod_pic, vod_play_from, vod_play_url}]}
        """
        if not ids:
            return {"list": []}

        vod_id = ids[0]
        detail_url = BaseSpider.fix_url(vod_id, self.siteUrl)

        # 获取播放页 HTML
        html = self.fetch(detail_url, referer=self.siteUrl)

        if not html:
            # 降级：返回最小可用信息
            return {"list": [{
                "vod_id": vod_id,
                "vod_name": "未知标题",
                "vod_pic": "",
                "vod_play_from": "okxxx源",
                "vod_play_url": f"正片${detail_url}",
            }]}

        detail = self.parser.parse_video_detail(html, vod_id, self.siteUrl)
        return {"list": [detail]}

    # ──────────────────────────────────────────────
    # playerContent: 播放地址解析
    # ──────────────────────────────────────────────
    def playerContent(self, flag: str, id: str, vipFlags: str = "") -> Dict:
        """
        解析最终播放地址。

        参数:
          flag:    播放源名称
          id:      播放地址（来自 detailContent 的 vod_play_url 中的链接部分）
          vipFlags: VIP 标记

        返回: {"parse": 0/1, "url": str, "header": str}

        说明:
          detailContent 已直接给出 mp4 直链，此处直接返回 parse:0。
          若 id 是视频页面 URL（兜底场景），则重新抓取页面提取源地址。
        """
        # 如果已经是直链 mp4/m3u8，直接返回
        if id and (".mp4" in id or ".m3u8" in id):
            return {"parse": 0, "url": id, "header": f"Referer={self.siteUrl}/"}

        # 如果是视频页面 URL，重新提取源地址
        if id and "/video/" in id:
            if not id.startswith("http"):
                id = BaseSpider.fix_url(id, self.siteUrl)
            html = self.fetch(id, referer=self.siteUrl)
            if html:
                real_url = self.parser.parse_player(html)
                if real_url:
                    return {
                        "parse": 0,
                        "url": real_url,
                        "header": f"Referer={self.siteUrl}/",
                    }

        # 兜底：交给播放器自行解析
        return {"parse": 1, "url": id, "header": ""}

    # ──────────────────────────────────────────────
    # searchContent: 视频搜索
    # ──────────────────────────────────────────────
    def searchContent(self, key: str, quick: str = None,
                      pg: str = "1") -> Dict:
        """
        搜索视频。

        参数:
          key:   搜索关键词
          quick: 快速搜索标记（TVBox 内部使用）
          pg:    页码（1 为首页，2+ 为 /search/{key}/{pg}/）

        返回: {"list": [{vod_id, vod_name, vod_pic}]}
        """
        encoded = parse.quote(key)
        if pg == "1":
            search_url = f"{self.siteUrl}/search/{encoded}/"
        else:
            search_url = f"{self.siteUrl}/search/{encoded}/{pg}/"
        html = self.fetch(search_url, referer=self.siteUrl)

        if not html:
            return {"list": []}

        videos = self.parser.parse_video_list(html, self.siteUrl)
        return {"list": videos}


# ══════════════════════════════════════════════════════════════
# TVBox 标准入口（兼容 drpy 框架）
# ══════════════════════════════════════════════════════════════
# 如果运行在 drpy 框架中，框架会自动调用 Spider 类
# 自包含模式则走下面的 CLI 入口

# ══════════════════════════════════════════════════════════════
# CLI 自检入口
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="okxxx 播放器规则 — 适配 okxxx.art"
    )
    parser.add_argument("--test-home", action="store_true", help="测试 homeContent")
    parser.add_argument("--test-category", action="store_true", help="测试 categoryContent (默认 brazzers)")
    parser.add_argument("--test-detail", action="store_true", help="测试 detailContent（自动获取第一条热门视频）")
    parser.add_argument("--test-search", action="store_true", help="测试 searchContent")
    parser.add_argument("--test-player", action="store_true", help="测试 playerContent")
    parser.add_argument("--tid", default="brazzers", help="分类 ID（默认 brazzers）")
    parser.add_argument("--pg", default="1", help="页码（默认 1）")
    parser.add_argument("--key", default="milf", help="搜索关键词（默认 milf）")
    args = parser.parse_args()

    spider = Spider()

    # 自检模式：无参数时运行
    if not any([args.test_home, args.test_category, args.test_detail,
                args.test_search, args.test_player]):
        print("=" * 60)
        print("  okxxx 播放器规则 — 自检")
        print("=" * 60)
        print(f"  站点: {spider.siteUrl}")
        print(f"  分类: {len(HOME_CLASS)} 个")
        for c in HOME_CLASS:
            print(f"    [{c['type_id']}] {c['type_name']}")
        print()
        print("  可用测试参数:")
        print("    --test-home      测试首页接口")
        print("    --test-category  测试分类列表")
        print("    --test-detail    测试视频详情")
        print("    --test-search    测试搜索功能")
        print("    --test-player    测试播放地址解析")
        print("=" * 60)

    # 测试各个接口
    if args.test_home:
        result = spider.homeContent()
        print(json.dumps(result, ensure_ascii=False, indent=2))

    if args.test_category:
        result = spider.categoryContent(tid=args.tid, pg=args.pg, filter=False, extend={})
        print(json.dumps(result, ensure_ascii=False, indent=2))

    if args.test_search:
        result = spider.searchContent(key=args.key, pg=args.pg)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    if args.test_detail:
        # 先获取分类列表的第一条视频
        cat_result = spider.categoryContent(tid="brazzers", pg="1", filter=False, extend={})
        if cat_result.get("list"):
            first_video = cat_result["list"][0]
            vod_id = first_video["vod_id"]
            print(f"测试详情: vod_id={vod_id}")
            result = spider.detailContent(ids=[vod_id])
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print("无法获取视频列表以测试详情接口")

    if args.test_player:
        # 先获取一个视频的详情，再测试播放
        cat_result = spider.categoryContent(tid="brazzers", pg="1", filter=False, extend={})
        if cat_result.get("list"):
            first_video = cat_result["list"][0]
            vod_id = first_video["vod_id"]
            detail = spider.detailContent(ids=[vod_id])
            if detail.get("list"):
                play_url = detail["list"][0].get("vod_play_url", "")
                if play_url and "$" in play_url:
                    # 支持多线路（# 分隔）和单线路
                    if "#" in play_url:
                        first_line = play_url.split("#")[0]
                    else:
                        first_line = play_url
                    if "$" in first_line:
                        _, play_id = first_line.split("$", 1)
                        print(f"测试播放: {play_id[:80]}...")
                        result = spider.playerContent(flag="", id=play_id)
                        print(json.dumps(result, ensure_ascii=False, indent=2))
                else:
                    print("未找到播放地址")
        else:
            print("无法获取视频列表以测试播放接口")
