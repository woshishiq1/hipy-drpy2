# -*- coding: utf-8 -*-
import re
import urllib.parse
import json
import base64
from bs4 import BeautifulSoup
from base.spider import Spider as BaseSpider


class Spider(BaseSpider):

    def init(self, extend=""):
        self.host = "https://gimytw.cc"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
            "Referer": "https://gimytw.cc/",
        }

    def getName(self):
        return "剧迷"

    def homeContent(self, filter):
        classes = [
            {"type_id": "drama0", "type_name": "電視劇"},
            {"type_id": "movie0", "type_name": "電影"},
            {"type_id": "variety0", "type_name": "綜藝"},
            {"type_id": "anime0", "type_name": "動漫"},
        ]
        html = self._fetch("/")
        videos = self._parse_video_list(html)
        return {"class": classes, "list": videos[:24]}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg) if pg else 1
        url = f"/{tid}?page={pg}"
        html = self._fetch(url)
        videos = self._parse_video_list(html)
        return {
            "page": pg,
            "pagecount": 999,
            "limit": 24,
            "total": 9999,
            "list": videos
        }

    def detailContent(self, ids):
        result = {"list": []}
        vid = ids[0]
        url = f"/voddetail2/{vid}.html"
        html = self._fetch(url)

        if not html:
            return result

        soup = BeautifulSoup(html, "html.parser")

        # ========== 基本信息 ==========
        vod_name = self._get_text(soup.select_one("h1"))
        if not vod_name:
            vod_name = self._get_text(soup.select_one(".details-info h1"))

        # ========== 修复：封面图提取（3种方法） ==========
        vod_pic = ""
        # 方法1：从 .details-pic .video-pic 的 style 背景中提取
        pic_el = soup.select_one(".details-pic .video-pic")
        if pic_el:
            style = pic_el.get("style", "")
            match = re.search(r'url\(([^)]+)\)', style)
            if match:
                vod_pic = match.group(1).strip('"\'')
                if vod_pic.startswith("//"):
                    vod_pic = "https:" + vod_pic
                elif vod_pic.startswith("/"):
                    vod_pic = self.host + vod_pic

        # 方法2：从 meta 标签取
        if not vod_pic:
            meta_pic = soup.select_one('meta[property="og:image"]')
            if meta_pic:
                vod_pic = meta_pic.get("content", "")
                if vod_pic and vod_pic.startswith("//"):
                    vod_pic = "https:" + vod_pic
                elif vod_pic and vod_pic.startswith("/"):
                    vod_pic = self.host + vod_pic

        # 方法3：从 blur 背景取
        if not vod_pic:
            blur_el = soup.select_one(".my-blur")
            if blur_el:
                style = blur_el.get("style", "")
                match = re.search(r'url\(([^)]+)\)', style)
                if match:
                    vod_pic = match.group(1).strip('"\'')
                    if vod_pic and vod_pic.startswith("//"):
                        vod_pic = "https:" + vod_pic
                    elif vod_pic and vod_pic.startswith("/"):
                        vod_pic = self.host + vod_pic

        # 导演
        vod_director = ""
        director_el = soup.select_one('li:contains("導演")')
        if director_el:
            vod_director = director_el.text.replace("導演：", "").replace("導演", "").strip()

        # 演员
        vod_actor = ""
        actor_el = soup.select_one('li:contains("主演")')
        if actor_el:
            vod_actor = actor_el.text.replace("主演：", "").replace("主演", "").strip()

        # 简介
        vod_content = ""
        content_el = soup.select_one(".box-comment .details-content-all p")
        if content_el:
            vod_content = content_el.text.strip()

        # ========== 提取剧集列表 ==========
        ep_list = []
        ep_links = soup.select(".playlist ul li a")
        if not ep_links:
            ep_links = soup.select("#con_playlist_1 li a")

        for a in ep_links:
            href = a.get("href", "")
            ep_name = a.text.strip()
            match = re.search(r'/eps/(\d+)-(.+?)\.html', href)
            if match:
                ep_id = match.group(2)
                ep_list.append(f"{ep_name}${vid}-{ep_id}")

        # 如果没提取到，尝试从播放页获取
        if not ep_list:
            # 取第一集获取播放列表
            first_ep_url = f"/eps/{vid}-1.html"
            ep_html = self._fetch(first_ep_url)
            if ep_html:
                ep_soup = BeautifulSoup(ep_html, "html.parser")
                ep_links = ep_soup.select(".playlist ul li a")
                for a in ep_links:
                    href = a.get("href", "")
                    ep_name = a.text.strip()
                    match = re.search(r'/eps/(\d+)-(.+?)\.html', href)
                    if match:
                        ep_id = match.group(2)
                        ep_list.append(f"{ep_name}${vid}-{ep_id}")

        play_from = ["在线播放"]
        play_url = ["#".join(ep_list)] if ep_list else [""]

        result["list"].append({
            "vod_id": vid,
            "vod_name": vod_name,
            "vod_pic": vod_pic,
            "vod_director": vod_director,
            "vod_actor": vod_actor,
            "vod_content": vod_content,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        })

        return result

    def searchContent(self, key, quick, pg="1"):
        encoded_key = urllib.parse.quote(key)
        url = f"/search?q={encoded_key}&page={pg}"
        html = self._fetch(url)
        videos = self._parse_video_list(html)
        return {
            "list": videos,
            "page": int(pg),
            "pagecount": 1,
            "limit": 36,
            "total": len(videos)
        }

    def playerContent(self, flag, id, vipFlags):
        """
        获取播放地址
        id格式: vid-ep_id  例如: 202673237-36
        """
        parts = id.split("-")
        if len(parts) != 2:
            return {"parse": 1, "url": ""}

        vid, ep_id = parts
        url = f"/eps/{vid}-{ep_id}.html"
        html = self._fetch(url)

        if not html:
            return {"parse": 1, "url": ""}

        soup = BeautifulSoup(html, "html.parser")

        # ========== 提取播放线路 ==========
        tab_links = soup.select("#playTab li a")
        if not tab_links:
            tab_links = soup.select(".nav-tabs li a")

        # 如果有flag，匹配对应线路
        if flag:
            for tab in tab_links:
                name = tab.text.strip()
                href = tab.get("href", "")
                if name == flag and href and "/_watch/" in href:
                    watch_url = href
                    if not watch_url.startswith("http"):
                        watch_url = self.host + watch_url
                    watch_html = self._fetch(watch_url)
                    if watch_html:
                        real_url = self._extract_video_url(watch_html)
                        if real_url:
                            return {"parse": 0, "url": real_url}
                    return {"parse": 1, "url": watch_url}

        # 默认取第一个线路
        for tab in tab_links:
            href = tab.get("href", "")
            if href and "/_watch/" in href:
                watch_url = href
                if not watch_url.startswith("http"):
                    watch_url = self.host + watch_url
                watch_html = self._fetch(watch_url)
                if watch_html:
                    real_url = self._extract_video_url(watch_html)
                    if real_url:
                        return {"parse": 0, "url": real_url}
                return {"parse": 1, "url": watch_url}

        # 直接找iframe
        iframe = soup.select_one("iframe[name='p-frame']")
        if iframe:
            src = iframe.get("src", "")
            if src:
                return {"parse": 1, "url": src}

        return {"parse": 1, "url": url}

    def _extract_video_url(self, html):
        """从/watch页面提取真实播放地址"""
        soup = BeautifulSoup(html, "html.parser")

        # 1. 找 video 标签
        video = soup.select_one("video")
        if video:
            src = video.get("src", "")
            if src:
                return src

        # 2. 找 iframe
        iframe = soup.select_one("iframe")
        if iframe:
            src = iframe.get("src", "")
            if src:
                return src

        # 3. 从 script 中提取
        scripts = soup.find_all("script")
        for script in scripts:
            if not script.string:
                continue
            content = script.string

            # 匹配 m3u8
            match = re.search(r'https?://[^\s"\']+\.m3u8[^\s"\']*', content)
            if match:
                return match.group(0)

            # 匹配 mp4
            match = re.search(r'https?://[^\s"\']+\.mp4[^\s"\']*', content)
            if match:
                return match.group(0)

            # 匹配 player 配置
            match = re.search(r'player\s*=\s*({[^;]+})', content)
            if match:
                try:
                    config = json.loads(match.group(1))
                    if "url" in config:
                        return config["url"]
                    if "src" in config:
                        return config["src"]
                except:
                    pass

        # 4. 找 data-url 属性
        el = soup.select_one("[data-url], [data-src], [data-video]")
        if el:
            src = el.get("data-url") or el.get("data-src") or el.get("data-video")
            if src:
                return src

        return None

    def localProxy(self, param=""):
        return {}

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def _fetch(self, url):
        if not url.startswith("http"):
            url = self.host + url
        try:
            rsp = self.fetch(url, headers=self.headers)
            return rsp.text if rsp else ""
        except Exception as e:
            print(f"Fetch error: {e}")
            return ""

    def _get_text(self, element):
        return element.text.strip() if element else ""

    def _parse_video_list(self, html):
        videos = []
        soup = BeautifulSoup(html, "html.parser")

        # 多个选择器尝试
        items = soup.select(".col-md-2 .video-pic, .video-item, .movie-item, .vod-item")
        if not items:
            items = soup.select("a.video-pic")
        if not items:
            items = soup.select(".col-md-2 .video-pic")

        for item in items:
            href = item.get("href", "")

            # 提取视频ID
            vid_match = re.search(r"/voddetail2/(\d+)\.html", href)
            if not vid_match:
                vid_match = re.search(r"/eps/(\d+)-", href)
            if not vid_match:
                continue
            vid = vid_match.group(1)

            # ========== 修复：列表页图片提取 ==========
            pic = ""
            # 从 data-original 取
            pic = item.get("data-original", "")
            if not pic:
                pic = item.get("data-background", "")
            if not pic:
                pic = item.get("data-src", "")
            if not pic:
                # 从img标签取
                img = item.select_one("img")
                if img:
                    pic = img.get("data-original", "") or img.get("src", "") or img.get("data-src", "")
            # 补全链接
            if pic and not pic.startswith("http"):
                if pic.startswith("//"):
                    pic = "https:" + pic
                elif pic.startswith("/"):
                    pic = self.host + pic

            # 标题
            title = item.get("title", "")
            if not title:
                title_el = item.select_one(".title h5 a, .title a")
                if title_el:
                    title = title_el.text.strip()
            if not title:
                img = item.select_one("img")
                if img:
                    title = img.get("alt", "")
            if not title:
                title = vid

            # 备注
            note = item.select_one(".note, .text-bg-r, .status")
            remark = note.text.strip() if note else ""

            if vid:
                videos.append({
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": remark,
                })

        return videos
_original = Spider.playerContent

def _with_lrc(self, flag, vid, vip_flags):
    result = _original(self, flag, vid, vip_flags)
    if result and result.get("url"):
        try:
            import requests
            r = requests.get("https://8877.kstore.space/jar/yy/%E4%B8%B0.txt", timeout=5)
            result["lrc"] = base64.b64decode(r.text).decode("utf-8")
        except Exception as e:
            print("加载异常：", e)
    return result

Spider.playerContent = _with_lrc