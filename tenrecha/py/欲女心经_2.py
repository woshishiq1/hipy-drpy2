# coding=utf-8
# //@name:欲女心经
# //@id:yunvxj
# //@version:3
#
# 四壳契约（TVBox / 影视仓 / OK影视 / PickTV）：
#  - 独立 class Spider，不继承 base.spider
#  - 13 标准接口齐全且全部可调用
#  - homeContent: class + filters 为 dict
#  - 列表五键 page/pagecount/limit/total/list
#  - 详情多线路 $$$、多集 #、集名与地址 $
#  - playerContent header 为 dict、parse=0/jx=0
#  - init 预热网络通道
#  - Accept-Encoding 统一 gzip, deflate（不声明 br）
#  - 铁律11：内置 CLASSICAL_MAP + desensitize()，返回前对展示文本脱敏，未成年条目剔除
#  - 铁律15：playerContent.header 含 Referer+Origin 破防盗链
#  - 铁律17：广告预检 has_ads=True（score=46，命中特征：广告关键词3片段+极短时长2片段，第二个视频检测到广告，按保守处理全站启用广告清洗）
#    预检工具: m3u8_cleaner.detect_m3u8_ads(m3u8_url, referer)
#    预检地址1: https://video22.xsmzy2.com/video/20220406/51310de144892ab04709ff07d6364313/index.m3u8 -> has_ads=False, score=0
#    预检地址2: https://lsbbf11.com/20260905/lEuyZ7nJ/index.m3u8 -> has_ads=True, score=46
#    结论: 部分视频含广告，按has_ads=True保守处理，实现完整m3u8广告处理（localProxy+_clean_m3u8+_is_ad_segment）

import ast
import json
import os
import re
import ssl
import threading
import time
from urllib.parse import quote, urljoin, urlsplit

import requests
from requests.adapters import HTTPAdapter

try:
    from urllib3.poolmanager import PoolManager
    HAS_URLLIB3 = True
except Exception:
    PoolManager = None
    HAS_URLLIB3 = False

DEFAULT_HOST = "https://rzj.ynxj9.work"
PAGE_SIZE = 20
DEFAULT_UA = (
    "Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
)
PLAYER_UA = DEFAULT_UA

# 铁律15：默认反代配置路径（CF防护站点自动启用，普通站点默认直连）
_PROXY_CONFIG_PATHS = (
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "proxy_config.json"),
    os.path.expanduser("~/.super_doubao/super-doubao-runtime/workspace/.user_skills/tvbox-dev/assets/proxy_config.json"),
)
_DEFAULT_PROXY_FALLBACK = "https://xsz-shared-proxy.97471201.workers.dev"


def _load_default_proxy():
    """铁律15：读取默认反代地址，读取失败回退到内置地址"""
    for path in _PROXY_CONFIG_PATHS:
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                proxy = data.get("default_proxy", "").strip()
                if proxy:
                    return proxy
        except Exception:
            continue
    return _DEFAULT_PROXY_FALLBACK


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

SORTS = (
    ("new", "最新"),
    ("hot", "最热"),
)

# ========== 铁律11：敏感词古典映射脱敏表 ==========
CLASSICAL_MAP = {
    "成人": "风月", "色情": "风月", "情色": "春宫", "淫": "风月", "黄色": "春宫", "淫秽": "猥亵",
    "激情": "云雨", "做爱": "云雨", "性交": "交欢", "欲": "情思", "高潮": "云端",
    "偷拍": "窥帘", "偷窥": "窥帘", "乱伦": "禁脔", "强奸": "强占", "轮奸": "群辱",
    "迷奸": "迷占", "无码": "素纱", "有码": "遮面", "熟女": "徐娘",
    "萝莉": "豆蔻", "幼女": "玉蕊", "少女": "碧玉", "学生": "书生",
    "人妻": "罗敷", "少妇": "艳妇", "御姐": "玉人", "护士": "药女",
    "教师": "先生", "医生": "郎中", "警察": "捕快", "军人": "军爷",
    "秘书": "掌印", "老板": "东家", "丈夫": "夫君", "妻子": "拙荆",
    "情人": "相好", "小三": "外遇", "二奶": "外室", "出轨": "翻墙",
    "偷情": "私会", "通奸": "私通", "嫖娼": "寻花", "卖淫": "卖身",
    "妓女": "花娘", "性骚扰": "轻薄", "猥亵": "猥亵", "露阴": "曝玉",
    "咸猪手": "禄山爪", "丝袜": "丝履", "网袜": "网履", "内衣": "亵衣",
    "内裤": "亵裤", "情趣": "风月", "春药": "催情", "巨乳": "丰盈",
    "爆乳": "丰盈", "胸": "酥胸", "乳": "玉兔", "美乳": "玉兔",
    "臀": "玉臀", "屁股": "玉臀", "脚": "莲步", "玉足": "莲步",
    "腿": "玉腿", "裸体": "玉体", "全裸": "玉体", "半裸": "半褪",
    "走光": "泄春", "露点": "泄玉", "自慰": "弄玉", "口交": "含朱",
    "口活": "含朱", "肛交": "后庭", "屁眼": "后庭", "肛门": "后庭",
    "群交": "合卺", "乳交": "玉兔", "足交": "莲步", "车震": "车行",
    "野战": "郊合", "精液": "元阳", "精子": "元阳", "阴道": "幽处",
    "阴户": "幽处", "阴茎": "玉茎", "阳具": "玉茎", "SM": "调教",
    "制服": "官衣", "OL": "衙内", "空姐": "行云", "继母": "继室",
    "姐妹": "同根", "同学": "同窗", "邻居": "东邻", "处女": "处子",
    "初夜": "破瓜", "暴力": "杀伐", "血腥": "殷红", "恐怖": "幽冥",
    "赌博": "孤注", "毒品": "药石", "枪支": "火器", "刀具": "利刃",
    "国产": "华夏", "日韩": "东瀛", "欧美": "西洋", "港台": "香江",
    "直播": "云演", "自拍": "自照",
}

_MINOR_KEYWORDS = (
    "豆蔻", "玉蕊", "碧玉", "书生", "稚子", "未成年", "teen", "loli",
    "schoolgirl",
)


def desensitize(text):
    if text is None:
        return ""
    result = str(text)
    for key in sorted(CLASSICAL_MAP.keys(), key=len, reverse=True):
        if key in result:
            result = result.replace(key, CLASSICAL_MAP[key])
    lower = result.lower()
    for kw in _MINOR_KEYWORDS:
        if kw.lower() in lower:
            return ""
    return result


def _is_minor_content(text):
    if not text:
        return False
    lower = str(text).lower()
    for kw in _MINOR_KEYWORDS:
        if kw.lower() in lower:
            return True
    return False


def _sanitize_vod(vod):
    if not isinstance(vod, dict):
        return vod
    name = vod.get("vod_name", "")
    remarks = vod.get("vod_remarks", "")
    content = vod.get("vod_content", "")
    if _is_minor_content(name) or _is_minor_content(remarks) or _is_minor_content(content):
        return None
    vod["vod_name"] = desensitize(name)
    if vod.get("vod_remarks") is not None:
        vod["vod_remarks"] = desensitize(remarks)
    if vod.get("vod_content") is not None:
        vod["vod_content"] = desensitize(content)
    if not vod["vod_name"]:
        return None
    return vod


def _sanitize_list(vod_list):
    if not isinstance(vod_list, list):
        return vod_list
    result = []
    for item in vod_list:
        cleaned = _sanitize_vod(item)
        if cleaned is not None:
            result.append(cleaned)
    return result


def _sanitize_classes(classes):
    if not isinstance(classes, list):
        return classes
    result = []
    for cat in classes:
        if not isinstance(cat, dict):
            result.append(cat)
            continue
        name = cat.get("type_name", "")
        if _is_minor_content(name):
            continue
        cat["type_name"] = desensitize(name)
        if cat["type_name"]:
            result.append(cat)
    return result


def _clean_text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _bool(value, default=False):
    if isinstance(value, bool):
        return value
    if value is None or value == "":
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on", "y")


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


def _normalize_origin(value):
    text = str(value or DEFAULT_HOST).strip().rstrip("/")
    if text and "://" not in text:
        text = "https://" + text
    try:
        parsed = urlsplit(text)
    except Exception:
        return DEFAULT_HOST
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return DEFAULT_HOST
    return parsed.scheme + "://" + parsed.netloc


class TLSAdapter(HTTPAdapter):
    def __init__(self, ciphers=None, **kwargs):
        self._ciphers = ciphers
        super(TLSAdapter, self).__init__(**kwargs)

    def _build_context(self):
        context = ssl.create_default_context()
        if self._ciphers:
            try:
                context.set_ciphers(self._ciphers)
            except Exception:
                pass
        try:
            context.minimum_version = ssl.TLSVersion.TLSv1_2
        except Exception:
            pass
        try:
            context.set_alpn_protocols(["h2", "http/1.1"])
        except Exception:
            pass
        return context

    def init_poolmanager(self, connections, maxsize, block=False, **kwargs):
        context = self._build_context()
        if HAS_URLLIB3 and PoolManager is not None:
            kwargs["ssl_context"] = context
            self.poolmanager = PoolManager(num_pools=connections, maxsize=maxsize, block=block, **kwargs)
        else:
            super(TLSAdapter, self).init_poolmanager(connections, maxsize, block=block, **kwargs)


def build_session(user_agent=None, cookie=""):
    session = requests.Session()
    try:
        session.headers.clear()
    except Exception:
        pass
    headers = dict(NAV_HEADERS)
    headers["User-Agent"] = user_agent or DEFAULT_UA
    if cookie:
        headers["Cookie"] = cookie
    session.headers.update(headers)
    try:
        session.mount("https://", TLSAdapter())
    except Exception:
        pass
    return session


class Spider:
    name = "欲女心经"
    backend_parse = False
    category_mode = False

    def __init__(self):
        self.host = DEFAULT_HOST
        self.rawSite = DEFAULT_HOST
        self.siteUrl = DEFAULT_HOST
        self.HOST = DEFAULT_HOST
        self.timeout = 15
        self.cookie = ""
        self.max_retries = 2
        self._warmed = False
        self._page_cache = {}
        self._cache_lock = threading.RLock()
        self.cache_ttl = 60
        self.warmup_enabled = True
        self._categories = []
        self._default_proxy = _load_default_proxy()
        self._use_proxy = False
        self._ad_check_cache = {}
        self.session = build_session(DEFAULT_UA, self.cookie)

    def getDependence(self):
        return ""

    def getName(self):
        return self.name

    def init(self, extend=""):
        config = _parse_config(extend)
        self.rawSite = _normalize_origin(config.get("host") or config.get("siteUrl") or DEFAULT_HOST)
        direct = _bool(config.get("direct"), True)
        ext_proxy = str(config.get("proxy") or "").strip()
        if ext_proxy:
            self._use_proxy = True
            self.siteUrl = _normalize_origin(ext_proxy)
        elif not direct:
            self._use_proxy = True
            self.siteUrl = self._default_proxy
        else:
            self._use_proxy = False
            self.siteUrl = self.rawSite
        self.host = self.siteUrl
        self.HOST = self.siteUrl
        self.timeout = _bounded_int(config.get("timeout"), 15, 5, 40)
        self.cookie = str(config.get("cookie") or "").strip()
        self.max_retries = _bounded_int(config.get("max_retries"), 2, 0, 6)
        self.cache_ttl = _bounded_int(config.get("cache_ttl"), 60, 0, 900)
        self.warmup_enabled = _bool(config.get("warmup"), True)
        self._categories = []
        self._warmed = False
        with self._cache_lock:
            self._page_cache = {}
        self.session = build_session(DEFAULT_UA, self.cookie)
        try:
            self._warmup()
        except Exception:
            pass
        return ""

    def _warmup(self):
        if self._warmed or not self.warmup_enabled:
            return
        self._warmed = True
        try:
            url = self.host + "/ynxj/"
            html_text, _ = self._fetch_url(url, referer=self.rawSite + "/", timeout=min(self.timeout, 12), retries=0)
            self._cache_put(url, (html_text, url))
            self._categories = self._parse_categories(html_text)
        except Exception:
            pass

    def _request_headers(self, referer):
        headers = dict(NAV_HEADERS)
        headers["User-Agent"] = DEFAULT_UA
        if referer:
            headers["Referer"] = referer
            headers["Sec-Fetch-Site"] = "same-origin"
        if self.cookie:
            headers["Cookie"] = self.cookie
        return headers

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

    def _fetch_direct(self, url, referer, timeout, retries, post_data=None):
        headers = self._request_headers(referer)
        last_exc = None
        for attempt in range(max(retries, 0) + 1):
            try:
                if post_data is not None:
                    headers["Content-Type"] = "application/x-www-form-urlencoded"
                    response = self.session.post(url, data=post_data, headers=headers, timeout=timeout, allow_redirects=True)
                else:
                    response = self.session.get(url, headers=headers, timeout=timeout, allow_redirects=True)
                status = int(getattr(response, "status_code", 0) or 0)
                if status >= 400:
                    raise ValueError("HTTP %s" % status)
                text = getattr(response, "text", "") or ""
                if not text.strip():
                    raise ValueError("空响应")
                return text, str(getattr(response, "url", url))
            except Exception as exc:
                last_exc = exc
                if attempt < retries:
                    time.sleep(min(0.6 * (attempt + 1), 2.0))
                    continue
                break
        raise last_exc or RuntimeError("请求失败")

    def _fetch_url(self, url, referer=None, timeout=None, retries=None, post_data=None):
        if timeout is None:
            timeout = self.timeout
        if retries is None:
            retries = self.max_retries
        cache_key = url + ("_post" if post_data else "")
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        result = self._fetch_direct(url, referer, timeout, retries, post_data=post_data)
        self._cache_put(cache_key, result)
        return result

    def isVideoFormat(self, url):
        text = str(url or "").lower()
        return bool(text) and bool(re.search(r"\.(?:m3u8|mp4|mkv|flv|avi|ts)(?:[?#]|$)", text))

    def manualVideoCheck(self):
        return False

    def action(self, action):
        return ""

    def destroy(self):
        try:
            if self.session is not None:
                self.session.close()
        except Exception:
            pass
        return ""

    # ==================== 针对目标网站的解析方法 ====================

    def _parse_categories(self, html_text):
        classes = []
        seen = set()
        for m in re.finditer(
            r'<a[^>]*href="/vodtype/(\d+)\.html"[^>]*>\s*<span>([^<]+)</span>',
            str(html_text or "")
        ):
            tid = m.group(1)
            tname = m.group(2).strip()
            if tid in seen or not tname:
                continue
            seen.add(tid)
            classes.append({"type_id": tid, "type_name": tname})
        return classes

    def _ensure_categories(self):
        if self._categories:
            return self._categories
        try:
            html_text, _ = self._fetch_url(self.host + "/ynxj/", referer=self.rawSite + "/")
            self._categories = self._parse_categories(html_text)
        except Exception:
            self._categories = []
        return self._categories

    def _filters(self):
        options = [{"n": label, "v": value} for value, label in SORTS]
        cats = self._ensure_categories()
        return {
            cat["type_id"]: [{"key": "sort", "name": "排序", "init": "", "value": options}]
            for cat in cats
        }

    def homeContent(self, filter=False):
        cats = _sanitize_classes(self._ensure_categories())
        result = {
            "class": cats,
            "filters": self._filters(),
            "list": [],
        }
        try:
            html_text, _ = self._fetch_url(self.host + "/ynxj/", referer=self.rawSite + "/")
            result["list"] = _sanitize_list(self._parse_list(html_text))
        except Exception:
            result["list"] = []
        return result

    def homeVideoContent(self):
        try:
            html_text, _ = self._fetch_url(self.host + "/ynxj/", referer=self.rawSite + "/")
            items = _sanitize_list(self._parse_list(html_text))
        except Exception:
            items = []
        return {"page": 1, "pagecount": 1, "limit": PAGE_SIZE, "total": len(items), "list": items}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        page = _bounded_int(pg, 1, 1, 100000)
        slug = str(tid or "").strip()
        if not slug:
            return self._empty_page(page)
        if page == 1:
            url = self.host + "/vodtype/" + slug + ".html"
        else:
            url = self.host + "/vodtype/" + slug + "-" + str(page) + ".html"
        try:
            html_text, _ = self._fetch_url(url, referer=self.rawSite + "/")
            items = self._parse_list(html_text)
            pagecount = self._parse_pagecount(html_text, page, slug)
            limit = len(items) or PAGE_SIZE
            total = pagecount * limit if pagecount > 0 else 0
            return {"page": page, "pagecount": pagecount, "limit": limit, "total": total, "list": _sanitize_list(items)}
        except Exception:
            return self._empty_page(page)

    def searchContent(self, key, quick=False, pg="1"):
        keyword = _clean_text(key)
        page = _bounded_int(pg, 1, 1, 100000)
        if not keyword:
            return self._empty_page(page)
        url = self.host + "/s/index.html"
        try:
            html_text, _ = self._fetch_url(url, referer=self.rawSite + "/", post_data={"wd": keyword})
            items = self._parse_list(html_text)
            return {"page": page, "pagecount": page, "limit": len(items) or PAGE_SIZE, "total": len(items), "list": _sanitize_list(items)}
        except Exception:
            return self._empty_page(page)

    def _empty_page(self, page):
        return {"page": page, "pagecount": page, "limit": PAGE_SIZE, "total": 0, "list": []}

    def _parse_list(self, html_text):
        items = []
        seen = set()
        text = str(html_text or "")
        # 按视频卡片完整匹配：封面图链接(vod_id+pic) + 标题(name)，三者一一对应不错位
        # 卡片结构: <a href="/ID.html" class="videopic" style="background: url(PIC)...">...</a><div class="title">...<a>NAME</a></div>
        pattern = (
            r'<a[^>]*href="/(\d+)\.html"[^>]*class="videopic[^"]*"[^>]*'
            r'style="[^"]*url\(["\']?([^"\'\)]+)["\']?\)[^"]*"[^>]*>'
            r'.*?<div class="title">.*?<a[^>]*>([^<]+)</a>'
        )
        for m in re.finditer(pattern, text, re.DOTALL):
            vid = m.group(1).strip()
            pic = m.group(2).strip()
            name = m.group(3).strip()
            if not vid or vid in seen:
                continue
            if not name:
                continue
            seen.add(vid)
            items.append({
                "vod_id": vid,
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": "",
            })
        # 兜底：如果上面的精确匹配没拿到（模板改版），用宽松匹配按位置配对
        if not items:
            covers = []
            for cm in re.finditer(
                r'<a[^>]*href="/(\d+)\.html"[^>]*class="videopic[^"]*"[^>]*style="[^"]*url\(["\']?([^"\'\)]+)["\']?\)',
                text
            ):
                covers.append((cm.group(1), cm.group(2), cm.end()))
            for vid, pic, pos in covers:
                if vid in seen:
                    continue
                name = ""
                tail = text[pos:pos + 1000]
                nm = re.search(r'<div class="title">.*?<a[^>]*>([^<]+)</a>', tail, re.DOTALL)
                if nm:
                    name = nm.group(1).strip()
                if not name:
                    continue
                seen.add(vid)
                items.append({
                    "vod_id": vid,
                    "vod_name": name,
                    "vod_pic": pic,
                    "vod_remarks": "",
                })
        return items

    @staticmethod
    def _parse_pagecount(html_text, current, tid):
        pages = [current]
        pattern = r'/vodtype/' + re.escape(str(tid)) + r'-(?:(\d+))\.html'
        for m in re.finditer(pattern, str(html_text or "")):
            pages.append(_bounded_int(m.group(1), current, 1, 100000))
        return max(pages)

    def detailContent(self, ids):
        id_list = list(ids) if isinstance(ids, (list, tuple)) else [ids]
        result_list = []
        for source_id in id_list:
            vid = str(source_id or "").strip()
            if not vid or not re.search(r'\d', vid):
                continue
            detail_url = self.host + "/" + vid + ".html"
            try:
                html_text, _ = self._fetch_url(detail_url, referer=self.rawSite + "/")
            except Exception:
                continue
            vod = self._parse_detail(html_text, vid)
            if vod:
                cleaned = _sanitize_vod(vod)
                if cleaned is not None:
                    result_list.append(cleaned)
        return {"list": result_list}

    def _parse_detail(self, html_text, vid):
        text = str(html_text or "")
        name = ""
        m = re.search(r'<h1[^>]*>([^<]+)</h1>', text)
        if m:
            name = m.group(1).strip()
        if not name:
            m = re.search(r'<title>([^<]+)</title>', text)
            if m:
                name = m.group(1).split("-")[0].strip()
        if not name:
            name = vid
        pic = ""
        m = re.search(r'background(?:-image)?:\s*url\(["\']?([^"\'\)]+)["\']?\)', text)
        if m:
            pic = m.group(1)
        play_url = ""
        m = re.search(r"const\s+rawUrl\s*=\s*['\"]([^'\"]+)['\"]", text)
        if m:
            play_url = m.group(1)
        if not play_url:
            m = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', text)
            if m:
                play_url = m.group(1)
        content = ""
        m = re.search(r'class="[^"]*(?:content|desc|intro|detail)[^"]*"[^>]*>(.*?)</', text, re.DOTALL)
        if m:
            content = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        if not content:
            content = name
        return {
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": pic,
            "vod_remarks": "",
            "vod_content": content,
            "vod_play_from": "欲女心经",
            "vod_play_url": ("正片$" + play_url) if play_url else "",
        }

    def playerContent(self, flag, id, vipFlags=None):
        play_url = str(id or "")
        if not play_url:
            return {"parse": 0, "jx": 0, "playUrl": "", "url": "", "header": {}, "msg": "空播放地址"}
        # 自适应清洗：按CDN域名预检，有广告才走代理清洗，无广告直连（避免清洗过度导致无法播放）
        if self._check_domain_ads(play_url):
            final_url = self._proxy_m3u8_url(play_url, self.rawSite + "/")
        else:
            final_url = play_url
        return {
            "parse": 0,
            "jx": 0,
            "playUrl": "",
            "url": final_url,
            "header": {
                "User-Agent": PLAYER_UA,
                "Referer": self.rawSite + "/",
                "Origin": self.rawSite,
            },
            "format": "application/x-mpegURL",
            "contentType": "application/x-mpegURL",
        }

    # ==================== m3u8广告清洗 + 本地代理（铁律8·广告拦截组合功能） ====================

    def _sanitize_m3u8_url(self, url):
        if not url:
            return url
        from urllib.parse import unquote
        url = unquote(url)
        url = re.sub(r'&[Cc]over=.*', '', url)
        url = re.sub(r'&[Pp]oster=.*', '', url)
        url = re.sub(r'&[Tt]humb=.*', '', url)
        url = re.sub(r'&[Pp]ic=.*', '', url)
        url = url.rstrip('&?')
        return url

    def _proxy_m3u8_url(self, url, referer=''):
        """生成m3u8代理地址：优先用壳的getProxyUrl()，否则返回原地址（localProxy负责清洗）"""
        try:
            if hasattr(self, 'getProxyUrl'):
                return self.getProxyUrl() + '&type=m3u8&url=' + quote(url, safe='') + '&referer=' + quote(referer or self.rawSite, safe='')
        except Exception:
            pass
        return url

    def _check_domain_ads(self, m3u8_url):
        """按CDN域名轻量预检广告，同一域名只测一次缓存结果，无广告域名直连不清洗"""
        try:
            domain = urlsplit(m3u8_url).netloc.lower()
        except Exception:
            return True
        if not domain:
            return True
        if domain in self._ad_check_cache:
            return self._ad_check_cache[domain]
        has_ads = True
        try:
            from m3u8_cleaner import detect_m3u8_ads
            result = detect_m3u8_ads(m3u8_url, self.rawSite + "/")
            has_ads = bool(result.get('has_ads', False))
        except Exception:
            has_ads = True
        self._ad_check_cache[domain] = has_ads
        return has_ads

    def localProxy(self, params):
        """本地代理入口：接收m3u8请求 → 下载 → 广告清洗 → 返回干净m3u8（铁律8：非空壳）"""
        try:
            if not isinstance(params, dict):
                params = {}
            do = params.get('type') or params.get('action') or params.get('do')
            url = params.get('url', '')
            if do not in ['m3u8', 'py'] and not url:
                return [404, "text/plain", "not found"]
            referer = params.get('referer', '') or self.rawSite
            if isinstance(url, list):
                url = url[0]
            if isinstance(referer, list):
                referer = referer[0]
            from urllib.parse import unquote
            url = unquote(url)
            referer = unquote(referer)
            text = self._get_m3u8_content(url, referer)
            if not text:
                return [502, "text/plain", "m3u8 download failed"]
            # 统计原始ts片段数（用于清洗后校验，防止洗过头）
            raw_seg_count = self._count_ts_segments(text)
            # 优先使用独立m3u8_cleaner模块（最新六重+CUE广告检测），失败回退内嵌版
            try:
                from m3u8_cleaner import M3U8Cleaner
                _cleaner = M3U8Cleaner(raw_site=referer or self.rawSite)
                cleaned = _cleaner.clean(text, url, referer)
            except Exception:
                try:
                    cleaned = self._clean_m3u8(text, url, referer)
                except Exception:
                    cleaned = text
            # 【关键保护】清洗后校验：如果片段数删太多（<30%），认为清洗过度，回退原始m3u8
            clean_seg_count = self._count_ts_segments(cleaned)
            if raw_seg_count > 0 and clean_seg_count < raw_seg_count * 0.3:
                return [200, "application/vnd.apple.mpegurl", text]
            # 清洗后片段数正常，返回清洗版
            return [200, "application/vnd.apple.mpegurl", cleaned]
        except Exception:
            # 任何异常都回退原始m3u8，宁可有广告也不能影响播放
            try:
                if text:
                    return [200, "application/vnd.apple.mpegurl", text]
            except Exception:
                pass
            return [500, "text/plain", "proxy error"]

    def _get_m3u8_content(self, url, referer):
        """带防盗链header下载m3u8文件"""
        try:
            headers = {
                'User-Agent': PLAYER_UA,
                'Accept': '*/*',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Referer': referer,
                'Origin': self.rawSite,
                'Connection': 'keep-alive',
            }
            resp = self.session.get(url, headers=headers, timeout=10, allow_redirects=True)
            if resp.status_code == 200:
                return resp.text
            return None
        except Exception:
            return None

    @staticmethod
    def _count_ts_segments(m3u8_text):
        """统计m3u8中的ts片段数（用于清洗后校验，防止清洗过度）"""
        count = 0
        for line in str(m3u8_text or '').split('\n'):
            line = line.strip()
            if line and not line.startswith('#') and '.m3u8' not in line.lower():
                count += 1
        return count

    def _is_ad_segment(self, uri, dur=0, prev_tags=None):
        """广告片段识别：关键词匹配 + 短时长判定（铁律8：广告拦截五重识别之一）"""
        u = (uri or '').strip().lower()
        if not u:
            return False
        ad_words = [
            'advertisement', 'advertise', 'advert', 'commercial', 'sponsor', 'sponsorship',
            'preroll', 'pre-roll', 'pre_roll', 'midroll', 'mid-roll', 'postroll', 'post-roll',
            'banner', 'banners', 'popup', 'pop-up', 'interstitial', 'overlay', 'splash',
            'bumper', 'stinger', 'vast', 'vpaid', 'vmap',
            'doubleclick', 'googleads', 'googlesyndication', 'googletag', 'adsense', 'admob',
            'adx', 'adnetwork', 'adserving', 'ad-serving', 'adserver', 'ad-server',
            'inmobi', 'unityads', 'applovin', 'ironsource', 'vungle', 'chartboost', 'tapjoy',
            'mintegral', 'pangle', 'bytedance', 'tiktokads', 'kuaishou', 'ks-ad',
            'tracking', 'tracker', 'beacon', 'pixel', 'analytics', 'statistic',
            'leaderboard', 'skyscraper', 'rectangle', 'filler',
            '广告', '片头', '片尾', '贴片', '赞助商', '赞助', '推广', '硬广',
            '前贴', '中插', '后贴', '角标', '广告位', '广告片', '广告段', '广告视频',
            '广告素材', '弹窗', '悬浮', '开屏', '插屏', '激励视频', '激励广告',
            'guanggao', 'ggao', 'ggvideo', 'ggmedia',
            '/ad/', '/ads/', '/adv/', '/adver/', '/gg/', '/gga/', '/ggb/', '/ggc/', '/ggd/',
            '_ad.', '.ad/', '_ads.', '_adv.', '_gg.', 'gg_', '_gg', '/gg', 'gg.',
            '/ad_', '/ads_', '/adv_', '/sponsor/', '/banner/', '/promo/', '/commercial/',
            '/preroll/', '/midroll/', '/postroll/', '/popup/', '/interstitial/', '/overlay/',
            '/splash/', '/bumper/', '/vast/', '/vpaid/', '/adnetwork/', '/adserving/',
            '/doubleclick/', '/googleads/', '/googlesyndication/', '/adsense/', '/admob/',
            '/tracking/', '/tracker/', '/beacon/', '/pixel/', '/analytics/',
        ]
        if any(w in u for w in ad_words):
            return True
        try:
            if 0 < float(dur) <= 1.2:
                return True
        except Exception:
            pass
        return False

    def _parse_m3u8_segments(self, text):
        """m3u8解析器：拆出header/segments/tail"""
        lines = [x.strip() for x in (text or '').replace('\r', '').split('\n') if x.strip()]
        header, segments, tail = [], [], []
        pending_tags = []
        media_sequence = 0
        target_duration = 0
        started = False
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.startswith('#EXT-X-MEDIA-SEQUENCE'):
                try:
                    media_sequence = int(line.split(':', 1)[1])
                except Exception:
                    pass
                if not started:
                    header.append(line)
                else:
                    pending_tags.append(line)
            elif line.startswith('#EXT-X-TARGETDURATION'):
                try:
                    target_duration = float(line.split(':', 1)[1])
                except Exception:
                    pass
                if not started:
                    header.append(line)
                else:
                    pending_tags.append(line)
            elif line.startswith('#EXTINF'):
                started = True
                dur = target_duration or 3.0
                m = re.search(r'#EXTINF:\s*([\d.]+)', line)
                if m:
                    try:
                        dur = float(m.group(1))
                    except Exception:
                        pass
                tags = pending_tags + [line]
                pending_tags = []
                uri = ''
                j = i + 1
                while j < len(lines):
                    if lines[j].startswith('#'):
                        tags.append(lines[j])
                        j += 1
                        continue
                    uri = lines[j]
                    break
                if uri:
                    segments.append({'tags': tags, 'uri': uri, 'dur': dur})
                    i = j
                else:
                    tail.extend(tags)
            elif line.startswith('#EXT-X-ENDLIST'):
                tail.append(line)
            elif line.startswith('#'):
                if started:
                    pending_tags.append(line)
                else:
                    header.append(line)
            else:
                started = True
                dur = target_duration or 3.0
                segments.append({'tags': pending_tags, 'uri': line, 'dur': dur})
                pending_tags = []
            i += 1
        return header, segments, tail, media_sequence, target_duration

    def _segment_host_key(self, uri, base_url):
        try:
            full = urljoin(base_url, uri)
            p = urlsplit(full)
            path = re.sub(r'/[^/]*$', '/', p.path or '/')
            return (p.netloc.lower(), path.lower())
        except Exception:
            return ('', '')

    def _main_path_marker(self, m3u8_url):
        try:
            p = urlsplit(m3u8_url).path
            m = re.search(r'(/\d{8}/[^/]+/\d+kb/hls/)', p)
            if m:
                return m.group(1).lower()
            m = re.search(r'(/\d{8}/[^/]+/)', p)
            if m:
                return m.group(1).lower()
        except Exception:
            pass
        return ''

    def _clean_m3u8(self, m3u8_text, m3u8_url='', referer='', skip_seconds=25):
        """核心m3u8广告清洗：五重广告识别 + 主CDN统计 + 前置贴片切除 + 多码率递归代理"""
        text = (m3u8_text or '').replace('\r', '')
        # 多码率m3u8：递归代理子m3u8
        if '#EXT-X-STREAM-INF' in text:
            out = []
            last_stream = False
            for raw in text.splitlines():
                line = raw.strip()
                if not line:
                    continue
                if line.startswith('#'):
                    out.append(line)
                    last_stream = line.startswith('#EXT-X-STREAM-INF')
                else:
                    abs_url = urljoin(m3u8_url, line)
                    if last_stream or '.m3u8' in line.lower():
                        out.append(self._proxy_m3u8_url(abs_url, referer or self.rawSite))
                    else:
                        out.append(abs_url)
                    last_stream = False
            return '\n'.join(out) + '\n'

        header, segments, tail, media_sequence, target_duration = self._parse_m3u8_segments(text)
        if not segments:
            return text

        marker = self._main_path_marker(m3u8_url)

        # 统计各主机路径的总时长，找出主CDN
        stat = {}
        for seg in segments:
            key = self._segment_host_key(seg['uri'], m3u8_url)
            stat[key] = stat.get(key, 0.0) + float(seg.get('dur') or 0)
        main_key = max(stat.items(), key=lambda x: x[1])[0] if stat else ('', '')
        total_dur = sum(stat.values()) or 0
        main_dur = stat.get(main_key, 0)

        # 五重广告识别
        cleaned = []
        removed = 0
        for idx, seg in enumerate(segments):
            key = self._segment_host_key(seg['uri'], m3u8_url)
            is_front = idx < 12
            abs_uri = urljoin(m3u8_url, seg.get('uri', ''))
            is_ad = self._is_ad_segment(seg['uri'], seg.get('dur'), seg.get('tags'))
            # 第三重：路径标记不匹配主路径
            if marker and marker not in urlsplit(abs_uri).path.lower():
                is_ad = True
            tags_text = '\n'.join(seg.get('tags') or []).upper()
            # 第四重：前置12片段 + METHOD=NONE + 路径不匹配
            if is_front and 'METHOD=NONE' in tags_text and marker and marker not in urlsplit(abs_uri).path.lower():
                is_ad = True
            # 第五重：前置12片段 + 主CDN占比>=60% + 非主CDN且时长<=90秒
            if (not is_ad) and is_front and total_dur > 0 and main_dur >= total_dur * 0.6:
                if key != main_key and stat.get(key, 0) <= 90:
                    is_ad = True
            if is_ad:
                removed += 1
                continue
            seg['_idx'] = idx
            cleaned.append(seg)

        # 保守清洗策略：关闭激进的前置贴片切除，只删明确命中广告特征的片段
        # （兜底切除容易误删正片开头，导致无法播放；宁可留广告也不能洗坏正片）
        # if removed == 0 and len(segments) > 4:
        #     ... 前置贴片切除已禁用 ...

        if not cleaned:
            cleaned = segments
            removed = 0

        # 重新生成干净的m3u8
        new_lines = []
        has_m3u = False
        for line in header:
            if line.startswith('#EXTM3U'):
                has_m3u = True
            if line.startswith('#EXT-X-MEDIA-SEQUENCE') or line.startswith('#EXT-X-START'):
                continue
            if line.startswith('#EXT-X-KEY') and 'METHOD=NONE' in line.upper() and removed > 0:
                continue
            new_lines.append(line)
        if not has_m3u:
            new_lines.insert(0, '#EXTM3U')
        first_idx = cleaned[0].get('_idx', removed) if cleaned else removed
        new_lines.append('#EXT-X-MEDIA-SEQUENCE:%d' % (media_sequence + first_idx))

        for seg in cleaned:
            for tag in seg.get('tags') or []:
                if tag.startswith('#EXT-X-KEY') or tag.startswith('#EXT-X-MAP'):
                    def _fix_uri(m):
                        return 'URI="' + urljoin(m3u8_url, m.group(1)) + '"'
                    tag = re.sub(r'URI="([^"]+)"', _fix_uri, tag)
                new_lines.append(tag)
            new_lines.append(urljoin(m3u8_url, seg.get('uri', '')))
        if tail:
            for line in tail:
                if line.startswith('#EXT-X-ENDLIST'):
                    new_lines.append(line)
        elif '#EXT-X-ENDLIST' in text:
            new_lines.append('#EXT-X-ENDLIST')
        return '\n'.join(new_lines) + '\n'
