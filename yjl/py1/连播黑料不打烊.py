# -*- coding: utf-8 -*-
#🔗 黑料不打烊最新地址
#👉 国内：https://cbdy4.com
#🌐 海外：https://hl365.com
#🔒 永久：https://hlbdy1.com
#📧 邮箱：heiliaobdy@gmail.com
import base64, html, json, re
from urllib.parse import quote, unquote
import requests
from lxml import etree
try:
    from Crypto.Cipher import AES
except Exception:
    AES = None
try:
    from base.spider import Spider as BaseSpider
except Exception:
    BaseSpider = object

class Spider(BaseSpider):
    def getName(self): return "黑料不打烊"
    def init(self, extend=""):
        self.host = "https://badly.okttbipbu.cc"
        self.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36", "Referer": self.host + "/", "Accept": "*/*", "Accept-Language": "zh-CN,zh;q=0.9"}
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.last_error = ""
        self.categories = [{"type_id": "/", "type_name": "首页"}, {"type_id": "/category/24hcg/", "type_name": "今日看料"}, {"type_id": "/category/rgtj/", "type_name": "热门吃瓜"}, {"type_id": "/category/mrrg/", "type_name": "每日热瓜"}, {"type_id": "/category/hlda/", "type_name": "黑料大事"}, {"type_id": "/category/whhl/", "type_name": "网红吃瓜"}, {"type_id": "/category/mxbg/", "type_name": "明星吃瓜"}, {"type_id": "/category/fcns/", "type_name": "反差女神"}, {"type_id": "/category/xyrg/", "type_name": "学院热瓜"}, {"type_id": "/category/mrds/", "type_name": "每日大赛"}, {"type_id": "/category/swdj/", "type_name": "AI短剧"}, {"type_id": "/category/lydt/", "type_name": "撸友看片"}, {"type_id": "/category/avjs/", "type_name": "AV解说"}, {"type_id": "/category/mrst/", "type_name": "禁播动漫"}, {"type_id": "/category/pmv/", "type_name": "PMV混剪"}]
    def _client(self): return getattr(self, "session", requests)
    def _error(self, msg):
        self.last_error = msg
        try: self.log(msg)
        except Exception: pass
    def _get(self, url):
        try:
            client = self._client()
            r = client.get(url, headers=self.headers, timeout=25, verify=False, allow_redirects=True)
            if (r.status_code != 200 or not (r.text or "").strip()) and url.rstrip("/") != self.host:
                client.get(self.host + "/", headers=self.headers, timeout=25, verify=False, allow_redirects=True)
                r = client.get(url, headers=self.headers, timeout=25, verify=False, allow_redirects=True)
            if r.status_code != 200:
                self._error(f"GET {url} status={r.status_code} body={(r.text or '')[:120]}")
                return ""
            text = r.content.decode("utf-8", errors="ignore")
            if not (text or "").strip(): self._error(f"GET {url} empty body")
            return text
        except Exception as e:
            self._error(f"GET {url} error={type(e).__name__}: {e}")
            return ""
    def _fix(self, u):
        if not u: return ""
        u = html.unescape(u.strip())
        return "https:" + u if u.startswith("//") else self.host + u if u.startswith("/") else u
    def _clean(self, s): return re.sub(r"\s+", " ", html.unescape(s or "")).strip()
    def _player_header(self): return self.headers
    def _html(self, text):
        if isinstance(text, bytes): text = text.decode("utf-8", errors="ignore")
        return etree.HTML((text or "").replace("\x00", "").encode("utf-8", errors="ignore"))
    def _ids(self, ids): return ids if isinstance(ids, (list, tuple)) else [ids] if ids else []
    def _detail_url(self, sid):
        sid = str(sid or "").strip()
        if sid.startswith("http"): return self._fix(sid)
        m = re.search(r"(?:archives/)?(\d{3,})(?:\.html)?", sid)
        if m: return f"{self.host}/archives/{m.group(1)}.html"
        return self._fix(sid)
    def _is_encrypted_img(self, u): return any(x in (u or "") for x in ["/xiao/", "/upload_01/xiao/", "/upload/upload/xiao/"])
    def _is_cdn_img(self, u): return any(x in (u or "") for x in ["/xiao/", "/usr/", "/upload_01/", "/uploads/", "/upload/upload/"])
    def _proxy_base(self):
        try:
            f = getattr(self, "getProxyUrl", None)
            return f() if callable(f) else ""
        except Exception:
            return ""
    def _proxy_img_url(self, base, url):
        sep = "" if base.endswith(("?", "&")) else "&" if "?" in base else "?"
        return base + sep + "type=img&url=" + quote(url, safe="")
    def _mime_from_bytes(self, data, ext="jpeg"):
        if data.startswith(b"\xff\xd8\xff"): return "jpeg"
        if data.startswith(b"\x89PNG\r\n\x1a\n"): return "png"
        if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"): return "gif"
        if data[:4] == b"RIFF" and data[8:12] == b"WEBP": return "webp"
        return "jpeg" if ext in ["jpg", "jpeg"] else ext if ext in ["png", "gif", "webp"] else "jpeg"
    def _decrypt_image_bytes(self, data):
        if not AES: return ""
        try:
            raw = AES.new(b"f5d965df75336270", AES.MODE_CBC, b"97b60394abc2fbe1").decrypt(base64.b64decode(data))
            pad = raw[-1] if raw else 0
            return raw[:-pad] if 0 < pad <= 16 and raw.endswith(bytes([pad]) * pad) else raw
        except Exception:
            return b""
    def _image_data_url(self, url):
        try:
            data, mime = self._image_bytes(url)
            return f"data:image/{mime};base64,{base64.b64encode(data).decode()}" if data else url
        except Exception:
            return url
    def _image_bytes(self, url):
        url = unquote(url)
        ext = (url.split("?")[0].rsplit(".", 1)[-1] or "jpeg").lower()
        r = self._client().get(url, headers=self.headers, timeout=25, verify=False, allow_redirects=True)
        if self._is_encrypted_img(url):
            raw = self._decrypt_image_bytes(base64.b64encode(r.content).decode())
            if raw: return raw, self._mime_from_bytes(raw, ext)
        ctype = (r.headers.get("Content-Type") or "").split(";")[0].lower()
        mime = ctype.split("/", 1)[1] if ctype.startswith("image/") else self._mime_from_bytes(r.content, ext)
        return r.content, mime
    def _pic_url(self, url):
        base = self._proxy_base()
        if base: return self._proxy_img_url(base, url)
        if url.startswith("data:"): return url
        return self._image_data_url(url) if self._is_encrypted_img(url) else url
    def _cover_url(self, url):
        url = self._fix(url)
        base = self._proxy_base()
        return self._proxy_img_url(base, url) if base and self._is_encrypted_img(url) else url
    def proxy(self, params):
        url = params.get("url") or params.get("img") or ""
        if isinstance(url, list): url = url[0] if url else ""
        try:
            data, mime = self._image_bytes(url)
            return [200, "image/" + mime, data]
        except Exception:
            return [404, "text/plain", ""]
    def localProxy(self, params): return self.proxy(params)
    def _page_url(self, tid, pg):
        pg = int(pg or 1)
        path = tid or "/"
        if path.startswith("http"): base = path.rstrip("/") + "/"
        else: base = self.host + (path if path.startswith("/") else "/" + path)
        base = base.rstrip("/") + "/"
        if pg <= 1: return base
        return base + f"page/{pg}/" if path.strip("/") == "" else base + f"{pg}/"
    def _parse_list(self, html_text):
        if not html_text: return []
        tree = self._html(html_text)
        if tree is None: return []
        result, seen = [], set()
        items = tree.xpath('//div[@id="index" or @id="archive"]//article[.//a[contains(@href,"/archives/")]]') or tree.xpath('//article[.//a[contains(@href,"/archives/")]]')
        for item in items:
            if self._is_ad_item(item): continue
            href = "".join(item.xpath('.//a[contains(@href,"/archives/")]/@href')).strip()
            m = re.search(r"/archives/(\d+)\.html", href)
            if not m or m.group(1) in seen: continue
            seen.add(m.group(1))
            title = self._clean(" ".join(item.xpath('.//*[contains(@class,"post-card-bottom-text")]//text()')) or " ".join(item.xpath('.//h2//text()')) or "".join(item.xpath('.//a[contains(@href,"/archives/")]/@title')))
            pics = item.xpath('.//meta[@itemprop="image" or @itemprop="thumbnailUrl"]/@content') or item.xpath('.//img/@z-image-loader-url') or item.xpath('.//img/@data-xkrkllgl') or item.xpath('.//img/@data-src') or item.xpath('.//img/@src')
            pic = pics[0] if pics else ""
            result.append({"vod_id": self._fix(href), "vod_name": title or m.group(1), "vod_pic": self._cover_url(pic)})
        return result
    def _content_node(self, tree):
        nodes = tree.xpath('//div[contains(concat(" ",normalize-space(@class)," ")," post-content ")]')
        return nodes[0] if nodes else tree
    def _is_ad_item(self, item):
        return bool(item.xpath('.//a[contains(concat(" ",normalize-space(@rel)," ")," sponsored ") or @data-event="ad_click" or @data-ad_slot_key or @data-ad_id]'))
    def _parse_videos(self, node):
        videos, seen = [], set()
        for d in node.xpath('.//div[contains(@class,"dplayer") and @data-config]'):
            title = f"视频{len(videos)+1}"
            conf = html.unescape(d.get("data-config") or "")
            url = ""
            try: url = ((json.loads(conf).get("video") or {}).get("url") or "").replace("\\/", "/")
            except Exception:
                m = re.search(r'"video"\s*:\s*\{.*?"url"\s*:\s*"([^"]+)"', conf)
                url = m.group(1).replace("\\/", "/") if m else ""
            if url and url not in seen:
                seen.add(url)
                videos.append((title, self._fix(url)))
        return videos
    def _parse_images(self, node):
        imgs, seen = [], set()
        for img in node.xpath('.//img'):
            src = img.get("z-image-loader-url") or img.get("data-xkrkllgl") or img.get("data-original") or img.get("data-src") or img.get("data-lazyload") or img.get("data-lazy-src") or img.get("src") or ""
            src = self._fix(src)
            if not src or src in seen or "/usr/themes/" in src or "/usr/plugins/" in src or "/uploads/default/other/" in src: continue
            seen.add(src)
            imgs.append(src)
        return imgs
    def homeContent(self, filter):
        return {"class": self.categories, "list": self._parse_list(self._get(self.host + "/")), "filters": {}}
    def categoryContent(self, tid, pg, filter, extend):
        items = self._parse_list(self._get(self._page_url(tid, pg)))
        total = 9990 if items else 0
        return {"page": int(pg), "pagecount": 999 if items else int(pg), "limit": 10, "total": total, "count": total, "list": items}
    def detailContent(self, ids):
        self.last_error = ""
        result = {"list": []}
        for sid in self._ids(ids):
            try:
                url = self._detail_url(sid)
                html_text = self._get(url)
                if not html_text:
                    if not self.last_error: self._error(f"detail {url} empty html")
                    continue
                tree = self._html(html_text)
                if tree is None:
                    self._error(f"detail {url} etree none body={html_text[:120]}")
                    continue
                node = self._content_node(tree)
                name = self._clean("".join(tree.xpath('//meta[@property="og:title"]/@content')) or "".join(tree.xpath('//h1/text()')) or "".join(tree.xpath('//title/text()')))
                videos, imgs = self._parse_videos(node), self._parse_images(node)
                pic = self._cover_url(imgs[0] if imgs else "".join(tree.xpath('//meta[@property="og:image"]/@content')))
                text = self._clean(" ".join(node.xpath('.//p[not(ancestor::*[contains(@class,"article-ads-btn")])]/text()')))[:800]
                names, plays = [], []
                if videos:
                    names.append("视频")
                    plays.append("#".join(f"{t}${u}" for t, u in videos))
                if imgs:
                    names.append("图集")
                    plays.append("全部$pics://" + "&&".join(imgs))
                if text:
                    names.append("正文")
                    plays.append("正文$text://" + text)
                result["list"].append({"vod_id": url, "vod_name": name, "vod_pic": pic, "vod_content": text, "vod_play_from": "$$$".join(names), "vod_play_url": "$$$".join(plays)})
            except Exception as e:
                self._error(f"detail sid={sid} error={type(e).__name__}: {e}")
                continue
        return result if result["list"] else {"list": [], "msg": self.last_error or "detail empty"}
    def searchContent(self, key, quick, pg="1"):
        url = self.host + "/search/" + quote(key) + "/" + (f"page/{pg}/" if int(pg or 1) > 1 else "")
        return {"list": self._parse_list(self._get(url)), "page": int(pg)}
    def playerContent(self, flag, id, vipFlags):
        if id.startswith("pics://"):
            return {"parse": 0, "url": "pics://" + "&&".join(self._pic_url(u) for u in id[7:].split("&&") if u), "header": self._player_header()}
        if id.startswith("text://"): return {"parse": 0, "url": id, "header": self._player_header()}
        url = self._fix(id)
        lower = url.lower()
        result = {"parse": 0 if any(x in lower for x in [".m3u8", ".mp4", ".flv"]) else 1, "url": url, "header": self._player_header()}
        if ".m3u8" in lower: result["format"] = "application/x-mpegURL"
        return result

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
