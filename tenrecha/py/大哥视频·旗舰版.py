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
        self.defaultHost = "https://dage.one"
        self.baseHost = self.defaultHost
        self.navUrls = ["https://x99dh.cc", "https://x99dh.one"]
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

        self.zone_matrix = {
            "z_gaoqing": {
                "name": "高清一区",
                "default_sub": "56",
                "subs": [
                    {"n": "亚洲有码", "v": "56"},
                    {"n": "亚洲无码", "v": "57"},
                    {"n": "亚洲主播", "v": "58"},
                    {"n": "韩国高清", "v": "59"},
                    {"n": "大陆高清", "v": "60"},
                    {"n": "欧美高清", "v": "61"},
                    {"n": "H动漫", "v": "62"},
                    {"n": "三级伦理", "v": "63"}
                ]
            },
            "z_jisu": {
                "name": "极速二区",
                "default_sub": "102",
                "subs": [
                    {"n": "中文字幕", "v": "102"},
                    {"n": "日韩无码", "v": "101"},
                    {"n": "国产自制", "v": "103"},
                    {"n": "约炮偷拍", "v": "104"},
                    {"n": "传媒剧情", "v": "105"},
                    {"n": "强制乱伦", "v": "106"},
                    {"n": "SM调教", "v": "107"},
                    {"n": "剧情动漫", "v": "108"}
                ]
            },
            "z_san": {
                "name": "视频三区",
                "default_sub": "83",
                "subs": [
                    {"n": "国产制片", "v": "83"},
                    {"n": "日本无码", "v": "84"},
                    {"n": "中文字幕", "v": "85"},
                    {"n": "AV剧情", "v": "86"},
                    {"n": "长腿丝袜", "v": "87"},
                    {"n": "邻家人妻", "v": "88"},
                    {"n": "网红主播", "v": "89"},
                    {"n": "国模私拍", "v": "90"}
                ]
            },
            "z_si": {
                "name": "视频四区",
                "default_sub": "92",
                "subs": [
                    {"n": "抖阴视频", "v": "92"},
                    {"n": "网红头条", "v": "93"},
                    {"n": "AV解说", "v": "94"},
                    {"n": "制服诱惑", "v": "95"},
                    {"n": "明星换脸", "v": "96"},
                    {"n": "SM调教", "v": "97"},
                    {"n": "女同性恋", "v": "98"},
                    {"n": "VR视角", "v": "99"}
                ]
            }
        }

    def init(self, extend=""):
        if isinstance(extend, dict):
            self.options = extend
        elif extend:
            try:
                self.options = json.loads(extend)
            except Exception:
                self.options = {}

        self._get_active_host()
        return True

    def getName(self):
        return "大哥视频·旗舰版"

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
                    text = raw.decode("utf-8", errors="ignore")
            except Exception:
                continue

            if not text:
                continue

            b64_blocks = re.findall(r'["\']([A-Za-z0-9+/=]{100,})["\']', text)
            for b in b64_blocks:
                try:
                    decoded = base64.b64decode(b).decode("utf-8", errors="ignore")
                    unquoted = urllib.parse.unquote(decoded)
                    if "大哥" in unquoted or "dage" in unquoted or "[" in unquoted:
                        site_list = json.loads(unquoted)
                        for item in site_list:
                            if "大哥" in item.get("name", "") or "dage" in item.get("url", ""):
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
                                    chk = self._fetch(base + "/api/index.json", check_host=False)
                                    if chk.get("code") == 200:
                                        return base
                except Exception:
                    continue

        return self.defaultHost

    def _get_active_host(self):
        cached_host = self.getCache("dage_live_host")
        if cached_host and cached_host.startswith("http"):
            self.baseHost = cached_host
            return self.baseHost

        new_host = self._resolve_nav_sites()
        self.baseHost = new_host if new_host else self.defaultHost
        self.setCache("dage_live_host", self.baseHost)
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
            "Referer": referer if referer else (self.baseHost + "/list/102.html"),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive"
        }

        last_err = ""
        for attempt in range(2):
            try:
                req = urllib.request.Request(target_url, headers=headers)
                with self.opener.open(req, timeout=10) as resp:
                    code = resp.getcode()
                    final_url = resp.geturl()
                    raw = resp.read()
                    enc = resp.headers.get("Content-Encoding", "").lower()
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
                    return {"code": code, "text": text, "bytes": raw, "err": "", "final_url": final_url}
            except urllib.error.HTTPError as e:
                last_err = "HTTP %s" % e.code
                if e.code in (404, 502, 503) and check_host and attempt == 0:
                    self.delCache("dage_live_host")
                    self._get_active_host()
                    target_url = re.sub(r'https?://[^/]+', self.baseHost, target_url)
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
                    self.delCache("dage_live_host")
                    self._get_active_host()
                    target_url = re.sub(r'https?://[^/]+', self.baseHost, target_url)
                    continue
                return {"code": -1, "text": "", "bytes": b"", "err": str(e), "final_url": target_url}

        return {"code": -1, "text": "", "bytes": b"", "err": last_err, "final_url": target_url}

    def _decrypt_payload(self, enc_str):
        if not enc_str or not isinstance(enc_str, str):
            return {}
        try:
            s = enc_str.replace("/", "0").replace("@", "/").replace(".", "+")[::-1]
            mod = len(s) % 4
            if mod != 0:
                s += "=" * (4 - mod)
            raw = base64.b64decode(s).decode("utf-8", errors="ignore")
            return json.loads(raw)
        except Exception:
            return {}

    def _clean_stream_url(self, raw_url):
        if not raw_url:
            return ""
        match_inner = re.search(r'url-(https?://[^\s\'"<>]+)', raw_url)
        if match_inner:
            return match_inner.group(1).strip()
        pos = raw_url.rfind("http://")
        if pos == -1:
            pos = raw_url.rfind("https://")
        if pos > 0:
            return raw_url[pos:].strip()
        return raw_url.strip()

    def homeContent(self, filter):
        classes = []
        ordered_keys = ["z_gaoqing", "z_jisu", "z_san", "z_si"]
        for k in ordered_keys:
            classes.append({
                "type_name": self.zone_matrix[k]["name"],
                "type_id": k
            })

        result = {"class": classes}

        if filter:
            filters = {}
            for k in ordered_keys:
                filters[k] = [
                    {
                        "key": "sub_id",
                        "name": "分类",
                        "value": self.zone_matrix[k]["subs"]
                    }
                ]
            result["filters"] = filters

        return result

    def homeVideoContent(self):
        res = self._fetch("/api/lists/56/1/24.json")
        v_list = []
        if res.get("code") == 200:
            try:
                outer = json.loads(res.get("text", "{}"))
                data = self._decrypt_payload(outer.get("data", ""))
                items = data.get("items", [])
                for it in items:
                    v_id = str(it.get("vod_id") or "")
                    title = it.get("title", "")
                    pic = it.get("img", "")
                    duration = it.get("duration", "")
                    remarks = "蝴蝶影视" + (" " + duration if duration else "")
                    if v_id and title:
                        v_list.append({
                            "vod_id": v_id,
                            "vod_name": title,
                            "vod_pic": pic,
                            "vod_remarks": remarks,
                            "style": {"type": "rect", "ratio": 1.78}
                        })
            except Exception:
                pass
        return {"list": v_list}

    def categoryContent(self, tid, pg, filter, extend):
        del filter
        zone_slug = str(tid).strip("/")
        page = int(pg) if str(pg).isdigit() else 1
        limit = 24

        sub_id = ""
        if isinstance(extend, dict):
            sub_id = extend.get("sub_id", "")

        if not sub_id:
            zone_info = self.zone_matrix.get(zone_slug)
            sub_id = zone_info["default_sub"] if zone_info else zone_slug

        target_path = "/api/lists/%s/%s/%s.json" % (sub_id, page, limit)
        res = self._fetch(target_path)

        items = []
        total_count = 0
        if res.get("code") == 200:
            try:
                outer = json.loads(res.get("text", "{}"))
                data = self._decrypt_payload(outer.get("data", ""))
                items = data.get("items", [])
                total_count = data.get("page", {}).get("count", 0)
            except Exception:
                items = []

        vod_list = []
        for it in items:
            v_id = str(it.get("vod_id") or "")
            title = it.get("title", "")
            pic = it.get("img", "")
            duration = it.get("duration", "")
            remarks = "蝴蝶影视" + (" " + duration if duration else "")
            if v_id and title:
                vod_list.append({
                    "vod_id": v_id,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": remarks,
                    "style": {"type": "rect", "ratio": 1.78}
                })

        page_count = (total_count // limit) + (1 if total_count % limit != 0 else 0)
        if page_count <= 0:
            page_count = 1

        return {
            "page": page,
            "pagecount": page_count,
            "limit": limit,
            "total": total_count if total_count > 0 else len(vod_list),
            "list": vod_list
        }

    def detailContent(self, ids):
        raw_id = ids[0] if isinstance(ids, (list, tuple)) else str(ids)
        clean_id = raw_id.strip()

        res = self._fetch("/api/play/%s.json" % clean_id)
        title = "视频详情"
        pic = ""
        desc = "暂无简介"
        play_url = ""

        if res.get("code") == 200:
            try:
                outer = json.loads(res.get("text", "{}"))
                data = self._decrypt_payload(outer.get("data", ""))
                title = data.get("title") or data.get("name") or title
                pic = data.get("img") or data.get("pic") or ""
                desc = data.get("content") or data.get("desc") or desc

                players = data.get("player", [])
                if isinstance(players, list) and players:
                    raw_play = players[0].get("play", "")
                    play_url = self._clean_stream_url(raw_play)

                if not play_url:
                    raw_play = data.get("url") or data.get("play_url") or data.get("m3u8") or ""
                    play_url = self._clean_stream_url(raw_play)
            except Exception:
                pass

        clean_title = re.sub(r'[\$#]', '', title)
        full_desc = (
            "【官方交流群: %s】\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "当前接入节点: %s\n"
            "%s"
        ) % (self.tgGroup, self.baseHost, desc)

        return {
            "list": [{
                "vod_id": clean_id,
                "vod_name": clean_title,
                "vod_pic": pic,
                "vod_actor": self.brandActor,
                "vod_director": self.brandDirector,
                "vod_remarks": "蝴蝶影视",
                "vod_content": full_desc.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"),
                "vod_play_from": "蝴蝶专线",
                "vod_play_url": "正片$%s" % play_url
            }]
        }

    def playerContent(self, flag, id, vipFlags):
        del flag, vipFlags
        stream_url = self._clean_stream_url(str(id).strip())

        return {
            "parse": 0,
            "playUrl": "",
            "url": stream_url,
            "header": {
                "User-Agent": self._ua,
                "Referer": "https://vostrely.com/"
            }
        }

    def searchContent(self, key, quick, pg="1"):
        del quick
        page_int = int(pg) if str(pg).isdigit() else 1
        res = self._fetch("/api/lists/102/1/50.json")
        v_list = []
        if res.get("code") == 200:
            try:
                outer = json.loads(res.get("text", "{}"))
                data = self._decrypt_payload(outer.get("data", ""))
                items = data.get("items", [])
                for it in items:
                    title = it.get("title", "")
                    if key.lower() in title.lower():
                        v_id = str(it.get("vod_id") or "")
                        pic = it.get("img", "")
                        duration = it.get("duration", "")
                        remarks = "蝴蝶影视" + (" " + duration if duration else "")
                        v_list.append({
                            "vod_id": v_id,
                            "vod_name": title,
                            "vod_pic": pic,
                            "vod_remarks": remarks,
                            "style": {"type": "rect", "ratio": 1.78}
                        })
            except Exception:
                pass
        return {
            "page": page_int,
            "pagecount": page_int,
            "limit": len(v_list),
            "total": len(v_list),
            "list": v_list
        }

    def action(self, action):
        return {"msg": "大哥视频自愈蜘蛛运行正常"}

    def liveContent(self):
        return ""

    def localProxy(self, params):
        return [404, "text/plain; charset=utf-8", "Proxy not configured"]

    def destroy(self):
        self.options = {}