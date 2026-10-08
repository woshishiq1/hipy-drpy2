# coding: utf-8
"""
4kvm.top
"""

import json
import re
import requests
from urllib.parse import quote, unquote
from base.spider import Spider
try:
    from html import unescape
except ImportError:
    from HTMLParser import HTMLParser
    unescape = HTMLParser().unescape

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
SITE = "https://4kvm.top"
TIME = 15


def _get(url):
    return requests.get(url, headers={"User-Agent": UA, "Accept": "text/html,application/xhtml+xml"}, timeout=TIME)


def _parse_cards(html):
    cards = []
    seen = set()
    for m in re.finditer(
        r'<a\s+href="/play/([^"]+)"[^>]*>[\s\S]*?(?:data-src|src)\s*=\s*"([^"]+)"[\s\S]*?alt="([^"]+)"',
        html, re.IGNORECASE,
    ):
        vid = m.group(1)
        if vid in seen:
            continue
        seen.add(vid)
        cards.append({"vod_id": vid, "vod_name": m.group(3).strip(), "vod_pic": unescape(m.group(2).strip()), "vod_remarks": ""})
    remarks_all = re.findall(r"(全\d+集|更新至\d+集|完结)", html)
    for i, card in enumerate(cards):
        if i < len(remarks_all):
            card["vod_remarks"] = remarks_all[i]
    if not cards:
        for m in re.finditer(
            r'href="/play/([^"]+)"[^>]*>[\s\S]*?(?:data-src|src)="([^"]+)"[\s\S]*?alt="([^"]+)"',
            html, re.IGNORECASE,
        ):
            cards.append({"vod_id": m.group(1), "vod_name": m.group(3).strip(), "vod_pic": unescape(m.group(2).strip()), "vod_remarks": ""})
    return cards


class Spider(Spider):

    def getName(self):
        return "4k"

    def init(self, extend=""):
        pass

    def isVideoFormat(self, url):
        return None

    def manualVideoCheck(self):
        return None

    def homeContent(self, filterable):
        result = {"class": [{"type_id": "movie", "type_name": "电影"}, {"type_id": "tv", "type_name": "电视剧"}, {"type_id": "anime", "type_name": "动漫"}], "list": []}
        try:
            resp = _get(SITE)
            result["list"] = _parse_cards(resp.text)
        except Exception:
            pass
        return result

    def homeVideoContent(self):
        return self.homeContent(False)

    def categoryContent(self, cid, pg, filter, ext):
        try:
            page = int(pg)
        except Exception:
            page = 1
        result = {"list": [], "page": page, "pagecount": 999, "limit": 24, "total": 999}
        try:
            resp = _get(SITE + "/" + cid + "?page=" + str(page))
            result["list"] = _parse_cards(resp.text)
        except Exception:
            pass
        return result

    def searchContent(self, key, quick, pg="1"):
        try:
            page = int(pg)
        except Exception:
            page = 1
        keyword = str(key or "").strip()
        result = {"list": [], "page": page, "pagecount": 1, "limit": 24, "total": 0}
        try:
            resp = _get(SITE + "/search?q=" + quote(keyword) + "&page=" + str(page))
            result["list"] = _parse_cards(resp.text)
            result["total"] = len(result["list"])
        except Exception:
            pass
        return result

    def detailContent(self, ids):
        vid = str(ids[0]) if ids else ""
        url = SITE + "/play/" + vid
        result = {"list": []}
        try:
            resp = _get(url)
            html = resp.text

            title = ""
            m = re.search(r"<title>\s*(.+?)\s*[-–]\s*4k影视", html)
            if m:
                title = re.sub(r"\s*[-–]\s*第\d+集$", "", m.group(1).strip())

            poster = ""
            m = re.search(r'og:image"\s+content="([^"]+)"', html)
            if m:
                poster = m.group(1)

            desc = ""
            m = re.search(r'og:description"\s+content="([^"]+)"', html)
            if m:
                desc = m.group(1)

            year, type_name = "", ""
            m = re.search(r'name="keywords"\s+content="([^"]+)"', html)
            if m:
                parts = [x.strip() for x in m.group(1).split(",") if x.strip()]
                for p in parts:
                    if re.match(r"^\d{4}$", p):
                        year = p
                    elif p not in ("4k", title, "4k影视") and not type_name:
                        type_name = p

            rating = ""
            m = re.search(r"(\d+\.\d+)\s*/\s*(?:10|<)", html)
            if m:
                rating = m.group(1)

            play_urls = []
            seen_eps = set()
            for m in re.finditer(
                r'<a\s+href="(/play/[^"]+)"[^>]*data-episode="(\d+)"',
                html,
            ):
                ep_url, ep_num = m.group(1), m.group(2)
                if ep_num in seen_eps:
                    continue
                seen_eps.add(ep_num)
                play_urls.append("第" + ep_num + "集$" + SITE + ep_url)

            if not play_urls:
                play_urls = ["正片$" + url]

            remarks = ""
            m = re.search(r"(全\d+集|更新至\d+集|完结)", html)
            if m:
                remarks = m.group(1)

            vod = {
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": poster,
                "type_name": type_name,
                "vod_year": year,
                "vod_content": desc,
                "vod_remarks": remarks or rating or "",
                "vod_play_from": "4k影视",
                "vod_play_url": "#".join(play_urls),
            }
            result["list"].append(vod)
        except Exception:
            pass
        return result

    def playerContent(self, flag, id, vipFlags=None):
        play_url = str(id or "").strip()
        if not play_url.startswith("http"):
            play_url = SITE + play_url
        return {
            "parse": 1,
            "playUrl": "",
            "url": play_url,
            "header": json.dumps({"User-Agent": UA, "Referer": SITE + "/"}),
        }

    def localProxy(self, params):
        return None
