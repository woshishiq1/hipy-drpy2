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
        def setCache(self, key, value): "fail"
        def delCache(self, key): "fail"


class Spider(SpiderBase):
    def __init__(self):
        super(Spider, self).__init__()
        # 发布导航站双活入口与默认兜底主站
        self.navUrls = ["https://x99dh.cc", "https://x99dh.one"]
        self.defaultHost = "https://rou666.cc"
        self.siteUrl = self.defaultHost
        self.siteName = "rouAV"
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

        # 启动优先从本地持久化缓存读取最新解析到的有效主站
        cached_site = self.getCache("rouav_dynamic_site_url")
        if cached_site and cached_site.startswith("http"):
            self.siteUrl = cached_site.strip().rstrip("/")
        else:
            self._refresh_site_url()
        return True

    def getName(self):
        return "肉视频·动态发布自愈版"

    def isVideoFormat(self, url):
        low = (url or "").lower()
        return any(k in low for k in (".m3u8", ".mp4", ".flv", ".mkv", ".avi", ".ts", ".mpd", "index.png"))

    def manualVideoCheck(self):
        return False

    # 核心：复用 X99 导航站 Base64+URL二次反解与矩阵探测引擎，精准提取 rouAV
    def _refresh_site_url(self):
        headers = {
            "User-Agent": self._ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate"
        }

        for nav in self.navUrls:
            text = ""
            try:
                req = urllib.request.Request(nav, headers=headers)
                with self.opener.open(req, timeout=8) as resp:
                    raw = resp.read()
                    enc = getattr(resp, "headers", {}).get("Content-Encoding", "")
                    if raw.startswith(b"\x1f\x8b") or enc == "gzip":
                        raw = gzip.decompress(raw)
                    text = raw.decode("utf-8", errors="ignore")
            except urllib.error.HTTPError as e:
                try:
                    raw = e.read()
                    if raw.startswith(b"\x1f\x8b"):
                        raw = gzip.decompress(raw)
                    text = raw.decode("utf-8", errors="ignore")
                except Exception:
                    text = ""
            except Exception:
                continue

            if not text:
                continue

            # 扫描并反解页面内嵌入的长 Base64 数据块
            b64_blocks = re.findall(r'["\']([A-Za-z0-9+/=]{100,})["\']', text)
            for b in b64_blocks:
                try:
                    decoded = base64.b64decode(b).decode("utf-8", errors="ignore")
                    unquoted = urllib.parse.unquote(decoded)
                    if "[" in unquoted and self.siteName.lower() in unquoted.lower():
                        site_list = json.loads(unquoted)
                        for item in site_list:
                            name = item.get("name", "").strip().lower()
                            if name == self.siteName.lower():
                                cand_urls = []
                                main_url = item.get("url", "")
                                if main_url:
                                    cand_urls.append(main_url)
                                for u_obj in item.get("urls", []):
                                    u = u_obj.get("url", "")
                                    if u and u not in cand_urls:
                                        cand_urls.append(u)

                                # 提取根域名并发送轻量验活
                                for c_url in cand_urls:
                                    parsed = urllib.parse.urlparse(c_url)
                                    base = "%s://%s" % (parsed.scheme, parsed.netloc)
                                    chk = self._fetch(base + "/v", check_host=False)
                                    if chk.get("code") == 200:
                                        self.siteUrl = base
                                        self.setCache("rouav_dynamic_site_url", base)
                                        return True
                except Exception:
                    continue

        return False

    def _fetch(self, target_url, referer="", check_host=True):
        if not target_url:
            return {"code": 0, "text": "", "err": "", "final_url": ""}
        if target_url.startswith("//"):
            target_url = "https:" + target_url
        elif target_url.startswith("/"):
            target_url = self.siteUrl + target_url

        headers = {
            "User-Agent": self._ua,
            "Referer": referer if referer else (self.siteUrl + "/v"),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive"
        }

        last_err = ""
        domain_retried = False

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
                    return {"code": code, "text": text, "err": "", "final_url": final_url}
            except urllib.error.HTTPError as e:
                last_err = "HTTP %s" % e.code
                if e.code in (404, 451, 502, 503) and check_host and not domain_retried:
                    old_host = urllib.parse.urlparse(self.siteUrl).netloc
                    self.delCache("rouav_dynamic_site_url")
                    if self._refresh_site_url():
                        domain_retried = True
                        new_host = urllib.parse.urlparse(self.siteUrl).netloc
                        target_url = target_url.replace(old_host, new_host)
                        continue
                if e.code in (451, 403, 429) and attempt == 0:
                    continue
                err_raw = ""
                try:
                    err_raw = e.read().decode("utf-8", errors="ignore")
                except Exception:
                    pass
                return {"code": e.code, "text": err_raw, "err": str(e), "final_url": target_url}
            except Exception as e:
                last_err = str(e)
                if check_host and not domain_retried:
                    old_host = urllib.parse.urlparse(self.siteUrl).netloc
                    self.delCache("rouav_dynamic_site_url")
                    if self._refresh_site_url():
                        domain_retried = True
                        new_host = urllib.parse.urlparse(self.siteUrl).netloc
                        target_url = target_url.replace(old_host, new_host)
                        continue
                if attempt == 0:
                    continue
                return {"code": -1, "text": "", "err": str(e), "final_url": target_url}

        return {"code": -1, "text": "", "err": last_err, "final_url": target_url}

    def homeContent(self, filter):
        result = {
            "class": [
                {"type_name": "🔥 最新发布", "type_id": "/v?order=createdAt"},
                {"type_name": "👑 最多播放", "type_id": "/v?order=viewCount"},
                {"type_name": "❤️ 最受喜爱", "type_id": "/v?order=likeCount"},
                {"type_name": "🤖 AI成人短剧", "type_id": "/t/AI短劇"},
                {"type_name": "📱 自拍流出", "type_id": "/t/自拍流出"},
                {"type_name": "🕵️ 探花精选", "type_id": "/t/探花"},
                {"type_name": "🇨🇳 国产AV", "type_id": "/t/國產AV"},
                {"type_name": "🇯🇵 日本精选", "type_id": "/t/日本"},
                {"type_name": "🀄 中文字幕", "type_id": "/t/中文字幕"},
                {"type_name": "麻豆传媒", "type_id": "/t/麻豆傳媒"},
                {"type_name": "糖心Vlog", "type_id": "/t/糖心Vlog"},
                {"type_name": "蜜桃传媒", "type_id": "/t/蜜桃影像傳媒"},
                {"type_name": "香蕉视频", "type_id": "/t/香蕉視頻傳媒"},
                {"type_name": "星空无限", "type_id": "/t/星空無限傳媒"},
                {"type_name": "天美传媒", "type_id": "/t/天美傳媒"},
                {"type_name": "OnlyFans", "type_id": "/t/OnlyFans"},
                {"type_name": "巨乳", "type_id": "/t/巨乳"},
                {"type_name": "人妻", "type_id": "/t/人妻"},
                {"type_name": "丝袜", "type_id": "/t/絲襪"},
                {"type_name": "熟女", "type_id": "/t/熟女"},
                {"type_name": "美少女", "type_id": "/t/美少女"},
                {"type_name": "中出", "type_id": "/t/中出"},
                {"type_name": "口交", "type_id": "/t/口交"},
                {"type_name": "痴女", "type_id": "/t/痴女"},
                {"type_name": "多人运动", "type_id": "/t/多人運動"},
                {"type_name": "NTR", "type_id": "/t/NTR"}
            ]
        }
        if filter:
            result["filters"] = {}
        return result

    def homeVideoContent(self):
        return {"list": []}

    def _parse_vod_list(self, html_text):
        m_next = re.search(r'<script\s+id=["\']__NEXT_DATA__["\'][^>]*>([\s\S]*?)</script>', html_text, re.I)
        if m_next:
            try:
                data_obj = json.loads(m_next.group(1).strip())
                video_list = data_obj.get("props", {}).get("pageProps", {}).get("videos", [])
                if isinstance(video_list, list) and len(video_list) > 0:
                    cards = []
                    for v in video_list:
                        vid = v.get("id") or ""
                        if not vid:
                            continue
                        name = v.get("nameZh") or v.get("name") or "肉视频"
                        pic = v.get("coverImageUrl") or ""
                        dur_sec = v.get("duration") or 0
                        dur_str = "HD"
                        if dur_sec:
                            try:
                                m, s = divmod(int(dur_sec), 60)
                                h, m = divmod(m, 60)
                                dur_str = "%d:%02d:%02d" % (h, m, s) if h else "%02d:%02d" % (m, s)
                            except Exception:
                                pass

                        payload = {"vid": str(vid).strip(), "title": html_lib.unescape(name)}
                        b64_info = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")

                        cards.append({
                            "vod_id": "pkg_" + b64_info,
                            "vod_name": html_lib.unescape(name),
                            "vod_pic": pic,
                            "vod_remarks": dur_str,
                            "style": {"type": "rect", "ratio": 1.78}
                        })
                    if cards:
                        return cards
            except Exception:
                pass

        card_matches = re.findall(r'<a[^>]+href=["\'](/v/[a-z0-9]+)["\'][^>]*>([\s\S]*?)</a>', html_text, re.I)
        cards = []
        seen = set()
        for href, block in card_matches:
            if href in seen:
                continue
            seen.add(href)

            img_src = ""
            for pat in [r'data-src=["\']([^"\']+)["\']', r'data-original=["\']([^"\']+)["\']', r'src=["\']([^"\']+)["\']']:
                m = re.search(pat, block, re.I)
                if m and not m.group(1).endswith(".svg") and "data:image" not in m.group(1):
                    img_src = m.group(1).strip()
                    break

            title_m = re.search(r'(?:title|alt)=["\']([^"\']+)["\']', block, re.I)
            title = title_m.group(1).strip() if title_m else ""
            if not title:
                clean_text = re.sub(r'<[^>]+>', '', block).strip()
                title = clean_text.split("\n")[0].strip() if clean_text else "肉视频"

            dur_m = re.search(r'(\d{1,2}:\d{2}(?::\d{2})?)', block)
            dur = dur_m.group(1) if dur_m else "HD"

            if img_src.startswith("//"):
                img_src = "https:" + img_src
            elif img_src.startswith("/"):
                img_src = self.siteUrl + img_src

            vid = href.replace("/v/", "").strip("/")
            payload = {"vid": vid, "title": html_lib.unescape(title)}
            b64_info = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")

            cards.append({
                "vod_id": "pkg_" + b64_info,
                "vod_name": html_lib.unescape(title),
                "vod_pic": img_src,
                "vod_remarks": dur,
                "style": {"type": "rect", "ratio": 0.75}
            })
        return cards

    def categoryContent(self, tid, pg, filter, extend):
        del filter
        extend = extend if isinstance(extend, dict) else {}
        page_num = int(pg) if str(pg).isdigit() else 1

        path = str(tid).strip()
        sep = "&" if "?" in path else "?"
        raw_url = "%s%spage=%d" % (path, sep, page_num)
        req_url = urllib.parse.quote(raw_url, safe="/?=&:%")

        res = self._fetch(req_url)
        cards = self._parse_vod_list(res.get("text", ""))

        return {
            "page": page_num,
            "pagecount": page_num + 1 if len(cards) >= 12 else page_num,
            "limit": len(cards),
            "total": 9999,
            "list": cards
        }

    def detailContent(self, ids):
        raw_id = ids[0] if isinstance(ids, (list, tuple)) else str(ids)
        vid = ""
        cached_title = ""

        if str(raw_id).startswith("pkg_"):
            try:
                b64_str = raw_id[4:]
                pad = len(b64_str) % 4
                if pad:
                    b64_str += "=" * (4 - pad)
                pkg = json.loads(base64.urlsafe_b64decode(b64_str.encode("utf-8")).decode("utf-8"))
                vid = pkg.get("vid", "")
                cached_title = pkg.get("title", "")
            except Exception:
                vid = str(raw_id).strip()
        else:
            vid = str(raw_id).strip()

        target_path = "/v/%s" % vid
        res = self._fetch(target_path)
        html_text = res.get("text", "")

        vod_name = cached_title
        vod_pic = ""
        tag_str = ""
        desc = "暂无简介"

        m_next = re.search(r'<script\s+id=["\']__NEXT_DATA__["\'][^>]*>([\s\S]*?)</script>', html_text, re.I)
        if m_next:
            try:
                data_obj = json.loads(m_next.group(1).strip())
                video_obj = data_obj.get("props", {}).get("pageProps", {}).get("video", {})
                if video_obj:
                    if not vod_name:
                        vod_name = video_obj.get("nameZh") or video_obj.get("name") or "肉视频"
                    vod_pic = video_obj.get("coverImageUrl") or ""
                    tags = video_obj.get("tagsZh") or video_obj.get("tags") or []
                    tag_str = ", ".join(tags) if tags else ""
                    desc = video_obj.get("description") or desc
            except Exception:
                pass

        if not vod_name:
            vod_name = "肉视频"

        if not vod_pic:
            cover_m = re.search(r'property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html_text, re.I)
            if cover_m:
                vod_pic = cover_m.group(1).strip()

        full_desc = (
            "【🔥 官方交流群: %s】\n"
            "【当前发布域名: %s】\n"
            "【标签】: %s\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "%s"
        ) % (self.tgGroup, self.siteUrl, tag_str if tag_str else "精选", desc)

        escaped_desc = full_desc.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        play_api_url = self.siteUrl + "/api/hls/" + vid

        return {
            "list": [{
                "vod_id": raw_id,
                "vod_name": html_lib.unescape(vod_name),
                "vod_pic": vod_pic,
                "vod_actor": self.brandActor,
                "vod_director": self.brandDirector,
                "vod_remarks": "HD正片",
                "vod_content": escaped_desc,
                "vod_play_from": "肉视频极速专线",
                "vod_play_url": "正片完整版$%s" % play_api_url
            }]
        }

    def playerContent(self, flag, id, vipFlags):
        play_url = str(id).strip()

        if "/api/hls/" in play_url:
            try:
                headers = {
                    "User-Agent": self._ua,
                    "Referer": self.siteUrl + "/v",
                    "Accept": "*/*",
                    "Connection": "keep-alive"
                }
                req = urllib.request.Request(play_url, headers=headers)
                with self.opener.open(req, timeout=8) as resp:
                    final_stream = resp.geturl()
                    if final_stream and "index.png" in final_stream:
                        play_url = final_stream
            except Exception:
                pass

        return {
            "parse": 0,
            "jx": 0,
            "url": play_url,
            "header": {
                "User-Agent": self._ua,
                "Referer": self.siteUrl + "/",
                "Origin": self.siteUrl,
                "Connection": "keep-alive"
            },
            "position": 1
        }

    def searchContent(self, key, quick, pg="1"):
        if not key:
            return {"page": 1, "pagecount": 1, "limit": 0, "total": 0, "list": []}

        page_num = int(pg) if str(pg).isdigit() else 1
        encoded_key = urllib.parse.quote(str(key).strip())

        search_url = "/search?q=%s&page=%d" % (encoded_key, page_num)
        res = self._fetch(search_url)
        cards = self._parse_vod_list(res.get("text", ""))

        return {
            "page": page_num,
            "pagecount": page_num + 1 if len(cards) >= 12 else page_num,
            "limit": len(cards),
            "total": 9999,
            "list": cards
        }

    def action(self, action):
        if action == "toast":
            return {"msg": "当前有效主站: %s" % self.siteUrl}
        return {"msg": "ok"}

    def liveContent(self):
        return ""

    def localProxy(self, params):
        return [404, "text/plain; charset=utf-8", "Proxy not configured"]

    def destroy(self):
        self.options = {}
