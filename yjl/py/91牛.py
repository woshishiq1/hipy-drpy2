#!/usr/bin/python
# coding=utf-8
import json, requests, base64
from urllib.parse import urlencode
from base.spider import Spider

class Spider(Spider):
    def __init__(self):
        super().__init__()
        self.name = "91n视频"
        self.host = "https://www.trkikye.com:2087"
        self.api = "/v1"
        self.c = "t3"
        self.hosts = ["https://www.trkikye.com:2087", "https://www.dhtmvki.com:2087", "https://www.bfnaflq.com:2087", "https://www.fxjqfnm.com:2087"]
        self.header = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 12; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Referer": self.host + "/99.html",
            "X-Requested-With": "XMLHttpRequest",
            "Accept-Language": "zh-CN,zh;q=0.9"
        }
        self.PUB = """-----BEGIN PUBLIC KEY-----
MIIBVgIBADANBgkqhkiG9w0BAQEFAASCAUAwggE8AgEAAkEA0rEKiXbkCWY/EQm6
DwcV63B7euIlFsPPoCcyDJoD49qtgiLPyBprP3RIymcYQt/qRk1lx+djGynMDYkr
ir8zBQIDAQABAkAMXujHeXuaMa6ySWfrSfc3g7s8U9rpo0WlmaeOpdxknG8Yf57k
FympK1NK3oEqr5nvdoIc8NSoIxsyQOLqb58BAiEA8XdQYbfrcVmp13mPzveJkxLJ
mD1QHTTlZbvkk1zqhskCIQDfX4f1iJiBl8EZFi08+VLW/1PMP1n2AFypBcuimjxc
XQIhAOm+VziRAsCSTIBCs7xlEW8mw7G0wKXVO680qLsiOgFJAiEA1EvIPT0wrOJd
PQmNv0i7SelrbFC9oIehiWcfrg/m1GUCIQDgbwV9afN3SGQUkhS2CF1FA/nDM87n
jU4OJdpLWVH0NQ==
-----END PUBLIC KEY-----"""
        self._doh_domain = "91napp.17ctxt.com"
        self._doh_servers = [
            "https://dns.alidns.com/resolve?name={}&type=TXT",
            "https://doh.pub/dns-query?name={}&type=TXT",
            "https://cloudflare-dns.com/dns-query?name={}&type=TXT",
        ]
        self._cate = None
        self._hosts_fetched = False
        self._session = requests.Session()
        self._session.headers.update(self.header)

    def init(self, extend=""):
        return self

    def getName(self):
        return self.name

    def isVideoFormat(self, url):
        u = str(url or "").lower()
        return ".m3u8" in u or u.endswith(".mp4") or ".flv" in u or ".ts" in u

    def manualVideoCheck(self):
        return False

    def destroy(self):
        return

    def _refresh_hosts(self):
        if self._hosts_fetched:
            return
        self._hosts_fetched = True
        try:
            for doh in self._doh_servers:
                try:
                    url = doh.format(self._doh_domain)
                    hdrs = {"accept": "application/dns-json", "User-Agent": self.header["User-Agent"]}
                    r = self._session.get(url, headers=hdrs, timeout=8, verify=False)
                    if r.status_code != 200:
                        continue
                    data = r.json()
                    if "Answer" not in data:
                        continue
                    new_hosts = []
                    for ans in data["Answer"]:
                        txt = ans.get("data", "").strip('"')
                        for part in txt.split("|"):
                            part = part.strip()
                            if part.startswith("http") and "/99.html" in part:
                                base = part.replace("/99.html", "")
                                if base not in new_hosts and base not in self.hosts:
                                    new_hosts.append(base)
                    if new_hosts:
                        # 新发现的域名放前面，原有域名放后面去重
                        seen = set()
                        merged = []
                        for h in new_hosts + self.hosts:
                            if h not in seen:
                                seen.add(h)
                                merged.append(h)
                        self.hosts = merged
                        self.host = merged[0]
                        # 更新header中的Referer
                        self.header["Referer"] = self.host + "/99.html"
                        return
                except:
                    continue
        except:
            pass

    def _fetch(self, path, params=None):
        p = {"c": self.c}
        if params:
            p.update(params)
        qs = urlencode(p)
        self._refresh_hosts()
        for h in self.hosts:
            ref = h + "/99.html"
            hdrs = dict(self.header)
            hdrs["Referer"] = ref
            for _ in range(3):
                try:
                    r = self._session.get(h + self.api + path + "?" + qs, headers=hdrs, timeout=15, verify=False)
                    if r.status_code == 200:
                        body = r.text.strip()
                        if body:
                            return self._decrypt(json.loads(body))
                except:
                    continue
        return {}

    def _decrypt(self, res):
        if not isinstance(res, dict) or "data" not in res or "key" not in res:
            return res
        try:
            from Crypto.PublicKey import RSA
            from Crypto.Cipher import PKCS1_v1_5, AES
            aes_key = PKCS1_v1_5.new(RSA.importKey(self.PUB)).decrypt(base64.b64decode(res["key"]), None)
            ks = aes_key.decode("utf-8", "ignore")
            iv = ks[::-1][:16]
            plain = AES.new(aes_key, AES.MODE_CBC, iv.encode()).decrypt(base64.b64decode(res["data"]))
            pad = plain[-1] if plain and 1 <= plain[-1] <= 16 else 0
            j = json.loads((plain[:-pad] if pad else plain).decode("utf-8", "ignore"))
            return j.get("data", j) if isinstance(j, dict) else j
        except:
            return {}

    def _is_ad(self, v):
        return v.get("is_yp") or str(v.get("id", "")) in ("111", "112")

    def _img_proxy(self, url):
        if not url:
            return ""
        return "proxy://img?b64=" + base64.b64encode(url.encode("utf-8")).decode("utf-8")

    def _mk_vod(self, v):
        return {
            "vod_id": str(v.get("id", "")),
            "vod_name": v.get("name", ""),
            "vod_pic": self._img_proxy(v.get("enc_img", "")),
            "vod_remarks": v.get("time", "")
        }

    def _home_list(self, cates, limit=20):
        lst, seen = [], set()
        for c in cates:
            for v in c.get("videos", []):
                if self._is_ad(v):
                    continue
                vid = str(v.get("id", ""))
                if not vid or vid in seen:
                    continue
                seen.add(vid)
                lst.append(self._mk_vod(v))
                if len(lst) >= limit:
                    return lst
        return lst

    def _get_cates(self):
        if self._cate is not None:
            return self._cate
        j = self._fetch("/vod/category")
        cates = j.get("cates", []) if isinstance(j, dict) else []
        self._cate = cates
        return cates

    def _build_filters(self, cates):
        filters = {}
        for c in cates:
            cid = str(c.get("id", ""))
            if not cid:
                continue
            rows = []
            subs = c.get("sub_cates", [])
            if subs:
                rows.append({
                    "key": "cate_id",
                    "name": "分类",
                    "value": [{"n": "全部", "v": cid}] + [{"n": s.get("name", ""), "v": str(s.get("id", ""))} for s in subs]
                })
            tags = c.get("hot_tags", [])
            if tags:
                rows.append({
                    "key": "tag",
                    "name": "标签",
                    "value": [{"n": "全部", "v": ""}] + [{"n": t, "v": t} for t in tags]
                })
            if rows:
                filters[cid] = rows
        return filters

    def _extract_list(self, j):
        videos = j.get("videos", []) if isinstance(j, dict) else []
        total = j.get("total", 0) if isinstance(j, dict) else 0
        last_page = j.get("last_page", 0) if isinstance(j, dict) else 0
        seen, lst = set(), []
        for v in videos:
            if self._is_ad(v):
                continue
            vid = str(v.get("id", ""))
            if not vid or vid in seen:
                continue
            seen.add(vid)
            lst.append(self._mk_vod(v))
        return lst, total, last_page

    def homeContent(self, filter):
        cates = self._get_cates()
        classes = [{"type_id": str(c["id"]), "type_name": c.get("name", "")} for c in cates if c.get("id")]
        filters = self._build_filters(cates)
        return {"class": classes, "filters": filters, "list": self._home_list(cates)}

    def homeVideoContent(self):
        return {"list": self._home_list(self._get_cates())}

    def categoryContent(self, tid, pg="1", filter=False, extend={}):
        pg = max(int(pg or 1), 1)
        ext = extend if isinstance(extend, dict) else {}
        params = {"page": pg, "limit": 10, "cate_id": ext.get("cate_id") or tid}
        if ext.get("tag"):
            params["tag"] = ext["tag"]
        j = self._fetch("/vod", params)
        lst, total, last_page = self._extract_list(j)
        pagecount = last_page or max((total + 9) // 10, pg)
        return {"page": pg, "pagecount": pagecount, "limit": 10, "total": total, "list": lst}

    def detailContent(self, ids):
        vid = str(ids[0]) if ids else ""
        j = self._fetch("/vod/" + vid)
        if not isinstance(j, dict) or not j:
            return {"list": []}
        video = j.get("video", j) if isinstance(j, dict) else {}
        play_url = ""
        for k in ("url", "play_url", "m3u8_url", "enc_url", "file_url", "video_url"):
            v = video.get(k)
            if isinstance(v, str) and v:
                play_url = v
                break
        if not play_url and video.get("enc_img"):
            play_url = video.get("enc_img", "").replace("vod_en.jpg", "index.m3u8")
        vod = {
            "vod_id": vid,
            "vod_name": video.get("name", ""),
            "vod_pic": self._img_proxy(video.get("enc_img", "")),
            "vod_remarks": video.get("time", ""),
            "vod_year": video.get("create_time", ""),
            "vod_play_from": "91n视频",
            "vod_play_url": "正片$" + play_url if play_url else ""
        }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        pg = max(int(pg or 1), 1)
        params = {"keyword": key, "page": pg, "limit": 10}
        j = self._fetch("/vod/search", params)
        lst, total, last_page = self._extract_list(j)
        pagecount = last_page or max((total + 9) // 10, pg)
        return {"list": lst, "page": pg, "pagecount": pagecount, "limit": 10, "total": total}

    def playerContent(self, flag, id, vipFlags):
        header = {"User-Agent": self.header["User-Agent"], "Referer": self.host + "/"}
        return {"parse": 0, "playUrl": "", "url": id, "header": json.dumps(header, ensure_ascii=False)}

    def localProxy(self, param):
        param = str(param or "")
        if "img?b64=" not in param:
            return [200, "text/plain", ""]
        try:
            b64 = param.split("b64=")[-1].split("&")[0]
            url = base64.b64decode(b64).decode("utf-8")
            r = self._session.get(url, headers={"Referer": self.host + "/"}, timeout=15, verify=False)
            if r.status_code == 200:
                ct = "image/jpeg"
                if url.endswith(".png"): ct = "image/png"
                elif url.endswith(".gif"): ct = "image/gif"
                elif url.endswith(".webp"): ct = "image/webp"
                return [200, ct, r.content]
        except:
            pass
        return [404, "text/plain", ""]
