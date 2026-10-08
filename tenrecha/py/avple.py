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
        pass


class Spider(SpiderBase):
    def __init__(self):
        super(Spider, self).__init__()
        self.domains = [
            "https://avple.tv",
            "https://www.avple.tv"
        ]
        self.currentDomain = self.domains[0]
        self.tgGroup = "https://t.me/tvshare23"
        self.brandActor = "🦋 TG群: @tvshare23"
        self.brandDirector = "🦋 蝴蝶影视"
        self._ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

        self.cdnNodes = [
            "47b611.cdnedge.live",
            "i3qss1.cdnedge.live",
            "10j991.cdnedge.live",
            "je40u1.cdnedge.live",
            "s2jfy1.cdnedge.live",
            "l87ul1.cdnedge.live",
            "s6s6u1.cdnedge.live",
            "rup0u1.cdnedge.live",
            "ja34l1.cdnedge.live",
            "rr0s11.cdnedge.live",
            "c4m6s1.cdnedge.live",
            "60frt1.cdnedge.live",
            "rd1921.cdnedge.live",
            "2nm9j1.cdnedge.live",
            "l8uao1.cdnedge.live",
            "ie2ow1.cdnedge.live",
            "fhq061.cdnedge.live",
            "b3h6s1.cdnedge.live",
            "sms9q1.cdnedge.live",
            "xre5q1.cdnedge.live"
        ]

        self.ctx = ssl.create_default_context()
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE
        try:
            self.ctx.set_ciphers('DEFAULT@SECLEVEL=1')
        except Exception:
            pass

        self.cj = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cj),
            urllib.request.HTTPSHandler(context=self.ctx)
        )

    def init(self, extend=""):
        return {}

    def isVideoFormat(self, url):
        low = (url or "").lower()
        return any(k in low for k in (".m3u8", ".mp4", ".flv", ".mkv", ".ts"))

    def manualVideoCheck(self):
        return False

    def _dict(self, v):
        if isinstance(v, dict):
            return v
        if isinstance(v, (str, bytes)):
            try:
                d = json.loads(v)
                return d if isinstance(d, dict) else {}
            except Exception:
                return {}
        return {}

    def _list(self, v):
        if isinstance(v, (list, tuple)):
            return [str(i) for i in v]
        if isinstance(v, (str, bytes)):
            try:
                d = json.loads(v)
                if isinstance(d, (list, tuple)):
                    return [str(i) for i in d]
            except Exception:
                pass
            return [str(v)]
        return []

    def _clean_url(self, raw_url):
        if not raw_url:
            return self.currentDomain + "/"
        target = raw_url if (raw_url.startswith("http://") or raw_url.startswith("https://")) else (self.currentDomain + ("" if raw_url.startswith("/") else "/") + raw_url)
        unquoted = urllib.parse.unquote(target)
        parts = urllib.parse.urlsplit(unquoted)
        path = urllib.parse.quote(parts.path, safe="/:@&=+$,?#")
        query = urllib.parse.quote(parts.query, safe="/:@&=+$,?#")
        return urllib.parse.urlunsplit((parts.scheme, parts.netloc, path, query, parts.fragment))

    def _fetch_safe(self, path):
        safe_url = self._clean_url(path)
        headers = {
            "User-Agent": self._ua,
            "Referer": self.currentDomain + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
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
            req = urllib.request.Request(safe_url, headers=headers)
            with self.opener.open(req, timeout=12) as resp:
                raw = resp.read()
                if raw.startswith(b"\x1f\x8b"):
                    raw = gzip.decompress(raw)
                try:
                    text = raw.decode("utf-8")
                except Exception:
                    text = raw.decode("gbk", errors="ignore")
                return {"code": resp.getcode(), "text": text, "url": resp.geturl()}
        except urllib.error.HTTPError as e:
            raw_err = e.read()
            if raw_err.startswith(b"\x1f\x8b"):
                try:
                    raw_err = gzip.decompress(raw_err)
                except Exception:
                    pass
            try:
                err_text = raw_err.decode("utf-8")
            except Exception:
                err_text = raw_err.decode("latin1", errors="ignore")
            return {"code": e.code, "text": err_text, "url": safe_url}
        except Exception as e:
            return {"code": -1, "text": "", "url": safe_url, "err": str(e)}

    def _extract_next_data(self, html_text):
        m = re.search(r'<script id="__NEXT_DATA__" type="application/json">([\s\S]*?)</script>', html_text)
        if not m:
            return {}
        try:
            return json.loads(m.group(1))
        except Exception:
            return {}

    def _format_cover(self, raw_pic):
        if not raw_pic:
            return ""
        pic_str = str(raw_pic).strip()

        
        if pic_str.startswith("//"):
            pic_str = "https:" + pic_str
        elif not (pic_str.startswith("http://") or pic_str.startswith("https://")):
            clean = pic_str.lstrip("/")
            if clean.startswith("file/"):
                pic_str = f"https://47b611.cdnedge.live/{clean}"
            elif "avple-images" in clean:
                pic_str = f"https://hqua8q61at.cdnedge.live/{clean}"
            else:
                pic_str = f"https://47b611.cdnedge.live/file/avple-asserts/{clean}"

        
        if "asserts.avple.tv" in pic_str:
            pic_str = pic_str.replace("asserts.avple.tv", "47b611.cdnedge.live")
        elif "assert.avple.tv" in pic_str:
            pic_str = pic_str.replace("assert.avple.tv", "47b611.cdnedge.live")

        return pic_str

    def _pick_cover(self, item):
        if not isinstance(item, dict):
            return ""
        
        for k in ("img_normal", "img_preview", "poster", "preview", "img", "thumb", "cover"):
            val = item.get(k)
            if val and isinstance(val, str) and val.strip():
                return self._format_cover(val)
        return ""

    def homeContent(self, filter=False):
        classes = [
            {"type_name": "麻豆傳媒", "type_id": "121"},
            {"type_name": "果凍傳媒", "type_id": "123"},
            {"type_name": "皇家華人", "type_id": "124"},
            {"type_name": "精東影業", "type_id": "125"},
            {"type_name": "天美傳媒", "type_id": "126"},
            {"type_name": "星空無限傳媒", "type_id": "127"},
            {"type_name": "樂播傳媒", "type_id": "128"},
            {"type_name": "蜜桃傳媒", "type_id": "129"},
            {"type_name": "烏鴉傳媒", "type_id": "130"},
            {"type_name": "國產自拍", "type_id": "131"},
            {"type_name": "SWAG", "type_id": "122"},
            {"type_name": "FC2PPV", "type_id": "135"},
            {"type_name": "選台台灣AV", "type_id": "138"},
            {"type_name": "選台國產AV", "type_id": "142"},
            {"type_name": "選台最新影片", "type_id": "139"},
            {"type_name": "選台孟若羽", "type_id": "136"},
            {"type_name": "選台探花精選", "type_id": "132"},
            {"type_name": "選台自拍流出", "type_id": "143"},
            {"type_name": "選台熱門影片", "type_id": "140"},
            {"type_name": "黑絲", "type_id": "15"},
            {"type_name": "旗袍", "type_id": "113"},
            {"type_name": "校服", "type_id": "49"},
            {"type_name": "絲襪", "type_id": "13"},
            {"type_name": "女僕", "type_id": "97"},
            {"type_name": "吊帶襪", "type_id": "76"},
            {"type_name": "兔女郎", "type_id": "87"},
            {"type_name": "巨乳", "type_id": "1"},
            {"type_name": "貧乳", "type_id": "63"},
            {"type_name": "露出", "type_id": "79"},
            {"type_name": "中出", "type_id": "2"},
            {"type_name": "顏射", "type_id": "32"},
            {"type_name": "潮吹", "type_id": "18"},
            {"type_name": "綑綁", "type_id": "53"},
            {"type_name": "多P", "type_id": "33"}
        ]

        default_tid = classes[0]["type_id"]
        cate_res = self.categoryContent(default_tid, "1", filter)
        vod_list = cate_res.get("list", [])

        return {
            "class": classes,
            "list": vod_list
        }

    def categoryContent(self, tid, pg, filter=False, extend=None, *args, **kwargs):
        pg_num = str(pg).strip() if pg else "1"
        clean_tid = str(tid).strip().strip("/")
        if clean_tid.startswith("tags/"):
            clean_tid = clean_tid.split("/")[1]

        target_path = f"/tags/{clean_tid}/{pg_num}/date"
        res = self._fetch_safe(target_path)
        html_text = res.get("text", "")

        vod_list = []
        nd = self._extract_next_data(html_text)
        page_props = nd.get("props", {}).get("pageProps", {})
        raw_items = page_props.get("data", [])

        total_pages = int(page_props.get("totalPage", 100))

        if isinstance(raw_items, list) and raw_items:
            for item in raw_items:
                if not isinstance(item, dict):
                    continue
                vid = str(item.get("_id") or item.get("id") or "")
                title = str(item.get("title") or item.get("name") or "").strip()
                if not vid or not title:
                    continue

                pic = self._pick_cover(item)
                remarks = str(item.get("timeLengh") or item.get("timeLength") or item.get("release") or "")

                vod_list.append({
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": remarks
                })
        else:
            cards = re.findall(r'<a\s+[^>]*href=["\']/video/(\d+)["\'][^>]*>([\s\S]*?)</a>', html_text, re.I)
            seen_ids = set()
            for vid, inner in cards:
                if vid in seen_ids:
                    continue
                seen_ids.add(vid)

                tm = re.search(r'title=["\']([^"\']+)["\']', inner, re.I) or re.search(r'alt=["\']([^"\']+)["\']', inner, re.I)
                title = tm.group(1).strip() if tm else re.sub(r'<[^>]+>', '', inner).strip()
                if not title:
                    continue

                im = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', inner, re.I)
                pic = self._format_cover(im.group(1)) if im else ""

                vod_list.append({
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": ""
                })

        return {
            "page": int(pg_num),
            "pagecount": total_pages,
            "limit": 24,
            "total": total_pages * 24,
            "list": vod_list
        }

    def detailContent(self, ids):
        raw_ids = self._list(ids)
        if not raw_ids:
            return {"list": []}
        vid = raw_ids[0].strip()

        target_path = f"/video/{vid}"
        res = self._fetch_safe(target_path)
        html_text = res.get("text", "")

        nd = self._extract_next_data(html_text)
        page_props = nd.get("props", {}).get("pageProps", {})
        instance = page_props.get("instance", {})

        title = str(instance.get("title") or "").strip()
        if not title:
            tm = re.search(r'<title>([\s\S]*?)</title>', html_text, re.I)
            title = tm.group(1).split("-")[0].strip() if tm else f"AVPLE_{vid}"

        cover_url = self._pick_cover(instance)

        duration = str(instance.get("timeLengh") or instance.get("timeLength") or "")
        views = str(instance.get("view_count") or "")
        rel_date = str(instance.get("release") or "")
        remarks = f"{duration} | 播放:{views}" if duration and views else (duration or rel_date)

        play_path = str(instance.get("play") or "").strip()
        if not play_path:
            pm = re.search(r'["\'](hls/[a-zA-Z0-9_-]+/playlist\.m3u8)["\']', html_text)
            if pm:
                play_path = pm.group(1)

        play_sources = []
        if play_path:
            clean_rel = play_path.lstrip("/")
            for idx, cdn in enumerate(self.cdnNodes[:8], start=1):
                stream_url = f"https://{cdn}/file/avple-asserts/{clean_rel}"
                play_sources.append(f"线路{idx} (超清)${stream_url}")

        play_from = "AVPLE专线"
        play_url = "#".join(play_sources) if play_sources else "无法解析播放流$http://127.0.0.1"

        desc_content = (
            "【🔥 官方交流群: %s】\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "片名: %s\n"
            "时长: %s | 上架时间: %s\n"
            "播放量: %s\n"
            "视频ID: %s\n"
            "声明: 资源来源于网络，仅供交流学习。"
        ) % (self.tgGroup, title, duration, rel_date, views, vid)

        vod = {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": cover_url,
            "vod_actor": self.brandActor,
            "vod_director": self.brandDirector,
            "vod_remarks": remarks,
            "vod_content": desc_content,
            "vod_play_from": play_from,
            "vod_play_url": play_url
        }

        return {"list": [vod]}

    def playerContent(self, flag, id, vipFlags):
        raw_url = str(id).strip()
        headers = {
            "User-Agent": self._ua,
            "Referer": "https://avple.tv/",
            "Origin": "https://avple.tv"
        }
        return {
            "parse": 0,
            "playUrl": "",
            "url": raw_url,
            "header": json.dumps(headers)
        }

    def searchContent(self, key, quick, pg="1"):
        if not key:
            return {"list": []}
        pg_num = str(pg).strip() if pg else "1"
        encoded_key = urllib.parse.quote(str(key).strip())

        target_path = f"/search?key={encoded_key}&page={pg_num}"
        res = self._fetch_safe(target_path)
        html_text = res.get("text", "")

        vod_list = []
        nd = self._extract_next_data(html_text)
        page_props = nd.get("props", {}).get("pageProps", {})
        raw_items = page_props.get("data") or page_props.get("searchList") or []

        if isinstance(raw_items, list) and raw_items:
            for item in raw_items:
                if not isinstance(item, dict):
                    continue
                vid = str(item.get("_id") or item.get("id") or "")
                title = str(item.get("title") or item.get("name") or "").strip()
                if not vid or not title:
                    continue

                pic = self._pick_cover(item)
                remarks = str(item.get("timeLengh") or item.get("timeLength") or "")

                vod_list.append({
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": remarks
                })
        else:
            cards = re.findall(r'<a\s+[^>]*href=["\']/video/(\d+)["\'][^>]*>([\s\S]*?)</a>', html_text, re.I)
            seen_ids = set()
            for vid, inner in cards:
                if vid in seen_ids:
                    continue
                seen_ids.add(vid)

                tm = re.search(r'title=["\']([^"\']+)["\']', inner, re.I) or re.search(r'alt=["\']([^"\']+)["\']', inner, re.I)
                title = tm.group(1).strip() if tm else re.sub(r'<[^>]+>', '', inner).strip()
                if not title:
                    continue

                im = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', inner, re.I)
                pic = self._format_cover(im.group(1)) if im else ""

                vod_list.append({
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": ""
                })

        return {
            "page": int(pg_num),
            "pagecount": 10,
            "limit": len(vod_list),
            "total": len(vod_list) * 10,
            "list": vod_list
        }