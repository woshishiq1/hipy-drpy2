# -*- coding: utf-8 -*-
"""
谢欲频道 四壳通用Python Spider
站点: https://www.tongtoubani.cfd/
特点: 苹果CMS架构，m3u8在播放页JSON中
分类: 16个分类
模板: m1938pc
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
        self.siteUrl = "https://www.tongtoubani.cfd"
        self.rawSite = "https://www.tongtoubani.cfd"
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
            {"type_id": "1", "type_name": "国产传媒"},
            {"type_id": "2", "type_name": "国产视频"},
            {"type_id": "3", "type_name": "国产主播"},
            {"type_id": "4", "type_name": "国产明星"},
            {"type_id": "6", "type_name": "抖阴视频"},
            {"type_id": "7", "type_name": "网爆黑料"},
            {"type_id": "8", "type_name": "擦边电影"},
            {"type_id": "9", "type_name": "网红流出"},
            {"type_id": "10", "type_name": "欧美无码"},
            {"type_id": "11", "type_name": "中文字幕"},
            {"type_id": "12", "type_name": "丰满女优"},
            {"type_id": "13", "type_name": "女同性恋"},
            {"type_id": "14", "type_name": "激情动漫"},
            {"type_id": "15", "type_name": "强奸乱伦"},
            {"type_id": "16", "type_name": "日本无码"},
        ]
        filters = {}
        for c in classes:
            filters[c["type_id"]] = [
                {"key": "class", "name": "分类", "value": [{"n": "全部", "v": ""}]},
            ]
        list = self._parse_list(self._get(f"{self.siteUrl}/index.php/vod/type/id/1.html"))
        return {"class": classes, "list": list[:6], "filters": filters}

    def categoryContent(self, tid, page, *args):
        page = int(page) if page else 1
        if page <= 1:
            url = f"{self.siteUrl}/index.php/vod/type/id/{tid}.html"
        else:
            url = f"{self.siteUrl}/index.php/vod/type/id/{tid}/page/{page}.html"
        html = self._get(url)
        list = self._parse_list(html)
        total = len(list)
        pagecount = 999 if total >= 24 else 1
        return {"page": page, "pagecount": pagecount, "limit": 24, "total": total * pagecount, "list": list}

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
                detail_url = vod_id
                # 从URL中提取id
                id_match = re.search(r'/id/(\d+)\.html', vod_id)
                vod_id = id_match.group(1) if id_match else vod_id
            elif vod_id.startswith("/"):
                detail_url = f"{self.siteUrl}{vod_id}"
            else:
                detail_url = f"{self.siteUrl}/index.php/vod/detail/id/{vod_id}.html"

            html = self._get(detail_url)
            if not html:
                continue

            title = ""
            title_match = re.search(r'<title>([^<]+)</title>', html)
            if title_match:
                title = title_match.group(1).split("详情介绍")[0].split("在线观看")[0].strip()

            pic = ""
            pic_match = re.search(r'data-original=["\']([^"\']+)["\']', html)
            if pic_match:
                pic = pic_match.group(1)
            if not pic:
                pic_match = re.search(r'<img[^>]*src=["\']([^"\']+)["\']', html)
                if pic_match:
                    pic = pic_match.group(1)

            # 获取播放页链接
            play_link = ""
            play_match = re.search(r'href=["\'](/index\.php/vod/play/id/\d+/sid/\d+/nid/\d+\.html)["\']', html)
            if play_match:
                play_link = play_match.group(1)

            # 从播放页获取m3u8
            play_url = ""
            if play_link:
                play_html = self._get(f"{self.siteUrl}{play_link}")
                if play_html:
                    # 从JSON中提取m3u8（处理转义）
                    m3u8_match = re.search(r'["\']((?:https?:)?\\?/\\?/[^"\']+\.m3u8[^"\']*)["\']', play_html)
                    if m3u8_match:
                        play_url = m3u8_match.group(1).replace("\\/", "/").replace("\\", "")
                    if not play_url:
                        # 尝试其他格式
                        m3u8_match = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', play_html)
                        if m3u8_match:
                            play_url = m3u8_match.group(1)

            vod_play_from = "谢欲频道"
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
        url = f"{self.siteUrl}/index.php/vod/search/wd/{quote(key)}.html"
        html = self._get(url)
        list = self._parse_list(html)
        return {"page": page, "pagecount": 1, "limit": 24, "total": len(list), "list": list}

    def _parse_list(self, html):
        if not html:
            return []
        list = []
        # 苹果CMS m1938pc模板：提取所有详情链接
        items = re.findall(r'href=["\']/index\.php/vod/detail/id/(\d+)\.html["\'][^>]*title=["\']([^"\']+)["\']', html)
        seen = set()
        for vod_id, title in items:
            if vod_id in seen:
                continue
            seen.add(vod_id)
            # 提取封面（在同一个li块中）
            pic = ""
            # 找这个vod_id附近的封面
            pattern = rf'/index\.php/vod/detail/id/{vod_id}\.html.*?data-original=["\']([^"\']+)["\']'
            pic_match = re.search(pattern, html, re.DOTALL)
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
            print(f"[谢欲频道] 请求失败 {url}: {e}")
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
