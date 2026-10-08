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
        def getCache(self, key): return None
        def setCache(self, key, value): return "fail"
        def delCache(self, key): return "fail"

def format_remarks(brand="📺ZakaTV", meta=""):
    clean_meta = str(meta or "").strip()
    clean_meta = re.sub(r"[\r\n\t]+", " ", clean_meta).strip()
    if clean_meta:
        return "%s | %s" % (brand, clean_meta)
    return brand

def safe_quote_url(url):
    if not url:
        return ""
    parts = urllib.parse.urlsplit(url)
    encoded_path = urllib.parse.quote(parts.path, safe="/:")
    encoded_query = urllib.parse.quote(parts.query, safe="=&?/")
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, encoded_path, encoded_query, parts.fragment))

COLOR_PALETTES = [
    ("4f46e5", "ffffff"),
    ("0284c7", "ffffff"),
    ("059669", "ffffff"),
    ("d97706", "ffffff"),
    ("dc2626", "ffffff"),
    ("7c3aed", "ffffff"),
    ("db2777", "ffffff"),
    ("0d9488", "ffffff"),
    ("ea580c", "ffffff"),
    ("16a34a", "ffffff"),
    ("9333ea", "ffffff"),
    ("ca8a04", "ffffff"),
]

def get_color_dummy_pic(text, is_actor=False):
    idx = sum(ord(c) for c in text) % len(COLOR_PALETTES)
    bg_color, text_color = COLOR_PALETTES[idx]
    res = "400x400" if is_actor else "640x360"
    display_txt = text.strip()[:2]
    return "https://dummyimage.com/%s/%s/%s.png&text=%s" % (res, bg_color, text_color, quote(display_txt))

class Spider(SpiderBase):
    def __init__(self):
        super(Spider, self).__init__()
        self.siteUrl = "https://www.njav.com"
        self.entryUrl = "https://www.njav.com/zh"
        self.tgGroup = "https://t.me/+3t5XRPPo9mlkZDRl"
        self.brandActor = "📺TG群: https://t.me/+3t5XRPPo9mlkZDRl"
        self.brandDirector = "📺ZakaTV"
        self._ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        self.options = {}

        self._build_opener()

    def _build_opener(self):
        self.ctx = ssl.create_default_context()
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE
        try:
            self.ctx.set_ciphers("DEFAULT@SECLEVEL=1")
        except Exception:
            pass

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
        return "NJAV·ZakaTV"

    def isVideoFormat(self, url):
        low = (url or "").lower()
        return any(k in low for k in (".m3u8", ".mp4", ".flv", ".mkv", ".avi", ".ts", ".mpd", "index.png"))

    def manualVideoCheck(self):
        return False

    def _fetch(self, target_url, referer="", headers_extra=None):
        if not target_url.startswith("http"):
            target_url = urllib.parse.urljoin(self.entryUrl + "/", target_url)

        target_url = safe_quote_url(target_url)

        headers = {
            "User-Agent": self._ua,
            "Referer": referer if referer else (self.entryUrl + "/"),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Sec-Ch-Ua": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Upgrade-Insecure-Requests": "1",
            "Connection": "keep-alive"
        }
        if headers_extra:
            headers.update(headers_extra)

        last_err = ""
        for attempt in range(3):
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
                    text = raw.decode("utf-8", errors="ignore")
                    return {"code": code, "text": text, "bytes": raw, "final_url": final_url, "err": "", "headers": dict(resp.headers)}
            except urllib.error.HTTPError as e:
                last_err = "HTTP %s" % e.code
                err_raw = ""
                try:
                    err_raw = e.read().decode("utf-8", errors="ignore")
                except Exception:
                    pass
                return {"code": e.code, "text": err_raw, "bytes": b"", "final_url": target_url, "err": str(e), "headers": {}}
            except Exception as e:
                last_err = str(e)
                if attempt < 2 and any(k in last_err for k in ("EOF", "violation", "handshake", "reset")):
                    self._build_opener()
                    continue
                return {"code": -1, "text": "", "bytes": b"", "final_url": target_url, "err": last_err, "headers": {}}

        return {"code": -1, "text": "", "bytes": b"", "final_url": target_url, "err": last_err, "headers": {}}

    def homeContent(self, filter):
        classes = [
            {"type_name": "新上映", "type_id": "new-release"},
            {"type_name": "有码", "type_id": "censored"},
            {"type_name": "无码", "type_id": "uncensored"},
            {"type_name": "素人", "type_id": "amateur"},
            {"type_name": "中国AV", "type_id": "chinese-av"},
            {"type_name": "中国直播", "type_id": "chinese-live"},
            {"type_name": "韩国直播", "type_id": "korean-live"},
            {"type_name": "制造商", "type_id": "make"},
            {"type_name": "女优", "type_id": "actor"},
            {"type_name": "系列", "type_id": "series"}
        ]

        result = {"class": classes}

        if filter:
            result["filters"] = {
                "uncensored": [
                    {
                        "key": "sub",
                        "name": "厂牌/子类",
                        "init": "uncensored",
                        "value": [
                            {"n": "全部无码", "v": "uncensored"},
                            {"n": "无码流出", "v": "uncensored-leaked"}
                        ]
                    }
                ]
            }

        return result

    def homeVideoContent(self):
        return {"list": []}

    def _parse_cards(self, html_text):
        cards = []
        if not html_text:
            return cards

        chunks = html_text.split('class="box-item"')
        if len(chunks) <= 1:
            return cards

        seen = set()
        for chunk in chunks[1:]:
            href_m = re.search(r'href=["\'](/?xvideos/[^"\']+)["\']', chunk, re.I)
            if not href_m:
                continue
            href = href_m.group(1).strip()
            full_href = href if href.startswith("http") else ("https://www.njav.com/" + href.lstrip("/"))

            if full_href in seen:
                continue
            seen.add(full_href)

            pic = ""
            d_src = re.search(r'data-src=["\']([^"\']+)["\']', chunk, re.I)
            src_m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', chunk, re.I)
            if d_src:
                pic = d_src.group(1).strip()
            elif src_m and not src_m.group(1).startswith("data:image"):
                pic = src_m.group(1).strip()

            if pic.startswith("//"):
                pic = "https:" + pic

            title = ""
            detail_m = re.search(r'class=["\'][^"\']*detail[^"\']*["\'][\s\S]*?<a[^>]*>([\s\S]*?)</a>', chunk, re.I)
            if detail_m:
                title = re.sub(r'<[^>]+>', '', detail_m.group(1)).strip()

            if not title:
                alt_m = re.search(r'alt=["\']([^"\']+)["\']', chunk, re.I)
                if alt_m:
                    title = alt_m.group(1).strip()

            if not title:
                title = full_href.rstrip("/").split("/")[-1].upper()

            duration_m = re.search(r'class=["\'][^"\']*duration[^"\']*["\'][^>]*>([\s\S]*?)<', chunk, re.I)
            duration = duration_m.group(1).strip() if duration_m else ""

            cards.append({
                "vod_id": full_href,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": format_remarks("📺ZakaTV", duration),
                "style": {"type": "rect", "ratio": 1.78}
            })

        return cards

    def _parse_folders(self, html_text, cat_name):
        cards = []
        if not html_text:
            return cards

        clean_html = html_text
        pos = clean_html.find('id="body"')
        if pos == -1:
            pos = clean_html.find('id="page-list"')
        if pos != -1:
            clean_html = clean_html[pos:]

        footer_pos = clean_html.find("<footer")
        if footer_pos != -1:
            clean_html = clean_html[:footer_pos]

        blacklist = {
            "首页", "更多", "AV", "登入", "注册", "JAV", "观看", "DMCA",
            "最近更新", "新上映", "有码", "无码", "无码流出", "素人", "中国AV",
            "中国直播", "韩国直播", "类型", "制造商", "女优", "系列", "英文字幕"
        }

        links = re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>([\s\S]*?)</a>', clean_html, re.I)
        seen = set()

        is_actor = cat_name in ("女优", "演员")
        card_style = {"type": "oval", "ratio": 1.0} if is_actor else {"type": "rect", "ratio": 1.78}

        for href, inner in links:
            clean_name = re.sub(r'<[^>]+>', '', inner).strip()
            clean_href = href.strip()

            if not clean_name or clean_name.isdigit() or len(clean_name) > 35:
                continue
            if clean_name in blacklist or any(b in clean_name for b in ("在线观看", "版权声明", "用户协议")):
                continue
            if clean_href.startswith("javascript:") or clean_href == "#" or "?page=" in clean_href:
                continue
            if clean_href.rstrip("/").endswith(("/genre", "/make", "/actor", "/series")):
                continue

            full_href = clean_href if clean_href.startswith("http") else urllib.parse.urljoin(self.entryUrl + "/", clean_href)
            if full_href in seen:
                continue
            seen.add(full_href)

            colorful_pic = get_color_dummy_pic(clean_name, is_actor=is_actor)

            cards.append({
                "vod_id": "folder@@" + full_href,
                "vod_name": clean_name,
                "vod_pic": colorful_pic,
                "vod_remarks": "ZakaTV · %s" % cat_name,
                "vod_tag": "folder",
                "style": card_style
            })
        return cards

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg) if str(pg).isdigit() else 1
        raw_tid = str(tid).strip("/")

        target_sub = ""
        if isinstance(extend, dict):
            target_sub = extend.get("sub", "").strip("/")

        is_folder_reentry = raw_tid.startswith("folder@@")

        if is_folder_reentry:
            base_url = raw_tid.replace("folder@@", "")
            if pg > 1:
                req_url = ("%s&page=%d" % (base_url, pg)) if "?" in base_url else ("%s?page=%d" % (base_url, pg))
            else:
                req_url = base_url
        elif raw_tid in ("make", "actor", "series"):
            req_url = "%s/%s/?page=%d" % (self.entryUrl, raw_tid, pg) if pg > 1 else "%s/%s/" % (self.entryUrl, raw_tid)
        else:
            if target_sub and target_sub != raw_tid:
                req_url = "%s/%s/?page=%d" % (self.entryUrl, target_sub, pg) if pg > 1 else "%s/%s/" % (self.entryUrl, target_sub)
            else:
                req_url = "%s/%s/?page=%d" % (self.entryUrl, raw_tid, pg) if pg > 1 else "%s/%s/" % (self.entryUrl, raw_tid)

        res = self._fetch(req_url)
        html_body = res.get("text", "")

        if is_folder_reentry:
            cards = self._parse_cards(html_body)
        elif raw_tid in ("make", "actor", "series"):
            entity_map = {"make": "制造商", "actor": "女优", "series": "系列"}
            cards = self._parse_folders(html_body, entity_map.get(raw_tid, "聚合"))
        else:
            cards = self._parse_cards(html_body)

        return {
            "page": pg,
            "pagecount": (pg + 1) if len(cards) >= 12 else 1,
            "limit": len(cards),
            "total": 9999,
            "list": cards
        }

    def detailContent(self, ids):
        raw_id = ids[0] if isinstance(ids, (list, tuple)) else str(ids)

        if raw_id.startswith("folder@@"):
            return self.categoryContent(raw_id, 1, None, None)

        target_url = raw_id if raw_id.startswith("http") else ("https://www.njav.com/xvideos/" + raw_id.lstrip("/"))
        if not "/zh/" in target_url and self.entryUrl in target_url:
            target_url = target_url.replace(self.siteUrl, self.entryUrl)

        res = self._fetch(target_url)
        html = res.get("text", "")

        vod_name = ""
        data_title_m = re.search(r'data-title=["\']([^"\']+)["\']', html, re.I)
        if data_title_m and data_title_m.group(1).strip():
            vod_name = data_title_m.group(1).strip()

        if not vod_name:
            meta_title_m = re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']+)["\']', html, re.I)
            if meta_title_m and meta_title_m.group(1).strip():
                t = meta_title_m.group(1).strip()
                t = re.sub(r'^\s*nJAV\.com\s*:\s*(?:Watch\s*)?', '', t, flags=re.I)
                t = re.sub(r'\s*JAV\s+Free\s+Online.*$', '', t, flags=re.I).strip()
                if t:
                    vod_name = t

        if not vod_name:
            h1_m = re.search(r'<h1[^>]*>([\s\S]*?)</h1>', html, re.I)
            if h1_m:
                vod_name = re.sub(r'<[^>]+>', '', h1_m.group(1)).strip()

        if not vod_name:
            vod_name = raw_id.rstrip("/").split("/")[-1].upper()

        vod_name = html_lib.unescape(vod_name)

        pic_m = re.search(r'data-poster=["\']([^"\']+)["\']', html, re.I)
        if not pic_m:
            pic_m = re.search(r'data-pic=["\']([^"\']+)["\']', html, re.I)
        if not pic_m:
            pic_m = re.search(r'["\']thumbnailUrl["\']:\s*\[["\']([^"\']+)["\']', html, re.I)
        vod_pic = pic_m.group(1).strip() if pic_m else ""
        if vod_pic.startswith("//"):
            vod_pic = "https:" + vod_pic

        len_m = re.search(r'data-len=["\']([^"\']+)["\']', html, re.I)
        duration = len_m.group(1).strip() if len_m else ""

        slug = target_url.rstrip("/").split("/")[-1]
        vv_url = "https://www.njav.com/vv/%s" % slug

        desc = (
            "【🔥 官方交流群: %s】\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "• 片名: %s\n"
            "• 时长: %s\n"
            "• 播放源: 官方纯净 HLS 直链"
        ) % (self.tgGroup, vod_name, duration if duration else "完整版")

        return {
            "list": [{
                "vod_id": target_url,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_actor": self.brandActor,
                "vod_director": self.brandDirector,
                "vod_remarks": format_remarks("📺ZakaTV", duration),
                "vod_content": desc.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"),
                "vod_play_from": "Zaka专线",
                "vod_play_url": "正片全高清$%s" % vv_url
            }]
        }

    def playerContent(self, flag, id, vipFlags):
        raw_play = str(id).strip()

        if not raw_play.startswith("http"):
            raw_play = "https://www.njav.com/vv/" + raw_play.lstrip("/")

        vv_res = self._fetch(raw_play, referer=self.entryUrl + "/")
        vv_html = vv_res.get("text", "")

        jm_m = re.search(r'videoFrame\.src\s*=\s*["\'](/jm/[^"\']+)["\']', vv_html, re.I)
        if not jm_m:
            jm_m = re.search(r'["\'](/jm/[a-zA-Z0-9+/=]+)["\']', vv_html, re.I)

        if jm_m:
            jm_path = jm_m.group(1).strip()
            jm_url = "https://www.njav.com" + jm_path
            
            headers_iframe = {
                "Sec-Fetch-Dest": "iframe",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "same-origin"
            }
            jm_res = self._fetch(jm_url, referer=raw_play, headers_extra=headers_iframe)
            jm_html = jm_res.get("text", "")

            m3u8_m = re.search(r'PLAYER_CONFIG\s*=\s*\{[\s\S]*?["\']m3u8["\']:\s*["\']([^"\']+)["\']', jm_html, re.I)
            if not m3u8_m:
                m3u8_m = re.search(r'["\']m3u8["\']:\s*["\']([^"\']+)["\']', jm_html, re.I)

            if m3u8_m:
                raw_stream = m3u8_m.group(1).strip()
                clean_m3u8 = raw_stream.replace(r"\/", "/").encode("utf-8").decode("unicode_escape")
                
                final_header = {
                    "User-Agent": self._ua,
                    "Referer": "https://upload18.org/",
                    "Origin": "https://upload18.org"
                }
                return {
                    "parse": 0,
                    "jx": 0,
                    "url": clean_m3u8,
                    "header": json.dumps(final_header)
                }

        return {
            "parse": 1,
            "jx": 0,
            "url": raw_play,
            "header": json.dumps({"User-Agent": self._ua, "Referer": "https://www.njav.com/"})
        }

    def searchContent(self, key, quick, pg="1"):
        pg = int(pg) if str(pg).isdigit() else 1
        search_url = "%s/search?q=%s" % (self.entryUrl, quote(key))
        if pg > 1:
            search_url += "&page=%d" % pg

        res = self._fetch(search_url)
        cards = self._parse_cards(res.get("text", ""))

        return {
            "page": pg,
            "pagecount": (pg + 1) if len(cards) >= 12 else 1,
            "limit": len(cards),
            "total": 9999,
            "list": cards
        }

    def action(self, action):
        return {"msg": "运行正常"}

    def liveContent(self):
        return ""

    def localProxy(self, params):
        return [404, "text/plain; charset=utf-8", "Proxy not active"]

    def destroy(self):
        self.options = {}