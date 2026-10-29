# coding=utf-8
"""
创享影视 ys.cxkjg.cn | TVBox Python 爬虫 
关键:
  - 站点官方自带采集接口 /api/provide/vod (苹果CMS V10 标准协议)
  - 分类 / 筛选 / 搜索 / 分页 全部走该接口，字段与网站完全一致
  - 播放地址为 m3u8 直链，直接返回 parse=0 交给播放器
  - 兼容短剧（单集/全集完结）与多线路剧集
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
                print("[cxkjg]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://ys.cxkjg.cn"
API = HOST + "/api/provide/vod"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/api/upload/pic/poster/4d29184ceecbf8eb.png"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# 分类（type_id 与网站导航 / 接口 class 完全一致）
CLASSES = [
    {"type_id": "1",  "type_name": "电视剧"},
    {"type_id": "9",  "type_name": "电影"},
    {"type_id": "19", "type_name": "记录片"},
    {"type_id": "20", "type_name": "动漫"},
    {"type_id": "26", "type_name": "综艺"},
    {"type_id": "31", "type_name": "体育赛事"},
    {"type_id": "36", "type_name": "短剧"},
    {"type_id": "43", "type_name": "现代都市"},
    {"type_id": "44", "type_name": "穿越年代"},
]

_SORTS = [
    {"n": "最近更新", "v": "update_stamp"},
    {"n": "人气",      "v": "hits"},
    {"n": "评分",      "v": "score"},
    {"n": "时间",      "v": "year"},
]

_YEARS = [{"n": "全部", "v": ""}] + \
         [{"n": str(y), "v": str(y)} for y in range(2026, 1999, -1)]

# 各分类的「类型」子分类（接口 filters 的 cid 值，已逐一核验）
_CID_MAP = {
    "1":  [("全部", ""), ("欧美剧", "2"), ("香港剧", "3"), ("韩剧", "4"),
           ("日剧", "5"), ("马泰剧", "6"), ("内地剧", "7"), ("台湾剧", "8")],
    "9":  [("全部", ""), ("动作片", "11"), ("爱情片", "12"), ("喜剧片", "13"),
           ("科幻片", "14"), ("恐怖片", "15"), ("剧情片", "16"),
           ("战争片", "17"), ("预告片", "18")],
    "19": [],
    "20": [("全部", ""), ("动画片", "21"), ("中国动漫", "22"),
           ("日本动漫", "23"), ("欧美动漫", "24"), ("AI漫剧", "25")],
    "26": [("全部", ""), ("大陆综艺", "27"), ("日韩综艺", "28"),
           ("港台综艺", "29"), ("欧美综艺", "30")],
    "31": [("全部", ""), ("足球", "32"), ("篮球", "33"),
           ("台球", "34"), ("其他赛事", "35")],
    "36": [("全部", ""), ("古装仙侠", "37"), ("言情总裁", "38"),
           ("重生民国", "39"), ("反转爽剧", "40"), ("脑洞悬疑", "41")],
    "43": [],
    "44": [],
}

# 地区（兜底用；正常以接口 filters 为准）
_AREAS = [
    {"n": "全部", "v": ""},
    {"n": "中国大陆", "v": "中国大陆"}, {"n": "中国香港", "v": "香港"},
    {"n": "中国台湾", "v": "台湾"},     {"n": "美国",    "v": "美国"},
    {"n": "日本",    "v": "日本"},     {"n": "韩国",    "v": "韩国"},
    {"n": "英国",    "v": "英国"},     {"n": "法国",    "v": "法国"},
    {"n": "德国",    "v": "德国"},     {"n": "意大利",  "v": "意大利"},
    {"n": "泰国",    "v": "泰国"},     {"n": "印度",    "v": "印度"},
    {"n": "加拿大",  "v": "加拿大"},   {"n": "其他",    "v": "__others__"},
]

# 语言（兜底用；正常以接口 filters 为准）
_LANGS = [
    {"n": "全部", "v": ""},
    {"n": "国语",     "v": "国语"},
    {"n": "普通话",   "v": "普通话"},
    {"n": "英语",     "v": "英语"},
    {"n": "日语",     "v": "日语"},
    {"n": "韩语",     "v": "韩语"},
    {"n": "粤语",     "v": "粤语"},
    {"n": "泰语",     "v": "泰语"},
    {"n": "其他",     "v": "__others__"},
]


def _build_filters():
    out = {}
    for c in CLASSES:
        tid = c["type_id"]
        item = []
        cids = _CID_MAP.get(tid) or []
        if len(cids) > 1:
            item.append({
                "key": "cid", "name": "类型",
                "value": [{"n": n, "v": v} for n, v in cids],
            })
        item.append({"key": "area", "name": "地区", "value": _AREAS})
        item.append({"key": "language", "name": "语言", "value": _LANGS})
        item.append({"key": "year", "name": "年份", "value": _YEARS})
        item.append({"key": "sort", "name": "排序", "value": _SORTS})
        out[tid] = item
    return out


FILTERS = _build_filters()

# ===================== 正则 =====================
_RE_TAG = re.compile(r"<[^>]+>")
_RE_BR = re.compile(r"<br\s*/?>", re.I)
_RE_SEP = re.compile(r"[ \t\r\f\v]+")
_RE_MULTI_NL = re.compile(r"\n{2,}")
_RE_YEAR_SUFFIX = re.compile(r"\s*[\(（]\d{4}[\)）]\s*$")


class Spider(Spider):

    def getName(self):
        return "创享影视"

    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}

        self.site_url = (self.extend.get("site") or HOST).rstrip("/")
        self.api_url = self.extend.get("api") or (self.site_url + "/api/provide/vod")
        self.headers = {
            "User-Agent": UA,
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": self.site_url + "/",
        }
        self.default_pic = DEFAULT_PIC
        self._play_cache = {}
        self._cur_vid = ""
        self.log("init: site=%s api=%s" % (self.site_url, self.api_url))

    # ------------------------------------------------------------------
    # 基础请求
    # ------------------------------------------------------------------
    def _fetch_text(self, url, timeout=20):
        try:
            rsp = self.fetch(url, headers=self.headers, timeout=timeout)
            if hasattr(rsp, "text"):
                return rsp.text or ""
            if hasattr(rsp, "content"):
                return rsp.content.decode("utf-8", "ignore")
            return str(rsp)
        except Exception as e:
            self.log("fetch FAIL %s -> %s" % (url[:120], e))
            return ""

    def _get_json(self, params, timeout=20, retry=2):
        """请求官方采集接口，返回 dict（失败返回空 dict）。带重试，抗偶发超时。"""
        url = self.api_url + "?" + urllib.parse.urlencode(params)
        self.log("api: %s" % url[:220])

        for attempt in range(retry + 1):
            text = self._fetch_text(url, timeout=timeout)
            if not text:
                if attempt < retry:
                    self.log("  接口无响应，重试 %d/%d" % (attempt + 1, retry))
                    time.sleep(0.4 * (attempt + 1))
                    continue
                return {}

            text = text.strip()
            # 兼容 JSONP 包裹
            if text.startswith("/**/"):
                text = text[4:]
            if not text.startswith("{"):
                i, j = text.find("{"), text.rfind("}")
                if i >= 0 and j > i:
                    text = text[i:j + 1]
            try:
                data = json.loads(text)
                return data if isinstance(data, dict) else {}
            except Exception as e:
                self.log("json FAIL: %s | head=%s" % (e, text[:120]))
                if attempt < retry:
                    time.sleep(0.4 * (attempt + 1))
                    continue
                return {}
        return {}

    # ------------------------------------------------------------------
    # 工具
    # ------------------------------------------------------------------
    def _fix_url(self, url):
        if not url:
            return ""
        url = str(url).strip().replace("\\/", "/")
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
        s = str(s)
        s = _RE_BR.sub("\n", s)
        s = _RE_TAG.sub("", s)
        s = (s.replace("&nbsp;", " ").replace("\xa0", " ")
              .replace("&amp;", "&").replace("&quot;", '"')
              .replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">"))
        s = _RE_SEP.sub(" ", s)
        s = _RE_MULTI_NL.sub("\n", s)
        return s.strip()

    def _pic(self, url):
        pic = self._fix_url(url)
        return pic or self.default_pic

    # ------------------------------------------------------------------
    # 列表项 -> TVBox 标准 vod
    # ------------------------------------------------------------------
    def _vod_item(self, it):
        return {
            "vod_id":      it.get("vod_id"),
            "vod_name":    self._clean(it.get("vod_name"))[:120],
            "vod_pic":     self._pic(it.get("vod_pic")),
            "vod_remarks": self._clean(it.get("vod_remarks")),
            "vod_year":    self._clean(it.get("vod_year")),
            "vod_area":    self._clean(it.get("vod_area")),
            "vod_actor":   self._clean(it.get("vod_actor")),
            "vod_director": self._clean(it.get("vod_director")),
            "type_name":   self._clean(it.get("type_name")),
        }

    def _build_content(self, it):
        """简介：统一加前缀，网站字段优先，其次兜底拼接"""
        content = self._clean(it.get("vod_content"))
        if not content:
            content = self._clean(it.get("vod_blurb"))
        if not content:
            parts = []
            if it.get("vod_name"):
                parts.append("片名：%s" % self._clean(it.get("vod_name")))
            if it.get("type_name"):
                parts.append("类型：%s" % self._clean(it.get("type_name")))
            if it.get("vod_area"):
                parts.append("地区：%s" % self._clean(it.get("vod_area")))
            if it.get("vod_year"):
                parts.append("年份：%s" % self._clean(it.get("vod_year")))
            if it.get("vod_lang"):
                parts.append("语言：%s" % self._clean(it.get("vod_lang")))
            if it.get("vod_director"):
                parts.append("导演：%s" % self._clean(it.get("vod_director")))
            if it.get("vod_actor"):
                parts.append("主演：%s" % self._clean(it.get("vod_actor")))
            content = "\n".join(parts) if parts else "暂无简介，点击查看更多精彩内容..."
        return INTRO_PREFIX + "\n" + content

    # ------------------------------------------------------------------
    # 首页
    # ------------------------------------------------------------------
    def homeContent(self, filter=False):
        # 分类以接口 class 为准，失败时回落内置表
        data = self._get_json({"ac": "list"})
        classes = []
        for c in (data.get("class") or []):
            tid = c.get("type_id")
            name = c.get("type_name")
            if tid is None or not name:
                continue
            classes.append({"type_id": str(tid), "type_name": self._clean(name)})
        if not classes:
            classes = CLASSES

        filters = FILTERS
        remote = data.get("filters") or {}
        if remote:
            merged = {}
            for c in classes:
                tid = c["type_id"]
                if tid in remote:
                    merged[tid] = self._norm_filters(remote[tid])
                elif tid in FILTERS:
                    merged[tid] = FILTERS[tid]
            if merged:
                filters = merged

        return {"class": classes, "filters": filters}

    # 地区/语言的合法白名单（过滤网站采集源串入的非法值）
    _OK_AREA = (
        "全部", "中国大陆", "大陆", "内地", "中国", "香港", "中国香港",
        "台湾", "中国台湾", "澳门", "中国澳门", "美国", "日本", "韩国",
        "英国", "法国", "德国", "意大利", "西班牙", "葡萄牙", "俄罗斯",
        "加拿大", "澳大利亚", "新西兰", "印度", "泰国", "新加坡",
        "马来西亚", "越南", "菲律宾", "印度尼西亚", "土耳其", "以色列",
        "伊朗", "伊拉克", "南非", "埃及", "巴西", "阿根廷", "墨西哥",
        "瑞典", "挪威", "丹麦", "芬兰", "荷兰", "比利时", "瑞士",
        "奥地利", "波兰", "捷克", "匈牙利", "希腊", "乌克兰", "爱尔兰",
        "冰岛", "哥伦比亚", "智利", "秘鲁", "古巴", "巴基斯坦",
        "孟加拉国", "斯里兰卡", "尼泊尔", "柬埔寨", "缅甸", "老挝",
        "蒙古", "哈萨克斯坦", "阿联酋", "沙特阿拉伯", "卡塔尔",
        "科威特", "叙利亚", "黎巴嫩", "约旦", "巴勒斯坦", "阿富汗",
        "其他", "其它",
    )

    _OK_LANG = (
        "全部", "国语", "普通话", "汉语普通话", "中文", "英文", "英语",
        "粤语", "台语", "沪语", "日语", "韩语", "泰语", "法语", "德语",
        "意大利语", "西班牙语", "葡萄牙语", "俄语", "乌克兰语",
        "希腊语", "芬兰语", "印地语", "印度语", "他加禄语",
        "塔加拉族语", "四川方言", "云南方言", "其他", "其它",
    )

    # 采集源脏数据特征：把「集数/完结状态/会员字样/片段」误写进了地区或语言
    _DIRTY_WORDS = ("全集", "完结", "集】", "会员", "找打了", "核动力",
                    "电科", "主管", "知道了", "普通版", "了】", "··", "【")

    @classmethod
    def _valid_option(cls, key, name):
        """校验筛选项名称是否合法（剔除采集源串入的脏值）"""
        if not name:
            return False
        if any(w in name for w in cls._DIRTY_WORDS):
            return False
        if key == "area":
            return name in cls._OK_AREA
        if key == "language":
            return name in cls._OK_LANG
        return True

    def _norm_filters(self, raw):
        """接口 filters -> TVBox filters，剔除采集源串入的脏值"""
        out = []
        for f in raw or []:
            key = f.get("key")
            if key not in ("cid", "area", "language", "year", "sort", "class"):
                continue

            vals = []
            seen = set()
            for v in (f.get("value") or []):
                n, vv = v.get("n"), v.get("v", "")
                if n is None:
                    continue
                n = self._clean(n)
                vv = "" if vv is None else str(vv)
                if not n or vv in seen:
                    continue
                # 地区/语言：过滤采集源串入的非法值（集数、会员、完结状态等）
                if not self._valid_option(key, n):
                    continue
                seen.add(vv)
                vals.append({"n": n, "v": vv})

            if not vals:
                continue

            # 排序不需要「全部」，其余下拉补一个「全部」
            if key != "sort" and vals[0]["v"] != "":
                vals.insert(0, {"n": "全部", "v": ""})

            out.append({"key": key, "name": self._clean(f.get("name") or key),
                        "value": vals})
        return out

    def homeVideoContent(self):
        data = self._get_json({
            "ac": "detail", "t": "1", "pg": "1",
            "sort": "update_stamp", "pagesize": "30",
        })
        videos = [self._vod_item(it) for it in (data.get("list") or [])]
        return {"list": videos}

    # ------------------------------------------------------------------
    # 分类
    # ------------------------------------------------------------------
    def categoryContent(self, tid, pg, filter, extend):
        page = 1
        try:
            page = int(pg) if pg else 1
        except Exception:
            page = 1

        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        if not isinstance(extend, dict):
            extend = {}
        extend = dict(extend)

        for k in list(extend.keys()):
            if extend[k] in ("", None, "全部", "全部地区", "全部语言"):
                del extend[k]

        params = {
            "ac": "detail",
            "t": str(tid),
            "pg": str(page),
            "pagesize": "20",
            "sort": str(extend.get("sort") or "update_stamp"),
        }
        # 子分类：cid 优先，其次 class/类型名
        cid = extend.get("cid") or extend.get("class") or extend.get("type")
        if cid:
            params["cid"] = str(cid)
        if extend.get("area"):
            params["area"] = str(extend["area"])
        if extend.get("language"):
            params["language"] = str(extend["language"])

        # 年份：接口仅在 year 为数字串时过滤，数字串曾被验证会返回空，
        # 因此仅在确有必要时带上；若过滤后为空则回退到不带年份重取。
        year = extend.get("year")
        if year:
            params["year"] = str(year)

        data = self._get_json(params)
        items = data.get("list") or []

        if not items and year:
            self.log("  year=%s 无结果，回退不带年份" % year)
            params.pop("year", None)
            data = self._get_json(params)
            items = data.get("list") or []

        videos = [self._vod_item(it) for it in items]

        try:
            pagecount = int(data.get("pagecount") or 1)
        except Exception:
            pagecount = 1
        try:
            total = int(data.get("total") or 0)
        except Exception:
            total = 0

        if pagecount < page:
            pagecount = page
        if not total:
            total = pagecount * 20

        self.log("  => %d 条, 第 %d/%d 页, 共 %d" % (len(videos), page, pagecount, total))

        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": 20,
            "total": total,
        }

    # ------------------------------------------------------------------
    # 搜索
    # ------------------------------------------------------------------
    def searchContent(self, key, quick, pg="1"):
        page = 1
        try:
            page = int(pg) if pg else 1
        except Exception:
            page = 1

        data = self._get_json({
            "ac": "detail",
            "wd": str(key),
            "pg": str(page),
            "pagesize": "20",
        })
        videos = [self._vod_item(it) for it in (data.get("list") or [])]

        try:
            pagecount = int(data.get("pagecount") or 1)
        except Exception:
            pagecount = 1
        try:
            total = int(data.get("total") or 0)
        except Exception:
            total = 0
        if pagecount < page:
            pagecount = page
        if not total:
            total = len(videos)

        self.log("  搜索[%s] => %d 条" % (key, len(videos)))
        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": 20,
            "total": total,
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ------------------------------------------------------------------
    # 详情
    # ------------------------------------------------------------------
    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0]).strip()
        m = re.search(r"(\d{1,10})", vod_id)
        if m:
            vod_id = m.group(1)
        self.log("detail: id=%s" % vod_id)
        # 记录当前影片，供播放失败时回查其它线路
        self._cur_vid = vod_id

        data = self._get_json({"ac": "detail", "ids": vod_id})
        items = data.get("list") or []
        if not items:
            return {"list": []}
        it = items[0]

        name = self._clean(it.get("vod_name"))
        name = _RE_YEAR_SUFFIX.sub("", name).strip() or vod_id

        # ---- 线路与剧集 ----
        play_from = []
        play_url = []

        froms = [x for x in str(it.get("vod_play_from") or "").split("$$$")]
        urls = [x for x in str(it.get("vod_play_url") or "").split("$$$")]

        for i, url_group in enumerate(urls):
            flag = froms[i].strip() if i < len(froms) else ""
            flag = self._clean(flag) or ("线路%d" % (i + 1))

            eps = []
            for seg in str(url_group).split("#"):
                seg = seg.strip()
                if not seg:
                    continue
                if "$" in seg:
                    ep_name, ep_url = seg.split("$", 1)
                else:
                    ep_name, ep_url = "第%d集" % (len(eps) + 1), seg
                ep_name = self._clean(ep_name) or ("第%d集" % (len(eps) + 1))
                ep_url = self._fix_url(ep_url.strip())
                if not ep_url:
                    continue
                eps.append("%s$%s" % (ep_name, ep_url))

            if not eps:
                continue
            play_from.append(flag)
            play_url.append("#".join(eps))

        self.log("  线路: %d, 剧集: %s" % (len(play_from), [len(x.split("#")) for x in play_url]))

        if not play_from:
            return {"list": []}

        remarks = self._clean(it.get("vod_remarks"))
        if not remarks:
            remarks = "%d条线路" % len(play_from)

        return {"list": [{
            "vod_id":        vod_id,
            "vod_name":      name,
            "vod_pic":       self._pic(it.get("vod_pic")),
            "type_name":     self._clean(it.get("type_name")),
            "vod_year":      self._clean(it.get("vod_year")),
            "vod_area":      self._clean(it.get("vod_area")),
            "vod_lang":      self._clean(it.get("vod_lang")),
            "vod_remarks":   remarks,
            "vod_actor":     self._clean(it.get("vod_actor")),
            "vod_director":  self._clean(it.get("vod_director")),
            "vod_content":   self._build_content(it),
            "vod_score":     self._clean(it.get("vod_score")),
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url":  "$$$".join(play_url),
        }]}

    # ------------------------------------------------------------------
    # 播放
    # ------------------------------------------------------------------
    def playerContent(self, flag, id, vipFlags):
        play_url = str(id or "").strip()
        if not play_url:
            return {"parse": 1, "playUrl": "", "url": "", "header": {}}

        play_url = self._fix_url(play_url)
        self.log("player[%s]: %s" % (flag, play_url[:160]))

        now = int(time.time())
        if play_url in self._play_cache:
            item = self._play_cache[play_url]
            ts, res = item[0], item[1]
            alive = item[2] if len(item) > 2 else True
            # 只复用「确认可用」的缓存；死线路每次重探，避免源站恢复后仍播旧结果
            if alive and now - ts < 600:
                return res

        header = {
            "User-Agent": UA,
            "Referer": self.site_url + "/",
        }

        # 站点自带 ts-proxy 解出的直链
        if "/ts-proxy/" in play_url:
            play_url = self._unwrap_proxy(play_url)

        low = play_url.lower()
        if not (".m3u8" in low or ".mp4" in low or ".flv" in low):
            # 其它（如需解析的网页地址）交给 TVBox 嗅探
            res = {"parse": 1, "playUrl": "", "url": play_url, "header": header}
            self._play_cache[play_url] = (now, res, False)
            return res

        # ---- 播放前探活：死线路/坏分片直接换可用线路 ----
        final_url, final_header, alive = self._resolve_playable(flag, play_url, header)

        res = {
            "parse": 0,
            "playUrl": "",
            "url": final_url,
            "header": final_header,
        }
        # 死线路不缓存，下次还能重新探测（源站可能恢复）
        self._play_cache[play_url] = (now, res, alive)
        if final_url != play_url:
            self._play_cache[final_url] = (now, res, True)
        return res

    # ---------------- 探活 & 容错 ----------------

    def _http_probe(self, url, timeout=8, headers=None, want_body=True, max_bytes=262144):
        """
        返回 (status_code, body_text)。
        want_body=True 时尽量读完（m3u8 文本通常几十 KB），最多 max_bytes；
        want_body=False 时只要状态码（探 ts 分片用，省流量）。
        """
        h = {
            "User-Agent": UA,
            "Accept": "*/*",
        }
        if headers:
            h.update(headers)
        try:
            try:
                rsp = self.fetch(url, headers=h, timeout=timeout, stream=want_body)
            except TypeError:
                # 部分 TVBox 内核的 fetch 不支持 stream 参数
                rsp = self.fetch(url, headers=h, timeout=timeout)
            code = getattr(rsp, "status_code", 0) or 0

            if not want_body:
                # 只取状态码；顺手关闭连接
                try:
                    if hasattr(rsp, "close"):
                        rsp.close()
                except Exception:
                    pass
                return code, ""

            body = ""
            try:
                if hasattr(rsp, "raw") and hasattr(rsp.raw, "read"):
                    buf = b""
                    while len(buf) < max_bytes:
                        chunk = rsp.raw.read(16384)
                        if not chunk:
                            break
                        buf += chunk
                        # m3u8 已完整（有分片行）就没必要继续
                        if b"#EXTINF" in buf and len(buf) > 2048:
                            break
                    body = buf.decode("utf-8", "ignore") if isinstance(buf, bytes) else str(buf)
            except Exception:
                body = ""
            if not body and hasattr(rsp, "text"):
                body = (rsp.text or "")[:max_bytes]
            return code, body
        except Exception as e:
            self.log("  probe fail %s -> %s" % (url[:80], e))
            return 0, ""

    def _m3u8_alive(self, url, timeout=8, headers=None):
        """
        判断一个 m3u8 是否可播：
          1) HTTP 200 且含 #EXTM3U
          2) 若是 master，取第一个子列表再判
          3) 取第一个真实分片（跳过广告占位 ts1.*.com/index*.ts 之类）探活
        返回 (ok, 可能需要替换的 url)
        """
        code, body = self._http_probe(url, timeout=timeout, headers=headers)
        if code != 200 or "#EXTM3U" not in body:
            return False, url

        # 统一换行，去掉 \r
        body = body.replace("\r\n", "\n").replace("\r", "\n")
        lines = [x.strip() for x in body.split("\n") if x.strip()]

        # master 列表：取第一个子 m3u8（带宽最高/首个）
        sub = ""
        for i, ln in enumerate(lines):
            if ln.startswith("#EXT-X-STREAM-INF"):
                if i + 1 < len(lines):
                    sub = lines[i + 1]
                break
        if sub:
            sub_full = self._abs_url(sub, url)
            ok, _ = self._m3u8_alive(sub_full, timeout=timeout, headers=headers)
            # 子列表能通即认为原 master 地址可播，保留原地址不动
            return ok, url

        # media 列表：找第一个有效分片
        segs = [ln for ln in lines if not ln.startswith("#")]
        if not segs:
            return False, url

        # 樱花等线路首片是广告占位死链，跳过它继续往后试
        for seg in segs[:5]:
            full = self._abs_url(seg, url)
            if self._is_ad_segment(full):
                self.log("  跳过广告占位分片: %s" % full[:80])
                continue
            c, _ = self._http_probe(full, timeout=timeout, headers=headers,
                                    want_body=False)
            if c == 200:
                return True, url
        return False, url

    def _is_ad_segment(self, url):
        """识别广告占位分片：ts1.xxx.com/index2.ts 这类无集数特征的地址"""
        m = re.search(r"^https?://([^/]+)/(index\d*\.ts)$", url, re.I)
        return bool(m)

    def _abs_url(self, sub, base):
        """
        把 m3u8 里的相对地址解析成绝对地址。
        base 视为「目录」(以 / 结尾) 或「文件」(自动取其目录)。
        """
        sub = (sub or "").strip().strip('\r\n\t ')
        if not sub:
            return ""
        if sub.startswith("http://") or sub.startswith("https://"):
            return sub
        if sub.startswith("//"):
            return "https:" + sub

        # base 若是文件路径，先取目录
        b = base.strip()
        if not b.endswith("/"):
            b = b.rsplit("/", 1)[0] + "/"

        if sub.startswith("/"):
            m = re.match(r"(https?://[^/]+)", b)
            return (m.group(1) if m else "") + sub

        # 处理 ../ 与 ./
        parts = b.split("/")
        scheme_host = "/".join(parts[:3])          # https://host
        dir_parts = parts[3:]                      # 域名后的目录段
        if dir_parts and dir_parts[-1] == "":
            dir_parts = dir_parts[:-1]

        for seg in sub.split("/"):
            if seg == "" or seg == ".":
                continue
            if seg == "..":
                if dir_parts:
                    dir_parts.pop()
            else:
                dir_parts.append(seg)

        return scheme_host + "/" + "/".join(dir_parts)

    def _resolve_playable(self, flag, play_url, header):
        """
        先探当前线路；不通则回到详情里找同片其它线路，按顺序试到可用为止。
        返回 (url, header, alive)
        """
        ok, url = self._m3u8_alive(play_url, headers=header)
        if ok:
            return url, header, True

        self.log("  ⚠ 当前线路不可用，尝试切换到其它线路...")

        alt = self._find_alt_episode(flag, play_url)
        if alt:
            for f, u in alt:
                if u == play_url:
                    continue
                ok2, u2 = self._m3u8_alive(u, headers={"User-Agent": UA,
                                                       "Referer": self.site_url + "/"})
                if ok2:
                    self.log("  ✓ 切换线路 [%s] 可用: %s" % (f, u2[:120]))
                    return u2, {"User-Agent": UA, "Referer": self.site_url + "/"}, True

        self.log("  未找到其它可用线路，原样返回")
        return play_url, header, False

    def _find_alt_episode(self, flag, play_url):
        """根据当前播放地址，反查同片同集在其它线路的地址"""
        try:
            vid = self._cur_vid
        except Exception:
            vid = ""
        if not vid:
            return []

        data = self._get_json({"ac": "detail", "ids": str(vid)})
        items = data.get("list") or []
        if not items:
            return []
        it = items[0]

        # 定位当前是第几集
        ep_index = -1
        ep_name = ""
        froms = str(it.get("vod_play_from") or "").split("$$$")
        groups = str(it.get("vod_play_url") or "").split("$$$")
        for g in groups:
            for i, seg in enumerate(g.split("#")):
                if "$" in seg:
                    n, u = seg.split("$", 1)
                else:
                    n, u = "", seg
                if self._fix_url(u.strip()) == play_url:
                    ep_index = i
                    ep_name = n
                    break
            if ep_index >= 0:
                break

        if ep_index < 0:
            return []

        out = []
        for i, g in enumerate(groups):
            f = froms[i] if i < len(froms) else ("线路%d" % (i + 1))
            segs = g.split("#")
            if ep_index < len(segs):
                seg = segs[ep_index]
                u = seg.split("$", 1)[1] if "$" in seg else seg
                out.append((f, self._fix_url(u.strip())))
        return out

    def _unwrap_proxy(self, url):
        """把 /ts-proxy/host/443/path 还原成 https://host/path"""
        try:
            m = re.search(r"/ts-proxy/([^/]+)/(\d+)/(.*)$", url)
            if not m:
                return url
            host, port, path = m.group(1), m.group(2), m.group(3)
            scheme = "https" if port in ("443", "") else "http"
            out = "%s://%s/%s" % (scheme, host, path)
            self.log("  ts-proxy -> %s" % out[:160])
            return out
        except Exception:
            return url

    # ------------------------------------------------------------------
    # 其它
    # ------------------------------------------------------------------
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
        u = str(url or "").lower()
        return ".m3u8" in u or ".mp4" in u or ".flv" in u

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()
