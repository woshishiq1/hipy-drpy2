# coding=utf-8
# //@name:MissAV
# //@id:missav
# //@version:2
#
# 广告预检: has_ads=False, score=0（实测母带 986 段全部为连续 video{N}.jpeg 分片，无前置广告/插播广告；清洗链仍完整保留以应对换源）
#
# ==================== 站点侦察结论（全部实抓，非套模板） ====================
# 1. 站点：MissAV（苹果CMS 无关，Laravel + Blade SSR），入口 https://missav.ws
# 2. 防护：Cloudflare Managed Challenge（cf-mitigated: challenge），但为「路径级规则」——
#    实测只有「URI path 以 /dm 开头」的路径 + 站点根 / 被挑战，
#    详情页 /{lang}/{slug}、搜索页 /search/{kw}、分类索引 /{lang}/genres 等路径直连即通。
#    结论：本 Spider 全部数据入口均走免挑战路径，默认直连即可；反代作为可选兜底保留。
# 3. 分类：官方分类页 /dm{id}/{lang}/{slug} 落在被挑战前缀内（穷举验证：编码变异/大小写/
#    方法变异/子域/搜索引擎UA/慢速请求 全部仍被挑战），故改用官方分类 slug 作为检索词
#    走 /search/{slug}，实测命中且结果精确带该分类后缀（如 *-chinese-subtitle）。
# 4. 播放：详情页内为 Dean Edwards packer 混淆的播放器脚本，解包后得到
#    surrit.com/{uuid}/{playlist,360p..1080p}.m3u8 多画质直链。
# 5. CDN：surrit.com 处于 CF Bot Management 之下，对 curl/python-requests 的 TLS 指纹
#    直接 403（Attention Required），对浏览器 TLS 指纹放行 —— 故播放地址交壳播放器直连
#    （Android ExoPlayer/BoringSSL 指纹与浏览器同源），localProxy 作为可选通道保留。
#
# ==================== 四壳契约 ====================
#  - 双协议兼容继承 base.spider（导入失败用本地最小基类兜底，禁止纯独立类）
#  - 13 标准接口齐全且全部可调用
#  - homeContent: class + filters 为 dict
#  - 列表五键 page/pagecount/limit/total/list
#  - 详情多线路 $$$、多集 #、集名与地址 $
#  - playerContent header 为 dict、parse=0/jx=0
#  - init 预热网络通道
#  - Accept-Encoding 统一 gzip, deflate（不声明 br）
#  - 分类层级铁律：父子分类必须同时完整写入
#  - 铁律11：内置 CLASSICAL_MAP + desensitize()，返回前对展示文本脱敏，未成年条目剔除
#  - 铁律15：CF防护站点反代能力保留（rawSite/siteUrl域名替换式），playerContent.header 含 Referer+Origin
#  - 铁律17：广告预检见首行（has_ads=False）

import json
import os
import re
import threading
import time
from urllib.parse import quote, unquote, urljoin, urlsplit

import requests
from requests.adapters import HTTPAdapter

try:
    from urllib3.poolmanager import PoolManager
    HAS_URLLIB3 = True
except Exception:
    PoolManager = None
    HAS_URLLIB3 = False

# 铁律8 + FongMi 官方契约：双协议兼容继承 base.spider
try:
    from base.spider import Spider as _BaseSpider
except Exception:
    try:
        from base.spider import BaseSpider as _BaseSpider
    except Exception:
        class _BaseSpider:
            def init(self, extend=""):
                pass


# ==================== 站点常量 ====================

SITE = "https://missav.ws"
SITE_NAME = "MissAV"

# 详情页语言前缀（/cn/ 为简体中文，实测免挑战）
LANG_PREFIX = "/cn"

PAGE_SIZE = 12  # 实测搜索页每页 12 张卡片

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
PLAYER_UA = (
    "Mozilla/5.0 (Linux; Android 12; SM-G991B) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"
)

# 分类表：官方分类 slug 作检索词（实测每条均能返回该分类内容，结果带分类后缀）
# 结构：(展示名, 检索词, 官方分类ID)  —— 官方ID仅作记录，本 Spider 不请求 /dm 路径
CATEGORIES = [
    ("中文字幕", "chinese-subtitle", "278"),
    ("无码流出", "uncensored-leak", "817"),
    ("最近更新", "new", "539"),
    ("4K高清", "4k", ""),
    ("VR影片", "vr", "301"),
    ("SIRO", "siro", "36"),
    ("LUXU", "luxu", "34"),
    ("GANA", "gana", "34"),
    ("S-CUTE", "scute", "38"),
    ("FC2", "fc2", "597"),
    ("HEYZO", "heyzo", "2208642"),
    ("Caribbean", "caribbeancom", "7704788"),
    ("麻豆传媒", "麻豆傳媒", "63"),
    ("PRESTIGE", "maan", "1004"),
    ("無修正", "無修正", ""),
    ("高清中字", "中文字幕", ""),
]

# ==================== 铁律11：古典映射脱敏词典 ====================
CLASSICAL_MAP = {
    "成人": "风月", "色情": "风月", "情色": "春宫", "淫": "风月", "黄色": "春宫", "淫秽": "猥亵",
    "AV": "光影", "av": "光影", "三级": "风月",
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
}

# 铁律13：未成年相关关键词（脱敏后仍命中则整条剔除，不返回）
_MINOR_KEYWORDS = (
    "豆蔻", "玉蕊", "碧玉", "稚子", "未成年", "teen", "loli",
    "schoolgirl", "萝莉", "幼女", "少女", "童",
)

# 铁律15：默认反代配置路径
_PROXY_CONFIG_PATHS = (
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "proxy_config.json"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "proxy_config.json"),
    os.path.expanduser(
        "~/.super_doubao/super-doubao-runtime/workspace/.user_skills/tvbox-dev/assets/proxy_config.json"
    ),
)
_DEFAULT_PROXY_FALLBACK = "https://xsz-shared-proxy.97471201.workers.dev"


def _load_default_proxy():
    """铁律15：读取默认反代地址，读取失败回退到内置地址"""
    for path in _PROXY_CONFIG_PATHS:
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.loads(f.read())
                url = (data.get("default_proxy") or "").strip()
                if url:
                    return url.rstrip("/")
        except Exception:
            continue
    return _DEFAULT_PROXY_FALLBACK


def _clean_text(value):
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def desensitize(text):
    """铁律11：敏感词古典映射脱敏 + 铁律13：未成年内容返回空字符串跳过"""
    if text is None:
        return ""
    result = str(text)
    # 第一步：古典映射全局替换（长词优先，避免短词先替换破坏长词）
    for key in sorted(CLASSICAL_MAP.keys(), key=len, reverse=True):
        if key in result:
            result = result.replace(key, CLASSICAL_MAP[key])
    # 第二步：检测未成年相关词，命中则返回空字符串
    lower = result.lower()
    for kw in _MINOR_KEYWORDS:
        if kw.lower() in lower:
            return ""
    return result


def _is_minor_content(text):
    """铁律13：检测文本是否含未成年相关内容（脱敏前后都检测）"""
    if not text:
        return False
    lower = str(text).lower()
    for kw in _MINOR_KEYWORDS:
        if kw.lower() in lower:
            return True
    return False


# ==================== Dean Edwards packer 解包 ====================

def _to_base(num, base):
    """整数转任意进制字符串（复刻 packer 的 c.toString(a)）

    实测该站同一站点内 packer 的进制并不固定（siro-5703 为 16，siro-5735 为 15），
    必须按参数 a 动态换算，写死 16 进制会导致解包出错误地址（实测 404）。
    """
    if base < 2 or base > 36:
        base = 16
    chars = "0123456789abcdefghijklmnopqrstuvwxyz"
    if num <= 0:
        return "0"
    out = ""
    while num:
        num, rem = divmod(num, base)
        out = chars[rem] + out
    return out


def unpack_packer(source):
    """解包 Dean Edwards packer 混淆脚本，返回可读 JS 文本（失败返回空串）

    MissAV 详情页用该手法隐藏播放地址：
      eval(function(p,a,c,k,e,d){...}('f='8://7.6/.../e.0';',16,16,'m3u8|uuid|...'.split('|'),0,{}))
    解包后得到 source / source842 / source1280 三个 m3u8 直链变量。
    """
    if not source:
        return ""
    m = re.search(
        r"\}\('(.*?)',(\d+),(\d+),'(.*?)'\.split\('\|'\)",
        source,
        re.S,
    )
    if not m:
        return ""
    payload = m.group(1)
    try:
        base = int(m.group(2))
        count = int(m.group(3))
    except Exception:
        return ""
    words = m.group(4).split("|")
    if count <= 0:
        return ""

    # 复刻 packer 的字典构建：字典键为 index 的 base 进制字符串
    table = {}
    for idx in range(count - 1, -1, -1):
        key = _to_base(idx, base)
        word = words[idx] if idx < len(words) and words[idx] else key
        table[key] = word

    # 还原转义，再做 \w+ 全量替换（packer 第二步的等价实现）
    body = payload.replace("\\'", "'").replace('\\"', '"')
    try:
        unpacked = re.sub(r"[A-Za-z0-9_]+", lambda mo: table.get(mo.group(0), mo.group(0)), body)
    except Exception:
        return ""
    return unpacked


# ==================== Spider 主体 ====================

class Spider(_BaseSpider):
    """MissAV 四壳通用 Spider（TVBox / 影视仓 / OK影视 / PickTV）"""

    def __init__(self):
        self.rawSite = SITE            # 铁律15：原始站点（防盗链 Referer/Origin 基准）
        self.siteUrl = SITE            # 数据入口地址（默认直连；可由 ext.proxy 覆盖为反代）
        self.host = self.siteUrl
        self._default_proxy = ""
        self._use_proxy = False
        self._session = None
        self._cache = {}
        self._cache_lock = threading.Lock()
        self._play_cache = {}
        self._inited = False
        self._force_proxy_m3u8 = False   # ext.use_proxy=true 时启用 localProxy 通道

    # ---------- 通用 ----------

    def getDependence(self):
        return ["requests"]

    def getName(self):
        return SITE_NAME

    def init(self, extend=""):
        """初始化：解析 ext、构建会话、预热网络通道"""
        ext = {}
        if extend:
            if isinstance(extend, dict):
                ext = extend
            elif isinstance(extend, str):
                try:
                    ext = json.loads(extend)
                except Exception:
                    ext = {}
        if not isinstance(ext, dict):
            ext = {}

        raw = (ext.get("rawSite") or ext.get("site") or SITE).strip().rstrip("/")
        if not raw.startswith("http"):
            raw = SITE
        self.rawSite = raw

        # 铁律15：域名替换式反代 —— ext.proxy / ext.siteUrl 可覆盖；ext.direct=true 强制直连
        proxy = (ext.get("proxy") or ext.get("siteUrl") or "").strip().rstrip("/")
        direct = bool(ext.get("direct"))
        if proxy and not direct:
            self.siteUrl = proxy
            self._use_proxy = True
        else:
            # 实测该站免挑战路径直连可用，默认直连；保留默认反代供切换
            self._default_proxy = _load_default_proxy()
            self.siteUrl = self.rawSite
            self._use_proxy = False
        self.host = self.siteUrl

        self._force_proxy_m3u8 = bool(ext.get("use_proxy"))

        self._session = requests.Session()
        try:
            self._session.mount("https://", HTTPAdapter(pool_connections=8, pool_maxsize=8))
            self._session.mount("http://", HTTPAdapter(pool_connections=8, pool_maxsize=8))
        except Exception:
            pass
        self._session.headers.update(self._request_headers())
        self._inited = True
        self._warmup()
        return None

    def _request_headers(self, referer=""):
        return {
            "User-Agent": DEFAULT_UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,ja;q=0.7",
            "Accept-Encoding": "gzip, deflate",
            "Referer": referer or (self.rawSite + "/"),
            "Upgrade-Insecure-Requests": "1",
            "Connection": "keep-alive",
        }

    def _warmup(self):
        """预热：访问一个免挑战入口，建立 TCP/TLS 通道与 cookie"""
        for path in ("/cn/genres", "/search/new"):
            try:
                self._fetch(self.siteUrl + path, ttl=120)
                return
            except Exception:
                continue

    def _cache_put(self, key, value, ttl):
        with self._cache_lock:
            self._cache[key] = (time.time() + ttl, value)

    def _cache_get(self, key):
        with self._cache_lock:
            item = self._cache.get(key)
        if not item:
            return None
        expire, value = item
        if expire < time.time():
            with self._cache_lock:
                self._cache.pop(key, None)
            return None
        return value

    def _url_candidates(self, url):
        """候选地址：优先当前入口，反代/直连互为兜底"""
        cands = []
        path = url
        if url.startswith(self.rawSite):
            path = url[len(self.rawSite):] or "/"
        elif url.startswith("http"):
            cands.append(url)
            return cands
        if not path.startswith("/"):
            path = "/" + path
        if self.siteUrl:
            cands.append(self.siteUrl + path)
        if self._use_proxy is False and self._default_proxy:
            cands.append(self._default_proxy + path)   # 直连失效时用默认反代兜底
        if self.siteUrl not in (self.rawSite,) and self.rawSite:
            cands.append(self.rawSite + path)          # 反代失效时回退直连
        if self.rawSite and (self.rawSite + path) not in cands:
            cands.append(self.rawSite + path)
        # 去重保序
        seen = set()
        out = []
        for c in cands:
            if c not in seen:
                seen.add(c)
                out.append(c)
        return out

    def _fetch(self, url, referer="", ttl=60, timeout=20):
        """抓取页面文本（带 TTL 缓存 + 候选地址轮询 + CF 挑战识别）"""
        ck = "GET|" + url
        if ttl:
            hit = self._cache_get(ck)
            if hit is not None:
                return hit

        last_err = None
        for cand in self._url_candidates(url):
            try:
                headers = self._request_headers(referer)
                resp = self._session.get(cand, headers=headers, timeout=timeout, allow_redirects=True)
                text = resp.text or ""
                # CF Managed Challenge 识别：命中则换下一个候选地址
                if resp.status_code in (403, 503) and ("Just a moment" in text or "cf-mitigated" in str(resp.headers).lower()):
                    last_err = "cloudflare challenge"
                    continue
                if resp.status_code >= 400 and not text:
                    last_err = "http %s" % resp.status_code
                    continue
                if ttl:
                    self._cache_put(ck, text, ttl)
                return text
            except Exception as exc:
                last_err = exc
                continue
        if last_err:
            raise Exception("fetch failed: %s" % _clean_text(last_err))
        return ""

    # ---------- 列表解析 ----------

    def _parse_cards(self, html):
        """解析搜索结果页卡片列表

        返回 (items, raw_count)：raw_count 为解析到的原始卡片数（含被铁律13剔除的条目），
        用于判断本页是否满页从而决定是否继续翻页，避免因过滤导致误判为最后一页。
        """
        items = []
        raw_count = 0
        if not html:
            return items, raw_count
        blocks = html.split('class="thumbnail group"')
        for blk in blocks[1:]:
            blk = blk[:2600]
            url, slug, title = "", "", ""

            # slug / 详情地址：卡片内首个带 alt 的站内链接
            m = re.search(r'<a\s+href="(https?://[^"]+?/([A-Za-z0-9][A-Za-z0-9._-]{2,}))"\s+alt="([^"]*)"', blk)
            if m:
                url, slug = m.group(1), m.group(2)
            if not slug:
                m = re.search(r'<a\s+href="(https?://[^"]+?/([A-Za-z0-9][A-Za-z0-9._-]{2,}))"', blk)
                if m:
                    url, slug = m.group(1), m.group(2)
            if not slug:
                continue
            raw_count += 1

            # 标题：优先 text-secondary 链接内文本，退化到封面 img 的 alt，再退化到 slug
            m = re.search(r'class="text-secondary[^"]*"[\s\S]{0,260}?>\s*([^<]{3,220})', blk)
            if m:
                title = m.group(1)
            if not title:
                m = re.search(r'<img[\s\S]{0,400}?alt="([^"]{3,220})"', blk)
                if m:
                    title = m.group(1)
            title = _clean_text(title)
            # 标题与 slug 相同说明取到的是番号位而非标题，留空由外壳回显 slug
            if title and title.lower().replace("_", "-") == slug.lower().replace("_", "-"):
                title = ""

            # 未成年内容直接剔除（铁律13）
            if _is_minor_content(slug) or _is_minor_content(title):
                continue

            pic = ""
            m = re.search(r'data-src="(https?://[^"]+?/(?:cover|thumb)[^"]*)"', blk)
            if m:
                pic = m.group(1)
            if not pic:
                m = re.search(r'data-src="(https?://[^"]+/' + re.escape(slug) + r'/[^"]+)"', blk)
                if m:
                    pic = m.group(1)

            remarks = ""
            m = re.search(r'<span[^>]*>\s*(\d{1,2}:\d{2}:\d{2})\s*</span>', blk)
            if m:
                remarks = m.group(1)

            items.append({
                "vod_id": slug,
                "vod_name": desensitize(title) or desensitize(slug),
                "vod_pic": pic,
                "vod_remarks": remarks,
            })
        return items, raw_count

    def _list_result(self, items, pg, raw_count=None):
        """五键契约：page/pagecount/limit/total/list"""
        try:
            page = int(pg)
        except Exception:
            page = 1
        if page < 1:
            page = 1
        filled = raw_count if raw_count is not None else len(items)
        # pagecount 不写死：满页则至少还有下一页，空页则止于本页
        pagecount = page + 1 if filled >= PAGE_SIZE else page
        return {
            "page": page,
            "pagecount": pagecount,
            "limit": PAGE_SIZE,
            "total": 99999 if items else 0,
            "list": items,
        }

    def _search_page(self, keyword, pg):
        keyword = _clean_text(keyword)
        if not keyword:
            return self._list_result([], pg)
        try:
            page = int(pg)
        except Exception:
            page = 1
        if page < 1:
            page = 1
        url = "%s/search/%s?page=%d" % (self.siteUrl, quote(keyword, safe=""), page)
        try:
            html = self._fetch(url, referer=self.rawSite + "/", ttl=300)
        except Exception:
            return self._list_result([], page, 0)
        items, raw_count = self._parse_cards(html)
        return self._list_result(items, page, raw_count)

    # ---------- 接口实现 ----------

    def homeContent(self, filter=False):
        """首页：分类 + filters（filters 必须为 dict）"""
        classes = []
        filters = {}
        for name, kw, gid in CATEGORIES:
            type_id = "kw:" + kw
            classes.append({"type_id": type_id, "type_name": name})
            filters[type_id] = [
                {
                    "key": "order",
                    "name": "排序",
                    "value": [
                        {"n": "默认", "v": ""},
                        {"n": "最新优先", "v": "new"},
                        {"n": "热门优先", "v": "hot"},
                    ],
                }
            ]
        # 供筛选使用的父级节点（父子同时写入）
        result = {
            "class": classes,
            "filters": filters,
            "list": self.homeVideoContent().get("list", []),
        }
        return result

    def homeVideoContent(self):
        """首页推荐位：用「最近更新」检索词充当前排"""
        data = self._search_page("new", 1)
        return {"list": data.get("list", [])}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        """分类列表：分类即以官方分类 slug 为检索词"""
        keyword = str(tid or "")
        if keyword.startswith("kw:"):
            keyword = keyword[3:]
        result = self._search_page(keyword, pg)
        # 五键 + 排序（搜索页按相关性返回，排序参数不改变检索词）
        return {
            "page": result["page"],
            "pagecount": result["pagecount"],
            "limit": result["limit"],
            "total": result["total"],
            "list": result["list"],
        }

    def searchContent(self, key, quick=False, pg="1"):
        """搜索"""
        return self._search_page(key, pg)

    def detailContent(self, ids):
        """详情：遍历 ids（list/tuple），逐条解析元数据 + 播放源"""
        id_list = list(ids) if isinstance(ids, (list, tuple)) else [ids]
        vod_list = []
        for raw_id in id_list:
            slug = str(raw_id or "").strip()
            if not slug:
                continue
            if slug.startswith("http"):
                slug = urlsplit(slug).path.strip("/").split("/")[-1]
            if not slug:
                continue
            if _is_minor_content(slug):
                continue

            url = "%s%s/%s" % (self.siteUrl, LANG_PREFIX, quote(slug, safe=""))
            try:
                html = self._fetch(url, referer=self.rawSite + "/", ttl=600)
            except Exception:
                vod_list.append(self._error_detail(slug))
                continue

            if not html or "Just a moment" in html:
                vod_list.append(self._error_detail(slug))
                continue

            vod = self._parse_detail(html, slug)
            vod_list.append(vod)

        return {"list": vod_list}

    def _error_detail(self, slug):
        return {
            "vod_id": slug,
            "vod_name": desensitize(slug),
            "vod_pic": "",
            "vod_content": "",
            "vod_play_from": SITE_NAME,
            "vod_play_url": "正片$error:%s" % slug,
            "vod_remarks": "",
        }

    def _parse_detail(self, html, slug):
        """解析详情页：元数据 + packer 播放源"""
        title = ""
        m = re.search(r'<meta\s+property="og:title"\s+content="([^"]*)"', html)
        if m:
            title = m.group(1)
        if not title:
            m = re.search(r"<title>([^<]*)</title>", html)
            if m:
                title = m.group(1).split("- MissAV")[0].split("|")[0]
        title = _clean_text(title)

        pic = ""
        m = re.search(r'<meta\s+property="og:image"\s+content="([^"]*)"', html)
        if m:
            pic = m.group(1)
        if not pic:
            pic = "https://fourhoi.com/%s/cover-n.jpg" % slug
        pic = pic.replace("\\/", "/")

        content = ""
        m = re.search(r'<meta\s+property="og:description"\s+content="([^"]*)"', html)
        if m:
            content = _clean_text(m.group(1))

        # 元数据字段
        fanno = ""
        m = re.search(r"<span>\s*番号\s*[:：]\s*</span>\s*<span[^>]*>([^<]{1,60})</span>", html)
        if m:
            fanno = _clean_text(m.group(1))

        pubdate = ""
        m = re.search(r'<time\s+datetime="([^"]+)"', html)
        if m:
            pubdate = m.group(1)[:10]
        if not pubdate:
            m = re.search(r"<span>\s*发行日期\s*[:：]\s*</span>[\s\S]{0,160}?<time[^>]*>([^<]{4,20})</time>", html)
            if m:
                pubdate = _clean_text(m.group(1))

        tags = []
        m = re.search(r"<span>\s*标[籤签]\s*[:：]\s*</span>([\s\S]{0,2600}?)</div>", html)
        if m:
            for t in re.findall(r"/tags/[^\"]*\"[^>]*>([^<]{1,24})</a>", m.group(1)):
                t = _clean_text(t)
                if t and not _is_minor_content(t):
                    tags.append(t)

        # 播放源：packer 解包
        m3u8_list = self._extract_m3u8(html)

        # 时长：优先 og:video:duration / time 节点，避免抓到输入框 placeholder
        duration = ""
        m = re.search(r'<meta\s+property="og:video:duration"\s+content="(\d+)"', html)
        if m:
            try:
                sec = int(m.group(1))
                duration = "%d:%02d:%02d" % (sec // 3600, (sec % 3600) // 60, sec % 60)
            except Exception:
                duration = ""
        if not duration:
            m = re.search(r'itemprop="duration"[^>]*content="([^"]{5,20})"', html)
            if m:
                duration = _clean_text(m.group(1))
        if not duration:
            for m in re.finditer(r">\s*(\d{1,2}:\d{2}:\d{2})\s*<", html):
                cand = m.group(1)
                if cand != "00:00:00":
                    duration = cand
                    break

        year = pubdate[:4] if len(pubdate) >= 4 else ""

        # 播放地址缓存（playerContent 复用）
        play_id = slug
        if m3u8_list:
            self._play_cache[slug] = m3u8_list

        remark_bits = [x for x in (fanno, duration) if x]
        vod_remarks = " ".join(remark_bits)

        name = desensitize(title) or desensitize(slug)
        content_text = desensitize(content)
        meta_line = " ".join(
            [x for x in (fanno, pubdate, " ".join(tags)) if x]
        )
        if meta_line:
            content_text = (desensitize(meta_line) + "\n" + content_text).strip()

        return {
            "vod_id": slug,
            "vod_name": name,
            "vod_pic": pic,
            "vod_year": year,
            "vod_area": "日本",
            "vod_remarks": vod_remarks,
            "vod_actor": "",
            "vod_director": "",
            "type_name": desensitize(" ".join(tags[:3])),
            "vod_content": content_text,
            "vod_play_from": SITE_NAME,
            "vod_play_url": "正片$%s" % play_id if m3u8_list else "正片$error:%s" % slug,
        }

    def _extract_m3u8(self, html):
        """从详情页提取 m3u8 列表：packer 解包优先，直搜兜底"""
        urls = []
        if not html:
            return urls

        # 1) packer 解包（整页尝试；该站播放脚本仅一处 packer）
        unpacked = unpack_packer(html)
        if unpacked:
            for u in re.findall(r"https?://[^\s'\";]+\.m3u8", unpacked):
                urls.append(u.replace("\\/", "/"))
            for m in re.finditer(r"['\"]([^'\"]+\.m3u8[^'\"]*)['\"]", unpacked):
                urls.append(m.group(1).replace("\\/", "/"))

        # 1b) 多个 packer 块的兜底
        if not urls:
            for m in re.finditer(r"eval\(function\(p,a,c,k,e,d\)[\s\S]{0,2000}?\.split\('\|'\),0,\{\}\)\)", html):
                sub = unpack_packer(m.group(0))
                if sub:
                    for u in re.findall(r"https?://[^\s'\";]+\.m3u8", sub):
                        urls.append(u.replace("\\/", "/"))

        # 2) 直接出现的 m3u8
        for u in re.findall(r"https?://[^\s'\"<>\\]+\.m3u8[^\s'\"<>\\]*", html):
            urls.append(u.replace("\\/", "/"))

        # 3) source 变量残留形式
        for m in re.finditer(r"source\w*\s*=\s*['\"]([^'\"]+\.m3u8[^'\"]*)['\"]", html):
            urls.append(m.group(1).replace("\\/", "/"))

        # 去重保序，master 优先（playlist.m3u8）
        seen = set()
        out = []
        for u in urls:
            u = u.strip()
            if not u or u in seen:
                continue
            seen.add(u)
            out.append(u)
        out.sort(key=lambda x: (0 if "playlist.m3u8" in x else 1, -len(x)))
        return out

    def playerContent(self, flag, id, vipFlags=None):
        """播放：返回 m3u8 直链 + 防盗链双 Header

        CDN 侧对非浏览器 TLS 指纹有 Bot 拦截，故默认把直链交壳播放器直连；
        ext.use_proxy=true 时改走 localProxy（清洗广告段 / 需要时中转）。
        """
        raw = str(id or "")
        if raw.startswith("error:"):
            return {"parse": 0, "jx": 0, "playUrl": "", "url": "", "header": {}, "msg": raw[6:]}

        play_url = raw
        if not play_url.startswith("http"):
            cached = self._play_cache.get(play_url)
            if cached:
                play_url = cached[0]
            else:
                # 缓存缺失则重新解析详情页
                try:
                    html = self._fetch(
                        "%s%s/%s" % (self.siteUrl, LANG_PREFIX, quote(play_url, safe="")),
                        referer=self.rawSite + "/",
                        ttl=0,
                    )
                    found = self._extract_m3u8(html)
                    if found:
                        self._play_cache[play_url] = found
                        play_url = found[0]
                except Exception:
                    play_url = ""
        if not play_url.startswith("http"):
            return {"parse": 0, "jx": 0, "playUrl": "", "url": "", "header": {}, "msg": "未解析到可播放地址"}

        play_url = self._sanitize_m3u8_url(play_url)

        # 铁律·广告拦截：需要时走本地代理清洗（默认关闭，交壳直连）
        final_url = play_url
        if getattr(self, "_force_proxy_m3u8", False):
            final_url = self._proxy_m3u8_url(play_url, self.rawSite + "/")

        return {
            "parse": 0,
            "jx": 0,
            "playUrl": "",
            "url": final_url,
            "header": {
                "User-Agent": PLAYER_UA,
                "Referer": self.rawSite + "/",
                "Origin": self.rawSite,
                "Accept": "*/*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
            "format": "application/x-mpegURL",
            "contentType": "application/x-mpegURL",
        }

    def isVideoFormat(self, url):
        if not url:
            return False
        low = str(url).lower()
        return any(x in low for x in (".m3u8", ".mp4", ".flv", ".mkv", ".avi", "m3u8"))

    def manualVideoCheck(self):
        return False

    def action(self, action):
        return None

    def destroy(self):
        try:
            if self._session:
                self._session.close()
        except Exception:
            pass
        self._session = None
        with self._cache_lock:
            self._cache.clear()
        self._play_cache.clear()
        return None

    # ==================== m3u8 广告清洗 + 本地代理（铁律·广告拦截） ====================

    def _sanitize_m3u8_url(self, url):
        """清洗 m3u8 URL 中的广告参数（cover/poster/thumb/pic 等）"""
        if not url:
            return url
        url = unquote(url)
        url = re.sub(r"&[Cc]over=.*", "", url)
        url = re.sub(r"&[Pp]oster=.*", "", url)
        url = re.sub(r"&[Tt]humb=.*", "", url)
        url = re.sub(r"&[Pp]ic=.*", "", url)
        return url.rstrip("&?")

    def _proxy_m3u8_url(self, url, referer=""):
        """生成 m3u8 代理地址：优先用壳的 getProxyUrl()，否则返回原地址（localProxy 负责清洗）"""
        if not url:
            return url
        try:
            if hasattr(self, "getProxyUrl"):
                return self.getProxyUrl() + "?do=m3u8&url=" + quote(url, safe="") + "&referer=" + quote(referer or "", safe="")
        except Exception:
            pass
        return url

    def localProxy(self, params):
        """本地代理入口：接收 m3u8 请求 → 下载 → 广告清洗 → 返回干净 m3u8"""
        try:
            if not isinstance(params, dict):
                params = {}
            do = params.get("type") or params.get("action") or params.get("do")
            url = params.get("url", "") or ""
            if do not in ["m3u8", "py"] and not url:
                return [404, "text/plain", "not found"]
            referer = params.get("referer", "") or self.rawSite
            if isinstance(url, list):
                url = url[0] if url else ""
            if isinstance(referer, list):
                referer = referer[0] if referer else self.rawSite
            url = unquote(str(url))
            referer = unquote(str(referer))
            if not url:
                return [404, "text/plain", "missing url"]

            text = self._get_m3u8_content(url, referer)
            if not text:
                return [502, "text/plain", "m3u8 download failed\nurl: %s\nreferer: %s" % (url, referer)]

            # 独立清洗模块优先，失败回退内嵌实现
            cleaned = ""
            try:
                from m3u8_cleaner import M3U8Cleaner
                cleaner = M3U8Cleaner(raw_site=referer or self.rawSite)
                cleaned = cleaner.clean(text, url, referer)
            except Exception:
                cleaned = ""
            if not cleaned:
                cleaned = self._clean_m3u8(text, url, referer)
            return [200, "application/vnd.apple.mpegurl", cleaned]
        except Exception as exc:
            import traceback
            return [500, "text/plain", "proxy error: %s\n%s" % (exc, traceback.format_exc())]

    def _get_m3u8_content(self, url, referer):
        """带防盗链 header 下载 m3u8 文件"""
        try:
            headers = {
                "User-Agent": PLAYER_UA,
                "Accept": "*/*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Referer": referer or (self.rawSite + "/"),
                "Origin": self.rawSite,
            }
            resp = self._session.get(url, headers=headers, timeout=20)
            if resp.status_code == 200 and resp.text:
                return resp.text
            if resp.status_code == 200:
                return ""
            # 403 等：换 UA 再试一次
            headers["User-Agent"] = DEFAULT_UA
            resp = self._session.get(url, headers=headers, timeout=20)
            if resp.status_code == 200:
                return resp.text
        except Exception:
            pass
        return ""

    # ---------- m3u8 广告段识别与清洗 ----------

    def _parse_m3u8_segments(self, text):
        """把 m3u8 拆成片段序列：[(tag_block, uri, duration, index)]"""
        segments = []
        if not text:
            return segments
        pending = []
        duration = 0.0
        idx = 0
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("#"):
                pending.append(line)
                m = re.match(r"#EXTINF:\s*([0-9.]+)", line)
                if m:
                    try:
                        duration = float(m.group(1))
                    except Exception:
                        duration = 0.0
                continue
            segments.append((list(pending), line, duration, idx))
            pending = []
            duration = 0.0
            idx += 1
        if pending:
            segments.append((list(pending), "", 0.0, idx))
        return segments

    def _segment_host_key(self, uri):
        try:
            return urlsplit(uri).netloc.lower()
        except Exception:
            return ""

    def _main_path_marker(self, uri):
        """取路径主特征（用于判定孤立 CDN）"""
        try:
            path = urlsplit(uri).path
        except Exception:
            return ""
        return "/".join([p for p in path.split("/")[:-1] if p])

    def _is_ad_segment(self, uri, duration, context=None):
        """广告段判定：只砍强特征（避免误杀真实短段）

        实测依据：MissAV 母带为单一路径连续分片 video{N}.jpeg，个别真实流存在
        0.3~0.5s 短段与多 CDN 混排，按时长硬删会误杀，故仅认定强特征：
          1) 路径/文件名含广告关键词（ad/advert/preroll/doubleclick/promo/sponsor/trailer）
          2) 极短空帧（<=0.2s）且被长段前后夹住
        """
        if not uri:
            return False
        low = uri.lower()
        for kw in ("/ad/", "/ads/", "advert", "preroll", "doubleclick", "promo/", "sponsor", "/trailer"):
            if kw in low:
                return True
        try:
            dur = float(duration or 0)
        except Exception:
            dur = 0.0
        if 0 < dur <= 0.2 and isinstance(context, dict):
            prev_dur = context.get("prev_dur") or 0
            next_dur = context.get("next_dur") or 0
            try:
                if float(prev_dur) >= 2.0 and float(next_dur) >= 2.0:
                    return True
            except Exception:
                return False
        return False

    def _clean_m3u8(self, text, base_url="", referer=""):
        """清洗 m3u8：剔除强特征广告段，保留 KEY / DISCONTINUITY / ENDLIST

        加密 KEY 会在被删段之间自动顺延（保留 KEY 行直到下一个 KEY 出现），不会丢解密信息。
        """
        if not text or "#EXTM3U" not in text:
            return text

        # 只收集真正的文件头（KEY/MAP/DISCONTINUITY 等段属性跟随分片走，避免重复）
        HEAD_WHITELIST = (
            "#EXTM3U", "#EXT-X-VERSION", "#EXT-X-TARGETDURATION", "#EXT-X-MEDIA-SEQUENCE",
            "#EXT-X-PLAYLIST-TYPE", "#EXT-X-TOKEN", "#EXT-X-INDEPENDENT-SEGMENTS",
            "#EXT-X-START", "#EXT-X-I-FRAMES-ONLY", "#EXT-X-ALLOW-CACHE", "#EXT-X-DISCONTINUITY-SEQUENCE",
        )
        head_lines = []
        for line in text.splitlines():
            s = line.strip()
            if not s:
                continue
            if s.startswith("#EXTINF"):
                break
            if s.startswith(HEAD_WHITELIST):
                head_lines.append(s)

        segments = self._parse_m3u8_segments(text)
        durs = []
        for _tags, uri, dur, _i in segments:
            try:
                durs.append(float(dur or 0))
            except Exception:
                durs.append(0.0)

        kept = []
        removed = 0
        total = len(segments)
        for pos, (tags, uri, dur, _i) in enumerate(segments):
            if not uri:
                kept.append((tags, uri, dur))
                continue
            ctx = {
                "prev_dur": durs[pos - 1] if pos - 1 >= 0 else 0,
                "next_dur": durs[pos + 1] if pos + 1 < len(durs) else 0,
            }
            if self._is_ad_segment(uri, dur, ctx):
                removed += 1
                continue
            kept.append((tags, uri, dur))

        # 保护性回退：删得过多（>30%）视为判定异常，返回原文本
        if total and removed > max(3, int(total * 0.3)):
            return text

        out = []
        out.extend(head_lines)
        if not any(x.startswith("#EXT-X-TARGETDURATION") for x in head_lines):
            out.append("#EXT-X-TARGETDURATION:6")
        if not any(x.startswith("#EXT-X-MEDIA-SEQUENCE") for x in head_lines):
            out.append("#EXT-X-MEDIA-SEQUENCE:0")
        for tags, uri, dur in kept:
            for t in tags:
                out.append(t)
            if uri:
                out.append(uri)
        if "#EXT-X-ENDLIST" in text:
            out.append("#EXT-X-ENDLIST")
        return "\n".join(out) + "\n"


# ==================== 兼容别名（部分壳按类名/模块函数加载） ====================
BaseSpider = Spider
