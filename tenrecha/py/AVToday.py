# -*- coding: utf-8 -*-
# AVToday (https://avtoday.io) 爬虫源

import re
import json
import requests
from urllib.parse import urljoin, quote
from bs4 import BeautifulSoup
from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def init(self, extend=""):
        self.host = "https://avtoday.io"
        self.site_name = "AVToday"
        self.lang = "chs"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": self.host + "/",
        })
        self._debug = True
        return True

    def _log(self, msg):
        if self._debug:
            print(f"[{self.site_name}] {msg}")

    def _fix_url(self, url):
        if not url:
            return ""
        url = url.strip()
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return urljoin(self.host, url)
        if url.startswith("http"):
            return url
        return urljoin(self.host, "/" + url.lstrip("/"))

    def _fetch_html(self, url):
        try:
            resp = self.session.get(url, timeout=15)
            resp.encoding = "utf-8"
            return resp.text
        except Exception as e:
            self._log(f"请求失败: {url} -> {e}")
            return ""

    def _parse_videos(self, html):
        if not html:
            return []
        soup = BeautifulSoup(html, "html.parser")
        items = []

        cards = soup.select(".video-card.real-card, .thumbnail .video-card")
        if not cards:
            cards = soup.select(".thumbnail")
        if not cards:
            cards = soup.select(".video-card")

        self._log(f"找到 {len(cards)} 个视频卡片")

        for card in cards:
            try:
                pic = ""
                style = card.get("style", "")
                bg_match = re.search(r"url\(['\"]?([^'\"()]+)['\"]?\)", style)
                if bg_match:
                    pic = self._fix_url(bg_match.group(1))
                if not pic:
                    video_tag = card.select_one("video")
                    if video_tag:
                        bg = video_tag.get("style", "")
                        bg_match = re.search(r"url\(['\"]?([^'\"()]+)['\"]?\)", bg)
                        if bg_match:
                            pic = self._fix_url(bg_match.group(1))
                if not pic:
                    img = card.select_one("img")
                    if img:
                        pic = img.get("src") or ""
                        pic = self._fix_url(pic)

                a_tag = card.select_one("a[href*='/video/']")
                if not a_tag:
                    a_tag = card.select_one("a")
                if not a_tag:
                    continue
                href = a_tag.get("href", "")
                if not href or href == "#":
                    continue

                title = a_tag.get("title", "")
                if not title:
                    title_div = card.select_one(".video-title a")
                    if title_div:
                        title = title_div.get_text(strip=True)
                if not title:
                    title_span = card.select_one(".video-title")
                    if title_span:
                        title = title_span.get_text(strip=True)
                if not title:
                    title = href.split("/")[-1].replace(".html", "")

                vod_id = self._extract_id_from_url(href)
                if not vod_id:
                    match = re.search(r"/video/([^/]+)\.html", href)
                    if match:
                        vod_id = match.group(1)
                    else:
                        continue

                duration = ""
                duration_span = card.select_one(".video-duration")
                if duration_span:
                    duration = duration_span.get_text(strip=True)

                tag = ""
                tag_span = card.select_one(".video-tag")
                if tag_span:
                    tag = tag_span.get_text(strip=True)

                remark = duration
                if tag:
                    remark = f"{remark} {tag}" if remark else tag

                actor = ""
                actor_div = card.select_one(".video-actor")
                if actor_div:
                    actor = actor_div.get_text(strip=True)

                items.append({
                    "vod_id": vod_id,
                    "vod_name": title[:100],
                    "vod_pic": pic,
                    "vod_remarks": remark[:30],
                    "vod_actor": actor,
                    "_href": href,
                })
            except Exception as e:
                continue

        return items

    def _extract_id_from_url(self, url):
        match = re.search(r"/video/([^/]+)\.html", url)
        if match:
            return match.group(1)
        match = re.search(r"/video/([^/?]+)", url)
        if match:
            return match.group(1)
        return None

    def homeContent(self, filter=False):
        html = self._fetch_html(self.host)
        classes = []
        if html:
            soup = BeautifulSoup(html, "html.parser")
            sidebar_links = soup.select(".offcanvas-body .nav-link")
            for a in sidebar_links:
                href = a.get("href", "")
                name = a.get_text(strip=True)
                if href and name and href.startswith("/chs/catalog/"):
                    match = re.search(r"/chs/catalog/([^.]+)\.html", href)
                    if match:
                        tid = match.group(1)
                        if len(name) < 20 and name not in ["公告", "类型目录", "商务合作", "TG频道"]:
                            classes.append({
                                "type_id": tid,
                                "type_name": name
                            })

        if not classes:
            classes = [
                {"type_id": "中文字幕", "type_name": "中文字幕"},
                {"type_id": "無碼", "type_name": "無碼"},
                {"type_id": "FC2", "type_name": "FC2"},
                {"type_id": "長腿", "type_name": "長腿"},
                {"type_id": "巨乳", "type_name": "巨乳"},
                {"type_id": "多人", "type_name": "多人"},
                {"type_id": "素人", "type_name": "素人"},
            ]

        self._log(f"分类加载完成: {len(classes)} 个")
        return {"class": classes}

    def homeVideoContent(self):
        html = self._fetch_html(self.host)
        if not html:
            return {"list": []}
        items = self._parse_videos(html)
        seen = set()
        unique = []
        for v in items:
            if v["vod_id"] not in seen:
                seen.add(v["vod_id"])
                unique.append(v)
        return {"list": unique[:20]}

    def categoryContent(self, tid, pg=1, filter=False, extend=None):
        try:
            pg = int(pg) if pg else 1
            if pg == 1:
                url = self.host + f"/chs/catalog/{tid}.html"
            else:
                url = self.host + f"/chs/catalog/{tid}.html?page={pg}"
            self._log(f"分类请求: {url}")
            html = self._fetch_html(url)
            if not html:
                return {"list": [], "page": pg, "pagecount": 1, "limit": 0, "total": 0}

            items = self._parse_videos(html)
            self._log(f"解析到 {len(items)} 个视频")

            soup = BeautifulSoup(html, "html.parser")
            page_nav = soup.select(".pagination, .page-nav, .page-link")
            max_page = pg
            if page_nav:
                page_text = " ".join([p.get_text() for p in page_nav])
                nums = re.findall(r"(\d+)", page_text)
                if nums:
                    max_page = max([int(n) for n in nums if int(n) > 0])
            if max_page <= pg:
                max_page = pg + 1 if len(items) >= 20 else pg

            return {
                "list": items,
                "page": pg,
                "pagecount": max_page,
                "limit": len(items),
                "total": max_page * 20,
            }
        except Exception as e:
            self._log(f"categoryContent error: {e}")
            return {"list": [], "page": pg, "pagecount": 1, "limit": 0, "total": 0}

    def detailContent(self, ids):
        try:
            if isinstance(ids, list):
                vod_id = ids[0]
            else:
                vod_id = str(ids)

            if vod_id.startswith("http"):
                match = re.search(r"/video/([^/]+)\.html", vod_id)
                if match:
                    vod_id = match.group(1)
                else:
                    return {"list": []}

            self._log(f"详情 vod_id: {vod_id}")

            detail_url = self.host + f"/chs/video/{vod_id}.html"
            html = self._fetch_html(detail_url)
            if not html:
                return {"list": []}

            soup = BeautifulSoup(html, "html.parser")

            title = ""
            h1 = soup.find("h1")
            if h1:
                title = h1.get_text(strip=True)
            if not title:
                og_title = soup.find("meta", property="og:title")
                if og_title:
                    title = og_title.get("content", "")
            if not title:
                title_tag = soup.find("title")
                if title_tag:
                    title = title_tag.get_text(strip=True).split(" - ")[0]
            if not title:
                title = vod_id

            pic = ""
            og_image = soup.find("meta", property="og:image")
            if og_image:
                pic = og_image.get("content", "")
            if not pic:
                img = soup.select_one(".video-card img, .thumbnail img")
                if img:
                    pic = img.get("src") or ""
            if not pic:
                video_tag = soup.select_one("video")
                if video_tag:
                    bg = video_tag.get("style", "")
                    match = re.search(r"url\(['\"]?([^'\"()]+)['\"]?\)", bg)
                    if match:
                        pic = self._fix_url(match.group(1))
            pic = self._fix_url(pic)

            desc = ""
            meta_desc = soup.find("meta", attrs={"name": "description"})
            if meta_desc:
                desc = meta_desc.get("content", "")
            if not desc:
                desc_div = soup.select_one(".video-description, .description, .content")
                if desc_div:
                    desc = desc_div.get_text(strip=True)
            if not desc:
                for p in soup.select("p"):
                    text = p.get_text(strip=True)
                    if len(text) > 50 and len(text) < 1000:
                        desc = text
                        break

            play_url = self._extract_play_url(html)

            if play_url:
                if play_url.startswith("//"):
                    play_url = "https:" + play_url
                play_url = self._fix_url(play_url)
                play_url = f"全集${play_url}"
                play_from = self.site_name
            else:
                iframe = soup.select_one("iframe")
                if iframe:
                    iframe_src = iframe.get("src", "")
                    if iframe_src:
                        play_url = f"全集${self._fix_url(iframe_src)}"
                        play_from = self.site_name
                    else:
                        play_url = f"全集${detail_url}"
                        play_from = self.site_name
                else:
                    video = soup.select_one("video")
                    if video:
                        video_src = video.get("src", "")
                        if video_src:
                            play_url = f"全集${self._fix_url(video_src)}"
                            play_from = self.site_name
                        else:
                            source = video.select_one("source")
                            if source:
                                source_src = source.get("src", "")
                                if source_src:
                                    play_url = f"全集${self._fix_url(source_src)}"
                                    play_from = self.site_name
                                else:
                                    play_url = f"全集${detail_url}"
                                    play_from = self.site_name
                            else:
                                play_url = f"全集${detail_url}"
                                play_from = self.site_name
                    else:
                        play_url = f"全集${detail_url}"
                        play_from = self.site_name

            actor = ""
            actor_span = soup.select_one(".video-actor, .actor, .starring")
            if actor_span:
                actor = actor_span.get_text(strip=True)

            vod = {
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": pic,
                "vod_content": desc,
                "vod_actor": actor,
                "vod_play_from": play_from,
                "vod_play_url": play_url,
            }
            return {"list": [vod]}
        except Exception as e:
            self._log(f"detailContent error: {e}")
            return {"list": []}

    def _extract_play_url(self, html):
        patterns = [
            r'<video[^>]+src=["\']([^"\']+)["\']',
            r'<source[^>]+src=["\']([^"\']+)["\']',
            r'<iframe[^>]+src=["\']([^"\']+)["\']',
            r'video_url\s*[:=]\s*["\']([^"\']+)["\']',
            r'file\s*[:=]\s*["\']([^"\']+)["\']',
            r'url\s*[:=]\s*["\']([^"\']+\.(?:m3u8|mp4)[^"\']*)["\']',
            r'playUrl\s*[:=]\s*["\']([^"\']+)["\']',
            r'src\s*[:=]\s*["\']([^"\']+\.(?:m3u8|mp4)[^"\']*)["\']',
            r'(https?://[^\s"\']+\.(?:m3u8|mp4)[^\s"\']*)',
            r'(https?://[^\s"\']+/playlist\.m3u8[^\s"\']*)',
            r'var\s+now\s*=\s*["\']([^"\']+)["\']',
            r'player_data\s*=\s*({.*?})',
            r'var\s*player_aaaa\s*=\s*({.*?})',
            r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']',
        ]
        for pattern in patterns:
            m = re.search(pattern, html, re.I | re.DOTALL)
            if m:
                content = m.group(1).strip()
                if pattern.endswith('})'):
                    try:
                        data = json.loads(content)
                        for key in ["url", "playUrl", "video_url", "src", "file"]:
                            if key in data:
                                return self._fix_url(data[key])
                    except:
                        pass
                else:
                    if content.startswith("//"):
                        content = "https:" + content
                    if content.startswith("http"):
                        return content
        return None

    def playerContent(self, flag, id, vipFlags=None):
        if not id:
            return {"parse": 0, "url": "", "header": {}}

        if "$" in id:
            id = id.split("$", 1)[1]

        if id and (".m3u8" in id or ".mp4" in id or "playlist" in id):
            return {
                "parse": 0,
                "url": id,
                "header": json.dumps({
                    "User-Agent": "Mozilla/5.0",
                    "Referer": self.host + "/",
                    "Origin": self.host,
                })
            }

        if "/video/" in id:
            self._log(f"playerContent 请求: {id}")
            html = self._fetch_html(id)
            if html:
                play_url = self._extract_play_url(html)
                if play_url:
                    if play_url.startswith("//"):
                        play_url = "https:" + play_url
                    if ".m3u8" in play_url or ".mp4" in play_url or "playlist" in play_url:
                        return {
                            "parse": 0,
                            "url": play_url,
                            "header": json.dumps({
                                "User-Agent": "Mozilla/5.0",
                                "Referer": self.host + "/",
                            })
                        }
                iframe_match = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', html)
                if iframe_match:
                    iframe_url = self._fix_url(iframe_match.group(1))
                    iframe_html = self._fetch_html(iframe_url)
                    if iframe_html:
                        inner_url = self._extract_play_url(iframe_html)
                        if inner_url:
                            return {
                                "parse": 0,
                                "url": inner_url,
                                "header": json.dumps({
                                    "User-Agent": "Mozilla/5.0",
                                    "Referer": self.host + "/",
                                })
                            }
                    return {"parse": 1, "url": iframe_url, "header": json.dumps({"Referer": self.host + "/"})}

        return {"parse": 1, "url": id, "header": json.dumps({"Referer": self.host + "/"})}

    def searchContent(self, key, quick=False, pg="1"):
        try:
            pg = int(pg) if pg else 1
            enc_key = quote(key)
            url = self.host + f"/search?s={enc_key}"
            if pg > 1:
                url += f"&page={pg}"
            self._log(f"搜索: {url}")
            html = self._fetch_html(url)
            if not html:
                return {"list": [], "page": pg, "pagecount": 1, "limit": 0, "total": 0}

            items = self._parse_videos(html)

            soup = BeautifulSoup(html, "html.parser")
            page_nav = soup.select(".pagination, .page-nav")
            max_page = pg
            if page_nav:
                nums = re.findall(r"(\d+)", page_nav[0].get_text())
                if nums:
                    max_page = max([int(n) for n in nums if int(n) > 0])
            if max_page <= pg:
                max_page = pg + 1 if len(items) >= 20 else pg

            return {
                "list": items,
                "page": pg,
                "pagecount": max_page,
                "limit": len(items),
                "total": max_page * 20,
            }
        except Exception as e:
            self._log(f"searchContent error: {e}")
            return {"list": [], "page": int(pg), "pagecount": 1, "limit": 0, "total": 0}

    def isVideoFormat(self, url):
        return url and (".m3u8" in url or ".mp4" in url or "playlist" in url)

    def manualVideoCheck(self):
        return False

    def destroy(self):
        if self.session:
            self.session.close()