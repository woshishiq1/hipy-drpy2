# -*- coding: utf-8 -*-
# TVBox FongMi v2.1 Python Spider
# 站点: https://javday.app
# 说明: 基于网页 HTML 解析, 分类/列表/详情/搜索均走网页

import sys
sys.path.append('..')
from base.spider import Spider
import re
import json
import urllib.parse


class Spider(Spider):
    # ==================== 类属性 ====================
    siteUrl = "https://javday.app"
    header = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://javday.app/",
    }

    # 分类配置: 名称 -> 路径
    categories = [
        {"type_name": "最近更新", "type_id": "/label/new/"},
        {"type_name": "人氣系列", "type_id": "/label/hot/"},
        {"type_name": "新作上市", "type_id": "/category/new-release/"},
        {"type_name": "有碼", "type_id": "/category/censored/"},
        {"type_name": "無碼", "type_id": "/category/uncensored/"},
        {"type_name": "國產AV", "type_id": "/category/chinese-av/"},
        {"type_name": "無碼流出", "type_id": "/category/uncensored-leaked/"},
        {"type_name": "杏吧", "type_id": "/category/sex8/"},
        {"type_name": "HongKongDoll", "type_id": "/category/hongkongdoll/"},
        {"type_name": "AI短劇", "type_id": "/category/aiav/"},
        {"type_name": "國產AV廠商", "type_id": "/label/groups/"},
    ]

    # ==================== 基础 ====================
    def getName(self):
        return "javday"

    def init(self, extend=""):
        self.extend = extend

    def isVideoFormat(self, url):
        """判断 URL 是否为可直接播放的视频格式"""
        if not url:
            return False
        url_lower = str(url).lower()
        for ext in ('.m3u8', '.mp4', '.flv', '.mkv',
                    '.avi', '.webm', '.ts', '.mov'):
            if ext in url_lower:
                return True
        return False

    def manualVideoCheck(self):
        """不需要手动 WebView 拦截"""
        return False

    def getDependence(self):
        return []

    # ==================== 请求 ====================
    def _text(self, rsp):
        """安全获取响应文本, 兼容 Response / bytes / str"""
        try:
            return rsp.text
        except Exception:
            pass
        try:
            data = rsp.content
            if isinstance(data, bytes):
                return data.decode('utf-8', errors='ignore')
            return str(data)
        except Exception:
            pass
        if isinstance(rsp, bytes):
            return rsp.decode('utf-8', errors='ignore')
        return str(rsp)

    def _fetch(self, url):
        """发起 GET 请求并返回文本"""
        try:
            rsp = self.fetch(url, headers=self.header, timeout=15, verify=False)
            return self._text(rsp)
        except Exception:
            return ""

    def _clean(self, s):
        if not s:
            return ""
        s = re.sub(r"<[^>]+>", "", s)
        s = s.replace("&nbsp;", " ").replace("&amp;", "&")
        s = s.replace("&lt;", "<").replace("&gt;", ">")
        s = s.replace("&quot;", '"').replace("&#39;", "'")
        return s.strip()

    # ==================== 首页 ====================
    def homeContent(self, filter=False):
        result = {"class": [], "filters": {}}
        for c in self.categories:
            result["class"].append({
                "type_name": c["type_name"],
                "type_id": c["type_id"],
            })
        return result

    def homeVideoContent(self):
        return self._parse_list(self._fetch(self.siteUrl + "/"))

    # ==================== 分类 ====================
    def categoryContent(self, tid, pg, filter=False, extend=""):
        try:
            p = int(pg)
        except Exception:
            p = 1

        base = tid if str(tid).startswith("/") else "/" + str(tid)
        base = base.split("?")[0]
        if p <= 1:
            url = self.siteUrl + base
        else:
            url = self.siteUrl + base.rstrip("/") + "/" + str(p) + "/"

        html = self._fetch(url)
        videos = self._parse_list(html)

        return {
            "list": videos,
            "page": str(p),
            "pagecount": 9999,
            "limit": 24,
            "total": 999999,
        }

    # ==================== 列表解析（已修复） ====================
    def _parse_list(self, html):
        videos = []
        if not html:
            return videos

        # 优先按 /videos/ 链接切块，不依赖 videoBox 这个 class
        blocks = re.findall(
            r'<a[^>]+href="(/videos/[^"]+)"[^>]*>(.*?)(?=<a[^>]+href="/videos/|</body>|$)',
            html, re.S
        )

        # 兜底：更宽松的切块
        if not blocks:
            blocks = re.findall(
                r'<a[^>]+href="(/videos/[^"]+)"[^>]*>(.*?)(?=<a[^>]+href="/videos/|</body>|$)',
                html, re.S | re.I
            )

        for href, block in blocks:
            # 标题：优先 span.title，其次 title 属性
            title = ""
            tm = re.search(r'<span\s+class="title"[^>]*>(.*?)</span>',
                           block, re.S | re.I)
            if not tm:
                tm = re.search(r'<span[^>]+class="[^"]*\btitle\b[^"]*"[^>]*>(.*?)</span>',
                               block, re.S | re.I)
            if tm:
                title = self._clean(tm.group(1))
            if not title:
                tm = re.search(r'title="([^"]*)"', block)
                if tm:
                    title = self._clean(tm.group(1))

            # 封面
            pic = self._extract_pic(block)

            # 备注
            note = ""
            nm = re.search(r'<span\s+class="videoBox-time"[^>]*>(.*?)</span>',
                           block, re.S | re.I)
            if not nm:
                nm = re.search(
                    r'<span[^>]+class="[^"]*(?:videoBox-time|duration|tag)[^"]*"[^>]*>(.*?)</span>',
                    block, re.S | re.I
                )
            if nm:
                note = self._clean(nm.group(1))

            if not href:
                continue

            videos.append({
                "vod_id": href,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": note,
            })

        # 去重
        seen = set()
        uniq = []
        for v in videos:
            if v["vod_id"] in seen:
                continue
            seen.add(v["vod_id"])
            uniq.append(v)
        return uniq

    # ==================== 图片提取（已修复） ====================
    def _extract_pic(self, block):
        pic = ""

        # 1) background-image
        m = re.search(
            r'background(?:-image)?\s*:\s*url\(\s*[\'"]?([^\'")]+)[\'"]?\s*\)',
            block, re.I
        )
        if m:
            pic = m.group(1).strip()

        # 2) 懒加载属性
        if not pic:
            m = re.search(
                r'<img[^>]+(?:data-src|data-original|data-echo|data-lazy|data-url)\s*=\s*["\']([^"\']+)["\']',
                block, re.I
            )
            if m:
                pic = m.group(1).strip()

        # 3) src
        if not pic:
            m = re.search(r'<img[^>]+src\s*=\s*["\']([^"\']+)["\']', block, re.I)
            if m:
                pic = m.group(1).strip()

        # 4) data-bg / data-background / data-cover / data-poster
        if not pic:
            m = re.search(
                r'(?:data-bg|data-background|data-cover|data-poster)\s*=\s*["\']([^"\']+)["\']',
                block, re.I
            )
            if m:
                pic = m.group(1).strip()

        # 5) 任意图片 URL 兜底
        if not pic:
            m = re.search(
                r'["\'](https?://[^"\']+?\.(?:jpg|jpeg|png|webp|gif)(?:\?[^"\']*)?)["\']',
                block, re.I
            )
            if m:
                pic = m.group(1).strip()

        if not pic:
            return ""

        pic = pic.replace("&quot;", '"').replace("&amp;", "&").strip()

        low = pic.lower()
        if low.startswith("data:") or "loading" in low \
                or "blank" in low or "placeholder" in low:
            return ""

        if pic.startswith("//"):
            pic = "https:" + pic
        elif not pic.startswith("http"):
            pic = urllib.parse.urljoin(self.siteUrl, pic)

        return pic

    # ==================== 详情 ====================
    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vid = ids[0] if isinstance(ids, (list, tuple)) else ids
        url = vid if str(vid).startswith("http") else urllib.parse.urljoin(self.siteUrl, str(vid))
        html = self._fetch(url)
        if not html:
            return {"list": []}

        # 标题
        title = ""
        t_m = re.search(r"<title>(.*?)</title>", html, re.S)
        if t_m:
            title = self._clean(t_m.group(1)).split("|")[0].strip()

        # 封面 og:image
        pic = ""
        m = re.search(
            r'<meta[^>]+(?:property|name)=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
            html, re.I
        )
        if not m:
            m = re.search(
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']og:image["\']',
                html, re.I
            )
        if m:
            pic = m.group(1).strip()
        if not pic:
            pic = self._extract_pic(html)
        if pic and not pic.startswith("http"):
            if pic.startswith("//"):
                pic = "https:" + pic
            else:
                pic = urllib.parse.urljoin(self.siteUrl, pic)

        # 播放地址
        play_url = self._extract_play(html)
        if not play_url:
            play_url = self._extract_iframe(html)

        if not play_url:
            play_from = ""
            play_url_str = ""
        else:
            play_from = "默認線路"
            play_url_str = "第1集$" + play_url

        vod = {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic,
            "type_name": "",
            "vod_year": "",
            "vod_area": "",
            "vod_remarks": "",
            "vod_actor": "",
            "vod_director": "",
            "vod_content": "",
            "vod_play_from": play_from,
            "vod_play_url": play_url_str,
        }
        return {"list": [vod]}

    def _extract_iframe(self, html):
        """详情页内嵌 iframe 播放页"""
        m = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', html, re.I)
        if not m:
            return ""
        u = m.group(1).strip()
        if u.startswith("//"):
            u = "https:" + u
        elif not u.startswith("http"):
            u = urllib.parse.urljoin(self.siteUrl, u)
        return u

    def _extract_play(self, html):
        # 1) 直接 m3u8
        m = re.search(r'(https?://[^\s"\'<>]+?\.m3u8[^\s"\'<>]*)', html)
        if m:
            return m.group(1).replace('\\/', '/')
        # 2) 直接 mp4
        m = re.search(r'(https?://[^\s"\'<>]+?\.mp4[^\s"\'<>]*)', html)
        if m:
            return m.group(1).replace('\\/', '/')
        # 3) player_aaaa
        m = re.search(r'player_aaaa\s*=\s*(\{.*?\})', html, re.S)
        if m:
            raw = m.group(1)
            data = None
            try:
                data = json.loads(raw)
            except Exception:
                try:
                    cleaned = raw.replace('&quot;', '"').replace('&#34;', '"')
                    cleaned = cleaned.replace('&#39;', "'").replace('&amp;', '&')
                    data = json.loads(cleaned)
                except Exception:
                    data = None
            if data:
                u = data.get("url", "")
                enc = data.get("encrypt", 0)
                if u and enc == 1:
                    u = urllib.parse.unquote(u)
                elif u and enc == 2:
                    try:
                        import base64
                        u = urllib.parse.unquote(
                            base64.b64decode(u).decode('utf-8', errors='ignore')
                        )
                    except Exception:
                        pass
                if u:
                    u = u.replace('\\/', '/')
                    if u.startswith("//"):
                        u = "https:" + u
                    return u
        # 4) url: "xxx.m3u8"
        m = re.search(r'url\s*[:=]\s*["\']([^"\']+?\.(?:m3u8|mp4)[^"\']*)["\']', html)
        if m:
            u = m.group(1).replace('\\/', '/')
            if u.startswith("//"):
                u = "https:" + u
            return u
        return ""

    # ==================== 播放 ====================
    def playerContent(self, flag, id, vipFlags=None):
        raw = str(id or '').strip()
        if '$' in raw:
            raw = raw.split('$', 1)[-1].strip()
        raw = raw.replace('\\/', '/').replace('\\u0026', '&').strip()

        if not raw.startswith("http"):
            raw = urllib.parse.urljoin(self.siteUrl, raw)

        # 若网页非直链, 二次解析
        if not self.isVideoFormat(raw):
            html = self._fetch(raw)
            real = self._extract_play(html)
            if not real:
                real = self._extract_iframe(html)
            if real:
                raw = real

        headers = {
            'User-Agent': self.header['User-Agent'],
            'Referer': self.header['Referer'],
        }

        if '.m3u8' in raw:
            return {
                'parse': 0,
                'playUrl': '',
                'url': raw,
                'header': headers,
                'jx': 0,
                'format': 'application/x-mpegURL',
            }

        if raw.endswith(('.mp4', '.flv', '.mkv', '.avi', '.webm', '.mov')):
            return {
                'parse': 0,
                'playUrl': '',
                'url': raw,
                'header': headers,
                'jx': 0,
            }

        return {
            'parse': 1,
            'playUrl': '',
            'url': raw,
            'header': headers,
            'jx': 0,
        }

    # ==================== 搜索 ====================
    def searchContent(self, key, quick=False, pg="1"):
        result = {"list": []}
        if not key:
            return result
        try:
            p = int(pg)
        except Exception:
            p = 1

        q = urllib.parse.quote(key)
        candidates = [
            self.siteUrl + "/search/wd/" + q + "/" + ("" if p <= 1 else str(p) + "/"),
            self.siteUrl + "/search/" + q + "/" + ("" if p <= 1 else str(p) + "/"),
            self.siteUrl + "/vodsearch/" + q + "/" + ("" if p <= 1 else str(p) + "/"),
            self.siteUrl + "/search/?wd=" + q + ("&page=" + str(p) if p > 1 else ""),
        ]
        for url in candidates:
            html = self._fetch(url)
            lst = self._parse_list(html)
            if lst:
                result["list"] = lst
                break
        return result

    # ==================== localProxy ====================
    def localProxy(self, param):
        """按 FongMi 规范返回四元组 [code, MIME, bytes, headers]"""
        url = param.get("url", "") if isinstance(param, dict) else ""
        if not url:
            return [404, "text/plain", "", {}]
        try:
            rsp = self.fetch(url, headers=self.header, timeout=20, verify=False)
            body = rsp.content if hasattr(rsp, 'content') else rsp
            return [200, "application/octet-stream", body, {}]
        except Exception:
            return [500, "text/plain", "", {}]