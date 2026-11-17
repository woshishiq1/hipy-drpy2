# coding=utf-8
"""
洛雪TV · 影视推荐  tv.lxyy.club | TVBox Python 爬虫
站点结构:
  - 首页/目录: TMDB 代理 /api/tmdb.php?path=<endpoint>&api_key=&language=zh-CN&page=<n>
      · 推荐  trending/all/day
      · 电影  discover/movie
      · 剧集  discover/tv
      · 动漫  discover/tv?with_genres=16
      · 综艺/短剧  /api/quark-ranking.php?channel=<综艺|短剧>&limit=60
  - 采集搜索: GET /api/proxy.php?action=search&wd=<片名>&page=1
      返回 {success, total, sources:{源id:源名}, results:[{source,id,name,pic,remarks,type,year,area}]}
  - 播放详情: GET /api/proxy.php?action=detail&source=<源id>&id=<源内部id>
      返回 {success, details:[{actor,area,content,director,episodes,lang,name,pic,
                              play_url,player_api,remarks,source,source_name,type,year}]}
      episodes 为多线路分组: [{group, episodes:[{name,url}]}]
  - 播放链路:
      · 集地址本身是 .m3u8/.mp4 直链 -> parse:0 直放
      · 集地址是第三方平台页面   -> 用该源 player_api 拼接成解析页 -> parse:1 iframe
简介统一加锁定前缀（逐字不可改）。
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
                print("[luoxue]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://tv.lxyy.club"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = ""
IMAGE_BASE = "https://image.tmdb.org/t/p/w342"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# ===================== 分类（对齐站点侧边栏/目录页签）=====================
CLASSES = [
    {"type_id": "recommend", "type_name": "推荐"},
    {"type_id": "movie",    "type_name": "电影"},
    {"type_id": "series",   "type_name": "剧集"},
    {"type_id": "anime",    "type_name": "动漫"},
    {"type_id": "variety",  "type_name": "综艺"},
    {"type_id": "short",    "type_name": "短剧"},
]

# 采集源优先级与源名（站点 source_order / sources 配置）
SOURCE_ORDER = ["qilin", "mj", "jl", "360zy", "dytt", "ik", "md", "fy"]
SOURCE_NAMES = {
    "qilin": "官采蓝光", "mj": "4k60帧🔥", "jl": "自营🔥", "360zy": "360资源",
    "dytt": "电影天堂", "ik": "ikun", "md": "魔都", "fy": "官方源",
}
SOURCE_PARSER = {
    "qilin": "https://svip.qlplayer.cyou/?url=",
    "mj": "https://mujizybf.com/m3u8/?url=",
    "jl": "https://jimaoys99.com/parse?url=",
    "360zy": "https://jimaoys99.com/parse?url=",
    "dytt": "https://jimaoys99.com/parse?url=",
    "ik": "https://jimaoys99.com/parse?url=",
    "md": "https://jimaoys99.com/parse?url=",
    "fy": "https://svip.qlplayer.cyou/?url=",
}
DEFAULT_PARSER = "https://svip.qlplayer.cyou/?url="

# 站点公开 iframe 备用解析（对齐 official_routes 中 type=iframe、official_only=false 的线路，
# 顺序与网页"解析线路"区一致）；type=json 的鉴权路由无会话 403，不在此列。
PUBLIC_IFRAME_PARSERS = [
    {"name": "默认解析", "api": "https://svip.qlplayer.cyou/?url="},
    {"name": "无名",     "api": "https://jx.wmxz.online/?url="},
    {"name": "闪电",     "api": "https://bfq.txnp.cn/excessive?url="},
    # m1907 站点配置 hide_mobile=true（手机端隐藏），TVBox 爬虫不分端，予以保留
    {"name": "m1907",   "api": "https://im1907.top/?jx="},
    {"name": "洛雪聚合", "api": "https://jx.lxyy.club/index.php?url="},
]

# 筛选：排序
SORTS = [
    {"n": "热度最高", "v": "popularity.desc"},
    {"n": "时间最新", "v": "time"},
    {"n": "评分最高", "v": "vote_average.desc"},
]

# 筛选：地区（TMDB origin_country 代码）
AREAS = [
    {"n": "全部", "v": ""}, {"n": "中国大陆", "v": "CN"}, {"n": "美国", "v": "US"},
    {"n": "日本", "v": "JP"}, {"n": "韩国", "v": "KR"}, {"n": "中国香港", "v": "HK"},
    {"n": "中国台湾", "v": "TW"}, {"n": "英国", "v": "GB"}, {"n": "法国", "v": "FR"},
    {"n": "泰国", "v": "TH"}, {"n": "印度", "v": "IN"}, {"n": "德国", "v": "DE"},
]

# 筛选：年份
YEARS = [{"n": "全部", "v": ""}] + [
    {"n": str(y), "v": str(y)} for y in range(2026, 2014, -1)]

# 筛选：类型（TMDB 题材 id）
MOVIE_GENRES = [
    ("全部", ""), ("剧情", "18"), ("喜剧", "35"), ("动作", "28"), ("爱情", "10749"),
    ("悬疑", "9648"), ("科幻", "878"), ("恐怖", "27"), ("惊悚", "53"), ("冒险", "12"),
    ("奇幻", "14"), ("犯罪", "80"), ("历史", "36"), ("战争", "10752"),
    ("动画", "16"), ("纪录片", "99"),
]
SERIES_GENRES = [
    ("全部", ""), ("剧情", "18"), ("喜剧", "35"), ("动作冒险", "10759"), ("犯罪", "80"),
    ("悬疑", "9648"), ("科幻奇幻", "10765"), ("动画", "16"), ("纪录片", "99"),
]

FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    flt = [
        {"key": "area", "name": "地区", "value": AREAS},
        {"key": "year", "name": "年份", "value": YEARS},
        {"key": "sort", "name": "排序", "value": SORTS},
    ]
    if tid == "movie":
        flt.insert(0, {"key": "genre", "name": "类型",
                       "value": [{"n": n, "v": v} for n, v in MOVIE_GENRES]})
    elif tid in ("series", "anime"):
        flt.insert(0, {"key": "genre", "name": "类型",
                       "value": [{"n": n, "v": v} for n, v in SERIES_GENRES]})
    FILTERS[tid] = flt

# 夸克榜单频道映射（综艺/短剧走夸克榜单）
QUARK_CHANNEL = {"variety": "综艺", "short": "短剧"}

# 官方采集源与官方平台线路展示顺序（对齐 config.official_source / official_platform_order，
# playback-defaults.js lineOrder：仅官方源按此顺序重排平台组，其余源保持接口原序）
OFFICIAL_SOURCE = "qilin"
OFFICIAL_PLATFORM_ORDER = ["qq", "bilibili", "mgtv", "qiyi", "youku"]

_RE_DIRECT = re.compile(r"\.(?:m3u8|mp4)(?:[?#]|$)", re.I)
# 组名（平台/线路代号）友好别名，对齐站点 lineLabel 映射
GROUP_ALIAS = {
    "mjzy": "lx", "jlplayer": "lx", "bilibili": "B站", "b站": "B站",
    "qq": "腾讯视频", "腾讯": "腾讯视频", "qiyi": "爱奇艺", "爱奇艺": "爱奇艺",
    "youku": "优酷", "优酷": "优酷", "mgtv": "芒果", "芒果": "芒果",
}
# 纯编码后缀类组名（m3u8/hls/mp4）站点不显示代号，归入默认线路
_RE_CODEC_GROUP = re.compile(r"^[a-z0-9_.-]*(?:m3u8|hls|mp4)[a-z0-9_.-]*$", re.I)

# TMDB 地区代码 -> 中文
AREA_CN = {
    "CN": "中国大陆", "US": "美国", "JP": "日本", "KR": "韩国", "HK": "中国香港",
    "TW": "中国台湾", "GB": "英国", "FR": "法国", "TH": "泰国", "IN": "印度",
    "DE": "德国", "CA": "加拿大", "AU": "澳大利亚", "SG": "新加坡", "RU": "俄罗斯",
    "IT": "意大利", "ES": "西班牙", "MY": "马来西亚", "PH": "菲律宾", "ID": "印度尼西亚",
}


def _fmt_score(v):
    try:
        f = float(v)
        if f <= 0:
            return ""
        return ("%.1f" % f).rstrip("0").rstrip(".")
    except Exception:
        return str(v or "")


class Spider(Spider):

    def getName(self):
        return "洛雪TV"

    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}

        self.site_url = (self.extend.get("site") or HOST).rstrip("/")
        self.headers = {
            "User-Agent": UA,
            "Accept": "application/json,text/html,application/xhtml+xml,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": self.site_url + "/",
        }
        self.default_pic = DEFAULT_PIC
        self._play_cache = {}
        self._parser_map = {}
        self.log("init: site=%s" % self.site_url)

    # ---------------- 基础工具 ----------------
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

    def _get_json(self, url, timeout=15):
        text = self._fetch(url, timeout=timeout)
        if not text:
            return {}
        try:
            return json.loads(text)
        except Exception:
            # 个别榜单接口字符串内夹带未转义字符，做一次宽松剥离后重试
            try:
                return json.loads(text.encode("utf-8", "ignore").decode("utf-8"))
            except Exception:
                return {}

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

    def _is_placeholder_pic(self, pic):
        if not pic:
            return True
        low = pic.lower()
        for bad in ("placeholder", "default", "blank", "loading", "none.gif",
                    "empty.png", "data:image/gif"):
            if bad in low:
                return True
        return False

    # ---------------- 片名匹配（对齐站点 titleScore / normalizeTitle）----------------
    def _normalize_title(self, v):
        s = re.sub(r"[\s\u3000]+", "", str(v or "").lower())
        s = re.sub(r"[·•・:：,，.。!！?？'‘’\"“”()（）\[\]【】{}<>《》\-_/\\]", "", s)
        s = re.sub(r"(?:第?[一二三四五六七八九十百0-9]+季|season[0-9]+)", "", s, flags=re.I)
        s = re.sub(r"(?:20\d{2}|19\d{2})$", "", s)
        return s

    def _title_score(self, name, wanted):
        a, b = self._normalize_title(name), self._normalize_title(wanted)
        if not a or not b:
            return 99
        if a == b:
            return 0
        if a.startswith(b) or b.startswith(a):
            return 1
        if (b in a or a in b) and min(len(a), len(b)) >= 3:
            return 2
        return 99

    def _group_label(self, raw):
        raw = self._clean(raw)
        if not raw:
            return ""
        if _RE_CODEC_GROUP.match(raw):
            return ""
        key = re.sub(r"[\s_-]+", "", raw.lower())
        return GROUP_ALIAS.get(key, raw)

    # ---------------- 数据源请求 ----------------
    def _tmdb_get(self, endpoint, params=None, page=1):
        q = {"api_key": "", "language": "zh-CN", "page": page}
        if params:
            q.update(params)
        url = (self.site_url + "/api/tmdb.php?path=" +
               urllib.parse.quote(endpoint, safe="") + "&" + urllib.parse.urlencode(q))
        self.log("tmdb: %s" % url[:160])
        data = self._get_json(url, timeout=20)
        # 上游偶发超时/空响应，重试一次（列表端点看 results，详情端点看整体非空）
        if not isinstance(data, dict) or not data or not data.get("results"):
            data = self._get_json(url, timeout=20)
        return data if isinstance(data, dict) else {}

    def _proxy_search(self, keyword, page=1):
        if not keyword:
            return {"results": [], "sources": {}}
        q = {"action": "search", "wd": keyword, "page": str(page)}
        url = self.site_url + "/api/proxy.php?" + urllib.parse.urlencode(q)
        self.log("proxy search: %s" % url[:160])
        data = self._get_json(url)
        if not isinstance(data, dict) or not data.get("success"):
            return {"results": [], "sources": {}}
        return data

    def _proxy_detail(self, source, sid):
        if not source or sid in (None, ""):
            return {}
        q = {"action": "detail", "source": str(source), "id": str(sid)}
        url = self.site_url + "/api/proxy.php?" + urllib.parse.urlencode(q)
        self.log("proxy detail: %s" % url[:160])
        data = self._get_json(url, timeout=20)
        if not isinstance(data, dict) or not data.get("success"):
            return {}
        details = data.get("details") or []
        return details[0] if details else {}

    def _quark_ranking(self, channel, limit=60):
        q = {"channel": channel, "limit": str(limit)}
        url = self.site_url + "/api/quark-ranking.php?" + urllib.parse.urlencode(q)
        text = self._fetch(url)
        data = {}
        try:
            data = json.loads(text)
        except Exception:
            data = {"items": self._quark_fallback_items(text)}
        items = data.get("items") or [] if isinstance(data, dict) else []
        return [x for x in items if isinstance(x, dict)]

    def _quark_fallback_items(self, text):
        """宽松兜底：主 JSON 解析失败时，按字段正则抽取榜单条目。"""
        if not text:
            return []
        blocks = re.findall(r'\{[^{}]*"title"\s*:\s*"[^"]+"[^{}]*\}', text)
        out = []
        for blk in blocks:
            def field(name):
                m = re.search(r'"%s"\s*:\s*"([^"]*)"' % name, blk)
                return m.group(1) if m else ""
            out.append({
                "title": field("title"), "src": field("src"),
                "year": field("year"), "area": field("area"),
                "score": field("score"), "category": field("category"),
                "actors": field("actors"), "desc": field("desc"),
                "episodes": field("episodes"), "channel": "",
                "ranking": len(out) + 1,
            })
        return out

    # ---------------- 卡片归一化 ----------------
    def _tmdb_card(self, item, default_media=""):
        media = item.get("media_type") or default_media or "movie"
        name = self._clean(item.get("title") or item.get("name") or "")
        if not name:
            return None
        poster = item.get("poster_path") or ""
        pic = (IMAGE_BASE + poster) if poster else self.default_pic
        date = item.get("release_date") or item.get("first_air_date") or ""
        year = (date or "")[:4]
        vote = _fmt_score(item.get("vote_average"))
        score = ("%s分" % vote) if vote else ""
        remark = " · ".join([x for x in (year, score) if x])
        return {
            "vod_id": "tmdb:%s:%s" % (media, item.get("id")),
            "vod_name": name[:100],
            "vod_pic": pic,
            "vod_remarks": remark,
            "vod_subtitle": self._clean(item.get("overview") or "")[:60],
        }

    def _quark_card(self, raw, channel):
        title = self._clean(raw.get("title") or "")
        if not title:
            return None
        pic = self._fix_url(raw.get("src") or "")
        if self._is_placeholder_pic(pic):
            pic = self.default_pic
        year = self._clean(raw.get("year") or "")
        area = self._clean(raw.get("area") or "")
        score = raw.get("score") or ""
        score = ("%s分" % score) if score else ""
        remark = " · ".join([x for x in (year, area, score) if x])
        ranking = raw.get("ranking") or 0
        return {
            "vod_id": "quark:%s:%s:%s" % (channel, ranking, title),
            "vod_name": title[:100],
            "vod_pic": pic,
            "vod_remarks": remark,
            "vod_subtitle": self._clean(raw.get("actors") or "")[:60],
        }

    # ---------------- 首页 / 分类 / 搜索 ----------------
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        data = self._tmdb_get("trending/all/day", page=1)
        results = data.get("results") or []
        videos = [c for c in (self._tmdb_card(x) for x in results) if c]
        self.log("home 推荐: %d 条" % len(videos))
        return {"list": videos}

    def _discover_params(self, tid, extend):
        is_movie = tid == "movie"
        params = {}
        sort = extend.get("sort") or "popularity.desc"
        if sort == "time":
            sort = ("primary_release_date.desc" if is_movie
                    else "first_air_date.desc")
        params["sort_by"] = sort
        if is_movie:
            params["primary_release_date.lte"] = "today"
            params["include_adult"] = "false"
            params["include_video"] = "false"
        else:
            params["first_air_date.lte"] = "today"
            params["include_null_first_air_dates"] = "false"
            params["include_adult"] = "false"
        if extend.get("area"):
            params["with_origin_country"] = extend["area"]
        if extend.get("year"):
            y = extend["year"]
            if is_movie:
                params["primary_release_date.gte"] = "%s-01-01" % y
                params["primary_release_date.lte"] = "%s-12-31" % y
            else:
                params["first_air_date.gte"] = "%s-01-01" % y
                params["first_air_date.lte"] = "%s-12-31" % y
        if extend.get("genre"):
            params["with_genres"] = extend["genre"]
        if tid == "anime":
            params["with_genres"] = "16"
        return params

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

        videos = []

        # 综艺 / 短剧走夸克榜单
        if tid in QUARK_CHANNEL:
            items = self._quark_ranking(QUARK_CHANNEL[tid])
            videos = [c for c in (self._quark_card(x, QUARK_CHANNEL[tid]) for x in items) if c]
            return {"list": videos, "page": page, "pagecount": 1,
                    "limit": 60, "total": len(videos)}

        if tid == "recommend":
            data = self._tmdb_get("trending/all/day", page=page)
            results = data.get("results") or []
            videos = [c for c in (self._tmdb_card(x) for x in results) if c]
        elif tid == "movie":
            data = self._tmdb_get("discover/movie", self._discover_params(tid, extend), page)
            results = data.get("results") or []
            videos = [c for c in (self._tmdb_card(x, "movie") for x in results) if c]
        elif tid in ("series", "anime"):
            data = self._tmdb_get("discover/tv", self._discover_params(tid, extend), page)
            results = data.get("results") or []
            videos = [c for c in (self._tmdb_card(x, "tv") for x in results) if c]
        else:
            data = self._tmdb_get("trending/all/day", page=page)
            videos = [c for c in (self._tmdb_card(x) for x in (data.get("results") or [])) if c]

        pagecount = int(data.get("total_pages") or 1) if isinstance(data, dict) else 1
        pagecount = max(1, min(pagecount, 99))
        self.log("category %s: %d 条, 总页数 %d" % (tid, len(videos), pagecount))
        return {"list": videos, "page": page, "pagecount": pagecount,
                "limit": 24, "total": pagecount * 24}

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        data = self._proxy_search(str(key or "").strip(), page)
        rows = data.get("results") or []
        videos = []
        for row in rows:
            if not row or not row.get("source") or row.get("id") in (None, ""):
                continue
            source = str(row["source"])
            name = self._clean(row.get("name") or "")
            if not name:
                continue
            pic = row.get("pic") or ""
            if self._is_placeholder_pic(pic):
                pic = self.default_pic
            else:
                pic = self._fix_url(pic)
            meta = [self._clean(x) for x in (row.get("remarks"), row.get("type"),
                                            row.get("year")) if self._clean(x)]
            videos.append({
                "vod_id": "source:%s:%s" % (source, row["id"]),
                "vod_name": name[:100],
                "vod_pic": pic,
                "vod_remarks": " · ".join(meta),
                "vod_subtitle": self._clean(row.get("area") or ""),
            })
        self.log("search %s: %d 条" % (key, len(videos)))
        return {"list": videos, "page": page, "pagecount": 1,
                "limit": 30, "total": len(videos)}

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------------- 详情 ----------------
    def _meta_from_tmdb(self, detail):
        if not detail:
            return {}
        crew = (detail.get("credits") or {}).get("crew") or []
        cast = (detail.get("credits") or {}).get("cast") or []
        directors = [c.get("name") for c in crew if c.get("job") == "Director"]
        actors = [c.get("name") for c in cast[:10] if c.get("name")]
        genres = [g.get("name") for g in (detail.get("genres") or [])]
        date = detail.get("release_date") or detail.get("first_air_date") or ""
        poster = detail.get("poster_path") or ""
        area = ",".join(AREA_CN.get(c, c) for c in (detail.get("origin_country") or []))
        return {
            "name": self._clean(detail.get("title") or detail.get("name") or ""),
            "pic": (IMAGE_BASE + poster) if poster else self.default_pic,
            "year": (date or "")[:4],
            "director": ",".join([x for x in directors if x]),
            "actor": ",".join([x for x in actors if x]),
            "area": area,
            "lang": detail.get("original_language") or "",
            "classify": ",".join([x for x in genres if x]),
            "score": _fmt_score(detail.get("vote_average")),
            "content": self._clean(detail.get("overview") or ""),
        }

    def _ordered_rows(self, rows, wanted="", year=""):
        # 与站点 buildCandidates 一致：同一源只保留片名最匹配的一条，
        # 按源顺序 -> 片名相似度 -> 原始下标排序；不匹配（score=99）的剔除。
        best = {}
        for idx, row in enumerate(rows or []):
            if not row or not row.get("source"):
                continue
            src = str(row["source"])
            score = self._title_score(row.get("name") or "", wanted)
            if year and str(row.get("year") or "") == str(year):
                score -= 0.2
            cand = {"row": row, "score": score, "index": idx}
            old = best.get(src)
            if old is None or cand["score"] < old["score"]:
                best[src] = cand
        ordered = [c["row"] for c in best.values() if c["score"] < 99]
        ordered.sort(key=lambda r: (
            SOURCE_ORDER.index(r["source"]) if r["source"] in SOURCE_ORDER else 99,
            best[r["source"]]["score"], best[r["source"]]["index"]))
        return ordered

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0])
        self.log("detail: %s" % vod_id)

        meta = {}
        rows = []
        tmdb_detail = None

        if vod_id.startswith("source:"):
            parts = vod_id.split(":", 2)
            source, sid = parts[1], parts[2]
            # 搜索结果卡片直连：该源该行即用户所选，不再做片名相似度筛选
            ordered = [{"source": source, "id": sid}]
        elif vod_id.startswith("tmdb:"):
            parts = vod_id.split(":", 2)
            media, tid = parts[1], parts[2]
            tmdb_detail = self._tmdb_detail(media, tid)
            meta = self._meta_from_tmdb(tmdb_detail)
            rows = self._proxy_search(meta.get("name") or "").get("results") or []
            ordered = self._ordered_rows(rows, meta.get("name") or "", meta.get("year") or "")
        elif vod_id.startswith("quark:"):
            parts = vod_id.split(":", 3)
            title = parts[3] if len(parts) > 3 else ""
            meta = {"name": title}
            rows = self._proxy_search(title).get("results") or []
            ordered = self._ordered_rows(rows, title, "")
        else:
            rows = self._proxy_search(vod_id).get("results") or []
            ordered = self._ordered_rows(rows, vod_id, "")

        self.log("  候选源: %d 个" % len(ordered))

        # 站点候选上限 12；详情按需拉取，这里取前 8 个源兼顾加载速度
        chosen = []
        for row in ordered[:8]:
            det = self._proxy_detail(row["source"], row["id"])
            if det:
                chosen.append((row, det))

        # 用首个有效详情补齐元信息
        if chosen:
            first = chosen[0][1]
            for k in ("actor", "area", "director", "year", "lang", "content",
                      "remarks", "type", "pic", "name"):
                if not meta.get(k) and first.get(k):
                    meta[k] = self._clean(first.get(k))
            if not meta.get("classify") and first.get("type"):
                meta["classify"] = self._clean(first.get("type"))
            if not meta.get("score") and first.get("score"):
                meta["score"] = self._clean(first.get("score"))

        # ===== 线路 / 选集 =====
        self._parser_map = {}
        play_from, play_url = [], []
        for row, det in chosen:
            source = row["source"]
            source_name = (det.get("source_name") or
                           SOURCE_NAMES.get(source, source))
            player_api = det.get("player_api") or SOURCE_PARSER.get(source) or DEFAULT_PARSER
            groups = det.get("episodes") or []
            if not groups and det.get("play_url"):
                # 兜底：详情已预拼好 名称$链接#...
                groups = [{"group": "", "episodes": self._parse_play_url(det["play_url"])}]

            # 官方源平台组按站点 official_platform_order 重排（稳定排序，未列平台保持原序）
            if source == OFFICIAL_SOURCE and len(groups) > 1:
                def _plat_rank(g):
                    k = re.sub(r"[\s_-]+", "", str(g.get("group") or "").lower())
                    return OFFICIAL_PLATFORM_ORDER.index(k) if k in OFFICIAL_PLATFORM_ORDER else len(OFFICIAL_PLATFORM_ORDER)
                groups = sorted(groups, key=_plat_rank)

            for g in groups:
                eps = g.get("episodes") or []
                if not eps:
                    continue
                label = source_name
                glabel = self._group_label(g.get("group") or "")
                if glabel and glabel.lower() != source.lower():
                    label = "%s·%s" % (source_name, glabel)
                # 线路名去重
                base_label, idx = label, 2
                while label in play_from:
                    label = "%s(%d)" % (base_label, idx)
                    idx += 1
                ep_lines = []
                for i, ep in enumerate(eps):
                    ep_name = self._clean(ep.get("name") or "") or ("第%d集" % (i + 1))
                    ep_url = ep.get("url") or ""
                    if ep_url:
                        ep_lines.append("%s$%s" % (ep_name, ep_url))
                if not ep_lines:
                    continue

                # 直链组（.m3u8/.mp4）：parse:0 直放，不挂解析备用
                first_url = (eps[0].get("url") or "") if eps else ""
                is_direct = bool(_RE_DIRECT.search(first_url or ""))

                # 主线路（源自带 player_api / 默认解析）
                play_from.append(label)
                play_url.append("#".join(ep_lines))
                self._parser_map[label] = player_api

                # 解析页组：并列网站公开 iframe 备用解析（对齐网页"解析线路"区），
                # 与主解析相同的那条跳过；json 鉴权路由不在此列。
                if not is_direct:
                    for p in PUBLIC_IFRAME_PARSERS:
                        if p["api"] == player_api:
                            continue
                        alt_label = "%s〔%s〕" % (label, p["name"])
                        alt_base, alt_idx = alt_label, 2
                        while alt_label in play_from:
                            alt_label = "%s(%d)" % (alt_base, alt_idx)
                            alt_idx += 1
                        play_from.append(alt_label)
                        play_url.append("#".join(ep_lines))
                        self._parser_map[alt_label] = p["api"]

        name = meta.get("name") or vod_id
        content = meta.get("content") or ""
        content = (INTRO_PREFIX + "\n" + content) if content else INTRO_PREFIX

        vod = {
            "vod_id": vod_id,
            "vod_name": name[:100],
            "vod_pic": meta.get("pic") or self.default_pic,
            "vod_content": content,
            "vod_actor": meta.get("actor") or "",
            "vod_director": meta.get("director") or "",
            "vod_score": meta.get("score") or "",
            "vod_remarks": meta.get("remarks") or ("%d条线路" % len(play_from) if play_from else "暂无可用资源"),
            "vod_area": meta.get("area") or "",
            "vod_year": meta.get("year") or "",
            "vod_lang": meta.get("lang") or "",
            "vod_classify": meta.get("classify") or "",
            "type_name": meta.get("classify") or "",
            "vod_alias": "",
            "vod_update": "",
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }
        return {"list": [vod]}

    def _tmdb_detail(self, media, tid):
        endpoint = "%s/%s" % (media, tid)
        append = "credits,images"
        if media == "tv":
            append = "credits,images,season/1"
        data = self._tmdb_get(endpoint, {
            "append_to_response": append,
            "include_image_language": "zh,null,en",
        })
        return data if isinstance(data, dict) else {}

    def _parse_play_url(self, play_url):
        """解析预拼 play_url：名称$链接#名称$链接 ..."""
        eps = []
        if not play_url:
            return eps
        for seg in str(play_url).split("#"):
            if "$" in seg:
                n, u = seg.split("$", 1)
                eps.append({"name": self._clean(n), "url": u})
        return eps

    # ---------------- 播放 ----------------
    def playerContent(self, flag, id, vipFlags):
        play_url = id if str(id).startswith("http") else self._fix_url(id)
        self.log("player: %s" % play_url)

        if not play_url:
            return {"parse": 0, "playUrl": "", "url": "",
                    "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}

        now = int(time.time())
        if play_url in self._play_cache:
            ts, res = self._play_cache[play_url]
            if now - ts < 600:
                return res

        header = {"User-Agent": UA, "Referer": self.site_url + "/"}

        if _RE_DIRECT.search(play_url or ""):
            # 直链 m3u8 / mp4
            res = {"parse": 0, "playUrl": "", "url": play_url, "header": header}
        else:
            parser = self._parser_map.get(flag) or SOURCE_PARSER.get(flag) or DEFAULT_PARSER
            target = play_url
            if parser:
                target = parser + urllib.parse.quote(play_url or "", safe="")
            res = {"parse": 1, "playUrl": "", "url": target, "header": header}

        self._play_cache[play_url] = (now, res)
        self.log("  => parse=%s url=%s" % (res["parse"], res["url"][:160]))
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
