# -*- coding: utf-8 -*-
"""
露思AV网 四壳通用Python Spider
站点: https://ron.lsavw8.work/lsavw/
特点: 苹果CMS架构（020_tpl_wap模板），m3u8在播放页JSON中
分类: 14个分类
"""

import re
import json

try:
    from base.spider import Spider
except Exception:
    class Spider:
        def __init__(self):
            self.extend = {}
        def init(self, extend):
            self.extend = extend or {}

class Spider(Spider):
    def __init__(self):
        super().__init__()
        self.siteUrl = "https://ron.lsavw8.work"
        self.rawSite = "https://ron.lsavw8.work"
        self.HOST = self.siteUrl
        self.cookie = ""
        self.ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1"

    def init(self, extend=""):
        if extend and isinstance(extend, str):
            try:
                self.extend = json.loads(extend)
            except Exception:
                self.extend = {}
        elif extend and isinstance(extend, dict):
            self.extend = extend
        else:
            self.extend = {}
        if self.extend.get("siteUrl"):
            self.siteUrl = self.extend["siteUrl"]
            self.HOST = self.siteUrl
        if self.extend.get("rawSite"):
            self.rawSite = self.extend["rawSite"]

    def homeContent(self, *args):
        classes = [
            {"type_id": "20", "type_name": "国产精品"},
            {"type_id": "21", "type_name": "主播大秀"},
            {"type_id": "22", "type_name": "抖阴视频"},
            {"type_id": "23", "type_name": "女神学生"},
            {"type_id": "24", "type_name": "美熟少妇"},
            {"type_id": "25", "type_name": "娇妻素人"},
            {"type_id": "26", "type_name": "空姐模特"},
            {"type_id": "27", "type_name": "国产乱伦"},
            {"type_id": "28", "type_name": "自慰群交"},
            {"type_id": "29", "type_name": "野合车震"},
            {"type_id": "30", "type_name": "职场同事"},
            {"type_id": "31", "type_name": "国产名人"},
            {"type_id": "32", "type_name": "日本无码"},
            {"type_id": "33", "type_name": "精品三级"},
        ]
        filters = {}
        for c in classes:
            filters[c["type_id"]] = [
                {"key": "class", "name": "分类", "value": [{"n": "全部", "v": ""}]},
            ]
        list = self._parse_list(self._get(f"{self.siteUrl}/cn/home/web/index.php/vod/type/id/20.html"))
        return {"class": classes, "list": list[:6], "filters": filters}

    def categoryContent(self, tid, page, *args):
        page = int(page) if page else 1
        if page <= 1:
            url = f"{self.siteUrl}/cn/home/web/index.php/vod/type/id/{tid}.html"
        else:
            url = f"{self.siteUrl}/cn/home/web/index.php/vod/type/id/{tid}/page/{page}.html"
        html = self._get(url)
        list = self._parse_list(html)
        total = len(list)
        pagecount = 999 if total >= 30 else 1
        return {"page": page, "pagecount": pagecount, "limit": 30, "total": total * pagecount, "list": list}

    def detailContent(self, ids, *args):
        if not ids:
            return {"list": []}
        if isinstance(ids, str):
            ids = [ids]
        list = []
        for vod_id in ids:
            if not vod_id:
                continue
            # 播放页URL
            play_url = f"{self.siteUrl}/cn/home/web/index.php/vod/play/id/{vod_id}/sid/1/nid/1.html"
            html = self._get(play_url)
            if not html:
                continue
            # 标题：class="name"
            title = ""
            name_match = re.search(r'class="name"[^>]*>(.*?)</', html, re.DOTALL)
            if name_match:
                title = re.sub(r"<[^>]+>", "", name_match.group(1)).strip()
            if not title:
                title_match = re.search(r'<title>([^<]+)</title>', html)
                if title_match:
                    title = title_match.group(1).strip()
            # 封面
            pic = ""
            pic_match = re.search(r'background-image:\s*url\(([^)]+)\)', html)
            if pic_match:
                pic = pic_match.group(1).strip()
            # m3u8（JSON转义格式）
            m3u8_url = ""
            m3u8_match = re.search(r'["\']((?:https?:)?\\?/\\?/[^"\']+\.m3u8[^"\']*)["\']', html)
            if m3u8_match:
                m3u8_url = m3u8_match.group(1).replace('\\/', '/').replace('\\', '')
            vod_play_from = "露思AV网"
            vod_play_url = f"第1集${m3u8_url}" if m3u8_url else ""
            list.append({
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": "",
                "vod_content": title,
                "vod_play_from": vod_play_from,
                "vod_play_url": vod_play_url,
            })
        return {"list": list}

    def playerContent(self, flag, id, vipFlags, *args):
        url = id
        if not url.startswith("http"):
            url = f"{self.siteUrl}/{url}"
        return {
            "parse": 0,
            "jx": 0,
            "url": url,
            "header": {
                "User-Agent": self.ua,
                "Referer": f"{self.rawSite}/",
                "Origin": self.rawSite,
            },
        }

    def searchContent(self, key, page, *args):
        from urllib.parse import quote
        page = int(page) if page else 1
        url = f"{self.siteUrl}/cn/home/web/index.php/vod/search/wd/{quote(key)}.html"
        html = self._get(url)
        list = self._parse_list(html)
        return {"page": page, "pagecount": 1, "limit": 30, "total": len(list), "list": list}

    def _parse_list(self, html):
        if not html:
            return []
        list = []
        # 020_tpl_wap模板：封面链接+标题分开
        # 封面：<a href="/vod/play/id/{id}/sid/1/nid/1.html" class="figure" style="background-image: url(封面);">
        # 标题：<strong class="figure_title"><a href="..." title="标题">标题</a></strong>
        items = re.findall(r'href="([^"]*vod/play/id/(\d+)[^"]*)"[^>]*style="[^"]*url\(([^)]+)\)', html)
        # 标题映射
        title_map = {}
        title_items = re.findall(r'class="figure_title"><a[^>]*href="[^"]*vod/play/id/(\d+)[^"]*"[^>]*title="([^"]*)"', html)
        for vid, title in title_items:
            title_map[vid] = title

        seen = set()
        for url_path, vod_id, pic in items:
            if vod_id in seen:
                continue
            seen.add(vod_id)
            title = title_map.get(vod_id, "")
            if not title:
                # 备用：从a标签文本提取
                title_match = re.search(rf'vod/play/id/{vod_id}[^"]*"[^>]*>(.*?)</a>', html, re.DOTALL)
                if title_match:
                    title = re.sub(r"<[^>]+>", "", title_match.group(1)).strip()
            pic = pic.strip()
            if title and len(title) > 1:
                list.append({
                    "vod_id": vod_id,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": "",
                })
        return list

    def _get(self, url):
        try:
            import urllib.request
            import ssl
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            proxy_handler = urllib.request.ProxyHandler({})
            opener = urllib.request.build_opener(proxy_handler, urllib.request.HTTPSHandler(context=ctx))
            req = urllib.request.Request(url, headers={
                "User-Agent": self.ua,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9",
            })
            resp = opener.open(req, timeout=20)
            return resp.read().decode("utf-8", errors="ignore")
        except Exception as e:
            print(f"[露思AV网] 请求失败 {url}: {e}")
            return ""

    def getDependence(self, *args):
        return ""

    def localProxy(self, *args):
        return [404, "text/plain", ""]

    def isVideoFormat(self, url, *args):
        return any(url.endswith(ext) for ext in [".m3u8", ".mp4", ".avi", ".mkv", ".flv"])

    def manualVideoCheck(self, *args):
        return False

    def destroy(self, *args):
        pass
