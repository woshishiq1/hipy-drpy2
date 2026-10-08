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

class Spider(SpiderBase):
    def __init__(self):
        super(Spider, self).__init__()
        self.navUrls = ["https://x99dh.cc", "https://x99dh.one"]
        self.defaultHost = "https://591av.ws"
        self.siteUrl = self.defaultHost
        self.siteName = "亚洲素人精选"
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

        cached_site = self.getCache("591av_dynamic_site_url")
        if cached_site and cached_site.startswith("http"):
            self.siteUrl = cached_site.strip().rstrip("/")
        else:
            self._refresh_site_url()
        return True

    def getName(self):
        return "蝴蝶·591AV(动态自愈版)"

    def isVideoFormat(self, url):
        low = (url or "").lower()
        return any(k in low for k in (".m3u8", ".mp4", ".flv", ".mkv", ".avi", ".ts", ".mpd", "index.png"))

    def manualVideoCheck(self):
        return False

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

            b64_blocks = re.findall(r'["\']([A-Za-z0-9+/=]{100,})["\']', text)
            for b in b64_blocks:
                try:
                    decoded = base64.b64decode(b).decode("utf-8", errors="ignore")
                    unquoted = urllib.parse.unquote(decoded)
                    if "[" in unquoted and (self.siteName in unquoted or "591av" in unquoted.lower()):
                        site_list = json.loads(unquoted)
                        for item in site_list:
                            name = item.get("name", "").strip()
                            if self.siteName in name or name in self.siteName:
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
                                    chk = self._fetch(base + "/categories/released/", check_host=False)
                                    if chk.get("code") == 200:
                                        self.siteUrl = base
                                        self.setCache("591av_dynamic_site_url", base)
                                        return True
                except Exception:
                    continue

        return False

    def _fetch(self, target_url, referer="", check_host=True):
        if not target_url:
            return {"code": 0, "text": "", "bytes": b"", "err": "", "final_url": "", "headers": {}}
        if target_url.startswith("//"):
            target_url = "https:" + target_url
        elif target_url.startswith("/"):
            target_url = self.siteUrl + target_url

        headers = {
            "User-Agent": self._ua,
            "Referer": referer if referer else (self.siteUrl + "/"),
            "Accept": "*/*",
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
                    resp_headers = dict(resp.headers)
                    enc = resp_headers.get("Content-Encoding", "").lower()
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
                    return {
                        "code": code,
                        "text": text,
                        "bytes": raw,
                        "err": "",
                        "final_url": final_url,
                        "headers": resp_headers
                    }
            except urllib.error.HTTPError as e:
                last_err = "HTTP %s" % e.code
                if e.code in (404, 451, 502, 503) and check_host and not domain_retried:
                    old_host = urllib.parse.urlparse(self.siteUrl).netloc
                    self.delCache("591av_dynamic_site_url")
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
                return {
                    "code": e.code,
                    "text": err_raw,
                    "bytes": b"",
                    "err": str(e),
                    "final_url": target_url,
                    "headers": dict(getattr(e, "headers", {}))
                }
            except Exception as e:
                last_err = str(e)
                if check_host and not domain_retried:
                    old_host = urllib.parse.urlparse(self.siteUrl).netloc
                    self.delCache("591av_dynamic_site_url")
                    if self._refresh_site_url():
                        domain_retried = True
                        new_host = urllib.parse.urlparse(self.siteUrl).netloc
                        target_url = target_url.replace(old_host, new_host)
                        continue
                if attempt == 0:
                    continue
                return {"code": -1, "text": "", "bytes": b"", "err": str(e), "final_url": target_url, "headers": {}}

        return {"code": -1, "text": "", "bytes": b"", "err": last_err, "final_url": target_url, "headers": {}}

    def homeContent(self, filter):
        result = {
            "class": [
                {"type_name": "流出", "type_id": "/categories/released/"},
                {"type_name": "探花", "type_id": "/categories/91-tanhua/"},
                {"type_name": "最新上架", "type_id": "/new/"},
                {"type_name": "热门排行", "type_id": "/pp1/hot/"},
                {"type_name": "日本片商", "type_id": "/categories/japan-producer/"}
            ]
        }
        if filter:
            result["filters"] = {}
        return result

    def homeVideoContent(self):
        return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        del filter, extend
        slug = str(tid).strip()
        page_num = int(pg) if pg else 1
        base_slug = slug.rstrip("/")
        page_url = "%s/%d/" % (base_slug, page_num) if page_num > 1 else ("%s/" % base_slug)

        res = self._fetch(self.siteUrl + page_url)
        html = res.get("text", "")

        vod_list = []
        v_matches = re.findall(r'(<a[^>]+href=["\']([^"\']*/v/[^"\']+)["\'][^>]*>([\s\S]*?)</a>)', html, re.I)
        seen_hrefs = set()

        for full_a, href, inner in v_matches:
            clean_href = href.strip()
            if clean_href in seen_hrefs:
                continue
            seen_hrefs.add(clean_href)

            pic_m = re.search(r'data-src=["\']([^"\']+)["\']', full_a, re.I)
            if not pic_m:
                pic_m = re.search(r'(?:data-original|poster|src)=["\']([^"\']+)["\']', full_a, re.I)
            if not pic_m:
                continue

            v_pic = pic_m.group(1).strip()
            if "video-placeholder" in v_pic:
                continue

            if v_pic.startswith("//"):
                v_pic = "https:" + v_pic
            elif v_pic.startswith("/"):
                v_pic = self.siteUrl + v_pic

            t_m = re.search(r'(?:title|alt)=["\']([^"\']+)["\']', full_a, re.I)
            v_title = t_m.group(1).strip() if t_m else ""
            if not v_title:
                txt = re.sub(r'<[^>]+>', ' ', inner).strip()
                v_title = txt.split("\n")[0].strip() if txt else "591AV"

            vod_list.append({
                "vod_id": clean_href,
                "vod_name": v_title,
                "vod_pic": v_pic,
                "vod_remarks": "蝴蝶影视",
                "style": {"type": "rect", "ratio": 1.78}
            })

        return {
            "page": page_num,
            "pagecount": (page_num + 1) if len(vod_list) >= 12 else page_num,
            "limit": len(vod_list),
            "total": 9999,
            "list": vod_list
        }

    def detailContent(self, ids):
        raw_id = ids[0] if isinstance(ids, (list, tuple)) else str(ids)
        vod_url = raw_id if raw_id.startswith("http") else (self.siteUrl + raw_id)

        res = self._fetch(vod_url)
        html = res.get("text", "")

        t_m = re.search(r'<title>(.*?)</title>', html, re.I)
        vod_name = t_m.group(1).split("-")[0].split("|")[0].strip() if t_m else "591AV"

        media_candidates = re.findall(r'["\'](https?://[^"\']+\.(?:m3u8|mp4)[^"\']*)["\']', html, re.I)
        valid_streams = [m for m in media_candidates if "preview" not in m.lower() and "sample" not in m.lower()]

        final_stream = valid_streams[0] if valid_streams else vod_url
        vod_play_url = "正片$%s" % final_stream

        full_desc = (
            "【🔥 官方交流群: %s】\n"
            "【当前动态主站: %s】\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "片名：%s\n"
            "线路：591AV原生原画直链解析专线，已穿透调度端点支持高速拖拽。"
        ) % (self.tgGroup, self.siteUrl, vod_name)

        escaped_desc = full_desc.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        return {
            "list": [{
                "vod_id": raw_id,
                "vod_name": vod_name,
                "vod_pic": "",
                "vod_actor": self.brandActor,
                "vod_director": self.brandDirector,
                "vod_remarks": "蝴蝶影视",
                "vod_content": escaped_desc,
                "vod_play_from": "591AV极速专线",
                "vod_play_url": vod_play_url
            }]
        }

    def playerContent(self, flag, id, vipFlags):
        stream_url = str(id).strip()

        if "/jmpres/" in stream_url or "stream/" in stream_url:
            res = self._fetch(stream_url, referer=self.siteUrl + "/")
            final_url = res.get("final_url", stream_url)
            headers_dict = res.get("headers", {})

            if final_url == stream_url:
                loc = headers_dict.get("Location") or headers_dict.get("location")
                if loc:
                    final_url = loc if loc.startswith("http") else urllib.parse.urljoin(stream_url, loc)

            return {
                "parse": 0,
                "playUrl": "",
                "url": final_url,
                "header": {
                    "User-Agent": self._ua,
                    "Referer": self.siteUrl + "/",
                    "Origin": self.siteUrl,
                    "Connection": "keep-alive"
                },
                "position": 1
            }

        return {
            "parse": 0,
            "playUrl": "",
            "url": stream_url,
            "header": {
                "User-Agent": self._ua,
                "Referer": self.siteUrl + "/",
                "Origin": self.siteUrl,
                "Connection": "keep-alive"
            },
            "position": 1
        }

    def searchContent(self, key, quick, pg="1"):
        page_num = int(pg) if pg else 1
        query_encoded = quote(key)
        search_path = "/search/%s/%d/" % (query_encoded, page_num) if page_num > 1 else ("/search/%s/" % query_encoded)
        res = self._fetch(self.siteUrl + search_path)
        html = res.get("text", "")

        vod_list = []
        v_matches = re.findall(r'(<a[^>]+href=["\']([^"\']*/v/[^"\']+)["\'][^>]*>([\s\S]*?)</a>)', html, re.I)
        seen_hrefs = set()

        for full_a, href, inner in v_matches:
            clean_href = href.strip()
            if clean_href in seen_hrefs:
                continue
            seen_hrefs.add(clean_href)

            pic_m = re.search(r'data-src=["\']([^"\']+)["\']', full_a, re.I)
            if not pic_m:
                pic_m = re.search(r'(?:data-original|poster|src)=["\']([^"\']+)["\']', full_a, re.I)
            if not pic_m:
                continue

            v_pic = pic_m.group(1).strip()
            if "video-placeholder" in v_pic:
                continue

            if v_pic.startswith("//"):
                v_pic = "https:" + v_pic
            elif v_pic.startswith("/"):
                v_pic = self.siteUrl + v_pic

            t_m = re.search(r'(?:title|alt)=["\']([^"\']+)["\']', full_a, re.I)
            v_title = t_m.group(1).strip() if t_m else ""
            if not v_title:
                txt = re.sub(r'<[^>]+>', ' ', inner).strip()
                v_title = txt.split("\n")[0].strip() if txt else "591AV"

            vod_list.append({
                "vod_id": clean_href,
                "vod_name": v_title,
                "vod_pic": v_pic,
                "vod_remarks": "蝴蝶影视",
                "style": {"type": "rect", "ratio": 1.78}
            })

        return {
            "page": page_num,
            "pagecount": (page_num + 1) if len(vod_list) >= 12 else page_num,
            "limit": len(vod_list),
            "total": 9999,
            "list": vod_list
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