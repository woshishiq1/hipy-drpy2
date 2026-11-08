# -*- coding: utf-8 -*-
"""
森林影院 m.zbtiehong.com | TVBox Python 爬虫 

关键:
  - 站点为苹果CMS(maccms) + hl048/stui 模板，与 ewave 主题的解析规则完全不同
  - 详情页 = /yingshi/z{id}.html，播放页 = /vodview/z{id}/{sid}/{nid}.html
  - 播放数据内联 var player_aaaa={...}，encrypt=0，url 即直链 m3u8，无需二次解析
  - 线路顺序【完全按详情页面板 DOM 顺序】输出，不做任何排序（与网站显示一致）；
    注意面板文字「线路1/线路2/…」与链接里的 sid 并不对应，切勿按名字或 sid 排序
  - 剧集名需剔除 $ 和 #（TVBox 协议分隔符），否则播放列表会错位
  - 源站被 Cloudflare 前置，520 抖动极频繁，需带退避重试 + Session 保活
  - 兼容无副标题、无封面（/static/images/load.png 占位）、无演员的卡片
"""

import sys
import re
import json
import time
import html as htmllib
from urllib.parse import quote, urljoin

sys.path.append('..')

# ---- TVBox 基类：优先用宿主提供的 Spider，独立运行时降级为内置实现 ----
try:
    from base.spider import Spider
except Exception:
    class Spider(object):
        pass

# ---- requests：TVBox Python 环境一般自带；缺失时走降级 ----
try:
    import requests
    _HAS_REQUESTS = True
except Exception:
    requests = None
    _HAS_REQUESTS = False


# ======================================================================
#  一、全局配置
# ======================================================================

# 简介前缀（用户指定，不可改动）
INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

HOST = "https://m.zbtiehong.com"

# 站点图片占位符：务必过滤，否则 TVBox 会显示一堆破图
PLACEHOLDER_IMG = "/static/images/load.png"
PLACEHOLDER_GIF = "load.gif"

# 缓存 TTL（秒）—— 电视盒子上同一部片反复点开很常见，缓存能显著降延迟
PLAY_CACHE_TTL = 600      # 播放地址缓存 10 分钟
DETAIL_CACHE_TTL = 600    # 详情缓存 10 分钟

# 网络重试次数 —— 源站 520 是常态，3 次退避基本够用；极端情况自动升到 25
MAX_RETRY = 3
MAX_RETRY_HARD = 25       # 连续失败后的激进重试（仅播放页使用）

# 线路播放顺序 —— 完全按详情页面板的 DOM 顺序输出，不做任何排序！
#
# 【重要】面板文字「线路1/线路2/…」与链接里的 sid 并不对应（线路1 可能是 sid=6），
#         且不同影片的面板排布也不一样，例如：
#
#           《伟大的长征》面板顺序: 线路1(6) 线路2(2) 线路3(3) 线路4(1) 线路6(4) 线路5(5)
#           《哥斯拉-0.0》面板顺序:  线路1(3) 线路2(1) 线路4(2) 线路5(4) 线路6(5)
#
#         站点网页怎么显示，我们就原样怎么输出 —— 不按名字排、不按 sid 排。
#         （详情页「立即播放」指向 sid=1 只是站点默认播放链接，与显示顺序无关）

# 双 UA：移动端 UA 命中率最高；iPad UA 在播放页被墙时作为备选
MOBILE_UA = (
    "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
)
IPAD_UA = (
    "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)

HEADERS = {
    "User-Agent": MOBILE_UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


# ======================================================================
#  二、分类表（与站点顶部导航 / 侧栏子分类完全一致）
# ======================================================================

# (一级分类名, 一级ID, [(二级分类名, 二级ID), ...])
CATEGORY_TREE = [
    ("电影", "1", [
        ("动作片", "6"), ("喜剧片", "7"), ("爱情片", "8"), ("科幻片", "9"),
        ("剧情片", "10"), ("战争片", "11"), ("动画片", "41"), ("记录片", "12"),
        ("恐怖片", "39"),
    ]),
    ("电视剧", "2", [
        ("国产剧", "13"), ("香港剧", "14"), ("韩国剧", "15"), ("欧美剧", "16"),
        ("台湾剧", "22"), ("日本剧", "21"), ("泰国剧", "20"), ("海外剧", "23"),
    ]),
    ("综艺片", "3", [
        ("大陆综艺", "25"), ("日韩综艺", "26"), ("港台综艺", "27"), ("欧美综艺", "28"),
    ]),
    ("动漫", "4", [
        ("国产动漫", "29"), ("日本动漫", "30"), ("港台动漫", "42"), ("欧美动漫", "31"),
        ("海外动漫", "43"),
    ]),
    ("短剧", "24", [
        ("短剧大全", "40"), ("AI漫剧", "44"),
    ]),
]

# 首页板块标题 -> 该板块归属的展示名（用于首页卡片补 type_name）
HOME_BOARDS = [
    ("本周热门电影", "电影"),
    ("本周热门电视剧", "电视剧"),
    ("本周热门综艺片", "综艺片"),
    ("本周热门动漫", "动漫"),
    ("本周热门短剧", "短剧"),
]


# ======================================================================
#  三、筛选表（逐项抄自 /sort/{id}.html 顶部筛选面板）
# ======================================================================

LETTERS = [chr(c) for c in range(65, 91)] + ["0-9"]

FILTER_DB = {
    # 电影
    "1": {
        "class": ["喜剧", "爱情", "恐怖", "动作", "科幻", "剧情", "战争", "警匪",
                  "犯罪", "动画", "奇幻", "武侠", "冒险", "枪战", "悬疑", "惊悚",
                  "经典", "青春", "文艺", "微电影", "古装", "历史", "运动", "农村",
                  "儿童", "网络电影"],
        "area": ["大陆", "香港", "台湾", "美国", "法国", "英国", "日本", "韩国",
                 "德国", "泰国", "印度", "意大利", "西班牙", "加拿大", "其他"],
        "year": ["2026", "2025", "2024", "2023", "2022", "2021", "2020", "2019",
                 "2018", "2017", "2016", "2015", "2014", "2013", "2012", "2011", "2010"],
    },
    # 电视剧：比电影多「语言」「字母」两行
    "2": {
        "class": ["古装", "战争", "青春偶像", "喜剧", "家庭", "犯罪", "动作", "奇幻",
                  "剧情", "历史", "经典", "乡村", "情景", "商战", "网剧", "其他"],
        "area": ["内地", "韩国", "香港", "台湾", "日本", "美国", "泰国", "英国",
                 "新加坡", "其他"],
        "year": ["2026", "2025", "2024", "2023", "2022", "2021", "2020", "2019",
                 "2018", "2017", "2016", "2015", "2014", "2013", "2012", "2011", "2010"],
        "lang": ["国语", "英语", "粤语", "闽南语", "韩语", "日语", "其它"],
        "letter": LETTERS,
    },
    # 综艺：地区只有 4 项，年份下探到 2004
    "3": {
        "class": ["选秀", "情感", "访谈", "播报", "旅游", "音乐", "美食", "纪实",
                  "曲艺", "生活", "游戏互动", "财经", "求职"],
        "area": ["内地", "港台", "日韩", "欧美"],
        "year": ["2026", "2025", "2024", "2023", "2022", "2021", "2020", "2019",
                 "2018", "2017", "2016", "2015", "2014", "2013", "2012", "2011",
                 "2010", "2009", "2008", "2007", "2006", "2005", "2004"],
    },
    # 动漫
    "4": {
        "class": ["冒险", "热血", "搞笑", "运动", "竞技", "武侠", "玄幻", "魔法",
                  "科幻", "悬疑", "推理", "恋爱", "治愈", "校园", "日常", "原创",
                  "亲子", "格斗", "机战", "其他"],
        "area": ["国产", "日本", "欧美", "港台", "韩国", "其他"],
        "year": ["2026", "2025", "2024", "2023", "2022", "2021", "2020", "2019",
                 "2018", "2017", "2016", "2015", "2014", "2013", "2012", "2011", "2010"],
    },
    # 短剧：实测面板只有「按类型」一组（短剧大全/AI漫剧），
    #       剧情/地区/年份三行在页面上是空壳（<a> 内无文字），故 cfg 留空，
    #       但「类型」组由 _build_filter 依据 subs 照常生成
    "24": {},
}


# ======================================================================
#  四、工具函数
# ======================================================================

def _clean(text):
    """去标签 / 解实体 / 收空白，统一输出纯文本"""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    text = htmllib.unescape(text)
    text = text.replace("\u200b", "").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def _join_host(url):
    """相对路径补全为绝对地址"""
    if not url:
        return ""
    url = url.strip()
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if url.startswith("//"):
        return "https:" + url
    return urljoin(HOST, url)


def _safe_img(url):
    """过滤站点占位图，避免 TVBox 显示破图"""
    url = _join_host(url).strip().strip("'\"")
    if not url:
        return ""
    if PLACEHOLDER_IMG in url or PLACEHOLDER_GIF in url:
        return ""
    return url


def _norm_ep_name(name):
    """剧集名清洗：$ 与 # 是 TVBox 播放列表的分隔符，必须剔除"""
    name = (name or "").replace("$", "").replace("#", "")
    name = name.replace("￥", "").replace("＃", "")
    return _clean(name)


# ======================================================================
#  五、主类
# ======================================================================

class Spider(Spider):

    # ----------------------------------------------------------------
    #  5.1 生命周期
    # ----------------------------------------------------------------

    def getName(self):
        return "森林影院"

    def init(self, extend=""):
        self.extend = extend or ""
        self._play_cache = {}
        self._detail_cache = {}
        self._session = None
        # 站点证书链偶尔不完整，requests 关闭校验避免 TVBox 直接抛异常
        try:
            import urllib3
            urllib3.disable_warnings()
        except Exception:
            pass

    def destroy(self):
        self._play_cache = {}
        self._detail_cache = {}
        self._session = None

    def close(self):
        self.destroy()

    # ----------------------------------------------------------------
    #  5.2 网络层
    #      源站前面挂了 Cloudflare，同一个 URL 可能连续 520 十几次，
    #      所以这里做了「Session 保活 + 指数退避 + 多 UA 轮换」三重保险。
    # ----------------------------------------------------------------

    def _headers(self, referer=None):
        h = dict(HEADERS)
        # 站内跳转必须有 Referer，否则部分列表页会返回空壳
        h["Referer"] = referer or (HOST + "/")
        return h

    def _requests_get(self, url, referer=None, timeout=15, ua=None):
        if not _HAS_REQUESTS:
            return None
        try:
            # 复用 Session：保留 Cloudflare 下发的 __cf_bm 等 cookie，命中率明显更高
            if self._session is None:
                self._session = requests.Session()
                self._session.headers.update(HEADERS)
            headers = self._headers(referer)
            if ua:
                headers["User-Agent"] = ua
            resp = self._session.get(url, headers=headers, timeout=timeout, verify=False)
            if resp.status_code == 200:
                resp.encoding = "utf-8"
                text = resp.text
                # 520/浏览器错误页也常常是 200 + 一小段 HTML，用长度做二次判定
                if len(text) > 2000:
                    return text
        except Exception as e:
            self.log("requests error %s %s" % (url, e))
        return None

    def fetch(self, url, headers=None, **kw):
        url = _join_host(url)
        referer = (headers or {}).get("Referer", HOST + "/")

        # 第一轮：常规退避重试
        delay = 0.6
        for i in range(MAX_RETRY):
            text = self._requests_get(url, referer)
            if text:
                return text
            if i < MAX_RETRY - 1:
                time.sleep(delay)
                delay = min(delay * 1.8, 4.0)

        # 第二轮：换 iPad UA 再冲几次（实测播放页用 iPad UA 更容易过）
        for i in range(3):
            time.sleep(1.2)
            text = self._requests_get(url, referer, ua=IPAD_UA)
            if text:
                return text

        # 第三轮：回落到基类内置 fetch（部分播放器环境自带请求栈）
        base_fetch = getattr(super(Spider, self), "fetch", None)
        if callable(base_fetch):
            try:
                text = base_fetch(url, headers=headers or self._headers(referer), **kw)
                if text and len(str(text)) > 200:
                    return text
            except Exception as e:
                self.log("base fetch error %s %s" % (url, e))

        self.log("fetch failed: %s" % url)
        return ""

    def fetch_hard(self, url, referer=None):
        """激进重试：仅用于播放页解析。实测某些线路要 20+ 次才 200"""
        url = _join_host(url)
        for i in range(MAX_RETRY_HARD):
            text = self._requests_get(url, referer or (HOST + "/"))
            if text:
                return text
            # 前后交替 UA，避免被单一指纹标记
            text = self._requests_get(url, referer or (HOST + "/"), ua=IPAD_UA)
            if text:
                return text
            time.sleep(0.8 + (i % 4) * 0.5)
        return ""

    def log(self, msg):
        try:
            print("[森林影院] %s" % msg)
        except Exception:
            pass

    # ----------------------------------------------------------------
    #  5.3 首页
    # ----------------------------------------------------------------

    def homeVideoContent(self):
        videos = []
        try:
            html_text = self.fetch(HOST + "/")
            if html_text:
                videos = self._parse_home(html_text)
        except Exception as e:
            self.log("homeVideoContent error %s" % e)

        # 首页解析失败时退化为「电影第一页」，保证 TVBox 首屏不至于空白
        if not videos:
            try:
                videos = self.categoryContent("1", "1", False, {})["list"]
            except Exception:
                videos = []

        return {"list": videos}

    def homeContent(self, filter):
        result = {"class": [], "filters": {}}

        # 分类：只放 5 个一级分类，与站点顶部导航一致；
        # 子分类（动作片/喜剧片…）通过筛选面板里的「类型」进入，不平铺
        for name, tid, subs in CATEGORY_TREE:
            result["class"].append({"type_id": tid, "type_name": name})

        # 筛选：一级分类挂自己的面板；面板第一组「剧情」里带上子分类，
        # 选中即等价于切到该子分类（与站点筛选面板行为一致）
        if filter:
            for name, tid, subs in CATEGORY_TREE:
                result["filters"][tid] = self._build_filter(tid, subs)

        videos = []
        try:
            html_text = self.fetch(HOST + "/")
            if html_text:
                videos = self._parse_home(html_text)
        except Exception as e:
            self.log("homeContent error %s" % e)

        if not videos:
            try:
                videos = self.categoryContent("1", "1", False, {})["list"]
            except Exception:
                videos = []

        result["list"] = videos
        return result

    def _build_filter(self, top_tid, subs=None):
        """
        生成筛选组。
        subs 为该分类的子分类列表 —— 作为「类型」组放在最前面，
        选中后 categoryContent 会通过 flt["sub"] 切换到对应子分类，
        与站点筛选面板的「按类型」行为完全一致。
        短剧等无 剧情/地区/年份 的分类，「类型」组仍要生成（站点面板如此）。
        """
        cfg = FILTER_DB.get(top_tid, {})
        groups = []

        # 「类型」组 = 子分类（动作片/喜剧片… 或 短剧大全/AI漫剧）
        if subs:
            groups.append({
                "key": "sub",
                "name": "类型",
                "value": [{"n": "全部", "v": ""}] +
                         [{"n": n, "v": "sub:%s" % sid} for n, sid in subs],
            })

        # 该分类没有 剧情/地区/年份 面板时（如短剧），到此为止
        if not cfg:
            return groups

        def _grp(key, label, values):
            return {
                "key": key,
                "name": label,
                # 第一项固定「全部」，值传空串表示不筛选
                "value": [{"n": "全部", "v": ""}] + [{"n": x, "v": x} for x in values],
            }

        groups.append(_grp("class", "剧情", cfg.get("class", [])))
        groups.append(_grp("area", "地区", cfg.get("area", [])))
        groups.append(_grp("year", "年份", cfg.get("year", [])))
        if cfg.get("lang"):
            groups.append(_grp("lang", "语言", cfg["lang"]))
        if cfg.get("letter"):
            groups.append(_grp("letter", "字母", cfg["letter"]))

        return groups

    def _parse_home(self, html_text):
        """
        首页是「5 个横向板块」，每个板块一个 stui-pannel：
          本周热门电影 / 本周热门电视剧 / 本周热门综艺片 / 本周热门动漫 / 本周热门短剧
        卡片为媒体型（左图右文），封面写在 style="background-image: url(...)" 里。
        """
        videos = []
        seen = set()

        # 按面板切块，避免跨板块串数据
        blocks = re.split(r'(?=<div class="stui-pannel stui-pannel-bg clearfix">)', html_text)

        for block in blocks:
            m_title = re.search(r'<h3 class="title">\s*(?:<img[^>]*/>)?\s*([^<]{1,20}?)\s*</h3>', block)
            if not m_title:
                continue
            title = _clean(m_title.group(1))

            type_name = ""
            for board_key, board_name in HOME_BOARDS:
                if board_key in title:
                    type_name = board_name
                    break
            if not type_name:
                continue

            # 媒体型卡片：封面藏在 background-image
            for m in re.finditer(
                r'<a class="stui-vodlist__thumb[^"]*"\s+href="(/yingshi/z\d+\.html)"'
                r'[^>]*title="([^"]*)"[^>]*style="[^"]*url\(([^)]*)\)',
                block
            ):
                url, name, pic = m.group(1), m.group(2), m.group(3)
                vod_id = self._id_from_url(url)
                if not vod_id or vod_id in seen:
                    continue
                seen.add(vod_id)
                videos.append({
                    "vod_id": vod_id,
                    "vod_name": _clean(name),
                    "vod_pic": _safe_img(pic),
                    "vod_remarks": "",
                    "vod_play_from": "森林影院",
                })

        if not videos:
            # 兜底：首页轮播 / 其它变体卡片的 data-original 写法
            for m in re.finditer(
                r'<a class="[^"]*stui-vodlist__thumb[^"]*"\s+href="(/yingshi/z\d+\.html)"'
                r'[^>]*?title="([^"]*)"[^>]*?data-original="([^"]*)"',
                html_text
            ):
                url, name, pic = m.group(1), m.group(2), m.group(3)
                vod_id = self._id_from_url(url)
                if not vod_id or vod_id in seen:
                    continue
                seen.add(vod_id)
                videos.append({
                    "vod_id": vod_id,
                    "vod_name": _clean(name),
                    "vod_pic": _safe_img(pic),
                    "vod_remarks": "",
                    "vod_play_from": "森林影院",
                })

        return videos

    # ----------------------------------------------------------------
    #  5.4 分类页
    # ----------------------------------------------------------------

    def categoryContent(self, tid, pg, filter, extend):
        tid = str(tid or "1")
        page = int(pg) if str(pg).isdigit() else 1
        extend = extend or {}

        # 「类型」筛选值形如 "sub:13"，表示切到子分类；与其它筛选可叠加
        sub = str(extend.get("sub", "") or "")
        if sub.startswith("sub:"):
            extend["sub"] = sub[4:]
        elif "sub" in extend:
            extend.pop("sub")

        url = self._build_category_url(tid, page, extend)

        result = {
            "list": [],
            "page": page,
            "pagecount": 9999,
            "limit": 30,
            "total": 999999,
        }

        html_text = self.fetch(url)
        if not html_text:
            # 分类页偶尔也会被挡，兜底激进重试
            self.log("category retry hard: %s" % url)
            html_text = self.fetch_hard(url, referer=HOST + "/")
        if not html_text:
            return result

        result["list"] = self._parse_vod_list(html_text)

        total_page = self._parse_pager(html_text)
        if total_page:
            result["pagecount"] = total_page

        # 站点每页固定 30 条
        result["total"] = result["pagecount"] * 30
        return result

    def _build_category_url(self, tid, page, flt):
        """
        两套 URL 语法（与站点完全一致）：

        ① 无筛选：
             /sort/{id}.html
             /sort/{id}-{page}.html
        ② 有筛选（路径式）：
             /choice/[class/{剧情}/][area/{地区}/]id/{id}/[year/{年}/][lang/{语言}/][letter/{字母}/][page/{n}].html

           注意 page 段必须放在最后，且从第 2 页才开始出现。
        """
        cate_id = str(flt.get("sub") or tid)

        cls = str(flt.get("class", "") or "")
        area = str(flt.get("area", "") or "")
        year = str(flt.get("year", "") or "")
        lang = str(flt.get("lang", "") or "")
        letter = str(flt.get("letter", "") or "")

        has_filter = any([cls, area, year, lang, letter])

        if not has_filter:
            if page <= 1:
                return "%s/sort/%s.html" % (HOST, cate_id)
            return "%s/sort/%s-%d.html" % (HOST, cate_id, page)

        segs = []
        if cls:
            segs.append("class/" + quote(cls, safe=""))
        if area:
            segs.append("area/" + quote(area, safe=""))
        segs.append("id/" + cate_id)
        if year:
            segs.append("year/" + quote(year, safe=""))
        if lang:
            segs.append("lang/" + quote(lang, safe=""))
        if letter:
            segs.append("letter/" + quote(letter, safe=""))
        if page > 1:
            segs.append("page/%d" % page)

        return "%s/choice/%s.html" % (HOST, "/".join(segs))

    # ----------------------------------------------------------------
    #  5.5 搜索
    #      第 1 页：/scan/wd/{kw}.html
    #      第 N 页：/scan/page/{n}/wd/{kw}.html
    #      搜索结果用的是媒体型卡片（左图右文），和分类页的网格卡片不同，
    #      所以必须单独写一个解析器。
    # ----------------------------------------------------------------

    def searchContent(self, key, quick, pg="1"):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick, pg="1"):
        page = int(pg) if str(pg).isdigit() else 1
        kw = quote(str(key or "").strip(), safe="")

        if page <= 1:
            url = "%s/scan/wd/%s.html" % (HOST, kw)
        else:
            url = "%s/scan/page/%d/wd/%s.html" % (HOST, page, kw)

        result = {"list": [], "page": page, "pagecount": 1, "limit": 20, "total": 0}

        html_text = self.fetch(url)
        if not html_text:
            # 搜索页同样受 520 影响，兜底激进重试
            self.log("search retry hard: %s" % url)
            html_text = self.fetch_hard(url, referer=HOST + "/")
        if not html_text:
            return result

        result["list"] = self._parse_search_list(html_text)

        total_page = self._parse_pager(html_text)
        if total_page:
            result["pagecount"] = total_page
        result["total"] = result["pagecount"] * 20
        return result

    def _parse_search_list(self, html_text):
        """
        搜索结果结构：
          <a class="v-thumb stui-vodlist__thumb lazyload" href="/yingshi/zxxx.html"
             title="片名" data-original="封面">
            <span class="pic-text text-right">副标题</span>
          </a>
        """
        videos = []
        seen = set()

        for m in re.finditer(
            r'<a class="v-thumb stui-vodlist__thumb[^"]*"\s+href="(/yingshi/z\d+\.html)"'
            r'[^>]*?title="([^"]*)"[^>]*?data-original="([^"]*)"(.*?)</li>',
            html_text, re.S
        ):
            url, name, pic, tail = m.group(1), m.group(2), m.group(3), m.group(4)
            vod_id = self._id_from_url(url)
            if not vod_id or vod_id in seen:
                continue
            seen.add(vod_id)

            m_rem = re.search(r'<span class="pic-text text-right">(.*?)</span>', tail, re.S)

            videos.append({
                "vod_id": vod_id,
                "vod_name": _clean(name),
                "vod_pic": _safe_img(pic),
                "vod_remarks": _clean(m_rem.group(1)) if m_rem else "",
                "vod_play_from": "森林影院",
            })

        return videos

    # ----------------------------------------------------------------
    #  5.6 列表解析（分类页网格卡片）
    # ----------------------------------------------------------------

    def _id_from_url(self, url):
        """从 /yingshi/z{id}.html 抽出纯数字 ID"""
        m = re.search(r'/z(\d+)\.html', url or "")
        return m.group(1) if m else ""

    def _parse_vod_list(self, html_text):
        """
        分类页卡片结构（stui-vodlist__box）：

          <a class="stui-vodlist__thumb lazyload" href="/yingshi/zxxx.html"
             title="片名" data-original="封面">
            <span class="play hidden-xs"></span>
            <span class="pic-text text-right">副标题</span>   <-- vod_remarks
          </a>
          <div class="stui-vodlist__detail">
            <h4 class="title text-overflow"><a ...>片名</a></h4>
            <p class="text text-overflow text-muted hidden-xs">演员</p>
          </div>
        """
        videos = []
        seen = set()

        pattern = (
            r'<a class="stui-vodlist__thumb[^"]*"\s+href="(/yingshi/z\d+\.html)"'
            r'\s+title="([^"]*)"\s+data-original="([^"]*)"[^>]*>(.*?)</a>\s*'
            r'<div class="stui-vodlist__detail">\s*'
            r'<h4 class="title[^"]*"><a[^>]*>(.*?)</a></h4>\s*'
            r'<p class="text[^"]*">(.*?)</p>'
        )

        for m in re.finditer(pattern, html_text, re.S):
            url, name, pic, inner, name2, actor = m.groups()
            vod_id = self._id_from_url(url)
            if not vod_id or vod_id in seen:
                continue
            seen.add(vod_id)

            # 副标题（更新至XX集 / 正片 / TC中字 …）
            m_rem = re.search(r'<span class="pic-text[^"]*">(.*?)</span>', inner, re.S)

            videos.append({
                "vod_id": vod_id,
                "vod_name": _clean(name) or _clean(name2),
                "vod_pic": _safe_img(pic),
                "vod_remarks": _clean(m_rem.group(1)) if m_rem else "",
                "vod_actor": _clean(actor),
                "vod_play_from": "森林影院",
            })

        # 兜底：侧栏 / 相关推荐里属性顺序不同的卡片
        if not videos:
            for m in re.finditer(
                r'<a class="[^"]*stui-vodlist__thumb[^"]*"\s+href="(/yingshi/z\d+\.html)"'
                r'[^>]*?title="([^"]*)"[^>]*?data-original="([^"]*)"[^>]*>(.*?)</a>',
                html_text, re.S
            ):
                url, name, pic, inner = m.groups()
                vod_id = self._id_from_url(url)
                if not vod_id or vod_id in seen:
                    continue
                seen.add(vod_id)
                m_rem = re.search(r'<span class="pic-text[^"]*">(.*?)</span>', inner, re.S)
                videos.append({
                    "vod_id": vod_id,
                    "vod_name": _clean(name),
                    "vod_pic": _safe_img(pic),
                    "vod_remarks": _clean(m_rem.group(1)) if m_rem else "",
                    "vod_play_from": "森林影院",
                })

        return videos

    def _parse_pager(self, html_text):
        """
        三路兜底拿总页数：
          ① <span class="num">1/23751</span>   ← 移动端最可靠
          ② 尾页链接 ...-{n}.html
          ③ 数字链接里的最大值
        """
        m = re.search(r'<span class="num">\s*(\d+)\s*/\s*(\d+)\s*</span>', html_text)
        if m:
            try:
                return int(m.group(2))
            except Exception:
                pass

        m = re.search(r'href="[^"]*?-(\d+)\.html"[^>]*>\s*尾页', html_text)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                pass

        nums = [
            int(x) for x in re.findall(
                r'<li class="hidden-xs[^"]*"><a href="[^"]*?-(\d+)\.html">\d+</a></li>',
                html_text
            )
        ]
        if nums:
            return max(nums)

        # 搜索页/筛选页的分页是 /page/{n}/ 形式
        nums = [
            int(x) for x in re.findall(r'<(?:li|a)[^>]*href="[^"]*/page/(\d+)/[^"]*"', html_text)
        ]
        if nums:
            return max(nums)

        return 0

    # ----------------------------------------------------------------
    #  5.7 详情页
    # ----------------------------------------------------------------

    def detailContent(self, ids):
        # ids 可能是 ["123"]、["123", ...] 或字符串
        vod_id = ""
        if isinstance(ids, (list, tuple)):
            if ids:
                vod_id = str(ids[0])
        else:
            vod_id = str(ids or "")

        vod_id = self._id_from_url(vod_id) or re.sub(r'\D', '', vod_id)
        if not vod_id:
            return {"list": []}

        cache_key = "d_%s" % vod_id
        cached = self._detail_cache.get(cache_key)
        if cached and time.time() - cached["t"] < DETAIL_CACHE_TTL:
            return {"list": [cached["v"]]}

        url = "%s/yingshi/z%s.html" % (HOST, vod_id)
        html_text = self.fetch(url)
        if not html_text:
            # 详情页同样加激进重试，避免 TVBox 里点进去一片空白
            self.log("detail retry hard: %s" % url)
            html_text = self.fetch_hard(url, referer=HOST + "/")
        if not html_text:
            return {"list": []}

        vod = self._parse_detail(html_text, vod_id)
        if not vod:
            return {"list": []}

        self._detail_cache[cache_key] = {"t": time.time(), "v": vod}
        return {"list": [vod]}

    def _parse_detail(self, html_text, vod_id):
        """
        详情页结构（stui-content__detail）：

          <h1 class="title">片名</h1>
          <p class="data"><span class="text-muted">主演：</span><a>…</a>&nbsp;<a>…</a></p>
          <p class="data"><span class="text-muted">导演：</span><a>…</a></p>
          <p class="data">
            <span class="text-muted">类型：</span>剧情,科幻,灾难
            <span class="split-line"></span>
            <span class="text-muted hidden-xs">地区：</span>日本
            <span class="split-line"></span>
            <span class="text-muted hidden-xs">年份：</span>2026
          </p>
          <p class="desc detail hidden-xs">
            <span class="detail-sketch">短简介</span>
            <span class="detail-content" style="display:none">完整简介</span>
          </p>
        """
        vod = {
            "vod_id": vod_id,
            "vod_name": "",
            "vod_pic": "",
            "type_name": "",
            "vod_year": "",
            "vod_area": "",
            "vod_remarks": "",
            "vod_actor": "",
            "vod_director": "",
            "vod_content": "",
            "vod_play_from": "",
            "vod_play_url": "",
        }

        # 片名
        m = re.search(r'<div class="stui-content__detail">\s*<h1 class="title">(.*?)</h1>',
                      html_text, re.S)
        if m:
            vod["vod_name"] = _clean(m.group(1))
        if not vod["vod_name"]:
            m = re.search(r'<title>(.*?)</title>', html_text, re.S)
            if m:
                vod["vod_name"] = _clean(m.group(1)).split("-")[0].strip()

        # 封面 + 副标题（pic-text 即站点上的角标：TC中字 / 第40集已完结 …）
        m = re.search(r'<a class="stui-vodlist__thumb picture v-thumb"[^>]*>(.*?)</a>',
                      html_text, re.S)
        if m:
            inner = m.group(1)
            m2 = re.search(r'data-original="([^"]*)"', inner)
            if m2:
                vod["vod_pic"] = _safe_img(m2.group(1))
            m3 = re.search(r'<span class="pic-text[^"]*">(.*?)</span>', inner, re.S)
            if m3:
                vod["vod_remarks"] = _clean(m3.group(1))

        # 主演（多个 <a> 逗号拼接）
        m = re.search(r'<span class="text-muted">主演：</span>(.*?)</p>', html_text, re.S)
        if m:
            names = [_clean(x) for x in re.findall(r'<a[^>]*>(.*?)</a>', m.group(1), re.S)]
            vod["vod_actor"] = ",".join([x for x in names if x])

        # 导演
        m = re.search(r'<span class="text-muted">导演：</span>(.*?)</p>', html_text, re.S)
        if m:
            names = [_clean(x) for x in re.findall(r'<a[^>]*>(.*?)</a>', m.group(1), re.S)]
            vod["vod_director"] = ",".join([x for x in names if x])

        # 类型 / 地区 / 年份 拼在同一个 <p> 里，以 split-line 分隔
        m = re.search(r'<span class="text-muted">类型：</span>(.*?)</p>', html_text, re.S)
        if m:
            seg = m.group(1)
            vod["type_name"] = _clean(re.split(r'<span class="split-line"></span>', seg)[0]).strip(" ,")
            m_area = re.search(r'地区：</span>(.*?)(?:<span class="split-line"></span>|$)', seg, re.S)
            if m_area:
                vod["vod_area"] = _clean(m_area.group(1)).strip(" ,")
            m_year = re.search(r'年份：</span>(.*?)$', seg, re.S)
            if m_year:
                vod["vod_year"] = _clean(m_year.group(1)).strip(" ,")

        # 简介：优先取 detail-content（完整版），退化到 detail-sketch（摘要）
        m = re.search(r'<span class="detail-content"[^>]*>(.*?)</span>', html_text, re.S)
        if not m:
            m = re.search(r'<span class="detail-sketch">(.*?)</span>', html_text, re.S)
        if m:
            content = _clean(m.group(1))
            content = re.sub(r'^简介[:：]\s*', '', content)
            if content:
                vod["vod_content"] = INTRO_PREFIX + content

        # 播放列表
        lines, episodes = self._parse_playlist(html_text)
        if lines:
            vod["vod_play_from"] = "$$$".join(lines)
            vod["vod_play_url"] = "$$$".join(episodes)

        return vod

    def _parse_playlist(self, html_text):
        """
        每个线路一个独立面板：

          <div class="stui-pannel-box b playlist mb">
            <h3 class="title">线路1</h3>
            ...
            <ul class="stui-content__playlist clearfix">
              <li><a href="/vodview/z3754249/3/1.html">TC</a></li>
            </ul>
          </div>

        注意：线路顺序【完全按页面 DOM 顺序】输出，不做任何排序！
              实测《伟大的长征》(z3133109) 详情页面板顺序为：
                线路1(sid=6) → 线路2(sid=2) → 线路3(sid=3)
                → 线路4(sid=1) → 线路6(sid=4) → 线路5(sid=5)
              既不是按名字排，也不是按 sid 排 —— 站点网页显示什么顺序，
              我们就原样输出什么顺序，这样 TVBox 里看到的线路列表才和网站一致。
              （「立即播放」按钮指向 sid=1 只是站点的默认播放链接，与显示顺序无关）
        """
        groups = []

        for m in re.finditer(
            r'<div class="stui-pannel-box b playlist[^"]*">(.*?)'
            r'<ul class="stui-content__playlist[^"]*">(.*?)</ul>',
            html_text, re.S
        ):
            head, body = m.group(1), m.group(2)

            m_name = re.search(r'<h3 class="title">\s*(.*?)\s*</h3>', head, re.S)
            line_name = _clean(m_name.group(1)) if m_name else ""
            if not line_name:
                line_name = "线路%d" % (len(groups) + 1)

            eps = []
            for a in re.finditer(r'<a href="(/vodview/z\d+/\d+/\d+\.html)">(.*?)</a>', body, re.S):
                href = a.group(1)
                ep_name = _norm_ep_name(a.group(2))
                if not ep_name:
                    ep_name = "第%d集" % (len(eps) + 1)
                eps.append("%s$%s" % (ep_name, _join_host(href)))

            if eps:
                groups.append({"name": line_name, "eps": eps})

        if not groups:
            return [], []

        # 不排序 —— 保持页面原始顺序
        lines = [g["name"] for g in groups]
        episodes = ["#".join(g["eps"]) for g in groups]
        return lines, episodes

    # ----------------------------------------------------------------
    #  5.8 播放
    # ----------------------------------------------------------------

    def playerContent(self, flag, id, vip_flags):
        play_url = _join_host(id)

        # 兜底返回：解析不出来时把播放页交给 TVBox 内置嗅探，绝不返回空
        result = {"parse": 1, "playUrl": "", "url": play_url, "header": {}}

        cache_key = "p_%s" % play_url
        cached = self._play_cache.get(cache_key)
        if cached and time.time() - cached["t"] < PLAY_CACHE_TTL:
            return cached["v"]

        data = self._parse_player(play_url)
        if not data:
            return result

        url = (data.get("url", "") or "").replace("\\/", "/").strip()
        if not url:
            return result

        header = {
            "User-Agent": MOBILE_UA,
            "Referer": play_url,
            "Origin": HOST,
        }

        # 站点 encrypt=0，url 就是直链 m3u8，直接交给播放器（parse:0）
        # 万一拿到的是网页地址，则降级为 parse:1 交给外部解析
        if self.isVideoFormat(url):
            result = {"parse": 0, "playUrl": "", "url": url, "header": header}
        else:
            result = {"parse": 1, "playUrl": "", "url": url, "header": header}

        self._play_cache[cache_key] = {"t": time.time(), "v": result}
        return result

    def _parse_player(self, play_url):
        html_text = self.fetch(play_url, headers={"Referer": HOST + "/"})
        if not html_text:
            # 播放页被墙概率最高，启用激进重试
            self.log("player retry hard: %s" % play_url)
            html_text = self.fetch_hard(play_url, referer=HOST + "/")
        if not html_text:
            return None
        return self._parse_player_html(html_text)

    def _parse_player_html(self, html_text):
        """
        播放页内联一段 player_aaaa（苹果CMS 标准播放器变量）：

          var player_aaaa={"flag":"play","encrypt":0,...,"url":"https:\\/\\/vv.jisuzyv.com\\/play\\/xxx\\/index.m3u8",
                           "from":"jsm3u8","sid":1,"nid":1}</script>

        三种取法，逐级降级，确保一定能拿到 url：
          ① 严格 JSON 解析
          ② 反转义 \/ 后再解析
          ③ 正则逐字段抠（应对末尾带非法字符的情况）
          ④ 页面里裸 m3u8 兜底
        """
        raw = ""

        m = re.search(r'var\s+player_aaaa\s*=\s*(\{.*?\})\s*</script>', html_text, re.S)
        if m:
            raw = m.group(1)
        else:
            m = re.search(r'var\s+player_aaaa\s*=\s*(\{.*?\});', html_text, re.S)
            if m:
                raw = m.group(1)

        if raw:
            raw = raw.strip()

            # ① 严格 JSON
            try:
                return json.loads(raw)
            except Exception:
                pass

            # ② 反转义斜杠
            try:
                return json.loads(raw.replace("\\/", "/"))
            except Exception:
                pass

            # ③ 逐字段正则兜底
            data = {}
            for key in ["url", "from", "server", "link", "link_next", "link_pre"]:
                mm = re.search(r'"%s"\s*:\s*"(.*?)"' % key, raw, re.S)
                if mm:
                    data[key] = mm.group(1).replace("\\/", "/")
            mm = re.search(r'"encrypt"\s*:\s*(\d+)', raw)
            if mm:
                data["encrypt"] = int(mm.group(1))
            if data.get("url"):
                return data

        # ④ 页面里直接出现 m3u8
        mm = re.search(r'(https?://[^\s"\'<>]+?\.m3u8[^\s"\'<>]*)', html_text)
        if mm:
            return {"url": mm.group(1), "from": "m3u8", "encrypt": 0}

        return None

    # ----------------------------------------------------------------
    #  5.9 其它标准接口
    # ----------------------------------------------------------------

    def isVideoFormat(self, url):
        if not url:
            return False
        u = url.lower()
        for ext in [".m3u8", ".mp4", ".flv", ".mkv", ".avi", ".mov", ".ts", ".m4a", ".mp3"]:
            if ext in u:
                return True
        return False

    def manualVideoCheck(self):
        # 站点播放地址均为直链，无需人工校验
        return False

    def localProxy(self, param):
        # 本爬虫无本地代理需求
        return [200, "text/plain", "", ""]
