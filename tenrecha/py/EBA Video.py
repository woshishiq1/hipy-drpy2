# -*- coding: utf-8 -*-
import json
import re
from urllib.parse import quote, urljoin

import requests
from lxml import etree
from base.spider import Spider


class Spider(Spider):
    def getName(self):
        return "EBA Video"

    def init(self, extend=""):
        self.host = "https://ebavideo.online"
        self.embed_host = "https://vwfastdelivery.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/"
        }
        self.classes = [
            {"type_id": "new", "type_name": "【最新】"},
            {"type_id": "popular", "type_name": "【精选】"},
            {"type_id": "mamy", "type_name": "MILF"},
            {"type_id": "domashnee", "type_name": "自拍"},
            {"type_id": "seks-molodyh", "type_name": "年轻"},
            {"type_id": "18-letnie", "type_name": "18岁"},
            {"type_id": "aziatki", "type_name": "亚洲"},
            {"type_id": "krasotki", "type_name": "美女"},
            {"type_id": "bolshie-siski", "type_name": "巨乳"},
            {"type_id": "bolshaya-zadnica", "type_name": "丰臀"},
            {"type_id": "minet", "type_name": "口交"},
            {"type_id": "anal", "type_name": "后庭"},
            {"type_id": "zrelye", "type_name": "熟女"},
            {"type_id": "zheny", "type_name": "人妻"},
            {"type_id": "sperma", "type_name": "内射"},
            {"type_id": "seks-russkih", "type_name": "俄罗斯"},
            {"type_id": "blondinki", "type_name": "金发"},
            {"type_id": "bryunetki", "type_name": "棕发"},
            {"type_id": "lyubitelskoe", "type_name": "业余"},
            {"type_id": "massazh", "type_name": "按摩"},
            {"type_id": "solo", "type_name": "独角"},
            {"type_id": "erotika", "type_name": "情色"},
            {"type_id": "gruppovoi-seks", "type_name": "群交"},
            {"type_id": "bolshoi-chlen", "type_name": "巨阳"},
            {"type_id": "kunilingus", "type_name": "舔阴"},
            {"type_id": "ot-pervogo-lica", "type_name": "POV"},
            {"type_id": "onlifans", "type_name": "OnlyFans"},
            {"type_id": "tiktok", "type_name": "TikTok"},
            {"type_id": "podborki", "type_name": "合集"},
            {"type_id": "kino", "type_name": "电影"},
        ]
        self.filters = {}

    def _get(self, url, referer=""):
        try:
            headers = dict(self.headers)
            if referer:
                headers["Referer"] = referer
            resp = requests.get(url, headers=headers, timeout=20)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding or "utf-8"
            return resp.text
        except Exception:
            return ""

    def _fix(self, url):
        return urljoin(self.host + "/", url or "")

    def _parse_list(self, html):
        if not html:
            return []
        tree, result, seen = etree.HTML(html), [], set()
        for node in tree.xpath('//a[contains(@class,"thumb__link") and contains(@href,"/novideo/")]'):
            href = node.get("href", "")
            match = re.search(r"/novideo/(\d+-\d+)\.html", href)
            if not match or match.group(1) in seen:
                continue
            seen.add(match.group(1))
            name = "".join(node.xpath('.//img/@alt')).strip()
            pic = "".join(node.xpath('.//img/@src')).strip()
            remark = "".join(node.xpath('.//em[contains(@class,"-bl")]//text()')).strip()
            result.append({
                "vod_id": match.group(1),
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": remark
            })
        return result

    def _pagecount(self, tree, page):
        values = []
        for href in tree.xpath('//a[contains(@href,"/")]/@href'):
            m = re.search(r"/(?:\w[\w-]*)/(\d+)/$", href)
            if m:
                values.append(int(m.group(1)))
        return max(values + [page])

    def homeContent(self, filter):
        return {
            "class": self.classes,
            "list": self._parse_list(self._get(self.host + "/")),
            "filters": self.filters
        }

    def categoryContent(self, tid, pg, filter, extend):
        page = max(1, int(pg or 1))
        if page == 1:
            url = f"{self.host}/{tid}/"
        else:
            url = f"{self.host}/{tid}/{page}/"
        html = self._get(url)
        tree = etree.HTML(html) if html else etree.HTML("<html/>")
        videos = self._parse_list(html)
        pagecount = self._pagecount(tree, page)
        return {
            "page": page,
            "pagecount": pagecount,
            "limit": len(videos),
            "total": pagecount * max(len(videos), 1),
            "list": videos
        }

    def detailContent(self, ids):
        result = []
        for vid in ids:
            html = self._get(f"{self.host}/novideo/{vid}.html")
            if not html:
                continue
            tree = etree.HTML(html)
            poster = "".join(tree.xpath('//div[contains(@class,"video-info__poster")]//img/@src')).strip()
            tags = tree.xpath('//a[contains(@class,"tags__tag")]')
            tag_names = [t.get("title", "") or "".join(t.itertext()).strip() for t in tags]
            categories = ", ".join(t for t in tag_names if t)
            meta_items = tree.xpath('//p[contains(@class,"video-info__inline")]')
            meta_text = " ".join("".join(m.itertext()).strip() for m in meta_items)
            iframe_src = "".join(tree.xpath('//div[contains(@class,"video__player")]//iframe/@src')).strip()
            title, play_url = "", ""
            if iframe_src:
                embed_html = self._get(iframe_src, referer=self.host + "/")
                if embed_html:
                    tm = re.search(r"video_title:\s*'([^']*)'", embed_html)
                    if tm:
                        title = tm.group(1)
                    um = re.search(r"video_url:\s*'([^']*)'", embed_html)
                    if um:
                        play_url = um.group(1)
            if not title:
                title = str(vid)
            content = f"{meta_text}\n分类: {categories}" if categories else meta_text
            plays = [f"播放${play_url}"] if play_url else []
            result.append({
                "vod_id": str(vid),
                "vod_name": title,
                "vod_pic": poster,
                "vod_content": content,
                "vod_play_from": "💕蜗牛专线💕",
                "vod_play_url": "#".join(plays)
            })
        return {"list": result}

    def searchContent(self, key, quick, pg="1"):
        page = max(1, int(pg or 1))
        url = f"{self.host}/search/?q={quote(key)}"
        if page > 1:
            url += f"&page={page}"
        return {
            "page": page,
            "pagecount": page,
            "list": self._parse_list(self._get(url))
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    def isVideoFormat(self, url):
        pass

    def playerContent(self, flag, id, vipFlags):
        play_url = id
        if play_url and any(x in play_url.lower() for x in (".mp4", ".m3u8", ".flv")):
            return {
                "parse": 0,
                "url": play_url,
                "header": {
                    "User-Agent": self.headers["User-Agent"],
                    "Referer": self.embed_host + "/"
                }
            }
        return {
            "parse": 1,
            "url": play_url or self.host,
            "header": dict(self.headers)
        }
