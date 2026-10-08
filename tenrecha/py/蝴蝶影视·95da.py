#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import re
import json
import base64
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

def format_remarks(brand="蝴蝶影视", meta=""):
    clean_meta = str(meta or "").strip()
    clean_meta = re.sub(r"[\r\n\t]+", " ", clean_meta).strip()
    if clean_meta:
        return "%s | %s" % (brand, clean_meta)
    return brand

class Spider(SpiderBase):
    def __init__(self):
        super(Spider, self).__init__()
        self.siteUrl = "https://edj.352963.xyz"
        self.tgGroup = "https://t.me/tvshare23"
        self.brandActor = "🦋 TG群: @tvshare23"
        self.brandDirector = "🦋 蝴蝶影视"
        self._ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        self.options = {}

        self.zone_names = ["视频一区", "视频二区", "视频三区", "视频四区", "视频五区"]
        self.classes = [
            {"type_name": name, "type_id": "zone_%d" % (idx + 1)}
            for idx, name in enumerate(self.zone_names)
        ]

        self.sub_names_matrix = [
            ["国产精品", "国产传媒", "外围探花", "大神作品", "网黄女神", "良家人妻", "直播大秀", "夫妻交换"],
            ["绿帽淫妻", "近亲乱伦", "强奸迷奸", "亚洲媚黑", "港台三级", "情侣泄密", "浴室偷拍", "酒店偷拍"],
            ["女性按摩", "街拍抄底", "家庭监控", "激情艳舞", "模特私拍", "裸贷裸条", "字母调教", "捆绑绳艺"],
            ["变态重口", "户外露出", "男女直播", "学妹直播", "美女直播", "户外直播", "淫乱直播", "直播精品"],
            ["日韩伦理", "网红流出", "x福利姬", "金主定制", "丝足诱惑", "成人动漫", "TSCD变性", "厕拍偷拍"]
        ]

        self.filters = {}
        self.zone_default_cid = {}

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

        self._init_zone_filters()
        return True

    def getName(self):
        return "蝴蝶影视·95da"

    def isVideoFormat(self, url):
        low = (url or "").lower()
        return any(k in low for k in (".m3u8", ".mp4", ".flv", ".mkv", ".avi", ".ts", ".mpd", "index.png"))

    def manualVideoCheck(self):
        return False

    def _decrypt_payload(self, raw_html):
        m = re.search(r"['\"]([A-Za-z0-9+/=]{100,})['\"]\s*\.split\(['\"]['\"]\)\.reverse\(\)\.join\(['\"]['\"]", raw_html)
        if not m:
            m = re.search(r"\bvar\s+[a-zA-Z0-9_$]+\s*=\s*[a-zA-Z0-9_$]+\s*\(\s*['\"]([A-Za-z0-9+/=]{100,})['\"]", raw_html)
        if not m:
            return raw_html

        cipher = m.group(1)
        try:
            rev = cipher[::-1]
            b_data = base64.b64decode(rev)
            return b_data.decode("utf-8", errors="ignore")
        except Exception:
            return raw_html

    def _fetch(self, target_url, referer=""):
        if not target_url:
            return {"code": 0, "text": "", "bytes": b"", "err": "", "final_url": ""}
        if target_url.startswith("//"):
            target_url = "https:" + target_url
        elif target_url.startswith("/"):
            target_url = self.siteUrl + target_url

        headers = {
            "User-Agent": self._ua,
            "Referer": referer if referer else (self.siteUrl + "/"),
            "Origin": self.siteUrl,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive"
        }

        for attempt in range(2):
            try:
                req = urllib.request.Request(target_url, headers=headers)
                with self.opener.open(req, timeout=10) as resp:
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
                if e.code in (451, 403, 429) and attempt == 0:
                    continue
                err_raw = ""
                try:
                    err_raw = e.read().decode("utf-8", errors="ignore")
                except Exception:
                    pass
                return {"code": e.code, "text": err_raw, "bytes": b"", "err": str(e), "final_url": target_url}
            except Exception as e:
                if attempt == 0:
                    continue
                return {"code": -1, "text": "", "bytes": b"", "err": str(e), "final_url": target_url}

        return {"code": -1, "text": "", "bytes": b"", "err": "timeout", "final_url": target_url}

    def _init_zone_filters(self):
        js_url = urllib.parse.urljoin(self.siteUrl, "/html/js/i1789810722.js")
        res = self._fetch(js_url)
        js_text = res.get("text", "")

        cids = []
        if js_text:
            h_match = re.search(r"(?:var\s+)?h\s*=\s*['\"]([A-Za-z0-9+/=]+)['\"]", js_text)
            if h_match:
                try:
                    tpl_html = base64.b64decode(h_match.group(1)).decode("utf-8", errors="ignore")
                    found_cids = re.findall(r'/list/([0-9]+)-[0-9]+\.html', tpl_html)
                    seen = set()
                    for cid in found_cids:
                        if cid not in seen:
                            seen.add(cid)
                            cids.append(cid)
                except Exception:
                    pass

        for z_idx, z_item in enumerate(self.classes):
            z_key = z_item["type_id"]
            names = self.sub_names_matrix[z_idx]
            sub_options = []

            for s_idx, name in enumerate(names):
                global_idx = z_idx * 8 + s_idx
                cid = cids[global_idx] if global_idx < len(cids) else ("20%02d0496" % (global_idx + 1))
                sub_options.append({"n": name, "v": cid})

            if sub_options:
                self.zone_default_cid[z_key] = sub_options[0]["v"]
                self.filters[z_key] = [
                    {
                        "key": "sub_cid",
                        "name": "分类",
                        "init": sub_options[0]["v"],
                        "value": sub_options
                    }
                ]

    def homeContent(self, filter):
        if not self.filters:
            self._init_zone_filters()

        result = {"class": self.classes}
        if filter:
            result["filters"] = self.filters
        return result

    def homeVideoContent(self):
        first_zone = self.classes[0]["type_id"]
        res = self.categoryContent(first_zone, 1, False, {})
        return {"list": res.get("list", [])}

    def categoryContent(self, tid, pg, filter, extend):
        del filter
        zone_id = str(tid).strip("/")
        page = int(pg) if str(pg).isdigit() else 1

        if not self.filters:
            self._init_zone_filters()

        target_cid = ""
        if isinstance(extend, dict) and extend.get("sub_cid"):
            target_cid = str(extend.get("sub_cid")).strip()
        if not target_cid:
            target_cid = self.zone_default_cid.get(zone_id, "20110496")

        target_path = "/list/%s-%d.html" % (target_cid, page)
        target_url = urllib.parse.urljoin(self.siteUrl, target_path)

        res = self._fetch(target_url)
        raw_html = res.get("text", "")
        if not raw_html:
            return {"page": page, "pagecount": 1, "limit": 20, "total": 0, "list": []}

        plain_html = self._decrypt_payload(raw_html)

        j_b64_m = re.search(r"var\s+j_b64\s*=\s*['\"]([A-Za-z0-9+/=]+)['\"]", plain_html)
        if not j_b64_m:
            j_b64_m = re.search(r"['\"]j_b64['\"]\s*:\s*['\"]([A-Za-z0-9+/=]+)['\"]", plain_html)

        vod_list = []
        if j_b64_m:
            try:
                dec_bytes = base64.b64decode(j_b64_m.group(1))
                json_str = dec_bytes.decode("utf-8", errors="ignore")
                p_data = json.loads(json_str)

                raw_items = []
                if "l" in p_data and isinstance(p_data["l"], dict):
                    for k, sub_arr in p_data["l"].items():
                        if isinstance(sub_arr, list):
                            raw_items.extend(sub_arr)
                elif isinstance(p_data, list):
                    raw_items = p_data

                for itm in raw_items:
                    v_title = itm.get("title", "")
                    v_url = itm.get("url", "")
                    v_pic = itm.get("pic", "")
                    v_dur = itm.get("duration", "")

                    if not v_title or not v_url:
                        continue

                    remarks = format_remarks("蝴蝶影视", v_dur)

                    p_info = json.dumps({"t": v_title, "p": v_pic, "u": v_url}, ensure_ascii=False)
                    pack_id = "vpack_" + base64.urlsafe_b64encode(p_info.encode("utf-8")).decode("utf-8")

                    vod_list.append({
                        "vod_id": pack_id,
                        "vod_name": v_title,
                        "vod_pic": v_pic,
                        "vod_remarks": remarks,
                        "style": {"type": "rect", "ratio": 1.78}
                    })
            except Exception:
                pass

        page_count = page + 1 if len(vod_list) >= 20 else page

        return {
            "page": page,
            "pagecount": page_count,
            "limit": 20,
            "total": 999,
            "list": vod_list
        }

    def detailContent(self, ids):
        raw_id = ids[0] if isinstance(ids, (list, tuple)) else str(ids)
        
        v_title = "正片播放"
        v_pic = ""
        v_url = raw_id

        if str(raw_id).startswith("vpack_"):
            try:
                dec_json = base64.urlsafe_b64decode(raw_id[6:].encode("utf-8")).decode("utf-8")
                info = json.loads(dec_json)
                v_title = info.get("t", v_title)
                v_pic = info.get("p", v_pic)
                v_url = info.get("u", v_url)
            except Exception:
                pass
        elif "@@" in raw_id:
            parts = raw_id.split("@@")
            if len(parts) >= 3:
                v_title = unquote(parts[0])
                v_pic = unquote(parts[1])
                v_url = unquote(parts[2])

        full_detail_url = v_url if v_url.startswith("http") else urllib.parse.urljoin(self.siteUrl, v_url)

        res = self._fetch(full_detail_url)
        plain_html = self._decrypt_payload(res.get("text", ""))

        j_b64_m = re.search(r"var\s+j_b64\s*=\s*['\"]([A-Za-z0-9+/=]+)['\"]", plain_html)
        if not j_b64_m:
            j_b64_m = re.search(r"['\"]j_b64['\"]\s*:\s*['\"]([A-Za-z0-9+/=]+)['\"]", plain_html)

        from_list = []
        url_list = []

        if j_b64_m:
            try:
                dec_bytes = base64.b64decode(j_b64_m.group(1))
                detail_data = json.loads(dec_bytes.decode("utf-8", errors="ignore"))

                direct_m3 = detail_data.get("m3", "")
                if direct_m3 and direct_m3.startswith("http"):
                    from_list.append("🦋 极速直链")
                    url_list.append("正片$%s" % direct_m3)

                cdn_arr = detail_data.get("cdn", [])
                for idx, cdn_item in enumerate(cdn_arr):
                    c_name = cdn_item.get("name") or ("线路%d" % (idx + 1))
                    c_url = cdn_item.get("url") or ""
                    if c_url:
                        from_list.append("🦋 %s" % c_name)
                        url_list.append("正片$%s" % c_url)
            except Exception:
                pass

        if not from_list:
            from_list = ["🦋 蝴蝶备用"]
            url_list = ["正片$%s" % full_detail_url]

        desc = (
            "【🔥 官方交流群: %s】\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "视频片名: %s\n"
            "极速直链与多线 CDN 均已就绪，首推【极速直链】线路秒开起播！"
        ) % (self.tgGroup, v_title)

        escaped_desc = desc.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        return {
            "list": [{
                "vod_id": raw_id,
                "vod_name": v_title,
                "vod_pic": v_pic,
                "vod_actor": self.brandActor,
                "vod_director": self.brandDirector,
                "vod_remarks": "蝴蝶影视",
                "vod_content": escaped_desc,
                "vod_play_from": "$$$".join(from_list),
                "vod_play_url": "$$$".join(url_list)
            }]
        }

    def playerContent(self, flag, id, vipFlags):
        del flag, vipFlags
        raw_url = str(id).strip()
        final_m3u8 = raw_url

        if "/api.php" in raw_url:
            res = self._fetch(raw_url, referer=self.siteUrl + "/")
            txt = res.get("text", "")
            try:
                data = json.loads(txt)
                if data.get("m3u8Url"):
                    final_m3u8 = data["m3u8Url"]
                elif data.get("url"):
                    final_m3u8 = data["url"]
            except Exception:
                m_match = re.search(r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', txt)
                if m_match:
                    final_m3u8 = m_match.group(1).replace("\\/", "/")

        return {
            "parse": 0,
            "playUrl": "",
            "url": final_m3u8,
            "header": {
                "User-Agent": self._ua,
                "Referer": self.siteUrl + "/",
                "Origin": self.siteUrl
            }
        }

    def searchContent(self, key, quick, pg="1"):
        return {"page": 1, "pagecount": 1, "limit": 0, "total": 0, "list": []}

    def action(self, action):
        return {"msg": "运行正常"}

    def liveContent(self):
        return ""

    def localProxy(self, params):
        return [404, "text/plain; charset=utf-8", "Proxy not configured"]

    def destroy(self):
        self.options = {}