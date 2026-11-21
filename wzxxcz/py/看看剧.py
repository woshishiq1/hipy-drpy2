# coding=utf-8
"""
看看剧 kkju.app (kankanju.app) | TVBox Python 爬虫

站点形态：Vue SPA，数据走后端 REST API（baseURL /api/app）。
安全校验：每个请求带 X-Device-ID / X-Platform / X-Timestamp / X-Nonce /
X-Signature / X-App-Version 头，签名为双层 HMAC-SHA256：
  1) deriveKey = HMAC_SHA256(salt, deviceId).hexdigest()
  2) signature = HMAC_SHA256(deriveKey(utf8), signingString).hexdigest()
  signingString = method \n path \n sortedQuery \n timestamp \n nonce \n appVersion \n [bodyHash]
  bodyHash = SHA256(body 文本).hexdigest()（仅非 GET）。

播放链路：详情 /videos/{id} 返回 playGroups[]（线路）→ playUrls[]（选集）；
真正直链由 POST /play/token {videoId, episode(0基), groupCode} 换取
data.playUrl（m3u8/mp4）、data.format、data.headers。
"""
import re
import sys
import json
import time
import hmac
import hashlib
import uuid
import urllib.parse

sys.path.append('..')

try:
    import requests as _requests
    try:
        import urllib3
        urllib3.disable_warnings()
    except Exception:
        pass
except ImportError:
    _requests = None

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

        def fetch(self, url, params=None, cookies=None, headers=None,
                  timeout=5, verify=True, stream=False, allow_redirects=True):
            r = self._sess.get(url, params=params, cookies=cookies,
                               headers=headers, timeout=timeout, verify=verify,
                               stream=stream, allow_redirects=allow_redirects)
            r.encoding = 'utf-8'
            return r

        def post(self, url, params=None, data=None, json=None, cookies=None,
                 headers=None, timeout=5, verify=True, stream=False,
                 allow_redirects=True):
            r = self._sess.post(url, params=params, data=data, json=json,
                                cookies=cookies, headers=headers, timeout=timeout,
                                verify=verify, stream=stream,
                                allow_redirects=allow_redirects)
            r.encoding = 'utf-8'
            return r

        def log(self, *a, **kw):
            try:
                print("[kkju]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.kkju.app"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = ""
API_PREFIX = "/api/app"
APP_VERSION = "web"
# 差分/反编译实证的签名盐值（逐站固定，勿照搬其它站）
_SIGN_SALT = b"cms_device_salt_v1_2024cms_app_sign_key_v1_2024_secure"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

PAGE_SIZE = 28

# 筛选维度：契约 key -> 站点参数名 / 展示名
_FILTER_DEFS = [
    ("class", "类型"),
    ("area",  "地区"),
    ("year",  "年份"),
    ("lang",  "语言"),
]


class Spider(Spider):

    # ---------- 基础 ----------
    # 兼容壳子基类 log 单参签名：多参拼接为一行，避免 TypeError 把成功结果兜底成首页
    def log(self, *a, **kw):
        try:
            parts = []
            for x in a:
                if isinstance(x, (dict, list)):
                    parts.append(json.dumps(x, ensure_ascii=False))
                else:
                    parts.append(str(x))
            print("[kkju]", " ".join(parts))
        except Exception:
            pass

    def getName(self):
        return "看看剧"

    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}
        self.site_url = (self.extend.get("site") or HOST).rstrip("/")
        self.headers = {
            "User-Agent": UA,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.site_url + "/",
            "Origin": self.site_url,
        }
        self.default_pic = DEFAULT_PIC
        # 匿名设备 ID：每次启动生成一个稳定值即可，服务端不做账号绑定
        self.device_id = "web-" + str(uuid.uuid4())
        self._play_cache = {}
        self._classes = None
        self._filters = None
        self._settings = None
        self._live_channels = None
        # 自建 Session，不依赖壳子基类是否提供 fetch/post/session
        self._http = self._build_http()

    def _build_http(self):
        if _requests is None:
            return None
        try:
            sess = _requests.Session()
            sess.verify = False
            adapter = _requests.adapters.HTTPAdapter(
                pool_connections=10, pool_maxsize=10, max_retries=0)
            sess.mount("https://", adapter)
            sess.mount("http://", adapter)
            return sess
        except Exception as e:
            self.log("自建 Session 不可用,回退基类:", e)
            return None

    def _request(self, method, url, headers, body=None, timeout=20, stream=False):
        method = method.upper()
        # 优先自建 Session；任一环节异常再回退壳子基类方法（版本/兼容双保险）
        if self._http is not None:
            try:
                if method == "POST":
                    return self._http.post(url, headers=headers, data=body,
                                           timeout=timeout, verify=False, stream=stream)
                return self._http.get(url, headers=headers, timeout=timeout,
                                      verify=False, stream=stream)
            except Exception as e:
                self.log("自建请求失败,回退基类:", method, url[:60], e)
        # 回退壳子基类方法（版本差异兜底）
        if method == "POST":
            return self.post(url, headers=headers, data=body, timeout=timeout,
                             verify=False)
        return self.fetch(url, headers=headers, timeout=timeout, verify=False,
                          stream=stream)

    # ---------- 签名与请求 ----------
    def _sorted_query(self, params):
        if not params:
            return ""
        items = sorted((k, str(v)) for k, v in params.items() if v is not None)
        return "&".join("%s=%s" % (k, v) for k, v in items)

    def _sign_headers(self, method, path, raw_query, body_text):
        ts = str(int(time.time()))
        nonce = str(uuid.uuid4())
        derive = hmac.new(_SIGN_SALT, self.device_id.encode(),
                          hashlib.sha256).hexdigest()
        parts = [method, API_PREFIX + path, raw_query, ts, nonce, APP_VERSION]
        body_hash = ""
        if body_text is not None:
            body_hash = hashlib.sha256(body_text.encode()).hexdigest()
            parts.append(body_hash)
        msg = "\n".join(parts)
        sig = hmac.new(derive.encode(), msg.encode(),
                       hashlib.sha256).hexdigest()
        h = {
            "X-Device-ID": self.device_id,
            "X-Platform": "web",
            "X-Timestamp": ts,
            "X-Nonce": nonce,
            "X-Signature": sig,
            "X-App-Version": APP_VERSION,
        }
        if body_hash:
            h["X-Body-Hash"] = body_hash
        return h

    def _api(self, method, path, params=None, payload=None):
        method = method.upper()
        params = params or {}
        raw_query = self._sorted_query(params)
        body_text = None
        if payload is not None:
            body_text = json.dumps(payload, separators=(",", ":"),
                                   ensure_ascii=False)
        sign = self._sign_headers(method, path, raw_query, body_text)
        headers = dict(self.headers)
        headers.update(sign)
        if method == "POST":
            headers["Content-Type"] = "application/json"

        url = self.site_url + API_PREFIX + path
        if params:
            url += "?" + urllib.parse.urlencode(params)

        try:
            body_bytes = body_text.encode("utf-8") if body_text is not None else None
            rsp = self._request(method, url, headers, body=body_bytes, timeout=20)
        except Exception as e:
            self.log("api FAIL", method, path, e)
            return None

        text = ""
        if hasattr(rsp, "text"):
            text = rsp.text or ""
        elif hasattr(rsp, "content"):
            text = rsp.content.decode("utf-8", "ignore")
        if not text:
            return None
        try:
            data = json.loads(text)
        except Exception:
            self.log("api 非 JSON", path, text[:120])
            return None
        if isinstance(data, dict) and data.get("code") not in (200, None):
            self.log("api code", data.get("code"), data.get("message"), path)
            return None
        return data.get("data") if isinstance(data, dict) else data

    # ---------- 工具 ----------
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

    def _pic(self, item):
        pic = item.get("picSlide") or item.get("pic") or ""
        return pic or self.default_pic

    def _remarks(self, item):
        rk = self._clean(item.get("remarks") or "")
        if rk:
            return rk
        total = item.get("total") or 0
        serial = item.get("serial") or 0
        is_end = item.get("isEnd")
        if total:
            return ("全%d集" % total) if is_end else ("更新至第%d集" % serial)
        return ""

    def _card(self, item):
        vid = str(item.get("id") or "")
        return {
            "vod_id": vid,
            "vod_name": self._clean(item.get("name") or "")[:100] or vid,
            "vod_pic": self._pic(item),
            "vod_remarks": self._remarks(item),
            "vod_subtitle": self._clean(item.get("subTitle") or ""),
        }

    def _resolve_sub_stream(self, url, header):
        """master 多码率 → 第一条子 m3u8；已是播放列表/mp4 原样；失败回退 master。"""
        if not url or ".mp4" in url.lower():
            return url

        def _head(target):
            last = None
            for _ in range(2):
                try:
                    rs = self._request("GET", target, header, timeout=10,
                                       stream=True)
                    if getattr(rs, "status_code", 200) == 200:
                        return rs, None
                    last = Exception("http_%s" % getattr(rs, "status_code", "?"))
                except Exception as e:
                    last = e
            return None, last

        try:
            rm, err = _head(url)
            if err is not None:
                return url
            ctype = rm.headers.get("Content-Type", "") or ""
            chunk = next(rm.iter_content(2048), b"")
            rm.close()
            # 非 HLS/DASH（mp4/flv/图片等）原样返回
            if "mpegurl" not in ctype and "dash+xml" not in ctype \
                    and not chunk.lstrip().startswith(b"#EXTM3U"):
                return url
            text = chunk.decode("utf-8", "ignore")
            if "#EXT-X-STREAM-INF" not in text:
                return url
            for line in text.splitlines():
                line = line.strip().replace("\\/", "/")
                if line and not line.startswith("#"):
                    sub = urllib.parse.urljoin(url, line)
                    rs, sub_err = _head(sub)
                    if rs is not None:
                        rs.close()
                        return sub
                    break
        except Exception as e:
            self.log("子流解析回退:", e)
        return url

    @staticmethod
    def _as_list(data):
        if data is None:
            return []
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("list") or data.get("records") or []
        return []

    # ---------- 直播 ----------
    def _load_settings(self):
        if self._settings is not None:
            return self._settings
        data = self._api("GET", "/settings")
        self._settings = data if isinstance(data, dict) else {}
        return self._settings

    def _parse_playlist_text(self, text):
        out, group, logo, pending = [], "", "", None
        for raw in (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            line = raw.strip()
            if not line:
                continue
            if line.startswith("#EXTM3U") or line.startswith("#EXT-X"):
                continue
            if "#genre#" in line:
                group = line.split(",")[0].strip()
                continue
            if line.startswith("#EXTINF"):
                m = re.search(r'group-title="([^"]*)"', line)
                if m:
                    group = m.group(1).strip()
                ml = re.search(r'tvg-logo="([^"]*)"', line)
                logo = ml.group(1).strip() if ml else ""
                if "," in line:
                    pending = line.split(",", 1)[1].strip()
                continue
            if line.startswith("#"):
                continue
            if "://" not in line:
                continue
            if "," in line:
                name, url = line.split(",", 1)
                name, url = name.strip(), url.strip()
            else:
                url, name = line, (pending or line)
            if url:
                out.append({"name": self._clean(name) or url, "url": url,
                            "group": group, "logo": logo, "remarks": ""})
            pending, logo = None, ""
        return out

    def _tv_channels(self, settings):
        raw = (settings.get("live_m3u_urls") or settings.get("live_m3u_url") or "").strip()
        urls = []
        try:
            arr = json.loads(raw) if raw.startswith("[") else [raw]
            if isinstance(arr, list):
                urls = [x.strip() for x in arr if isinstance(x, str) and x.strip()]
        except Exception:
            if raw:
                urls = [raw]
        out = []
        for u in urls:
            try:
                rsp = self._request("GET", u, {"User-Agent": UA}, timeout=12)
                text = rsp.content.decode("utf-8", "ignore")
                if "EXTM3U" not in text and "genre#" not in text:
                    text = rsp.content.decode("gb18030", "ignore")
                out.extend(self._parse_playlist_text(text))
            except Exception as e:
                self.log("订阅拉取失败:", u, e)
        return out

    def _match_channels(self, settings):
        enabled = str(settings.get("live_match_enabled_web")
                      or settings.get("live_match_enabled_app") or "1")
        if enabled not in ("1", "true", "True"):
            return []
        base = (settings.get("live_match_api_base")
                or "https://api.okzhibo.live/live/api/live/").strip().rstrip("/") + "/"
        out = []
        gt_group = {"1": "足球", "18": "篮球"}
        try:
            rsp = self._request("GET", base + "all",
                                {"User-Agent": UA,
                                 "Referer": self.site_url + "/"}, timeout=12)
            lst = (rsp.json().get("data") or {}).get("list") or []
            for m in lst:
                url = m.get("live_m3u8_url") or m.get("live_flv_url") or ""
                if not url or "://" not in url:
                    continue
                home = m.get("home") or {}
                away = m.get("away") or {}
                hn, an = home.get("name") or "", away.get("name") or ""
                hs, as_ = home.get("score"), away.get("score")
                name = ("%s vs %s" % (hn, an)) if (hn or an) else str(m.get("matchId"))
                league = m.get("leagueName") or ""
                mt = m.get("matchTimeText") or ""
                score = ""
                if hs is not None and as_ is not None:
                    score = "%s-%s" % (hs, as_)
                remarks = " ".join(x for x in (league, score, mt) if x)
                gt = str(m.get("gameType") or "")
                grp = gt_group.get(gt, "赛事直播")
                out.append({"name": self._clean(name), "url": url,
                            "group": grp, "logo": m.get("leagueLogo") or "",
                            "remarks": remarks})
        except Exception as e:
            self.log("赛事拉取失败:", e)
        return out

    def _fetch_live_channels(self):
        if self._live_channels is not None:
            return self._live_channels
        settings = self._load_settings() or {}
        # 站点 /live 默认展示「赛事直播」，赛事排前；电视频道排后
        chans = self._match_channels(settings) + self._tv_channels(settings)
        seen, ded = set(), []
        for c in chans:
            if c["url"] in seen:
                continue
            seen.add(c["url"])
            ded.append(c)
        self._live_channels = ded
        return ded

    def liveContent(self, url):
        if url and "://" in url:
            try:
                rsp = self._request("GET", url, {"User-Agent": UA}, timeout=12)
                return rsp.content.decode("utf-8", "ignore")
            except Exception:
                pass
        lines, cur_group = [], None
        for c in self._fetch_live_channels():
            g = c.get("group") or "直播"
            if g != cur_group:
                lines.append("%s,#genre#" % g)
                cur_group = g
            lines.append("%s,%s" % (c["name"], c["url"]))
        return "\n".join(lines)

    def _live_detail(self, vid):
        chans = self._fetch_live_channels()
        try:
            idx = int(vid.split("@", 1)[1])
        except Exception:
            return {"list": []}
        if idx < 0 or idx >= len(chans):
            return {"list": []}
        c = chans[idx]
        return {"list": [{
            "vod_id": vid,
            "vod_name": c["name"],
            "vod_pic": c.get("logo") or "",
            "vod_subtitle": "",
            "vod_content": "",
            "vod_remarks": c.get("remarks") or c.get("group") or "直播",
            "vod_play_from": "直播",
            "vod_play_url": "%s$%s" % (c["name"], vid),
        }]}

    # ---------- 分类 / 筛选 ----------
    def _load_classes(self):
        if self._classes is not None:
            return self._classes
        data = self._api("GET", "/categories")
        classes = []
        if isinstance(data, list):
            for c in data:
                if c.get("status") not in (1, None):
                    continue
                classes.append({
                    "type_id": str(c.get("id")),
                    "type_name": self._clean(c.get("name") or ""),
                })
        # 站点导航独立「直播」页（电视订阅 + 赛事），不在 /categories 内
        classes.append({"type_id": "live", "type_name": "直播"})
        self._classes = classes
        return classes

    def _live_group_filter(self):
        """直播分组筛选：对齐站点 /live 固定的 全部/足球/篮球；电视订阅组追加在后。"""
        priority = ["足球", "篮球", "赛事直播"]
        groups, seen = [], set()
        for g in priority:  # 赛事固定分组先列，即使当前暂无对应赛事
            groups.append(g)
            seen.add(g)
        for c in self._fetch_live_channels():
            g = c.get("group") or "直播"
            if g not in seen:
                seen.add(g)
                groups.append(g)
        value = [{"n": "全部", "v": ""}]
        value += [{"n": g, "v": g} for g in groups]
        return [{"key": "group", "name": "分组", "value": value}]

    def _load_filters(self):
        if self._filters is not None:
            return self._filters
        filters = {}
        for c in self._load_classes():
            cid = c["type_id"]
            if cid == "live":
                filters[cid] = self._live_group_filter()
                continue
            detail = self._api("GET", "/categories/" + cid)
            f = {}
            if isinstance(detail, dict):
                f = detail.get("filters") or {}
            dims = []
            for key, label in _FILTER_DEFS:
                opts = f.get(key) or []
                value = [{"n": "全部", "v": ""}]
                for opt in opts:
                    value.append({"n": self._clean(opt), "v": self._clean(opt)})
                dims.append({"key": key, "name": label, "value": value})
            filters[cid] = dims
        self._filters = filters
        return filters

    def homeContent(self, filter=False):
        return {"class": self._load_classes(), "filters": self._load_filters()}

    def homeVideoContent(self):
        data = self._api("GET", "/videos/recent", {"limit": PAGE_SIZE})
        videos = [self._card(x) for x in self._as_list(data)]
        return {"list": videos}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        extend = extend or {}
        if str(tid) == "live":
            grp = extend.get("group")
            all_chans = self._fetch_live_channels()
            view = all_chans
            if grp and grp != "全部":
                view = [c for c in all_chans
                        if (c.get("group") or "直播") == grp]
            view_ids = {id(c) for c in view}
            videos = [{
                "vod_id": "live@%d" % i,
                "vod_name": c["name"],
                "vod_pic": c.get("logo") or "",
                "vod_remarks": c.get("remarks") or c.get("group") or "",
                "vod_subtitle": "",
            } for i, c in enumerate(all_chans) if id(c) in view_ids]
            return {"list": videos, "page": 1, "pagecount": 1,
                    "limit": len(videos), "total": len(videos)}
        params = {"page": page, "page_size": PAGE_SIZE}
        for key, _label in _FILTER_DEFS:
            val = extend.get(key)
            if val not in ("", None, "全部"):
                params[key] = val
        data = self._api("GET", "/categories/%s/videos" % tid, params)
        items = self._as_list(data)
        videos = [self._card(x) for x in items]
        total = data.get("total", 0) if isinstance(data, dict) else 0
        pagecount = 1
        if total:
            pagecount = (int(total) + PAGE_SIZE - 1) // PAGE_SIZE
        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": PAGE_SIZE,
            "total": total or len(videos),
        }

    # ---------- 搜索 ----------
    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        keyword = str(key or "").strip()
        params = {"keyword": keyword, "page": page, "page_size": PAGE_SIZE}
        data = self._api("GET", "/videos/search", params)
        videos = [self._card(x) for x in self._as_list(data)]
        return {
            "list": videos,
            "page": page,
            "pagecount": 1,
            "limit": PAGE_SIZE,
            "total": len(videos),
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------- 详情 ----------
    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0])
        if vod_id.startswith("live@"):
            return self._live_detail(vod_id)
        data = self._api("GET", "/videos/" + vod_id)
        if not data:
            return {"list": []}

        name = self._clean(data.get("name") or "") or vod_id
        pic = self._pic(data)
        sub_title = self._clean(data.get("subTitle") or "")
        actor = self._clean(data.get("actor") or "")
        director = self._clean(data.get("director") or "")
        cls = self._clean(data.get("classExtend") or data.get("categoryName") or "")
        year = self._clean(str(data.get("year") or ""))
        area = self._clean(data.get("area") or "")
        lang = self._clean(data.get("lang") or "")
        score = self._clean(str(data.get("doubanScore") or ""))
        remarks = self._remarks(data)

        content = self._clean(data.get("content") or "")
        content = (INTRO_PREFIX + "\n" + content) if content else INTRO_PREFIX

        # 线路 playGroups（按接口数组原序，不重排）
        play_from, play_url = [], []
        for group in data.get("playGroups") or []:
            code = str(group.get("code") or "")
            gname = self._clean(group.get("name") or code)
            eps = group.get("playUrls") or []
            if not eps:
                continue
            ep_strs = []
            for idx, ep in enumerate(eps):
                ep_name = self._clean(ep.get("name") or "")
                if not ep_name:
                    ep_name = "第%d集" % (idx + 1)
                # 内部标识：videoId@episodeIndex(0基)@groupCode
                token_id = "%s@%d@%s" % (vod_id, idx, code)
                ep_strs.append("%s$%s" % (ep_name, token_id))
            play_from.append(gname)
            play_url.append("#".join(ep_strs))

        if not play_from:
            return {"list": []}

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name[:100],
            "vod_pic": pic,
            "vod_subtitle": sub_title,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_class": cls,
            "vod_year": year,
            "vod_area": area,
            "vod_lang": lang,
            "vod_score": score,
            "vod_remarks": remarks or ("%d条线路" % len(play_from)),
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }]}

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags):
        # 整体兜底：任何未捕获异常都返回合法结构，避免冒泡到壳子 Java 侧变成空 Result
        try:
            return self._player_main(flag, id, vipFlags)
        except Exception as e:
            self.log("playerContent 异常兜底:", e)
            return {"parse": 1, "playUrl": "", "url": self.site_url + "/",
                    "header": {"User-Agent": UA,
                               "Referer": self.site_url + "/"}}

    def _player_main(self, flag, id, vipFlags):
        token_id = str(id or "")
        now = int(time.time())

        # 直播频道直链
        if token_id.startswith("live@"):
            chans = self._fetch_live_channels()
            try:
                idx = int(token_id.split("@", 1)[1])
                channel = chans[idx]
            except Exception:
                channel = None
            if channel:
                header = {"User-Agent": UA, "Referer": self.site_url + "/"}
                return {"parse": 0, "playUrl": "", "url": channel["url"],
                        "header": header}
            return {"parse": 1, "playUrl": "", "url": self.site_url + "/",
                    "header": {"User-Agent": UA,
                               "Referer": self.site_url + "/"}}
        if token_id in self._play_cache:
            ts, res = self._play_cache[token_id]
            if now - ts < 600:
                return res

        header = {"User-Agent": UA, "Referer": self.site_url + "/"}
        res = {"parse": 1, "playUrl": "", "url": self.site_url + "/",
               "header": header}

        parts = token_id.split("@")
        if len(parts) != 3:
            self.log("播放标识异常:", token_id)
            self._play_cache[token_id] = (now, res)
            return res
        video_id, ep_idx, group_code = parts[0], parts[1], parts[2]
        try:
            episode = int(ep_idx)
        except Exception:
            episode = 0

        data = self._api("POST", "/play/token",
                         payload={"videoId": int(video_id),
                                  "episode": episode,
                                  "groupCode": group_code})
        if not data:
            self._play_cache[token_id] = (now, res)
            return res

        play_url = (data.get("playUrl") or "").strip()
        if not play_url:
            self._play_cache[token_id] = (now, res)
            return res

        # 线路自带的 Referer / UA（若有）
        extra = data.get("headers") or {}
        if isinstance(extra, dict):
            ref = extra.get("referer") or extra.get("Referer")
            if ref:
                header["Referer"] = ref
            uagent = extra.get("userAgent") or extra.get("User-Agent")
            if uagent:
                header["User-Agent"] = uagent

        # needParse / parseApi 表示还需二次解析，壳子侧嗅探兜底
        need_parse = bool(data.get("needParse"))
        parse_api = (data.get("parseApi") or "").strip()
        if need_parse or parse_api:
            res = {"parse": 1, "playUrl": "", "url": play_url, "header": header}
            self._play_cache[token_id] = (now, res)
            return res

        # master 多码率 → 首条子流；mp4 原样
        raw_fmt = (data.get("format") or "").strip()
        fmt = raw_fmt.lower()
        if fmt != "mp4":
            play_url = self._resolve_sub_stream(play_url, header)

        res = {"parse": 0, "playUrl": "", "url": play_url, "header": header}
        if raw_fmt:
            res["format"] = raw_fmt
        self._play_cache[token_id] = (now, res)
        self.log("直链:", play_url[:120])
        return res

    # ---------- 其余契约 ----------
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
            if url.startswith("/"):
                url = self.site_url + url
            rsp = self._request("GET", url, {"User-Agent": UA,
                                              "Referer": self.site_url + "/"})
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
