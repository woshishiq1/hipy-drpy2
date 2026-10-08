# -*- coding: utf-8 -*-
#!/usr/bin/env python3
# 大米星球 TVBox/影视仓 Python源
# 站点: https://www.dmxq39.com  CMS: 苹果CMS  加密: encrypt=3 (AES-CBC)

import re
import json
import base64
import time
import threading

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
except ImportError:
    requests = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

# ===== 配置 =====
SITE_NAME = "大米星球"
HOSTS = [
    "https://www.dmxq39.com", "https://dmxq39.com",
    "https://www.dami29.com", "https://dami29.com",
    "https://www.dami3.com", "https://dami3.com",
    "https://www.dami0.com", "https://dami0.com",
]
AES_KEY = "81f834a7f68d4c52"
AES_IV = "zkz8scsGXttFVZBb"
TIMEOUT = 12
CONNECT_POOL_SIZE = 10
DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
MOBILE_UA = "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"

# 特殊分类 (放最前)
LABEL_CATEGORIES = [
    {"type_id": "label_netflix", "type_name": "Netflix专区"},
    {"type_id": "label_new", "type_name": "今日更新"},
]
# 常规分类
VOD_CATEGORIES = [
    {"type_id": "20", "type_name": "电影"},
    {"type_id": "21", "type_name": "电视剧"},
    {"type_id": "22", "type_name": "动漫"},
    {"type_id": "23", "type_name": "综艺"},
    {"type_id": "36", "type_name": "短剧"},
    {"type_id": "35", "type_name": "福利"},
]
# 排行榜分类 (放最后)
RANK_CATEGORIES = [
    {"type_id": "label_rank_movie", "type_name": "电影排行榜"},
    {"type_id": "label_rank_tv", "type_name": "电视剧排行榜"},
    {"type_id": "label_rank_anime", "type_name": "动漫排行榜"},
    {"type_id": "label_rank_variety", "type_name": "综艺排行榜"},
    {"type_id": "label_rank_drama", "type_name": "短剧排行榜"},
    {"type_id": "label_rank_welfare", "type_name": "福利排行榜"},
]
RANK_PREFIX_MAP = {
    "label_rank_movie": "电影", "label_rank_tv": "电视剧",
    "label_rank_anime": "动漫", "label_rank_variety": "综艺",
    "label_rank_drama": "短剧", "label_rank_welfare": "福利",
}
RANK_PERIODS = ["总榜", "月榜", "周榜", "日榜"]
RANK_VOD_MAP = {
    "label_rank_movie": "20", "label_rank_tv": "21",
    "label_rank_anime": "22", "label_rank_variety": "23",
    "label_rank_drama": "36", "label_rank_welfare": "35",
}


class Spider:

    def __init__(self):
        self.host = HOSTS[0]
        self.session = None
        self.headers = {
            "User-Agent": DEFAULT_UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "",
        }
        self._host_idx = 0
        self._hot_cache = None
        self._hot_cache_time = 0
        self._pic_map_cache = {}
        self._rank_merge_cache = {}

    def init(self, extend=""):
        try:
            if extend:
                cfg = json.loads(extend)
                if cfg.get("host"):
                    custom_host = cfg["host"].rstrip("/")
                    if custom_host not in HOSTS:
                        HOSTS.insert(0, custom_host)
                    self.host = custom_host
                if cfg.get("UA"):
                    self.headers["User-Agent"] = cfg["UA"]
        except Exception:
            pass
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        adapter = HTTPAdapter(
            max_retries=Retry(total=1, backoff_factor=0.3, status_forcelist=[502, 503, 504]),
            pool_connections=CONNECT_POOL_SIZE, pool_maxsize=CONNECT_POOL_SIZE,
        )
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        return ""

    def _switch_host(self):
        self._host_idx = (self._host_idx + 1) % len(HOSTS)
        self.host = HOSTS[self._host_idx]
        self._hot_cache = None

    _fetch_lock = threading.Lock()

    def _fetch(self, url, retry=2):
        if url.startswith("/"):
            url = self.host + url
        if url.startswith("https://") or url.startswith("http://"):
            path = "/" + url.split("/", 3)[-1]
        else:
            path = url
        for attempt in range(retry + 1):
            try:
                with Spider._fetch_lock:
                    resp = self.session.get(self.host + path, timeout=TIMEOUT, verify=False)
                if resp.status_code == 200:
                    resp.encoding = self._detect_encoding(resp)
                    return resp.text
                if resp.status_code == 404:
                    return ""
            except Exception:
                pass
            if attempt < retry:
                self._switch_host()
        # 所有域名都失败, 重建session防止连接池损坏
        try:
            self.session = requests.Session()
            self.session.headers.update(self.headers)
            adapter = HTTPAdapter(
                max_retries=Retry(total=1, backoff_factor=0.3, status_forcelist=[502, 503, 504]),
                pool_connections=CONNECT_POOL_SIZE, pool_maxsize=CONNECT_POOL_SIZE,
            )
            self.session.mount("http://", adapter)
            self.session.mount("https://", adapter)
        except Exception:
            pass
        return ""

    def _get_hot_html(self):
        now = time.time()
        if self._hot_cache and (now - self._hot_cache_time) < 60:
            return self._hot_cache
        html = self._fetch("/label/hot.html")
        if html and "module-paper-item" in html:
            self._hot_cache = html
            self._hot_cache_time = now
            return html
        if self._hot_cache:
            return self._hot_cache
        return html or ""

    def _get_pic_map(self, vod_tid):
        if vod_tid in self._pic_map_cache:
            return self._pic_map_cache[vod_tid]
        pic_map = {}
        hits_html = self._fetch(f"/vodshow/{vod_tid}--hits------1---.html")
        if hits_html:
            if BeautifulSoup:
                soup = BeautifulSoup(hits_html, "html.parser")
                for card in soup.find_all("a", class_=re.compile(r"module-poster-item"), href=re.compile(r"/voddetail/\d+")):
                    m = re.search(r"/voddetail/(\d+)\.html", card.get("href", ""))
                    if m and m.group(1) not in pic_map:
                        img = card.find("img")
                        if img:
                            pic = img.get("data-original", "") or img.get("data-src", "") or img.get("src", "")
                            if pic:
                                pic_map[m.group(1)] = pic
            else:
                for m in re.finditer(r'href="/voddetail/(\d+)\.html"[^>]*>.*?data-original="([^"]*)"', hits_html, re.DOTALL):
                    if m.group(1) not in pic_map:
                        pic_map[m.group(1)] = m.group(2)
        self._pic_map_cache[vod_tid] = pic_map
        return pic_map

    def _get_merged_rank(self, hot_html, prefix, cache_key):
        if cache_key in self._rank_merge_cache:
            return self._rank_merge_cache[cache_key]
        all_videos = []
        seen_ids = set()
        for period in RANK_PERIODS:
            for v in self._parse_single_rank(hot_html, f"{prefix}{period}"):
                if v["vod_id"] in seen_ids:
                    continue
                seen_ids.add(v["vod_id"])
                remarks = v.get("vod_remarks", "")
                v["vod_remarks"] = f"[{period}] {remarks}" if remarks else f"[{period}]"
                all_videos.append(v)
        self._rank_merge_cache[cache_key] = all_videos
        return all_videos

    def _fill_missing_pics(self, videos, limit=25, batch_size=25):
        missing = [(v["vod_id"], v["vod_name"]) for v in videos if not v.get("vod_pic")]
        if not missing:
            return
        missing = missing[:limit]
        from urllib.parse import quote
        results = {}
        results_lock = threading.Lock()
        host = self.host

        def _lookup(vid, name):
            try:
                # 直接用requests.get, 不走self.session (避免线程安全问题)
                api_url = f"{host}/index.php/ajax/suggest?mid=1&wd={quote(name)}&limit=5"
                resp = requests.get(api_url, timeout=5, verify=False, headers=self.headers)
                if resp.status_code == 200:
                    data = json.loads(resp.text)
                    if data.get("code") == 1 and data.get("list"):
                        for item in data["list"]:
                            if str(item.get("id", "")) == vid:
                                pic = item.get("pic", "")
                                if pic:
                                    with results_lock:
                                        results[vid] = pic
                                return
                        for item in data["list"]:
                            if item.get("name", "") == name:
                                pic = item.get("pic", "")
                                if pic:
                                    with results_lock:
                                        results[vid] = pic
                                return
            except Exception:
                pass

        for i in range(0, len(missing), batch_size):
            threads = []
            for vid, name in missing[i:i + batch_size]:
                t = threading.Thread(target=_lookup, args=(vid, name))
                threads.append(t)
                t.start()
            for t in threads:
                t.join(timeout=3)

        for v in videos:
            if not v.get("vod_pic") and v["vod_id"] in results:
                v["vod_pic"] = self._fix_pic(results[v["vod_id"]])

    def _page(self, pg):
        try:
            pg = int(pg)
            return max(pg, 1)
        except Exception:
            return 1

    def _detect_encoding(self, resp):
        ct = resp.headers.get("Content-Type", "")
        for part in ct.split(";"):
            part = part.strip()
            if part.lower().startswith("charset="):
                return part.split("=", 1)[1].strip().strip('"')
        head = resp.content[:2048].decode("ascii", errors="ignore")
        m = re.search(r'charset=["\']?([\w-]+)', head, re.IGNORECASE)
        return m.group(1) if m else "utf-8"

    def _clean_text(self, text):
        if not text:
            return ""
        text = re.sub(r"<[^>]+>", "", text)
        return text.replace("&amp;", "&").replace("&nbsp;", " ").strip()

    def _fix_pic(self, pic):
        if not pic:
            return ""
        pic = pic.replace("&amp;", "&")
        if pic.startswith("//"):
            return "https:" + pic
        if pic.startswith("/"):
            return self.host + pic
        return pic

    def _decrypt_url(self, enc_url):
        if not enc_url:
            return ""
        if enc_url.startswith("http"):
            return enc_url
        try:
            modified = enc_url.replace("O0O0O", "=").replace("o000o", "+").replace("oo00o", "/")
            while len(modified) % 4 != 0:
                modified += "="
            ciphertext = base64.b64decode(modified)
            if HAS_CRYPTO:
                cipher = AES.new(AES_KEY.encode(), AES.MODE_CBC, AES_IV.encode())
                return unpad(cipher.decrypt(ciphertext), AES.block_size).decode("utf-8")
            return self._decrypt_fallback(modified)
        except Exception:
            return ""

    def _decrypt_fallback(self, modified_url):
        try:
            import subprocess
            ciphertext = base64.b64decode(modified_url)
            proc = subprocess.Popen(
                ["openssl", "enc", "-aes-128-cbc", "-d", "-K", AES_KEY.encode().hex(), "-iv", AES_IV.encode().hex()],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            out, _ = proc.communicate(ciphertext)
            if out:
                pad_len = out[-1]
                if pad_len <= 16 and all(b == pad_len for b in out[-pad_len:]):
                    out = out[:-pad_len]
                return out.decode("utf-8")
        except Exception:
            pass
        return ""

    # ===== 接口 =====

    def getName(self):
        return SITE_NAME

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url

    def manualVideoCheck(self):
        return False

    def getDependence(self):
        return ["requests"]

    def homeContent(self, filter):
        result = {"class": [], "filters": {}}
        for cat in LABEL_CATEGORIES:
            result["class"].append({"type_id": cat["type_id"], "type_name": cat["type_name"]})
        for cat in VOD_CATEGORIES:
            result["class"].append({"type_id": cat["type_id"], "type_name": cat["type_name"]})
        for cat in RANK_CATEGORIES:
            result["class"].append({"type_id": cat["type_id"], "type_name": cat["type_name"]})
        return result

    def homeVideoContent(self):
        result = {"list": []}
        try:
            html = self._fetch(self.host + "/index/home.html")
            if html:
                result["list"] = self._parse_home_sections(html)
        except Exception:
            pass
        return result

    def categoryContent(self, tid, pg, filter, extend):
        page = self._page(pg)
        result = {"list": [], "page": page, "pagecount": 1, "limit": 30, "total": 0}
        try:
            if tid.startswith("label_"):
                return self._label_content(tid, page, result)
            return self._vod_content(tid, page, extend, result)
        except Exception:
            return result

    def _vod_content(self, tid, page, extend, result):
        # 解析筛选参数 (壳子不支持二级分类时不传extend, 默认按最新)
        sort = "time"
        area = ""
        year = ""
        vod_class = ""
        if extend:
            try:
                ext = json.loads(extend) if isinstance(extend, str) else extend
                sort = ext.get("排序", ext.get("by", "time")) or "time"
                area = ext.get("地区", ext.get("area", "")) or ""
                year = ext.get("年份", ext.get("year", "")) or ""
                vod_class = ext.get("类型", ext.get("class", "")) or ""
            except Exception:
                pass
        # 统一用vodshow格式: /vodshow/{tid}-{area}-{by}-{class}-----{page}---{year}.html
        from urllib.parse import quote
        url = f"{self.host}/vodshow/{tid}-{quote(area)}-{sort}-{quote(vod_class)}-----{page}---{year}.html"
        html = self._fetch(url)
        if not html:
            return result
        videos = self._parse_video_list(html)
        result["list"] = videos
        pagecount = self._parse_pagecount(html)
        if pagecount and pagecount > page:
            result["pagecount"] = pagecount
        elif len(videos) >= 30 and page < 200:
            result["pagecount"] = page + 1
        else:
            result["pagecount"] = page
        result["total"] = result["pagecount"] * 30
        return result

    def _label_content(self, tid, page, result):
        if tid == "label_netflix":
            url = f"{self.host}/label/netflix.html" if page == 1 else f"{self.host}/label/netflix/page/{page}.html"
            html = self._fetch(url)
            if not html:
                return result
            videos = self._parse_video_list(html)
            result["list"] = videos
            pages = re.findall(r"/label/netflix/page/(\d+)\.html", html)
            if pages:
                result["pagecount"] = max(int(p) for p in pages)
            elif len(videos) >= 16 and page < 50:
                result["pagecount"] = page + 1
            else:
                result["pagecount"] = page
            result["total"] = result["pagecount"] * 16
            result["limit"] = 16

        elif tid.startswith("label_rank_"):
            prefix = RANK_PREFIX_MAP.get(tid, "")
            vod_tid = RANK_VOD_MAP.get(tid, "")
            if not prefix:
                return result
            hot_html = self._get_hot_html()
            if not hot_html:
                return result
            pic_map = self._get_pic_map(vod_tid)
            all_videos = self._get_merged_rank(hot_html, prefix, f"rank_{tid}")
            if not all_videos:
                return result
            per_page = 10
            start = (page - 1) * per_page
            videos = all_videos[start:start + per_page]
            for v in videos:
                if not v.get("vod_pic") and v["vod_id"] in pic_map:
                    v["vod_pic"] = self._fix_pic(pic_map[v["vod_id"]])
            self._fill_missing_pics(videos, limit=10, batch_size=10)
            result["list"] = videos
            result["pagecount"] = (len(all_videos) + per_page - 1) // per_page
            result["total"] = len(all_videos)
            result["limit"] = per_page

        elif tid == "label_new":
            html = self._fetch(f"{self.host}/label/new.html")
            if not html:
                return result
            videos = self._parse_video_list(html)
            result["list"] = videos
            result["pagecount"] = 1
            result["total"] = len(videos)
            result["limit"] = len(videos)

        return result

    def detailContent(self, ids):
        vod_id = ids[0] if isinstance(ids, list) else ids
        result = {"list": []}
        try:
            html = self._fetch(f"{self.host}/voddetail/{vod_id}.html")
            if html:
                result["list"] = [self._parse_detail(html, vod_id)]
        except Exception:
            pass
        return result

    def playerContent(self, flag, id, vipFlags):
        result = {"parse": 0, "url": "", "header": {"User-Agent": DEFAULT_UA, "Referer": self.host}}
        try:
            if id.startswith("http"):
                play_url = id
            elif id.startswith("/vodplay/"):
                play_url = self.host + id
            else:
                parts = id.split("-")
                play_url = f"{self.host}/vodplay/{id}.html" if len(parts) < 3 else f"{self.host}/vodplay/{parts[0]}-{parts[1]}-{parts[2]}.html"
            html = self._fetch(play_url)
            if not html:
                return result
            m = re.search(r'player_aaaa\s*=\s*(\{.*?\})\s*</script>', html, re.DOTALL) or re.search(r'player_aaaa\s*=\s*(\{.*?\})', html)
            if m:
                player_data = json.loads(m.group(1))
                enc_url = player_data.get("url", "")
                encrypt = player_data.get("encrypt", 0)
                if enc_url.startswith("http"):
                    result["url"] = enc_url
                elif encrypt == 3:
                    result["url"] = self._decrypt_url(enc_url)
                elif encrypt == 2:
                    try:
                        modified = enc_url.replace("O0O0O", "=").replace("o000o", "+").replace("oo00o", "/")
                        while len(modified) % 4 != 0:
                            modified += "="
                        result["url"] = base64.b64decode(modified).decode("utf-8")
                    except Exception:
                        pass
                else:
                    result["url"] = enc_url
                result["header"] = {"User-Agent": MOBILE_UA, "Referer": self.host, "Origin": self.host}
        except Exception:
            pass
        return result

    def searchContent(self, key, quick, pg="1"):
        page = self._page(pg)
        result = {"list": [], "page": page}
        try:
            if page == 1:
                html = self._fetch(f"{self.host}/index.php/ajax/suggest?mid=1&wd={key}&limit=30")
                if html:
                    try:
                        data = json.loads(html)
                        if data.get("code") == 1 and data.get("list"):
                            for item in data["list"]:
                                result["list"].append({
                                    "vod_id": str(item["id"]),
                                    "vod_name": item["name"],
                                    "vod_pic": self._fix_pic(item.get("pic", "")),
                                    "vod_remarks": "",
                                })
                            result["pagecount"] = 1
                            result["limit"] = 30
                            result["total"] = len(result["list"])
                            return result
                    except json.JSONDecodeError:
                        pass
            from urllib.parse import quote
            html = self._fetch(f"{self.host}/vodsearch/{quote(key)}----------{page}---.html")
            if not html:
                return result
            videos = self._parse_search_list(html)
            result["list"] = videos
            pagecount = self._parse_search_pagecount(html)
            if pagecount:
                result["pagecount"] = pagecount
            elif len(videos) >= 10:
                result["pagecount"] = page + 1
            else:
                result["pagecount"] = page
            result["limit"] = 10
            result["total"] = result["pagecount"] * 10
        except Exception:
            pass
        return result

    # ===== 解析 =====

    def _parse_home_sections(self, html):
        videos = []
        seen_ids = set()
        if BeautifulSoup:
            soup = BeautifulSoup(html, "html.parser")
            for mod in soup.find_all("div", class_="module"):
                items = mod.find_all("a", class_=re.compile(r"module-poster-item|module-item"), href=re.compile(r"/voddetail/\d+"))
                for item in items:
                    try:
                        m = re.search(r"/voddetail/(\d+)\.html", item.get("href", ""))
                        if not m:
                            continue
                        vod_id = m.group(1)
                        if vod_id in seen_ids:
                            continue
                        title = item.get("title", "")
                        img = item.find("img")
                        pic = ""
                        if img:
                            if not title:
                                title = img.get("alt", "")
                            pic = img.get("data-original", "") or img.get("data-src", "") or img.get("src", "")
                        note_el = item.find("div", class_="module-item-note")
                        remarks = note_el.get_text(strip=True) if note_el else ""
                        if title:
                            seen_ids.add(vod_id)
                            videos.append({"vod_id": vod_id, "vod_name": title, "vod_pic": self._fix_pic(pic), "vod_remarks": remarks})
                    except Exception:
                        continue
            if not videos:
                videos = self._parse_video_list(html)
        else:
            for m in re.finditer(r'href="/voddetail/(\d+)\.html"[^>]*\s+title="([^"]*)"[^>]*>.*?data-original="([^"]*)"', html, re.DOTALL):
                vod_id, title, pic = m.groups()
                if vod_id not in seen_ids and title:
                    seen_ids.add(vod_id)
                    videos.append({"vod_id": vod_id, "vod_name": title, "vod_pic": self._fix_pic(pic), "vod_remarks": ""})
        return videos

    def _parse_video_list(self, html):
        videos = []
        seen_ids = set()
        if BeautifulSoup:
            soup = BeautifulSoup(html, "html.parser")
            items = soup.find_all("a", class_=re.compile(r"module-poster-item|module-item"), href=re.compile(r"/voddetail/\d+"))
            for item in items:
                try:
                    m = re.search(r"/voddetail/(\d+)\.html", item.get("href", ""))
                    if not m:
                        continue
                    vod_id = m.group(1)
                    if vod_id in seen_ids:
                        continue
                    title = item.get("title", "")
                    img = item.find("img")
                    pic = ""
                    if img:
                        if not title:
                            title = img.get("alt", "")
                        pic = img.get("data-original", "") or img.get("data-src", "") or img.get("src", "")
                    note_el = item.find("div", class_="module-item-note")
                    remarks = note_el.get_text(strip=True) if note_el else ""
                    if title:
                        seen_ids.add(vod_id)
                        videos.append({"vod_id": vod_id, "vod_name": title, "vod_pic": self._fix_pic(pic), "vod_remarks": remarks})
                except Exception:
                    continue
            if not videos:
                for item in soup.find_all("div", class_="module-item"):
                    try:
                        link = item.find("a", href=re.compile(r"/voddetail/\d+"))
                        if not link:
                            continue
                        m = re.search(r"/voddetail/(\d+)\.html", link.get("href", ""))
                        if not m:
                            continue
                        vod_id = m.group(1)
                        if vod_id in seen_ids:
                            continue
                        img = item.find("img")
                        title = pic = ""
                        if img:
                            title = img.get("alt", "")
                            pic = img.get("data-original", "") or img.get("data-src", "") or img.get("src", "")
                        note_el = item.find("div", class_="module-item-note")
                        remarks = note_el.get_text(strip=True) if note_el else ""
                        if title:
                            seen_ids.add(vod_id)
                            videos.append({"vod_id": vod_id, "vod_name": title, "vod_pic": self._fix_pic(pic), "vod_remarks": remarks})
                    except Exception:
                        continue
        else:
            for m in re.finditer(r'href="/voddetail/(\d+)\.html"[^>]*\s+title="([^"]*)"[^>]*>.*?data-original="([^"]*)"', html, re.DOTALL):
                vod_id, title, pic = m.groups()
                if vod_id not in seen_ids and title:
                    seen_ids.add(vod_id)
                    videos.append({"vod_id": vod_id, "vod_name": title, "vod_pic": self._fix_pic(pic), "vod_remarks": ""})
        return videos

    def _parse_single_rank(self, html, section_name):
        videos = []
        seen_ids = set()
        if BeautifulSoup:
            soup = BeautifulSoup(html, "html.parser")
            for section in soup.find_all("div", class_=lambda c: c and "module-paper-item" in c and "module-item" in c):
                title_el = section.find("h3", class_=re.compile(r"module-paper-item-title"))
                if (title_el.get_text(strip=True) if title_el else "") != section_name:
                    continue
                for item in section.find_all("a", href=re.compile(r"/voddetail/\d+")):
                    try:
                        m = re.search(r"/voddetail/(\d+)\.html", item.get("href", ""))
                        if not m:
                            continue
                        vod_id = m.group(1)
                        if vod_id in seen_ids:
                            continue
                        num_el = item.find("div", class_=re.compile(r"module-paper-item-num"))
                        rank = num_el.get_text(strip=True) if num_el else ""
                        name_el = item.find("span", class_=re.compile(r"module-paper-item-infotitle|title"))
                        title = name_el.get_text(strip=True) if name_el else item.get("title", "")
                        remark_el = item.find("p")
                        remarks = remark_el.get_text(strip=True) if remark_el else ""
                        if rank:
                            remarks = f"第{rank}名 {remarks}" if remarks else f"第{rank}名"
                        if title:
                            seen_ids.add(vod_id)
                            videos.append({"vod_id": vod_id, "vod_name": title, "vod_pic": "", "vod_remarks": remarks})
                    except Exception:
                        continue
                break
        else:
            sections = re.split(r'module-paper-item-title[^>]*>([^<]+)</h3>', html)
            for i in range(1, len(sections), 2):
                if sections[i].strip() != section_name:
                    continue
                content = sections[i + 1] if i + 1 < len(sections) else ""
                for m in re.finditer(r'href="/voddetail/(\d+)\.html"[^>]*>.*?module-paper-item-num[^>]*>(\d+)</div>.*?module-paper-item-infotitle[^>]*>([^<]+)</span>.*?<p>([^<]*)</p>', content, re.DOTALL):
                    vod_id, rank, title, remarks = m.groups()
                    if vod_id not in seen_ids and title:
                        seen_ids.add(vod_id)
                        combined = f"第{rank}名 {remarks.strip()}" if remarks.strip() else f"第{rank}名"
                        videos.append({"vod_id": vod_id, "vod_name": title.strip(), "vod_pic": "", "vod_remarks": combined})
                break
        return videos

    def _parse_search_list(self, html):
        videos = []
        seen_ids = set()
        if BeautifulSoup:
            soup = BeautifulSoup(html, "html.parser")
            for item in soup.find_all("div", class_="module-item"):
                try:
                    link = item.find("a", href=re.compile(r"/voddetail/\d+"))
                    if not link:
                        continue
                    m = re.search(r"/voddetail/(\d+)\.html", link.get("href", ""))
                    if not m:
                        continue
                    vod_id = m.group(1)
                    if vod_id in seen_ids:
                        continue
                    img = item.find("img")
                    title = pic = ""
                    if img:
                        title = img.get("alt", "")
                        pic = img.get("data-original", "") or img.get("data-src", "") or img.get("src", "")
                    title = title.replace("<em>", "").replace("</em>", "")
                    note_el = item.find("div", class_="module-item-note")
                    remarks = note_el.get_text(strip=True) if note_el else ""
                    if title:
                        seen_ids.add(vod_id)
                        videos.append({"vod_id": vod_id, "vod_name": title, "vod_pic": self._fix_pic(pic), "vod_remarks": remarks})
                except Exception:
                    continue
        else:
            for m in re.finditer(r'href="/voddetail/(\d+)\.html".*?data-original="([^"]*)".*?alt="([^"]*)"', html, re.DOTALL):
                vod_id, pic, title = m.groups()
                title = title.replace("<em>", "").replace("</em>", "")
                if vod_id not in seen_ids and title:
                    seen_ids.add(vod_id)
                    videos.append({"vod_id": vod_id, "vod_name": title, "vod_pic": self._fix_pic(pic), "vod_remarks": ""})
        return videos

    def _parse_detail(self, html, vod_id):
        vod = {
            "vod_id": vod_id, "vod_name": "", "vod_pic": "", "vod_year": "",
            "vod_area": "", "vod_class": "", "vod_director": "", "vod_actor": "",
            "vod_content": "", "vod_remarks": "", "vod_play_from": "", "vod_play_url": "",
        }
        if BeautifulSoup:
            soup = BeautifulSoup(html, "html.parser")
            h1 = soup.find("h1")
            if h1:
                vod["vod_name"] = h1.get_text(strip=True)
            poster = soup.find("div", class_="module-info-poster")
            if poster:
                img = poster.find("img")
                if img:
                    vod["vod_pic"] = self._fix_pic(img.get("data-original", "") or img.get("src", ""))
            genres = []
            for tag in soup.find_all("div", class_="module-info-tag-link"):
                a = tag.find("a")
                if a:
                    val = a.get_text(strip=True)
                    if re.match(r"^\d{4}$", val):
                        vod["vod_year"] = val
                    elif not vod["vod_area"] and val:
                        vod["vod_area"] = val
                    else:
                        genres.append(val)
            vod["vod_class"] = " ".join(genres)
            for item in soup.find_all("div", class_="module-info-item"):
                label_el = item.find("span", class_="module-info-item-title") or item.find("div", class_="module-info-item-label")
                content_el = item.find("div", class_="module-info-item-content")
                if not (label_el and content_el):
                    continue
                label_text = label_el.get_text(strip=True)
                links = content_el.find_all("a")
                val = " ".join(a.get_text(strip=True) for a in links) if links else content_el.get_text(strip=True)
                val = val.rstrip("/").strip()
                if "导演" in label_text:
                    vod["vod_director"] = val
                elif "主演" in label_text or "演员" in label_text:
                    vod["vod_actor"] = val
                elif "备注" in label_text or "状态" in label_text:
                    vod["vod_remarks"] = val
                elif "更新" in label_text and not vod["vod_remarks"]:
                    vod["vod_remarks"] = val
            intro = soup.find("div", class_="module-info-introduction-content")
            if intro:
                vod["vod_content"] = intro.get_text(strip=True)
            tab_names = [tab.get("data-dropdown-value", "") for tab in soup.find_all("div", class_="module-tab-item") if tab.get("data-dropdown-value")]
            play_from = []
            play_url = []
            for i, plist in enumerate(soup.find_all("div", class_="module-play-list-content")):
                source_name = tab_names[i] if i < len(tab_names) else f"线路{i+1}"
                episodes = []
                links = plist.find_all("a", class_="module-play-list-link") or plist.find_all("a", href=re.compile(r"/vodplay/"))
                for link in links:
                    href = link.get("href", "")
                    span = link.find("span")
                    ep_name = span.get_text(strip=True) if span else link.get_text(strip=True)
                    m = re.search(r"/vodplay/(\d+-\d+-\d+)\.html", href)
                    play_id = m.group(1) if m else href
                    episodes.append(f"{ep_name}${play_id}")
                if episodes:
                    play_from.append(source_name)
                    play_url.append("#".join(episodes))
            vod["vod_play_from"] = "$$$".join(play_from)
            vod["vod_play_url"] = "$$$".join(play_url)
        else:
            m = re.search(r"<h1[^>]*>([^<]+)</h1>", html)
            if m:
                vod["vod_name"] = m.group(1).strip()
            m = re.search(r'<div class="module-info-poster">.*?<img[^>]*?(?:data-original|src)="([^"]*)"', html, re.DOTALL)
            if m:
                vod["vod_pic"] = self._fix_pic(m.group(1))
            genres = []
            for val in re.findall(r'<div class="module-info-tag-link"><a[^>]*>([^<]+)</a>', html):
                val = val.strip()
                if re.match(r"^\d{4}$", val):
                    vod["vod_year"] = val
                elif not vod["vod_area"]:
                    vod["vod_area"] = val
                else:
                    genres.append(val)
            vod["vod_class"] = " ".join(genres)
            m = re.search(r'导演.*?<a[^>]*>([^<]+)</a>', html)
            if m:
                vod["vod_director"] = m.group(1).strip()
            actors = re.findall(r'主演.*?</div>\s*<div class="module-info-item-content">(.*?)</div>', html, re.DOTALL)
            if actors:
                vod["vod_actor"] = " ".join(re.findall(r"<a[^>]*>([^<]+)</a>", actors[0]))
            m = re.search(r'class="module-info-introduction-content"[^>]*>(.*?)</div>', html, re.DOTALL)
            if m:
                vod["vod_content"] = self._clean_text(m.group(1))
            tab_names = re.findall(r'data-dropdown-value="([^"]+)"', html)
            play_from = []
            play_url = []
            for i, block in enumerate(re.findall(r'<div class="module-play-list-content[^"]*">(.*?)</div>', html, re.DOTALL)):
                source_name = tab_names[i] if i < len(tab_names) else f"线路{i+1}"
                episodes = re.findall(r'href="/vodplay/(\d+-\d+-\d+)\.html"[^>]*><span>([^<]+)</span>', block)
                if not episodes:
                    episodes = re.findall(r'href="/vodplay/(\d+-\d+-\d+)\.html"[^>]*>(.*?)</a>', block, re.DOTALL)
                if episodes:
                    play_from.append(source_name)
                    play_url.append("#".join(f"{self._clean_text(name)}${pid}" for pid, name in episodes))
            vod["vod_play_from"] = "$$$".join(play_from)
            vod["vod_play_url"] = "$$$".join(play_url)
        if not vod["vod_remarks"]:
            m = re.search(r'<div class="module-item-note">([^<]+)</div>', html)
            if m:
                vod["vod_remarks"] = m.group(1).strip()
        return vod

    def _parse_pagecount(self, html):
        pages = re.findall(r'/vodshow/\d+[^"]*-----?(\d+)---', html)
        if pages:
            return max(int(p) for p in pages)
        pages = re.findall(r"/vodtype/\d+-(\d+)\.html", html)
        if pages:
            return max(int(p) for p in pages)
        return None

    def _parse_search_pagecount(self, html):
        pages = re.findall(r"----------(\d+)---\.html", html)
        if pages:
            return max(int(p) for p in pages)
        return None

    def destroy(self):
        if self.session:
            try:
                self.session.close()
            except Exception:
                pass


try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except Exception:
    pass
