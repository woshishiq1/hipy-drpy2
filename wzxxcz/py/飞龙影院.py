# coding=utf-8
"""
飞龙影院 www.feilongyy.com | TVBox Python 爬虫
站点结构（传统服务端渲染 HTML 采集站）:
  - 首页:  /
  - 分类:  /type/<tid>.html  （tid: 1 电影 / 2 电视剧 / 5 动漫 / 59 AI漫剧 / 29 短剧 / 37 综艺）
  - 筛选+列表+分页: /vs/<tid>/<题材>/<地区>/<语言=all>/<年份>/<排序=all>/<页码>.html
      · 题材 / 地区 / 年份 取值均来自站点筛选栏实测；语言、排序站点固定 all，爬虫一并写 all
  - 搜索:  /search.html?wd=<关键词>&page=<页码>
  - 详情:  /detail/<id>.html
      · 片名 h1.clearfix；状态 em.em_num；评分 em.em_score
      · 元信息: <em class="em_tit">标签：</em>值 （主演/导演/地区/年份/语言/类型）
      · 简介: li.li_intro 内「简介：」后正文
      · 线路标签: <a apiname="..." alt="线路名">，顺序即线路号；
        选集: 多个 ul.play_num_list，顺序与线路标签一一对应；
        集链接: /play/<id>-<线路号>-<集号>.html
  - 播放:  /play/<id>-<sid>-<nid>.html
      · 内嵌转义 JSON: "url" 指向 m3u8/mp4 直链 / "from":"1080zyk" / "sid" / "nid"
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

        def reset_session(self):
            """关闭并丢弃复用坏连接的会话，下次请求重建新连接。"""
            try:
                if self._session is not None:
                    self._session.close()
            except Exception:
                pass
            self._session = None

        def fetch(self, url, headers=None, **kw):
            timeout = kw.pop('timeout', 15)
            r = self._sess.get(url, headers=headers, timeout=timeout, **kw)
            r.encoding = 'utf-8'
            return r

        def log(self, *a, **kw):
            try:
                print("[feilong]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.feilongyy.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = ""

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# ===================== 分类（对齐站点导航 /type/<id>.html）=====================
CLASSES = [
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "2",  "type_name": "电视剧"},
    {"type_id": "5",  "type_name": "动漫"},
    {"type_id": "59", "type_name": "AI漫剧"},
    {"type_id": "29", "type_name": "短剧"},
    {"type_id": "37", "type_name": "综艺"},
]

# 年代通用区间（站点多数分类 2026~2010）
_YEAR_MAIN = [str(y) for y in range(2026, 2009, -1)]
# 电视剧年代（站点实测 22 个，站点自身缺 2007，按原样保留）
_YEAR_TV = ["2026", "2025", "2024", "2023", "2022", "2021", "2020", "2019", "2018",
            "2017", "2016", "2015", "2014", "2013", "2012", "2011", "2010", "2009",
            "2008", "2006", "2005", "2004"]
# AI漫剧年代（站点实测 2026~2017）
_YEAR_AI = [str(y) for y in range(2026, 2016, -1)]

# 各分类筛选选项（逐字取自站点对应 /type/<tid>.html 筛选栏 dl，顺序与网站一致；
# 地区注意：动漫/短剧/综艺用「内地」，电影/电视剧/AI漫剧用「大陆」）
_FILTER_DATA = {
    "1": {
        "genre": ["喜剧", "爱情", "恐怖", "动作", "科幻", "剧情", "战争", "警匪", "犯罪",
                  "动画", "奇幻", "武侠", "冒险", "枪战", "悬疑", "惊悚", "经典", "青春",
                  "文艺", "微电影", "古装", "历史", "运动", "农村", "儿童", "网络电影"],
        "area": ["大陆", "香港", "台湾", "美国", "法国", "英国", "日本", "韩国", "德国",
                 "泰国", "印度", "意大利", "西班牙", "加拿大", "其他"],
        "year": _YEAR_MAIN,
    },
    "2": {
        "genre": ["古装", "战争", "青春偶像", "喜剧", "家庭", "犯罪", "动作", "奇幻", "剧情",
                  "历史", "经典", "乡村", "情景", "商战", "网剧", "其他"],
        "area": ["大陆", "韩国", "香港", "台湾", "日本", "美国", "泰国", "英国", "新加坡", "其他"],
        "year": _YEAR_TV,
    },
    "5": {
        "genre": ["冒险", "热血", "科幻", "玄幻", "逆袭", "修仙", "爽文", "恋爱", "治愈"],
        "area": ["内地", "韩国", "香港", "台湾", "日本", "美国", "泰国", "英国", "新加坡", "其他"],
        "year": _YEAR_MAIN,
    },
    "59": {
        "genre": ["剧情", "奇幻", "古装", "动作", "逆袭", "穿越", "爱情", "喜剧", "犯罪", "惊悚"],
        "area": ["大陆", "香港", "台湾", "美国", "法国", "英国", "日本", "韩国", "德国",
                 "泰国", "印度", "俄罗斯", "西班牙", "加拿大", "新加坡"],
        "year": _YEAR_AI,
    },
    "29": {
        "genre": ["古装", "现代", "科幻", "悬疑", "爱情"],
        "area": ["内地", "韩国", "香港", "台湾", "日本", "美国", "泰国", "英国", "新加坡", "其他"],
        "year": _YEAR_MAIN,
    },
    "37": {
        "genre": ["真人秀", "脱口秀", "音综", "文化益智"],
        "area": ["内地", "韩国", "香港", "台湾", "日本", "美国", "泰国", "英国", "新加坡", "其他"],
        "year": _YEAR_MAIN,
    },
}

FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    d = _FILTER_DATA[tid]
    FILTERS[tid] = [
        {"key": "genre", "name": "分类",
         "value": [{"n": "全部", "v": ""}] + [{"n": x, "v": x} for x in d["genre"]]},
        {"key": "area", "name": "地区",
         "value": [{"n": "全部", "v": ""}] + [{"n": x, "v": x} for x in d["area"]]},
        {"key": "year", "name": "年代",
         "value": [{"n": "全部", "v": ""}] + [{"n": x, "v": x} for x in d["year"]]},
    ]

# ===================== 正则 =====================
_RE_DETAIL = re.compile(r'href="(/detail/(\d+)\.html)"[^>]*?(?:title="([^"]*)")?', re.I)
_RE_IMG = re.compile(r'data-original="([^"]*)"', re.I)
_RE_TITLE_A = re.compile(r'<a[^>]*href="/detail/\d+\.html"[^>]*title="([^"]*)"', re.I)
_RE_STRONG = re.compile(r'<strong>([^<]*)</strong>', re.I)
_RE_TIPS = re.compile(r'v-tips[^>]*>(?:<em>)?([^<]*)<', re.I)
_RE_VNUM = re.compile(r'v-num[^>]*>([^<]*)<', re.I)
_RE_SCORE = re.compile(r'(?:em_score|s_score|em-score)">\s*([0-9.]+)\s*(?:<i>分</i>|分)?<', re.I)
_RE_DES = re.compile(r's-des">([^<]*)<', re.I)
_RE_H1 = re.compile(r'<h1[^>]*>([\s\S]*?)</h1>', re.I)
_RE_PLAY_LABEL = re.compile(r'apiname="([^"]*)"[^>]*alt="([^"]*)"', re.I)
_RE_EP_UL = re.compile(r'<ul class="play_num_list[^"]*">([\s\S]*?)</ul>', re.I)
_RE_EP_A = re.compile(r'<a\s+href="(/play/\d+-\d+-\d+\.html)"[^>]*>([^<]*)</a>', re.I)
_RE_STREAM = re.compile(r'"url"\s*:\s*"(https?://[^"\\]*(?:m3u8|mp4)[^"]*)"', re.I)
_RE_PAGE = re.compile(r'/vs/[^"]*/(\d+)\.html')


class Spider(Spider):

    def getName(self):
        return "飞龙影院"

    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}

        self.site_url = (self.extend.get("site") or HOST).rstrip("/")
        self.headers = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": self.site_url + "/",
        }
        self.default_pic = DEFAULT_PIC
        self._play_cache = {}
        self.log("init: site=%s" % self.site_url)

    # ---------------- 基础工具 ----------------
    def _is_upstream_error(self, text):
        if not text:
            return True
        low = text.lower()
        return any(k in low for k in (
            "upstream connect error", "connection timeout", "connection reset",
            "bad gateway", "service unavailable", "reset reason",
            "<title>503", "<title>502", "<title>429"))

    def _reset_session(self):
        """best-effort 关闭复用坏连接的会话，下次请求重建新连接。"""
        try:
            if hasattr(self, "reset_session"):
                self.reset_session()
                return
            sess = getattr(self, "_session", None) or getattr(self, "_sess", None)
            if sess is not None:
                try:
                    sess.close()
                except Exception:
                    pass
            self._session = None
        except Exception:
            pass

    def _fetch(self, url, timeout=15, headers=None):
        def _once():
            h = dict(self.headers)
            if headers:
                h.update(headers)
            rsp = self.fetch(url, headers=h, timeout=timeout)
            if hasattr(rsp, "text"):
                return rsp.text or ""
            if hasattr(rsp, "content"):
                return rsp.content.decode("utf-8", "ignore")
            return str(rsp)

        text = ""
        for attempt in range(3):
            try:
                text = _once()
            except Exception as e:
                self.log("fetch FAIL %s -> %s" % (url, e))
                text = ""
            # 正常页面直接返回；上游 503/超时/坏连接文本则重置会话后重试
            if text and not self._is_upstream_error(text):
                return text
            self._reset_session()
            time.sleep(0.8 * (attempt + 1))
        return text

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
        s = re.sub(r"<br\s*/?>", "\n", str(s), flags=re.I)
        s = re.sub(r"<[^>]+>", "", s)
        s = (s.replace("&nbsp;", " ").replace("\xa0", " ")
              .replace("&amp;", "&").replace("&quot;", '"')
              .replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">"))
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n{2,}", "\n", s)
        return s.strip()

    def _strip_label(self, s):
        """剥离「演员：」「导演：」这类冒号前缀，保留正文。"""
        if not s:
            return ""
        return re.sub(r"^(?:演员|主演|导演|地区|年份|年代|语言|类型|状态)\s*[:：]\s*", "", s).strip()

    def _is_placeholder_pic(self, pic):
        if not pic:
            return True
        low = pic.lower()
        for bad in ("placeholder", "default", "blank", "loading", "none.gif",
                    "empty.png", "data:image/gif"):
            if bad in low:
                return True
        return False

    # ---------------- 列表卡片解析（兼容 v-pic 与搜索 item 两种结构）----------------
    def _parse_cards(self, html):
        videos = []
        seen = set()
        if not html:
            return videos

        # 收集所有详情链接及其位置
        hits = []
        for m in _RE_DETAIL.finditer(html):
            href, vid, title = m.group(1), m.group(2), m.group(3)
            if vid in seen:
                continue
            seen.add(vid)
            hits.append((m.start(), href, vid, title))

        for pos, href, vid, title in hits:
            block = html[max(0, pos - 480):pos + 480]

            if not title:
                mt = _RE_TITLE_A.search(block)
                if mt:
                    title = mt.group(1)
                else:
                    ms = _RE_STRONG.search(block)
                    title = ms.group(1) if ms else ""
            title = self._clean(title)

            mp = _RE_IMG.search(block)
            pic = self._fix_url(mp.group(1)) if mp else self.default_pic
            if self._is_placeholder_pic(pic):
                pic = self.default_pic

            mtip = _RE_TIPS.search(block) or _RE_VNUM.search(block)
            remarks = self._clean(mtip.group(1)) if mtip else ""

            msc = _RE_SCORE.search(block)
            score = msc.group(1) if msc else ""

            mdes = _RE_DES.search(block)
            subtitle = self._clean(mdes.group(1)) if mdes else ""
            subtitle = self._strip_label(subtitle)

            if not title:
                continue
            videos.append({
                "vod_id": href,
                "vod_name": title[:100],
                "vod_pic": pic,
                "vod_remarks": remarks or (("%s分" % score) if score else ""),
                "vod_subtitle": subtitle,
            })
        return videos

    def _page_count(self, html):
        if not html:
            return 1
        pages = [int(x) for x in _RE_PAGE.findall(html)]
        if pages:
            return max(1, max(pages))
        return 1

    # ---------------- 首页 / 分类 / 搜索 ----------------
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        html = self._fetch(self.site_url + "/")
        videos = self._parse_cards(html)
        self.log("home: %d 条" % len(videos))
        return {"list": videos}

    def categoryContent(self, tid, pg, filter, extend):
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

        genre = extend.get("genre") or "all"
        area = extend.get("area") or "all"
        year = extend.get("year") or "all"
        # 站点 /vs/<tid>/<题材>/<地区>/<语言=all>/<年份>/<排序=all>/<页码>.html
        seg = [str(tid), genre, area, "all", year, "all", str(page)]
        url = self.site_url + "/vs/" + "/".join(
            urllib.parse.quote(x, safe="") for x in seg) + ".html"
        self.log("category: %s" % url)

        html = self._fetch(url)
        videos = self._parse_cards(html)
        pagecount = self._page_count(html)
        self.log("  最终: %d 条, 总页数 %d" % (len(videos), pagecount))
        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 30, "total": pagecount * 30,
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        keyword = urllib.parse.quote(str(key or "").strip())
        url = "%s/search.html?wd=%s&page=%d" % (self.site_url, keyword, page)
        self.log("search: %s" % url)
        html = self._fetch(url)
        videos = self._parse_cards(html)
        self.log("  搜索结果: %d 条" % len(videos))
        return {
            "list": videos, "page": page,
            "pagecount": self._page_count(html) or 1,
            "limit": 30, "total": len(videos),
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------------- 详情字段提取 ----------------
    def _field(self, html, label):
        m = re.search(r'<em class="em_tit">%s：</em>([\s\S]*?)(?=<em class="em_tit">|</li>)'
                      % re.escape(label), html, re.I)
        if not m:
            return ""
        return self._clean(m.group(1))

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0])
        url = vod_id if vod_id.startswith("http") else self._fix_url(vod_id)
        self.log("detail: %s" % url)

        html = self._fetch(url)
        if not html:
            return {"list": []}

        # 片名：第二个 h1（首个 h1 为站点 logo）
        name = ""
        h1s = _RE_H1.findall(html)
        if len(h1s) >= 2:
            name = self._clean(h1s[1])
        elif h1s:
            name = self._clean(h1s[0])
        if not name:
            mt = re.search(r"<title>(.*?)</title>", html, re.S)
            if mt:
                name = self._clean(mt.group(1).split("_")[0].split("-")[0])
        name = name or vod_id

        # 海报（详情主海报）
        pic = self.default_pic
        mp = re.search(r'<div class="v-pic">\s*<img[^>]*data-original="([^"]*)"', html, re.I)
        if not mp:
            mp = _RE_IMG.search(html)
        if mp:
            pic = self._fix_url(mp.group(1))
            if self._is_placeholder_pic(pic):
                pic = self.default_pic

        # 状态（更新第35集 / 完结 / 完整版…），剥离站点「状态：」前缀
        remarks = ""
        mnum = re.search(r'<em class="em_num">([^<]*)</em>', html, re.I)
        if mnum:
            remarks = self._clean(mnum.group(1))
            remarks = re.sub(r"^状态[:：]\s*", "", remarks)

        # 评分
        score = ""
        msc = _RE_SCORE.search(html)
        if msc:
            score = msc.group(1)

        # 元信息（站点标签：主演/导演/地区/年份/语言/类型；搜索页用「年代」兼容「年份」）
        actor = self._field(html, "主演")
        director = self._field(html, "导演")
        area = self._field(html, "地区")
        year = self._field(html, "年份") or self._field(html, "年代")
        lang = self._field(html, "语言")
        classify = self._field(html, "类型")

        # 简介
        content = ""
        mint = re.search(r'<em class="em_tit">简介：</em>([\s\S]*?)</li>', html, re.I)
        if mint:
            content = self._clean(mint.group(1))
        if not content:
            mdesc = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', html, re.I)
            if mdesc:
                content = self._clean(mdesc.group(1))
        content = (INTRO_PREFIX + "\n" + content) if content else INTRO_PREFIX

        # ===== 线路标签（顺序即线路号）=====
        labels = [(m.group(1), self._clean(m.group(2))) for m in _RE_PLAY_LABEL.finditer(html)]
        # ===== 选集分组（ul 顺序与线路标签一一对应）=====
        uls = _RE_EP_UL.findall(html)

        play_from, play_url = [], []
        # 以线路标签为基准；标签缺省时用选集 ul 兜底
        if labels:
            for idx, (apiname, alt) in enumerate(labels):
                group_name = alt or apiname
                if idx < len(uls):
                    eps = _RE_EP_A.findall(uls[idx])
                else:
                    eps = []
                if not eps:
                    continue
                lines = []
                for ep_href, ep_name in eps:
                    ep_name = self._clean(ep_name) or "第%d集" % (len(lines) + 1)
                    lines.append("%s$%s" % (ep_name, ep_href))
                if lines:
                    # 线路名去重
                    base, i = group_name, 2
                    while group_name in play_from:
                        group_name = "%s(%d)" % (base, i)
                        i += 1
                    play_from.append(group_name)
                    play_url.append("#".join(lines))
        else:
            for idx, ul in enumerate(uls):
                eps = _RE_EP_A.findall(ul)
                if not eps:
                    continue
                lines = []
                for ep_href, ep_name in eps:
                    ep_name = self._clean(ep_name) or "第%d集" % (len(lines) + 1)
                    lines.append("%s$%s" % (ep_name, ep_href))
                if lines:
                    play_from.append("线路%d" % (idx + 1))
                    play_url.append("#".join(lines))

        if not play_from:
            self.log("  未解析到选集")
            return {"list": []}

        vod = {
            "vod_id": vod_id,
            "vod_name": name[:100],
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_score": score,
            "vod_remarks": remarks or ("%d条线路" % len(play_from)),
            "vod_area": area,
            "vod_year": year,
            "vod_lang": lang,
            "vod_classify": classify,
            "type_name": classify,
            "vod_alias": "",
            "vod_update": remarks,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }
        return {"list": [vod]}

    # ---------------- 播放 ----------------
    def _extract_stream(self, html):
        """从播放页内嵌 JSON 提取直链 m3u8/mp4；站点自身域名不算直链。"""
        if not html:
            return ""
        # 反转义 \/ 与 unicode
        text = html.replace("\\/", "/")
        m = _RE_STREAM.search(text)
        if not m:
            return ""
        url = m.group(1)
        # 排除站点自身占位地址
        if "feilongyy.com" in url or "www.feilong" in url:
            return ""
        return url

    def playerContent(self, flag, id, vipFlags):
        play_page = id if str(id).startswith("http") else self._fix_url(id)
        self.log("player: %s" % play_page)

        now = int(time.time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 600:
                return res

        header = {"User-Agent": UA, "Referer": self.site_url + "/"}

        # 传入的本身已是 m3u8/mp4 裸直链，直接放行
        if _RE_STREAM.search(play_page):
            res = {"parse": 0, "playUrl": "", "url": play_page, "header": header}
            self._play_cache[play_page] = (now, res)
            return res

        stream = ""
        if play_page.startswith(self.site_url + "/play/"):
            html = self._fetch(play_page)
            stream = self._extract_stream(html)

        if stream:
            res = {"parse": 0, "playUrl": "", "url": stream, "header": header}
            self._play_cache[play_page] = (now, res)
            self.log("  => 直链 parse=0 %s" % stream[:140])
            return res

        # 兜底：交客户端嗅探播放页
        res = {"parse": 1, "playUrl": "", "url": play_page, "header": header}
        self._play_cache[play_page] = (now, res)
        self.log("  => 嗅探兜底 parse=1 %s" % play_page[:120])
        return res

    # ---------------- 其他契约方法 ----------------
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
