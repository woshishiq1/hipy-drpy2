# coding=utf-8
# //@name:快猫社区
# //@id:kuaimao
# //@version:2

import ast
import base64
import json
import re
import threading
import time
import uuid
from urllib.parse import quote, unquote, urljoin

import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

try:
    from base.spider import Spider as _BaseSpider
except ImportError:
    class _BaseSpider:
        def init(self, extend=""):
            pass

DEFAULT_HOST = "https://www.kma85.cc:8888"
API_DOMAINS = [
    "https://aiai.tplxbj.cn",
    "https://cici.tplxbj.cn",
    "https://zizi.tplxbj.cn",
    "https://fj.gqgoex.cn",
]
IMG_DOMAIN = "https://aiai.tplxbj.cn/"
SITE_ID = 61
AES_KEY = b"xFRLmCacUcKXbKwo"
PAGE_SIZE = 48
DEFAULT_CATEGORIES = (
    ("guo", "國產"),
    ("chuan", "傳媒"),
    ("you", "女优"),
    ("vip", "VIP专区"),
    ("rihan", "日韓"),
    ("zongyi", "解說"),
    ("dongman", "動漫"),
    ("oumei", "歐美"),
    ("AIhuanlian", "AI換臉"),
    ("tong", "同性"),
    ("sanpian", "三級片"),
)
DEFAULT_UA = (
    "Mozilla/5.0 (Linux; Android 12; Pixel 6) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
)
PLAYER_UA = DEFAULT_UA
NAV_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
    "Accept-Encoding": "gzip, deflate",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-User": "?1",
}

_MINOR_KEYWORDS = (
    "未成年", "幼女", "幼童", "儿童", "孩童", "小孩", "小学生",
    "中学生", "初中生", "高中生", "学生妹", "少女", "萝莉", "罗莉",
    "loli", "lolita", "teen", "teenager", "child", "kid",
    "baby", "infant", "minor", "underage", "schoolgirl",
    "未满18", "14岁", "15岁", "16岁", "17岁",
)


def _is_minor_text(text):
    if not text:
        return False
    lower = str(text).lower()
    return any(kw.lower() in lower for kw in _MINOR_KEYWORDS)


def _clean_text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _bounded_int(value, default, minimum, maximum):
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return default
    return min(max(number, minimum), maximum)


def _parse_config(value):
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, (list, tuple)):
        merged = {}
        for item in value:
            merged.update(_parse_config(item))
        return merged
    text = str(value or "").strip()
    if not text:
        return {}
    for loader in (json.loads, ast.literal_eval):
        try:
            data = loader(text)
            if isinstance(data, dict):
                return data
        except Exception:
            continue
    return {}


def _filter_minor_list(items):
    if not isinstance(items, list):
        return items
    result = []
    for item in items:
        if not isinstance(item, dict):
            result.append(item)
            continue
        check_fields = ("vod_name", "vod_sub", "vod_blurb", "vod_remarks",
                        "vod_actor", "vod_content", "name", "title", "actor_name")
        combined = " ".join(str(item.get(k, "")) for k in check_fields if item.get(k))
        if _is_minor_text(combined):
            continue
        result.append(item)
    return result


class Spider(_BaseSpider):
    name = "快猫社区"
    backend_parse = False

    def __init__(self):
        self.rawSite = DEFAULT_HOST
        self.siteUrl = DEFAULT_HOST
        self.HOST = DEFAULT_HOST
        self.apiDomain = API_DOMAINS[0]
        self.siteId = SITE_ID
        self.timeout = 20
        self.max_retries = 2
        self.cache_ttl = 60
        self._cache_lock = threading.RLock()
        self._page_cache = {}
        self._categories = self._default_categories()
        self.session = self._build_session()

    @staticmethod
    def _default_categories():
        return [{"type_id": tid, "type_name": name} for tid, name in DEFAULT_CATEGORIES]

    def getDependence(self):
        return ""

    def getName(self):
        return self.name

    def init(self, extend=""):
        config = _parse_config(extend)
        host = str(config.get("host") or config.get("site_url") or DEFAULT_HOST).strip().rstrip("/")
        if host and "://" not in host:
            host = "https://" + host
        self.rawSite = host or DEFAULT_HOST
        self.siteUrl = self.rawSite
        self.HOST = self.rawSite
        if config.get("api_domain"):
            self.apiDomain = str(config["api_domain"]).strip().rstrip("/")
        if config.get("site_id"):
            self.siteId = _bounded_int(config["site_id"], SITE_ID, 1, 999999)
        self.timeout = _bounded_int(config.get("timeout"), 20, 5, 40)
        self.cache_ttl = _bounded_int(config.get("cache_ttl"), 60, 0, 900)
        with self._cache_lock:
            self._page_cache = {}
        self._categories = self._default_categories()
        try:
            self._warmup()
        except Exception:
            pass
        return ""

    def _build_session(self):
        session = requests.Session()
        session.headers.update({
            "User-Agent": DEFAULT_UA,
            "Accept-Language": "zh-CN,zh;q=0.9",
        })
        return session

    def _warmup(self):
        try:
            app_data = self._fetch_app_data(self.rawSite + "/")
            if app_data:
                live = self._parse_classes(app_data)
                if live:
                    self._categories = live
        except Exception:
            pass

    def _cache_put(self, key, value):
        with self._cache_lock:
            self._page_cache[key] = (time.time(), value)
            if len(self._page_cache) > 24:
                oldest = sorted(self._page_cache.items(), key=lambda kv: kv[1][0])[:8]
                for stale_key, _ in oldest:
                    self._page_cache.pop(stale_key, None)

    def _cache_get(self, key):
        with self._cache_lock:
            hit = self._page_cache.get(key)
        if not hit:
            return None
        stamp, value = hit
        if time.time() - stamp > self.cache_ttl:
            with self._cache_lock:
                self._page_cache.pop(key, None)
            return None
        return value

    def fetch(self, url, referer=None, timeout=None, retries=None):
        if timeout is None:
            timeout = self.timeout
        if retries is None:
            retries = self.max_retries
        headers = dict(NAV_HEADERS)
        headers["User-Agent"] = DEFAULT_UA
        if referer:
            headers["Referer"] = referer
            headers["Sec-Fetch-Site"] = "same-origin"
        last_exc = None
        for attempt in range(max(retries, 0) + 1):
            try:
                resp = self.session.get(url, headers=headers, timeout=timeout,
                                        allow_redirects=True, verify=False)
                if resp.status_code == 429:
                    time.sleep(min(0.6 * (attempt + 1), 2.0))
                    continue
                if resp.status_code >= 500:
                    last_exc = ValueError("HTTP %s" % resp.status_code)
                    if attempt < retries:
                        time.sleep(min(0.6 * (attempt + 1), 2.0))
                        continue
                    raise last_exc
                resp.encoding = "utf-8"
                return resp.text, str(getattr(resp, "url", url))
            except Exception as exc:
                last_exc = exc
                if attempt < retries:
                    time.sleep(min(0.6 * (attempt + 1), 2.0))
                    continue
                break
        raise last_exc or RuntimeError("请求失败")

    def _aes_encrypt(self, data):
        if isinstance(data, (dict, list)):
            plaintext = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
        else:
            plaintext = str(data)
        iv = uuid.uuid4().bytes
        cipher = AES.new(AES_KEY, AES.MODE_CBC, iv)
        ct = cipher.encrypt(pad(plaintext.encode("utf-8"), AES.block_size))
        if len(ct) >= 32:
            custom = ct[:32] + iv + ct[32:]
        else:
            custom = ct + iv
        return base64.b64encode(custom).decode("ascii")

    def _aes_decrypt(self, encrypted_b64):
        if not encrypted_b64:
            return None
        try:
            raw = base64.b64decode(encrypted_b64)
        except Exception:
            return None
        if len(raw) < 48:
            iv_len = 16
            ct_len = len(raw) - iv_len
            if ct_len <= 0:
                return None
            ciphertext = raw[:ct_len]
            iv = raw[ct_len:]
        else:
            ciphertext = raw[:32] + raw[48:]
            iv = raw[32:48]
        try:
            cipher = AES.new(AES_KEY, AES.MODE_CBC, iv)
            decrypted = unpad(cipher.decrypt(ciphertext), AES.block_size)
            text = decrypted.decode("utf-8")
        except Exception:
            return None
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            return text

    @staticmethod
    def _decode_obfuscated_html(html):
        m = re.search(
            r"var _0x266e9=['\"]([^'\"]+)['\"][\s\S]*?var _0x486c2=(0x[0-9a-fA-F]+)",
            html,
        )
        if not m:
            return html
        encoded = m.group(1)
        xor_key = int(m.group(2), 16)
        try:
            raw = base64.b64decode(encoded)
            xored = bytes([b ^ xor_key for b in raw])
            return unquote(xored.decode("utf-8", errors="replace"))
        except Exception:
            return html

    @staticmethod
    def _extract_blob(html):
        m = re.search(r"new APP\.ActType\('([^']+)'\)", html)
        return m.group(1) if m else None

    def _fetch_app_data(self, url):
        cached = self._cache_get(url)
        if cached is not None:
            return cached
        html_text, _ = self.fetch(url, referer=self.rawSite + "/")
        decoded = self._decode_obfuscated_html(html_text)
        blob = self._extract_blob(decoded)
        if not blob:
            return None
        app_data = self._aes_decrypt(blob)
        if not isinstance(app_data, dict):
            return None
        self._cache_put(url, app_data)
        return app_data

    def _api_get(self, endpoint, params=None):
        if params is None:
            params = {}
        params.setdefault("uuid", uuid.uuid4().hex)
        params.setdefault("timestamp", int(time.time()))
        encrypted = self._aes_encrypt(params)
        last_exc = None
        domains = [self.apiDomain] + [d for d in API_DOMAINS if d != self.apiDomain]
        for domain in domains:
            try:
                resp = self.session.get(
                    domain + endpoint,
                    params={"params": encrypted},
                    headers={"User-Agent": DEFAULT_UA, "Accept": "application/json"},
                    timeout=self.timeout,
                    verify=False,
                )
                result = resp.json()
                if isinstance(result, dict) and isinstance(result.get("data"), str):
                    decrypted = self._aes_decrypt(result["data"])
                    if decrypted is not None:
                        result["data"] = decrypted
                self.apiDomain = domain
                return result
            except Exception as exc:
                last_exc = exc
                continue
        return {"code": -1, "msg": str(last_exc)}

    def _full_img(self, path):
        if not path:
            return ""
        if path.startswith("http"):
            return path
        if path.startswith("//"):
            return "https:" + path
        return IMG_DOMAIN + path.lstrip("/")

    def _parse_classes(self, app_data):
        classes = []
        seen = set()

        def collect(items):
            if not isinstance(items, list):
                return
            for item in items:
                if not isinstance(item, dict):
                    continue
                label = item.get("label")
                if not label:
                    jm = re.search(r"/type/([^/]+)/?", str(item.get("jumpurl") or ""))
                    if jm:
                        label = jm.group(1)
                name = _clean_text(item.get("name"))
                if not label or not name or label in seen:
                    continue
                if _is_minor_text(name):
                    continue
                classes.append({"type_id": str(label), "type_name": name})
                seen.add(label)

        collect(app_data.get("sub_menu", []))
        collect(app_data.get("menu", []))
        return classes

    def _ensure_classes(self):
        if self._categories:
            return self._categories
        live = []
        try:
            app_data = self._fetch_app_data(self.rawSite + "/")
            if app_data:
                live = self._parse_classes(app_data)
        except Exception:
            live = []
        self._categories = live if live else self._default_categories()
        return self._categories

    def _filters(self):
        return {}

    def _normalize_vod(self, item):
        if not isinstance(item, dict):
            return None

        def pick(*keys):
            for key in keys:
                value = item.get(key)
                if value not in (None, ""):
                    return value
            return ""

        vod_id = str(pick("vod_id", "actor_id", "id")).strip()
        if not vod_id:
            return None
        name = _clean_text(pick("vod_name", "actor_name", "name"))
        if not name or _is_minor_text(name):
            return None
        remarks = pick("vod_remarks", "actor_remarks", "remarks")
        content = pick("vod_content", "vod_blurb", "actor_blurb", "actor_content", "content")
        pic = pick("vod_pic", "actor_pic", "pic")
        return {
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": self._full_img(pic),
            "vod_remarks": _clean_text(remarks),
            "vod_year": str(pick("vod_year", "actor_birthday", "year")),
            "vod_area": _clean_text(pick("vod_area", "actor_area", "area")),
            "vod_lang": _clean_text(pick("vod_lang", "lang")),
            "vod_actor": _clean_text(pick("vod_actor", "actor_alias", "actor")),
            "vod_director": _clean_text(pick("vod_director", "director")),
            "vod_content": _clean_text(content),
        }

    def _list_from_appdata(self, app_data, page):
        if not app_data:
            return {"page": page, "pagecount": page, "limit": PAGE_SIZE, "total": 0, "list": []}
        raw_list = _filter_minor_list(app_data.get("list", []))
        vod_list = []
        for item in raw_list:
            vod = self._normalize_vod(item)
            if vod:
                vod_list.append(vod)
        total = _bounded_int(app_data.get("total"), len(vod_list), 0, 9999999)
        limit = _bounded_int(app_data.get("limit"), PAGE_SIZE, 1, 200)
        pagecount = (total + limit - 1) // limit if limit else page
        if vod_list and pagecount <= page:
            pagecount = page + 1
        return {"page": page, "pagecount": pagecount, "limit": limit, "total": total, "list": vod_list}

    def _empty_page(self, page):
        return {"page": page, "pagecount": page, "limit": PAGE_SIZE, "total": 0, "list": []}

    def homeContent(self, *args):
        try:
            classes = self._ensure_classes()
        except Exception:
            classes = []
        if not classes:
            classes = self._default_categories()
            self._categories = classes
        result = {"class": classes, "filters": self._filters(), "list": []}
        try:
            if classes:
                first = classes[0]["type_id"]
                result["list"] = self.categoryContent(first, 1, False, {}).get("list", [])
        except Exception:
            result["list"] = []
        return result

    def homeVideoContent(self, *args):
        try:
            classes = self._ensure_classes()
            if classes:
                return self.categoryContent(classes[0]["type_id"], 1, False, {})
            app_data = self._fetch_app_data(self.rawSite + "/")
            return self._list_from_appdata(app_data, 1)
        except Exception:
            return self._empty_page(1)

    def categoryContent(self, *args):
        tid = str(args[0] if len(args) > 0 else "").strip()
        pg = args[1] if len(args) > 1 else 1
        page = _bounded_int(pg, 1, 1, 100000)
        if not tid:
            return self._empty_page(page)
        extend = args[3] if len(args) > 3 else {}
        if not isinstance(extend, dict):
            extend = {}
        child = str(extend.get("child", ""))
        cls = str(extend.get("class", ""))
        sort = str(extend.get("sort", "1"))
        if page <= 1 and not child and not cls:
            url = "%s/type/%s/" % (self.rawSite, tid)
        else:
            url = "%s/type/%s/%s-%s-%s-%s" % (
                self.rawSite, tid, child, quote(cls), sort, page
            )
        try:
            app_data = self._fetch_app_data(url)
            return self._list_from_appdata(app_data, page)
        except Exception as exc:
            return {"page": page, "pagecount": page, "limit": PAGE_SIZE, "total": 1,
                    "list": [{"vod_id": "error:%s" % _clean_text(exc),
                              "vod_name": "访问受限", "vod_pic": "",
                              "vod_remarks": _clean_text(exc)}]}

    def searchContent(self, *args):
        key = args[0] if args else ""
        keyword = _clean_text(key)
        pg = 1
        if len(args) >= 3:
            pg = args[2]
        elif len(args) == 2 and isinstance(args[1], (int, str)) and not isinstance(args[1], bool):
            pg = args[1]
        page = _bounded_int(pg, 1, 1, 100000)
        if not keyword:
            return self._empty_page(page)
        url = "%s/search/%s/%s" % (self.rawSite, quote(keyword), page)
        if page <= 1:
            url = "%s/search/%s/" % (self.rawSite, quote(keyword))
        try:
            app_data = self._fetch_app_data(url)
            return self._list_from_appdata(app_data, page)
        except Exception:
            return self._empty_page(page)

    def detailContent(self, ids):
        id_list = list(ids) if isinstance(ids, (list, tuple)) else [ids]
        result_list = []
        for source_id in id_list:
            vid = str(source_id or "").strip()
            if vid.startswith("error:"):
                result_list.append(self._error_detail(vid[6:]))
                continue
            if not vid:
                result_list.append(self._error_detail("缺少标识"))
                continue
            vod_info = {}
            try:
                app_data = self._fetch_app_data("%s/vod/details/%s" % (self.rawSite, vid))
                if app_data:
                    vod_info = app_data.get("data") or {}
                    if not isinstance(vod_info, dict):
                        vod_info = {}
            except Exception:
                vod_info = {}
            play_data = None
            api_result = self._api_get("/v2/api/vodData", {"id": vid, "site": self.siteId})
            if api_result.get("code") == 1 and isinstance(api_result.get("data"), dict):
                play_data = api_result["data"]
            name = _clean_text(vod_info.get("vod_name") or vod_info.get("name"))
            if not name and play_data:
                name = _clean_text(play_data.get("vod_name"))
            if not name:
                name = vid
            if _is_minor_text(name):
                continue
            play_from, play_url = self._parse_play_sources(
                (play_data or {}).get("vod_play_url")
            )
            down_from, down_url = self._parse_play_sources(
                (play_data or {}).get("vod_down_url")
            )
            vod = {
                "vod_id": vid,
                "vod_name": name,
                "vod_pic": self._full_img(
                    vod_info.get("vod_pic") or vod_info.get("pic")
                    or ((play_data or {}).get("vod_pic") if play_data else "")
                ),
                "vod_remarks": _clean_text(vod_info.get("vod_remarks") or vod_info.get("remarks")),
                "vod_year": str(vod_info.get("vod_year") or ""),
                "vod_area": _clean_text(vod_info.get("vod_area")),
                "vod_lang": _clean_text(vod_info.get("vod_lang")),
                "vod_actor": _clean_text(vod_info.get("vod_actor")),
                "vod_director": _clean_text(vod_info.get("vod_director")),
                "vod_content": _clean_text(
                    vod_info.get("vod_content") or vod_info.get("vod_blurb") or vod_info.get("content")
                ),
                "vod_play_from": "$$$".join(play_from),
                "vod_play_url": "$$$".join(play_url),
                "vod_down_from": "$$$".join(down_from),
                "vod_down_url": "$$$".join(down_url),
            }
            result_list.append(vod)
        return {"list": result_list}

    def _parse_play_sources(self, sources):
        play_from = []
        play_url = []
        if not isinstance(sources, list):
            return play_from, play_url
        for idx, source in enumerate(sources):
            if not isinstance(source, dict):
                continue
            source_name = _clean_text(source.get("name")) or ("线路%d" % (idx + 1))
            eps = source.get("list") or []
            ep_list = []
            for ep in eps:
                if not isinstance(ep, dict):
                    continue
                ep_name = _clean_text(ep.get("name")) or "正片"
                ep_url = ep.get("h264") or ep.get("url") or ep.get("play_url") or ep.get("down_url") or ""
                if ep_url:
                    ep_list.append("%s$%s" % (ep_name, ep_url))
            if ep_list:
                play_from.append(source_name)
                play_url.append("#".join(ep_list))
        return play_from, play_url

    def _error_detail(self, message):
        return {
            "vod_id": "error", "vod_name": "详情加载失败", "vod_pic": "",
            "vod_remarks": message, "vod_year": "", "vod_area": "", "vod_lang": "",
            "vod_actor": "", "vod_director": "", "vod_content": message,
            "vod_play_from": "默认线路", "vod_play_url": "",
        }

    def playerContent(self, *args):
        play_url = str(args[1] if len(args) > 1 else "" or "")
        if play_url.startswith("error:"):
            return {"parse": 0, "jx": 0, "playUrl": "", "url": "", "header": {},
                    "msg": play_url[6:]}
        if not play_url:
            return {"parse": 0, "jx": 0, "playUrl": "", "url": "", "header": {},
                    "msg": "播放地址为空"}
        proxy_url = self._proxy_m3u8_url(play_url, self.rawSite + "/")
        return {
            "parse": 0,
            "jx": 0,
            "playUrl": "",
            "url": proxy_url,
            "header": {
                "User-Agent": PLAYER_UA,
                "Referer": self.rawSite + "/",
                "Origin": self.rawSite,
            },
            "format": "application/x-mpegURL",
            "contentType": "application/x-mpegURL",
        }

    def _proxy_m3u8_url(self, url, referer=""):
        try:
            if hasattr(self, "getProxyUrl"):
                return self.getProxyUrl() + "&type=m3u8&url=" + quote(url, safe="") + \
                       "&referer=" + quote(referer or self.rawSite, safe="")
        except Exception:
            pass
        return url

    def isVideoFormat(self, *args):
        url = str(args[0] if args else "").lower()
        return bool(url) and bool(re.search(r"\.(?:m3u8|mp4|mkv|flv|avi|ts)(?:[?#]|$)", url))

    def manualVideoCheck(self, *args):
        return False

    def action(self, action):
        return ""

    def localProxy(self, params):
        try:
            if not isinstance(params, dict):
                params = {}
            do = params.get("type") or params.get("action") or params.get("do")
            url = params.get("url", "")
            if do not in ("m3u8", "py") and not url:
                return [404, "text/plain", "not found"]
            referer = params.get("referer", "") or self.rawSite
            if isinstance(url, list):
                url = url[0]
            if isinstance(referer, list):
                referer = referer[0]
            url = unquote(url)
            referer = unquote(referer)
            text = self._get_m3u8_content(url, referer)
            if not text:
                return [502, "text/plain", "m3u8 download failed"]
            cleaned = self._clean_m3u8(text, url, referer)
            return [200, "application/vnd.apple.mpegurl", cleaned]
        except Exception as exc:
            return [500, "text/plain", "proxy error: %s" % exc]

    def _get_m3u8_content(self, url, referer):
        try:
            headers = {
                "User-Agent": PLAYER_UA,
                "Accept": "*/*",
                "Referer": referer,
                "Origin": self.rawSite,
            }
            resp = self.session.get(url, headers=headers, timeout=10, verify=False)
            if resp.status_code == 200:
                resp.encoding = "utf-8"
                return resp.text
        except Exception:
            pass
        return None

    def _is_ad_segment(self, uri, dur=0):
        u = (uri or "").strip().lower()
        if not u:
            return False
        ad_words = (
            "advertisement", "advert", "commercial", "sponsor", "preroll",
            "midroll", "postroll", "/ad/", "/ads/", "/gg/", "adv",
            "doubleclick", "googleads", "广告", "片头", "片尾", "贴片",
        )
        if any(w in u for w in ad_words):
            return True
        if dur and float(dur) <= 1.2 and not re.search(r"\d{4,}", u):
            return True
        return False

    def _clean_m3u8(self, text, base_url, referer):
        if not text:
            return text
        lines = text.splitlines()
        out = []
        pending_dur = 0.0
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("#EXTINF"):
                m = re.search(r":([\d.]+)", stripped)
                pending_dur = float(m.group(1)) if m else 0.0
                out.append(line)
                continue
            if stripped.startswith("#") or not stripped:
                out.append(line)
                continue
            if self._is_ad_segment(stripped, pending_dur):
                if out and out[-1].startswith("#EXTINF"):
                    out.pop()
                pending_dur = 0.0
                continue
            pending_dur = 0.0
            if not stripped.startswith("http") and base_url:
                stripped = urljoin(base_url, stripped)
            out.append(stripped)
        return "\n".join(out)

    def destroy(self):
        try:
            if self.session is not None:
                self.session.close()
        except Exception:
            pass
        return ""
