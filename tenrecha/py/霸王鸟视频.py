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
        self.siteHost = "https://xn--cl0a.bawangniao.click"
        self.tgGroup = "https://t.me/tvshare23"
        self.brandActor = "🦋 TG群: @tvshare23"
        self.brandDirector = "🦋 蝴蝶影视"
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
            target_url = self.siteHost + target_url

        headers = {
            "User-Agent": self._ua,
            "Referer": self.siteHost + "/welcome/",
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

    # 1. 首页：固化提纯后的 15 个内生分类
    def homeContent(self, *args, **kwargs):
        return {
            "class": [
                {"type_name": "国产视频", "type_id": "guochan"},
                {"type_name": "中文字幕", "type_id": "zhongwenzimu"},
                {"type_name": "AV明星", "type_id": "avmingxing"},
                {"type_name": "日韩无码", "type_id": "renhanwuma"},
                {"type_name": "自拍偷拍", "type_id": "zipai"},
                {"type_name": "制服诱惑", "type_id": "fuzhuang"},
                {"type_name": "口交口爆", "type_id": "zuiqu"},
                {"type_name": "多人运动", "type_id": "duorenyundong"},
                {"type_name": "巨乳尤物", "type_id": "juruyouwu"},
                {"type_name": "强奸乱伦", "type_id": "qiangluan"},
                {"type_name": "欧美精品", "type_id": "oumeijingpin"},
                {"type_name": "特殊职业", "type_id": "zhiye"},
                {"type_name": "自慰系列", "type_id": "weixi"},
                {"type_name": "邻家人妻", "type_id": "lingjiarenqi"},
                {"type_name": "SM重味", "type_id": "zhongweism"}
            ]
        }

    # 2. 列表页：纯净视频卡片提取
    def categoryContent(self, tid, pg, *args, **kwargs):
        page_num = str(pg or "1").strip()
        tid = str(tid).strip()

        if page_num == "1":
            target_path = "/videos/categories/%s/" % tid
        else:
            target_path = "/videos/categories/%s/?page=%s" % (tid, page_num)

        res = self._fetch(target_path)
        html_text = res.get("text", "")

        card_matches = re.findall(r'(<a[^>]+href=["\']([^"\']*(?:/video/|/videos/|/play/)[^"\']+)["\'][^>]*>([\s\S]*?)</a>)', html_text, re.I)
        
        vod_list = []
        seen_urls = set()

        for full_a, v_href, inner in card_matches:
            clean_href = v_href.strip()
            if clean_href in seen_urls or "/categories/" in clean_href:
                continue
            seen_urls.add(clean_href)

            title = ""
            title_m = re.search(r'title=["\']([^"\']+)["\']', full_a, re.I)
            if title_m:
                title = title_m.group(1).strip()
            else:
                title = re.sub(r'<[^>]+>', '', inner).strip()

            if not title or len(title) < 2 or any(k in title for k in ("下一页", "上一页", "首页", "尾页", "返回")):
                continue

            pic = ""
            img_m = re.search(r'<img[^>]+data-original=["\']([^"\']+)["\']', inner, re.I)
            if not img_m:
                img_m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', inner, re.I)
            if img_m:
                val = img_m.group(1).strip()
                if not val.startswith("data:image"):
                    pic = val

            if pic.startswith("//"):
                pic = "https:" + pic
            elif pic.startswith("/"):
                pic = self.siteHost + pic

            safe_id = "v_" + base64.urlsafe_b64encode(clean_href.encode("utf-8")).decode("utf-8").rstrip("=")

            vod_list.append({
                "vod_id": safe_id,
                "vod_name": self._unesc(title),
                "vod_pic": pic,
                "vod_remarks": "高清"
            })

        return {
            "page": int(page_num),
            "pagecount": 99,
            "limit": len(vod_list),
            "total": 99,
            "list": vod_list
        }

    # 3. 详情页：直接提取流媒体直链与标准回显
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

            decrypted_url = ""

            # 核心规则：提取 JS video_url 变量
            js_v = re.search(r'(?:video_url|videoUrl|file)\s*[:=]\s*["\'](https?://[^"\']+)["\']', html_text, re.I)
            if js_v:
                decrypted_url = js_v.group(1).strip()

            # 兜底规则：正则匹配页面内的 m3u8 与 mp4
            if not decrypted_url:
                m3u8_m = re.search(r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', html_text, re.I)
                if m3u8_m:
                    decrypted_url = m3u8_m.group(1).strip()
                else:
                    mp4_m = re.search(r'["\'](https?://[^"\']+\.mp4[^"\']*)["\']', html_text, re.I)
                    if mp4_m:
                        decrypted_url = mp4_m.group(1).strip()

            if decrypted_url:
                decrypted_url = decrypted_url.replace(r"\/", "/")

            title_m = re.search(r'<title>(.*?)</title>', html_text, re.I)
            page_title = title_m.group(1).strip() if title_m else "精彩视频"
            page_title = re.sub(r'(-|\||_).*$', '', page_title).strip()

            # 简介信息
            desc_m = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']', html_text, re.I)
            clean_content = desc_m.group(1).strip() if desc_m else ""

            custom_notice = "【💡 温馨提示：如遇加载较慢请稍作等待或快进缓冲。】"
            group_info = "【🔥 官方交流群: %s】" % self.tgGroup

            if clean_content:
                vod_content = "%s\n\n%s\n\n%s" % (group_info, custom_notice, clean_content)
            else:
                vod_content = "%s\n\n%s\n\n暂无简介，欢迎加入官方群交流！" % (group_info, custom_notice)

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

    # 4. 播放器：parse: 0 免二次解析直传
    def playerContent(self, flag, id, vipFlags):
        real_url = str(id).strip()
        return {
            "parse": 0,
            "playUrl": "",
            "url": real_url,
            "header": json.dumps({
                "User-Agent": self._ua,
                "Referer": self.siteHost + "/"
            })
        }

    # 5. 搜索保底实现
    def searchContent(self, key, quick, pg="1"):
        return {"list": []}