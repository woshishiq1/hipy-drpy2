# coding=utf-8
"""
枫叶影院 926dy.com | TVBox Python 爬虫 
站点类型: 苹果CMS10 (maccms) + jufeng 模板, 伪静态友好路径
关键:
  - 分类: /type/{id}.html (子分类聚合)  /sort/{id}/{class}/{area}/{year}/by/{time|hits|score}/page/{n}.html
  - 详情: /post/{id}.html
  - 播放: /watch/{id}-{sid}-{nid}.html   player_aaaa.url = URL编码的 m3u8 直链
  - 线路: DD线路(dyttm3u8) / RY线路(rym3u8) / LZ线路(lzm3u8) 三元组对齐
  - 副标题: 取列表卡片 .state (HD/更新至第xx集/已完结)
"""
import re
import sys
import json
import time
import html as _html
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
                print("[fengye]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.926dy.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/template/jufeng/img/logo_black.png"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# 顶级分类: type_id -> 分类页 type/{id}.html ; sort_id 用于筛选列表
CLASSES = [
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "2",  "type_name": "连续剧"},
    {"type_id": "3",  "type_name": "综艺"},
    {"type_id": "4",  "type_name": "动漫"},
    {"type_id": "34", "type_name": "短剧"},
]

_SORTS = [
    {"n": "最新", "v": "time"},
    {"n": "最热", "v": "hits"},
    {"n": "评分", "v": "score"},
]

_YEARS = [{"n": "全部", "v": ""}] + \
         [{"n": str(y), "v": str(y)} for y in range(2026, 1999, -1)]

# ============================================================
# 二级分类（网站 type 页第一行: 全部 / 国产剧 / 大陆综艺 / 国产动漫 ...）
# 实测要点：
#   1) 该行的值 = 苹果CMS 详情页「类型」字段(vod_class)，用 class= 传即可命中
#   2) class 可与 area / year / by / page 任意组合，且顺序不限
#   3) 站点 vod_class 只有单值，故 sub / genre 互斥（代码里已判优）
#   4) 下列 v 均为线上实测有数据的值；空值项(如"港台剧")已剔除，避免点开空白
# ============================================================
SUB_TYPES = {
    "1": [
        {"n": "全部", "v": ""},
        {"n": "动作片", "v": "动作"},
        {"n": "喜剧片", "v": "喜剧"},
        {"n": "爱情片", "v": "爱情"},
        {"n": "科幻片", "v": "科幻"},
        {"n": "恐怖片", "v": "恐怖"},
        {"n": "剧情片", "v": "剧情"},
        {"n": "战争片", "v": "战争"},
        {"n": "纪录片", "v": "记录"},
    ],
    "2": [
        {"n": "全部", "v": ""},
        {"n": "国产剧", "v": "国产"},
        {"n": "欧美剧", "v": "欧美"},
        {"n": "海外剧", "v": "海外"},
    ],
    "3": [
        {"n": "全部", "v": ""},
        {"n": "大陆综艺", "v": "大陆综艺"},
        {"n": "日韩综艺", "v": "日韩综艺"},
        {"n": "港台综艺", "v": "港台综艺"},
        {"n": "欧美综艺", "v": "欧美综艺"},
    ],
    "4": [
        {"n": "全部", "v": ""},
        {"n": "国产动漫", "v": "国产动漫"},
        {"n": "日韩动漫", "v": "日韩动漫"},
        {"n": "欧美动漫", "v": "欧美动漫"},
        {"n": "海外动漫", "v": "海外动漫"},
    ],
    "34": [
        {"n": "全部", "v": ""},
    ],
}

# 地区（逐分类，与站点下拉一致；短剧无地区行）
_AREAS = {
    "1": ["全部", "大陆", "香港", "台湾", "美国", "法国", "英国", "日本", "韩国",
          "德国", "泰国", "印度", "意大利", "西班牙", "加拿大", "其他"],
    "2": ["全部", "韩国", "香港", "台湾", "日本", "美国", "泰国", "英国",
          "新加坡", "其他"],
    "3": ["全部", "内地", "港台", "日韩", "欧美"],
    "4": ["全部", "国产", "日本", "欧美", "其他"],
    "34": ["全部"],
}

# 剧情题材（仅电影该行真实投放有效: 喜剧/爱情/恐怖/动作/科幻/剧情/战争）
_MOVIE_GENRES = ["全部", "喜剧", "爱情", "恐怖", "动作", "科幻", "剧情", "战争"]

FILTERS = {}
for _c in CLASSES:
    _tid = _c["type_id"]
    _fl = [{"key": "sub", "name": "分类", "value": SUB_TYPES.get(_tid, [{"n": "全部", "v": ""}])}]

    if _tid == "1":
        _fl.append({"key": "genre", "name": "剧情",
                    "value": [{"n": x, "v": "" if x == "全部" else x} for x in _MOVIE_GENRES]})

    _fl.append({"key": "area", "name": "地区",
                "value": [{"n": x, "v": "" if x == "全部" else x}
                          for x in _AREAS.get(_tid, ["全部"])]})
    _fl.append({"key": "year", "name": "年份", "value": _YEARS})
    _fl.append({"key": "by", "name": "排序", "value": _SORTS})
    FILTERS[_tid] = _fl


# ===================== 正则 =====================
# 列表卡片：整块 li.item（含 .state 副标题 / 评分 / 标题 / tags）
_RE_CARD = re.compile(
    r'<a\s+href="(/post/\d+\.html)"[^>]*class="thumb"[^>]*>'
    r'([\s\S]{0,900}?)</a>\s*'
    r'<h5[^>]*class="subject"[^>]*>\s*<a[^>]*>([\s\S]*?)</a>',
    re.S | re.I)

_RE_TITLE_ATTR = re.compile(r'title="([^"]*)"', re.I)
_RE_IMG_SRC = re.compile(
    r'<img[^>]*?(?:data-original|data-src|src)="([^"]+)"', re.I)
_RE_STATE = re.compile(r'<span[^>]*class="state"[^>]*>([\s\S]*?)</span>', re.I)
_RE_SCORE = re.compile(r'<span[^>]*class="tip-(?:score|gf|tj)"[^>]*>([\s\S]*?)</span>', re.I)
_RE_TAGS = re.compile(r'<p[^>]*class="tags"[^>]*>([\s\S]*?)</p>', re.I)

# 详情页
_RE_H1 = re.compile(r'<h1[^>]*class="article-subject-m"[^>]*>([\s\S]*?)</h1>', re.I)
_RE_H1_ANY = re.compile(r'<h1[^>]*>([\s\S]*?)</h1>', re.I)
_RE_THUMB = re.compile(
    r'<img[^>]*?(?:data-original|data-src|src)="([^"]+)"[^>]*?id="movie_thumb"', re.I)
_RE_THUMB2 = re.compile(
    r'<img[^>]*?id="movie_thumb"[^>]*?(?:data-original|data-src|src)="([^"]+)"', re.I)
_RE_INFO_P = re.compile(
    r'<p>\s*<label>([^<：:]{1,8})[：:]?\s*</label>\s*<span>([\s\S]{0,3000}?)</span>\s*</p>', re.I)
_RE_SUMMARY = re.compile(
    r'<div class="summary-con[\s\S]*?<div class="box">\s*<div[^>]*>([\s\S]*?)</div>',
    re.I)
_RE_META_DESC = re.compile(
    r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', re.I)

# 线路/剧集
_RE_RESOURCE = re.compile(r'<div class="resource-box">([\s\S]*?)</section>', re.I)
_RE_TAB = re.compile(r'class="tab-nav"[^>]*>([\s\S]*?)</a>', re.I)
_RE_RB_ITEM = re.compile(
    r'<div class="rb-item"[^>]*>\s*<ul[^>]*>([\s\S]*?)</ul>\s*</div>', re.I)
_RE_EP = re.compile(r'<a\s+href="(/watch/\d+-\d+-\d+\.html)"[^>]*>([\s\S]*?)</a>', re.I)

# 播放页
_RE_PLAYER = re.compile(r'var\s+player_aaaa\s*=\s*(\{[\s\S]*?\})\s*</script>', re.I)
_RE_VIDEO_ANY = re.compile(r'https?://[^\s"\'<>\\]+?\.(?:m3u8|mp4)[^\s"\'<>\\]*', re.I)

# 分页
_RE_PAGE_TOTAL = re.compile(r'mac_page_total"\)\.text\((\d+)\)', re.I)
_RE_PAGE_NUM = re.compile(r'/page/(\d+)\.html', re.I)
_RE_RECORD = re.compile(r'mac_record_total"\)\.text\((\d+)\)', re.I)

# 线路优先级（保持站点顺序：DD -> RY -> LZ，前端即按此顺序展示）
_LINE_PRIORITY = ["dyttm3u8", "rym3u8", "lzm3u8", "xhm3u8", "bfzym3u8", "ffm3u8",
                  "lzm3u8", "wjm3u8", "kuaikan", "modum3u8", "jsm3u8", "mtm3u8", "vip"]
_LINE_ALIAS = {
    "dyttm3u8": "DD线路", "rym3u8": "RY线路", "lzm3u8": "LZ线路",
    "xhm3u8": "星海资源", "bfzym3u8": "暴风资源", "ffm3u8": "非凡M3U8",
    "wjm3u8": "无尽M3U8", "kuaikan": "快看", "modum3u8": "魔都M3U8",
    "jsm3u8": "极速M3U8", "mtm3u8": "茅台M3U8", "vip": "VIP线路",
}


class Spider(Spider):

    def getName(self):
        return "枫叶影院"

    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}

        self.site_url = (self.extend.get("site") or HOST).rstrip("/")
        self.headers = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
                      "image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": self.site_url + "/",
            "Upgrade-Insecure-Requests": "1",
        }
        self.default_pic = DEFAULT_PIC
        self._play_cache = {}
        self._line_name_cache = {}
        self.log("init: site=%s" % self.site_url)

    # ------------------------------------------------------------------ 基础
    def _raw_get(self, url, headers, timeout, allow_redirects=True):
        """带 SSL 兜底的原始请求"""
        try:
            try:
                return self.fetch(url, headers=headers, timeout=timeout,
                                  allow_redirects=allow_redirects)
            except TypeError:
                return self.fetch(url, headers=headers, timeout=timeout)
        except Exception as e1:
            msg = str(e1)
            if ("SSL" in msg) or ("certificate" in msg.lower()):
                self.log("SSL 异常，降级重试: %s" % msg[:80])
                try:
                    import requests as _rq2
                    rs = _rq2.get(url, headers=headers, timeout=timeout,
                                  verify=False, allow_redirects=allow_redirects)
                    rs.encoding = "utf-8"
                    return rs
                except Exception as e2:
                    self.log("降级仍失败: %s" % str(e2)[:80])
            raise

    def _fetch(self, url, timeout=20, headers=None, allow_redirects=True):
        try:
            h = dict(self.headers)
            if headers:
                h.update(headers)
            rsp = self._raw_get(url, h, timeout, allow_redirects)
            text = ""
            if hasattr(rsp, "text"):
                text = rsp.text or ""
            elif hasattr(rsp, "content"):
                text = rsp.content.decode("utf-8", "ignore")
            if not text:
                try:
                    text = rsp.content.decode("utf-8", "ignore")
                except Exception:
                    text = ""
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
        s = _html.unescape(s)
        s = (s.replace("\u00a0", " ").replace("\u3000", " ")
              .replace("\ufffd", ""))
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n{2,}", "\n", s)
        return s.strip()

    # ------------------------------------------------------------------ 列表解析
    def _extract_videos(self, html):
        videos = []
        seen = set()
        if not html:
            return videos

        for m in _RE_CARD.finditer(html):
            href = m.group(1).replace("&amp;", "&")
            inner = m.group(2)
            inner_title = m.group(3)

            if href in seen:
                continue
            seen.add(href)

            name = ""
            mt = _RE_TITLE_ATTR.search(inner)
            if mt:
                name = self._clean(mt.group(1))
            if not name:
                name = self._clean(inner_title)
            if not name:
                name = href.split("/")[-1].replace(".html", "")

            pic = ""
            mp = _RE_IMG_SRC.search(inner)
            if mp:
                pic = self._fix_url(mp.group(1))

            remarks = ""
            ms = _RE_STATE.search(inner)
            if ms:
                remarks = self._clean(ms.group(1))

            score = ""
            msc = _RE_SCORE.search(inner)
            if msc:
                score = self._clean(msc.group(1))
                # tip-gf 形如 "豆瓣高分9.0"，抽取数字
                mnum = re.search(r"([\d.]+)\s*$", score)
                if mnum:
                    score = mnum.group(1)

            tags = ""
            mtg = _RE_TAGS.search(m.group(0))
            if mtg:
                tags = self._clean(mtg.group(1))

            videos.append({
                "vod_id": href,
                "vod_name": name[:120],
                "vod_pic": pic or self.default_pic,
                "vod_remarks": remarks,
                "vod_score": score,
                "vod_tag": tags.split("/")[0].strip() if tags else "",
            })

        # 兜底：纯 href 抓取
        if not videos:
            for href in re.findall(r'href="(/post/\d+\.html)"', html):
                if href in seen:
                    continue
                seen.add(href)
                videos.append({
                    "vod_id": href,
                    "vod_name": href.split("/")[-1].replace(".html", ""),
                    "vod_pic": self.default_pic,
                    "vod_remarks": "",
                })
        return videos

    def _page_count(self, html, limit=32):
        if not html:
            return 1
        m = _RE_PAGE_TOTAL.search(html)
        if m:
            try:
                return max(1, int(m.group(1)))
            except Exception:
                pass
        nums = _RE_PAGE_NUM.findall(html)
        if nums:
            try:
                return max(int(x) for x in nums)
            except Exception:
                pass
        # 末页 "»" 链接
        m = re.search(r'title="末页"[^>]*href="[^"]*?page/(\d+)\.html"', html, re.I)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                pass
        m = re.search(r'>\.\.(\d+)页<', html)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                pass
        return limit

    # ------------------------------------------------------------------ 首页
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        html = self._fetch(self.site_url + "/")
        self.log("home HTML 长度: %d" % len(html))
        videos = self._extract_videos(html)
        # 去重保序
        out, seen = [], set()
        for v in videos:
            if v["vod_id"] in seen:
                continue
            seen.add(v["vod_id"])
            out.append(v)
        self.log("home 解析: %d 条" % len(out))
        return {"list": out}

    # ------------------------------------------------------------------ 分类
    def _sort_path(self, tid, extend, page):
        """构造 /sort/{tid}/class/{c}/area/{a}/year/{y}/by/{by}/page/{n}.html

        站点 vod_class 字段只存一个值，故 class 只能出现一次：
          优先 sub（二级分类: 国产/大陆综艺/国产动漫…），
          其次 genre（电影剧情: 喜剧/爱情…），二者互斥。
        """
        seg = [self.site_url, "sort", str(tid)]

        cls = (extend.get("sub") or "").strip()
        if not cls or cls == "全部":
            cls = (extend.get("genre") or "").strip()
        if not cls or cls == "全部":
            cls = (extend.get("class") or "").strip()

        area = (extend.get("area") or "").strip()
        year = (extend.get("year") or "").strip()
        by = (extend.get("by") or "").strip()

        if cls and cls != "全部":
            seg.append("class")
            seg.append(urllib.parse.quote(cls))
        if area and area != "全部":
            seg.append("area")
            seg.append(urllib.parse.quote(area))
        if year and year != "全部":
            seg.append("year")
            seg.append(urllib.parse.quote(str(year)))
        if by and by != "全部":
            seg.append("by")
            seg.append(urllib.parse.quote(by))
        if page and int(page) > 1:
            seg.append("page")
            seg.append(str(int(page)))
        return "/".join(seg) + ".html"

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        if not isinstance(extend, dict):
            extend = {}
        extend = {k: v for k, v in extend.items() if v not in ("", None, "全部")}

        videos, pagecount, url = [], 1, ""
        total_pages = 0
        # 依次尝试：完整条件 -> 去掉 class -> 仅本期 id，保证任何组合都不空白
        for i in range(3):
            cur = dict(extend)
            if i == 1:
                cur.pop("sub", None)
                cur.pop("genre", None)
                cur.pop("class", None)
            elif i == 2:
                cur = {}
            url = self._sort_path(tid, cur, page if i == 0 else 1)
            self.log("category[%d]: %s" % (i, url))
            html = self._fetch(url)
            videos = self._extract_videos(html)
            self.log("  HTML 长度: %d, 解析: %d 条" % (len(html), len(videos)))
            if videos:
                pagecount = self._page_count(html)
                total_pages = pagecount
                break
        if not total_pages:
            total_pages = 1

        limit = len(videos) if videos else 32
        self.log("  最终: %d 条, 总页数: %d" % (len(videos), pagecount))

        return {
            "list": videos,
            "page": page if videos else 1,
            "pagecount": pagecount,
            "limit": limit,
            "total": pagecount * limit,
        }

    # ------------------------------------------------------------------ 搜索
    def searchContent(self, key, quick=False, pg="1"):
        page = int(pg) if pg else 1
        kw = urllib.parse.quote(key)
        if page <= 1:
            url = "%s/search/%s----------1---.html" % (self.site_url, kw)
        else:
            url = "%s/search/%s----------%d---.html" % (self.site_url, kw, page)
        self.log("search: %s" % url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))

        videos = self._extract_videos(html)
        if not videos:
            # 兜底：?wd= 形式
            url2 = "%s/search/-------------.html?wd=%s" % (self.site_url, kw)
            html2 = self._fetch(url2)
            videos = self._extract_videos(html2)
            if not videos:
                html2 = html
            html = html2

        pagecount = self._page_count(html)
        total = pagecount * (len(videos) if videos else 32)
        m = _RE_RECORD.search(html)
        if m:
            try:
                total = int(m.group(1))
            except Exception:
                pass

        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": len(videos) if videos else 32,
            "total": total,
        }

    def searchContentPage(self, key, quick=False, pg="1"):
        return self.searchContent(key, quick, pg)

    # ------------------------------------------------------------------ 详情
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

        # ---- 标题
        name = ""
        m = _RE_H1.search(html) or _RE_H1_ANY.search(html)
        if m:
            name = self._clean(m.group(1))
        if not name:
            mt = re.search(r"<title>(.*?)</title>", html, re.S | re.I)
            if mt:
                name = self._clean(mt.group(1)).split("_")[0].split("免费观看")[0]
        name = re.sub(r"\s*[《》]\s*", "", name).strip() or vod_id

        # ---- 封面
        pic = self.default_pic
        m = _RE_THUMB.search(html)
        if m:
            pic = self._fix_url(m.group(1)) or self.default_pic
        if pic == self.default_pic:
            mo = re.search(r'<meta[^>]*property="og:image"[^>]*content="([^"]+)"', html, re.I)
            if mo:
                pic = self._fix_url(mo.group(1))

        # ---- 元信息 (类型/导演/主演/年份/地区/资源/豆瓣)
        info = {}
        for k, v in _RE_INFO_P.findall(html):
            k = self._clean(k).replace("：", "").replace(":", "")
            val = self._clean(v)
            if k and k not in info:
                info[k] = val

        director = info.get("导演", "")
        actor = re.sub(r"\s*,\s*", ", ", info.get("主演", ""))
        year = info.get("年份", "")
        area = info.get("地区", "")
        remark = re.sub(r"\s+", "", info.get("资源", ""))
        remark = re.sub(r"(期|集|话)\1+$", r"\1", remark)
        score = info.get("豆瓣", "")
        vclass = info.get("类型", "")

        # ---- 简介（详情介绍 -> meta description）
        content = ""
        m = _RE_SUMMARY.search(html)
        if m:
            content = self._clean(m.group(1))
        if not content:
            m = _RE_META_DESC.search(html)
            if m:
                desc = _html.unescape(m.group(1))
                # 去掉站点头部套话，保留“简介：”之后
                idx = desc.find("简介：")
                content = self._clean(desc[idx + 3:]) if idx >= 0 else self._clean(desc)
        content = re.sub(r"\s{2,}", "\n", content).strip()
        content = INTRO_PREFIX + ("\n" + content if content else "")

        # ---- 线路 + 剧集（严格对齐 tab 名称与 rb-item 顺序）
        groups = self._parse_episodes(html)
        self.log("  剧集: %s" % [(k, len(v)) for k, v in groups])

        if not groups:
            return {"list": [{
                "vod_id": vod_id,
                "vod_name": name,
                "vod_pic": pic,
                "vod_content": content,
                "vod_actor": actor,
                "vod_director": director,
                "vod_year": year,
                "vod_area": area,
                "vod_score": score,
                "vod_remarks": remark,
                "vod_play_from": "",
                "vod_play_url": "",
            }]}

        # 线路按站点展示顺序（tab 自然顺序）输出
        play_from, play_url = [], []
        for origin, eps in groups:
            play_from.append(_LINE_ALIAS.get(origin, origin))
            play_url.append("#".join("%s$%s" % (n, h) for n, h in eps))

        total_ep = sum(len(e) for _, e in groups)
        if remark:
            remarks = remark
        else:
            remarks = "%d条线路" % len(groups)
        if total_ep and len(groups) == 1:
            remarks = "%s｜%d集" % (remarks, total_ep)

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_year": year,
            "vod_area": area,
            "vod_score": score,
            "vod_class": vclass,
            "vod_remarks": remarks,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }]}

    def _parse_episodes(self, html):
        """返回 [(origin_key, [(ep_name, ep_url), ...]), ...]，顺序与站点线路一致"""
        result = []
        try:
            box = _RE_RESOURCE.search(html)
            seg = box.group(1) if box else html

            tabs = [self._clean(t) for t in _RE_TAB.findall(seg)]
            items = _RE_RB_ITEM.findall(seg)

            # 无 tab（部分模板）时退化：直接从 watch 链接里解析 sid
            if not items:
                buckets = {}
                order = []
                for href, txt in _RE_EP.findall(html):
                    ms = re.match(r"/watch/(\d+)-(\d+)-(\d+)\.html", href)
                    if not ms:
                        continue
                    sid = ms.group(2)
                    if sid not in buckets:
                        buckets[sid] = []
                        order.append(sid)
                    buckets[sid].append((self._clean(txt) or ("第%s集" % ms.group(3)),
                                         self._fix_url(href)))
                for sid in order:
                    result.append(("sid" + sid, buckets[sid]))
                return result

            for idx, item in enumerate(items):
                eps = []
                for href, txt in _RE_EP.findall(item):
                    ep_name = self._clean(txt)
                    if not ep_name:
                        mid = re.search(r"-(\d+)\.html", href)
                        ep_name = "第%s集" % (mid.group(1) if mid else len(eps) + 1)
                    eps.append((ep_name, self._fix_url(href.replace("&amp;", "&"))))
                if not eps:
                    continue
                tab_name = tabs[idx] if idx < len(tabs) else ""
                key = self._line_key(tab_name, eps[0][1], idx)
                result.append((key, eps))
            return result
        except Exception as e:
            self.log("  剧集解析失败: %s" % e)
            return result

    def _line_key(self, tab_name, ep_url, idx):
        """把站点线路中文名映射成 origin key，保证顺序与站点一致"""
        name = (tab_name or "").upper()
        if name:
            for k, alias in _LINE_ALIAS.items():
                if alias.upper() == name:
                    return k
        # 从 watch URL 推断 sid 顺序：DD=3 RY=2 LZ=1
        m = re.search(r"/watch/\d+-(\d+)-\d+\.html", ep_url or "")
        if m:
            sid = m.group(1)
            mapping = {"3": "dyttm3u8", "2": "rym3u8", "1": "lzm3u8"}
            if sid in mapping:
                return mapping[sid]
        return "line%d" % idx

    # ------------------------------------------------------------------ 播放
    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith("http") else self._fix_url(id)
        self.log("player: %s" % play_page)

        now = int(time.time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 600:
                return res

        html = self._fetch(play_page)
        info = self._extract_player(html)

        real_url = info.get("url", "")
        origin = info.get("from", "")

        if real_url:
            low = real_url.lower()
            # 直链 m3u8 / mp4 —— 大多数线路都是 CDN 直链，直接交给播放器
            if ".m3u8" in low or ".mp4" in low:
                res = {
                    "parse": 0,
                    "playUrl": "",
                    "url": real_url,
                    "header": {
                        "User-Agent": UA,
                        "Referer": self.site_url + "/",
                    },
                }
                self._play_cache[play_page] = (now, res)
                self.log("  => 直链(%s): %s" % (origin or "?", real_url[:160]))
                return res

            # 非标准直链（iframe / 解析接口页）→ 嗅探
            res = {
                "parse": 1,
                "playUrl": "",
                "url": real_url,
                "header": {"User-Agent": UA, "Referer": play_page},
            }
            self._play_cache[play_page] = (now, res)
            return res

        # 兜底：播放页里任意 m3u8/mp4
        m = _RE_VIDEO_ANY.search(html or "")
        if m:
            u = m.group(0).replace("\\/", "/").replace("&amp;", "&")
            res = {
                "parse": 0,
                "playUrl": "",
                "url": u,
                "header": {"User-Agent": UA, "Referer": self.site_url + "/"},
            }
            self._play_cache[play_page] = (now, res)
            self.log("  => 兜底直链: %s" % u[:160])
            return res

        # 最后交给 TVBox 嗅探
        res = {"parse": 1, "playUrl": "", "url": play_page,
               "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}
        self._play_cache[play_page] = (now, res)
        return res

    def _extract_player(self, html):
        """解析 var player_aaaa={...}，返回 {url, from, encrypt, ...}"""
        out = {}
        if not html:
            return out
        m = _RE_PLAYER.search(html)
        if not m:
            m2 = re.search(r'"url"\s*:\s*"([^"]+)"', html)
            if m2:
                out["url"] = self._decode_url(m2.group(1))
            return out

        raw = m.group(1).strip()
        data = None
        try:
            data = json.loads(raw)
        except Exception:
            try:
                data = json.loads(raw.replace("\\'", "'"))
            except Exception:
                data = None

        if data is None:
            m3 = re.search(r'"url"\s*:\s*"([^"]+)"', raw)
            if m3:
                out["url"] = self._decode_url(m3.group(1))
            m4 = re.search(r'"from"\s*:\s*"([^"]*)"', raw)
            if m4:
                out["from"] = m4.group(1)
            return out

        out["from"] = data.get("from", "") or ""
        raw_url = data.get("url", "") or ""
        out["encrypt"] = data.get("encrypt", 0)

        # 站点 encrypt=1 时 url 为 URL 编码（可能多重）
        out["url"] = self._decode_url(raw_url)
        out["url_next"] = self._decode_url(data.get("url_next", "") or "")
        out["link_next"] = data.get("link_next", "")
        return out

    def _decode_url(self, u):
        if not u:
            return ""
        u = str(u).replace("\\/", "/").replace("&amp;", "&")
        for _ in range(3):
            if "%" not in u:
                break
            nu = urllib.parse.unquote(u)
            if nu == u:
                break
            u = nu
        return u.strip()

    # ------------------------------------------------------------------ 其他
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
        if not url:
            return False
        low = url.lower()
        return ".m3u8" in low or ".mp4" in low or ".flv" in low

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()
