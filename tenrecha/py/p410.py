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
            "http://www.bdjmcc.com",
            "https://www.bdjmcc.com",
            "http://bdjmcc.com",
            "https://bdjmcc.com"
        ]
        self.currentDomain = self.domains[0]
        self.tgGroup = "https://t.me/+3t5XRPPo9mlkZDRl"
        self.brandActor = "📺TG群: https://t.me/+3t5XRPPo9mlkZDRl"
        self.brandDirector = "📺ZakaTV"
        self._ua = "Mozilla/5.0 (Linux; Android 12; Pixel 6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"

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
        return any(k in low for k in (".m3u8", ".mp4", ".flv", ".mkv", ".avi", ".ts"))

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

    def _is_valid_html(self, html_text):
        if not html_text or len(html_text) < 300:
            return False
        block_keywords = ("发布页", "enter-link", "enter-maomi", "点击进入", "Just a moment...", "Attention Required")
        for kw in block_keywords:
            if kw in html_text:
                return False
        return True

    def _fetch_safe(self, path, referer="", headers_extra=None, raw_bytes=False):
        candidates = [self.currentDomain] + [d for d in self.domains if d != self.currentDomain]

        for domain in candidates:
            if path.startswith("http://") or path.startswith("https://"):
                target_url = path
            else:
                target_url = domain + path if path.startswith("/") else (domain + "/" + path)

            headers = {
                "User-Agent": self._ua,
                "Referer": referer if referer else (domain + "/"),
                "Accept": "*/*",
                "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
                "Connection": "close"
            }
            if headers_extra:
                headers.update(headers_extra)

            try:
                req = urllib.request.Request(target_url, headers=headers)
                with self.opener.open(req, timeout=10) as resp:
                    code = resp.getcode()
                    if code != 200:
                        continue

                    raw = resp.read()
                    if raw.startswith(b"\x1f\x8b"):
                        raw = gzip.decompress(raw)
                    elif getattr(resp, "headers", {}).get("Content-Encoding") == "deflate":
                        try:
                            raw = zlib.decompress(raw)
                        except Exception:
                            raw = zlib.decompress(raw, -zlib.MAX_WBITS)

                    if raw_bytes:
                        return {"code": code, "bytes": raw, "text": "", "err": ""}

                    try:
                        text = raw.decode("utf-8")
                    except Exception:
                        try:
                            text = raw.decode("gbk")
                        except Exception:
                            text = raw.decode("latin1", errors="ignore")

                    if not (path.startswith("http://") or path.startswith("https://")):
                        if not self._is_valid_html(text):
                            continue

                    if not (path.startswith("http://") or path.startswith("https://")):
                        if domain != self.currentDomain:
                            self.currentDomain = domain

                    return {"code": code, "text": text, "bytes": raw, "err": ""}
            except Exception:
                continue

        return {"code": -1, "text": "", "bytes": b"", "err": "请求失败"}

    def _parse_cards(self, html_text):
        card_blocks = re.findall(r'(<a[^>]+href=["\'](/v/[a-zA-Z0-9_-]+\.html)["\'][^>]*>[\s\S]*?</a>)', html_text, re.I)
        video_list = []
        seen_ids = set()
        noise_words = ("上一页", "下一页", "尾页", "首页", "查看更多", "详情")

        for block, v_href in card_blocks:
            if v_href in seen_ids:
                continue

            t_match = re.search(r'title=["\']([^"\']+)["\']', block, re.I)
            clean_title = t_match.group(1).strip() if t_match else re.sub(r'<[^>]+>', '', block).strip()
            clean_title = re.sub(r'\s+', ' ', clean_title)

            if not clean_title or any(w in clean_title for w in noise_words) or len(clean_title) <= 1:
                continue

            seen_ids.add(v_href)

            pic_url = ""
            p_match = re.search(r'data-original=["\']([^"\']+)["\']', block, re.I)
            if p_match:
                pic_url = p_match.group(1).strip()
            if not pic_url:
                s_match = re.search(r'src=["\']([^"\']+)["\']', block, re.I)
                if s_match and not s_match.group(1).strip().startswith("data:image"):
                    pic_url = s_match.group(1).strip()

            if pic_url.startswith("//"):
                pic_url = "https:" + pic_url
            elif pic_url.startswith("/"):
                pic_url = self.currentDomain + pic_url

            remarks_match = re.search(r'<span[^>]*class=["\'][^"\']*dfgdfgf[^"\']*["\'][^>]*>([\s\S]*?)</span>', block, re.I)
            if not remarks_match:
                remarks_match = re.search(r'<span[^>]*class=["\'][^"\']*(?:remarks|note|state|text-right)[^"\']*["\'][^>]*>([\s\S]*?)</span>', block, re.I)
            remarks = remarks_match.group(1).strip() if remarks_match else ""

            safe_id = "v_" + base64.urlsafe_b64encode(v_href.encode("utf-8")).decode("utf-8").rstrip("=")

            video_list.append({
                "vod_id": safe_id,
                "vod_name": clean_title,
                "vod_pic": pic_url,
                "vod_remarks": remarks
            })
        return video_list

    def homeContent(self, filter=False):
        classes = [
            {"type_name": "连续剧", "type_id": "A051pCM47kBg2"},
            {"type_name": "电影", "type_id": "A1sQHJp3ggh3P"},
            {"type_name": "动漫", "type_id": "A2yIcGx03608i"},
            {"type_name": "综艺", "type_id": "A1U43X24bwf2t"}
        ]

        filters = {
            "A051pCM47kBg2": [
                {
                    "key": "sub_tid",
                    "name": "类型",
                    "value": [
                        {"n": "全部", "v": ""},
                        {"n": "国产剧", "v": "A0hLbxS3mdi9Z"},
                        {"n": "港台剧", "v": "A3acP230qrYEa"},
                        {"n": "欧美剧", "v": "A26Nql80kYj9l"},
                        {"n": "韩国剧", "v": "A0lzOAf2AnMYc"},
                        {"n": "日本剧", "v": "A3CGBFG0fQSp3"},
                        {"n": "泰国剧", "v": "A1Orj7n0sv4s5"},
                        {"n": "其他剧", "v": "A3yycoq1C7ZVU"}
                    ]
                }
            ],
            "A1sQHJp3ggh3P": [
                {
                    "key": "sub_tid",
                    "name": "类型",
                    "value": [
                        {"n": "全部", "v": ""},
                        {"n": "喜剧", "v": "A2ZwOUA4eaYwf"},
                        {"n": "动作", "v": "A0mXwMh43XY4p"},
                        {"n": "爱情", "v": "A3Meq3k0Tezgj"},
                        {"n": "恐怖", "v": "A4SXB0s2ndOVj"},
                        {"n": "犯罪", "v": "A2f8itP1la8Rv"},
                        {"n": "剧情", "v": "A1AuA9U0K1cOR"},
                        {"n": "奇幻", "v": "A44AxE519ugB7"},
                        {"n": "战争", "v": "A2GmV6c1gqj6w"},
                        {"n": "悬疑", "v": "A0TO2z91gaOAS"},
                        {"n": "动画", "v": "A4l8WCO4HYvub"},
                        {"n": "科幻", "v": "A1ZGNwH3MCXg7"},
                        {"n": "其他片", "v": "A2Uk44v27gayS"}
                    ]
                }
            ],
            "A2yIcGx03608i": [
                {
                    "key": "sub_tid",
                    "name": "类型",
                    "value": [
                        {"n": "全部", "v": ""},
                        {"n": "国漫", "v": "A2BaAhN0y27Zr"},
                        {"n": "日漫", "v": "A0OBiZu0aFUwF"},
                        {"n": "其他动漫", "v": "A3HSVeV2PEdwr"}
                    ]
                }
            ],
            "A1U43X24bwf2t": [
                {
                    "key": "sub_tid",
                    "name": "类型",
                    "value": [
                        {"n": "全部", "v": ""},
                        {"n": "国产综艺", "v": "A1jf2kl0SLzeU"},
                        {"n": "港澳综艺", "v": "A4gUjzb24vEsg"},
                        {"n": "日韩综艺", "v": "A1nDwua2qYC8K"},
                        {"n": "其他综艺", "v": "A2t6Hri39mDKQ"}
                    ]
                }
            ]
        }

        res = self._fetch_safe("/")
        rec_list = self._parse_cards(res.get("text", ""))

        return {
            "class": classes,
            "filters": filters,
            "list": rec_list
        }

    def homeVideoContent(self):
        res = self._fetch_safe("/")
        return {"list": self._parse_cards(res.get("text", ""))}

    def categoryContent(self, tid, pg, filter=False, extend=None, *args, **kwargs):
        try:
            page_num = max(1, int(str(pg).strip() or 1))
        except Exception:
            page_num = 1

        f = {}
        ff = self._dict(filter)
        if ff:
            f.update(ff)
        fe = self._dict(extend)
        if fe:
            f.update(fe)

        for k in ("extend", "ext", "filter"):
            if k in kwargs:
                f.update(self._dict(kwargs.get(k)))

        clean_tid = str(tid).strip("/")
        actual_tid = f.get("sub_tid") or clean_tid

        target_path = "/list/%s/%d.html" % (actual_tid, page_num)

        res = self._fetch_safe(target_path)
        html_text = res.get("text", "")
        vods = self._parse_cards(html_text)

        return {
            "page": page_num,
            "pagecount": 99,
            "limit": 20,
            "total": 999,
            "list": vods
        }

    def detailContent(self, ids):
        raw_id = self._list(ids)[0] if self._list(ids) else ""
        if not raw_id:
            return {"list": []}

        detail_path = ""
        if str(raw_id).startswith("v_"):
            try:
                b64_str = raw_id[2:]
                pad = len(b64_str) % 4
                if pad:
                    b64_str += "=" * (4 - pad)
                detail_path = base64.urlsafe_b64decode(b64_str.encode("utf-8")).decode("utf-8")
            except Exception:
                detail_path = str(raw_id)
        else:
            detail_path = str(raw_id)

        res = self._fetch_safe(detail_path)
        html_text = res.get("text", "")

        title_m = re.search(r'<h1[^>]*>([\s\S]*?)</h1>', html_text, re.I)
        vod_title = re.sub(r'<[^>]+>', '', title_m.group(1)).strip() if title_m else "未知片名"

        desc_m = re.search(r'<div[^>]*class=["\'][^"\']*(?:desc|content|detail-content|plot|intro)[^"\']*["\'][^>]*>([\s\S]*?)</div>', html_text, re.I)
        clean_content = re.sub(r'<[^>]+>', '', desc_m.group(1)).strip() if desc_m else ""

        p_links = re.findall(r'<a\s+[^>]*href=["\'](/p/[^"\']+)["\'][^>]*>([\s\S]*?)</a>', html_text, re.I)
        episodes = []
        seen_ep_href = set()
        for p_href, p_text in p_links:
            if p_href in seen_ep_href:
                continue
            seen_ep_href.add(p_href)
            clean_t = re.sub(r'<[^>]+>', '', p_text).strip()
            clean_t = re.sub(r'\s+', ' ', clean_t)
            if not clean_t:
                clean_t = "播放"
            episodes.append("%s$%s" % (clean_t, p_href))

        custom_notice = "【💡 温馨提示：视频加载如遇卡顿请尝试切换线路或快进。】"
        group_info = "【🔥 官方交流群: %s】" % self.tgGroup

        if clean_content:
            vod_content = "%s\n\n%s\n\n%s" % (group_info, custom_notice, clean_content)
        else:
            vod_content = "%s\n\n%s\n\n暂无详细简介，欢迎加入TG群获取最新资源！" % (group_info, custom_notice)

        play_str = "#".join(episodes) if episodes else "正片$http://127.0.0.1"

        return {
            "list": [{
                "vod_id": raw_id,
                "vod_name": vod_title,
                "vod_pic": "",
                "vod_actor": self.brandActor,
                "vod_director": self.brandDirector,
                "vod_remarks": "全%s集" % len(episodes),
                "vod_content": vod_content,
                "vod_play_from": "北斗专线",
                "vod_play_url": play_str
            }]
        }

    def playerContent(self, flag, id, vipFlags):
        raw_target = str(id).strip()
        final_stream_url = ""

        if raw_target.startswith("/p/"):
            sub_res = self._fetch_safe(raw_target)
            sub_html = sub_res.get("text", "")

            v_match = re.search(r'player\.html\?v=([a-zA-Z0-9_-]+)', sub_html)
            if not v_match:
                v_match = re.search(r'[?&]v=([a-zA-Z0-9_-]+)', sub_html)

            if v_match:
                v_param = v_match.group(1)
                proxy_url = "https://ttss.langfeng888.com/proxy/%s" % v_param
                proxy_headers = {
                    "User-Agent": self._ua,
                    "Referer": "https://ttss.langfeng888.com/d5xc/player.html?v=%s" % v_param,
                    "Accept": "application/json, text/plain, */*",
                    "Connection": "close"
                }

                try:
                    req = urllib.request.Request(proxy_url, headers=proxy_headers)
                    with self.opener.open(req, timeout=12) as resp:
                        api_text = resp.read().decode("utf-8", errors="ignore")
                        data = json.loads(api_text)
                        if isinstance(data, dict):
                            final_stream_url = data.get("url") or data.get("data", {}).get("url") or data.get("play_url") or ""
                except Exception:
                    pass

        if not final_stream_url:
            final_stream_url = raw_target

        play_headers = {
            "User-Agent": self._ua,
            "Accept": "*/*",
            "Connection": "keep-alive"
        }

        return {
            "parse": 0,
            "playUrl": "",
            "url": final_stream_url,
            "header": json.dumps(play_headers)
        }

    def searchContent(self, key, quick, pg="1"):
        try:
            page_num = max(1, int(str(pg).strip() or 1))
        except Exception:
            page_num = 1

        if not key:
            return {"list": []}

        try:
            token = base64.urlsafe_b64encode(key.strip().encode("utf-8")).decode("utf-8").rstrip("=")
        except Exception:
            token = ""

        if not token:
            return {"list": []}

        search_path = "/search/%s/%d.html" % (token, page_num)
        res = self._fetch_safe(search_path)
        vods = self._parse_cards(res.get("text", ""))

        return {
            "page": page_num,
            "pagecount": 99,
            "limit": 20,
            "total": 999,
            "list": vods
        }