# -*- coding: utf-8 -*-
import re
import json
import requests
import base64
from urllib.parse import quote
from base.spider import Spider
from bs4 import BeautifulSoup


class Spider(Spider):

    # ☰
    def getName(self):
        return "太极影视"

    # ☷
    def init(self, extend=""):
        self.host = "https://104.233.159.136:2666"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.host + "/",
        })

    def _fix_url(self, url):
        if not url:
            return ""
        if url.startswith("http"):
            return url
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return self.host + url
        return self.host + "/" + url

    def _fetch(self, url, timeout=20):
        try:
            resp = self.session.get(url, timeout=timeout)
            if resp.status_code == 200:
                resp.encoding = "utf-8"
                return resp.text
            return ""
        except Exception as e:
            print(f"[{self.getName()}] 请求失败: {e}")
            return ""

    # ☳
    def homeContent(self, filter=False):
        try:
            html = self._fetch(self.host)
            if not html:
                return {"class": self._default_classes()}
            soup = BeautifulSoup(html, "html.parser")
            classes = []
            seen = set()
            for dl in soup.select(".youmu-app .area dl"):
                dt = dl.find("dt")
                if not dt:
                    continue
                a = dt.find("a")
                if not a:
                    continue
                name = a.get_text(strip=True)
                href = a.get("href", "")
                if "/vodtype/" in href:
                    tid = re.search(r"/vodtype/(\d+)\.html", href)
                    if tid and tid.group(1) not in seen:
                        seen.add(tid.group(1))
                        classes.append({"type_id": tid.group(1), "type_name": name})
            if not classes:
                classes = self._default_classes()
            return {"class": classes}
        except Exception as e:
            print(f"[{self.getName()}] homeContent 异常: {e}")
            return {"class": self._default_classes()}

    def _default_classes(self):
        return [
            {"type_id": "25", "type_name": "华章译语"},
            {"type_id": "26", "type_name": "泰西风月"},
            {"type_id": "27", "type_name": "云堆雪拥"},
            {"type_id": "22", "type_name": "素面朝天"},
            {"type_id": "23", "type_name": "镜花水月"},
            {"type_id": "24", "type_name": "丹青幻境"},
            {"type_id": "21", "type_name": "群芳竞艳"},
            {"type_id": "20", "type_name": "霓裳羽衣"},
            {"type_id": "34", "type_name": "阴阳化形"},
            {"type_id": "35", "type_name": "太虚幻境"},
            {"type_id": "31", "type_name": "风月宝鉴"},
            {"type_id": "32", "type_name": "并蒂莲开"},
            {"type_id": "33", "type_name": "豆蔻年华"},
            {"type_id": "28", "type_name": "赤诚相见"},
            {"type_id": "29", "type_name": "镜中倩影"},
            {"type_id": "30", "type_name": "窥影猎奇"},
        ]

    # ☲
    def homeVideoContent(self):
        try:
            html = self._fetch(self.host)
            if not html:
                return {"list": []}
            videos = self._extract_videos(html)
            return {"list": videos[:30]}
        except Exception as e:
            print(f"[{self.getName()}] homeVideoContent 异常: {e}")
            return {"list": []}

    def _extract_videos(self, html, container_selector=".thumbnail-group"):
        soup = BeautifulSoup(html, "html.parser")
        videos = []
        seen = set()
        for item in soup.select(container_selector + " li"):
            a = item.find("a", class_="thumbnail")
            if not a:
                continue
            href = a.get("href", "")
            if "/voddetail/" not in href:
                continue
            id_match = re.search(r"/voddetail/(\d+)\.html", href)
            vod_id = id_match.group(1) if id_match else ""
            if not vod_id or vod_id in seen:
                continue
            seen.add(vod_id)
            info = item.find("div", class_="video-info")
            name = ""
            if info:
                h5 = info.find("h5")
                if h5:
                    a2 = h5.find("a")
                    if a2:
                        name = a2.get_text(strip=True)
            if not name:
                name = a.get("title", "") or f"视频{vod_id}"
            img = a.find("img")
            pic = ""
            if img:
                pic = img.get("data-original", "") or img.get("src", "")
            pic = self._fix_url(pic)
            remarks = ""
            span = a.find("span", class_="video-grade")
            if span:
                remarks = span.get_text(strip=True)
            videos.append({"vod_id": vod_id, "vod_name": name, "vod_pic": pic, "vod_remarks": remarks})
        return videos

    def _extract_pagecount(self, html):
        soup = BeautifulSoup(html, "html.parser")
        for span in soup.select(".page span, .pagination span, .pages span"):
            text = span.get_text(strip=True)
            if "/" in text:
                parts = text.split("/")
                if len(parts) == 2:
                    try:
                        return int(parts[1].strip())
                    except:
                        pass
        for a in soup.select(".page a, .pagination a, .pages a"):
            href = a.get("href", "")
            if "尾页" in a.get_text() or "末页" in a.get_text():
                m = re.search(r"[-_](\d+)\.html", href)
                if m:
                    try:
                        return int(m.group(1))
                    except:
                        pass
        return 1

    # ☴
    def categoryContent(self, tid, pg, filter=False, extend=None):
        try:
            pg = int(pg) if str(pg).isdigit() else 1
            if pg <= 1:
                url = f"{self.host}/vodtype/{tid}.html"
            else:
                url = f"{self.host}/vodtype/{tid}-{pg}.html"
            html = self._fetch(url)
            if not html:
                return {"list": [], "page": pg, "pagecount": 1, "limit": 24, "total": 0}
            videos = self._extract_videos(html)
            pagecount = self._extract_pagecount(html)
            return {
                "list": videos,
                "page": pg,
                "pagecount": pagecount if pagecount > 1 else pg + 1,
                "limit": 24,
                "total": pagecount * 24 if pagecount > 1 else len(videos),
            }
        except Exception as e:
            print(f"[{self.getName()}] categoryContent 异常: {e}")
            return {"list": [], "page": pg, "pagecount": 1, "limit": 24, "total": 0}

    # ☱
    def detailContent(self, ids):
        try:
            vod_id = ids[0]
            if "/voddetail/" in vod_id:
                id_match = re.search(r"/voddetail/(\d+)\.html", vod_id)
                if id_match:
                    vod_id = id_match.group(1)
            url = f"{self.host}/voddetail/{vod_id}.html"
            html = self._fetch(url)
            if not html:
                return {"list": []}
            soup = BeautifulSoup(html, "html.parser")
            title = ""
            for tag in ["h1", "h2", "h3"]:
                title_el = soup.find(tag)
                if title_el:
                    title = title_el.get_text(strip=True)
                    if title:
                        break
            if not title:
                title_match = re.search(r"<title>(.*?)</title>", html, re.DOTALL)
                if title_match:
                    title = title_match.group(1).strip()
                    title = re.split(r"[-_](?:一牛影视|6080yy|爽爽婬人)", title)[0].strip()
                    title = re.split(r"[-_]\s*一牛", title)[0].strip()
            pic = ""
            img_el = soup.find("img", class_="loadi") or soup.find("img", class_="lazy")
            if img_el:
                pic = img_el.get("data-original", "") or img_el.get("src", "")
            pic = self._fix_url(pic)
            desc = ""
            meta_el = soup.find("meta", attrs={"name": "description"})
            if meta_el and meta_el.get("content"):
                desc = meta_el.get("content").strip()
                ad_keywords = ["同城", "约炮", "上门", "直播", "美女", "空降", "裸聊", "换妻", "强奸", "乱伦"]
                if any(k in desc for k in ad_keywords):
                    desc = ""
            if not desc:
                desc_el = soup.find("div", class_="content") or soup.find("div", class_="intro")
                if desc_el:
                    desc = desc_el.get_text(strip=True)
                    ad_keywords = ["同城", "约炮", "上门", "直播", "美女", "空降", "裸聊", "换妻", "强奸", "乱伦"]
                    if any(k in desc for k in ad_keywords):
                        desc = ""
            play_url = ""
            player_aaaa_match = re.search(r'var\s+player_aaaa\s*=\s*(\{.*?\})', html, re.DOTALL)
            if player_aaaa_match:
                try:
                    data = json.loads(player_aaaa_match.group(1))
                    play_url = data.get("url", "")
                except:
                    pass
            if not play_url:
                now_match = re.search(r'var\s+now\s*=\s*["\']([^"\']+\.m3u8[^"\']*)["\']', html)
                if now_match:
                    play_url = now_match.group(1)
            if not play_url:
                player_match = re.search(r'player_data\s*=\s*(\{.*?\})', html, re.DOTALL)
                if player_match:
                    try:
                        data = json.loads(player_match.group(1))
                        play_url = data.get("url", "")
                    except:
                        pass
            if not play_url:
                video_match = re.search(r'<video[^>]+src="([^"]+\.m3u8[^"]*)"', html)
                if video_match:
                    play_url = video_match.group(1)
            if not play_url:
                iframe_match = re.search(r'<iframe[^>]+src="([^"]+)"', html)
                if iframe_match:
                    iframe_src = iframe_match.group(1)
                    if iframe_src.startswith("/"):
                        iframe_src = self._fix_url(iframe_src)
                    if iframe_src.startswith("http"):
                        iframe_html = self._fetch(iframe_src)
                        if iframe_html:
                            m3u8_match = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', iframe_html)
                            if m3u8_match:
                                play_url = m3u8_match.group(1)
            if not play_url:
                play_btn = soup.find("a", href=re.compile(r"/vodplay/\d+-\d+-\d+\.html?"))
                if play_btn:
                    play_url = play_btn.get("href")
                else:
                    play_list = soup.select(".detail-play-list a")
                    for a in play_list:
                        href = a.get("href", "")
                        if "/vodplay/" in href:
                            play_url = href
                            break
            if play_url:
                if play_url.startswith("//"):
                    play_url = "https:" + play_url
                elif play_url.startswith("/"):
                    play_url = self._fix_url(play_url)
                if not play_url.startswith("http"):
                    play_url = self._fix_url(play_url)
            return {
                "list": [{
                    "vod_id": vod_id,
                    "vod_name": title or f"视频{vod_id}",
                    "vod_pic": pic,
                    "vod_content": desc,
                    "vod_play_from": "直链",
                    "vod_play_url": f"正片${play_url}" if play_url else f"正片$#",
                }]
            }
        except Exception as e:
            print(f"[{self.getName()}] detailContent 异常: {e}")
            return {"list": []}

    # ☵
    def playerContent(self, flag, id, vipFlags=None):
        try:
            result = {"parse": 0, "playUrl": "", "url": "", "header": {}}
            if not id or id == "#":
                return result
            if id.startswith("http") and (".m3u8" in id or ".mp4" in id or ".ts" in id):
                result["url"] = id
                result["header"] = {
                    "Referer": self.host + "/",
                    "User-Agent": self.session.headers.get("User-Agent", "Mozilla/5.0"),
                }
                return result
            if "/vodplay/" in id or "vodplay" in id or ".htm" in id:
                if not id.startswith("http"):
                    id = self._fix_url(id)
                html = self._fetch(id)
                if html:
                    player_aaaa_match = re.search(r'var\s+player_aaaa\s*=\s*(\{.*?\})', html, re.DOTALL)
                    if player_aaaa_match:
                        try:
                            data = json.loads(player_aaaa_match.group(1))
                            m3u8_url = data.get("url", "")
                            if m3u8_url and not m3u8_url.startswith("http"):
                                m3u8_url = self._fix_url(m3u8_url)
                            if m3u8_url:
                                result["url"] = m3u8_url
                                result["header"] = {
                                    "Referer": self.host + "/",
                                    "User-Agent": self.session.headers.get("User-Agent", "Mozilla/5.0"),
                                }
                                return result
                        except Exception as e:
                            print(f"[playerContent] player_aaaa 解析失败: {e}")
                    now_match = re.search(r'var\s+now\s*=\s*["\']([^"\']+\.m3u8[^"\']*)["\']', html)
                    if now_match:
                        m3u8_url = now_match.group(1)
                        if not m3u8_url.startswith("http"):
                            m3u8_url = self._fix_url(m3u8_url)
                        result["url"] = m3u8_url
                        result["header"] = {
                            "Referer": self.host + "/",
                            "User-Agent": self.session.headers.get("User-Agent", "Mozilla/5.0"),
                        }
                        return result
                    player_match = re.search(r'player_data\s*=\s*(\{.*?\})', html, re.DOTALL)
                    if player_match:
                        try:
                            data = json.loads(player_match.group(1))
                            m3u8_url = data.get("url", "")
                            if m3u8_url and not m3u8_url.startswith("http"):
                                m3u8_url = self._fix_url(m3u8_url)
                            if m3u8_url:
                                result["url"] = m3u8_url
                                result["header"] = {
                                    "Referer": self.host + "/",
                                    "User-Agent": self.session.headers.get("User-Agent", "Mozilla/5.0"),
                                }
                                return result
                        except:
                            pass
                    video_match = re.search(r'<video[^>]+src="([^"]+\.m3u8[^"]*)"', html)
                    if video_match:
                        m3u8_url = video_match.group(1)
                        if not m3u8_url.startswith("http"):
                            m3u8_url = self._fix_url(m3u8_url)
                        result["url"] = m3u8_url
                        result["header"] = {
                            "Referer": self.host + "/",
                            "User-Agent": self.session.headers.get("User-Agent", "Mozilla/5.0"),
                        }
                        return result
            if id.startswith("/"):
                id = self._fix_url(id)
                result["url"] = id
                result["header"] = {
                    "Referer": self.host + "/",
                    "User-Agent": self.session.headers.get("User-Agent", "Mozilla/5.0"),
                }
                return result
            result["url"] = id
            return result
        except Exception as e:
            print(f"[{self.getName()}] playerContent 异常: {e}")
            return {"parse": 0, "playUrl": "", "url": id, "header": {}}

    # ☳
    def searchContent(self, key, quick=False, pg="1"):
        try:
            pg = int(pg) if str(pg).isdigit() else 1
            enc_key = quote(key)
            url = f"{self.host}/vodsearch/-------------.html?wd={enc_key}"
            if pg > 1:
                url += f"&page={pg}"
            html = self._fetch(url)
            if not html:
                return {"list": [], "page": pg, "pagecount": 1, "limit": 24, "total": 0}
            videos = self._extract_videos(html)
            pagecount = self._extract_pagecount(html)
            return {
                "list": videos,
                "page": pg,
                "pagecount": pagecount if pagecount > 1 else pg + 1,
                "limit": 24,
                "total": pagecount * 24 if pagecount > 1 else len(videos),
            }
        except Exception as e:
            print(f"[{self.getName()}] searchContent 异常: {e}")
            return {"list": [], "page": pg, "pagecount": 1, "limit": 24, "total": 0}

    def isVideoFormat(self, url):
        return url and (".m3u8" in url or ".mp4" in url or ".ts" in url)

    def manualVideoCheck(self):
        return False

    def destroy(self):
        if self.session:
            self.session.close()

    # ☶
    def localProxy(self, param):
        try:
            url = param.get("url", "")
            if not url:
                return [404, "text/plain", b""]
            resp = self.session.get(url, headers={
                "Referer": self.host + "/",
                "User-Agent": self.session.headers.get("User-Agent", "Mozilla/5.0"),
            }, timeout=15)
            content_type = resp.headers.get("Content-Type", "image/jpeg")
            return [200, content_type, resp.content]
        except Exception as e:
            print(f"[{self.getName()}] localProxy 异常: {e}")
            gif = base64.b64decode("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7")
            return [200, "image/gif", gif]
