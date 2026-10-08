#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import re
import json
import base64
import html as html_lib
import urllib.request
import urllib.parse
from urllib.parse import urlparse, quote, unquote
import http.cookiejar
import gzip
import zlib
import ssl

try:
    from base.spider import Spider as SpiderBase
except ImportError:
    class SpiderBase(object):
        def __init__(self):
            self.extend = ""

        def getCache(self, key):
            return None

        def setCache(self, key, value):
            return "fail"

        def delCache(self, key):
            return "fail"


def _text(value):
    val = re.sub(r"<[^>]*>", "", value or "")
    return html_lib.unescape(re.sub(r"\s+", " ", val)).strip()


def _format_remarks(brand="蝴蝶影视", meta=""):
    clean_meta = str(meta or "").strip()
    clean_meta = re.sub(r"[\r\n\t]+", " ", clean_meta).strip()
    if clean_meta:
        return "%s | %s" % (brand, clean_meta)
    return brand


class Spider(SpiderBase):
    def __init__(self):
        super(Spider, self).__init__()
        self.defaultHost = "https://cn.avjoy.ws"
        self.baseHost = self.defaultHost
        self.navUrls = ["https://x99dh.cc", "https://x99dh.one"]
        self.targetSiteName = "avjoy"
        self.tgGroup = "https://t.me/tvshare23"
        self.brandActor = "🦋 TG群: @tvshare23"
        self.brandDirector = "🦋 蝴蝶影视"
        self._ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
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

        ext_host = self.options.get("siteUrl") or self.options.get("host")
        if ext_host:
            self.defaultHost = ext_host.rstrip("/")

        self._get_active_host()
        return True

    def getName(self):
        return "AVJOY·蝴蝶影视"

    def isVideoFormat(self, url):
        low = (url or "").lower()
        return any(k in low for k in (".m3u8", ".mp4", ".flv", ".mkv", ".avi", ".ts", ".mpd", "index.png"))

    def manualVideoCheck(self):
        return False

    def _resolve_nav_sites(self):
        headers = {
            "User-Agent": self._ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate"
        }

        for nav in self.navUrls:
            try:
                req = urllib.request.Request(nav, headers=headers)
                with self.opener.open(req, timeout=8) as resp:
                    raw = resp.read()
                    enc = getattr(resp, "headers", {}).get("Content-Encoding", "")
                    if raw.startswith(b"\x1f\x8b") or enc == "gzip":
                        raw = gzip.decompress(raw)
                    elif enc == "deflate":
                        try:
                            raw = zlib.decompress(raw)
                        except Exception:
                            raw = zlib.decompress(raw, -zlib.MAX_WBITS)
                    text = raw.decode("utf-8", errors="ignore")
            except Exception:
                text = ""

            if not text:
                continue

            b64_blocks = re.findall(r'["\']([A-Za-z0-9+/=]{100,})["\']', text)
            for b in b64_blocks:
                try:
                    decoded = base64.b64decode(b).decode("utf-8", errors="ignore")
                    unquoted = urllib.parse.unquote(decoded)
                    if self.targetSiteName in unquoted.lower() and "[" in unquoted:
                        site_list = json.loads(unquoted)
                        for item in site_list:
                            name_low = str(item.get("name", "")).strip().lower()
                            if name_low == self.targetSiteName:
                                cand_urls = []
                                main_url = item.get("url", "")
                                if main_url:
                                    cand_urls.append(main_url)
                                for u_obj in item.get("urls", []):
                                    u = u_obj.get("url", "")
                                    if u and u not in cand_urls:
                                        cand_urls.append(u)

                                for c_url in cand_urls:
                                    parsed = urllib.parse.urlparse(c_url)
                                    base = "%s://%s" % (parsed.scheme, parsed.netloc)
                                    chk = self._fetch(base + "/enter", check_host=False)
                                    if chk.get("code") == 200:
                                        return base
                except Exception:
                    continue

        return self.defaultHost

    def _get_active_host(self):
        cached_host = self.getCache("avjoy_live_host")
        if cached_host and cached_host.startswith("http"):
            self.baseHost = cached_host
            return self.baseHost

        new_host = self._resolve_nav_sites()
        self.baseHost = new_host if new_host else self.defaultHost
        self.setCache("avjoy_live_host", self.baseHost)
        return self.baseHost

    def _fetch(self, target_url, referer="", check_host=True):
        if not target_url:
            return {"code": 0, "text": "", "bytes": b"", "err": "", "final_url": ""}

        if target_url.startswith("//"):
            target_url = "https:" + target_url
        elif target_url.startswith("/"):
            target_url = self.baseHost + target_url

        headers = {
            "User-Agent": self._ua,
            "Referer": referer if referer else (self.baseHost + "/"),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive"
        }

        last_err = ""
        for attempt in range(2):
            try:
                req = urllib.request.Request(target_url, headers=headers)
                with self.opener.open(req, timeout=15) as resp:
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
                if e.code in (404, 451, 502, 503) and check_host and attempt == 0:
                    self.delCache("avjoy_live_host")
                    self._get_active_host()
                    target_url = re.sub(r'^https?://[^/]+', self.baseHost, target_url)
                    headers["Referer"] = self.baseHost + "/"
                    continue
                err_raw = ""
                try:
                    err_raw = e.read().decode("utf-8", errors="ignore")
                except Exception:
                    pass
                return {"code": e.code, "text": err_raw, "bytes": b"", "err": str(e), "final_url": target_url}
            except Exception as e:
                last_err = str(e)
                if attempt == 0 and check_host:
                    self.delCache("avjoy_live_host")
                    self._get_active_host()
                    target_url = re.sub(r'^https?://[^/]+', self.baseHost, target_url)
                    headers["Referer"] = self.baseHost + "/"
                    continue
                return {"code": -1, "text": "", "bytes": b"", "err": str(e), "final_url": target_url}

        return {"code": -1, "text": "", "bytes": b"", "err": last_err, "final_url": target_url}

    def homeContent(self, filter):
        classes = [
            {"type_name": "全部视频", "type_id": "/videos"},
            {"type_name": "📂 类别大全", "type_id": "/categories"},
            {"type_name": "最新发布", "type_id": "/videos?o=mr"},
            {"type_name": "最受喜爱", "type_id": "/videos?o=mv"},
            {"type_name": "最高评分", "type_id": "/videos?o=tr"},
            {"type_name": "播放最多", "type_id": "/videos?o=bw"},
            {"type_name": "中文字幕", "type_id": "/search/videos/%E4%B8%AD%E6%96%87%E5%AD%97%E5%B9%95"},
            {"type_name": "国产自拍", "type_id": "/search/videos/%E5%9B%BD%E4%BA%A7"}
        ]

        filters_map = {}
        if filter:
            video_filter = [
                {
                    "key": "o",
                    "name": "排序",
                    "init": "mr",
                    "value": [
                        {"n": "最新发布", "v": "mr"},
                        {"n": "最受喜爱", "v": "mv"},
                        {"n": "最高评分", "v": "tr"},
                        {"n": "最多收藏", "v": "tf"},
                        {"n": "播放最多", "v": "bw"},
                        {"n": "最多评论", "v": "md"},
                        {"n": "片长最长", "v": "lg"}
                    ]
                },
                {
                    "key": "type",
                    "name": "类型",
                    "init": "all",
                    "value": [
                        {"n": "全部", "v": "all"},
                        {"n": "精选视频", "v": "featured"},
                        {"n": "公开视频", "v": "public"},
                        {"n": "私密视频", "v": "private"}
                    ]
                },
                {
                    "key": "q",
                    "name": "画质",
                    "init": "all",
                    "value": [
                        {"n": "全部画质", "v": "all"},
                        {"n": "高清 1080P", "v": "hd"}
                    ]
                },
                {
                    "key": "t",
                    "name": "时间",
                    "init": "a",
                    "value": [
                        {"n": "全部时间", "v": "a"},
                        {"n": "今日更新", "v": "t"},
                        {"n": "本周更新", "v": "w"},
                        {"n": "本月更新", "v": "m"}
                    ]
                }
            ]
            filters_map["/videos"] = video_filter

        return {"class": classes, "filters": filters_map}

    def homeVideoContent(self):
        try:
            res = self._fetch("/videos")
            vod_list = self._parse_cards(res.get("text", ""))
            return {"list": vod_list[:20]}
        except Exception:
            return {"list": []}

    def _parse_categories(self, html):
        cards = []
        if not html:
            return cards

        pattern = re.compile(
            r'<a\b[^>]*href=["\'](/videos/[^"\']+)["\'][^>]*>[\s\S]*?'
            r'<img\b[^>]*src=["\']([^"\']+)["\'][^>]*>[\s\S]*?'
            r'<div\b[^>]*class=["\'][^"\']*title-truncate[^"\']*["\'][^>]*>([\s\S]*?)</div>[\s\S]*?'
            r'<div\b[^>]*class=["\'][^"\']*float-right[^"\']*["\'][^>]*>([\s\S]*?)</div>',
            re.I
        )

        seen_routes = set()
        for match in pattern.finditer(html):
            href, raw_img, raw_title, raw_count = match.group(1), match.group(2), match.group(3), match.group(4)
            clean_route = href.strip()
            if clean_route in seen_routes:
                continue

            title = _text(raw_title)
            count = _text(raw_count)

            pic = raw_img.strip()
            if pic.startswith("//"):
                pic = "https:" + pic
            elif pic.startswith("/"):
                pic = self.baseHost + pic

            cards.append({
                "vod_id": "folder@@" + clean_route,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": "蝴蝶影视 · %s部" % count if count else "蝴蝶影视",
                "vod_tag": "folder",
                "style": {"type": "rect", "ratio": 1.78}
            })
            seen_routes.add(clean_route)

        return cards

    def _parse_cards(self, html):
        cards = []
        if not html:
            return cards

        scope = html
        for sp in ["</header>", "</nav>", "class=\"content\"", "id=\"content\""]:
            if sp in scope:
                parts = scope.split(sp, 1)
                if len(parts) > 1:
                    scope = parts[1]
                    break

        seen_ids = set()
        card_re = re.compile(r'<a[^>]+href=["\'](/video/(\d+)/?[^"\']*)["\'][^>]*>([\s\S]*?)</a>', re.I)
        for match in card_re.finditer(scope):
            href, vid, body = match.group(1), match.group(2), match.group(3)
            if not vid or vid in seen_ids:
                continue

            title_m = re.search(r'title=["\']([^"\']+)["\']', body) or re.search(r'<span[^>]+class=["\'][^"\']*title[^"\']*["\'][^>]*>(.*?)</span>', body, re.I)
            raw_title = title_m.group(1).strip() if title_m else ("视频_%s" % vid)
            title = _text(raw_title)

            dur_m = re.search(r'(\d{1,2}:\d{2}(?::\d{2})?)', body)
            duration = dur_m.group(1) if dur_m else ""

            pic_m = (
                re.search(r'data-src=["\']([^"\']+)["\']', body, re.I) or
                re.search(r'data-original=["\']([^"\']+)["\']', body, re.I) or
                re.search(r'src=["\']([^"\']+)["\']', body, re.I) or
                re.search(r'url\([\'"]?([^\'")]+)[\'"]?\)', body, re.I)
            )
            raw_pic = pic_m.group(1).strip() if pic_m else ""
            if raw_pic.startswith("//"):
                pic = "https:" + raw_pic
            elif raw_pic.startswith("/"):
                pic = self.baseHost + raw_pic
            else:
                pic = raw_pic

            cards.append({
                "vod_id": str(vid),
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": _format_remarks("蝴蝶影视", duration),
                "style": {"type": "rect", "ratio": 1.78}
            })
            seen_ids.add(vid)

        return cards

    def categoryContent(self, tid, pg, filter, extend):
        del filter
        page = max(1, int(pg))
        route = str(tid).strip() if tid else "/videos"

        if route.startswith("folder@@"):
            real_cat_route = route.replace("folder@@", "")
            target_path = real_cat_route
            if page > 1:
                sep = "&" if "?" in target_path else "?"
                target_path = "%s%spage=%d" % (target_path, sep, page)

            try:
                res = self._fetch(target_path, referer=self.baseHost + "/categories")
                html = res.get("text", "")
                cards = self._parse_cards(html)

                pages = [int(p) for p in re.findall(r'[?&]page=(\d+)', html)]
                pagecount = max(pages) if pages else (page + (1 if len(cards) >= 16 else 0))

                return {
                    "page": page,
                    "pagecount": max(1, pagecount),
                    "limit": 20,
                    "total": max(1, pagecount) * 20,
                    "list": cards
                }
            except Exception:
                return {"page": page, "pagecount": max(1, page), "limit": 20, "total": 0, "list": []}

        if route == "/categories":
            try:
                res = self._fetch("/categories")
                html = res.get("text", "")
                cat_cards = self._parse_categories(html)
                return {
                    "page": 1,
                    "pagecount": 1,
                    "limit": len(cat_cards),
                    "total": len(cat_cards),
                    "list": cat_cards
                }
            except Exception:
                return {"page": 1, "pagecount": 1, "limit": 0, "total": 0, "list": []}

        parsed_url = urllib.parse.urlparse(route)
        base_path = parsed_url.path
        query_params = urllib.parse.parse_qs(parsed_url.query)

        if extend:
            for k in ("o", "type", "q", "t"):
                if extend.get(k) and extend.get(k) != "all":
                    query_params[k] = [extend.get(k)]

        if page > 1:
            query_params["page"] = [str(page)]

        new_query = urllib.parse.urlencode(query_params, doseq=True)
        final_url = base_path + (("?" + new_query) if new_query else "")

        try:
            res = self._fetch(final_url)
            html = res.get("text", "")
            cards = self._parse_cards(html)

            pages = [int(p) for p in re.findall(r'[?&]page=(\d+)', html)]
            pagecount = max(pages) if pages else (page + (1 if len(cards) >= 16 else 0))

            return {
                "page": page,
                "pagecount": max(1, pagecount),
                "limit": 20,
                "total": max(1, pagecount) * 20,
                "list": cards
            }
        except Exception:
            return {"page": page, "pagecount": max(1, page), "limit": 20, "total": 0, "list": []}

    def searchContent(self, key, quick, pg="1"):
        del quick
        page = max(1, int(pg))
        clean_key = str(key or "").strip()
        if not clean_key:
            return {"page": page, "pagecount": 1, "limit": 20, "total": 0, "list": []}

        enc_key = urllib.parse.quote(clean_key)
        target_path = "/search/videos/%s" % enc_key
        if page > 1:
            target_path += "?page=%d" % page

        try:
            res = self._fetch(target_path)
            html = res.get("text", "")
            cards = self._parse_cards(html)

            pages = [int(p) for p in re.findall(r'[?&]page=(\d+)', html)]
            pagecount = max(pages) if pages else (page + (1 if len(cards) >= 16 else 0))

            return {
                "page": page,
                "pagecount": max(1, pagecount),
                "limit": 20,
                "total": max(1, pagecount) * 20,
                "list": cards
            }
        except Exception:
            return {"page": page, "pagecount": max(1, page), "limit": 20, "total": 0, "list": []}

    def detailContent(self, ids):
        raw_id = ids[0] if isinstance(ids, (list, tuple)) else str(ids)
        vid = str(raw_id).strip()

        target_path = "/video/%s" % vid
        res = self._fetch(target_path, referer=self.baseHost + "/videos")
        html = res.get("text", "")

        is_missing = "video_missing" in html or "notfound" in html or res.get("code") == 404

        title_m = re.search(r'<h1[^>]*>([\s\S]*?)</h1>', html, re.I) or re.search(r'<title>([\s\S]*?)</title>', html, re.I)
        title = _text(title_m.group(1) if title_m else ("视频_%s" % vid))

        poster_m = (
            re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html, re.I) or
            re.search(r'poster=["\']([^"\']+)["\']', html, re.I) or
            re.search(r'data-poster=["\']([^"\']+)["\']', html, re.I)
        )
        poster = poster_m.group(1).strip() if poster_m else ""
        if poster.startswith("//"):
            poster = "https:" + poster
        elif poster.startswith("/"):
            poster = self.baseHost + poster

        tag_matches = re.findall(r'<a[^>]+href=["\'](?:/tag/|/search/videos/)[^"\']+["\'][^>]*>([\s\S]*?)</a>', html, re.I)
        tags = [_text(t) for t in tag_matches if _text(t) and len(_text(t)) < 20]

        dur_m = re.search(r'(\d{1,2}:\d{2}(?::\d{2})?)', html)
        duration = dur_m.group(1) if dur_m else ""

        if is_missing:
            play_from = "蝴蝶影视"
            play_url = "⚠️ 源站该视频已下架或失效$missing"
            tip_str = "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n【系统提醒】: 源站物理文件已删除或下架（Video Missing）"
        else:
            media_urls = re.findall(r'["\'](https?://[^"\']+\.(?:m3u8|mp4)[^"\']*)["\']', html)
            valid_media = [u for u in media_urls if not any(ext in u.lower() for ext in (".jpg", ".png", ".webp", ".gif"))]
            play_from = "蝴蝶影视"
            if valid_media:
                play_url = "正片$%s" % valid_media[0]
            else:
                play_url = "正片$%s" % vid
            tip_str = ""

        content_desc = (
            "【🔥 官方交流群: %s】\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "【当前接入节点】: %s\n"
            "【片名】: %s\n"
            "【时长】: %s\n"
            "【标签】: %s%s"
        ) % (self.tgGroup, self.baseHost, title, duration if duration else "全本", " / ".join(tags[:10]) if tags else "影视", tip_str)

        detail = {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": poster,
            "vod_actor": self.brandActor,
            "vod_director": self.brandDirector,
            "vod_remarks": _format_remarks("蝴蝶影视", duration),
            "vod_content": content_desc,
            "vod_play_from": play_from,
            "vod_play_url": play_url
        }

        return {"list": [detail]}

    def playerContent(self, flag, id, vipFlags):
        del flag, vipFlags
        raw_target = str(id).strip()

        if raw_target == "missing":
            return {"parse": 0, "playUrl": "", "url": "", "header": {}}

        if raw_target.startswith("http://") or raw_target.startswith("https://"):
            media_url = raw_target
        else:
            res = self._fetch("/video/%s" % raw_target, referer=self.baseHost + "/videos")
            html = res.get("text", "")
            if "video_missing" in html or "notfound" in html:
                return {"parse": 0, "playUrl": "", "url": "", "header": {}}

            media_urls = re.findall(r'["\'](https?://[^"\']+\.(?:m3u8|mp4)[^"\']*)["\']', html)
            valid_media = [u for u in media_urls if not any(ext in u.lower() for ext in (".jpg", ".png", ".webp", ".gif"))]
            media_url = valid_media[0] if valid_media else ""

        return {
            "parse": 0,
            "playUrl": "",
            "url": media_url,
            "header": {
                "User-Agent": self._ua,
                "Referer": self.baseHost + "/"
            }
        }

    def localProxy(self, params):
        return [404, "text/plain; charset=utf-8", "Proxy not configured"]

    def liveContent(self):
        return ""

    def action(self, action):
        return {}

    def destroy(self):
        self.options = {}