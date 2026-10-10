# coding=utf-8
import re
import sys
import json
import time
import urllib.parse

sys.path.append('..')

try:
    from base.spider import Spider
except ImportError:
    import requests

    class _BaseSpider:
        def __init__(self):
            self._session = None

        @property
        def _sess(self):
            if self._session is None:
                self._session = requests.Session()
                self._session.verify = False
            return self._session

        def fetch(self, url, headers=None, **kw):
            timeout = kw.pop('timeout', 15)
            r = self._sess.get(url, headers=headers, timeout=timeout, **kw)
            r.encoding = 'utf-8'
            return r

        def log(self, *a, **kw):
            print("[66ys]", *a)

    Spider = _BaseSpider


HOST = "https://www.xaxhj.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = ""

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

CLASSES = [
    {"type_id": "1", "type_name": "电影"},
    {"type_id": "2", "type_name": "电视剧"},
    {"type_id": "3", "type_name": "综艺"},
    {"type_id": "4", "type_name": "动漫"},
    {"type_id": "26", "type_name": "短剧"},
]

# ---------- 筛选选项 ----------
_YEARS = [{"n": "全部", "v": ""}] + \
         [{"n": str(y), "v": str(y)} for y in range(2021, 2009, -1)]

_ORDERS = [
    {"n": "时间", "v": "time"},
    {"n": "人气", "v": "hits"},
    {"n": "评分", "v": "score"},
]

_LANGS = [
    {"n": "全部", "v": ""},
    {"n": "国语", "v": "国语"},
    {"n": "英语", "v": "英语"},
    {"n": "粤语", "v": "粤语"},
    {"n": "闽南语", "v": "闽南语"},
    {"n": "韩语", "v": "韩语"},
    {"n": "日语", "v": "日语"},
    {"n": "法语", "v": "法语"},
    {"n": "德语", "v": "德语"},
    {"n": "其它", "v": "其它"},
]

_AREAS_MOVIE = [
    {"n": "全部", "v": ""},
    {"n": "大陆", "v": "大陆"},
    {"n": "香港", "v": "香港"},
    {"n": "台湾", "v": "台湾"},
    {"n": "美国", "v": "美国"},
    {"n": "法国", "v": "法国"},
    {"n": "英国", "v": "英国"},
    {"n": "日本", "v": "日本"},
    {"n": "韩国", "v": "韩国"},
    {"n": "德国", "v": "德国"},
    {"n": "泰国", "v": "泰国"},
    {"n": "印度", "v": "印度"},
    {"n": "意大利", "v": "意大利"},
    {"n": "西班牙", "v": "西班牙"},
    {"n": "加拿大", "v": "加拿大"},
    {"n": "其他", "v": "其他"},
]

_AREAS_TV = [
    {"n": "全部", "v": ""},
    {"n": "内地", "v": "内地"},
    {"n": "韩国", "v": "韩国"},
    {"n": "香港", "v": "香港"},
    {"n": "台湾", "v": "台湾"},
    {"n": "日本", "v": "日本"},
    {"n": "美国", "v": "美国"},
    {"n": "泰国", "v": "泰国"},
    {"n": "英国", "v": "英国"},
    {"n": "新加坡", "v": "新加坡"},
    {"n": "其他", "v": "其他"},
]

_AREAS_VARIETY = [
    {"n": "全部", "v": ""},
    {"n": "内地", "v": "内地"},
    {"n": "港台", "v": "港台"},
    {"n": "日韩", "v": "日韩"},
    {"n": "欧美", "v": "欧美"},
]

_AREAS_ANIME = [
    {"n": "全部", "v": ""},
    {"n": "国产", "v": "国产"},
    {"n": "日本", "v": "日本"},
    {"n": "欧美", "v": "欧美"},
    {"n": "其他", "v": "其他"},
]

_CLASS_MOVIE = [
    {"n": "全部", "v": ""},
    {"n": "动作片", "v": "6"},
    {"n": "喜剧片", "v": "7"},
    {"n": "爱情片", "v": "8"},
    {"n": "科幻片", "v": "9"},
    {"n": "恐怖片", "v": "10"},
    {"n": "剧情片", "v": "11"},
    {"n": "战争片", "v": "12"},
    {"n": "纪录片", "v": "24"},
]

_CLASS_TV = [
    {"n": "全部", "v": ""},
    {"n": "美剧", "v": "20"},
    {"n": "韩剧", "v": "13"},
    {"n": "日剧", "v": "14"},
    {"n": "泰剧", "v": "15"},
    {"n": "港剧", "v": "16"},
    {"n": "国产剧", "v": "25"},
]


def _make_filters(areas, subclass=None):
    f = []
    if subclass:
        f.append({"key": "class", "name": "类型", "value": subclass})
    f.append({"key": "area", "name": "地区", "value": areas})
    f.append({"key": "year", "name": "年份", "value": _YEARS})
    f.append({"key": "lang", "name": "语言", "value": _LANGS})
    f.append({"key": "order", "name": "排序", "value": _ORDERS})
    return f


FILTERS = {
    "1": _make_filters(_AREAS_MOVIE, _CLASS_MOVIE),
    "2": _make_filters(_AREAS_TV, _CLASS_TV),
    "3": _make_filters(_AREAS_VARIETY),
    "4": _make_filters(_AREAS_ANIME),
    # 短剧 26 没有筛选
}


class Spider(Spider):

    def getName(self):
        return "66影视"

    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}

        self.site_url = (self.extend.get("site") or HOST).rstrip("/")
        self.headers = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.site_url + "/",
        }
        self.log("init: site=%s" % self.site_url)

    def _fetch(self, url, timeout=15, headers=None):
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
              .replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">"))
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n{2,}", "\n", s)
        return s.strip()

    def _parse_list(self, html):
        videos = []
        if not html:
            return videos

        pattern = re.compile(
            r'<a[^>]*class="[^"]*stui-vodlist__thumb[^"]*"[^>]*'
            r'href="([^"]+)"[^>]*'
            r'title="([^"]*)"[^>]*'
            r'data-original="([^"]+)"[^>]*>'
            r'.*?'
            r'<span[^>]*class="[^"]*pic-text[^"]*"[^>]*><b>([^<]*)</b>',
            re.S | re.I
        )
        for m in pattern.finditer(html):
            videos.append({
                "vod_id": m.group(1),
                "vod_name": self._clean(m.group(2)),
                "vod_pic": self._fix_url(m.group(3)) or DEFAULT_PIC,
                "vod_remarks": self._clean(m.group(4)),
            })

        if not videos:
            pattern2 = re.compile(
                r'<a[^>]*href="(/product/[^"]+)"[^>]*title="([^"]*)"',
                re.I
            )
            for m in pattern2.finditer(html):
                videos.append({
                    "vod_id": m.group(1),
                    "vod_name": self._clean(m.group(2)),
                    "vod_pic": DEFAULT_PIC,
                    "vod_remarks": "",
                })
        return videos

    def _page_count(self, html):
        if not html:
            return 1
        m = re.search(r'<a[^>]*href="([^"]+)"[^>]*>尾页</a>', html, re.I)
        if m:
            nums = re.findall(r'(\d+)', m.group(1))
            if nums:
                try:
                    return int(nums[-1])
                except Exception:
                    pass
        m = re.search(r'(\d+)/(\d+)', html)
        if m:
            try:
                return int(m.group(2))
            except Exception:
                pass
        return 9999

    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        html = self._fetch(self.site_url + "/")
        return {"list": self._parse_list(html)}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        if extend is None:
            extend = {}
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}

        if extend.get("class"):
            tid = extend["class"]

        f1 = str(tid)
        f2 = extend.get("area", "") or ""
        f3 = extend.get("order", "") or ""
        f4 = ""
        f5 = extend.get("lang", "") or ""
        f6 = ""
        f7 = ""
        f8 = ""
        f9 = str(page)
        f10 = ""
        f11 = ""
        f12 = extend.get("year", "") or ""

        has_filter = bool(f2 or f3 or f5 or f12)

        if not has_filter:
            if page == 1:
                url = "%s/list/%s.html" % (self.site_url, tid)
            else:
                url = "%s/list/%s-%d.html" % (self.site_url, tid, page)
        else:
            path = "-".join([f1, f2, f3, f4, f5, f6, f7, f8, f9, f10, f11, f12])
            url = "%s/vodshow/%s.html" % (self.site_url, path)

        self.log("category: %s" % url)
        html = self._fetch(url)
        videos = self._parse_list(html)
        pagecount = self._page_count(html)

        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": 24,
            "total": pagecount * 24,
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        keyword = urllib.parse.quote(key)
        url = "%s/vodsearch/%s-------------.html" % (self.site_url, keyword)
        self.log("search: %s" % url)
        html = self._fetch(url)
        videos = self._parse_list(html)

        return {
            "list": videos,
            "page": page,
            "pagecount": self._page_count(html),
            "limit": 24,
            "total": 999,
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    def detailContent(self, ids):
        if not ids:
            return {"list": []}

        vod_id = str(ids[0])
        url = self._fix_url(vod_id)
        self.log("detail: %s" % url)
        html = self._fetch(url)
        if not html:
            return {"list": []}

        # ---------- 标题 ----------
        name = ""
        m = re.search(r'<h1[^>]*class="title"[^>]*>([\s\S]*?)</h1>', html, re.I)
        if m:
            name = self._clean(m.group(1))
        if not name:
            m = re.search(r'<title>(.*?)</title>', html, re.S | re.I)
            if m:
                name = self._clean(m.group(1).split("_")[0].split("-")[0])
        name = re.sub(r"\s*\(\d{4}\)\s*$", "", name).strip() or vod_id

        # ---------- 封面 ----------
        pic = DEFAULT_PIC
        m = re.search(
            r'<img[^>]*class="[^"]*lazyload[^"]*"[^>]*data-original="([^"]+)"',
            html, re.I
        )
        if not m:
            m = re.search(r'<img[^>]*data-original="([^"]+)"', html, re.I)
        if m:
            pic = self._fix_url(m.group(1))

        # ---------- 年份 ----------
        vod_year = ""
        m = re.search(r'年份：<a[^>]*>(\d{4})</a>', html, re.I)
        if not m:
            m = re.search(r'年份：\s*(\d{4})', html, re.I)
        if m:
            vod_year = m.group(1)

        # ---------- 地区 ----------
        vod_area = ""
        m = re.search(r'地区：\s*([^ /<\n]+)', html, re.I)
        if m:
            vod_area = self._clean(m.group(1))

        # ---------- 语言 ----------
        vod_lang = ""
        m = re.search(r'语言：\s*([^<\n]+)', html, re.I)
        if m:
            vod_lang = self._clean(m.group(1))

        # ---------- 状态 ----------
        vod_remarks = ""
        m = re.search(r'状态：\s*<span[^>]*>([^<]+)</span>', html, re.I)
        if m:
            vod_remarks = self._clean(m.group(1))
        if not vod_remarks:
            m = re.search(r'状态：\s*([^<\n]+)', html, re.I)
            if m:
                vod_remarks = self._clean(m.group(1))

        # ---------- 更新日期 ----------
        m = re.search(r'更新：\s*([\d\-]+)', html, re.I)
        if m:
            update_date = self._clean(m.group(1))
            if vod_remarks:
                vod_remarks = vod_remarks + " " + update_date
            else:
                vod_remarks = update_date

        # ---------- 简介 ----------
        content = ""
        m = re.search(
            r'<span[^>]*class="[^"]*detail-content[^"]*"[^>]*>([\s\S]*?)</span>',
            html, re.I
        )
        if m:
            content = self._clean(m.group(1))

        if not content:
            m = re.search(
                r'<span[^>]*class="[^"]*detail-sketch[^"]*"[^>]*>([\s\S]*?)</span>',
                html, re.I
            )
            if m:
                content = self._clean(m.group(1))

        if not content:
            m = re.search(
                r'<meta[^>]*name="description"[^>]*content="([^"]*)"',
                html, re.I
            )
            if m:
                content = self._clean(m.group(1))

        if content:
            content = INTRO_PREFIX + "\n" + content
        else:
            content = INTRO_PREFIX

        # ---------- 主演 ----------
        actor = ""
        m = re.search(r'<p[^>]*class="data"[^>]*>主演：([\s\S]*?)</p>', html, re.I)
        if m:
            actors = re.findall(r'<a[^>]*>([^<]+)</a>', m.group(1))
            actor = ", ".join(self._clean(a) for a in actors)

        # ---------- 导演 ----------
        director = ""
        m = re.search(r'<p[^>]*class="data"[^>]*>导演：([\s\S]*?)</p>', html, re.I)
        if m:
            directors = re.findall(r'<a[^>]*>([^<]+)</a>', m.group(1))
            director = ", ".join(self._clean(d) for d in directors)

        # ---------- 剧集 ----------
        # 1) 先按页面 tab 顺序记录线路顺序
        line_order = {}
        line_names = {}
        order_idx = 0
        for m in re.finditer(r'<a href="#playlist(\d+)"[^>]*>([^<]+)</a>', html, re.I):
            sid = m.group(1)
            if sid not in line_order:
                line_order[sid] = order_idx
                order_idx += 1
            line_names[sid] = self._clean(m.group(2))

        # 2) 提取剧集
        episodes = {}
        for m in re.finditer(
            r'href="(/html/(\d+)-(\d+)-(\d+)\.html)"[^>]*>([^<]*)</a>',
            html, re.I
        ):
            url_path = m.group(1)
            sid = m.group(3)
            nid = int(m.group(4))
            ep_name = self._clean(m.group(5)) or ("第%d集" % nid)
            full_url = self.site_url + url_path
            episodes.setdefault(sid, []).append((nid, ep_name, full_url))

        if not episodes:
            return {"list": []}

        # 3) 按 tab 顺序排序（不在 tab 里的线路排最后）
        sorted_sids = sorted(
            episodes.keys(),
            key=lambda x: line_order.get(x, 9999)
        )

        play_from = []
        play_url = []
        for sid in sorted_sids:
            eps = sorted(episodes[sid], key=lambda x: x[0])
            play_from.append(line_names.get(sid, "线路%s" % sid))
            play_url.append("#".join("%s$%s" % (n, u) for _, n, u in eps))

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_year": vod_year,
            "vod_area": vod_area,
            "vod_lang": vod_lang,
            "vod_remarks": vod_remarks,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }]}

    def playerContent(self, flag, id, vipFlags):
        play_page = self._fix_url(id)
        self.log("player: %s" % play_page)
        html = self._fetch(play_page)
        if not html:
            return {"parse": 1, "playUrl": "", "url": play_page, "header": {}}

        m = re.search(r'var\s+player_aaaa\s*=\s*(\{.*?\})\s*</script>', html, re.S)
        if not m:
            m = re.search(r'var\s+player_aaaa\s*=\s*(\{.*?\})', html, re.S)

        if m:
            try:
                data = json.loads(m.group(1))
                url = data.get("url", "")
                if url:
                    url = url.replace("\\/", "/")
                    if url.startswith("//"):
                        url = "https:" + url
                    elif url.startswith("/"):
                        url = self.site_url + url
                    self.log("player url: %s" % url[:200])
                    return {
                        "parse": 0,
                        "playUrl": "",
                        "url": url,
                        "header": {
                            "User-Agent": UA,
                            "Referer": self.site_url + "/",
                        },
                    }
            except Exception as e:
                self.log("player_aaaa parse fail: %s" % e)

        m = re.search(r'<iframe[^>]*src="([^"]+)"', html, re.I)
        if m:
            url = self._fix_url(m.group(1))
            return {
                "parse": 1,
                "playUrl": "",
                "url": url,
                "header": {"User-Agent": UA, "Referer": self.site_url + "/"},
            }

        return {
            "parse": 1,
            "playUrl": "",
            "url": play_page,
            "header": {"User-Agent": UA, "Referer": self.site_url + "/"},
        }

    def localProxy(self, param):
        return [200, "text/plain", b"", ""]

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()
