#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 蜂蜜影视（FongMi TV）原生 Python 蜘蛛 - XVideos 生产级正式版（海报视频数精准还原版）

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
        self.siteUrl = "https://www.xvideos.com"
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
        return True

    def getName(self):
        return "XVideos·蝴蝶影视"

    def isVideoFormat(self, url):
        low = (url or "").lower()
        return any(k in low for k in (".m3u8", ".mp4", ".flv", ".mkv", ".avi", ".ts", ".mpd", "index.png"))

    def manualVideoCheck(self):
        return False

    def _fetch(self, target_url, referer="", data=None, is_post=False):
        if not target_url:
            return {"code": 0, "text": "", "bytes": b"", "err": "", "final_url": ""}
        if target_url.startswith("//"):
            target_url = "https:" + target_url
        elif target_url.startswith("/"):
            target_url = self.siteUrl + target_url

        headers = {
            "User-Agent": self._ua,
            "Referer": referer if referer else (self.siteUrl + "/"),
            "Accept": "application/json, text/javascript, */*; q=0.01" if is_post else "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive"
        }
        if is_post:
            headers["X-Requested-With"] = "XMLHttpRequest"

        last_err = ""
        for attempt in range(2):
            try:
                post_bytes = None
                if is_post:
                    post_bytes = b"" if data is None else (data.encode("utf-8") if isinstance(data, str) else data)
                req = urllib.request.Request(target_url, data=post_bytes, headers=headers)
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
                    return {"code": code, "text": text, "bytes": raw, "err": "", "final_url": final_url}
            except urllib.error.HTTPError as e:
                last_err = "HTTP %s" % e.code
                if e.code in (451, 403, 429) and attempt == 0:
                    continue
                err_raw = ""
                try:
                    err_raw = e.read().decode("utf-8", errors="ignore")
                except Exception:
                    pass
                return {"code": e.code, "text": err_raw, "bytes": b"", "err": str(e), "final_url": target_url}
            except Exception as e:
                last_err = str(e)
                if attempt == 0:
                    continue
                return {"code": -1, "text": "", "bytes": b"", "err": str(e), "final_url": target_url}

        return {"code": -1, "text": "", "bytes": b"", "err": last_err, "final_url": target_url}

    def _get_color_block_pic(self, text):
        colors = ["2B3A4A", "3E2723", "1A237E", "004D40", "BF360C", "311B92", "4A148C"]
        c = colors[sum([ord(ch) for ch in text]) % len(colors)]
        t = quote(text[:12] if text else "XVideos")
        return "https://dummyimage.com/640x360/%s/ffffff.png&text=%s" % (c, t)

    def homeContent(self, filter):
        result = {
            "class": [
                {"type_name": "▶ 最佳影片", "type_id": "nav_best"},
                {"type_name": "🏷 分类", "type_id": "nav_tags"},
                {"type_name": "📺 频道", "type_id": "nav_channels"},
                {"type_name": "⭐ 色情明星", "type_id": "nav_pornstars"}
            ]
        }

        if filter:
            month_filters = [{"n": "当前月份/最新", "v": ""}]
            cn_months = ["一月", "二月", "三月", "四月", "五月", "六月", "七月", "八月", "九月", "十月", "十一月", "十二月"]
            for m in range(8, 0, -1):
                month_filters.append({"n": "%s 2026" % cn_months[m-1], "v": "/%04d-%02d" % (2026, m)})
            for y in range(2025, 2020, -1):
                for m in range(12, 0, -1):
                    month_filters.append({"n": "%s %d" % (cn_months[m-1], y), "v": "/%04d-%02d" % (y, m)})

            best_filters = [
                {
                    "key": "month",
                    "name": "历史月份",
                    "init": "",
                    "value": month_filters
                }
            ]

            category_options = [
                {"n": "說中文的色情", "v": "/lang/chinese"},
                {"n": "3d", "v": "/tags/3d-animation"},
                {"n": "阿拉伯", "v": "/c/Arab-159"},
                {"n": "按摩", "v": "/c/Massage-61"},
                {"n": "變性", "v": "/c/Transsexual-18"},
                {"n": "成熟", "v": "/c/Mature-38"},
                {"n": "出軌背叛/火辣妻子", "v": "/c/Cuckold-237"},
                {"n": "調教", "v": "/c/Femdom-235"},
                {"n": "肛交", "v": "/c/Anal-12"},
                {"n": "褐髮", "v": "/c/Brunette-25"},
                {"n": "黑人", "v": "/c/Black_Woman-30"},
                {"n": "紅髮", "v": "/c/Redhead-31"},
                {"n": "家庭亂搞", "v": "/c/Fucked_Up_Family-81"},
                {"n": "金髮", "v": "/c/Blonde-20"},
                {"n": "巨屌", "v": "/c/Big_Cock-34"},
                {"n": "巨乳", "v": "/c/Big_Tits-23"},
                {"n": "巨臀", "v": "/c/Big_Ass-24"},
                {"n": "口交", "v": "/c/Blowjob-15"},
                {"n": "拉丁裔", "v": "/c/Latina-16"},
                {"n": "辣媽", "v": "/c/MILF-27"},
                {"n": "裂開", "v": "/c/Creampie-14"},
                {"n": "麻豆", "v": "/tags/madou"},
                {"n": "美臀", "v": "/c/Small_Tits-32"},
                {"n": "男同", "v": "/c/Gay-17"},
                {"n": "女同", "v": "/c/Lesbian-26"},
                {"n": "胖女", "v": "/c/BBW-21"},
                {"n": "噴出", "v": "/c/Squirting-40"},
                {"n": "拳交", "v": "/c/Fisting-48"},
                {"n": "人妻", "v": "/tags/housewife"},
                {"n": "日本", "v": "/tags/japanese"},
                {"n": "日本無碼成人电影", "v": "/c/Uncensored_Japanese_Porn-171"},
                {"n": "少女", "v": "/c/Teen-13"},
                {"n": "射顏", "v": "/c/Facial-19"},
                {"n": "攝像頭", "v": "/c/Cam_Porn-69"},
                {"n": "雙性戀", "v": "/c/Bisexual-49"},
                {"n": "絲襪", "v": "/c/Pantyhose-57"},
                {"n": "台灣", "v": "/tags/taiwan"},
                {"n": "塗油", "v": "/c/Oiled-44"},
                {"n": "香港", "v": "/tags/hong-kong"},
                {"n": "性感內衣", "v": "/c/Lingerie-58"},
                {"n": "亞洲的", "v": "/tags/asian"},
                {"n": "業餘", "v": "/tags/amateur"},
                {"n": "異族", "v": "/c/Interracial-22"},
                {"n": "印度的", "v": "/c/Indian-155"},
                {"n": "中出", "v": "/tags/creampie"},
                {"n": "中國", "v": "/tags/chinese"},
                {"n": "自慰", "v": "/c/Solo_and_Masturbation-33"},
                {"n": "AI（人工智能）", "v": "/c/AI-239"},
                {"n": "ASMR", "v": "/c/ASMR-243"},
                {"n": "China", "v": "/tags/china"},
                {"n": "Cosplay", "v": "/tags/cosplay"},
                {"n": "📂 所有標籤目錄", "v": "all_tags_folder"}
            ]

            tag_filters = [
                {
                    "key": "cat",
                    "name": "分类项目",
                    "init": "/lang/chinese",
                    "value": category_options
                }
            ]

            channel_filters = [
                {
                    "key": "main_cat",
                    "name": "取向",
                    "init": "/channels-index",
                    "value": [
                        {"n": "直", "v": "/channels-index"},
                        {"n": "男同", "v": "/channels-gay"},
                        {"n": "跨性別", "v": "/channels-trans"}
                    ]
                },
                {
                    "key": "geo",
                    "name": "地区范围",
                    "init": "",
                    "value": [
                        {"n": "全球频道", "v": ""},
                        {"n": "中国人 频道", "v": "/china"},
                        {"n": "香港人 频道", "v": "/hong_kong"},
                        {"n": "亞洲的 频道", "v": "/asia"}
                    ]
                },
                {
                    "key": "sort",
                    "name": "排序方式",
                    "init": "",
                    "value": [
                        {"n": "最近在 中国 已观看", "v": ""},
                        {"n": "最近觀看的", "v": "/from/worldwide"},
                        {"n": "热门排行", "v": "/from/worldwide/top"},
                        {"n": "中国 热门排行", "v": "/top"},
                        {"n": "新建", "v": "/new"}
                    ]
                }
            ]

            star_filters = [
                {
                    "key": "geo",
                    "name": "模特地区",
                    "init": "/pornstars-index",
                    "value": [
                        {"n": "全球模特", "v": "/pornstars-index"},
                        {"n": "中国人 模特", "v": "/pornstars-index/china"},
                        {"n": "香港人 模特", "v": "/pornstars-index/hong_kong"},
                        {"n": "亞洲的 模特", "v": "/pornstars-index/asia"}
                    ]
                },
                {
                    "key": "type",
                    "name": "模特类型",
                    "init": "",
                    "value": [
                        {"n": "所有类型", "v": ""},
                        {"n": "女色情演员", "v": "/porn-actresses-index"},
                        {"n": "业余爱好者", "v": "/amateurs-index"},
                        {"n": "视频女", "v": "/webcam-models-index"},
                        {"n": "淫欲模特", "v": "/erotic-models-index"}
                    ]
                },
                {
                    "key": "sort",
                    "name": "排名排序",
                    "init": "",
                    "value": [
                        {"n": "默认排序", "v": ""},
                        {"n": "全球订阅者（曾经）", "v": "/from/worldwide/ever"},
                        {"n": "全球订阅者（1 年）", "v": "/from/worldwide"},
                        {"n": "全球订阅者（3 月）", "v": "/from/worldwide/3months"},
                        {"n": "中国人订户（曾经）", "v": "/ever"},
                        {"n": "中国人订户（3个月）", "v": "/3months"},
                        {"n": "新資料", "v": "/new"},
                        {"n": "A-Z列表", "v": "/list"},
                        {"n": "國家/地區列表", "v": "/countries"}
                    ]
                }
            ]

            result["filters"] = {
                "nav_best": best_filters,
                "nav_tags": tag_filters,
                "nav_channels": channel_filters,
                "nav_pornstars": star_filters
            }

        return result

    def homeVideoContent(self):
        return {"list": []}

    def _extract_channel_remarks(self, chunk):
        """精准提取频道和明星卡片上的真实视频数量（1:1 对齐 72視頻、555視頻）"""
        # 1. 直接匹配截图中的繁简格式，如 "72視頻"、"555視頻"、"61 视频"
        v_cnt_m = re.search(r'([0-9,.]+[kKmM]?)\s*(?:視頻|视频|部影片|影片|videos|video)', chunk)
        if v_cnt_m:
            return "%s視頻" % v_cnt_m.group(1).strip()

        # 2. 从专属 DOM 节点中提取视频数量
        cnt_block = re.search(r'<span[^>]*class=["\'](?:count|video-count|nb-videos)["\'][^>]*>([^<]+)</span>', chunk)
        if cnt_block:
            num = cnt_block.group(1).strip()
            if num:
                return "%s視頻" % num

        # 3. 从 data-videos 数组中统计视频数量
        dv_m = re.search(r'data-videos=["\'](\[[^"\']+\])["\']', chunk)
        if dv_m:
            try:
                v_arr = json.loads(dv_m.group(1))
                if isinstance(v_arr, list) and len(v_arr) > 0:
                    return "%d視頻" % len(v_arr)
            except Exception:
                pass

        # 4. 匹配订阅数，如 "992.1k 订阅"
        sub_m = re.search(r'([0-9,.]+[kKmM]?)\s*(?:订阅|訂閱|订户|subscribers|subs)', chunk, re.I)
        if sub_m:
            return "%s订阅" % sub_m.group(1).strip()

        # 5. 兜底提取详细信息文本
        detail_m = re.search(r'class=["\'](?:subscribers|profile-details)["\'][^>]*>([\s\S]*?)<', chunk)
        if detail_m:
            clean_txt = re.sub(r'<[^>]+>', '', detail_m.group(1)).strip()
            if clean_txt:
                return clean_txt

        return "蝴蝶影视"

    def _parse_video_cards(self, content_str):
        vod_list = []
        html_text = content_str

        # 1. 解析 JSON 数据流
        if content_str.strip().startswith("{") and content_str.strip().endswith("}"):
            try:
                j_data = json.loads(content_str)
                if isinstance(j_data.get("videos"), list) and len(j_data["videos"]) > 0:
                    for item in j_data["videos"]:
                        raw_u = item.get("u") or item.get("url") or ("/video%s/" % item.get("id"))
                        v_id = raw_u.split("?")[0]
                        v_name = item.get("tf") or item.get("t") or item.get("title") or "XVideos 视频"
                        v_pic = item.get("i") or item.get("img") or ""
                        v_dur = item.get("d") or item.get("duration") or ""

                        vod_list.append({
                            "vod_id": v_id,
                            "vod_name": html_lib.unescape(v_name),
                            "vod_pic": v_pic if v_pic else self._get_color_block_pic(v_name),
                            "vod_remarks": v_dur if v_dur else "蝴蝶影视",
                            "style": {"type": "rect", "ratio": 1.78}
                        })
                    return vod_list
                html_text = j_data.get("html", "") or html_text
            except Exception:
                pass

        # 2. 全量提取 HTML 视频卡片
        chunks = []
        if 'class="frame-block' in html_text:
            chunks = html_text.split('class="frame-block')[1:]
        elif 'class="thumb-block' in html_text:
            chunks = html_text.split('class="thumb-block')[1:]
        elif 'id="video_' in html_text:
            chunks = html_text.split('id="video_')[1:]
        else:
            chunks = html_text.split('class="thumb-under')[1:]

        for chunk in chunks:
            href_m = re.search(r'href=["\'](/video[^"\'?#\s>]+)', chunk)
            if not href_m:
                continue
            v_url = href_m.group(1).split("?")[0]

            title = "视频"
            title_m = re.search(r'title=["\']([^"\']+)["\']', chunk)
            if title_m:
                title = title_m.group(1).strip()
            else:
                t2 = re.search(r'<p[^>]*class=["\']title["\'][^>]*>[\s\S]*?<a[^>]*>([^<]+)</a>', chunk)
                if t2:
                    title = t2.group(1).strip()
                else:
                    t3 = re.search(r'<a[^>]*title=["\']([^"\']+)["\']', chunk)
                    if t3:
                        title = t3.group(1).strip()

            pic_url = ""
            pic_m = re.search(r'<img[^>]+(?:data-src|src)=["\']([^"\']+)["\']', chunk)
            if pic_m:
                pic_url = pic_m.group(1)
                if pic_url.startswith("//"):
                    pic_url = "https:" + pic_url

            duration = ""
            dur_m = re.search(r'class=["\']duration["\'][^>]*>([^<]+)<', chunk)
            if dur_m:
                duration = dur_m.group(1).strip()

            quality = "1080P" if ("video-hd-mark" in chunk or "HD" in chunk) else ""
            remarks = ("%s | %s" % (duration, quality)).strip(" | ") if duration else "蝴蝶影视"

            vod_list.append({
                "vod_id": v_url,
                "vod_name": html_lib.unescape(title),
                "vod_pic": pic_url if pic_url else self._get_color_block_pic(title),
                "vod_remarks": remarks,
                "style": {"type": "rect", "ratio": 1.78}
            })
        return vod_list

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        slug = str(tid).strip()
        extend = extend if isinstance(extend, dict) else {}

        vod_list = []
        is_folder_entity = False
        target_path = ""
        is_post_request = False

        # ---------------- 1. 最佳影片 ----------------
        if slug == "nav_best":
            month = extend.get("month", "")
            effective_month = month if month else "/2026-08"
            target_path = "/best" + effective_month
            if page > 1:
                target_path = "%s/%d" % (target_path.rstrip("/"), page - 1)

        # ---------------- 2. 分类 ----------------
        elif slug == "nav_tags":
            cat = extend.get("cat", "/lang/chinese")
            if cat == "all_tags_folder":
                is_folder_entity = True
                res = self._fetch(self.siteUrl + "/tags")
                tag_matches = re.findall(r'<a[^>]+href=["\'](/tags/[^"\'?#]+)["\'][^>]*>([\s\S]*?)</a>', res.get("text", ""), re.I)
                seen = set()
                for href, body in tag_matches:
                    tname = re.sub(r'<[^>]+>', '', body).strip()
                    if tname and len(tname) < 25 and not tname.isdigit() and href not in seen:
                        seen.add(href)
                        vod_list.append({
                            "vod_id": "folder:" + href,
                            "vod_name": html_lib.unescape(tname),
                            "vod_pic": self._get_color_block_pic(tname),
                            "vod_remarks": "点击进入标签",
                            "vod_tag": "folder",
                            "style": {"type": "rect", "ratio": 1.78}
                        })
            else:
                target_path = cat
                if page > 1:
                    target_path = "%s/%d" % (target_path.rstrip("/"), page - 1)

        # ---------------- 3. 频道 ----------------
        elif slug == "nav_channels":
            is_folder_entity = True
            main_cat = extend.get("main_cat", "/channels-index")
            geo = extend.get("geo", "")
            sort = extend.get("sort", "")

            base = main_cat
            if sort:
                target_path = base + sort
            elif geo:
                target_path = base + geo
            else:
                target_path = base

            if page > 1:
                target_path = "%s/%d" % (target_path.rstrip("/"), page - 1)

        # ---------------- 4. 色情明星 ----------------
        elif slug == "nav_pornstars":
            is_folder_entity = True
            geo = extend.get("geo", "/pornstars-index")
            m_type = extend.get("type", "")
            sort = extend.get("sort", "")

            base = m_type if m_type else geo
            target_path = base + sort
            if page > 1:
                target_path = "%s/%d" % (target_path.rstrip("/"), page - 1)

        # ---------------- 5. Folder 二级下钻流 ----------------
        elif slug.startswith("folder:"):
            raw_url = slug.replace("folder:", "")
            clean_url = raw_url.split("#")[0].strip()

            if clean_url.startswith("/video"):
                return self.detailContent([clean_url])

            # 明星下钻：标准 POST /pornstars/{name}/videos/best/{p}
            if "/pornstars/" in clean_url or "/profiles/" in clean_url:
                s_name = clean_url.strip("/").split("/")[-1]
                target_path = "/pornstars/%s/videos/best/%d" % (s_name, page - 1)
                is_post_request = True

            # 频道下钻：标准 POST /channels/{name}/videos/best/{p}
            elif not clean_url.startswith("/tags/"):
                c_name = clean_url.strip("/").split("/")[-1]
                target_path = "/channels/%s/videos/best/%d" % (c_name, page - 1)
                is_post_request = True

            else:
                target_path = clean_url
                if page > 1:
                    target_path = "%s/%d" % (target_path.rstrip("/"), page - 1)

        else:
            target_path = slug
            if page > 1:
                target_path = "%s/%d" % (target_path.rstrip("/"), page - 1)

        # 网络请求与解析
        if not vod_list and target_path:
            full_req_url = target_path if target_path.startswith("http") else (self.siteUrl + target_path)
            res = self._fetch(full_req_url, is_post=is_post_request)
            html_text = res.get("text", "")
            code = res.get("code", 0)

            def has_data(txt, c):
                if c != 200 or not txt: return False
                if '"videos":[]' in txt.replace(" ", ""): return False
                if '"videos":[' in txt: return True
                return any(k in txt for k in ('href="/video', 'id="video_'))

            # 级联 1：尝试 /videos/uploads/ 接口
            if is_post_request and not has_data(html_text, code):
                alt_up = re.sub(r"/videos/best/", "/videos/uploads/", target_path)
                res = self._fetch(self.siteUrl + alt_up, is_post=True)
                html_text = res.get("text", "")
                code = res.get("code", 0)

            # 级联 2：回退到主页静态 HTML
            if is_post_request and not has_data(html_text, code):
                clean_target = slug.replace("folder:", "").split("#")[0].strip()
                fallback_url = self.siteUrl + "/" + clean_target.lstrip("/")
                res = self._fetch(fallback_url, is_post=False)
                html_text = res.get("text", "")

            if is_folder_entity:
                chunks = []
                if 'class="thumb-block' in html_text:
                    chunks = html_text.split('class="thumb-block')[1:]
                elif 'class="frame-block' in html_text:
                    chunks = html_text.split('class="frame-block')[1:]
                else:
                    chunks = html_text.split('class="thumb-inside')[1:]

                for chunk in chunks:
                    href_m = re.search(r'href=["\'](/[^"\'?#]+)', chunk)
                    if not href_m:
                        continue
                    c_url = href_m.group(1)
                    if c_url in ("/channels-index", "/pornstars-index"):
                        continue

                    # 1. 优先提取明星卡片上的排名编号（如 "#1"）
                    rank_str = ""
                    rank_m = re.search(r'class=["\']profile-rank["\'][^>]*>([^<]+)<', chunk) or re.search(r'class=["\']rank["\'][^>]*>([^<]+)<', chunk)
                    if rank_m:
                        rank_val = rank_m.group(1).strip()
                        if rank_val:
                            rank_str = ("#" + rank_val.lstrip("#")) + " "

                    # 2. 提取名称
                    name_m = re.search(r'class=["\']profile-name["\'][^>]*>([^<]+)<', chunk) or \
                             re.search(r'<a[^>]+class=["\']title["\'][^>]*>([^<]+)</a>', chunk) or \
                             re.search(r'title=["\']([^"\']+)["\']', chunk)
                    base_name = name_m.group(1).strip() if name_m else "专栏/模特"
                    full_display_name = rank_str + base_name

                    pic = ""
                    srcset_m = re.search(r'(?:srcset|src)=["\']([^"\']+\.(?:jpg|jpeg|png|webp|avif)[^"\']*)["\']', chunk)
                    if srcset_m:
                        pic = srcset_m.group(1).split()[0]
                    if pic.startswith("//"):
                        pic = "https:" + pic

                    # 精准提取视频数量角标（如 72視頻、555視頻）
                    remarks = self._extract_channel_remarks(chunk)

                    if c_url.startswith("/video"):
                        dur_m = re.search(r'class=["\']duration["\'][^>]*>([^<]+)<', chunk)
                        vod_list.append({
                            "vod_id": c_url,
                            "vod_name": html_lib.unescape(full_display_name),
                            "vod_pic": pic if pic else self._get_color_block_pic(base_name),
                            "vod_remarks": dur_m.group(1).strip() if dur_m else "蝴蝶影视",
                            "style": {"type": "rect", "ratio": 1.78}
                        })
                    else:
                        vod_list.append({
                            "vod_id": "folder:" + c_url,
                            "vod_name": html_lib.unescape(full_display_name),
                            "vod_pic": pic if pic else self._get_color_block_pic(base_name),
                            "vod_remarks": remarks,
                            "vod_tag": "folder",
                            "style": {"type": "rect", "ratio": 1.78}
                        })

                if not vod_list:
                    vod_list = self._parse_video_cards(html_text)
            else:
                vod_list = self._parse_video_cards(html_text)

        return {
            "page": page,
            "pagecount": page + 1 if len(vod_list) >= 15 else page,
            "limit": len(vod_list),
            "total": 9999,
            "list": vod_list
        }

    def detailContent(self, ids):
        raw_id = ids[0] if isinstance(ids, (list, tuple)) else str(ids)
        target_detail_url = self.siteUrl + raw_id if raw_id.startswith("/") else raw_id

        res = self._fetch(target_detail_url)
        html_text = res.get("text", "")

        title_m = re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']+)["\']', html_text) or re.search(r'<title>(.*?)</title>', html_text)
        vod_name = html_lib.unescape(title_m.group(1).strip()) if title_m else "XVideos 视频"
        vod_name = re.sub(r' - XVIDEOS(?:\.COM|\.RED)', '', vod_name, flags=re.I).strip()

        pic_m = re.search(r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)["\']', html_text)
        vod_pic = pic_m.group(1).strip() if pic_m else ""

        hls_url = ""
        mp4_high = ""
        mp4_low = ""

        hls_m = re.search(r'html5player\.setVideoHLS\(["\']([^"\']+)["\']\)', html_text)
        if hls_m: hls_url = hls_m.group(1)

        high_m = re.search(r'html5player\.setVideoUrlHigh\(["\']([^"\']+)["\']\)', html_text)
        if high_m: mp4_high = high_m.group(1)

        low_m = re.search(r'html5player\.setVideoUrlLow\(["\']([^"\']+)["\']\)', html_text)
        if low_m: mp4_low = low_m.group(1)

        # 兜底：内联 JSON 变量
        if not hls_url:
            hls_v = re.search(r'["\'](?:hls|url_hls)["\']\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']', html_text)
            if hls_v: hls_url = hls_v.group(1).replace(r"\/", "/")

        if not mp4_high:
            mp4_v = re.search(r'["\'](?:url_high|high)["\']\s*:\s*["\']([^"\']+\.mp4[^"\']*)["\']', html_text)
            if mp4_v: mp4_high = mp4_v.group(1).replace(r"\/", "/")

        if not mp4_low:
            mp4_lv = re.search(r'["\'](?:url_low|low)["\']\s*:\s*["\']([^"\']+\.mp4[^"\']*)["\']', html_text)
            if mp4_lv: mp4_low = mp4_lv.group(1).replace(r"\/", "/")

        play_lines = []
        if hls_url:
            play_lines.append("HLS自适应$%s" % hls_url)
        if mp4_high:
            play_lines.append("1080P高清$%s" % mp4_high)
        if mp4_low:
            play_lines.append("标清备用$%s" % mp4_low)

        if not play_lines:
            play_lines.append("默认播放$%s" % target_detail_url)

        full_desc = (
            "【🔥 官方交流群: %s】\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "• 视频标题: %s\n"
            "• 播放协议: 纯直链原生交付 (HLS/MP4)\n"
            "• 解析状态: 蝴蝶影视专属通道"
        ) % (self.tgGroup, vod_name)

        return {
            "list": [{
                "vod_id": raw_id,
                "vod_name": vod_name,
                "vod_pic": vod_pic if vod_pic else self._get_color_block_pic(vod_name),
                "vod_actor": self.brandActor,
                "vod_director": self.brandDirector,
                "vod_remarks": "蝴蝶影视",
                "vod_content": full_desc.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"),
                "vod_play_from": "XVideos专线",
                "vod_play_url": "#".join(play_lines)
            }]
        }

    def playerContent(self, flag, id, vipFlags):
        media_url = str(id).strip()
        headers = {
            "User-Agent": self._ua,
            "Referer": self.siteUrl + "/"
        }
        return {
            "parse": 0,
            "jx": 0,
            "url": media_url,
            "header": headers
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        query = quote(key)
        target_path = "/?k=%s" % query
        if page > 1:
            target_path = "%s&p=%d" % (target_path, page - 1)

        res = self._fetch(self.siteUrl + target_path)
        vod_list = self._parse_video_cards(res.get("text", ""))

        return {
            "page": page,
            "pagecount": page + 1 if len(vod_list) >= 20 else page,
            "limit": len(vod_list),
            "total": 9999,
            "list": vod_list
        }

    def action(self, action):
        return {"msg": "正式版运行正常"}

    def liveContent(self):
        return ""

    def localProxy(self, params):
        return [404, "text/plain; charset=utf-8", "Proxy not configured"]

    def destroy(self):
        self.options = {}
