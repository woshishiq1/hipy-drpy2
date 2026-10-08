#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===================================================
  风欲熟女 (jbm.fysn9.ink) TVBox 爬虫源
  框架: 苹果CMS v10 标准模板
  特征:
    - 分类: /cn/home/web/index.php/vod/type/id/{tid}/page/{pg}.html
    - 搜索: /cn/home/web/index.php/vod/search/wd/{wd}.html
    - 播放页: /cn/home/web/index.php/vod/play/id/{vid}/sid/{sid}/nid/{nid}.html
    - m3u8: 播放页 var player_data={"url":"https://...m3u8"}
    - 封面 CDN 需 Referer
  日期: 2026-09-01
===================================================
"""

import sys
import re
import json
import time
import random
import warnings
from urllib.parse import quote, urljoin
from typing import Dict, List, Optional

warnings.filterwarnings("ignore")

try:
    import requests as _req
    _HAS_REQ = True
except ImportError:
    _HAS_REQ = False

try:
    import httpx as _httpx
    _HAS_HTTPX = True
except ImportError:
    _HAS_HTTPX = False

try:
    from bs4 import BeautifulSoup
    _HAS_BS4 = True
except ImportError:
    _HAS_BS4 = False

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        pass


HOST = "https://jbm.fysn9.ink"
BASE_PATH = "/cn/home/web"

CATEGORIES = [
    {"type_id": "1", "type_name": "乱伦"},
    {"type_id": "2", "type_name": "出轨"},
    {"type_id": "3", "type_name": "制服"},
    {"type_id": "4", "type_name": "自慰"},
    {"type_id": "5", "type_name": "偷拍"},
    {"type_id": "20", "type_name": "自拍"},
    {"type_id": "21", "type_name": "国产"},
    {"type_id": "22", "type_name": "同性"},
    {"type_id": "23", "type_name": "日韩"},
    {"type_id": "24", "type_name": "欧美"},
    {"type_id": "25", "type_name": "三级"},
    {"type_id": "26", "type_name": "动漫"},
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

PAGE_SIZE = 24


def _extract_vid(href: str) -> Optional[str]:
    """从播放链接提取视频ID"""
    m = re.search(r"/vod/play/id/(\d+)", href)
    return m.group(1) if m else None


class Spider(BaseSpider):

    def init(self, extend=""):
        if extend and isinstance(extend, str) and extend.startswith("http"):
            self.siteUrl = extend.rstrip("/")
        else:
            self.siteUrl = HOST
        self._session = None

    def __init__(self):
        super().__init__()
        self.siteUrl = HOST
        self._session = None

    def _get_session(self):
        if self._session is None:
            if _HAS_REQ:
                self._session = _req.Session()
                self._session.headers.update(HEADERS)
                self._session.verify = False
            elif _HAS_HTTPX:
                self._session = _httpx.Client(
                    http2=True, headers=HEADERS, verify=False, follow_redirects=True
                )
        return self._session

    def _fetch(self, path: str) -> Optional[str]:
        url = path if path.startswith("http") else urljoin(self.siteUrl, path)
        session = self._get_session()
        for attempt in range(3):
            try:
                if _HAS_REQ:
                    resp = session.get(url, timeout=20, verify=False)
                    return resp.text
                elif _HAS_HTTPX:
                    resp = session.get(url, timeout=20)
                    return resp.text
                else:
                    import urllib.request
                    req = urllib.request.Request(url, headers=HEADERS)
                    with urllib.request.urlopen(req, timeout=20) as r:
                        return r.read().decode("utf-8", errors="replace")
            except Exception as e:
                print(f"[jbm] fetch error (attempt {attempt+1}): {e}", file=sys.stderr)
                time.sleep(1 + random.random())
        return None

    # ==================== 首页 ====================

    def homeContent(self, filter: bool = False) -> Dict:
        try:
            cats = [{"type_id": c["type_id"], "type_name": c["type_name"]} for c in CATEGORIES]
            html = self._fetch(BASE_PATH + "/")
            videos = self._parse_list(html) if html else []
            return {"class": cats, "list": videos, "filters": {}}
        except Exception as e:
            print(f"[jbm] homeContent error: {e}", file=sys.stderr)
            return {"class": [{"type_id": c["type_id"], "type_name": c["type_name"]} for c in CATEGORIES], "list": [], "filters": {}}

    def homeVideoContent(self) -> Dict:
        try:
            html = self._fetch(BASE_PATH + "/")
            videos = self._parse_list(html) if html else []
            return {"list": videos}
        except Exception:
            return {"list": []}

    # ==================== 分类 ====================

    def categoryContent(self, tid: str, pg: str = "1", filter: bool = False, extend: Dict = None) -> Dict:
        try:
            page = int(pg or 1)
            path = f"{BASE_PATH}/index.php/vod/type/id/{tid}.html"
            if page > 1:
                path = f"{BASE_PATH}/index.php/vod/type/id/{tid}/page/{page}.html"
            html = self._fetch(path)
            if not html:
                return {"list": [], "page": page, "pagecount": 1, "limit": PAGE_SIZE, "total": 0}
            videos = self._parse_list(html)
            pagecount = self._parse_pagecount(html, page)
            return {"list": videos, "page": page, "pagecount": pagecount, "limit": PAGE_SIZE, "total": pagecount * PAGE_SIZE}
        except Exception as e:
            print(f"[jbm] categoryContent error: {e}", file=sys.stderr)
            return {"list": [], "page": int(pg or 1), "pagecount": 1, "limit": 0, "total": 0}

    # ==================== 详情 ====================

    def detailContent(self, ids: List[str]) -> Dict:
        try:
            if not ids:
                return {"list": []}
            vid = str(ids[0])
            if not vid:
                return {"list": []}

            # 1) 先取详情页（封面 + 元信息）
            detail_path = f"{BASE_PATH}/index.php/vod/detail/id/{vid}.html"
            detail_html = self._fetch(detail_path)
            info = self._parse_detail(detail_html or "", vid)

            # 2) 再取播放页（m3u8）
            play_path = f"{BASE_PATH}/index.php/vod/play/id/{vid}/sid/1/nid/1.html"
            play_html = self._fetch(play_path)
            m3u8 = self._parse_m3u8(play_html or "")

            if m3u8:
                info["vod_play_from"] = "风欲熟女"
                info["vod_play_url"] = f"第1集${m3u8}"
            else:
                # fallback：用播放页 URL 让 TVBox 嗅探
                info["vod_play_from"] = "风欲熟女"
                info["vod_play_url"] = f"第1集${self.siteUrl}{play_path}"

            return {"list": [info]}
        except Exception as e:
            print(f"[jbm] detailContent error: {e}", file=sys.stderr)
            return {"list": []}

    def _parse_m3u8(self, html: str) -> Optional[str]:
        if not html:
            return None
        # player_data 后紧跟 </script>，没有分号，因此正则不能带 ;
        player_m = re.search(r'var\s+player_data\s*=\s*(\{.*?\})', html)
        if player_m:
            try:
                player = json.loads(player_m.group(1))
                url = player.get("url", "")
                if url:
                    return url.replace("\\/", "/")
            except Exception:
                # fallback 正则
                url_m = re.search(r'"url":"(https?://[^"]+\.m3u8[^"]*)"', player_m.group(1))
                if url_m:
                    return url_m.group(1).replace("\\/", "/")
        else:
            # 兜底：在整页中直接搜 m3u8 链接
            url_m = re.search(r'"url":"(https?://[^"]+\.m3u8[^"]*)"', html)
            if url_m:
                return url_m.group(1).replace("\\/", "/")
        return None

    # ==================== 搜索 ====================

    def searchContent(self, key: str, quick: str = None, pg: str = "1") -> Dict:
        try:
            if not key:
                return {"list": [], "page": 1, "pagecount": 1}
            page = int(pg or 1)
            path = f"{BASE_PATH}/index.php/vod/search/wd/{quote(key)}.html"
            if page > 1:
                path = f"{BASE_PATH}/index.php/vod/search/wd/{quote(key)}/page/{page}.html"
            html = self._fetch(path)
            if not html:
                return {"list": [], "page": page, "pagecount": 1}
            videos = self._parse_list(html)
            pagecount = self._parse_pagecount(html, page)
            return {"list": videos, "page": page, "pagecount": pagecount}
        except Exception as e:
            print(f"[jbm] searchContent error: {e}", file=sys.stderr)
            return {"list": [], "page": int(pg or 1), "pagecount": 1}

    # ==================== 播放 ====================

    def playerContent(self, flag: str, id: str, vipFlags: str = None) -> Dict:
        try:
            if not id:
                return {"parse": 0, "url": "", "header": {}}
            header = {
                "User-Agent": HEADERS["User-Agent"],
                "Referer": self.siteUrl + "/",
            }
            return {"parse": 0, "url": id, "header": header}
        except Exception as e:
            print(f"[jbm] playerContent error: {e}", file=sys.stderr)
            return {"parse": 0, "url": id, "header": {}}

    # ==================== 解析工具 ====================

    def _parse_list(self, html: str) -> List[Dict]:
        videos = []
        if not html:
            return videos
        soup = BeautifulSoup(html, "html.parser") if _HAS_BS4 else None
        if soup:
            # 限制在 .img-list 内匹配，避免命中侧边栏 .ranking-list 的无封面条目
            for a in soup.select('.img-list a[href*="/vod/play/id/"]'):
                href = a.get("href", "")
                vid = _extract_vid(href)
                if not vid:
                    continue
                title = a.get("title", "")
                if not title:
                    title = a.get_text(strip=True)
                # Remove date suffix like "09-01"
                title = re.sub(r"\d{2}-\d{2}$", "", title).strip()
                if not title:
                    continue
                # Find image
                img = a.select_one("img")
                pic = ""
                if img:
                    pic = img.get("src") or img.get("data-original") or ""
                # Extract quality/duration from parent
                parent = a.parent
                remark = ""
                if parent:
                    badge = parent.select_one(".badge, .label, .duration, .quality, .remark, .pic-text, .pic_text")
                    if badge:
                        remark = badge.get_text(strip=True)
                videos.append({"vod_id": vid, "vod_name": title, "vod_pic": pic, "vod_remarks": remark})
        else:
            # Regex fallback: require <li> wrapper + <img>
            pattern = re.compile(
                r'<li[^>]*>.*?<a[^>]*href="(/cn/home/web/index\.php/vod/play/id/(\d+)/sid/\d+/nid/\d+\.html)"[^>]*title="([^"]*)"[^>]*>.*?<img[^>]*(?:src|data-original)="([^"]*)"[^>]*>.*?</a>.*?</li>',
                re.DOTALL
            )
            for m in pattern.finditer(html):
                vid, title, pic = m.group(2), m.group(3), m.group(4)
                title = re.sub(r"\d{2}-\d{2}$", "", title).strip()
                if title:
                    videos.append({"vod_id": vid, "vod_name": title, "vod_pic": pic, "vod_remarks": ""})
        return videos

    def _parse_pagecount(self, html: str, current_page: int) -> int:
        if not html:
            return 1
        pages = re.findall(r'/page/(\d+)\.html', html)
        if pages:
            max_page = max(int(p) for p in pages)
            return max(max_page, current_page)
        return current_page

    def _parse_detail(self, html: str, vid: str) -> Dict:
        info = {
            "vod_id": vid,
            "vod_name": "",
            "vod_pic": "",
            "vod_content": "",
            "vod_year": "",
            "vod_area": "",
            "vod_actor": "",
            "vod_director": "",
            "vod_remarks": "",
            "vod_play_from": "",
            "vod_play_url": "",
        }
        if not html:
            return info

        # Extract title from <title> or h1
        title_m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.DOTALL)
        if title_m:
            info["vod_name"] = re.sub(r'<[^>]+>', '', title_m.group(1)).strip()
        else:
            title_m = re.search(r'<title>([^<]+)</title>', html)
            if title_m:
                raw = title_m.group(1).strip()
                # "在线播放【xxx】第1集 - ..." -> extract video name
                m = re.search(r'在线播放(.+?)第\d+集', raw)
                if m:
                    info["vod_name"] = m.group(1).strip()
                else:
                    info["vod_name"] = raw.split("-")[0].replace("在线播放", "").strip()

        # Extract m3u8 from player_data
        m3u8 = None
        player_m = re.search(r'var\s+player_data\s*=\s*(\{.*?\});', html, re.DOTALL)
        if player_m:
            try:
                player = json.loads(player_m.group(1))
                m3u8 = player.get("url", "")
            except:
                # Fallback: direct regex on the script content
                url_m = re.search(r'"url":"(https?://[^"]+\.m3u8[^"]*)"', player_m.group(1))
                if url_m:
                    m3u8 = url_m.group(1).replace("\\/", "/")
        else:
            # Direct search in page
            url_m = re.search(r'"url":"(https?://[^"]+\.m3u8[^"]*)"', html)
            if url_m:
                m3u8 = url_m.group(1).replace("\\/", "/")

        # Extract cover image
        if _HAS_BS4:
            soup = BeautifulSoup(html, "html.parser")
            cover = soup.select_one("img[src*='/upload/']")
            if cover:
                info["vod_pic"] = cover.get("src", "")
            # Info from info box
            info_box = soup.select_one(".video_info, .video-info")
            if info_box:
                text = info_box.get_text(strip=True, separator="\n")
                # Extract year
                year_m = re.search(r"年份[：:]\s*(\d{4})", text)
                if year_m:
                    info["vod_year"] = year_m.group(1)
                # Extract type/area
                type_m = re.search(r"类型[：:]\s*([^\n]+)", text)
                if type_m:
                    info["vod_area"] = type_m.group(1).strip()
                # Extract description
                desc_m = re.search(r"剧情[：:]\s*([^\n]+)", text)
                if desc_m:
                    info["vod_content"] = desc_m.group(1).strip()
        else:
            cover_m = re.search(r'<img[^>]*src="([^"]*upload[^"]*)"', html)
            if cover_m:
                info["vod_pic"] = cover_m.group(1)

        # Build play info
        if m3u8:
            info["vod_play_from"] = "风欲熟女"
            info["vod_play_url"] = f"第1集${m3u8}"
        else:
            info["vod_play_from"] = "风欲熟女"
            info["vod_play_url"] = f"第1集${self.siteUrl}{BASE_PATH}/index.php/vod/play/id/{vid}/sid/1/nid/1.html"

        return info

    # ==================== 辅助接口 ====================

    def isHD(self) -> bool:
        return True

    def manualVideoCheck(self) -> bool:
        return False

    def getPicHeader(self) -> Dict:
        return {
            "User-Agent": HEADERS["User-Agent"],
            "Referer": self.siteUrl + "/",
        }

    def get_HTTP_live_Header(self) -> Dict:
        return HEADERS


# ========================================================================
#  自检
# ========================================================================

def self_test():
    print("=" * 60)
    print("  风欲熟女 (jbm.fysn9.ink) TVBox 爬虫源 自检")
    print("=" * 60)

    spider = Spider()

    print("\n[1] homeContent...")
    home = spider.homeContent()
    print(f"  分类: {len(home.get('class', []))}")
    print(f"  推荐: {len(home.get('list', []))} 条")
    if home.get("list"):
        v = home["list"][0]
        print(f"  首条: vid={v['vod_id']}, name={v['vod_name'][:30]}, pic={v['vod_pic'][:50]}")

    print("\n[2] categoryContent(tid=1, pg=1)...")
    cat = spider.categoryContent("1", "1")
    print(f"  视频: {len(cat.get('list', []))}")
    print(f"  页数: {cat.get('pagecount', 0)}")
    if cat.get("list"):
        v = cat["list"][0]
        print(f"  首条: vid={v['vod_id']}, name={v['vod_name'][:30]}")

    print("\n[3] searchContent('文轩')...")
    search = spider.searchContent("文轩", "", "1")
    print(f"  结果: {len(search.get('list', []))} 条")
    if search.get("list"):
        v = search["list"][0]
        print(f"  首条: vid={v['vod_id']}, name={v['vod_name'][:30]}")

    print("\n[4] detailContent...")
    if search.get("list"):
        test_vid = search["list"][0]["vod_id"]
        detail = spider.detailContent([test_vid])
        if detail.get("list"):
            d = detail["list"][0]
            print(f"  名称: {d['vod_name'][:40]}")
            print(f"  封面: {d['vod_pic'][:60]}")
            print(f"  播放源: {d['vod_play_from']}")
            print(f"  播放: {d['vod_play_url'][:100]}")

            print("\n[5] playerContent...")
            play_url = d["vod_play_url"].split("$")[1] if "$" in d["vod_play_url"] else d["vod_play_url"]
            play = spider.playerContent("风欲熟女", play_url)
            print(f"  parse: {play.get('parse', 0)}")
            print(f"  url: {play.get('url', '')[:80]}")
        else:
            print("  详情为空!")
    else:
        print("  跳过")

    print("\n" + "=" * 60)
    print("  自检完成")
    print("=" * 60)


if __name__ == "__main__":
    self_test()
