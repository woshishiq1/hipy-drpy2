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
        self.defaultHost = "https://madou8.pw"
        self.siteUrl = self.defaultHost
        self.siteName = "LissAV国产区"
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
        cached_site = self.getCache("lissav_cn_dynamic_site_url")
        if cached_site and cached_site.startswith("http"):
            self.siteUrl = cached_site.strip().rstrip("/")
        else:
            self._refresh_site_url()
        return True

    def getName(self):
        return "LissAV国产区·动态发布自愈版"

    def isVideoFormat(self, url):
        low = (url or "").lower()
        return any(k in low for k in (".m3u8", ".mp4", ".flv", ".mkv", ".avi", ".ts", ".mpd"))

    def manualVideoCheck(self):
        return False

    # 核心：复用 X99 导航站 Base64+URL二次反解与矩阵探测引擎
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
                    if "[" in unquoted and self.siteName in unquoted:
                        site_list = json.loads(unquoted)
                        for item in site_list:
                            if item.get("name", "").strip() == self.siteName:
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
                                    chk = self._fetch(base + "/asian/zh-CN", check_host=False)
                                    if chk.get("code") == 200:
                                        self.siteUrl = base
                                        self.setCache("lissav_cn_dynamic_site_url", base)
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
            "Referer": referer if referer else (self.siteUrl + "/asian/zh-CN"),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
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
                    self.delCache("lissav_cn_dynamic_site_url")
                    if self._refresh_site_url():
                        domain_retried = True
                        new_host = urllib.parse.urlparse(self.siteUrl).netloc
                        target_url = target_url.replace(old_host, new_host)
                        continue
                if e.code in (451, 403, 429) and attempt == 0:
                    continue
                return {"code": e.code, "text": "", "err": str(e), "final_url": target_url}
            except Exception as e:
                last_err = str(e)
                if check_host and not domain_retried:
                    old_host = urllib.parse.urlparse(self.siteUrl).netloc
                    self.delCache("lissav_cn_dynamic_site_url")
                    if self._refresh_site_url():
                        domain_retried = True
                        new_host = urllib.parse.urlparse(self.siteUrl).netloc
                        target_url = target_url.replace(old_host, new_host)
                        continue
                if attempt == 0:
                    continue
                return {"code": -1, "text": "", "err": str(e), "final_url": target_url}

        return {"code": -1, "text": "", "err": last_err, "final_url": target_url}

    def _fetch_json(self, target_url, referer=""):
        if not target_url:
            return {}
        if target_url.startswith("//"):
            target_url = "https:" + target_url
        elif target_url.startswith("/"):
            target_url = self.siteUrl + target_url

        headers = {
            "User-Agent": self._ua,
            "Referer": referer if referer else (self.siteUrl + "/asian/zh-CN"),
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "X-Requested-With": "XMLHttpRequest",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive"
        }

        try:
            req = urllib.request.Request(target_url, headers=headers)
            with self.opener.open(req, timeout=12) as resp:
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
                return json.loads(text)
        except Exception:
            return {}

    def homeContent(self, filter):
        result = {
            "class": [
                {"type_name": "🤖 AI成人短剧", "type_id": "domestic/zh-CN/videos/genre/AI成人短剧"},
                {"type_name": "🕵️ 探花系列", "type_id": "domestic/zh-CN/videos/genre/探花"},
                {"type_name": "📱 自拍流出", "type_id": "domestic/zh-CN/videos/genre/自拍"},
                {"type_name": "🇨🇳 国产AV", "type_id": "domestic/zh-CN/videos/genre/国产"},
                {"type_name": "🇯🇵 日本精选", "type_id": "asian/zh-CN/videos/genre/日本"},
                {"type_name": "🔥 最近更新", "type_id": "asian/zh-CN/videos/recent"},
                {"type_name": "✨ 新作上市", "type_id": "asian/zh-CN/videos/new-releases"},
                {"type_name": "📅 今日热门", "type_id": "asian/zh-CN/videos/hot/today"},
                {"type_name": "🏆 本周热门", "type_id": "asian/zh-CN/videos/hot/week"},
                {"type_name": "👑 本月热门", "type_id": "asian/zh-CN/videos/hot/month"},
                {"type_name": "🀄 中文字幕", "type_id": "asian/zh-CN/videos/tag/中文字幕"},
                {"type_name": "💧 无码流出", "type_id": "asian/zh-CN/videos/tag/无码流出"},
                {"type_name": "💎 4K专区", "type_id": "asian/zh-CN/videos/genre/4K"},
                {"type_name": "独家", "type_id": "asian/zh-CN/videos/genre/独家"},
                {"type_name": "高清", "type_id": "asian/zh-CN/videos/genre/高清"},
                {"type_name": "素人", "type_id": "asian/zh-CN/videos/genre/素人"},
                {"type_name": "人妻", "type_id": "asian/zh-CN/videos/genre/人妻"},
                {"type_name": "熟女", "type_id": "asian/zh-CN/videos/genre/熟女"},
                {"type_name": "巨乳", "type_id": "asian/zh-CN/videos/genre/巨乳"},
                {"type_name": "美少女", "type_id": "asian/zh-CN/videos/genre/美少女"},
                {"type_name": "中出", "type_id": "asian/zh-CN/videos/genre/中出"},
                {"type_name": "剧情", "type_id": "asian/zh-CN/videos/genre/剧情"},
                {"type_name": "痴女", "type_id": "asian/zh-CN/videos/genre/痴女"},
                {"type_name": "多人运动", "type_id": "asian/zh-CN/videos/genre/多人运动"},
                {"type_name": "骑乘", "type_id": "asian/zh-CN/videos/genre/骑乘"},
                {"type_name": "苗条", "type_id": "asian/zh-CN/videos/genre/苗条"},
                {"type_name": "潮吹", "type_id": "asian/zh-CN/videos/genre/潮吹"},
                {"type_name": "NTR", "type_id": "asian/zh-CN/videos/genre/NTR"},
                {"type_name": "美乳", "type_id": "asian/zh-CN/videos/genre/美乳"},
                {"type_name": "颜射", "type_id": "asian/zh-CN/videos/genre/颜射"},
                {"type_name": "企划", "type_id": "asian/zh-CN/videos/genre/企划"},
                {"type_name": "乱伦", "type_id": "asian/zh-CN/videos/genre/乱伦"},
                {"type_name": "搭讪", "type_id": "asian/zh-CN/videos/genre/搭讪"},
                {"type_name": "合集", "type_id": "asian/zh-CN/videos/genre/合集"},
                {"type_name": "偷拍", "type_id": "asian/zh-CN/videos/genre/偷拍"},
                {"type_name": "制服", "type_id": "asian/zh-CN/videos/genre/制服"},
                {"type_name": "女大学生", "type_id": "asian/zh-CN/videos/genre/女大学生"},
                {"type_name": "自慰", "type_id": "asian/zh-CN/videos/genre/自慰"},
                {"type_name": "辣妹", "type_id": "asian/zh-CN/videos/genre/辣妹"},
                {"type_name": "拘束", "type_id": "asian/zh-CN/videos/genre/拘束"},
                {"type_name": "丝袜", "type_id": "asian/zh-CN/videos/genre/丝袜"},
                {"type_name": "按摩", "type_id": "asian/zh-CN/videos/genre/按摩"},
                {"type_name": "女教师", "type_id": "asian/zh-CN/videos/genre/女教师"},
                {"type_name": "S1风格", "type_id": "asian/zh-CN/videos/genre/S1%20NO.1%20STYLE"},
                {"type_name": "Madonna", "type_id": "asian/zh-CN/videos/genre/Madonna"}
            ]
        }
        if filter:
            result["filters"] = {}
        return result

    def homeVideoContent(self):
        return {"list": []}

    def _parse_vod_list(self, html_text):
        vod_matches = re.findall(r'<a[^>]+href=["\']([^"\']*/(?:video|watch|v)/[^"\']*)["\'][^>]*>([\s\S]*?)</a>', html_text, re.I)
        if not vod_matches:
            vod_matches = re.findall(r'<a[^>]+href=["\']([^"\']*/videos/[^"\']+)["\'][^>]*>([\s\S]*?)</a>', html_text, re.I)

        cards = []
        seen = set()
        for href, block in vod_matches:
            if any(x in href for x in ("recent", "new-releases", "hot", "tag", "actors", "genres", "page", "search")):
                continue
            if href in seen:
                continue
            seen.add(href)

            img_src = ""
            for pat in [r'data-original=["\']([^"\']+)["\']', r'data-src=["\']([^"\']+)["\']', r'data-thumb=["\']([^"\']+)["\']', r'src=["\']([^"\']+)["\']']:
                m = re.search(pat, block, re.I)
                if m and not m.group(1).endswith(".svg") and "data:image" not in m.group(1):
                    img_src = m.group(1).strip()
                    break

            title_m = re.search(r'title=["\']([^"\']+)["\']', block, re.I)
            if not title_m:
                title_m = re.search(r'alt=["\']([^"\']+)["\']', block, re.I)
            title = title_m.group(1).strip() if title_m else ""
            if not title:
                clean_inner = re.sub(r'<[^>]+>', '', block).strip()
                title = clean_inner.split("\n")[0].strip() if clean_inner else "麻豆精选"

            dur_m = re.search(r'(\d{1,2}:\d{2}(?::\d{2})?)', block)
            dur = dur_m.group(1) if dur_m else ""

            if img_src.startswith("//"):
                img_src = "https:" + img_src
            elif img_src.startswith("/"):
                img_src = self.siteUrl + img_src

            payload = {"url": href, "title": html_lib.unescape(title)}
            b64_info = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")

            cards.append({
                "vod_id": "pkg_" + b64_info,
                "vod_name": html_lib.unescape(title),
                "vod_pic": img_src,
                "vod_remarks": dur if dur else "正片HD",
                "style": {"type": "rect", "ratio": 1.78}
            })
        return cards

    def categoryContent(self, tid, pg, filter, extend):
        del filter
        extend = extend if isinstance(extend, dict) else {}
        page_num = int(pg) if str(pg).isdigit() else 1

        path = str(tid).strip("/")
        if not (path.startswith("asian/") or path.startswith("domestic/")):
            path = "asian/zh-CN/" + path

        encoded_path = urllib.parse.quote(urllib.parse.unquote(path), safe="/:%")
        req_url = "/%s/page/%d" % (encoded_path, page_num) if page_num > 1 else ("/%s" % encoded_path)

        res = self._fetch(req_url)
        html_text = res.get("text", "")
        cards = self._parse_vod_list(html_text)

        return {
            "page": page_num,
            "pagecount": page_num + 1 if len(cards) >= 10 else page_num,
            "limit": len(cards),
            "total": 9999,
            "list": cards
        }

    def detailContent(self, ids):
        raw_id = ids[0] if isinstance(ids, (list, tuple)) else str(ids)
        target_path = ""
        cached_title = ""

        if str(raw_id).startswith("pkg_"):
            try:
                b64_str = raw_id[4:]
                pad = len(b64_str) % 4
                if pad:
                    b64_str += "=" * (4 - pad)
                pkg = json.loads(base64.urlsafe_b64decode(b64_str.encode("utf-8")).decode("utf-8"))
                target_path = pkg.get("url", "")
                cached_title = pkg.get("title", "")
            except Exception:
                target_path = raw_id
        elif str(raw_id).startswith("vod_"):
            try:
                b64_str = raw_id[4:]
                pad = len(b64_str) % 4
                if pad:
                    b64_str += "=" * (4 - pad)
                target_path = base64.urlsafe_b64decode(b64_str.encode("utf-8")).decode("utf-8")
            except Exception:
                target_path = raw_id
        else:
            target_path = raw_id

        res = self._fetch(target_path)
        html_text = res.get("text", "")

        vod_name = cached_title
        if not vod_name:
            title_m = re.search(r'<h1[^>]*>([\s\S]*?)</h1>', html_text, re.I)
            if title_m:
                vod_name = re.sub(r'<[^>]+>', '', title_m.group(1)).strip()
        if not vod_name:
            m_og = re.search(r'property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']', html_text, re.I)
            if m_og:
                vod_name = m_og.group(1).strip()
        if not vod_name:
            m_meta_title = re.search(r'<title>(.*?)</title>', html_text, re.I)
            if m_meta_title:
                clean_title = m_meta_title.group(1).split("-")[0].split("_")[0].strip()
                if clean_title:
                    vod_name = clean_title
        if not vod_name:
            vod_name = "麻豆精选视频"

        cover_m = re.search(r'<video[^>]+poster=["\']([^"\']+)["\']', html_text, re.I)
        if not cover_m:
            cover_m = re.search(r'property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html_text, re.I)
        vod_pic = cover_m.group(1).strip() if cover_m else ""
        if vod_pic.startswith("//"):
            vod_pic = "https:" + vod_pic
        elif vod_pic.startswith("/"):
            vod_pic = self.siteUrl + vod_pic

        actor_matches = re.findall(r'<a[^>]+href=["\'](?:[^"\']*/actors/[^"\']*)["\'][^>]*>([\s\S]*?)</a>', html_text, re.I)
        actors = [re.sub(r'<[^>]+>', '', a).strip() for a in actor_matches if re.sub(r'<[^>]+>', '', a).strip()]
        actor_str = ", ".join(actors) if actors else self.brandActor

        desc_m = re.search(r'class=["\'][^"\']*movie-description[^"\']*["\']>([\s\S]*?)</div>', html_text, re.I)
        raw_desc = re.sub(r'<[^>]+>', '', desc_m.group(1)).strip() if desc_m else "暂无简介"

        m_api = re.search(r'var\s+streamApi\s*=\s*["\']([^"\']+)["\']', html_text)
        stream_endpoint = m_api.group(1) if m_api else "/asian/zh-CN/api/video/stream"

        m_uid = re.search(r'var\s+videoUid\s*=\s*["\']([^"\']+)["\']', html_text)
        video_uid = m_uid.group(1) if m_uid else ""

        real_m3u8 = ""
        if video_uid:
            sep = "&" if "?" in stream_endpoint else "?"
            api_url = "%s%svideo_uid=%s" % (stream_endpoint, sep, video_uid)
            stream_data = self._fetch_json(api_url, referer=self.siteUrl + target_path)

            playlist = stream_data.get("playlist", [])
            if isinstance(playlist, list) and len(playlist) > 0:
                first_item = playlist[0]
                if isinstance(first_item, dict):
                    real_m3u8 = first_item.get("url", "")
            if not real_m3u8:
                m3u8_matches = re.findall(r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*', json.dumps(stream_data))
                if m3u8_matches:
                    real_m3u8 = m3u8_matches[0]

        play_lines = []
        if real_m3u8:
            play_lines.append("正片完整版$%s" % real_m3u8)
        else:
            script_videos = re.findall(r'["\'](https?:\\?/\\?/[^"\']+\.(?:m3u8|mp4)[^"\']*)["\']', html_text, re.I)
            for idx, sv in enumerate(script_videos, 1):
                clean_url = sv.replace(r"\/", "/")
                play_lines.append("备用线路%d$%s" % (idx, clean_url))

        if not play_lines:
            play_lines.append("暂无有效线路$http://127.0.0.1")

        full_content = (
            "【🔥 官方交流群: %s】\n"
            "【当前发布域名: %s】\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "%s"
        ) % (self.tgGroup, self.siteUrl, raw_desc)
        escaped_desc = full_content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        return {
            "list": [{
                "vod_id": raw_id,
                "vod_name": html_lib.unescape(vod_name),
                "vod_pic": vod_pic,
                "vod_actor": actor_str,
                "vod_director": self.brandDirector,
                "vod_remarks": "HD正片",
                "vod_content": escaped_desc,
                "vod_play_from": "麻豆正片专线",
                "vod_play_url": "#".join(play_lines)
            }]
        }

    def playerContent(self, flag, id, vipFlags):
        target_play_url = str(id).strip()
        return {
            "parse": 0,
            "jx": 0,
            "url": target_play_url,
            "header": {
                "User-Agent": self._ua,
                "Referer": self.siteUrl + "/",
                "Origin": self.siteUrl
            },
            "position": 1
        }

    def searchContent(self, key, quick, pg="1"):
        if not key:
            return {"page": 1, "pagecount": 1, "limit": 0, "total": 0, "list": []}

        page_num = int(pg) if str(pg).isdigit() else 1
        encoded_key = urllib.parse.quote(str(key).strip())

        if page_num > 1:
            search_url = "/asian/zh-CN/videos/search/%s/page/%d" % (encoded_key, page_num)
        else:
            search_url = "/asian/zh-CN/videos/search/%s" % encoded_key

        res = self._fetch(search_url)
        html_text = res.get("text", "")
        cards = self._parse_vod_list(html_text)

        return {
            "page": page_num,
            "pagecount": page_num + 1 if len(cards) >= 10 else page_num,
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
        return [404, "text/plain; charset=utf-8", "Proxy not needed"]

    def destroy(self):
        self.options = {}
