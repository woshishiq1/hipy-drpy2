# -*- coding: utf-8 -*-
"""
狼友天堂 TVBox 四壳通用 Spider
站点: https://yri.lytt6.motorcycles
CMS: 苹果CMS (MacCMS)
防护: Cloudflare 403 硬封 → X25519 TLS 指纹破甲
播放: player_data.url 直出 m3u8 (无加密, ckplayer)
铁律13: 未成年相关条目直接剔除
铁律11: 代码层不脱敏, 展示文本返回原始内容
铁律15: CF破甲 + playerContent.header 含 Referer/Origin 破防盗链
"""

import json
import re
import ssl
import urllib.parse
from urllib.parse import urlsplit

import requests
from requests.adapters import HTTPAdapter

try:
    from urllib3.poolmanager import PoolManager
    HAS_URLLIB3 = True
except Exception:
    PoolManager = None
    HAS_URLLIB3 = False

# ============================================================
# 双协议兼容: 优先继承四壳基类, 失败则本地最小基类兜底
# ============================================================
try:
    from base.spider import Spider as _BaseSpider
except Exception:
    class _BaseSpider:
        """本地最小基类兜底, 仅提供空实现"""
        def init(self, extend=""):
            pass

        def homeContent(self, *args):
            return {}

        def homeVideoContent(self, *args):
            return []

        def categoryContent(self, *args):
            return {}

        def detailContent(self, *args):
            return {}

        def searchContent(self, *args):
            return {}

        def playerContent(self, *args):
            return {}

        def localProxy(self, *args):
            return ""

        def isVideoFormat(self, url):
            return False

        def manualVideoCheck(self):
            return False

        def action(self, action):
            pass

        def destroy(self):
            pass

        def getName(self):
            return "狼友天堂"

        def getDependence(self):
            return ""


# ============================================================
# 常量配置
# ============================================================
SITE_NAME = "狼友天堂"
RAW_SITE = "https://yri.lytt6.motorcycles"
BASE_PATH = "/cn/home/web"
DEFAULT_UA = (
    "Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
)

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

# 分类列表 (9个, 无父子层级)
CATEGORIES = [
    {"type_id": "20", "type_name": "偷拍自拍"},
    {"type_id": "21", "type_name": "强奸乱伦"},
    {"type_id": "22", "type_name": "人妻熟女"},
    {"type_id": "23", "type_name": "制服情景"},
    {"type_id": "24", "type_name": "国产情色"},
    {"type_id": "25", "type_name": "亚洲精品"},
    {"type_id": "26", "type_name": "卡通动漫"},
    {"type_id": "27", "type_name": "欧美性爱"},
    {"type_id": "28", "type_name": "精品三级"},
]

# 铁律13: 未成年关键词 (命中则剔除条目)
JUVENILE_KEYWORDS = (
    "未成年", "少女", "萝莉", "幼女", "童", "teen", "loli",
    "schoolgirl", "小学生", "初中生", "高中生", "JK", "豆蔻",
    "玉蕊", "碧玉", "稚子", "幼", "小孩",
)

# 视频列表正则
LIST_ITEM_RE = re.compile(
    r'<li>\s*<a href="[^"]*vod/play/id/(\d+)/sid/\d+/nid/\d+\.html"[^>]*>'
    r'(.*?)</a>\s*</li>',
    re.S,
)
ITEM_IMG_RE = re.compile(r'<img[^>]+src="([^"]+)"[^>]*alt="([^"]*)"', re.S)
ITEM_PNAME_RE = re.compile(r'<p class="pname">(.*?)</p>', re.S)
ITEM_PSTARRING_RE = re.compile(r'<p class="pstarring">(.*?)</p>', re.S)

# 播放页 player_data 正则 (兼容 } 后接 ; 或 </script>)
PLAYER_DATA_RE = re.compile(r'var\s+player_data\s*=\s*(\{.*?\})\s*(?:;|<)', re.S)

# 分页最大页码正则
MAX_PAGE_RE = re.compile(r'vod/type/id/\d+/page/(\d+)\.html')
SEARCH_MAX_PAGE_RE = re.compile(r'vod/search/page/(\d+)/wd/')


# ============================================================
# Cloudflare TLS 破甲适配器 (X25519 曲线)
# ============================================================
class CloudflareTLSAdapter(HTTPAdapter):
    def __init__(self, use_x25519=False, **kwargs):
        self._use_x25519 = use_x25519
        super(CloudflareTLSAdapter, self).__init__(**kwargs)

    def _build_context(self):
        context = ssl.create_default_context()
        try:
            context.minimum_version = ssl.TLSVersion.TLSv1_2
        except Exception:
            pass
        try:
            context.set_alpn_protocols(["h2", "http/1.1"])
        except Exception:
            pass
        if self._use_x25519:
            for curve in ("X25519", "prime256v1"):
                try:
                    context.set_ecdh_curve(curve)
                    break
                except Exception:
                    continue
        return context

    def init_poolmanager(self, connections, maxsize, block=False, **kwargs):
        context = self._build_context()
        if HAS_URLLIB3 and PoolManager is not None:
            kwargs["ssl_context"] = context
            self.poolmanager = PoolManager(
                num_pools=connections, maxsize=maxsize, block=block, **kwargs
            )
        else:
            super(CloudflareTLSAdapter, self).init_poolmanager(
                connections, maxsize, block=block, **kwargs
            )

    def proxy_manager_for(self, proxy, **kwargs):
        try:
            kwargs["ssl_context"] = self._build_context()
        except Exception:
            pass
        return super(CloudflareTLSAdapter, self).proxy_manager_for(proxy, **kwargs)


def build_tls_session(user_agent=None, cookie="", use_x25519=True):
    """构建带 CF 破甲的 requests.Session"""
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
        session.mount("https://", CloudflareTLSAdapter(use_x25519=use_x25519))
    except Exception:
        pass
    return session


# ============================================================
# 工具函数
# ============================================================
def _normalize_origin(value):
    text = str(value or RAW_SITE).strip().rstrip("/")
    if text and "://" not in text:
        text = "https://" + text
    try:
        parsed = urlsplit(text)
    except Exception:
        return RAW_SITE
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return RAW_SITE
    return parsed.scheme + "://" + parsed.netloc


def _parse_config(extend):
    """解析 extend 配置字符串 (支持 JSON 或 key=value 格式)"""
    config = {}
    if not extend:
        return config
    text = str(extend).strip()
    if not text:
        return config
    # 尝试 JSON
    if text.startswith("{"):
        try:
            config = json.loads(text)
            return config
        except Exception:
            pass
    # 尝试 key=value&key2=value2 格式
    try:
        parsed = urllib.parse.parse_qs(text)
        for k, v in parsed.items():
            if v:
                config[k] = v[0]
    except Exception:
        pass
    return config


def _bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in ("1", "true", "yes", "on", "是"):
        return True
    if text in ("0", "false", "no", "off", "否"):
        return False
    return default


def _is_juvenile(text):
    """铁律13: 检测文本是否含未成年关键词"""
    if not text:
        return False
    text_lower = str(text).lower()
    for kw in JUVENILE_KEYWORDS:
        if kw.lower() in text_lower:
            return True
    return False


def _strip_html(text):
    """去除HTML标签并清理空白"""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _filter_juv_list(items):
    """铁律13: 从列表中剔除未成年条目"""
    result = []
    for item in items:
        name = item.get("vod_name", "")
        remarks = item.get("vod_remarks", "")
        if _is_juvenile(name) or _is_juvenile(remarks):
            continue
        result.append(item)
    return result


# ============================================================
# Spider 主类
# ============================================================
class Spider(_BaseSpider):
    name = SITE_NAME
    backend_parse = False
    category_mode = False

    def __init__(self):
        self.rawSite = RAW_SITE
        self.siteUrl = RAW_SITE
        self.HOST = RAW_SITE
        self.timeout = 20
        self.cookie = ""
        self._use_proxy = False
        self._session = None
        self._categories = list(CATEGORIES)

    # --------------------------------------------------------
    # 基础接口
    # --------------------------------------------------------
    def getDependence(self):
        return ""

    def getName(self):
        return self.name

    def init(self, extend=""):
        config = _parse_config(extend)

        # 原始站点
        self.rawSite = _normalize_origin(config.get("host") or RAW_SITE)

        # 反代/直连配置
        direct = _bool(config.get("direct"), False)
        ext_proxy = str(config.get("proxy") or config.get("siteUrl") or "").strip()

        if direct:
            self._use_proxy = False
            self.siteUrl = self.rawSite
        elif ext_proxy:
            self._use_proxy = True
            self.siteUrl = _normalize_origin(ext_proxy)
        else:
            # 默认 X25519 TLS 破甲直连
            self._use_proxy = False
            self.siteUrl = self.rawSite

        self.HOST = self.siteUrl
        self.timeout = int(config.get("timeout") or 20)
        self.cookie = str(config.get("cookie") or "").strip()

        # 构建会话
        self._session = build_tls_session(
            user_agent=DEFAULT_UA,
            cookie=self.cookie,
            use_x25519=True,
        )

        # 铁律13: 过滤未成年分类
        self._categories = [
            c for c in CATEGORIES if not _is_juvenile(c["type_name"])
        ]

    # --------------------------------------------------------
    # 网络请求
    # --------------------------------------------------------
    def _fetch(self, url, referer=None):
        """发起 GET 请求, 自动带 Referer"""
        if self._session is None:
            self._session = build_tls_session(use_x25519=True)
        headers = {}
        if referer:
            headers["Referer"] = referer
        else:
            headers["Referer"] = self.rawSite + "/"
        resp = self._session.get(url, headers=headers, timeout=self.timeout)
        resp.encoding = resp.apparent_encoding or "utf-8"
        return resp.text

    def _build_url(self, path):
        """构建完整URL"""
        return self.siteUrl + path

    # --------------------------------------------------------
    # 解析: 视频列表
    # --------------------------------------------------------
    def _parse_video_list(self, html):
        """从分类页/搜索页HTML解析视频列表"""
        items = []
        matches = LIST_ITEM_RE.findall(html)
        for vid, block in matches:
            # 封面图
            img_match = ITEM_IMG_RE.search(block)
            cover = img_match.group(1).strip() if img_match else ""
            alt = img_match.group(2).strip() if img_match else ""

            # 标题 (优先 pname, 回退 alt)
            name_match = ITEM_PNAME_RE.search(block)
            name = _strip_html(name_match.group(1)) if name_match else _strip_html(alt)
            if not name:
                name = alt

            # 日期/备注
            date_match = ITEM_PSTARRING_RE.search(block)
            remarks = _strip_html(date_match.group(1)) if date_match else ""

            items.append({
                "vod_id": str(vid),
                "vod_name": name,
                "vod_pic": cover,
                "vod_remarks": remarks,
            })
        return items

    def _extract_max_page(self, html, pattern=MAX_PAGE_RE):
        """从分页HTML提取最大页码"""
        pages = pattern.findall(html)
        if pages:
            try:
                return max(int(p) for p in pages)
            except Exception:
                pass
        return 1

    # --------------------------------------------------------
    # 首页
    # --------------------------------------------------------
    def homeContent(self, *args):
        classes = [
            {"type_id": c["type_id"], "type_name": c["type_name"]}
            for c in self._categories
        ]
        return {
            "class": classes,
            "filters": {},
        }

    def homeVideoContent(self, *args):
        return []

    # --------------------------------------------------------
    # 分类页
    # --------------------------------------------------------
    def categoryContent(self, tid, pg, filter=None, extend=None, *args):
        # 兼容参数签名
        if isinstance(tid, (list, tuple)) and len(tid) >= 1:
            tid = tid[0]
        tid = str(tid or "20")
        pg = str(pg or "1")

        # 构建URL
        if pg == "1":
            path = f"{BASE_PATH}/index.php/vod/type/id/{tid}.html"
        else:
            path = f"{BASE_PATH}/index.php/vod/type/id/{tid}/page/{pg}.html"
        url = self._build_url(path)

        try:
            html = self._fetch(url)
        except Exception:
            html = ""

        items = self._parse_video_list(html)
        # 铁律13: 剔除未成年条目
        items = _filter_juv_list(items)

        max_page = self._extract_max_page(html)
        pagecount = max(max_page, int(pg))
        total = pagecount * 60

        return {
            "page": int(pg),
            "pagecount": pagecount,
            "limit": 60,
            "total": total,
            "list": items,
        }

    # --------------------------------------------------------
    # 详情页 (用播放页代替, 该站无独立详情页)
    # --------------------------------------------------------
    def detailContent(self, ids, *args):
        if isinstance(ids, str):
            ids = [ids]
        if not isinstance(ids, (list, tuple)):
            ids = [str(ids)]

        result_list = []
        for vid in ids:
            vid = str(vid).strip()
            if not vid:
                continue
            path = f"{BASE_PATH}/index.php/vod/play/id/{vid}/sid/1/nid/1.html"
            url = self._build_url(path)

            try:
                html = self._fetch(url)
            except Exception:
                html = ""

            # 提取 player_data
            play_url = ""
            play_from = "ckplayer"
            vod_name = ""
            vod_pic = ""
            vod_remarks = ""

            pd_match = PLAYER_DATA_RE.search(html)
            if pd_match:
                try:
                    pd_text = pd_match.group(1)
                    player_data = json.loads(pd_text)
                    play_url = player_data.get("url", "")
                    play_from = player_data.get("from", "ckplayer") or "ckplayer"
                except Exception:
                    pass

            # 从页面提取标题和封面
            title_match = re.search(r"<title>(.*?)</title>", html, re.S)
            if title_match:
                vod_name = _strip_html(title_match.group(1))
                # 去掉站点后缀
                vod_name = re.sub(r"\s*-\s*狼友天堂\s*$", "", vod_name)

            og_img = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', html)
            if og_img:
                vod_pic = og_img.group(1).strip()

            # 铁律13: 未成年条目跳过
            if _is_juvenile(vod_name):
                continue

            # 构建播放地址 (单集)
            if play_url:
                vod_play_url = f"第1集${play_url}"
            else:
                vod_play_url = ""

            result_list.append({
                "vod_id": vid,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_remarks": vod_remarks,
                "vod_play_from": play_from,
                "vod_play_url": vod_play_url,
            })

        return {"list": result_list}

    # --------------------------------------------------------
    # 搜索
    # --------------------------------------------------------
    def searchContent(self, wd, quick=False, *args):
        # 兼容参数签名
        if isinstance(wd, (list, tuple)) and len(wd) >= 1:
            wd = wd[0]
        wd = str(wd or "").strip()
        if not wd:
            return {"page": 1, "pagecount": 0, "limit": 60, "total": 0, "list": []}

        pg = "1"
        # 检查是否有分页参数
        if isinstance(quick, str) and quick.isdigit():
            pg = quick
            quick = False

        encoded_wd = urllib.parse.quote(wd)
        if pg == "1":
            path = f"{BASE_PATH}/index.php/vod/search.html?wd={encoded_wd}"
        else:
            path = f"{BASE_PATH}/index.php/vod/search/page/{pg}/wd/{encoded_wd}.html"
        url = self._build_url(path)

        try:
            html = self._fetch(url)
        except Exception:
            html = ""

        items = self._parse_video_list(html)
        # 铁律13: 剔除未成年条目
        items = _filter_juv_list(items)

        if quick:
            items = items[:10]

        max_page = self._extract_max_page(html, pattern=SEARCH_MAX_PAGE_RE)
        pagecount = max(max_page, int(pg))
        total = pagecount * 60

        return {
            "page": int(pg),
            "pagecount": pagecount,
            "limit": 60,
            "total": total,
            "list": items,
        }

    # --------------------------------------------------------
    # 播放
    # --------------------------------------------------------
    def playerContent(self, flag, id, vipFlags=None, *args):
        # id 就是 m3u8 地址 (从 vod_play_url 中解析)
        video_url = str(id or "")
        # 如果 id 包含 $ 分隔符, 取最后一段
        if "$" in video_url:
            video_url = video_url.split("$")[-1]

        return {
            "parse": "0",
            "jx": "0",
            "url": video_url,
            "header": {
                "User-Agent": DEFAULT_UA,
                "Referer": self.rawSite + "/",
                "Origin": self.rawSite,
            },
        }

    # --------------------------------------------------------
    # 其他接口
    # --------------------------------------------------------
    def localProxy(self, *args):
        return ""

    def isVideoFormat(self, url, *args):
        if not url:
            return False
        url_lower = str(url).lower()
        return url_lower.endswith(".m3u8") or url_lower.endswith(".mp4")

    def manualVideoCheck(self, *args):
        return False

    def action(self, action, *args):
        pass

    def destroy(self, *args):
        try:
            if self._session:
                self._session.close()
        except Exception:
            pass
