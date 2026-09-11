import base64
import hashlib
import json
import re
import time
import urllib.parse
import zlib

import requests

from base.spider import Spider as BaseSpider


FILM_FILTERS = {"6_1": "欧美", "6_2": "日本", "6_3": "国产", "6_4": "直播", "6_5": "新作", "3_3": "4K独播", "manga": "漫画", "album": "写真"}
FILM_ORDER = ("6_3", "6_2", "6_1", "6_5", "3_3", "6_4", "manga", "album")
ONE_API = "https://api.em1oifd0.com/"
ONE_MIRRORS = ("https://api.3459381.com/", "https://api.61c76a0.com/", "https://api.87735d5.com/", "https://api.c6dd5cc.com/", "https://api.j7y675.com/", "https://api.em1oifd0.com/")
BOOTSTRAP_LINES = ("http://198.44.248.101:9672/", "http://198.44.248.102:9672/", "http://122.10.20.249:9672/")
BOX_KEY = b"dnf45as45fs1ace1"
BOX_IV = b"dn5as4fs1ac5f4e1"
ONE_KEY = b"l*bv%Ziq000Biaog"
ONE_IV = b"8597506002939249"
ONE_SIGN_SUFFIX = "m4n2hjPeYWkD6tFpqKF^3HO^h24P@idT"
ONE_IMAGE_KEY = b"saIZXc4yMvq0Iz56"
ONE_IMAGE_IV = b"kbJYtBJUECT0oyjo"
REQUEST_TIMEOUT = 15


def _pad(data):
    length = 16 - (len(data) % 16)
    return data + bytes([length]) * length


def _unpad(data):
    if not data:
        return data
    length = data[-1]
    if length < 1 or length > 16 or data[-length:] != bytes([length]) * length:
        raise ValueError("invalid cipher padding")
    return data[:-length]


def _aes(data, key, iv, decrypt=False):
    try:
        from Crypto.Cipher import AES
        cipher = AES.new(key, AES.MODE_CBC, iv)
        return cipher.decrypt(data) if decrypt else cipher.encrypt(_pad(data))
    except ImportError:
        import subprocess
        command = ["openssl", "enc", "-aes-128-cbc"]
        if decrypt:
            command.append("-d")
        command.extend(["-nopad", "-K", key.hex(), "-iv", iv.hex()])
        source = data if decrypt else _pad(data)
        process = subprocess.run(command, input=source, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return process.stdout


def _decrypt_one_image(data):
    return _unpad(_aes(data, ONE_IMAGE_KEY, ONE_IMAGE_IV, decrypt=True))


def _image_kind(data):
    if data.startswith(b"\xff\xd8\xff") and data.endswith(b"\xff\xd9"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n") and data.endswith(b"IEND\xaeB`\x82"):
        return "image/png"
    if data.startswith((b"GIF87a", b"GIF89a")) and data.endswith(b";"):
        return "image/gif"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP" and len(data) >= 12 and int.from_bytes(data[4:8], "little") == len(data) - 8:
        return "image/webp"
    return None


def _choose_media(item):
    if not isinstance(item, dict):
        return None
    for field in ("video_hls", "video_hls_h265", "video_file", "video"):
        value = item.get(field)
        if isinstance(value, str) and value and not Spider._is_audio_path(value) and not any(word in field.lower() for word in ("preview", "trailer", "sample")):
            return field, value
    return None


def _diagnostic(message, detail=None):
    safe = str(message).replace("\n", " ")[:180]
    if detail:
        safe += ": " + str(detail).replace("\n", " ")[:180]
    return {"error": safe}


class Spider(BaseSpider):
    def __init__(self):
        super().__init__()
        self._ready = False
        self._config = None
        self._token = None
        self._hosts = {}
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "Dart/3.4 (dart:io)"})

    def init(self, extend=""):
        self.extend = extend or ""
        self._ready = False

    def _ensure_ready(self):
        if self._ready:
            return None
        try:
            self._bootstrap()
            self._ready = True
            return None
        except Exception as error:
            return _diagnostic("初始化失败", type(error).__name__)

    def _bootstrap(self):
        last = None
        for line in BOOTSTRAP_LINES:
            try:
                response = self._session.post(line + "box/api/config", params={"channel": "Channel"}, timeout=REQUEST_TIMEOUT)
                response.raise_for_status()
                config = self._decode_box(response.content)
                if not isinstance(config.get("data"), dict):
                    raise ValueError("invalid config shape")
                self._config = config
                self._token = next(item["token"] for item in config["data"].get("token", []) if item.get("name") == "token_one")
                self._hosts = {item.get("name"): item.get("host", "") for item in config["data"].get("api", [])}
                return
            except Exception as error:
                last = error
        raise RuntimeError(type(last).__name__ if last else "bootstrap unavailable")

    @staticmethod
    def _decode_box(body):
        raw = _unpad(_aes(body, BOX_KEY, BOX_IV, decrypt=True))
        return json.loads(zlib.decompress(raw).decode("utf-8"))

    def _one_headers(self):
        timestamp = str(int(time.time()))
        uuid = getattr(self, "_uuid", None) or "48b067ec-6cfd-3491-84f5-023eb1e7d562"
        user_key = getattr(self, "_user_key", None) or "563e8eeef42931cc858dc0d1080f4f6f"
        platform = "3"
        ip = "0.0.0.0"
        first = hashlib.md5(".".join((ip, platform, timestamp, user_key, uuid)).encode()).hexdigest()
        sign = hashlib.md5((first + ONE_SIGN_SUFFIX).encode()).hexdigest()
        return {"ip": ip, "uuid": uuid, "timestamp": timestamp, "platform": platform, "token": self._token, "sign": sign, "user-key": user_key, "app-version": "2.6.3.1", "Content-Type": "application/x-www-form-urlencoded"}

    def _request(self, endpoint, params, retries=1):
        query = "&".join("{}={}".format(key, params[key]) for key in sorted(params))
        encoded = base64.b64encode(_aes(query.encode(), ONE_KEY, ONE_IV)).decode()
        primary = self._hosts.get("one", ONE_API)
        bases = [primary] + [m for m in ONE_MIRRORS if m != primary][:1]
        last = None
        for attempt in range(retries + 1):
            for base in bases:
                try:
                    response = self._session.post(base.rstrip("/") + "/" + endpoint.lstrip("/"), data=encoded, headers=self._one_headers(), timeout=8)
                    response.raise_for_status()
                    decoded = _aes(base64.b64decode(response.text.strip()), ONE_KEY, ONE_IV, decrypt=True)
                    return json.loads(_unpad(decoded).decode("utf-8"))
                except Exception as error:
                    last = error
            if attempt < retries:
                time.sleep(0.4 * (attempt + 1))
        raise last

    def _one_url(self, name, path):
        prefix = self._hosts.get(name, "")
        if not prefix:
            return ""
        return urllib.parse.urljoin(prefix, path.lstrip("/"))

    def _proxy_url(self, url):
        return self.getProxyUrl() + "&url=" + urllib.parse.quote(url, safe="")

    @staticmethod
    def _is_audio_path(path):
        return isinstance(path, str) and path.lower().split("?", 1)[0].endswith((".mp3", ".m4a", ".aac", ".wav", ".flac"))

    def _item(self, item):
        media = _choose_media(item)
        cover = item.get("thumb") or item.get("thumbnail") or ""
        if cover and not cover.startswith(("http://", "https://")):
            cover = self._one_url("one_img", cover)
        if cover:
            cover = self._proxy_url(cover)
        playable = media and not self._is_audio_path(media[1])
        return {"vod_id": str(item.get("id", "")), "vod_name": item.get("title", ""), "vod_pic": cover, "vod_remarks": item.get("video_length", ""), "vod_year": str(item.get("published_at", ""))[:4], "vod_content": item.get("description", ""), "vod_play_from": "One" if playable else "", "vod_play_url": "正片$" + str(item.get("id")) if playable else ""}

    def homeContent(self, filter):
        error = self._ensure_ready()
        if error:
            return error
        classes = [{"type_id": key, "type_name": FILM_FILTERS[key]} for key in FILM_ORDER]
        return {"class": classes, "filters": {}, "list": []}

    def homeVideoContent(self):
        return {"list": []}

    def _series_item(self, item, kind):
        cover = item.get("thumb") or item.get("thumbnail") or ""
        if cover and not cover.startswith(("http://", "https://")):
            cover = self._one_url("one_img", cover)
        if cover:
            cover = self._proxy_url(cover)
        vid = ("m:" if kind == "manga" else "a:") + str(item.get("id", ""))
        return {"vod_id": vid, "vod_name": item.get("title", ""), "vod_pic": cover, "vod_remarks": (item.get("latest_at") or "")[:10], "vod_year": (item.get("first_at") or "")[:4], "vod_content": "作者: {}".format(item.get("author", "")), "vod_play_from": "漫画" if kind == "manga" else "写真", "vod_play_url": "全篇${}".format(vid)}

    def categoryContent(self, tid, pg, filter, extend):
        error = self._ensure_ready()
        if error:
            return error
        demand_tag_id = str(tid)
        if demand_tag_id not in FILM_FILTERS:
            demand_tag_id = FILM_ORDER[0]
        page = max(1, int(pg))
        try:
            if demand_tag_id in ("manga", "album"):
                ep = "v2.5/series/manga/list" if demand_tag_id == "manga" else "v2.5/series/album/list"
                result = self._request(ep, {"page": page, "size": 20})
                items = result.get("data", []) if isinstance(result, dict) else []
                rows = [self._series_item(item, demand_tag_id) for item in items if item.get("id")]
                return {"page": page, "pagecount": page + 1 if len(rows) >= 20 else page, "limit": 20, "total": len(rows), "list": rows}
            model, tag = (int(x) for x in demand_tag_id.split("_"))
            items, month_back, inner_page = self._monthly_discovery(model, tag, page)
        except Exception:
            return {"page": page, "pagecount": page, "limit": 20, "total": 0, "list": []}
        seen = set()
        rows = []
        for item in items:
            identity = item.get("id")
            if identity in seen:
                continue
            seen.add(identity)
            rows.append(self._item(item))
        page_count = page
        if month_back >= 0:
            page_count = page + 1 if self._has_next(model, tag, month_back, inner_page) else page
        return {"page": page, "pagecount": page_count, "limit": 20, "total": len(rows), "list": rows}

    @staticmethod
    def _month_str(back):
        import datetime
        now = datetime.datetime.now()
        year, month = now.year, now.month - back
        while month <= 0:
            month += 12
            year -= 1
        return "%04d-%02d" % (year, month)

    def _monthly_discovery(self, model, tag, page, months=12):
        acc = 0
        for back in range(months):
            month = self._month_str(back)
            result = self._request("v2.5/article/discovery", {"demand_tag_id": tag, "model_id": model, "page": 1, "published_at": month, "size": 20, "sort": "published_at"})
            first = result.get("data", []) if isinstance(result, dict) else []
            pages = (len(first) + 19) // 20
            if not pages:
                continue
            if page <= acc + pages:
                inner = page - acc
                if inner > 1:
                    again = self._request("v2.5/article/discovery", {"demand_tag_id": tag, "model_id": model, "page": inner, "published_at": month, "size": 20, "sort": "published_at"})
                    first = again.get("data", []) if isinstance(again, dict) else []
                return first, back, inner
            acc += pages
        return [], -1, 1

    def _has_next(self, model, tag, month_back, inner_page):
        try:
            if inner_page > 1:
                month = self._month_str(month_back)
                result = self._request("v2.5/article/discovery", {"demand_tag_id": tag, "model_id": model, "page": inner_page + 1, "published_at": month, "size": 20, "sort": "published_at"})
                if result.get("data"):
                    return True
            for nb in (month_back + 1, month_back + 2):
                result = self._request("v2.5/article/discovery", {"demand_tag_id": tag, "model_id": model, "page": 1, "published_at": self._month_str(nb), "size": 20, "sort": "published_at"})
                if result.get("data"):
                    return True
            return False
        except Exception:
            return True

    def detailContent(self, ids):
        error = self._ensure_ready()
        if error:
            return error
        try:
            raw = str(ids[0] if isinstance(ids, (list, tuple)) else ids)
            kind = ""
            if raw.startswith(("m:", "a:")):
                kind = raw[:1]
                raw = raw[2:]
            item_id = int(raw)
            if kind:
                result = self._request("v2.5/series/chapters", {"series_id": item_id})
                d = result.get("data") or {}
                chapters = d.get("chapters") or [] if isinstance(d, dict) else []
                cover = d.get("thumb") or ""
                if cover and not cover.startswith(("http://", "https://")):
                    cover = self._one_url("one_img", cover)
                if cover:
                    cover = self._proxy_url(cover)
                play_url = "#".join("{}${}".format((c.get("title") or "第{}话".format(c.get("chapter", ""))).replace("#", " ").replace("$", " "), c.get("id")) for c in chapters if c.get("id"))
                detail = {"vod_id": raw, "vod_name": d.get("title", ""), "vod_pic": cover, "vod_year": (d.get("first_at") or "")[:4], "vod_area": "", "vod_class": "", "vod_director": "", "vod_actor": d.get("author", ""), "vod_content": d.get("description", ""), "vod_remarks": "共{}话".format(len(chapters)), "vod_play_from": "漫画" if kind == "m" else "写真", "vod_play_url": play_url}
                return {"list": [detail]}
            result = self._request("v2.5/article/detail", {"id": item_id})
            item = result.get("data", {})
            media = _choose_media(item)
            play_entries = [("正片", item_id)] if media else []
            series_id = item.get("series_id")
            if series_id and media:
                try:
                    chapters = self._request("v2.5/series/chapters", {"series_id": int(series_id)}).get("data", {}).get("chapters", [])
                    if chapters:
                        play_entries = [(chapter.get("title") or "第{}集".format(chapter.get("chapter", "")), chapter.get("id")) for chapter in chapters if chapter.get("id")]
                except Exception:
                    pass
            play_url = "#".join("{}${}".format(title.replace("#", " ").replace("$", " "), chapter_id) for title, chapter_id in play_entries)
            detail = self._item(item)
            detail.update({"vod_id": str(item_id), "vod_play_from": "One" if play_entries else "", "vod_play_url": play_url})
            return {"list": [detail]}
        except Exception as error:
            return _diagnostic("详情请求失败", type(error).__name__)

    def searchContent(self, key, quick, pg="1"):
        error = self._ensure_ready()
        if error:
            return error
        try:
            page = max(1, int(pg))
            result = self._request("v2.5/article/search", {"keyword": str(key), "page": page, "size": 20})
            items = result.get("data", []) if isinstance(result, dict) else []
            seen = set()
            rows = []
            for item in items:
                identity = item.get("id")
                if identity in seen:
                    continue
                seen.add(identity)
                rows.append(self._item(item))
            return {"list": rows, "page": page, "pagecount": page if len(rows) < 20 else page + 1, "limit": 20, "total": len(rows)}
        except Exception:
            return {"list": [], "page": 1, "pagecount": 1, "limit": 0, "total": 0}

    def playerContent(self, flag, id, vipFlags):
        error = self._ensure_ready()
        if error:
            return error
        try:
            item_id = int(str(id).split("$")[-1])
            result = self._request("v2.5/article/detail", {"id": item_id})
            item = result.get("data", {})
            content = item.get("content") or item.get("description") or ""
            images = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', content)
            if images:
                urls = []
                for src in images:
                    if src.startswith("http"):
                        urls.append(src)
                    else:
                        urls.append(self._one_url("one_img", src))
                pics = "&&".join(self._proxy_url(u) for u in urls)
                return {"parse": 0, "playUrl": "", "url": "pics://" + pics, "header": {"User-Agent": "Dart/3.4 (dart:io)"}}
            media = _choose_media(item)
            if not media:
                return {"parse": 0, "playUrl": "", "url": "", "header": {}, "error": "无已证实正片源，未将试看或预览标为正片"}
            field, path = media
            if field.startswith("video_hls"):
                url = self._one_url("one_video", path)
                return {"parse": 0, "playUrl": "", "url": url, "header": {"User-Agent": "Dart/3.4 (dart:io)"}, "media_field": field}
            return {"parse": 0, "playUrl": "", "url": self._one_url("one_video", path), "header": {"User-Agent": "Dart/3.4 (dart:io)"}, "media_field": field}
        except Exception as error:
            return _diagnostic("播放请求失败", type(error).__name__)

    def localProxy(self, param):
        if not isinstance(param, dict):
            return [400, "text/plain", b"invalid proxy parameters"]
        url = param.get("url", "")
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            return [400, "text/plain", b"invalid proxy URL"]
        try:
            parsed = urllib.parse.urlparse(url)
            configured = urllib.parse.urlparse(self._hosts.get("one_img", ""))
            if not configured.hostname or parsed.hostname != configured.hostname or parsed.netloc.lower() != configured.netloc.lower():
                return [403, "text/plain", b"proxy host is not allowed"]
            if parsed.query or parsed.fragment or parsed.username or parsed.password:
                return [400, "text/plain", b"proxy query is not allowed"]
            response = self._session.get(url, headers={"User-Agent": "Dart/3.4 (dart:io)"}, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            content = _decrypt_one_image(response.content)
            content_type = _image_kind(content)
            if not content_type:
                return [502, "text/plain", b"proxy image integrity check failed"]
            return [200, content_type, content]
        except Exception as error:
            return [502, "text/plain", ("proxy error: " + type(error).__name__).encode()]

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
