# -*- coding: utf-8 -*-
# ==========================================================
# 多多影视 | 深度修复版【列表/封面标题/播放线路】
# 适配影视仓 FongMi Spider
# 修复点：
#   1. 列表显示：接口异常兜底、空数据保护、分页修复
#   2. 封面标题：相对路径自动补全、空值占位
#   3. 播放线路：protobuf解码重试、线路空兜底、签名校验
#   4. 首页分类：优先接口动态分类，失败降级静态分类
#   5. 详情页：封面补全、播放源空友好提示
#   6. 搜索：接口异常兜底，不崩溃
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

    STATIC_CATEGORIES = [
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
    DEFAULT_SUBTYPE = {"1": "hits", "2": "hits", "3": "hits", "4": "hits"}

    def init(self, extend=''):
        return {}

    def getName(self):
        return self.name

    def isVideoFormat(self, url):
        low = (url or "").lower()
        return any(k in low for k in (".m3u8", ".mp4", ".mp3", ".m4a", ".flv", ".avi", ".mkv", ".mov", ".ts"))

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

    # ========= protobuf 编码解码 =========
    def _vint(self, n):
        out = b""
        while True:
            b = n & 0x7F
            n >>= 7
            if n:
                out += bytes([b | 0x80])
            else:
                out += bytes([b])
                break
        return out

    def _pb(self, url_str, vf, ts):
        sig_raw = f"finger={self.F}&id={self.ID}&nonce={'0'*32}&sk={self.SK}&time={ts}&v=1"
        sig = hashlib.sha256(sig_raw.encode()).hexdigest().upper()
        parts = [
            b'\x0a', self._vint(len(url_str)), url_str.encode('utf-8'),
            b'\x12', self._vint(len(vf)), vf.encode('utf-8'),
            b'\x18', self._vint(ts),
            b'\x22', self._vint(32), b'0' * 32,
            b'\x2a', self._vint(64), sig.encode('utf-8'),
            b'\x32', self._vint(14), b'com.web.player',
            b'\x38', b'\x01'
        ]
        buf = b""
        for p in parts:
            buf += p
        return buf

    def _parse_pb(self, buf):
        fields = {}
        try:
            arr = bytearray(buf)
            i = 0
            while i < len(arr):
                tag = arr[i]
                i += 1
                f = tag >> 3
                w = tag & 7
                if w == 0:
                    v = 0
                    s = 0
                    while True:
                        x = arr[i]
                        i += 1
                        v |= (x & 0x7F) << s
                        if not (x & 0x80):
                            break
                        s += 7
                    fields[f] = v
                elif w == 2:
                    ln = 0
                    s2 = 0
                    while True:
                        x = arr[i]
                        i += 1
                        ln |= (x & 0x7F) << s2
                        if not (x & 0x80):
                            break
                        s2 += 7
                    sub = arr[i:i + ln]
                    fields[f] = sub.decode("utf-8", "replace")
                    i += ln
                elif w == 5:
                    i += 4
        except Exception as e:
            print(f"[DEBUG] _parse_pb异常:{e}")
        return fields

    # ========= 请求工具，多host轮询 =========
    def _headers(self):
        return {
            "User-Agent": self.UA,
            "web-sign": self.W,
            "X-Client": self.XC,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.host + "/"
        }

    def _fetch_bin(self, path, post_bin=None):
        for candidate in self.HOST_POOL:
            try:
                url = candidate + path
                hd = self._headers()
                if post_bin is not None:
                    hd["Content-Type"] = "application/x-protobuf"
                    hd["Accept"] = "application/x-protobuf"
                    r = self.fetch(url, headers=hd, data=post_bin, timeout=8)
                else:
                    r = self.fetch(url, headers=hd, timeout=8)
                if r and r.status_code == 200:
                    self.host = candidate
                    return r.content
            except Exception as e:
                print(f"[DEBUG] host {candidate} fail:{str(e)}")
                continue
        return b""

    def _get(self, path, params=None):
        try:
            url = self.host + path
            hd = self._headers()
            resp = self.fetch(url, headers=hd, params=params, timeout=8)
            text = resp.text if resp else ""
            return json.loads(text)
        except Exception as e:
            print(f"[DEBUG] _get异常 {path} err:{str(e)}")
            return {}

    # ========= 修复：封面路径补全，标题空值兜底 =========
    def _parse_vod(self, vod):
        vod_id = str(vod.get("vod_id", "")).strip()
        vod_name = str(vod.get("vod_name", "")).strip()
        if not vod_name:
            vod_name = "未知影片"
        vod_pic = str(vod.get("vod_pic", "")).strip()
        if vod_pic:
            if vod_pic.startswith("//"):
                vod_pic = "https:" + vod_pic
            elif vod_pic.startswith("/"):
                vod_pic = self.host + vod_pic
        vod_remarks = str(vod.get("vod_remarks", "")).strip()
        return {
            "vod_id": vod_id,
            "vod_name": vod_name,
            "vod_pic": vod_pic,
            "vod_remarks": vod_remarks
        }

    # ========= homeContent 首页【优先动态分类，降级静态分类】 =========
    def homeContent(self, filter=False):
        ret = {"class": [], "filters": self.FILTERS, "list": []}
        try:
            data = self._get("/api.php/web/index/home")
            cats_data = data.get("data", {}).get("categories", [])
            # 优先接口动态分类
            dynamic_class = []
            for cat in cats_data:
                cid = str(cat.get("type_id", ""))
                cname = str(cat.get("type_name", "")).strip()
                if cid and cname:
                    dynamic_class.append({"type_id": cid, "type_name": cname})
            if len(dynamic_class) > 0:
                ret["class"] = dynamic_class
            else:
                ret["class"] = self.STATIC_CATEGORIES

            for cat in cats_data:
                videos = cat.get("videos", [])
                for item in videos:
                    ret["list"].append(self._parse_vod(item))
            print(f"[DEBUG] homeContent 解析列表:{len(ret['list'])}")
        except Exception as e:
            print(f"[DEBUG] homeContent异常:{str(e)}")
            ret["class"] = self.STATIC_CATEGORIES
        return ret

    def homeVideoContent(self):
        ret = {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 20}
        try:
            data = self._get("/api.php/web/index/home")
            cats_data = data.get("data", {}).get("categories", [])
            for cat in cats_data:
                for item in cat.get("videos", []):
                    ret["list"].append(self._parse_vod(item))
        except Exception:
            pass
        return ret

    # ========= categoryContent 修复分类参数，列表空值兜底 =========
    def categoryContent(self, tid, pg, filter=False, extend=""):
        try:
            page = int(pg or 1)
        except Exception:
            page = 1
        if page < 1:
            page = 1

        ext = extend
        if isinstance(ext, str) and ext.strip().startswith("{"):
            try:
                ext = json.loads(ext)
            except Exception:
                ext = {}
        if not isinstance(ext, dict):
            ext = {}

        ret = {"list": [], "page": page, "pagecount": 9999, "limit": self.PAGE_SIZE, "total": 999999}
        try:
            sub_type = ext.get("subtype", "") or self.DEFAULT_SUBTYPE.get(str(tid), "hits")
            if tid == "all":
                name_param = ""
            else:
                name_param = str(tid)
            params = {"type_name": name_param, "page": page, "sort": sub_type}
            api_data = self._get("/api.php/web/filter/vod", params=params)
            items = api_data.get("data", [])
            if isinstance(items, list) and len(items) > 0:
                ret["list"] = [self._parse_vod(it) for it in items]
                ret["pagecount"] = page + 1
            else:
                ret["pagecount"] = page
            print(f"[DEBUG] categoryContent tid={tid} page={page} list_len={len(ret['list'])}")
        except Exception as e:
            print(f"[DEBUG] categoryContent异常 {str(e)}")
            ret["pagecount"] = page
        return ret

    # ========= detailContent 修复封面、播放线路空兜底 =========
    def detailContent(self, ids):
        rid = ids[0] if isinstance(ids, (list, tuple)) and ids else str(ids or "")
        rid = str(rid).strip()
        ret = {}
        try:
            api_data = self._get("/api.php/web/vod/get_detail", params={"vod_id": rid})
            arr = api_data.get("data", [])
            song = arr[0] if isinstance(arr, list) else arr
            if not song or not isinstance(song, dict):
                ret["list"] = [{
                    "vod_id": rid,
                    "vod_name": "未找到资源",
                    "vod_content": "接口返回空数据",
                    "vod_remarks": "",
                    "vod_play_from": self.name,
                    "vod_play_url": ""
                }]
                return ret
            content_parts = []
            if song.get("vod_class"):
                content_parts.append(f"类型:{song.get('vod_class')}")
            if song.get("vod_year"):
                content_parts.append(f"年份:{song.get('vod_year')}")
            if song.get("vod_area"):
                content_parts.append(f"地区:{song.get('vod_area')}")
            if song.get("vod_actor"):
                content_parts.append(f"演员:{song.get('vod_actor')}")
            if song.get("vod_director"):
                content_parts.append(f"导演:{song.get('vod_director')}")
            if song.get("vod_content"):
                content_parts.append(f"\n简介:\n{song.get('vod_content')}")

            vod_name = str(song.get("vod_name", "")).strip() or "未知影片"
            vod_pic = str(song.get("vod_pic", "")).strip()
            if vod_pic:
                if vod_pic.startswith("//"):
                    vod_pic = "https:" + vod_pic
                elif vod_pic.startswith("/"):
                    vod_pic = self.host + vod_pic

            vod_play_from = str(song.get("vod_play_from", self.name)).strip()
            vod_play_url = str(song.get("vod_play_url", "")).strip()
            # 线路为空友好提示
            if not vod_play_url:
                vod_play_url = "暂无播放源$#"
                vod_play_from = "提示"

            vod = {
                "vod_id": rid,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_content": "\n".join(content_parts),
                "vod_remarks": str(song.get("vod_remarks", "")).strip(),
                "vod_year": str(song.get("vod_year", "")).strip(),
                "vod_area": str(song.get("vod_area", "")).strip(),
                "vod_actor": str(song.get("vod_actor", "")).strip(),
                "vod_director": str(song.get("vod_director", "")).strip(),
                "vod_play_from": vod_play_from,
                "vod_play_url": vod_play_url,
                "type_name": str(song.get("vod_class", "")).strip()
            }
            ret["list"] = [vod]
            print(f"[DEBUG] detailContent vod_name={vod_name} play_url_len={len(vod_play_url)}")
        except Exception as e:
            print(f"[DEBUG] detailContent异常 {str(e)}")
            ret["list"] = [{
                "vod_id": rid,
                "vod_name": "详情加载失败",
                "vod_content": f"异常:{str(e)}",
                "vod_remarks": "",
                "vod_play_from": self.name,
                "vod_play_url": ""
            }]
        return ret

    # ========= playerContent 修复播放线路解码重试、异常捕获 =========
    def playerContent(self, flag, id, flags=None):
        slug = str(id or "").strip()
        if self.isVideoFormat(slug) and slug.startswith("http"):
            return {
                "parse": 0,
                "playUrl": "",
                "url": slug,
                "header": {"User-Agent": self.UA, "Referer": self.host + "/"}
            }
        res = {"parse": 0, "playUrl": "", "url": "", "header": {"User-Agent": self.UA, "Referer": self.host + "/"}}
        try:
            ts = int(time.time())
            bin_payload = self._pb(slug, flag, ts)
            real_url = ""
            # 最多2次重试
            for attempt in range(2):
                bin_resp = self._fetch_bin("/api.php/web/decode/url", post_bin=bin_payload)
                if bin_resp and len(bin_resp) > 0:
                    pb_out = self._parse_pb(bin_resp)
                    if pb_out.get(1) == 1 and pb_out.get(3):
                        real_url = pb_out[3]
                        break
                time.sleep(0.3)
            if real_url and real_url.startswith("http"):
                res["url"] = real_url
                res["header"] = {"User-Agent": self.UA, "Referer": self.host + "/"}
            else:
                print(f"[DEBUG] playerContent 解码未拿到有效url")
        except Exception as e:
            print(f"[DEBUG] playerContent异常:{str(e)}")
        return res

    # ========= searchContent 搜索异常兜底 =========
    def searchContent(self, key, quick=False, pg="1"):
        key = str(key or "").strip()
        if not key:
            return {"list": [], "page": 1, "pagecount": 1, "limit": self.SEARCH_PER_PAGE, "total": 0}
        try:
            page = int(pg or 1)
        except Exception:
            page = 1
        params = {"wd": key, "page": page, "limit": self.SEARCH_PER_PAGE}
        api_data = self._get("/api.php/web/search/index", params=params)
        items = api_data.get("data", [])
        if not isinstance(items, list):
            items = []
        list_data = [self._parse_vod(i) for i in items]
        total = len(list_data)
        pagecount = max(1, (total + self.SEARCH_PER_PAGE - 1) // self.SEARCH_PER_PAGE) if total else 1
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
    print(f"分类数量:{len(h.get('class', []))}, 首页列表:{len(h.get('list', []))}")
    print("===== categoryContent =====")
    cat = s.categoryContent("1", 1)
    print(f"分类第一页列表:{len(cat.get('list', []))}")
