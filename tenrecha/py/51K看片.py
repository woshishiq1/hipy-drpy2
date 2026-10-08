# -*- coding: utf-8 -*-
"""
51K看片 四壳通用Python Spider
站点: https://a9a1.91003.xyz/
特点: 苹果CMS（default_pc模板），播放页/vodplay/{id}-1-1.html，m3u8在player_aaaa JSON中
分类: 20+个分类
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
        self.siteUrl = "https://a9a1.91003.xyz"
        self.rawSite = "https://a9a1.91003.xyz"
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
            {"type_id": "1", "type_name": "精选"},
            {"type_id": "20", "type_name": "黑料吃瓜"},
            {"type_id": "6", "type_name": "主播直播"},
            {"type_id": "9", "type_name": "国产私拍"},
            {"type_id": "8", "type_name": "探花优选"},
            {"type_id": "16", "type_name": "传媒出品"},
            {"type_id": "2", "type_name": "极品"},
            {"type_id": "13", "type_name": "撸管必看"},
            {"type_id": "7", "type_name": "学生空姐"},
            {"type_id": "15", "type_name": "玩转户外"},
            {"type_id": "14", "type_name": "偷情乱伦"},
            {"type_id": "11", "type_name": "SM反差"},
            {"type_id": "3", "type_name": "日韩"},
            {"type_id": "25", "type_name": "高清无码"},
            {"type_id": "10", "type_name": "中文字幕"},
            {"type_id": "24", "type_name": "颜值明星"},
            {"type_id": "21", "type_name": "AV解说"},
            {"type_id": "4", "type_name": "特供"},
        ]
        filters = {}
        for c in classes:
            filters[c["type_id"]] = [
                {"key": "class", "name": "分类", "value": [{"n": "全部", "v": ""}]},
            ]
        list = self._parse_list(self._get(f"{self.siteUrl}/vodtype/1.html"))
        return {"class": classes, "list": list[:6], "filters": filters}

    def categoryContent(self, tid, page, *args):
        page = int(page) if page else 1
        if page <= 1:
            url = f"{self.siteUrl}/vodtype/{tid}.html"
        else:
            url = f"{self.siteUrl}/vodtype/{tid}-{page}.html"
        html = self._get(url)
        list = self._parse_list(html)
        total = len(list)
        pagecount = 999 if total >= 14 else 1
        return {"page": page, "pagecount": pagecount, "limit": 14, "total": total * pagecount, "list": list}

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
            play_url = f"{self.siteUrl}/vodplay/{vod_id}-1-1.html"
            html = self._get(play_url)
            if not html:
                continue
            # 标题：从title标签提取，去掉"正在播放《》"和后缀
            title = ""
            title_match = re.search(r'<title>([^<]+)</title>', html)
            if title_match:
                title = title_match.group(1).strip()
                # 去掉"正在播放《"和"》"
                title = re.sub(r'^正在播放[《【]', '', title)
                title = re.sub(r'[》】].*$', '', title).strip()
            # 封面
            pic = ""
            pic_match = re.search(r'data-src=["\']([^"\']+)["\']', html)
            if pic_match:
                pic = pic_match.group(1)
            if not pic:
                pic_match = re.search(r'<img[^>]*src=["\']([^"\']+)["\']', html)
                if pic_match:
                    pic = pic_match.group(1)
            # m3u8：从player_aaaa JSON提取
            m3u8_url = ""
            player_match = re.search(r'player_aaaa\s*=\s*({.*?})', html, re.DOTALL)
            if player_match:
                try:
                    player_data = json.loads(player_match.group(1))
                    raw_url = player_data.get("url", "")
                    if raw_url:
                        m3u8_url = raw_url.replace('\\/', '/').replace('\\', '')
                except Exception:
                    pass
            if not m3u8_url:
                # 备用：直接正则找m3u8
                m3u8_match = re.search(r'["\']((?:https?:)?\\?/\\?/[^"\']+\.m3u8[^"\']*)["\']', html)
                if m3u8_match:
                    m3u8_url = m3u8_match.group(1).replace('\\/', '/').replace('\\', '')
            vod_play_from = "51K看片"
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
        url = f"{self.siteUrl}/vodsearch/{quote(key)}----------{page}---.html"
        html = self._get(url)
        list = self._parse_list(html)
        return {"page": page, "pagecount": 1, "limit": 10, "total": len(list), "list": list}

    def _parse_list(self, html):
        if not html:
            return []
        list = []
        # default_pc模板：播放页链接 /vodplay/{id}-1-1.html
        # 封面用data-src懒加载
        # <div class="vod-item"><a href="/vodplay/48707-1-1.html"><img data-src="封面"></a></div>
        items = re.findall(r'href=["\']/vodplay/(\d+)-\d+-\d+\.html["\'][^>]*>(.*?)</a>', html, re.DOTALL)
        seen = set()
        for vod_id, content in items:
            if vod_id in seen:
                continue
            seen.add(vod_id)
            # 封面：优先data-src，其次src
            pic = ""
            pic_match = re.search(r'data-src=["\']([^"\']+)["\']', content)
            if pic_match:
                pic = pic_match.group(1)
            if not pic:
                pic_match = re.search(r'<img[^>]*src=["\']([^"\']+)["\']', content)
                if pic_match:
                    pic = pic_match.group(1)
            # 标题：从alt属性或文本提取
            title = ""
            alt_match = re.search(r'alt=["\']([^"\']+)["\']', content)
            if alt_match:
                title = alt_match.group(1).strip()
            if not title:
                text = re.sub(r"<[^>]+>", "", content).strip()
                if text and len(text) > 1:
                    title = text
            if not title:
                # 从a标签的title属性
                title_match = re.search(r'title=["\']([^"\']+)["\']', content)
                if title_match:
                    title = title_match.group(1).strip()
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
            print(f"[51K看片] 请求失败 {url}: {e}")
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
