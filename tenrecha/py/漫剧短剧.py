#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
══════════════════════════════════════════════════════════════════
《遮天法 2.0》定制源 — 漫剧影院 (hg.115567.xyz)
全链路真实 API 最终版：
  1. 列表接口: /api/filter?category_id={id}&page={pg}&pageSize=30
  2. 详情接口: /api/drama?id={id}
  3. 播放解析: /api/stream?drama={id}&ep={ep}&epId={epId} -> stream 直链
══════════════════════════════════════════════════════════════════
"""

import sys
import os
import re
import json
import time
from urllib.parse import urljoin, quote, unquote
import threading

import requests

try:
    from base.spider import Spider as SpiderBase
except ImportError:
    class SpiderBase:
        pass


class Spider(SpiderBase):
    def __init__(self):
        super().__init__()
        self.siteUrl = "https://hg.115567.xyz"
        self._ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        self._local = threading.local()

    @property
    def session(self) -> requests.Session:
        if not hasattr(self._local, "session"):
            self._local.session = requests.Session()
        return self._local.session

    def _headers(self):
        return {
            "User-Agent": self._ua,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": f"{self.siteUrl}/",
            "Origin": self.siteUrl,
            "Connection": "keep-alive"
        }

    def fetch(self, url: str, timeout: int = 10) -> str:
        try:
            resp = self.session.get(url, headers=self._headers(), timeout=timeout, allow_redirects=True)
            resp.encoding = getattr(resp, "apparent_encoding", None) or "utf-8"
            return resp.text
        except Exception:
            return ""

    def fix_url(self, url: str) -> str:
        if not url:
            return ""
        if url.startswith("//"):
            return f"https:{url}"
        if url.startswith("http"):
            return url
        return urljoin(self.siteUrl, url)

    def init(self, extend=""):
        return True

    # ══════════════════════════════════════════════════════════
    # 1. 分类导航与 Filter 筛选
    # ══════════════════════════════════════════════════════════
    def homeContent(self, filter=False) -> dict:
        classes = [
            {"type_name": "成人漫剧", "type_id": "1"},
            {"type_name": "AI短剧", "type_id": "2"},
            {"type_name": "擦边短剧", "type_id": "18"}
        ]
        
        filter_dict = {}
        for c in classes:
            cid = c["type_id"]
            filter_dict[cid] = [
                {
                    "key": "badge",
                    "name": "标签",
                    "value": [
                        {"n": "全部", "v": ""},
                        {"n": "18+", "v": "18+"},
                        {"n": "擦边", "v": "擦边"},
                        {"n": "漫剧", "v": "漫剧"}
                    ]
                },
                {
                    "key": "status",
                    "name": "状态",
                    "value": [
                        {"n": "全部", "v": ""},
                        {"n": "完结", "v": "ended"},
                        {"n": "连载", "v": "ongoing"}
                    ]
                },
                {
                    "key": "lang",
                    "name": "语言",
                    "value": [
                        {"n": "全部", "v": ""},
                        {"n": "中文", "v": "中文"},
                        {"n": "国语", "v": "国语"},
                        {"n": "汉语普通话", "v": "汉语普通话"}
                    ]
                }
            ]

        res = {"class": classes}
        if filter:
            res["filters"] = filter_dict
        return res

    # ══════════════════════════════════════════════════════════
    # 2. 分类数据列表
    # ══════════════════════════════════════════════════════════
    def categoryContent(self, tid: str, pg: str, filter: bool, extend: dict) -> dict:
        videos = []
        page = int(pg)
        
        params = [f"category_id={tid}", f"page={page}", "pageSize=30"]
        if extend:
            if extend.get("badge"):
                params.append(f"badge={quote(extend['badge'])}")
            if extend.get("status"):
                params.append(f"status={quote(extend['status'])}")
            if extend.get("lang"):
                params.append(f"lang={quote(extend['lang'])}")

        api_url = f"{self.siteUrl}/api/filter?{'&'.join(params)}"
        resp_text = self.fetch(api_url)
        
        has_more = False
        if resp_text and resp_text.strip().startswith("{"):
            try:
                data = json.loads(resp_text)
                has_more = data.get("hasMore", False)
                item_list = data.get("list", [])
                
                for item in item_list:
                    v_id = str(item.get("id"))
                    v_name = item.get("title", "")
                    
                    # 补全封面（无图片时留空走 TVBox 原生文字色块）
                    cover_raw = item.get("cover", "")
                    v_pic = self.fix_url(cover_raw) if cover_raw else ""
                    
                    ep_count = item.get("episode_count", 1)
                    badge = item.get("badge", "")
                    remarks = f"{badge} · 全{ep_count}集" if badge else f"全{ep_count}集"

                    videos.append({
                        "vod_id": v_id,
                        "vod_name": v_name,
                        "vod_pic": v_pic,
                        "vod_remarks": remarks
                    })
            except Exception:
                pass

        return {
            "list": videos,
            "page": page,
            "pagecount": page + 1 if has_more else page,
            "limit": 30,
            "total": (page + 1) * 30 if has_more else page * len(videos)
        }

    # ══════════════════════════════════════════════════════════
    # 3. 剧集详情解析（对接 /api/drama?id=...）
    # ══════════════════════════════════════════════════════════
    def detailContent(self, ids: list) -> dict:
        drama_id = ids[0]
        detail_api = f"{self.siteUrl}/api/drama?id={drama_id}"
        resp_text = self.fetch(detail_api)
        
        name = "漫剧短剧"
        pic = ""
        desc = ""
        episodes = []

        if resp_text and resp_text.strip().startswith("{"):
            try:
                data = json.loads(resp_text)
                info = data.get("drama") or data.get("data") or data
                name = info.get("title") or name
                pic = self.fix_url(info.get("cover") or "")
                desc = info.get("description") or info.get("intro") or ""

                # 提取选集列表 (包含 id, ep 等参数)
                ep_list = info.get("episodes") or data.get("episodes") or info.get("list") or []
                if isinstance(ep_list, list) and len(ep_list) > 0:
                    for idx, ep in enumerate(ep_list):
                        ep_title = ep.get("title") or ep.get("name") or f"第{idx+1}集"
                        ep_num = ep.get("ep") or ep.get("episode") or (idx + 1)
                        ep_id = ep.get("id") or ep.get("epId") or (idx + 1)
                        play_token = f"{drama_id}@@{ep_num}@@{ep_id}"
                        episodes.append(f"{ep_title}${play_token}")
                else:
                    ep_count = info.get("episode_count", 1)
                    for i in range(1, ep_count + 1):
                        episodes.append(f"第{i}集${drama_id}@@{i}@@{i}")
            except Exception:
                pass

        if not episodes:
            episodes.append(f"第1集${drama_id}@@1@@1")

        return {
            "list": [{
                "vod_id": drama_id,
                "vod_name": name,
                "vod_pic": pic,
                "vod_content": desc,
                "vod_play_from": "漫剧专线",
                "vod_play_url": "#".join(episodes)
            }]
        }

    # ══════════════════════════════════════════════════════════
    # 4. 播放地址解析（对接 /api/stream 并返回真实直链）
    # ══════════════════════════════════════════════════════════
    def playerContent(self, flag: str, id: str, vipFlags: str) -> dict:
        play_url = ""
        if "@@" in id:
            parts = id.split("@@")
            drama_id = parts[0]
            ep = parts[1] if len(parts) > 1 else "1"
            ep_id = parts[2] if len(parts) > 2 else ep
        else:
            drama_id = id
            ep = "1"
            ep_id = "1"

        # 请求真实 stream 接口
        stream_api = f"{self.siteUrl}/api/stream?drama={drama_id}&ep={ep}&epId={ep_id}"
        resp_text = self.fetch(stream_api)
        
        if resp_text and resp_text.strip().startswith("{"):
            try:
                data = json.loads(resp_text)
                stream_path = data.get("stream", "")
                if stream_path:
                    play_url = self.fix_url(stream_path)
            except Exception:
                pass

        if not play_url:
            play_url = stream_api

        headers = {
            "User-Agent": self._ua,
            "Referer": f"{self.siteUrl}/",
            "Origin": self.siteUrl
        }

        return {
            "parse": 0,
            "url": play_url,
            "header": json.dumps(headers)
        }

    # ══════════════════════════════════════════════════════════
    # 5. 搜索功能
    # ══════════════════════════════════════════════════════════
    def searchContent(self, key: str, quick: str, pg: str = "1") -> dict:
        videos = []
        search_api = f"{self.siteUrl}/api/filter?category_id=1&keyword={quote(key)}&page={pg}&pageSize=30"
        resp_text = self.fetch(search_api)
        
        if resp_text and resp_text.strip().startswith("{"):
            try:
                data = json.loads(resp_text)
                for item in data.get("list", []):
                    videos.append({
                        "vod_id": str(item.get("id")),
                        "vod_name": item.get("title", ""),
                        "vod_pic": self.fix_url(item.get("cover", "")),
                        "vod_remarks": item.get("badge", "")
                    })
            except Exception:
                pass
        return {"list": videos}

    def isVideoFormat(self, url: str) -> bool:
        formats = [".m3u8", ".mp4", ".ts"]
        return any(f in url.lower() for f in formats)

    def manualVideoCheck(self) -> bool:
        return False

    def localProxy(self, param: dict) -> list:
        return [200, "text/plain", "OK"]