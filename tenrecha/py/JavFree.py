#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
遮天九秘 · javfree.com 爬虫脚本 v7
境界：轮海秘境 · 彼岸境（轻量直取）
分类: Featured / Most Watched / Censored / Uncensored / Jav Stars
"""

import sys
import re
import json
import requests
from urllib import parse

sys.path.append("..")
from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.siteUrl = "https://javfree.com"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://javfree.com/",
        })
        # 临字秘：主分类硬编码（Featured / Most Watched / Censored / Uncensored / Jav Stars）
        self.main_categories = [
            {"type_id": "featured", "type_name": "Featured"},
            {"type_id": "most-watched", "type_name": "Most Watched"},
            {"type_id": "censored", "type_name": "Censored"},
            {"type_id": "uncensored", "type_name": "Uncensored"},
            {"type_id": "star", "type_name": "Jav Stars"},
        ]
        self.p_item = re.compile(
            r'<div class="post movie-item">\s*'
            r'<a[^>]*?title="([^"]+)"[^>]*?href="([^"]+)"[^>]*?>\s*'
            r'.*?<img[^>]*?data-src="([^"]+)"[^>]*?>.*?'
            r'<i class="type">([^<]+)</i>.*?'
            r'<span class="date">([^<]+)</span>',
            re.DOTALL
        )
        self.p_star = re.compile(
            r'<div class="star-b">\s*'
            r'<div class="thumb">\s*'
            r'<a href="https?://javfree\.com/star/([^/]+)/"[^>]*title="([^"]+)"[^>]*>\s*'
            r'<img src="([^"]+)"',
            re.DOTALL
        )

    def init(self, extend=""):
        try:
            self.session.headers.update({"Referer": "https://javfree.com/"})
            return True
        except Exception as e:
            print(f"[init] 失败: {e}")
            return False

    def fetch(self, url, timeout=15):
        try:
            resp = self.session.get(url, timeout=timeout)
            resp.encoding = "utf-8"
            return resp.text
        except Exception as e:
            print(f"[fetch] 失败: {url} | {e}")
            return ""

    def post(self, url, data=None, timeout=15):
        try:
            resp = self.session.post(url, data=data, timeout=timeout)
            resp.encoding = "utf-8"
            return resp.text
        except Exception as e:
            print(f"[post] 失败: {url} | {e}")
            return ""

    # ═════════ 首页 ═════════
    def homeContent(self, filter):
        html = self.fetch(self.siteUrl + "/home/")
        classes = list(self.main_categories)
        videos = self._extract_videos(html)
        return {"class": classes, "list": videos[:12]}

    # ═════════ 分类列表 ═════════
    def categoryContent(self, tid, pg, filter, extend):
        if tid == "star":
            url = f"{self.siteUrl}/star/?p={pg}"
            html = self.fetch(url)
            videos = self._extract_stars(html)
        elif tid.startswith("star_"):
            slug = tid.replace("star_", "")
            url = f"{self.siteUrl}/star/{slug}/?p={pg}"
            html = self.fetch(url)
            videos = self._extract_videos(html)
        else:
            # featured / most-watched / censored / uncensored
            url = f"{self.siteUrl}/{tid}/?p={pg}"
            html = self.fetch(url)
            videos = self._extract_videos(html)

        pagecount = 999
        has_next = re.search(r'data-page="%d"' % (int(pg) + 1), html)
        if not has_next and len(videos) < 20:
            pagecount = int(pg)

        return {
            "list": videos,
            "page": int(pg),
            "pagecount": pagecount,
            "limit": 40,
            "total": pagecount * 40
        }

    def _extract_videos(self, html):
        videos = []
        matches = self.p_item.findall(html)
        for title, href, pic, vtype, duration in matches:
            vid_match = re.search(r'/video-([^/]+)/', href)
            vod_id = vid_match.group(1) if vid_match else href
            videos.append({
                "vod_id": vod_id,
                "vod_name": self._clean_title(title),
                "vod_pic": pic,
                "vod_remarks": f"{vtype.strip()} | {duration.strip()}",
            })
        return videos

    def _extract_stars(self, html):
        videos = []
        matches = self.p_star.findall(html)
        for slug, name, pic in matches:
            videos.append({
                "vod_id": f"star_{slug}",
                "vod_name": self._clean_title(name),
                "vod_pic": pic,
                "vod_remarks": "Jav Star",
            })
        return videos

    # ═════════ 详情 ═════════
    def detailContent(self, ids):
        vod_id = ids[0]

        if vod_id.startswith("star_"):
            slug = vod_id.replace("star_", "")
            url = f"{self.siteUrl}/star/{slug}/"
            html = self.fetch(url)
            if not html:
                return {"list": []}

            name_match = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.DOTALL)
            star_name = self._clean_title(re.sub(r'<[^>]+>', '', name_match.group(1))) if name_match else slug.replace('-', ' ').title()

            videos = self._extract_videos(html)
            if not videos:
                return {"list": []}

            play_urls = []
            for i, v in enumerate(videos, 1):
                play_urls.append(f"第{i}集${self.siteUrl}/video-{v['vod_id']}/")

            return {
                "list": [{
                    "vod_id": vod_id,
                    "vod_name": star_name,
                    "vod_pic": videos[0]["vod_pic"] if videos else "",
                    "vod_actor": star_name,
                    "vod_content": f"{star_name} 的作品列表，共 {len(videos)} 部",
                    "vod_play_from": "作品列表",
                    "vod_play_url": "#".join(play_urls)
                }]
            }

        if vod_id.startswith("http"):
            url = vod_id
        else:
            url = f"{self.siteUrl}/video-{vod_id}/"

        html = self.fetch(url)
        if not html:
            return {"list": []}

        title_match = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.DOTALL)
        title = self._clean_title(re.sub(r'<[^>]+>', '', title_match.group(1))) if title_match else vod_id

        pic = ""
        cover_match = re.search(r'img\.javfree\.com/thumb/(?:600x0|640x0)/([^"\'\s]+)', html)
        if cover_match:
            size = "600x0" if "600x0" in html[cover_match.start()-10:cover_match.start()] else "640x0"
            pic = f"https://img.javfree.com/thumb/{size}/{cover_match.group(1)}"
        else:
            cover_match2 = re.search(r'img\.javfree\.com/thumb/[^"\'/]+/([^"\'\s]+)', html)
            if cover_match2:
                pic = f"https://img.javfree.com/thumb/600x0/{cover_match2.group(1)}"

        desc_match = re.search(r'<div[^>]*class="[^"]*description[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
        desc = re.sub(r'<[^>]+>', '', desc_match.group(1)).strip() if desc_match else ""

        stars = re.findall(r'href="https?://javfree\.com/star/([^/]+)/"[^>]*>([^<]+)</a>', html)
        actors = [name for _, name in stars]

        tags = re.findall(r'href="https?://javfree\.com/genre/([^/]+)/"[^>]*>([^<]+)</a>', html)
        genres = [name for _, name in tags]

        # 提取 movie 对象，为每个服务器生成一条线路
        movie_match = re.search(r'movie\s*=\s*({[\s\S]+?});', html)
        play_froms = []
        play_urls = []

        if movie_match:
            movie_str = movie_match.group(1)
            sv_matches = re.findall(r'"(\d+)"\s*:\s*\["([^"]+)","([^"]+)"\]', movie_str)
            epi_matches = re.findall(r'"(\d+)"\s*:\s*\["([^"]+)"\]', movie_str)

            sv_map = {sid: name for sid, idx, name in sv_matches}
            epi_map = {sid: b64 for sid, b64 in epi_matches}

            for sid, server_name in sv_map.items():
                if sid in epi_map and server_name != "DOWNLOAD":
                    play_froms.append(server_name)
                    play_urls.append(f"第1集${url}")

        if not play_froms:
            external = re.findall(r'(https?://k2s\.cc/file/[^\s"\'<>]+)', html)
            external += re.findall(r'(https?://rapidgator\.net/file/[^\s"\'<>]+)', html, re.IGNORECASE)
            if external:
                play_froms = ["网盘外链"]
                play_urls = [f"第1集${external[0]}"]
            else:
                play_froms = ["详情页"]
                play_urls = [f"第1集${url}"]

        return {
            "list": [{
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": pic,
                "vod_actor": ",".join(actors),
                "vod_tag": ",".join(genres),
                "vod_content": desc,
                "vod_play_from": "$$$".join(play_froms),
                "vod_play_url": "$$$".join(play_urls)
            }]
        }

    # ═════════ 搜索 ═════════
    def searchContent(self, key, quick, pg="1"):
        url = f"{self.siteUrl}/search/?q={parse.quote(key)}&p={pg}"
        html = self.fetch(url)
        videos = self._extract_videos(html)
        return {"list": videos, "page": int(pg), "pagecount": 999}

    # ═════════ 播放 ═════════
    def playerContent(self, flag, id, vipFlags):
        """
        id = 详情页 URL
        flag = 线路名称 (ServerTV, ServerHD, ServerVX, ServerST)
        """
        header = "User-Agent=Mozilla/5.0"

        if "k2s.cc" in id or "rapidgator" in id:
            return {"parse": 0, "url": id, "header": header}

        detail_url = id
        if not detail_url.startswith("http"):
            return {"parse": 0, "url": id, "header": header}

        html = self.fetch(detail_url)
        if not html:
            return {"parse": 0, "url": id, "header": header}

        movie_match = re.search(r'movie\s*=\s*({[\s\S]+?});', html)
        if not movie_match:
            return {"parse": 0, "url": id, "header": header}

        movie_str = movie_match.group(1)
        movie_id_match = re.search(r"id\s*:\s*['\"]([^'\"]+)['\"]", movie_str)
        movie_id = movie_id_match.group(1) if movie_id_match else ""

        sv_matches = re.findall(r'"(\d+)"\s*:\s*\["([^"]+)","([^"]+)"\]', movie_str)
        epi_matches = re.findall(r'"(\d+)"\s*:\s*\["([^"]+)"\]', movie_str)

        sv_map = {sid: name for sid, idx, name in sv_matches}
        epi_map = {sid: b64 for sid, b64 in epi_matches}

        selected_sid = None
        for sid, name in sv_map.items():
            if name == flag and sid in epi_map:
                selected_sid = sid
                break

        if not selected_sid:
            for sid, name in sv_map.items():
                if sid in epi_map and name != "DOWNLOAD":
                    selected_sid = sid
                    break

        if not selected_sid or not movie_id:
            return {"parse": 0, "url": id, "header": header}

        hash_b64 = epi_map[selected_sid]

        try:
            resp = self.session.post(
                f"{self.siteUrl}/api/watch",
                data={"id": movie_id, "hash": hash_b64},
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                    "Referer": detail_url,
                    "X-Requested-With": "XMLHttpRequest",
                    "Origin": "https://javfree.com",
                },
                timeout=15
            )
            result = resp.json()
            if result.get("status") == 1 and result.get("embed"):
                embed_url = result["embed"]
                if embed_url.startswith("//"):
                    embed_url = "https:" + embed_url

                if "turbovidhls" in embed_url or "turboviplay" in embed_url:
                    embed_resp = self.session.get(embed_url, headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                        "Referer": "https://javfree.com/",
                    }, timeout=15)
                    m3u8_match = re.search(r'(https?://[^\s"\'<>]+\.m3u8)', embed_resp.text)
                    if m3u8_match:
                        return {
                            "parse": 0,
                            "url": m3u8_match.group(1),
                            "header": header + "&Referer=" + embed_url
                        }
                    else:
                        return {"parse": 1, "url": embed_url, "header": header}
                else:
                    return {"parse": 1, "url": embed_url, "header": header}
        except Exception as e:
            print(f"[playerContent] 错误: {e}")

        return {"parse": 0, "url": id, "header": header}

    def _clean_title(self, text):
        text = text.replace("&#039;", "'").replace("&amp;", "&").replace("&quot;", '"').replace("&#8211;", "-")
        text = re.sub(r'<[^>]+>', '', text)
        return text.strip()

    def localProxy(self, param):
        return [404, "text/plain", "Not Found"]

    def isVideoFormat(self, url):
        return any(url.lower().endswith(ext) for ext in [".m3u8", ".mp4", ".ts", ".flv"])

    def manualVideoCheck(self):
        return False
