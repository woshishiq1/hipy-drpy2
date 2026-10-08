#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
野马视频 / yemahk.xyz - PyramidStore 插件 (修复版 v3.3)
修复内容:
1. 修复正则表达式引号嵌套导致的 SyntaxError
2. 修复列表页标题为空（优先匹配 data-lazy-src 而非 src）
3. 修复列表页时间备注提取（从 <time> 标签提取 base64 编码的日期）
4. [v3.3] 域名失效修复：旧域名 yemahk.xyz 已变为跳转页，
   新增自动检测跳转页面并切换到可用备用域名的逻辑
   备用域名：yemahp / yemahq / yemahr / yemahs / yemaht (.xyz)
"""

import requests
import re
import base64
import json
import sys
import os
import time
import urllib3
from urllib.parse import quote, urljoin, unquote

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

sys.path.append("../../")
try:
    from base.spider import Spider
except ImportError:
    class Spider:
        def init(self, extend=""):
            pass


_CACHE_FILE = "野马视频site.txt"

# 旧域名已失效（变为跳转页），备用域名列表
_BACKUP_DOMAINS = [
    "https://www.yemahp.xyz",
    "https://www.yemahq.xyz",
    "https://www.yemahr.xyz",
    "https://www.yemahs.xyz",
    "https://www.yemaht.xyz",
]
# 旧域名，访问时返回跳转页面而非真实内容
_LEGACY_DOMAIN = "https://www.yemahk.xyz"


def decode_title(text):
    if not text or not isinstance(text, str):
        return ""
    text = text.strip()
    if not text:
        return ""
    try:
        d1 = base64.b64decode(text).decode("utf-8")
        d2 = base64.b64decode(d1).decode("utf-8")
        return d2
    except Exception:
        try:
            return base64.b64decode(text).decode("utf-8")
        except Exception:
            return text


def decrypt_magnet(bin_str):
    if not bin_str or len(bin_str) < 8:
        return ""
    result = ""
    for i in range(0, len(bin_str) - 7, 8):
        chunk = bin_str[i:i + 8]
        try:
            val = int(chunk, 2) - 10
            if 0 <= val <= 255:
                result += chr(val)
        except Exception:
            pass
    return result


class Spider(Spider):
    def __init__(self):
        self.siteUrl = "https://www.yemahp.xyz"
        self.userAgent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
        self.timeout = 15
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.userAgent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        })
        self._domain_resolved = False
        self._ensure_verified_cookie()

    def _ensure_verified_cookie(self):
        try:
            from urllib.parse import urlparse
            domain = urlparse(self.siteUrl).hostname
            self.session.cookies.set("verified", "true", domain=domain, path="/")
        except Exception as e:
            print(f"[WARN] 设置 cookie 失败: {e}")

    def _get_headers(self, referer=None):
        return {
            "User-Agent": self.userAgent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": referer or self.siteUrl,
        }

    def _is_redirect_page(self, text, url=None):
        """检测是否为旧域名的跳转页面（非真实内容）"""
        if not text:
            return False
        # JSON/API 响应不检测
        if url and any(api in url for api in ["get_m3u8.php", "jiasu_m3u8.php", "fontsearch.php"]):
            return False
        stripped = text.lstrip()
        if stripped.startswith("{") or stripped.startswith("["):
            return False
        # 跳转页特征：JS 中有 baseUrls 数组或标题含跳转提示
        if "baseUrls" in text or "即将跳转" in text or "选择最优线路" in text:
            return True
        # 内容太短且没有实际视频结构
        if len(text) < 8000 and "video.php" not in text and "list.php" not in text and "cili.php" not in text:
            return True
        return False

    def _fetch_with_fallback(self, url, headers=None, retries=2):
        if headers is None:
            headers = self._get_headers()
        for attempt in range(retries):
            try:
                resp = self.session.get(url, headers=headers, timeout=self.timeout, verify=False)
                resp.raise_for_status()
                if "确认进入" in resp.text and "verified" in resp.text and attempt < retries - 1:
                    print(f"[WARN] 遇到验证页面，尝试备用请求头 (attempt {attempt + 1})")
                    headers["Accept"] = "*/*"
                    headers["Cache-Control"] = "no-cache"
                    headers["Pragma"] = "no-cache"
                    time.sleep(0.5)
                    continue
                # v3.3: 检测旧域名跳转页面，自动切换到备用域名
                if self._is_redirect_page(resp.text, url):
                    print(f"[WARN] 检测到跳转页面，正在切换备用域名...")
                    new_domain = self._find_working_domain()
                    if new_domain and new_domain != self.siteUrl:
                        self.siteUrl = new_domain
                        self._ensure_verified_cookie()
                        self._save_cache()
                        # 用新域名重新请求
                        new_url = url.replace(url.split("//")[0] + "//" + url.split("//")[1].split("/")[0], self.siteUrl)
                        resp = self.session.get(new_url, headers=self._get_headers(), timeout=self.timeout, verify=False)
                        resp.raise_for_status()
                        print(f"[INFO] 已切换到: {self.siteUrl}")
                return resp
            except requests.exceptions.RequestException as e:
                if attempt < retries - 1:
                    print(f"[WARN] 请求失败，重试 {attempt + 1}: {url}")
                    time.sleep(1)
                else:
                    print(f"[ERROR] fetch {url} failed: {e}")
                    return None
        return None

    def _find_working_domain(self):
        """依次探测备用域名，返回第一个有真实内容的域名"""
        for domain in _BACKUP_DOMAINS:
            try:
                resp = self.session.get(domain, headers=self._get_headers(), timeout=8, verify=False)
                if resp.status_code == 200 and not self._is_redirect_page(resp.text, domain):
                    if "video.php" in resp.text or "list.php" in resp.text:
                        print(f"[INFO] 找到可用域名: {domain}")
                        return domain
            except Exception:
                continue
        # 所有备用域名都失败，返回第一个作为兜底
        print("[WARN] 所有备用域名探测失败，使用默认域名")
        return _BACKUP_DOMAINS[0]

    def init(self, extend=""):
        if extend and isinstance(extend, str):
            if extend.startswith("http"):
                self.siteUrl = extend.rstrip("/")
                self._ensure_verified_cookie()
        self._resolve_site_url()

    def _resolve_site_url(self):
        cached_url = ""
        try:
            if os.path.exists(_CACHE_FILE):
                with open(_CACHE_FILE, "r", encoding="utf-8") as f:
                    cached_url = f.read().strip()
        except Exception:
            pass

        # v3.3: 如果缓存的是旧域名，清除并重新探测
        if cached_url and cached_url == _LEGACY_DOMAIN:
            print("[WARN] 缓存域名为旧域名，清除缓存重新探测")
            cached_url = ""

        if cached_url:
            self.siteUrl = cached_url
            self._ensure_verified_cookie()

        # v3.3: 探测当前域名是否可用（非跳转页）
        try:
            resp = self._fetch_with_fallback(self.siteUrl)
            if resp:
                if self._is_redirect_page(resp.text, self.siteUrl):
                    # 当前域名是跳转页，自动查找可用备用域名
                    print("[WARN] 当前域名为跳转页，自动探测备用域名...")
                    new_domain = self._find_working_domain()
                    if new_domain:
                        self.siteUrl = new_domain
                        self._ensure_verified_cookie()
                        self._save_cache()
                        print(f"[INFO] 已切换到: {self.siteUrl}")
                elif "确认进入" in resp.text:
                    print("[WARN] 验证页面未绕过，尝试刷新 cookie")
                    self._ensure_verified_cookie()
                    resp2 = self._fetch_with_fallback(self.siteUrl)
                    if resp2 and "确认进入" not in resp2.text and not self._is_redirect_page(resp2.text, self.siteUrl):
                        print(f"[INFO] 网址验证通过: {self.siteUrl}")
                        self._save_cache()
                    else:
                        print(f"[WARN] 无法绕过验证页面，请检查域名")
                else:
                    print(f"[INFO] 网址验证通过: {self.siteUrl}")
                    self._save_cache()
        except Exception as e:
            print(f"[WARN] 网址验证异常: {e}")
            # 异常时尝试备用域名
            new_domain = self._find_working_domain()
            if new_domain:
                self.siteUrl = new_domain
                self._ensure_verified_cookie()
                self._save_cache()
                print(f"[INFO] 异常恢复，已切换到: {self.siteUrl}")

    def _save_cache(self):
        try:
            with open(_CACHE_FILE, "w", encoding="utf-8") as f:
                f.write(self.siteUrl)
        except Exception as e:
            print(f"[WARN] 缓存写入失败: {e}")

    def getName(self):
        return "野马视频"

    def fetch(self, url, headers=None):
        return self._fetch_with_fallback(url, headers)

    def _get_m3u8_api(self, classid, video_ids):
        if not video_ids:
            return {}
        ids_param = ",".join(video_ids)
        api_url = f"{self.siteUrl}/get_m3u8.php?classid={classid}"
        post_headers = self._get_headers()
        post_headers["Content-Type"] = "application/x-www-form-urlencoded"
        post_headers["X-Requested-With"] = "XMLHttpRequest"
        try:
            resp = self.session.post(api_url, headers=post_headers, data=f"ids={ids_param}", timeout=10, verify=False)
            if resp.status_code == 200:
                data = resp.json()
                if "error" not in data:
                    return data
        except Exception as e:
            print(f"[WARN] get_m3u8 API失败: {e}")
        return {}

    def _get_accelerated_url(self, m3u8_url):
        if not m3u8_url:
            return ""
        try:
            api_url = f"{self.siteUrl}/jiasu_m3u8.php?m3u8={quote(m3u8_url)}&cdn=auto&t={int(time.time() * 1000)}"
            resp = self.fetch(api_url)
            if resp:
                data = resp.json()
                play_url = data.get("play_url", m3u8_url)
                play_url = play_url.replace("https://auto/https/", "https://")
                play_url = play_url.replace("https://auto/http/", "http://")
                play_url = play_url.replace("http://auto/https/", "https://")
                play_url = play_url.replace("http://auto/http/", "http://")
                return play_url
        except Exception as e:
            print(f"[ERROR] 加速接口失败: {e}")
        return m3u8_url

    def _extract_videos_from_list(self, html, classid):
        videos = []
        seen_ids = set()
        # 修复：优先匹配 data-lazy-src，避免匹配到 src="/gifjiazai.gif"
        img_pattern = (
            r'<a[^>]*href=[\'"]([^\'"]*video\.php\?classid=(\d+)&id=(\d+))[\'"][^>]*>'
            + r'.*?'
            + r'<img[^>]*data-lazy-src=[\'"]([^\'"]+)[\'"][^>]*alt=[\'"]([^\'"]*)[\'"][^>]*>'
            + r'.*?</a>'
        )
        img_items = re.findall(img_pattern, html, re.DOTALL | re.IGNORECASE)
        for item in img_items:
            href, cid, vid, img, alt = item
            vid_str = f"{cid}-{vid}"
            if vid_str in seen_ids:
                continue
            seen_ids.add(vid_str)
            img_url = img if img.startswith("http") else urljoin(self.siteUrl, img)
            title = decode_title(alt.strip()) if alt else ""
            # 修复：从 <time> 标签提取 base64 编码的日期
            time_code = ""
            idx = html.find(href)
            if idx > 0:
                nearby = html[idx:idx + 500]
                time_match = re.search(r'<time>([A-Za-z0-9+/=]{10,30})</time>', nearby)
                if time_match:
                    time_code = decode_title(time_match.group(1))
            videos.append({
                "vod_id": vid_str,
                "vod_name": title,
                "vod_pic": img_url,
                "vod_remarks": time_code,
            })
        # 备选：从 h2 标签提取标题（如果img模式没匹配到）
        h2_pattern = r'<h2><a[^>]*href=[\'"]([^\'"]*video\.php\?classid=(\d+)&id=(\d+))[\'"][^>]*>([^<]+)</a></h2>'
        h2_items = re.findall(h2_pattern, html, re.IGNORECASE)
        for item in h2_items:
            href, cid, vid, text = item
            vid_str = f"{cid}-{vid}"
            text = text.strip()
            if not text or vid_str in seen_ids:
                continue
            seen_ids.add(vid_str)
            # 尝试找对应图片
            pic = ""
            idx = html.find(href)
            if idx > 0:
                nearby = html[idx:idx + 400]
                img_match = re.search(r'data-lazy-src=[\'"]([^\'"]+)[\'"]', nearby)
                if img_match:
                    pic = img_match.group(1)
                    if not pic.startswith("http"):
                        pic = urljoin(self.siteUrl, pic)
            # 尝试找对应时间
            time_code = ""
            if idx > 0:
                nearby = html[idx:idx + 500]
                time_match = re.search(r'<time>([A-Za-z0-9+/=]{10,30})</time>', nearby)
                if time_match:
                    time_code = decode_title(time_match.group(1))
            videos.append({
                "vod_id": vid_str,
                "vod_name": decode_title(text),
                "vod_pic": pic,
                "vod_remarks": time_code,
            })
        return videos

    def _extract_cili_videos(self, html):
        videos = []
        seen_ids = set()
        # 修复：同样优先匹配 data-lazy-src
        pattern = (
            r'<a[^>]*href=[\'"]([^\'"]*cili\.php\?classid=41&id=(\d+))[\'"][^>]*>'
            + r'.*?'
            + r'<img[^>]*data-lazy-src=[\'"]([^\'"]+)[\'"][^>]*alt=[\'"]([^\'"]*)[\'"][^>]*>'
            + r'.*?</a>'
        )
        items = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
        for item in items:
            href, vid, img, alt = item
            if vid in seen_ids:
                continue
            seen_ids.add(vid)
            img_url = img if img.startswith("http") else urljoin(self.siteUrl, img)
            title = decode_title(alt.strip()) if alt else ""
            videos.append({
                "vod_id": f"41-{vid}",
                "vod_name": title,
                "vod_pic": img_url,
                "vod_remarks": "磁力",
            })
        # 备选：从 h2 提取
        h2_pattern = r'<h2><a[^>]*href=[\'"]([^\'"]*cili\.php\?classid=41&id=(\d+))[\'"][^>]*>([^<]+)</a></h2>'
        h2_items = re.findall(h2_pattern, html, re.IGNORECASE)
        for item in h2_items:
            href, vid, text = item
            if vid in seen_ids:
                continue
            seen_ids.add(vid)
            text = text.strip()
            pic = ""
            idx = html.find(href)
            if idx > 0:
                nearby = html[idx:idx + 400]
                img_match = re.search(r'data-lazy-src=[\'"]([^\'"]+)[\'"]', nearby)
                if img_match:
                    pic = img_match.group(1)
                    if not pic.startswith("http"):
                        pic = urljoin(self.siteUrl, pic)
            if text:
                videos.append({
                    "vod_id": f"41-{vid}",
                    "vod_name": decode_title(text),
                    "vod_pic": pic,
                    "vod_remarks": "磁力",
                })
        return videos

    def _extract_pagecount(self, html):
        page_matches = re.findall(r"[?&]page=(\d+)", html)
        if page_matches:
            return max(int(p) for p in page_matches)
        text_match = re.search(r"共\s*(\d+)\s*页", html)
        if text_match:
            return int(text_match.group(1))
        return 1

    def _get_video_m3u8(self, classid, vid):
        m3u8_map = self._get_m3u8_api(classid, [vid])
        if vid in m3u8_map and m3u8_map[vid]:
            url = m3u8_map[vid]
            if url.startswith("http"):
                return self._get_accelerated_url(url)
        url = f"{self.siteUrl}/video.php?classid={classid}&id={vid}"
        resp = self.fetch(url)
        if resp:
            m3u8_matches = re.findall(r'(https?://[^\s\'"]+?\.m3u8[^\s\'"]*)', resp.text)
            if m3u8_matches:
                return self._get_accelerated_url(m3u8_matches[0])
        return ""

    def _get_cili_magnets(self, vid):
        url = f"{self.siteUrl}/cili.php?classid=41&id={vid}"
        resp = self.fetch(url)
        if not resp:
            return []
        html = resp.text
        # 修复：使用原始字符串避免引号冲突
        bin_matches = re.findall(r'reurl\([\'"]([01]{100,})[\'"]', html)
        magnets = []
        for bin_str in bin_matches:
            hash_val = decrypt_magnet(bin_str)
            if len(hash_val) == 40 and all(c in "0123456789abcdefABCDEF" for c in hash_val):
                magnets.append(f"magnet:?xt=urn:btih:{hash_val}")
        return magnets

    def _extract_pic(self, html):
        img_matches = re.findall(r'<img[^>]*src=[\'"]([^\'"]+)[\'"][^>]*>', html)
        for img in img_matches:
            if "/img/" in img and not any(x in img for x in ["skin", "sucai", "gifjiazai", "yema"]):
                return img if img.startswith("http") else urljoin(self.siteUrl, img)
        poster_match = re.search(r'<video[^>]*poster=[\'"]([^\'"]+)[\'"]', html, re.IGNORECASE)
        if poster_match:
            poster = poster_match.group(1)
            if "/img/" in poster:
                return poster if poster.startswith("http") else urljoin(self.siteUrl, poster)
        lazy_matches = re.findall(r'data-lazy-src=[\'"]([^\'"]+)[\'"]', html)
        for img in lazy_matches:
            if "/img/" in img and not any(x in img for x in ["skin", "sucai", "gifjiazai", "yema"]):
                return img if img.startswith("http") else urljoin(self.siteUrl, img)
        return ""

    def homeContent(self, filter):
        result = {"class": [], "filters": {}}
        classes = [
            {"type_id": "39", "type_name": "番号视频"},
            {"type_id": "40", "type_name": "国产视频"},
            {"type_id": "41", "type_name": "有码番号"},
        ]
        filters_map = {
            "39": [
                {
                    "key": "fenlei",
                    "name": "子分类",
                    "value": [
                        {"n": "全部", "v": ""},
                        {"n": "中文字幕", "v": "中文字幕"},
                        {"n": "巨乳美乳", "v": "巨乳美乳"},
                        {"n": "强姦乱伦", "v": "强姦乱伦"},
                        {"n": "制服丝袜", "v": "制服丝袜"},
                        {"n": "萝莉少女", "v": "萝莉少女"},
                        {"n": "精品素人", "v": "精品素人"},
                        {"n": "亚洲有码", "v": "亚洲有码"},
                        {"n": "亚洲无码", "v": "亚洲无码"},
                        {"n": "女同性恋", "v": "女同性恋"},
                    ]
                }
            ],
            "40": [
                {
                    "key": "fenlei",
                    "name": "子分类",
                    "value": [
                        {"n": "全部", "v": ""},
                        {"n": "国产自拍", "v": "国产自拍"},
                        {"n": "国产传媒", "v": "国产传媒"},
                        {"n": "AV解说", "v": "AV解说"},
                        {"n": "国产乱伦", "v": "国产乱伦"},
                        {"n": "网红主播", "v": "网红主播"},
                        {"n": "探花约炮", "v": "探花约炮"},
                        {"n": "ai换脸", "v": "ai换脸"},
                        {"n": "伦理三级", "v": "伦理三级"},
                        {"n": "欧美精品", "v": "欧美精品"},
                        {"n": "成人动漫", "v": "成人动漫"},
                    ]
                }
            ],
            "41": []
        }
        result["class"] = classes
        if filter:
            result["filters"] = filters_map
        return result

    def homeVideoContent(self):
        result = {"list": []}
        all_videos = []
        for cid in ["39", "40"]:
            resp = self.fetch(f"{self.siteUrl}/list.php?classid={cid}")
            if resp:
                videos = self._extract_videos_from_list(resp.text, cid)
                all_videos.extend(videos[:6])
        seen = set()
        unique = []
        for v in all_videos:
            if v["vod_id"] not in seen:
                seen.add(v["vod_id"])
                unique.append(v)
        result["list"] = unique[:12]
        return result

    def categoryContent(self, tid, pg, filter, extend):
        result = {"list": [], "page": pg, "pagecount": 0, "limit": 20, "total": 0}
        if tid == "41":
            url = f"{self.siteUrl}/list.php?classid=41&page={pg}"
            resp = self.fetch(url)
            if resp:
                videos = self._extract_cili_videos(resp.text)
                pagecount = self._extract_pagecount(resp.text)
                result.update({
                    "list": videos,
                    "page": pg,
                    "pagecount": pagecount,
                    "limit": 20,
                    "total": pagecount * 20,
                })
            return result
        url = f"{self.siteUrl}/list.php?classid={tid}&page={pg}"
        if extend and isinstance(extend, dict):
            fenlei = extend.get("fenlei", "")
            if fenlei:
                url += f"&fenlei={quote(fenlei)}"
        resp = self.fetch(url)
        if not resp:
            return result
        videos = self._extract_videos_from_list(resp.text, tid)
        pagecount = self._extract_pagecount(resp.text)
        result.update({
            "list": videos,
            "page": pg,
            "pagecount": pagecount,
            "limit": 20,
            "total": pagecount * 20,
        })
        return result

    def detailContent(self, ids):
        result = {"list": []}
        if not ids:
            return result
        video_id = ids[0] if isinstance(ids, list) else ids
        if "-" in video_id:
            classid, vid = video_id.split("-", 1)
        else:
            classid, vid = "39", video_id
        if classid == "41":
            url = f"{self.siteUrl}/cili.php?classid=41&id={vid}"
            resp = self.fetch(url)
            if not resp:
                return result
            html = resp.text
            title = ""
            title_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
            if title_match:
                parts = title_match.group(1).split(" - ")
                if parts:
                    title = decode_title(parts[0])
            pic = self._extract_pic(html)
            magnets = self._get_cili_magnets(vid)
            play_url = "#".join(f"磁力{i+1}${m}" for i, m in enumerate(magnets)) if magnets else ""
            vod = {
                "vod_id": video_id,
                "vod_name": title or f"磁力{vid}",
                "vod_pic": pic,
                "vod_remarks": f"{len(magnets)}个磁力" if magnets else "无磁力",
                "vod_year": "",
                "vod_area": "",
                "vod_actor": "",
                "vod_director": "",
                "vod_content": "",
                "vod_play_from": "磁力",
                "vod_play_url": play_url,
            }
            result["list"] = [vod]
            return result
        url = f"{self.siteUrl}/video.php?classid={classid}&id={vid}"
        resp = self.fetch(url)
        if not resp:
            return result
        html = resp.text
        title = ""
        title_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
        if title_match:
            parts = title_match.group(1).split(" - ")
            if parts:
                title = decode_title(parts[0])
        pic = self._extract_pic(html)
        m3u8 = self._get_video_m3u8(classid, vid)
        vod = {
            "vod_id": video_id,
            "vod_name": title or f"视频{vid}",
            "vod_pic": pic,
            "vod_remarks": "",
            "vod_year": "",
            "vod_area": "",
            "vod_actor": "",
            "vod_director": "",
            "vod_content": "",
            "vod_play_from": "默认",
            "vod_play_url": f"播放${m3u8}" if m3u8 else "",
        }
        result["list"] = [vod]
        return result

    def searchContent(self, key, quick, pg=1):
        result = {"list": []}
        url = f"{self.siteUrl}/fontsearch.php?query={quote(key)}&classid=39&orderby=newstime"
        if pg > 1:
            url += f"&page={pg}"
        resp = self.fetch(url)
        if not resp:
            return result
        videos = self._extract_videos_from_list(resp.text, "39")
        result["list"] = videos
        return result

    def searchContentPage(self, key, quick, pg=1):
        return self.searchContent(key, quick, pg)

    def playerContent(self, flag, id, vipFlags):
        result = {}
        if not id:
            return result
        headers = {
            "User-Agent": self.userAgent,
            "Referer": self.siteUrl,
        }
        if self.isVideoFormat(id):
            result["parse"] = 0
            result["url"] = id
            result["header"] = headers
        else:
            play_url = id if id.startswith("http") else urljoin(self.siteUrl, id)
            result["parse"] = 0
            result["url"] = play_url
            result["header"] = headers
        return result

    def isVideoFormat(self, url):
        if not url or not isinstance(url, str):
            return False
        if not url.startswith("http"):
            return False
        fmt = [".mp4", ".m3u8", ".ts", ".mkv", ".avi", ".webm", ".flv"]
        for f in fmt:
            if url.lower().find(f) > -1:
                return True
        return False

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        action = param.get("action")
        if action == "proxy":
            url = param.get("url")
            if not url:
                return None
            headers = {
                "User-Agent": self.userAgent,
                "Referer": self.siteUrl,
            }
            try:
                if param.get("type") == "cover":
                    r = requests.get(url, headers=headers, timeout=10, verify=False)
                    if r.status_code == 200 and r.content:
                        return [200, r.headers.get("Content-Type", "image/jpeg"), r.content]
                    return [404, "text/plain", "cover not found"]
                elif param.get("type") == "m3u8":
                    content = requests.get(url, headers=headers, timeout=10, verify=False).text
                    return [200, "application/vnd.apple.mpegurl", content]
                elif param.get("type") == "media":
                    r = requests.get(url, headers=headers, stream=True, timeout=10, verify=False)
                    return [206, "application/octet-stream", r.content]
                else:
                    content = requests.get(url, headers=headers, timeout=10, verify=False).text
                    return [200, "text/plain", content]
            except Exception as e:
                print(f"[ERROR] localProxy failed: {e}")
                return [500, "text/plain", str(e)]
        return None


def test():
    print("=" * 70)
    print("野马视频 TVBox 爬虫 - 联网测试")
    print("=" * 70)
    spider = Spider()
    spider.init()

    print("\n--- [1/9] homeContent ---")
    home = spider.homeContent(filter=True)
    print(f"分类: {len(home.get('class', []))} 个")
    for c in home.get("class", []):
        print(f"  {c['type_id']}: {c['type_name']}")

    print("\n--- [2/9] homeVideoContent ---")
    hv = spider.homeVideoContent()
    print(f"首页视频: {len(hv.get('list', []))} 个")
    for v in hv.get("list", [])[:3]:
        print(f"  [{v['vod_id']}] {v['vod_name'][:40]} | 备注:{v['vod_remarks']}")

    print("\n--- [3/9] categoryContent 39 ---")
    cat39 = spider.categoryContent(tid="39", pg=1, filter=True, extend={})
    print(f"番号视频: {len(cat39.get('list', []))} 个, 总页: {cat39.get('pagecount')}")
    for v in cat39.get("list", [])[:3]:
        print(f"  [{v['vod_id']}] {v['vod_name'][:40]} | 备注:{v['vod_remarks']}")

    print("\n--- [4/9] categoryContent 40 ---")
    cat40 = spider.categoryContent(tid="40", pg=1, filter=True, extend={})
    print(f"国产视频: {len(cat40.get('list', []))} 个, 总页: {cat40.get('pagecount')}")
    for v in cat40.get("list", [])[:3]:
        print(f"  [{v['vod_id']}] {v['vod_name'][:40]} | 备注:{v['vod_remarks']}")

    print("\n--- [5/9] categoryContent 41 ---")
    cat41 = spider.categoryContent(tid="41", pg=1, filter=True, extend={})
    print(f"磁力视频: {len(cat41.get('list', []))} 个, 总页: {cat41.get('pagecount')}")
    for v in cat41.get("list", [])[:3]:
        print(f"  [{v['vod_id']}] {v['vod_name'][:40]} | 备注:{v['vod_remarks']}")

    print("\n--- [6/9] detailContent + 播放测试 ---")
    for tid, name in [("39", "番号"), ("40", "国产"), ("41", "磁力")]:
        cat = spider.categoryContent(tid=tid, pg=1, filter=True, extend={})
        if cat.get("list"):
            vid = cat["list"][0]["vod_id"]
            d = spider.detailContent([vid])
            if d.get("list"):
                v = d["list"][0]
                print(f"  [{name}] {v['vod_name'][:40]}...")
                if v.get("vod_play_url"):
                    if tid == "41":
                        print(f"    磁力: {v['vod_play_url'][:80]}...")
                    else:
                        play_url = v["vod_play_url"].split("$")[1] if "$" in v["vod_play_url"] else v["vod_play_url"]
                        pc = spider.playerContent("默认", play_url, "")
                        print(f"    播放: {pc.get('url', '')[:80]}...")

    print("\n--- [7/9] searchContent ---")
    s = spider.searchContent("护士", quick=False, pg=1)
    print(f"搜索: {len(s.get('list', []))} 个结果")
    for v in s.get("list", [])[:3]:
        print(f"  [{v['vod_id']}] {v['vod_name'][:40]}")

    print("\n" + "=" * 70)
    print("测试完成")
    print("=" * 70)


if __name__ == "__main__":
    test()
