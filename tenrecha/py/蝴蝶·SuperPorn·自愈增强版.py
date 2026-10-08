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
import http.client
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


# 1. 通用标准库长连接复用处理器
class PersistentHTTPSHandler(urllib.request.HTTPSHandler):
    def __init__(self, context=None):
        super(PersistentHTTPSHandler, self).__init__(context=context)
        self._pool = {}

    def https_open(self, req):
        host = req.host
        conn = self._pool.get(host)
        if conn is None or conn.sock is None:
            conn = http.client.HTTPSConnection(host, context=self._context, timeout=20)
            self._pool[host] = conn
        try:
            return self.do_open(lambda h, timeout=20: conn, req)
        except Exception:
            self._pool.pop(host, None)
            return super(PersistentHTTPSHandler, self).https_open(req)


# 2. X99 导航动态活链解析调度器
class LiveHostResolver(object):
    NAV_URLS = ["https://x99dh.cc", "https://x99dh.one"]

    @classmethod
    def resolve_site(cls, site_name, default_host, ua, opener=None, test_path="/"):
        headers = {
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate"
        }

        for nav in cls.NAV_URLS:
            text = ""
            try:
                req = urllib.request.Request(nav, headers=headers)
                fetch_op = opener if opener else urllib.request.build_opener()
                with fetch_op.open(req, timeout=8) as resp:
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

            # 提取长 Base64 数据块并双重反解
            b64_blocks = re.findall(r'["\']([A-Za-z0-9+/=]{100,})["\']', text)
            for b in b64_blocks:
                try:
                    decoded = base64.b64decode(b).decode("utf-8", errors="ignore")
                    unquoted = urllib.parse.unquote(decoded)
                    if "[" in unquoted and site_name.lower() in unquoted.lower():
                        site_list = json.loads(unquoted)
                        for item in site_list:
                            if item.get("name", "").strip().lower() == site_name.lower():
                                cand_urls = []
                                if item.get("url"):
                                    cand_urls.append(item["url"])
                                for u_obj in item.get("urls", []):
                                    u = u_obj.get("url")
                                    if u and u not in cand_urls:
                                        cand_urls.append(u)

                                for c_url in cand_urls:
                                    parsed = urllib.parse.urlparse(c_url)
                                    base = "%s://%s" % (parsed.scheme, parsed.netloc)
                                    # 验活握手
                                    try:
                                        t_req = urllib.request.Request(base + test_path, headers=headers)
                                        with fetch_op.open(t_req, timeout=5) as t_resp:
                                            if t_resp.getcode() in (200, 301, 302):
                                                return base
                                    except Exception:
                                        continue
                except Exception:
                    continue

        return default_host


class Spider(SpiderBase):
    def __init__(self):
        super(Spider, self).__init__()
        # 活链调度身份与基准配置
        self.siteName = "SuperPorn"
        self.defaultHost = "https://cn.superporn.ws"
        self.baseHost = self.defaultHost
        self.cacheKey = "live_host_%s" % self.siteName.lower()

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
            PersistentHTTPSHandler(context=self.ctx)
        )
        self._warmed_up = False

    def init(self, extend=""):
        if isinstance(extend, dict):
            self.options = extend
        elif extend:
            try:
                self.options = json.loads(extend)
            except Exception:
                self.options = {}

        # 优先读取持久缓存中的活链，防止冷启动网络开销
        cached = self.getCache(self.cacheKey)
        if cached and str(cached).startswith("http"):
            self.baseHost = str(cached).rstrip("/")
        else:
            self.refresh_live_host()

        return True

    def refresh_live_host(self):
        resolved = LiveHostResolver.resolve_site(
            site_name=self.siteName,
            default_host=self.defaultHost,
            ua=self._ua,
            opener=self.opener,
            test_path="/enter"
        )
        self.baseHost = resolved.rstrip("/")
        self.setCache(self.cacheKey, self.baseHost)
        return self.baseHost

    def getName(self):
        return "蝴蝶·SuperPorn·自愈增强版"

    def isVideoFormat(self, url):
        low = (url or "").lower()
        return any(k in low for k in (".m3u8", ".mp4", ".flv", ".mkv", ".avi", ".ts", ".mpd", "index.png"))

    def manualVideoCheck(self):
        return False

    def _warmup_session(self):
        if self._warmed_up:
            return
        try:
            req = urllib.request.Request(self.baseHost + "/enter", headers={
                "User-Agent": self._ua,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Connection": "keep-alive"
            })
            with self.opener.open(req, timeout=15) as resp:
                resp.read()
            self._warmed_up = True
        except Exception:
            pass

    def _fetch(self, target_url, referer="", retry=2):
        if not target_url:
            return {"code": 0, "text": "", "final_url": ""}
        if target_url.startswith("//"):
            target_url = "https:" + target_url
        elif target_url.startswith("/"):
            target_url = self.baseHost + target_url

        self._warmup_session()

        headers = {
            "User-Agent": self._ua,
            "Referer": referer if referer else (self.baseHost + "/"),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive"
        }

        for attempt in range(retry):
            try:
                req = urllib.request.Request(target_url, headers=headers)
                with self.opener.open(req, timeout=20) as resp:
                    code = resp.getcode()
                    final_url = resp.geturl()
                    raw = resp.read()
                    enc = getattr(resp, "headers", {}).get("Content-Encoding", "")
                    if raw.startswith(b"\x1f\x8b") or enc == "gzip":
                        try:
                            raw = gzip.decompress(raw)
                        except Exception:
                            pass
                    elif enc == "deflate":
                        try:
                            raw = zlib.decompress(raw)
                        except Exception:
                            try:
                                raw = zlib.decompress(raw, -zlib.MAX_WBITS)
                            except Exception:
                                pass
                    try:
                        text = raw.decode("utf-8")
                    except Exception:
                        text = raw.decode("latin1", errors="ignore")
                    return {"code": code, "text": text, "final_url": final_url}
            except urllib.error.HTTPError as e:
                # 触发被动自愈：若遇到 404/502/503，尝试重刷活链
                if e.code in (404, 502, 503) and attempt == 0:
                    self.delCache(self.cacheKey)
                    self._warmed_up = False
                    self.refresh_live_host()
                    target_url = re.sub(r'https?://[^/]+', self.baseHost, target_url)
                    continue
                if e.code in (451, 403, 429) and attempt < retry - 1:
                    continue
                err_text = ""
                try:
                    err_text = e.read().decode("utf-8", errors="ignore")
                except Exception:
                    pass
                return {"code": e.code, "text": err_text, "final_url": target_url}
            except Exception:
                if attempt == 0:
                    self.delCache(self.cacheKey)
                    self._warmed_up = False
                    self.refresh_live_host()
                    target_url = re.sub(r'https?://[^/]+', self.baseHost, target_url)
                    continue
                return {"code": -1, "text": "", "final_url": target_url}

        return {"code": -1, "text": "", "final_url": target_url}

    # 1. 首页：纯内存静态装载
    def homeContent(self, filter):
        classes = [
            {"type_name": "日本人", "type_id": "japanese"},
            {"type_name": "女同", "type_id": "lesbian"},
            {"type_name": "MILF", "type_id": "milf"},
            {"type_name": "成人动漫", "type_id": "hentai"},
            {"type_name": "丰臀", "type_id": "big-ass"},
            {"type_name": "黑人", "type_id": "ebony"},
            {"type_name": "拉丁裔", "type_id": "latina"},
            {"type_name": "肛交", "type_id": "anal"},
            {"type_name": "3P", "type_id": "threesome"},
            {"type_name": "内射", "type_id": "creampie"},
            {"type_name": "女性向", "type_id": "female-friendly"},
            {"type_name": "BBW", "type_id": "bbw"},
            {"type_name": "青少年", "type_id": "teen"},
            {"type_name": "Big tits", "type_id": "big-tits"},
            {"type_name": "异族", "type_id": "interracial"},
            {"type_name": "巨根", "type_id": "big-cock"},
            {"type_name": "亚洲人", "type_id": "asian"},
            {"type_name": "公开场合", "type_id": "public"},
            {"type_name": "群交", "type_id": "gangbang"},
            {"type_name": "POV", "type_id": "pov"},
            {"type_name": "喷射", "type_id": "squirting"},
            {"type_name": "成熟", "type_id": "mature"},
            {"type_name": "性高潮", "type_id": "orgasm"}
        ]

        result = {"class": classes}

        if filter:
            filter_item = [
                {
                    "key": "order",
                    "name": "排序",
                    "init": "",
                    "value": [
                        {"n": "默认排序", "v": ""},
                        {"n": "趋势上升", "v": "trending"},
                        {"n": "最受欢迎", "v": "popular"}
                    ]
                }
            ]
            filters = {}
            for item in classes:
                filters[item["type_id"]] = filter_item
            result["filters"] = filters

        return result

    def homeVideoContent(self):
        cate_res = self.categoryContent("japanese", "1", False, {})
        return {"list": cate_res.get("list", [])[:12]}

    # 2. 分类页：伪静态 /{slug}/{pg} 路径与严格防污染
    def categoryContent(self, tid, pg, filter, extend):
        del filter
        extend = extend if isinstance(extend, dict) else {}
        slug = str(tid).strip("/")

        page_str = str(pg).strip() if pg else "1"
        page_int = int(page_str) if page_str.isdigit() else 1

        if page_int > 1:
            target_path = "/%s/%s" % (slug, page_int)
        else:
            target_path = "/%s" % slug

        order_val = extend.get("order", "").strip()
        if order_val:
            target_path += "?order=" + urllib.parse.quote(order_val)

        target_url = self.baseHost + target_path
        res = self._fetch(target_url)
        html_text = res.get("text", "")

        vod_list = []
        cards_raw = html_text.split('class="thumb-video')
        for block in cards_raw[1:]:
            if 'thumb-video__avatar--serie' in block and '/video/' not in block[:300]:
                continue

            link_m = re.search(r'href=["\']([^"\']*/video/[^"\']+)["\']', block)
            if not link_m:
                continue
            vod_href = link_m.group(1).strip()

            alt_m = re.search(r'<img[^>]+alt=["\']([^"\']+)["\']', block)
            vod_name = alt_m.group(1).strip() if alt_m else ""
            if not vod_name:
                t_m = re.search(r'title=["\']([^"\']+)["\']', block)
                vod_name = t_m.group(1).strip() if t_m else ""

            if not vod_name or vod_name in ("无标题", "Oriental Delights"):
                continue

            img_m = re.search(r'data-src=["\'](https?://[^"\']+)["\']', block)
            if not img_m:
                img_m = re.search(r'src=["\'](https?://[^"\']+)["\']', block)
            vod_pic = img_m.group(1).strip() if img_m else ""

            dur_m = re.search(r'class=["\']duracion["\'][^>]*>([\s\S]*?)</span>', block)
            vod_remarks = re.sub(r'\s+', ' ', dur_m.group(1)).strip() if dur_m else ""

            clean_vid = vod_href
            if clean_vid.startswith("http"):
                clean_vid = re.sub(r'https?://[^/]+', '', clean_vid)
            if not clean_vid.startswith("/"):
                clean_vid = "/" + clean_vid

            vod_list.append({
                "vod_id": "vod" + clean_vid,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_remarks": vod_remarks,
                "style": {"type": "rect", "ratio": 1.78}
            })

        if len(vod_list) > 0:
            pagecount = page_int + 50
            total = pagecount * len(vod_list)
        else:
            pagecount = page_int
            total = page_int * 20

        return {
            "page": page_int,
            "pagecount": pagecount,
            "limit": len(vod_list),
            "total": total,
            "list": vod_list
        }

    # 3. 详情页：直接解析动态签名直链
    def detailContent(self, ids):
        raw_id = ids[0] if isinstance(ids, (list, tuple)) else str(ids)
        path = raw_id[3:] if str(raw_id).startswith("vod/") else str(raw_id)
        if not path.startswith("/"):
            path = "/" + path

        target_url = self.baseHost + path
        res = self._fetch(target_url)
        html_text = res.get("text", "")

        source_m = re.search(r'<source[^>]+src=["\']([^"\']+)["\']', html_text, re.I)
        direct_stream_url = source_m.group(1).strip() if source_m else ""

        if not direct_stream_url:
            js_stream_m = re.search(r'["\'](https?://[^"\']+\.mp4[^"\']*)["\']', html_text, re.I)
            if js_stream_m:
                direct_stream_url = js_stream_m.group(1).strip()

        iframe_m = re.search(r'<iframe[^>]+src=["\']([^"\']*/embed/[^"\']*)["\']', html_text, re.I)
        embed_url = iframe_m.group(1).strip() if iframe_m else ""

        title_m = re.search(r'<h1[^>]*>([\s\S]*?)</h1>', html_text, re.I)
        if not title_m:
            title_m = re.search(r'<title>([^<]+)</title>', html_text, re.I)
        raw_title = re.sub(r'<[^>]+>', '', title_m.group(1)).strip() if title_m else "视频详情"

        pic_m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html_text, re.I)
        if not pic_m:
            pic_m = re.search(r'poster=["\']([^"\']+)["\']', html_text, re.I)
        vod_pic = pic_m.group(1).strip() if pic_m else ""

        desc_m = re.search(r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']', html_text, re.I)
        vod_desc = desc_m.group(1).strip() if desc_m else raw_title

        play_from_list = []
        play_url_list = []

        if direct_stream_url:
            play_from_list.append("蝴蝶直连")
            play_url_list.append("正片$" + direct_stream_url)

        if embed_url:
            play_from_list.append("内核嗅探")
            play_url_list.append("备用$" + embed_url)
        elif not direct_stream_url:
            play_from_list.append("备用嗅探")
            play_url_list.append("正片$" + target_url)

        intro_text = (
            "【🔥 官方交流群: %s】\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "%s"
        ) % (self.tgGroup, vod_desc)

        escaped_intro = intro_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        return {
            "list": [{
                "vod_id": raw_id,
                "vod_name": raw_title,
                "vod_pic": vod_pic,
                "vod_actor": self.brandActor,
                "vod_director": self.brandDirector,
                "vod_remarks": "1080P超清",
                "vod_content": escaped_intro,
                "vod_play_from": "$$$".join(play_from_list),
                "vod_play_url": "$$$".join(play_url_list)
            }]
        }

    # 4. 播放解析
    def playerContent(self, flag, id, vipFlags):
        url = str(id).strip()
        is_embed = "/embed/" in url or "/video/" in url

        return {
            "parse": 1 if is_embed else 0,
            "jx": 0,
            "url": url,
            "header": {
                "User-Agent": self._ua,
                "Referer": self.baseHost + "/"
            }
        }

    # 5. 搜索模块
    def searchContent(self, key, quick, pg="1"):
        page_str = str(pg).strip() if pg else "1"
        page_int = int(page_str) if page_str.isdigit() else 1

        target_path = "/search?q=" + urllib.parse.quote(key)
        if page_int > 1:
            target_path += "&p=" + str(page_int)

        target_url = self.baseHost + target_path
        res = self._fetch(target_url)
        html_text = res.get("text", "")

        vod_list = []
        cards_raw = html_text.split('class="thumb-video')
        for block in cards_raw[1:]:
            if 'thumb-video__avatar--serie' in block and '/video/' not in block[:300]:
                continue

            link_m = re.search(r'href=["\']([^"\']*/video/[^"\']+)["\']', block)
            if not link_m:
                continue
            vod_href = link_m.group(1).strip()

            alt_m = re.search(r'<img[^>]+alt=["\']([^"\']+)["\']', block)
            vod_name = alt_m.group(1).strip() if alt_m else ""
            if not vod_name:
                t_m = re.search(r'title=["\']([^"\']+)["\']', block)
                vod_name = t_m.group(1).strip() if t_m else ""

            if not vod_name or vod_name in ("无标题", "Oriental Delights"):
                continue

            img_m = re.search(r'data-src=["\'](https?://[^"\']+)["\']', block)
            if not img_m:
                img_m = re.search(r'src=["\'](https?://[^"\']+)["\']', block)
            vod_pic = img_m.group(1).strip() if img_m else ""

            dur_m = re.search(r'class=["\']duracion["\'][^>]*>([\s\S]*?)</span>', block)
            vod_remarks = re.sub(r'\s+', ' ', dur_m.group(1)).strip() if dur_m else ""

            clean_vid = vod_href
            if clean_vid.startswith("http"):
                clean_vid = re.sub(r'https?://[^/]+', '', clean_vid)
            if not clean_vid.startswith("/"):
                clean_vid = "/" + clean_vid

            vod_list.append({
                "vod_id": "vod" + clean_vid,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_remarks": vod_remarks,
                "style": {"type": "rect", "ratio": 1.78}
            })

        if len(vod_list) > 0:
            pagecount = page_int + 50
            total = pagecount * len(vod_list)
        else:
            pagecount = page_int
            total = page_int * 20

        return {
            "page": page_int,
            "pagecount": pagecount,
            "limit": len(vod_list),
            "total": total,
            "list": vod_list
        }

    def action(self, action):
        return {"msg": "蝴蝶蜘蛛运行就绪"}

    def liveContent(self):
        return ""

    def localProxy(self, params):
        return [404, "text/plain; charset=utf-8", "Proxy not configured"]

    def destroy(self):
        self.options = {}