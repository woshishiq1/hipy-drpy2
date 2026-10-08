#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TVBox Spider - 爽上天聚合站
框架: Maccsms
"""

import re
import json
import base64
from urllib.parse import urlparse, urljoin
import ssl
import urllib.request
from typing import List, Dict, Any

# ============ 站点配置 ============
SITENAME = "爽上天"
SITE_URL = "https://mya.sst9.casa/sst/"
RAW_SITE = "https://mya.sst9.casa"
CMS_PATH = "/cn/home/web"
ENDPOINT = "index.php/vod"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36",
    "Referer": "https://mya.sst9.casa/",
    "Origin": "https://mya.sst9.casa",
}
# ============ 站点配置 ============


class Spider:
    def __init__(self):
        self.site = SITENAME
        self.base = SITE_URL
        self.raw = RAW_SITE
        self.api = f"{SITE_URL}{CMS_PATH}/{ENDPOINT}"
        self.cls = {}
        self.cache = {}
        
    def _get(self, url: str) -> str:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url, headers=HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
                return resp.read().decode('utf-8', errors='ignore')
        except:
            return ""

    def homeContent(self) -> dict:
        html = self._get(self.base)
        cats = re.findall(
            r'<li[^>]*><a[^>]*href="(/cn/home/web/index.php/vod/type/id/(\d+)\.html)"[^>]*title="([^"]+)"',
            html
        )
        cls = [{"type_id": int(c[1]), "type_name": c[2]} for c in cats]
        return {"class": cls, "filters": {}}

    def categoryContent(self, tid: str, page: int = 1) -> dict:
        url = f"{self.api}/type/id/{tid}.html"
        html = self._get(url)
        items = []
        vids = re.findall(
            r'<a[^>]*href="/cn/home/web/index.php/vod/play/id/(\d+)/sid/(\d+)/nid/(\d+)\.html"[^>]*>.*?<img[^>]*data-original="([^"]*)"[^>]*alt="([^"]*)".*?<span[^>]*class="des">([^<]*)</span>',
            html, re.DOTALL
        )
        for vid, sid, nid, img, title, mark in vids[:30]:
            items.append({
                "vod_id": vid,
                "vod_name": title[:40],
                "vod_pic": img if img.startswith('http') else self.raw + img,
                "vod_remarks": mark.strip()
            })
        return {"page": page, "pagecount": 10, "limit": 30, "total": 300, "list": items}

    def detailContent(self, vod_ids: List[str]) -> dict:
        vod_id = vod_ids[0] if isinstance(vod_ids, list) else vod_ids
        url = f"{self.api}/play/id/{vod_id}/sid/1/nid/1.html"
        html = self._get(url)
        
        # 提取标题
        title = re.search(r'<title>(.*?)</title>', html)
        title = title.group(1).replace(' - 爽上天', '').strip() if title else '未知'
        
        # 提取封面
        pic = re.search(r'<img[^>]*src="([^"]*)"[^>]*class="[^"]*pic[^"]*"', html)
        pic = pic.group(1) if pic else ''
        
        # 提取播放源
        play_from = ["在线播放"]
        
        return {
            "list": [{
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": pic,
                "vod_playfrom": "$$$".join(play_from),
                "vod_playurl": url + "#",
                "vod_remarks": "",
                "vod_content": ""
            }]
        }

    def searchContent(self, wd: str, page: int = 1) -> dict:
        url = f"{self.api}/search.html?wd={wd}"
        html = self._get(url)
        items = []
        vids = re.findall(
            r'href="/cn/home/web/index.php/vod/play/id/(\d+)/sid/(\d+)/nid/(\d+)\.html"[^>]*>.*?<img[^>]*data-original="([^"]*)"[^>]*alt="([^"]*)"',
            html, re.DOTALL
        )
        for vid, sid, nid, img, title in vids[:30]:
            items.append({
                "vod_id": vid,
                "vod_name": title[:40],
                "vod_pic": img if img.startswith('http') else self.raw + img,
                "vod_remarks": ""
            })
        return {"page": page, "pagecount": 5, "limit": 30, "total": 100, "list": items}

    def playerContent(self, flag: str, id: str, vipFlags: str = "0") -> dict:
        # 此处需要解析实际播放地址
        # Maccms站点的实际播放链接需要在详情页提取
        # 这里返回空值，需要更复杂的解析
        return {
            "parse": 0,
            "jx": 0,
            "url": "",
            "header": {
                "User-Agent": HEADERS["User-Agent"],
                "Referer": self.raw + "/",
                "Origin": self.raw
            }
        }

if __name__ == "__main__":
    s = Spider()
    print("Spider 初始化成功")
