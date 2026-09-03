# -*- coding: utf-8 -*-
import json
import re
from urllib.parse import quote, unquote, urljoin

import requests
from lxml import etree
from base.spider import Spider


class Spider(Spider):
    def getName(self): return "叔叔和侄女"

    def init(self, extend=""):
        self.host = "https://a1b2c3d4.shushu19.cc"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Referer": self.host + "/"
        }
        self.img_headers = {"Referer": self.host + "/"}
        self.classes = [
            {"type_id": "1", "type_name": "国产传媒"},
            {"type_id": "2", "type_name": "国产剧情"},
            {"type_id": "58", "type_name": "网曝黑料"},
            {"type_id": "3", "type_name": "特色仓库"},
            {"type_id": "69", "type_name": "精品资源"},
            {"type_id": "78", "type_name": "热播片库"},
        ]
        self.filters = {c["type_id"]: [] for c in self.classes}

    def _get(self, url):
        try:
            response = requests.get(url, headers=self.headers, timeout=15, verify=False)
            response.raise_for_status()
            ct = response.headers.get("Content-Type", "")
            m = re.search(r"charset=([\w-]+)", ct)
            response.encoding = m.group(1) if m else "utf-8"
            return response.text
        except Exception:
            return ""

    def _fix(self, url):
        return urljoin(self.host + "/", url or "")

    def _parse_list(self, html):
        if not html:
            return []
        tree = etree.HTML(html)
        result, seen = [], set()
        for card in tree.xpath('//a[contains(@href,"/voddetail/")]'):
            match = re.search(r"/voddetail/(\d+)\.html", card.get("href", ""))
            if not match or match.group(1) in seen:
                continue
            vid = match.group(1)
            seen.add(vid)
            name = "".join(card.xpath('.//p[contains(@class,"vod-name")]//text()')).strip()
            if not name:
                name = "".join(card.xpath('.//text()')).strip()
            pic = ""
            for attr in ("@data-original", "@data-src", "@src"):
                vals = card.xpath(f'.//img[contains(@class,"vod-pic")]/{attr}')
                if vals:
                    pic = vals[0]
                    break
            pic = self._fix(pic) if pic and not pic.startswith("http") else pic
            if "/template/" in pic:
                pic = ""
            remark = "".join(card.xpath('.//span[contains(@class,"vod-date")]//text()')).strip()
            result.append({"vod_id": vid, "vod_name": name, "vod_pic": pic, "vod_remarks": remark})
        return result

    def _pagecount(self, tree, page):
        tail = tree.xpath('//a[contains(text(),"尾")]/@href')
        if tail:
            m = re.findall(r"-(\d+)\.html", tail[0])
            if m:
                return int(m[-1])
        values = [int(x) for x in tree.xpath('//a[contains(@href,"/vodtype/")]/@href') for x in re.findall(r"-(\d+)\.html", x)]
        return max(values + [page])

    def homeContent(self, filter):
        html = self._get(f"{self.host}/vodtype/1-1.html")
        return {
            "class": self.classes,
            "list": self._parse_list(html),
            "filters": self.filters,
            "header": self.img_headers
        }

    def homeVideoContent(self):
        return {"list": self._parse_list(self._get(f"{self.host}/vodtype/1-1.html"))}

    def categoryContent(self, tid, pg, filter, extend):
        page = max(1, int(pg or 1))
        url = f"{self.host}/vodtype/{tid}-{page}.html"
        html = self._get(url)
        tree = etree.HTML(html) if html else etree.HTML("<html/>")
        videos = self._parse_list(html)
        pc = self._pagecount(tree, page)
        return {
            "page": page,
            "pagecount": pc,
            "limit": len(videos),
            "total": pc * max(len(videos), 1),
            "list": videos,
            "header": self.img_headers
        }

    def detailContent(self, ids):
        result = []
        for vid in ids:
            html = self._get(f"{self.host}/voddetail/{vid}.html")
            if not html:
                continue
            tree = etree.HTML(html)
            name = "".join(tree.xpath('//div[contains(@class,"detail-pos")]//text()')).strip()
            if not name:
                name = "".join(tree.xpath('//h1//text() | //h2//text()')).strip()
            pic = ""
            for attr in ("@data-original", "@data-src", "@src"):
                vals = tree.xpath(f'//img[contains(@class,"detail-vod-pic")]/{attr}')
                if vals:
                    pic = vals[0]
                    break
            pic = self._fix(pic) if pic and not pic.startswith("http") else pic
            content = " ".join(x.strip() for x in tree.xpath('//span[contains(@class,"detail-intro")]//text() | //div[contains(@class,"detail-intro")]//text()') if x.strip())
            play_btns = tree.xpath('//a[contains(@href,"/vodplay/")]/@href')
            play_path = play_btns[0] if play_btns else ""
            if not play_path:
                continue
            result.append({
                "vod_id": str(vid),
                "vod_name": name,
                "vod_pic": pic,
                "vod_content": content,
                "vod_play_from": "蜗牛专线",
                "vod_play_url": f"正片${play_path}"
            })
        return {"list": result}

    def searchContent(self, key, quick, pg="1"):
        page = max(1, int(pg or 1))
        url = f"{self.host}/vodsearch/-------------.html?wd={quote(key)}&page={page}"
        html = self._get(url)
        tree = etree.HTML(html) if html else etree.HTML("<html/>")
        videos = self._parse_list(html)
        tail = tree.xpath('//a[contains(text(),"尾")]/@href')
        pagecount = 1
        if tail:
            m = re.findall(r"----------(\d+)---", tail[0])
            if m:
                pagecount = int(m[0])
        return {"page": page, "pagecount": pagecount, "list": videos}

    def playerContent(self, flag, id, vipFlags):
        url = self._fix(id)
        html = self._get(url)
        marker = "var player_aaaa="
        if marker in html:
            try:
                data = json.JSONDecoder().raw_decode(html.split(marker, 1)[1])[0]
                play_url = data.get("url", "")
                if int(data.get("encrypt", 0)) == 1:
                    play_url = unquote(play_url)
                if play_url and any(x in play_url.lower() for x in (".m3u8", ".mp4", ".flv")):
                    return {
                        "parse": 0,
                        "url": play_url,
                        "header": {"User-Agent": self.headers["User-Agent"], "Referer": url}
                    }
            except Exception:
                pass
        return {"parse": 1, "url": url, "header": self.headers}
