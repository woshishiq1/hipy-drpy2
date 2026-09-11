#coding=utf-8
#!/usr/bin/python
"""
==================================================
  杏吧视频 媒体解析插件 (优先默认域名/故障容灾版)
  作者: 飞鱼
==================================================
"""
import sys
import re
import json
import requests
from urllib.parse import quote, unquote
from pyquery import PyQuery as pq

sys.path.append('..')
try:
    from base.spider import Spider
except Exception:
    try:
        from spider import Spider
    except Exception:
        class Spider(object):
            pass

class Spider(Spider):
    FOLDER_PREFIX = "kw:"
    KEYWORDS_TID = "keywords"
    CAT_KEYWORDS = {
        "20": ["小马拉大车","监控","姐妹","少妇白洁","舞蹈生","房东","舔穴","骚妈","美臀","福利姬","铃木美咲","亲妹妹"],
        "21": ["抖音","猎奇","网黄","推特","cos","洛丽塔","萝莉","玩偶姐姐","四级","白虎","宝妈","网易CC","AI魔改","海角","乡下"],
        "22": ["TS","户外","充气娃娃","AI漫剧","口交","厕拍","石川澪","抄底","王者","小早川","翘臀","节目","女兵"],
        "23": ["聊天记录""高潮","催眠","自慰喷水","偷窥","家庭乱伦","强迫","喝醉","辛尤里","李雅","美少女","情深叉喔","IPZZ"],
        "24": ["AI换脸","绿帽","电话","ntr","直男","息子","三角洲","饥渴","舞蹈生","被发现","IPZZ","超市","豪乳"],
        "25": ["瑜伽裤","古装","搜查官","真空","朋友","nsfs","小舞","濑户","父亲","金先生","淫乱","swag"],
        "26": ["媚药","高颜值","侄女","公交车","阴蒂","内射合集","可爱","4p","永濑唯","大槻","欧美剧情"],
        "27": ["精神小妹","中文","少女","足疗","裸贷","拉屎","混剪","新有菜","爷爷","希岛","字幕"],
        "28": ["欧美中字","未亡人","橘玛丽","椎名由奈","女同性恋","包养","Juq","李琼","开房","松本","小泽玛利亚"],
        "29": ["短剧","噗噗","厨房","馒头","派对","假屌","金先生","木村爱心","狗狗","禁断介护","本庄玲","城崎百濑"],
        "30": ["自慰","姐弟","友田真希","麻豆传媒","裤袜","骚货","叔母","真空","借种","舔穴","子宫"],
    }

    def getName(self):
        return "杏吧视频"

    def init(self, extend=""):
        self.site_url = "https://jlj.xbsp6.boats"
        self.publish_page_url = "https://ruv.xxkk7.com/323/"
        self._keyword_cache = None
        if not self.check_site_available(self.site_url):
            self.get_latest_site_url()

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def getHeader(self):
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": getattr(self, "site_url", "https://jlj.xbsp6.boats/")
        }

    def check_site_available(self, url):
        try:
            resp = requests.head(url, headers=self.getHeader(), timeout=3, allow_redirects=True)
            if resp.status_code == 200:
                return True
        except Exception:
            pass
        return False

    def get_latest_site_url(self):
        try:
            resp = requests.get(self.publish_page_url, headers=self.getHeader(), timeout=10)
            resp.encoding = "UTF-8"
            html = resp.text
            sub_domain_match = re.search(r"sub_domain\s*=\s*['\"]([^'\"]+)['\"]", html)
            prefix_match = re.search(r"prefix\s*=\s*['\"]([^'\"]+)['\"]", html)
            suffix_match = re.search(r"suffix\s*=\s*['\"]([^'\"]+)['\"]", html)
            if sub_domain_match and prefix_match and suffix_match:
                sub_domain = sub_domain_match.group(1)
                prefix = prefix_match.group(1)
                suffix = suffix_match.group(1)
                self.site_url = f"https://{sub_domain}.{prefix}.{suffix}".rstrip("/")
        except Exception as e:
            print(e)

    def _parse_extend(self, extend):
        if not extend:
            return {}
        if isinstance(extend, dict):
            return extend
        if isinstance(extend, str):
            try:
                data = json.loads(extend)
                if isinstance(data, dict):
                    return data
            except Exception:
                return {}
        return {}

    def _build_filter_rows(self, tags, chunk=8):
        rows = []
        clean = [t for t in tags if t]
        if not clean:
            return rows
        for i in range(0, len(clean), chunk):
            part = clean[i:i + chunk]
            rows.append({"key": "videoTag", "name": "分类", "value": [{"n": t, "v": t} for t in part]})
        return rows

    def _search_url(self, tag, page):
        q = quote(tag)
        if str(page) == "1":
            return f"{self.site_url}/s/{q}.html"
        return f"{self.site_url}/s/{q}/page/{page}.html"

    def _type_url(self, tid, page):
        if str(page) == "1":
            return f"{self.site_url}/vodtype/{tid}.html"
        return f"{self.site_url}/vodtype/{tid}-{page}.html"

    def _page_result(self, videos, pg, pagecount=9999, limit=20, total=9999):
        return {
            "list": videos,
            "page": pg,
            "pagecount": pagecount,
            "limit": limit,
            "total": total
        }

    def _fetch_keyword_names(self):
        if getattr(self, "_keyword_cache", None):
            return self._keyword_cache
        names = []
        seen = set()
        try:
            url = f"{self.site_url}/label/more_keywords.html"
            resp = requests.get(url, headers=self.getHeader(), timeout=15)
            resp.encoding = "UTF-8"
            for href, name in re.findall(r'href="/s/([^"/]+)\.html">([^<]+)</a>', resp.text):
                name = name.strip()
                if not name or name in seen:
                    continue
                seen.add(name)
                names.append(name)
        except Exception as e:
            print(e)
        self._keyword_cache = names
        return names

    def _keyword_video_list(self, pg):
        names = self._fetch_keyword_names()
        page = int(pg) if str(pg).isdigit() else 1
        if page < 1:
            page = 1
        limit = 20
        start = (page - 1) * limit
        chunk = names[start:start + limit]
        videos = []
        for name in chunk:
            videos.append({
                "vod_id": f"keyword:{name}",
                "vod_name": name,
                "vod_pic": "",
                "vod_remarks": "关键词"
            })
        total = len(names)
        pagecount = (total + limit - 1) // limit if total else 1
        return self._page_result(videos, page, pagecount=pagecount, limit=limit, total=total)

    def _search_videos(self, tag, pg):
        videos = []
        page = str(pg) if pg else "1"
        try:
            url = self._search_url(tag, page)
            resp = requests.get(url, headers=self.getHeader(), timeout=10)
            resp.encoding = "UTF-8"
            videos = self._get_items_from_html(resp.text, base_url=self.site_url)
        except Exception as e:
            print(e)
        return self._page_result(videos, page)

    def _get_items_from_html(self, html_str, base_url=""):
        videos = []
        try:
            doc = pq(html_str)
            for item in doc("#posts article").items():
                title = item("h2").text().strip()
                href = item("a").attr("href") or ""
                img = item("img").attr("data-src") or item("img").attr("src") or ""
                remark = item(".meta-content").text().strip()
                if not title and not href:
                    continue
                if href and not href.startswith("http"):
                    href = base_url + ("" if href.startswith("/") else "/") + href
                videos.append({
                    "vod_id": href,
                    "vod_name": title,
                    "vod_pic": img,
                    "vod_remarks": remark
                })
        except Exception as e:
            print(f"Parse error: {e}")
        return videos

    def homeContent(self, filter):
        result = {}
        classes = [
            {"type_id": "20", "type_name": "熟母少妇"},
            {"type_id": "21", "type_name": "网红直播"},
            {"type_id": "22", "type_name": "自拍偷拍"},
            {"type_id": "23", "type_name": "强奸乱伦"},
            {"type_id": "24", "type_name": "高清国产"},
            {"type_id": "25", "type_name": "韩国专区"},
            {"type_id": "26", "type_name": "日本有码"},
            {"type_id": "27", "type_name": "日本无码"},
            {"type_id": "28", "type_name": "欧美情色"},
            {"type_id": "29", "type_name": "动漫卡通"},
            {"type_id": "30", "type_name": "三级伦理"},
            {"type_id": self.KEYWORDS_TID, "type_name": "热门关键词"}
        ]
        result["class"] = classes
        filters = {}
        for tid, tags in self.CAT_KEYWORDS.items():
            rows = self._build_filter_rows(tags)
            if rows:
                filters[tid] = rows
        kw_rows = self._build_filter_rows(self._fetch_keyword_names())
        if kw_rows:
            filters[self.KEYWORDS_TID] = kw_rows
        result["filters"] = filters
        try:
            home_url = f"{self.site_url}/xbsp/"
            resp = requests.get(home_url, headers=self.getHeader(), timeout=10)
            resp.encoding = "UTF-8"
            result["list"] = self._get_items_from_html(resp.text, base_url=self.site_url)
        except Exception as e:
            print(e)
        return result

    def homeVideoContent(self):
        return {"list": []}

    def categoryContent(self, tid, pg="1", filter=False, extend={}):
        tid = unquote(str(tid or ""))
        extend = self._parse_extend(extend)
        tag = str(extend.get("videoTag") or "").strip()
        if tag:
            return self._search_videos(tag, pg)
        if tid == self.KEYWORDS_TID:
            return self._keyword_video_list(pg)
        videos = []
        page = str(pg) if pg else "1"
        try:
            url = self._type_url(tid, page)
            resp = requests.get(url, headers=self.getHeader(), timeout=10)
            resp.encoding = "UTF-8"
            videos = self._get_items_from_html(resp.text, base_url=self.site_url)
        except Exception as e:
            print(e)
        return self._page_result(videos, page)

    def detailContent(self, ids):
        vod = {}
        try:
            url = ids[0] if isinstance(ids, list) else ids
            url = unquote(str(url or ""))
            vod["vod_id"] = url
            vod["vod_name"] = "在线播放"
            vod["type_name"] = "福利"
            vod["vod_play_from"] = "杏吧播放"
            vod["vod_play_url"] = f"正片${url}"
        except Exception as e:
            print(e)
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        videos = []
        try:
            url = self._search_url(key, str(pg) if pg else "1")
            resp = requests.get(url, headers=self.getHeader(), timeout=10)
            resp.encoding = "UTF-8"
            videos = self._get_items_from_html(resp.text, base_url=self.site_url)
        except Exception as e:
            print(e)
        return {"list": videos}

    def playerContent(self, flag, id, vipFlags):
        play_id = unquote(str(id or ""))
        play_url = play_id
        try:
            resp = requests.get(play_id, headers=self.getHeader(), timeout=10)
            resp.encoding = "UTF-8"
            html = resp.text
            raw_match = re.search(r"const\s+rawUrl\s*=\s*['\"]([^'\"]+\.m3u8[^'\"]*)['\"]", html)
            if raw_match:
                play_url = raw_match.group(1)
            else:
                m3u8_match = re.search(r"https?://[^\s$#\'\"]+\.m3u8(?:\?[^\s#\'\"]*)?", html, re.IGNORECASE)
                if m3u8_match:
                    play_url = m3u8_match.group(0)
        except Exception as e:
            print(f"Player parsing error: {e}")
        return {
            "parse": 0,
            "url": play_url,
            "header": self.getHeader()
        }

    def localProxy(self, param):
        pass

# ===== PAGE_PLAYLIST_START =====
def _pl_install(_C):
    if getattr(_C, "_pl_patched", False):
        return _C
    _C._pl_patched = True
    _orig_init = getattr(_C, "init", None)
    _orig_home = getattr(_C, "homeContent", None)
    _orig_homev = getattr(_C, "homeVideoContent", None)
    _orig_cate = getattr(_C, "categoryContent", None)
    _orig_detail = getattr(_C, "detailContent", None)
    _orig_search = getattr(_C, "searchContent", None)
    _orig_searchp = getattr(_C, "searchContentPage", None)
    _orig_player = getattr(_C, "playerContent", None)

    def _ensure(self):
        if not hasattr(self, "page_cache"):
            self.page_cache = {}
            self.page_index = {}
            self.page_keys = []
            self._src_cache = {}

    def _clean(s):
        return str(s or "").replace("$", " ").replace("#", " ").strip()

    def _enc(s):
        try:
            from urllib.parse import quote
            return quote(str(s or ""), safe="")
        except Exception:
            return str(s or "")

    def _dec(s):
        try:
            from urllib.parse import unquote
            return unquote(str(s or ""))
        except Exception:
            return str(s or "")

    def _cache_page(self, key, items):
        _ensure(self)
        out = []
        for x in items or []:
            if isinstance(x, dict) and x.get("vod_id"):
                out.append(x)
        if not out:
            return
        self.page_cache[key] = out
        if key in self.page_keys:
            self.page_keys.remove(key)
        self.page_keys.append(key)
        for it in out:
            self.page_index[str(it["vod_id"])] = key
        while len(self.page_keys) > 30:
            old = self.page_keys.pop(0)
            self.page_cache.pop(old, None)

    def _page_of(self, vid):
        _ensure(self)
        key = self.page_index.get(str(vid))
        if key in self.page_cache:
            return list(self.page_cache[key])
        return []

    def _as_result(r):
        if r is None:
            return {}
        if isinstance(r, dict):
            return r
        if isinstance(r, (bytes, bytearray)):
            r = r.decode("utf-8", "ignore")
        if isinstance(r, str):
            s = r.strip()
            if s.startswith("{") or s.startswith("["):
                try:
                    import json as _j
                    return _j.loads(s)
                except Exception:
                    return {}
        return {}

    def _split_sources(vod):
        fr = str((vod or {}).get("vod_play_from") or "").split("$$$")
        ur = str((vod or {}).get("vod_play_url") or "").split("$$$")
        while len(ur) < len(fr):
            ur.append("")
        sources = []
        for i, name in enumerate(fr):
            parts = []
            for p in (ur[i] or "").split("#"):
                if not p:
                    continue
                if "$" in p:
                    n, u = p.split("$", 1)
                else:
                    n, u = str(i + 1), p
                parts.append((_clean(n), u))
            sources.append((_clean(name) or ("线路%d" % (i + 1)), parts))
        return [x for x in sources if x[1]]

    def _call_detail(self, vid):
        if not _orig_detail:
            return {}
        try:
            return _as_result(_orig_detail(self, [vid]))
        except TypeError:
            try:
                return _as_result(_orig_detail(self, vid))
            except Exception:
                return {}
        except Exception:
            return {}

    def _load_src(self, vid):
        _ensure(self)
        vid = str(vid)
        if vid in self._src_cache:
            return self._src_cache[vid]
        r = self._pl_call_detail(vid)
        vod = ((r.get("list") or [None])[0]) or {}
        sources = _split_sources(vod)
        self._src_cache[vid] = sources
        return sources

    def _item_parts(self, it, src_idx, current_sources, current_vid):
        iid = str(it.get("vod_id") or "")
        if not iid:
            return []
        name = _clean(it.get("vod_name") or iid) or iid
        if iid == str(current_vid):
            eps = []
            if current_sources:
                if src_idx < len(current_sources) and current_sources[src_idx][1]:
                    eps = current_sources[src_idx][1]
                else:
                    eps = current_sources[0][1]
            if len(eps) > 1:
                out = []
                for i, (en, u) in enumerate(eps):
                    label = _clean("%s %s" % (name, en or ("%02d" % (i + 1))))
                    out.append("%s$%s" % (label, u))
                return out
            if eps:
                return ["%s$%s" % (name, eps[0][1])]
            return ["%s$nid:%s" % (name, _enc(iid))]
        return ["%s$nid:%s" % (name, _enc(iid))]

    def _apply_playlist(self, vid, vod, items):
        sources = _split_sources(vod)
        _ensure(self)
        self._src_cache[str(vid)] = sources
        if not items:
            return vod
        ordered = [x for x in items if str(x.get("vod_id")) == str(vid)]
        ordered += [x for x in items if str(x.get("vod_id")) != str(vid)]
        plist, seen = [], set()
        for it in ordered:
            iid = str(it.get("vod_id") or "")
            if not iid or iid in seen:
                continue
            seen.add(iid)
            plist.append(it)
        if not plist:
            return vod
        if not sources:
            sources = [("线路1", [("播放", "nid:%s" % _enc(vid))])]
        play_from, play_urls = [], []
        for i, (sname, _eps) in enumerate(sources):
            parts = []
            for it in plist:
                parts.extend(self._pl_item_parts(it, i, sources, vid))
            if not parts:
                continue
            play_from.append(sname or ("线路%d" % (i + 1)))
            play_urls.append("#".join(parts))
        if not play_from:
            return vod
        vod = dict(vod)
        vod["vod_play_from"] = "$$$".join(play_from)
        vod["vod_play_url"] = "$$$".join(play_urls)
        return vod

    def init(self, *args, **kwargs):
        _ensure(self)
        if _orig_init:
            return _orig_init(self, *args, **kwargs)

    def homeContent(self, *args, **kwargs):
        _ensure(self)
        r = _orig_home(self, *args, **kwargs) if _orig_home else {}
        try:
            _cache_page(self, ("home",), _as_result(r).get("list"))
        except Exception:
            pass
        return r

    def homeVideoContent(self, *args, **kwargs):
        _ensure(self)
        r = _orig_homev(self, *args, **kwargs) if _orig_homev else {"list": []}
        try:
            _cache_page(self, ("homev",), _as_result(r).get("list"))
        except Exception:
            pass
        return r

    def categoryContent(self, *args, **kwargs):
        _ensure(self)
        r = _orig_cate(self, *args, **kwargs) if _orig_cate else {"list": []}
        try:
            tid = args[0] if args else kwargs.get("tid", "")
            pg = args[1] if len(args) > 1 else kwargs.get("pg", "1")
            ext = args[3] if len(args) > 3 else kwargs.get("extend", "")
            _cache_page(self, ("cate", str(tid), str(pg), str(ext)), _as_result(r).get("list"))
        except Exception:
            pass
        return r

    def searchContent(self, *args, **kwargs):
        _ensure(self)
        if not _orig_search:
            return {"list": []}
        r = _orig_search(self, *args, **kwargs)
        try:
            key = args[0] if args else kwargs.get("key", "")
            pg = args[2] if len(args) > 2 else kwargs.get("pg", "1")
            _cache_page(self, ("search", str(key), str(pg)), _as_result(r).get("list"))
        except Exception:
            pass
        return r

    def searchContentPage(self, *args, **kwargs):
        _ensure(self)
        if not _orig_searchp:
            return {"list": []}
        r = _orig_searchp(self, *args, **kwargs)
        try:
            key = args[0] if args else kwargs.get("key", "")
            pg = args[2] if len(args) > 2 else kwargs.get("page", kwargs.get("pg", "1"))
            _cache_page(self, ("searchp", str(key), str(pg)), _as_result(r).get("list"))
        except Exception:
            pass
        return r

    def detailContent(self, ids, *args, **kwargs):
        _ensure(self)
        if isinstance(ids, (list, tuple)):
            vid = str(ids[0]) if ids else ""
            call_ids = list(ids)
        else:
            vid = str(ids)
            call_ids = [vid]
        if vid.startswith("nid:"):
            vid = _dec(vid[4:])
            call_ids[0] = vid
        cached = _page_of(self, vid)
        if _orig_detail:
            try:
                r = _orig_detail(self, call_ids, *args, **kwargs)
            except TypeError:
                r = _orig_detail(self, call_ids)
        else:
            r = {"list": []}
        try:
            rr = _as_result(r)
            lst = rr.get("list") or []
            if not lst or not isinstance(lst[0], dict):
                return r
            vod = dict(lst[0])
            vod["vod_id"] = str(vod.get("vod_id") or vid)
            if not vod.get("vod_name"):
                hit = next((x for x in cached if str(x.get("vod_id")) == vid), None)
                if hit:
                    vod["vod_name"] = hit.get("vod_name") or vid
            if cached:
                vod = self._pl_apply_playlist(vid, vod, cached)
            rr = dict(rr)
            rr["list"] = [vod]
            if isinstance(r, dict) or r is None:
                return rr
            try:
                import json as _j
                return _j.dumps(rr, ensure_ascii=False)
            except Exception:
                return rr
        except Exception:
            return r

    def playerContent(self, flag, id, vipFlags=None, *args, **kwargs):
        _ensure(self)
        s = str(id)
        if s.startswith("nid:"):
            vid = _dec(s[4:])
            sources = self._pl_load_src(vid)
            real = ""
            if sources:
                picked = None
                for name, eps in sources:
                    if str(name) == str(flag) and eps:
                        picked = eps
                        break
                if not picked:
                    picked = sources[0][1]
                if picked:
                    real = picked[0][1]
            if real and not str(real).startswith("nid:"):
                id = real
            else:
                id = vid
        if not _orig_player:
            return {"parse": 0, "url": id}
        try:
            return _orig_player(self, flag, id, vipFlags, *args, **kwargs)
        except TypeError:
            try:
                return _orig_player(self, flag, id, vipFlags)
            except TypeError:
                return _orig_player(self, flag, id)

    _C._pl_call_detail = _call_detail
    _C._pl_load_src = _load_src
    _C._pl_item_parts = _item_parts
    _C._pl_apply_playlist = _apply_playlist
    if _orig_init:
        _C.init = init
    if _orig_home:
        _C.homeContent = homeContent
    if _orig_homev:
        _C.homeVideoContent = homeVideoContent
    if _orig_cate:
        _C.categoryContent = categoryContent
    if _orig_search:
        _C.searchContent = searchContent
    if _orig_searchp:
        _C.searchContentPage = searchContentPage
    if _orig_detail:
        _C.detailContent = detailContent
    if _orig_player:
        _C.playerContent = playerContent
    return _C

try:
    _pl_install(Spider)
except Exception:
    pass
# ===== PAGE_PLAYLIST_END =====
