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
        self.siteUrl = "https://msa.91tk.lat"
        self.tgGroup = "https://t.me/tvshare23"
        self.brandActor = "🦋 TG群: @tvshare23"
        self.brandDirector = "🦋 蝴蝶影视"
        self._ua = "Mozilla/5.0 (Linux; Android 12; Pixel 6) AppleWebKit/537.36 Chrome/126.0.6478.134 Mobile Safari/537.36"

    def init(self, extend=""):
        return True

    def isVideoFormat(self, url):
        low = (url or "").lower()
        return any(k in low for k in (".m3u8", ".mp4", ".flv", ".mkv", ".avi", ".ts"))

    def manualVideoCheck(self):
        return False

    def _build_opener(self):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        cj = http.cookiejar.CookieJar()
        return urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(cj),
            urllib.request.HTTPSHandler(context=ctx)
        )

    def _fetch(self, target_url):
        if not target_url:
            return {"code": 0, "text": "", "err": ""}
        if target_url.startswith("/"):
            target_url = self.siteUrl.rstrip("/") + target_url

        headers = {
            "User-Agent": self._ua,
            "Referer": self.siteUrl + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "Sec-Ch-Ua": '"Chromium";v="126", "Not?A_Brand";v="8", "Android Chrome";v="126"',
            "Sec-Ch-Ua-Mobile": "?1",
            "Sec-Ch-Ua-Platform": '"Android"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1"
        }

        try:
            opener = self._build_opener()
            req = urllib.request.Request(target_url, headers=headers)
            with opener.open(req, timeout=12) as resp:
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
        except urllib.error.HTTPError as e:
            err_body = ""
            try:
                raw_err = e.read()
                if raw_err.startswith(b"\x1f\x8b"):
                    raw_err = gzip.decompress(raw_err)
                err_body = raw_err.decode("utf-8", errors="ignore")
            except Exception:
                pass
            return {"code": e.code, "text": err_body, "err": "HTTPError: %s" % str(e)}
        except Exception as e:
            return {"code": -1, "text": "", "err": "Exception: %s" % str(e)}

    def _unesc(self, s):
        try:
            return html_lib.unescape(s or "").strip()
        except Exception:
            return (s or "").strip()

    def homeContent(self, filter=False):
        return {
            "class": [
                {"type_name": "自拍偷拍", "type_id": "自拍偷拍"},
                {"type_name": "中文字幕", "type_id": "中文字幕"},
                {"type_name": "国产传媒", "type_id": "国产传媒"},
                {"type_name": "日本无码", "type_id": "日本无码"},
                {"type_name": "抖阴视频", "type_id": "抖阴视频"},
                {"type_name": "网红主播", "type_id": "网红主播"},
                {"type_name": "探花系列", "type_id": "探花系列"},
                {"type_name": "黑丝诱惑", "type_id": "黑丝诱惑"},
                {"type_name": "门事件", "type_id": "门事件"},
                {"type_name": "激情动漫", "type_id": "激情动漫"},
                {"type_name": "三级伦理", "type_id": "三级伦理"},
                {"type_name": "素人搭讪", "type_id": "素人搭讪"},
                {"type_name": "VR视角", "type_id": "vr视角"},
                {"type_name": "SWAG", "type_id": "swag"},
                {"type_name": "AV解说", "type_id": "av解说"},
                {"type_name": "cosplay", "type_id": "cosplay"}
            ]
        }

    def homeVideoContent(self):
        return {"list": []}

    def categoryContent(self, tid, pg="1", filter=False, extend=None):
        page_num = str(pg or "1").strip()
        cat_name = str(tid).strip()

        encoded_cat = urllib.parse.quote(cat_name)
        if page_num == "1":
            target_path = "/k/category/%s/" % encoded_cat
        else:
            target_path = "/k/category/%s/page/%s/" % (encoded_cat, page_num)

        res = self._fetch(target_path)
        html_text = res.get("text", "")

        articles = re.findall(r'<article[\s\S]*?</article>', html_text, re.I)
        vod_dict = {}

        if articles:
            for art in articles:
                link_m = re.search(r'href=["\']([^"\']*(?:/k/\d+\.html|/archives/\d+)[^"\']*)["\']', art, re.I)
                if not link_m:
                    continue
                clean_href = link_m.group(1).strip()
                if self.siteUrl in clean_href:
                    clean_href = clean_href.replace(self.siteUrl, "")

                title = ""
                h_m = re.search(r'<h[1-4][^>]*>([\s\S]*?)</h[1-4]>', art, re.I)
                if h_m:
                    title = re.sub(r'<[^>]+>', '', h_m.group(1)).strip()
                if not title:
                    t_m = re.search(r'title=["\']([^"\']+)["\']', art, re.I)
                    if t_m:
                        title = t_m.group(1).strip()

                pic = ""
                img_m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', art, re.I)
                if not img_m:
                    img_m = re.search(r'<img[^>]+data-(?:src|original)=["\']([^"\']+)["\']', art, re.I)
                if img_m:
                    pic = self._unesc(img_m.group(1).strip())

                if pic.startswith("//"):
                    pic = "https:" + pic
                elif pic.startswith("/"):
                    pic = self.siteUrl.rstrip("/") + pic

                if title and clean_href not in vod_dict:
                    vod_dict[clean_href] = {"title": title, "pic": pic}
        else:
            raw_cards = re.findall(r'<a[^>]+href=["\']([^"\']*/k/\d+\.html)["\'][^>]*>([\s\S]*?)</a>', html_text, re.I)
            for href, inner in raw_cards:
                clean_href = href.strip()
                if self.siteUrl in clean_href:
                    clean_href = clean_href.replace(self.siteUrl, "")

                if clean_href not in vod_dict:
                    vod_dict[clean_href] = {"title": "", "pic": ""}

                img_m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', inner, re.I)
                if img_m:
                    pic_val = self._unesc(img_m.group(1).strip())
                    if pic_val.startswith("//"):
                        pic_val = "https:" + pic_val
                    elif pic_val.startswith("/"):
                        pic_val = self.siteUrl.rstrip("/") + pic_val
                    vod_dict[clean_href]["pic"] = pic_val

                text_clean = re.sub(r'<[^>]+>', '', inner).strip()
                if text_clean and len(text_clean) > 3 and not any(k in text_clean for k in ("下一页", "上一页")):
                    vod_dict[clean_href]["title"] = text_clean

        vod_list = []
        for href, item in vod_dict.items():
            if not item["title"]:
                continue
            safe_id = "v_" + base64.urlsafe_b64encode(href.encode("utf-8")).decode("utf-8").rstrip("=")
            vod_list.append({
                "vod_id": safe_id,
                "vod_name": self._unesc(item["title"]),
                "vod_pic": item["pic"],
                "vod_remarks": "高清"
            })

        return {
            "page": int(page_num),
            "pagecount": 99,
            "limit": len(vod_list),
            "total": 99,
            "list": vod_list
        }

    def detailContent(self, ids):
        try:
            if isinstance(ids, (list, tuple)):
                raw_id = ids[0] if ids else ""
            else:
                raw_id = str(ids or "")
            raw_id = str(raw_id).strip()

            play_path = ""
            if raw_id.startswith("v_"):
                b64_str = raw_id[2:]
                pad = len(b64_str) % 4
                if pad:
                    b64_str += "=" * (4 - pad)
                play_path = base64.urlsafe_b64decode(b64_str.encode("utf-8")).decode("utf-8")
            else:
                play_path = raw_id

            if not play_path:
                return {"list": []}

            res = self._fetch(play_path)
            html_text = res.get("text", "")

            raw_url = ""

            t_url_m = re.search(r't\.php\?url=(https?://[^"\'&\s]+)', html_text, re.I)
            if t_url_m:
                raw_url = t_url_m.group(1).strip()

            if not raw_url:
                iframe_src_m = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', html_text, re.I)
                if iframe_src_m:
                    iframe_full = self._unesc(iframe_src_m.group(1).strip())
                    sub_m = re.search(r'url=(https?://[^"\'&\s]+)', iframe_full, re.I)
                    if sub_m:
                        raw_url = sub_m.group(1).strip()

            if not raw_url:
                m3u8_m = re.search(r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', html_text, re.I)
                if m3u8_m:
                    raw_url = m3u8_m.group(1).strip()
                else:
                    mp4_m = re.search(r'["\'](https?://[^"\']+\.mp4[^"\']*)["\']', html_text, re.I)
                    if mp4_m:
                        raw_url = mp4_m.group(1).strip()

            decrypted_url = raw_url.replace(r"\/", "/") if raw_url else ""

            title_m = re.search(r'<title>(.*?)</title>', html_text, re.I)
            page_title = title_m.group(1).strip() if title_m else "精彩视频"
            page_title = re.sub(r'(-|\||_).*$', '', page_title).strip()

            desc_m = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']', html_text, re.I)
            clean_content = desc_m.group(1).strip() if desc_m else ""

            custom_notice = "【💡 温馨提示：视频加载如遇卡顿请尝试切换网络或快进。】"
            group_info = "【🔥 官方交流群: %s】" % self.tgGroup

            if clean_content:
                vod_content = "%s\n\n%s\n\n%s" % (group_info, custom_notice, clean_content)
            else:
                vod_content = "%s\n\n%s\n\n暂无详细简介，欢迎加入官方交流群获取最新资源！" % (group_info, custom_notice)

            final_play_url = decrypted_url if (decrypted_url and decrypted_url.startswith("http")) else "http://127.0.0.1"

            return {
                "list": [{
                    "vod_id": raw_id,
                    "vod_name": self._unesc(page_title),
                    "vod_pic": "",
                    "vod_actor": self.brandActor,
                    "vod_director": self.brandDirector,
                    "vod_remarks": "高清直链",
                    "vod_content": vod_content,
                    "vod_play_from": "蝴蝶专线",
                    "vod_play_url": "正片$%s" % final_play_url
                }]
            }
        except Exception:
            return {"list": []}

    def playerContent(self, flag, id, vipFlags):
        real_url = str(id).strip()
        return {
            "parse": 0,
            "playUrl": "",
            "url": real_url,
            "header": json.dumps({
                "User-Agent": self._ua,
                "Referer": self.siteUrl + "/"
            })
        }

    def searchContent(self, key, quick, pg="1"):
        return {"list": []}