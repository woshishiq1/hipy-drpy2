# coding=utf-8
# //@name:午夜剧场
# //@id:wuyejuchang
# //@version:1.1
#
# 四壳契约（TVBox / 影视仓 / OK影视 / PickTV）：
#  - 双协议兼容继承 base.spider（try导入失败则本地基类兜底）
#  - 13 标准接口齐全且全部可调用
#  - homeContent: class + filters 为 dict
#  - 列表五键 page/pagecount/limit/total/list
#  - 详情多线路 $$$、多集 #
#  - playerContent header 为 dict、parse=0/jx=0
#  - 铁律11：代码层全部不脱敏，分类名/视频标题/热门标签/详情直接返回网站原始内容
#  - 仅保留未成年内容过滤（内容安全底线，与脱敏无关）
#  - 铁律13：未成年相关条目（萝莉/幼女/少女/童/teen/loli/schoolgirl等）直接剔除不返回
#  - 纯HTML正则解析，零第三方依赖（仅标准库urllib），确保任何壳环境都能正常返回视频列表
#  - 站点：https://bra.wyjc7.quest/cn/home/web/
#  - 筛选原理与网站一致：分类页仅分页，排行榜走独立label页，热门标签走搜索

import re
import json
import sys
import ssl
import gzip
from io import BytesIO
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

# 不验证SSL（避免证书问题导致请求失败）
try:
    _SSL_CTX = ssl.create_default_context()
    _SSL_CTX.check_hostname = False
    _SSL_CTX.verify_mode = ssl.CERT_NONE
except Exception:
    _SSL_CTX = None

# ========== 站点配置 ==========
DEFAULT_HOST = "https://bra.wyjc7.quest"
HOME_PATH = "/cn/home/web/"
PAGE_SIZE = 40

DEFAULT_UA = (
    "Mozilla/5.0 (Linux; Android 12; Pixel 6) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
)

NAV_HEADERS = {
    "User-Agent": DEFAULT_UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
    "Accept-Encoding": "gzip, deflate",
    "Upgrade-Insecure-Requests": "1",
    "Referer": DEFAULT_HOST + "/",
}

# ========== 分类（与网站顶部分类一致，11个） ==========
CATEGORIES = [
    {"type_id": "20", "type_name": "美女写真"},
    {"type_id": "21", "type_name": "国产精品"},
    {"type_id": "22", "type_name": "无码专区"},
    {"type_id": "23", "type_name": "中文字幕"},
    {"type_id": "24", "type_name": "强奸乱伦"},
    {"type_id": "25", "type_name": "人妻熟女"},
    {"type_id": "26", "type_name": "亚洲情色"},
    {"type_id": "27", "type_name": "制服丝袜"},
    {"type_id": "28", "type_name": "SM捆绑"},
    {"type_id": "29", "type_name": "自淫系列"},
    {"type_id": "30", "type_name": "三级伦理"},
]

# ========== 排行榜筛选（与网站一致：独立label页面） ==========
RANK_FILTERS = [
    {"n": "默认", "v": ""},
    {"n": "总排行榜", "v": "hot"},
    {"n": "月排行榜", "v": "hot_month"},
    {"n": "周排行榜", "v": "hot_week"},
    {"n": "日排行榜", "v": "hot_day"},
    {"n": "最新上传", "v": "new"},
]

RANK_PATH_MAP = {
    "hot": "/label/hot.html",
    "hot_month": "/label/hot_month.html",
    "hot_week": "/label/hot_week.html",
    "hot_day": "/label/hot_day.html",
    "new": "/label/new.html",
}

# ========== 热门标签（动态获取，不硬编码） ==========
# homeContent时从网站首页"热门关键词"区域动态提取，加缓存
# 网站更新标签后Spider自动跟着变

# ========== 热门标签（filters中使用，点击即搜索） ==========
# ========== 未成年关键词（铁律13，命中即剔除） ==========
UNDERAGE_KEYWORDS = [
    "萝莉", "幼女", "少女", "童", "未成年", "teen", "loli", "schoolgirl",
    "小女", "女童", "幼童", "小孩", "小学生", "初中生", "JK萝莉", "合法萝莉",
    "洛丽塔", "豆蔻", "玉蕊", "碧玉",
]

# ========== 正则（纯HTML解析，零依赖） ==========
# 视频卡片：<li ...><a href="/12345.html" title="标题"><img src="封面" ...>...</a>...</li>
VIDEO_ITEM_RE = re.compile(
    r'<li[^>]*>\s*'
    r'<a[^>]*href="(/\d+\.html)"[^>]*title="([^"]*)"[^>]*>'
    r'(.*?)</a>',
    re.S | re.I,
)
# 兜底：href在后面的情况
VIDEO_ITEM_RE2 = re.compile(
    r'<li[^>]*>\s*'
    r'<a[^>]*title="([^"]*)"[^>]*href="(/\d+\.html)"[^>]*>'
    r'(.*?)</a>',
    re.S | re.I,
)
# 图片地址
IMG_SRC_RE = re.compile(r'<img[^>]*src="([^"]+)"', re.I)
IMG_DATA_RE = re.compile(r'<img[^>]*data-(?:src|original)="([^"]+)"', re.I)
# 标题（从h5/h4等提取）
TITLE_TAG_RE = re.compile(r'<h[3-6][^>]*>(.*?)</h[3-6]>', re.S | re.I)
# 详情页播放地址
RAW_URL_RE = re.compile(r"const\s+rawUrl\s*=\s*['\"]([^'\"]+)['\"]", re.I)
M3U8_RE = re.compile(r"https?://[^\s'\"$#]+\.m3u8(?:\?[^\s'\"]*)?", re.I)
# 总页数
TOTAL_PAGE_RE = re.compile(r"var\s+i\s*=\s*0;\s*i<(\d+);", re.I)
# HTML标签清理
TAG_CLEAN_RE = re.compile(r'<[^>]+>')


def _is_underage(text):
    """铁律13：检测是否含未成年相关关键词"""
    if not text:
        return False
    text_lower = text.lower()
    for kw in UNDERAGE_KEYWORDS:
        if kw.lower() in text_lower:
            return True
    return False


def _clean_text(text):
    """清理HTML标签和多余空白"""
    if not text:
        return ""
    text = TAG_CLEAN_RE.sub("", text)
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&quot;", '"').replace("&#39;", "'").replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", text).strip()


# ========== 双协议兼容基类 ==========
try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider(object):
        def __init__(self):
            self.extend = {}
        def init(self, extend):
            self.extend = extend if isinstance(extend, dict) else {}
        def homeContent(self, *args):
            return {}
        def categoryContent(self, *args):
            return {}
        def detailContent(self, *args):
            return {}
        def searchContent(self, *args):
            return {}
        def playerContent(self, *args):
            return {}
        def localProxy(self, *args):
            return [404, "text/plain", ""]
        def isVideoFormat(self, url):
            return False
        def manualVideoCheck(self):
            return False
        def getDependence(self):
            return ""
        def getName(self):
            return self.__class__.__name__


class Spider(BaseSpider):
    """午夜剧场 - 四壳通用Python Spider（纯正则解析，零依赖）"""

    def __init__(self):
        super().__init__()
        self.siteUrl = DEFAULT_HOST
        self.rawSite = DEFAULT_HOST
        self.HOST = DEFAULT_HOST
        self._cookie = ""
        self._hot_tags_cache = None
        self._hot_tags_time = 0

    # ========== 基础工具 ==========
    def _get(self, url, timeout=20):
        """发起GET请求（纯urllib标准库实现，零第三方依赖，任何Python环境都能跑）"""
        import sys as _sys
        def _dbg(msg):
            try:
                _sys.stderr.write("[午夜剧场][_get] %s -> %s\n" % (url[:60], msg))
            except Exception:
                pass

        try:
            headers = {
                "User-Agent": DEFAULT_UA,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate",
                "Referer": DEFAULT_HOST + "/",
                "Connection": "keep-alive",
            }
            if self._cookie:
                headers["Cookie"] = self._cookie

            req = Request(url, headers=headers)
            kwargs = {"timeout": timeout}
            if _SSL_CTX:
                kwargs["context"] = _SSL_CTX

            resp = urlopen(req, **kwargs)
            raw = resp.read()

            # 保存cookie
            try:
                ck = resp.headers.get("Set-Cookie", "")
                if ck:
                    self._cookie = ck.split(";")[0]
            except Exception:
                pass

            # gzip解压
            encoding = resp.headers.get("Content-Encoding", "").lower()
            if "gzip" in encoding:
                try:
                    raw = gzip.GzipFile(fileobj=BytesIO(raw)).read()
                except Exception:
                    pass

            # 编码检测
            charset = "utf-8"
            ct = resp.headers.get("Content-Type", "")
            cm = re.search(r"charset=([\w-]+)", ct, re.I)
            if cm:
                charset = cm.group(1)

            for enc in [charset, "utf-8", "gbk", "gb2312"]:
                try:
                    text = raw.decode(enc)
                    if text and len(text) > 50:
                        _dbg("成功, 长度=%d, 编码=%s" % (len(text), enc))
                        return text
                except Exception:
                    continue

            text = raw.decode("utf-8", errors="ignore")
            _dbg("强制解码, 长度=%d" % len(text))
            return text

        except HTTPError as e:
            _dbg("HTTP错误: %d" % e.code)
            return ""
        except URLError as e:
            _dbg("URL错误: %s" % str(e.reason)[:100])
            return ""
        except Exception as e:
            _dbg("异常: %s" % str(e)[:100])
            return ""


    def _build_url(self, path):
        """拼接完整URL"""
        if path.startswith("http"):
            return path
        if path.startswith("/"):
            return self.siteUrl + path
        return self.siteUrl + "/" + path

    def _fetch_hot_tags(self):
        """动态获取热门标签（从"更多关键词"页拉全量，过滤未成年，取前200个，缓存30分钟）"""
        import time as _time
        # 缓存30分钟
        if self._hot_tags_cache and (_time.time() - self._hot_tags_time) < 1800:
            return self._hot_tags_cache

        tags = []
        try:
            # 优先从"更多关键词"页拉全量标签
            html = self._get(self.siteUrl + "/label/more_keywords.html")
            if html:
                for a in re.finditer(r'<a[^>]*href="/s/([^"]+)\.html"[^>]*>([^<]+)</a>', html):
                    tag = a.group(2).strip()
                    # 铁律13：未成年标签剔除
                    if tag and tag not in tags and not _is_underage(tag):
                        tags.append(tag)
        except Exception:
            pass

        # 如果更多关键词页没拿到，从首页补
        if len(tags) < 10:
            try:
                html = self._get(self.siteUrl + "/cn/home/web/")
                if html:
                    m = re.search(r'热门关键词</h3>(.*?)</div>', html, re.S)
                    if m:
                        for a in re.finditer(r'<a[^>]*href="/s/([^"]+)\.html"[^>]*>([^<]+)</a>', m.group(1)):
                            tag = a.group(2).strip()
                            if tag and tag not in tags and not _is_underage(tag):
                                tags.append(tag)
            except Exception:
                pass

        # 铁律13：未成年标签已在提取时过滤，全部挂上不限制数量
        # TVBox筛选栏支持折叠滚动，标签多也能正常显示

        # 兜底标签
        if not tags:
            tags = ["人妻", "熟女", "丝袜", "制服", "巨乳", "无码", "中出", "口交",
                    "自慰", "偷拍", "乱伦", "强奸", "人妻熟女", "国产", "日本",
                    "3D动漫", "AI", "抖音风", "剧情", "对白", "高清", "无码流出", "中文字幕"]

        self._hot_tags_cache = tags
        self._hot_tags_time = _time.time()
        return tags

    # ========== 13标准接口 ==========
    def init(self, extend, *args):
        """初始化，支持ext覆盖站点地址"""
        if isinstance(extend, dict):
            self.extend = extend
            if extend.get("siteUrl"):
                self.siteUrl = extend["siteUrl"].rstrip("/")
                self.rawSite = self.siteUrl
                self.HOST = self.siteUrl
        elif isinstance(extend, str) and extend:
            try:
                ext = json.loads(extend)
                self.init(ext)
            except Exception:
                pass
        return ""

    def homeContent(self, *args):
        """首页：返回分类 + filters（排行榜筛选+热门标签筛选）"""
        classes = []
        for cat in CATEGORIES:
            classes.append({
                "type_id": cat["type_id"],
                "type_name": cat["type_name"],
            })

        # filters：标准四壳数组格式，每个筛选含key/name/init/value
        filters = {}
        rank_filter = [{"n": f["n"], "v": f["v"]} for f in RANK_FILTERS]
        hot_tags = self._fetch_hot_tags()
        # 铁律13：未成年标签剔除
        hot_tags = [t for t in hot_tags if not _is_underage(t)]
        tag_filter = [{"n": "全部", "v": ""}] + [{"n": t, "v": t} for t in hot_tags]

        for cat in CATEGORIES:
            filters[cat["type_id"]] = [
                {"key": "sort", "name": "排序", "init": "", "value": rank_filter},
                {"key": "tag", "name": "热门标签", "init": "", "value": tag_filter},
            ]

        return {
            "class": classes,
            "filters": filters,
        }

    def categoryContent(self, tid, page, filter=None, extend=None, *args):
        """分类页：筛选原理与网站一致
        - 分类页本身无筛选参数，仅分页 /vodtype/{id}-{page}.html
        - 排行榜是独立label页：/label/hot.html 等
        - 热门标签是搜索：/s/{tag}.html
        四壳协议签名：categoryContent(tid, page, filter, extend)
        """
        # 强制类型转换（TVBox传入的page/tid可能是字符串）
        try:
            tid = str(tid)
        except Exception:
            tid = "1"
        try:
            page = int(page)
        except Exception:
            page = 1

        import sys as _sys
        def _dbg(msg):
            try:
                _sys.stderr.write("[午夜剧场][category] tid=%s page=%s %s\n" % (tid, page, msg))
            except Exception:
                pass

        # 兼容不同壳的参数顺序和类型
        if filter is None:
            filter = {}
        if isinstance(filter, str):
            try:
                filter = json.loads(filter)
            except Exception:
                filter = {}
        elif not isinstance(filter, dict):
            if isinstance(extend, dict):
                filter = extend
            else:
                filter = {}

        sort_v = filter.get("排序", "") or filter.get("sort", "") or ""
        tag_v = filter.get("热门标签", "") or filter.get("tag", "") or filter.get("标签", "") or ""
        _dbg("sort=%s tag=%s filter=%s" % (sort_v, tag_v, str(filter)[:100]))

        # 热门标签筛选 → 走搜索（与网站一致：点击标签即搜索）
        if tag_v:
            _dbg("走搜索: %s" % tag_v)
            return self.searchContent(tag_v, page)

        # 排行榜筛选 → 走独立label页面（与网站一致）
        if sort_v and sort_v in RANK_PATH_MAP:
            label_path = RANK_PATH_MAP[sort_v]
            page_path = label_path if page == 1 else label_path.replace(".html", "-%d.html" % page)
            _dbg("走排行榜: %s" % page_path)
            html = self._get(self._build_url(page_path))
            _dbg("HTML长度: %d" % len(html or ""))
            result = self._parse_list_page(html, page)
            _dbg("解析结果: %d条" % len(result.get("list", [])))
            if not result.get("list"):
                result = self._diagnostic_result(html, page_path, page)
            elif len(result.get("list", [])) < PAGE_SIZE:
                result["pagecount"] = page
            return result

        # 正常分类页（与网站一致：/vodtype/{id}-{page}.html，无额外筛选参数）
        page_path = "/vodtype/%s-%d.html" % (tid, page) if page > 1 else "/vodtype/%s.html" % tid
        _dbg("走分类页: %s" % page_path)
        html = self._get(self._build_url(page_path))
        _dbg("HTML长度: %d" % len(html or ""))
        result = self._parse_list_page(html, page)
        _dbg("解析结果: %d条 pagecount=%s" % (len(result.get("list", [])), result.get("pagecount")))
        if not result.get("list"):
            result = self._diagnostic_result(html, page_path, page)
        return result

    def _diagnostic_result(self, html, page_path, page):
        """空列表时返回诊断视频，让用户在TVBox中看到错误原因"""
        html_len = len(html or "")
        if html_len == 0:
            reason = "网络请求失败（HTML长度=0），请检查TVBox网络是否能访问该网站"
        elif html_len < 500:
            reason = "返回内容过短（%d字节），可能被网站拦截或返回错误页" % html_len
        else:
            reason = "HTML获取成功（%d字节）但解析失败，可能网站结构已变更" % html_len

        diag = {
            "vod_id": "diag_%d" % page,
            "vod_name": "【诊断】%s" % reason,
            "vod_pic": "",
            "vod_remarks": "URL:%s | HTML:%d字节 | 站点:%s" % (page_path, html_len, self.siteUrl),
        }
        return {
            "page": page,
            "pagecount": 1,
            "limit": PAGE_SIZE,
            "total": 1,
            "list": [diag],
        }

    def _parse_list_page(self, html, page):
        """纯正则解析列表页，返回五键结构（零第三方依赖）"""
        # 强制类型转换
        try:
            page = int(page)
        except Exception:
            page = 1
        if not html:
            return {"page": page, "pagecount": 0, "limit": PAGE_SIZE, "total": 0, "list": []}

        videos = []
        seen_ids = set()

        # 尝试第一种匹配模式
        for m in VIDEO_ITEM_RE.finditer(html):
            try:
                href = m.group(1)
                title_attr = m.group(2)
                inner = m.group(3)

                vid_match = re.search(r"/(\d+)\.html", href)
                if not vid_match:
                    continue
                vod_id = vid_match.group(1)
                if vod_id in seen_ids:
                    continue

                # 标题：优先用title属性，再从内部h标签提取
                vod_name = _clean_text(title_attr)
                if not vod_name:
                    title_m = TITLE_TAG_RE.search(inner)
                    if title_m:
                        vod_name = _clean_text(title_m.group(1))
                if not vod_name:
                    vod_name = _clean_text(inner)

                # 封面
                vod_pic = ""
                img_m = IMG_SRC_RE.search(inner)
                if img_m:
                    vod_pic = img_m.group(1)
                else:
                    img_m = IMG_DATA_RE.search(inner)
                    if img_m:
                        vod_pic = img_m.group(1)

                # 铁律13：未成年剔除
                if _is_underage(vod_name):
                    continue

                if vod_name and vod_id:
                    seen_ids.add(vod_id)
                    videos.append({
                        "vod_id": vod_id,
                        "vod_name": vod_name,
                        "vod_pic": vod_pic,
                        "vod_remarks": "",
                    })
            except Exception:
                continue

        # 如果第一种没匹配到，尝试第二种（title在前href在后）
        if not videos:
            for m in VIDEO_ITEM_RE2.finditer(html):
                try:
                    title_attr = m.group(1)
                    href = m.group(2)
                    inner = m.group(3)

                    vid_match = re.search(r"/(\d+)\.html", href)
                    if not vid_match:
                        continue
                    vod_id = vid_match.group(1)
                    if vod_id in seen_ids:
                        continue

                    vod_name = _clean_text(title_attr)
                    if not vod_name:
                        title_m = TITLE_TAG_RE.search(inner)
                        if title_m:
                            vod_name = _clean_text(title_m.group(1))

                    vod_pic = ""
                    img_m = IMG_SRC_RE.search(inner)
                    if img_m:
                        vod_pic = img_m.group(1)

                    if _is_underage(vod_name):
                        continue

                    if vod_name and vod_id:
                        seen_ids.add(vod_id)
                        videos.append({
                            "vod_id": vod_id,
                            "vod_name": vod_name,
                            "vod_pic": vod_pic,
                            "vod_remarks": "",
                        })
                except Exception:
                    continue

        # 第三种：超简单匹配（只抓href="/数字.html" + 最近的title）
        if not videos:
            try:
                for m in re.finditer(r'href="/(\d+)\.html"[^>]*title="([^"]*)"', html):
                    vod_id = m.group(1)
                    if vod_id in seen_ids:
                        continue
                    vod_name = _clean_text(m.group(2))
                    if not vod_name:
                        continue
                    if _is_underage(vod_name):
                        continue
                    seen_ids.add(vod_id)
                    videos.append({
                        "vod_id": vod_id,
                        "vod_name": vod_name,
                        "vod_pic": "",
                        "vod_remarks": "",
                    })
            except Exception:
                pass

        # 第四种：暴力提取（所有详情页链接，用链接附近文本当标题）
        if not videos:
            try:
                for m in re.finditer(r'/(\d+)\.html', html):
                    vod_id = m.group(1)
                    if vod_id in seen_ids or len(vod_id) < 4:
                        continue
                    # 取链接前后50字符作为标题来源
                    start = max(0, m.start() - 30)
                    end = min(len(html), m.end() + 50)
                    snippet = html[start:end]
                    title_m = re.search(r'title="([^"]{2,60})"', snippet)
                    if title_m:
                        vod_name = _clean_text(title_m.group(1))
                    else:
                        text_m = re.search(r'>([^<]{2,40})<', snippet)
                        vod_name = _clean_text(text_m.group(1)) if text_m else "视频" + vod_id
                    if not vod_name or _is_underage(vod_name):
                        continue
                    seen_ids.add(vod_id)
                    videos.append({
                        "vod_id": vod_id,
                        "vod_name": vod_name,
                        "vod_pic": "",
                        "vod_remarks": "",
                    })
                    if len(videos) >= 40:
                        break
            except Exception:
                pass

        # 解析总页数
        pagecount = page
        total = len(videos)
        tm = TOTAL_PAGE_RE.search(html)
        if tm:
            try:
                pagecount = int(tm.group(1))
                total = pagecount * PAGE_SIZE
            except Exception:
                pass
        else:
            tail_match = re.search(r"/vodtype/\d+-(\d+)\.html[^>]*>尾页", html)
            if tail_match:
                try:
                    pagecount = int(tail_match.group(1))
                    total = pagecount * PAGE_SIZE
                except Exception:
                    pass
            elif videos:
                pagecount = page + 1 if len(videos) >= PAGE_SIZE else page

        return {
            "page": page,
            "pagecount": pagecount,
            "limit": PAGE_SIZE,
            "total": total,
            "list": videos,
        }

    def detailContent(self, ids, *args):
        """详情页：遍历ids，提取播放地址"""
        if not ids:
            return {"list": []}

        if isinstance(ids, str):
            ids = [ids]
        elif isinstance(ids, (list, tuple)):
            pass
        else:
            ids = [str(ids)]

        details = []
        for vod_id in ids:
            try:
                vod_id = str(vod_id).strip()
                if not vod_id:
                    continue
                html = self._get(self._build_url("/%s.html" % vod_id))
                if not html:
                    continue

                # 标题
                vod_name = ""
                title_m = re.search(r'<div class="head"><h3>(.*?)</h3>', html, re.S)
                if title_m:
                    vod_name = _clean_text(title_m.group(1))
                if not vod_name:
                    title_m = re.search(r"<title>(?:正在播放:)?([^<|-]+)", html)
                    if title_m:
                        vod_name = _clean_text(title_m.group(1))

                # 铁律13：未成年剔除
                if _is_underage(vod_name):
                    continue

                # 播放地址
                play_url = ""
                raw_match = RAW_URL_RE.search(html)
                if raw_match:
                    play_url = raw_match.group(1)
                else:
                    m3u8_match = M3U8_RE.search(html)
                    if m3u8_match:
                        play_url = m3u8_match.group(0)

                if not play_url:
                    continue

                # 类型
                vod_type = ""
                type_m = re.search(r'<a[^>]*href="/vodtype/\d+\.html"[^>]*>(.*?)</a>', html, re.S)
                if type_m:
                    vod_type = _clean_text(type_m.group(1))

                # 时间/备注
                vod_remarks = ""
                time_m = re.search(r"时间[：:]\s*([0-9\-]+)", html)
                if time_m:
                    vod_remarks = time_m.group(1)

                # 构造播放线路（单线路）
                vod_play_from = "在线播放"
                vod_play_url = "第1集$%s" % play_url

                details.append({
                    "vod_id": vod_id,
                    "vod_name": vod_name,
                    "vod_pic": "",
                    "vod_type": vod_type,
                    "vod_remarks": vod_remarks,
                    "vod_play_from": vod_play_from,
                    "vod_play_url": vod_play_url,
                    "vod_content": vod_name,
                })
            except Exception:
                continue

        return {"list": details}

    def searchContent(self, wd, page, *args):
        """搜索页"""
        # 强制类型转换
        try:
            page = int(page)
        except Exception:
            page = 1
        if not wd:
            return {"page": page, "pagecount": 0, "limit": PAGE_SIZE, "total": 0, "list": []}

        wd = wd.strip()
        # 铁律13：未成年关键词直接返回空
        if _is_underage(wd):
            return {"page": page, "pagecount": 0, "limit": PAGE_SIZE, "total": 0, "list": []}

        try:
            from urllib.parse import quote
            search_path = "/s/%s.html" % quote(wd)
        except Exception:
            search_path = "/s/%s.html" % wd

        html = self._get(self._build_url(search_path))
        return self._parse_list_page(html, page)

    def playerContent(self, flag, id, vipFlags, *args):
        """播放：返回m3u8直链，parse=0 jx=0"""
        url = id if id else ""
        if url and "$" in url:
            parts = url.split("$")
            if len(parts) >= 2:
                url = parts[-1]

        header = {
            "User-Agent": DEFAULT_UA,
            "Referer": self.rawSite + "/",
            "Origin": self.rawSite,
        }

        return {
            "parse": 0,
            "jx": 0,
            "url": url,
            "header": header,
        }

    def localProxy(self, flag, id, *args):
        return [404, "text/plain", ""]

    def isVideoFormat(self, url, *args):
        return bool(url and (".m3u8" in url or ".mp4" in url))

    def manualVideoCheck(self, *args):
        return False

    def getDependence(self, *args):
        return ""

    def getName(self, *args):
        return "午夜剧场"


# ========== 本地测试 ==========
if __name__ == "__main__":
    sp = Spider()
    print("=== homeContent ===")
    home = sp.homeContent()
    print("分类数:", len(home.get("class", [])))
    print("filters类型:", type(home.get("filters")))

    print("\n=== categoryContent 国产精品 ===")
    cat = sp.categoryContent("21", 1)
    print("page:", cat.get("page"), "pagecount:", cat.get("pagecount"))
    print("列表数:", len(cat.get("list", [])))
    if cat.get("list"):
        print("第一个:", cat["list"][0].get("vod_name", "")[:40])

    print("\n=== categoryContent 排行榜筛选 ===")
    cat2 = sp.categoryContent("21", 1, {"排序": "hot"})
    print("总排行列表数:", len(cat2.get("list", [])))

    print("\n=== categoryContent 热门标签筛选 ===")
    cat3 = sp.categoryContent("21", 1, {"热门标签": "人妻"})
    print("标签'人妻'列表数:", len(cat3.get("list", [])))

    print("\n=== searchContent ===")
    search = sp.searchContent("人妻", 1)
    print("搜索结果数:", len(search.get("list", [])))

    print("\n=== detailContent ===")
    if cat.get("list"):
        vid = cat["list"][0]["vod_id"]
        detail = sp.detailContent([vid])
        if detail.get("list"):
            d = detail["list"][0]
            print("标题:", d.get("vod_name", "")[:40])
            print("播放地址:", d.get("vod_play_url", "")[:80])
