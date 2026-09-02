import sys
sys.path.append('..')

import json
import base64
import re
import socket
import requests
from urllib.parse import quote, unquote
from Crypto.Cipher import AES
from base.spider import Spider

_PIN_MAP = {}
_PIN_INSTALLED = [False]
_POISON_IP_PREFIX = ('31.13.94.', '31.13.95.', '75.126.', '157.240.')
_PIN_CACHE_TTL = [1800]
_PIN_TIME = {}


def _install_pin():
    if _PIN_INSTALLED[0]:
        return
    _PIN_INSTALLED[0] = True
    _orig = socket.getaddrinfo

    def _pinned(host, port, *args, **kwargs):
        _ips = _PIN_MAP.get(host)
        if _ips:
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (ip, port)) for ip in _ips]
        return _orig(host, port, *args, **kwargs)

    socket.getaddrinfo = _pinned


def _doh_resolve(hostname):
    _doh_list = [
        'https://doh.pub/dns-query',
        'https://dns.alidns.com/resolve',
        'https://dns.google/resolve',
        'https://cloudflare-dns.com/dns-query',
    ]
    picked = []
    for _u in _doh_list:
        try:
            _r = requests.get(_u, params={'name': hostname, 'type': 'A'},
                              headers={'accept': 'application/dns-json'}, timeout=6, verify=False)
            _j = _r.json()
            for _a in _j.get('Answer', []):
                if _a.get('type') == 1 and _a.get('data'):
                    _d = _a['data']
                    if _d and not _d.startswith('0.'):
                        if _d.startswith(_POISON_IP_PREFIX):
                            continue
                        picked.append(_d)
            if picked:
                break
        except Exception:
            continue
    return picked


def _doh_pin_domain(hostname, fallback=None):
    """国内 DNS 污染时,通过 DoH 获取真实 IP,并钉扎域名解析,绕过被劫持的系统 DNS。
    仅对指定 hostname 生效,不影响其他域名解析。DoH 失败时可用 fallback IP 兜底。
    已钉扎的域名在缓存期内直接复用,避免每个分片请求都重复 DoH 查询拖慢播放。"""
    try:
        if not hostname:
            return
        _install_pin()
        import time
        _now = time.time()
        if hostname in _PIN_MAP and _now - _PIN_TIME.get(hostname, 0) < _PIN_CACHE_TTL[0]:
            return
        picked = _doh_resolve(hostname)
        if not picked and fallback:
            picked = list(fallback)
        elif fallback:
            picked = list(dict.fromkeys(list(fallback) + picked))
        if picked:
            _PIN_MAP[hostname] = picked
            _PIN_TIME[hostname] = _now
    except Exception:
        pass


def _pin_url_host(url):
    try:
        _m = re.match(r'https?://([^/:]+)', url or '')
        if _m:
            _doh_pin_domain(_m.group(1))
    except Exception:
        pass


# 站点分类 value 最新实测值；contentOptions 可拉取时优先使用实时值，失败用此兜底
_DEFAULT_THEME_VAL = {"成人": 24, "51原创": 47, "种田": 14, "志怪": 19, "脑洞": 10}
_DEFAULT_SETTING_VAL = {"大男主": 2, "大女主": 1, "重生": 27, "穿越": 28, "系统": 29, "双向奔赴": 48,
                        "互相救赎": 50, "甜宠": 49, "传承觉醒": 38, "家长里短": 37, "强者回归": 33,
                        "先婚后爱": 32, "虐恋": 35, "小人物": 31, "神豪": 30, "马甲": 26, "打脸虐渣": 25}
_DEFAULT_BG_VAL = {"校园": 54, "架空": 53, "民国": 52, "职场": 45, "年代": 44, "现代": 40, "都市": 41,
                   "古代": 42, "乡村": 43}


class Spider(Spider):
    def init(self, extend=""):
        self.host = "https://adjust.cbpjoocbe.com"
        self.api_host = "https://api.51dj1.com"
        self.play_aes_key = "2acf7e91e9864673"
        self.play_aes_iv = "1c29882d3ddfcfd6"
        self.img_aes_key = "f5d965df75336270"
        self.img_aes_iv = "97b60394abc2fbe1"
        self.oauth_id = ""
        # 站点分类 value 会不定时重新编排（如成人曾 47->24），故按名称引用、运行时动态解析。
        # backgrounds 为全量背景（校园/架空/民国/职场/年代/现代/都市/古代/乡村），
        # 顺序按当前实测"该主分类下有内容者优先"排列，其余补在后面。
        self.cat_map = [
            {"type_id": "adult", "type_name": "成人", "theme_name": "成人",
             "settings": ["大男主", "大女主", "打脸虐渣", "穿越", "虐恋", "小人物", "甜宠", "系统", "互相救赎", "神豪", "马甲"],
             "backgrounds": ["职场", "现代", "都市", "古代", "乡村", "校园", "架空", "民国", "年代"]},
            {"type_id": "original", "type_name": "原创", "theme_name": "51原创",
             "settings": [],
             "backgrounds": ["校园", "架空", "民国", "职场", "年代", "现代", "都市", "古代", "乡村"]},
            {"type_id": "farm", "type_name": "种田", "theme_name": "种田",
             "settings": ["穿越", "重生", "打脸虐渣", "大男主", "大女主", "系统", "小人物", "甜宠"],
             "backgrounds": ["年代", "现代", "都市", "古代", "乡村", "校园", "架空", "民国", "职场"]},
            {"type_id": "ghost", "type_name": "灵异", "theme_name": "灵异",
             "settings": [],
             "backgrounds": ["校园", "架空", "民国", "职场", "年代", "现代", "都市", "古代", "乡村"]},
            {"type_id": "mystic", "type_name": "志怪", "theme_name": "志怪",
             "settings": ["打脸虐渣", "大男主", "大女主", "穿越", "重生", "传承觉醒", "小人物"],
             "backgrounds": ["民国", "现代", "都市", "古代", "乡村", "校园", "架空", "职场", "年代"]},
            {"type_id": "brains", "type_name": "脑洞", "theme_name": "脑洞",
             "settings": ["打脸虐渣", "穿越", "重生", "大男主", "系统", "小人物", "传承觉醒", "家长里短", "大女主", "马甲", "强者回归", "神豪", "甜宠", "先婚后爱", "虐恋", "双向奔赴", "互相救赎"],
             "backgrounds": ["校园", "架空", "民国", "职场", "年代", "现代", "都市", "古代", "乡村"]},
        ]
        self._opt_theme = {}
        self._opt_setting = {}
        self._opt_background = {}
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
            "Referer": self.host + "/",
        }
        self.session = self._create_session()
        self._sync_options()
        self._ensure_oauth()
        # DNS 污染防护：钉扎站点与媒体域名到真实 IP
        _doh_pin_domain(self.host.split("//")[-1].split("/")[0],
                        fallback=["43.230.113.205", "43.230.114.206", "43.230.112.204", "43.228.232.202", "43.228.233.203"])
        _doh_pin_domain("hls.dscxru.cn",
                        fallback=["144.7.103.53", "220.181.181.205", "43.169.25.54"])
        _doh_pin_domain("dx.cqjuyl.cn",
                        fallback=["123.125.246.130", "113.200.43.43"])
        _doh_pin_domain("pic.xustgq.cn")

    def _create_session(self):
        s = requests.Session()
        s.headers.update(self.headers)
        s.verify = False
        return s

    def _ensure_oauth(self):
        try:
            _pin_url_host(self.host + "/")
            r = self.session.get(self.host + "/", timeout=15)
            self.oauth_id = r.cookies.get("OAUTH_ID", "")
        except Exception:
            self.oauth_id = ""

    def _sync_options(self):
        """拉取站点分类体系(主题/设定/背景 value)。站点会不定期重编分类 value,
        故每次初始化尽量同步一次;失败时保留内置默认值兜底。"""
        try:
            r = self.session.post(self.api_host + "/api/home/contentOptions",
                                  data={}, headers=self.headers, timeout=15)
            j = r.json()
            if j.get("errcode") != 0 or not j.get("data"):
                return
            vf = (self._decrypt_api(j["data"]).get("data") or {}).get("video_filter") or {}
            self._opt_theme = {it["name"]: it["value"] for it in vf.get("theme", {}).get("list", [])}
            self._opt_setting = {it["name"]: it["value"] for it in vf.get("setting", {}).get("list", [])}
            self._opt_background = {it["name"]: it["value"] for it in vf.get("background", {}).get("list", [])}
        except Exception:
            pass

    def _theme_val(self, name):
        if name in self._opt_theme:
            return self._opt_theme[name]
        return _DEFAULT_THEME_VAL.get(name)

    def _setting_val(self, name):
        if name in self._opt_setting:
            return self._opt_setting[name]
        return _DEFAULT_SETTING_VAL.get(name)

    def _bg_val(self, name):
        if name in self._opt_background:
            return self._opt_background[name]
        return _DEFAULT_BG_VAL.get(name)

    def getName(self):
        return "51短剧"

    def isVideoFormat(self, url):
        return url.endswith(".m3u8") or url.endswith(".mp4") or url.endswith(".ts")

    def manualVideoCheck(self):
        return False

    def _decode_img(self, data):
        cipher = AES.new(self.img_aes_key.encode(), AES.MODE_CBC, self.img_aes_iv.encode())
        dec = cipher.decrypt(data)
        pad = dec[-1]
        if 1 <= pad <= 16:
            dec = dec[:-pad]
        return dec

    @staticmethod
    def _nuxt_payload(html):
        m = re.search(r'<script type="application/json"[^>]*id="__NUXT_DATA__"[^>]*>(.*?)</script>', html or "", re.S)
        if not m:
            return None
        try:
            return json.loads(m.group(1))
        except Exception:
            return None

    @staticmethod
    def _make_deref(arr):
        cache = {}

        def r(x, path=()):
            if isinstance(x, int) and 0 <= x < len(arr):
                if x in path:
                    return None
                if x in cache:
                    return cache[x]
                v = r(arr[x], path + (x,))
                cache[x] = v
                return v
            if isinstance(x, list):
                return [r(i, path) for i in x]
            if isinstance(x, dict):
                return {k: r(v, path) for k, v in x.items()}
            return x

        return r

    @staticmethod
    def _decode_cover(src):
        if not src.startswith("/_img/"):
            return ""
        b64 = src[len("/_img/"):].split(".")[0]
        pad = 4 - len(b64) % 4
        if pad != 4:
            b64 += "=" * pad
        try:
            return base64.b64decode(b64).decode("utf-8")
        except Exception:
            return ""

    def _img_proxy_url(self, url):
        if not url:
            return ""
        pic_b64 = base64.b64encode(url.encode("utf-8")).decode("utf-8")
        b = self._proxy_base()
        return b + "type=tbr_img&url=" + quote(pic_b64, safe="")

    def _parse_list_cards(self, html):
        videos = []
        seen = set()
        arr = self._nuxt_payload(html)
        if arr:
            deref = self._make_deref(arr)
            root = deref(arr)

            def collect(o):
                if isinstance(o, dict):
                    vid = o.get("video_id")
                    if isinstance(vid, (str, int)) and o.get("title") and o.get("cover"):
                        vid = str(vid)
                        if vid not in seen:
                            seen.add(vid)
                            videos.append({
                                "vod_id": vid,
                                "vod_name": o["title"],
                                "vod_pic": self._img_proxy_url(o["cover"]),
                                "vod_remarks": "",
                            })
                    for v in o.values():
                        collect(v)
                elif isinstance(o, list):
                    for v in o:
                        collect(v)

            collect(root)
        if videos:
            return videos
        pat = re.compile(r'<a href="/drama-play\?id=(\d+)[^"]*"')
        for m in pat.finditer(html or ""):
            pid = m.group(1)
            if pid in seen:
                continue
            seen.add(pid)
            title = ""
            cover = ""
            a_end = html.find(">", m.end())
            if a_end == -1:
                continue
            end = html.find("</a>", a_end)
            if end == -1 or end - a_end > 2000:
                end = a_end + 1500
            body = html[a_end + 1:end]
            im = re.search(r'<img[^>]*src="([^"]*)"[^>]*alt="([^"]*)"', body)
            src = alt = ""
            if im:
                src, alt = im.group(1), im.group(2)
            else:
                im2 = re.search(r'<img[^>]*alt="([^"]*)"[^>]*src="([^"]*)"', body)
                if im2:
                    alt, src = im2.group(1), im2.group(2)
            title = alt.strip()
            if not title:
                pm = re.search(r'<p[^>]*>([^<]{2,40})</p>', body)
                if pm:
                    title = pm.group(1).strip()
            if src.startswith("/_img/"):
                cover = self._decode_cover(src)
            if not title:
                win = html[max(0, m.start() - 1000):m.start()]
                im3 = re.search(r'<img[^>]*src="([^"]*)"[^>]*alt="([^"]*)"', win)
                if im3:
                    src, alt = im3.group(1), im3.group(2)
                    title = alt.strip()
                    if src.startswith("/_img/"):
                        cover = self._decode_cover(src)
            if not title:
                continue
            videos.append({
                "vod_id": pid,
                "vod_name": title,
                "vod_pic": self._img_proxy_url(cover),
                "vod_remarks": "",
            })
        return videos

    def _decrypt_api(self, data):
        raw = base64.b64decode(data.replace(" ", "+"))
        dec = AES.new(self.play_aes_key.encode(), AES.MODE_CBC, self.play_aes_iv.encode()).decrypt(raw)
        pad = dec[-1]
        if 1 <= pad <= 16:
            dec = dec[:-pad]
        return json.loads(dec.decode("utf-8"))

    def _explore(self, params):
        try:
            r = self.session.post(self.api_host + "/api/theater/exploreList", data=params, headers=self.headers, timeout=20)
            j = r.json()
            if j.get("errcode") != 0 or not j.get("data"):
                return {}
            return self._decrypt_api(j["data"]).get("data") or {}
        except Exception:
            return {}

    def _parse_api_videos(self, items):
        videos = []
        seen = set()
        for it in items or []:
            try:
                vid = str(it.get("video_id") or "")
                title = (it.get("title") or "").strip()
                if not vid or not title or vid in seen:
                    continue
                seen.add(vid)
                remark = it.get("play_count_text") or it.get("serialize_status_text") or ""
                videos.append({"vod_id": vid, "vod_name": title, "vod_pic": self._img_proxy_url(it.get("cover") or ""), "vod_remarks": remark})
            except Exception:
                continue
        return videos

    def _build_filters(self):
        filters = {}
        for cat in self.cat_map:
            if self._theme_val(cat["theme_name"]) is None:
                continue
            settings = [{"n": n, "v": self._setting_val(n)} for n in cat["settings"]]
            settings = [s for s in settings if s["v"] is not None]
            bgs = [{"n": n, "v": self._bg_val(n)} for n in cat["backgrounds"]]
            bgs = [b for b in bgs if b["v"] is not None]
            filters[cat["type_id"]] = []
            if settings:
                filters[cat["type_id"]].append({"key": "setting", "name": "题材",
                                                "value": settings})
            if bgs:
                filters[cat["type_id"]].append({"key": "background", "name": "背景",
                                                "value": bgs})
        return filters

    def homeContent(self, filter):
        classes = [{"type_id": c["type_id"], "type_name": c["type_name"]}
                   for c in self.cat_map if self._theme_val(c["theme_name"]) is not None]
        filters = self._build_filters()
        try:
            html = self._html(self.host + "/")
            videos = self._parse_list_cards(html)
        except Exception:
            videos = []
        return {"class": classes, "filters": filters, "list": videos}

    def homeVideoContent(self):
        html = self._html(self.host + "/")
        return {"list": self._parse_list_cards(html)}

    def categoryContent(self, tid, pg, filter, extend):
        result = {"list": [], "page": int(pg) if pg else 1, "pagecount": 1, "limit": 24, "total": 0}
        page = int(pg) if pg else 1
        cat = next((c for c in self.cat_map if str(tid) == c["type_id"]), None)
        if not cat:
            cat = next((c for c in self.cat_map if str(tid) == c["type_name"]), None)
        if cat:
            theme_val = self._theme_val(cat["theme_name"])
            if theme_val is not None:
                ex = extend or {}
                params = {"theme": theme_val, "page": page}
                if ex.get("setting"):
                    params["setting"] = ex["setting"]
                if ex.get("background"):
                    params["background"] = ex["background"]
                d = self._explore(params)
                if d and d.get("list"):
                    items = d["list"]
                    result["list"] = self._parse_api_videos(items)
                    result["total"] = d.get("total") or 0
                    limit = d.get("limit") or 24
                    result["limit"] = limit
                    result["page"] = d.get("page") or page
                    result["pagecount"] = max(1, -(-result["total"] // limit)) if result["total"] else 1
                    return result
                if params.get("background"):
                    d = self._explore({"theme": theme_val, "page": page})
                if d and d.get("list"):
                    result["list"] = self._parse_api_videos(d["list"])
                    result["total"] = d.get("total") or 0
                    result["page"] = d.get("page") or page
                    result["pagecount"] = 1
                    return result
        try:
            html = self._html(self.host + "/explore-drama")
        except Exception:
            html = ""
        result["list"] = self._parse_list_cards(html)
        return result

    def searchContent(self, key, quick=False, pg=1):
        try:
            html = self._html(self.host + "/search?wd=" + quote(key, safe=""))
        except Exception:
            return {"list": []}
        videos = self._parse_list_cards(html)
        return {"list": videos}

    def _fetch_detail(self, playlet_id):
        try:
            html = self._html(self.host + "/drama-play?id=" + str(playlet_id))
        except Exception:
            return {}
        arr = self._nuxt_payload(html)
        if not arr:
            return {}
        deref = self._make_deref(arr)
        for e in arr:
            if isinstance(e, dict) and "episodeAll" in e:
                dr = deref(e)
                if isinstance(dr, dict):
                    return dr
        return {}

    def detailContent(self, ids):
        pid = str(ids[0])
        d = self._fetch_detail(pid)
        if not d or not isinstance(d, dict):
            return {}
        episodes = []
        eps = d.get("episodeAll") or []
        for i, item in enumerate(eps):
            if not isinstance(item, dict):
                continue
            url = item.get("video_url") or item.get("video_url_h265") or ""
            if not url:
                continue
            title = item.get("episode_title") or ("第%d集" % (i + 1))
            episodes.append("%s$%s@%d" % (title, pid, i))
        vod_play_url = "#".join(episodes)
        remarks = ""
        if episodes:
            remarks = "共%d集" % len(episodes)
        elif d.get("serialize_status_text"):
            remarks = d.get("serialize_status_text")
        vod = {
            "vod_id": pid,
            "vod_name": d.get("video_title") or "",
            "vod_pic": self._img_proxy_url(d.get("cover_img") or ""),
            "vod_play_from": "51短剧",
            "vod_play_url": vod_play_url,
            "vod_content": d.get("description") or "",
            "vod_remarks": remarks,
        }
        return {"list": [vod]}

    def _proxy_base(self):
        b = self.getProxyUrl()
        if not b:
            b = "http://127.0.0.1:9978/proxy?do=py"
        return b + ("&" if "?" in b else "?")

    def playerContent(self, flag, id, vipFlags):
        val = str(id).split("$")[-1]
        if val.startswith("http"):
            return {"playUrl": "", "url": val, "parse": 0, "header": self.headers, "position": "0"}
        if "@" in val:
            try:
                pid, idx = val.rsplit("@", 1)
                idx = int(idx)
                d = self._fetch_detail(pid)
                eps = d.get("episodeAll") or []
                if 0 <= idx < len(eps) and isinstance(eps[idx], dict):
                    url = eps[idx].get("video_url") or eps[idx].get("video_url_h265") or ""
                    if url:
                        _pin_url_host(url)
                        b = self._proxy_base()
                        return {"playUrl": "", "url": b + "type=m3u8&url=" + quote(url, safe=""),
                                "parse": 0, "header": self.headers, "position": "0"}
            except Exception as e:
                print("[51duanju] player err:", e)
        return {"playUrl": "", "msg": "无效的播放地址: %s" % val}

    def localProxy(self, params):
        try:
            pt = params.get("type") or ""
            if pt in ("m3u8", "key", "ts"):
                u = unquote(params.get("url", ""))
                if not u:
                    return [404, "text/plain", "not found"]
                _pin_url_host(u)
                r = self.session.get(u, headers=self.headers, timeout=20)
                if r.status_code != 200:
                    return [404, "text/plain", "not found"]
                if pt == "m3u8":
                    body = r.text
                    b = self._proxy_base()
                    body = re.sub(r'(URI=")([^"]+)(")',
                                  lambda mm: mm.group(1) + b + "type=key&url=" + quote(mm.group(2), safe="") + mm.group(3),
                                  body)
                    lines = []
                    for line in body.splitlines():
                        s = line.strip()
                        if s.startswith("http://") or s.startswith("https://"):
                            line = b + "type=ts&url=" + quote(s, safe="")
                        lines.append(line)
                    return [200, "application/vnd.apple.mpegurl;charset=UTF-8", ("\n".join(lines)).encode("utf-8")]
                if pt == "key":
                    return [200, "application/octet-stream", r.content]
                return [200, "video/mp2t", r.content]
            if pt != "tbr_img":
                return [404, "text/plain", "not found"]
            img_b64 = unquote(params.get("url", ""))
            pad = 4 - len(img_b64) % 4
            if pad != 4:
                img_b64 += "=" * pad
            img_url = base64.b64decode(img_b64).decode("utf-8")
            _pin_url_host(img_url)
            img_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
                "Referer": self.host + "/",
            }
            r = self.session.get(img_url, headers=img_headers, timeout=20)
            if r.status_code != 200:
                return [404, "text/plain", "image not found"]
            data = r.content
            if data[:3] == b"\xff\xd8\xff":
                return [200, "image/jpeg", data, {"Content-Length": str(len(data))}]
            if data[:4] == b"\x89PNG":
                return [200, "image/png", data, {"Content-Length": str(len(data))}]
            if data[:4] == b"GIF8":
                return [200, "image/gif", data, {"Content-Length": str(len(data))}]
            dec = self._decode_img(data)
            if dec[:3] == b"\xff\xd8\xff":
                return [200, "image/jpeg", dec, {"Content-Length": str(len(dec))}]
            if dec[:4] == b"\x89PNG":
                return [200, "image/png", dec, {"Content-Length": str(len(dec))}]
            if dec[:4] == b"GIF8":
                return [200, "image/gif", dec, {"Content-Length": str(len(dec))}]
            if len(dec) > 12 and dec[:4] == b"RIFF" and dec[8:12] == b"WEBP":
                return [200, "image/webp", dec, {"Content-Length": str(len(dec))}]
            return [200, "image/jpeg", dec, {"Content-Length": str(len(dec))}]
        except Exception:
            return [500, "text/plain", "decryption failed"]

    def _html(self, url):
        _pin_url_host(url)
        r = self.session.get(url, timeout=15)
        return r.text