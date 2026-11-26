# coding=utf-8
"""
茶杯虎影视 cuptgr.com | TVBox Python 爬虫
站点形态: MacCMS mizhiady 模板, 服务端 HTML 直出, 无 PoW / 验证码墙。
分类: 1 电影 / 2 电视剧 / 3 综艺 / 4 动漫 (四分类, 无短剧)。
路由:
  - 分类       /type/<tid>.html        分页 /type/<tid>-<page>.html
  - 筛选       /show/<12 槽>.html    seg0=tid seg1=地区 seg2=排序 seg3=类型 seg4=语言 seg8=页码 seg11=年份
  - 详情       /detail/<vid>.html
  - 搜索       /search/<词>-------------.html?wd=<词>
  - 播放       /play/<vid>-<sid>-<nid>.html
播放: player_aaaa 明文 JSON (encrypt=0); m3u8/mp4 直链 parse:0, 平台外链 parse:1 嗅探。
"""
import re
import sys
import json
import time
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
            r = self._sess.get(url, headers=headers, timeout=timeout, **kw)
            r.encoding = 'utf-8'
            return r

        def log(self, *a, **kw):
            try:
                print("[cuptgr]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://cuptgr.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/template/mizhiady/statics/images/error-poster.png"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

CLASSES = [
    {"type_id": "1", "type_name": "电影"},
    {"type_id": "2", "type_name": "电视剧"},
    {"type_id": "3", "type_name": "综艺"},
    {"type_id": "4", "type_name": "动漫"},
]

# 站点 show 库页线上渲染五组筛选: 地区 / 年份 / 剧情(类型) / 语言 / 排序。
# 选项清单按四分类逐分类取自线上 show/<tid>-----------.html (地区/类型/语言各分类不同, 不共用)。
# show 12 槽: seg0=tid seg1=地区 seg2=排序(time/hits/score) seg3=类型 seg4=语言 seg8=页码 seg11=年份。
_YEARS = [str(y) for y in range(2027, 2009, -1)]
_SORTS = [{"n": "全部", "v": ""}, {"n": "添加时间", "v": "time"},
          {"n": "人气高低", "v": "hits"}, {"n": "评分高低", "v": "score"}]

_FILTER_OPTIONS = {
    "1": {
        "area": ["大陆", "香港", "台湾", "美国", "法国", "英国", "日本", "韩国", "德国",
                 "泰国", "印度", "意大利", "西班牙", "加拿大", "其他"],
        "type": ["喜剧", "爱情", "恐怖", "动作", "科幻", "剧情", "战争", "警匪", "犯罪",
                 "动画", "奇幻", "武侠", "冒险", "枪战", "悬疑", "惊悚", "经典", "青春",
                 "文艺", "微电影", "古装", "历史", "运动", "农村", "儿童", "网络电影"],
        "lang": ["国语", "英语", "粤语", "闽南语", "韩语", "日语", "法语", "德语", "其它"],
    },
    "2": {
        "area": ["内地", "韩国", "香港", "台湾", "日本", "美国", "泰国", "英国", "新加坡", "其他"],
        "type": ["古装", "战争", "青春偶像", "喜剧", "家庭", "犯罪", "动作", "奇幻", "剧情",
                 "历史", "经典", "乡村", "情景", "商战", "网剧", "其他"],
        "lang": ["国语", "英语", "粤语", "闽南语", "韩语", "日语", "其它"],
    },
    "3": {
        "area": ["内地", "港台", "日韩", "欧美"],
        "type": ["选秀", "情感", "访谈", "播报", "旅游", "音乐", "美食", "纪实", "曲艺",
                 "生活", "游戏互动", "财经", "求职"],
        "lang": ["国语", "英语", "粤语", "闽南语", "韩语", "日语", "其它"],
    },
    "4": {
        "area": ["国产", "日本", "欧美", "其他"],
        "type": ["情感", "科幻", "热血", "推理", "搞笑", "冒险", "萝莉", "校园", "动作",
                 "机战", "运动", "战争", "少年", "少女", "社会", "原创", "亲子", "益智",
                 "励志", "其他"],
        "lang": ["国语", "英语", "粤语", "闽南语", "韩语", "日语", "其它"],
    },
}

FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    opt = _FILTER_OPTIONS.get(tid, {"area": [], "type": [], "lang": []})

    def _vals(items):
        return [{"n": "全部", "v": ""}] + [{"n": x, "v": x} for x in items]

    FILTERS[tid] = [
        {"key": "area", "name": "地区", "value": _vals(opt["area"])},
        {"key": "year", "name": "年份",
         "value": [{"n": "全部", "v": ""}] + [{"n": y, "v": y} for y in _YEARS]},
        {"key": "class", "name": "剧情", "value": _vals(opt["type"])},
        {"key": "lang", "name": "语言", "value": _vals(opt["lang"])},
        {"key": "sort", "name": "排序", "value": _SORTS},
    ]

# ===================== 正则 =====================
# 卡片锚点: <a href="/detail/<id>.html">
_RE_CARD_HREF = re.compile(r'<a\s+href="(/detail/(\d+)\.html)"[^>]*>', re.I)
_RE_IMG = re.compile(
    r'<img[^>]*?(?:data-original|data-src|src)="([^"]*)"', re.S | re.I)
_RE_IMG_ALT = re.compile(r'<img[^>]*?alt="([^"]*)"', re.S | re.I)
_RE_TITLE = re.compile(r'<div class="title">([\s\S]*?)</div>', re.I)
_RE_SCORE_CARD = re.compile(r'<div class="score">([\d.]+)</div>', re.I)
_RE_TIME_CARD = re.compile(r'<div class="info-time">([\s\S]*?)</div>', re.I)

# 详情
_RE_H1 = re.compile(r'<h1[^>]*>([\s\S]*?)</h1>', re.I)
_RE_TITLE_TAG = re.compile(r'<title>([\s\S]*?)</title>', re.I)
_RE_IMG_BOX = re.compile(r'<div class="img-box">([\s\S]*?)</div>\s*<div class="bottom', re.S | re.I)
_RE_DATA_ORIGINAL = re.compile(r'data-original="([^"]*)"', re.I)
_RE_DATA_SRC = re.compile(r'data-src="([^"]*)"', re.I)
_RE_IMG_SRC = re.compile(r'<img[^>]*?src="([^"]*)"', re.S | re.I)
_RE_TAGS = re.compile(r'<a class="tag"[^>]*>([^<]+)</a>', re.I)
_RE_DIRECTOR_BLOCK = re.compile(
    r'<div class="director text-overflow">\s*<div class="name">([^<]+)</div>\s*([\s\S]*?)</div>',
    re.S | re.I)
_RE_INTRO_FULL = re.compile(
    r'<div class="wrapper_more_text">([\s\S]*?)</div>', re.S | re.I)
_RE_INTRO_DIV = re.compile(
    r'<div class="intro">([\s\S]*?)</div>', re.S | re.I)
_RE_META_DESC = re.compile(
    r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', re.I)
_RE_SCORE = re.compile(r'<div class="score">([\d.]+)</div>', re.I)
_RE_ROLES = re.compile(
    r'<div class="roles">\s*<div class="name">别名:</div>([\s\S]*?)</div>', re.I)
_RE_ITEM = re.compile(
    r'<div class="item">([\s\S]*?)</div>\s*(?=<div class="line">|<div class="item">|</div>\s*</div>)',
    re.S | re.I)
_RE_ITEM_TOP = re.compile(r'<div class="item-top">([\s\S]*?)</div>', re.S | re.I)
_RE_ITEM_BOT = re.compile(r'<div class="item-bottom">([\s\S]*?)</div>', re.S | re.I)
_RE_YEAR = re.compile(r'(19|20)\d{2}')
_RE_AREA_PAREN = re.compile(r'\(([^)]+)\)')

# 线路 / 选集
_RE_TAB = re.compile(
    r'<a[^>]+href="#(playlist\d+)"[^>]*class="swiper-slide-text">([^<]+)<', re.I)
_RE_TAB_NAME = re.compile(r'swiper-slide-text">([^<]+)<', re.I)
_RE_EP_BOX = re.compile(
    r'<div id="(playlist\d+)"[^>]*>([\s\S]*?)(?=<div id="playlist\d+"|'
    r'<div class="item">|$)', re.S | re.I)
_RE_EP_A = re.compile(
    r'<a[^>]*href="(/play/[^"]+\.html)"[^>]*>([\s\S]*?)</a>', re.I)

_PLACEHOLDER_PICS = ("lazyload-poster", "error-poster", "default", "placeholder",
                      "loading", "blank")


class Spider(Spider):

    def getName(self):
        return "茶杯虎影视"

    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
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
        self.log("init: site=%s" % self.site_url)

    # ---------------- 基础工具 ----------------
    def _fetch(self, url, timeout=60, headers=None):
        try:
            h = dict(self.headers)
            if headers:
                h.update(headers)
            rsp = self.fetch(url, headers=h, timeout=timeout)
            if hasattr(rsp, "text"):
                return rsp.text or ""
            if hasattr(rsp, "content"):
                return rsp.content.decode("utf-8", "ignore")
            return str(rsp)
        except Exception as e:
            self.log("fetch FAIL %s -> %s" % (url, e))
            return ""

    def _fix_url(self, url):
        if not url:
            return ""
        url = url.strip()
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
              .replace("&emsp;", " ").replace("&ensp;", " ")
              .replace("&#12288;", " "))
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n{2,}", "\n", s)
        return s.strip()

    def _is_placeholder_pic(self, pic):
        if not pic:
            return True
        return any(k in pic for k in _PLACEHOLDER_PICS)

    def _fix_pic(self, pic):
        pic = self._fix_url(pic)
        if self._is_placeholder_pic(pic):
            return self.default_pic
        return pic or self.default_pic

    # ---------------- 卡片解析 ----------------
    def _extract_videos(self, html):
        videos = []
        seen = set()
        if not html:
            return videos

        # 按 detail 锚点切块, 块内提取封面 / 片名 / 备注
        anchors = list(_RE_CARD_HREF.finditer(html))
        for i, m in enumerate(anchors):
            href = m.group(1)
            vid = m.group(2)
            if href in seen:
                continue
            end = anchors[i + 1].start() if i + 1 < len(anchors) else len(html)
            block = re.sub(r"<!--[\s\S]*?-->", "", html[m.start():end])

            # 封面: data-original / data-src 优先, 兜底 src, 剔除占位图
            pic = ""
            pm = re.search(r'data-original="([^"]*)"', block, re.I)
            if not pm:
                pm = re.search(r'data-src="([^"]*)"', block, re.I)
            if not pm:
                pm = _RE_IMG.search(block)
            if pm:
                pic = pm.group(1)

            # 片名: img alt 兜底 .title
            am = _RE_IMG_ALT.search(block)
            name = self._clean(am.group(1)) if am else ""
            if not name:
                tm = _RE_TITLE.search(block)
                name = self._clean(tm.group(1)) if tm else ""
            name = name[:100] or vid

            # 备注: 评分兜底更新时间
            remarks = ""
            sm = _RE_SCORE_CARD.search(block)
            if sm:
                remarks = sm.group(1)
            if not remarks:
                tm = _RE_TIME_CARD.search(block)
                if tm:
                    remarks = self._clean(tm.group(1))

            seen.add(href)
            videos.append({
                "vod_id": href,
                "vod_name": name,
                "vod_pic": self._fix_pic(pic),
                "vod_remarks": remarks,
            })

        self.log("  卡片: %d 条 (去重 %d)" % (len(anchors), len(videos)))
        return videos

    # ---------------- 筛选 URL ----------------
    def _build_show_url(self, tid, ctype="", page=1, area="", sort="", lang="", year=""):
        seg = [""] * 12
        seg[0] = str(tid)
        seg[1] = area or ""    # 地区
        seg[2] = sort or ""    # 排序 time/hits/score
        seg[3] = ctype or ""   # 剧情/类型
        seg[4] = lang or ""    # 语言
        seg[8] = str(page) if page and int(page) > 1 else ""  # 页码
        seg[11] = year or ""   # 年份
        slug = "-".join(urllib.parse.quote(x) for x in seg)
        return "/show/%s.html" % slug

    def _pagecount(self, html, limit=24):
        if not html:
            return 1
        pages = re.findall(r'/type/\d+-(\d+)\.html', html)
        if pages:
            try:
                return max(int(p) for p in pages) + 1
            except Exception:
                pass
        # 本站深页重复首页, 不下发真实总页; 首页可见即单页
        return 1

    # ---------------- 契约: 首页 ----------------
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        try:
            html = self._fetch(self.site_url + "/")
            self.log("home HTML 长度: %d" % len(html))
            videos = self._extract_videos(html)
            if not videos:
                # 多级兜底: 合并四个分类首页, href 去重
                merged, seen = [], set()
                for c in CLASSES:
                    h = self._fetch("%s/type/%s.html" % (self.site_url, c["type_id"]))
                    for v in self._extract_videos(h):
                        if v["vod_id"] not in seen:
                            seen.add(v["vod_id"])
                            merged.append(v)
                videos = merged
            return {"list": videos}
        except Exception as e:
            self.log("homeVideoContent FAIL: %s" % e)
            return {"list": []}

    # ---------------- 契约: 分类 / 筛选 ----------------
    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = int(pg) if pg else 1
            if isinstance(extend, str):
                try:
                    extend = json.loads(extend)
                except Exception:
                    extend = {}
            if not extend:
                extend = {}
            for k in list(extend.keys()):
                if extend[k] in ("", None, "全部"):
                    del extend[k]

            ctype = extend.get("class") or ""
            area = extend.get("area") or ""
            lang = extend.get("lang") or ""
            year = extend.get("year") or ""
            sort = extend.get("sort") or ""

            has_filter = any([ctype, area, lang, year, sort])
            if has_filter:
                url = self.site_url + self._build_show_url(
                    tid, ctype, page, area=area, sort=sort, lang=lang, year=year)
            elif page > 1:
                url = "%s/type/%s-%d.html" % (self.site_url, tid, page)
            else:
                url = "%s/type/%s.html" % (self.site_url, tid)

            self.log("category: %s" % url)
            html = self._fetch(url)
            videos = self._extract_videos(html)
            pagecount = self._pagecount(html)
            self.log("  最终: %d 条, 总页数: %d" % (len(videos), pagecount))

            return {
                "list": videos,
                "page": page,
                "pagecount": pagecount,
                "limit": 24,
                "total": len(videos),
            }
        except Exception as e:
            self.log("categoryContent FAIL: %s" % e)
            return {"list": [], "page": 1, "pagecount": 1, "limit": 24, "total": 0}

    # ---------------- 契约: 搜索 ----------------
    def searchContent(self, key, quick, pg="1"):
        try:
            page = int(pg) if pg else 1
            keyword = urllib.parse.quote(key)
            url = "%s/search/%s-------------.html?wd=%s" % (
                self.site_url, keyword, keyword)
            self.log("search: %s" % url)
            html = self._fetch(url)
            videos = self._extract_videos(html)
            return {
                "list": videos,
                "page": page,
                "pagecount": 1,
                "limit": 24,
                "total": len(videos),
            }
        except Exception as e:
            self.log("searchContent FAIL: %s" % e)
            return {"list": [], "page": 1, "pagecount": 1, "limit": 24, "total": 0}

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------------- 契约: 详情 ----------------
    def detailContent(self, ids):
        try:
            if not ids:
                return {"list": []}
            vod_id = str(ids[0])
            url = vod_id if vod_id.startswith("http") else self._fix_url(vod_id)
            self.log("detail: %s" % url)

            html = self._fetch(url)
            if not html:
                return {"list": []}

            # 片名
            name = ""
            m = _RE_H1.search(html)
            if m:
                name = self._clean(m.group(1))
            if not name:
                m = _RE_TITLE_TAG.search(html)
                if m:
                    name = self._clean(m.group(1).split("_")[0].split("-")[0])
            name = re.sub(r"\s*\(\d{4}\)\s*$", "", name).strip() or vod_id

            # 海报: data-original / data-src 优先, 兜底 src, 剔除懒加载占位图
            pic = self.default_pic
            box = _RE_IMG_BOX.search(html)
            box_html = re.sub(r"<!--[\s\S]*?-->", "", box.group(1)) if box else html
            pm = _RE_DATA_ORIGINAL.search(box_html) or \
                _RE_DATA_SRC.search(box_html) or \
                _RE_IMG_SRC.search(box_html)
            if pm:
                pic = self._fix_pic(pm.group(1))

            # 类型标签
            vclass = ", ".join(self._clean(x) for x in _RE_TAGS.findall(html)
                               if self._clean(x))

            # 导演 / 主演
            director, actor = "", ""
            for dm in _RE_DIRECTOR_BLOCK.finditer(html):
                label = self._clean(dm.group(1)).rstrip(":：")
                body = self._clean(dm.group(2))
                if label == "导演":
                    director = body
                elif label == "主演":
                    actor = re.sub(r"\s*,\s*", ", ", body)

            # 简介: 折叠全文 -> intro 段 -> meta description
            content = ""
            m = _RE_INTRO_FULL.search(html)
            if m:
                content = self._clean(m.group(1))
            if not content:
                m = _RE_INTRO_DIV.search(html)
                if m:
                    content = self._clean(m.group(1))
            if not content:
                m = _RE_META_DESC.search(html)
                if m:
                    content = self._clean(m.group(1))
            content = re.sub(r"^(剧情简介|简介|剧情)[:：]\s*", "", content)
            if content:
                content = INTRO_PREFIX + "\n" + content
            else:
                content = INTRO_PREFIX

            # 年份 / 地区 / 语言 / 评分: 按 item-bottom 标签配对 item-top
            year, area, lang, score = "", "", "", ""
            for im in _RE_ITEM.finditer(html):
                blk = im.group(1)
                tm = _RE_ITEM_TOP.search(blk)
                bm = _RE_ITEM_BOT.search(blk)
                if not tm or not bm:
                    continue
                top = self._clean(tm.group(1))
                bot = self._clean(bm.group(1))
                if "评分" in bot:
                    sm = _RE_SCORE.search(blk)
                    if sm:
                        score = sm.group(1)
                elif bot == "语言":
                    lang = top
                elif bot == "上映时间":
                    date_seg = top
                    ym = _RE_YEAR.search(date_seg)
                    if ym:
                        year = ym.group(0)
                    am = _RE_AREA_PAREN.search(date_seg)
                    if am:
                        area = self._clean(am.group(1))
            if score in ("0", "0.0", "0.00"):
                score = ""

            # 别名 (副标题); 站点占位 "未知" 视为空
            subtitle = ""
            rm = _RE_ROLES.search(html)
            if rm:
                subtitle = self._clean(rm.group(1))
            if subtitle in ("未知", "暂无", "无", "未知 "):
                subtitle = ""

            # ===== 线路 / 选集 =====
            groups = self._parse_line_groups(html)
            self.log("  线路: %s" % {k: len(v) for k, v in groups.items()})

            if not groups:
                return {"list": []}

            # 线路顺序严格对齐网站 nav 顺序
            tabs = self._parse_tabs(html)
            ordered = []
            for pid, line_name in tabs:
                if pid in groups:
                    ordered.append((line_name or pid, groups[pid]))
            # 兜底: nav 未配对上的线路按 DOM 顺序补入
            for pid, eps in groups.items():
                if not any(p == pid for p, _ in tabs):
                    ordered.append((pid, eps))

            play_from, play_url = [], []
            for line_name, eps in ordered:
                play_from.append(line_name)
                play_url.append("#".join("%s$%s" % (n, h) for n, h in eps))

            remarks = ""
            if score:
                remarks = score
            remarks = remarks or ("%d条线路" % len(ordered))

            return {"list": [{
                "vod_id": vod_id,
                "vod_name": name,
                "vod_pic": pic,
                "vod_content": content,
                "vod_actor": actor,
                "vod_director": director,
                "vod_score": score,
                "vod_remarks": remarks,
                "vod_class": vclass,
                "vod_year": year,
                "vod_area": area,
                "vod_lang": lang,
                "vod_subtitle": subtitle,
                "vod_play_from": "$$$".join(play_from),
                "vod_play_url": "$$$".join(play_url),
            }]}
        except Exception as e:
            self.log("detailContent FAIL: %s" % e)
            return {"list": []}

    def _parse_tabs(self, html):
        """线路标签栏: [(playlistN, 线路名)], 顺序即网站 nav 顺序。"""
        tabs = [(m.group(1), self._clean(m.group(2)))
                for m in _RE_TAB.finditer(html)]
        if tabs:
            return tabs
        # 兜底: 仅按名字顺序, playlist 编号顺延
        names = [self._clean(x) for x in _RE_TAB_NAME.findall(html)]
        return [("playlist%d" % (i + 1), n) for i, n in enumerate(names)]

    def _parse_line_groups(self, html):
        """返回 {playlistN: [(集名, 播放链接), ...]}, 选集按 nid 正序去重。"""
        groups = {}
        try:
            for box in _RE_EP_BOX.finditer(html):
                pid, body = box.group(1), box.group(2)
                eps, seen_nid = [], set()
                for em in _RE_EP_A.finditer(body):
                    href = em.group(1).replace("&amp;", "&")
                    ep_name = self._clean(em.group(2))
                    nid_m = re.search(r'-(\d+)\.html', href)
                    nid = nid_m.group(1) if nid_m else str(len(eps) + 1)
                    if nid in seen_nid:
                        continue
                    seen_nid.add(nid)
                    if not ep_name or ep_name in ("立即播放", "播放"):
                        ep_name = "第%s集" % nid
                    eps.append((int(nid), ep_name, href))
                eps.sort(key=lambda x: x[0])
                groups[pid] = [(n, h) for _, n, h in eps]
        except Exception as e:
            self.log("  线路选集解析失败: %s" % e)
        return groups

    # ---------------- 契约: 播放 ----------------
    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith("http") else self._fix_url(id)
        self.log("player: %s" % play_page)

        now = int(time.time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 600:
                return res

        html = self._fetch(play_page)
        aa = self._parse_player_json(html)
        url = ""
        if aa:
            url = (aa.get("url") or "").replace("\\/", "/")
            url = url.replace("\\u0026", "&").replace("&amp;", "&")
            encrypt = str(aa.get("encrypt") or "0")
        else:
            encrypt = "0"

        self.log("  url: %s" % (url[:160] if url else "EMPTY"))

        # 情况 A: 明文 m3u8 / mp4 直链
        if url.startswith("http") and (".m3u8" in url.lower() or ".mp4" in url.lower()):
            res = {
                "parse": 0,
                "playUrl": "",
                "url": url,
                "header": {"User-Agent": UA, "Referer": self.site_url + "/"},
            }
            self._play_cache[play_page] = (now, res)
            self.log("  => 直链: %s" % url[:160])
            return res

        # 情况 B: 平台外链 / 网盘, 交客户端嗅探播放页
        res = {
            "parse": 1,
            "playUrl": "",
            "url": play_page,
            "header": {"User-Agent": UA, "Referer": self.site_url + "/"},
        }
        self._play_cache[play_page] = (now, res)
        return res

    @staticmethod
    def _parse_player_json(html):
        """括号配对提取 player_aaaa 对象, 兼容嵌套大括号与字符串转义。"""
        if not html:
            return None
        i = html.find("player_aaaa")
        if i < 0:
            return None
        j = html.find("{", i)
        if j < 0:
            return None
        depth, instr, esc = 0, False, False
        for k in range(j, len(html)):
            c = html[k]
            if esc:
                esc = False
                continue
            if c == "\\":
                esc = True
                continue
            if c == '"':
                instr = not instr
                continue
            if instr:
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    raw = html[j:k + 1]
                    try:
                        return json.loads(raw)
                    except Exception:
                        try:
                            return json.loads(raw.replace("\\/", "/"))
                        except Exception:
                            return None
        return None

    # ---------------- 契约: 其余 ----------------
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
            rsp = self.fetch(url, headers={"User-Agent": UA,
                                           "Referer": self.site_url + "/"}, timeout=15)
            content = rsp.content
            ctype = rsp.headers.get("Content-Type", "image/jpeg")
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
