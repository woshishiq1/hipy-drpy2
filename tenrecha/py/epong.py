#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Eporner TVBox 源
===============
境界：四极秘境 · 四肢通天（hash 加密破解 + xhr API 调用）
作者：基于 yt-dlp EpornerIE 逆向工程
"""

import sys
import re
import json
import time
import requests
from urllib import parse

sys.path.append("..")
from base.spider import Spider


# ═══════════════════════════════════════════════════
# 四极秘境 · Eporner 破解功法
# ═══════════════════════════════════════════════════
class EpornerSpider(Spider):
    """
    【四极秘境 · Eporner 专修道场】

    网站特征：
        - 视频页 URL: https://www.eporner.com/video-{id}/{slug}/
        - 播放地址藏在 xhr API 后，需要 hash 计算解锁
        - 返回 sources 包含 mp4 直链和 hls(m3u8)

    破解流程：
        1. 请求视频页 HTML
        2. 提取 32 位十六进制 hash
        3. 每 8 位一组转 36 进制，拼接成新 hash
        4. 携带 hash 请求 /xhr/video/{id} 获取真实播放地址
    """

    siteUrl = "https://www.eporner.com"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    # 常用分类（硬编码 + 动态抓取）
    CATEGORIES = [
        {"type_id": "hd-porn", "type_name": "最新高清"},
        {"type_id": "most-popular", "type_name": "最热门"},
        {"type_id": "top-rated", "type_name": "最高评分"},
        {"type_id": "longest", "type_name": "最长视频"},
        {"type_id": "cat/teen", "type_name": "Teen"},
        {"type_id": "cat/milf", "type_name": "MILF"},
        {"type_id": "cat/anal", "type_name": "Anal"},
        {"type_id": "cat/lesbian", "type_name": "Lesbian"},
        {"type_id": "cat/interracial", "type_name": "Interracial"},
        {"type_id": "cat/asian", "type_name": "Asian"},
        {"type_id": "cat/ebony", "type_name": "Ebony"},
        {"type_id": "cat/blowjob", "type_name": "Blowjob"},
        {"type_id": "cat/creampie", "type_name": "Creampie"},
        {"type_id": "cat/threesome", "type_name": "Threesome"},
        {"type_id": "cat/big-tits", "type_name": "Big Tits"},
    ]

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    # ───────── 四极秘术 · hash 计算（逆向自 vjs.js）─────────
    @staticmethod
    def _encode_base_n(num, n, table=None):
        """将整数编码为 N 进制字符串"""
        FULL_TABLE = '0123456789abcdefghijklmnopqrstuvwxyz'
        if not table:
            table = FULL_TABLE[:n]
        if not num:
            return table[0]
        ret = ''
        while num:
            ret = table[num % n] + ret
            num = num // n
        return ret

    def _calc_hash(self, hash_hex):
        """
        四极秘术——hash 破解。
        从页面提取的 32 位十六进制 hash，每 8 位一组转为 36 进制。
        """
        return ''.join(
            self._encode_base_n(int(hash_hex[lb:lb + 8], 16), 36)
            for lb in range(0, 32, 8)
        )

    def _fetch(self, url, params=None):
        """通用 HTTP GET"""
        try:
            resp = self.session.get(url, params=params, timeout=15)
            resp.encoding = "utf-8"
            return resp.text
        except Exception as e:
            print(f"[Eporner] 请求失败: {url}, 错误: {e}")
            return ""

    def _fetch_json(self, url, params=None):
        """通用 HTTP GET 返回 JSON"""
        try:
            resp = self.session.get(url, params=params, timeout=15)
            resp.encoding = "utf-8"
            return resp.json()
        except Exception as e:
            print(f"[Eporner] JSON 请求失败: {url}, 错误: {e}")
            return {}

    # ───────── TVBox 标准接口 · 首页分类 ─────────
    def homeContent(self, filter):
        """返回首页分类"""
        return {"class": self.CATEGORIES}

    # ───────── TVBox 标准接口 · 分类列表 ─────────
    def categoryContent(self, tid, pg, filter, extend):
        """
        抓取分类/搜索列表。
        URL 格式:
            分类: https://www.eporner.com/cat/xxx/{page}/
            排序: https://www.eporner.com/most-popular/{page}/
            最新: https://www.eporner.com/hd-porn/{page}/
        """
        if tid.startswith("cat/"):
            url = f"{self.siteUrl}/{tid}/{pg}/"
        else:
            url = f"{self.siteUrl}/{tid}/{pg}/"

        html = self._fetch(url)
        videos = self._parse_list(html)
        return {
            "list": videos,
            "page": pg,
            "pagecount": 999,
            "limit": 60,
            "total": 99999
        }

    def _parse_list(self, html):
        """
        解析列表页 HTML 提取视频信息。
        Eporner 列表项大致结构:
            <div class="mb">
                <a href="/video-XXXXX/title/" title="...">
                    <img src="..." alt="...">
                </a>
                <span class="mbtim">12:34</span>
            </div>
        """
        videos = []
        if not html:
            return videos

        # 匹配视频卡片
        # 尝试多种可能的 HTML 结构
        patterns = [
            # 标准视频卡片
            r'<div[^>]*class=["\'][^"\']*mb[^"\']*["\'][^>]*>.*?<a[^>]*href=["\'](/video-[^"\']+)["\'][^>]*title=["\']([^"\']+)["\'].*?</div>',
            # 带缩略图
            r'<a[^>]*href=["\'](/video-[^"\']+)["\'][^>]*title=["\']([^"\']+)["\'][^>]*>.*?<img[^>]*src=["\']([^"\']+)["\'].*?</a>',
            # 更宽松
            r'href=["\'](/video-[a-zA-Z0-9]+/[^"\']*)["\'][^>]*title=["\']([^"\']+)["\']',
        ]

        seen = set()
        for pattern in patterns:
            matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
            for match in matches:
                if len(match) >= 2:
                    href = match[0]
                    title = match[1]
                    pic = match[2] if len(match) >= 3 else ""

                    # 提取 video_id
                    vid_match = re.search(r'/video-([a-zA-Z0-9]+)', href)
                    if not vid_match:
                        continue
                    vid = vid_match.group(1)

                    if vid in seen:
                        continue
                    seen.add(vid)

                    # 清理标题
                    title = re.sub(r'<[^>]+>', '', title).strip()

                    # 清理图片 URL
                    if pic:
                        pic = pic.replace(" ", "").replace("\n", "")
                        if pic.startswith("//"):
                            pic = "https:" + pic

                    videos.append({
                        "vod_id": vid,
                        "vod_name": title,
                        "vod_pic": pic,
                        "vod_remarks": "HD"
                    })

        # 如果正则没抓到，用 BeautifulSoup 兜底
        if not videos:
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html, "html.parser")
                for item in soup.select(".mb, .vid, [data-id]"):
                    a = item.find("a", href=re.compile(r'/video-[a-zA-Z0-9]+'))
                    if not a:
                        continue
                    href = a.get("href", "")
                    title = a.get("title", "") or a.get_text(strip=True)
                    img = a.find("img")
                    pic = img.get("src") or img.get("data-src", "") if img else ""

                    vid_match = re.search(r'/video-([a-zA-Z0-9]+)', href)
                    if not vid_match:
                        continue
                    vid = vid_match.group(1)

                    if vid in seen:
                        continue
                    seen.add(vid)

                    videos.append({
                        "vod_id": vid,
                        "vod_name": title,
                        "vod_pic": pic,
                        "vod_remarks": "HD"
                    })
            except ImportError:
                pass

        return videos

    # ───────── TVBox 标准接口 · 详情页 ─────────
    def detailContent(self, ids):
        """
        获取视频详情和播放地址。
        核心：破解 hash -> 调用 xhr API -> 提取 mp4/m3u8
        """
        video_id = ids[0]
        # 构造详情页 URL（slug 不重要，会被重定向）
        detail_url = f"{self.siteUrl}/video-{video_id}/"
        html = self._fetch(detail_url)

        if not html:
            return {"list": []}

        # 1. 提取页面 hash（32位十六进制）
        hash_match = re.search(r'hash\s*[:=]\s*["\']([\da-f]{32})', html)
        if not hash_match:
            print(f"[Eporner] 未能提取 hash，尝试备用方案")
            return self._fallback_detail(video_id, html)

        hash_hex = hash_match.group(1)

        # 2. 计算 hash
        computed_hash = self._calc_hash(hash_hex)

        # 3. 请求 xhr API
        api_url = f"{self.siteUrl}/xhr/video/{video_id}"
        params = {
            "hash": computed_hash,
            "device": "generic",
            "domain": "www.eporner.com",
            "fallback": "false"
        }

        data = self._fetch_json(api_url, params)

        if not data or data.get("available") is False:
            msg = data.get("message", "unknown error") if data else "no data"
            print(f"[Eporner] API 返回不可用: {msg}")
            return self._fallback_detail(video_id, html)

        # 4. 解析视频源
        sources = data.get("sources", {})
        play_url = ""
        play_from = "mp4"

        # 优先取 mp4 直链（按清晰度排序）
        mp4_sources = sources.get("mp4", {})
        if mp4_sources:
            # 按清晰度从高到低排序
            best_url = ""
            best_height = 0
            for fmt_id, fmt_info in mp4_sources.items():
                if not isinstance(fmt_info, dict):
                    continue
                src = fmt_info.get("src", "")
                if not src or not src.startswith("http"):
                    continue
                # 提取清晰度 720p, 1080p 等
                height_match = re.search(r'(\d+)[pP]', fmt_id)
                height = int(height_match.group(1)) if height_match else 0
                if height > best_height:
                    best_height = height
                    best_url = src
            if best_url:
                play_url = best_url
                play_from = f"mp4-{best_height}p" if best_height else "mp4"

        # 如果没有 mp4，尝试 hls
        if not play_url:
            hls_sources = sources.get("hls", {})
            if hls_sources:
                for fmt_id, fmt_info in hls_sources.items():
                    if not isinstance(fmt_info, dict):
                        continue
                    src = fmt_info.get("src", "")
                    if src and src.startswith("http"):
                        play_url = src
                        play_from = "hls"
                        break

        # 5. 提取标题和封面
        title = self._extract_title(html)
        thumb = self._extract_thumb(html)

        if not play_url:
            return self._fallback_detail(video_id, html)

        return {
            "list": [{
                "vod_id": video_id,
                "vod_name": title,
                "vod_pic": thumb,
                "vod_play_from": play_from,
                "vod_play_url": f"第1集${play_url}"
            }]
        }

    def _fallback_detail(self, video_id, html):
        """备用方案：尝试从页面直接提取 embed 或 og:video"""
        # 尝试 og:video
        og_video = re.search(r'<meta[^>]+property=["\']og:video["\'][^>]+content=["\']([^"\']+)["\']', html)
        if og_video:
            url = og_video.group(1)
            title = self._extract_title(html)
            thumb = self._extract_thumb(html)
            return {
                "list": [{
                    "vod_id": video_id,
                    "vod_name": title,
                    "vod_pic": thumb,
                    "vod_play_from": "fallback",
                    "vod_play_url": f"第1集${url}"
                }]
            }
        return {"list": []}

    def _extract_title(self, html):
        """提取视频标题"""
        # 先尝试 og:title
        og = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']', html)
        if og:
            return og.group(1).replace(" - EPORNER", "").strip()
        # 备用
        m = re.search(r'<title>(.+?)\s*-\s*EPORNER', html, re.IGNORECASE)
        if m:
            return m.group(1).strip()
        return "Unknown"

    def _extract_thumb(self, html):
        """提取缩略图"""
        og = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html)
        if og:
            return og.group(1)
        return ""

    # ───────── TVBox 标准接口 · 播放 ─────────
    def playerContent(self, flag, id, vipFlags):
        """
        Eporner 的 mp4 是直链，直接返回。
        如果是 m3u8，TVBox 会自动处理。
        """
        # 需要 Referer 伪装（某些 CDN 会检查）
        header = "Referer=https://www.eporner.com/&User-Agent=Mozilla/5.0"
        return {
            "parse": 0,
            "url": id,
            "header": header
        }

    # ───────── TVBox 标准接口 · 搜索 ─────────
    def searchContent(self, key, quick, pg="1"):
        """
        搜索 URL: https://www.eporner.com/search/{keyword}/{page}/
        """
        keyword = parse.quote(key)
        url = f"{self.siteUrl}/search/{keyword}/{pg}/"
        html = self._fetch(url)
        videos = self._parse_list(html)
        return {
            "list": videos,
            "page": pg,
            "pagecount": 999
        }

    def searchContentPage(self, key, quick, pg):
        return self.searchContent(key, quick, pg)

    # ───────── TVBox 标准接口 · 本地代理（可选）─────────
    def localProxy(self, param):
        return [404, "text/plain", "Not Found"]

    def isVideoFormat(self, url):
        return any(ext in url.lower() for ext in [".m3u8", ".mp4", ".ts", ".flv", ".mkv"])

    def manualVideoCheck(self):
        return False

    def init(self, extend=""):
        return True


# ═══════════════════════════════════════════════════
# TVBox 入口
# ═══════════════════════════════════════════════════
class Spider(EpornerSpider):
    pass