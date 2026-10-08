#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import re
import json
import base64
import hashlib
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

def clean_html_text(raw_html):
    txt = re.sub(r'<[^>]+>', '', raw_html or '')
    txt = html_lib.unescape(txt)
    return re.sub(r'[\r\n\t\s]+', ' ', txt).strip()

def format_seconds(secs):
    try:
        s = int(secs)
        h = s // 3600
        m = (s % 3600) // 60
        sec = s % 60
        if h > 0:
            return "%02d:%02d:%02d" % (h, m, sec)
        return "%02d:%02d" % (m, sec)
    except Exception:
        return ""

def generate_color_card(text, is_ctrl=False):
    palette = [
        ("#4f46e5", "#7c3aed"),
        ("#2563eb", "#06b6d4"),
        ("#059669", "#10b981"),
        ("#d97706", "#f59e0b"),
        ("#dc2626", "#ea580c"),
        ("#db2777", "#f43f5e"),
        ("#475569", "#334155"),
        ("#0891b2", "#0284c7")
    ]
    name_str = (text or "GetAV").strip()
    if is_ctrl:
        c1, c2 = ("#e11d48", "#be123c")
    else:
        h_val = int(hashlib.md5(name_str.encode("utf-8")).hexdigest()[:4], 16)
        c1, c2 = palette[h_val % len(palette)]
    
    display_title = name_str[:12]
    font_size = "40" if len(display_title) <= 6 else ("32" if len(display_title) <= 9 else "26")
    
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360" viewBox="0 0 640 360">'
        '<defs>'
        '<linearGradient id="g" x1="0%%" y1="0%%" x2="100%%" y2="100%%">'
        '<stop offset="0%%" stop-color="%s"/>'
        '<stop offset="100%%" stop-color="%s"/>'
        '</linearGradient>'
        '</defs>'
        '<rect width="640" height="360" rx="24" fill="url(#g)"/>'
        '<text x="50%%" y="54%%" font-size="%s" font-family="sans-serif" font-weight="bold" '
        'fill="#ffffff" text-anchor="middle" dominant-baseline="middle">'
        '%s'
        '</text>'
        '</svg>'
    ) % (c1, c2, font_size, display_title)
    b64_svg = base64.b64encode(svg.encode("utf-8")).decode("utf-8")
    return "data:image/svg+xml;base64,%s" % b64_svg

class SmartRedirectHandler(urllib.request.HTTPRedirectHandler):
    def http_error_308(self, req, fp, code, msg, headers):
        infourl = urllib.response.addinfourl(fp, headers, req.get_full_url())
        infourl.status = code
        infourl.code = code
        return self.parent.open(req.get_header('Location', ''))

class Spider(SpiderBase):
    def __init__(self):
        super(Spider, self).__init__()
        self.navSite = "https://getav.info/zh/"
        self.hosts = [
            "https://getav.net",
            "https://getav.me",
            "https://getav.live",
            "https://getav.co",
            "https://getav.top"
        ]
        self._host_idx = 0
        self.baseHost = self.hosts[0]
        self.staticHost = "https://static.worldstatic.com"
        self.tgGroup = "https://t.me/+3t5XRPPo9mlkZDRl"
        self.brandActor = "📺TG群: https://t.me/+3t5XRPPo9mlkZDRl"
        self.brandDirector = "📺ZakaTV"
        self._ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        self.options = {}

        self.ctx = ssl.create_default_context()
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE

        self.cj = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cj),
            urllib.request.HTTPSHandler(context=self.ctx),
            SmartRedirectHandler()
        )

    def init(self, extend=""):
        if isinstance(extend, dict):
            self.options = extend
        elif extend:
            try:
                self.options = json.loads(extend)
            except Exception:
                self.options = {}

        custom_host = self.options.get("host") or self.options.get("siteUrl")
        if custom_host:
            custom_host = custom_host.rstrip("/")
            if custom_host not in self.hosts:
                self.hosts.insert(0, custom_host)
            self.baseHost = custom_host
        else:
            cached_host = self.getCache("getav_live_host")
            if cached_host and str(cached_host).startswith("http"):
                if cached_host not in self.hosts:
                    self.hosts.insert(0, cached_host)
                self.baseHost = cached_host
            else:
                self._update_live_host()
        return True

    def getName(self):
        return "GetAV"

    def isVideoFormat(self, url):
        low = (url or "").lower()
        return any(k in low for k in (".m3u8", ".mp4", ".flv", ".mkv", ".avi", ".ts", ".mpd", "index.png", "index.txt"))

    def manualVideoCheck(self):
        return False

    def _update_live_host(self):
        try:
            req = urllib.request.Request(self.navSite, headers={
                "User-Agent": self._ua,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            })
            with self.opener.open(req, timeout=5) as resp:
                raw = resp.read()
                enc = getattr(resp, "headers", {}).get("Content-Encoding", "")
                if raw.startswith(b"\x1f\x8b") or enc == "gzip":
                    raw = gzip.decompress(raw)
                html = raw.decode("utf-8", errors="ignore")

                domains = re.findall(r'getav\.(?:net|me|live|co|top|[a-z0-9]+)', html, re.I)
                clean_hosts = []
                for d in domains:
                    h = ("https://%s" % d.lower()).strip()
                    if "info" not in h and h not in clean_hosts:
                        clean_hosts.append(h)

                if clean_hosts:
                    for ch in reversed(clean_hosts):
                        if ch not in self.hosts:
                            self.hosts.insert(0, ch)
                    self.baseHost = self.hosts[0]
                    self._host_idx = 0
                    self.setCache("getav_live_host", self.baseHost)
                    return True
        except Exception:
            pass
        return False

    def _fetch_api(self, api_path, timeout=10):
        headers = {
            "User-Agent": self._ua,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive"
        }

        for i in range(len(self.hosts)):
            idx = (self._host_idx + i) % len(self.hosts)
            cur_host = self.hosts[idx]

            if api_path.startswith("http"):
                url = re.sub(r"^https?://[^/]+", cur_host, api_path)
            else:
                url = cur_host + ("/" + api_path.lstrip("/"))

            headers["Referer"] = cur_host + "/zh"
            headers["Origin"] = cur_host

            for attempt in range(2):
                try:
                    req = urllib.request.Request(url, headers=headers)
                    with self.opener.open(req, timeout=timeout) as resp:
                        raw = resp.read()
                        enc = getattr(resp, "headers", {}).get("Content-Encoding", "")
                        if raw.startswith(b"\x1f\x8b") or enc == "gzip":
                            raw = gzip.decompress(raw)
                        elif enc == "deflate":
                            try:
                                raw = zlib.decompress(raw)
                            except Exception:
                                raw = zlib.decompress(raw, -zlib.MAX_WBITS)
                        data = json.loads(raw.decode("utf-8", errors="ignore"))
                        if data:
                            self._host_idx = idx
                            self.baseHost = cur_host
                            return data
                except Exception:
                    if attempt == 0:
                        continue

        if self._update_live_host():
            return self._fetch_api(api_path, timeout=timeout)

        return {}

    def _format_poster(self, raw_url):
        if not raw_url:
            return ""
        pic = raw_url.strip()
        if pic.startswith("//"):
            pic = "https:" + pic
        elif pic.startswith("/"):
            pic = self.staticHost + pic
        img_tail = "@Referer=%s/&User-Agent=%s" % (self.baseHost, quote(self._ua))
        return pic + img_tail

    def homeContent(self, filter):
        classes = [
            {"type_name": "🔥 最近更新", "type_id": "api@@latest"},
            {"type_name": "📈 热门影片", "type_id": "api@@hot"},
            {"type_name": "✨ 新片上市", "type_id": "api@@new-releases"},
            {"type_name": "🔞 无码影片", "type_id": "api@@uncensored"},
            {"type_name": "🈵 有码影片", "type_id": "api@@censored"},
            {"type_name": "🔤 字幕专区", "type_id": "api@@subtitle"},
            {"type_name": "💎 4K 超高清", "type_id": "api@@4k"},
            {"type_name": "📂 类型大全", "type_id": "folder@@genres"},
            {"type_name": "📂 演员大全", "type_id": "folder@@stars"},
            {"type_name": "📂 片商大全", "type_id": "folder@@studios"},
            {"type_name": "📂 番号系列", "type_id": "folder@@codes"}
        ]

        video_filters = [
            {
                "key": "sortBy",
                "name": "排序",
                "value": [
                    {"n": "最新", "v": "latest"},
                    {"n": "最热", "v": "popular"},
                    {"n": "评分", "v": "rating"},
                    {"n": "时长", "v": "duration"}
                ]
            },
            {
                "key": "subtitles",
                "name": "字幕",
                "value": [
                    {"n": "全部", "v": ""},
                    {"n": "中文字幕", "v": "true"}
                ]
            },
            {
                "key": "resolution",
                "name": "画质",
                "value": [
                    {"n": "全部", "v": ""},
                    {"n": "4K超高清", "v": "4k"}
                ]
            }
        ]

        folder_sort_filters = [
            {
                "key": "sort",
                "name": "排序",
                "value": [
                    {"n": "最热", "v": "popular"},
                    {"n": "名称", "v": "name"},
                    {"n": "数量", "v": "movies"}
                ]
            }
        ]

        filters = {
            "api@@latest": video_filters,
            "api@@hot": video_filters,
            "api@@new-releases": video_filters,
            "api@@uncensored": video_filters,
            "api@@censored": video_filters,
            "api@@subtitle": video_filters,
            "api@@4k": video_filters,
            "folder@@genres": folder_sort_filters,
            "folder@@studios": folder_sort_filters,
            "folder@@codes": folder_sort_filters,
            "folder@@stars": [
                {
                    "key": "gender",
                    "name": "性别",
                    "value": [
                        {"n": "女优", "v": "2"},
                        {"n": "男优", "v": "1"}
                    ]
                },
                {
                    "key": "sort",
                    "name": "排序",
                    "value": [
                        {"n": "最热", "v": "popular"},
                        {"n": "最新", "v": "latest"},
                        {"n": "数量", "v": "movies"},
                        {"n": "名称", "v": "name"}
                    ]
                }
            ]
        }
        return {"class": classes, "filters": filters}

    def homeVideoContent(self):
        res = self._fetch_api("/api/movies?category=latest&sortBy=latest&limit=20&page=1&locale=zh")
        movies = (res.get("data") or {}).get("movies") or []
        v_list = []
        for m in movies:
            cid = str(m.get("id", "")).strip().lower()
            if not cid or cid.isdigit():
                continue
            dur = format_seconds(m.get("videoLength", 0))
            v_list.append({
                "vod_id": cid,
                "vod_name": m.get("title") or cid.upper(),
                "vod_pic": self._format_poster(m.get("localImg") or m.get("img")),
                "vod_remarks": "ZakaTV | %s" % dur if dur else "ZakaTV",
                "style": {"type": "rect", "ratio": 1.42}
            })
        return {"list": v_list}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if str(pg).isdigit() else 1
        extend = extend or {}

        if str(tid).startswith("folder@@"):
            f_type = tid.replace("folder@@", "")

            if f_type == "stars":
                gender = extend.get("gender", "2")
                sort_type = extend.get("sort", "popular")

                query_parts = [
                    "page=%d" % page,
                    "limit=24",
                    "sort=%s" % sort_type,
                    "locale=zh"
                ]
                if gender:
                    query_parts.append("gender=%s" % gender)

                api_url = "/api/stars?" + "&".join(query_parts)
                res = self._fetch_api(api_url)
                data_obj = res.get("data") or {}
                stars = data_obj.get("stars") or (res.get("data") if isinstance(res.get("data"), list) else [])
                v_list = []
                for s in stars:
                    s_id = str(s.get("id", "")).strip()
                    base_name = s.get("name") or s.get("originalName") or s.get("nameJp") or ""
                    if not base_name:
                        continue
                    count = s.get("movieCount") or s.get("movie_count") or ""
                    display_name = "%s (%s部)" % (base_name, count) if count else base_name
                    remarks = "ZakaTV | %s部" % count if count else "ZakaTV"
                    
                    raw_avatar = s.get("localAvatar") or s.get("avatar") or s.get("localImg") or s.get("img")
                    avatar = self._format_poster(raw_avatar) if raw_avatar else generate_color_card(base_name)

                    v_list.append({
                        "vod_id": "subfolder@@star@@%s@@sortBy=popular@@subtitles=@@resolution=@@name=%s" % (s_id, quote(base_name)),
                        "vod_name": display_name,
                        "vod_pic": avatar,
                        "vod_remarks": remarks,
                        "vod_tag": "folder",
                        "style": {"type": "oval", "ratio": 1.0}
                    })

                total_pages = (data_obj.get("pagination") or {}).get("totalPages", page + 1 if len(v_list) >= 24 else page)
                return {
                    "page": page,
                    "pagecount": total_pages,
                    "limit": len(v_list),
                    "total": 5487,
                    "list": v_list
                }

            elif f_type == "genres":
                sort_type = extend.get("sort", "popular")
                api_url = "/api/genres?limit=100&sort=%s&locale=zh-CN" % sort_type
                res = self._fetch_api(api_url)
                items = (res.get("data") or {}).get("genres") or []
                v_list = []
                for g in items:
                    g_id = str(g.get("id", ""))
                    name = g.get("name") or g.get("originalName", "")
                    count = g.get("movieCount", "")
                    remarks = "ZakaTV | %s部" % count if count else "ZakaTV"
                    v_list.append({
                        "vod_id": "subfolder@@genre@@%s@@sortBy=latest@@subtitles=@@resolution=@@name=%s" % (g_id, quote(name)),
                        "vod_name": name,
                        "vod_pic": generate_color_card(name),
                        "vod_remarks": remarks,
                        "vod_tag": "folder",
                        "style": {"type": "rect", "ratio": 1.78}
                    })
                return {"page": 1, "pagecount": 1, "limit": len(v_list), "total": len(v_list), "list": v_list}

            elif f_type == "studios":
                sort_type = extend.get("sort", "popular")
                api_url = "/api/studios?limit=100&sort=%s&locale=zh-CN" % sort_type
                res = self._fetch_api(api_url)
                studios = (res.get("data") or {}).get("studios") or []
                v_list = []
                for st in studios:
                    st_id = str(st.get("id", ""))
                    name = st.get("name", "")
                    count = st.get("movieCount") or st.get("movie_count") or ""
                    remarks = "ZakaTV | %s部" % count if count else "ZakaTV"
                    v_list.append({
                        "vod_id": "subfolder@@studio@@%s@@sortBy=latest@@subtitles=@@resolution=@@name=%s" % (st_id, quote(name)),
                        "vod_name": name,
                        "vod_pic": generate_color_card(name),
                        "vod_remarks": remarks,
                        "vod_tag": "folder",
                        "style": {"type": "rect", "ratio": 1.78}
                    })
                return {"page": 1, "pagecount": 1, "limit": len(v_list), "total": len(v_list), "list": v_list}

            elif f_type == "codes":
                sort_type = extend.get("sort", "popular")
                api_url = "/api/codes?limit=100&sort=%s&locale=zh-CN" % sort_type
                res = self._fetch_api(api_url)
                codes = (res.get("data") or {}).get("codes") or []
                v_list = []
                for cd in codes:
                    cd_code = str(cd.get("code") or cd.get("name", "")).strip().upper()
                    count = cd.get("movieCount") or cd.get("movie_count") or ""
                    remarks = "ZakaTV | %s部" % count if count else "ZakaTV"
                    v_list.append({
                        "vod_id": "subfolder@@code@@%s@@sortBy=latest@@subtitles=@@resolution=@@name=%s" % (cd_code, quote(cd_code)),
                        "vod_name": cd_code,
                        "vod_pic": generate_color_card(cd_code),
                        "vod_remarks": remarks,
                        "vod_tag": "folder",
                        "style": {"type": "rect", "ratio": 1.78}
                    })
                return {"page": 1, "pagecount": 1, "limit": len(v_list), "total": len(v_list), "list": v_list}

        if str(tid).startswith("subfolder@@"):
            parts = str(tid).split("@@")
            sub_type = parts[1]
            target_id = parts[2]
            
            p_dict = {
                "sortBy": "popular" if sub_type == "star" else "latest",
                "subtitles": "",
                "resolution": "",
                "name": target_id
            }
            for p in parts[3:]:
                if "=" in p:
                    k, v = p.split("=", 1)
                    p_dict[k] = unquote(v)

            curr_sort = p_dict["sortBy"]
            curr_sub = p_dict["subtitles"]
            curr_res = p_dict["resolution"]
            sub_name = p_dict["name"]

            api_params = [
                "page=%d" % page,
                "limit=40",
                "locale=zh",
                "sortBy=%s" % curr_sort
            ]
            if curr_sub == "true":
                api_params.append("subtitles=true")
            if curr_res == "4k":
                api_params.append("resolution=4k")

            if sub_type == "star":
                api_params.append("starId=%s" % target_id)
            elif sub_type == "genre":
                api_params.append("genreId=%s" % target_id)
            elif sub_type == "studio":
                api_params.append("studioId=%s" % target_id)
            elif sub_type == "code":
                api_params.append("code=%s" % quote(target_id))

            api_url = "/api/movies?" + "&".join(api_params)
            res = self._fetch_api(api_url)
            data_obj = res.get("data") or {}
            movies = data_obj.get("movies") or []

            v_list = []

            if page == 1:
                sort_next_map = {
                    "popular": ("latest", "最热", "最新"),
                    "latest": ("duration", "最新", "时长"),
                    "duration": ("popular", "时长", "最热")
                }
                next_sort, cur_s_n, next_s_n = sort_next_map.get(curr_sort, ("popular", curr_sort, "最热"))
                sort_tid = "subfolder@@%s@@%s@@sortBy=%s@@subtitles=%s@@resolution=%s@@name=%s" % (
                    sub_type, target_id, next_sort, curr_sub, curr_res, quote(sub_name)
                )
                v_list.append({
                    "vod_id": sort_tid,
                    "vod_name": "🔀 排序: %s (点击切换)" % cur_s_n,
                    "vod_pic": generate_color_card("排序:%s" % cur_s_n, is_ctrl=True),
                    "vod_remarks": "切至 %s" % next_s_n,
                    "vod_tag": "folder",
                    "style": {"type": "rect", "ratio": 1.42}
                })

                next_sub = "" if curr_sub == "true" else "true"
                cur_sub_n = "中文字幕" if curr_sub == "true" else "全部版本"
                next_sub_n = "全部版本" if curr_sub == "true" else "中文字幕"
                sub_tid = "subfolder@@%s@@%s@@sortBy=%s@@subtitles=%s@@resolution=%s@@name=%s" % (
                    sub_type, target_id, curr_sort, next_sub, curr_res, quote(sub_name)
                )
                v_list.append({
                    "vod_id": sub_tid,
                    "vod_name": "🔤 字幕: %s" % cur_sub_n,
                    "vod_pic": generate_color_card("%s" % cur_sub_n, is_ctrl=True),
                    "vod_remarks": "切至 %s" % next_sub_n,
                    "vod_tag": "folder",
                    "style": {"type": "rect", "ratio": 1.42}
                })

                next_res = "" if curr_res == "4k" else "4k"
                cur_res_n = "4K超清" if curr_res == "4k" else "全部画质"
                next_res_n = "全部画质" if curr_res == "4k" else "4K超清"
                res_tid = "subfolder@@%s@@%s@@sortBy=%s@@subtitles=%s@@resolution=%s@@name=%s" % (
                    sub_type, target_id, curr_sort, curr_sub, next_res, quote(sub_name)
                )
                v_list.append({
                    "vod_id": res_tid,
                    "vod_name": "💎 画质: %s" % cur_res_n,
                    "vod_pic": generate_color_card("%s" % cur_res_n, is_ctrl=True),
                    "vod_remarks": "切至 %s" % next_res_n,
                    "vod_tag": "folder",
                    "style": {"type": "rect", "ratio": 1.42}
                })

            for m in movies:
                cid = str(m.get("id", "")).strip().lower()
                if not cid or cid.isdigit():
                    continue
                dur = format_seconds(m.get("videoLength", 0))
                v_list.append({
                    "vod_id": cid,
                    "vod_name": m.get("title") or cid.upper(),
                    "vod_pic": self._format_poster(m.get("localImg") or m.get("img")),
                    "vod_remarks": "ZakaTV | %s" % dur if dur else "ZakaTV",
                    "style": {"type": "rect", "ratio": 1.42}
                })

            total_pages = (data_obj.get("pagination") or {}).get("totalPages", page + 1 if len(movies) >= 40 else page)
            return {
                "page": page,
                "pagecount": total_pages,
                "limit": len(v_list),
                "total": 9999,
                "list": v_list
            }

        params = [
            "page=%d" % page,
            "limit=40",
            "locale=zh"
        ]

        sort_val = extend.get("sortBy", "latest")
        params.append("sortBy=%s" % sort_val)

        if extend.get("subtitles") == "true":
            params.append("subtitles=true")
        if extend.get("resolution") == "4k":
            params.append("resolution=4k")

        query_tail = "&".join(params)
        cat = tid.replace("api@@", "") if str(tid).startswith("api@@") else "latest"
        api_query = "/api/movies?category=%s&%s" % (cat, query_tail)

        res = self._fetch_api(api_query)
        data_obj = res.get("data") or {}
        movies = data_obj.get("movies") or []
        v_list = []
        for m in movies:
            cid = str(m.get("id", "")).strip().lower()
            if not cid or cid.isdigit():
                continue
            dur = format_seconds(m.get("videoLength", 0))
            v_list.append({
                "vod_id": cid,
                "vod_name": m.get("title") or cid.upper(),
                "vod_pic": self._format_poster(m.get("localImg") or m.get("img")),
                "vod_remarks": "ZakaTV | %s" % dur if dur else "ZakaTV",
                "style": {"type": "rect", "ratio": 1.42}
            })

        total_pages = (data_obj.get("pagination") or {}).get("totalPages", page + 1 if len(v_list) >= 40 else page)
        return {
            "page": page,
            "pagecount": total_pages,
            "limit": len(v_list),
            "total": 9999,
            "list": v_list
        }

    def detailContent(self, ids):
        raw_id = ids[0] if isinstance(ids, (list, tuple)) else str(ids)

        if str(raw_id).startswith("subfolder@@"):
            return self.categoryContent(raw_id, 1, None, None)

        code = str(raw_id).strip().lower()
        res = self._fetch_api("/api/movies/%s" % code)
        data = res.get("data") or {}

        title = data.get("title", code.upper())
        poster = self._format_poster(data.get("localImg") or data.get("img"))

        actors_list = data.get("stars") or []
        actor_names = [clean_html_text(a.get("name", "")) for a in actors_list if a.get("name")]
        actor_str = ", ".join(actor_names) if actor_names else self.brandActor

        genres_list = data.get("genres") or []
        genre_names = [clean_html_text(g.get("name", "")) for g in genres_list if g.get("name")]
        type_str = " / ".join(genre_names) if genre_names else "情色"

        dur_str = format_seconds(data.get("videoLength", 0))
        remarks = "ZakaTV | %s" % dur_str if dur_str else "ZakaTV"

        desc = data.get("description") or title
        full_content = (
            "【🔥 官方交流群: %s】\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "番号: %s\n"
            "片名: %s\n"
            "时长: %s\n"
            "发行: %s\n"
            "简介: %s"
        ) % (self.tgGroup, code.upper(), title, dur_str, str(data.get("date", ""))[:10], desc)

        video_sources = data.get("videoSources") or []
        play_lines = []
        label_map = {
            "raw_1080p": "正片 1080P",
            "raw_720p": "高清 720P",
            "raw_480p": "标清 480P",
            "raw_240p": "流畅 240P"
        }

        for vs in video_sources:
            s_url = vs.get("url", "")
            s_type = vs.get("type", "")
            if s_url:
                t_label = label_map.get(s_type, s_type or "默认线路")
                play_lines.append("%s$%s" % (t_label, s_url))

        if not play_lines:
            if data.get("localM3u8Path4k"):
                play_lines.append("超清 4K$%s" % data["localM3u8Path4k"])
            if data.get("localM3u8Path"):
                play_lines.append("高清 1080P$%s" % data["localM3u8Path"])
            if data.get("localM3u8PathUc"):
                play_lines.append("无码专线$%s" % data["localM3u8PathUc"])

        preview_url = data.get("previewVideoUrl")
        if preview_url:
            full_preview = self.staticHost + preview_url if not preview_url.startswith("http") else preview_url
            play_lines.append("精彩预告$%s" % full_preview)

        play_url_str = "#".join(play_lines) if play_lines else "暂无可用线路$http://127.0.0.1"

        vod_detail = {
            "vod_id": code,
            "vod_name": title,
            "vod_pic": poster,
            "type_name": type_str,
            "vod_year": str(data.get("date", ""))[:4],
            "vod_area": "日本",
            "vod_remarks": remarks,
            "vod_actor": actor_str,
            "vod_director": self.brandDirector,
            "vod_content": full_content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"),
            "vod_play_from": "ZakaTV专线",
            "vod_play_url": play_url_str
        }

        return {"list": [vod_detail]}

    def playerContent(self, flag, id, vipFlags):
        play_url = str(id).strip()
        headers = {
            "User-Agent": self._ua,
            "Referer": self.baseHost + "/zh",
            "Origin": self.baseHost
        }
        return {
            "parse": 0,
            "jx": 0,
            "url": play_url,
            "header": headers
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if str(pg).isdigit() else 1
        kw = quote(key.strip())
        api_url = "/api/movies?q=%s&sortBy=latest&limit=40&page=%d&locale=zh" % (kw, page)

        res = self._fetch_api(api_url)
        data_obj = res.get("data") or {}
        movies = data_obj.get("movies") or []
        v_list = []
        for m in movies:
            cid = str(m.get("id", "")).strip().lower()
            if not cid or cid.isdigit():
                continue
            dur = format_seconds(m.get("videoLength", 0))
            v_list.append({
                "vod_id": cid,
                "vod_name": m.get("title") or cid.upper(),
                "vod_pic": self._format_poster(m.get("localImg") or m.get("img")),
                "vod_remarks": "ZakaTV | %s" % dur if dur else "ZakaTV",
                "style": {"type": "rect", "ratio": 1.42}
            })

        total_pages = (data_obj.get("pagination") or {}).get("totalPages", page + 1 if len(v_list) >= 40 else page)
        return {
            "page": page,
            "pagecount": total_pages,
            "limit": len(v_list),
            "total": 9999,
            "list": v_list
        }

    def action(self, action):
        return {"msg": "ok"}

    def liveContent(self):
        return ""

    def localProxy(self, params):
        return [404, "text/plain; charset=utf-8", "Proxy not configured"]

    def destroy(self):
        self.options = {}
