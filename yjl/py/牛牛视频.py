#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
牛牛视频 爬虫 (from APK _1.6.2.apk)
分类固定 10 个: 电影/剧集/综艺/动漫/短剧 走 src2 (3DES-CBC, dy.wnhyjc.com, 短剧=type_pid 31);
传媒/吃瓜/福利/午夜/热舞走 xxcjpt.com (反转base64, 封面AES-128-ECB)
"""
import base64
import hashlib
import json
import os
import re
import socket
import tempfile
import time
import uuid
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote, unquote, urljoin
from Crypto.Cipher import DES3, AES
from Crypto.Util.Padding import pad, unpad

try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider:
        pass


class _Crypto:
    """3DES-CBC 加解密 (src2: iv=51518888, key=ZT8g6QH2kS3Xj7G5wG4JtU1F)"""

    @staticmethod
    def des3_encrypt(data, key, iv):
        cipher = DES3.new(key.encode("utf-8"), DES3.MODE_CBC, iv.encode("utf-8"))
        ct = cipher.encrypt(pad(data.encode("utf-8"), DES3.block_size))
        return base64.b64encode(ct).decode("ascii")

    @staticmethod
    def des3_decrypt(data, key, iv):
        raw = base64.b64decode(data)
        cipher = DES3.new(key.encode("utf-8"), DES3.MODE_CBC, iv.encode("utf-8"))
        pt = unpad(cipher.decrypt(raw), DES3.block_size)
        return pt.decode("utf-8")


# ========== DNS DoH Pin (部分数据源域名被系统 DNS 污染解析到 127.0.0.2, 用 DoH 获取真实 IP) ==========
_PIN_MAP = {}
_PIN_INSTALLED = [False]


def _install_pin():
    if _PIN_INSTALLED[0]:
        return
    _PIN_INSTALLED[0] = True
    _orig = socket.getaddrinfo

    def _pinned(host, port, *args, **kwargs):
        _ips = _PIN_MAP.get(host)
        if _ips:
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port)) for ip in _ips]
        return _orig(host, port, *args, **kwargs)

    socket.getaddrinfo = _pinned


def _doh_resolve(hostname):
    _doh_list = [
        "https://doh.pub/dns-query",
        "https://dns.alidns.com/resolve",
        "https://dns.google/resolve",
        "https://cloudflare-dns.com/dns-query",
    ]
    picked = []
    for _u in _doh_list:
        try:
            _r = requests.get(_u, params={"name": hostname, "type": "A"},
                              headers={"accept": "application/dns-json"}, timeout=6, verify=False)
            _j = _r.json()
            for _a in _j.get("Answer", []):
                if _a.get("type") == 1 and _a.get("data"):
                    _d = _a["data"]
                    if _d and not _d.startswith("0."):
                        picked.append(_d)
            if picked:
                break
        except Exception:
            continue
    return picked


def _doh_pin_domain(hostname):
    try:
        if not hostname or hostname in _PIN_MAP:
            return
        _install_pin()
        picked = _doh_resolve(hostname)
        if picked:
            _PIN_MAP[hostname] = picked
    except Exception:
        pass


def _pin_url_host(url):
    try:
        _m = re.match(r"https?://([^/:]+)", url or "")
        if _m:
            _doh_pin_domain(_m.group(1))
    except Exception:
        pass


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://dy.wnhyjc.com"
        self.init_url = "http://49.233.217.152:5112/api/user/init"
        self.list_url = "/api/vod/info"
        self.play_url = "/api/vod/play_url"
        self.iv = "51518888"
        self.key = "ZT8g6QH2kS3Xj7G5wG4JtU1F"
        self.replace_domain = "http://xs85.ruxiangsuisu.cn"
        self.play_domain = ""
        self.token = ""
        self.name = "牛牛视频"
        self.device_id = uuid.uuid4().hex
        self.session = requests.Session()
        self.session.headers.update({
            "appid": "jijing",
            "Version-Code": "10000",
            "Channel": "share",
            "Sys-Release": "11",
            "prefersex": "1",
            "Sys-Platform": "Android",
            "User-Agent": "Android",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/vnd.yourapi.v1.full+json",
            "device-id": self.device_id,
        })
        self.class_cache = None
        self.filter_cache = {}
        self.token_time = 0
        self.page_size = 20
        # xxcjpt.com 成人源 (传媒/吃瓜/福利/午夜/热舞)
        self._xxcjpt_token = "66b30e51a0ab342bc76502b698399356"
        self._xxcjpt_headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "origin": "https://sixth.xxcjpt.com",
            "user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 abab/113eyhy5u7lhz52p1owi",
            "cookie": "device=113eyhy5u7lhz52p1owi",
        }

    def init(self, extend=""):
        if extend:
            try:
                cfg = json.loads(extend)
                if cfg.get("site"):
                    self.host = cfg["site"].rstrip("/")
                if cfg.get("iv"):
                    self.iv = cfg["iv"]
                if cfg.get("key"):
                    self.key = cfg["key"]
                if cfg.get("replace_domain"):
                    self.replace_domain = cfg["replace_domain"]
                if cfg.get("init_url"):
                    self.init_url = cfg["init_url"]
                if cfg.get("xxcjpt_token"):
                    self._xxcjpt_token = cfg["xxcjpt_token"]
            except Exception:
                pass
        self._get_token()

    def getName(self):
        return self.name

    # ========== Token管理 ==========

    def _get_token(self):
        if self.token and time.time() - self.token_time < 3600:
            return
        try:
            r = requests.post(self.init_url, data="password=&account=", timeout=15, verify=False,
                              headers=self.session.headers)
            r.raise_for_status()
            data = self._decrypt(r.json().get("data", ""))
            if data and data.get("code") == 10000:
                result = data.get("result", {})
                user_info = result.get("user_info", {})
                self.token = user_info.get("token", "")
                sys_conf = result.get("sys_conf", {})
                if sys_conf.get("host_main"):
                    self.host = sys_conf["host_main"].rstrip("/")
                if sys_conf.get("play_domain"):
                    self.play_domain = sys_conf["play_domain"]
                self.token_time = time.time()
        except Exception:
            pass

    def _decrypt(self, enc_str):
        if not enc_str:
            return {}
        try:
            enc_str = enc_str.replace("\n", "").replace(" ", "").replace("\r", "")
            return json.loads(_Crypto.des3_decrypt(enc_str, self.key, self.iv))
        except Exception:
            try:
                return json.loads(enc_str)
            except Exception:
                return {}

    def _api_post(self, path, params=None):
        self._get_token()
        url = self.host + path if path.startswith("/") else path
        headers = dict(self.session.headers)
        if self.token:
            headers["token"] = self.token
        for attempt in range(2):
            try:
                r = requests.post(url, data=params or {}, headers=headers, timeout=15, verify=False)
                r.raise_for_status()
                data = self._decrypt(r.json().get("data", ""))
                if data:
                    return data
            except Exception:
                pass
            if attempt == 0:
                time.sleep(1)
        return {}

    def _xxcjpt_decode(self, text):
        """xxcjpt.com响应: 反转字符串 → base64解码 → JSON"""
        if not text or text.startswith("Error"):
            return None
        try:
            rev = text[::-1]
            pad = len(rev) % 4
            if pad:
                rev += "=" * (4 - pad)
            raw = base64.b64decode(rev)
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return None

    def _xxcjpt_get(self, vid):
        """调用xxcjpt.com获取视频数据"""
        url = "https://sixth.xxcjpt.com/java/show/%s" % vid
        body = "token=%s&vid=%s&spm=home.latest" % (self._xxcjpt_token, vid)
        try:
            r = requests.post(url, data=body, headers=self._xxcjpt_headers, timeout=15, verify=False)
            return self._xxcjpt_decode(r.text)
        except Exception:
            return None

    # ========== 固定分类 (电影/剧集/综艺/动漫/短剧=src2, 传媒/吃瓜/福利/午夜/热舞=xxcjpt) ==========
    _FALLBACK_CLASSES = [
        {"type_id": "1", "type_name": "电影"},
        {"type_id": "2", "type_name": "剧集"},
        {"type_id": "3", "type_name": "综艺"},
        {"type_id": "4", "type_name": "动漫"},
        {"type_id": "5", "type_name": "短剧"},
        {"type_id": "7", "type_name": "传媒"},
        {"type_id": "8", "type_name": "吃瓜"},
        {"type_id": "9", "type_name": "福利"},
        {"type_id": "10", "type_name": "午夜"},
        {"type_id": "11", "type_name": "热舞"},
    ]

    # src2 各分类的 id 簇 (枚举实测: 内容按 id 段聚集, 段间有巨大空洞)
    _SRC2_CLUSTERS = {
        "1": [(1, 7000), (100000, 101000)],
        "2": [(100000, 103000), (155000, 155600)],
        "3": [(100000, 103000), (155000, 155600)],
        "4": [(100000, 103000), (155000, 155600)],
        "5": [(155000, 160000), (100000, 100300)],
    }

    # 分类tid → src2 type_pid 映射 (电影/剧集/综艺/动漫/短剧 走src2; 短剧=pid 31)
    _PID_MAP = {"1": "1", "2": "2", "3": "3", "4": "4", "5": "31"}

    # 每分类每页扫描的 id 数 (按实测密度定制; 实际每页扫描 step*2 个 id, 控制在 src2 限流阈值内)
    _SRC2_STEP = {"1": 70, "2": 30, "3": 60, "4": 60, "5": 70}

    # xxcjpt.com 各分类的关键词过滤 (传媒按子分类, 其余按整分类; 短剧走src2)
    _XC_KEYWORDS = {
        "5": ["剧情", "人妻", "二次元", "JK", "女仆", "制服", "cos", "nana", "狐不妖"],
        "7": {
            "探花偷拍": ["探花", "偷拍", "约炮", "网约", "外卖", "上门", "真实", "自拍"],
            "剧情人妻": ["剧情", "人妻", "姐夫", "嫂子", "表妹", "邻居", "出轨", "小三", "房东"],
            "丝袜制服": ["丝袜", "黑丝", "白丝", "制服", "足交", "高跟鞋", "包臀"],
            "萝莉调教": ["萝莉", "调教", "少女", "校花", "青春", "清纯"],
            "熟女阿姨": ["熟女", "阿姨", "妈妈", "丰满", "丰腴", "熟妇"],
            "国产自拍": ["国产", "自拍", "素人", "偷拍"],
        },
        "8": ["吃瓜", "偷拍", "泄密", "爆料", "真实", "网约", "曝光", "泄露"],
        "9": ["福利", "私拍", "独家", "泄露", "流出"],
        "10": ["午夜", "深夜", "夜色", "凌晨", "夜间", "夜夜"],
        "11": ["舞蹈", "热舞", "秀场", "直播", "扭腰", "钢管"],
    }

    # xxcjpt index 的 spm 参数, 不同分类使用不同 spm 以增加内容差异
    _XC_SPM = {"5": "latest", "7": "home.latest", "8": "home.hot", "9": "home.new", "10": "home.recommend", "11": "latest"}

    _FALLBACK_FILTERS = {
        "1": {
            "class": "剧情,武侠,战争,奇幻,犯罪,同性,动作,喜剧,爱情,科幻,悬疑,恐怖,动画,纪录片",
            "area": "内地,美国,韩国,日本,法国,英国,泰国,香港,台湾,菲律宾",
            "lang": "国语,英语,粤语,韩语,日语,泰语,法语",
            "year": "2027,2026,2025,2024,2023,2022,2021,2020,2019,2018,2017,2016,2015,2014,2013,2012,2011,2010,2009,2008,2007,2006,2005,2004,2003,2002,2001,1999,1998",
        },
        "2": {
            "class": "剧情,古装,历史,都市,动作,喜剧,爱情,科幻,悬疑,恐怖,动画,武侠,战争,奇幻,犯罪,同性,纪录片",
            "area": "内地,美国,韩国,日本,法国,英国,泰国,香港,台湾",
            "lang": "国语,英语,粤语,韩语,日语,泰语,法语",
            "year": "2027,2026,2025,2024,2023,2022,2021,2020,2019,2018,2017,2016,2015,2014,2013,2012,2011,2010,2009,2008,2007,2006,2005,2004,2003,2002,2001,1999,1998",
        },
        "3": {
            "class": "纪录片,真人秀,相声,脱口秀,音乐",
            "area": "内地,美国,韩国,日本,法国,英国,泰国,香港,台湾",
            "lang": "国语,英语,粤语,韩语,日语,泰语,法语",
            "year": "2027,2026,2025,2024,2023,2022,2021,2020,2019,2018,2017,2016,2015,2014,2013,2012,2011,2010,2009,2008,2007,2006,2005,2004,2003,2002,2001,1999,1998",
        },
        "4": {
            "class": "热血,搞笑,运动,动作,喜剧,爱情,科幻,冒险,恋爱,励志,推理,校园,奇幻,竞技,恐怖,同性",
            "area": "内地,美国,韩国,日本,法国,英国,香港,台湾",
            "lang": "国语,英语,粤语,韩语,日语,法语",
            "year": "2027,2026,2025,2024,2023,2022,2021,2020,2019,2018,2017,2016,2015,2014,2013,2012,2011,2010,2009,2008,2007,2006,2005,2004,2003,2002,2001,1999,1998",
        },
        "5": {
            "class": "都市,古风,玄幻,漫剧,逆袭,年代,总裁,大女主,大男主,家庭,喜剧,重生,穿越,悬疑",
        },
        "7": {
            "class": "探花偷拍,剧情人妻,丝袜制服,萝莉调教,熟女阿姨,国产自拍",
        },
    }

    def _classes(self):
        """固定分类列表 (短剧/电影/剧集/综艺/动漫=src2, 成人分类来自xxcjpt)"""
        if self.class_cache:
            return self.class_cache
        self.class_cache = [dict(c) for c in self._FALLBACK_CLASSES]
        return self.class_cache

    def _filters(self, classes):
        """生成筛选, 从固定分类表提取"""
        fs = {}
        for c in classes:
            tid = c["type_id"]
            ext = self._FALLBACK_FILTERS.get(tid, {})
            filters = []
            if ext.get("class"):
                vals = [{"n": v, "v": v} for v in ext["class"].split(",")]
                filters.append({"key": "class", "name": "类型", "value": vals})
            if ext.get("area"):
                vals = [{"n": v, "v": v} for v in ext["area"].split(",")]
                filters.append({"key": "area", "name": "地区", "value": vals})
            if ext.get("lang"):
                vals = [{"n": v, "v": v} for v in ext["lang"].split(",")]
                filters.append({"key": "lang", "name": "语言", "value": vals})
            if ext.get("year"):
                vals = [{"n": v, "v": v} for v in ext["year"].split(",")]
                filters.append({"key": "year", "name": "年份", "value": vals})
            fs[tid] = filters
        return fs

    # ========== TVBox Spider 接口 ==========

    def _fetch_batch(self, vid_list, max_workers=10):
        """并发获取多个vod_id的详情"""
        results = {}
        def fetch(vid):
            data = self._api_post(self.list_url, {"vod_id": str(vid)})
            result = data.get("result")
            if result and isinstance(result, dict) and result.get("title"):
                return vid, result
            return vid, None
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(fetch, vid): vid for vid in vid_list}
            for f in as_completed(futures):
                vid, result = f.result()
                if result:
                    results[vid] = result
        return results

    def homeContent(self, filter):
        classes = self._classes()
        batch = self._fetch_batch(range(1, 13))
        items = [self._vod_from_detail(batch[vid]) for vid in sorted(batch.keys())]
        return {
            "class": classes,
            "filters": self._filters(classes),
            "list": items,
        }

    def homeVideoContent(self):
        batch = self._fetch_batch(range(1, 7))
        items = [self._vod_from_detail(batch[vid]) for vid in sorted(batch.keys())]
        return {"list": items}

    def categoryContent(self, tid, pg, filter, extend):
        extend = extend or {}
        pg = int(pg) if str(pg).isdigit() else 1

        # 短剧/电影/剧集/综艺/动漫: src2 API 按 id 簇扫描过滤 type_pid
        if str(tid) in ("1", "2", "3", "4", "5"):
            return self._src2_category(tid, pg, extend)

        # 传媒/吃瓜/福利/午夜/热舞: xxcjpt.com 成人源 (传媒按子分类关键词)
        return self._xxcjpt_category(tid, pg, extend)

    def _src2_pool(self, tid):
        """拼接该分类的候选 id 簇 (src2内容按id段聚集, 段间有空洞)"""
        pool = []
        for lo, hi in self._SRC2_CLUSTERS.get(str(tid), []):
            pool.extend(range(lo, hi))
        return pool

    def _cache_dir(self):
        try:
            d = os.path.join(tempfile.gettempdir(), "niuniu_py")
            os.makedirs(d, exist_ok=True)
            return d
        except Exception:
            return tempfile.gettempdir()

    def _src2_category(self, tid, pg, extend):
        """src2分类: 从候选id簇中扫描, 过滤 type_pid (控制扫描量避免触发限流)"""
        want_pid = self._PID_MAP.get(str(tid), str(tid))
        pool = self._src2_pool(tid)
        if not pool:
            return {"page": pg, "pagecount": pg, "limit": self.page_size, "total": 0, "list": []}

        # 分类页缓存: 降低 src2 请求压力, 规避限流
        cache_key = "cat_%s_%s_%s" % (tid, pg, extend.get("class") or "")
        cache_path = os.path.join(self._cache_dir(), cache_key + ".json")
        try:
            if os.path.exists(cache_path) and time.time() - os.path.getmtime(cache_path) < 1800:
                with open(cache_path, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                if cached.get("list"):
                    return cached
        except Exception:
            pass

        total = len(pool)
        step = self._SRC2_STEP.get(str(tid), 100)
        start = ((pg - 1) * step) % total
        picked = []
        seen = set()
        for k in range(2):
            for i in range(step):
                v = pool[(start + k * step + i) % total]
                if v not in seen:
                    seen.add(v)
                    picked.append(v)

        batch = self._fetch_batch(picked, max_workers=12)

        # src2 有请求速率限制: 批量请求成功率过低时等待后重试一次
        if len(batch) < max(1, len(picked) * 0.3):
            time.sleep(3)
            batch = self._fetch_batch(picked, max_workers=12)

        items = []
        for vid in sorted(batch.keys()):
            result = batch[vid]
            pid = str(result.get("type_pid", ""))
            tags = result.get("tags") or ""
            is_short = "短剧" in tags
            if str(tid) == "5":
                # 短剧: type_pid=31 或 tags 含"短剧" (100000 段的短剧标为 pid=2)
                ok = pid == "31" or is_short
            elif str(tid) == "2":
                # 剧集: type_pid=2 且排除短剧
                ok = pid == "2" and not is_short
            else:
                ok = pid == want_pid
            if ok:
                if self._match_filter(result, extend):
                    items.append(self._vod_from_detail(result))
            if len(items) >= self.page_size:
                break

        pagecount = pg + 1 if items else pg
        result = {
            "page": pg,
            "pagecount": pagecount,
            "limit": self.page_size,
            "total": 99999,
            "list": items,
        }
        if items:
            try:
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False)
            except Exception:
                pass
        return result

    def _xxcjpt_index(self, spm, page, pages=4):
        """翻页获取 xxcjpt index 内容列表 [{id,title,image,duration}]"""
        out = []
        seen = set()
        for p in range(page, page + pages):
            try:
                r = requests.post(
                    "https://sixth.xxcjpt.com/java/index",
                    data="token=%s&spm=%s&page=%d" % (self._xxcjpt_token, spm, p),
                    headers=self._xxcjpt_headers, timeout=12, verify=False,
                )
                data = self._xxcjpt_decode(r.text)
                lst = (data or {}).get("data", {}).get("list", []) or []
                for it in lst:
                    if it.get("id") is not None and it["id"] not in seen:
                        seen.add(it["id"])
                        out.append(it)
            except Exception:
                break
            if len(out) >= pages * 20:
                break
        return out

    def _xx_img(self, url):
        """xxcjpt封面: 返回本地代理URL, 由localProxy解密(AES-128-ECB)"""
        if not url:
            return ""
        try:
            b = self.getProxyUrl()
            if "?" not in b:
                b += "?do=py"
            return b + "&type=img&url=" + quote(url, safe="")
        except Exception:
            return url

    def localProxy(self, param):
        """本地代理: 解密xxcjpt封面(AES-128-ECB)"""
        try:
            if not isinstance(param, dict):
                param = {}
            pt = param.get("type") or param.get("do") or ""
            u = param.get("url", "")
            if pt == "img" and u:
                r = requests.get(unquote(u), headers=self._xxcjpt_headers, timeout=15, verify=False)
                ct = base64.b64decode(r.text.strip())
                cipher = AES.new(b"976f97d638360cde", AES.MODE_ECB)
                data = unpad(cipher.decrypt(ct), AES.block_size)
                m = re.match(rb"^data:(.*?);base64,(.*)$", data)
                if m:
                    img = base64.b64decode(m.group(2))
                    return [200, m.group(1).decode("ascii"), img]
            return [404, "text/plain", b"nf"]
        except Exception:
            return [500, "text/plain", b"err"]

    def _xx_item(self, it):
        return {
            "vod_id": "x_%s" % it.get("id"),
            "vod_name": it.get("title", "") or "",
            "vod_pic": self._xx_img(it.get("image", "") or ""),
            "vod_remarks": self._format_duration(it.get("duration", 0)),
        }

    def _xxcjpt_category(self, tid, pg, extend):
        """xxcjpt.com分类: 传媒(tid=7, 按子分类关键词) / 吃瓜(8) / 福利(9) / 午夜(10) / 热舞(11)"""
        page_size = self.page_size
        tid = str(tid)
        spm = self._XC_SPM.get(tid, "home.latest")

        kws = []
        if tid == "7":
            sub = extend.get("class") or ""
            kws = self._XC_KEYWORDS["7"].get(sub, [])
        elif tid in self._XC_KEYWORDS:
            kws = self._XC_KEYWORDS[tid]

        items = []

        # 吃瓜分类: 优先枚举探花真实段 (id 10000+) 补充真实事件内容
        if tid == "8":
            x_start = 10000 + (pg - 1) * 10
            x_vids = list(range(x_start, x_start + 10))
            def x_fetch(vid):
                data = self._xxcjpt_get(str(vid))
                if data and data.get("code") == 1:
                    v = data.get("data", {}).get("video", {})
                    if v and v.get("title"):
                        return self._xx_item(v)
                return None
            with ThreadPoolExecutor(max_workers=10) as pool:
                futures = [pool.submit(x_fetch, vid) for vid in x_vids]
                for f in as_completed(futures):
                    r = f.result()
                    if r:
                        items.append(r)
                    if len(items) >= page_size:
                        break

        feed = self._xxcjpt_index(spm, pg, pages=4)
        picked = []
        for it in feed:
            title = it.get("title") or ""
            if not title:
                continue
            if not kws or any(k in title for k in kws):
                picked.append(it)

        if len(items) < page_size:
            for it in picked:
                items.append(self._xx_item(it))
                if len(items) >= page_size:
                    break

        # 关键词命中不足 → 用最新流兜底, 保证分类有内容
        if len(items) < page_size:
            for it in feed:
                if it in picked:
                    continue
                items.append(self._xx_item(it))
                if len(items) >= page_size:
                    break

        pagecount = pg + 1 if items else pg
        return {
            "page": pg,
            "pagecount": pagecount,
            "limit": page_size,
            "total": 99999,
            "list": items[:page_size],
        }

    def detailContent(self, ids):
        vid = str(ids[0])

        # xxcjpt源 (id以x_开头)
        if vid.startswith("x_"):
            return self._xxcjpt_detail(vid[2:])

        # src2源
        data = {}
        for _ in range(3):
            data = self._api_post(self.list_url, {"vod_id": vid})
            if data.get("result"):
                break
            time.sleep(2)
        result = data.get("result")

        if not result or not isinstance(result, dict):
            return {"list": []}

        name = result.get("title") or vid
        pic = result.get("pic") or ""
        year = result.get("year") or ""
        area = result.get("area") or ""
        typename = result.get("tags") or ""
        actor = result.get("actor") or ""
        director = result.get("director") or ""
        content = result.get("intro") or ""
        remarks = result.get("remarks") or ""

        map_list = result.get("map_list") or []
        eps = []
        seen_eps = set()
        for m in map_list:
            mid = str(m.get("id", ""))
            title = str(m.get("title") or "高清")
            # 数字标题 = 集数 (短剧/动漫每集一个 map); 其余为清晰度/分组名
            if title.isdigit():
                key = ("ep", title)
                if key in seen_eps:
                    continue
                seen_eps.add(key)
                eps.append("第%s集$%s_%s" % (title, vid, mid))
            else:
                eps.append("%s$%s_%s" % (title, vid, mid))

        play_url = "#".join(eps) if eps else "高清$%s_1" % vid

        vod = {
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": pic,
            "vod_year": year,
            "vod_area": area,
            "type_name": typename,
            "vod_actor": actor,
            "vod_director": director,
            "vod_content": content,
            "vod_remarks": remarks,
            "vod_play_from": self.name,
            "vod_play_url": play_url,
        }
        return {"list": [vod]}

    def _xxcjpt_detail(self, vid):
        """xxcjpt.com视频详情"""
        data = self._xxcjpt_get(vid)
        if not data or data.get("code") != 1:
            return {"list": []}

        d = data.get("data", {})
        video = d.get("video", {})
        if not video:
            return {"list": []}

        title = video.get("title") or vid
        pic = video.get("image") or ""
        duration = self._format_duration(video.get("duration", 0))
        content = " ".join(video.get("content", []))
        src = video.get("src") or ""

        guess = d.get("guess", [])
        play_url = "高清$x_%s" % vid

        vod = {
            "vod_id": "x_%s" % vid,
            "vod_name": title,
            "vod_pic": self._xx_img(pic),
            "vod_year": "",
            "vod_area": "",
            "type_name": "",
            "vod_actor": "",
            "vod_director": "",
            "vod_content": content,
            "vod_remarks": duration,
            "vod_play_from": self.name,
            "vod_play_url": play_url,
        }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        pg = int(pg) if str(pg).isdigit() else 1

        # 1) src2 API: 并发枚举多个id簇, 匹配标题/演员/导演
        #    (电影簇1-100 + 剧集/综艺/动漫簇100000-100060 + 短剧簇155000-155040)
        search_segments = [
            range(1, 101),
            range(100000, 100070),
            range(155000, 155050),
        ]
        vids = []
        for seg in search_segments:
            vids.extend(seg)
        batch = self._fetch_batch(vids, max_workers=20)
        items = []
        for vid in sorted(batch.keys()):
            result = batch[vid]
            title = result.get("title", "")
            actor = result.get("actor", "")
            director = result.get("director", "")
            if key in title or key in actor or key in director:
                items.append(self._vod_from_detail(result))
            if len(items) >= 20:
                break

        # 2) xxcjpt.com: 并发枚举 10000 段, 匹配标题
        if len(items) < 10:
            x_vids = list(range(10000, 10060))
            def x_search(vid):
                data = self._xxcjpt_get(str(vid))
                if data and data.get("code") == 1:
                    video = data.get("data", {}).get("video", {})
                    if video and key in (video.get("title") or ""):
                        return {
                            "vod_id": "x_%s" % video.get("id", vid),
                            "vod_name": video.get("title", ""),
                            "vod_pic": video.get("image", ""),
                            "vod_remarks": self._format_duration(video.get("duration", 0)),
                        }
                return None
            with ThreadPoolExecutor(max_workers=12) as pool:
                futures = [pool.submit(x_search, vid) for vid in x_vids]
                for f in as_completed(futures):
                    r = f.result()
                    if r:
                        items.append(r)
                    if len(items) >= 20:
                        break

        pagecount = pg + 1 if len(items) >= self.page_size else pg
        return {
            "page": pg,
            "pagecount": pagecount,
            "limit": self.page_size,
            "total": 99999,
            "list": items,
        }

    def playerContent(self, flag, id, vipFlags):
        s = str(id)

        # xxcjpt源 (id以x_开头)
        if s.startswith("x_"):
            vid = s[2:]
            data = self._xxcjpt_get(vid)
            if data and data.get("code") == 1:
                src = data.get("data", {}).get("video", {}).get("src", "")
                if src:
                    header = {
                        "User-Agent": "Mozilla/5.0 (Linux; Android 11) AppleWebKit/537.36",
                        "Referer": "https://sixth.xxcjpt.com",
                    }
                    return {
                        "parse": 0,
                        "playUrl": "",
                        "url": src,
                        "header": json.dumps(header),
                    }
            return {"parse": 1, "playUrl": "", "url": ""}

        # src2源: id格式 vod_id_vod_map_id
        parts = s.split("_")
        vid = parts[0]
        vod_map_id = parts[1] if len(parts) > 1 else "1"

        data = self._api_post(self.play_url, {"vod_id": vid, "vod_map_id": vod_map_id})
        result = data.get("result", {})
        url = result.get("vod_url") or ""

        if not url:
            return {"parse": 1, "playUrl": "", "url": ""}

        header = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 11) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Referer": self.host,
        }
        return {
            "parse": 0,
            "playUrl": "",
            "url": url,
            "header": json.dumps(header),
        }

    def isVideoContent(self):
        return True

    # ========== 内部方法 ==========

    def _list(self, data):
        if isinstance(data, list):
            return data
        if not isinstance(data, dict):
            return []
        for key in ("list", "items", "data", "result", "rows"):
            val = data.get(key)
            if isinstance(val, list):
                return val
            if isinstance(val, dict):
                return self._list(val)
        return []

    def _vod_from_detail(self, result):
        return {
            "vod_id": str(result.get("vod_id") or result.get("id") or ""),
            "vod_name": result.get("title") or "",
            "vod_pic": result.get("pic") or "",
            "vod_remarks": result.get("remarks") or "",
        }

    def _match_filter(self, result, extend):
        if extend.get("class") and extend["class"] not in (result.get("tags") or ""):
            return False
        if extend.get("area") and extend["area"] not in (result.get("area") or ""):
            return False
        if extend.get("year") and extend["year"] != (result.get("year") or ""):
            return False
        return True

    def _format_duration(self, seconds):
        if not seconds:
            return ""
        try:
            seconds = int(seconds)
            m = seconds // 60
            s = seconds % 60
            return "%02d:%02d" % (m, s)
        except Exception:
            return ""
