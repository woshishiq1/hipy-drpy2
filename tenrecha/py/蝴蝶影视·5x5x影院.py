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
        # 发布页与初始备用最新域名池
        self.publishUrls = [
            "https://5x5x.tv"
        ]
        self.defaultDomains = [
            "https://www.grko8wh.vip",
            "https://www.8lk5cso.vip",
            "https://www.51miscl.vip",
            "https://www.uqhf6f3.vip",
            "https://uqhf6f3.vip"
        ]
        self.siteUrl = self.defaultDomains[0]
        self.tgGroup = "https://t.me/tvshare23"
        self.brandActor = "🦋 TG群: @tvshare23"
        self.brandDirector = "🦋 蝴蝶影视"
        self._ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        self.options = {}

        self.ctx = ssl.create_default_context()
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE

        self.cj = http.cookiejar.CookieJar()
        self._init_opener()

    def _init_opener(self, proxy_url=None):
        handlers = [
            urllib.request.HTTPCookieProcessor(self.cj),
            urllib.request.HTTPSHandler(context=self.ctx)
        ]
        if proxy_url:
            handlers.append(urllib.request.ProxyHandler({
                "http": proxy_url,
                "https": proxy_url
            }))
        self.opener = urllib.request.build_opener(*handlers)

    def init(self, extend=""):
        if isinstance(extend, dict):
            self.options = extend
        elif extend:
            try:
                self.options = json.loads(extend)
            except Exception:
                self.options = {}

        if self.options.get("proxy"):
            self._init_opener(self.options.get("proxy"))

        # 优先读取缓存活跃域名
        cached_domain = self.getCache("spider_active_domain_5x5x")
        if cached_domain and str(cached_domain).startswith("http"):
            self.siteUrl = str(cached_domain).strip().rstrip("/")
        else:
            self._check_drift_domain()
        return True

    def getName(self):
        return "蝴蝶影视·5x5x影院"

    def isVideoFormat(self, url):
        low = (url or "").lower()
        return any(k in low for k in (".m3u8", ".mp4", ".flv", ".mkv", ".avi", ".ts", ".mpd"))

    def manualVideoCheck(self):
        return False

    # 域名多级探测与自愈漂移逻辑
    def _check_drift_domain(self):
        cand_domains = []
        custom_domain = self.options.get("domain") or self.options.get("host")
        if custom_domain:
            if not str(custom_domain).startswith("http"):
                custom_domain = "https://" + str(custom_domain).strip()
            cand_domains.append(str(custom_domain).rstrip("/"))

        for d in self.defaultDomains:
            if d not in cand_domains:
                cand_domains.append(d)

        headers = {
            "User-Agent": self._ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }

        # 阶段一：快速探测静态候选池
        for domain in cand_domains:
            try:
                req = urllib.request.Request(domain, headers=headers)
                with self.opener.open(req, timeout=4) as resp:
                    if resp.getcode() == 200:
                        self.siteUrl = domain
                        self.setCache("spider_active_domain_5x5x", domain)
                        return
            except Exception:
                continue

        # 阶段二：静态全灭时，自动请求发布页动态提取最新域名
        for pub_url in self.publishUrls:
            try:
                req = urllib.request.Request(pub_url, headers=headers)
                with self.opener.open(req, timeout=5) as resp:
                    raw = resp.read()
                    try:
                        html_text = raw.decode("utf-8")
                    except Exception:
                        html_text = raw.decode("latin1", errors="ignore")

                    # 提取发布页上的所有最新域名
                    found_urls = re.findall(r'https?://[a-zA-Z0-9_\-\.]+\.(?:vip|com|top|tv|me|xyz)', html_text)
                    for u in found_urls:
                        clean_u = u.rstrip("/")
                        if "5x5x.tv" in clean_u:
                            continue
                        try:
                            chk_req = urllib.request.Request(clean_u, headers=headers)
                            with self.opener.open(chk_req, timeout=4) as chk_resp:
                                if chk_resp.getcode() == 200:
                                    self.siteUrl = clean_u
                                    self.setCache("spider_active_domain_5x5x", clean_u)
                                    return
                        except Exception:
                            continue
            except Exception:
                continue

    def _fetch(self, target_url, referer=""):
        if not target_url:
            return {"code": 0, "text": "", "err": ""}
        if target_url.startswith("/"):
            target_url = self.siteUrl + target_url

        headers = {
            "User-Agent": self._ua,
            "Referer": referer if referer else (self.siteUrl + "/"),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,ja;q=0.7",
            "Connection": "close"
        }

        for attempt in range(2):
            try:
                req = urllib.request.Request(target_url, headers=headers)
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
                    return {"code": code, "text": text, "err": ""}
            except Exception as e:
                # 首次请求失败且可能是域名失效，主动触发漂移并重试
                if attempt == 0:
                    self._check_drift_domain()
                    if target_url.startswith("http"):
                        p = urllib.parse.urlparse(target_url)
                        target_url = self.siteUrl + p.path + ("?" + p.query if p.query else "")
                else:
                    return {"code": -1, "text": "", "err": str(e)}
        return {"code": -1, "text": "", "err": "timeout"}

    def homeContent(self, filter):
        classes = [
            {"type_name": "🇨🇳 大陆视频", "type_id": "/category/1/"},
            {"type_name": "🇯🇵 日韩精选", "type_id": "/category/2/"},
            {"type_name": "🇺🇸 欧美高清", "type_id": "/category/3/"},
            {"type_name": "🎨 动漫精品", "type_id": "/category/4/"},
            {"type_name": "🔞 三级经典", "type_id": "/category/5/"},
            {"type_name": "🔥 热门黑料", "type_id": "/tags/%e7%83%ad%e9%97%a8%e9%bb%91%e6%96%99/"},
            {"type_name": "💬 中文字幕", "type_id": "/tags/%e4%b8%ad%e6%96%87%e5%ad%97%e5%b9%95/"},
            {"type_name": "📸 网红主播", "type_id": "/tags/%e7%bd%91%e7%ba%a2%e4%b8%bb%e6%92%ad/"},
            {"type_name": "✨ 高清无码", "type_id": "/tags/%e9%ab%98%e6%b8%85%e6%97%a0%e7%a0%81/"}
        ]
        result = {"class": classes}
        if filter:
            result["filters"] = {}
        return result

    def homeVideoContent(self):
        return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        del filter
        slug = str(tid).strip()
        pg_num = int(pg) if str(pg).isdigit() else 1

        target_path = slug
        if pg_num > 1:
            if target_path.endswith("/"):
                target_path = "%spage/%d/" % (target_path, pg_num)
            else:
                target_path = "%s/page/%d/" % (target_path, pg_num)

        res = self._fetch(target_path)
        html_text = res.get("text", "")

        videos = []
        seen_ids = set()

        blocks = re.split(r'<a\s+(?:[^>]*\s+)?href=', html_text, flags=re.I)
        for block in blocks[1:]:
            href_m = re.match(r'["\']?([^"\'\s>]+)["\']?', block)
            if not href_m:
                continue
            href = href_m.group(1).strip()
            if not href.startswith("/vd/") or href in seen_ids:
                continue

            pic_m = re.search(r'data-src=["\']?([^"\'\s>]+)["\']?', block, re.I)
            pic = pic_m.group(1).strip() if pic_m else ""
            if pic.startswith("//"):
                pic = "https:" + pic
            elif pic.startswith("/"):
                pic = self.siteUrl + pic

            title = ""
            title_m = re.search(r'class=["\']?card-title["\']?[^>]*>([\s\S]*?)</div>', block, re.I)
            if title_m:
                title = title_m.group(1).strip()
            else:
                alt_m = re.search(r'alt=["\']?([^"\'\s>]+)["\']?', block, re.I)
                if alt_m:
                    title = alt_m.group(1).strip()

            title = re.sub(r'<[^>]+>', '', title).strip()

            if href and (title or pic):
                seen_ids.add(href)
                videos.append({
                    "vod_id": href,
                    "vod_name": html_lib.unescape(title) if title else "精彩视频",
                    "vod_pic": pic if pic else "https://dummyimage.com/400x600/1a1a1a/ffffff.png&text=No+Pic",
                    "vod_remarks": "超清",
                    "style": {"type": "rect", "ratio": 0.75}
                })

        page_count = pg_num + 1 if len(videos) >= 15 else (pg_num if len(videos) > 0 else 1)
        total_count = 9999 if len(videos) >= 15 else (pg_num * len(videos) if len(videos) > 0 else 0)

        return {
            "page": pg_num,
            "pagecount": page_count,
            "limit": len(videos),
            "total": total_count,
            "list": videos
        }

    def detailContent(self, ids):
        raw_id = ids[0] if isinstance(ids, (list, tuple)) else str(ids)
        detail_url = raw_id if raw_id.startswith("http") else self.siteUrl + raw_id
        res = self._fetch(detail_url)
        html_text = res.get("text", "")

        m3u8_url = ""
        mp4_url = ""

        m3u8_m = re.search(r'data-m3u8=["\']?([^"\'\s>]+)["\']?', html_text, re.I)
        if m3u8_m and m3u8_m.group(1).strip():
            m3u8_url = m3u8_m.group(1).strip()

        mp4_m = re.search(r'data-mp4=["\']?([^"\'\s>]+)["\']?', html_text, re.I)
        if mp4_m and mp4_m.group(1).strip():
            mp4_url = mp4_m.group(1).strip()

        if not m3u8_url and not mp4_url:
            gen_m = re.search(r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', html_text, re.I)
            if gen_m:
                m3u8_url = gen_m.group(1).strip()

        play_entries = []
        if m3u8_url:
            clean_m3u8 = m3u8_url.replace("$", "").replace("#", "")
            play_entries.append("M3U8极速直链$%s" % clean_m3u8)
        if mp4_url:
            clean_mp4 = mp4_url.replace("$", "").replace("#", "")
            play_entries.append("MP4备用直链$%s" % clean_mp4)

        if not play_entries:
            play_entries.append("暂无直链$http://127.0.0.1")

        title_m = re.search(r'<title>(.*?)</title>', html_text, re.I)
        vod_name = title_m.group(1).split("-")[0].strip() if title_m else "精彩影视"

        desc_lines = [
            "【🔥 官方交流群: %s】" % self.tgGroup,
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "• 影片名称: %s" % vod_name,
            "• 当前活跃节点: %s" % self.siteUrl,
            "• 播放模式: 纯直链零嗅探秒播",
            "• 蝴蝶影视已启用动态域名漂移防护机制。"
        ]
        escaped_desc = "\n".join(desc_lines).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        return {
            "list": [{
                "vod_id": raw_id,
                "vod_name": html_lib.unescape(vod_name),
                "vod_pic": "",
                "vod_actor": self.brandActor,
                "vod_director": self.brandDirector,
                "vod_remarks": "1080P直链",
                "vod_content": escaped_desc,
                "vod_play_from": "🦋蝴蝶极速专线",
                "vod_play_url": "#".join(play_entries)
            }]
        }

    def playerContent(self, flag, id, vipFlags):
        real_url = str(id).strip()
        return {
            "parse": 0,
            "jx": 0,
            "url": real_url,
            "header": {
                "User-Agent": self._ua,
                "Referer": self.siteUrl + "/"
            }
        }

    def searchContent(self, key, quick, pg="1"):
        pg_num = int(pg) if str(pg).isdigit() else 1
        search_path = "/search/%s/" % urllib.parse.quote(key)
        if pg_num > 1:
            search_path = "%spage/%d/" % (search_path, pg_num)

        res = self._fetch(search_path)
        html_text = res.get("text", "")

        videos = []
        seen_ids = set()

        blocks = re.split(r'<a\s+(?:[^>]*\s+)?href=', html_text, flags=re.I)
        for block in blocks[1:]:
            href_m = re.match(r'["\']?([^"\'\s>]+)["\']?', block)
            if not href_m:
                continue
            href = href_m.group(1).strip()
            if not href.startswith("/vd/") or href in seen_ids:
                continue

            pic_m = re.search(r'data-src=["\']?([^"\'\s>]+)["\']?', block, re.I)
            pic = pic_m.group(1).strip() if pic_m else ""
            if pic.startswith("//"):
                pic = "https:" + pic
            elif pic.startswith("/"):
                pic = self.siteUrl + pic

            title = ""
            title_m = re.search(r'class=["\']?card-title["\']?[^>]*>([\s\S]*?)</div>', block, re.I)
            if title_m:
                title = title_m.group(1).strip()
            else:
                alt_m = re.search(r'alt=["\']?([^"\'\s>]+)["\']?', block, re.I)
                if alt_m:
                    title = alt_m.group(1).strip()

            title = re.sub(r'<[^>]+>', '', title).strip()

            if href and (title or pic):
                seen_ids.add(href)
                videos.append({
                    "vod_id": href,
                    "vod_name": html_lib.unescape(title) if title else key,
                    "vod_pic": pic if pic else "https://dummyimage.com/400x600/1a1a1a/ffffff.png&text=Search",
                    "vod_remarks": "搜索结果",
                    "style": {"type": "rect", "ratio": 0.75}
                })

        return {
            "page": pg_num,
            "pagecount": pg_num + 1 if len(videos) >= 15 else 1,
            "limit": len(videos),
            "total": 9999 if len(videos) >= 15 else len(videos),
            "list": videos
        }

    def action(self, action):
        if action == "toast":
            return {"msg": "🦋 蝴蝶影视正在为您极速解析"}
        return {"msg": "ok"}

    def liveContent(self):
        return ""

    def localProxy(self, params):
        return [404, "text/plain; charset=utf-8", "Proxy not configured"]

    def destroy(self):
        self.options = {}
