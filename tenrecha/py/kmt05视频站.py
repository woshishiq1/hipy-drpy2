#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import re
import json
import urllib.request
import urllib.parse
import ssl
from typing import Dict, List, Optional, Any
class TVBoxPlugin:
    BASE_URL = "https://www.kmt05.cc:1234"
    CATEGORIES = [
        {"type_id": "1", "type_name": "推荐"},
        {"type_id": "2", "type_name": "直播"},
        {"type_id": "3", "type_name": "本土"},
        {"type_id": "4", "type_name": "AI"},
        {"type_id": "5", "type_name": "VIP专区"},
        {"type_id": "6", "type_name": "韩国"},
        {"type_id": "7", "type_name": "解说"},
        {"type_id": "8", "type_name": "动漫"},
        {"type_id": "9", "type_name": "欧美"},
        {"type_id": "10", "type_name": "女同"},
        {"type_id": "11", "type_name": "三级片"},
        {"type_id": "12", "type_name": "专题"},
    ]
    def __init__(self):
        self._ssl_ctx = ssl.create_default_context()
        self._ssl_ctx.check_hostname = False
        self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1',
            'Referer': 'https://www.kmt05.cc:1234/',
        }
    def getName(self) -> str:
        return "kmt05视频站"
    def init(self, extend: str = ""):
        pass
    def homeContent(self, filter: bool = True) -> Dict:
        return {"class": self.CATEGORIES.copy()}
    def categoryContent(self, tid: str, pg: int, filter: bool = False, extend: Dict = {}) -> Dict:
        url = f"{self.BASE_URL}/search/{self.CATEGORIES[int(tid)-1]['type_name']}?page={pg}" if int(tid) <= len(self.CATEGORIES) else f"{self.BASE_URL}/search/?page={pg}"
        html = self._request(url)
        if not html:
            return self._empty_page(pg)
        videos = self._parse_video_list(html)
        pc = self._parse_page_count(html)
        return {"list": videos, "page": pg, "pagecount": max(pc, 1), "limit": 20, "total": pc * 20}
    def detailContent(self, ids: List[str]) -> Dict:
        if not ids: return {"list": []}
        vid = ids[0]
        url = f"{self.BASE_URL}/detail/{vid}"
        html = self._request(url)
        if not html: return {"list": []}
        detail = self._parse_video_detail(html, vid)
        return {"list": [detail]}
    def searchContent(self, key: str, quick: bool = False) -> Dict:
        url = f"{self.BASE_URL}/search/{urllib.parse.quote(key)}"
        html = self._request(url)
        if not html: return {"list": []}
        videos = self._parse_video_list(html)
        return {"list": videos}
    def playerContent(self, flag: str, id: str, vipFlags: List[str] = []) -> Dict:
        return {"parse": 0, "playUrl": "", "url": id}
    def localProxy(self, params):
        return [200, "video/MP4", {}, ""]
    def isVideoFormat(self, url) -> bool:
        return bool(re.search(r'\.(m3u8|mp4|flv|avi|mkv|wmv|ts)', url, re.I))
    def manualVideoCheck(self) -> bool:
        return False
    def _request(self, url: str) -> Optional[str]:
        try:
            req = urllib.request.Request(url, headers=self.headers)
            resp = urllib.request.urlopen(req, context=self._ssl_ctx, timeout=15)
            data = resp.read()
            for enc in ['utf-8', 'gbk', 'gb2312', 'latin-1']:
                try:
                    return data.decode(enc)
                except Exception:
                    continue
            return data.decode('utf-8', errors='ignore')
        except Exception as e:
            print(f"请求错误: {e}", file=sys.stderr)
            return None
    def _parse_video_list(self, html: str) -> List[Dict]:
        videos = []
        pat = re.compile(r'<a[^>]*href=["\'](?:https?://[^/]+)?/detail/([^"\']+?)(?:\.html)?["\'][^>]*>([\s\S]*?)</a>', re.I)
        for m in pat.finditer(html):
            vid, body = m.group(1), m.group(2)
            title = self._extract_title(body)
            poster = self._extract_poster(body)
            info = self._extract_info(body)
            if title:
                videos.append({"vod_id": vid, "vod_name": title, "vod_pic": poster, "vod_remarks": info})
        if not videos:
            pat2 = re.compile(r'<a[^>]*href=["\']([^"\']*(?:detail|video|play)[^"\']*)["\'][^>]*>([\s\S]*?)</a>', re.I)
            for m in pat2.finditer(html):
                href, body = m.group(1), m.group(2)
                vm = re.search(r'/(\d+)', href)
                if not vm: continue
                vid = vm.group(1)
                title = self._extract_title(body)
                poster = self._extract_poster(body)
                info = self._extract_info(body)
                if title:
                    videos.append({"vod_id": vid, "vod_name": title, "vod_pic": poster, "vod_remarks": info})
        seen = set()
        out = []
        for v in videos:
            if v['vod_id'] not in seen:
                seen.add(v['vod_id'])
                out.append(v)
        return out[:30]
    def _parse_video_detail(self, html: str, vid: str) -> Dict:
        detail = {"vod_id": vid, "vod_name": "", "vod_pic": "", "vod_year": "", "vod_area": "", "vod_remarks": "", "vod_content": "", "vod_director": "", "vod_actor": "", "type_name": "", "play_from": "kmt05", "play_url": ""}
        for p in [r'<h1[^>]*>([^<]+)</h1>', r'class=["\'][^"\']*title[^"\']*["\'][^>]*>([^<]+)<', r'<title>([^<|]+)']:
            m = re.search(p, html, re.I)
            if m:
                detail["vod_name"] = m.group(1).strip()
                break
        for p in [r'<meta[^>]*property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']', r'<img[^>]*class=["\'][^"\']*cover[^"\']*["\'][^>]*src=["\']([^"\']+)["\']']:
            m = re.search(p, html, re.I)
            if m:
                detail["vod_pic"] = m.group(1)
                break
        for p in [r'(https?://[^"\'<>\s]+\.m3u8[^"\'<>\s]*)', r'playurl["\']?\s*[:=]\s*["\']?(https?://[^"\'<>\s]+)']:
            m = re.search(p, html, re.I)
            if m:
                detail["play_url"] = m.group(1)
                break
        return detail
    def _parse_page_count(self, html: str) -> int:
        for p in [r'共\s*(\d+)\s*页', r'pagecount["\']?\s*[:=]\s*["\']?(\d+)', r'totalPage["\']?\s*[:=]\s*["\']?(\d+)', r'(\d+)\s*前往页']:
            m = re.search(p, html, re.I)
            if m: return int(m.group(1))
        return 1
    def _extract_title(self, content: str) -> str:
        for p in [r'class=["\'][^"\']*title[^"\']*["\'][^>]*>([^<]+)<', r'alt=["\']([^"\']+)["\']', r'title=["\']([^"\']+)["\']']:
            m = re.search(p, content, re.I)
            if m and len(m.group(1).strip()) > 2: return m.group(1).strip()
        t = re.sub(r'<[^>]+>', ' ', content).strip()
        return t[:50] if t else ""
    def _extract_poster(self, content: str) -> str:
        m = re.search(r'<img[^>]*src=["\']([^"\']+\.(?:jpg|jpeg|png|webp))["\']', content, re.I)
        return m.group(1) if m else ""
    def _extract_info(self, content: str) -> str:
        parts = []
        m = re.search(r'([\d.]+[万kK]?)\s*(?:次)?播放', content)
        if m: parts.append(m.group(1) + "播放")
        m = re.search(r'(\d{1,2}:\d{2}(?::\d{2})?)', content)
        if m: parts.append(m.group(1))
        return " | ".join(parts)
    def _empty_page(self, pg: int) -> Dict:
        return {"list": [], "page": pg, "pagecount": 1, "limit": 20, "total": 0}
def main():
    plugin = TVBoxPlugin()
    if len(sys.argv) < 2:
        print("Usage: python3 tvbox_plugin.py <home|category|detail|search> [args]")
        return
    act = sys.argv[1]
    if act == "home":
        print(json.dumps(plugin.homeContent(), ensure_ascii=False, indent=2))
    elif act == "category":
        tid = sys.argv[2] if len(sys.argv) > 2 else "1"
        pg = int(sys.argv[3]) if len(sys.argv) > 3 else 1
        print(json.dumps(plugin.categoryContent(tid, pg), ensure_ascii=False, indent=2))
    elif act == "detail":
        vid = sys.argv[2] if len(sys.argv) > 2 else "1"
        print(json.dumps(plugin.detailContent([vid]), ensure_ascii=False, indent=2))
    elif act == "search":
        key = sys.argv[2] if len(sys.argv) > 2 else ""
        print(json.dumps(plugin.searchContent(key), ensure_ascii=False, indent=2))
if __name__ == "__main__":
    main()