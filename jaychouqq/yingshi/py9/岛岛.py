# -*- coding: utf-8 -*-
# ==========================================================
# 多多影视 | 参照儿歌乐园.py模板重构版【修复播放/列表bug】
# 修复：时间戳、player参数解析、首页分类、搜索逻辑
# ==========================================================
import sys
import json
import time
sys.path.append('..')
try:
    from base.spider import Spider as BaseSpider
except ImportError:
    import requests
    class BaseSpider(object):
        def fetch(self, url, headers=None, timeout=20, verify=False, cookies=None):
            s = requests.Session()
            s.trust_env = False
            return s.get(url, headers=headers, timeout=timeout, verify=verify, cookies=cookies)

try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except Exception:
    pass

try:
    import requests as _requests
except ImportError:
    _requests = None

try:
    import hashlib
except ImportError:
    hashlib = None

class Spider(BaseSpider):
    name = "多多影视"
    HOST_POOL = [
        "https://323433ssdfd.top",
        "https://duoduosdf12223234334.top",
        "https://xds2435u23422342342u.top",
        "https://dduotv01.top"
    ]
    host = HOST_POOL[0]
    UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"
    F = "WF-2c064bc5b3400788f31b848849bc3a60f835423ba2dfe69d7ea93974c216e4f2"
    SK = "WEB-50a8e9c84a1dc05669a692ded99a2dac46527229e607a7be15db88dbc59059d1"
    ID = "com.web.player"
    W = "ddtvf65f3a83d6d9ad6f"
    XC = "8f3d2a1c7b6e5d4c9a0b1f2e3d4c5b6a"

    PAGE_SIZE = 18
    SEARCH_PER_PAGE = 20

    # 【静态分类，保留儿歌乐园格式；建议使用接口动态分类】
    CATEGORIES = [
        {"type_name": "电影", "type_id": "1"},
        {"type_name": "剧集", "type_id": "2"},
        {"type_name": "动漫", "type_id": "3"},
        {"type_name": "综艺", "type_id": "4"},
        {"type_name": "全部", "type_id": "all"}
    ]
    FILTERS = {
        "1": [{"key": "subtype", "name": "筛选", "init": "", "value": [
            {"n": "热门", "v": "hits"},
            {"n": "最新", "v": "new"}
        ]}],
        "2": [{"key": "subtype", "name": "筛选", "init": "", "value": [
            {"n": "热门", "v": "hits"},
            {"n": "最新", "v": "new"}
        ]}],
        "3": [{"key": "subtype", "name": "筛选", "init": "", "value": [
            {"n": "热门", "v": "hits"},
            {"n": "最新", "v": "new"}
        ]}],
        "4": [{"key": "subtype", "name": "筛选", "init": "", "value": [
            {"n": "热门", "v": "hits"},
            {"n": "最新", "v": "new"}
        ]}]
    }
    DEFAULT_SUBTYPE = {"1":"hits","2":"hits","3":"hits","4":"hits"}

    def init(self, extend=''):
        self._search_cache = {}
        self._all_vods_cache = None
        return {}

    def getName(self):
        return self.name

    def isVideoFormat(self, url):
        low = (url or "").lower()
        return any(k in low for k in (".m3u8",".mp4",".mp3",".m4a",".flv",".avi",".mkv",".mov",".ts"))

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def localProxy(self, param):
        return [200, "text/plain", ""]

    def liveContent(self, url):
        return ""

    def action(self, action):
        return "{}"

    # ========= protobuf 编码解码 多多原版 =========
    def _vint(self,n):
        out = b""
        while True:
            b = n & 0x7F
            n >>=7
            if n:
                out += bytes([b | 0x80])
            else:
                out += bytes([b])
                break
        return out

    def _pb(self,url_str, vf, ts):
        sig_raw = f"finger={self.F}&id={self.ID}&nonce={'0'*32}&sk={self.SK}&time={ts}&v=1"
        sig = hashlib.sha256(sig_raw.encode()).hexdigest().upper()
        parts = [
            b'\x0a', self._vint(len(url_str)), url_str.encode('utf‑8'),
            b'\x12', self._vint(len(vf)), vf.encode('utf‑8'),
            b'\x18', self._vint(ts),
            b'\x22', self._vint(32), b'0'*32,
            b'\x2a', self._vint(64), sig.encode('utf‑8'),
            b'\x32', self._vint(14), b'com.web.player',
            b'\x38', b'\x01'
        ]
        buf = b""
        for p in parts:
            buf += p
        return buf

    def _parse_pb(self, buf):
        fields = {}
        arr = bytearray(buf)
        i = 0
        while i < len(arr):
            tag = arr[i]
            i +=1
            f = tag >>3
            w = tag &7
            if w ==0:
                v =0
                s=0
                while True:
                    x = arr[i]
                    i +=1
                    v |= (x &0x7F) << s
                    if not (x &0x80):
                        break
                    s +=7
                fields[f] = v
            elif w ==2:
                ln =0
                s2=0
                while True:
                    x = arr[i]
                    i +=1
                    ln |= (x &0x7F) << s2
                    if not (x &0x80):
                        break
                    s2 +=7
                sub = arr[i:i+ln]
                fields[f] = sub.decode("utf‑8","replace")
                i += ln
            elif w ==5:
                i +=4
        return fields

    # ========= 请求工具，多host轮询 =========
    def _headers(self):
        return {
            "User‑Agent": self.UA,
            "web‑sign": self.W,
            "X‑Client": self.XC,
            "Accept":"application/json, text/plain, */*",
            "Accept‑Language":"zh‑CN,zh;q=0.9",
            "Referer": self.host + "/"
        }

    def _fetch_bin(self, path, post_bin=None):
        """二进制请求，用于protobuf解码接口"""
        for candidate in self.HOST_POOL:
            try:
                url = candidate + path
                hd = self._headers()
                if post_bin is not None:
                    hd["Content‑Type"] = "application/x‑protobuf"
                    hd["Accept"] = "application/x‑protobuf"
                    # 直接传bytes，不要做编码
                    r = self.fetch(url, headers=hd, data=post_bin, timeout=8)
                else:
                    r = self.fetch(url, headers=hd, timeout=8)
                if r and r.status_code ==200:
                    self.host = candidate
                    return r.content
            except Exception:
                continue
        return b""

    def _get(self, path, params=None):
        """GET返回JSON，和儿歌乐园接口完全同名"""
        try:
            url = self.host + path
            hd = self._headers()
            resp = self.fetch(url, headers=hd, params=params, timeout=8)
            return json.loads(resp.text)
        except Exception:
            return {}

    def _parse_vod(self, vod):
        """ 【和儿歌乐园_parse_song对齐】把原始api条目转为vod字典 """
        return {
            "vod_id": str(vod.get("vod_id","")),
            "vod_name": vod.get("vod_name","未知"),
            "vod_pic": vod.get("vod_pic",""),
            "vod_remarks": vod.get("vod_remarks","")
        }

    # ========= homeContent 首页分类+首页列表 =========
    def homeContent(self, filter=False):
        ret = {"class": self.CATEGORIES, "filters": self.FILTERS, "list":[]}
        try:
            data = self._get("/api.php/web/index/home")
            cats_data = data.get("data",{}).get("categories",[])
            for cat in cats_data:
                for item in cat.get("videos",[]):
                    ret["list"].append(self._parse_vod(item))
        except Exception:
            pass
        return ret

    def homeVideoContent(self):
        ret = {"list":[], "page":1, "pagecount":1, "limit":20, "total":20}
        try:
            data = self._get("/api.php/web/index/home")
            cats_data = data.get("data",{}).get("categories",[])
            for cat in cats_data:
                for item in cat.get("videos",[]):
                    ret["list"].append(self._parse_vod(item))
        except Exception:
            pass
        return ret

    # ========= categoryContent 分类列表 =========
    def categoryContent(self, tid, pg, filter=False, extend=""):
        try:
            page = int(pg or 1)
        except Exception:
            page =1
        if page <1: page=1

        ext = extend
        if isinstance(ext, str) and ext.strip().startswith("{"):
            try:
                ext = json.loads(ext)
            except Exception:
                ext = {}
        if not isinstance(ext, dict):
            ext = {}

        ret = {"list":[], "page":page, "pagecount":9999, "limit":self.PAGE_SIZE, "total":999999}
        try:
            sub_type = ext.get("subtype","") or self.DEFAULT_SUBTYPE.get(str(tid),"hits")
            # 修复：tid=all type_name为空；其余使用接口传入type_name，不再硬编码
            if tid == "all":
                name_param = ""
            else:
                name_param = str(tid)
            params = {"type_name":name_param, "page":page, "sort":sub_type}
            api_data = self._get("/api.php/web/filter/vod", params=params)
            items = api_data.get("data",[])
            if isinstance(items, list):
                ret["list"] = [self._parse_vod(it) for it in items]
            else:
                ret["pagecount"] = page
        except Exception:
            ret["pagecount"] = page
        return ret

    # ========= detailContent 详情接口 =========
    def detailContent(self, ids):
        rid = ids[0] if isinstance(ids,(list,tuple)) and ids else str(ids or "")
        rid = str(rid).strip()
        ret = {}
        try:
            api_data = self._get("/api.php/web/vod/get_detail", params={"vod_id":rid})
            arr = api_data.get("data",[])
            song = arr[0] if isinstance(arr,list) else arr
            if not song or not isinstance(song,dict):
                ret["list"] = [{
                    "vod_id": rid,
                    "vod_name":"未找到",
                    "vod_content":"未找到该资源",
                    "vod_remarks":"未找到",
                    "vod_play_from":self.name,
                    "vod_play_url":""
                }]
                return ret
            # 拼接简介
            content_parts = []
            if song.get("vod_class"): content_parts.append(f"类型:{song.get('vod_class')}")
            if song.get("vod_year"): content_parts.append(f"年份:{song.get('vod_year')}")
            if song.get("vod_area"): content_parts.append(f"地区:{song.get('vod_area')}")
            if song.get("vod_actor"): content_parts.append(f"演员:{song.get('vod_actor')}")
            if song.get("vod_director"): content_parts.append(f"导演:{song.get('vod_director')}")
            if song.get("vod_content"): content_parts.append(f"\n简介:\n{song.get('vod_content')}")

            vod = {
                "vod_id": rid,
                "vod_name": song.get("vod_name",""),
                "vod_pic": song.get("vod_pic",""),
                "vod_content":"\n".join(content_parts),
                "vod_remarks": song.get("vod_remarks",""),
                "vod_year": song.get("vod_year",""),
                "vod_area": song.get("vod_area",""),
                "vod_actor": song.get("vod_actor",""),
                "vod_director": song.get("vod_director",""),
                "vod_play_from": song.get("vod_play_from",self.name),
                "vod_play_url": song.get("vod_play_url",""),
                "type_name": song.get("vod_class","")
            }
            ret["list"] = [vod]
        except Exception as e:
            ret["list"] = [{
                "vod_id": rid,
                "vod_name":"加载失败",
                "vod_content":f"加载失败:{str(e)}",
                "vod_remarks":"加载失败",
                "vod_play_from":self.name,
                "vod_play_url":""
            }]
        return ret

    # ========= playerContent 【修复核心bug】 =========
    def playerContent(self, flag, id, flags=None):
        # 修复：id就是播放id，不要错误取args
        slug = str(id or "")
        # 如果本身就是直链，直接返回
        if self.isVideoFormat(slug) and slug.startswith("http"):
            return {
                "parse":0,
                "playUrl":"",
                "url":slug,
                "header":{"User‑Agent":self.UA,"Referer":self.host+"/"}
            }
        res = {"parse":0,"playUrl":"","url":"","header":{}}
        try:
            # 修复：时间戳是秒，不是毫秒！！！
            ts = int(time.time())
            bin_payload = self._pb(slug, flag, ts)
            real_url = ""
            for _ in range(2):
                bin_resp = self._fetch_bin("/api.php/web/decode/url", post_bin=bin_payload)
                if bin_resp:
                    pb_out = self._parse_pb(bin_resp)
                    if pb_out.get(1) == 1 and pb_out.get(3):
                        real_url = pb_out[3]
                        break
                time.sleep(0.3)
            if real_url:
                res["url"] = real_url
                res["header"] = {"User‑Agent":self.UA,"Referer":self.host+"/"}
                return res
        except Exception:
            pass
        # 解码失败，不使用parse=1跳转网页，直接返回空
        res["parse"] = 0
        res["url"] = ""
        res["header"] = {"User‑Agent":self.UA,"Referer":self.host+"/"}
        return res

    # ========= searchContent 【修改为调用接口搜索，不再全量拉取内存，解决卡顿】 =========
    def searchContent(self, key, quick=False, pg="1"):
        key = str(key or "").strip()
        if not key:
            return {"list":[]}
        try:
            page = int(pg or 1)
        except Exception:
            page =1
        params = {"wd":key,"page":page,"limit":self.SEARCH_PER_PAGE}
        api_data = self._get("/api.php/web/search/index", params=params)
        items = api_data.get("data",[])
        list_data = [self._parse_vod(i) for i in items]
        total = len(list_data)
        pagecount = max(1, (total + self.SEARCH_PER_PAGE - 1)//self.SEARCH_PER_PAGE) if total else 1
        return {
            "list": list_data,
            "page": page,
            "pagecount": pagecount,
            "limit": self.SEARCH_PER_PAGE,
            "total": total
        }

    def searchContentPage(self, key, quick, pg):
        return self.searchContent(key, quick, pg)

if __name__ == '__main__':
    s = Spider()
    s.init()
    print("===== homeContent =====")
    h = s.homeContent()
    print("分类数量", len(h.get("class",[])))
    print("首页列表", len(h.get("list",[])))
    print("===== categoryContent =====")
    cat = s.categoryContent("电影",1)
    print("电影第一页", len(cat.get("list",[])))
    print("===== detailContent =====")
    if cat["list"]:
        d = s.detailContent([cat["list"][0]["vod_id"]])
        print(d)
    print("===== searchContent =====")
    sr = s.searchContent("战争")
    print("搜索结果总条数", sr.get("total"))