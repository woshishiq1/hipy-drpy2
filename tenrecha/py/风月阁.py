# -*- coding: utf-8 -*-
import re
import json
import gzip
import urllib.parse
import urllib.request

# PyramidStore/TVBox标准: 继承base.spider基类
# 四壳协议: 独立class即可
# 双兼容: 尝试导入基类，失败则用本地最小基类
try:
    from base.spider import Spider as _BaseSpider
except ImportError:
    class _BaseSpider:
        def init(self, extend=""):
            pass


class Spider(_BaseSpider):
    def __init__(self):
        self.rawSite = "https://cedgwc.ydg9.skin"
        self.siteUrl = "https://cedgwc.ydg9.skin/ydg"
        self.HOST = self.siteUrl
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
            resp = urllib.request.urlopen(req, timeout=10)
            data = resp.read()
            if resp.headers.get("Content-Encoding") == "gzip":
                data = gzip.decompress(data)
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
            result.append({
                "vod_id": vid,
                "vod_name": title_map.get(vid, ""),
                "vod_pic": cover_m.group(1),
                "vod_remarks": "",
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

    # ===== 接口(双协议兼容: *args接受两种调用方式) =====

    def init(self, extend=""):
        try:
            if extend:
                if isinstance(extend, str):
                    ext = json.loads(extend)
                elif isinstance(extend, dict):
                    ext = extend
                else:
                    ext = {}
                if ext.get("siteUrl"):
                    self.siteUrl = ext["siteUrl"]
                    self.HOST = self.siteUrl
        except Exception:
            pass
        return

    def getName(self):
        return "风月阁"

    # 四壳: homeContent(self)
    # PyramidStore: homeContent(self, filter)
    def homeContent(self, *args):
        vod_list = []
        try:
            html = self._get(self.siteUrl + "/", referer=self.siteUrl + "/")
            if html:
                vod_list = self._parse(html)[:24]
        except Exception:
            vod_list = []
        result = {
            "class": self.classes,
            "filters": self.filters,
            "list": vod_list,
        }
        return result

    def homeVideoContent(self):
        html = self._get(self.siteUrl + "/", referer=self.siteUrl + "/")
        lst = self._parse(html)[:24]
        return {"page": 1, "pagecount": 1, "limit": len(lst), "total": len(lst), "list": lst}

    # 四壳: categoryContent(self, tid, page, filter, extend)
    # PyramidStore: categoryContent(self, tid, pg, filter, extend)
    def categoryContent(self, *args):
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

    def detailContent(self, ids):
        if isinstance(ids, str):
            ids = [ids]
        elif isinstance(ids, tuple):
            ids = list(ids)
        result = []
        for vid in ids:
            try:
                html = self._get(self._url("/%s.html" % vid), referer=self.siteUrl + "/")
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
                play_url = ""
                if m3u8:
                    play_url = "第01集$" + m3u8
                result.append({
                    "vod_id": str(vid),
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": "高清",
                    "vod_content": title,
                    "vod_play_from": "在线播放",
                    "vod_play_url": play_url,
                })
            except Exception:
                continue
        return {"list": result}

    # 四壳: searchContent(self, wd, page)
    # PyramidStore: searchContent(self, key, quick) 或 (self, key, quick, pg)
    def searchContent(self, *args):
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
        # PyramidStore直接返回list, 四壳返回dict
        # 为兼容两种, 返回dict(四壳标准), PyramidStore会取list字段
        return {"page": p, "pagecount": pc, "limit": 72, "total": pc * 72, "list": lst}

    def playerContent(self, flag, id, vipFlags):
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

    def localProxy(self, flag, id):
        if not id or ".m3u8" not in id:
            return [404, "text/plain", ""]
        try:
            headers = {"User-Agent": self.ua, "Referer": self.rawSite + "/"}
            req = urllib.request.Request(id, headers=headers)
            resp = urllib.request.urlopen(req, timeout=10)
            data = resp.read()
            if resp.headers.get("Content-Encoding") == "gzip":
                data = gzip.decompress(data)
            return [200, "application/vnd.apple.mpegurl", data.decode("utf-8", errors="ignore")]
        except Exception:
            return [404, "text/plain", ""]

    def isVideoFormat(self, url):
        if not url:
            return False
        for ext in [".m3u8", ".mp4", ".ts", ".flv", ".mkv"]:
            if ext in url.lower():
                return True
        return False

    def manualVideoCheck(self):
        return False

    def getDependence(self):
        return ""

    def destroy(self):
        pass

    def action(self, action, str):
        if action == "proxy":
            return self.localProxy("", str)
        return ""
