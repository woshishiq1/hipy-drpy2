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
        self.siteUrl = "https://eetftz.hqs2.homes"
        self.tgGroup = "https://t.me/+3t5XRPPo9mlkZDRl"
        self.brandActor = "📺TG群: https://t.me/+3t5XRPPo9mlkZDRl"
        self.brandDirector = "📺ZakaTV"
        self._ua = "Mozilla/5.0 (Linux; Android 12; Pixel 6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.6478.134 Mobile Safari/537.36"

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
            "Referer": self.siteUrl + "/hqs/",
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

    # 1. 首页：纯内存静态返回 10 个核心分类，零网络阻塞
    def homeContent(self, filter=False):
        return {
            "class": [
                {"type_name": "亚洲情色", "type_id": "20"},
                {"type_name": "中文字幕", "type_id": "26"},
                {"type_name": "无码专区", "type_id": "29"},
                {"type_name": "偷拍自拍", "type_id": "25"},
                {"type_name": "制服师生", "type_id": "21"},
                {"type_name": "人妻熟女", "type_id": "28"},
                {"type_name": "强奸乱伦", "type_id": "24"},
                {"type_name": "欧美性爱", "type_id": "27"},
                {"type_name": "三级伦理", "type_id": "23"},
                {"type_name": "卡通动漫", "type_id": "22"}
            ]
        }

    def homeVideoContent(self):
        return {"list": []}

    # 2. 列表页：多级标题穿透提纯，彻底消除 "Play"
    def categoryContent(self, tid, pg="1", filter=False, extend=None):
        page_num = str(pg or "1").strip()
        tid = str(tid).strip()

        if page_num == "1":
            target_path = "/vodtype/%s.html" % tid
        else:
            target_path = "/vodtype/%s-%s.html" % (tid, page_num)

        res = self._fetch(target_path)
        html_text = res.get("text", "")

        card_matches = re.findall(r'(<a[^>]+href=["\']([^"\']*(?:/\d+\.html|/voddetail/|/vodplay/)[^"\']*)["\'][^>]*>([\s\S]*?)</a>)', html_text, re.I)

        vod_dict = {}  # 用于按 clean_href 去重并优先保留真实长标题

        for full_a, v_href, inner in card_matches:
            clean_href = v_href.strip()
            if "vodtype" in clean_href:
                continue

            # 多层级解析真实标题：img alt -> title 属性 -> 内部文本
            title = ""
            alt_m = re.search(r'<img[^>]+alt=["\']([^"\']+)["\']', inner, re.I)
            if alt_m and alt_m.group(1).strip() and alt_m.group(1).strip().lower() != "play":
                title = alt_m.group(1).strip()

            if not title:
                title_m = re.search(r'title=["\']([^"\']+)["\']', full_a, re.I)
                if title_m and title_m.group(1).strip() and title_m.group(1).strip().lower() != "play":
                    title = title_m.group(1).strip()

            if not title:
                text_clean = re.sub(r'<[^>]+>', '', inner).strip()
                if text_clean and text_clean.lower() != "play":
                    title = text_clean

            # 图片提取
            pic = ""
            img_m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', inner, re.I)
            if not img_m:
                img_m = re.search(r'<img[^>]+data-original=["\']([^"\']+)["\']', inner, re.I)
            if img_m:
                val = img_m.group(1).strip()
                if not val.startswith("data:image"):
                    pic = val

            if pic.startswith("//"):
                pic = "https:" + pic
            elif pic.startswith("/"):
                pic = self.siteUrl.rstrip("/") + pic

            if clean_href not in vod_dict:
                vod_dict[clean_href] = {
                    "title": title if title else "精彩视频",
                    "pic": pic
                }
            else:
                # 若已存在但当前抓到了更长的有效标题，进行覆盖
                if title and len(title) > len(vod_dict[clean_href]["title"]):
                    vod_dict[clean_href]["title"] = title
                if not vod_dict[clean_href]["pic"] and pic:
                    vod_dict[clean_href]["pic"] = pic

        vod_list = []
        for href, item in vod_dict.items():
            t = item["title"]
            if any(k in t for k in ("下一页", "上一页", "首页", "尾页", "返回")):
                continue

            safe_id = "v_" + base64.urlsafe_b64encode(href.encode("utf-8")).decode("utf-8").rstrip("=")
            vod_list.append({
                "vod_id": safe_id,
                "vod_name": self._unesc(t),
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

    # 3. 详情页：直接起播与标准简介注入
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

            # 提取真实标题
            title_m = re.search(r'<title>(.*?)</title>', html_text, re.I)
            page_title = title_m.group(1).strip() if title_m else "精彩视频"
            page_title = re.sub(r'(-|\||_).*$', '', page_title).strip()

            # 核心嗅探播放直链
            raw_url = ""
            p_match = re.search(r'(?:player_data|player_aaaa)[\s\S]*?["\']url["\']\s*:\s*["\']([^"\']+)["\']', html_text)
            if p_match:
                raw_url = p_match.group(1).strip()

            if not raw_url:
                m3u8_m = re.search(r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', html_text, re.I)
                if m3u8_m:
                    raw_url = m3u8_m.group(1).strip()
                else:
                    mp4_m = re.search(r'["\'](https?://[^"\']+\.mp4[^"\']*)["\']', html_text, re.I)
                    if mp4_m:
                        raw_url = mp4_m.group(1).strip()

            decrypted_url = raw_url.replace(r"\/", "/") if raw_url else ""

            # 简介提纯
            desc_m = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']', html_text, re.I)
            clean_content = desc_m.group(1).strip() if desc_m else ""

            custom_notice = "【💡 温馨提示：视频如遇卡顿请尝试切换播放器核心或快进。】"
            group_info = "【🔥 官方交流群: %s】" % self.tgGroup

            if clean_content:
                vod_content = "%s\n\n%s\n\n%s" % (group_info, custom_notice, clean_content)
            else:
                vod_content = "%s\n\n%s\n\n暂无详细简介，欢迎加入官方群交流！" % (group_info, custom_notice)

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
                    "vod_play_from": "Zaka专线",
                    "vod_play_url": "正片$%s" % final_play_url
                }]
            }
        except Exception:
            return {"list": []}

    # 4. 播放器直连：parse: 0
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