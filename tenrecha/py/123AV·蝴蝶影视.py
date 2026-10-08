#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 蜂蜜影视（FongMi TV）原生 Python 爬虫 - 123AV 生产实战终极版 (Release)
# 规范对齐: 全标准库、无 f-string、全分类 1:1 子筛选联动、Folder 目录穿透、零死锁分页

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
        self.siteUrl = "https://123av.com/cn"
        self.baseHost = "https://123av.com"
        self.tgGroup = "https://t.me/tvshare23"
        self.brandActor = "🦋 TG群: @tvshare23"
        self.brandDirector = "🦋 蝴蝶影视"
        self._ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        self.options = {}

        self.palette = [
            ("19bcd4", "ffffff"),
            ("5b6ac8", "ffffff"),
            ("26a69a", "ffffff"),
            ("9b59b6", "ffffff"),
            ("ff3b6f", "ffffff"),
            ("8ec051", "ffffff"),
            ("ffbe1a", "ffffff"),
            ("ff5733", "ffffff"),
            ("3498db", "ffffff"),
            ("e91e63", "ffffff")
        ]

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
        return True

    def getName(self):
        return "123AV·蝴蝶影视"

    def isVideoFormat(self, url):
        low = (url or "").lower()
        return any(k in low for k in (".m3u8", ".mp4", ".flv", ".mkv", ".avi", ".ts", ".mpd", "index.png"))

    def manualVideoCheck(self):
        return False

    def _get_color_card(self, title):
        char = title.strip()[:1].upper() if title.strip() else "A"
        idx = abs(hash(title)) % len(self.palette)
        bg_col, fg_col = self.palette[idx]
        return "https://dummyimage.com/640x360/%s/%s.png&text=%s" % (bg_col, fg_col, quote(char))

    def _fetch(self, target_url, referer=""):
        if not target_url:
            return {"code": 0, "text": "", "bytes": b"", "err": "", "final_url": ""}
        if target_url.startswith("//"):
            target_url = "https:" + target_url
        elif target_url.startswith("/"):
            target_url = self.baseHost + target_url

        headers = {
            "User-Agent": self._ua,
            "Referer": referer if referer else (self.baseHost + "/cn"),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Sec-Ch-Ua": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1"
        }

        for attempt in range(2):
            try:
                req = urllib.request.Request(target_url, headers=headers)
                with self.opener.open(req, timeout=15) as resp:
                    code = resp.getcode()
                    final_url = resp.geturl()
                    raw = resp.read()
                    enc = getattr(resp, "headers", {}).get("Content-Encoding", "").lower()
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
            except Exception as e:
                if attempt == 0:
                    continue
                return {"code": -1, "text": "", "bytes": b"", "err": str(e), "final_url": target_url}

        return {"code": -1, "text": "", "bytes": b"", "err": "timeout", "final_url": target_url}

    def homeContent(self, filter):
        classes = [
            {"type_name": "🔥 热门", "type_id": "cn/hot"},
            {"type_name": "✨ 最新", "type_id": "cn/new"},
            {"type_name": "🕒 最近", "type_id": "cn/recent"},
            {"type_name": "🎯 有码", "type_id": "cn/censored"},
            {"type_name": "💎 无码", "type_id": "cn/uncensored"},
            {"type_name": "⚠️ 无码泄露", "type_id": "cn/uncensored-leaked"},
            {"type_name": "📈 今日趋势", "type_id": "cn/all?sort=today"},
            {"type_name": "📊 本周趋势", "type_id": "cn/all?sort=week"},
            {"type_name": "📉 本月趋势", "type_id": "cn/all?sort=month"},
            {"type_name": "💃 女演员", "type_id": "cn/actresses"},
            {"type_name": "🏷️ 类别", "type_id": "cn/genres"},
            {"type_name": "🏢 制作商", "type_id": "cn/makers"},
            {"type_name": "🎬 系列", "type_id": "cn/series"},
            {"type_name": "SIRO", "type_id": "cn/tags/siro"},
            {"type_name": "LUXU", "type_id": "cn/tags/259luxu"},
            {"type_name": "200GANA", "type_id": "cn/tags/200gana"},
            {"type_name": "PRESTIGE", "type_id": "cn/tags/prestige-premium"},
            {"type_name": "ORECO", "type_id": "cn/tags/230oreco"},
            {"type_name": "S-CUTE", "type_id": "cn/makers/s-cute"},
            {"type_name": "ARA", "type_id": "cn/tags/261ara"},
            {"type_name": "390JAC", "type_id": "cn/tags/390jac"},
            {"type_name": "FC2", "type_id": "cn/makers/fc2"},
            {"type_name": "HEYZO", "type_id": "cn/makers/heyzo"},
            {"type_name": "1pondo", "type_id": "cn/makers/1pondo"},
            {"type_name": "Caribbeancom", "type_id": "cn/makers/caribbeancom"},
            {"type_name": "10musume", "type_id": "cn/makers/10musume"},
            {"type_name": "Pacopacomama", "type_id": "cn/makers/pacopacomama"},
            {"type_name": "Tokyo Hot", "type_id": "cn/makers/tokyo-hot"},
            {"type_name": "XXX-AV", "type_id": "cn/makers/xxx-av"}
        ]

        result = {"class": classes}

        if filter:
            video_filters = [
                {
                    "key": "type",
                    "name": "类型",
                    "init": "",
                    "value": [
                        {"n": "全部", "v": ""},
                        {"n": "有码", "v": "censored"},
                        {"n": "无码", "v": "uncensored"},
                        {"n": "无码泄露", "v": "uncensored-leaked"}
                    ]
                },
                {
                    "key": "year",
                    "name": "年份",
                    "init": "",
                    "value": [
                        {"n": "全部", "v": ""},
                        {"n": "2026", "v": "2026"},
                        {"n": "2025", "v": "2025"},
                        {"n": "2024", "v": "2024"},
                        {"n": "2023", "v": "2023"},
                        {"n": "2022", "v": "2022"},
                        {"n": "2021", "v": "2021"},
                        {"n": "2020", "v": "2020"},
                        {"n": "2019", "v": "2019"},
                        {"n": "2018", "v": "2018"},
                        {"n": "2017", "v": "2017"},
                        {"n": "2016", "v": "2016"},
                        {"n": "2015", "v": "2015"},
                        {"n": "2014", "v": "2014"},
                        {"n": "2013", "v": "2013"},
                        {"n": "2012", "v": "2012"},
                        {"n": "2011", "v": "2011"},
                        {"n": "2010", "v": "2010"},
                        {"n": "2009", "v": "2009"},
                        {"n": "2008", "v": "2008"}
                    ]
                },
                {
                    "key": "actress",
                    "name": "女演员",
                    "init": "",
                    "value": [
                        {"n": "全部", "v": ""},
                        {"n": "单人", "v": "single"},
                        {"n": "多人", "v": "multiple"}
                    ]
                }
            ]

            actress_filters = [
                {
                    "key": "height",
                    "name": "身高",
                    "init": "",
                    "value": [
                        {"n": "任意身高", "v": ""},
                        {"n": "130-134cm", "v": "130-134"},
                        {"n": "135-139cm", "v": "135-139"},
                        {"n": "140-144cm", "v": "140-144"},
                        {"n": "145-149cm", "v": "145-149"},
                        {"n": "150-154cm", "v": "150-154"},
                        {"n": "155-159cm", "v": "155-159"},
                        {"n": "160-164cm", "v": "160-164"},
                        {"n": "165-169cm", "v": "165-169"},
                        {"n": "170-174cm", "v": "170-174"},
                        {"n": "175-179cm", "v": "175-179"},
                        {"n": "180-184cm", "v": "180-184"},
                        {"n": "185-189cm", "v": "185-189"},
                        {"n": "190-194cm", "v": "190-194"}
                    ]
                },
                {
                    "key": "cup",
                    "name": "罩杯",
                    "init": "",
                    "value": [
                        {"n": "任意罩杯", "v": ""},
                        {"n": "A", "v": "A"}, {"n": "B", "v": "B"}, {"n": "C", "v": "C"},
                        {"n": "D", "v": "D"}, {"n": "E", "v": "E"}, {"n": "F", "v": "F"},
                        {"n": "G", "v": "G"}, {"n": "H", "v": "H"}, {"n": "I", "v": "I"},
                        {"n": "J", "v": "J"}, {"n": "K", "v": "K"}, {"n": "L", "v": "L"},
                        {"n": "M", "v": "M"}, {"n": "N", "v": "N"}, {"n": "O", "v": "O"},
                        {"n": "P", "v": "P"}, {"n": "Q", "v": "Q"}, {"n": "Z", "v": "Z"}
                    ]
                },
                {
                    "key": "age",
                    "name": "年龄",
                    "init": "",
                    "value": [
                        {"n": "任意年龄", "v": ""},
                        {"n": "< 20岁", "v": "0-19"},
                        {"n": "20-24岁", "v": "20-24"},
                        {"n": "25-29岁", "v": "25-29"},
                        {"n": "30-34岁", "v": "30-34"},
                        {"n": "35-39岁", "v": "35-39"},
                        {"n": "40-44岁", "v": "40-44"},
                        {"n": "45-49岁", "v": "45-49"},
                        {"n": "50-54岁", "v": "50-54"},
                        {"n": "> 60岁", "v": "60-99"}
                    ]
                },
                {
                    "key": "sort",
                    "name": "排序",
                    "init": "count",
                    "value": [
                        {"n": "视频数量", "v": "count"},
                        {"n": "姓名 (A–Z)", "v": "name"},
                        {"n": "最受欢迎", "v": "views"},
                        {"n": "今日观看", "v": "today"},
                        {"n": "每周观看", "v": "week"},
                        {"n": "每月观看", "v": "month"},
                        {"n": "关注最多", "v": "favorited"}
                    ]
                }
            ]

            collection_filters = [
                {
                    "key": "sort",
                    "name": "排序",
                    "init": "count",
                    "value": [
                        {"n": "视频数量", "v": "count"},
                        {"n": "姓名 (A–Z)", "v": "name"},
                        {"n": "最受欢迎", "v": "views"},
                        {"n": "今日观看", "v": "today"},
                        {"n": "每周观看", "v": "week"},
                        {"n": "每月观看", "v": "month"}
                    ]
                }
            ]

            filters = {}
            for c in classes:
                cid = c["type_id"]
                if cid == "cn/actresses":
                    filters[cid] = actress_filters
                elif cid in ("cn/genres", "cn/makers", "cn/series"):
                    filters[cid] = collection_filters
                else:
                    filters[cid] = video_filters
            result["filters"] = filters

        return result

    def homeVideoContent(self):
        return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        raw_slug = str(tid).strip("/")
        page = int(pg) if pg else 1

        is_folder_request = raw_slug.startswith("folder/")
        slug = raw_slug[7:] if is_folder_request else raw_slug

        extend = extend if isinstance(extend, dict) else {}
        f_type = extend.get("type", "").strip()
        f_year = extend.get("year", "").strip()
        f_actress = extend.get("actress", "").strip()
        f_height = extend.get("height", "").strip()
        f_cup = extend.get("cup", "").strip()
        f_age = extend.get("age", "").strip()
        f_sort = extend.get("sort", "").strip()

        if "?" in slug:
            base_path, qs = slug.split("?", 1)
            params = qs.split("&")
        else:
            base_path = slug
            params = []

        if page > 1:
            params.append("page=%d" % page)
        if f_type: params.append("type=%s" % f_type)
        if f_year: params.append("year=%s" % f_year)
        if f_actress: params.append("actress=%s" % f_actress)
        if f_height: params.append("height=%s" % f_height)
        if f_cup: params.append("cup=%s" % f_cup)
        if f_age: params.append("age=%s" % f_age)
        if f_sort: params.append("sort=%s" % f_sort)

        full_url = "%s/%s" % (self.baseHost, base_path.lstrip("/"))
        if params:
            full_url = full_url + ("?" + "&".join(params))

        res = self._fetch(full_url, referer=self.siteUrl)
        html = res.get("text", "")
        vod_list = []

        main_html = html
        for kw in ('</header>', '</nav>', '<main', 'class="content"', 'class="grid"'):
            pos = html.find(kw)
            if pos != -1:
                main_html = html[pos:]
                break

        # 女演员一级索引: 正圆头像 + 完整信息
        if base_path == "cn/actresses":
            act_cards = main_html.split('class="actress"')
            if len(act_cards) <= 1:
                act_cards = main_html.split('class="actress ')

            for chunk in act_cards[1:]:
                link_m = re.search(r'href=["\'](/cn/actresses/[^"\']+)["\']', chunk, re.I)
                if not link_m:
                    continue
                act_href = link_m.group(1).strip().lstrip("/")

                pic_m = re.search(r'url\(["\']?(https?://[^"\'\)]+)["\']?\)', chunk, re.I)
                act_pic = pic_m.group(1).strip() if pic_m else ""

                name_m = re.search(r'<(?:h3|h4|div|span|a)[^>]*class=["\'][^"\']*name[^"\']*["\'][^>]*>([\s\S]*?)</', chunk, re.I)
                if not name_m:
                    name_m = re.search(r'title=["\']([^"\']+)["\']', chunk, re.I)
                act_name = re.sub(r'<[^>]+>', '', name_m.group(1)).strip() if name_m else act_href.split("/")[-1]

                nums = re.findall(r'>\s*([0-9,.]+[KMkm]?)\s*<', chunk)
                v_count = ""
                v_views = ""
                if nums:
                    v_count = nums[0].strip()
                    if len(nums) >= 2:
                        v_views = nums[1].strip()

                if v_count and v_views:
                    remarks = "%s部 · %s播" % (v_count, v_views)
                elif v_count:
                    remarks = "%s 部作品" % v_count
                else:
                    remarks = "女优专栏"

                vod_list.append({
                    "vod_id": "folder/" + act_href,
                    "vod_name": act_name,
                    "vod_pic": act_pic,
                    "vod_remarks": remarks,
                    "vod_tag": "folder",
                    "style": {"type": "oval", "ratio": 1.0}
                })

        # 类别专区
        elif base_path == "cn/genres":
            items = re.findall(r'<a[^>]+href=["\'](/cn/genres/[^"\']+)["\'][^>]*>([\s\S]*?)</a>', main_html, re.I)
            seen = set()
            for href, inner in items:
                if href in seen:
                    continue
                clean_raw = re.sub(r'<[^>]+>', '', inner).strip()
                clean_raw = re.sub(r'\s+', ' ', clean_raw)
                if not clean_raw or len(clean_raw) > 35:
                    continue

                seen.add(href)
                m = re.match(r'^(.*?)\s+([0-9,]+)$', clean_raw)
                if m:
                    c_title = m.group(1).strip()
                    c_badge = m.group(2).strip() + " 部"
                else:
                    c_title = clean_raw
                    c_badge = "类别专栏"

                vod_list.append({
                    "vod_id": "folder/" + href.strip().lstrip("/"),
                    "vod_name": c_title,
                    "vod_pic": self._get_color_card(c_title),
                    "vod_remarks": c_badge,
                    "vod_tag": "folder",
                    "style": {"type": "rect", "ratio": 1.78}
                })

        # 制作商专区
        elif base_path == "cn/makers":
            items = re.findall(r'<a[^>]+href=["\'](/cn/makers/[^"\']+)["\'][^>]*>([\s\S]*?)</a>', main_html, re.I)
            seen = set()
            for href, inner in items:
                if href in seen:
                    continue
                clean_raw = re.sub(r'<[^>]+>', '', inner).strip()
                clean_raw = re.sub(r'\s+', ' ', clean_raw)
                if not clean_raw or len(clean_raw) > 35:
                    continue

                seen.add(href)
                m = re.match(r'^(.*?)\s+([0-9,]+)$', clean_raw)
                if m:
                    c_title = m.group(1).strip()
                    c_badge = m.group(2).strip() + " 部"
                else:
                    c_title = clean_raw
                    c_badge = "制作商专栏"

                vod_list.append({
                    "vod_id": "folder/" + href.strip().lstrip("/"),
                    "vod_name": c_title,
                    "vod_pic": self._get_color_card(c_title),
                    "vod_remarks": c_badge,
                    "vod_tag": "folder",
                    "style": {"type": "rect", "ratio": 1.78}
                })

        # 系列专区
        elif base_path == "cn/series":
            items = re.findall(r'<a[^>]+href=["\'](/cn/series/[^"\']+)["\'][^>]*>([\s\S]*?)</a>', main_html, re.I)
            seen = set()
            for href, inner in items:
                if href in seen:
                    continue
                clean_raw = re.sub(r'<[^>]+>', '', inner).strip()
                clean_raw = re.sub(r'\s+', ' ', clean_raw)
                if not clean_raw or len(clean_raw) > 35:
                    continue

                seen.add(href)
                m = re.match(r'^(.*?)\s+([0-9,]+)$', clean_raw)
                if m:
                    c_title = m.group(1).strip()
                    c_badge = m.group(2).strip() + " 部"
                else:
                    c_title = clean_raw
                    c_badge = "系列专栏"

                vod_list.append({
                    "vod_id": "folder/" + href.strip().lstrip("/"),
                    "vod_name": c_title,
                    "vod_pic": self._get_color_card(c_title),
                    "vod_remarks": c_badge,
                    "vod_tag": "folder",
                    "style": {"type": "rect", "ratio": 1.78}
                })

        # 常规视频与二级展开视频海报
        else:
            chunks = main_html.split('class="card"')
            if len(chunks) <= 1:
                chunks = main_html.split('class="card ')

            for chunk in chunks[1:]:
                link_m = re.search(r'href=["\'](/cn/v/[^"\']+)["\']', chunk, re.I)
                if not link_m:
                    continue
                v_id = link_m.group(1).strip()

                title_m = re.search(r'<(?:h3|h4|div|a)[^>]*class=["\'][^"\']*title[^"\']*["\'][^>]*>([\s\S]*?)</', chunk, re.I)
                v_name = ""
                if title_m:
                    v_name = re.sub(r'<[^>]+>', '', title_m.group(1)).strip()
                if not v_name or v_name == "观看":
                    next_a = re.search(r'</a>\s*<a[^>]+href=["\']/cn/v/[^"\']+["\'][^>]*>([\s\S]*?)</a>', chunk, re.I)
                    if next_a:
                        v_name = re.sub(r'<[^>]+>', '', next_a.group(1)).strip()
                if not v_name or v_name == "观看":
                    v_name = v_id.split("/")[-1].upper()

                pic_m = re.search(r'<img[^>]+src=["\'](https?://[^"\']+)["\']', chunk, re.I)
                v_pic = pic_m.group(1).strip() if pic_m else ""

                dur_m = re.search(r'class="card__dur">([\s\S]*?)</span>', chunk, re.I)
                v_dur = dur_m.group(1).strip() if dur_m else "蝴蝶影视"

                vod_list.append({
                    "vod_id": v_id,
                    "vod_name": v_name,
                    "vod_pic": v_pic,
                    "vod_remarks": v_dur if v_dur != "0:00" else "蝴蝶影视",
                    "style": {"type": "rect", "ratio": 1.78}
                })

        page_count = page + 1 if len(vod_list) >= 12 else page
        return {
            "page": page,
            "pagecount": page_count if page_count > 0 else 1,
            "limit": 24,
            "total": 9999,
            "list": vod_list
        }

    def detailContent(self, ids):
        raw_id = ids[0] if isinstance(ids, (list, tuple)) else str(ids)
        real_id = raw_id[7:] if raw_id.startswith("folder/") else raw_id
        target_url = real_id if real_id.startswith("http") else (self.baseHost + "/" + real_id.lstrip("/"))

        res = self._fetch(target_url, referer=self.siteUrl)
        html = res.get("text", "")

        title_m = re.search(r'<h1[^>]*>([\s\S]*?)</h1>', html, re.I)
        vod_name = re.sub(r'<[^>]+>', '', title_m.group(1)).strip() if title_m else real_id.split("/")[-1].upper()

        pic_m = re.search(r'poster=([^\s&"\']+)', html)
        if pic_m:
            vod_pic = unquote(pic_m.group(1))
        else:
            pic_m2 = re.search(r'url\(["\']?(https?://[^"\'\)]+cover\.[^"\'\)]+)["\']?\)', html, re.I)
            vod_pic = pic_m2.group(1).strip() if pic_m2 else ""

        episodes = []
        player_json_m = re.search(r'x-data="player\(JSON\.parse\(\'([\s\S]*?)\'\)', html)
        if player_json_m:
            raw_json_str = player_json_m.group(1)
            try:
                clean_json_str = raw_json_str.encode("utf-8").decode("unicode_escape").replace(r"\/", "/")
                parsed_eps = json.loads(clean_json_str)
                if isinstance(parsed_eps, list):
                    for ep in parsed_eps:
                        ep_name = str(ep.get("name", "正片")).strip().replace("$", "").replace("#", "")
                        ep_url = ep.get("url", "").strip()
                        if ep_url:
                            episodes.append("%s$%s" % (ep_name, ep_url))
            except Exception:
                pass

        if not episodes:
            urls = re.findall(r'["\'](https?:\\/\\/[^"\']*(?:javplayer|player|embed|\.m3u8)[^"\']*)["\']', html)
            for idx, u in enumerate(urls):
                clean_u = u.replace(r"\/", "/")
                episodes.append("线路%d$%s" % (idx + 1, clean_u))

        play_url_str = "#".join(episodes) if episodes else "正片$%s" % target_url

        full_desc = (
            "【🔥 官方交流群: %s】\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "蝴蝶影视全能力极速引擎已接入！本片支持多选集超清秒播。"
        ) % self.tgGroup

        return {
            "list": [{
                "vod_id": raw_id,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_actor": self.brandActor,
                "vod_director": self.brandDirector,
                "vod_remarks": "蝴蝶影视",
                "vod_content": full_desc,
                "vod_play_from": "蝴蝶专线",
                "vod_play_url": play_url_str
            }]
        }

    def playerContent(self, flag, id, vipFlags):
        raw_url = str(id).strip()

        if any(raw_url.lower().endswith(ext) for ext in (".m3u8", ".mp4", ".flv", ".mpd", "index.png")):
            return {
                "parse": 0,
                "playUrl": "",
                "url": raw_url,
                "header": {
                    "User-Agent": self._ua,
                    "Referer": self.siteUrl + "/"
                }
            }

        if "javplayer.cc" in raw_url or "/e/" in raw_url:
            res = self._fetch(raw_url, referer=self.siteUrl)
            inner_html = res.get("text", "")

            m3u8_m = re.search(r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', inner_html)
            if m3u8_m:
                return {
                    "parse": 0,
                    "playUrl": "",
                    "url": m3u8_m.group(1).replace(r"\/", "/"),
                    "header": {
                        "User-Agent": self._ua,
                        "Referer": raw_url
                    }
                }

            mp4_matches = re.findall(r'["\'](https?://[^"\']+\.mp4[^"\']*)["\']', inner_html)
            for mp4 in mp4_matches:
                if not any(k in mp4.lower() for k in ("sample", "preview", "trailer")):
                    return {
                        "parse": 0,
                        "playUrl": "",
                        "url": mp4.replace(r"\/", "/"),
                        "header": {
                            "User-Agent": self._ua,
                            "Referer": raw_url
                        }
                    }

        return {
            "parse": 1,
            "playUrl": "",
            "url": raw_url,
            "header": {
                "User-Agent": self._ua,
                "Referer": self.siteUrl + "/"
            }
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        query_key = quote(key.strip())
        target_url = "%s/cn/search?kw=%s&page=%d" % (self.baseHost, query_key, page)

        res = self._fetch(target_url, referer=self.siteUrl)
        html = res.get("text", "")

        vod_list = []
        chunks = html.split('class="card"')
        if len(chunks) <= 1:
            chunks = html.split('class="card ')

        for chunk in chunks[1:]:
            link_m = re.search(r'href=["\'](/cn/v/[^"\']+)["\']', chunk, re.I)
            if not link_m:
                continue
            v_id = link_m.group(1).strip()

            title_m = re.search(r'<(?:h3|h4|div|a)[^>]*class=["\'][^"\']*title[^"\']*["\'][^>]*>([\s\S]*?)</', chunk, re.I)
            v_name = ""
            if title_m:
                v_name = re.sub(r'<[^>]+>', '', title_m.group(1)).strip()
            if not v_name or v_name == "观看":
                next_a = re.search(r'</a>\s*<a[^>]+href=["\']/cn/v/[^"\']+["\'][^>]*>([\s\S]*?)</a>', chunk, re.I)
                if next_a:
                    v_name = re.sub(r'<[^>]+>', '', next_a.group(1)).strip()
            if not v_name or v_name == "观看":
                v_name = v_id.split("/")[-1].upper()

            pic_m = re.search(r'<img[^>]+src=["\'](https?://[^"\']+)["\']', chunk, re.I)
            v_pic = pic_m.group(1).strip() if pic_m else ""

            dur_m = re.search(r'class="card__dur">([\s\S]*?)</span>', chunk, re.I)
            v_dur = dur_m.group(1).strip() if dur_m else "蝴蝶影视"

            vod_list.append({
                "vod_id": v_id,
                "vod_name": v_name,
                "vod_pic": v_pic,
                "vod_remarks": v_dur if v_dur != "0:00" else "蝴蝶影视",
                "style": {"type": "rect", "ratio": 1.78}
            })

        page_count = page + 1 if len(vod_list) >= 12 else page
        return {
            "page": page,
            "pagecount": page_count if page_count > 0 else 1,
            "limit": 24,
            "total": 9999,
            "list": vod_list
        }

    def action(self, action):
        return {"msg": "OK"}

    def liveContent(self):
        return ""

    def localProxy(self, params):
        url = params.get("url", "")
        if not url:
            return [404, "text/plain; charset=utf-8", "Missing url parameter"]
        res = self._fetch(url, referer=self.siteUrl)
        return [res.get("code", 200), "image/jpeg", res.get("bytes", b"")]

    def destroy(self):
        self.options = {}