# -*- coding: utf-8 -*-
# 欢迎来到有料视频！牢记回家地址：  yltv.live
# 1.编辑任意邮件至邮箱获取最新下载地址youliao1688@gmail.com(地址找回)
import base64
import hashlib
import json
import time

try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider(object):
        pass

try:
    import requests
except Exception:
    requests = None

import urllib.request
import urllib.parse


class _AES(object):
    @staticmethod
    def dec(data, key, iv):
        try:
            from Crypto.Cipher import AES
            return _AES.unpad(AES.new(key, AES.MODE_CBC, iv).decrypt(data))
        except Exception:
            pass
        try:
            from Cryptodome.Cipher import AES
            return _AES.unpad(AES.new(key, AES.MODE_CBC, iv).decrypt(data))
        except Exception:
            pass
        try:
            from cryptography.hazmat.backends import default_backend
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            d = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend()).decryptor()
            return _AES.unpad(d.update(data) + d.finalize())
        except Exception:
            pass
        try:
            import pyaes
            out = b""
            c = pyaes.AESModeOfOperationCBC(key, iv=iv)
            for i in range(0, len(data) - 15, 16):
                out += c.decrypt(data[i:i + 16])
            return _AES.unpad(out)
        except Exception:
            return b""

    @staticmethod
    def unpad(d):
        n = d[-1] if d else 0
        return d[:-n] if 1 <= n <= 16 else d


class Spider(BaseSpider):
    SALT = "a2ef62227536ab01"
    KEY = b"ec5279154d05ac2c"
    IV = b"515cd1587d7cfbdd"
    INIT_HOSTS = ["https://h5init.qn.pnwkult.com/api", "https://init.al.pnwkult.com/api",
                  "https://init.youliao88.com/api", "https://h5init.m.nbajkbq.com/api",
                  "https://h5init.qn.nbajkbq.com/api", "https://h5init.al.pnwkult.com/api"]
    CHANNEL = "1031"
    UA = "Mozilla/5.0 (Linux; Android 12; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
    ORIGIN = "https://0zq6w.shddlcd.cn"
    PROXY = "https://py.fzcrym.link:1314"
    IMG_PROXY = PROXY + "/yl_img?u="
    API_PROXY = PROXY + "/yl_api"
    ENC_IMG_HOSTS = ("qgtp.m.shallql.cn", "qgtp.m.vivmpg.cn", "qgtp.m.xmmxjk.com")
    NEW = "n_new"
    REC = "n_rec"
    LIB = "n_lib"

    def init(self, extend=""):
        self.api = ""
        self.token = ""
        self.uid = ""
        self.viaproxy = False
        self.cate2 = {}
        self.plans = {}
        self.recs = []
        self.libs = []
        self._boot()
        return self

    def getName(self):
        return "有料"

    def isVideoFormat(self, url):
        u = str(url)
        return ".m3u8" in u or u.endswith(".mp4")

    def manualVideoCheck(self):
        return False

    def destroy(self):
        return

    def _sign(self, path, t):
        return hashlib.md5(("%s?time=%s&%s" % (path, t, self.SALT)).encode()).hexdigest().lower()

    def _dec(self, text):
        try:
            p = _AES.dec(base64.b64decode(text), self.KEY, self.IV)
            if p:
                return json.loads(p.decode("utf-8", "ignore"))
        except Exception:
            pass
        try:
            return json.loads(text)
        except Exception:
            return {}

    def _post(self, base, path, data=None, auth=True):
        t = int(time.time())
        p = urllib.parse.urlparse(base + path).path
        h = {"time": str(t), "sign": self._sign(p, t), "Content-Type": "application/x-www-form-urlencoded",
             "User-Agent": self.UA, "Origin": self.ORIGIN, "Referer": self.ORIGIN + "/"}
        if auth and self.token and self.uid:
            h["uid"] = str(self.uid)
            h["token"] = self.token
            h["Access-Token"] = self.token
        body = urllib.parse.urlencode(data or {}).encode()
        try:
            if requests:
                return self._dec(requests.post(base + path, data=body, headers=h, timeout=20).text)
            return self._dec(urllib.request.urlopen(urllib.request.Request(base + path, data=body, headers=h), timeout=20).read().decode("utf-8", "ignore"))
        except Exception:
            return {}

    def _boot(self):
        if self.api:
            return True
        for host in self.INIT_HOSTS:
            r = self._post(host, "/player/do_init_h5", {"system": 3, "channel": self.CHANNEL, "new_live": 1}, False)
            d = r.get("data") if isinstance(r, dict) else None
            if isinstance(d, dict) and d.get("api_url"):
                self.api = d["api_url"].rstrip("/") + "/api"
                pi = d.get("player_info") or {}
                self.token = pi.get("token") or ""
                self.uid = pi.get("uid") or ""
                self.viaproxy = False
                return True
        return self._boot_proxy()

    def _boot_proxy(self):
        r = self._proxy("/player/do_init_h5", {"system": 3, "channel": self.CHANNEL, "new_live": 1})
        d = r.get("data") if isinstance(r, dict) else None
        if isinstance(d, dict) and d.get("api_url"):
            self.api = d["api_url"].rstrip("/") + "/api"
            pi = d.get("player_info") or {}
            self.token = pi.get("token") or ""
            self.uid = pi.get("uid") or ""
            self.viaproxy = True
            return True
        return False

    def _proxy(self, path, data=None):
        url = "%s?p=%s&d=%s" % (self.API_PROXY, urllib.parse.quote(path, safe=""),
                                urllib.parse.quote(json.dumps(data or {}, ensure_ascii=False), safe=""))
        h = {"User-Agent": self.UA}
        try:
            if requests:
                return json.loads(requests.get(url, headers=h, timeout=25).text)
            return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=25).read().decode("utf-8", "ignore"))
        except Exception:
            return {}

    def _call(self, path, data=None):
        if not self._boot():
            return {}
        if self.viaproxy:
            r = self._proxy(path, data)
            return r if isinstance(r, dict) else {}
        r = self._post(self.api, path, data)
        if isinstance(r, dict) and r.get("code") == 3:
            self.api = ""
            if self._boot():
                r = self._post(self.api, path, data) if not self.viaproxy else self._proxy(path, data)
        if not isinstance(r, dict) or not r:
            r = self._proxy(path, data)
            if isinstance(r, dict) and r.get("code") == 1:
                self.viaproxy = True
        return r if isinstance(r, dict) else {}

    def _full(self, url):
        u = str(url or "")
        if ".m3u8" not in u:
            return u
        i = u.rfind("/")
        return u[:i + 1] + "index.m3u8" if i > 0 else u

    def _num(self, n):
        try:
            v = float(n)
            return "%.1fw" % (v / 10000) if v >= 10000 else str(int(v))
        except Exception:
            return str(n)

    def _img(self, u):
        u = str(u or "").strip()
        if not u:
            return ""
        if u.startswith("//"):
            u = "https:" + u
        if not u.startswith("http"):
            return u
        for h in self.ENC_IMG_HOSTS:
            if h in u:
                return self.IMG_PROXY + urllib.parse.quote(u, safe="")
        return u

    def _vod(self, it):
        vid = it.get("video_id") or it.get("id") or ""
        name = it.get("title") or it.get("video_title") or it.get("name") or ""
        pic = it.get("img") or it.get("video_img") or it.get("cover") or it.get("icon") or ""
        rem = str(it.get("video_time") or it.get("time") or "")
        pn = it.get("play_num") or it.get("video_play_num")
        if pn:
            rem = ("%s %s" % (rem, self._num(pn))).strip()
        return {"vod_id": str(vid), "vod_name": str(name), "vod_pic": self._img(pic), "vod_remarks": rem}

    def _pick(self, obj):
        if isinstance(obj, list):
            return obj
        if not isinstance(obj, dict):
            return []
        for k in ("list", "data", "items", "rows", "video_list", "library_list"):
            v = obj.get(k)
            if isinstance(v, list):
                return v
            if isinstance(v, dict):
                r = self._pick(v)
                if r:
                    return r
        return []

    def _flat(self, arr):
        out = []
        for x in arr:
            if isinstance(x, dict) and isinstance(x.get("list"), list):
                out += x["list"]
            elif isinstance(x, dict):
                out.append(x)
        return out

    def _dedup(self, items):
        seen, out = set(), []
        for it in items:
            if not isinstance(it, dict):
                continue
            try:
                v = self._vod(it)
            except Exception:
                continue
            if not v["vod_id"] or not v["vod_name"] or v["vod_id"] in seen:
                continue
            seen.add(v["vod_id"])
            out.append(v)
        return out

    def homeContent(self, filter):
        d = self._call("/video/index", {}).get("data") or {}
        self.recs = [{"id": str(b.get("cate_id")), "name": str(b.get("name") or "")} for b in (d.get("recommend_list") or []) if b.get("cate_id")]
        cls = [{"type_id": self.NEW, "type_name": "最新"}, {"type_id": self.REC, "type_name": "推荐"}]
        for c in (d.get("cate_list") or []):
            if c.get("cate_id"):
                cls.append({"type_id": str(c["cate_id"]), "type_name": str(c.get("name") or c["cate_id"])})
        cls.append({"type_id": self.LIB, "type_name": "片库"})
        vl = []
        for b in (d.get("recommend_list") or []):
            vl += b.get("list") or []
        return {"class": cls, "filters": self._filters(cls), "list": self._dedup(vl)}

    def _filters(self, cls):
        f = {}
        if self.recs:
            f[self.REC] = [{"key": "rec", "name": "板块", "value": [{"n": r["name"], "v": r["id"]} for r in self.recs]}]
        lg = self._libs()
        if lg:
            f[self.LIB] = [{"key": "lib", "name": "片库", "value": lg}]
        for c in cls:
            tid = c["type_id"]
            if tid in (self.NEW, self.REC, self.LIB):
                continue
            subs = self._subs(tid)
            if not subs:
                continue
            f[tid] = [{"key": "cate2", "name": "子类",
                       "value": [{"n": "全部", "v": ""}] + [{"n": str(s.get("name") or ""), "v": str(s.get("id"))} for s in subs if s.get("id")]}]
        return f

    def _subs(self, tid):
        if tid in self.cate2:
            return self.cate2[tid]
        r = self._call("/video/cate2", {"cate_id": tid})
        subs = r.get("data") if isinstance(r.get("data"), list) else []
        if not subs:
            subs = (self._call("/video/cate_list", {"cate_id": tid, "page": 1}).get("data") or {}).get("cate2_list") or []
        self.cate2[tid] = subs
        return subs

    def _plan(self, tid):
        if tid in self.plans:
            return self.plans[tid]
        plan = []
        for s in self._subs(tid):
            sid = s.get("id")
            if not sid:
                continue
            try:
                cnt = int(s.get("video_count") or 0)
            except Exception:
                cnt = 0
            pages = (cnt + 19) // 20 if cnt else 30
            for p in range(1, pages + 1):
                plan.append((str(sid), p))
        self.plans[tid] = plan
        return plan

    def _libs(self):
        if self.libs:
            return self.libs
        d = self._call("/video/video_library_list", {"page": 1}).get("data") or {}
        out = [{"n": "全部", "v": ""}]
        for g in (d.get("library_list") or []):
            gn = str(g.get("name") or "")
            for it in (g.get("list") or []):
                if it.get("library_id"):
                    out.append({"n": "%s·%s" % (gn, it.get("name") or ""), "v": str(it["library_id"])})
        self.libs = out if len(out) > 1 else []
        return self.libs

    def homeVideoContent(self):
        return {"list": self.homeContent(False)["list"]}

    def _batch(self, jobs):
        out = []
        if not jobs:
            return out
        try:
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=min(8, len(jobs))) as ex:
                for r in ex.map(lambda j: self._pick(self._call("/video/cate2_list", {"cate2_id": j[0], "page": j[1]}).get("data")), jobs):
                    out += r
        except Exception:
            for j in jobs:
                out += self._pick(self._call("/video/cate2_list", {"cate2_id": j[0], "page": j[1]}).get("data"))
        return out

    def categoryContent(self, tid, pg, filter, extend):
        pg = max(int(pg or 1), 1)
        ext = extend or {}
        if tid == self.NEW:
            items = self._pick(self._call("/video/new_update_list", {"page": pg}).get("data"))
            return self._page(items, pg, 12)
        if tid == self.REC:
            rid = str(ext.get("rec") or "")
            if not rid:
                if not self.recs:
                    self.homeContent(False)
                rid = self.recs[0]["id"] if self.recs else "29"
            items = self._pick(self._call("/video/recommend_cate", {"cate_id": rid, "page": pg}).get("data"))
            return self._page(items, pg, 12)
        if tid == self.LIB:
            lid = str(ext.get("lib") or "")
            if lid:
                return self._sub_page(lid, pg)
            items = (self._call("/video/video_library_list", {"page": pg}).get("data") or {}).get("list") or []
            return self._page(items, pg, 20)
        c2 = str(ext.get("cate2") or "").strip()
        if c2:
            return self._sub_page(c2, pg)
        plan = self._plan(tid)
        if not plan:
            items = self._flat((self._call("/video/cate_list", {"cate_id": tid, "page": pg}).get("data") or {}).get("list") or [])
            return self._page(items, pg, 42)
        per = 2
        total = len(plan)
        pc = max((total + per - 1) // per, 1)
        jobs = plan[(pg - 1) * per:pg * per]
        vl = self._dedup(self._batch(jobs))
        return {"list": vl, "page": pg, "pagecount": pc, "limit": 40, "total": total * 20}

    def _sub_page(self, sid, pg):
        items = self._pick(self._call("/video/cate2_list", {"cate2_id": sid, "page": pg}).get("data"))
        cnt = 0
        for subs in self.cate2.values():
            for s in subs:
                if str(s.get("id")) == str(sid):
                    try:
                        cnt = int(s.get("video_count") or 0)
                    except Exception:
                        cnt = 0
        if not cnt:
            info = (self._call("/video/cate2_list", {"cate2_id": sid, "page": 1}).get("data") or {}).get("cate2_info") or {}
            try:
                cnt = int(info.get("count") or 0)
            except Exception:
                cnt = 0
        vl = self._dedup(items)
        pc = (cnt + 19) // 20 if cnt else (pg + 1 if len(vl) >= 20 else pg)
        return {"list": vl, "page": pg, "pagecount": max(pc, pg), "limit": 20, "total": cnt or pc * 20}

    def _page(self, items, pg, limit):
        vl = self._dedup(items)
        pc = pg + 1 if len(vl) >= limit else pg
        return {"list": vl, "page": pg, "pagecount": pc, "limit": limit, "total": pc * limit}

    def searchContent(self, key, quick, pg="1"):
        pg = int(pg or 1)
        items = self._pick(self._call("/video/search_list", {"keyword": key, "page": pg}).get("data"))
        if not items and pg == 1:
            items = self._pick(self._call("/video/search_video_library", {"keyword": key, "page": pg}).get("data"))
        vl = self._dedup(items)
        return {"list": vl, "page": pg, "pagecount": pg + 1 if len(vl) >= 8 else pg, "limit": 10, "total": (pg + 1) * 10}

    def detailContent(self, ids):
        vid = str(ids[0]) if ids else ""
        vi = {}
        for path in ("/video/video_info", "/video/video_info_v3"):
            r = self._call(path, {"video_id": vid, "uid": self.uid, "is_h5": 1})
            if r.get("code") == 1:
                cand = (r.get("data") or {}).get("video_info") or {}
                if cand.get("url") or cand.get("video_line"):
                    vi = cand
                    break
        if not vi:
            return {"list": []}
        lines = [x for x in (vi.get("video_line") or []) if x.get("url")]
        if not lines and vi.get("url"):
            lines = [{"name": "线路1", "url": vi["url"]}]
        froms = [str(l.get("name") or ("线路%d" % (i + 1))) for i, l in enumerate(lines)]
        urls = ["播放$" + str(l["url"]) for l in lines]
        tags = vi.get("tags")
        if isinstance(tags, list):
            tags = ",".join(str(t.get("name") or "") for t in tags if isinstance(t, dict))
        c2 = vi.get("cate2") or {}
        vod = {"vod_id": vid, "vod_name": str(vi.get("title") or ""), "vod_pic": self._img(vi.get("img")),
               "type_name": str(c2.get("name") or (tags or "")), "vod_remarks": str(vi.get("video_time") or ""),
               "vod_year": "", "vod_area": "", "vod_actor": "", "vod_director": "",
               "vod_content": "播放 %s ｜ 时长 %s ｜ %s" % (self._num(vi.get("play_num") or 0), vi.get("video_time") or "", tags or ""),
               "vod_play_from": "$$$".join(froms) or "线路1", "vod_play_url": "$$$".join(urls)}
        return {"list": [vod]}

    def playerContent(self, flag, id, vipFlags):
        return {"parse": 0, "playUrl": "", "url": self._full(id),
                "header": json.dumps({"User-Agent": self.UA, "Referer": self.ORIGIN + "/"})}

    def localProxy(self, param):
        return [200, "text/plain", ""]
