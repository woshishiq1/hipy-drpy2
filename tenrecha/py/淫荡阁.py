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
        def init(self, extend=""):
            pass


class Spider(SpiderBase):
    def __init__(self):
        super(Spider, self).__init__()
        self.rawSite = "https://cedgwc.ydg9.skin"
        self.siteUrl = "https://cedgwc.ydg9.skin/ydg"
        self.HOST = self.siteUrl
        self._enc_group = "aHR0cHM6Ly90Lm1lL3R2c2hhcmUyMw=="
        self._enc_actor = "J+OiqOeahOivkee7n+S9n+S4gQ=="
        self._enc_director = "J+OiqOWPsuS6uuS8lw=="
        self.tgGroup = self._dec(self._enc_group) or "https://t.me/tvshare23"
        self.brandActor = "🦋 TG群: @tvshare23"
        self.brandDirector = "🦋 蝴蝶影视"

        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        
        self.classes = [
            {"type_id": "20", "type_name": "国产视频"},
            {"type_id": "21", "type_name": "日韩有码"},
            {"type_id": "22", "type_name": "日韩无码"},
            {"type_id": "23", "type_name": "制服学生"},
            {"type_id": "24", "type_name": "动漫卡通"},
            {"type_id": "25", "type_name": "欧美变态"},
            {"type_id": "26", "type_name": "三级伦理"},
        ]
        self.filters = {}
        for c in self.classes:
            self.filters[c["type_id"]] = []

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

    def _dec(self, b64_str):
        try:
            pad = len(b64_str) % 4
            if pad:
                b64_str += "=" * (4 - pad)
            return base64.b64decode(b64_str.encode("utf-8")).decode("utf-8")
        except Exception:
            return ""

    def init(self, extend=""):
        try:
            if extend:
                ext = json.loads(extend) if isinstance(extend, str) else extend
                if ext.get("siteUrl"):
                    self.siteUrl = ext["siteUrl"]
                    self.HOST = self.siteUrl
        except Exception:
            pass
        return True

    def isVideoFormat(self, url):
        low = (url or "").lower()
        return any(k in low for k in (".m3u8", ".mp4", ".flv", ".mkv", ".avi", ".ts"))

    def manualVideoCheck(self):
        return False

    def _get(self, url, referer=None):
        try:
            headers = {
                "User-Agent": self.ua,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9",
            }
            if referer:
                headers["Referer"] = referer
            req = urllib.request.Request(url, headers=headers)
            with self.opener.open(req, timeout=10) as resp:
                data = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    data = gzip.decompress(data)
                elif resp.headers.get("Content-Encoding") == "deflate":
                    try:
                        data = zlib.decompress(data)
                    except Exception:
                        data = zlib.decompress(data, -zlib.MAX_WBITS)
                return data.decode("utf-8", errors="ignore")
        except Exception:
            return ""

    def _url(self, path):
        if path.startswith("http"):
            return path
        if path == "/":
            return self.siteUrl + "/"
        if path.startswith("/"):
            return self.rawSite + path
        return self.siteUrl + "/" + path

    def _unesc(self, s):
        try:
            return html_lib.unescape(s or "").strip()
        except Exception:
            return (s or "").strip()

    def _parse(self, html):
        if not html:
            return []
        result = []
        title_map = {}
        for m in re.finditer(r'<a\s+[^>]*href="/(\d+)\.html"[^>]*>([^<]+)</a>', html):
            vid = m.group(1)
            if vid not in title_map:
                title_map[vid] = m.group(2).strip()

        seen = set()
        for m in re.finditer(r'<a\s+[^>]*href="/(\d+)\.html"[^>]*>', html):
            vid = m.group(1)
            if vid in seen:
                continue
            tag = m.group(0)
            cover_m = re.search(r"background-image:\s*url\(['\"]?([^'\")]+)", tag)
            if not cover_m:
                continue
            seen.add(vid)
            
            title = title_map.get(vid, "正片视频")
            clean_url = self._url("/%s.html" % vid)
            safe_id = "v_" + base64.urlsafe_b64encode(clean_url.encode("utf-8")).decode("utf-8").rstrip("=")

            result.append({
                "vod_id": safe_id,
                "vod_name": self._unesc(title),
                "vod_pic": cover_m.group(1),
                "vod_remarks": "高清正片",
            })
        return result

    def _pagecount(self, html, prefix):
        if not html:
            return 1
        m = re.search(r'href="(' + re.escape(prefix) + r'[^"]*)"[^>]*>\s*尾页', html)
        if m:
            n = re.search(r'[/-](\d+)\.html', m.group(1))
            if n:
                return int(n.group(1))
        nums = re.findall(r'href="' + re.escape(prefix) + r'[^\"]*[/-](\d+)\.html"', html)
        if nums:
            return max(int(x) for x in nums)
        return 1

    def homeContent(self, *args, **kwargs):
        vod_list = []
        try:
            html = self._get(self.siteUrl + "/", referer=self.siteUrl + "/")
            if html:
                vod_list = self._parse(html)[:24]
        except Exception:
            vod_list = []
        return {
            "class": self.classes,
            "filters": self.filters,
            "list": vod_list,
        }

    def homeVideoContent(self, *args, **kwargs):
        html = self._get(self.siteUrl + "/", referer=self.siteUrl + "/")
        lst = self._parse(html)[:24]
        return {"page": 1, "pagecount": 1, "limit": len(lst), "total": len(lst), "list": lst}

    def categoryContent(self, *args, **kwargs):
        tid = str(args[0]) if len(args) > 0 else "20"
        try:
            p = int(args[1]) if len(args) > 1 else 1
        except Exception:
            p = 1
        
        if p <= 1:
            url = self._url("/vodtype/%s.html" % tid)
        else:
            url = self._url("/vodtype/%s-%s.html" % (tid, p))
        
        html = self._get(url, referer=self.siteUrl + "/")
        lst = self._parse(html)
        pc = self._pagecount(html, "/vodtype/%s" % tid)
        return {"page": p, "pagecount": pc, "limit": 72, "total": pc * 72, "list": lst}

    def detailContent(self, ids, *args, **kwargs):
        if isinstance(ids, str):
            vid_list = [ids]
        elif isinstance(ids, (list, tuple)):
            vid_list = list(ids)
        else:
            vid_list = [str(ids)]

        result = []
        for raw_item in vid_list:
            try:
                if str(raw_item).startswith("v_"):
                    b64_str = raw_item[2:]
                    pad = len(b64_str) % 4
                    if pad:
                        b64_str += "=" * (4 - pad)
                    detail_url = base64.urlsafe_b64decode(b64_str.encode("utf-8")).decode("utf-8")
                else:
                    detail_url = self._url("/%s.html" % raw_item)

                html = self._get(detail_url, referer=self.siteUrl + "/")
                if not html:
                    continue

                title = ""
                tm = re.search(r'<div class="song-info"[^>]*>\s*<h3>(.*?)</h3>', html, re.DOTALL)
                if tm:
                    title = re.sub(r'<[^>]+>', '', tm.group(1)).strip()
                else:
                    pt = re.search(r'<title>(.*?)</title>', html)
                    if pt:
                        title = pt.group(1).split("-")[0].strip()

                m3u8 = ""
                rm = re.search(r"rawUrl\s*=\s*['\"]([^'\"]+)['\"]", html)
                if rm:
                    m3u8 = rm.group(1)
                else:
                    mm = re.search(r'https?://[^\s"\'\\>]+\.m3u8[^\s"\'\\>]*', html)
                    if mm:
                        m3u8 = mm.group(0)

                pic = ""
                pm = re.search(r'background-image:\s*url\([\'"]?([^\'")]+)', html)
                if pm:
                    pic = pm.group(1)

                if not m3u8:
                    continue

                play_url = "正片高清$" + m3u8

                raw_content_m = re.search(r'简介：(.*?)</p>', html)
                raw_content = raw_content_m.group(1) if raw_content_m else ""
                clean_content = self._unesc(re.sub(r'<[^>]+>', '', raw_content)).strip()
                
                custom_notice = "【💡 温馨提示：视频加载如遇卡顿请尝试切换线路或快进。】"
                group_info = "【🔥 官方交流群: %s】" % self.tgGroup
                
                if clean_content:
                    vod_content = "%s\n\n%s\n\n%s" % (group_info, custom_notice, clean_content)
                else:
                    vod_content = "%s\n\n%s\n\n暂无详细简介，欢迎加入TG群获取最新资源！" % (group_info, custom_notice)

                escaped_desc = vod_content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

                result.append({
                    "vod_id": str(raw_item),
                    "vod_name": self._unesc(title),
                    "vod_pic": pic,
                    "vod_actor": self.brandActor,
                    "vod_director": self.brandDirector,
                    "vod_remarks": "高清直连",
                    "vod_content": escaped_desc,
                    "vod_play_from": "高清线路",
                    "vod_play_url": play_url,
                })
            except Exception:
                continue
        return {"list": result}

    def playerContent(self, flag, id, vipFlags, *args, **kwargs):
        return {
            "parse": 0,
            "jx": 0,
            "url": id,
            "format": "application/x-mpegURL",
            "header": {
                "User-Agent": self.ua,
                "Referer": self.rawSite + "/",
                "Origin": self.rawSite,
            },
        }

    def searchContent(self, *args, **kwargs):
        wd = str(args[0]) if len(args) > 0 else ""
        p = 1
        if len(args) >= 2:
            try:
                p = int(args[1])
            except Exception:
                pass
        if len(args) >= 3:
            try:
                p = int(args[2])
            except Exception:
                pass
        
        ew = urllib.parse.quote(wd)
        if p <= 1:
            url = self._url("/s/index.html?wd=%s" % ew)
        else:
            url = self._url("/s/%s/page/%s.html" % (ew, p))
        
        html = self._get(url, referer=self.siteUrl + "/")
        lst = self._parse(html)
        pc = self._pagecount(html, "/s/%s/page" % ew)
        return {"page": p, "pagecount": pc, "limit": 72, "total": pc * 72, "list": lst}