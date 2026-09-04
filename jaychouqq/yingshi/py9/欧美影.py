# -*- coding: utf-8 -*-
import json
import re
from urllib.parse import quote, unquote, urljoin

import requests
import urllib3
from lxml import etree

urllib3.disable_warnings()

try:
    from base.spider import Spider
except Exception:
    Spider = object


class Spider(Spider):
    def getName(self):
        return "欧美影院"

    def init(self, extend=""):
        self.host = "https://omeitv.com"
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        self.headers = {
            "User-Agent": self.ua,
            "Referer": self.host + "/",
        }
        self.classes = [
            {"type_id": "1", "type_name": "电影"},
            {"type_id": "2", "type_name": "连续剧"},
            {"type_id": "3", "type_name": "综艺"},
            {"type_id": "4", "type_name": "动漫"},
            {"type_id": "27", "type_name": "短剧"},
            {"type_id": "20", "type_name": "理论片"},
            {"type_id": "5", "type_name": "动作片"},
            {"type_id": "6", "type_name": "喜剧片"},
            {"type_id": "7", "type_name": "爱情片"},
            {"type_id": "8", "type_name": "科幻片"},
            {"type_id": "9", "type_name": "恐怖片"},
            {"type_id": "10", "type_name": "剧情片"},
            {"type_id": "11", "type_name": "战争片"},
            {"type_id": "22", "type_name": "纪录片"},
            {"type_id": "33", "type_name": "动画片"},
        ]
        self.filters = {c["type_id"]: [] for c in self.classes}

    # ---- HTTP ----

    def _get(self, url):
        try:
            r = requests.get(url, headers=self.headers, timeout=20, verify=False)
            r.raise_for_status()
            r.encoding = r.encoding or "utf-8"
            return r.text
        except Exception:
            return ""

    def _fix(self, url):
        return urljoin(self.host + "/", url or "")

    # ---- list parsing ----

    def _parse_list(self, html):
        """parse video cards: module-poster-item (category/home) + module-card-item (search)"""
        if not html:
            return []
        tree = etree.HTML(html)
        result, seen = [], set()

        # pattern 1: module-poster-item (category & homepage)
        for node in tree.xpath('//a[contains(@class,"module-poster-item") and contains(@href,"/film/")]'):
            match = re.search(r"/film/(\w+)\.html", node.get("href", ""))
            if not match or match.group(1) in seen:
                continue
            seen.add(match.group(1))
            name = node.get("title") or "".join(
                node.xpath('.//div[contains(@class,"module-poster-item-title")]/text()')
            ).strip()
            pic = "".join(
                node.xpath('.//div[contains(@class,"module-item-pic")]/@data-original')
            ).strip()
            remark = "".join(
                node.xpath('.//div[contains(@class,"module-item-note")]/text()')
            ).strip()
            result.append({
                "vod_id": match.group(1),
                "vod_name": name,
                "vod_pic": self._fix(pic),
                "vod_remarks": remark,
            })

        # pattern 2: module-card-item (search results, exclude container "module-card-items")
        for card in tree.xpath('//div[contains(@class,"module-card-item") and not(contains(@class,"module-card-items"))]'):
            link = card.xpath('.//a[contains(@href,"/film/") and contains(@class,"play-btn")]/@href')
            if not link:
                continue
            match = re.search(r"/film/(\w+)\.html", link[0])
            if not match or match.group(1) in seen:
                continue
            seen.add(match.group(1))
            name = "".join(
                card.xpath('.//div[contains(@class,"module-card-item-title")]//text()')
            ).strip()
            pic = "".join(
                card.xpath('.//div[contains(@class,"module-item-pic")]/@data-original')
            ).strip()
            remark = "".join(
                card.xpath('.//div[contains(@class,"module-item-note")]/text()')
            ).strip()
            result.append({
                "vod_id": match.group(1),
                "vod_name": name,
                "vod_pic": self._fix(pic),
                "vod_remarks": remark,
            })

        return result

    # ---- six interfaces ----

    def homeContent(self, filter):
        html = self._get(self.host + "/")
        return {
            "class": self.classes,
            "list": self._parse_list(html),
            "filters": self.filters,
            "header": {"Referer": self.host + "/"},
        }

    def homeVideoContent(self):
        return self._parse_list(self._get(self.host + "/"))

    def categoryContent(self, tid, pg, filter, extend):
        page = max(1, int(pg or 1))
        url = f"{self.host}/om/{tid}.html"
        html = self._get(url)
        videos = self._parse_list(html)
        return {
            "page": page,
            "pagecount": 1,
            "limit": len(videos),
            "total": len(videos),
            "list": videos,
            "header": {"Referer": self.host + "/"},
        }

    def detailContent(self, ids):
        result = []
        for vid in ids:
            html = self._get(f"{self.host}/film/{vid}.html")
            if not html:
                continue
            tree = etree.HTML(html)

            name = "".join(tree.xpath("//h1//text()")).strip()

            # pic: first data-original on the page (detail poster)
            pics = tree.xpath('//*[@data-original]/@data-original')
            pic = pics[0] if pics else ""

            # content
            content = " ".join(
                x.strip()
                for x in tree.xpath(
                    '//div[contains(@class,"module-info-content")]//text() | '
                    '//div[contains(@class,"content")]//text()'
                )
                if x.strip()
            )

            # play sources: each module-play-list panel = one source
            panels = tree.xpath('//div[contains(@class,"module-play-list")]')
            sources, playlists = [], []
            for i, panel in enumerate(panels):
                episodes = panel.xpath('.//a[contains(@href,"/play/")]')
                if not episodes:
                    continue

                # source name from heading
                heading_text = ""
                heading = panel.xpath(
                    './preceding-sibling::div[contains(@class,"module-heading")]//text() | '
                    './ancestor::div[contains(@class,"wi-play-list-box")]//div[contains(@class,"module-title")]//text()'
                )
                heading_text = " ".join(h.strip() for h in heading if h.strip())
                source_name = heading_text if heading_text else f"线路{i + 1}"

                plays = []
                seen_eps = set()
                for ep in episodes:
                    href = ep.get("href", "")
                    if href in seen_eps:
                        continue
                    seen_eps.add(href)
                    label = "".join(ep.xpath(".//text()")).strip()
                    if not label or label == "立即播放":
                        label = str(len(plays) + 1)
                    plays.append(label + "$" + href)
                if plays:
                    sources.append(source_name)
                    playlists.append("#".join(plays))

            result.append({
                "vod_id": str(vid),
                "vod_name": name,
                "vod_pic": self._fix(pic),
                "vod_content": content,
                "vod_play_from": "$$$".join(sources),
                "vod_play_url": "$$$".join(playlists),
            })
        return {"list": result}

    def searchContent(self, key, quick, pg="1"):
        page = max(1, int(pg or 1))
        url = f"{self.host}/search/{quote(key)}----------{page}---.html"
        html = self._get(url)
        tree = etree.HTML(html) if html else etree.HTML("<html/>")

        # pagecount from pagination links
        pagecount = 1
        page_values = [
            int(m)
            for href in tree.xpath('//a[contains(@href,"/search/")]/@href')
            for m in re.findall(r"----------(\d+)---", href)
        ]
        if page_values:
            pagecount = max(page_values + [page])

        videos = self._parse_list(html)
        return {
            "page": page,
            "pagecount": pagecount,
            "list": videos,
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    def playerContent(self, flag, id, vipFlags):
        url = self._fix(id)
        html = self._get(url)
        marker = "var player_aaaa="
        if marker in html:
            try:
                data = json.JSONDecoder().raw_decode(html.split(marker, 1)[1])[0]
                play_url = data.get("url", "")
                encrypt = int(data.get("encrypt", 0))
                if encrypt == 1:
                    play_url = unquote(play_url)
                if play_url and any(
                    x in play_url.lower() for x in (".m3u8", ".mp4", ".flv")
                ):
                    return {
                        "parse": 0,
                        "url": play_url,
                        "header": {
                            "User-Agent": self.ua,
                            "Referer": url,
                        },
                    }
            except Exception:
                pass
        return {
            "parse": 1,
            "url": url,
            "header": self.headers,
        }

    def isVideoFormat(self, url):
        pass
