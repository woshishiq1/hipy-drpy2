# -*- coding: utf-8 -*-
# TVBox爬虫 - ASMR大全
# 目标：http://asmrdq.com

import sys
import re
import json
import urllib.parse
from base.spider import Spider
from bs4 import BeautifulSoup
import requests

class Spider(Spider):
    def getName(self):
        return "ASMR大全"

    def init(self, extend=""):
        self.host = "https://asmrdq.com"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept-Encoding": "gzip, deflate",
        })
        # 只保留视频分类，去掉作者分类
        self.class_map = {
            "cn": "国内ASMR视频",
            "gw": "国外ASMR视频",
        }

    def _fix_url(self, url):
        if not url:
            return ""
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return self.host + url
        return url

    def _fetch(self, url, timeout=15):
        try:
            resp = self.session.get(url, timeout=timeout)
            resp.encoding = "utf-8"
            return resp.text
        except Exception as e:
            print(f"[Fetch Error] {url} -> {e}")
            return ""

    def homeContent(self, filter=False):
        classes = [{"type_id": tid, "type_name": name} for tid, name in self.class_map.items()]
        return {"class": classes}

    def homeVideoContent(self):
        return self.categoryContent("cn", "1", None, {})

    def categoryContent(self, tid, pg, filter=False, extend=None):
        pg = int(pg) if pg else 1
        if tid == "cn":
            base_url = f"{self.host}/play/cn"
        elif tid == "gw":
            base_url = f"{self.host}/play/gw"
        else:
            return {"list": [], "page": pg, "pagecount": 1, "limit": 20, "total": 0}

        if pg <= 1:
            url = base_url
        else:
            url = base_url + f"/page/{pg}"

        html = self._fetch(url)
        if not html:
            return {"list": [], "page": pg, "pagecount": 1, "limit": 20, "total": 0}

        soup = BeautifulSoup(html, "html.parser")
        videos = []
        seen = set()

        for item in soup.find_all("div", class_="list-item"):
            a_tag = item.find("a", class_="list-goto")
            if not a_tag:
                continue
            href = a_tag.get("href", "")
            id_match = re.search(r"/(\d+)\.html", href)
            vod_id = id_match.group(1) if id_match else ""
            if not vod_id or vod_id in seen:
                continue
            seen.add(vod_id)

            title_tag = item.find("div", class_="list-title")
            title = title_tag.get_text(strip=True) if title_tag else ""

            media = item.find("div", class_="media-content")
            pic = ""
            if media:
                pic = media.get("data-wpfc-original-src", "")
                if not pic:
                    style = media.get("style", "")
                    bg_match = re.search(r'url\(["\']?([^"\']+)["\']?\)', style)
                    if bg_match:
                        pic = bg_match.group(1)
            pic = self._fix_url(pic)

            videos.append({
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": ""
            })

        pagecount = 1
        next_link = soup.find("a", class_="next")
        if next_link:
            pagecount = pg + 1
        elif len(videos) >= 20:
            pagecount = pg + 1

        return {
            "list": videos,
            "page": pg,
            "pagecount": max(pagecount, pg),
            "limit": 20,
            "total": max(pagecount, pg) * 20
        }

    def detailContent(self, ids):
        vod_id = ids[0]
        url = f"{self.host}/{vod_id}.html"
        html = self._fetch(url)

        if not html:
            return {"list": []}

        soup = BeautifulSoup(html, "html.parser")

        title = ""
        title_tag = soup.find("h1", class_="post-title") or soup.find("h1")
        if title_tag:
            title = title_tag.get_text(strip=True)
        if not title:
            title_match = re.search(r"<title>(.*?)</title>", html)
            if title_match:
                title = title_match.group(1).strip()

        pic = ""
        img_tag = soup.find("img", class_="wp-post-image") or soup.find("img", class_="attachment-post-thumbnail")
        if img_tag:
            pic = img_tag.get("src", "")
        if not pic:
            content = soup.find("div", class_="post-content")
            if content:
                img = content.find("img")
                if img:
                    pic = img.get("src", "")
        pic = self._fix_url(pic)

        desc = ""
        excerpt = soup.find("div", class_="post-excerpt")
        if excerpt:
            desc = excerpt.get_text(strip=True)[:200]

        play_url = url

        return {
            "list": [{
                "vod_id": vod_id,
                "vod_name": title or "未命名",
                "vod_pic": pic,
                "vod_content": desc,
                "vod_play_from": "ASMR大全",
                "vod_play_url": f"全集${play_url}"
            }]
        }

    def playerContent(self, flag, id, vipFlags=None):
        try:
            html = self._fetch(id)
            if not html:
                return {"parse": 0, "url": "", "msg": "页面加载失败"}

            iframe = re.search(r'<iframe[^>]+(?:data-wpfc-original-src|src)=["\']([^"\']+)["\']', html)
            if iframe:
                url = iframe.group(1)
                if url.startswith("//"):
                    url = "https:" + url
                return {
                    "parse": 1,
                    "url": url,
                    "header": json.dumps({"Referer": self.host, "User-Agent": "Mozilla/5.0"})
                }

            video = re.search(r'<video[^>]+src="([^"]+)"', html)
            if video:
                return {"parse": 0, "url": self._fix_url(video.group(1)), "header": json.dumps({"Referer": self.host})}

            media = re.search(r'(https?://[^\s"\']+\.(?:m3u8|mp4|flv))', html)
            if media:
                return {"parse": 0, "url": media.group(1), "header": json.dumps({"Referer": self.host})}

            return {"parse": 0, "url": "", "msg": "未找到视频源"}
        except Exception as e:
            print(f"playerContent error: {e}")
            return {"parse": 0, "url": "", "msg": str(e)}

    def searchContent(self, key, quick=False, pg="1"):
        pg = int(pg) if pg else 1
        enc_key = urllib.parse.quote(key)
        url = f"{self.host}/?s={enc_key}"
        if pg > 1:
            url += f"&paged={pg}"

        html = self._fetch(url)
        if not html:
            return {"list": [], "page": pg, "pagecount": 1, "limit": 20, "total": 0}

        soup = BeautifulSoup(html, "html.parser")
        videos = []
        seen = set()

        for item in soup.find_all("div", class_="list-item"):
            a_tag = item.find("a", class_="list-goto")
            if not a_tag:
                continue
            href = a_tag.get("href", "")
            id_match = re.search(r"/(\d+)\.html", href)
            vod_id = id_match.group(1) if id_match else ""
            if not vod_id or vod_id in seen:
                continue
            seen.add(vod_id)

            title_tag = item.find("div", class_="list-title")
            title = title_tag.get_text(strip=True) if title_tag else ""

            media = item.find("div", class_="media-content")
            pic = ""
            if media:
                pic = media.get("data-wpfc-original-src", "")
            pic = self._fix_url(pic)

            videos.append({
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": "搜索"
            })

        pagecount = 3 if len(videos) >= 20 else 1
        return {"list": videos, "page": pg, "pagecount": pagecount, "limit": 20, "total": pagecount * 20}

    def isVideoFormat(self, url):
        return any(ext in url for ext in [".m3u8", ".mp4", ".flv", ".ts"])

    def manualVideoCheck(self):
        return False

    def destroy(self):
        if self.session:
            self.session.close()

    def localProxy(self, param):
        return None