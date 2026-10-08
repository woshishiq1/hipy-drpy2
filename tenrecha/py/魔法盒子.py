#!/usr/bin/python
# -*- coding: utf-8 -*-
import re, json, requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from base.spider import Spider

class Spider(Spider):
    def getName(self): return "魔法盒子"

    def init(self, extend=""):
        self.host = "http://movie.l98.cn"
        self.headers = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0", "Referer": self.host}
        self._sources = None
        self._home_data = None
        self._play_headers = {"User-Agent": "Mozilla/5.0"}
        # ========== 优化1: 添加Session复用连接 ==========
        self._session = requests.Session()
        self._session.headers.update(self.headers)

    def _post(self, url, data, timeout=15):
        try:
            # ========== 使用Session而非requests ==========
            return self._session.post(url, json=data, timeout=timeout).json()
        except: return {}

    def _get(self, url, timeout=15):
        try:
            # ========== 使用Session而非requests ==========
            return self._session.get(url, timeout=timeout).json()
        except: return {}

    def _fix(self, u): return "https:" + u if u and u.startswith("//") else u or ""

    def getSources(self):
        if self._sources is not None: return self._sources
        self._sources = self._get(f"{self.host}/api/tvbox/sources", timeout=8).get("data", [])
        return self._sources

    def _fetch_home(self, s):
        try:
            d = self._post(f"{self.host}/api/tvbox/home", {"api": s["api"], "filter": True}, timeout=5)
            return s["key"], d.get("data", {})
        except: return s["key"], {}

    def _load_all_homes(self):
        if self._home_data is not None: return self._home_data
        sources = self.getSources()
        if not sources: return {}
        self._home_data = {}
        pool = ThreadPoolExecutor(max_workers=13)
        futures = [pool.submit(self._fetch_home, s) for s in sources]
        ok_count = 0
        for f in as_completed(futures):
            if ok_count >= 15:  # ========== 优化2: 放宽限制 ==========
                break
            try:
                key, hdata = f.result(timeout=0.5)  # ========== 放宽超时 ==========
            except: continue
            if hdata and hdata.get("class"):
                self._home_data[key] = hdata
                ok_count += 1
        pool.shutdown(wait=False)
        return self._home_data

    def _get_source_home(self, key):
        homes = self._load_all_homes()
        if key in homes: return homes[key]
        sources = self.getSources()
        src = next((s for s in sources if s["key"] == key), None)
        if not src: return {}
        hdata = self._post(f"{self.host}/api/tvbox/home", {"api": src["api"], "filter": True}, timeout=10).get("data", {})
        if hdata: self._home_data[key] = hdata
        return hdata

    def homeContent(self, filter):
        result = {"class": [], "filters": {}, "list": []}
        sources = self.getSources()
        if not sources: return result
        homes = self._load_all_homes()
        cat_order = ["source-681f32793f", "source-37dc8f3871", "tv", "source-a45d5761c9", "source-aa4f0ed30b", "4kav", "source-e18321eaa8", "source-8ee56df12f", "hema", "source-a63c5a93bc", "source-4df616f958", "yunyun", "source-ac9aba9c5a"]
        sources_sorted = sorted(sources, key=lambda s: cat_order.index(s["key"]) if s["key"] in cat_order else 99)
        merged_list = []
        for s in sources_sorted:
            key = s["key"]
            hdata = homes.get(key, {})
            classes = hdata.get("class", [])
            base_filters = hdata.get("filters", {})
            result["class"].append({"type_id": key, "type_name": s["name"]})
            if classes:
                sub_vals = [{"n": c.get("type_name", ""), "v": str(c.get("type_id", ""))} for c in classes]
                sub_vals.insert(0, {"n": "\u5168\u90e8", "v": ""})
                fl = [{"name": "\u5206\u7c7b", "key": "sub_tid", "value": sub_vals}]
                for c in classes:
                    sf = base_filters.get(str(c.get("type_id", "")), [])
                    if sf:
                        fl.extend(sf)
                        break
                result["filters"][key] = fl
            for item in hdata.get("list", [])[:4]:
                if isinstance(item, dict) and item.get("vod_name") and item.get("vod_id"):
                    merged_list.append({"vod_id": f'{key}|{item["vod_id"]}', "vod_name": item.get("vod_name",""), "vod_pic": self._fix(item.get("vod_pic","")), "vod_remarks": item.get("vod_remarks","")})
        result["list"] = merged_list[:24]
        return result

    def categoryContent(self, tid, pg, filter, extend):
        result = {"list": [], "page": int(pg) if pg else 1, "pagecount": 1, "limit": 30, "total": 0}
        try:
            key = tid
            sources = self.getSources()
            src = next((s for s in sources if s["key"] == key), None)
            if not src: return result
            hdata = self._get_source_home(key)
            classes = hdata.get("class", [])
            sub_tid = (extend or {}).get("sub_tid", "")
            if not sub_tid and classes:
                sub_tid = str(classes[0].get("type_id", ""))
            real_extend = {k: v for k, v in (extend or {}).items() if k != "sub_tid" and v}
            page = int(pg) if pg else 1
            data = self._post(f"{self.host}/api/tvbox/category", {"api": src["api"], "tid": sub_tid, "page": page, "filter": bool(real_extend), "extend": real_extend}, timeout=10).get("data", {})
            items = []
            for v in data.get("list", []):
                if not isinstance(v, dict) or not v.get("vod_id"): continue
                items.append({"vod_id": f'{key}|{v["vod_id"]}', "vod_name": v.get("vod_name",""), "vod_pic": self._fix(v.get("vod_pic","")), "vod_remarks": v.get("vod_remarks","")})
            result["list"] = items
            result["pagecount"] = data.get("pagecount") or 99
            result["limit"] = data.get("limit") or len(items)
            result["total"] = data.get("total") or len(items)
        except: pass
        return result

    def detailContent(self, ids):
        result = {"list": []}
        try:
            tid = ids[0] if ids else ""
            key, real_id = tid.split("|", 1) if "|" in tid else (tid, "")
            sources = self.getSources()
            src = next((s for s in sources if s["key"] == key), None)
            if not src: return result
            data = self._post(f"{self.host}/api/detail", {"api": src["api"], "ids": [str(real_id)]}, timeout=8).get("data", {})
            if isinstance(data, list) and data: data = data[0]
            play_url = data.get("vod_play_url", "")
            if play_url:
                play_url = re.sub(r'(/api/tvbox/play/[^\s#$]+)', lambda m: self.host + m.group(0) if not m.group(0).startswith("http") else m.group(0), play_url)
            vod = {"vod_id": tid, "vod_name": data.get("vod_name",""), "vod_pic": self._fix(data.get("vod_pic","")), "vod_remarks": data.get("vod_remarks",""), "vod_year": data.get("vod_year",""), "vod_area": data.get("vod_area",""), "vod_actor": data.get("vod_actor",""), "vod_director": data.get("vod_director",""), "vod_content": data.get("vod_content",""), "vod_play_from": data.get("vod_play_from",""), "vod_play_url": play_url}
            result["list"] = [vod]
        except: pass
        return result

    def searchContent(self, key, quick, pg="1"):
        result = {"list": [], "page": int(pg) if pg else 1}
        sources = self.getSources()
        if not sources: return result
        def fetch_search(s):
            try:
                d = self._post(f"{self.host}/api/search", {"api": s["api"], "key": key, "quick": quick, "page": int(pg) if pg else 1}, timeout=5)
                if not d.get("success"): return []
                items = d.get("data", [])
                if isinstance(items, dict): items = items.get("list", [])
                if not isinstance(items, list): return []
                return [{"vod_id": f'{s["key"]}|{v["vod_id"]}', "vod_name": v.get("vod_name",""), "vod_pic": self._fix(v.get("vod_pic","")), "vod_remarks": v.get("vod_remarks","")} for v in items if isinstance(v, dict) and v.get("vod_id") and v.get("vod_name")]
            except: return []
        all_results = []
        pool = ThreadPoolExecutor(max_workers=13)
        futures = [pool.submit(fetch_search, s) for s in sources]
        ok_count = 0
        for f in as_completed(futures):
            if ok_count >= 8:  # ========== 优化3: 放宽搜索限制 ==========
                break
            try:
                items = f.result(timeout=0.5)  # ========== 放宽超时 ==========
                if items:
                    all_results.extend(items)
                    ok_count += 1
            except: continue
        pool.shutdown(wait=False)
        seen = set()
        for item in all_results:
            if item["vod_name"] not in seen: seen.add(item["vod_name"]); result["list"].append(item)
        return result

    def playerContent(self, flag, id, vipFlags):
        url = id if id.startswith("http") else self.host + id if id.startswith("/") else id
        try:
            # ========== 优化4: 使用Session获取播放地址 ==========
            r = self._session.get(url, allow_redirects=False, timeout=8, headers=self._play_headers)
            if r.status_code in (301, 302, 303, 307, 308):
                loc = r.headers.get("location", "")
                if loc:
                    if not loc.startswith("http"):
                        loc = self.host + loc
                    return {"parse": 0, "url": loc, "header": json.dumps(self._play_headers)}
        except: pass
        return {"parse": 0, "url": url, "header": json.dumps(self._play_headers)}
