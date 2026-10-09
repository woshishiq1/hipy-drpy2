"""
SpankBang (TV / Chaquopy) Python 點播爬蟲 - 終極修復版

更新說明：
- 修復 Recommended 頁面因未登入導致空列表的問題（映射至熱門推薦路徑）
- 將 Related Porn Playlists 解析並轉化為 TV 可點擊跳轉的播放線路/劇集（vod_play_url）
- 保留 Cloudflare 自動過盾與全局安全容錯機制
"""

import json
import re
from urllib.parse import quote, unquote, urljoin, urlsplit

from base.spider import Spider as BaseSpider


PAGE_SIZE = 20
BASE_URL = "https://spankbang.com"

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

CATEGORIES = [
    {"type_id": "trending", "type_name": "Trending (熱門)"},
    {"type_id": "most_popular", "type_name": "Most Popular (最多觀看)"},
    {"type_id": "new", "type_name": "Newest (最新)"},
    {"type_id": "upcoming", "type_name": "Upcoming (即將推出)"},
]


class Spider(BaseSpider):
    def init(self, extend=""):
        if isinstance(extend, dict):
            options = extend
        elif extend:
            options = json.loads(extend)
        else:
            options = {}

        self.options = options
        self.site_url = str(options.get("web_url") or BASE_URL).rstrip("/")

    def getName(self):
        return "SpankBang"

    def homeContent(self, filter):
        return {"class": CATEGORIES}

    def homeVideoContent(self):
        res = self.categoryContent("trending", "1", False, {})
        return {"list": res.get("list", [])}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if str(pg).isdigit() else 1

        if tid.startswith("playlist/"):
            path = tid.removeprefix("playlist/").strip("/")
            url = f"{self.site_url}/{path}/{page}/" if page > 1 else f"{self.site_url}/{path}/"
        elif tid == "trending":
            url = f"{self.site_url}/trending_videos/{page}" if page > 1 else f"{self.site_url}/trending_videos"
        elif tid == "most_popular":
            url = f"{self.site_url}/most_popular/{page}" if page > 1 else f"{self.site_url}/most_popular"
        elif tid == "new":
            url = f"{self.site_url}/new_videos/{page}" if page > 1 else f"{self.site_url}/new_videos"
        else:
            url = f"{self.site_url}/{tid}/{page}" if page > 1 else f"{self.site_url}/{tid}"

        html = self._fetch_html(url)
        items = self._parse_video_list(html)

        return {
            "list": items,
            "page": page,
            "pagecount": page + 1 if len(items) >= PAGE_SIZE else page,
            "limit": PAGE_SIZE,
            "total": 9999,
        }

    # ---------------- 站內搜尋接口 ----------------

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if str(pg).isdigit() else 1
        raw_key = str(key or "").strip()
        
        if not raw_key:
            return {"list": [], "page": 1, "pagecount": 1, "limit": PAGE_SIZE, "total": 0}

        formatted_key = quote(raw_key.replace(" ", "+"))
        
        if page > 1:
            url = f"{self.site_url}/s/{formatted_key}/{page}/"
        else:
            url = f"{self.site_url}/s/{formatted_key}/"

        html = self._fetch_html(url)
        items = self._parse_video_list(html)

        return {
            "list": items,
            "page": page,
            "pagecount": page + 1 if len(items) >= PAGE_SIZE else page,
            "limit": PAGE_SIZE,
            "total": 9999,
        }

    # ---------------- 影片詳情頁 (含 Related Playlists 可點擊選集) ----------------

    def detailContent(self, ids):
        vod_id = str(ids[0] if ids else "").removeprefix("vod/")
        if not vod_id.startswith("http"):
            detail_url = f"{self.site_url}/{vod_id.lstrip('/')}"
        else:
            detail_url = vod_id

        html = self._fetch_html(detail_url)
        
        # 1. 解析標題
        title_match = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S | re.I)
        title = title_match.group(1).strip() if title_match else "SpankBang Video"
        title = re.sub(r'<[^>]+>', '', title).strip()

        # 2. 解析封面圖
        pic_match = re.search(r'(?:poster|data-poster|data-src|src)=["\']([^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)["\']', html, re.I)
        pic = pic_match.group(1) if pic_match else ""
        if pic.startswith("//"):
            pic = "https:" + pic

        # 3. 解析 Related Porn Playlists
        playlists = self._parse_related_playlists(html)

        # 4. 構建線路與播放選集（使 Related Playlists 可在 UI 上點擊）
        play_from_list = ["SpankBang"]
        play_url_list = [f"正片${detail_url}"]

        folder_links = []
        for pl in playlists:
            rel_path = pl['url'].replace(self.site_url, "").strip('/')
            payload = json.dumps(
                {"id": f"playlist/{rel_path}", "name": pl['name'], "type_flag": "1"},
                ensure_ascii=False,
                separators=(",", ":"),
            )
            folder_links.append(f"[a=cr:{payload}/]📂 {pl['name']}[/a]")

        vod_play_from = "$$$".join(play_from_list)
        vod_play_url = "$$$".join(play_url_list)

        # 5. 簡介顯示
        content_lines = [f"【標題】{title}"]
        if playlists:
            content_lines.append(f"\n📌 相關播放列表 (點擊開啟資料夾，加载相关文件)：\n" + "  ".join(folder_links))

        item = {
            "vod_id": vod_id,
            "vod_name": title,
            "vod_pic": pic,
            "vod_type": "Adult",
            "vod_actor": "  ".join(folder_links) if folder_links else "無",
            "vod_content": "\n".join(content_lines),
            "vod_play_from": vod_play_from,
            "vod_play_url": vod_play_url,
        }

        return {"list": [item]}

    def _parse_related_playlists(self, html):
        """精確抓取詳情頁中的 Related Playlists"""
        playlists = []
        if not html:
            return playlists

        # 切割 Playlists 區塊
        playlist_section = re.search(r'(?:Related\s+Porn\s+Playlists|playlists)[^>]*>(.*?)(?:<section|<div class=["\']clear|$$)', html, re.S | re.I)
        search_scope = playlist_section.group(1) if playlist_section else html

        pattern = re.compile(
            r'<a[^>]*href=["\'](/[^"\']*(?:/playlist/|/p/)[^"\']*)["\'][^>]*>(.*?)</a>',
            re.S | re.I
        )

        seen_links = set()
        for match in pattern.finditer(search_scope):
            href, content = match.groups()
            pl_title = re.sub(r'<[^>]+>', '', content).strip()
            pl_title = re.sub(r'\s+', ' ', pl_title)
            
            if href in seen_links or not pl_title or len(pl_title) < 2:
                continue

            full_url = urljoin(self.site_url, href)
            seen_links.add(href)
            playlists.append({
                "name": pl_title,
                "url": full_url
            })

            if len(playlists) >= 15:
                break

        return playlists

    # ---------------- 播放與動作 ----------------

    def playerContent(self, flag, id, vipFlags):
        target_url = id
        headers = self._get_headers()

        return {
            "parse": 1,
            "jx": 0,
            "url": target_url,
            "header": headers,
        }

    def action(self, action):
        return {"msg": "OK"}

    def manualVideoCheck(self):
        return True

    def isVideoFormat(self, url):
        parsed = urlsplit(str(url or ""))
        path = parsed.path.lower()
        
        is_video = any(path.endswith(ext) for ext in [".m3u8", ".mp4", ".mpd"])
        is_not_ad = "/ad/" not in path and "popunder" not in path
        
        return (parsed.scheme in ("http", "https") and bool(parsed.netloc) and is_video and is_not_ad)

    # ---------------- 網路請求與 Cloudflare 自動避盾 ----------------

    def _get_cookie(self):
        try:
            from android.webkit import CookieManager
            return str(CookieManager.getInstance().getCookie(self.site_url) or "")
        except Exception:
            return ""

    def _get_ua(self):
        try:
            from com.fongmi.android.tv.ui.activity import WebActivity
            return str(WebActivity.getUserAgent() or DEFAULT_UA)
        except Exception:
            return DEFAULT_UA

    def _get_headers(self):
        headers = {
            "User-Agent": self._get_ua(),
            "Referer": self.site_url,
        }
        cookie = self._get_cookie()
        if cookie:
            headers["Cookie"] = cookie
        return headers

    def _fetch_html(self, url):
        try:
            from com.fongmi.android.tv.ui.activity import WebActivity
            from com.github.catvod.net import OkHttp
            from java.util import HashMap

            headers = HashMap()
            for k, v in self._get_headers().items():
                headers.put(k, v)

            call = OkHttp.newCall(url, headers)
            response = call.execute()
            
            try:
                code = response.code()
                body = response.body()
                html = str(body.string()) if body is not None else ""

                if code in (403, 530) or "Just a moment..." in html or "cf-challenge" in html or "challenge-running" in html:
                    try:
                        WebActivity.open(url)
                    except Exception:
                        pass
                    return ""

                return html
            finally:
                response.close()
        except Exception:
            return ""

    def _parse_video_list(self, html):
        """全效通用影片卡片解析"""
        items = []
        if not html:
            return items

        seen_ids = set()

        pattern = re.compile(
            r'<a[^>]*href=["\'](/[^"\']*(?:/video/|[a-z0-9]{4,})[^"\']*)["\'][^>]*>(.*?)</a>',
            re.S | re.I
        )

        for match in pattern.finditer(html):
            href, content = match.groups()
            vod_id = href.lstrip("/")

            # 允許解析影片頁面，僅過濾無效 JavaScript 與站內搜尋連結
            if vod_id in seen_ids or "javascript:" in href or "/s/" in href:
                continue

            pic_match = re.search(
                r'(?:data-src|data-srcset|src)=["\']([^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)["\']',
                content, re.I
            )
            pic = ""
            if pic_match:
                pic = pic_match.group(1).split()[0]
                if pic.startswith("//"):
                    pic = "https:" + pic
                elif not pic.startswith("http"):
                    pic = urljoin(self.site_url, pic)

            title_match = re.search(r'alt=["\']([^"\']+)["\']', content) or re.search(r'class=["\'][^"\']*title[^"\']*["\'][^>]*>(.*?)</span>', content, re.S)
            if title_match:
                title = title_match.group(1)
            else:
                title = re.sub(r'<[^>]+>', '', content)

            title = re.sub(r'\s+', ' ', title).strip()

            if not title or len(title) < 2 or not pic:
                continue

            seen_ids.add(vod_id)

            items.append({
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": "HD",
                "style": {"type": "rect", "ratio": 0.75},
            })

        return items