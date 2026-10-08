# -*- coding: utf-8 -*-
# 91动漫 - PeekPro 专用版
import re
import json
import time
import requests
from urllib.parse import urljoin, quote
from base.spider import Spider

class Spider(Spider):
    def getName(self):
        return "91动漫"

    def init(self, extend=""):
        self.host = "https://91dongman.net"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.host + "/",
        })
        self.class_map = {
            "lifan": "里番动漫",
            "paomian": "泡面番",
            "3d": "3D动画",
            "ai": "AI漫剧",
        }

    def _fetch(self, url, timeout=15):
        try:
            resp = self.session.get(url, timeout=timeout)
            resp.encoding = "utf-8"
            return resp.text
        except Exception as e:
            print(f"[91] 请求失败: {url} -> {e}")
            return ""

    def _fix_url(self, url):
        if not url:
            return ""
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return urljoin(self.host, url)
        return url

    def _parse_card(self, card):
        try:
            from bs4 import BeautifulSoup
            a = card.select_one("a.dm-card__media")
            if not a:
                return None
            href = a.get("href")
            if not href:
                return None
            path = href if href.startswith("/") else "/" + href
            title_tag = card.select_one(".dm-card__title h3")
            title = title_tag.get_text(strip=True) if title_tag else ""
            img = card.select_one(".dm-cover__image")
            pic = ""
            if img:
                pic = img.get("data-src") or img.get("src") or ""
            pic = self._fix_url(pic)
            remarks = []
            duration = card.select_one(".dm-card__duration")
            if duration:
                remarks.append(duration.get_text(strip=True))
            views = card.select_one(".dm-card__views")
            if views:
                remarks.append(views.get_text(strip=True))
            remark = " ".join(remarks)
            return {
                "vod_id": path,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remark,
            }
        except Exception:
            return None

    def homeContent(self, filter=False):
        classes = [{"type_id": tid, "type_name": name} for tid, name in self.class_map.items()]
        return {"class": classes}

    def homeVideoContent(self):
        return self.categoryContent("lifan", "1")

    def categoryContent(self, tid, pg, filter=False, extend=None):
        pg = int(pg) if pg else 1
        url = f"{self.host}/anime/{tid}/"
        if pg > 1:
            url = f"{url}?page={pg}"
        html = self._fetch(url)
        if not html:
            return {"list": [], "page": pg, "pagecount": 1, "limit": 20, "total": 0}

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select("article.dm-card")
        video_list = []
        for card in cards:
            item = self._parse_card(card)
            if item:
                video_list.append(item)

        pagecount = pg
        pagination = soup.select(".dm-pagination, .pagination, .pages")
        if pagination:
            max_page = 1
            for a in pagination[0].find_all("a"):
                href = a.get("href", "")
                m = re.search(r"[?&]page=(\d+)", href) or re.search(r"/page/(\d+)", href)
                if m:
                    num = int(m.group(1))
                    if num > max_page:
                        max_page = num
            if max_page > 1:
                pagecount = max_page
        else:
            if len(video_list) >= 20:
                pagecount = pg + 1

        return {
            "list": video_list,
            "page": pg,
            "pagecount": max(pagecount, pg),
            "limit": 20,
            "total": max(pagecount, pg) * 20,
        }

    def detailContent(self, ids):
        vid_path = ids[0] if isinstance(ids, list) else ids
        if not vid_path.startswith("/"):
            for cate in ["3d", "lifan", "paomian", "ai"]:
                test_path = f"/anime/{cate}/{vid_path}/"
                if self._fetch(urljoin(self.host, test_path)):
                    vid_path = test_path
                    break
            if not vid_path.startswith("/"):
                return {"list": []}

        detail_url = urljoin(self.host, vid_path) + "?_t=" + str(int(time.time()))
        html = self._fetch(detail_url)
        if not html:
            return {"list": []}

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")

        # ---- 标题 ----
        title = ""
        og_title = soup.find("meta", property="og:title")
        if og_title:
            title = og_title.get("content", "")
        if not title:
            title_tag = soup.find("title")
            if title_tag:
                title = title_tag.get_text(strip=True).replace(" - 91动漫", "")
        if not title:
            h1 = soup.find("h1")
            if h1:
                title = h1.get_text(strip=True)
        if not title:
            title = "未知标题"

        # ---- 封面 ----
        pic = ""
        og_img = soup.find("meta", property="og:image")
        if og_img:
            pic = og_img.get("content", "")
        if not pic:
            twitter_img = soup.find("meta", attrs={"name": "twitter:image"})
            if twitter_img:
                pic = twitter_img.get("content", "")
        if not pic:
            img = soup.select_one(".dm-cover__image")
            if img:
                pic = img.get("data-src") or img.get("src") or ""
        pic = self._fix_url(pic)

        # ---- 简介 ----
        desc = ""
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc:
            desc = meta_desc.get("content", "")
        if not desc:
            og_desc = soup.find("meta", property="og:description")
            if og_desc:
                desc = og_desc.get("content", "")
        if not desc:
            intro = soup.select_one(".dm-video-profile-card__intro p")
            if intro:
                desc = intro.get_text(strip=True)
        if not desc:
            desc = "暂无简介"

        # ---- 播放地址 ----
        play_url = ""
        player_div = soup.find(attrs={"data-video-url": True})
        if player_div:
            play_url = player_div.get("data-video-url")
        if not play_url:
            script_match = re.search(r'window\.dmPlayUrl\s*=\s*"([^"]+)"', html)
            if script_match:
                play_url = script_match.group(1)
        if not play_url:
            source = soup.find("source", src=True)
            if source:
                play_url = source.get("src")
        if not play_url:
            m3u8_match = re.search(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', html)
            if m3u8_match:
                play_url = m3u8_match.group(1)
        if play_url:
            play_url = self._fix_url(play_url)

        play_url_str = f"全集${play_url}" if play_url else ""

        # ---- 构建结果（多字段兼容） ----
        vod = {
            "vod_id": vid_path,
            "vod_name": title,
            "vod_pic": pic,
            "vod_poster": pic,          # 部分主题用
            "vod_img": pic,             # 冗余
            "vod_content": desc,
            "vod_desc": desc,           # 部分播放器用
            "vod_play_from": "91动漫",
            "vod_play_url": play_url_str,
        }

        # 打印提取结果（如果 PeekPro 有日志功能可查看）
        print(f"[91] 详情: 标题={title}, 封面={pic[:80]}, 简介={desc[:30]}, 播放={play_url[:60]}")
        return {"list": [vod]}

    def playerContent(self, flag, id, vipFlags=None):
        if not id or not id.startswith("http"):
            return {"parse": 0, "url": "", "header": {}}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": self.host + "/",
            "Origin": self.host,
        }
        return {"parse": 0, "url": id, "header": json.dumps(headers)}

    def searchContent(self, key, quick=False, pg="1"):
        pg = int(pg) if pg else 1
        enc_key = quote(key)
        url = f"{self.host}/search-result/?q={enc_key}"
        if pg > 1:
            url += f"&page={pg}"
        html = self._fetch(url)
        if not html:
            return {"list": [], "page": pg, "pagecount": 1, "limit": 20, "total": 0}

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select("article.dm-card")
        video_list = []
        for card in cards:
            item = self._parse_card(card)
            if item:
                video_list.append(item)

        pagecount = pg
        pagination = soup.select(".dm-pagination, .pagination, .pages")
        if pagination:
            max_page = 1
            for a in pagination[0].find_all("a"):
                href = a.get("href", "")
                m = re.search(r"[?&]page=(\d+)", href)
                if m:
                    num = int(m.group(1))
                    if num > max_page:
                        max_page = num
            if max_page > 1:
                pagecount = max_page
        else:
            if len(video_list) >= 20:
                pagecount = pg + 1

        return {
            "list": video_list,
            "page": pg,
            "pagecount": max(pagecount, pg),
            "limit": 20,
            "total": max(pagecount, pg) * 20,
        }

    def isVideoFormat(self, url):
        return url and (".m3u8" in url or ".mp4" in url)

    def manualVideoCheck(self):
        return False

    def destroy(self):
        if self.session:
            self.session.close()

    def localProxy(self, param):
        # 不实现代理，直接使用原始URL，PeekPro可能自己处理
        return None
