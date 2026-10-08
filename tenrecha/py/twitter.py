# -*- coding: utf-8 -*-
"""
══════════════════════════════════════════════════════════════════
Pektino Video Spider for TVBox / 影视仓
官方交流频道/群组: https://t.me/tvshare23
══════════════════════════════════════════════════════════════════
"""
import re
import json
from urllib import parse
from bs4 import BeautifulSoup
import requests

try:
    from base.spider import Spider as SpiderBase
except ImportError:
    class SpiderBase:
        pass

class Spider(SpiderBase):
    def __init__(self):
        super().__init__()
        self.siteUrl = "https://pektino.com"
        self.session = requests.Session()
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        self.channel_url = "https://t.me/tvshare23"
        
        # 广告、导流与占位过滤关键词
        self.ad_keywords = [
            "telegram", "tg频道", "tg群", "电报", "チャンネル", 
            "お気に入り", "favorite", "qrcode", "二维码", "推广", 
            "广告", "赞助", "官方群", "交流群", "关注"
        ]

    def _is_ad(self, title: str, href: str, pic: str) -> bool:
        """过滤广告与无效占位卡片"""
        combined = f"{title} {href} {pic}".lower()
        if any(kw in combined for kw in self.ad_keywords):
            return True
        if "t.me/" in href or "telegram.me/" in href:
            return True
        return False

    def _build_headers(self, is_ajax: bool = False, extra: dict = None) -> dict:
        h = {
            "User-Agent": self.ua,
            "Accept": "*/*" if is_ajax else "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": f"{self.siteUrl}/",
        }
        if is_ajax:
            h["HX-Request"] = "true"
            h["HX-Target"] = "main"
            h["HX-Current-URL"] = f"{self.siteUrl}/zh-CN"
        if extra:
            h.update(extra)
        return h

    def _fetch(self, url: str, is_ajax: bool = False) -> str:
        try:
            h = self._build_headers(is_ajax=is_ajax)
            resp = self.session.get(url, headers=h, timeout=12, allow_redirects=True)
            resp.encoding = getattr(resp, "apparent_encoding", None) or "utf-8"
            return resp.text
        except Exception:
            return ""

    def _fix_url(self, url: str) -> str:
        if not url:
            return ""
        if url.startswith("http"):
            return url
        if url.startswith("//"):
            return f"https:{url}"
        if url.startswith("/"):
            return f"{self.siteUrl.rstrip('/')}{url}"
        return f"{self.siteUrl.rstrip('/')}/{url}"

    def _clean_title(self, title: str) -> str:
        import html as _html
        t = _html.unescape(title or "")
        t = re.sub(r"<[^>]+>", "", t)
        return t.strip()

    def init(self, extend=""):
        return True

    def isVideoFormat(self, url):
        return any(ext in url.lower() for ext in [".m3u8", ".mp4", ".ts", ".flv", ".mov"])

    def manualVideoCheck(self):
        return False

    # ───── 1. 首页分类 ─────
    def homeContent(self, filter=False):
        return {
            "class": [
                {"type_name": "🔥 每天", "type_id": "/zh-CN"},
                {"type_name": "📅 每周", "type_id": "/zh-CN/weekly"},
                {"type_name": "📈 每月", "type_id": "/zh-CN/monthly"},
                {"type_name": "⏳ 控球时间", "type_id": "/zh-CN/duration"},
            ]
        }

    # ───── 2. 分类列表 ─────
    def categoryContent(self, tid, pg, filter=False, extend=None):
        base_url = self._fix_url(tid)
        
        if int(pg) > 1:
            sep = "&" if "?" in base_url else "?"
            url = f"{base_url}{sep}page={pg}"
        else:
            url = base_url

        html = self._fetch(url, is_ajax=True)
        if not html or len(html) < 200:
            html = self._fetch(url, is_ajax=False)

        if not html or ("404" in html[:300] and "/zh-CN/" in base_url):
            tab_name = base_url.split("/")[-1]
            fallback_url = f"{self.siteUrl}/zh-CN?tab={tab_name}"
            if int(pg) > 1:
                fallback_url += f"&page={pg}"
            html = self._fetch(fallback_url, is_ajax=False)

        videos = []
        seen = set()

        # 优先解析 Next.js 数据
        if "__NEXT_DATA__" in html:
            try:
                m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
                if m:
                    jdata = json.loads(m.group(1))
                    page_props = jdata.get("props", {}).get("pageProps", {})
                    items = page_props.get("videos") or page_props.get("list") or page_props.get("posts") or []
                    for it in items:
                        vid = it.get("id") or it.get("slug")
                        if not vid:
                            continue
                        vurl = f"/zh-CN/post/{vid}" if not str(vid).startswith("/") else str(vid)
                        if vurl in seen:
                            continue

                        title = self._clean_title(it.get("title") or it.get("text") or "精选推文")
                        pic = self._fix_url(it.get("cover") or it.get("thumb") or it.get("poster") or "")

                        if self._is_ad(title, vurl, pic):
                            continue

                        seen.add(vurl)
                        videos.append({
                            "vod_id": vurl,
                            "vod_name": title,
                            "vod_pic": pic,
                            "vod_remarks": "推文"
                        })
            except Exception:
                pass

        # 页面 DOM 兜底解析
        if not videos:
            soup = BeautifulSoup(html, "html.parser")
            for a in soup.select("a[href*='/post/'], a[href*='/video/'], a[href*='/watch/'], .video-card a, .card a, a:has(img)"):
                href = a.get("href", "")
                if not href or href in seen or href in ["/", "/zh-CN", "/zh-CN/weekly", "/zh-CN/monthly", "/zh-CN/duration"]:
                    continue
                
                if not re.search(r'/(?:post|video|watch|[a-zA-Z0-9_-]{6,})', href):
                    continue

                img = a.find("img")
                title = self._clean_title(a.get("title") or (img.get("alt", "") if img else "") or a.get_text(strip=True))
                pic = ""
                if img:
                    pic = self._fix_url(img.get("data-src") or img.get("data-original") or img.get("src", "") or "")

                if self._is_ad(title, href, pic):
                    continue

                seen.add(href)
                videos.append({
                    "vod_id": href,
                    "vod_name": title[:60] if title else "精彩视频",
                    "vod_pic": pic,
                    "vod_remarks": "推文"
                })

        return {
            "list": videos,
            "page": int(pg),
            "pagecount": 999 if len(videos) >= 6 else int(pg),
            "limit": len(videos),
            "total": 9999
        }

    # ───── 3. 详情页 ─────
    def detailContent(self, ids):
        vod_id = ids[0]
        url = self._fix_url(vod_id)
        html = self._fetch(url, is_ajax=False)
        soup = BeautifulSoup(html, "html.parser")

        title_node = soup.select_one("h1, h2, .title, meta[property='og:title']")
        if title_node:
            title = title_node.get("content") if title_node.name == "meta" else title_node.get_text(strip=True)
        else:
            title = "视频播放"

        pic_node = soup.select_one("meta[property='og:image'], video[poster], img.poster, img.cover")
        pic = ""
        if pic_node:
            pic = pic_node.get("content") or pic_node.get("poster") or pic_node.get("src", "")

        return {
            "list": [{
                "vod_id": vod_id,
                "vod_name": self._clean_title(title),
                "vod_pic": self._fix_url(pic),
                "vod_content": f"交流频道: {self.channel_url}",
                "vod_play_from": "官方直连",
                "vod_play_url": f"点击播放${url}"
            }]
        }

    # ───── 4. 播放地址解析 ─────
    def playerContent(self, flag, id, vipFlags):
        url = self._fix_url(id)
        play_header = f"User-Agent={self.ua}&Referer={self.siteUrl}/"

        if self.isVideoFormat(url):
            return {
                "parse": 0,
                "url": url,
                "header": play_header
            }

        html = self._fetch(url, is_ajax=False)

        # 1. 抓取 Twitter 视频源 (video.twimg.com / mp4 / m3u8)
        tw_match = re.search(r'(https?://[^"\',\\s]*video\.twimg\.com[^"\',\\s]*\.(?:mp4|m3u8)[^"\',\\s]*)', html)
        if tw_match:
            real_url = tw_match.group(1).replace("\\/", "/")
            return {
                "parse": 0,
                "url": real_url,
                "header": play_header
            }

        # 2. 匹配 video 标签
        video_match = re.search(r'<(?:video|source)[^>]+src=["\']([^"\']+)["\']', html)
        if video_match:
            real_url = self._fix_url(video_match.group(1))
            return {
                "parse": 0,
                "url": real_url,
                "header": play_header
            }

        # 3. 匹配通用 mp4/m3u8 直链正则
        media_match = re.search(r'(https?://[^"\s\',]+\.(?:mp4|m3u8)[^"\s\',]*)', html)
        if media_match:
            real_url = media_match.group(1).replace("\\/", "/")
            return {
                "parse": 0,
                "url": real_url,
                "header": play_header
            }

        # 4. 嗅探兜底
        return {
            "parse": 1,
            "url": url,
            "header": play_header
        }

    # ───── 5. 搜索 ─────
    def searchContent(self, key, quick, pg="1"):
        search_url = f"{self.siteUrl}/zh-CN/search?q={parse.quote(key)}"
        html = self._fetch(search_url, is_ajax=True)
        soup = BeautifulSoup(html, "html.parser")
        videos = []
        for a in soup.select("a[href*='/post/'], a[href*='/video/'], .card a"):
            href = a.get("href", "")
            img = a.find("img")
            title = self._clean_title(a.get("title") or (img.get("alt", "") if img else "") or a.get_text(strip=True))
            pic = self._fix_url(img.get("src", "") if img else "")
            
            if not href or not title or self._is_ad(title, href, pic):
                continue
                
            videos.append({
                "vod_id": href,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": "搜索结果"
            })
        return {"list": videos}

    # ───── 6. 本地代理 ─────
    def localProxy(self, param):
        return [404, "text/plain", "Not supported"]