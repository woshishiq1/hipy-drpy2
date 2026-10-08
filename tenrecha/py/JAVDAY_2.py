#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 蜂蜜影视（FongMi TV / Chaquopy）原生 Python 蜘蛛 - JAVDAY 生产级规范版
# 严格遵循：纯标准库、无 f-string、品牌版权规范、宽屏 1.78 海报版型

import sys
import os
import re
import json
import base64
import html as html_module
import urllib.request
import urllib.parse
from urllib.parse import urljoin, quote, unquote
import http.cookiejar
import gzip
import zlib
import ssl

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider(object):
        def __init__(self):
            self.extend = ""

        def getProxyUrl(self, local=True):
            return "http://127.0.0.1:9978/proxy?do=py"


BASE_URL = "https://javday.app/"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
PAGE_SIZE = 20

CATEGORIES = (
    ("/label/new/", "最近更新"),
    ("/label/hot/", "人氣系列"),
    ("/category/new-release/", "新作上市"),
    ("/category/censored/", "有碼"),
    ("/category/uncensored/", "無碼"),
    ("/category/chinese-av/", "國產AV"),
    ("/category/uncensored-leaked/", "無碼流出"),
    ("/category/sex8/", "杏吧"),
    ("/category/hongkongdoll/", "HongKongDoll"),
    ("/category/aiav/", "AI短劇"),
)


def _text(value):
    value = re.sub(r"<[^>]*>", "", value or "")
    return html_module.unescape(re.sub(r"\s+", " ", value)).strip()


def _safe_title(value):
    return (value or "").replace("#", " ").replace("$", " ").strip()


def _absolute(base_url, value):
    return urllib.parse.urljoin(base_url, html_module.unescape(value or ""))


def category_path(route, page):
    page = max(1, int(page))
    route = "/" + route.strip("/") + "/"
    return route if page == 1 else ("%spage/%d/" % (route, page))


def search_path(keyword, page):
    page = max(1, int(page))
    encoded = urllib.parse.quote(str(keyword).strip(), safe="")
    root = "/search/wd/%s/" % encoded
    return root if page == 1 else ("%spage/%d/" % (root, page))


def parse_video_cards(document, base_url=BASE_URL):
    rows = []
    seen = set()
    anchor_re = re.compile(
        r'<a\b[^>]*href=["\'](?P<href>/videos/[^"\']+/)["\'][^>]*class=["\'][^"\']*\bvideoBox\b[^"\']*["\'][^>]*>(?P<body>.*?)(?=</a>)',
        re.I | re.S,
    )
    for match in anchor_re.finditer(document or ""):
        href = match.group("href")
        vod_id = href.strip("/").split("/")[-1]
        if not vod_id or vod_id in seen:
            continue
        body = match.group("body")
        title_match = re.search(r'<span\b[^>]*class=["\'][^"\']*\btitle\b[^"\']*["\'][^>]*>(.*?)</span>', body, re.I | re.S)
        pic_match = re.search(r'background-image\s*:\s*url\(\s*["\']?([^\)"\']+)', body, re.I)
        
        title = _text(title_match.group(1) if title_match else vod_id)
        raw_pic = html_module.unescape(pic_match.group(1).strip() if pic_match else "").strip("\"'")
        pic = _absolute(base_url, raw_pic)
        
        rows.append({
            "vod_id": vod_id,
            "vod_name": title or vod_id,
            "vod_pic": pic,
            "vod_remarks": "ZakaTV",
            "style": {"type": "rect", "ratio": 1.78}
        })
        seen.add(vod_id)
    return rows


def _first_group(document, pattern):
    match = re.search(pattern, document or "", re.I | re.S)
    return match.group(1).strip() if match else ""


def _all_text(document, pattern):
    return [_text(item) for item in re.findall(pattern, document or "", re.I | re.S) if _text(item)]


def extract_media_url(document):
    patterns = (
        r'new\s+Artplayer\s*\(\s*\{.*?\burl\s*:\s*["\'](https://[^"\']+\.m3u8(?:\?[^"\']*)?)["\']',
        r'<source\b[^>]*src=["\'](https://[^"\']+\.m3u8(?:\?[^"\']*)?)["\']',
        r'(https://[^"\'<>\s]+\.m3u8(?:\?[^"\'<>\s]*)?)',
    )
    for pattern in patterns:
        value = _first_group(document, pattern)
        if value:
            return html_module.unescape(value)
    return ""


def parse_detail(document, vod_id, base_url=BASE_URL, tg_group="https://t.me/+3t5XRPPo9mlkZDRl"):
    title = _text(_first_group(document, r'<h1\b[^>]*class=["\'][^"\']*\bvideo-title\b[^"\']*["\'][^>]*>(.*?)</h1>'))
    number = _text(_first_group(document, r'<span\b[^>]*class=["\'][^"\']*\bjpnum\b[^"\']*["\'][^>]*>(.*?)</span>'))
    tag_block = _first_group(document, r'<span\b[^>]*class=["\'][^"\']*\btag\b[^"\']*["\'][^>]*>(.*?)</span>')
    tags = _all_text(tag_block, r'<a\b[^>]*>(.*?)</a>')
    poster = _first_group(document, r'<meta\b[^>]*property=["\']og:image["\'][^>]*content=["\']([^"\']+)')
    if not poster:
        poster = _first_group(document, r'\bposter\s*:\s*["\']([^"\']+)["\']')
    
    media_url = extract_media_url(document)
    
    content_desc = (
        "【🔥 官方交流群: %s】\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "【片名】: %s\n"
        "【番號】: %s\n"
        "【標籤】: %s"
    ) % (tg_group, title or vod_id, number or "暂无", ", ".join(tags) if tags else "综合")
    
    detail = {
        "vod_id": str(vod_id),
        "vod_name": title or number or str(vod_id),
        "vod_pic": _absolute(base_url, poster),
        "vod_actor": "📺TG群: https://t.me/+3t5XRPPo9mlkZDRl",
        "vod_director": "📺ZakaTV",
        "vod_remarks": "ZakaTV",
        "vod_tag": ", ".join(tags),
        "vod_content": content_desc,
        "vod_play_from": "ZakaTV" if media_url else "",
        "vod_play_url": ("正片$%s" % vod_id) if media_url else "",
        "media_url": media_url,
    }
    return detail


def advertised_pagecount(document, current_page, item_count):
    numbers = [int(x) for x in re.findall(r'/page/(\d+)/', document or "", re.I)]
    if numbers:
        return max(max(numbers), int(current_page))
    return int(current_page) + (1 if item_count >= PAGE_SIZE else 0)


class Spider(BaseSpider):
    def __init__(self):
        super(Spider, self).__init__()
        self.siteUrl = BASE_URL
        self.tgGroup = "https://t.me/+3t5XRPPo9mlkZDRl"
        self.brandActor = "📺TG群: https://t.me/+3t5XRPPo9mlkZDRl"
        self.brandDirector = "📺ZakaTV"
        self._ua = USER_AGENT
        self.options = {}

        self.ctx = ssl.create_default_context()
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE

        self.cj = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cj),
            urllib.request.HTTPSHandler(context=self.ctx)
        )

    def init(self, extend=""):
        if isinstance(extend, dict):
            self.options = extend
        elif extend:
            try:
                self.options = json.loads(extend)
            except Exception:
                self.options = {}
        return True

    def getName(self):
        return "JAVDAY"

    def isVideoFormat(self, url):
        low = (url or "").lower()
        return any(k in low for k in (".m3u8", ".mp4", ".flv", ".mkv", ".avi", ".ts", ".mpd", "index.png"))

    def manualVideoCheck(self):
        return False

    def _fetch(self, path_or_url, referer=""):
        if not path_or_url:
            return {"code": 0, "text": "", "bytes": b"", "err": "", "final_url": ""}
        
        target_url = path_or_url if str(path_or_url).startswith(("http://", "https://")) else _absolute(self.siteUrl, path_or_url)
        
        headers = {
            "User-Agent": self._ua,
            "Referer": referer if referer else (self.siteUrl + "/"),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive"
        }

        last_err = ""
        for attempt in range(2):
            try:
                req = urllib.request.Request(target_url, headers=headers)
                with self.opener.open(req, timeout=12) as resp:
                    code = resp.getcode()
                    final_url = resp.geturl()
                    raw = resp.read()
                    enc = getattr(resp, "headers", {}).get("Content-Encoding", "")
                    if raw.startswith(b"\x1f\x8b") or enc == "gzip":
                        raw = gzip.decompress(raw)
                    elif enc == "deflate":
                        try:
                            raw = zlib.decompress(raw)
                        except Exception:
                            raw = zlib.decompress(raw, -zlib.MAX_WBITS)
                    try:
                        text = raw.decode("utf-8")
                    except Exception:
                        text = raw.decode("latin1", errors="ignore")
                    return {"code": code, "text": text, "bytes": raw, "err": "", "final_url": final_url}
            except urllib.error.HTTPError as e:
                last_err = "HTTP %s" % e.code
                if e.code in (451, 403, 429) and attempt == 0:
                    continue
                err_raw = ""
                try:
                    err_raw = e.read().decode("utf-8", errors="ignore")
                except Exception:
                    pass
                return {"code": e.code, "text": err_raw, "bytes": b"", "err": str(e), "final_url": target_url}
            except Exception as e:
                last_err = str(e)
                if attempt == 0:
                    continue
                return {"code": -1, "text": "", "bytes": b"", "err": str(e), "final_url": target_url}

        return {"code": -1, "text": "", "bytes": b"", "err": last_err, "final_url": target_url}

    def homeContent(self, filter):
        return {
            "class": [{"type_id": route, "type_name": name} for route, name in CATEGORIES],
            "filters": {},
            "list": []
        }

    def homeVideoContent(self):
        try:
            res = self._fetch("/")
            rows = parse_video_cards(res.get("text", ""), self.siteUrl)
            return {"list": rows[:PAGE_SIZE]}
        except Exception as error:
            return {"list": [], "msg": "首頁請求失敗：%s" % type(error).__name__}

    def categoryContent(self, tid, pg, filter, extend):
        del filter, extend
        page = max(1, int(pg))
        route = tid if any(tid == item[0] for item in CATEGORIES) else CATEGORIES[0][0]
        try:
            res = self._fetch(category_path(route, page))
            document = res.get("text", "")
            rows = parse_video_cards(document, self.siteUrl)
            pagecount = advertised_pagecount(document, page, len(rows))
            return {
                "page": page,
                "pagecount": pagecount,
                "limit": PAGE_SIZE,
                "total": pagecount * PAGE_SIZE,
                "list": rows
            }
        except Exception as error:
            return {
                "page": page,
                "pagecount": max(1, page),
                "limit": PAGE_SIZE,
                "total": 0,
                "list": [],
                "msg": "分類請求失敗：%s" % type(error).__name__
            }

    def searchContent(self, key, quick, pg="1"):
        del quick
        page = max(1, int(pg))
        if not str(key).strip():
            return {"page": page, "pagecount": 1, "limit": PAGE_SIZE, "total": 0, "list": []}
        try:
            res = self._fetch(search_path(key, page))
            document = res.get("text", "")
            rows = parse_video_cards(document, self.siteUrl)
            pagecount = advertised_pagecount(document, page, len(rows))
            return {
                "page": page,
                "pagecount": pagecount,
                "limit": PAGE_SIZE,
                "total": pagecount * PAGE_SIZE,
                "list": rows
            }
        except Exception as error:
            return {
                "page": page,
                "pagecount": max(1, page),
                "limit": PAGE_SIZE,
                "total": 0,
                "list": [],
                "msg": "搜尋請求失敗：%s" % type(error).__name__
            }

    def detailContent(self, ids):
        vod_id = str(ids[0] if isinstance(ids, (list, tuple)) else ids).strip()
        try:
            url_path = "/videos/%s/" % urllib.parse.quote(vod_id, safe="")
            res = self._fetch(url_path)
            detail = parse_detail(res.get("text", ""), vod_id, self.siteUrl, self.tgGroup)
            detail.pop("media_url", None)
            return {"list": [detail]}
        except Exception as error:
            return {"list": [], "msg": "詳情請求失敗：%s" % type(error).__name__}

    def playerContent(self, flag, id, vipFlags):
        del vipFlags
        vod_id = str(id).split("$")[-1].strip()
        try:
            url_path = "/videos/%s/" % urllib.parse.quote(vod_id, safe="")
            res = self._fetch(url_path)
            media_url = extract_media_url(res.get("text", ""))
            if not media_url:
                return {"parse": 0, "playUrl": "", "url": "", "header": {}, "msg": "詳情頁未發現已證實媒體源"}
            return {
                "parse": 0,
                "playUrl": "",
                "url": media_url,
                "header": {
                    "User-Agent": self._ua,
                    "Referer": _absolute(self.siteUrl, url_path)
                }
            }
        except Exception as error:
            return {"parse": 0, "playUrl": "", "url": "", "header": {}, "msg": "播放請求失敗：%s" % type(error).__name__}

    def localProxy(self, params):
        return [404, "text/plain; charset=utf-8", "Proxy not configured"]

    def liveContent(self):
        return ""

    def action(self, action):
        return {}

    def destroy(self):
        self.options = {}