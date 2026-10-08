# -*- coding: utf-8 -*-
"""
聚合影视 四壳通用Python Spider
站点: https://av.cuct.ccwu.cc/
特点: 多源聚合站（56个源），Vue SPA + REST API
API: /api/v1/spiders/{key}/home|category|detail|search|play
"""

import re
import json
from urllib.parse import quote

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
        self.siteUrl = "https://av.cuct.ccwu.cc"
        self.rawSite = "https://av.cuct.ccwu.cc"
        self.HOST = self.siteUrl
        self.apiBase = f"{self.siteUrl}/api/v1"
        self.ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1"
        self._spiders_cache = None
        self._categories_cache = {}
        self._default_source = "jable"

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
            self.apiBase = f"{self.siteUrl}/api/v1"
        if self.extend.get("defaultSource"):
            self._default_source = self.extend["defaultSource"]

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
                "Accept": "application/json",
            })
            resp = opener.open(req, timeout=20)
            return resp.read().decode("utf-8", errors="ignore")
        except Exception as e:
            print(f"[聚合影视] 请求失败 {url}: {e}")
            return ""

    def _get_json(self, url):
        text = self._get(url)
        if not text:
            return None
        try:
            return json.loads(text)
        except Exception:
            return None

    def _get_spiders(self):
        """获取所有源列表（带缓存）"""
        if self._spiders_cache is not None:
            return self._spiders_cache
        data = self._get_json(f"{self.apiBase}/spiders")
        if data and isinstance(data, list):
            self._spiders_cache = data
        else:
            self._spiders_cache = []
        return self._spiders_cache

    def _get_categories(self, src_key):
        """获取指定源的分类（带缓存）"""
        if src_key in self._categories_cache:
            return self._categories_cache[src_key]
        data = self._get_json(f"{self.apiBase}/spiders/{src_key}/home")
        cats = []
        if data and isinstance(data, dict):
            cats = data.get("categories", [])
        self._categories_cache[src_key] = cats
        return cats

    def homeContent(self, *args):
        spiders = self._get_spiders()
        # 所有源作为一级分类
        classes = []
        for s in spiders:
            key = s.get("key", "")
            name = s.get("name", key)
            if key:
                classes.append({"type_id": key, "type_name": name})

        # 首页推荐：使用默认源的第一个分类
        list = []
        if classes:
            default_key = self._default_source
            # 确保默认源存在
            if not any(c["type_id"] == default_key for c in classes):
                default_key = classes[0]["type_id"]
            cats = self._get_categories(default_key)
            if cats:
                first_tid = cats[0].get("tid", "")
                if first_tid:
                    data = self._get_json(f"{self.apiBase}/spiders/{default_key}/category?tid={quote(first_tid)}&page=1")
                    if data and isinstance(data, dict):
                        list = self._parse_vod_list(data.get("list", []), default_key)[:6]

        # filters：每个源的分类列表
        filters = {}
        for s in spiders[:20]:  # 只缓存前20个源的分类，避免太慢
            key = s.get("key", "")
            if key:
                cats = self._get_categories(key)
                filter_list = [{"n": "全部", "v": ""}]
                for c in cats:
                    tid = c.get("tid", "")
                    name = c.get("name", tid)
                    if tid:
                        filter_list.append({"n": name, "v": tid})
                filters[key] = [{"key": "class", "name": "子分类", "value": filter_list}]

        return {"class": classes, "list": list, "filters": filters}

    def categoryContent(self, tid, page, *args):
        page = int(page) if page else 1
        src_key = tid
        # 从filters中获取子分类
        sub_tid = ""
        if len(args) >= 2 and args[1]:
            filters = args[1]
            if isinstance(filters, dict):
                sub_tid = filters.get("class", "")
        # 如果没有子分类，使用该源的第一个分类
        if not sub_tid:
            cats = self._get_categories(src_key)
            if cats:
                sub_tid = cats[0].get("tid", "")

        if not sub_tid:
            return {"page": page, "pagecount": 0, "limit": 24, "total": 0, "list": []}

        data = self._get_json(f"{self.apiBase}/spiders/{src_key}/category?tid={quote(sub_tid)}&page={page}")
        if not data or not isinstance(data, dict):
            return {"page": page, "pagecount": 0, "limit": 24, "total": 0, "list": []}

        list = self._parse_vod_list(data.get("list", []), src_key)
        total = data.get("total", len(list))
        pagecount = data.get("pagecount", 1)
        return {"page": page, "pagecount": pagecount, "limit": 24, "total": total, "list": list}

    def detailContent(self, ids, *args):
        if not ids:
            return {"list": []}
        if isinstance(ids, str):
            ids = [ids]
        list = []
        for vod_id in ids:
            if not vod_id:
                continue
            # vod_id格式: {src_key}||{视频ID}
            if "||" in vod_id:
                parts = vod_id.split("||", 1)
                src_key = parts[0]
                video_id = parts[1]
            else:
                src_key = self._default_source
                video_id = vod_id

            data = self._get_json(f"{self.apiBase}/spiders/{src_key}/detail?id={quote(video_id)}")
            if not data or not isinstance(data, dict):
                continue

            name = data.get("name", "")
            pic = data.get("pic", "")
            remarks = data.get("remarks", "")
            episodes = data.get("episodes", [])

            # 转换episodes为播放列表
            vod_play_from = []
            vod_play_url = []
            for ep in episodes:
                ep_name = ep.get("name", "播放")
                ep_flag = ep.get("flag", "默认")
                ep_id = ep.get("id", "")
                if ep_id:
                    # 播放地址格式: {src_key}||{ep_id}
                    play_url = f"{src_key}||{ep_id}"
                    vod_play_from.append(ep_flag)
                    vod_play_url.append(f"{ep_name}${play_url}")

            list.append({
                "vod_id": vod_id,
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": remarks,
                "vod_content": name,
                "vod_play_from": "$$$".join(vod_play_from),
                "vod_play_url": "#".join(vod_play_url),
            })
        return {"list": list}

    def playerContent(self, flag, id, vipFlags, *args):
        # id格式: {src_key}||{ep_id}
        if "||" in id:
            parts = id.split("||", 1)
            src_key = parts[0]
            play_id = parts[1]
        else:
            src_key = self._default_source
            play_id = id

        data = self._get_json(f"{self.apiBase}/spiders/{src_key}/play?id={quote(play_id)}")
        if not data or not isinstance(data, dict):
            return {"parse": 0, "jx": 0, "url": "", "header": {}}

        url = data.get("url", "")
        header = data.get("header", {})
        if not isinstance(header, dict):
            header = {}
        # 确保有UA
        if "User-Agent" not in header:
            header["User-Agent"] = self.ua

        return {
            "parse": 0,
            "jx": 0,
            "url": url,
            "header": header,
        }

    def searchContent(self, key, page, *args):
        page = int(page) if page else 1
        # 在默认源搜索
        src_key = self._default_source
        data = self._get_json(f"{self.apiBase}/spiders/{src_key}/search?q={quote(key)}&page={page}")
        if not data or not isinstance(data, dict):
            return {"page": page, "pagecount": 0, "limit": 24, "total": 0, "list": []}

        list = self._parse_vod_list(data.get("list", []), src_key)
        total = data.get("total", len(list))
        pagecount = data.get("pagecount", 1)
        return {"page": page, "pagecount": pagecount, "limit": 24, "total": total, "list": list}

    def _parse_vod_list(self, items, src_key):
        """解析视频列表，vod_id格式: {src_key}||{视频ID}"""
        if not items:
            return []
        list = []
        for item in items:
            if not isinstance(item, dict):
                continue
            vid = item.get("id", "")
            name = item.get("name", "")
            pic = item.get("pic", "")
            remarks = item.get("remarks", "")
            if vid and name:
                list.append({
                    "vod_id": f"{src_key}||{vid}",
                    "vod_name": name,
                    "vod_pic": pic,
                    "vod_remarks": remarks,
                })
        return list

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
