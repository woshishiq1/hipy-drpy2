# -*- coding: utf-8 -*-
# !/usr/bin/python
"""
@header({
  searchable: 1,
  filterable: 1,
  quickSearch: 1,
  title: '911爆料网',
  lang: 'hipy'
})
"""
import sys
import re
import json
import base64
import html
import time
import threading
import requests
import urllib3
from urllib.parse import urljoin, quote, unquote, urlparse
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    from lxml import etree
except ImportError:
    etree = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

try:
    from Crypto.Cipher import AES
except ImportError:
    AES = None

sys.path.append('..')
try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        def __init__(self, *args, **kwargs):
            self.t4_api = kwargs.get("t4_api", "")
        def getName(self): return "Spider"
        def init(self, extend=""): pass
        def homeContent(self, filter=False): return {'class': [], 'filters': {}}
        def homeVideoContent(self): return {'list': []}
        def categoryContent(self, tid, pg, filter=False, extend=None): return {'list': [], 'page': 1, 'pagecount': 1, 'limit': 20, 'total': 0}
        def detailContent(self, ids): return {'list': []}
        def playerContent(self, flag, id, vipFlags=None): return {'parse': 0, 'url': '', 'header': {}}
        def searchContent(self, key, quick=False, pg="1"): return {'list': [], 'page': 1, 'pagecount': 1, 'limit': 20, 'total': 0}
        def localProxy(self, param): return [200, "text/plain", b""]
        def isVideoFormat(self, url): return False
        def manualVideoCheck(self): return False
        def getProxyUrl(self, flag=False): return getattr(self, "t4_api", "")
        def destroy(self): pass

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 全局内存短时缓存 (解决客户端并发请求/预加载/反复切页卡顿)
CACHE_STORE = {}
CACHE_LOCK = threading.Lock()

def get_cache(key):
    with CACHE_LOCK:
        if key in CACHE_STORE:
            val, expire_time = CACHE_STORE[key]
            if time.time() < expire_time:
                return val
            del CACHE_STORE[key]
    return None

def set_cache(key, val, ttl=180):
    with CACHE_LOCK:
        if len(CACHE_STORE) > 500:
            now = time.time()
            expired = [k for k, v in CACHE_STORE.items() if now >= v[1]]
            for k in expired:
                del CACHE_STORE[k]
            if len(CACHE_STORE) > 500:
                CACHE_STORE.clear()
        CACHE_STORE[key] = (val, time.time() + ttl)

def _page(pg):
    try:
        v = int(str(pg or "").strip())
        return v if v > 0 else 1
    except Exception:
        return 1

class Spider(BaseSpider):
    AES_KEY = b"f5d965df75336270"
    AES_IV = b"97b60394abc2fbe1"

    AD_KEYWORDS = {
        "app", "911爆料app", "下载app", "官方推荐", "加入911", "章鱼导航", "欲洛降临",
        "七夕活动", "911暑期活动", "回家的路", "投稿方式", "常见问题", "广告商务",
        "所有标签", "关于我们", "官方tg群", "官方推特", "ai换脸脱衣", "广告", "商务合作"
    }

    # 多线路域名池（含 CloudFront 亚马逊全球 CDN 与高速镜像）
    DOMAIN_POOL = [
        "https://d10cq29fdobmmg.cloudfront.net",
        "https://catch.belwfufv.cc",
        "https://911bla.com",
        "https://911bl16.com",
        "https://911bl.com",
        "https://carry.cyepzjnb.com",
        "https://admire.cyepzjnb.com"
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.t4_api = kwargs.get("t4_api", "")
        self.host = self.DOMAIN_POOL[0]
        self.ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1"
        self.headers = {
            "User-Agent": self.ua,
            "Referer": self.host + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
        }
        self.session = requests.Session()
        adapter = HTTPAdapter(pool_connections=25, pool_maxsize=50, max_retries=Retry(total=1, backoff_factor=0.1))
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        self.session.headers.update(self.headers)
        self.ext = ""
        self._img_cache = {}
        self._img_lock = threading.Lock()
        self.categories = [
            {"type_id": "category/jrgb", "type_name": "今日大瓜"},
            {"type_id": "category/mrds", "type_name": "每日大赛"},
            {"type_id": "category/hjsq", "type_name": "海角社区"},
            {"type_id": "category/aidj", "type_name": "AI短剧"},
            {"type_id": "category/crfys", "type_name": "午夜剧场"},
            {"type_id": "category/dmhv", "type_name": "动漫天堂"},
            {"type_id": "category/sgpjs", "type_name": "水果派解说"},
            {"type_id": "category/rmgb", "type_name": "独家爆料"},
            {"type_id": "category/rlph", "type_name": "黑料排行"},
            {"type_id": "category/ssdbl", "type_name": "热点吃瓜"},
            {"type_id": "category/xyss", "type_name": "校园吃瓜"},
            {"type_id": "category/bgzq", "type_name": "反差爆料"},
            {"type_id": "category/whbl", "type_name": "网红黑料"},
            {"type_id": "category/mxhl", "type_name": "明星吃瓜"},
            {"type_id": "category/blqw", "type_name": "猎奇吃瓜"},
            {"type_id": "category/tksm", "type_name": "偷窥泄密"},
            {"type_id": "category/zksr", "type_name": "SM专区"},
            {"type_id": "category/ntll", "type_name": "男男女女"},
            {"type_id": "category/thjx", "type_name": "探花经典"},
            {"type_id": "category/fljq", "type_name": "福利视频"},
            {"type_id": "category/crlz", "type_name": "网黄专辑"},
            {"type_id": "category/slec", "type_name": "影视床戏"},
            {"type_id": "category/kpzj", "type_name": "看片专辑"}
        ]

    def getName(self):
        return "911爆料网"

    def _select_fastest_host(self):
        """并发测速选出延迟最低的主机，并缓存 15 分钟"""
        cache_key = "fastest_911_host"
        cached = get_cache(cache_key)
        if cached:
            return cached

        results = {}
        threads = []

        def test_host(u):
            try:
                st = time.time()
                r = requests.head(u, headers=self.headers, timeout=1.5, allow_redirects=True, verify=False)
                if r.status_code < 400:
                    results[u] = (time.time() - st) * 1000
                else:
                    results[u] = float('inf')
            except Exception:
                results[u] = float('inf')

        for u in self.DOMAIN_POOL:
            t = threading.Thread(target=test_host, args=(u,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=1.8)

        valid = {k: v for k, v in results.items() if v < float('inf')}
        best = min(valid.items(), key=lambda x: x)[0] if valid else self.DOMAIN_POOL[0]
        set_cache(cache_key, best, ttl=900)
        return best

    def setExtendInfo(self, extend):
        self.ext = extend or ""
        if isinstance(extend, str) and extend.startswith("http"):
            self.host = extend.rstrip("/")
        elif isinstance(extend, dict) and extend.get("host"):
            self.host = str(extend["host"]).rstrip("/")
        else:
            self.host = self._select_fastest_host()

        self.headers["Referer"] = self.host + "/"
        self.session.headers.update(self.headers)
        return None

    def init(self, extend=""):
        raw = getattr(self, "ext", "") or extend or ""
        self.setExtendInfo(raw)
        return None

    def isVideoFormat(self, url):
        return bool(re.search(r'\.(?:m3u8|mp4|flv|m4a)(?:$|[?#])', str(url or ''), re.I))

    def manualVideoCheck(self):
        return False

    def destroy(self):
        if hasattr(self, "session") and self.session:
            try:
                self.session.close()
            except Exception:
                pass

    def _fix_url(self, url):
        if not url:
            return ""
        url = str(url).strip()
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("http://") or url.startswith("https://"):
            return url
        return urljoin(self.host, url)

    def _proxy_base(self):
        try:
            f = getattr(self, "getProxyUrl", None)
            url = f() if callable(f) else ""
            if url:
                return url
        except Exception:
            pass
        return getattr(self, "t4_api", "")

    def _fix_pic(self, pic):
        if not pic:
            return ""
        pic_url = self._fix_url(pic)
        base = self._proxy_base()
        if base and pic_url.startswith("http"):
            sep = "&" if "?" in base else "?"
            return f"{base}{sep}type=img&url={quote(pic_url, safe='')}"
        if "@Referer=" not in pic_url and pic_url.startswith("http"):
            pic_url += f"@Referer={self.host}/&User-Agent={self.ua}"
        return pic_url

    def _fetch(self, url, retry_backup=True):
        if not hasattr(self, "session") or not self.session:
            self.session = requests.Session()
            self.session.headers.update(self.headers)

        candidates = [url]
        if retry_backup:
            for b_host in self.DOMAIN_POOL:
                parsed = urlparse(url)
                if parsed.netloc and parsed.netloc != urlparse(b_host).netloc:
                    candidates.append(url.replace(f"{parsed.scheme}://{parsed.netloc}", b_host))

        # 双级超时优化：连接超时 2.5s，传输超时 5s
        for target_url in candidates[:3]:
            try:
                r = self.session.get(target_url, headers=self.headers, timeout=(2.5, 5), verify=False)
                if r.status_code == 200:
                    r.encoding = "utf-8"
                    if len(r.text) > 200:
                        return r.text
            except Exception:
                continue
        return ""

    def _decrypt_image_bytes(self, data):
        if not data:
            return b""
        if AES:
            try:
                cipher = AES.new(self.AES_KEY, AES.MODE_CBC, self.AES_IV)
                raw = cipher.decrypt(data)
                pad = raw[-1] if raw else 0
                if 0 < pad <= 16 and raw.endswith(bytes([pad]) * pad):
                    return raw[:-pad]
                return raw
            except Exception:
                pass
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            from cryptography.hazmat.backends import default_backend
            cipher = Cipher(algorithms.AES(self.AES_KEY), modes.CBC(self.AES_IV), backend=default_backend())
            decryptor = cipher.decryptor()
            raw = decryptor.update(data) + decryptor.finalize()
            pad = raw[-1] if raw else 0
            if 0 < pad <= 16 and raw.endswith(bytes([pad]) * pad):
                return raw[:-pad]
            return raw
        except Exception:
            pass
        return data

    def _mime_from_bytes(self, data):
        if data.startswith(b"\xff\xd8\xff"):
            return "jpeg"
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            return "png"
        if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
            return "gif"
        if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            return "webp"
        return "jpeg"

    def _extract_pic_from_node(self, node, raw_str=""):
        if not raw_str and node is not None:
            raw_str = str(node)

        # 1. 匹配 loadBannerDirect
        script_match = re.search(r"loadBannerDirect\(['\"]([^'\"]+)['\"]", raw_str)
        if script_match:
            return script_match.group(1).strip()

        # 2. 匹配 meta 标签
        if hasattr(node, "xpath") and etree:
            meta_imgs = node.xpath('.//meta[@itemprop="image" or @itemprop="thumbnailUrl"]/@content')
            if meta_imgs and meta_imgs[0].strip():
                return meta_imgs[0].strip()
        elif hasattr(node, "select_one"):
            meta_img = node.select_one('meta[itemprop="image"], meta[itemprop="thumbnailUrl"]')
            if meta_img and meta_img.get("content"):
                return meta_img.get("content").strip()

        # 3. 匹配混淆与懒加载属性
        if hasattr(node, "xpath") and etree:
            for attr in ["z-image-loader-url", "data-xkrkllgl", "data-original", "data-src", "data-lazy-src", "data-cover", "data-thumb", "data-echo", "data-bg", "src"]:
                vals = node.xpath(f'.//img/@{attr}')
                if vals:
                    val = str(vals[0]).strip()
                    if val and not val.startswith("data:image") and not any(x in val.lower() for x in ["placeholder", "loading", "blank", "1px", "default", "ads"]):
                        return val
        elif hasattr(node, "select_one"):
            img = node.select_one("img")
            if img:
                for attr in ["z-image-loader-url", "data-xkrkllgl", "data-original", "data-src", "data-lazy-src", "data-cover", "data-thumb", "data-echo", "data-bg", "src"]:
                    val = img.get(attr, "")
                    if val and not val.startswith("data:image") and not any(x in val.lower() for x in ["placeholder", "loading", "blank", "1px", "default", "ads"]):
                        return val

        # 4. 匹配 CSS background-image
        bg_match = re.search(r'background-image\s*:\s*url\([\'"]?([^\'")]+)[\'"]?\)', raw_str, re.I)
        if bg_match:
            bg_url = bg_match.group(1).strip()
            if not bg_url.startswith("data:image") and not any(x in bg_url.lower() for x in ["placeholder", "loading", "blank", "1px", "ads"]):
                return bg_url

        return ""

    def _is_valid_item(self, title, href, pic, raw_node=""):
        if not title or not href:
            return False
        clean_title = title.strip().lower()
        if clean_title in self.AD_KEYWORDS or any(kw == clean_title for kw in self.AD_KEYWORDS):
            return False
        if len(clean_title) <= 3 and clean_title in ["app", "vip", "gg", "ad", "ads"]:
            return False
        if raw_node and any(x in raw_node for x in ['rel="sponsored"', 'data-event="ad_click"', 'class="ad', 'class="advert', 'class="sticky-ad']):
            return False
        if not re.search(r"/(?:archives|article|post|detail)/\d+", href) and not re.search(r"/\d+\.html", href):
            return False
        if not pic or not str(pic).strip():
            return False
        return True

    def _extract_cards(self, html_text):
        videos = []
        if not html_text:
            return videos

        # 优先采用 C 语言级加速的 lxml.etree 极速解析
        if etree:
            try:
                parser = etree.HTMLParser(recover=True, encoding="utf-8")
                tree = etree.HTML(html_text.encode("utf-8", errors="ignore"), parser=parser)
                if tree is not None:
                    items = tree.xpath('//div[@id="index" or @id="archive"]//article[.//a[contains(@href,"/archives/")]] | //ul[contains(@class,"row")]/li[.//a] | //article[.//a]')
                    for item in items:
                        try:
                            hrefs = item.xpath('.//a[contains(@href,"/archives/") or contains(@href,"/article/")]/@href') or item.xpath('.//a/@href')
                            href = str(hrefs[0]).strip() if hrefs else ""
                            titles = item.xpath('.//h2[contains(@class,"headline")]//text() | .//h2//text() | .//h3//text() | .//*[contains(@class,"post-card-bottom-text")]//text()')
                            title = "".join(titles).strip()
                            remarks = item.xpath('.//span[@itemprop="datePublished"]//text() | .//span[contains(@class,"small")]//text() | .//time//text() | .//span[contains(@class,"text-muted")]//text()')
                            remark = "".join(remarks).strip()
                            raw_str = etree.tostring(item, encoding="utf-8").decode("utf-8", errors="ignore")
                            pic = self._extract_pic_from_node(item, raw_str)

                            if not self._is_valid_item(title, href, pic, raw_str):
                                continue

                            videos.append({
                                "vod_id": self._fix_url(href),
                                "vod_name": title[:100],
                                "vod_pic": self._fix_pic(pic),
                                "vod_remarks": remark
                            })
                        except Exception:
                            continue
            except Exception:
                pass

        # 备选 BeautifulSoup 降级
        if not videos and BeautifulSoup:
            doc = BeautifulSoup(html_text, "html.parser")
            containers = doc.select("div#index article, div#archive article, ul.row li, div.article-item, article, .post-item, .video-item, div[class*='item']")
            for item in containers:
                try:
                    title_elem = item.select_one("h2.headline, .headline, h2 a, h3 a, a[title], .post-card-bottom-text, .title, h2, h3")
                    title = title_elem.get("title") or title_elem.get_text(strip=True) if title_elem else ""
                    a_elem = item.select_one("a[href*='/archives/'], a[href*='/article/'], a[href*='/post/'], a")
                    href = a_elem.get("href", "") if a_elem else ""
                    remark_elem = item.select_one("span[itemprop='datePublished'], span.small, time, .date, .time, span.text-muted, .item-meta")
                    remark = remark_elem.get_text(strip=True) if remark_elem else ""
                    pic = self._extract_pic_from_node(item, str(item))

                    if not self._is_valid_item(title, href, pic, str(item)):
                        continue

                    videos.append({
                        "vod_id": self._fix_url(href),
                        "vod_name": title[:100],
                        "vod_pic": self._fix_pic(pic),
                        "vod_remarks": remark
                    })
                except Exception:
                    continue

        return videos

    def homeContent(self, filter=False):
        return {
            "class": self.categories,
            "filters": {}
        }

    def homeVideoContent(self):
        # 直接复用 categoryContent 推荐第一页，利用内存缓存
        return self.categoryContent("category/jrgb", "1")

    def categoryContent(self, tid, pg, filter=False, extend=None):
        page = _page(pg)
        clean_tid = str(tid or "category/jrgb").strip("/")
        if not clean_tid.startswith("category/"):
            clean_tid = f"category/{clean_tid}"

        cache_key = f"cate_{clean_tid}_{page}"
        cached = get_cache(cache_key)
        if cached:
            return cached

        url = f"{self.host}/{clean_tid}/{page}/" if page > 1 else f"{self.host}/{clean_tid}/"
        html_text = self._fetch(url)
        videos = self._extract_cards(html_text)
        res = {
            "list": videos,
            "page": page,
            "pagecount": page + 1 if len(videos) >= 10 else page,
            "limit": len(videos) if videos else 20,
            "total": 9999
        }
        if videos:
            set_cache(cache_key, res, ttl=180)
        return res

    def _extract_video_urls(self, html_text):
        play_urls = []
        seen_urls = set()

        if BeautifulSoup:
            doc = BeautifulSoup(html_text, "html.parser")
            for d in doc.select(".dplayer[data-config], div[data-config]"):
                raw_conf = html.unescape(d.get("data-config") or "")
                url = ""
                try:
                    cfg = json.loads(raw_conf)
                    video_cfg = cfg.get("video") or {}
                    url = video_cfg.get("url") or ""
                except Exception:
                    m = re.search(r'"video"\s*:\s*\{.*?\"url\"\s*:\s*"([^"]+)"', raw_conf)
                    if m: url = m.group(1)
                if url:
                    clean_u = self._fix_url(url.replace(r"\/", "/").replace("\\", "").strip())
                    if clean_u and clean_u not in seen_urls:
                        seen_urls.add(clean_u)
                        play_urls.append(clean_u)

            for v in doc.select("video[src], source[src]"):
                u = (v.get("src") or "").strip()
                if u and not u.endswith((".jpg", ".png", ".gif")):
                    clean_u = self._fix_url(u)
                    if clean_u not in seen_urls:
                        seen_urls.add(clean_u)
                        play_urls.append(clean_u)

            for ifr in doc.select("iframe[src]"):
                u = (ifr.get("src") or "").strip()
                pm = re.search(r"[?&]url=([^&]+)", u)
                if pm:
                    clean_u = self._fix_url(unquote(pm.group(1)).strip())
                    if clean_u and clean_u not in seen_urls:
                        seen_urls.add(clean_u)
                        play_urls.append(clean_u)
                elif any(x in u.lower() for x in ["player", "play", "m3u8", "dp", "video"]):
                    clean_u = self._fix_url(u)
                    if clean_u not in seen_urls:
                        seen_urls.add(clean_u)
                        play_urls.append(clean_u)

        for m in re.finditer(r'video\s*:\s*\{[^\}]*?url\s*:\s*["\']([^"\']+)["\']', html_text, re.I | re.S):
            raw_u = m.group(1).replace(r"\/", "/").replace("\\", "").strip()
            if raw_u and not raw_u.endswith((".jpg", ".png", ".gif", ".css", ".js")):
                clean_u = self._fix_url(raw_u)
                if clean_u not in seen_urls:
                    seen_urls.add(clean_u)
                    play_urls.append(clean_u)

        if not play_urls:
            for direct_m in re.finditer(r'(https?://[^\s"\'<>]+\.(?:m3u8|mp4)[^\s"\'<>]*)', html_text, re.I):
                clean_u = direct_m.group(1).replace(r"\/", "/").replace("\\", "").strip()
                if clean_u not in seen_urls:
                    seen_urls.add(clean_u)
                    play_urls.append(clean_u)

        return play_urls

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        did = ids[0] if isinstance(ids, list) else ids
        url = self._fix_url(did)

        cache_key = f"detail_{url}"
        cached = get_cache(cache_key)
        if cached:
            return cached

        html_text = self._fetch(url)
        if not html_text:
            return {"list": []}

        # 1. 标题提取
        title = ""
        t_match = re.search(r'<h1[^>]*class=["\'][^"\']*(?:title|headline)[^"\']*["\'][^>]*>(.+?)</h1>', html_text, re.I | re.S)
        if t_match:
            title = re.sub(r'<[^>]+>', '', t_match.group(1)).strip()
        if not title:
            t_match = re.search(r'<h1[^>]*>(.+?)</h1>', html_text, re.I | re.S)
            if t_match:
                title = re.sub(r'<[^>]+>', '', t_match.group(1)).strip()
        if not title:
            t_match = re.search(r'<title>(.+?)</title>', html_text, re.I | re.S)
            if t_match:
                title = t_match.group(1).split("-")[0].split("_")[0].strip()

        # 2. 封面提取
        pic = ""
        og_match = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html_text, re.I)
        if not og_match:
            og_match = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', html_text, re.I)
        if og_match:
            pic = og_match.group(1).strip()
        if not pic:
            p_match = re.search(r'<(?:div|article|section)[^>]*class=["\'][^"\']*(?:content|post|entry)[^"\']*["\'][^>]*>.*?<img[^>]+(?:z-image-loader-url|data-xkrkllgl|data-original|data-src|src)=["\']([^"\']+)["\']', html_text, re.I | re.S)
            if p_match:
                pic = p_match.group(1).strip()

        # 3. 简介提取
        desc = ""
        desc_match = re.search(r'<meta[^>]+(?:name|property)=["\'](?:og:description|description)["\'][^>]+content=["\']([^"\']+)["\']', html_text, re.I)
        if not desc_match:
            desc_match = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:name|property)=["\'](?:og:description|description)["\']', html_text, re.I)
        if desc_match:
            desc = desc_match.group(1).strip()

        # 4. 发布时间
        date_str = ""
        d_match = re.search(r'(?:datePublished|pubdate|time)[^>]*>([0-9\-\s:]+)<', html_text, re.I)
        if d_match:
            date_str = d_match.group(1).strip()

        # 5. 精确提取视频流列表
        play_urls = self._extract_video_urls(html_text)

        # 6. 选集与线路组装
        episodes = []
        for idx, p_url in enumerate(play_urls, 1):
            ep_title = f"视频{idx}" if len(play_urls) > 1 else "在线播放"
            episodes.append(f"{ep_title}${p_url}")

        play_url_str = "#".join(episodes) if episodes else f"在线播放${url}"

        vod = {
            "vod_id": did,
            "vod_name": title or "911爆料",
            "vod_pic": self._fix_pic(pic),
            "vod_remarks": date_str,
            "vod_content": desc,
            "vod_play_from": "$$$".join(["911爆料", "备用解析"]),
            "vod_play_url": "$$$".join([play_url_str, play_url_str])
        }
        res = {"list": [vod]}
        set_cache(cache_key, res, ttl=300)
        return res

    def searchContent(self, key, quick=False, pg="1"):
        page = _page(pg)
        encoded_key = quote(str(key or '').strip())
        url = f"{self.host}/search/{encoded_key}/{page}/" if page > 1 else f"{self.host}/search/{encoded_key}/"
        html_text = self._fetch(url)
        videos = self._extract_cards(html_text)
        return {
            "list": videos,
            "page": page,
            "pagecount": page + 1 if len(videos) >= 10 else page,
            "limit": len(videos) if videos else 20,
            "total": 9999
        }

    def playerContent(self, flag, id, vipFlags=None):
        play_id = str(id or "").strip()
        if "$" in play_id:
            play_id = play_id.split("$")[-1].strip()
        play_id = unquote(play_id).replace(r'\/', '/').replace('\\', '').strip()

        if self.isVideoFormat(play_id):
            return {
                "parse": 0,
                "playUrl": "",
                "url": play_id,
                "header": {
                    "User-Agent": self.ua,
                    "Referer": self.host + "/"
                }
            }

        return {
            "parse": 1,
            "playUrl": "",
            "url": play_id,
            "header": {
                "User-Agent": self.ua,
                "Referer": self.host + "/"
            }
        }

    def localProxy(self, param):
        if not hasattr(self, "session") or not self.session:
            self.session = requests.Session()
            self.session.headers.update(self.headers)

        url = param.get("url") or param.get("img") or ""
        if isinstance(url, list):
            url = url[0] if url else ""
        if not url:
            return [400, "text/plain", b""]

        url = unquote(url).strip()
        if "loadBannerDirect" in url:
            m = re.search(r"loadBannerDirect\(['\"]([^'\"]+)['\"]", url)
            if m:
                url = m.group(1).strip()

        # 图片二进制内存缓存（快速滑动防抖，防止重复请求和重复 AES 解密）
        with self._img_lock:
            if url in self._img_cache:
                mime, c_data = self._img_cache[url]
                return [200, "image/" + mime, c_data]

        try:
            req_headers = {
                "Referer": self.host + "/",
                "User-Agent": self.ua
            }
            r = self.session.get(url, headers=req_headers, timeout=(2.5, 6), verify=False, allow_redirects=True)
            content = r.content

            is_encrypted = any(x in url for x in ["/xiao/", "/upload_01/xiao/", "/upload/upload/xiao/"])
            is_valid_magic = (content.startswith(b"\xff\xd8\xff") or content.startswith(b"\x89PNG") or content.startswith(b"GIF") or content[:4] == b"RIFF")
            
            if is_encrypted or not is_valid_magic:
                try:
                    dec = self._decrypt_image_bytes(content)
                    if dec and (dec.startswith(b"\xff\xd8\xff") or dec.startswith(b"\x89PNG") or dec.startswith(b"GIF") or dec[:4] == b"RIFF"):
                        content = dec
                except Exception:
                    pass

            mime = self._mime_from_bytes(content)

            with self._img_lock:
                if len(self._img_cache) > 200:
                    self._img_cache.clear()
                self._img_cache[url] = (mime, content)

            return [200, "image/" + mime, content]
        except Exception as e:
            return [500, "text/plain", str(e).encode("utf-8")]
