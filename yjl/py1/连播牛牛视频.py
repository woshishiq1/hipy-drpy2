#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
牛牛视频 爬虫 v3 (主 API nn.123xiangshang.com, 与 APP 数据一致)
- 分类:   GET /types
- 排序:   _CLASS_ORDER 偏好(如 AI短剧紧跟短剧), 仅调序不改数据
- 配置:   GET /config  (动态获取 parser/src 解析器配置)
- 筛选:   子分类超 _FILTER_SPLIT(8) 个拆分为多个筛选组(class/class_moreN), 每组分行显示
- 列表:   GET /list  (class/order/type_id/area/year/state/wd/page, 子分类走 class)
- 首页:   GET /main
- 详情:   GET /detail?vod_id=X   (sources[].episodes[].url, 含 player_id)
- 播放:   player_id → 解析器URL → JSON {code,url,headers}
- 路线:   多播放源用 $$$ 分隔(集内 #, 集 $), 显示 APP 中文线路名(player_name)
- 短剧:   keymp4 为 CENC 加密 mp4+key, 经 _KEYMP4_PROXY 解密代理(见 keymp4_proxy.py)输出明文
- 连播:   列表页缓存整页; 点中的放第一; 多集展开成「片名 01」; 每条原线路都带整页
响应 AES/ECB/PKCS5 加密, key = "/path?query" 截断16位(不足补"0")
"""
import base64
import json
import re
import requests
from urllib.parse import quote

try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider:
        pass

from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad


class Spider(BaseSpider):
    name = "牛牛视频"

    _HOST = "https://nn.123xiangshang.com:35620"
    _KEYMP4_PROXY = "https://8765-abb3ee7c09cf0bb4.monkeycode-ai.online"

    _HEADERS = {
        "p": "android",
        "pkg": "com.sexy.goddess",
        "t": "",
        "d": "0000000000000000",
        "v": "1.6.2",
        "y": "0",
        "product": "Pixel 7",
        "sys": "13",
        "User-Agent": "okhttp/4.9.3",
    }

    _SAFE = "-_.!~*'()[]:/?,%&="

    _SRC_PIDS = {
        "src3": "pp", "src4": "madou", "src5": "douban", "src6": "juzi",
        "src8": "shanju", "src9": "ningmeng", "src10": "shizi",
        "src11": "paopao", "src12": "leidian",
    }

    _BAD = {"juzi", "shanju", "jzzy", "hmjc"}
    _XM3U8 = {"xm3u8", "xiaocao", "hema"}
    _CLASS_ORDER = [("11", "4"), ("12", "11")]
    _FILTER_SPLIT = 8
    _LIST_BATCH = 3

    def __init__(self):
        self.host = self._HOST
        self.class_cache = None
        self.config_cache = None
        self.parsers_cache = None
        self.page_size = 12
        self.session = requests.Session()
        self.session.verify = False
        self.page_cache = {}
        self.page_index = {}
        self.page_keys = []
        self._src_cache = {}

    def init(self, extend=""):
        if extend:
            try:
                cfg = json.loads(extend)
                if cfg.get("host"):
                    self.host = cfg["host"].rstrip("/")
            except Exception:
                pass

    def getName(self):
        return self.name

    def _decrypt(self, pathq, text):
        text = (text or "").strip()
        if not text:
            return {}
        try:
            return json.loads(text)
        except Exception:
            pass
        try:
            key = (pathq if len(pathq) >= 16 else pathq + "0" * (16 - len(pathq)))[:16]
            ct = base64.b64decode(text)
            cipher = AES.new(key.encode("utf-8"), AES.MODE_ECB)
            return json.loads(unpad(cipher.decrypt(ct), AES.block_size).decode("utf-8"))
        except Exception:
            return {}

    def _get(self, path, params=None):
        raw_q = "&".join("%s=%s" % (k, v) for k, v in (params or {}).items())
        suffix = path + ("?" + quote(raw_q, safe=self._SAFE) if raw_q else "")
        url = self.host + "/" + suffix
        pathq = "/" + suffix
        try:
            r = self.session.get(url, headers=self._HEADERS, timeout=15)
            return self._decrypt(pathq, r.text)
        except Exception:
            return {}

    def _config(self):
        if self.config_cache is not None:
            return self.config_cache
        j = self._get("config")
        data = (j or {}).get("data") or {}
        self.config_cache = data
        return data

    def _parsers(self):
        if self.parsers_cache is not None:
            return self.parsers_cache
        cfg = self._config()
        mapping = {}
        for p in cfg.get("parser") or []:
            pid = p.get("player_id")
            url = p.get("url") or ""
            if pid and url and p.get("enable") == 1:
                mapping[pid] = url
        for src_key, pid in self._SRC_PIDS.items():
            y_url = (cfg.get(src_key) or {}).get("yUrl") or ""
            if y_url:
                mapping[pid] = y_url
        self.parsers_cache = mapping
        return mapping

    def _player_names(self):
        cfg = self._config()
        names = {}
        for p in cfg.get("parser") or []:
            pid = p.get("player_id")
            if not pid:
                continue
            name = (p.get("player_name") or "").strip()
            names[pid] = name if name else pid
        return names

    def _list_params(self, wd="", tid="", cls="", order="最新", area="", year="", pg="1"):
        return {
            "class": cls,
            "order": order,
            "type_id": str(tid),
            "area": area,
            "year": year,
            "state": "",
            "wd": wd,
            "page": str(pg),
        }

    def _classes(self):
        if self.class_cache is not None:
            return self.class_cache
        arr = []
        j = self._get("types")
        for m in (j or {}).get("data") or []:
            tid = m.get("type_id")
            name = m.get("type_name")
            if tid is not None and name and str(tid) != "5" and str(name) != "短剧":
                arr.append({"type_id": str(tid), "type_name": str(name),
                            "type_extend": m.get("type_extend") or {}})
        self.class_cache = self._reorder(arr)
        return self.class_cache

    def _reorder(self, classes):
        classes = list(classes)
        for after, before in self._CLASS_ORDER:
            m = next((c for c in classes if c["type_id"] == after), None)
            if not m or not any(c["type_id"] == before for c in classes):
                continue
            classes = [c for c in classes if c["type_id"] != after]
            pos = next(i + 1 for i, c in enumerate(classes) if c["type_id"] == before)
            classes.insert(pos, m)
        return classes

    def _filters(self, classes):
        filters = {}
        for c in classes:
            te = c.get("type_extend") or {}
            f = []
            if te.get("class"):
                vals = [v for v in str(te["class"]).split(",") if v]
                groups = [vals[i:i + self._FILTER_SPLIT]
                          for i in range(0, len(vals), self._FILTER_SPLIT)]
                for gi, g in enumerate(groups):
                    f.append({
                        "key": "class" if gi == 0 else "class_more%d" % gi,
                        "name": "类型" if gi == 0 else "类型·更多%d" % gi,
                        "value": [{"n": v, "v": v} for v in g],
                    })
            if te.get("area"):
                f.append({
                    "key": "area", "name": "地区",
                    "value": [{"n": v, "v": v} for v in str(te["area"]).split(",")],
                })
            if te.get("year"):
                f.append({
                    "key": "year", "name": "年份",
                    "value": [{"n": v, "v": v} for v in str(te["year"]).split(",")],
                })
            f.append({
                "key": "order", "name": "排序",
                "value": [
                    {"n": "最新", "v": "最新"},
                    {"n": "最热", "v": "最热"},
                    {"n": "评分", "v": "评分"},
                ],
            })
            filters[c["type_id"]] = f
        return filters

    def _cache_page(self, key, items):
        items = [x for x in (items or []) if isinstance(x, dict) and x.get("vod_id")]
        if not items:
            return
        self.page_cache[key] = items
        if key in self.page_keys:
            self.page_keys.remove(key)
        self.page_keys.append(key)
        for it in items:
            self.page_index[str(it["vod_id"])] = key
        while len(self.page_keys) > 30:
            old = self.page_keys.pop(0)
            self.page_cache.pop(old, None)

    def _page_of(self, vid):
        key = self.page_index.get(str(vid))
        if key in self.page_cache:
            return list(self.page_cache[key])
        return []

    def _load_src(self, vid):
        vid = str(vid)
        if vid in self._src_cache:
            return self._src_cache[vid]
        j = self._get("detail", {"vod_id": vid})
        d = (j or {}).get("data") or {}
        sources = self._playable_sources(d) if d.get("vod_name") else []
        self._src_cache[vid] = sources
        return sources

    def _prefetch_src(self, items, keep_vid):
        unknown = []
        for it in items or []:
            iid = str(it.get("vod_id") or "")
            if iid and iid != str(keep_vid) and iid not in self._src_cache:
                unknown.append(iid)
        if not unknown:
            return
        try:
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=min(8, len(unknown))) as ex:
                list(ex.map(self._load_src, unknown))
        except Exception:
            for iid in unknown:
                self._load_src(iid)

    def _clean_title(self, s):
        return re.sub(r"[$#]", " ", str(s or "")).strip()

    def _source_by_pid(self, sources, pid):
        for s_ in sources or []:
            if str(s_.get("player_id") or "") == str(pid):
                return s_
        return (sources or [None])[0]

    def _item_play_parts(self, it, pid=""):
        iid = str(it.get("vod_id") or "")
        if not iid:
            return []
        name = self._clean_title(it.get("vod_name") or iid) or iid
        sources = self._src_cache.get(iid) or []
        s_ = self._source_by_pid(sources, pid) if sources else None
        eps = (s_.get("episodes") or []) if s_ else []
        use_pid = (s_.get("player_id") if s_ else "") or pid
        if len(eps) > 1:
            return [
                "%s$%s@@%s" % (
                    self._clean_title("%s %s" % (name, e.get("name") or "%02d" % (i + 1))),
                    e.get("url") or "",
                    use_pid,
                )
                for i, e in enumerate(eps)
            ]
        if eps:
            return ["%s$%s@@%s" % (name, eps[0].get("url") or "", use_pid)]
        return ["%s$nid:%s" % (name, iid)]

    def _fetch_list_pages(self, pg, tid="", cls="", order="最新", area="", year="", wd=""):
        start = (int(pg) - 1) * self._LIST_BATCH + 1
        items = []
        full = True
        for i in range(self._LIST_BATCH):
            params = self._list_params(tid=tid, cls=cls, order=order, area=area, year=year, wd=wd, pg=start + i)
            j = self._get("list", params)
            chunk = [self._vod_from_list(v) for v in (j or {}).get("data") or []]
            items.extend(chunk)
            if len(chunk) < self.page_size:
                full = False
                break
        return items, full

    def _playable_sources(self, d):
        sources = []
        parsers = self._parsers()
        for s_ in (d or {}).get("sources") or []:
            pid = s_.get("player_id")
            if not pid or pid in self._BAD or pid in self._XM3U8:
                continue
            eps = s_.get("episodes") or []
            if not eps:
                continue
            first_url = eps[0].get("url") or ""
            if not first_url.startswith("http") and pid not in parsers:
                continue
            raw = s_.get("prio")
            try:
                prio = int(raw) if raw not in (None, "") else 999
            except (TypeError, ValueError):
                prio = 999
            sources.append({"player_id": pid, "prio": prio, "episodes": eps})
        sources.sort(key=lambda x: x["prio"])
        return sources

    def homeContent(self, filter):
        classes = self._classes()
        items = []
        j = self._get("main")
        for block in (j or {}).get("data") or []:
            if str(block.get("type_id") or "") == "5" or str(block.get("type_name") or "") == "短剧":
                continue
            for v in block.get("list") or []:
                items.append(self._vod_from_list(v))
        items = items[:40]
        self._cache_page(("home",), items)
        return {
            "class": [{"type_id": c["type_id"], "type_name": c["type_name"]} for c in classes],
            "filters": self._filters(classes),
            "list": items,
        }

    def homeVideoContent(self):
        return {"list": self.homeContent(False).get("list") or []}

    def categoryContent(self, tid, pg, filter, extend):
        extend = extend or {}
        pg = int(pg) if str(pg).isdigit() else 1
        cls = str(extend.get("class") or "")
        for k, v in extend.items():
            if k.startswith("class_more") and v:
                cls = str(v)
                break
        order = str(extend.get("order") or "最新")
        area = str(extend.get("area") or "")
        year = str(extend.get("year") or "")
        items, full = self._fetch_list_pages(pg, tid=tid, cls=cls, order=order, area=area, year=year)
        self._cache_page(("cate", str(tid), cls, order, area, year, pg), items)
        return self._page_result(pg, items, full)

    def _playlist_items(self, vid, items, self_item, name="", pic=""):
        if not items:
            items = [self_item] if self_item else [{"vod_id": vid, "vod_name": name, "vod_pic": pic}]
        self._prefetch_src(items, vid)
        ordered = [x for x in items if str(x.get("vod_id")) == str(vid)]
        ordered += [x for x in items if str(x.get("vod_id")) != str(vid)]
        out, seen = [], set()
        for it in ordered:
            iid = str(it.get("vod_id") or "")
            if not iid or iid in seen:
                continue
            seen.add(iid)
            out.append(it)
        return out

    def _playlist_parts(self, vid, items, pid=""):
        parts = []
        for it in items:
            parts.extend(self._item_play_parts(it, pid))
        return parts or ["播放$nid:%s" % vid]

    def _source_lines(self, sources, vid, items):
        names = self._player_names()
        play_from, play_urls = [], []
        for s_ in sources or []:
            pid = s_["player_id"]
            play_from.append(self._clean_title(names.get(pid, pid)) or pid)
            play_urls.append("#".join(self._playlist_parts(vid, items, pid)))
        if not play_from:
            play_from = ["线路1"]
            play_urls = ["#".join(self._playlist_parts(vid, items))]
        return play_from, play_urls

    def _detail_with_playlist(self, vid, d, items, self_item, sources=None):
        name = (d.get("vod_name") if d else "") or (self_item or {}).get("vod_name") or vid
        pic = (d.get("vod_pic") if d else "") or (self_item or {}).get("vod_pic") or ""
        remarks = (d.get("vod_remarks") if d else "") or (self_item or {}).get("vod_remarks") or ""
        plist = self._playlist_items(vid, items, self_item, name, pic)
        play_from, play_urls = self._source_lines(sources, vid, plist)
        vod = {
            "vod_id": str((d or {}).get("vod_id") or vid),
            "vod_name": name,
            "vod_pic": pic,
            "vod_year": str((d or {}).get("vod_year") or ""),
            "vod_area": (d or {}).get("vod_area", ""),
            "type_name": (d or {}).get("vod_class", ""),
            "vod_actor": (d or {}).get("vod_actor", ""),
            "vod_director": (d or {}).get("vod_director", ""),
            "vod_content": (d or {}).get("vod_content", "") or (d or {}).get("vod_blurb", "") or remarks,
            "vod_remarks": remarks,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_urls),
        }
        return {"list": [vod]}

    def detailContent(self, ids):
        vid = str(ids[0])
        if vid.startswith("nid:"):
            vid = vid[4:]
        cached = self._page_of(vid)
        self_item = next((x for x in cached if str(x.get("vod_id")) == vid), None)

        j = self._get("detail", {"vod_id": vid})
        d = (j or {}).get("data") or {}
        sources = self._playable_sources(d) if d.get("vod_name") else []
        self._src_cache[vid] = sources
        return self._detail_with_playlist(vid, d, cached, self_item, sources)

    def searchContent(self, key, quick, pg="1"):
        pg = int(pg) if str(pg).isdigit() else 1
        items, full = self._fetch_list_pages(pg, wd=str(key))
        self._cache_page(("search", str(key), pg), items)
        return self._page_result(pg, items, full)

    def _nid_sources(self, vid):
        return self._load_src(vid)

    def _resolve_player(self, player, parsers):
        if player in parsers:
            return player
        for pid, name in self._player_names().items():
            if name == player and pid in parsers:
                return pid
        return player

    def _play_one(self, ep, player, parsers=None):
        parsers = parsers or self._parsers()
        player = self._resolve_player(player, parsers)
        if ep.startswith("http") and re.search(r"\.(m3u8|mp4|ts|flv)(\?|$)", ep):
            return {"parse": 0, "playUrl": "", "url": ep, "header": "{}"}
        tpl = parsers.get(player)
        if not tpl:
            return None
        url = tpl.replace("%s", ep) if "%s" in tpl else tpl + ep
        try:
            r = self.session.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
            j = r.json()
        except Exception:
            return None
        play = (j or {}).get("url") or ""
        if not play:
            return None
        if (j or {}).get("type") == "keymp4" and self._KEYMP4_PROXY:
            key = (j or {}).get("key") or ""
            if key:
                play = "%s/decode?u=%s&k=%s" % (self._KEYMP4_PROXY, quote(play, safe=""), key)
        headers = self._parse_headers((j or {}).get("headers") or "")
        return {"parse": 0, "playUrl": "", "url": play, "header": json.dumps(headers)}

    def _play_sources(self, sources):
        parsers = self._parsers()
        for s_ in sources or []:
            eps = s_.get("episodes") or []
            if not eps:
                continue
            r = self._play_one(eps[0].get("url") or "", s_.get("player_id") or "", parsers)
            if r and r.get("url"):
                return r
        return {"parse": 1, "playUrl": "", "url": ""}

    def playerContent(self, flag, id, vipFlags):
        s = str(id)
        if s.startswith("nid:"):
            return self._play_sources(self._nid_sources(s[4:]))
        if "@@" in s:
            ep, player = s.rsplit("@@", 1)
        else:
            ep, player = s, str(flag)
        r = self._play_one(ep, player)
        return r if r and r.get("url") else {"parse": 1, "playUrl": "", "url": ""}

    def isVideoContent(self):
        return True

    def _page_result(self, pg, items, full=None):
        if full is None:
            full = bool(items)
        return {
            "page": pg,
            "pagecount": pg + 1 if full else pg,
            "limit": self.page_size * self._LIST_BATCH,
            "total": 99999,
            "list": items,
        }

    @staticmethod
    def _parse_headers(s):
        out = {}
        if not s:
            return out
        for line in str(s).replace("\r", "").split("\n"):
            if ":" in line:
                k, _, v = line.partition(":")
                k = k.strip()
                if k:
                    out[k] = v.strip()
        return out

    @staticmethod
    def _vod_from_list(v):
        return {
            "vod_id": str(v.get("vod_id") or ""),
            "vod_name": v.get("vod_name", ""),
            "vod_pic": v.get("vod_pic", ""),
            "vod_remarks": v.get("vod_remarks", ""),
        }
