# coding=utf-8
"""
麒麟影视网 www.qlys.cc | TVBox Python 爬虫 
站点特征: 苹果CMS (maccms) + 海螺主题 HL093
关键:
  - 分类列表: /index.php/vod/type/id/{tid}/page/{pg}.html
  - 筛选列表: /index.php/vod/show/id/{tid}/class/{c}/year/{y}/area/{a}/page/{pg}.html
  - 详情页解析 line-tabs (线路) + ep-chip (剧集)
  - 播放页解析 player_aaaa JSON, 直接返回 m3u8 直链
  - 搜索: /index.php/vod/search.html?wd=xxx&page=N
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
                print("[qlys]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.qlys.cc"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = ""

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

CLASSES = [
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "2",  "type_name": "电视剧"},
    {"type_id": "3",  "type_name": "短剧"},
    {"type_id": "4",  "type_name": "动漫"},
    {"type_id": "5",  "type_name": "综艺"},
    {"type_id": "23", "type_name": "漫剧"},
]

# 与网站筛选栏完全一致 (分类=子类型ID / 剧情 / 年代 / 地区)
# 子类型 ID 取自网站 /vod/show/id/{tid}.html 筛选栏链接
_SUBTYPE = {
    "1": [("10", "动作片"), ("11", "恐怖片"), ("12", "科幻片"),
          ("13", "战争片"), ("14", "爱情片"), ("15", "喜剧片"),
          ("16", "剧情片"), ("17", "记录片")],
    "2": [("6", "内地剧"), ("7", "港台剧"), ("8", "日韩剧"),
          ("9", "欧美剧"), ("22", "泰剧")],
    "4": [("18", "内地番"), ("19", "日韩番"), ("20", "港台番"),
          ("21", "欧美番")],
}
_CLASS_MAP = {
    "1": ["剧情", "悬疑", "恐怖", "惊悚", "喜剧", "爱情", "犯罪", "动作",
          "动画", "奇幻", "音乐", "科幻", "历史", "战争", "冒险", "家庭",
          "纪录", "西部", "古装", "传记", "运动", "武侠", "歌舞", "记录片",
          "灾难", "短片"],
    "2": ["喜剧", "爱情", "恐怖", "动作", "科幻", "剧情", "战争", "警匪",
          "犯罪", "动画", "奇幻", "武侠", "冒险", "枪战", "悬疑", "惊悚",
          "经典", "青春", "文艺", "微电视剧", "古装", "历史", "运动",
          "农村", "儿童", "网络电视剧", "其他"],
    "4": ["热血", "励志", "玄幻", "古风", "动态漫", "恋爱", "青春", "校园",
          "运动", "科幻", "冒险", "魔法", "日常", "治愈", "机战", "推理",
          "都市", "小说改", "游戏改", "漫画改"],
}
_YEARS = [{"n": "全部", "v": ""}] + \
         [{"n": str(y), "v": str(y)} for y in range(2026, 1999, -1)]
_AREAS = [
    {"n": "全部", "v": ""},
    {"n": "美国", "v": "美国"}, {"n": "法国", "v": "法国"},
    {"n": "中国", "v": "中国"}, {"n": "日本", "v": "日本"},
    {"n": "韩国", "v": "韩国"}, {"n": "中国香港", "v": "中国香港"},
    {"n": "俄罗斯", "v": "俄罗斯"}, {"n": "波兰", "v": "波兰"},
    {"n": "德国", "v": "德国"}, {"n": "意大利", "v": "意大利"},
    {"n": "中国台湾", "v": "中国台湾"}, {"n": "澳大利亚", "v": "澳大利亚"},
    {"n": "西班牙", "v": "西班牙"}, {"n": "英国", "v": "英国"},
    {"n": "加拿大", "v": "加拿大"}, {"n": "泰国", "v": "泰国"},
    {"n": "印度", "v": "印度"}, {"n": "丹麦", "v": "丹麦"},
    {"n": "中国大陆", "v": "中国大陆"}, {"n": "马来西亚", "v": "马来西亚"},
    {"n": "菲律宾", "v": "菲律宾"}, {"n": "瑞典", "v": "瑞典"},
    {"n": "挪威", "v": "挪威"}, {"n": "阿根廷", "v": "阿根廷"},
    {"n": "冰岛", "v": "冰岛"}, {"n": "保加利亚", "v": "保加利亚"},
    {"n": "爱尔兰", "v": "爱尔兰"},
]

FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    subs = _SUBTYPE.get(tid, [])
    cls = _CLASS_MAP.get(tid, [])
    fl = []
    if subs:
        fl.append({"key": "type", "name": "分类",
                   "value": [{"n": "全部", "v": ""}] +
                            [{"n": n, "v": v} for v, n in subs]})
    if cls:
        fl.append({"key": "class", "name": "剧情",
                   "value": [{"n": "全部", "v": ""}] +
                            [{"n": x, "v": x} for x in cls]})
    fl.append({"key": "year", "name": "年代", "value": _YEARS})
    fl.append({"key": "area", "name": "地区", "value": _AREAS})
    FILTERS[tid] = fl


# ===================== 正则 =====================
# 列表卡片 (分类/搜索/首页通用)
_RE_CARD = re.compile(
    r'<a href="(/index\.php/vod/detail/id/\d+\.html)" class="movie-link" title="([^"]*)">\s*'
    r'<div class="movie-poster">\s*'
    r'<img[^>]*?src="([^"]*)"[^>]*?>\s*'
    r'(?:<span class="ep-badge">([^<]*)</span>)?',
    re.S | re.I)

# 轮播大卡 (首页)
_RE_BIG_CARD = re.compile(
    r'<img[^>]*?src="([^"]*)"[^>]*?alt="([^"]*)">[\s\S]{0,300}?'
    r'<a href="(/index\.php/vod/detail/id/\d+\.html)" class="btn-play"',
    re.S | re.I)

_RE_HREF = re.compile(r'href="(/index\.php/vod/detail/id/\d+\.html)', re.I)
_RE_IMG = re.compile(r'<img[^>]*?alt="([^"]*)"[^>]*?(?:data-src|src)="([^"]*)"', re.S | re.I)
_RE_EP_BADGE = re.compile(r'<span class="ep-badge">([^<]*)</span>', re.I)

# 详情页
_RE_H1 = re.compile(r'<h1[^>]*>([\s\S]*?)</h1>', re.I)
_RE_PIC = re.compile(r'<div class="detail-poster">[\s\S]{0,300}?<img src="([^"]*)"', re.S | re.I)
_RE_DESC = re.compile(r'<div id="descInner">([\s\S]*?)</div>', re.S | re.I)
_RE_META_DESC = re.compile(
    r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', re.I)
_RE_STAFF = re.compile(
    r'<div class="staff-row">([\s\S]*?)</div>\s*(?:<div|<span)', re.S | re.I)
_RE_DIRECTOR = re.compile(r'<strong>导演：</strong>([^<]*)', re.I)
_RE_ACTOR = re.compile(r'<strong>主演：</strong>([^<]*)', re.I)
_RE_SCORE = re.compile(r'rank-badge[^>]*>[^<]*<[^>]*>\s*</?i[^>]*>[^<]*([\d.]+)\s*<', re.I)

# 线路 tab: <a ... class="line-tab ..." data-line="1" data-target="#epList1" title="XG">
_RE_LINE_TAB = re.compile(
    r'<a href="javascript:;" class="line-tab[^"]*"\s*'
    r'data-line="(\d+)"\s*data-target="#epList\d+"\s*title="([^"]*)"', re.I)

# 剧集: 宽松匹配 ep-chip / ep-btn <a> 整块, 再分别提取属性 (兼容属性顺序差异)
_RE_EPISODE_A = re.compile(
    r'<a\s+href="(/index\.php/vod/play/id/\d+/sid/(\d+)/nid/(\d+)\.html)"'
    r'([^>]*)>', re.I)
_RE_EP_HAS_CLASS = re.compile(r'class="(?:ep-chip|ep-btn)', re.I)
_RE_EP_SID = re.compile(r'data-sid="(\d+)"', re.I)
_RE_EP_TITLE = re.compile(r'title="([^"]*)"', re.I)

# 线路别名 (网站 line-tab title 常见值)
_LINE_ALIAS = {
    "XG": "西瓜线路", "WSY": "无尽线路", "SD": "闪电线路",
    "DYTT": "电影天堂", "ZY": "最大资源", "KY": "快看线路",
    "MD": "陌东线路", "JM": "杰明线路",
}

# 播放页 player_aaaa
_RE_PLAYER = re.compile(r'var\s+player_aaaa\s*=\s*(\{.*?\})\s*</script>', re.S)

# 分页
_RE_PAGE = re.compile(r'class="page-btn[^"]*"\s+title="第\d+页"', re.I)
_RE_TOTAL_PAGE = re.compile(r'共\s*(\d+)\s*页')


class Spider(Spider):

    def getName(self):
        return "麒麟影视"

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
        self._warmed = False
        self.log("init: site=%s" % self.site_url)

    def _warm_up(self):
        if self._warmed:
            return
        try:
            self._fetch(self.site_url + "/", timeout=15)
            self._warmed = True
            self.log("预热完成")
        except Exception as e:
            self.log("预热失败: %s" % e)

    def _fetch(self, url, timeout=30, headers=None):
        try:
            h = dict(self.headers)
            if headers:
                h.update(headers)
            rsp = self.fetch(url, headers=h, timeout=timeout)
            text = ""
            if hasattr(rsp, "text"):
                text = rsp.text or ""
            elif hasattr(rsp, "content"):
                text = rsp.content.decode("utf-8", "ignore")
            else:
                text = str(rsp)
            return text
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
              .replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">"))
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n{2,}", "\n", s)
        return s.strip()

    def _extract_videos(self, html):
        """解析列表卡片, 与网站 movie-card 结构完全一致"""
        videos = []
        seen = set()
        if not html:
            self.log("  HTML 为空")
            return videos

        matches = _RE_CARD.findall(html)
        self.log("  卡片: %d 条" % len(matches))
        for href, alt, pic, badge in matches:
            href = href.replace("&amp;", "&")
            if href in seen:
                continue
            seen.add(href)
            videos.append({
                "vod_id":      href,
                "vod_name":    self._clean(alt)[:100] or href,
                "vod_pic":     self._fix_url(pic) or self.default_pic,
                "vod_remarks": self._clean(badge)[:20],
            })
        if videos:
            return videos

        # 兜底: 首页轮播大卡
        for pic, alt, href in _RE_BIG_CARD.findall(html):
            href = href.replace("&amp;", "&")
            if href in seen:
                continue
            seen.add(href)
            videos.append({
                "vod_id":      href,
                "vod_name":    self._clean(alt)[:100] or href,
                "vod_pic":     self._fix_url(pic) or self.default_pic,
                "vod_remarks": "",
            })
        if videos:
            return videos

        # 最终兜底: href 与 img 配对
        hrefs = _RE_HREF.findall(html)
        imgs = _RE_IMG.findall(html)
        self.log("  兜底: href=%d img=%d" % (len(hrefs), len(imgs)))
        for i, href in enumerate(hrefs):
            if href in seen:
                continue
            seen.add(href)
            alt, pic = ("", "")
            if i < len(imgs):
                alt, pic = imgs[i]
            videos.append({
                "vod_id":      href,
                "vod_name":    self._clean(alt)[:100] or href,
                "vod_pic":     self._fix_url(pic) or self.default_pic,
                "vod_remarks": "",
            })
        return videos

    def _page_count(self, html):
        if not html:
            return 1
        # 优先: "共 10855 部" -> ceil(总数/每页24)
        m = re.search(r'共\s*(\d+)\s*部', html)
        if m:
            try:
                total = int(m.group(1))
                if total > 0:
                    return (total + 23) // 24
            except Exception:
                pass
        pages = re.findall(r'/page/(\d+)\.html', html)
        if pages:
            try:
                return max(int(p) for p in pages)
            except Exception:
                pass
        return 9999

    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        self._warm_up()
        html = self._fetch(self.site_url + "/")
        self.log("home HTML 长度: %d" % len(html))
        videos = self._extract_videos(html)
        return {"list": videos}

    def _build_show_url(self, tid, page, extend):
        """构建与网站完全一致的筛选 URL (子分类ID替换主ID, 与网站链接一致)"""
        real_id = extend.get("type") or tid
        base = "%s/index.php/vod/show/id/%s" % (self.site_url, real_id)
        segs = []
        if extend.get("class"):
            segs.append("class/" + urllib.parse.quote(str(extend["class"])))
        if extend.get("year"):
            segs.append("year/" + urllib.parse.quote(str(extend["year"])))
        if extend.get("area"):
            segs.append("area/" + urllib.parse.quote(str(extend["area"])))
        segs.append("page/%d" % page)
        return base + "/" + "/".join(segs) + ".html"

    def categoryContent(self, tid, pg, filter, extend):
        self._warm_up()
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

        if filter and extend:
            url = self._build_show_url(tid, page, extend)
        else:
            url = "%s/index.php/vod/type/id/%s/page/%d.html" % (
                self.site_url, tid, page)

        self.log("category: %s" % url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))

        videos = self._extract_videos(html)
        pagecount = self._page_count(html)
        self.log("  最终: %d 条, 总页数: %d" % (len(videos), pagecount))

        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 24, "total": pagecount * 24,
        }

    def searchContent(self, key, quick, pg="1"):
        self._warm_up()
        page = int(pg) if pg else 1
        url = "%s/index.php/vod/search.html?wd=%s&page=%d" % (
            self.site_url, urllib.parse.quote(key), page)
        self.log("search: %s" % url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))
        videos = self._extract_videos(html)
        return {
            "list": videos, "page": page,
            "pagecount": self._page_count(html),
            "limit": 24, "total": 999,
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0])
        url = vod_id if vod_id.startswith("http") else self._fix_url(vod_id)
        self.log("detail: %s" % url)

        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))
        if not html:
            return {"list": []}

        # 标题
        name = ""
        try:
            m = _RE_H1.search(html)
            if m:
                name = self._clean(m.group(1))
        except Exception:
            pass
        if not name:
            try:
                m = re.search(r"<title>(.*?)</title>", html, re.S)
                if m:
                    name = self._clean(m.group(1).split("_")[0])
            except Exception:
                pass
        name = re.sub(r"\s*\(\d{4}\)\s*$", "", name).strip() or vod_id

        # 封面
        pic = self.default_pic
        try:
            m = _RE_PIC.search(html)
            if m:
                pic = self._fix_url(m.group(1))
        except Exception:
            pass

        # 简介
        content = ""
        try:
            m = _RE_DESC.search(html)
            if m:
                content = self._clean(m.group(1))
        except Exception:
            pass
        if not content:
            try:
                m = _RE_META_DESC.search(html)
                if m:
                    content = self._clean(m.group(1))
            except Exception:
                pass

        if content:
            content = INTRO_PREFIX + "\n" + content
        else:
            content = INTRO_PREFIX

        # 导演 / 主演
        director = ""
        actor = ""
        try:
            m = _RE_STAFF.search(html)
            if m:
                staff = m.group(1)
                md = _RE_DIRECTOR.search(staff)
                ma = _RE_ACTOR.search(staff)
                if md:
                    director = self._clean(md.group(1))
                if ma:
                    actor = re.sub(r"\s*,\s*", ", ", self._clean(ma.group(1)))
        except Exception:
            pass

        # 评分 (轮播有 rank-badge, 详情页可能没有)
        score = ""
        try:
            m = re.search(r'rank-badge"[^>]*>[\s\S]{0,120}?([\d.]+)\s*</span>', html)
            if m:
                score = m.group(1)
        except Exception:
            pass

        # ===== 元信息 (与网站 meta-row 一致) =====
        vod_year = vod_area = vod_lang = ""
        vod_class = ""
        try:
            rows = re.findall(
                r'<div class="meta-row[^"]*">([\s\S]*?)</div>', html)
            if rows:
                # 第一行: 年份 / 地区 / 语言
                for m in re.finditer(
                        r'<a href="[^"]*"[^>]*title="([^"]*)"', rows[0]):
                    t = self._clean(m.group(1))
                    if re.match(r"^(19|20)\d{2}$", t):
                        vod_year = t
                    elif not vod_area:
                        vod_area = t
                    elif not vod_lang:
                        vod_lang = t
            # 第二行: 类型 (首个是子分类名, 其余为剧情标签)
            if len(rows) > 1:
                tags = [self._clean(x) for x in
                        re.findall(r'<a href="[^"]*"[^>]*title="([^"]*)"', rows[1])]
                tags = [x for x in tags if x]
                if tags:
                    vod_class = ",".join(tags)
        except Exception as e:
            self.log("  元信息解析失败: %s" % e)
        self.log("  元信息: year=%s area=%s lang=%s class=%s" % (
            vod_year, vod_area, vod_lang, vod_class))

        # ===== 线路 & 剧集 (与网站 line-tabs + ep-chip 一致, 顺序同网站) =====
        line_names = {}
        line_tabs_order = []  # 保持网站 tab 出现顺序
        try:
            for m in _RE_LINE_TAB.finditer(html):
                line_names[m.group(1)] = m.group(2).strip()
                line_tabs_order.append((m.group(1), m.group(2).strip()))
        except Exception:
            pass
        self.log("  线路: %s" % line_names)

        groups = {}
        try:
            for m in _RE_EPISODE_A.finditer(html):
                attrs = m.group(4)
                if not _RE_EP_HAS_CLASS.search(attrs):
                    continue
                ms = _RE_EP_SID.search(attrs)
                if not ms:
                    continue
                sid = ms.group(1)
                nid = m.group(3)
                href = m.group(1).replace("&amp;", "&")
                mt = _RE_EP_TITLE.search(attrs)
                ep_name = self._clean(mt.group(1)) if mt else ""
                # ep-btn 无 title, 取标签内文本兜底
                if not ep_name:
                    end = html.find("</a>", m.end())
                    if 0 < end - m.end() < 200:
                        ep_name = self._clean(html[m.end():end])
                if not ep_name:
                    ep_name = "第%s集" % nid
                groups.setdefault(sid, []).append((int(nid), ep_name, href))
        except Exception as e:
            self.log("  剧集解析失败: %s" % e)

        self.log("  剧集: %s" % {k: len(v) for k, v in groups.items()})

        if not groups:
            return {"list": []}

        # 线路顺序 = 网站 line-tabs 出现顺序 (XG/WSY/DYTT/QY/JJ/FF ...)
        ordered_sids = [s for s, _ in line_tabs_order if s in groups]
        for s in groups:
            if s not in ordered_sids:
                ordered_sids.append(s)

        play_from = []
        play_url = []
        for sid in ordered_sids:
            eps = sorted(groups[sid], key=lambda x: x[0])
            alias = line_names.get(sid) or ("线路%s" % sid)
            play_from.append(alias)
            play_url.append("#".join("%s$%s" % (n, h) for _, n, h in eps))

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_score": score,
            "vod_class": vod_class,
            "vod_area": vod_area,
            "vod_year": vod_year,
            "vod_lang": vod_lang,
            "vod_remarks": ("共%d条线路" % len(groups)) if len(groups) > 1 else "",
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url":  "$$$".join(play_url),
        }]}

    # -------- 播放 --------
    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith("http") else self._fix_url(id)
        self.log("player: %s" % play_page)

        now = int(time.time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 600:
                return res

        html = self._fetch(play_page)
        real_url = self._extract_real_url(html) if html else ""
        self.log("  real_url: %s" % (real_url[:200] if real_url else "EMPTY"))

        if real_url and ".mp4" in real_url.lower():
            res = {
                "parse": 0, "playUrl": "", "url": real_url,
                "header": {"User-Agent": UA, "Referer": self.site_url + "/"},
            }
            self._play_cache[play_page] = (now, res)
            return res

        if real_url and ".m3u8" in real_url.lower():
            # 关键: 服务端会 302 跳转 (svip.xgplayN.com -> vipN.jimxtc.com),
            # master m3u8 内是相对路径子播放列表, 部分播放内核处理不了,
            # 这里自己完成 302 跟随 + master->子 m3u8 解析, 返回最终直链
            final_url = self._resolve_real_m3u8(real_url)
            self.log("  => 最终直链: %s" % final_url[:160])
            res = {
                "parse": 0, "playUrl": "", "url": final_url,
                "header": {"User-Agent": UA, "Referer": self.site_url + "/"},
            }
            self._play_cache[play_page] = (now, res)
            return res

        # 兜底: 交给 TVBox 嗅探
        res = {"parse": 1, "playUrl": "", "url": play_page,
               "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}
        self._play_cache[play_page] = (now, res)
        return res

    def _resolve_real_m3u8(self, url):
        """跟随 302, 若为 master m3u8 则解析出绝对地址的子 m3u8"""
        try:
            rsp = self.fetch(url, headers={
                "User-Agent": UA,
                "Accept": "*/*",
            }, timeout=15)
        except Exception as e:
            self.log("  resolve fail: %s" % e)
            return url

        # requests 跟随 302 后 rsp.url 为最终地址
        final = url
        try:
            if hasattr(rsp, "url") and rsp.url:
                final = rsp.url
        except Exception:
            pass

        text = ""
        try:
            text = rsp.text if hasattr(rsp, "text") else ""
        except Exception:
            text = ""

        if "#EXTM3U" not in text:
            self.log("  非 m3u8 内容, 返回原地址")
            return final

        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
        for i, line in enumerate(lines):
            if line.startswith("#EXT-X-STREAM-INF") and i + 1 < len(lines):
                sub = lines[i + 1].strip()
                if sub.startswith("#"):
                    continue
                # 相对路径 -> 基于最终地址拼接
                full = urllib.parse.urljoin(final, sub)
                self.log("  master 子 m3u8: %s" % full[:160])
                return full

        self.log("  无子 m3u8, 返回最终地址")
        return final

    def _extract_real_url(self, html):
        """解析 player_aaaa JSON, 取真实 m3u8 地址 (encrypt=0)"""
        if not html:
            return ""
        m = _RE_PLAYER.search(html)
        if not m:
            m2 = re.search(r'player_aaaa\s*=\s*(\{[\s\S]*?\})\s*;', html)
            if not m2:
                return ""
            raw = m2.group(1)
        else:
            raw = m.group(1)
        try:
            data = json.loads(raw)
            url = data.get("url", "")
            encrypt = int(data.get("encrypt", 0) or 0)
            if encrypt == 1:
                import base64
                url = base64.b64decode(url).decode("utf-8", "ignore")
            elif encrypt == 2:
                import base64
                url = base64.b64decode(
                    base64.b64decode(url).decode("utf-8", "ignore")
                ).decode("utf-8", "ignore")
            return urllib.parse.unquote(url) if url else ""
        except Exception as e:
            self.log("  player_aaaa 解析失败: %s" % e)
            m3 = re.search(r'"url"\s*:\s*"([^"]+)"', raw)
            return m3.group(1).replace("\\/", "/") if m3 else ""

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
