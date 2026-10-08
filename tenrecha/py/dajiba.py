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
            "https://k1.dajiji.us.cc",
            "https://ccc.djj88.sbs",
            "https://dajiji.sbs",
            "https://k2.dajiji.us.cc"
        ]
        self.currentDomain = self.domains[0]
        self.tgGroup = "https://t.me/tvshare23"
        self.brandActor = "🦋 TG群: @tvshare23"
        self.brandDirector = "🦋 蝴蝶影视"
        self._ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

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

    def _clean_url(self, raw_url):
        if not raw_url:
            return ""
        unquoted = urllib.parse.unquote(raw_url)
        parts = urllib.parse.urlsplit(unquoted)
        path = urllib.parse.quote(parts.path, safe="/:@&=+$,?#")
        query = urllib.parse.quote(parts.query, safe="/:@&=+$,?#")
        return urllib.parse.urlunsplit((parts.scheme, parts.netloc, path, query, parts.fragment))

    def _fetch_safe(self, path, referer="", headers_extra=None, raw_bytes=False):
        candidates = [self.currentDomain] + [d for d in self.domains if d != self.currentDomain]

        for domain in candidates:
            if path.startswith("http://") or path.startswith("https://"):
                target_url = self._clean_url(path)
            else:
                target_url = self._clean_url(domain + path if path.startswith("/") else (domain + "/" + path))

            headers = {
                "User-Agent": self._ua,
                "Referer": referer if referer else (domain + "/"),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Connection": "close"
            }
            if headers_extra:
                headers.update(headers_extra)

            try:
                req = urllib.request.Request(target_url, headers=headers)
                with self.opener.open(req, timeout=12) as resp:
                    code = resp.getcode()
                    if code != 200:
                        continue

                    final_url = resp.geturl()
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

                    parts = urllib.parse.urlsplit(final_url)
                    real_base = "%s://%s" % (parts.scheme, parts.netloc)
                    if real_base and real_base.startswith("http") and real_base != self.currentDomain:
                        self.currentDomain = real_base
                        if real_base not in self.domains:
                            self.domains.insert(0, real_base)

                    return {"code": code, "text": text, "bytes": raw, "err": ""}
            except Exception:
                continue

        return {"code": -1, "text": "", "bytes": b"", "err": "请求失败"}

    def _parse_cards(self, html_text):
        blocks = re.findall(r'(<div[^>]*class=["\'][^"\']*news-thumb[^"\']*["\'][^>]*>[\s\S]*?</div>)', html_text, re.I)
        if not blocks:
            blocks = re.findall(r'(<a[^>]+href=["\'][^"\']*/s/\d+\.htm["\'][^>]*>[\s\S]*?</a>)', html_text, re.I)

        video_list = []
        seen_ids = set()

        for block in blocks:
            href_m = re.search(r'href=["\']([^"\']*/s/(\d+)\.htm)["\']', block, re.I)
            if not href_m:
                continue

            v_href = href_m.group(1).strip()
            vid = href_m.group(2).strip()
            if vid in seen_ids:
                continue

            title = ""
            title_m = re.search(r'title=["\']([^"\']+)["\']', block, re.I)
            if title_m:
                title = title_m.group(1).strip()
            if not title:
                alt_m = re.search(r'alt=["\']([^"\']+)["\']', block, re.I)
                if alt_m:
                    title = alt_m.group(1).strip()
            if not title:
                title = re.sub(r'<[^>]+>', '', block).strip()

            title = re.sub(r'\s+', ' ', title)
            if not title or len(title) <= 1:
                continue

            seen_ids.add(vid)

            pic = ""
            img_m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', block, re.I)
            if img_m:
                raw_pic = img_m.group(1).strip()
                if "url=" in raw_pic:
                    param_url = raw_pic.split("url=", 1)[-1]
                    pic = urllib.parse.unquote(param_url)
                else:
                    pic = raw_pic

            if pic.startswith("//"):
                pic = "https:" + pic
            elif pic.startswith("/"):
                pic = self.currentDomain + pic

            video_list.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": "高清"
            })

        return video_list

    def homeContent(self, filter=False):
        classes = [
            {"type_name": "91探花", "type_id": "91探花"},
            {"type_name": "国产色情", "type_id": "国产色情"},
            {"type_name": "主播直播", "type_id": "主播直播"},
            {"type_name": "自拍偷拍", "type_id": "自拍偷拍"},
            {"type_name": "萝莉少女", "type_id": "萝莉少女"},
            {"type_name": "网曝门", "type_id": "网曝门"},
            {"type_name": "网红流出", "type_id": "网红流出"},
            {"type_name": "Cosplay", "type_id": "cosplay"},
            {"type_name": "素人自拍", "type_id": "素人自拍"},
            {"type_name": "强奸乱伦", "type_id": "强奸乱伦"},
            {"type_name": "日本精品", "type_id": "日本精品"},
            {"type_name": "亚洲有码", "type_id": "亚洲有码"},
            {"type_name": "多人多P", "type_id": "多人多P"}
        ]

        res = self._fetch_safe("/")
        rec_list = self._parse_cards(res.get("text", ""))

        return {
            "class": classes,
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

        clean_slug = urllib.parse.unquote(str(tid).strip("/"))
        clean_slug = clean_slug.replace("s/category/", "").replace("category/", "").strip("/")

        if page_num == 1:
            target_path = "/s/category/%s/" % clean_slug
        else:
            target_path = "/s/category/%s/page/%d/" % (clean_slug, page_num)

        res = self._fetch_safe(target_path)
        vods = self._parse_cards(res.get("text", ""))

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

        detail_path = "/s/%s.htm" % raw_id
        res = self._fetch_safe(detail_path)
        html_text = res.get("text", "")

        t_m = re.search(r'<h1[^>]*>([\s\S]*?)</h1>', html_text, re.I)
        vod_title = re.sub(r'<[^>]+>', '', t_m.group(1)).strip() if t_m else "精彩视频"

        final_stream = ""
        ifr_m = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', html_text, re.I)
        if ifr_m:
            ifr_src = ifr_m.group(1).strip()
            if "url=" in ifr_src:
                extracted = ifr_src.split("url=", 1)[-1]
                final_stream = urllib.parse.unquote(extracted)
            elif ".m3u8" in ifr_src or ".mp4" in ifr_src:
                final_stream = ifr_src

        if not final_stream:
            m_stream = re.search(r'["\'](https?://[^\s"\'<>]+\.(?:m3u8|mp4)[^\s"\'<>]*)["\']', html_text)
            if m_stream:
                final_stream = m_stream.group(1)

        if not final_stream:
            v_tag = re.search(r'<video[^>]+src=["\']([^"\']+\.(?:m3u8|mp4)[^\s"\'<>]*)["\']', html_text, re.I)
            if v_tag:
                final_stream = v_tag.group(1).strip()

        if not final_stream:
            final_stream = detail_path

        custom_notice = "【💡 温馨提示：视频加载如遇卡顿请尝试切换线路或快进。】"
        group_info = "【🔥 官方交流群: %s】" % self.tgGroup
        vod_content = "%s\n\n%s\n\n【说明：本站持续为您搜集全网高清精彩视频，欢迎加入TG群获取最新资源！】" % (group_info, custom_notice)

        return {
            "list": [{
                "vod_id": raw_id,
                "vod_name": vod_title,
                "vod_pic": "",
                "vod_actor": self.brandActor,
                "vod_director": self.brandDirector,
                "vod_remarks": "高清",
                "vod_content": vod_content,
                "vod_play_from": "官方专线",
                "vod_play_url": "正片$%s" % final_stream
            }]
        }

    def playerContent(self, flag, id, vipFlags):
        url = str(id).strip()

        if not self.isVideoFormat(url) and not url.startswith("http"):
            res = self._fetch_safe(url)
            html = res.get("text", "")
            ifr_m = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', html, re.I)
            if ifr_m and "url=" in ifr_m.group(1):
                url = urllib.parse.unquote(ifr_m.group(1).split("url=", 1)[-1])
            else:
                m = re.search(r'["\'](https?://[^\s"\'<>]+\.(?:m3u8|mp4)[^\s"\'<>]*)["\']', html)
                if m:
                    url = m.group(1)

        play_headers = {
            "User-Agent": self._ua,
            "Accept": "*/*",
            "Connection": "keep-alive"
        }

        return {
            "parse": 0,
            "playUrl": "",
            "url": url,
            "header": json.dumps(play_headers)
        }

    def searchContent(self, key, quick, pg="1"):
        try:
            page_num = max(1, int(str(pg).strip() or 1))
        except Exception:
            page_num = 1

        if not key:
            return {"list": []}

        encoded_key = urllib.parse.quote(str(key))
        if page_num == 1:
            search_path = "/?s=%s" % encoded_key
        else:
            search_path = "/page/%d/?s=%s" % (page_num, encoded_key)

        res = self._fetch_safe(search_path)
        vods = self._parse_cards(res.get("text", ""))

        return {
            "page": page_num,
            "pagecount": 99,
            "limit": 20,
            "total": 999,
            "list": vods
        }
