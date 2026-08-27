#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
国色天香 / 我草视频 - PyramidStore 插件 (修复版 v5.0)
目标: 动态域名自适应
修复: 2026-08-16 更新域名至 wckz813.vip，修复881响应解析，修复data.json解析
"""

import requests
import json
import html as html_module
import re
import sys
import os
from urllib.parse import quote, urljoin, unquote

# 兼容本地调试与 PyramidStore 环境
sys.path.append('../../')
try:
    from base.spider import Spider
except ImportError:
    class Spider:
        def init(self, extend=""):
            pass


# ========== 解密映射表 (来自 public.min.js) ==========
_DECRYPT_MAP = {
    'e':'P','w':'D','T':'y','+':'J','l':'!','t':'L','E':'E','@':'2','d':'a','b':'%',
    'q':'l','X':'v','~':'R','5':'r','&':'X','C':'j',']':'F','a':')','^':'m',',':'~',
    '}':'1','x':'C','c':'(','G':'@','h':'h','.':'*','L':'s','=':',','p':'g','I':'Q',
    '1':'7','_':'u','K':'6','F':'t','2':'n','8':'=','k':'G','Z':']',')':'b','P':'}',
    'B':'U','S':'k','6':'i','g':':','N':'N','i':'S','%':'+','-':'Y','?':'|','4':'z',
    '*':'-','3':'^','[':'{','(':'c','u':'B','y':'M','U':'Z','H':'[','z':'K','9':'H',
    '7':'f','R':'x','v':'&','!':';','M':'_','Q':'9','Y':'e','o':'4','r':'A','m':'.',
    'O':'o','V':'W','J':'p','f':'d',':':'q','{':'8','W':'I','j':'?','n':'5','s':'3',
    '|':'T','A':'V','D':'w',';':'O'
}

# 默认基础域名(当缓存和跳转都失败时的最后保底)
_BACKUP_BASE_URLS = [
    "https://VwLYxvSnvzcai.wckz813.vip:8801",
    "https://2tcW6DEkfnvzcai.wckz813.vip:8801",
    "https://QXxadAnnvzcai.wckz813.vip:8801",
    "https://iin.wckk799.vip:8801",
]

# 缓存文件名
_CACHE_FILE = "国色天香site.txt"


def decrypt_text(text: str) -> str:
    if not text or not isinstance(text, str):
        return ""
    result = "".join(_DECRYPT_MAP.get(ch, ch) for ch in text)
    return html_module.unescape(result)


def _extract_redirect_url_from_881(html_text: str) -> str:
    if not html_text:
        return ""

    # 格式1: document.write(decodeURIComponent("..."))
    m = re.search(r'document\.write\(decodeURIComponent\("([^"]+)"\)\)', html_text)
    if m:
        decoded = html_module.unescape(m.group(1))
        decoded2 = unquote(decoded)
        m2 = re.search(r'var\s+url\s*=\s*["\x27](https?://[^"\x27]+)["\x27]', decoded2)
        if m2:
            redirect = m2.group(1)
            if redirect.endswith('/index.htm'):
                redirect = redirect[:-len('/index.htm')]
            return redirect
        m3 = re.search(r'window\.location\.replace\(["\x27](https?://[^"\x27]+)["\x27]\)', decoded2)
        if m3:
            redirect = m3.group(1)
            if redirect.endswith('/index.htm'):
                redirect = redirect[:-len('/index.htm')]
            return redirect

    # 格式2: 直接的 var url
    m = re.search(r'var\s+url\s*=\s*["\x27](https?://[^"\x27]+)["\x27]', html_text)
    if m:
        redirect = m.group(1)
        if redirect.endswith('/index.htm'):
            redirect = redirect[:-len('/index.htm')]
        return redirect

    # 格式3: window.location.replace
    m2 = re.search(r'window\.location\.replace\(["\x27](https?://[^"\x27]+)["\x27]\)', html_text)
    if m2:
        redirect = m2.group(1)
        if redirect.endswith('/index.htm'):
            redirect = redirect[:-len('/index.htm')]
        return redirect

    # 格式4: location.href
    m3 = re.search(r'location\.href\s*=\s*["\x27](https?://[^"\x27]+)["\x27]', html_text)
    if m3:
        redirect = m3.group(1)
        if redirect.endswith('/index.htm'):
            redirect = redirect[:-len('/index.htm')]
        return redirect

    return ""


class Spider(Spider):

    def __init__(self):
        self.siteUrl = _BACKUP_BASE_URLS[0]
        self.userAgent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
        self.timeout = 15
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.userAgent,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
        })

        # 动态域名信息
        self.css_domain = ""
        self.pic_domain = ""
        self.novel_domain = ""
        self.csstime = ""
        self.channel_id = ""

    # ==================== 动态网址解析（核心新增）====================

    def _resolve_site_url(self, default_url: str = None, max_redirects: int = 3) -> str:
        default_url = default_url or getattr(self, 'siteUrl', _BACKUP_BASE_URLS[0])

        # ---------- 1. 读取缓存 ----------
        cached_url = ""
        try:
            if os.path.exists(_CACHE_FILE):
                with open(_CACHE_FILE, "r", encoding="utf-8") as f:
                    cached_url = f.read().strip()
                if cached_url:
                    print(f"[INFO] 从缓存读取网址: {cached_url}")
        except Exception as e:
            print(f"[WARN] 读取缓存文件失败: {e}")
            cached_url = ""

        # ---------- 2. 内部验证函数 ----------
        def _check_url(url: str) -> tuple:
            if not url:
                return False, url, 0
            try:
                # 先尝试 HEAD，减少流量
                resp = self.session.head(url, timeout=10, allow_redirects=False)

                if resp.status_code == 200:
                    return True, url, 200

                if resp.status_code in (301, 302, 307, 308):
                    location = resp.headers.get("Location", "")
                    if location:
                        new_url = urljoin(url, location)
                        return False, new_url, resp.status_code
                    return False, url, resp.status_code

                if resp.status_code == 881:
                    resp_get = self.session.get(url, timeout=10, allow_redirects=False)
                    redirect_url = _extract_redirect_url_from_881(resp_get.text)
                    if redirect_url:
                        return False, redirect_url, 881
                    return False, url, 881

                # 其他状态码，尝试 GET 确认
                resp_get = self.session.get(url, timeout=10, allow_redirects=False)
                if resp_get.status_code == 200:
                    return True, url, 200
                if resp_get.status_code in (301, 302, 307, 308):
                    location = resp_get.headers.get("Location", "")
                    if location:
                        new_url = urljoin(url, location)
                        return False, new_url, resp_get.status_code
                if resp_get.status_code == 881:
                    redirect_url = _extract_redirect_url_from_881(resp_get.text)
                    if redirect_url:
                        return False, redirect_url, 881

                return True, url, resp_get.status_code

            except Exception as e:
                print(f"[WARN] 验证 {url} 失败: {e}")
                return False, url, 0

        # ---------- 3. 验证缓存 ----------
        target_url = default_url
        if cached_url:
            is_valid, checked_url, status = _check_url(cached_url)
            if is_valid:
                print(f"[INFO] 缓存网址有效，直接使用: {cached_url}")
                self.siteUrl = cached_url
                return cached_url
            elif checked_url != cached_url:
                print(f"[INFO] 缓存网址需要跳转({status}): {cached_url} -> {checked_url}")
                target_url = checked_url
            else:
                print(f"[INFO] 缓存网址失效，使用默认: {default_url}")
                target_url = default_url

        # ---------- 4. 追踪跳转 ----------
        final_url = target_url
        visited = set()

        for i in range(max_redirects):
            if final_url in visited:
                print(f"[WARN] 检测到跳转循环，终止: {final_url}")
                break
            visited.add(final_url)

            is_valid, checked_url, status = _check_url(final_url)

            if is_valid:
                try:
                    test_resp = self.session.get(f"{final_url}/data.json", timeout=10, allow_redirects=False)
                    if test_resp.status_code == 200 or test_resp.status_code == 881:
                        print(f"[INFO] 网址验证通过(HTTP {test_resp.status_code}): {final_url}")
                        break
                except Exception:
                    pass
                break

            if checked_url != final_url:
                print(f"[INFO] 第{i+1}次跳转(HTTP {status}): {final_url} -> {checked_url}")
                final_url = checked_url
            else:
                break

        # 清理 URL
        if final_url.endswith('/index.htm'):
            final_url = final_url[:-len('/index.htm')]
        final_url = final_url.rstrip('/')

        # ---------- 5. 更新缓存 ----------
        if final_url != cached_url:
            try:
                with open(_CACHE_FILE, "w", encoding="utf-8") as f:
                    f.write(final_url)
                print(f"[INFO] 网址已缓存到 {_CACHE_FILE}: {final_url}")
            except Exception as e:
                print(f"[WARN] 无法写入缓存文件 {_CACHE_FILE}: {e}")

        # ---------- 6. 更新实例变量 ----------
        self.siteUrl = final_url
        print(f"[INFO] 最终使用网址: {final_url}")
        return final_url

    # ==================== 原有接口 ====================

    def init(self, extend=""):
        """插件初始化(框架回调)"""
        global _BACKUP_BASE_URLS

        if extend and isinstance(extend, str):
            custom_urls = [u.strip() for u in extend.split(",") if u.strip().startswith("http")]
            if custom_urls:
                _BACKUP_BASE_URLS = custom_urls + [u for u in _BACKUP_BASE_URLS if u not in custom_urls]
                self.siteUrl = custom_urls[0]
                print(f"[INFO] 使用自定义域名: {self.siteUrl}")

        # 动态解析网址（缓存 + 跳转追踪）
        self._resolve_site_url()

        # 刷新子域名信息
        ok = self.refresh_domains()
        if not ok:
            print("[WARN] 域名信息刷新失败，部分功能可能受限")

    def getName(self):
        return "国色天香"

    def refresh_domains(self) -> bool:
        candidates = [self.siteUrl] + [u for u in _BACKUP_BASE_URLS if u != self.siteUrl]
        seen = set()
        unique_candidates = []
        for c in candidates:
            if c not in seen:
                seen.add(c)
                unique_candidates.append(c)
        candidates = unique_candidates

        for candidate in candidates:
            try:
                resp = self.session.get(f"{candidate}/data.json", timeout=self.timeout)

                if resp.status_code == 881:
                    redirect_url = _extract_redirect_url_from_881(resp.text)
                    if redirect_url and redirect_url not in candidates:
                        print(f"[INFO] 域名 {candidate} 返回 881，发现新域名: {redirect_url}")
                        candidates.append(redirect_url)
                        try:
                            resp2 = self.session.get(f"{redirect_url}/data.json", timeout=self.timeout)
                            if resp2.status_code == 200:
                                resp = resp2
                                candidate = redirect_url
                            else:
                                continue
                        except Exception as e2:
                            print(f"[WARN] 新域名 {redirect_url} 请求失败: {e2}")
                            continue
                    else:
                        print(f"[WARN] 域名 {candidate} 返回 881，未能提取新域名")
                        continue

                resp.raise_for_status()
                content = resp.text

                # 修复: data.json 返回的是 JS 变量格式，不是纯 JSON
                start = content.find("var Group=")
                if start == -1:
                    start = content.find("var Group =")
                end = content.find("var Token=", start)
                if end == -1:
                    end = content.find("var Token =", start)

                if start == -1 or end == -1:
                    print(f"[WARN] {candidate}/data.json 格式异常")
                    continue

                json_str = content[start:end].strip()
                json_str = re.sub(r"var\s+Group\s*=\s*", "", json_str).rstrip(";").strip()

                group = json.loads(json_str)
                self.siteUrl = candidate
                self.css_domain = group.get("css_domain", "")
                self.pic_domain = group.get("pic_domain", "")
                self.novel_domain = group.get("novel_domain", "")
                self.csstime = str(group.get("csstime", ""))
                self.channel_id = str(group.get("channel_id", ""))

                if not self.pic_domain:
                    self.pic_domain = self.siteUrl
                if not self.novel_domain:
                    self.novel_domain = self.siteUrl
                if not self.css_domain:
                    self.css_domain = self.siteUrl

                print(f"[INFO] 域名刷新成功: {candidate}")
                return True
            except requests.exceptions.RequestException as e:
                print(f"[WARN] 域名 {candidate} 请求失败: {e}")
                continue
            except json.JSONDecodeError as e:
                print(f"[WARN] 域名 {candidate} JSON解析失败: {e}")
                continue
            except Exception as e:
                print(f"[WARN] 域名 {candidate} 未知错误: {e}")
                continue
        return False

    def fetch(self, url, headers=None):
        if headers is None:
            headers = {
                "User-Agent": self.userAgent,
                "Referer": self.siteUrl,
            }
        try:
            resp = self.session.get(url, headers=headers, timeout=self.timeout)
            resp.raise_for_status()
            return resp
        except Exception as e:
            print(f"[ERROR] fetch {url} failed: {e}")
            return None

    def _get_json(self, path: str, params: dict = None):
        if "?" in path:
            base_path, existing_query = path.split("?", 1)
            url = f"{self.siteUrl}{base_path}?{existing_query}"
        else:
            url = f"{self.siteUrl}{path}"

        if params:
            query = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
            url += ("&" if "?" in url else "?") + query

        resp = self.fetch(url)
        if not resp:
            return None
        try:
            return resp.json()
        except Exception as e:
            print(f"[ERROR] JSON解析失败: {e}")
            return None

    def cover_url(self, serial_number: str) -> str:
        if not serial_number:
            return ""
        pic_base = self.pic_domain if self.pic_domain else self.siteUrl
        css_url = f"{pic_base}/pic/{serial_number}/thumbnail.css"
        return f"http://xg3.mingapi.top/tvbox/php/国色天香_pic.php?url={quote(css_url)}"

    def m3u8_url(self, serial_number: str) -> str:
        if not serial_number:
            return ""
        novel_base = self.novel_domain if self.novel_domain else self.siteUrl
        return f"{novel_base}/m3u8/{serial_number}/index_domain.m3u8?{self.csstime}"

    def _format_vod(self, item: dict) -> dict:
        serial = item.get("serial_number", "")
        return {
            "vod_id": str(item.get("id", "")),
            "vod_name": decrypt_text(item.get("title", "")),
            "vod_pic": self.cover_url(serial) if serial else "",
            "vod_remarks": str(item.get("read_number", "")),
        }

    # ==================== TVBox 标准接口 ====================

    def homeContent(self, filter):
        result = {"class": [], "filters": {}}
        default_classes = [
            {"type_id": "1", "type_name": "国产"},
            {"type_id": "2", "type_name": "日本"},
            {"type_id": "3", "type_name": "韩国"},
            {"type_id": "4", "type_name": "欧美"},
        ]

        data = self._get_json(f"/index.json?{self.csstime}")
        classes = []
        filters_map = {}

        if data and "index_videos" in data:
            for key, cat in data["index_videos"].items():
                cat_id = str(cat.get("id", key))
                cat_name = decrypt_text(cat.get("name", ""))
                if not cat_name:
                    continue
                classes.append({"type_id": cat_id, "type_name": cat_name})

                genre_filter = {
                    "key": "genre",
                    "name": "流派",
                    "value": [{"n": "全部", "v": ""}]
                }
                for g in cat.get("genres", []):
                    g_name = decrypt_text(g.get("name", ""))
                    if g_name:
                        genre_filter["value"].append({"n": g_name, "v": str(g.get("id", ""))})

                label_filter = {
                    "key": "label",
                    "name": "标签",
                    "value": [{"n": "全部", "v": ""}]
                }
                for l in cat.get("labels", []):
                    l_name = html_module.unescape(l.get("name", ""))
                    if l_name:
                        label_filter["value"].append({"n": l_name, "v": str(l.get("id", ""))})

                filters_map[cat_id] = [genre_filter, label_filter]

        if not classes:
            classes = default_classes
            if filter:
                for c in classes:
                    filters_map[c["type_id"]] = []

        result['class'] = classes
        if filter:
            result['filters'] = filters_map
        return result

    def homeVideoContent(self):
        result = {"list": []}
        data = self._get_json(f"/index.json?{self.csstime}")
        if not data or "index_videos" not in data:
            return result

        videos = []
        seen_ids = set()
        for _, cat in data["index_videos"].items():
            for v in cat.get("videos", [])[:6]:
                vid = str(v.get("id", ""))
                if vid and vid not in seen_ids:
                    seen_ids.add(vid)
                    videos.append(self._format_vod(v))
        result["list"] = videos
        return result

    def categoryContent(self, tid, pg, filter, extend):
        result = {"list": [], "page": pg, "pagecount": 0, "limit": 20, "total": 0}
        api_path = f"/type/{tid}_{pg}.json?{self.csstime}"

        params = {}
        if extend and isinstance(extend, dict):
            if extend.get("genre"):
                params["genre"] = extend["genre"]
            if extend.get("label"):
                params["label"] = extend["label"]

        data = self._get_json(api_path, params=params if params else None)
        if not data:
            return result

        videos = []
        for v in data.get("data", {}).get("videos", []):
            videos.append(self._format_vod(v))

        page_count = data.get("data", {}).get("page_count", 1)
        result.update({
            "list": videos,
            "page": pg,
            "pagecount": page_count,
            "limit": 20,
            "total": page_count * 20,
        })
        return result

    def detailContent(self, ids):
        result = {"list": []}
        if not ids:
            return result
        video_id = ids[0] if isinstance(ids, list) else ids

        data = self._get_json(f"/video/{video_id}.json?{self.csstime}")
        if not data or "video" not in data:
            return result

        video = data["video"]
        serial = video.get("serial_number", "")

        vod = {
            "vod_id": str(video_id),
            "vod_name": decrypt_text(video.get("title", "")),
            "vod_pic": self.cover_url(serial) if serial else "",
            "vod_remarks": str(video.get("read_number", "")),
            "vod_year": "",
            "vod_area": "",
            "vod_actor": str(video.get("actresses", "")),
            "vod_director": "",
            "vod_content": html_module.unescape(video.get("description", "")),
            "vod_play_from": "默认",
            "vod_play_url": "",
        }

        if serial:
            m3u8 = self.m3u8_url(serial)
            vod["vod_play_url"] = f"播放${m3u8}"

        result["list"] = [vod]
        return result

    def searchContent(self, key, quick, pg=1):
        result = {"list": []}
        data = self._get_json("/search.json", params={"search": key})
        if not data:
            return result

        videos = []
        for v in data.get("videos", []):
            videos.append(self._format_vod(v))
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
            play_url = f"{self.siteUrl}{id}" if not id.startswith("http") else id
            resp = self.fetch(play_url)
            if resp:
                html_text = resp.text
                m = re.search(r'https?://[^\s"\']+\.m3u8[^\s"\']*', html_text)
                if m:
                    result["parse"] = 0
                    result["url"] = m.group(0)
                    result["header"] = headers
                else:
                    result["parse"] = 1
                    result["url"] = play_url
                    result["header"] = headers
            else:
                result["parse"] = 1
                result["url"] = play_url
                result["header"] = headers
        return result

    def isVideoFormat(self, url):
        if not url or not isinstance(url, str):
            return False
        if not url.startswith("http"):
            return False
        fmt = ['.mp4', '.m3u8', '.ts', '.mkv', '.avi', '.webm', '.flv']
        for f in fmt:
            if url.lower().find(f) > -1:
                return True
        return False

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        """本地代理(处理m3u8/key/封面解密等)"""
        action = param.get('action')
        if action == 'proxy':
            url = param.get('url')
            headers = {
                "User-Agent": self.userAgent,
                "Referer": self.siteUrl,
            }
            try:
                if param.get('type') == 'cover':
                    r = requests.get(url, headers=headers, timeout=10)
                    if r.status_code == 200 and r.content:
                        decrypted = bytes(b ^ 0x88 for b in r.content)
                        return [200, "image/webp", decrypted]
                    return [404, "text/plain", "cover not found"]
                elif param.get('type') == 'm3u8':
                    content = requests.get(url, headers=headers, timeout=10).text
                    return [200, "application/vnd.apple.mpegurl", content]
                elif param.get('type') == 'media':
                    r = requests.get(url, headers=headers, stream=True, timeout=10)
                    return [206, "application/octet-stream", r.content]
                else:
                    content = requests.get(url, headers=headers, timeout=10).text
                    return [200, "text/plain", content]
            except Exception as e:
                print(f"[ERROR] localProxy failed: {e}")
                return [500, "text/plain", str(e)]
        return None
