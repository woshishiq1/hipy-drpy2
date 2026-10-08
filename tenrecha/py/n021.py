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
        self.siteUrl = "https://zcl.ssm4.xyz"
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
        try:
            ctx.set_ciphers("DEFAULT:@SECLEVEL=1")
        except Exception:
            pass
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
            "Referer": self.siteUrl + "/ssm/",
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
                for enc in ("utf-8", "gbk", "gb2312", "latin1"):
                    try:
                        return {"code": code, "text": raw.decode(enc), "err": ""}
                    except Exception:
                        continue
                return {"code": code, "text": raw.decode("utf-8", errors="replace"), "err": ""}
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
                {"type_name": "女神学生", "type_id": "21"},
                {"type_name": "美女直播", "type_id": "22"},
                {"type_name": "人妻系列", "type_id": "23"},
                {"type_name": "强纳聚麀", "type_id": "24"},
                {"type_name": "自拍偷拍", "type_id": "25"},
                {"type_name": "制服诱惑", "type_id": "26"},
                {"type_name": "巨乳系列", "type_id": "27"},
                {"type_name": "自慰系列", "type_id": "28"},
                {"type_name": "国产视频", "type_id": "29"},
                {"type_name": "无码视频", "type_id": "30"},
                {"type_name": "有码视频", "type_id": "31"},
                {"type_name": "中文字幕", "type_id": "32"},
                {"type_name": "日韩精品", "type_id": "33"},
                {"type_name": "欧美精品", "type_id": "34"},
                {"type_name": "动漫精品", "type_id": "35"},
                {"type_name": "三级伦理", "type_id": "36"}
            ]
        }

    def homeVideoContent(self):
        return {"list": []}

    def categoryContent(self, tid, pg="1", filter=False, extend=None):
        page_num = str(pg or "1").strip()
        tid = str(tid).strip()

        if page_num == "1":
            target_path = "/vodtype/%s.html" % tid
        else:
            target_path = "/vodtype/%s-%s.html" % (tid, page_num)

        res = self._fetch(target_path)
        html_text = res.get("text", "")

        blocks = re.split(r"<li\b", html_text)
        vod_dict = {}

        for b in blocks:
            m = re.search(r'<a\b[^>]*class="[^"]*v-playBtn[^"]*"[^>]*>', b, re.I)
            if not m:
                continue
            tag = m.group(0)
            hm = re.search(r'href=["\']\s*([^"\']+?)\s*["\']', tag, re.I)
            if not hm:
                continue
            clean_href = hm.group(1).strip()
            if self.siteUrl in clean_href:
                clean_href = clean_href.replace(self.siteUrl, "")

            title = ""
            tm = re.search(r'title=["\']([^"\']*)["\']', tag, re.I)
            if tm and tm.group(1).strip() and tm.group(1).strip().lower() != "play":
                title = tm.group(1).strip()

            if not title:
                am = re.search(r'<img\b[^>]*alt=["\']([^"\']*)["\']', b, re.I)
                if am and am.group(1).strip() and am.group(1).strip().lower() != "play":
                    title = am.group(1).strip()

            if not title:
                text_clean = re.sub(r'<[^>]+>', '', b).strip()
                if text_clean and text_clean.lower() != "play":
                    title = text_clean

            if not title or any(k in title for k in ("下一页", "上一页", "首页", "尾页", "返回")):
                continue

            pic = ""
            im = re.search(r'<img\b[^>]*src=["\']([^"\']+)["\']', b, re.I)
            if not im:
                im = re.search(r'<img\b[^>]*data-original=["\']([^"\']+)["\']', b, re.I)
            if im:
                val = im.group(1).strip()
                if not val.startswith("data:image"):
                    pic = val

            if pic.startswith("//"):
                pic = "https:" + pic
            elif pic.startswith("/"):
                pic = self.siteUrl.rstrip("/") + pic

            rm = re.search(r'<span class="fr">([^<]*)</span>', b, re.I)
            rem = rm.group(1).strip() if rm else "高清"

            if clean_href not in vod_dict:
                vod_dict[clean_href] = {"title": title, "pic": pic, "rem": rem}
            else:
                if len(title) > len(vod_dict[clean_href]["title"]):
                    vod_dict[clean_href]["title"] = title
                if not vod_dict[clean_href]["pic"] and pic:
                    vod_dict[clean_href]["pic"] = pic

        vod_list = []
        for href, item in vod_dict.items():
            safe_id = "v_" + base64.urlsafe_b64encode(href.encode("utf-8")).decode("utf-8").rstrip("=")
            vod_list.append({
                "vod_id": safe_id,
                "vod_name": self._unesc(item["title"]),
                "vod_pic": item["pic"],
                "vod_remarks": item["rem"]
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

            if not play_path.startswith("/"):
                play_path = "/" + play_path
            if not play_path.endswith(".html"):
                play_path += ".html"

            res = self._fetch(play_path)
            html_text = res.get("text", "")

            raw_url = ""
            encrypt_flag = "0"

            m = re.search(r"const rawUrl\s*=\s*['\"]([^'\"]+)['\"]", html_text, re.I)
            if m:
                raw_url = m.group(1).strip()

            if not raw_url:
                p_match = re.search(r'(?:player_data|player_aaaa|mac_player_data)[\s\S]*?["\']url["\']\s*:\s*["\']([^"\']+)["\']', html_text)
                if p_match:
                    raw_url = p_match.group(1).strip()
                    enc_match = re.search(r'(?:player_data|player_aaaa|mac_player_data)[\s\S]*?["\']encrypt["\']\s*:\s*(\d+)', html_text)
                    if enc_match:
                        encrypt_flag = enc_match.group(1).strip()

            if not raw_url:
                v_tag = re.search(r'<video[^>]+src=["\']([^"\']+)["\']', html_text, re.I)
                if v_tag:
                    raw_url = v_tag.group(1).strip()

            if not raw_url:
                m3u8_m = re.search(r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', html_text, re.I)
                if m3u8_m:
                    raw_url = m3u8_m.group(1).strip()
                else:
                    mp4_m = re.search(r'["\'](https?://[^"\']+\.mp4[^"\']*)["\']', html_text, re.I)
                    if mp4_m:
                        raw_url = mp4_m.group(1).strip()

            decrypted_url = ""
            if raw_url:
                if encrypt_flag == "0":
                    decrypted_url = raw_url
                elif encrypt_flag == "1":
                    decrypted_url = urllib.parse.unquote(raw_url)
                elif encrypt_flag == "2":
                    try:
                        decrypted_url = urllib.parse.unquote(base64.b64decode(raw_url.encode("utf-8")).decode("utf-8"))
                    except Exception:
                        decrypted_url = raw_url

            if decrypted_url:
                decrypted_url = decrypted_url.replace(r"\/", "/")

            tm = re.search(r"<title>(?:正在播放\s*)?(.*?)</title>", html_text, re.I)
            page_title = tm.group(1).strip() if tm else "精彩视频"
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
                    "vod_play_from": "Zaka专线",
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