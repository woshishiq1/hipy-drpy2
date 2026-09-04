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
import html
import time
import socket
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

# ===== DNS 污染防护:DoH 域名钉扎 + 静态 IP 池兜底 =====
_PIN_MAP = {}
_PIN_INSTALLED = [False]
_POISON_IP_PREFIX = ('31.13.94.', '31.13.95.', '75.126.', '157.240.')
_PIN_CACHE_TTL = [1800]
_PIN_TIME = {}

# 实测可达的真实 IP 池:主站/播放/图片域名,设备侧 DNS 被劫持时绕过污染
_STATIC_IP_POOL = {
    '911bla.com': ['104.21.8.173', '172.67.157.201'],
    '911bl16.com': ['43.228.232.202', '43.230.113.205', '43.230.114.206', '43.228.233.203', '43.230.112.204'],
    '911bl.com': ['43.228.233.203', '43.228.232.202', '43.230.113.205', '43.230.114.206', '43.230.112.204'],
    'd10cq29fdobmmg.cloudfront.net': ['13.32.32.194', '13.32.32.49', '13.32.32.58', '13.32.32.169'],
    'catch.belwfufv.cc': ['3.175.214.82', '3.175.214.128', '3.175.214.30'],
    'carry.cyepzjnb.com': ['13.35.190.44', '13.35.190.5', '13.35.190.13', '13.35.190.85'],
    'admire.cyepzjnb.com': ['13.35.190.13', '13.35.190.85', '13.35.190.44', '13.35.190.5'],
    'op.etbjf.cn': ['122.188.57.53', '116.162.172.54', '180.178.234.61', '180.178.234.60', '180.178.234.59'],
    'as.oolrvd.cn': ['43.168.60.46', '43.152.14.61', '43.175.118.114', '43.175.120.27', '43.168.62.60'],
    'pic.uforxk.cn': ['36.155.170.198', '43.175.44.52', '43.174.128.40'],
}


def _install_pin():
    if _PIN_INSTALLED[0]:
        return
    _PIN_INSTALLED[0] = True
    _orig = socket.getaddrinfo

    def _pinned(host, port, *args, **kwargs):
        _ips = _PIN_MAP.get(host)
        if _ips:
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (ip, port)) for ip in _ips]
        return _orig(host, port, *args, **kwargs)

    socket.getaddrinfo = _pinned


def _ip_alive(ip, port=443, timeout=1.0):
    """快速 TCP 探测,过滤失效 IP。仅用于少量候选时挑可用项。"""
    try:
        socket.setdefaulttimeout(timeout)
        c = socket.create_connection((ip, port), timeout=timeout)
        c.close()
        return True
    except Exception:
        return False


def _doh_resolve(hostname):
    _doh_list = [
        'https://cloudflare-dns.com/dns-query',
        'https://dns.google/resolve',
        'https://doh.pub/dns-query',
        'https://dns.alidns.com/resolve',
    ]
    picked = []
    for _u in _doh_list:
        try:
            _r = requests.get(_u, params={'name': hostname, 'type': 'A'},
                              headers={'accept': 'application/dns-json'}, timeout=2, verify=False)
            _j = _r.json()
            for _a in _j.get('Answer', []):
                if _a.get('type') == 1 and _a.get('data'):
                    _d = _a['data']
                    if _d and not _d.startswith('0.') and not _d.startswith(_POISON_IP_PREFIX):
                        picked.append(_d)
            if picked:
                break
        except Exception:
            continue
    if len(picked) > 1:
        picked = [ip for ip in picked[:3] if _ip_alive(ip)] + picked[3:]
    return picked


def _doh_pin_domain(hostname, fallback=None):
    """国内 DNS 污染时,通过 DoH 获取真实 IP,并钉扎域名解析,绕过被劫持的系统 DNS。
    静态 IP 池优先且即时生效:有静态池的域名直接钉扎,DoH 仅作后台异步补充。"""
    try:
        if not hostname:
            return
        _install_pin()
        _now = time.time()
        if hostname in _PIN_MAP and _now - _PIN_TIME.get(hostname, 0) < _PIN_CACHE_TTL[0]:
            return
        picked = list(_STATIC_IP_POOL.get(hostname, []))
        if picked:
            _PIN_MAP[hostname] = picked
            _PIN_TIME[hostname] = _now
            _doh_last = _PIN_TIME.get(hostname + ":doh", 0)
            if _doh_last and _now - _doh_last > 600:
                _PIN_TIME[hostname + ":doh"] = _now
                try:
                    def _doh_refresh(_hn, _pk):
                        try:
                            _dh = _doh_resolve(_hn)
                            if _dh:
                                _PIN_MAP[_hn] = list(dict.fromkeys(_pk + _dh))
                        except Exception:
                            pass

                    threading.Thread(target=_doh_refresh, args=(hostname, picked), daemon=True).start()
                except Exception:
                    pass
            return
        picked = _doh_resolve(hostname)
        if fallback:
            picked = list(dict.fromkeys(list(fallback) + picked))
        if picked:
            _PIN_MAP[hostname] = picked
            _PIN_TIME[hostname] = _now
    except Exception:
        pass


def _pin_url_host(url):
    try:
        _m = re.match(r'https?://([^/:]+)', url or '')
        if _m:
            _doh_pin_domain(_m.group(1))
    except Exception:
        pass

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

    _IMG_ATTRS = ("z-image-loader-url", "data-xkrkllgl", "data-original", "data-src",
                  "data-lazy-src", "data-cover", "data-thumb", "data-echo", "data-bg", "src")
    _BAD_PIC_MARKS = ("placeholder", "loading", "blank", "1px", "default", "ads")

    AD_KEYWORDS = {
        "app", "911爆料app", "下载app", "官方推荐", "加入911", "章鱼导航", "欲洛降临",
        "七夕活动", "911暑期活动", "回家的路", "投稿方式", "常见问题", "广告商务",
        "所有标签", "关于我们", "官方tg群", "官方推特", "ai换脸脱衣", "广告", "商务合作"
    }

    # 网站主导航的分组分类 (主分类 -> 子分类), 与网页排序一致
    CATEGORY_GROUPS = [
        ("18+精选", [("mrds", "每日大赛"), ("hjsq", "海角社区"), ("aidj", "AI短剧"),
                     ("crfys", "午夜剧场"), ("dmhv", "动漫天堂"), ("sgpjs", "水果派解说")]),
        ("吃瓜爆料", [("rmgb", "独家爆料"), ("rlph", "黑料排行"), ("ssdbl", "热点吃瓜"),
                     ("xyss", "校园吃瓜")]),
        ("名人黑料", [("bgzq", "反差爆料"), ("whbl", "网红黑料"), ("mxhl", "明星吃瓜")]),
        ("猎奇社区", [("blqw", "猎奇吃瓜"), ("tksm", "偷窥泄密"), ("zksr", "SM专区"),
                     ("ntll", "男男女女")]),
        ("尤物品鉴", [("thjx", "探花经典"), ("fljq", "福利视频"), ("crlz", "网黄专辑"),
                     ("slec", "影视床戏"), ("kpzj", "看片专辑")]),
    ]

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
        self._last_detail_url = ""
        self._img_cache = {}
        self._img_lock = threading.Lock()
        self._group_subs = {gname: subs for gname, subs in self.CATEGORY_GROUPS}
        self.categories = self._build_categories()

    def _build_categories(self):
        cats = [{"type_id": "category/jrgb", "type_name": "今日大瓜"}]
        for gname, _ in self.CATEGORY_GROUPS:
            cats.append({"type_id": gname, "type_name": gname})
        return cats

    def getName(self):
        return "911爆料网"

    def _select_fastest_host(self):
        """并发探测各域名分类页,选出能解析出内容且延迟最低的主机,并缓存 15 分钟。
        仅靠 HEAD 延迟会选中返回验证页/跳转页的坏域名,这里直接验证内容有效性。"""
        cache_key = "fastest_911_host"
        cached = get_cache(cache_key)
        if cached:
            return cached

        probe_path = "/category/jrgb/"
        results = {}
        threads = []

        def test_host(u):
            try:
                _pin_url_host(u)
                st = time.time()
                r = requests.get(u + probe_path, headers=self.headers, timeout=3, allow_redirects=True, verify=False)
                cost = (time.time() - st) * 1000
                if r.status_code != 200:
                    results[u] = None
                    return
                if not self._looks_like_content(r.text):
                    results[u] = None
                    return
                cards = self._extract_cards(r.text)
                results[u] = (cost, len(cards)) if len(cards) >= 5 else None
            except Exception:
                results[u] = None

        for u in self.DOMAIN_POOL:
            t = threading.Thread(target=test_host, args=(u,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=3.5)

        valid = {k: v for k, v in results.items() if v}
        best = min(valid.items(), key=lambda x: x[1][0])[0] if valid else self.DOMAIN_POOL[0]
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
        _pin_url_host(self.host)
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

    @staticmethod
    def _clean_url(u):
        return str(u or "").replace(r"\/", "/").replace("\\", "").strip()

    def _proxy_base(self):
        try:
            f = getattr(self, "getProxyUrl", None)
            url = f() if callable(f) else ""
            if url:
                return url
        except Exception:
            pass
        return getattr(self, "t4_api", "")

    def _wrap_media_proxy(self, url):
        """TVBox 有 localProxy 代理时,把直连 m3u8/mp4 改为经代理地址,规避设备侧
        DNS 污染与防盗链;本地/无代理环境保持直链。"""
        try:
            if not url:
                return url
            if not re.search(r'\.(?:m3u8|mp4)(?:$|[?#])', str(url), re.I):
                return url
            b = self._proxy_base()
            if not b:
                return url
            _pin_url_host(url)
            sep = "&" if "?" in b else "?"
            return b + sep + "type=m3u8&url=" + quote(url, safe="")
        except Exception:
            return url

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

    @staticmethod
    def _looks_like_content(html_text):
        """粗略判断响应是否为真实内容页,用于跳过 JS 验证页/跳转页等无效响应。"""
        if not html_text or len(html_text) < 500:
            return False
        return bool(re.search(r"/(?:archives|article|post|detail)/\d+", html_text, re.I))

    def _ensure_session(self):
        if not hasattr(self, "session") or not self.session:
            self.session = requests.Session()
            self.session.headers.update(self.headers)
        return self.session

    def _req_headers(self):
        return {
            "Referer": self.host + "/",
            "User-Agent": self.ua
        }

    def _fetch(self, url, retry_backup=True):
        self._ensure_session()

        _pin_url_host(url)
        candidates = [url]
        if retry_backup:
            for b_host in self.DOMAIN_POOL:
                parsed = urlparse(url)
                if parsed.netloc and parsed.netloc != urlparse(b_host).netloc:
                    candidates.append(url.replace(f"{parsed.scheme}://{parsed.netloc}", b_host))

        # 双级超时优化：连接超时 2.5s，传输超时 5s；JS 验证页/跳转页会被判定为无效并继续尝试下一候选
        for target_url in candidates:
            try:
                r = self.session.get(target_url, headers=self.headers, timeout=(2.5, 5), verify=False)
                if r.status_code == 200:
                    r.encoding = "utf-8"
                    if self._looks_like_content(r.text):
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

    @staticmethod
    def _good_pic_val(val):
        v = str(val).strip()
        return bool(v) and not v.startswith("data:image") and not any(x in v.lower() for x in Spider._BAD_PIC_MARKS)

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
            for attr in self._IMG_ATTRS:
                vals = node.xpath(f'.//img/@{attr}')
                if vals and self._good_pic_val(vals[0]):
                    return str(vals[0]).strip()
        elif hasattr(node, "select_one"):
            img = node.select_one("img")
            if img:
                for attr in self._IMG_ATTRS:
                    val = img.get(attr, "")
                    if self._good_pic_val(val):
                        return val

        # 4. 匹配 CSS background-image
        bg_match = re.search(r'background-image\s*:\s*url\([\'"]?([^\'")]+)[\'"]?\)', raw_str, re.I)
        if bg_match and self._good_pic_val(bg_match.group(1)):
            return bg_match.group(1).strip()

        return ""

    def _is_valid_item(self, title, href, pic, raw_node=""):
        if not title or not href:
            return False
        clean_title = title.strip().lower()
        if clean_title in self.AD_KEYWORDS:
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

    def _make_card(self, href, title, remark, pic):
        return {
            "vod_id": self._fix_url(href),
            "vod_name": title[:100],
            "vod_pic": self._fix_pic(pic),
            "vod_remarks": remark
        }

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

                            videos.append(self._make_card(href, title, remark, pic))
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

                    videos.append(self._make_card(href, title, remark, pic))
                except Exception:
                    continue

        return videos

    def homeContent(self, filter=False):
        filters = {}
        for gname, subs in self.CATEGORY_GROUPS:
            filters[gname] = [{
                "key": "sub",
                "name": "子分类",
                "value": [{"n": "全部", "v": ""}] + [{"n": name, "v": sid} for sid, name in subs]
            }]
        return {
            "class": self.categories,
            "filters": filters
        }

    def homeVideoContent(self):
        # 直接复用 categoryContent 推荐第一页，利用内存缓存
        return self.categoryContent("category/jrgb", "1")

    def categoryContent(self, tid, pg, filter=False, extend=None):
        page = _page(pg)
        raw = str(tid or "category/jrgb").strip("/")
        group_name, sub_id = self._split_tid(raw)

        # 主分类页: 用户选择子分类筛选后切换到对应子分类, 默认聚合该组
        if group_name:
            sel = (extend or {}).get("sub") or ""
            if sel in dict(self._group_subs.get(group_name, [])):
                sub_id, group_name = sel, None
            else:
                cache_key = f"cate_group_{group_name}"
                cached = get_cache(cache_key)
                if cached:
                    return cached
                videos = self._fetch_group(group_name)
                res = {"list": videos, "page": page, "pagecount": page,
                       "limit": len(videos) if videos else 20, "total": len(videos)}
                if videos:
                    set_cache(cache_key, res, ttl=180)
                return res

        cache_key = f"cate_{sub_id}_{page}"
        cached = get_cache(cache_key)
        if cached:
            return cached

        url = f"{self.host}/category/{sub_id}/{page}/" if page > 1 else f"{self.host}/category/{sub_id}/"
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

    def _split_tid(self, raw):
        """把 type_id 拆成 (主分类名, 子分类id)。
        "18+精选" 为主分类聚合; "18+精选/aidj" / "category/jrgb" 均按子分类处理。"""
        parts = raw.split("/") if raw else []
        if len(parts) >= 2:
            return None, parts[-1]
        if raw in self._group_subs:
            return raw, None
        return None, raw or "jrgb"

    def _fetch_group(self, group_name):
        """聚合主分类下所有子分类第一页内容并去重。"""
        videos, seen = [], set()
        for sub_id, _ in self._group_subs.get(group_name, []):
            html_text = self._fetch(f"{self.host}/category/{sub_id}/")
            for v in self._extract_cards(html_text):
                if v["vod_id"] not in seen:
                    seen.add(v["vod_id"])
                    videos.append(v)
        return videos

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
                    clean_u = self._fix_url(self._clean_url(url))
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
            raw_u = self._clean_url(m.group(1))
            if raw_u and not raw_u.endswith((".jpg", ".png", ".gif", ".css", ".js")):
                clean_u = self._fix_url(raw_u)
                if clean_u not in seen_urls:
                    seen_urls.add(clean_u)
                    play_urls.append(clean_u)

        if not play_urls:
            for direct_m in re.finditer(r'(https?://[^\s"\'<>]+\.(?:m3u8|mp4)[^\s"\'<>]*)', html_text, re.I):
                clean_u = self._clean_url(direct_m.group(1))
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
        self._last_detail_url = url

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
            episodes.append(f"{ep_title}${self._wrap_media_proxy(p_url)}")

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
        play_id = self._clean_url(unquote(play_id))

        # 本地代理地址(/proxy? /local/)或直连视频格式直接透传,其余走解析
        passthrough = self.isVideoFormat(play_id) or (
            play_id.startswith("http") and ("/proxy?" in play_id or "/local/" in play_id)
        )
        return {
            "parse": 0 if passthrough else 1,
            "playUrl": "",
            "url": play_id,
            "header": {
                "User-Agent": self.ua,
                "Referer": self.host + "/"
            }
        }

    def _refresh_auth_url(self, old_url):
        """播放失败时重抓最近详情页,尝试拿到新 auth_key 的 m3u8(CDN 缓存刷新后生效)。"""
        try:
            if not self._last_detail_url:
                return ""
            html_text = self._fetch(self._last_detail_url)
            if not html_text:
                return ""
            parts = urlparse(old_url).path.rsplit("/", 1)
            vhash = parts[1].split(".")[0] if len(parts) >= 2 else ""
            for m in re.finditer(r'https?://[^\s"\'<>\\]+\.m3u8[^\s"\'<>\\]*', html_text):
                u = m.group(0).replace("\\", "").strip()
                if vhash and vhash not in u:
                    continue
                return u
        except Exception:
            return ""
        return ""

    def _media_proxy(self, pt, url):
        """m3u8/ts/key 播放代理:拉取远端 m3u8 并把分片/密钥改写为代理地址,
        规避设备侧 DNS 污染与防盗链。"""
        try:
            _pin_url_host(url)
            host = urlparse(url).hostname
            req_headers = self._req_headers()
            r = None
            for _try in range(3):
                try:
                    if _try == 0:
                        r = self.session.get(url, headers=req_headers, timeout=(2.5, 8), verify=False, allow_redirects=True)
                    else:
                        # 失败重试:轮换钉扎 IP 顺序,避开返回 404/400 的坏节点
                        if host and _PIN_MAP.get(host) and len(_PIN_MAP[host]) > 1:
                            _PIN_MAP[host].append(_PIN_MAP[host].pop(0))
                        r = requests.get(url, headers=req_headers, timeout=(2.5, 8), verify=False, allow_redirects=True)
                    if r.status_code == 200:
                        break
                except Exception:
                    r = None
                if _try < 2:
                    time.sleep(0.3)
            if r is None or r.status_code != 200:
                new_url = self._refresh_auth_url(url)
                if new_url and new_url != url:
                    try:
                        r = requests.get(new_url, headers=req_headers, timeout=(2.5, 8), verify=False, allow_redirects=True)
                    except Exception:
                        r = None
            if r is None or r.status_code != 200:
                return [404, "text/plain", "not found"]
            if pt == "m3u8":
                body = r.text
                b = self._proxy_base()
                if b:
                    sep = "&" if "?" in b else "?"
                    body = re.sub(r'(URI=")([^"]+)(")',
                                  lambda mm: mm.group(1) + b + sep + "type=key&url=" + quote(mm.group(2), safe="") + mm.group(3),
                                  body)
                    lines = []
                    for line in body.splitlines():
                        s = line.strip()
                        if s.startswith("http://") or s.startswith("https://"):
                            line = b + sep + "type=ts&url=" + quote(s, safe="")
                        lines.append(line)
                    body = "\n".join(lines)
                return [200, "application/vnd.apple.mpegurl;charset=UTF-8", body.encode("utf-8")]
            if pt == "key":
                return [200, "application/octet-stream", r.content]
            return [200, "video/mp2t", r.content]
        except Exception as e:
            return [500, "text/plain", str(e).encode("utf-8")]

    def localProxy(self, param):
        self._ensure_session()

        url = param.get("url") or param.get("img") or ""
        if isinstance(url, list):
            url = url[0] if url else ""
        if not url:
            return [400, "text/plain", b""]

        url = unquote(url).strip()
        _pin_url_host(url)
        _pt = param.get("type") or ""
        if _pt in ("m3u8", "ts", "key"):
            return self._media_proxy(_pt, url)
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
            req_headers = self._req_headers()
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
