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
        self.siteHost = "https://dzf.lcfd3.lat"
        self.entryPrefix = "/cn/home/web/index.php"
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
            "Referer": self.siteHost + self.entryPrefix + "/",
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

    # 1. 首页：固化提纯后的原生内生分类矩阵，零多余网络开销
    def homeContent(self, *args, **kwargs):
        return {
            "class": [
                {"type_name": "乱伦", "type_id": "1"},
                {"type_name": "出轨", "type_id": "2"},
                {"type_name": "制服", "type_id": "3"},
                {"type_name": "自慰", "type_id": "4"},
                {"type_name": "偷拍", "type_id": "5"},
                {"type_name": "自拍", "type_id": "20"},
                {"type_name": "国产", "type_id": "21"},
                {"type_name": "同性", "type_id": "22"},
                {"type_name": "日韩", "type_id": "23"},
                {"type_name": "欧美", "type_id": "24"},
                {"type_name": "三级", "type_id": "25"},
                {"type_name": "动漫", "type_id": "26"}
            ]
        }

    # 2. 列表页：纯净提纯真实卡片，全面剔除广告、搜索热词与诊断卡片
    def categoryContent(self, tid, pg, *args, **kwargs):
        page_num = str(pg or "1").strip()
        tid = str(tid).strip()

        if page_num == "1":
            target_path = "%s/vod/type/id/%s.html" % (self.entryPrefix, tid)
        else:
            target_path = "%s/vod/type/id/%s/page/%s.html" % (self.entryPrefix, tid, page_num)

        res = self._fetch(target_path)
        html_text = res.get("text", "")

        vod_list = []
        card_matches = re.findall(r'(<a[^>]+href=["\']([^"\']*vod/play/id/[^"\']+)["\'][^>]*>([\s\S]*?)</a>)', html_text, re.I)
        seen_urls = set()

        for full_a, play_href, inner in card_matches:
            clean_href = play_href.strip()
            if clean_href in seen_urls:
                continue
            seen_urls.add(clean_href)

            title_m = re.search(r'title=["\']([^"\']+)["\']', full_a, re.I)
            if title_m:
                title = title_m.group(1).strip()
            else:
                title = re.sub(r'<[^>]+>', '', inner).strip()

            if not title or any(k in title for k in ("上一页", "下一页", "尾页", "首页", "排行榜", "搜索")):
                continue

            pic = ""
            img_m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', inner, re.I)
            if not img_m:
                img_m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', full_a, re.I)
            if img_m:
                pic = img_m.group(1).strip()
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

    # 3. 详情页：直链极速还原与官方品牌模板封装
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

            # 提取核心直链
            raw_url = ""
            url_match = re.search(r'player_data[\s\S]*?["\']url["\']\s*:\s*["\']([^"\']+)["\']', html_text)
            if url_match:
                raw_url = url_match.group(1).strip()
            else:
                url_match2 = re.search(r'["\']url["\']\s*:\s*["\'](https?[^"\']+)["\']', html_text)
                if url_match2:
                    raw_url = url_match2.group(1).strip()

            # 提取 encrypt 标志
            enc_match = re.search(r'player_data[\s\S]*?["\']encrypt["\']\s*:\s*(\d+)', html_text)
            encrypt_flag = enc_match.group(1).strip() if enc_match else "0"

            # 苹果 CMS 加解密调度
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

            # 标题提取与清洗
            title_m = re.search(r'<title>(.*?)</title>', html_text, re.I)
            page_title = title_m.group(1).strip() if title_m else "精彩视频"
            page_title = re.sub(r'(-|\||_).*$', '', page_title).strip()

            # 简介提取
            clean_content = ""
            desc_m = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']', html_text, re.I)
            if desc_m:
                clean_content = desc_m.group(1).strip()

            # 品牌与版权规范结构
            custom_notice = "【💡 温馨提示：视频加载如遇卡顿请尝试切换网络或快进。】"
            group_info = "【🔥 官方交流群: %s】" % self.tgGroup

            if clean_content:
                vod_content = "%s\n\n%s\n\n%s" % (group_info, custom_notice, clean_content)
            else:
                vod_content = "%s\n\n%s\n\n暂无详细简介，欢迎加入TG群获取最新资源！" % (group_info, custom_notice)

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

    # 4. 播放器：parse: 0 直连交付，附带合规 Header
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