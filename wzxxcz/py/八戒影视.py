# -*- coding: utf-8 -*-
"""
八戒影视 Spider（hipy / CatVod 类爬虫框架适配）V3 — 真机字段校准版
已用真实接口 (82.156.118.137:88      http://osstexll.oss-rg-china-mainland.aliyuncs.com/domainPath.json) 逐字段验证:
  - screenType: 树形结构，一级分类(M15电视剧/M16电影/M14短剧/M17动漫/M18综艺/M396动画片)
    children 为筛选组(地区/类型/年份)，叶子 name 即筛选值(如"内地","古装","2025")
  - screenMovie condition: {classify:类型中文名, region:地区中文名,
    sreecnTypeEnum:NEWEST, typeId, year} —— 全部传中文名，组合筛选已验证生效
  - 列表项字段: id / typeId / cover / name / type / desc / year / area / source
  - movieDetails: episodeList[{id,episode,lock}] / moviePlayerList[
    {id,moviePlayerName,episodeTotal}] (如 腾讯 / 4K-YKT)
  - movieDesc: introduce / star(演员!) / director / classify / area / year / score / watch
本资源来源于互联网公开渠道，仅可用于个人学习爬虫技术。
严禁将其用于任何商业用途，下载后请于 24 小时内删除。
"""

import sys
import os
import re
import json
import time
import urllib.parse
import concurrent.futures
from urllib.parse import quote
from typing import Dict, List, Any, Optional, Tuple

sys.path.append('..')

try:
    from base.spider import Spider as _BaseSpider
except ImportError:
    import requests as _rq
    try:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
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

        def post(self, url, data=None, headers=None, **kw):
            timeout = kw.pop('timeout', 15)
            r = self._sess.post(url, data=data, headers=headers,
                                timeout=timeout, **kw)
            r.encoding = 'utf-8'
            return r

        def log(self, *a, **kw):
            try:
                print("[bajie]", *a)
            except Exception:
                pass


# ===================== 常量 =====================
DOMAIN_CFG_URL = ("http://osstexll.oss-rg-china-mainland.aliyuncs.com/"
                  "domainPath.json")

UA_APP = "okhttp/4.12.0"
UA_PLAY = ("Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X) "
           "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0.3 "
           "Mobile/15E148 Safari/604.1")

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

DEVICE_ID = "2d590b9842d064a1"

# 源站筛选树里的脏节点（命名不当/无内容），直接剔除不展示
FILTER_LEAF_BLOCKLIST = {"小日本"}

# 筛选组名 → screenMovie condition 参数名（真机验证）
FILTER_GROUP_KEY = {"地区": "region", "类型": "classify", "年份": "year"}

# 清晰度识别：数值越大越清晰（用于线路排序）
_QUALITY_RULES = (
    (r"4k|2160p|uhd|蓝光4k|原画", 100),
    (r"1080p|fhd|超清|蓝光|bd|bluray", 80),
    (r"720p|hd\b|高清|hdrip", 60),
    (r"480p|sd|标清", 40),
    (r"360p|流畅|极速|省流", 20),
)
_QUALITY_TAG = {100: "4K", 80: "1080P", 60: "720P", 40: "480P", 20: "流畅"}

SHORT_KEYWORDS = ("合集", "短剧", "RO", "分剧", "分集")
SHORT_EP_MAX = 500
NORMAL_EP_MAX = 200
SHORT_EP_THRESHOLD = 80

TTL_HOME = 600
TTL_HOME_VIDEO = 300
TTL_CATEGORY = 120
TTL_SEARCH = 60
TTL_DETAIL = 600
TTL_PROBE = 1800

PAGE_SIZE = 40


class Spider(_BaseSpider):
    host: str = ""
    userid: str = ""
    _cache: Dict = {}

    headers = {
        "User-Agent": UA_APP,
        "Connection": "Keep-Alive",
        "Accept-Encoding": "gzip",
        "Content-Type": "application/json;charset=UTF-8",
        "Cache-Control": "no-cache",
        "token": "",
        "deviceId": DEVICE_ID,
        "client": "app",
        "deviceType": "Android",
    }

    # ---------- 基础 ----------
    def _log(self, *a):
        try:
            print("[bajie]", *a)
        except Exception:
            pass

    def _sg(self, data: Dict, key: str, default: Any = "") -> Any:
        if not isinstance(data, dict):
            return default
        v = data.get(key, default)
        return default if v is None else v

    def _to_int(self, v, default: int = 0) -> int:
        try:
            return int(str(v).strip())
        except Exception:
            return default

    # ---------- 清晰度 ----------
    def _quality_score(self, text: str) -> int:
        if not text:
            return 0
        t = str(text).lower()
        best = 0
        for pattern, score in _QUALITY_RULES:
            if re.search(pattern, t):
                best = max(best, score)
        return best

    def _player_quality(self, pl: Dict) -> Tuple[int, str]:
        """真机字段 moviePlayerName（如 4K-YKT / 腾讯），文本识别清晰度"""
        name = str(self._sg(pl, "moviePlayerName", ""))
        sc = self._quality_score(name)
        return sc, _QUALITY_TAG.get(sc, "")

    def _label_player(self, pl: Dict, used: set,
                      probe: Optional[Dict] = None) -> str:
        base = str(self._sg(pl, "moviePlayerName", "")).strip() or \
            ("线路%s" % pl.get("id", ""))
        res = (probe or {}).get(pl.get("id"))
        if res:
            tag = self._measured_tag(res)
        else:
            tag = self._player_quality(pl)[1]
        if tag and tag.lower() not in base.lower():
            base = "%s [%s]" % (base, tag)
        elif tag and base.lower().startswith("4k") and tag == "标清":
            # 名字吹4K实测标清 → 加实测标签避免误导
            base = "%s [实测%s]" % (base, tag)
        name, i = base, 2
        while name in used:
            name = "%s(%d)" % (base, i)
            i += 1
        used.add(name)
        return name

    # ---------- 实测分辨率（纯Python，不依赖ffprobe） ----------
    def _probe_resolution(self, m3u8_url: str) -> Optional[Tuple[int, int]]:
        """下载首个ts分片，从H.264 SPS解析真实宽高"""
        try:
            t = self._http_get_text(m3u8_url)
            seg = None
            for line in t.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    seg = urllib.parse.urljoin(m3u8_url, line)
                    break
            if not seg:
                return None
            # 分片可能本身是 master 嵌套，跟进一层
            if seg.endswith(".m3u8"):
                return self._probe_resolution(seg)
            return self._sps_from_segment(seg)
        except Exception:
            return None

    def _http_get_text(self, url: str) -> str:
        r = self.fetch(url, headers={"User-Agent": UA_PLAY}, timeout=15)
        if hasattr(r, "text"):
            return r.text or ""
        return (r.content or b"").decode("utf-8", "ignore")

    def _sps_from_segment(self, seg_url: str,
                          max_bytes: int = 1200000) -> Optional[Tuple[int, int]]:
        try:
            try:
                r = self.fetch(seg_url, headers={"User-Agent": UA_PLAY},
                               timeout=20)
            except TypeError:
                r = self.fetch(seg_url, headers={"User-Agent": UA_PLAY})
            data = getattr(r, "content", b"") or b""
            if not data:
                return None
            sps = self._find_sps(data[:max_bytes])
            if not sps:
                return None
            return self._parse_sps(sps)
        except Exception:
            return None

    @staticmethod
    def _find_sps(data: bytes) -> Optional[bytes]:
        for pat in (b"\x00\x00\x00\x01\x67", b"\x00\x00\x01\x67"):
            i = data.find(pat)
            if i >= 0:
                return data[i + len(pat):i + len(pat) + 64]
        return None

    @staticmethod
    def _parse_sps(b: bytes) -> Optional[Tuple[int, int]]:
        """H.264 SPS → (宽,高)，纯位流解析"""
        class _BR:
            __slots__ = ("b", "p")
            def __init__(s, bb): s.b, s.p = bb, 0
            def bit(s):
                v = (s.b[s.p >> 3] >> (7 - (s.p & 7))) & 1
                s.p += 1
                return v
            def bits(s, n):
                v = 0
                for _ in range(n):
                    v = (v << 1) | s.bit()
                return v
            def ue(s):
                z = 0
                while not s.bit():
                    z += 1
                    if z > 32:
                        raise ValueError
                return ((1 << z) - 1 + s.bits(z)) if z else 0
            def se(s):
                v = s.ue()
                return ((-1) ** (v + 1)) * ((v + 1) >> 1) if v else 0

        try:
            r = _BR(b)
            r.bits(8)
            profile = r.bits(8)
            r.bits(8)
            r.bits(8)
            r.ue()
            chroma = 1
            if profile in (100, 110, 122, 244, 44, 83, 86, 118, 128,
                           138, 139, 134, 135):
                chroma = r.ue()
                if chroma == 3:
                    r.bit()
                r.ue()
                r.ue()
                if r.bit():          # scaling_matrix_present
                    cnt = 8 if chroma != 3 else 12
                    for _i in range(cnt):
                        if r.bit():  # scaling_list_present_flag
                            size = 16 if _i < 6 else 64
                            last_scale, next_scale = 8, 8
                            for _ in range(size):
                                if next_scale != 0:
                                    delta = r.se()
                                    next_scale = (last_scale + delta + 256) % 256
                                if next_scale:
                                    last_scale = next_scale
            r.ue()
            poc = r.ue()
            if poc == 0:
                r.ue()
            elif poc == 1:
                r.bit()
                r.ue()
                r.ue()
            r.ue()
            r.bit()
            w = (r.ue() + 1) * 16
            h = (r.ue() + 1) * 16
            if not r.bit():
                r.bit()
            r.bit()
            if r.bit():              # crop
                cl = r.ue(); cr = r.ue(); ct = r.ue(); cb = r.ue()
                if chroma == 0:
                    cu = cv = 2
                elif chroma == 3:
                    cu = cv = 1
                else:
                    cu, cv = 2, 2
                w -= (cl + cr) * cu
                h -= (ct + cb) * cv
            if 16 <= w <= 8192 and 16 <= h <= 8192:
                return int(w), int(h)
            return None
        except Exception:
            return None

    def _probe_lines(self, video_id: str, player_list: List,
                     episode_list: List) -> Dict[Any, Tuple[int, int]]:
        """并发探测各线路真实分辨率，结果缓存30分钟"""
        cache_key = "probe_%s" % video_id
        cached = self._get_cache(cache_key, TTL_PROBE)
        if cached is not None:
            return cached

        ep0 = (episode_list[0].get("id") if episode_list else "") or ""

        def _probe_one(pl):
            try:
                pl_id = pl.get("id")
                if ep0:
                    payload = {"episodeId": str(ep0), "id": video_id,
                               "playerId": str(pl_id), "source": 0,
                               "typeId": "M17", "userId": self.userid}
                else:
                    payload = {"episodeIndex": "0", "id": self._to_int(video_id, 0),
                               "playerId": str(pl_id), "source": 0,
                               "typeId": "M16", "userId": self.userid}
                result = self._api("/api/v1/app/play/movieDetails",
                                   payload=payload)
                if not result:
                    return pl_id, None
                data = result.get("data", {}) or {}
                parse_url = self._sg(data, "url")
                if not parse_url:
                    return pl_id, None
                analysis = self._api(
                    "/api/v1/app/play/analysisMovieUrl?playerUrl=%s&playerId=%s"
                    % (quote(str(parse_url), safe=""), pl_id), method="GET")
                url = (analysis.get("data", "") if analysis else "") or ""
                if isinstance(url, dict):
                    url = url.get("url", "") or ""
                if not str(url).startswith("http"):
                    return pl_id, None
                return pl_id, self._probe_resolution(str(url))
            except Exception:
                return pl.get("id"), None

        out: Dict[Any, Tuple[int, int]] = {}
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
                for pl_id, res in ex.map(_probe_one, player_list or []):
                    out[pl_id] = res
        except Exception as e:
            self._log("probe: 并发探测失败(降级为名称识别): %s" % e)
            out = {}
        self._log("probe: %s" % {k: v for k, v in out.items()})
        self._set_cache(cache_key, out)
        return out

    @staticmethod
    def _measured_tag(res) -> str:
        """实测分辨率 → 标签"""
        if not res:
            return ""
        w = res[0]
        if w >= 3600:
            return "4K"
        if w >= 1900:
            return "1080P"
        if w >= 1200:
            return "720P"
        return "标清"

    def _sorted_players(self, player_list: List, current_id,
                        probe: Optional[Dict] = None) -> List[Dict]:
        """
        排序：实测分辨率 高→低（探测失败沉到已探测线路之后）；
        无实测时按名称清晰度分；当前源在同等条件下优先。
        """
        def _key(pl):
            is_cur = 1 if pl.get("id") == current_id else 0
            if probe:
                res = probe.get(pl.get("id"))
                measured = 1 if res else 0
                w = res[0] if res else 0
                # 有实测的排前（按宽度降序），没实测的按名称分排后
                return (0 if measured else 1, -w,
                        -self._player_quality(pl)[0], -is_cur)
            score, _ = self._player_quality(pl)
            low = 0 if score >= 60 else 1
            return (low, -score, -is_cur)
        return sorted(player_list or [], key=_key)

    # ---------- 列表项 ----------
    def _build_video_item(self, data: Dict) -> Dict:
        """真机字段: id/cover/name/type/desc/year/area"""
        return {
            "vod_id": self._sg(data, "id"),
            "vod_name": self._sg(data, "name", "未知影片"),
            "vod_pic": self._sg(data, "cover", ""),
            # 角标优先用类型（如"都市,剧情"），其次地区
            "vod_remarks": self._sg(data, "type",
                                    self._sg(data, "area", "")),
            "vod_year": self._sg(data, "year", ""),
            "vod_area": self._sg(data, "area", ""),
        }

    # ---------- 请求 ----------
    def _api(self, path: str, payload: Dict = None, method: str = "POST",
             max_retries: int = 3) -> Optional[Dict]:
        url = "%s%s" % (self.host, path)
        for attempt in range(max_retries):
            try:
                if method.upper() == "POST":
                    resp = self.post(url, data=json.dumps(payload)
                                     if payload is not None else None,
                                     headers=self.headers)
                else:
                    resp = self.fetch(url, headers=self.headers)
                if resp.status_code == 200:
                    result = resp.json()
                    code = result.get("code", 200)
                    if code in (200, 0):
                        return result
                    self._log("[API错误] code=%s msg=%s %s"
                              % (code, result.get("msg", ""), path))
                    if attempt < max_retries - 1:
                        time.sleep(1)
                        continue
                    return None
                self._log("[HTTP错误] %s %s" % (resp.status_code, path))
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                return None
            except Exception as e:
                self._log("[请求失败] %d/%d %s: %s"
                          % (attempt + 1, max_retries, path, e))
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                return None
        return None

    def _get_cache(self, key: str, ttl: int = 300):
        if key in self._cache:
            data, ts = self._cache[key]
            if time.time() - ts < ttl:
                return data
            del self._cache[key]
        return None

    def _set_cache(self, key: str, value: Any):
        self._cache[key] = (value, time.time())

    # ---------- 筛选树（真机结构） ----------
    def _build_filters_from_tree(self, tree: List) -> Tuple[List[Dict], Dict]:
        """
        screenType 树 → (classes, filters)
        一级节点 = 分类；其 children = 筛选组(地区/类型/年份)；
        叶子 name 直接作为筛选值传给 screenMovie condition。
        """
        classes: List[Dict] = []
        filters: Dict[str, List[Dict]] = {}

        for node in tree or []:
            tid = str(self._sg(node, "id", ""))
            tname = str(self._sg(node, "name", ""))
            if not tid or not tname:
                continue
            classes.append({"type_id": tid, "type_name": tname})

            flist = []
            children = (node.get("children") or []) if isinstance(node, dict) else []
            for group in children:
                gname = str(self._sg(group, "name", ""))
                gkey = FILTER_GROUP_KEY.get(gname)
                leaves = group.get("children", []) or []
                if not gkey or not leaves:
                    continue
                values = [{"n": "全部", "v": ""}] + [
                    {"n": str(self._sg(leaf, "name")),
                     "v": str(self._sg(leaf, "name"))}
                    for leaf in leaves
                    if self._sg(leaf, "name")
                    and str(self._sg(leaf, "name")) not in FILTER_LEAF_BLOCKLIST
                ]
                flist.append({"key": gkey, "name": gname, "value": values})

            # 排序固定补充（sreecnTypeEnum）
            flist.append({"key": "sreecnTypeEnum", "name": "排序", "value": [
                {"n": "最新上线", "v": "NEWEST"},
                {"n": "最热播放", "v": "HOT"},
                {"n": "评分最高", "v": "SCORE"},
            ]})
            if flist:
                filters[tid] = flist

        return classes, filters

    # ---------- 框架接口 ----------
    def getName(self):
        return "八戒影视"

    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}
        self._cache = {}
        # 可选：外部解析接口（用于爱奇艺网页型片源）
        # ext 配置示例: {"jxapi": "https://your.jx/api/?url="}
        # 返回 JSON: {"code":200/1, "url": "直链m3u8/mp4"}
        self.jxapi = str(self.extend.get("jxapi", "") or "").strip()

        # 1) host（支持 BAJIE_HOST 覆盖）
        cfg_host = os.environ.get("BAJIE_HOST", "").strip()
        if cfg_host:
            self.host = cfg_host.rstrip("/")
            self._log("init: 环境变量 host: %s" % self.host)
        else:
            try:
                resp = self.fetch(DOMAIN_CFG_URL, headers={
                    "User-Agent": UA_APP,
                    "Connection": "Keep-Alive",
                    "Accept-Encoding": "gzip",
                })
                j = resp.json()
                urls = j.get("url") if isinstance(j, dict) else None
                if not urls:
                    raise RuntimeError("domainPath.json 无 url: "
                                       + str(j)[:200])
                self.host = str(urls[0]).rstrip("/")
                self._log("init: 远程 host: %s" % self.host)
            except Exception as e:
                self._log("init: 获取域名失败: %s" % e)
                raise

        # 2) 游客 token
        try:
            resp = self.fetch("%s/api/v1/app/user/visitorInfo" % self.host,
                              headers=self.headers)
            data = resp.json().get("data", {}) or {}
            self.userid = str(data.get("id", "") or "")
            self.headers["token"] = data.get("token", "") or ""
            self._log("init: userid=%s" % self.userid)
        except Exception as e:
            # 降级：拿不到游客身份也先让分类/搜索可用
            self.userid = ""
            self.headers["token"] = ""
            self._log("init: 游客信息失败(降级运行): %s" % e)

    def homeContent(self, filter=False):
        """分类 + 筛选（直接来自 screenType 树，真机验证）"""
        cache_key = "home_content"
        cached = self._get_cache(cache_key, ttl=TTL_HOME)
        if cached:
            return cached

        try:
            result = self._api("/api/v1/app/screen/screenType")
            tree = (result.get("data", []) if result else []) or []
            classes, filters = self._build_filters_from_tree(tree)
            if not classes:
                # 接口返回空/业务码异常 → 静态兜底（分类绝不能空）
                self._log("homeContent: 接口空数据, 使用静态兜底")
                classes, filters = self._fallback_classes()
            self._log("homeContent: %d 分类, %d 分类带筛选"
                      % (len(classes), len(filters)))
            result_data = {"class": classes, "filters": filters}
            self._set_cache(cache_key, result_data)
            return result_data
        except Exception as e:
            self._log("homeContent FAIL: %s (使用静态兜底)" % e)
            classes, filters = self._fallback_classes()
            return {"class": classes, "filters": filters}

    @staticmethod
    def _fallback_classes(self=None):
        """静态分类兜底（真机验证过的6个分类id）"""
        classes = [
            {"type_id": "M15", "type_name": "电视剧"},
            {"type_id": "M14", "type_name": "短剧"},
            {"type_id": "M16", "type_name": "电影"},
            {"type_id": "M17", "type_name": "动漫"},
            {"type_id": "M18", "type_name": "综艺"},
            {"type_id": "M396", "type_name": "动画片"},
        ]
        return classes, {}

    def homeVideoContent(self):
        """首页推荐（并发各板块）"""
        cache_key = "home_video"
        cached = self._get_cache(cache_key, ttl=TTL_HOME_VIDEO)
        if cached:
            return cached

        try:
            result = self._api("/api/v1/app/recommend/recommendList")
            data = (result.get("data", []) if result else []) or []
            videos, seen = [], set()

            def _collect(item_id):
                sub = self._api("/api/v1/app/recommend/recommendSubList",
                                {"condition": item_id, "pageNum": 1,
                                 "pageSize": 6})
                if not sub:
                    return []
                return (sub.get("data", {}) or {}).get("records", []) or []

            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
                futures = {ex.submit(_collect, it["id"]): it["id"]
                           for it in data if self._sg(it, "id")}
                for fut in concurrent.futures.as_completed(futures):
                    try:
                        for v in fut.result():
                            vid = self._sg(v, "id")
                            if vid and vid not in seen:
                                seen.add(vid)
                                videos.append(self._build_video_item(v))
                    except Exception as e:
                        self._log("推荐板块失败: %s" % e)

            self._log("homeVideoContent: %d 条" % len(videos))
            result_data = {"list": videos}
            self._set_cache(cache_key, result_data)
            return result_data
        except Exception as e:
            self._log("homeVideoContent FAIL: %s" % e)
            return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        """
        分类内容。extend 值即筛选叶子中文名（region/classify/year 直接传），
        真机验证: region="内地" classify="古装" year="2025" 组合均生效。
        """
        if isinstance(extend, str):
            try:
                extend = json.loads(extend) if extend else {}
            except Exception:
                extend = {}
        if not isinstance(extend, dict):
            extend = {}
        extend = {k: v for k, v in extend.items()
                  if v not in ("", None, "全部", "不限")}

        page = self._to_int(pg, 1) or 1
        cache_key = "category_%s_%s_%s" % (
            tid, page, json.dumps(extend, sort_keys=True, ensure_ascii=False))
        cached = self._get_cache(cache_key, ttl=TTL_CATEGORY)
        if cached:
            return cached

        try:
            cond = {
                "classify": extend.get("classify", ""),
                "region": extend.get("region", ""),
                "sreecnTypeEnum": extend.get("sreecnTypeEnum", "NEWEST"),
                "typeId": tid,
                "year": extend.get("year", ""),
            }
            result = self._api("/api/v1/app/screen/screenMovie",
                               {"condition": cond, "pageNum": page,
                                "pageSize": PAGE_SIZE})
            if not result:
                return {"list": [], "page": page, "pagecount": 1,
                        "limit": PAGE_SIZE, "total": 0}

            d = result.get("data", {}) or {}
            records = d.get("records", []) or []
            total = self._to_int(d.get("total", 0), 0)
            pagecount = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
            videos = [self._build_video_item(i) for i in records]

            self._log("category: tid=%s pg=%s %s -> %d 条"
                      % (tid, page, cond, len(videos)))
            result_data = {"list": videos, "page": page,
                           "pagecount": pagecount, "limit": PAGE_SIZE,
                           "total": total}
            self._set_cache(cache_key, result_data)
            return result_data
        except Exception as e:
            self._log("categoryContent FAIL (tid=%s): %s" % (tid, e))
            return {"list": [], "page": page, "pagecount": 1,
                    "limit": PAGE_SIZE, "total": 0}

    def searchContent(self, key, quick, pg="1"):
        page = self._to_int(pg, 1) or 1
        cache_key = "search_%s_%s" % (key, page)
        cached = self._get_cache(cache_key, ttl=TTL_SEARCH)
        if cached:
            return cached

        try:
            result = self._api("/api/v1/app/search/searchMovie",
                               {"condition": {"value": key},
                                "pageNum": page, "pageSize": PAGE_SIZE})
            if not result:
                return {"list": [], "page": page}

            d = result.get("data", {}) or {}
            records = d.get("records", []) or []
            total = self._to_int(d.get("total", 0), 0)
            pagecount = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
            videos = [self._build_video_item(i) for i in records]

            self._log("search: '%s' pg=%s -> %d 条" % (key, page, len(videos)))
            result_data = {"list": videos, "page": page,
                           "pagecount": pagecount, "limit": PAGE_SIZE,
                           "total": total}
            self._set_cache(cache_key, result_data)
            return result_data
        except Exception as e:
            self._log("searchContent FAIL: %s" % e)
            return {"list": [], "page": page}

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------- 详情 ----------
    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        video_id = str(ids[0])
        cache_key = "detail_%s" % video_id
        cached = self._get_cache(cache_key, ttl=TTL_DETAIL)
        if cached:
            return cached

        try:
            result = self._api("/api/v1/app/play/movieDetails",
                               {"id": video_id, "source": 0, "typeId": "M17",
                                "userId": self.userid})
            if not result:
                return {"list": []}
            data = result.get("data", {}) or {}
            if not data:
                self._log("detail: %s 无数据" % video_id)
                return {"list": []}

            desc_result = self._api("/api/v1/app/play/movieDesc",
                                    {"id": video_id, "typeId": "M17"})
            d2 = (desc_result.get("data", {}) if desc_result else {}) or {}

            video_detail = self._build_detail_data(video_id, data, d2)
            self._log("detail: %s | 线路: %s"
                      % (video_detail.get("vod_name"),
                         video_detail.get("vod_play_from")))
            result_data = {"list": [video_detail]}
            self._set_cache(cache_key, result_data)
            return result_data
        except Exception as e:
            self._log("detailContent FAIL: %s" % e)
            return {"list": []}

    def _build_detail_data(self, video_id: str, data: Dict,
                           desc_data: Dict) -> Dict:
        """
        真机字段:
          movieDetails: episodeList / moviePlayerList / playerId
          movieDesc: introduce / star(演员) / director / classify /
                     area / year / score / watch
        """
        current_id = data.get("playerId", 0)
        episode_list = data.get("episodeList", []) or []
        player_list = data.get("moviePlayerList", []) or []

        # 实测各线路真实分辨率（并发+缓存，失败自动回退名称识别）
        probe = self._probe_lines(video_id, player_list, episode_list)

        if self._is_short_drama(data, player_list):
            play_urls, show = self._build_short_drama_playlist(
                video_id, player_list, current_id, probe)
        else:
            play_urls, show = self._build_normal_playlist(
                video_id, episode_list, player_list, current_id, probe)

        if not play_urls:
            show = ["默认源"]
            play_urls = ["第1集$1@0@%s@virtual" % video_id]

        # ===== 简介: 仅前缀 + 正文 =====
        # 主演/导演/类型/年份/地区/评分均已写入 vod_actor / vod_director /
        # type_name / vod_year / vod_area / vod_score 独立字段，
        # 详情页头部自行展示，不再重复塞进简介
        intro = str(self._sg(desc_data, "introduce")
                    or self._sg(data, "desc") or "").strip()

        content = (INTRO_PREFIX + "\n" + intro) if intro else INTRO_PREFIX

        # 备注: 实测最高分辨率 + 线路数（探测失败才用名称识别）
        best_tag = ""
        best_w = 0
        for pl in player_list or []:
            res = probe.get(pl.get("id"))
            if res and res[0] > best_w:
                best_w = res[0]
                best_tag = self._measured_tag(res)
        if not best_tag:
            for pl in player_list or []:
                _, tg = self._player_quality(pl)
                if tg:
                    best_tag = tg
                    break
        remarks = ("%s · %d条线路" % (best_tag, len(show))
                   if best_tag else "%d条线路" % len(show))

        return {
            "vod_id": video_id,
            "vod_name": (self._sg(desc_data, "name")
                         or self._sg(data, "name", "未知影片")),
            "vod_pic": (self._sg(desc_data, "cover")
                        or self._sg(data, "cover", "")),
            "vod_content": content,
            "vod_year": (self._sg(desc_data, "year")
                         or self._sg(data, "year", "")),
            "vod_area": (self._sg(desc_data, "area")
                         or self._sg(data, "area", "")),
            "vod_remarks": remarks,
            "vod_score": str(self._sg(desc_data, "score", "")),
            "type_name": (self._sg(desc_data, "classify")
                          or self._sg(data, "type", "")),
            "vod_director": str(self._sg(desc_data, "director", "")),
            "vod_actor": str(self._sg(desc_data, "star", "")),
            "vod_play_from": "$$$".join(show),
            "vod_play_url": "$$$".join(play_urls),
        }

    def _is_short_drama(self, data: Dict, player_list: List) -> bool:
        type_name = str(self._sg(data, "typeName")
                        or self._sg(data, "classify") or "")
        if "短剧" in type_name:
            return True
        for pl in player_list or []:
            if any(kw in str(self._sg(pl, "moviePlayerName", ""))
                   for kw in SHORT_KEYWORDS):
                return True
        for pl in player_list or []:
            if self._to_int(self._sg(pl, "episodeTotal", 0)) \
                    > SHORT_EP_THRESHOLD:
                return True
        return False

    def _build_short_drama_playlist(self, video_id, player_list, current_id,
                                    probe=None) -> Tuple[List[str], List[str]]:
        play_urls, show, used = [], [], set()
        for pl in self._sorted_players(player_list, current_id, probe):
            ep_total = self._to_int(self._sg(pl, "episodeTotal", 0))
            if ep_total <= 0:
                continue
            pu = ["第%d集$%d@%s@%s@virtual" % (ep, ep, pl.get("id"), video_id)
                  for ep in range(1, min(ep_total + 1, SHORT_EP_MAX))]
            if pu:
                play_urls.append("#".join(pu))
                show.append(self._label_player(pl, used, probe))
        return play_urls, show

    def _build_normal_playlist(self, video_id, episode_list, player_list,
                               current_id, probe=None) -> Tuple[List[str], List[str]]:
        """真机 episodeList: [{id, episode:'第1集', lock}]"""
        play_urls, show, used = [], [], set()
        done_ids = set()

        if episode_list:
            # 真实分集：清晰度排序后，逐源尝试匹配 episodeTotal；
            # 第一源用真实分集，其余源虚拟分集
            for pl in self._sorted_players(player_list, current_id, probe):
                pl_id = pl.get("id")
                if pl_id in done_ids:
                    continue
                if not play_urls:
                    # 首个（最清晰/当前）源 → 真实分集
                    pu = ["%s$%s@%s@%s@episode"
                          % (self._sg(ep, "episode", "第%d集" % (i + 1)),
                             video_id, pl_id, self._sg(ep, "id", ""))
                          for i, ep in enumerate(episode_list)]
                    done_ids.add(pl_id)
                else:
                    ep_total = self._to_int(
                        self._sg(pl, "episodeTotal", len(episode_list)))
                    if ep_total <= 0:
                        continue
                    pu = ["第%d集$%d@%s@%s@virtual"
                          % (ep, ep, pl_id, video_id)
                          for ep in range(1, min(ep_total + 1, NORMAL_EP_MAX))]
                    done_ids.add(pl_id)
                if pu:
                    play_urls.append("#".join(pu))
                    show.append(self._label_player(pl, used, probe))
        else:
            for pl in self._sorted_players(player_list, current_id, probe):
                ep_total = self._to_int(self._sg(pl, "episodeTotal", 0))
                if ep_total <= 0:
                    continue
                pu = ["第%d集$%d@%s@%s@virtual" % (ep, ep, pl.get("id"),
                                                video_id)
                      for ep in range(1, min(ep_total + 1, NORMAL_EP_MAX))]
                if pu:
                    play_urls.append("#".join(pu))
                    show.append(self._label_player(pl, used, probe))

        return play_urls, show

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags):
        """id: param@playerid@param2@param3
        virtual → episodeIndex；episode → episodeId（真机验证）"""
        try:
            parts = str(id).split("@")
            if len(parts) < 4:
                self._log("player: 无效ID: %s" % id)
                return self._empty_play()

            param, playerid, param2, param3 = parts[:4]

            if param3 == "virtual":
                payload = {"episodeIndex": str(max(0, self._to_int(param, 1)
                                                   - 1)),
                           "id": self._to_int(param2, 0),
                           "playerId": playerid, "source": 0,
                           "typeId": "M16", "userId": self.userid}
            else:
                payload = {"episodeId": param2, "id": param,
                           "playerId": playerid, "source": 0,
                           "typeId": "M16", "userId": self.userid}

            result = self._api("/api/v1/app/play/movieDetails",
                               payload=payload)
            if not result:
                return self._empty_play()

            data = result.get("data", {}) or {}
            parse_url = self._sg(data, "url")
            playerid = data.get("playerId", playerid)
            if not parse_url:
                self._log("player: 无播放URL")
                return self._empty_play()

            url = self._resolve_play_url(parse_url, playerid)

            # ===== 终极兜底：解析结果是网页而非媒体直链 =====
            # 源站部分片源(爱奇艺等)analysisMovieUrl 解析失败会原样
            # 返回网页地址，parse=0 会导致盒子黑屏 → 交给嗅探
            if url and not self._is_media_url(url):
                # 二次尝试：playerId 转整型再解析一次
                url2 = self._resolve_play_url(
                    parse_url, self._to_int(playerid, playerid))
                if url2 and self._is_media_url(url2):
                    url = url2
                else:
                    page = str(url)
                    # ① 外部解析钩子（extend 配置 jxapi 时启用）
                    if self.jxapi:
                        jx_url = self._try_jx(page)
                        if jx_url:
                            self._log("player: jx解析成功 %s"
                                      % str(jx_url)[:120])
                            return {"jx": "0", "parse": "0",
                                    "url": jx_url,
                                    "header": {"User-Agent": UA_PLAY}}
                    # ② 交给 TVBox 嗅探（需配置里有嗅探/WebView 能力）
                    self._log("player: 非媒体直链, 交给嗅探: %s"
                              % page[:120])
                    return {"jx": "0", "parse": "1", "url": page,
                            "header": {"User-Agent": UA_PLAY}}

            self._log("player: %s" % str(url)[:160])
            return {"jx": "0", "parse": "0", "url": url,
                    "header": {"User-Agent": UA_PLAY}}
        except Exception as e:
            self._log("playerContent FAIL: %s" % e)
            return self._empty_play()

    def _try_jx(self, page: str) -> str:
        """调用外部解析接口，成功返回媒体直链，失败返回空"""
        try:
            resp = self.fetch(self.jxapi + quote(page, safe=""),
                              headers={"User-Agent": UA_PLAY}, timeout=12)
            try:
                j = resp.json()
            except Exception:
                return ""
            url = (j.get("url") or j.get("data", {}).get("url")
                   if isinstance(j.get("data"), dict) else j.get("url")) or ""
            if isinstance(url, dict):
                url = url.get("url", "")
            url = str(url or "")
            return url if self._is_media_url(url) else ""
        except Exception:
            return ""

    def _resolve_play_url(self, parse_url, playerid):
        """调用 analysisMovieUrl 解析真实直链"""
        analysis = self._api(
            "/api/v1/app/play/analysisMovieUrl?playerUrl=%s&playerId=%s"
            % (quote(str(parse_url), safe=""), playerid),
            method="GET")
        url = (analysis.get("data", "") if analysis else "") or ""
        if isinstance(url, dict):
            url = url.get("url", "") or ""
        return url

    @staticmethod
    def _is_media_url(url: str) -> bool:
        u = str(url).lower().split("?")[0]
        return (".m3u8" in u or ".mp4" in u or ".flv" in u
                or ".ts" in u or ".mkv" in u)

    def _empty_play(self):
        return {"jx": "0", "parse": "0", "url": "", "header": {}}

    # ---------- 预留 ----------
    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url or url.startswith("http")

    def manualVideoCheck(self):
        return False

    def destroy(self):
        self._log("destroy")
        try:
            self._cache.clear()
        except Exception:
            pass

    def close(self):
        self.destroy()

    def localProxy(self, param):
        return [200, "image/jpeg", b"", ""]


# ---------- 独立自测 ----------
if __name__ == "__main__":
    print("=" * 66)
    print("八戒影视爬虫 V3 - 真机校准测试")
    print("=" * 66)

    sp = Spider()

    print("\n[1] 初始化...")
    try:
        sp.init()
        print("✅ host=%s userid=%s" % (sp.host, sp.userid))
    except Exception as e:
        print("❌ %s" % e)
        sys.exit(1)

    print("\n[2] 分类+筛选树...")
    try:
        hc = sp.homeContent(True)
        classes = hc.get("class", [])
        filters = hc.get("filters", {})
        print("✅ %d 分类: %s"
              % (len(classes), [(c["type_id"], c["type_name"])
                                for c in classes]))
        tid0 = classes[0]["type_id"] if classes else "M15"
        for f in filters.get(tid0, []):
            print("   %s(%s): %s..."
                  % (f["name"], f["key"],
                     [v["n"] for v in f["value"][:8]]))
    except Exception as e:
        print("❌ %s" % e)

    print("\n[3] 筛选生效验证 (内地+古装+2025)...")
    try:
        r = sp.categoryContent("M15", "1", None,
                               {"region": "内地", "classify": "古装",
                                "year": "2025"})
        for v in r.get("list", [])[:5]:
            print("   %s (%s/%s/%s)"
                  % (v["vod_name"], v["vod_year"], v["vod_area"],
                     v["vod_remarks"]))
        print("   pagecount=%s total=%s"
              % (r.get("pagecount"), r.get("total")))
    except Exception as e:
        print("❌ %s" % e)

    print("\n[4] 搜索'蒸蒸日上'...")
    videos = []
    try:
        videos = sp.searchContent("蒸蒸日上", False, "1").get("list", [])
        print("✅ %d 条" % len(videos))
    except Exception as e:
        print("❌ %s" % e)

    if videos:
        print("\n[5] 详情（前缀/元信息/清晰度线路）...")
        try:
            d = sp.detailContent([videos[0]["vod_id"]])["list"][0]
            print("   名称: %s  评分: %s" % (d["vod_name"], d["vod_score"]))
            print("   年份:%s 地区:%s 类型:%s"
                  % (d["vod_year"], d["vod_area"], d["type_name"]))
            print("   导演: %s" % d.get("vod_director"))
            print("   演员: %s" % d.get("vod_actor"))
            print("   备注: %s" % d.get("vod_remarks"))
            print("   简介:")
            for line in d["vod_content"].split("\n"):
                print("     | %s" % line[:70])
            print("   线路:")
            urls = d["vod_play_url"].split("$$$")
            for i, name in enumerate(d["vod_play_from"].split("$$$")):
                print("     %d. %-24s %d集"
                      % (i + 1, name, len(urls[i].split("#"))))
        except Exception as e:
            print("❌ %s" % e)

    print("\n" + "=" * 66)
    print("测试完成")
    print("=" * 66)
