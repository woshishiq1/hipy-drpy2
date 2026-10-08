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


class Spider(SpiderBase):
    def __init__(self):
        super(Spider, self).__init__()
        self.domains = ["https://hohoj.tv", "https://hohoj.cc", "https://hohoj.net"]
        self.siteUrl = self.domains[0]
        
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
        
        custom_domain = self.options.get("domain") or self.options.get("siteUrl")
        if custom_domain:
            custom_domain = custom_domain.rstrip("/")
            if custom_domain not in self.domains:
                self.domains.insert(0, custom_domain)
            self.siteUrl = custom_domain
        return True

    def getName(self):
        return "🦋 蝴蝶影视·HoHoJ多域漂移版"

    def isVideoFormat(self, url):
        low = (url or "").lower()
        return any(k in low for k in (".m3u8", ".mp4", ".flv", ".mkv", ".avi", ".ts", ".mpd"))

    def manualVideoCheck(self):
        return False

    def _fetch(self, target_url, referer=""):
        if not target_url:
            return {"code": 0, "text": "", "err": ""}
        
        if target_url.startswith("/"):
            target_url = self.siteUrl + target_url

        path_part = target_url
        for d in self.domains:
            if target_url.startswith(d):
                path_part = target_url[len(d):]
                break

        for index, domain in enumerate(self.domains):
            current_url = domain + path_part if path_part.startswith("/") else target_url
            current_referer = referer if referer else (domain + "/")

            headers = {
                "User-Agent": self._ua,
                "Referer": current_referer,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,ja;q=0.7",
                "Sec-Ch-Ua": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Windows"',
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
                "Connection": "close"
            }

            try:
                req = urllib.request.Request(current_url, headers=headers)
                with self.opener.open(req, timeout=10) as resp:
                    code = resp.getcode()
                    raw = resp.read()
                    if raw.startswith(b"\x1f\x8b"):
                        raw = gzip.decompress(raw)
                    elif getattr(resp, "headers", {}).get("Content-Encoding") == "deflate":
                        try:
                            raw = zlib.decompress(raw)
                        except Exception:
                            raw = zlib.decompress(raw, -zlib.MAX_WBITS)
                    try:
                        text = raw.decode("utf-8")
                    except Exception:
                        text = raw.decode("latin1", errors="ignore")
                    
                    if code == 200 and text:
                        if index > 0:
                            self.domains.insert(0, self.domains.pop(index))
                            self.siteUrl = domain
                        return {"code": code, "text": text, "err": ""}
            except Exception:
                continue

        return {"code": -1, "text": "", "err": "All domains failed"}

    def homeContent(self, filter):
        result = {
            "class": [
                {"type_name": "中文无码", "type_id": "/search?type=uncensored"},
                {"type_name": "中文字幕", "type_id": "/search?type=chinese"},
                {"type_name": "有码流出", "type_id": "/search?type=censored"},
                {"type_name": "欧美无码", "type_id": "/search?type=europe"},
                {"type_name": "日本语", "type_id": "/search?type=japanese"},
                {"type_name": "出轨", "type_id": "/main_ctg?id=7&name=出轨"},
                {"type_name": "走后门", "type_id": "/main_ctg?id=11&name=走後門"},
                {"type_name": "潮吹放尿", "type_id": "/main_ctg?id=10&name=潮吹放尿"},
                {"type_name": "制服诱惑", "type_id": "/main_ctg?id=4&name=制服誘惑"},
                {"type_name": "乱伦", "type_id": "/main_ctg?id=8&name=亂倫"},
                {"type_name": "内射受孕", "type_id": "/main_ctg?id=12&name=內射受孕"},
                {"type_name": "丝袜美腿", "type_id": "/main_ctg?id=1&name=絲襪美腿"},
                {"type_name": "强姦凌辱", "type_id": "/main_ctg?id=2&name=強姦凌辱"},
                {"type_name": "多P群交", "type_id": "/main_ctg?id=5&name=多P群交"},
                {"type_name": "主奴调教", "type_id": "/main_ctg?id=3&name=主奴調教"},
                {"type_name": "角色剧情", "type_id": "/main_ctg?id=6&name=角色劇情"}
            ]
        }
        if filter:
            order_filter = {
                "key": "order", 
                "name": "排序", 
                "init": "latest", 
                "value": [
                    {"n": "最新发布", "v": "latest"}, 
                    {"n": "最多播放", "v": "views"}
                ]
            }
            filters_dict = {}
            for c in result["class"]:
                filters_dict[c["type_id"]] = [order_filter]
            result["filters"] = filters_dict
        return result

    def homeVideoContent(self):
        return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        del filter
        extend = extend if isinstance(extend, dict) else {}
        
        safe_tid = tid
        if any(ord(c) > 127 for c in tid):
            path_part, query_part = tid.split("?", 1) if "?" in tid else (tid, "")
            if query_part:
                q_parsed = urllib.parse.parse_qsl(query_part)
                safe_tid = "%s?%s" % (path_part, urllib.parse.urlencode(q_parsed))

        if "?" in safe_tid:
            target_url = "%s%s&page=%s" % (self.siteUrl, safe_tid, pg)
        else:
            target_url = "%s%s?page=%s" % (self.siteUrl, safe_tid, pg)
            
        order = extend.get("order", "")
        if order:
            target_url += "&order=%s" % order

        res = self._fetch(target_url)
        html_text = res.get("text", "")

        videos = []
        cards = html_text.split('class="video-item')

        for card in cards[1:]:
            href_match = re.search(r'href=["\']([^"\']+)["\']', card, re.I)
            if not href_match:
                continue
            v_id = href_match.group(1)

            title_match = re.search(r'title=["\']([^"\']+)["\']', card, re.I)
            if not title_match:
                title_match = re.search(r'alt=["\']([^"\']+)["\']', card, re.I)
            if not title_match:
                title_match = re.search(r'<(?:h3|a|div)[^>]+class="[^"]*title[^"]*"[^>]*>([\s\S]*?)</(?:h3|a|div)>', card, re.I)
            
            v_name = html_lib.unescape(re.sub(r'<[^>]+>', '', title_match.group(1)).strip()) if title_match else "未知标题"

            pic_match = re.search(r'(?:data-src|src)=["\']([^"\']+\.(?:jpg|png|webp|jpeg|avif)[^"\']*)["\']', card, re.I)
            if not pic_match:
                pic_match = re.search(r'(?:data-src|src)=["\']([^"\']+)["\']', card, re.I)
            
            v_pic = pic_match.group(1) if pic_match else ""
            if v_pic and v_pic.startswith("/"):
                v_pic = self.siteUrl + v_pic

            rem_match = re.search(r'class="[^"]*(?:remarks|duration|hd|label|badge)[^"]*"[^>]*>([\s\S]*?)<\/', card, re.I)
            v_rem = html_lib.unescape(re.sub(r'<[^>]+>', '', rem_match.group(1)).strip()) if rem_match else ""

            if v_id:
                videos.append({
                    "vod_id": v_id,
                    "vod_name": v_name,
                    "vod_pic": v_pic,
                    "vod_remarks": v_rem,
                    "style": {"type": "rect", "ratio": 0.75}
                })

        return {
            "page": int(pg),
            "pagecount": 999 if videos else int(pg),
            "limit": len(videos),
            "total": 999 if videos else 0,
            "list": videos
        }

    def detailContent(self, ids):
        raw_id = ids[0] if isinstance(ids, (list, tuple)) else str(ids)
        target_url = self.siteUrl + raw_id if raw_id.startswith("/") else raw_id
        
        res = self._fetch(target_url)
        html_text = res.get("text", "")

        title_match = re.search(r'<h1[^>]*>([\s\S]*?)</h1>', html_text, re.I)
        if not title_match:
            title_match = re.search(r'<title>(.*?)</title>', html_text, re.I)
        vod_name = html_lib.unescape(re.sub(r'<[^>]+>', '', title_match.group(1)).strip()) if title_match else "未知视频"

        pic_match = re.search(r'(?:property="og:image"|data-src|src)=["\']([^"\']+\.(?:jpg|png|webp|jpeg|avif)[^"\']*)["\']', html_text, re.I)
        vod_pic = pic_match.group(1) if pic_match else ""
        if vod_pic and vod_pic.startswith("/"):
            vod_pic = self.siteUrl + vod_pic

        vid_match = re.search(r'id=(\d+)', raw_id)
        embed_url = "%s/embed?id=%s" % (self.siteUrl, vid_match.group(1)) if vid_match else target_url
        
        embed_res = self._fetch(embed_url, referer=target_url)
        embed_text = embed_res.get("text", "")

        m3u8_match = re.search(r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', embed_text, re.I)
        if not m3u8_match:
            m3u8_match = re.search(r'src=["\'](https?://[^"\']+\.mp4[^"\']*)["\']', embed_text, re.I)
        if not m3u8_match:
            m3u8_match = re.search(r'([^"\']+\.m3u8[^"\']*)', embed_text, re.I)

        real_play_url = m3u8_match.group(1) if m3u8_match else embed_url
        if real_play_url.startswith("/"):
            real_play_url = self.siteUrl + real_play_url

        full_desc = (
            "【🔥 官方交流群: %s】\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "• 本资源由 蝴蝶影视 独家提供解析，支持全网高清流畅播放。\n"
            "• 欢迎加入 TG 交流群获取更多优质资源与最新电视盒子应用！"
        ) % self.tgGroup

        return {
            "list": [{
                "vod_id": raw_id,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_actor": self.brandActor,
                "vod_director": self.brandDirector,
                "vod_remarks": "高清正片",
                "vod_content": full_desc,
                "vod_play_from": "蝴蝶影视",
                "vod_play_url": "正片播放$%s" % real_play_url
            }]
        }

    def playerContent(self, flag, id, vipFlags):
        return {
            "parse": 0,
            "jx": 0,
            "url": str(id).strip(),
            "header": {"User-Agent": self._ua, "Referer": self.siteUrl + "/"}
        }

    def searchContent(self, key, quick, pg="1"):
        del quick
        target_url = "%s/search?keyword=%s&page=%s" % (self.siteUrl, urllib.parse.quote(key), pg)
        res = self._fetch(target_url)
        html_text = res.get("text", "")

        videos = []
        cards = html_text.split('class="video-item')

        for card in cards[1:]:
            href_match = re.search(r'href=["\']([^"\']+)["\']', card, re.I)
            if not href_match:
                continue
            v_id = href_match.group(1)

            title_match = re.search(r'title=["\']([^"\']+)["\']', card, re.I)
            if not title_match:
                title_match = re.search(r'alt=["\']([^"\']+)["\']', card, re.I)
            if not title_match:
                title_match = re.search(r'<(?:h3|a|div)[^>]+class="[^"]*title[^"]*"[^>]*>([\s\S]*?)</(?:h3|a|div)>', card, re.I)
            
            v_name = html_lib.unescape(re.sub(r'<[^>]+>', '', title_match.group(1)).strip()) if title_match else "未知标题"

            pic_match = re.search(r'(?:data-src|src)=["\']([^"\']+\.(?:jpg|png|webp|jpeg|avif)[^"\']*)["\']', card, re.I)
            if not pic_match:
                pic_match = re.search(r'(?:data-src|src)=["\']([^"\']+)["\']', card, re.I)
            
            v_pic = pic_match.group(1) if pic_match else ""
            if v_pic and v_pic.startswith("/"):
                v_pic = self.siteUrl + v_pic

            rem_match = re.search(r'class="[^"]*(?:remarks|duration|hd|label|badge)[^"]*"[^>]*>([\s\S]*?)<\/', card, re.I)
            v_rem = html_lib.unescape(re.sub(r'<[^>]+>', '', rem_match.group(1)).strip()) if rem_match else ""

            if v_id:
                videos.append({
                    "vod_id": v_id,
                    "vod_name": v_name,
                    "vod_pic": v_pic,
                    "vod_remarks": v_rem,
                    "style": {"type": "rect", "ratio": 0.75}
                })

        return {
            "page": int(pg),
            "pagecount": 999 if videos else int(pg),
            "limit": len(videos),
            "total": 999 if videos else 0,
            "list": videos
        }

    def action(self, action):
        return {"msg": "ok"}

    def destroy(self):
        self.options = {}