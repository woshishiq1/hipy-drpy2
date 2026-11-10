# coding=utf-8
"""
ZIP0 影视 zip0.com | TVBox Python 爬虫 
关键:
  - 调用 zip0.com 的 TanStack Start server functions (_serverFn)
    * 源目录   8fa43bc2...  GET  无参
    * 单源分类 7e1a065d...  GET  {area,type,year,category,page,source}
    * 单源搜索 924908a6...  GET  {area,type,year,query,source}
    * 近期更新 b42ee085...  GET  无参 (首页推荐 sections)
  - 详情页解析 /watch?source=&id= SSR HTML (含全部集数直链 m3u8)
  - 聚合 10 条线路 (dyttzy/ruyi/bfzy/ffzy/zy360/jisu/mdzy/zuid/ikun/lzi)
    线路命名与网站完全一致: 线路1 ~ 线路10, 顺序与源目录一致
  - 切换其他线路时在 playerContent 实时解析对应源的 /watch SSR
  - 筛选(类型/地区/年份/排序)取值与网站前端完全一致
"""
import re
import sys
import json
import time
import threading

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
                    pool_connections=20, pool_maxsize=20, max_retries=0)
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
                print("[zip0]", *a, **kw)
            except Exception:
                pass

    Spider = _BaseSpider


try:
    import urllib.request as _ureq
    import urllib.parse as _uparse
except Exception:
    _ureq = None
    _uparse = None


HOST = "https://zip0.com"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# ===================== 线路 (与 zip0 源目录顺序完全一致) =====================
SOURCE_ORDER = ["dyttzy", "ruyi", "bfzy", "ffzy", "zy360",
                "jisu", "mdzy", "zuid", "ikun", "lzi"]
SOURCE_NAME = {s: "线路%d" % (i + 1) for i, s in enumerate(SOURCE_ORDER)}

# ===================== server function id =====================
FN_CATALOG = "8fa43bc249007c84c4782b4237f5181449e18cd1723d5656f5f3c45c42e2daab"
FN_CATEGORY = "7e1a065dd0c4f105c2195db3af705adf30b75b211920223f5e3f9e62024916a0"
FN_SEARCH = "924908a6328d92c97055b1d048defe7b4f8102dee6907ac36be30470204c7535"
FN_RECENT = "b42ee085174093515a801f91174a8e544266b579c62db3cecc6d13f99a17dd1d"
FN_ALT = "a406c5547c83f4497d0bfc2c25bba7383721c724b5b695d7fe56f3f6e22e7710"

# ===================== 分类 (与 /category/$category 一致) =====================
CLASSES = [
    {"type_id": "movie",       "type_name": "电影"},
    {"type_id": "tv",          "type_name": "电视剧"},
    {"type_id": "short",       "type_name": "短剧"},
    {"type_id": "variety",     "type_name": "综艺"},
    {"type_id": "documentary", "type_name": "纪录片"},
    {"type_id": "sports",      "type_name": "体育"},
]

# ===================== 筛选 (与网站前端 value 完全一致) =====================
_TYPES = [
    {"n": "全部类型", "v": "all"}, {"n": "电影", "v": "movie"},
    {"n": "电视剧", "v": "tv"}, {"n": "综艺", "v": "variety"},
    {"n": "动漫", "v": "anime"}, {"n": "短剧", "v": "short"},
    {"n": "纪录片", "v": "documentary"}, {"n": "体育", "v": "sports"},
    {"n": "其他", "v": "other"},
]
_AREAS = [
    {"n": "全部地区", "v": "all"}, {"n": "大陆", "v": "mainland"},
    {"n": "香港", "v": "hong-kong"}, {"n": "台湾", "v": "taiwan"},
    {"n": "日本", "v": "japan"}, {"n": "韩国", "v": "korea"},
    {"n": "欧美", "v": "western"}, {"n": "泰国", "v": "thailand"},
    {"n": "印度", "v": "india"}, {"n": "其他", "v": "other"},
]
_YEARS = [
    {"n": "全部年份", "v": "all"}, {"n": "今年", "v": "current"},
    {"n": "去年", "v": "last"}, {"n": "2010 年代", "v": "2010s"},
    {"n": "2000 年代", "v": "2000s"}, {"n": "90 年代", "v": "1990s"},
    {"n": "更早", "v": "older"},
]
_SORTS = [
    {"n": "最近更新", "v": "updated"}, {"n": "评分最高", "v": "score"},
]

FILTERS = {}
for _c in CLASSES:
    FILTERS[_c["type_id"]] = [
        {"key": "type", "name": "类型", "value": _TYPES},
        {"key": "area", "name": "地区", "value": _AREAS},
        {"key": "year", "name": "年份", "value": _YEARS},
        {"key": "sort", "name": "排序", "value": _SORTS},
    ]

# ===================== SSR 详情提取正则 =====================
_RE_EPISODES = re.compile(
    r'episodes:?\s*(?::\$R\[\d+\])?=\[([\s\S]*?)\]\s*[,\}]', re.I)
_RE_EP_ITEM = re.compile(
    r'name:\s*"((?:[^"\\]|\\.)*)"\s*,\s*url:\s*"((?:[^"\\]|\\.)*)"')
_RE_STR = {
    "title":       re.compile(r'title:\s*"((?:[^"\\]|\\.)*)"'),
    "poster":      re.compile(r'poster:\s*"((?:[^"\\]|\\.)*)"'),
    "description": re.compile(r'description:\s*"((?:[^"\\]|\\.)*)"'),
    "actors":      re.compile(r'actors:\s*"((?:[^"\\]|\\.)*)"'),
    "director":    re.compile(r'director:\s*"((?:[^"\\]|\\.)*)"'),
    "score":       re.compile(r'score:\s*"((?:[^"\\]|\\.)*)"'),
    "year":        re.compile(r'\byear:\s*"((?:[^"\\]|\\.)*)"'),
    "remarks":     re.compile(r'remarks:\s*"((?:[^"\\]|\\.)*)"'),
    "area":        re.compile(r'\barea:\s*"((?:[^"\\]|\\.)*)"'),
    "language":    re.compile(r'language:\s*"((?:[^"\\]|\\.)*)"'),
    "category":    re.compile(r'category:\s*"((?:[^"\\]|\\.)*)"'),
}
_RE_H1 = re.compile(r'<h1[^>]*>([\s\S]*?)</h1>', re.I)
_RE_TITLE = re.compile(r'<title>(.*?)</title>', re.S)

# seroval 值类型: 0=数字 1=字符串 2=字符串 4=布尔 9=数组 10=对象


class Spider(Spider):

    def getName(self):
        return "ZIP0影视"

    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}
        self.site_url = (self.extend.get("site") or HOST).rstrip("/")
        self.headers = {
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/120.0.0.0 Safari/537.36"),
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": self.site_url + "/",
            "Origin": self.site_url,
            "sec-fetch-site": "same-origin",
            "sec-fetch-mode": "cors",
            "sec-fetch-dest": "empty",
        }
        self.fn_headers = dict(self.headers)
        self.fn_headers.update({
            "Accept": "application/json, application/x-tss-framed, application/x-ndjson",
            "x-tsr-serverFn": "true",
        })
        self.page_headers = dict(self.headers)
        self.page_headers.update({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "sec-fetch-mode": "navigate",
            "sec-fetch-dest": "document",
            "sec-fetch-site": "none",
            "Upgrade-Insecure-Requests": "1",
        })
        self._detail_cache = {}
        self._play_cache = {}
        self._sources_lock = threading.Lock()
        self._sources = list(SOURCE_ORDER)
        self.log("init: site=%s" % self.site_url)

    # ===================== 底层请求 =====================
    def _seroval_encode(self, v):
        if isinstance(v, dict):
            return {"t": 10, "i": 1,
                    "p": {"k": list(v.keys()),
                          "v": [self._seroval_encode(x) for x in v.values()]},
                    "o": 0}
        if isinstance(v, (list, tuple)):
            return {"t": 9, "i": 1,
                    "a": [self._seroval_encode(x) for x in v], "o": 0}
        if isinstance(v, bool):
            return {"t": 4, "s": v}
        if isinstance(v, (int, float)):
            return {"t": 0, "s": v}
        return {"t": 1, "s": str(v)}

    def _seroval_decode(self, x):
        if isinstance(x, dict):
            t = x.get("t")
            if t == 10:
                p = x.get("p") or {}
                return {k: self._seroval_decode(v)
                        for k, v in zip(p.get("k") or [], p.get("v") or [])}
            if t == 9:
                return [self._seroval_decode(v) for v in x.get("a") or []]
            if t in (0, 1, 2, 4):
                return x.get("s")
        return x

    def _post_ser(self, url, body, timeout=15):
        """POST 序列化 payload (备用通道)"""
        data = body.encode("utf-8")
        req = _ureq.Request(url, data=data, method="POST")
        for k, v in self.fn_headers.items():
            req.add_header(k, v)
        req.add_header("content-type", "application/json")
        rsp = _ureq.urlopen(req, timeout=timeout)
        return rsp.read().decode("utf-8", "ignore")

    def _call_fn(self, fn_id, data=None, timeout=12):
        """调用 zip0 server function, 返回解码后的 result (失败返回 None)"""
        url = self.site_url + "/_serverFn/" + fn_id
        try:
            if data is not None:
                payload = json.dumps(
                    {"t": self._seroval_encode({"data": data}),
                     "f": 127, "m": []},
                    separators=(",", ":"), ensure_ascii=False)
                url += "?payload=" + _uparse.quote(payload, safe="")
                rsp = self.fetch(url, headers=self.fn_headers, timeout=timeout)
                text = rsp.text if hasattr(rsp, "text") else str(rsp)
            else:
                rsp = self.fetch(url, headers=self.fn_headers, timeout=timeout)
                text = rsp.text if hasattr(rsp, "text") else str(rsp)
            obj = json.loads(text)
            if isinstance(obj, dict) and "result" in obj:
                return obj["result"]
            if isinstance(obj, dict) and obj.get("t") == 10:
                res = self._seroval_decode(obj)
                if isinstance(res, dict):
                    return res.get("result")
            return None
        except Exception as e:
            self.log("fn FAIL %s -> %s" % (fn_id[:8], e))
            return None

    # ===================== 数据获取 =====================
    def _get_sources(self):
        with self._sources_lock:
            return list(self._sources)

    def _fetch_source_catalog(self):
        res = self._call_fn(FN_CATALOG)
        if isinstance(res, list) and res:
            srcs = [x.get("source") for x in res if x.get("source")]
            if srcs:
                with self._sources_lock:
                    self._sources = srcs
                self.log("源目录: %s" % ",".join(srcs))

    def _warm_up(self):
        try:
            self.fetch(self.site_url + "/", headers=self.page_headers,
                       timeout=15)
            self._fetch_source_catalog()
        except Exception as e:
            self.log("预热失败: %s" % e)

    def _parallel(self, func, args_list, timeout=15):
        """并发执行, 按入参顺序返回结果列表"""
        results = [None] * len(args_list)
        threads = []

        def worker(i, a):
            try:
                results[i] = func(*a)
            except Exception:
                results[i] = None

        for i, a in enumerate(args_list):
            t = threading.Thread(target=worker, args=(i, a))
            t.daemon = True
            t.start()
            threads.append(t)
        deadline = time.time() + timeout
        for t in threads:
            t.join(max(0.1, deadline - time.time()))
        return results

    def _category_of_source(self, source, category, page, area, typ, year):
        res = self._call_fn(FN_CATEGORY, {
            "area": area, "type": typ, "year": year,
            "category": category, "page": int(page), "source": source,
        })
        if isinstance(res, dict):
            return res
        return {"items": [], "hasMore": 0}

    def _search_of_source(self, source, query, area, typ, year):
        res = self._call_fn(FN_SEARCH, {
            "area": area, "type": typ, "year": year,
            "query": query, "source": source,
        })
        if isinstance(res, dict):
            return res
        return {"items": [], "hasMore": 0}

    @staticmethod
    def _merge_items(responses):
        """多源结果按 (title+year) 聚合去重, 保持线路优先顺序"""
        seen = {}
        ordered = []
        for res in responses:
            if not isinstance(res, dict):
                continue
            for it in res.get("items") or []:
                key = (it.get("title") or "", it.get("year") or "")
                if key in seen:
                    continue
                seen[key] = True
                ordered.append(it)
        return ordered

    @staticmethod
    def _to_vod(it):
        remarks = it.get("remarks") or ""
        ep = it.get("episodeCount")
        if ep and not remarks:
            remarks = "全%s集" % ep
        return {
            "vod_id": "%s:%s" % (it.get("source"), it.get("id")),
            "vod_name": (it.get("title") or "")[:100],
            "vod_pic": it.get("poster") or "",
            "vod_remarks": remarks,
            "vod_year": it.get("year") or "",
        }

    # ===================== TVBox 接口 =====================
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        res = self._call_fn(FN_RECENT, timeout=20)
        videos = []
        if isinstance(res, dict):
            sections = res.get("sections") or {}
            for key in ("movie", "tv", "short", "variety", "anime"):
                for it in (sections.get(key) or [])[:8]:
                    v = self._to_vod(it)
                    v["vod_id"] = "%s:%s" % (it.get("source"), it.get("id"))
                    videos.append(v)
        if not videos:
            self._warm_up()
            res = self._call_fn(FN_RECENT, timeout=20)
            if isinstance(res, dict):
                for key in ("movie", "tv", "short", "variety", "anime"):
                    for it in (res.get("sections") or {}).get(key) or []:
                        videos.append(self._to_vod(it))
        # 去重
        seen = set()
        out = []
        for v in videos:
            if v["vod_id"] in seen:
                continue
            seen.add(v["vod_id"])
            out.append(v)
        self.log("home: %d 条" % len(out))
        return {"list": out}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if str(pg).isdigit() else 1
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        if not extend:
            extend = {}
        area = extend.get("area") or "all"
        typ = extend.get("type") or "all"
        year = extend.get("year") or "all"

        sources = self._get_sources()
        if not sources:
            self._warm_up()
            sources = self._get_sources() or SOURCE_ORDER

        args = [(s, tid, page, area, typ, year) for s in sources]
        responses = self._parallel(self._category_of_source, args, timeout=18)
        items = self._merge_items(responses)

        # 排序: 默认按更新时间, score 按评分
        sort_mode = extend.get("sort") or "updated"

        def _ts(it):
            try:
                return time.mktime(time.strptime(
                    it.get("updatedAt") or "", "%Y-%m-%d %H:%M:%S"))
            except Exception:
                return 0

        def _sc(it):
            try:
                return float(it.get("score") or 0)
            except Exception:
                return 0.0

        if sort_mode == "score":
            items.sort(key=lambda x: (-_sc(x), -_ts(x)))
        else:
            items.sort(key=_ts, reverse=True)

        videos = [self._to_vod(it) for it in items]
        has_more = any((r or {}).get("hasMore") for r in responses
                       if isinstance(r, dict))
        pagecount = page + 1 if has_more else page
        self.log("category %s p%d: %d 条" % (tid, page, len(videos)))
        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 40, "total": pagecount * 40,
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if str(pg).isdigit() else 1
        if page > 1:
            return {"list": [], "page": page, "pagecount": 1,
                    "limit": 40, "total": 40}
        sources = self._get_sources()
        if not sources:
            self._warm_up()
            sources = self._get_sources() or SOURCE_ORDER
        args = [(s, key, "all", "all", "all") for s in sources]
        responses = self._parallel(self._search_of_source, args, timeout=20)
        items = self._merge_items(responses)

        def _ts(it):
            try:
                return time.mktime(time.strptime(
                    it.get("updatedAt") or "", "%Y-%m-%d %H:%M:%S"))
            except Exception:
                return 0
        items.sort(key=_ts, reverse=True)
        videos = [self._to_vod(it) for it in items]
        self.log("search %s: %d 条" % (key, len(videos)))
        return {"list": videos, "page": 1, "pagecount": 1,
                "limit": 40, "total": len(videos)}

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ===================== 详情 =====================
    def _unesc(self, s):
        if not s:
            return ""
        s = s.replace('\\"', '"').replace("\\/", "/")
        s = s.replace("\\n", "\n").replace("\\\\", "\\")
        return s.strip()

    def _parse_watch_ssr(self, html):
        """从 /watch SSR HTML 提取详情与集数"""
        info = {"episodes": []}
        if not html:
            return info
        for k, rx in _RE_STR.items():
            m = rx.search(html)
            if m:
                info[k] = self._unesc(m.group(1))

        m = _RE_EPISODES.search(html)
        if m:
            eps = []
            for name, url in _RE_EP_ITEM.findall(m.group(1)):
                if url:
                    eps.append({"name": self._unesc(name), "url": self._unesc(url)})
            info["episodes"] = eps
        if not info["episodes"]:
            eps = []
            for name, url in _RE_EP_ITEM.findall(html):
                if url and ("m3u8" in url or "mp4" in url):
                    eps.append({"name": self._unesc(name), "url": self._unesc(url)})
            info["episodes"] = eps
        return info

    def _get_alt_sources(self, source, vid):
        """获取同片其他线路 (alternatives)"""
        res = self._call_fn(FN_ALT, {"source": source, "id": str(vid)})
        alts = []
        if isinstance(res, dict):
            for it in res.get("alternatives") or []:
                if it.get("source") and it.get("id"):
                    alts.append(it)
        # 只保留 zip0 源目录中的线路并按线路顺序排序
        order = {s: i for i, s in enumerate(SOURCE_ORDER)}
        alts = [a for a in alts if a.get("source") in order]
        alts.sort(key=lambda x: order.get(x.get("source"), 999))
        return alts

    def _watch_url(self, source, vid, ep=1):
        return "%s/watch?source=%s&id=%s&episode=%d" % (
            self.site_url, source, vid, ep)

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        raw = str(ids[0])
        if ":" in raw:
            source, vid = raw.split(":", 1)
        else:
            source, vid = SOURCE_ORDER[0], raw

        # 主线路详情 (SSR)
        html = ""
        try:
            rsp = self.fetch(self._watch_url(source, vid, 1),
                             headers=self.page_headers, timeout=30)
            html = rsp.text if hasattr(rsp, "text") else str(rsp)
        except Exception as e:
            self.log("detail SSR FAIL: %s" % e)

        info = self._parse_watch_ssr(html)
        name = info.get("title") or ""
        if not name:
            m = _RE_H1.search(html or "")
            if m:
                name = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        if not name:
            m = _RE_TITLE.search(html or "")
            if m:
                name = re.sub(r"\s*[|｜].*$", "", m.group(1)).strip()
        name = name or vid

        eps = info.get("episodes") or []
        content = info.get("description") or ""
        if content:
            content = INTRO_PREFIX + "\n" + content
        else:
            content = INTRO_PREFIX

        # 其他线路
        alts = self._get_alt_sources(source, vid)

        # ===== 线路组装: 当前线路用真实直链, 其他线路由 playerContent 实时解析 =====
        flags = []
        play_urls = []

        cur_flag = SOURCE_NAME.get(source, source)
        flags.append(cur_flag)
        if eps:
            play_urls.append("#".join(
                "%s$%s" % (e["name"], e["url"]) for e in eps))
        else:
            play_urls.append("暂无资源$%s:%s:1" % (source, vid))

        for alt in alts:
            a_src = alt.get("source")
            a_id = str(alt.get("id"))
            if a_src == source and a_id == str(vid):
                continue
            alias = SOURCE_NAME.get(a_src, a_src)
            n = alt.get("episodeCount") or len(eps) or 1
            try:
                n = int(n)
            except Exception:
                n = 1
            flags.append(alias)
            play_urls.append("#".join(
                ["第%d集$%s:%s:%d" % (i, a_src, a_id, i) for i in range(1, n + 1)]))

        remarks = info.get("remarks") or ""
        if not remarks and eps:
            remarks = "全%d集" % len(eps)
        meta_bits = []
        if info.get("year"):
            meta_bits.append(info["year"])
        if info.get("area"):
            meta_bits.append(info["area"])
        if info.get("language"):
            meta_bits.append(info["language"])

        return {"list": [{
            "vod_id": "%s:%s" % (source, vid),
            "vod_name": name,
            "vod_pic": info.get("poster") or "",
            "vod_content": content,
            "vod_actor": info.get("actors") or "",
            "vod_director": info.get("director") or "",
            "vod_score": info.get("score") or "",
            "vod_year": info.get("year") or "",
            "vod_area": info.get("area") or "",
            "vod_class": info.get("category") or "",
            "vod_remarks": remarks or ("%d条线路" % len(flags)),
            "vod_play_from": "$$$".join(flags),
            "vod_play_url": "$$$".join(play_urls),
        }]}

    # ===================== 播放 =====================
    def playerContent(self, flag, id, vipFlags):
        play_id = str(id)
        now = int(time.time())

        # 缓存命中
        if play_id in self._play_cache:
            ts, res = self._play_cache[play_id]
            if now - ts < 600:
                return res

        def _ok(url):
            return {
                "parse": 0, "playUrl": "", "url": url,
                "header": {
                    "User-Agent": self.headers["User-Agent"],
                    "Referer": self.site_url + "/",
                },
            }

        # 直链 (主线路选集)
        if play_id.startswith("http"):
            res = _ok(play_id)
            self._play_cache[play_id] = (now, res)
            return res

        # 其他线路: src:vid:epIndex -> 实时解析对应源 SSR
        parts = play_id.split(":")
        if len(parts) >= 3:
            source, vid = parts[0], parts[1]
            try:
                ep = int(parts[2])
            except Exception:
                ep = 1
            cache_key = "ssr:%s:%s" % (source, vid)
            eps = None
            if cache_key in self._detail_cache:
                ts, val = self._detail_cache[cache_key]
                if now - ts < 600:
                    eps = val
            if eps is None:
                try:
                    rsp = self.fetch(self._watch_url(source, vid, ep),
                                     headers=self.page_headers, timeout=30)
                    html = rsp.text if hasattr(rsp, "text") else str(rsp)
                    info = self._parse_watch_ssr(html)
                    eps = info.get("episodes") or []
                    self._detail_cache[cache_key] = (now, eps)
                except Exception as e:
                    self.log("player SSR FAIL %s -> %s" % (play_id, e))
                    eps = []
            if eps:
                idx = min(max(ep - 1, 0), len(eps) - 1)
                url = eps[idx]["url"]
                res = _ok(url)
                self._play_cache[play_id] = (now, res)
                self.log("player %s ep%d -> %s" % (play_id, ep, url[:120]))
                return res

        # 兜底: 交回播放页地址
        res = {
            "parse": 1, "playUrl": "",
            "url": self._watch_url(*parts[:2], ep=1) if len(parts) >= 2 else play_id,
            "header": {"User-Agent": self.headers["User-Agent"],
                       "Referer": self.site_url + "/"},
        }
        self._play_cache[play_id] = (now, res)
        return res

    # ===================== 其他 =====================
    def localProxy(self, param):
        return [200, "image/jpeg", b"", ""]

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url or url.startswith("http")

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()
