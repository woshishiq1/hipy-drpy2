# -*- coding: utf-8 -*-
# 自制爬虫 - Pornlulu 视频站
# 目标：https://www.pornlulu.net/

import sys
import re
import json
import requests
from urllib.parse import urljoin, quote
from bs4 import BeautifulSoup
sys.path.append('..')
from base.spider import Spider


class Spider(Spider):
    def getName(self):
        return "Pornlulu"

    def init(self, extend=""):
        self.host = "https://www.pornlulu.net"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": self.host + "/",
        })
        # 分类（优先从首页提取，失败则使用硬编码）
        self.classes = []
        self._load_classes()

    def _load_classes(self):
        """从侧边栏提取分类"""
        try:
            html = self._fetch(self.host)
            if not html:
                raise Exception("首页加载失败")
            soup = BeautifulSoup(html, "html.parser")
            # 侧边栏分类 <ul id="w4">
            ul = soup.select_one("ul#w4")
            if ul:
                for li in ul.find_all("li", class_="nav-item"):
                    a = li.find("a", href=True)
                    if not a:
                        continue
                    href = a.get("href")
                    # 只取 /cat/数字 的链接
                    if href and href.startswith("/cat/"):
                        tid = href.split("/")[-1]
                        name = a.get_text(strip=True)
                        if tid and name:
                            self.classes.append({"type_id": tid, "type_name": name})
            # 如果没提取到，使用硬编码（部分主要分类）
            if not self.classes:
                self.classes = [
                    {"type_id": "263", "type_name": "国产自拍"},
                    {"type_id": "48", "type_name": "中文字幕"},
                    {"type_id": "13", "type_name": "强奸乱伦"},
                    {"type_id": "249", "type_name": "国产精品"},
                    {"type_id": "270", "type_name": "日本无码"},
                    {"type_id": "269", "type_name": "日本有码"},
                    {"type_id": "92", "type_name": "制服诱惑"},
                    {"type_id": "401", "type_name": "AV明星"},
                    {"type_id": "416", "type_name": "麻豆传媒"},
                ]
        except Exception as e:
            print(f"[分类] 加载失败: {e}，使用硬编码")
            self.classes = [
                {"type_id": "263", "type_name": "国产自拍"},
                {"type_id": "48", "type_name": "中文字幕"},
                {"type_id": "13", "type_name": "强奸乱伦"},
                {"type_id": "249", "type_name": "国产精品"},
                {"type_id": "270", "type_name": "日本无码"},
                {"type_id": "269", "type_name": "日本有码"},
                {"type_id": "92", "type_name": "制服诱惑"},
                {"type_id": "401", "type_name": "AV明星"},
                {"type_id": "416", "type_name": "麻豆传媒"},
            ]

    def _fetch(self, url, headers=None):
        """请求页面"""
        try:
            h = headers or self.session.headers
            resp = self.session.get(url, headers=h, timeout=15)
            resp.encoding = "utf-8"
            return resp.text
        except Exception as e:
            print(f"[请求] 失败: {e}")
            return ""

    def _fix_url(self, url):
        if not url:
            return ""
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return self.host + url
        return url

    def _parse_video_list(self, html):
        """解析视频列表"""
        videos = []
        if not html:
            return videos
        soup = BeautifulSoup(html, "html.parser")
        # 列表容器 #videos
        container = soup.select_one("#videos")
        if not container:
            return videos
        for item in container.select(".item"):
            try:
                card = item.select_one(".card")
                if not card:
                    continue
                # 链接和封面
                a = card.select_one("a.visited")
                if not a:
                    continue
                href = a.get("href")
                if not href or not href.startswith("/v/"):
                    continue
                # 标题
                title_tag = card.select_one(".card-body .two-lines a")
                title = title_tag.get_text(strip=True) if title_tag else ""
                # 封面图
                img = card.select_one("img.card-img-top")
                pic = img.get("src") if img else ""
                pic = self._fix_url(pic)
                # 备注（可能无）
                remark = ""
                # 提取视频ID（从链接中获取）
                vid = href  # 如 /v/8nDGJk
                videos.append({
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": remark,
                })
            except Exception as e:
                print(f"[解析] 卡片失败: {e}")
        return videos

    def _get_pagination(self, html):
        """提取总页数"""
        soup = BeautifulSoup(html, "html.parser")
        pagination = soup.select("ul.pagination li.page-item")
        max_page = 1
        for li in pagination:
            a = li.find("a", href=True)
            if a:
                href = a.get("href")
                m = re.search(r"[?&]page=(\d+)", href)
                if m:
                    page_num = int(m.group(1))
                    if page_num > max_page:
                        max_page = page_num
        return max_page

    def homeContent(self, filter=False):
        return {"class": self.classes}

    def homeVideoContent(self):
        """首页推荐（最新）"""
        return self.categoryContent("0", "1", False, {})

    def categoryContent(self, tid, pg, filter=False, extend=None):
        """分类列表"""
        pg = int(pg) if pg else 1
        # 构造 URL
        if tid == "0":  # 首页
            base_url = self.host + "/"
        else:
            base_url = self.host + "/cat/" + str(tid)
        if pg == 1:
            url = base_url
        else:
            # 分页参数 ?page=2
            if "?" in base_url:
                url = base_url + "&page=" + str(pg)
            else:
                url = base_url + "?page=" + str(pg)

        html = self._fetch(url)
        if not html:
            return {"list": [], "page": pg, "pagecount": 1, "limit": 0, "total": 0}
        videos = self._parse_video_list(html)
        pagecount = self._get_pagination(html) or (pg + 1 if len(videos) >= 20 else pg)
        return {
            "list": videos,
            "page": pg,
            "pagecount": pagecount,
            "limit": len(videos),
            "total": pagecount * 20,
        }

    def detailContent(self, ids):
        """详情页提取播放地址（自制提取逻辑）"""
        vid = ids[0] if isinstance(ids, list) else ids
        if not vid.startswith("/v/"):
            vid = "/v/" + vid
        url = self.host + vid
        html = self._fetch(url)
        if not html:
            return {"list": []}
        soup = BeautifulSoup(html, "html.parser")

        # 标题
        title = ""
        h1 = soup.find("h1")
        if h1:
            title = h1.get_text(strip=True)
        if not title:
            og_title = soup.find("meta", property="og:title")
            if og_title:
                title = og_title.get("content", "")
        if not title:
            title = vid

        # 封面（备用）
        pic = ""
        og_img = soup.find("meta", property="og:image")
        if og_img:
            pic = og_img.get("content", "")
        if not pic:
            img = soup.select_one("img.card-img-top")
            if img:
                pic = img.get("src") or ""

        # 提取播放地址（多策略兜底）
        play_url = ""

        # 1. 查找 <video> 标签
        video = soup.find("video")
        if video:
            src = video.get("src")
            if src:
                play_url = self._fix_url(src)
        if not play_url:
            source = soup.find("source")
            if source:
                src = source.get("src")
                if src:
                    play_url = self._fix_url(src)

        # 2. 查找 <iframe> 标签（可能嵌入播放器）
        if not play_url:
            iframe = soup.find("iframe")
            if iframe:
                src = iframe.get("src")
                if src:
                    play_url = self._fix_url(src)

        # 3. 查找 JS 变量中的 m3u8/mp4
        if not play_url:
            scripts = soup.find_all("script")
            for script in scripts:
                content = script.string or ""
                patterns = [
                    r'var\s+(?:video|file|playUrl|play_url|url)\s*=\s*["\']([^"\']+\.(?:m3u8|mp4))["\']',
                    r'"videoUrl"\s*:\s*["\']([^"\']+\.(?:m3u8|mp4))["\']',
                    r'"file"\s*:\s*["\']([^"\']+\.(?:m3u8|mp4))["\']',
                    r'(https?://[^\s"\']+\.(?:m3u8|mp4)[^\s"\']*)',
                ]
                for pattern in patterns:
                    m = re.search(pattern, content, re.S)
                    if m:
                        play_url = m.group(1)
                        if play_url:
                            break
                if play_url:
                    break

        # 如果仍然没有，返回详情页本身（WebView）
        if not play_url:
            play_url = url

        vod = {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic,
            "vod_play_from": "Pornlulu",
            "vod_play_url": f"播放${play_url}",
        }
        return {"list": [vod]}

    def playerContent(self, flag, id, vipFlags=None):
        """播放返回"""
        if id and (".m3u8" in id or ".mp4" in id):
            headers = {
                "User-Agent": self.session.headers["User-Agent"],
                "Referer": self.host + "/",
            }
            return {"parse": 0, "url": id, "header": json.dumps(headers)}
        else:
            return {"parse": 1, "url": id, "header": json.dumps({"Referer": self.host + "/"})}

    def searchContent(self, key, quick=False, pg="1"):
        """搜索"""
        pg = int(pg) if pg else 1
        enc_key = quote(key)
        url = self.host + "/?q=" + enc_key
        if pg > 1:
            url += "&page=" + str(pg)
        html = self._fetch(url)
        if not html:
            return {"list": [], "page": pg, "pagecount": 1, "limit": 0, "total": 0}
        videos = self._parse_video_list(html)
        pagecount = self._get_pagination(html) or (pg + 1 if len(videos) >= 20 else pg)
        return {
            "list": videos,
            "page": pg,
            "pagecount": pagecount,
            "limit": len(videos),
            "total": pagecount * 20,
        }

    def isVideoFormat(self, url):
        return url and (".m3u8" in url or ".mp4" in url)

    def manualVideoCheck(self):
        return False

    def destroy(self):
        if self.session:
            self.session.close()

    def localProxy(self, param):
        return None
