# -*- coding: utf-8 -*-
"""
91波多 四壳通用Python Spider
站点: https://www.91bd3.skin/
特点: m3u8直链在详情页HTML中，无需额外API
分类: 11个分类（国产自拍/强奸乱伦/男同女同/重口味/日本AV/无码视频/有码视频/中文字幕/欧美极品/三级伦理/动漫精品）
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
        self.siteUrl = "https://www.91bd3.skin"
        self.rawSite = "https://www.91bd3.skin"
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
            {"type_id": "20", "type_name": "国产自拍"},
            {"type_id": "21", "type_name": "强奸乱伦"},
            {"type_id": "22", "type_name": "男同女同"},
            {"type_id": "23", "type_name": "重口味"},
            {"type_id": "24", "type_name": "日本AV"},
            {"type_id": "25", "type_name": "无码视频"},
            {"type_id": "26", "type_name": "有码视频"},
            {"type_id": "27", "type_name": "中文字幕"},
            {"type_id": "28", "type_name": "欧美极品"},
            {"type_id": "29", "type_name": "三级伦理"},
            {"type_id": "30", "type_name": "动漫精品"},
        ]
        filters = {}
        for c in classes:
            filters[c["type_id"]] = [
                {"key": "class", "name": "分类", "value": [{"n": "全部", "v": ""}]},
            ]
        # 首页推荐（取国产自拍第一页前6个）
        list = self._parse_list(self._get(f"{self.siteUrl}/vodtype/20.html"))
        return {"class": classes, "list": list[:6], "filters": filters}

    def categoryContent(self, tid, page, *args):
        page = int(page) if page else 1
        if page <= 1:
            url = f"{self.siteUrl}/vodtype/{tid}.html"
        else:
            url = f"{self.siteUrl}/vodtype/{tid}-{page}.html"
        html = self._get(url)
        list = self._parse_list(html)
        # 估算总页数（每页36个）
        total = len(list)
        pagecount = 999 if total >= 36 else 1
        return {"page": page, "pagecount": pagecount, "limit": 36, "total": total * pagecount, "list": list}

    def detailContent(self, ids, *args):
        if not ids:
            return {"list": []}
        if isinstance(ids, str):
            ids = [ids]
        list = []
        for vod_id in ids:
            if not vod_id:
                continue
            # vod_id可能是完整URL或纯数字
            if vod_id.startswith("http"):
                url = vod_id
            elif vod_id.startswith("/"):
                url = f"{self.siteUrl}{vod_id}"
            else:
                url = f"{self.siteUrl}/{vod_id}.html"
            html = self._get(url)
            if not html:
                continue
            # 标题
            title = ""
            title_match = re.search(r"<title>([^<]+)</title>", html)
            if title_match:
                title = title_match.group(1).split(" - ")[0].strip()
            # 封面
            pic = ""
            pic_match = re.search(r'<img[^>]*src=["\']([^"\']+)["\']', html)
            if pic_match:
                pic = pic_match.group(1)
            # m3u8播放地址
            play_url = ""
            m3u8_match = re.search(r'["\']([^"\']+\.m3u8[^"\']*)["\']', html)
            if m3u8_match:
                play_url = m3u8_match.group(1)
            # 播放线路
            vod_play_from = "91波多"
            vod_play_url = f"第1集${play_url}" if play_url else ""
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
        # id就是m3u8地址（从detailContent的vod_play_url解析）
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
        url = f"{self.siteUrl}/s/index.html?wd={quote(key)}"
        html = self._get(url)
        list = self._parse_list(html)
        return {"page": page, "pagecount": 1, "limit": 36, "total": len(list), "list": list}

    def _parse_list(self, html):
        """解析视频列表"""
        if not html:
            return []
        list = []
        # 匹配视频链接和标题
        items = re.findall(r'href=["\'](/(\d+)\.html)["\'][^>]*>(.*?)</a>', html, re.DOTALL)
        seen = set()
        for url_path, vod_id, content in items:
            if vod_id in seen:
                continue
            seen.add(vod_id)
            # 清理标题
            title = re.sub(r"<[^>]+>", "", content).strip()
            # 去掉开头的数字序号（如"1π1808..."）
            title = re.sub(r"^\d+", "", title).strip()
            # 封面
            pic = ""
            pic_match = re.search(r'<img[^>]*src=["\']([^"\']+)["\']', content)
            if pic_match:
                pic = pic_match.group(1)
            if title and len(title) > 1:
                list.append({
                    "vod_id": vod_id,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": "",
                })
        return list

    def _get(self, url):
        """HTTP GET请求（纯标准库urllib，禁用系统代理）"""
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
            print(f"[91波多] 请求失败 {url}: {e}")
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
