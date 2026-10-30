# coding=utf-8
"""
搜剧AI souju.ai | TVBox Python 爬虫 
关键:
  - 请求签名: HMAC-SHA256(secret, "GET\\n{path}{query}\\n{timestamp}\\n{nonce}")
    headers: x-ai-movie-timestamp / x-ai-movie-nonce / x-ai-movie-signature
  - 大分类与官网片库一致: 电视剧/电影/短剧/动漫/综艺/纪录片/体育
  - 详情页解析首集 playback/resolve, 按官网线路 label (1080P-官方/爱奇艺/
    红牛资源/西瓜资源...) 生成多线路分组, play_from=线路名
  - resolve_ticket 官方线路需登录权益, 游客自动兜底到直链 m3u8
  - 偶发 502 自动重试
"""
import re
import sys
import json
import time
import hmac
import hashlib
import secrets
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
                print("[souju]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://souju.ai"

# 站点请求签名密钥 (来自前端 JS, 与官网完全一致)
SIGN_SECRET = ("f39d73aa7a6426203cdee1ef17b31d3b7ea8c23f4c59c62a3a"
               "8aa0f39ee5e79d")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

DEFAULT_PIC = "https://souju.ai/assets/app-icon-512.png"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# 与官网片库 h_ 表完全一致 (label + order)
CLASSES = [
    {"type_id": "series",      "type_name": "电视剧"},
    {"type_id": "movie",       "type_name": "电影"},
    {"type_id": "short_drama", "type_name": "短剧"},
    {"type_id": "anime",       "type_name": "动漫"},
    {"type_id": "variety",     "type_name": "综艺"},
    {"type_id": "documentary", "type_name": "纪录片"},
    {"type_id": "sports",      "type_name": "体育"},
]

# 与官网 /v1/runtime/bootstrap 下发的片库筛选项一致
_GENRE_MAP = {
    "series": ["偶像", "爱情", "言情", "古装", "历史", "玄幻", "谍战", "历险",
               "都市", "科幻", "军旅", "喜剧", "武侠", "江湖", "罪案", "青春",
               "家庭", "战争", "悬疑", "穿越", "宫廷", "神话", "商战", "警匪",
               "动作", "惊悚", "剧情", "同性", "奇幻"],
    "movie": ["喜剧", "爱情", "动作", "犯罪", "科幻", "奇幻", "冒险", "灾难",
              "恐怖", "惊悚", "剧情", "战争", "歌舞", "经典", "悬疑", "动画",
              "同性", "网络电影"],
    # 短剧分类与官网一致 (另含"横屏/竖屏", 官网标注片库接口暂不支持, 故不列)
    "short_drama": ["真人剧", "comic", "偶像", "爱情", "言情", "古装", "历史",
                    "玄幻", "谍战", "都市", "历险", "科幻", "军旅", "喜剧",
                    "武侠", "江湖", "罪案", "青春", "家庭", "战争", "悬疑",
                    "穿越", "宫廷", "神话", "商战", "警匪", "动作", "惊悚",
                    "剧情", "同性", "奇幻", "女性", "系统", "逆袭", "无敌",
                    "乡村", "古风", "赘婿", "萌宝", "种田", "犯罪", "年代",
                    "志怪", "战神", "婚姻", "现言", "宫斗", "友情", "职场",
                    "民国", "法律", "抗战", "时空", "反转", "仙侠", "末世",
                    "体育", "刑侦", "成长", "游戏", "脑洞", "冒险", "恐怖",
                    "古代", "医疗", "推理", "灾难", "搞笑", "玄学", "轻喜剧",
                    "家族", "超凡", "日常", "伦理", "重生", "经营", "温情"],
    "anime": ["热血", "格斗", "机战", "少女", "竞技", "科幻", "魔幻", "爆笑",
              "推理", "冒险", "恋爱", "校园", "治愈", "泡面", "穿越", "灵异",
              "耽美", "剧场版", "其它"],
    "variety": ["真人秀", "选秀", "网综", "脱口秀", "搞笑", "竞技", "情感",
                "访谈", "演唱会", "晚会", "其它"],
}

# 子分类: 官网片库数据里真实存在的剧种/题材标签 (genre 参数实测均有效)
# 电视剧下即用户看到的 国产剧 / 美剧 / 日剧 / 韩剧 ... 这一层
_SUBGENRE_MAP = {
    "series": ["国产剧", "美剧", "日剧", "韩剧", "港剧", "台剧", "泰剧",
               "欧美剧", "海外剧", "网络剧", "短剧", "电视剧"],
    "movie": ["院线", "4K电影", "邵氏电影", "动漫电影", "网络电影", "枪战",
              "警匪", "纯爱", "灾难", "西部"],
    "anime": ["国产动漫", "日韩动漫", "日本动漫", "欧美动漫", "国创(B站)",
              "番(B站)", "番剧(B站)", "漫画改", "小说改", "游戏改", "原创",
              "热血", "战斗", "治愈", "日常", "机战", "特摄", "少儿",
              "恋爱", "校园"],
    "variety": ["真人秀", "大陆综艺", "日韩综艺", "港台综艺", "欧美综艺",
                "国产综艺", "脱口秀", "选秀", "访谈", "晚会", "春晚",
                "美食", "旅游", "游戏", "相声", "戏曲", "益智", "舞蹈",
                "音乐", "竞技"],
    "short_drama": ["脑洞悬疑", "现代都市", "爽文短剧", "古装仙侠", "现代言情",
                    "年代穿越", "言情总裁", "反转爽剧", "女频恋爱", "重生民国",
                    "AI漫剧", "漫剧", "闪婚离婚"],
    "documentary": ["纪录片"],
    "sports": ["体育赛事", "赛事", "奥运会", "足球", "世界杯"],
}

# 官网"其它"项 enabled=false (片库接口不支持), 故不列出, 以"全部"收尾
_AREAS = [
    {"n": "全部", "v": ""},
    {"n": "大陆", "v": "中国大陆"}, {"n": "香港", "v": "中国香港"},
    {"n": "台湾", "v": "中国台湾"}, {"n": "日本", "v": "日本"},
    {"n": "韩国", "v": "韩国"}, {"n": "欧美", "v": "欧美"},
    {"n": "英国", "v": "英国"}, {"n": "泰国", "v": "泰国"},
]

# 语言: 与官网 language 行一致
_LANGS = [
    {"n": "全部", "v": ""},
    {"n": "国语", "v": "国语"}, {"n": "粤语", "v": "粤语"},
    {"n": "英语", "v": "英语"}, {"n": "韩语", "v": "韩语"},
    {"n": "日语", "v": "日语"}, {"n": "西班牙语", "v": "西班牙语"},
    {"n": "法语", "v": "法语"}, {"n": "德语", "v": "德语"},
    {"n": "意大利语", "v": "意大利语"}, {"n": "泰国语", "v": "泰国语"},
]

# 年份: 官网提交的是区间参数, 统一用 "g:起始:结束" 编码 (空=不限)
# 今年/去年由 init() 按当前年份动态计算
_YEARS = [
    {"n": "全部", "v": ""},
    {"n": "今年", "v": "g::CY"},
    {"n": "去年", "v": "g::PY"},
    {"n": "更早", "v": "g::2024"},
    {"n": "90年代", "v": "g:1990:1999"},
    {"n": "80年代", "v": "g:1980:1989"},
    {"n": "1980年以前", "v": "g::1979"},
]

# 排序: 与官网 sort 行一致 (最新 / 最热)
_SORTS = [
    {"n": "最新", "v": "updated_desc"},
    {"n": "最热", "v": "heat_desc"},
]

FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    fl = []
    if tid in _SUBGENRE_MAP:
        fl.append({"key": "subgenre", "name": "子分类",
                   "value": [{"n": x, "v": x} for x in _SUBGENRE_MAP[tid]]})
    if tid in _GENRE_MAP:
        fl.append({"key": "genre", "name": "分类",
                   "value": [{"n": x, "v": x} for x in _GENRE_MAP[tid]]})
    fl.append({"key": "area", "name": "地区", "value": _AREAS})
    fl.append({"key": "language", "name": "语言", "value": _LANGS})
    fl.append({"key": "year", "name": "年份", "value": _YEARS})
    fl.append({"key": "sort", "name": "排序", "value": _SORTS})
    FILTERS[tid] = fl

PAGE_LIMIT = 24
MAX_RETRY = 4


class Spider(Spider):

    def getName(self):
        return "搜剧AI"

    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}

        self.site_url = (self.extend.get("site") or HOST).rstrip("/")
        self.headers = {
            "User-Agent": UA,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": self.site_url + "/",
            "Origin": self.site_url,
        }
        self.default_pic = DEFAULT_PIC
        self._detail_cache = {}
        self._play_cache = {}
        self._lines_cache = {}
        self._url_probe_cache = {}
        self.log("init: site=%s" % self.site_url)

    # ===================== 签名与请求 =====================
    def _signed_fetch(self, path, params=None, timeout=20):
        """对 /v1/ 接口按官网规则进行 HMAC-SHA256 请求签名后 GET (带重试)。"""
        base = {k: v for k, v in (params or {}).items() if v not in (None, "")}
        query = urllib.parse.urlencode(base) if base else ""
        url = self.site_url + path + (("?" + query) if query else "")
        full_path = path + (("?" + query) if query else "")

        last_err = ""
        for attempt in range(MAX_RETRY):
            try:
                ts = str(int(time.time() * 1000))
                nonce = secrets.token_hex(16)
                msg = "GET\n%s\n%s\n%s" % (full_path, ts, nonce)
                sig = hmac.new(SIGN_SECRET.encode(), msg.encode(),
                               hashlib.sha256).hexdigest()

                h = dict(self.headers)
                h["x-ai-movie-timestamp"] = ts
                h["x-ai-movie-nonce"] = nonce
                h["x-ai-movie-signature"] = sig

                rsp = self.fetch(url, headers=h, timeout=timeout)
                text = ""
                if hasattr(rsp, "text"):
                    text = rsp.text or ""
                elif hasattr(rsp, "content"):
                    text = rsp.content.decode("utf-8", "ignore")
                try:
                    return json.loads(text)
                except Exception:
                    last_err = "非JSON len=%d" % len(text)
            except Exception as e:
                last_err = str(e)
            if attempt < MAX_RETRY - 1:
                time.sleep(1.2 * (attempt + 1))

        self.log("signed_fetch FAIL %s -> %s" % (path, last_err))
        return {}

    def _browse(self, params):
        base = {"page": 1, "limit": PAGE_LIMIT}
        base.update({k: v for k, v in params.items() if v})
        return self._signed_fetch("/v1/browse/catalog", base)

    def _cards_to_videos(self, data):
        videos = []
        for card in (data.get("cards") or []):
            try:
                videos.append({
                    "vod_id":      card.get("id") or "",
                    "vod_name":    (card.get("title") or "")[:100],
                    "vod_pic":     card.get("poster_url") or self.default_pic,
                    "vod_remarks": (card.get("remarks") or "")[:20],
                })
            except Exception:
                continue
        return [v for v in videos if v["vod_id"]]

    def _pagecount(self, data, page):
        pagination = data.get("pagination") or {}
        try:
            total = pagination.get("total")
            if total:
                return min(9999, (int(total) + PAGE_LIMIT - 1) // PAGE_LIMIT)
            if pagination.get("has_more") is False:
                return page
        except Exception:
            pass
        return 9999

    # ===================== 线路解析 =====================
    def _resolve_lines(self, ep_token):
        """解析某集的线路列表。返回按官网顺序排序的 line_options 列表,
        直链 m3u8 优先, 其次官方 resolve_ticket 线路。"""
        if ep_token in self._lines_cache:
            return self._lines_cache[ep_token]

        data = self._signed_fetch(
            "/v1/playback/resolve/" + urllib.parse.quote(ep_token),
            {"view": "compact"})
        lines = data.get("line_options") or []

        def rank(ln):
            direct = 0 if (ln.get("resolved") and
                           ln.get("url_kind") == "m3u8" and
                           (ln.get("url") or "").startswith("http")) else 1
            return (direct, -ln.get("preference_weight", 0))

        lines = sorted(lines, key=rank)
        self._lines_cache[ep_token] = lines
        return lines

    def _check_url(self, url):
        """探测直链是否可用 (部分资源站返回的直链本身是 404 死链)。
        结果缓存 10 分钟。"""
        now = int(time.time())
        if url in self._url_probe_cache:
            ts, ok = self._url_probe_cache[url]
            if now - ts < 600:
                return ok
        ok = False
        try:
            h = {"User-Agent": UA, "Referer": self.site_url + "/"}
            rsp = self.fetch(url, headers=h, timeout=6)
            text = ""
            if hasattr(rsp, "text"):
                text = (rsp.text or "")[:300]
            elif hasattr(rsp, "content"):
                text = rsp.content.decode("utf-8", "ignore")[:300]
            code = getattr(rsp, "status_code", None) or getattr(
                rsp, "status", 0)
            ok = (200 <= int(code or 0) < 400) and \
                ("#EXTM3U" in text or ".m3u8" in url.lower())
        except Exception:
            ok = False
        self._url_probe_cache[url] = (now, ok)
        return ok

    def _pick_line(self, ep_token, flag_idx):
        """按线路序号取线路, 返回 (label, url)。
        - 直链先探测可用性, 死链(404等)自动跳到下一条线路
        - 用户指定线路不可用时兜底到任意可用直链
        - 官方 ticket 线路需登录权益, 失败自动降级"""
        lines = self._resolve_lines(ep_token)
        if not lines:
            return "", ""

        def get_url(ln):
            u = (ln.get("url") or "").strip()
            if ln.get("url_kind") == "resolve_ticket" and u.startswith("resolve://"):
                # 尝试按线路 id 请求官方解析 (需登录权益, 失败则返回空)
                data = self._signed_fetch(
                    "/v1/playback/resolve/" + urllib.parse.quote(ep_token),
                    {"view": "compact", "line": ln.get("id", "")})
                for cur in (data.get("line_options") or []):
                    if cur.get("id") == ln.get("id"):
                        u2 = (cur.get("url") or "").strip()
                        if cur.get("resolved") and u2.startswith("http"):
                            return u2
                return ""
            return u if u.startswith("http") else ""

        # 候选顺序: 用户指定线路优先, 之后按权重顺序扫全部
        order = []
        if isinstance(flag_idx, int) and 0 <= flag_idx < len(lines):
            order.append(flag_idx)
        order += [i for i in range(len(lines)) if i != flag_idx]

        fallback_url = ""   # 未探测过的直链, 万一全部探测失败时兜底
        for i in order:
            ln = lines[i]
            u = get_url(ln)
            if not u:
                continue
            if not fallback_url:
                fallback_url = u
            if self._check_url(u):
                return ln.get("label") or ln.get("provider_id") \
                    or "线路%d" % (i + 1), u
            self.log("  线路死链跳过: %s" % (ln.get("label") or i))

        # 全部探测失败 (网络差等): 返回第一条直链让播放器自行尝试
        if fallback_url:
            ln = lines[order[0]] if order else lines[0]
            return ln.get("label") or "", fallback_url
        return "", ""

    # ===================== TVBox 标准接口 =====================
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        data = self._signed_fetch("/v1/feed/home",
                                  {"scope": "public", "mode": "preview",
                                   "sections": "3", "cards": "10"})
        videos = []
        for section in (data.get("sections") or []):
            videos += self._cards_to_videos(section)
        seen, uniq = set(), []
        for v in videos:
            if v["vod_id"] not in seen:
                seen.add(v["vod_id"])
                uniq.append(v)
        return {"list": uniq}

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

        params = {"kind": tid, "page": page, "limit": PAGE_LIMIT}
        if extend.get("subgenre"):
            params["genre"] = extend["subgenre"]
        if extend.get("genre"):
            params["genre"] = extend["genre"]
        if extend.get("area"):
            params["area"] = extend["area"]
        if extend.get("language"):
            params["language"] = extend["language"]

        # 年份: 官网用 year / year_gte / year_lte 三个参数组合
        year_v = extend.get("year") or ""
        if year_v.startswith("g:"):
            parts = year_v.split(":")
            gte = parts[1] if len(parts) > 1 else ""
            lte = parts[2] if len(parts) > 2 else ""
            cur = time.localtime().tm_year
            if gte:
                params["year_gte"] = gte
            if lte == "CY":
                params["year"] = str(cur)
            elif lte == "PY":
                params["year"] = str(cur - 1)
            elif lte:
                params["year_lte"] = lte
        elif year_v:
            params["year"] = year_v

        params["sort"] = extend.get("sort") or "heat_desc"

        data = self._browse(params)
        videos = self._cards_to_videos(data)
        pagecount = self._pagecount(data, page)

        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": PAGE_LIMIT, "total": pagecount * PAGE_LIMIT,
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        data = self._browse({"q": key, "page": page,
                             "limit": PAGE_LIMIT, "intent": "catalog_search"})
        videos = self._cards_to_videos(data)
        pagecount = self._pagecount(data, page)
        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": PAGE_LIMIT, "total": pagecount * PAGE_LIMIT,
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0])
        self.log("detail: %s" % vod_id[:80])

        cached = self._detail_cache.get(vod_id)
        if cached:
            return {"list": [dict(cached["vod"])]}

        data = self._signed_fetch("/v1/catalog/" + urllib.parse.quote(vod_id))
        if not data or data.get("ERR"):
            return {"list": []}

        name = data.get("title") or vod_id
        pic = data.get("poster_url") or data.get("backdrop_url") \
            or self.default_pic
        year = data.get("year") or ""
        area = data.get("area") or ""
        genres = " ".join(data.get("genres") or [])
        remarks = data.get("remarks") or ""

        content = (data.get("description") or "").strip()
        if content:
            content = INTRO_PREFIX + "\n" + content
        else:
            content = INTRO_PREFIX

        actor = ", ".join(data.get("actors") or [])
        director = ", ".join(data.get("directors") or [])

        # ===== 剧集 (按 offset 分页拉全) =====
        episodes = list(data.get("episodes") or [])
        try:
            ep_pg = data.get("episode_pagination") or {}
            offset = ep_pg.get("offset", 0) + (ep_pg.get("limit") or 0)
            guard = 0
            while ep_pg.get("has_more") and guard < 60:
                more = self._signed_fetch(
                    "/v1/catalog/%s/episodes" % urllib.parse.quote(vod_id),
                    {"limit": ep_pg.get("limit") or 48, "offset": offset})
                batch = more.get("episodes") or []
                if not batch:
                    break
                episodes += batch
                ep_pg = more.get("episode_pagination") or {}
                offset += (ep_pg.get("limit") or 48)
                guard += 1
        except Exception as e:
            self.log("  剧集分页拉取失败: %s" % e)

        # 去重 (主 track 优先)
        seen_tokens, seen_ids = set(), set()
        eps = []
        for ep in episodes:
            tok = ep.get("token") or ""
            eid = ep.get("id") or ""
            if tok and tok in seen_tokens:
                continue
            if eid and eid in seen_ids:
                continue
            if tok:
                seen_tokens.add(tok)
            if eid:
                seen_ids.add(eid)
            eps.append(ep)

        if not eps:
            return {"list": []}

        # ===== 线路分组: 解析首集, 按官网 label 生成 play_from =====
        play_from = []
        play_url = []
        first_token = eps[0].get("token") or eps[0].get("id")
        try:
            lines = self._resolve_lines(first_token)
            for idx, ln in enumerate(lines):
                label = (ln.get("label") or ln.get("provider_id")
                         or "线路%d" % (idx + 1)).strip()
                if label in play_from:
                    label = "%s·%d" % (label, idx + 1)
                ep_names = []
                for i, ep in enumerate(eps):
                    n = (ep.get("display_name")
                         or ep.get("title") or "").strip()
                    if not n:
                        n = "第%d集" % (i + 1)
                    tok = ep.get("token") or ep.get("id")
                    ep_names.append("%s$%s|%d" % (n.replace("$", " "),
                                                  tok, idx))
                play_from.append(label)
                play_url.append("#".join(ep_names))
        except Exception as e:
            self.log("  线路解析失败: %s" % e)

        if not play_from:
            # 彻底兜底: 单线路
            ep_names = []
            for i, ep in enumerate(eps):
                n = (ep.get("display_name") or ep.get("title") or "").strip()
                if not n:
                    n = "第%d集" % (i + 1)
                tok = ep.get("token") or ep.get("id")
                ep_names.append("%s$%s|0" % (n.replace("$", " "), tok))
            play_from = ["搜剧AI"]
            play_url = ["#".join(ep_names)]

        vod_remarks = remarks or ("%d集" % len(eps))
        if year:
            vod_remarks = "%s · %s" % (year, vod_remarks)

        vod = {
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "type_name": genres,
            "vod_year": str(year),
            "vod_area": area,
            "vod_actor": actor,
            "vod_director": director,
            "vod_remarks": vod_remarks,
            "vod_content": content,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url":  "$$$".join(play_url),
        }
        self._detail_cache[vod_id] = {"vod": vod}
        return {"list": [dict(vod)]}

    # -------- 播放 --------
    def playerContent(self, flag, id, vipFlags):
        # id 格式: {episode_token}|{线路序号}
        ep_token = id
        flag_idx = 0
        if "|" in id:
            ep_token, idx = id.rsplit("|", 1)
            try:
                flag_idx = int(idx)
            except Exception:
                flag_idx = 0
        self.log("player: %s line=%d" % (ep_token[:80], flag_idx))

        now = int(time.time())
        cache_key = "%s|%d" % (ep_token, flag_idx)
        if cache_key in self._play_cache:
            ts, res = self._play_cache[cache_key]
            if now - ts < 600:
                return res

        label, url = self._pick_line(ep_token, flag_idx)
        self.log("  线路: %s" % (label or "兜底"))

        if url:
            res = {
                "parse": 0,
                "playUrl": "",
                "url": url,
                "header": {
                    "User-Agent": UA,
                    "Referer": self.site_url + "/",
                },
            }
            self._play_cache[cache_key] = (now, res)
            self.log("  => 直链: %s" % url[:160])
            return res

        # 兜底: 交给 TVBox 嗅探详情页
        res = {"parse": 1, "playUrl": "", "url": self.site_url,
               "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}
        self._play_cache[cache_key] = (now, res)
        return res

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
