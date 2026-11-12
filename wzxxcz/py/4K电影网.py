# coding=utf-8
"""
4K电影网 zzhczj.com | TVBox Python 爬虫 
关键:
  - 全站伪静态路由（从 /unit/2.html 频道页真实链接逐字实测）:
      频道      /unit/{type_id}.html         分页 /unit/{type_id}-{page}.html
      筛选      /pack/[by/{排序}/][class/{类型}/][area/{地区}/]id/{频道或分类ID}\
[/page/{页}][/year/{年份}][/lang/{语言}][/letter/{字母}].html
                （「按分类」是独立分类 id：国产剧=/pack/id/13.html 等）
                ★ 站点结果页模板存在第二种等价形态（year/lang 被渲染进 area 段：
                  /pack/area/2018/id/13.html），两套都试，命中率翻倍
      详情      /pagevid/{vod_id}.html
      播放      /slotplay/{vod_id}/{sid}/{nid}.html
  - 筛选 7 维与网页端 100% 同步: 分类(cat=站点真实分类id)/类型/地区/年份/语言/字母/排序，
    启动时实时抓站点筛选区解析（行级判定年份/语言）；短剧频道网页本身只有
    分类/字母/排序三维，如实照搬，不凭空加项
  - ★ 筛选主路径 = 「像用户一样逐项点击」：从分类页/频道页出发，每一步都从
    当前页面的筛选区提取真实链接再跳转（Cloudflare 缓存里存的正是这些 URL，命中率最高）；
    失败才退回直接拼 URL（两套形态互备）
  - ★ 源站数据库期性报错（动态页一律 HTTP 520，只有 CF 边缘缓存页可读）时：
      ① 成功过的页面永久落盘（.zzhczj_cache），源站再挂也秒开；
      ② 常驻后台搬运工按清单反复重抢（5 频道首页 -> 44 个分类页 -> 频道翻页 ->
         短剧/动漫字母页），源站抽搐复活的窗口自动补齐，无收获则指数退避；
      ③ 筛选失败默认返回空（绝不拿频道默认页冒充筛选结果）；
         需要「宁可给点内容也别空着」可在配置里加 {"fallback":"1"}
  - ★★ 自动容灾：本站片库上游就是「量子资源」
    （缩略图 img.lzipic.com 即量子图床，类型名逐一对应：国产动漫/大陆综艺/短剧/AI漫剧…），
    因此主站动态页 520 时按同一上游等价兜底，片单高度重合、播放链依旧直连：
      · 分类/筛选：按主站分类名映射到采源 type_id，year/area 走服务端筛选，
        class（类型）本地匹配；每屏合并 2 个源页凑够 36 条，与主站一屏条数一致
      · 详情：列表页已记下 vod_id->片名，主站详情页 520 时按片名去采源匹配同名片
      · 播放：采源 /share/xxx 分享页自动解析出真实 m3u8（parse=0 秒开，实测分片可取）
      · 搜索：主站 POST /find3.html 拿不到时同样接管
      ★ 主站能开就绝不走容灾，主站恢复后自动全走主站
  - 配置项: site=换域名、dynamic_filter=0 关动态筛选、fallback=1 空筛选降级、
            backup=0 彻底关闭容灾（只信主站）
  - 线路顺序严格按详情页「切换来源」下拉的显示顺序（页面里线路名与 sid 并不对应）
  - 播放直链从 player_aaaa 提取；当前线路播放页拿不到时自动接力其它线路同集，
    成功结果落盘缓存 7 天；所有 m3u8 已实测可直连（仅需 UA）
  - 列表「副标题」取缩略图角标 pic-text（正片 / 已完结 / 更新至xxxx期）
"""
import re
import os
import sys
import json
import time
import base64
import random
import hashlib
import tempfile
import threading
import urllib.parse

sys.path.append('..')

try:
    from base.spider import Spider
except ImportError:
    import requests as _rq
    try:
        import urllib3
        urllib3.disable_warnings()
    except Exception:
        pass

    class _BaseSpider:
        def __init__(self):
            self._session = None

        @property
        def _sess(self):
            if self._session is None:
                self._session = _rq.Session()
                self._session.verify = False
                adapter = _rq.adapters.HTTPAdapter(
                    pool_connections=10, pool_maxsize=10, max_retries=0)
                self._session.mount('https://', adapter)
                self._session.mount('http://', adapter)
            return self._session

        def fetch(self, url, headers=None, **kw):
            timeout = kw.pop('timeout', 15)
            method = kw.pop('method', 'get')
            data = kw.pop('data', None)
            if str(method).lower() == 'post':
                r = self._sess.post(url, headers=headers, timeout=timeout, data=data, **kw)
            else:
                r = self._sess.get(url, headers=headers, timeout=timeout, **kw)
            r.encoding = 'utf-8'
            return r

        def post(self, url, data=None, headers=None, **kw):
            kw['method'] = 'post'
            kw['data'] = data
            return self.fetch(url, headers=headers, **kw)

        def log(self, *a, **kw):
            try:
                print("[zzhczj]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.zzhczj.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/template/hl034/statics/img/load.gif"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# ---------------------------------------------------------------------------
# 备用源（容灾）：本站源站数据库阶段性故障，动态页一律 HTTP 520，
# 只有 Cloudflare 边缘缓存页可读。本站的片库正是「量子资源」供源
# （缩略图域名 img.lzipic.com 即量子图床），故用同一上游做兜底，
# 片单高度重合、播放链依旧可直连。主站能开就绝不走这里。
# ---------------------------------------------------------------------------
BACKUP_APIS = [
    ("量子资源", "https://cj.lziapi.com/api.php/provide/vod/"),
    ("非凡资源", "https://api.ffzyapi.com/api.php/provide/vod/"),
    ("魔都资源", "https://caiji.moduapi.cc/api.php/provide/vod/"),
]

CLASSES = [
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "2",  "type_name": "电视剧"},
    {"type_id": "3",  "type_name": "综艺片"},
    {"type_id": "4",  "type_name": "动漫"},
    {"type_id": "24", "type_name": "短剧"},
]

# ===== 静态兜底（homeContent 优先从站点实时解析，解析失败才用这份）=====
# 以下全部为 2026-11-11 从 5 个频道页实测抓取的真实值（含各频道真实分类 id）
# 注意：短剧频道网页上就没有类型/地区/年份筛选，兜底也保持为空
# 「按分类」是独立分类 id（/pack/id/{N}.html）
_CAT_MAP = {
    "1": [("动作片", "6"), ("喜剧片", "7"), ("爱情片", "8"), ("科幻片", "9"),
          ("剧情片", "10"), ("战争片", "11"), ("动画片", "41"), ("记录片", "12"),
          ("恐怖片", "39")],
    "2": [("国产剧", "13"), ("香港剧", "14"), ("韩国剧", "15"),
          ("欧美剧", "16"), ("台湾剧", "22"), ("日本剧", "21"),
          ("泰国剧", "20"), ("海外剧", "23")],
    "3": [("大陆综艺", "25"), ("日韩综艺", "26"), ("港台综艺", "27"),
          ("欧美综艺", "28")],
    "4": [("国产动漫", "29"), ("日本动漫", "30"), ("港台动漫", "42"),
          ("欧美动漫", "31"), ("海外动漫", "43")],
    "24": [("短剧大全", "40"), ("AI漫剧", "44")],
}

_CLASS_MAP = {
    "1": ["喜剧", "爱情", "恐怖", "动作", "科幻", "剧情", "战争", "警匪",
          "犯罪", "动画", "奇幻", "武侠", "冒险", "枪战", "悬疑", "惊悚",
          "经典", "青春", "文艺", "微电影", "古装", "历史", "运动", "农村",
          "儿童", "网络电影"],
    "2": ["古装", "战争", "青春偶像", "喜剧", "家庭", "犯罪", "动作", "奇幻",
          "剧情", "历史", "经典", "乡村", "情景", "商战", "网剧", "其他"],
    "3": ["选秀", "情感", "访谈", "播报", "旅游", "音乐", "美食", "纪实",
          "曲艺", "生活", "游戏互动", "财经", "求职"],
    "4": ["情感", "科幻", "热血", "推理", "搞笑", "冒险", "萝莉", "校园",
          "动作", "机战", "运动", "战争", "少年", "少女", "社会", "原创",
          "亲子", "益智", "励志", "其他"],
    "24": [],  # 网页上短剧频道无类型筛选
}

_AREA_MAP = {
    "1": ["大陆", "香港", "台湾", "美国", "法国", "英国", "日本", "韩国",
          "德国", "泰国", "印度", "意大利", "西班牙", "加拿大", "其他"],
    "2": ["内地", "韩国", "香港", "台湾", "日本", "美国", "泰国", "英国",
          "新加坡", "其他"],
    "3": ["内地", "港台", "日韩", "欧美"],
    "4": ["国产", "日本", "欧美", "其他"],
    "24": [],  # 网页上短剧频道无地区筛选
}

_YEAR_MAP = {
    "1": [str(y) for y in range(2026, 2009, -1)],
    "2": [str(y) for y in range(2026, 2009, -1)],
    "3": [str(y) for y in range(2018, 2003, -1)],
    "4": [str(y) for y in range(2018, 2003, -1)],
    "24": [],  # 网页上短剧频道无年份筛选
}

_LANG_MAP = {
    "1": ["国语", "英语", "粤语", "闽南语", "韩语", "日语", "法语", "德语", "其它"],
    "2": ["国语", "英语", "粤语", "闽南语", "韩语", "日语", "其它"],
    "3": ["国语", "英语", "粤语", "闽南语", "韩语", "日语", "其它"],
    "4": ["国语", "英语", "粤语", "闽南语", "韩语", "日语", "其它"],
    "24": [],
}

_LETTERS = [{"n": "全部", "v": ""}] + \
           [{"n": x, "v": x} for x in
            list("ABCDEFGHIJKLMNOPQRSTUVWXYZ") + ["0-9"]]

_SORTS = [{"n": "按时间", "v": "time"},
          {"n": "按人气", "v": "hits"},
          {"n": "按评分", "v": "score"}]

FILTERS = {}
for _c in CLASSES:
    _tid = _c["type_id"]
    _data = []
    if _CAT_MAP.get(_tid):
        _data.append({"key": "cat", "name": "分类",
                      "value": [{"n": "全部", "v": ""}] +
                               [{"n": n, "v": v} for n, v in _CAT_MAP[_tid]]})
    if _CLASS_MAP.get(_tid):
        _data.append({"key": "class", "name": "类型",
                      "value": [{"n": "全部", "v": ""}] +
                               [{"n": x, "v": x} for x in _CLASS_MAP[_tid]]})
    if _AREA_MAP.get(_tid):
        _data.append({"key": "area", "name": "地区",
                      "value": [{"n": "全部", "v": ""}] +
                               [{"n": x, "v": x} for x in _AREA_MAP[_tid]]})
    if _YEAR_MAP.get(_tid):
        _data.append({"key": "year", "name": "年份",
                      "value": [{"n": "全部", "v": ""}] +
                               [{"n": x, "v": x} for x in _YEAR_MAP[_tid]]})
    if _LANG_MAP.get(_tid):
        _data.append({"key": "lang", "name": "语言",
                      "value": [{"n": "全部", "v": ""}] +
                               [{"n": x, "v": x} for x in _LANG_MAP[_tid]]})
    _data.append({"key": "letter", "name": "字母", "value": _LETTERS})
    _data.append({"key": "sort", "name": "排序", "value": _SORTS})
    FILTERS[_tid] = _data


# ===================== 正则 =====================
# 列表卡片：<li class="stui-vodlist__item"> ... </li>
_RE_ITEM_BLOCK = re.compile(
    r'<li[^>]*class="[^"]*stui-vodlist__item[^"]*"[^>]*>([\s\S]*?)</li>', re.I)

_RE_HREF_PAGEVID = re.compile(r'href="([^"]*?/pagevid/[^"]+?)"', re.I)
_RE_TITLE_ATTR = re.compile(r'title="([^"]*)"', re.I)
_RE_PIC_ATTR = re.compile(r'(?:data-original|data-src|data-echo|src)="([^"]+)"', re.I)
_RE_PIC_TEXT = re.compile(
    r'<span[^>]*class="[^"]*pic-text[^"]*"[^>]*>([\s\S]*?)</span>', re.I)

# 旧式卡片（兜底：整段直配）
_RE_CARD_FALLBACK = re.compile(
    r'<a[^>]*class="[^"]*stui-vodlist__thumb[^"]*"[^>]*href="(/pagevid/[^"]+)"'
    r'[^>]*title="([^"]*)"[^>]*?(?:data-original|data-src|src)="([^"]*)"',
    re.S | re.I)

# 分页
_RE_PAGE_BLOCK = re.compile(
    r'<ul[^>]*class="[^"]*stui-page[^"]*"[^>]*>([\s\S]*?)</ul>', re.I)
_RE_TOTAL_PAGE = re.compile(r'<span[^>]*class="[^"]*num[^"]*"[^>]*>\s*\d+\s*/\s*(\d+)\s*</span>', re.I)
_RE_A_TAG = re.compile(r'<a[^>]*href="([^"]*)"[^>]*>([\s\S]*?)</a>', re.I)

# 筛选区
_RE_SCREEN_BLOCK = re.compile(
    r'<ul[^>]*class="[^"]*stui-screen__list[^"]*"[^>]*>([\s\S]*?)</ul>', re.I)
_RE_SCREEN_LABEL = re.compile(
    r'<span[^>]*class="[^"]*text-muted[^"]*"[^>]*>\s*按([^<]{1,6})</span>', re.I)
_RE_NAV_BLOCK = re.compile(
    r'<ul[^>]*class="[^"]*stui-pannel__nav[^"]*"[^>]*>([\s\S]*?)</ul>', re.I)
_RE_BY_VAL = re.compile(r'/by/([A-Za-z0-9_]+)/', re.I)

# 详情页
_RE_DETAIL_AREA = re.compile(
    r'<div[^>]*class="[^"]*stui-content__detail[^"]*"[^>]*>([\s\S]*?)<div[^>]*class="[^"]*playbtn',
    re.I)
_RE_H3_TITLE = re.compile(r'<h3[^>]*class="[^"]*title[^"]*"[^>]*>([\s\S]*?)</h3>', re.I)
_RE_SCORE = re.compile(r'<span[^>]*class="[^"]*score[^"]*"[^>]*>\s*([\d.]+)\s*<', re.I)
_RE_TYPE = re.compile(r'类型：</span>\s*([^<]*)<', re.I)
_RE_AREA = re.compile(r'地区：</span>\s*([^<]*)<', re.I)
_RE_YEAR = re.compile(r'年份：</span>\s*([^<]*)<', re.I)
_RE_ACTOR = re.compile(r'<p[^>]*class="[^"]*data[^"]*"[^>]*>\s*<span>\s*主演：\s*</span>([\s\S]*?)</p>', re.I)
_RE_DIRECTOR = re.compile(r'<p[^>]*class="[^"]*data[^"]*"[^>]*>\s*<span>\s*导演：\s*</span>([\s\S]*?)</p>', re.I)
_RE_DESC_BLOCK = re.compile(
    r'<div[^>]*class="[^"]*stui-content__desc[^"]*"[^>]*>([\s\S]*?)</div>', re.I)
_RE_DESC_SHORT = re.compile(
    r'<p[^>]*class="[^"]*desc[^"]*"[^>]*>([\s\S]*?)</p>', re.I)
_RE_PIC_TEXT_DETAIL = re.compile(
    r'<div[^>]*class="[^"]*stui-content__thumb[^"]*"[^>]*>([\s\S]*?)</div>', re.I)
_RE_META_DESC = re.compile(
    r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', re.I)
_RE_TAG_TITLE = re.compile(r'<title>([\s\S]*?)</title>', re.I)

# 播放列表
_RE_PLAYLIST_ZONE = re.compile(
    r'id="playlist"([\s\S]*?)(?:<!--\s*end 播放列表|剧情介绍)', re.I)
_RE_TAB_ITEM = re.compile(
    r'<a[^>]*href="#playlist(\d+)"[^>]*>([\s\S]*?)</a>', re.I)
_RE_EP_BLOCK = re.compile(
    r'<div[^>]*id="playlist(\d+)"[^>]*>([\s\S]*?)</ul>', re.I)
_RE_EP_A = re.compile(r'<a[^>]*href="([^"]+)"[^>]*>([\s\S]*?)</a>', re.I)

# 播放页
_RE_PLAYER_OBJ = re.compile(r'player_[A-Za-z0-9_]{0,24}\s*=\s*\{')
_RE_IFRAME = re.compile(r'<iframe[^>]+src=["\']([^"\']+)["\']', re.I)
_RE_M3U8 = re.compile(r'(https?:)?//[^\s"\'<>\\]+?\.m3u8[^\s"\'<>\\]*', re.I)
_RE_MP4 = re.compile(r'(https?:)?//[^\s"\'<>\\]+?\.mp4[^\s"\'<>\\]*', re.I)
# MacPlayer / 自定义播放器：url:"..." / Url:"..."
_RE_ANY_URL = re.compile(
    r'["\']?(?:url|Url|link|Link|src)["\']?\s*[:=]\s*["\']((?:https?:)?//[^"\']{10,})["\']')


class Spider(Spider):

    def getName(self):
        return "4K电影网"

    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}
        if not isinstance(self.extend, dict):
            self.extend = {}

        self.site_url = (self.extend.get("site") or HOST).rstrip("/")
        self.headers = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": self.site_url + "/",
            "Upgrade-Insecure-Requests": "1",
        }
        self.default_pic = DEFAULT_PIC
        self._play_cache = {}
        self._page_cache = {}
        self._filters_cache = None
        self._warmed = False
        self._disk_dir = None
        self._disk_checked = False
        self._bg_lock = threading.Lock()
        self._bg_started = False
        # fallback=1 时，筛选页拿不到就退回该频道首页列表（宁可给点内容也别空着）
        # 默认 0：宁可空，也绝不拿未筛选的内容冒充筛选结果
        self.fallback_unfiltered = str(self.extend.get("fallback", "0")) == "1"
        self._bz_types_cache = None      # 备用源类型表
        self._bz_types_ts = 0
        self._bz_used = ""               # 实际生效的备用源名
        # 列表页见过的 vod_id -> 片名：主站详情页 520 时靠它去备用源等价兜底
        self._name_cache = {}
        # backup=0 可彻底关闭容灾（只信主站）
        self.log("init: site=%s" % self.site_url)

    # ---------------------------------------------------------------- 基础
    def _warm_urls(self):
        """5 个频道首页：这几个页面几乎总是被 CF 缓存着，是最可靠的内容来源"""
        return ["%s/unit/%s.html" % (self.site_url, c["type_id"]) for c in CLASSES]

    def _warm_up(self):
        if self._warmed:
            return
        try:
            self._fetch(self.site_url + "/", timeout=12, retry=1)
            self._warmed = True
            self.log("预热完成")
        except Exception as e:
            self.log("预热失败: %s" % e)

    def _resp_text(self, rsp):
        if rsp is None:
            return ""
        try:
            if hasattr(rsp, "text") and rsp.text:
                return rsp.text
            if hasattr(rsp, "content"):
                return (rsp.content or b"").decode("utf-8", "ignore")
        except Exception:
            pass
        try:
            return str(rsp)
        except Exception:
            return ""

    def _fetch(self, url, timeout=20, headers=None, retry=3, data=None):
        """GET/POST 抓取，自带 520 / 空响应重试"""
        if not url:
            return ""
        for i in range(max(1, retry)):
            try:
                h = dict(self.headers)
                if headers:
                    h.update(headers)
                if data is not None:
                    try:
                        rsp = self.fetch(url, headers=h, timeout=timeout,
                                         method="post", data=data)
                    except TypeError:
                        rsp = self.fetch(url, headers=h, timeout=timeout, data=data)
                else:
                    rsp = self.fetch(url, headers=h, timeout=timeout)
                text = self._resp_text(rsp)
                code = getattr(rsp, "status_code", 0) or 0
                low = text or ""
                bad = (code in (403, 429, 502, 503, 520, 521, 522, 524)
                       or re.search(r"error\s*code[:\s]*5\d\d", low, re.I)
                       or "Web server is returning an unknown error" in low
                       or "cf-error-details" in low
                       or len(low) < 120)
                if not bad:
                    return text
                if i < retry - 1:
                    time.sleep(0.7 + i * 0.8 + random.random() * 0.4)
            except Exception as e:
                if i >= retry - 1:
                    self.log("fetch FAIL %s -> %s" % (url, e))
                time.sleep(0.6)
        return ""

    def _fix_url(self, url):
        if not url:
            return ""
        url = url.strip().replace("&amp;", "&")
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("http"):
            return url
        if url.startswith("/"):
            return self.site_url + url
        return urllib.parse.urljoin(self.site_url + "/", url)

    def _clean(self, s):
        if not s:
            return ""
        s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
        s = re.sub(r"<[^>]+>", "", s)
        s = (s.replace("&nbsp;", " ").replace("\xa0", " ")
              .replace("&amp;", "&").replace("&quot;", '"')
              .replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">")
              .replace("&ldquo;", "“").replace("&rdquo;", "”")
              .replace("&hellip;", "…").replace("&mdash;", "—"))
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n{2,}", "\n", s)
        return s.strip()

    def _safe_name(self, s):
        s = self._clean(s)
        s = s.replace("$", " ").replace("#", " ").replace("$$$", " ")
        return s.strip() or "正片"

    # ---------------------------------------------------------------- 列表
    def _extract_videos(self, html):
        videos = []
        seen = set()
        if not html:
            return videos

        for blk in _RE_ITEM_BLOCK.findall(html):
            mh = _RE_HREF_PAGEVID.search(blk)
            if not mh:
                continue
            href = mh.group(1).replace("&amp;", "&")
            if href in seen:
                continue

            mt = _RE_TITLE_ATTR.search(blk)
            name = self._clean(mt.group(1)) if mt else ""

            pic = ""
            for cand in _RE_PIC_ATTR.findall(blk):
                if cand and "load.gif" not in cand and not cand.startswith("data:"):
                    pic = cand
                    break

            remarks = ""
            mp = _RE_PIC_TEXT.search(blk)
            if mp:
                remarks = self._clean(mp.group(1))

            if not name:
                ml = re.findall(r'>([^<>]{1,60})</a>', blk)
                name = self._clean(ml[-1]) if ml else ""

            seen.add(href)
            videos.append({
                "vod_id": href,
                "vod_name": name or href.split("/")[-1].replace(".html", ""),
                "vod_pic": self._fix_url(pic) or self.default_pic,
                "vod_remarks": remarks,
            })

        if videos:
            return videos

        # 兜底：整段直配
        for href, alt, pic in _RE_CARD_FALLBACK.findall(html):
            href = href.replace("&amp;", "&")
            if href in seen:
                continue
            seen.add(href)
            videos.append({
                "vod_id": href,
                "vod_name": self._clean(alt) or href,
                "vod_pic": self._fix_url(pic) or self.default_pic,
                "vod_remarks": "",
            })
        return videos

    def _page_count(self, html):
        if not html:
            return 1
        m = _RE_TOTAL_PAGE.search(html)
        if m:
            try:
                return max(1, int(m.group(1)))
            except Exception:
                pass
        blk = _RE_PAGE_BLOCK.search(html)
        if blk:
            nums = []
            for href, txt in _RE_A_TAG.findall(blk.group(1)):
                t = self._clean(txt)
                if t.isdigit():
                    nums.append(int(t))
                if "尾页" in t:
                    mm = re.search(r"-(\d+)\.html", href) or re.search(r"/(\d+)\.html", href)
                    if mm:
                        nums.append(int(mm.group(1)))
            if nums:
                return max(nums)
        return 1

    def _page_tpl(self, html):
        """从分页区反推页码模板，如 /unit/1-2.html -> /unit/1-{p}.html"""
        blk = _RE_PAGE_BLOCK.search(html or "")
        if not blk:
            return ""
        block = blk.group(1)
        for href, txt in _RE_A_TAG.findall(block):
            t = self._clean(txt)
            if not t.isdigit() or not href:
                continue
            n = t
            cands = ["-%s.html" % n, "_%s.html" % n, "/page/%s.html" % n,
                     "/page/%s" % n, "page=%s" % n, "/%s.html" % n, "-%s-" % n]
            for pat in cands:
                if pat in href:
                    return href.replace(pat, pat.replace(n, "{p}"), 1)
        return ""

    def _page_url(self, html, cur_url, page):
        """取第 page 页的真实地址"""
        if page <= 1:
            return cur_url
        blk = _RE_PAGE_BLOCK.search(html or "")
        if blk:
            for href, txt in _RE_A_TAG.findall(blk.group(1)):
                if self._clean(txt) == str(page) and href:
                    return self._fix_url(href)
        tpl = self._page_tpl(html)
        if tpl:
            return self._fix_url(tpl.replace("{p}", str(page)))
        return ""

    # ---------------------------------------------------------------- 筛选
    def _key_from_href(self, href):
        h = href or ""
        if "/year/" in h:
            return "year"
        if "/lang/" in h:
            return "lang"
        if "/letter/" in h:
            return "letter"
        if "/area/" in h:
            return "area"
        if "/class/" in h:
            return "class"
        if re.search(r'/pack/id/\d+\.html$', h):
            return "cat"
        return ""

    def _key_from_label(self, label):
        label = label or ""
        if "分类" in label or "频道" in label:
            return "cat"
        if "类型" in label:
            return "class"
        if "地区" in label:
            return "area"
        if "年份" in label:
            return "year"
        if "语言" in label:
            return "lang"
        if "字母" in label:
            return "letter"
        return ""

    def _parse_screen(self, html):
        """解析筛选区，返回 {key: [(名称, 绝对URL)]}
        以链接形态判定维度（站点「按地区」标签有时写成语言列表，不能只信文字）
        """
        out = {}
        if not html:
            return out
        for block in _RE_SCREEN_BLOCK.findall(html):
            ml = _RE_SCREEN_LABEL.search(block)
            label = ml.group(1).strip() if ml else ""

            items = []
            for href, txt in _RE_A_TAG.findall(block):
                name = self._clean(txt)
                if not name or not href or href.startswith("javascript"):
                    continue
                items.append((name, self._fix_url(href)))
            if len(items) < 2:
                continue

            key = ""
            # 先用「非『全部』」链接形态判定维度（「全部」是 /pack/id/N.html，
            # 会被误判成 cat）；area 段再做行级判定：该站模板把年份/语言
            # 也生成为 /pack/area/{值}/（如 area/2018、area/国语）
            for name, href in items:
                if name == "全部":
                    continue
                k = self._key_from_href(href)
                if k:
                    key = k
                    break
            if key == "area":
                key = self._row_area_key(items) or "area"
            if not key:
                key = self._key_from_label(label)
            if not key or key in out:
                continue
            if key == "cat":
                # 「按频道」行（电影/电视剧/…）与「按分类」行同为 /pack/id/N.html，
                # 区别在于频道行没有「全部」项 —— 没有 /pack.html 的视为频道行，跳过
                if not any(h.rstrip("/").endswith("/pack.html") for _n, h in items):
                    continue
                # 频道 id 集合也是频道行特征（个别页面无 /pack.html 时兜底）
                ids = re.findall(r"/pack/id/(\d+)\.html", " ".join(h for _n, h in items))
                if ids and all(i in {c["type_id"] for c in CLASSES} for i in ids):
                    continue
            out[key] = items

        # 排序 nav
        nb = _RE_NAV_BLOCK.search(html)
        if nb:
            items = []
            for href, txt in _RE_A_TAG.findall(nb.group(1)):
                mb = _RE_BY_VAL.search(href)
                if not mb:
                    continue
                items.append((self._clean(txt), mb.group(1)))
            if items:
                out["sort"] = items
        return out

    def _match_screen(self, html, key, val):
        screen = self._parse_screen(html)
        items = screen.get(key) or []
        val = str(val).strip()
        for name, href in items:
            if name == val:
                return href
        for name, href in items:
            if val and (val in name or name in val):
                return href
        return ""

    # ---------------------------------------------------------------- 首页
    def _build_filters_from_site(self):
        """直接从站点筛选区抓真实选项，保证与网页一致；任何异常返回 None
        网页顺序: 按分类(独立id) -> 按类型 -> 按地区 -> 按年份 -> 按语言 -> 按字母 -> 排序
        """
        filters = {}
        for c in CLASSES:
            tid = c["type_id"]
            html = self._fetch("%s/unit/%s.html" % (self.site_url, tid),
                               timeout=8, retry=1)
            screen = self._parse_screen(html)
            data = []
            if screen.get("cat"):
                # 「按分类」是独立的分类 id（如 国产剧 -> /pack/id/13.html）
                items = []
                for n, href in screen["cat"]:
                    mnum = re.search(r"/pack/id/(\d+)\.html", href)
                    if mnum and n != "全部":
                        items.append({"n": n, "v": mnum.group(1)})
                if items:
                    data.append({"key": "cat", "name": "分类",
                                 "value": [{"n": "全部", "v": ""}] + items})
            if screen.get("class"):
                data.append({"key": "class", "name": "类型",
                             "value": [{"n": "全部", "v": ""}] +
                                      [{"n": n, "v": n} for n, _ in screen["class"]]})
            if screen.get("area"):
                data.append({"key": "area", "name": "地区",
                             "value": [{"n": "全部", "v": ""}] +
                                      [{"n": n, "v": n} for n, _ in screen["area"]]})
            if screen.get("year"):
                # 站点年份行本身有重复乱序项，去重保持原有顺序
                yitems, yseen = [], set()
                for n, _href in screen["year"]:
                    if n not in yseen:
                        yseen.add(n)
                        yitems.append(n)
                data.append({"key": "year", "name": "年份",
                             "value": [{"n": "全部", "v": ""}] +
                                      [{"n": n, "v": n} for n in yitems]})
            if screen.get("lang"):
                data.append({"key": "lang", "name": "语言",
                             "value": [{"n": "全部", "v": ""}] +
                                      [{"n": n, "v": n} for n, _ in screen["lang"]]})
            if screen.get("letter"):
                data.append({"key": "letter", "name": "字母",
                             "value": [{"n": "全部", "v": ""}] +
                                      [{"n": n, "v": n} for n, _ in screen["letter"]]})
            if screen.get("sort"):
                # 固定按网页默认顺序（时间→人气→评分），不受缓存页 active 状态影响
                sorder = {"time": 0, "hits": 1, "score": 2}
                sitems = [(n, v) for n, v in screen["sort"] if v in sorder]
                sitems.sort(key=lambda x: sorder[x[1]])
                data.append({"key": "sort", "name": "排序",
                             "value": [{"n": n, "v": v} for n, v in sitems]})
            if data:
                filters[tid] = data
        # 解析失败的频道用静态兜底补齐，保证筛选栏不缺项
        for c in CLASSES:
            tid = c["type_id"]
            if tid not in filters:
                filters[tid] = FILTERS.get(tid) or []
        return filters or None

    def _get_filters(self):
        if self._filters_cache is not None:
            return self._filters_cache
        use_dynamic = str(self.extend.get("dynamic_filter", "1")) != "0"
        filters = None
        if use_dynamic:
            try:
                filters = self._build_filters_from_site()
            except Exception as e:
                self.log("动态筛选失败: %s" % e)
        if not filters:
            filters = FILTERS
        self._filters_cache = filters
        return filters

    def homeContent(self, filter=False):
        self._start_bg_prefetch()
        return {"class": CLASSES, "filters": self._get_filters()}

    # ---------------------------------------------------- 后台静默预取（蚂蚁搬家）
    def _start_bg_prefetch(self):
        """源站大面积 520 时，后台按节奏慢慢抓，抓到一页就永久落盘一页。
        用户翻到哪算哪，越用越全（daemon 线程，不阻塞主流程）"""
        with self._bg_lock:
            if self._bg_started:
                return
            self._bg_started = True
        try:
            t = threading.Thread(target=self._bg_prefetch)
            t.daemon = True
            t.start()
        except Exception:
            pass

    def _prefetch_queue(self):
        """预热清单：源站数据库 intermittently 复活时，按这张清单把页面抢下来。
        顺序按「用户最常点」排：频道首页 -> 全部分类页 -> 频道翻页 -> 短剧/动漫的字母页
        """
        urls = []
        for c in CLASSES:                                   # ① 5 个频道首页
            urls.append("%s/unit/%s.html" % (self.site_url, c["type_id"]))
        for _tid, cats in _CAT_MAP.items():                 # ② 44 个「按分类」页
            for _name, cid in cats:
                urls.append("%s/pack/id/%s.html" % (self.site_url, cid))
        for c in CLASSES:                                   # ③ 频道第 2/3 页
            tid = c["type_id"]
            for p in (2, 3):
                urls.append("%s/unit/%s-%d.html" % (self.site_url, tid, p))
        for tid in ("24", "4"):                             # ④ 短剧/动漫 字母页（两站筛选维度里只剩字母）
            for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                urls.append("%s/pack/id/%s/letter/%s.html"
                            % (self.site_url, tid, ch))
        seen, queue = set(), []
        for u in urls:
            if u not in seen:
                seen.add(u)
                queue.append(u)
        return queue

    def _bg_prefetch(self):
        """常驻搬运工：只要 TVBox 进程活着，就按节奏反复重试清单里的页面。
        本站源站数据库大面积报错（返回 520，仅 CF 边缘缓存页可读），
        但历史上偶尔会抽搐复活几十秒 —— 抓住那个窗口把页面抢下来永久落盘，
        之后即使源站继续挂，这些筛选结果也能秒开（磁盘快照无限期有效）。"""
        try:
            time.sleep(2)
            warm = self._warm_urls()
            for u in warm:                      # 先把 5 个频道首页（几乎总是有缓存）落盘
                if self._disk_get(u):
                    continue
                h = self._fetch(u, timeout=12, retry=2)
                if h and self._extract_videos(h):
                    self._disk_put(u, h)
            queue = self._prefetch_queue()
            rnd = 0
            idle = 0
            while True:
                rnd += 1
                todo = [u for u in queue if not self._disk_get(u)]
                if not todo:
                    self.log("后台预取: 清单 %d 页全部就绪" % len(queue))
                    time.sleep(1800)        # 全都齐了，半小时后再看有没有新页
                    queue = self._prefetch_queue()
                    continue
                got = 0
                for u in todo:
                    h = self._fetch(u, timeout=8, retry=1)
                    if h and len(h) > 120 and self._extract_videos(h):
                        self._disk_put(u, h)
                        got += 1
                        self.log("抢到页面: %s" % u)
                    time.sleep(1.8 + random.random())
                self.log("后台预取第%d轮: 新增 %d / 待补 %d"
                         % (rnd, got, len(todo) - got))
                if got:
                    idle = 0
                    time.sleep(300)
                else:
                    # 整轮颗粒无收 -> 指数退避，别把源站和 CF 打得更死
                    idle = min(idle + 1, 4)
                    time.sleep(min(240 * (2 ** idle), 3600))
        except Exception as e:
            self.log("后台预取异常: %s" % e)

    def homeVideoContent(self):
        self._warm_up()
        html = self._fetch(self.site_url + "/")
        self.log("home HTML 长度: %d" % len(html))
        videos = self._extract_videos(html)
        self.log("home 视频: %d 条" % len(videos))
        return {"list": videos[:60]}

    # ---------------------------------------------------------------- 分类
    def _cache_root(self):
        """磁盘缓存目录（源站大面宕机，成功过一次的页面必须永久留底）"""
        if self._disk_checked:
            return self._disk_dir
        self._disk_checked = True
        cands = []
        try:
            cands.append(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                      ".zzhczj_cache"))
        except Exception:
            pass
        cands.append(os.path.join(tempfile.gettempdir(), "zzhczj_cache"))
        for d in cands:
            try:
                os.makedirs(d, exist_ok=True)
                probe = os.path.join(d, ".w")
                with open(probe, "w") as f:
                    f.write("1")
                os.remove(probe)
                self._disk_dir = d
                return d
            except Exception:
                continue
        self._disk_dir = ""
        return ""

    def _disk_path(self, url):
        d = self._cache_root()
        if not d:
            return ""
        return os.path.join(d, hashlib.md5(url.encode("utf-8")).hexdigest() + ".html")

    def _disk_get(self, url):
        p = self._disk_path(url)
        if not p:
            return ""
        try:
            if os.path.exists(p) and os.path.getsize(p) > 120:
                with open(p, "r", encoding="utf-8", errors="ignore") as f:
                    return f.read()
        except Exception:
            pass
        return ""

    def _disk_put(self, url, text):
        p = self._disk_path(url)
        if not p or not text or len(text) < 120:
            return
        try:
            with open(p, "w", encoding="utf-8", errors="ignore") as f:
                f.write(text)
            self._disk_gc()
        except Exception:
            pass

    def _disk_gc(self):
        """磁盘缓存超 400 个就按修改时间删掉最旧的 150 个"""
        d = self._cache_root()
        if not d:
            return
        try:
            files = [os.path.join(d, f) for f in os.listdir(d) if f.endswith(".html")]
            if len(files) <= 400:
                return
            files.sort(key=lambda p: os.path.getmtime(p))
            for p in files[:150]:
                try:
                    os.remove(p)
                except Exception:
                    pass
        except Exception:
            pass

    def _fetch_cached(self, url, timeout=15, retry=2, headers=None):
        """分类/筛选页抓取（三级缓存）：
        1) 内存 5 分钟：命中秒回
        2) 网络成功：写内存 + 落盘永久留底
        3) 网络失败（源站 520）：回读磁盘任意年龄的旧快照 —— 宁可给旧内容
           也绝不给「回退到频道默认页」那种牛头不对马嘴的结果
        """
        now = time.time()
        hit = self._page_cache.get(url)
        if hit:
            ts, text = hit
            if text and now - ts < 300:
                return text
            if not text and now - ts < 40:
                return ""
        html = self._fetch(url, timeout=timeout, retry=retry, headers=headers)
        ok = bool(html) and len(html) > 120
        if ok:
            self._page_cache[url] = (now, html)
            self._disk_put(url, html)
        else:
            old = self._disk_get(url)
            if old:
                self._page_cache[url] = (now, old)
                self.log("源站超时，改用本地快照: %s" % url)
                return old
            self._page_cache[url] = (now, "")
        # 缓存别无限膨胀
        if len(self._page_cache) > 200:
            for k in sorted(self._page_cache, key=lambda k: self._page_cache[k][0])[:100]:
                del self._page_cache[k]
        return html

    def _norm_extend(self, extend):
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        if not isinstance(extend, dict):
            extend = {}
        out = {}
        for k, v in extend.items():
            if v in ("", None, "全部", "0"):
                continue
            out[k] = v
        return out

    def _build_filter_url(self, tid, ext, page=1):
        """按站点真实伪静态规则拼装（2026-11-11 从 /unit/2.html 频道页真实链接逐字提取）：
        /pack/[by/{排序}/][class/{类型}/][area/{地区}/]id/{频道或分类ID}\
[/page/{页}][/year/{年份}][/lang/{语言}][/letter/{字母}].html
        实测真实链接：
            /pack/class/古装/id/2.html
            /pack/area/内地/id/2.html
            /pack/id/2/year/2018.html      <- 年份在 id 之后
            /pack/id/2/lang/国语.html       <- 语言在 id 之后
            /pack/id/2/letter/A.html
            /pack/id/2/page/2.html
            /pack/by/time/id/2.html
        注意：站点 pack 结果页的筛选区模板有 bug，会把年份/语言渲染成
        /pack/area/2018/id/13.html（错误形态，别照抄！），频道页 unit 的才是对的
        """
        def q(v):
            return urllib.parse.quote(str(v))

        parts = []
        if ext.get("sort"):
            parts.append("by/" + q(ext["sort"]))
        if ext.get("class"):
            parts.append("class/" + q(ext["class"]))
        if ext.get("area"):
            parts.append("area/" + q(ext["area"]))
        # 「分类」选中时它是独立的分类 id（/pack/id/13.html），替代频道 id
        ident = str(ext.get("cat") or tid)
        parts.append("id/" + str(ident))
        try:
            if int(page) > 1:
                parts.append("page/%d" % int(page))
        except Exception:
            pass
        if ext.get("year"):
            parts.append("year/" + q(ext["year"]))
        if ext.get("lang"):
            parts.append("lang/" + q(ext["lang"]))
        if ext.get("letter"):
            parts.append("letter/" + q(ext["letter"]))
        return "%s/pack/%s.html" % (self.site_url, "/".join(parts))

    _LANG_WORDS = {"国语", "英语", "粤语", "闽南语", "韩语", "日语",
                   "法语", "德语", "其它", "其他"}

    def _build_filter_url_alt(self, tid, ext, page=1):
        """备用形态：站点「结果页」模板把年份/语言渲染成 area 段（/pack/area/2018/id/13.html）。
        与 _build_filter_url 的 /pack/id/2/year/2018.html 是同一后端的两种入口，
        两套都试可将 CF 缓存命中概率翻倍。仅当年份/语言存在时才不同。
        """
        if not (ext.get("year") or ext.get("lang")):
            return ""
        def q(v):
            return urllib.parse.quote(str(v))
        parts = []
        if ext.get("sort"):
            parts.append("by/" + q(ext["sort"]))
        if ext.get("class"):
            parts.append("class/" + q(ext["class"]))
        for k in ("area", "year", "lang"):
            if ext.get(k):
                parts.append("area/" + q(ext[k]))
        ident = str(ext.get("cat") or tid)
        parts.append("id/" + str(ident))
        try:
            if int(page) > 1:
                parts.append("page/%d" % int(page))
        except Exception:
            pass
        if ext.get("letter"):
            parts.append("letter/" + q(ext["letter"]))
        return "%s/pack/%s.html" % (self.site_url, "/".join(parts))

    def _row_area_key(self, items):
        """行级判定 area 段维度：该站模板把年份/语言也生成为 /pack/area/{值}/。
        行内 area 值全为数字 -> 年份；多为语言词 -> 语言；否则 -> 地区
        """
        vals = []
        for _n, h in items:
            m = re.search(r"/pack/area/([^/]+)/", h)
            if m:
                vals.append(urllib.parse.unquote(m.group(1)))
        vals = [v for v in vals if v]
        if not vals:
            return ""
        if all(v.isdigit() for v in vals):
            return "year"
        hits = sum(1 for v in vals
                   if v.endswith("语") or v in self._LANG_WORDS)
        if hits and hits * 2 >= len(vals):
            return "lang"
        return "area"

    def _follow_filter(self, tid, ext, page=1):
        """像人一样逐个点筛选项，全程只使用页面里真实存在的链接。
        这是命中率最高的路径：用户浏览器也是这样一页页点过去的，
        Cloudflare 缓存里存的正是这些 URL。
        起点选择与用户一致：选了分类就从分类页起步（/pack/id/13.html），
        否则从频道页起步（/unit/2.html）。
        """
        cat = str(ext.get("cat") or "")
        cur_url = ""
        html = ""
        if cat:
            cur_url = "%s/pack/id/%s.html" % (self.site_url, cat)
        else:
            cur_url = "%s/unit/%s.html" % (self.site_url, tid)
        html = self._fetch_cached(cur_url, timeout=15, retry=2)
        if not html:
            alt = "%s/pack/id/%s.html" % (self.site_url, cat or tid)
            cur_url = alt
            html = self._fetch_cached(alt, timeout=15, retry=2)
        if not html:
            self.log("跟随起点打不开: %s" % cur_url)
            return "", ""

        for key in ("class", "area", "year", "lang", "letter"):
            val = ext.get(key)
            if not val:
                continue
            href = self._match_screen(html, key, val)
            if not href or href == cur_url:
                # 页面上找不到这一项 -> 无法保证与网页一致，整单放弃
                self.log("筛选项不存在于页面: %s=%s" % (key, val))
                return "", ""
            nxt = self._fetch_cached(href, timeout=12, retry=3)
            if not nxt or not self._extract_videos(nxt):
                # 该项请求失败 -> 整单放弃，绝不返回「只筛了一半」的错内容
                self.log("筛选项请求失败: %s=%s -> %s" % (key, val, href))
                return "", ""
            cur_url, html = href, nxt

        if ext.get("sort"):
            # 排序也走页面真实链接（by/xxx 段），不自己拼
            m2 = re.search(r'href="([^"]*/pack/by/%s/[^"]*)"'
                           % re.escape(str(ext["sort"])), html or "")
            if m2:
                href = self._fix_url(m2.group(1))
                nxt = self._fetch_cached(href, timeout=12, retry=2)
                if nxt and self._extract_videos(nxt):
                    cur_url, html = href, nxt

        if page > 1:
            purl = self._page_url(html, cur_url, page)
            if purl and purl != cur_url:
                nxt = self._fetch_cached(purl, timeout=15, retry=2)
                if nxt:
                    cur_url, html = purl, nxt
        return html, cur_url

    # ---------------------------------------------- 备用源（主站不可用时接管）
    def _bz_enabled(self):
        return str(self.extend.get("backup", "1")) != "0"

    def _bz_call(self, params, timeout=12, retry=2):
        """调用备用采集 API（苹果CMS 标准 json 接口），返回 dict；全挂返回 None"""
        # 一旦某个源成功过就优先沿用，保证同一列表翻页时片单来源一致
        eps = list(BACKUP_APIS)
        if self._bz_used:
            eps.sort(key=lambda x: 0 if x[0] == self._bz_used else 1)
        for name, base in eps:
            try:
                url = base + "?" + urllib.parse.urlencode(params)
                txt = self._fetch(url, timeout=timeout, retry=retry,
                                  headers={"Accept": "application/json"})
                if not txt:
                    continue
                txt = txt.strip()
                if not txt.startswith("{"):
                    continue
                d = json.loads(txt)
                if isinstance(d, dict) and (d.get("list") is not None
                                            or d.get("class") is not None):
                    self._bz_used = name
                    return d
            except Exception:
                continue
        return None

    def _bz_types(self):
        """备用源类型表（名称匹配用，缓存 1 小时）"""
        now = time.time()
        if self._bz_types_cache and now - self._bz_types_ts < 3600:
            return self._bz_types_cache
        d = self._bz_call({"ac": "list"}, timeout=10, retry=1)
        out = []
        for c in (d or {}).get("class") or []:
            try:
                out.append((int(c.get("type_id")), str(c.get("type_name") or "")))
            except Exception:
                pass
        if out:
            self._bz_types_cache, self._bz_types_ts = out, now
        return out or []

    # 主站分类名 -> 备用源类型名的匹配词（按优先级）
    _BZ_ALIAS = [
        ("AI漫剧",   ["AI漫剧", "漫剧"]),
        ("短剧大全", ["短剧"]),
        ("国产动漫", ["国产动漫", "国产动画"]),
        ("日本动漫", ["日韩动漫", "日本动漫"]),
        ("港台动漫", ["港台动漫"]),
        ("欧美动漫", ["欧美动漫"]),
        ("海外动漫", ["海外动漫"]),
        ("大陆综艺", ["大陆综艺"]),
        ("日韩综艺", ["日韩综艺"]),
        ("港台综艺", ["港台综艺"]),
        ("欧美综艺", ["欧美综艺"]),
    ]
    _BZ_TID_ALIAS = {
        "1": ["电影片", "电影"], "2": ["连续剧"], "3": ["综艺片", "综艺"],
        "4": ["动漫片", "动漫"], "24": ["短剧"],
    }

    def _bz_type_id(self, tid, ext):
        types = self._bz_types()
        if not types:
            return None
        catname = ""
        for _t, cats in _CAT_MAP.items():
            for n, cid in cats:
                if str(cid) == str(ext.get("cat") or ""):
                    catname = n
        words = []
        if catname:
            for key, al in self._BZ_ALIAS:
                if catname == key:
                    words = list(al)
                    break
            if not words:
                words = [catname]
        else:
            words = list(self._BZ_TID_ALIAS.get(str(tid), []))
        for w in words:
            for t_id, t_name in types:
                if w and w in t_name:
                    return t_id
        return None

    def _bz_area(self, area):
        """主站地区值 -> 备用源能识别的写法"""
        m = {"内地": "大陆", "台湾": "台湾", "香港": "香港", "其它": "其他"}
        return m.get(area, area)

    def _bz_category(self, tid, ext, page):
        """用备用源构造分类/筛选结果，返回 (list, pagecount)"""
        t_id = self._bz_type_id(tid, ext)
        if not t_id:
            return [], 0
        base = {"ac": "detail", "t": t_id}
        if ext.get("year"):
            base["year"] = ext["year"]
        if ext.get("area"):
            base["area"] = self._bz_area(ext["area"])
        kw = str(ext.get("class") or "")
        page = max(1, int(page))

        # 备用源单页 20 条，本站一屏 36 条 -> 每屏合并 2 个源页（有 class 时多翻几页筛选）
        n_src = 4 if kw else 2
        start_pg = (page - 1) * n_src + 1
        raw, seen = [], set()
        total = 0
        for k in range(n_src):
            p2 = dict(base)
            p2["pg"] = start_pg + k
            d = self._bz_call(p2)
            if not d:
                break
            try:
                total = max(total, int(d.get("total") or 0))
            except Exception:
                pass
            got = 0
            for v in d.get("list") or []:
                vid = str(v.get("vod_id") or "")
                if not vid or vid in seen:
                    continue
                seen.add(vid)
                got += 1
                raw.append(v)
            if got == 0:
                break
            if kw and len([x for x in raw
                           if kw in str(x.get("vod_class") or "")]) >= 36:
                break
        if kw:
            raw = [v for v in raw if kw in str(v.get("vod_class") or "")]

        out = []
        for v in raw[:36]:
            out.append({
                "vod_id": "bz|" + str(v.get("vod_id")),
                "vod_name": str(v.get("vod_name") or ""),
                "vod_pic": str(v.get("vod_pic") or "") or self.default_pic,
                "vod_remarks": str(v.get("vod_remarks") or ""),
                "vod_year": str(v.get("vod_year") or ""),
                "vod_area": str(v.get("vod_area") or ""),
            })
        pc = 0
        if total:
            pc = max(1, min(9999, (total + 20 * n_src - 1) // (20 * n_src)))
        if pc < page:
            pc = page
        return out, pc

    def _bz_detail(self, bvid):
        d = self._bz_call({"ac": "detail", "ids": bvid}, timeout=15, retry=2)
        lst = (d or {}).get("list") or []
        if not lst:
            return {"list": []}
        v = lst[0]
        name = str(v.get("vod_name") or "")
        froms = str(v.get("vod_play_from") or "").split("$$$")
        urls = str(v.get("vod_play_url") or "").split("$$$")
        lines, play_urls = [], []
        for i, grp in enumerate(urls):
            flag = froms[i] if i < len(froms) else ("线路%d" % (i + 1))
            eps = []
            for part in grp.split("#"):
                if not part.strip():
                    continue
                if "$" in part:
                    ep_name, ep_url = part.split("$", 1)
                else:
                    ep_name, ep_url = ("第%d集" % (len(eps) + 1)), part
                if not ep_url.startswith("http"):
                    continue
                token = base64.urlsafe_b64encode(
                    ep_url.encode("utf-8")).decode("ascii")
                eps.append("%s$bzplay|%s|%s"
                           % (ep_name.strip() or ("第%d集" % (len(eps) + 1)),
                              token, urllib.parse.quote(flag)))
            if eps:
                lines.append(flag)
                play_urls.append("#".join(eps))
        content = self._clean(str(v.get("vod_content") or ""))
        if content and not content.startswith(INTRO_PREFIX):
            content = INTRO_PREFIX + "\n" + content
        return {"list": [{
            "vod_id": "bz|" + bvid,
            "vod_name": name,
            "vod_pic": str(v.get("vod_pic") or "") or self.default_pic,
            "type_name": str(v.get("vod_class") or ""),
            "vod_year": str(v.get("vod_year") or ""),
            "vod_area": str(v.get("vod_area") or ""),
            "vod_remarks": str(v.get("vod_remarks") or ""),
            "vod_actor": str(v.get("vod_actor") or ""),
            "vod_director": str(v.get("vod_director") or ""),
            "vod_content": content,
            "vod_play_from": "$$$".join(lines),
            "vod_play_url": "$$$".join(play_urls),
        }]}

    def _bz_search(self, key, page):
        d = self._bz_call({"ac": "detail", "wd": key, "pg": int(page or 1)},
                          timeout=15, retry=2)
        out = []
        for v in (d or {}).get("list") or []:
            out.append({
                "vod_id": "bz|" + str(v.get("vod_id")),
                "vod_name": str(v.get("vod_name") or ""),
                "vod_pic": str(v.get("vod_pic") or "") or self.default_pic,
                "vod_remarks": str(v.get("vod_remarks") or ""),
                "vod_year": str(v.get("vod_year") or ""),
                "vod_area": str(v.get("vod_area") or ""),
            })
        return out

    def _remember(self, videos):
        """记住列表页的 vod_id->片名，供详情页主站 520 时兜底"""
        try:
            for v in videos or []:
                vid = str(v.get("vod_id") or "")
                nm = str(v.get("vod_name") or "")
                if vid and nm:
                    self._name_cache[vid] = nm
            if len(self._name_cache) > 3000:
                self._name_cache.clear()
        except Exception:
            pass

    def _bz_detail_by_name(self, vod_id, want=None):
        """主站详情页不可用（源站 520）-> 用片名去备用源匹配同名片，详情/播放照样能看"""
        if not self._bz_enabled():
            return {"list": []}
        raw = (want or self._name_cache.get(vod_id) or "").strip()
        if not raw:
            return {"list": []}
        # 先按原始片名（含「第X季/年番」）匹配，匹配不到再退化到主标题
        keys = [raw]
        k2 = re.sub(r"\s*(第[一二三四五六七八九十\d]+季|年番\d*|动画版)\s*", "",
                    raw).strip()
        if k2 and k2 != raw:
            keys.append(k2)

        for key in keys:
            d = self._bz_call({"ac": "detail", "wd": key, "pg": 1},
                              timeout=15, retry=2)
            lst = (d or {}).get("list") or []
            if not lst:
                continue
            # 采源按相关度排序：优先「完全同名」，其次第一条名字相关的
            best = None
            for v in lst:
                if str(v.get("vod_name") or "").strip() == key:
                    best = v
                    break
            if not best:
                for v in lst:
                    nm = str(v.get("vod_name") or "")
                    if nm and (key in nm or nm in key):
                        best = v
                        break
            if not best:
                continue
            self.log("主站详情不可用，按片名「%s」兜底到源=%s: %s"
                     % (key, self._bz_used or "备用源", best.get("vod_name")))
            res = self._bz_detail(str(best.get("vod_id")))
            # 保持原 vod_id，避免 TVBox 侧 id 漂移
            if res.get("list"):
                res["list"][0]["vod_id"] = vod_id
                return res
        return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        self._warm_up()
        page = int(pg) if pg else 1
        ext = self._norm_extend(extend)
        tid = str(tid).strip()

        has_filter = any(ext.get(k)
                         for k in ("cat", "class", "area", "year", "lang",
                                   "letter", "sort"))

        html, cur_url = "", ""
        if has_filter:
            # ===== 主路径①：像用户一样逐项点击（走的全是用户真实点过的 URL，
            # Cloudflare 缓存命中最高的就是这条链路）=====
            html, cur_url = self._follow_filter(tid, ext, page)

            # ===== 主路径②：按实测规则直接拼 URL（两套等价形态互备）=====
            if not self._extract_videos(html):
                u1 = self._build_filter_url(tid, ext, 1)
                h1 = self._fetch_cached(u1, timeout=15, retry=3)
                if not self._extract_videos(h1):
                    alt = self._build_filter_url_alt(tid, ext, 1)
                    if alt and alt != u1:
                        h1 = self._fetch_cached(alt, timeout=15, retry=3)
                        if self._extract_videos(h1):
                            u1 = alt
                if page > 1 and self._extract_videos(h1):
                    purl = self._page_url(h1, u1, page)
                    if purl and purl != u1:
                        html = self._fetch_cached(purl, timeout=15, retry=3)
                        if self._extract_videos(html):
                            cur_url, u1 = purl, purl
                if not self._extract_videos(html):
                    cur_url = self._build_filter_url(tid, ext, page)
                    html = h1 if (h1 and page == 1) else \
                        self._fetch_cached(cur_url, timeout=15, retry=3)
                    if page > 1 and not self._extract_videos(html):
                        # 筛选页翻页失败时退回「同条件第 1 页」，别给未筛选的错误内容
                        if self._extract_videos(h1):
                            html, cur_url = h1, u1

            if not self._extract_videos(html):
                # 主站动态页全 520（源站数据库故障）-> 交给备用源接管，保证有片可看
                if self._bz_enabled():
                    bz, bpc = self._bz_category(tid, ext, page)
                    if bz:
                        self.log("主站筛选页不可用，接管源=%s tid=%s ext=%s -> %d 条"
                                 % (self._bz_used or "备用源", tid, ext, len(bz)))
                        return {"list": bz, "page": page,
                                "pagecount": bpc or page, "limit": 24,
                                "total": max(bpc, page) * 24}
                if self.fallback_unfiltered:
                    # 可选降级：退回该频道首页列表（未筛选），至少让用户有片可点
                    u0 = "%s/unit/%s.html" % (self.site_url, tid)
                    h0 = self._fetch_cached(u0, timeout=12, retry=1)
                    if self._extract_videos(h0):
                        html, cur_url = h0, u0
                        self.log("筛选页不可用，按 fallback=1 退回频道首页: %s" % u0)
                if not self._extract_videos(html):
                    # 筛选彻底失败：宁可返回空，也绝不拿频道默认页冒充筛选结果
                    # （那正是「筛选出来的影片和网站完全不一致」的元凶）
                    self.log("筛选无结果（源站 520 且无本地快照）: tid=%s ext=%s"
                             % (tid, ext))
                    return {"list": [], "page": page, "pagecount": page,
                            "limit": 24, "total": 0}

        if not self._extract_videos(html) and not has_filter:
            # 无筛选：直接走频道页（/unit/{tid}.html、/unit/{tid}-{page}.html）
            if page > 1:
                cur_url = "%s/unit/%s-%d.html" % (self.site_url, tid, page)
            else:
                cur_url = "%s/unit/%s.html" % (self.site_url, tid)
            h2 = self._fetch_cached(cur_url, timeout=15, retry=2)
            if not h2 and page == 1:
                h2 = self._fetch_cached("%s/unit/%s-1.html" % (self.site_url, tid),
                                 timeout=12, retry=2)
                if h2:
                    cur_url = "%s/unit/%s-1.html" % (self.site_url, tid)
            if not h2:
                cur_url = "%s/pack/id/%s.html" % (self.site_url, tid)
                h2 = self._fetch_cached(cur_url, timeout=15, retry=2)
            if h2:
                html = h2

        videos = self._extract_videos(html)
        pagecount = self._page_count(html)
        self._remember(videos)
        self.log("category tid=%s pg=%s url=%s => %d 条 / %d 页"
                 % (tid, page, cur_url, len(videos), pagecount))

        if pagecount < page:
            pagecount = page
        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": 24,
            "total": min(pagecount, 9999) * 24,
        }

    # ---------------------------------------------------------------- 搜索
    def _search_html(self, key, page=1):
        q = urllib.parse.quote(key)
        # 1) 站点表单是 POST /find3.html
        html = self._fetch(self.site_url + "/find3.html",
                           data={"wd": key}, timeout=20, retry=2)
        if self._extract_videos(html):
            return html
        # 2) GET 形式
        for u in ("%s/find3.html?wd=%s" % (self.site_url, q),
                  "%s/index.php/vod/search/wd/%s.html" % (self.site_url, q),
                  "%s/search/%s-------------.html" % (self.site_url, q)):
            h2 = self._fetch(u, timeout=18, retry=2)
            if self._extract_videos(h2):
                return h2
        # 3) 联想接口
        try:
            h3 = self._fetch("%s/index.php/ajax/suggest?mid=1&wd=%s&limit=30"
                             % (self.site_url, q), timeout=15, retry=1)
            obj = json.loads(h3)
            lst = obj.get("list") or []
            if lst:
                videos = []
                for it in lst:
                    vid = it.get("id") or it.get("vod_id")
                    videos.append({
                        "vod_id": "/pagevid/%s.html" % vid,
                        "vod_name": self._clean(it.get("name") or it.get("vod_name")),
                        "vod_pic": self._fix_url(it.get("pic") or it.get("vod_pic")) or self.default_pic,
                        "vod_remarks": self._clean(it.get("remarks") or ""),
                    })
                self._suggest_cache = videos
                return "__SUGGEST__"
        except Exception:
            pass
        return ""

    def searchContent(self, key, quick, pg="1"):
        self._warm_up()
        page = int(pg) if pg else 1
        self._suggest_cache = None
        html = self._search_html(key, page)
        if html == "__SUGGEST__":
            videos = self._suggest_cache or []
            return {"list": videos, "page": 1, "pagecount": 1,
                    "limit": len(videos) or 24, "total": len(videos)}
        videos = self._extract_videos(html)
        pagecount = self._page_count(html)
        if not videos and self._bz_enabled():
            # 主站搜索接口是动态页（源站故障时同样 520）-> 备用源接管
            bz = self._bz_search(key, page)
            if bz:
                self.log("搜索接管源=%s 关键词=%s -> %d 条"
                         % (self._bz_used or "备用源", key, len(bz)))
                return {"list": bz, "page": page, "pagecount": page,
                        "limit": len(bz) or 24, "total": len(bz)}
        self._remember(videos)
        self.log("search %s => %d 条" % (key, len(videos)))
        return {"list": videos, "page": page, "pagecount": max(1, pagecount),
                "limit": 24, "total": max(1, pagecount) * 24}

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------------------------------------------------------------- 详情
    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0]).strip()
        # 备用源条目（列表/搜索接管时产出 bz|{备用源vod_id}）
        if vod_id.startswith("bz|"):
            return self._bz_detail(vod_id[3:])
        if vod_id.isdigit():
            vod_id = "/pagevid/%s.html" % vod_id
        url = vod_id if vod_id.startswith("http") else self._fix_url(vod_id)
        self.log("detail: %s" % url)

        html = self._fetch_cached(url, timeout=20, retry=2)
        self.log("  HTML 长度: %d" % len(html))
        if not html:
            return self._bz_detail_by_name(vod_id)

        # ---- 信息区 ----
        zone_m = _RE_DETAIL_AREA.search(html)
        zone = zone_m.group(1) if zone_m else html[:20000]

        name = ""
        m = _RE_H3_TITLE.search(zone)
        if m:
            name = self._clean(re.sub(r'<span[^>]*class="[^"]*score[^"]*"[\s\S]*?</span>', "", m.group(1)))
        if not name:
            m = _RE_TAG_TITLE.search(html)
            if m:
                name = self._clean(m.group(1).split("_")[0].split("-")[0].split("《")[-1].replace("》", ""))
        name = re.sub(r"\s*\(\d{4}\)\s*$", "", name).strip() or vod_id

        score = ""
        m = _RE_SCORE.search(zone) or _RE_SCORE.search(html)
        if m:
            score = m.group(1)

        type_name = area = year = ""
        m = _RE_TYPE.search(zone)
        if m:
            type_name = self._clean(m.group(1))
        m = _RE_AREA.search(zone)
        if m:
            area = self._clean(m.group(1))
        m = _RE_YEAR.search(zone)
        if m:
            year = self._clean(m.group(1))

        actor = ""
        m = _RE_ACTOR.search(zone)
        if m:
            actor = re.sub(r"\s*,\s*", ", ", self._clean(m.group(1)))

        director = ""
        m = _RE_DIRECTOR.search(zone)
        if m:
            director = re.sub(r"\s*,\s*", ", ", self._clean(m.group(1)))

        # 副标题（缩略图角标） / 封面
        thumb_zone = ""
        m = _RE_PIC_TEXT_DETAIL.search(html)
        if m:
            thumb_zone = m.group(1)

        remarks = ""
        if thumb_zone:
            mp = _RE_PIC_TEXT.search(thumb_zone)
            if mp:
                remarks = self._clean(mp.group(1))
        if not remarks:
            m = re.search(r'更新时间：\s*([\d-]+)', html)
            if m:
                remarks = "更新于" + m.group(1)

        pic = ""
        for cand in _RE_PIC_ATTR.findall(thumb_zone or html):
            if cand and "load.gif" not in cand and not cand.startswith("data:"):
                pic = cand
                break
        pic = self._fix_url(pic) or self.default_pic

        # ---- 简介 ----
        content = ""
        m = _RE_DESC_BLOCK.search(html)
        if m:
            content = self._clean(m.group(1))
        if not content:
            m = _RE_DESC_SHORT.search(zone)
            if m:
                content = self._clean(re.sub(r'<a[^>]*>[\s\S]*?</a>', "", m.group(1)))
                content = content.replace("简介：", "", 1)
        if not content:
            m = _RE_META_DESC.search(html)
            if m:
                content = self._clean(m.group(1))
        content = (INTRO_PREFIX + "\n" + content) if content else INTRO_PREFIX

        # ---- 播放线路（严格按「切换来源」下拉顺序）----
        play_from, play_url = self._parse_playlist(html)
        self.log("  线路: %s" % play_from)
        if not play_from:
            # 页面拿到了但线路区缺失（缓存残缺页）-> 按片名兜底
            return self._bz_detail_by_name(vod_id, want=name)

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_score": score,
            "vod_year": year,
            "vod_area": area,
            "vod_remarks": remarks or ("%d条线路" % len(play_from)),
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
            "type_name": type_name,
        }]}

    def _parse_playlist(self, html):
        """返回 (play_from, play_url)，顺序 = 详情页 tab 顺序"""
        zone_m = _RE_PLAYLIST_ZONE.search(html)
        zone = zone_m.group(1) if zone_m else html

        # tab 顺序
        tabs = []
        for sid, raw in _RE_TAB_ITEM.findall(zone):
            nm = self._clean(raw)
            if not nm:
                continue
            tabs.append((sid, nm))

        # 每个 sid 的剧集
        eps = {}
        for sid, body in _RE_EP_BLOCK.findall(zone):
            items = []
            for href, raw in _RE_EP_A.findall(body):
                href = href.replace("&amp;", "&").strip()
                if not href or href.startswith("javascript") or "#" in href:
                    continue
                items.append((self._safe_name(raw), self._fix_url(href)))
            if items:
                eps[sid] = items

        if not eps:
            return [], []

        order = []
        used = set()
        for sid, nm in tabs:
            if sid in eps and sid not in used:
                order.append((nm, sid))
                used.add(sid)
        for sid in eps.keys():
            if sid not in used:
                order.append(("线路%s" % sid, sid))
                used.add(sid)

        play_from, play_url = [], []
        names = set()
        for nm, sid in order:
            items = eps[sid]
            label = nm or ("线路%s" % sid)
            base = label
            i = 2
            while label in names:
                label = "%s-%d" % (base, i)
                i += 1
            names.add(label)
            play_from.append(label)
            play_url.append("#".join("%s$%s" % (n, h) for n, h in items))
        return play_from, play_url

    # ---------------------------------------------------------------- 播放
    def _play_disk_path(self, url):
        d = self._cache_root()
        if not d:
            return ""
        try:
            sub = os.path.join(d, "play")
            os.makedirs(sub, exist_ok=True)
            return os.path.join(sub, hashlib.md5(url.encode("utf-8")).hexdigest() + ".json")
        except Exception:
            return ""

    def _play_get(self, url, max_age=7 * 86400):
        now = time.time()
        hit = self._play_cache.get(url)
        if hit and now - hit[0] < max_age:
            return hit[1]
        p = self._play_disk_path(url)
        if p:
            try:
                if os.path.exists(p):
                    with open(p, "r", encoding="utf-8", errors="ignore") as f:
                        obj = json.load(f)
                    res, ts = obj.get("res"), float(obj.get("ts") or 0)
                    if res and now - ts < max_age:
                        self._play_cache[url] = (ts, res)
                        return res
            except Exception:
                pass
        return None

    def _play_put(self, url, res):
        now = time.time()
        self._play_cache[url] = (now, res)
        p = self._play_disk_path(url)
        if p:
            try:
                with open(p, "w", encoding="utf-8", errors="ignore") as f:
                    json.dump({"ts": now, "res": res}, f, ensure_ascii=False)
            except Exception:
                pass

    def _bz_resolve(self, share_url):
        """备用源播放地址若为 /share/xxxx 分享页，则解析出真实 m3u8 直链。
        页面里形如：var main = "/20251222/31325_xxx/index.m3u8?sign=..."
        """
        ck = "bzres:" + share_url
        hit = self._play_get(ck)
        if hit and hit.get("url"):
            return hit["url"]
        try:
            html = self._fetch(share_url, timeout=15, retry=1,
                               headers={"Referer": share_url, "User-Agent": UA})
        except Exception:
            html = ""
        if not html:
            return ""
        m = re.search(r'var\s+main\s*=\s*["\']([^"\']+)["\']', html)
        if not m:
            m = re.search(r'["\']([^"\']+?\.m3u8[^"\']*)["\']', html)
        if not m:
            return ""
        path = m.group(1).strip()
        if not path:
            return ""
        if path.startswith("http"):
            real = path
        elif path.startswith("//"):
            real = "https:" + path
        else:
            u = urllib.parse.urlparse(share_url)
            root = "%s://%s" % (u.scheme or "https", u.netloc)
            real = root + (path if path.startswith("/") else "/" + path)
        if real:
            self._play_put(ck, {"url": real, "ts": int(time.time())})
        return real

    def playerContent(self, flag, id, vipFlags):
        # 备用源条目：播放地址在列表阶段已内嵌（bzplay|base64直链|线路名），无需再请求
        if str(id).startswith("bzplay|"):
            parts = str(id).split("|")
            direct = ""
            if len(parts) >= 2 and parts[1]:
                try:
                    pad = "=" * (-len(parts[1]) % 4)
                    direct = base64.urlsafe_b64decode(parts[1] + pad).decode("utf-8")
                except Exception:
                    direct = ""
            if direct and not re.search(r"\.(m3u8|mp4)(\?|#|$)", direct, re.I):
                # /share/xxx 分享页 -> 解析真实 m3u8，做到 parse=0 秒开
                real = self._bz_resolve(direct)
                if real:
                    direct = real
            if direct:
                return self._make_play_res(direct)
            return {"parse": 0, "playUrl": "", "url": "",
                    "header": {"User-Agent": UA}}

        play_page = id if id.startswith("http") else self._fix_url(id)
        self.log("player: %s" % play_page)

        cached = self._play_get(play_page)
        if cached:
            return cached

        # 播放页 Referer 实测：各线路 CDN 对 Referer 不敏感，带站点首页即可
        html = self._fetch(play_page, timeout=20, retry=2,
                           headers={"Referer": self.site_url + "/"})
        direct = self._parse_play_html(html, play_page)
        self.log("  direct: %s" % (direct[:180] if direct else "EMPTY"))

        if direct:
            res = self._make_play_res(direct)
            self._play_put(play_page, res)
            return res

        # ===== 关键兜底：源站间歇 520，当前线路拿不到时自动接力其它线路的同集 =====
        # 播放页路由 /slotplay/{vid}/{sid}/{nid}.html，各线路同集数的 nid 一致
        m = re.search(r"/slotplay/(\d+)/(\d+)/(\d+)\.html", play_page)
        if m:
            vid, cur_sid, nid = m.group(1), int(m.group(2)), m.group(3)
            others = [s for s in range(1, 9) if s != cur_sid]
            for sid2 in others:
                alt = "%s/slotplay/%s/%d/%s.html" % (self.site_url, vid, sid2, nid)
                h2 = self._fetch(alt, timeout=12, retry=1,
                                 headers={"Referer": self.site_url + "/"})
                d2 = self._parse_play_html(h2, alt)
                if d2:
                    self.log("  线路%s 失败, 接力线路%s: %s"
                             % (cur_sid, sid2, d2[:120]))
                    res = self._make_play_res(d2)
                    self._play_put(play_page, res)
                    return res

        # 最终兜底：交给 TVBox 嗅探
        res = {"parse": 1, "playUrl": "", "url": play_page,
               "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}
        return res

    def _make_play_res(self, direct):
        low = direct.lower()
        if ".m3u8" in low or ".mp4" in low:
            return {
                "parse": 0, "playUrl": "", "url": direct,
                "header": {"User-Agent": UA, "Referer": self.site_url + "/"},
            }
        # 直链但没有视频扩展名 → 仍交嗅探
        return {"parse": 1, "playUrl": "", "url": direct,
                "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}

    def _parse_play_html(self, html, page_url=""):
        if not html:
            return ""

        # 1) player_aaaa = {...}
        for m in _RE_PLAYER_OBJ.finditer(html):
            start = m.end() - 1
            try:
                obj, _end = json.JSONDecoder().raw_decode(html[start:])
            except Exception:
                continue
            if not isinstance(obj, dict):
                continue
            url = self._pick_link(obj)
            if url:
                return url

        # 2) 宽松 "url" / "link"
        for key in ("url", "link"):
            m = re.search(r'"%s"\s*:\s*"([^"]{8,})"' % key, html)
            if m:
                u = self._pick_link({"url": m.group(1)})
                if u:
                    return u

        # 3) iframe 嵌套（再进一层）
        m = _RE_IFRAME.search(html)
        if m:
            src = self._fix_url(m.group(1))
            if src and src != page_url and "zzhczj" not in src:
                inner = self._fetch(src, headers={"Referer": page_url or self.site_url + "/"})
                u = self._parse_play_html(inner, src)
                if u:
                    return u

        # 4) 页面里裸的 m3u8 / mp4
        for reg in (_RE_M3U8, _RE_MP4):
            m = reg.search(html)
            if m:
                u = m.group(0).replace("\\/", "/")
                if u.startswith("//"):
                    u = "https:" + u
                return u

        # 5) 播放器配置里的其它 http 地址（无扩展名 m3u8 也能捞到）
        m = _RE_ANY_URL.search(html.replace("\\/", "/"))
        if m:
            u = m.group(1).strip()
            if u.startswith("//"):
                u = "https:" + u
            if not re.search(r'\.(?:jpg|jpeg|png|webp|gif|css|js|html?)(?:\?|$)', u, re.I):
                return u
        return ""

    def _pick_link(self, obj):
        enc = str(obj.get("encrypt", "0"))
        for key in ("url", "link"):
            raw = obj.get(key) or ""
            if not isinstance(raw, str):
                continue
            raw = raw.strip().replace("\\/", "/")
            if not raw:
                continue
            if raw.startswith("//"):
                raw = "https:" + raw
            # 注意：base64 / urlencode 后的串也可能以 http 开头，必须校验 ://
            if re.match(r'^https?://', raw, re.I):
                return raw

            dec = ""
            if enc == "1":
                dec = self._b64(raw)
            elif enc == "2":
                dec = urllib.parse.unquote(raw).replace("\\/", "/")
                if dec.startswith("//"):
                    dec = "https:" + dec
                if not re.match(r'^https?://', dec, re.I):
                    dec = ""
            else:
                dec = self._b64(raw)
                if not dec:
                    dec = urllib.parse.unquote(raw).replace("\\/", "/")
                    if dec.startswith("//"):
                        dec = "https:" + dec
                    if not re.match(r'^https?://', dec, re.I):
                        dec = ""
            if dec:
                return dec
        return ""

    def _b64(self, s):
        try:
            t = s.strip().replace("-", "+").replace("_", "/")
            pad = len(t) % 4
            if pad:
                t += "=" * (4 - pad)
            dec = base64.b64decode(t).decode("utf-8", "ignore").strip()
            dec = dec.replace("\\/", "/")
            if dec.lower().startswith("http"):
                return dec
        except Exception:
            pass
        return ""

    def localProxy(self, param):
        try:
            url = ""
            if isinstance(param, dict):
                url = param.get("url", "")
            else:
                for pair in str(param).split("&"):
                    if "=" in pair:
                        k, v = pair.split("=", 1)
                        if k == "url":
                            url = v
            if not url:
                return [200, "image/jpeg", b"", ""]
            url = urllib.parse.unquote(url) if "%" in url else url
            url = self._fix_url(url)
            rsp = self.fetch(url, headers={
                "User-Agent": UA, "Referer": self.site_url + "/"}, timeout=15)
            content = getattr(rsp, "content", b"") or b""
            ctype = ""
            if hasattr(rsp, "headers"):
                ctype = rsp.headers.get("Content-Type", "") or ""
            if not ctype.startswith("image/"):
                ctype = "image/jpeg"
            return [200, ctype, content, ""]
        except Exception:
            return [200, "image/jpeg", b"", ""]

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url or url.startswith("http")

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()
