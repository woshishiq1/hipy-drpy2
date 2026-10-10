# coding=utf-8
"""
西瓜TV TVBox 爬虫 - 最终版
加密: AES-256-CTR (Web Crypto API 兼容, counter length=64)
密钥: wK05tMq7sH2aP1cQ6eB9rV3fG4hL8nDx
"""
import re
import sys
import json
import time
import uuid
import base64
import hashlib
import urllib.parse

sys.path.append('..')

try:
    from base.spider import Spider
except ImportError:
    import requests as _rq
    class _BaseSpider:
        def __init__(self): self._session = None
        @property
        def _sess(self):
            if self._session is None:
                self._session = _rq.Session()
                self._session.verify = False
            return self._session
        def fetch(self, url, headers=None, **kw):
            timeout = kw.pop('timeout', 15)
            method = kw.pop('method', 'GET')
            r = self._sess.request(method, url, headers=headers, timeout=timeout, **kw)
            r.encoding = 'utf-8'
            return r
        def log(self, *a, **kw):
            try: print("[xigua]", *a)
            except Exception: pass
    Spider = _BaseSpider

# ==================== 配置 ====================
HOST = "https://by2.xiguatv.xyz"
API = HOST + "/api"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/logo.png"

# ★★★ 已验证的 AES 密钥 ★★★
AES_KEY = b"wK05tMq7sH2aP1cQ6eB9rV3fG4hL8nDx"

try:
    from Crypto.Cipher import AES
    from Crypto.Util import Counter
    HAS_PYCRYPTO = True
except ImportError:
    HAS_PYCRYPTO = False
    print("[xigua] 请先安装: pip install pycryptodome")


# ==================== AES-CTR (Web Crypto API 兼容) ====================
def aes_ctr_encrypt(plain_text: str, key=AES_KEY):
    """AES-CTR 加密, 返回 {data, iv}"""
    if not HAS_PYCRYPTO:
        return None
    # 生成 16 字节 IV
    iv = hashlib.md5((str(time.time()) + str(uuid.uuid4())).encode()).digest()
    # 高 64 位作为 nonce, 低 64 位作为 counter (Web Crypto API length=64)
    prefix = iv[:8]
    initial = int.from_bytes(iv[8:], 'big')
    ctr = Counter.new(64, prefix=prefix, initial_value=initial)
    cipher = AES.new(key, AES.MODE_CTR, counter=ctr)
    ct = cipher.encrypt(plain_text.encode('utf-8'))
    return {
        "data": base64.b64encode(ct).decode(),
        "iv": base64.b64encode(iv).decode(),
    }


def aes_ctr_decrypt(data_b64: str, iv_b64: str, key=AES_KEY):
    """AES-CTR 解密"""
    if not HAS_PYCRYPTO:
        return None
    try:
        iv = base64.b64decode(iv_b64)
        ct = base64.b64decode(data_b64)
        prefix = iv[:8]
        initial = int.from_bytes(iv[8:], 'big')
        ctr = Counter.new(64, prefix=prefix, initial_value=initial)
        cipher = AES.new(key, AES.MODE_CTR, counter=ctr)
        pt = cipher.decrypt(ct)
        return pt.decode('utf-8')
    except Exception as e:
        print("[xigua] 解密失败:", e)
        return None


# ==================== 分类 ====================
CLASSES = [
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "2",  "type_name": "连续剧"},
    {"type_id": "3",  "type_name": "综艺"},
    {"type_id": "4",  "type_name": "动漫"},
    {"type_id": "5",  "type_name": "短剧"},
    {"type_id": "6",  "type_name": "纪录片"},
]

FILTERS = {}


class Spider(Spider):

    def getName(self):
        return "西瓜TV"

    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}

        # 生成一个固定的 deviceId（每个爬虫实例一个）
        self.device_id = hashlib.md5(str(uuid.uuid4()).encode()).hexdigest()
        self.log("deviceId = %s" % self.device_id)

        self.headers = {
            "User-Agent": UA,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Content-Type": "application/json;charset=UTF-8",
            "Origin": HOST,
            "Referer": HOST + "/",
        }
        self._play_cache = {}
        self.log("init ok")

    def _post(self, path: str, body: dict = None, lang="zh_cn"):
        """POST 加密请求, 自动解密返回"""
        if body is None:
            body = {}
        # 关键：每个请求都要带 deviceId
        body["deviceId"] = self.device_id
        body["lang"] = lang

        enc = aes_ctr_encrypt(json.dumps(body, ensure_ascii=False, separators=(',', ':')))
        if not enc:
            return {}

        url = f"{API}{path}?lang={lang}"
        try:
            r = self.fetch(url, headers=self.headers, method="POST",
                           data=json.dumps(enc, separators=(',', ':')),
                           timeout=15)
            text = r.text
            self.log("POST %s -> %s" % (path, text[:120]))
            try:
                resp = json.loads(text)
                if isinstance(resp, dict) and "data" in resp and "iv" in resp:
                    plain = aes_ctr_decrypt(resp["data"], resp["iv"])
                    if plain:
                        return json.loads(plain)
                return resp
            except Exception as e:
                self.log("json parse fail:", e)
                return {}
        except Exception as e:
            self.log("post fail:", e)
            return {}

    # ---------- 首页 ----------
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        data = self._post("/init")
        return {"list": self._parse_list(data)}

    # ---------- 分类 ----------
    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        body = {
            "type_id": tid,
            "page": page,
        }
        if extend and isinstance(extend, dict):
            for k, v in extend.items():
                if v and v != "全部":
                    body[k] = v

        data = self._post("/video/category", body)
        videos = self._parse_list(data)

        return {
            "list": videos,
            "page": page,
            "pagecount": 9999,
            "limit": 24,
            "total": 99999,
        }

    # ---------- 搜索 ----------
    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        data = self._post("/search", {
            "keyword": key,
            "page": page,
        })
        videos = self._parse_list(data)
        return {
            "list": videos,
            "page": page,
            "pagecount": 9999,
            "limit": 24,
            "total": 99999,
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------- 详情 ----------
    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vid = str(ids[0])
        m = re.search(r'(\d+)', vid)
        pure_id = m.group(1) if m else vid

        data = self._post("/video/detail", {"id": int(pure_id)})
        info = self._extract_detail(data)
        if not info:
            return {"list": []}

        name = info.get("name") or info.get("title") or ""
        pic = info.get("pic") or info.get("cover") or DEFAULT_PIC
        content = info.get("content") or info.get("desc") or ""
        area = info.get("area") or ""
        year = info.get("year") or ""
        actor = info.get("actor") or ""
        director = info.get("director") or ""

        episodes = (info.get("episodes")
                    or info.get("play_list")
                    or info.get("playlist")
                    or info.get("urls")
                    or [])

        play_from = "西瓜TV"
        play_url_list = []

        if isinstance(episodes, dict):
            for line_name, eps in episodes.items():
                line_list = []
                if isinstance(eps, list):
                    for i, ep in enumerate(eps):
                        if isinstance(ep, dict):
                            ep_name = ep.get("name") or ep.get("title") or f"第{i+1}集"
                            ep_url = ep.get("url") or ep.get("play_url") or ""
                        elif isinstance(ep, str):
                            ep_name = f"第{i+1}集"
                            ep_url = ep
                        else:
                            continue
                        if ep_url:
                            line_list.append(f"{ep_name}${ep_url}")
                if line_list:
                    play_url_list.append("#".join(line_list))
        elif isinstance(episodes, list):
            line = []
            for ep in episodes:
                if isinstance(ep, dict):
                    ep_name = ep.get("name") or ep.get("title") or ""
                    ep_url = ep.get("url") or ep.get("play_url") or ""
                elif isinstance(ep, list) and len(ep) >= 2:
                    ep_name, ep_url = ep[0], ep[1]
                else:
                    continue
                if ep_url:
                    line.append(f"{ep_name}${ep_url}")
            if line:
                play_url_list = ["#".join(line)]

        return {"list": [{
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_area": area,
            "vod_year": year,
            "vod_remarks": "",
            "vod_play_from": play_from,
            "vod_play_url": "$$$".join(play_url_list) if play_url_list else "",
        }]}

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags):
        play_url = id
        if not play_url.startswith("http"):
            play_url = HOST + play_url

        now = int(time.time())
        if play_url in self._play_cache:
            ts, res = self._play_cache[play_url]
            if now - ts < 600:
                return res

        m = re.search(r'/(\d+)', play_url)
        if m:
            vid = int(m.group(1))
            data = self._post("/video/play", {"id": vid})
            info = data.get("data") if isinstance(data, dict) else None
            if isinstance(info, dict):
                url = info.get("url") or info.get("play_url") or info.get("m3u8") or ""
                if url:
                    res = {
                        "parse": 0, "playUrl": "", "url": url,
                        "header": {"User-Agent": UA, "Referer": HOST + "/"},
                    }
                    self._play_cache[play_url] = (now, res)
                    return res

        try:
            r = self.fetch(play_url, headers=self.headers, timeout=15)
            m = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', r.text)
            if m:
                m3u8 = m.group(1).replace("&amp;", "&")
                res = {
                    "parse": 0, "playUrl": "", "url": m3u8,
                    "header": {"User-Agent": UA, "Referer": HOST + "/"},
                }
                self._play_cache[play_url] = (now, res)
                return res
        except Exception as e:
            self.log("fetch play fail:", e)

        res = {
            "parse": 1, "playUrl": "", "url": play_url,
            "header": {"User-Agent": UA, "Referer": HOST + "/"},
        }
        self._play_cache[play_url] = (now, res)
        return res

    # ---------- 辅助 ----------
    def _extract_detail(self, data):
        if not isinstance(data, dict):
            return None
        for key in ("data", "info", "video", "detail"):
            v = data.get(key)
            if isinstance(v, dict):
                for k2 in ("info", "video", "detail"):
                    if isinstance(v.get(k2), dict):
                        return v[k2]
                return v
        return data if data.get("name") or data.get("title") else None

    def _parse_list(self, data):
        videos = []
        if not isinstance(data, dict):
            return videos
        candidates = []
        for key in ("list", "data", "items", "videos", "result"):
            v = data.get(key)
            if isinstance(v, list):
                candidates = v
                break
            if isinstance(v, dict):
                for k2 in ("list", "items", "data"):
                    if isinstance(v.get(k2), list):
                        candidates = v[k2]
                        break
                if candidates:
                    break
        if not candidates and isinstance(data.get("data"), list):
            candidates = data["data"]

        for item in candidates:
            if not isinstance(item, dict):
                continue
            vid = item.get("id") or item.get("vod_id") or ""
            name = item.get("name") or item.get("title") or ""
            pic = item.get("pic") or item.get("cover") or DEFAULT_PIC
            remark = item.get("remark") or item.get("note") or ""
            if not vid:
                continue
            videos.append({
                "vod_id": f"/video/{vid}",
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": remark,
            })
        return videos

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()
