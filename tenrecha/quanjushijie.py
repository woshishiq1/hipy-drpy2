# -*- coding: utf-8 -*-
"""
全劇視界 -> TVBox Spider v2.6.0 (外掛版)

- 全部原生 .so 與離線 DB 都放在 .py 同目錄，不再內嵌 base85。
- Android ARM64：載入 APK 抽出的 libduanju_core.so 原生核心。
- 其他平台：使用從 APK 逆向出的紅果 Web 規則（純 Python）。
"""
from __future__ import print_function

import os
import re
import json
import ssl
import base64
import zlib
import ctypes
import threading
import platform
import tempfile
import hashlib
import time
from html import unescape
from html.parser import HTMLParser

try:
    from urllib.request import Request, urlopen
    from urllib.parse import urlencode, quote, urljoin, urlparse, parse_qs
    from urllib.error import HTTPError, URLError
except ImportError:  # pragma: no cover
    from urllib2 import Request, urlopen, HTTPError, URLError
    from urllib import urlencode, quote
    from urlparse import urljoin, urlparse, parse_qs

try:
    from base.spider import Spider as _BaseSpider
except Exception:
    class _BaseSpider(object):
        pass


UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/150.0.0.0 Safari/537.36"
)
BASE = "https://hongguoduanju.com"


# ============================================================================
# 外掛檔案名稱與尋找邏輯
# ============================================================================
_NATIVE_SO_NAME = "libduanju_core.so"
_OFFLINE_DB_NAME = "offline_db.json.zlib"

# FFmpeg 相關 .so：載入順序不能亂，libduanju_core.so 依賴它們
_FFMPEG_SO_NAMES = (
    "libc++_shared.so",
    "libavutil.so",
    "libswresample.so",
    "libavcodec.so",
    "libavformat.so",
    "libswscale.so",
    "libavfilter.so",
    "libavdevice.so",
    "libffmpegkit.so",
)


def _find_sidecar(name):
    """在 .py 同目錄、./so/、上層目錄、cwd、常見 TVBox py 目錄中尋找外掛檔。"""
    candidates = []
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        # .py 同目錄
        candidates.append(os.path.join(here, name))
        # ./so/ 子目錄（你指定的）
        candidates.append(os.path.join(here, "so", name))
        # 舊版相容：native/arm64-v8a
        candidates.append(os.path.join(here, "native", "arm64-v8a", name))
        parent = os.path.dirname(here)
        candidates.append(os.path.join(parent, name))
        candidates.append(os.path.join(parent, "so", name))
        candidates.append(os.path.join(parent, "native", "arm64-v8a", name))
    except Exception:
        pass
    try:
        cwd = os.getcwd()
        candidates.append(os.path.join(cwd, name))
        candidates.append(os.path.join(cwd, "so", name))
        candidates.append(os.path.join(cwd, "py", name))
        candidates.append(os.path.join(cwd, "py", "so", name))
        candidates.append(os.path.join(cwd, "py", "native", "arm64-v8a", name))
    except Exception:
        pass
    seen = set()
    for p in candidates:
        p = os.path.abspath(p)
        if p in seen:
            continue
        seen.add(p)
        if os.path.isfile(p):
            return p
    return ""


def _pack(obj):
    raw = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    raw = zlib.compress(raw, 9)
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _unpack(s):
    s = str(s)
    s += "=" * ((4 - len(s) % 4) % 4)
    return json.loads(zlib.decompress(base64.urlsafe_b64decode(s.encode("ascii"))).decode("utf-8"))


def _clean_text(s):
    if s is None:
        return ""
    s = unescape(str(s))
    s = re.sub(r"(?is)<script\b.*?</script>", " ", s)
    s = re.sub(r"(?is)<style\b.*?</style>", " ", s)
    s = re.sub(r"(?is)<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _first_url(obj):
    """遞迴找 JSON 中第一個 m3u8/mp4 URL。"""
    if isinstance(obj, str):
        s = obj.replace("\\/", "/").replace("\\u0026", "&")
        m = re.search(r"https?://[^\s\"'<>]+(?:\.m3u8|\.mp4)(?:[^\s\"'<>]*)", s, re.I)
        return unescape(m.group(0)) if m else ""
    if isinstance(obj, dict):
        preferred = (
            "playUrl", "play_url", "videoUrl", "video_url", "videoSrc", "video_src",
            "url", "src", "hls", "hlsUrl", "hls_url", "backup_url", "backupUrl"
        )
        for k in preferred:
            if k in obj:
                u = _first_url(obj.get(k))
                if u:
                    return u
        for v in obj.values():
            u = _first_url(v)
            if u:
                return u
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            u = _first_url(v)
            if u:
                return u
    return ""


def _http_get(url, referer=None, timeout=18, max_bytes=8 * 1024 * 1024):
    headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/json,text/plain,*/*;q=0.8",
        "Accept-Language": "zh-TW,zh;q=0.9,zh-CN;q=0.8,en;q=0.5",
        "Connection": "close",
    }
    if referer:
        headers["Referer"] = referer
    req = Request(url, headers=headers)
    ctx = ssl.create_default_context()
    with urlopen(req, timeout=timeout, context=ctx) as r:
        data = r.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise RuntimeError("站源頁面過大")
        enc = "utf-8"
        ctype = r.headers.get("Content-Type", "") if getattr(r, "headers", None) else ""
        m = re.search(r"charset=([\w.-]+)", ctype, re.I)
        if m:
            enc = m.group(1)
        try:
            return data.decode(enc, "replace")
        except Exception:
            return data.decode("utf-8", "replace")


def _probe_native_media(url, headers=None, timeout=3):
    """Probe a native playback URL just enough to tell FongMi/Media3 its container."""
    u = str(url or "")
    low = u.lower().split("?", 1)[0]
    if low.endswith(".m3u8"):
        return "application/x-mpegURL", {"by": "extension", "contentType": ""}
    if low.endswith(".mpd"):
        return "application/dash+xml", {"by": "extension", "contentType": ""}
    if low.endswith(".mp4") or low.endswith(".m4v") or low.endswith(".mov"):
        return "video/mp4", {"by": "extension", "contentType": ""}
    if low.endswith(".ts"):
        return "video/mp2t", {"by": "extension", "contentType": ""}

    h = {}
    for k, v in (headers or {}).items():
        if k is not None and v is not None:
            h[str(k)] = str(v)
    h.setdefault("User-Agent", UA)
    h.setdefault("Accept", "*/*")
    h["Range"] = "bytes=0-4095"
    req = Request(u, headers=h)
    ctx = ssl.create_default_context()
    info = {"by": "probe", "contentType": "", "status": "", "first": ""}
    try:
        with urlopen(req, timeout=timeout, context=ctx) as r:
            try:
                info["status"] = str(getattr(r, "status", "") or r.getcode())
            except Exception:
                pass
            ctype = ""
            try:
                ctype = (r.headers.get("Content-Type", "") or "").split(";", 1)[0].strip().lower()
            except Exception:
                pass
            info["contentType"] = ctype
            b = r.read(4096) or b""
        lead = b.lstrip()[:64]
        info["first"] = b[:16].hex()

        if "mpegurl" in ctype or lead.startswith(b"#EXTM3U"):
            return "application/x-mpegURL", info
        if "dash+xml" in ctype or (lead.startswith(b"<?xml") and b"<MPD" in b[:4096]) or lead.startswith(b"<MPD"):
            return "application/dash+xml", info
        if ctype in ("video/mp4", "application/mp4"):
            return "video/mp4", info
        if len(b) >= 8 and b[4:8] in (b"ftyp", b"styp", b"moof"):
            return "video/mp4", info
        if ctype in ("video/mp2t", "video/mpegts"):
            return "video/mp2t", info
        if len(b) >= 377 and b[0] == 0x47 and b[188] == 0x47 and b[376] == 0x47:
            return "video/mp2t", info
        if ctype == "video/webm" or b.startswith(b"\x1a\x45\xdf\xa3"):
            return "video/webm", info
        return "", info
    except Exception as e:
        info["error"] = "%s: %s" % (e.__class__.__name__, e)
        return "", info


_HEX32_RE = re.compile(r"^[0-9a-fA-F]{32}$")


def _hex16(value):
    """Normalize a 16-byte key/KID to 32 lowercase hex chars."""
    if value is None:
        return ""
    if isinstance(value, (bytes, bytearray)):
        b = bytes(value)
        return b.hex() if len(b) == 16 else ""
    text = str(value).strip().replace("{", "").replace("}", "")
    compact = re.sub(r"[-:\s]", "", text)
    if _HEX32_RE.match(compact):
        return compact.lower()
    try:
        t = text.replace("-", "+").replace("_", "/")
        t += "=" * ((4 - len(t) % 4) % 4)
        b = base64.b64decode(t)
        if len(b) == 16:
            return b.hex()
    except Exception:
        pass
    return ""


def _find_native_kid(data):
    """Look for a KID exposed by core.nativePlan before touching the media URL."""
    wanted = ("kid", "keyid", "key_id", "defaultkid", "default_kid", "cenc_key_id")
    seen = set()

    def walk(v, path=""):
        oid = id(v)
        if isinstance(v, (dict, list)):
            if oid in seen:
                return ("", "")
            seen.add(oid)
        if isinstance(v, dict):
            for k, val in v.items():
                lk = str(k).replace("-", "_").lower()
                if lk in wanted:
                    h = _hex16(val)
                    if h:
                        return h, (path + "." + str(k)).strip(".")
            for k, val in v.items():
                if isinstance(val, (dict, list)):
                    got = walk(val, (path + "." + str(k)).strip("."))
                    if got[0]:
                        return got
        elif isinstance(v, list):
            for i, val in enumerate(v[:16]):
                if isinstance(val, (dict, list)):
                    got = walk(val, "%s[%d]" % (path, i))
                    if got[0]:
                        return got
        return ("", "")
    return walk(data)


def _extract_mp4_kid(blob):
    """Extract default_KID from a CENC MP4 tenc/pssh box."""
    if not blob:
        return "", ""
    b = bytes(blob)
    pos = 0
    while True:
        i = b.find(b"tenc", pos)
        if i < 0:
            break
        if i >= 4:
            try:
                size = int.from_bytes(b[i-4:i], "big")
            except Exception:
                size = 0
            payload = i + 4
            end = (i - 4 + size) if size >= 8 else len(b)
            ks = payload + 8
            if ks + 16 <= min(end, len(b)):
                kid = b[ks:ks+16]
                if kid != b"\x00" * 16:
                    return kid.hex(), "mp4:tenc"
        pos = i + 4
    pos = 0
    while True:
        i = b.find(b"pssh", pos)
        if i < 0:
            break
        payload = i + 4
        if payload + 24 <= len(b):
            version = b[payload]
            if version == 1:
                count_off = payload + 20
                if count_off + 4 <= len(b):
                    count = int.from_bytes(b[count_off:count_off+4], "big")
                    if 0 < count <= 64 and count_off + 4 + 16 <= len(b):
                        kid = b[count_off+4:count_off+20]
                        if kid != b"\x00" * 16:
                            return kid.hex(), "mp4:pssh"
        pos = i + 4
    return "", ""


def _scan_mp4_drm(blob):
    """Return lightweight CENC signalling diagnostics from the MP4 init area."""
    b = bytes(blob or b"")
    pssh = []
    pos = 0
    while True:
        i = b.find(b"pssh", pos)
        if i < 0:
            break
        try:
            start = i - 4
            size = int.from_bytes(b[start:i], "big") if start >= 0 else 0
            payload = i + 4
            if size >= 32 and payload + 20 <= len(b):
                ver = b[payload]
                system_id = b[payload+4:payload+20].hex()
                pssh.append("v%d:%s" % (ver, system_id))
        except Exception:
            pass
        pos = i + 4
    schemes = []
    pos = 0
    while True:
        i = b.find(b"schm", pos)
        if i < 0:
            break
        try:
            payload = i + 4
            if payload + 8 <= len(b):
                st = b[payload+4:payload+8].decode("ascii", "ignore")
                if st and st not in schemes:
                    schemes.append(st)
        except Exception:
            pass
        pos = i + 4
    return {
        "pssh": pssh,
        "schemes": schemes,
        "has_common_pssh": any(x.endswith("1077efecc0b24d02ace33c1e52e2fb4b") for x in pssh),
        "has_clearkey_pssh": any(x.endswith("e2719d58a985b3c9781ab030af78d30e") for x in pssh),
    }


def _probe_cenc_kid(url, headers=None, timeout=5, max_bytes=2*1024*1024):
    """Fetch only the MP4 initialization area and derive default_KID."""
    h = {}
    for k, v in (headers or {}).items():
        if k is not None and v is not None:
            h[str(k)] = str(v)
    h.setdefault("User-Agent", UA)
    h.setdefault("Accept", "*/*")
    h["Range"] = "bytes=0-%d" % (max_bytes - 1)
    req = Request(str(url), headers=h)
    ctx = ssl.create_default_context()
    try:
        with urlopen(req, timeout=timeout, context=ctx) as r:
            b = r.read(max_bytes) or b""
        kid, src = _extract_mp4_kid(b)
        drm_scan = _scan_mp4_drm(b)
        return kid, src, {"bytes": len(b), "first": b[:16].hex(), "error": "",
                          "pssh": drm_scan.get("pssh") or [],
                          "schemes": drm_scan.get("schemes") or [],
                          "commonPssh": bool(drm_scan.get("has_common_pssh")),
                          "clearKeyPssh": bool(drm_scan.get("has_clearkey_pssh"))}
    except Exception as e:
        return "", "", {"bytes": 0, "first": "", "error": "%s: %s" % (e.__class__.__name__, e), "pssh": [], "schemes": [], "commonPssh": False, "clearKeyPssh": False}


def _native_clear_key_info(data, url, headers):
    key_raw = data.get("decryptionKey") if isinstance(data, dict) else ""
    if not key_raw and isinstance(data, dict):
        key_raw = data.get("key") or ""
    key_hex = _hex16(key_raw)
    kid_hex, kid_source = _find_native_kid(data if isinstance(data, dict) else {})
    media_probe = {"bytes": 0, "first": "", "error": "", "pssh": [], "schemes": [], "commonPssh": False, "clearKeyPssh": False}
    if key_hex and not kid_hex and url:
        kid_hex, kid_source, media_probe = _probe_cenc_kid(url, headers)
    return {
        "key_hex": key_hex,
        "key_len": len(str(key_raw)) if key_raw else 0,
        "kid_hex": kid_hex,
        "kid_source": kid_source,
        "media_probe": media_probe,
        "ready": bool(key_hex and kid_hex),
    }


class _LinkCollector(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self.stack = []
        self.items = []
        self._cur = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag.lower() == "a":
            href = attrs.get("href", "") or ""
            if "/detail" in href and "series_id=" in href:
                self._cur = {
                    "href": href,
                    "title": attrs.get("title", "") or "",
                    "text": [],
                    "img": "",
                    "alt": "",
                }
                self.stack.append("a")
                return
        if self._cur is not None:
            self.stack.append(tag.lower())
            if tag.lower() == "img":
                self._cur["img"] = attrs.get("data-src") or attrs.get("src") or self._cur.get("img", "")
                self._cur["alt"] = attrs.get("alt") or self._cur.get("alt", "")

    def handle_endtag(self, tag):
        if self._cur is None:
            return
        tag = tag.lower()
        if tag == "a":
            self.items.append(self._cur)
            self._cur = None
            self.stack = []
        elif self.stack:
            try:
                self.stack.pop()
            except Exception:
                pass

    def handle_data(self, data):
        if self._cur is not None:
            self._cur["text"].append(data)


def _series_id_from_href(href):
    try:
        q = parse_qs(urlparse(urljoin(BASE, href)).query)
        sid = (q.get("series_id") or [""])[0]
        if sid:
            return str(sid)
    except Exception:
        pass
    m = re.search(r"series_id=(\d+)", href or "")
    return m.group(1) if m else ""


def _parse_cards(html):
    parser = _LinkCollector()
    try:
        parser.feed(html)
    except Exception:
        pass
    out = []
    seen = set()
    for x in parser.items:
        sid = _series_id_from_href(x.get("href", ""))
        if not sid or sid in seen:
            continue
        seen.add(sid)
        title = _clean_text(x.get("title") or x.get("alt") or "".join(x.get("text") or []))
        title = re.sub(r"^全\s*\d+\s*集\s*", "", title)
        if not title:
            title = "短劇 " + sid
        pic = x.get("img") or ""
        if pic.startswith("//"):
            pic = "https:" + pic
        elif pic.startswith("/"):
            pic = urljoin(BASE, pic)
        out.append({"id": sid, "title": title, "pic": pic})

    if not out:
        pat = re.compile(
            r"(?is)<a\b[^>]*href=[\"']([^\"']*?/detail\?[^\"']*?series_id=(\d+)[^\"']*)[\"'][^>]*>(.*?)</a>"
        )
        for href, sid, body in pat.findall(html):
            if sid in seen:
                continue
            seen.add(sid)
            title = _clean_text(body)
            title = re.sub(r"^全\s*\d+\s*集\s*", "", title)
            imgm = re.search(r"(?is)<img\b[^>]*(?:data-src|src)=[\"']([^\"']+)", body)
            pic = imgm.group(1) if imgm else ""
            if pic.startswith("//"):
                pic = "https:" + pic
            elif pic.startswith("/"):
                pic = urljoin(BASE, pic)
            out.append({"id": sid, "title": title or ("短劇 " + sid), "pic": pic})
    return out


def _meta_content(html, key, prop=True):
    attr = "property" if prop else "name"
    pats = [
        r"(?is)<meta\b[^>]*%s=[\"']%s[\"'][^>]*content=[\"']([^\"']*)[\"'][^>]*>" % (attr, re.escape(key)),
        r"(?is)<meta\b[^>]*content=[\"']([^\"']*)[\"'][^>]*%s=[\"']%s[\"'][^>]*>" % (attr, re.escape(key)),
    ]
    for p in pats:
        m = re.search(p, html)
        if m:
            return unescape(m.group(1)).strip()
    return ""


def _extract_json_script(html, script_id):
    m = re.search(
        r"(?is)<script\b[^>]*id=[\"']%s[\"'][^>]*>(.*?)</script>" % re.escape(script_id), html
    )
    if not m:
        return None
    s = unescape(m.group(1)).strip()
    try:
        return json.loads(s)
    except Exception:
        a = s.find("{")
        b = s.rfind("}")
        if 0 <= a < b:
            try:
                return json.loads(s[a:b + 1])
            except Exception:
                return None
    return None


def _json_string_field(html, key):
    m = re.search(r'"%s"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"' % re.escape(key), html or '', re.I)
    if not m:
        return ""
    raw = m.group(1)
    try:
        return json.loads('"' + raw.replace('"', '\\"') + '"')
    except Exception:
        return unescape(raw.replace('\\u002F', '/').replace('\\/', '/').replace('\\u0026', '&'))


def _router_episode_info(html, sid):
    html = html or ''
    m = re.search(r'"vid_list"\s*:\s*\[([^\]]*)\]', html, re.I | re.S)
    vids = []
    if m:
        for v in re.findall(r'"?(\d{8,})"?', m.group(1)):
            if v not in vids:
                vids.append(v)
    acc = 0
    macc = re.search(r'"accessible_episode_cnt"\s*:\s*(\d+)', html, re.I)
    if macc:
        try:
            acc = int(macc.group(1))
        except Exception:
            acc = 0
    series_name = _json_string_field(html, 'series_name')
    cover = _json_string_field(html, 'series_cover') or _json_string_field(html, 'cover_url')
    eps = []
    for i, vid in enumerate(vids):
        page = (BASE + '/player/' + str(sid)) if i == 0 else (BASE + '/player/' + str(sid) + '/' + str(vid))
        eps.append({
            'page': page,
            'eid': str(vid),
            'num': i + 1,
            'accessible': (acc <= 0 or (i + 1) <= acc),
        })
    return {'episodes': eps, 'accessible': acc, 'series_name': series_name, 'cover': cover}


def _normalize_media_url(raw):
    u = unescape(str(raw or ''))
    u = u.replace('\\u002F', '/').replace('\\/', '/').replace('\\u0026', '&')
    u = re.sub(r'([?&])Range=[^&]*', r'\1', u, flags=re.I)
    u = re.sub(r'[?&]$', '', u)
    if u.startswith('//'):
        u = 'https:' + u
    return u


def _detail_info(html, sid):
    title = ""
    m = re.search(r"(?is)<h1\b[^>]*>(.*?)</h1>", html)
    if m:
        title = _clean_text(m.group(1))
    if not title:
        title = _meta_content(html, "og:title", True)
        title = re.sub(r"[_\-|].*$", "", title).strip()

    pic = _meta_content(html, "og:image", True)
    desc = _meta_content(html, "description", False)
    if not desc:
        m = re.search(r"(?is)簡介[:：]\s*(.*?)(?:<|播放正片|下載)", html)
        if m:
            desc = _clean_text(m.group(1))

    episodes = []
    seen = set()
    for href, tail in re.findall(
        r"(?is)href=[\"']([^\"']*/player/%s(?:/([0-9]+))?[^\"']*)[\"']" % re.escape(str(sid)), html
    ):
        full = urljoin(BASE, href)
        key = full.split("#", 1)[0]
        if key in seen:
            continue
        seen.add(key)
        episodes.append({"page": key, "eid": tail or ""})

    data = _extract_json_script(html, "videoInitialData")
    found = []

    def walk(x):
        if isinstance(x, dict):
            eid = None
            for k in ("chapter_id", "chapterId", "episode_id", "episodeId", "video_id", "videoId", "id"):
                v = x.get(k)
                if isinstance(v, (str, int)) and re.match(r"^[0-9]{8,}$", str(v)):
                    eid = str(v)
                    break
            num = None
            for k in ("chapterNum", "episodeNum", "currentEpisode", "episode", "index", "seq"):
                v = x.get(k)
                if isinstance(v, (str, int)) and str(v).isdigit():
                    num = int(v)
                    break
            if eid and eid != str(sid):
                found.append((num, eid))
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    if data is not None:
        walk(data)

    for key in ("chapter_id", "chapterId", "episode_id", "episodeId", "video_id", "videoId"):
        for eid in re.findall(r"[\"']?%s[\"']?\s*[:=]\s*[\"']?([0-9]{8,})" % key, html):
            if eid != str(sid):
                found.append((None, eid))

    existing_eids = set(e.get("eid") for e in episodes if e.get("eid"))
    if found:
        with_num = [(n, e) for n, e in found if n is not None]
        without_num = [(n, e) for n, e in found if n is None]
        with_num.sort(key=lambda z: z[0])
        ordered = with_num + without_num
        for n, eid in ordered:
            if eid in existing_eids:
                continue
            existing_eids.add(eid)
            episodes.append({"page": "%s/player/%s/%s" % (BASE, sid, eid), "eid": eid, "num": n})

    first_page = "%s/player/%s" % (BASE, sid)
    if not episodes or all(e.get("page") != first_page for e in episodes):
        episodes.insert(0, {"page": first_page, "eid": "", "num": 1})

    final = []
    seen_pages = set()
    for i, e in enumerate(episodes):
        p = e.get("page")
        if not p or p in seen_pages:
            continue
        seen_pages.add(p)
        num = e.get("num")
        if not isinstance(num, int) or num <= 0:
            num = len(final) + 1
        final.append({"page": p, "eid": e.get("eid", ""), "num": num})

    return {
        "title": title or ("短劇 " + str(sid)),
        "pic": pic,
        "desc": desc,
        "episodes": final,
    }


def _extract_media_from_html(html):
    pats = [
        r'(?is)"main_url"\s*:\s*"([^"]+)"',
        r'(?is)"backup_url"\s*:\s*"([^"]+)"',
        r'(?is)"contentUrl"\s*:\s*"([^"]+)"',
        r"(?is)data-play-src=[\"']([^\"']+)[\"']",
        r"(?is)data-hls=[\"']([^\"']+)[\"']",
        r"(?i)(https?://[^\s\"'<>]+\.(?:m3u8|mp4)[^\s\"'<>]*)",
        r"(?is)[\"']?(?:videoSrc|videoUrl|playUrl|src|url)[\"']?\s*[:=]\s*[\"']([^\"']+\.(?:m3u8|mp4)[^\"']*)[\"']",
    ]
    for p in pats:
        m = re.search(p, html or '')
        if m:
            u = _normalize_media_url(m.group(1))
            if re.match(r'^https?://', u, re.I):
                return u
    data = _extract_json_script(html, "videoInitialData")
    if data is not None:
        return _normalize_media_url(_first_url(data))
    m = re.search(r"(?s)player_aaaa\s*=\s*(\{.*?\})\s*</script>", html or '')
    if m:
        try:
            u = _first_url(json.loads(m.group(1)))
            if u:
                return _normalize_media_url(u)
        except Exception:
            pass
    return ""


def _fallback_play_api(series_id, episode_id):
    if not series_id:
        return ""
    base = "https://djapi.999888456.xyz/api/hongguo/play?"
    attempts = []
    if episode_id:
        attempts.extend([
            {"series_id": series_id, "episode_id": episode_id},
            {"series_id": series_id, "video_id": episode_id},
            {"series_id": series_id, "chapter_id": episode_id},
            {"playlet_id": series_id, "chapter_id": episode_id},
            {"book_id": series_id, "chapter_id": episode_id},
        ])
    attempts.extend([
        {"series_id": series_id},
        {"playlet_id": series_id},
    ])
    for q in attempts:
        try:
            text = _http_get(base + urlencode(q), referer=BASE + "/", timeout=10, max_bytes=1024 * 1024)
            try:
                obj = json.loads(text)
                u = _first_url(obj)
            except Exception:
                u = _extract_media_from_html(text)
            if u:
                return u
        except Exception:
            continue
    return ""


# ============================================================================
# 離線分類 DB（外掛讀取）
# ============================================================================
_OFFLINE_DB = None
_OFFLINE_LOCK = threading.RLock()


def _offline_db():
    global _OFFLINE_DB
    if _OFFLINE_DB is None:
        with _OFFLINE_LOCK:
            if _OFFLINE_DB is None:
                path = _find_sidecar(_OFFLINE_DB_NAME)
                if not path:
                    print("[全劇視界] 找不到 %s，離線分類停用" % _OFFLINE_DB_NAME)
                    _OFFLINE_DB = {}
                else:
                    try:
                        with open(path, "rb") as f:
                            blob = f.read()
                        _OFFLINE_DB = json.loads(zlib.decompress(blob).decode("utf-8"))
                    except Exception as e:
                        print("[全劇視界] %s 讀取失敗: %s" % (_OFFLINE_DB_NAME, e))
                        _OFFLINE_DB = {}
    return _OFFLINE_DB


# ============================================================================
# 原生核心（外掛 .so）
# ============================================================================
class _NativeCore(object):
    def __init__(self):
        self._lib = None
        self._lock = threading.RLock()
        self._loaded_path = ""
        self._load_attempts = []
        self._initialized = False
        self._init_directory = ""
        self._init_result = None
        self._init_error = ""
        self._playback_sequence = int(time.time() * 1000)

    @staticmethod
    def platform_info():
        machine = (platform.machine() or "").strip().lower()
        plat = (platform.platform() or "").strip().lower()
        is_arm64 = (
            machine in ("aarch64", "arm64", "arm64-v8a")
            or "aarch64" in machine
            or "arm64" in machine
            or "armv8" in machine
        )
        is_android = bool(
            os.environ.get("ANDROID_ROOT")
            or os.environ.get("ANDROID_DATA")
            or os.path.exists("/system/bin/getprop")
            or os.path.exists("/system/build.prop")
            or "android" in plat
        )
        return {"machine": machine, "platform": plat, "is_android": is_android, "is_arm64": is_arm64}

    @staticmethod
    def available_platform():
        info = _NativeCore.platform_info()
        return bool(info.get("is_android") and info.get("is_arm64"))

    def _external_candidates(self):
        out = []
        seen = set()
        p = _find_sidecar(_NATIVE_SO_NAME)
        if p and p not in seen:
            seen.add(p)
            out.append(p)
        return out

    def _bind(self, p):
        lib = ctypes.CDLL(p)
        lib.DuanjuRequest.argtypes = [ctypes.c_char_p]
        lib.DuanjuRequest.restype = ctypes.c_void_p
        lib.DuanjuFree.argtypes = [ctypes.c_void_p]
        lib.DuanjuFree.restype = None
        self._lib = lib
        self._loaded_path = p
        return lib

    def _load(self):
        if self._lib is not None:
            return self._lib
        if not self.available_platform():
            raise RuntimeError("此平台不是 Android ARM64，已停用原生 .so")
        # 先載入 FFmpeg 依賴，避免 libduanju_core.so dlopen 時找不到符號
        try:
            _ffmpeg.load()
        except Exception:
            pass
        self._load_attempts = []
        last = None
        for p in self._external_candidates():
            try:
                self._load_attempts.append('TRY ' + p)
                return self._bind(p)
            except Exception as e:
                last = e
                self._load_attempts.append('FAIL %s => %s: %s' % (p, e.__class__.__name__, e))
        if last is not None:
            raise RuntimeError("Android 原生核心載入失敗: %s" % last)
        raise RuntimeError("Android 原生核心載入失敗: 找不到 %s，請放在 .py 同目錄" % _NATIVE_SO_NAME)

    def _request_raw(self, payload):
        lib = self._load()
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        with self._lock:
            ptr = lib.DuanjuRequest(raw)
            if not ptr:
                raise RuntimeError("DuanjuRequest 回傳 NULL")
            try:
                text = ctypes.string_at(ptr).decode("utf-8", "replace")
            finally:
                lib.DuanjuFree(ptr)
        obj = json.loads(text)
        if isinstance(obj, dict) and "ok" in obj:
            if not obj.get("ok"):
                raise RuntimeError(str(obj.get("error") or "原生接口失敗"))
            return obj.get("data")
        return obj

    def _runtime_directory(self):
        self._load()
        bases = []
        for d in [os.path.dirname(self._loaded_path or ""), os.environ.get("TMPDIR"), tempfile.gettempdir(), os.path.dirname(os.path.abspath(__file__))]:
            if d:
                d = os.path.abspath(d)
                if d not in bases:
                    bases.append(d)
        errors = []
        for base in bases:
            try:
                target = os.path.abspath(os.path.join(base, "quanju_core_v240"))
                if not target.startswith(os.sep):
                    continue
                if not os.path.isdir(target):
                    os.makedirs(target)
                probe = os.path.join(target, ".write_test")
                with open(probe, "wb") as f:
                    f.write(b"ok")
                try:
                    os.remove(probe)
                except Exception:
                    pass
                return target
            except Exception as e:
                errors.append("%s => %s: %s" % (base, e.__class__.__name__, e))
        raise RuntimeError("找不到可寫的原生核心資料目錄: " + " | ".join(errors))

    def _ensure_initialized(self):
        if self._initialized:
            return self._init_result
        with self._lock:
            if self._initialized:
                return self._init_result
            directory = self._runtime_directory()
            self._init_directory = directory
            try:
                result = self._request_raw({"action": "initialize", "directory": directory})
                self._init_result = result
                self._init_error = ""
                self._initialized = True
                return result
            except Exception as e:
                self._init_error = "%s: %s" % (e.__class__.__name__, e)
                raise RuntimeError("APK 原生核心 initialize 失敗: %s" % e)

    def next_sequence(self):
        with self._lock:
            self._playback_sequence += 1
            return self._playback_sequence

    def request(self, payload):
        action = str((payload or {}).get("action") or "").strip().lower() if isinstance(payload, dict) else ""
        if action == "initialize":
            return self._request_raw(payload)
        self._ensure_initialized()
        return self._request_raw(payload)


_native = _NativeCore()


# ============================================================================
# FFmpeg 解密橋接（外掛 .so）
# ============================================================================
class _FFmpegDecryptor(object):
    """Use the original APK's FFmpegKit to decrypt CENC MP4 into a clear cached MP4."""
    LOAD_ORDER = _FFMPEG_SO_NAMES

    def __init__(self):
        self._lock = threading.RLock()
        self._loaded = False
        self._error = ""
        self._dir = ""
        self._handles = []
        self._lib = None
        self._execute = None
        self._attempts = []

    def _base_dir(self):
        candidates = []
        for d in [
            os.path.dirname(_native._loaded_path or ""),
            _native._init_directory,
            os.environ.get("TMPDIR"),
            tempfile.gettempdir(),
            os.path.dirname(os.path.abspath(__file__)),
        ]:
            if d:
                d = os.path.abspath(d)
                if d not in candidates:
                    candidates.append(d)
        errors = []
        for base in candidates:
            try:
                root = os.path.join(base, "quanju_ffmpeg_v240")
                if not os.path.isdir(root):
                    os.makedirs(root)
                probe = os.path.join(root, ".write_test")
                with open(probe, "wb") as f:
                    f.write(b"ok")
                try:
                    os.remove(probe)
                except Exception:
                    pass
                return root
            except Exception as e:
                errors.append("%s => %s: %s" % (base, e.__class__.__name__, e))
        raise RuntimeError("找不到可寫 FFmpeg 目錄: " + " | ".join(errors))

    def _extract(self, root, name):
        """外掛模式：直接找 .py 同目錄的 .so。"""
        p = _find_sidecar(name)
        if p:
            return p
        local = os.path.join(root, name)
        if os.path.isfile(local):
            return local
        raise RuntimeError("找不到 FFmpeg 外掛 %s，請放在 .py 同目錄" % name)

    def load(self):
        if self._loaded:
            return True
        with self._lock:
            if self._loaded:
                return True
            if not _NativeCore.available_platform():
                raise RuntimeError("FFmpeg 解密橋接只支援 Android ARM64")
            self._attempts = []
            try:
                root = self._base_dir()
                self._dir = root
                paths = {}
                for name in self.LOAD_ORDER:
                    p = self._extract(root, name)
                    paths[name] = p
                    self._attempts.append("FOUND OK " + p)
                mode = getattr(ctypes, "RTLD_GLOBAL", 0)
                handles = []
                for name in self.LOAD_ORDER:
                    p = paths[name]
                    try:
                        h = ctypes.CDLL(p, mode=mode)
                    except TypeError:
                        h = ctypes.CDLL(p)
                    handles.append(h)
                    self._attempts.append("DLOPEN OK " + name)
                lib = handles[-1]
                fn = lib.ffmpeg_execute
                fn.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_char_p)]
                fn.restype = ctypes.c_int
                self._handles = handles
                self._lib = lib
                self._execute = fn
                self._loaded = True
                self._error = ""
                return True
            except Exception as e:
                self._error = "%s: %s" % (e.__class__.__name__, e)
                self._attempts.append("ERROR " + self._error)
                raise RuntimeError("APK FFmpegKit 載入失敗: %s" % e)

    def status(self):
        try:
            self.load()
            ok = True
        except Exception:
            ok = False
        return {
            "ok": ok,
            "loaded": self._loaded,
            "error": self._error,
            "directory": self._dir,
            "attempts": list(self._attempts),
            "embeddedFiles": list(self.LOAD_ORDER),
        }

    def _cache_dir(self):
        self.load()
        d = os.path.join(self._dir, "clear_mp4")
        if not os.path.isdir(d):
            os.makedirs(d)
        return d

    @staticmethod
    def _stable_id(p, data, url):
        d = (p or {}).get("d") or {}
        c = (p or {}).get("c") or {}
        vals = [
            str(d.get("source") or ""),
            str(d.get("sourceId") or d.get("id") or ""),
            str(c.get("sourceId") or c.get("id") or c.get("videoId") or c.get("chapterId") or ""),
            str((p or {}).get("i") or 0),
        ]
        if not vals[1] and not vals[2]:
            vals.append(str(url or ""))
        return hashlib.sha256("|".join(vals).encode("utf-8", "replace")).hexdigest()[:32]

    @staticmethod
    def _header_arg(headers):
        if not isinstance(headers, dict):
            return ""
        lines = []
        for k, v in headers.items():
            if not k or v is None:
                continue
            kl = str(k).strip().lower()
            if kl in ("user-agent", "range", "content-length", "host", "connection"):
                continue
            lines.append("%s: %s" % (str(k).strip(), str(v).strip()))
        return ("\r\n".join(lines) + "\r\n") if lines else ""

    def _cleanup(self, keep=""):
        try:
            d = self._cache_dir()
            items = []
            total = 0
            for n in os.listdir(d):
                p = os.path.join(d, n)
                if p == keep or not os.path.isfile(p) or not n.endswith('.mp4'):
                    continue
                st = os.stat(p)
                total += st.st_size
                items.append((st.st_mtime, st.st_size, p))
            try:
                if keep and os.path.isfile(keep):
                    total += os.path.getsize(keep)
            except Exception:
                pass
            if total <= 768 * 1024 * 1024:
                return
            items.sort()
            target = 512 * 1024 * 1024
            for _, sz, p in items:
                if total <= target:
                    break
                try:
                    os.remove(p)
                    total -= sz
                except Exception:
                    pass
        except Exception:
            pass

    def decrypt_to_mp4(self, url, key_hex, headers, p, data):
        key_hex = _hex16(key_hex)
        if not key_hex:
            raise RuntimeError("原生 resolve 未提供有效 32-hex decryptionKey")
        self.load()
        cache = self._cache_dir()
        sid = self._stable_id(p, data, url)
        final = os.path.join(cache, "qj_%s.mp4" % sid)
        if os.path.isfile(final):
            try:
                if os.path.getsize(final) > 256 * 1024:
                    try:
                        os.utime(final, None)
                    except Exception:
                        pass
                    return final, True, 0
            except Exception:
                pass
        tmp = final + ".tmp.mp4"
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass

        args = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-decryption_key", key_hex]
        ua = ""
        if isinstance(headers, dict):
            ua = str(headers.get("User-Agent") or headers.get("user-agent") or "")
        if ua:
            args += ["-user_agent", ua]
        hs = self._header_arg(headers)
        if hs:
            args += ["-headers", hs]
        args += ["-i", str(url), "-map", "0:v?", "-map", "0:a?", "-sn", "-dn", "-c", "copy", "-f", "mp4", tmp]

        encoded = [str(x).encode("utf-8") for x in args]
        argv = (ctypes.c_char_p * len(encoded))(*encoded)
        with self._lock:
            rc = int(self._execute(len(encoded), argv))
        if rc != 0:
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except Exception:
                pass
            raise RuntimeError("FFmpeg CENC 解密失敗 rc=%d" % rc)
        if not os.path.isfile(tmp) or os.path.getsize(tmp) < 64 * 1024:
            sz = os.path.getsize(tmp) if os.path.isfile(tmp) else 0
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except Exception:
                pass
            raise RuntimeError("FFmpeg 輸出異常 size=%d" % sz)
        try:
            os.replace(tmp, final)
        except Exception:
            try:
                if os.path.exists(final):
                    os.remove(final)
            except Exception:
                pass
            os.rename(tmp, final)
        self._cleanup(final)
        return final, False, rc


_ffmpeg = _FFmpegDecryptor()


# ============================================================================
# Spider 主體
# ============================================================================
class Spider(_BaseSpider):
    def getName(self):
        return "全劇視界.v2.6.0.Plugins"

    def init(self, extend=""):
        self.extend = extend or ""
        self.site_source = "hongguo"
        if isinstance(extend, str):
            m = re.search(r"(?:^|[,;&\s])source=([a-z0-9_-]+)", extend, re.I)
            if m:
                self.site_source = m.group(1).lower()
        elif isinstance(extend, dict):
            self.site_source = str(extend.get("source") or "hongguo").lower()
        self.prefer_native = _NativeCore.available_platform()
        self.native_only = False
        self.plan_diag = False
        self._catalog_cache = {}
        self._detail_cache = {}
        if isinstance(extend, str):
            low = extend.lower()
            if "webonly" in low:
                self.prefer_native = False
            if "nativeonly" in low:
                self.native_only = True
                self.prefer_native = True
            if "plandiag" in low:
                self.plan_diag = True
                self.native_only = True
                self.prefer_native = True

    def destroy(self):
        pass

    def isVideoFormat(self, url):
        return bool(re.search(r"\.(?:m3u8|mp4)(?:\?|$)", str(url or ""), re.I))

    def manualVideoCheck(self):
        return False

    @staticmethod
    def _extract_native_categories(payload, src):
        out = []
        seen = set()

        def add(cid, title):
            cid = str(cid or '').strip()
            title = str(title or cid).strip()
            if not cid or not title or len(cid) > 100 or len(title) > 100:
                return
            if cid in seen:
                return
            seen.add(cid)
            out.append({'type_id': src + ':' + cid, 'type_name': title})

        def walk_items(obj, depth=0):
            if depth > 3 or not obj:
                return
            if isinstance(obj, list):
                for item in obj[:100]:
                    walk_items(item, depth + 1)
            elif isinstance(obj, dict):
                cid = obj.get('id') or obj.get('value') or obj.get('key') or obj.get('category') or obj.get('code')
                title = obj.get('name') or obj.get('label') or obj.get('title') or obj.get('displayName')
                if isinstance(cid, (str, int)) and isinstance(title, str):
                    add(cid, title)
                for k in ('items', 'options', 'values', 'children', 'categories'):
                    if k in obj:
                        walk_items(obj[k], depth + 1)

        if isinstance(payload, dict):
            for k in ('categories', 'categoryOptions', 'catalogCategories', 'tabs', 'channels'):
                walk_items(payload.get(k))
            flt = payload.get('filters')
            if isinstance(flt, dict):
                for k in ('category', 'categories', 'categoryOptions', 'content_type'):
                    walk_items(flt.get(k))
        return out

    @staticmethod
    def _extract_native_topics(payload, src):
        if not isinstance(payload, dict):
            return []
        out = []
        seen = set()

        def add(v):
            if not isinstance(v, str):
                return
            v = v.strip()
            if not 1 < len(v) <= 24 or v.lower() in ('unknown', 'all', 'null', 'none'):
                return
            if v not in seen and len(out) < 30:
                seen.add(v)
                out.append({'type_id': src + ':topic:' + v, 'type_name': v})

        def gather(v):
            if isinstance(v, str):
                for x in re.split(r'[,，/、|；;]+', v):
                    add(x)
            elif isinstance(v, list):
                for x in v[:24]:
                    gather(x)
            elif isinstance(v, dict):
                for k in ('name', 'label', 'title', 'tagName', 'tag_name'):
                    if isinstance(v.get(k), str):
                        add(v[k])
                        return

        for d in (payload.get('items') or [])[:70]:
            if not isinstance(d, dict):
                continue
            for k in ('tags', 'tagList', 'tag_list', 'genres', 'genre', 'themes', 'theme', 'categories', 'categoryNames'):
                if k in d:
                    gather(d[k])
        return out

    _APP_NAME = "全劇視界 v2.6.0 外掛版"
    _OFFLINE_ALIASES = {'xifan': 'fanguo'}
    _NATIVE_MAP = {
        'real-drama': ('hongguo', 'short_play'),
        'comic-drama': ('hongguo', 'comic_series'),
        'ai-drama': ('hongguo', 'ai_series'),
        'hot-drama': ('hongguo', ''),
    }
    _CHINESE_EQUIV = str.maketrans({
        '黃': '黄', '國': '国', '劇': '剧', '戀': '恋', '愛': '爱', '寵': '宠', '單': '单',
        '體': '体', '歷': '历', '異': '异', '賢': '贤', '實': '实', '時': '时',
        '綜': '综', '藝': '艺', '兒': '儿', '總': '总', '網': '网', '未': '未',
        '類': '类', '動': '动', '遊': '游', '寶': '宝', '華': '华', '蘇': '苏',
        '暫': '暂', '畫': '画', '雲': '云', '靈': '灵', '懸': '悬', '現': '现',
        '裝': '装', '頻': '频', '視': '视', '貓': '猫', '鐘': '钟', '歡': '欢',
        '娛': '娱', '齡': '龄', '韓': '韩', '觸': '触', '臺': '台', '題': '题',
    })

    @classmethod
    def _norm_label(cls, value):
        return re.sub(r'\s+', '', str(value or '').translate(cls._CHINESE_EQUIV)).casefold()

    @classmethod
    def _label_parts(cls, record):
        parts = []
        for field in ('category', 'genre', 'genres', 'categories'):
            v = record.get(field) if isinstance(record, dict) else None
            if isinstance(v, str):
                parts.extend(re.split(r'[,，、/;；|]+', v))
            elif isinstance(v, list):
                parts.extend(str(x) for x in v if isinstance(x, (str, int)))
        tags = record.get('tags') if isinstance(record, dict) else []
        if isinstance(tags, list):
            parts.extend(str(x) for x in tags if isinstance(x, (str, int)))
        return {cls._norm_label(x) for x in parts if str(x or '').strip()}

    def _offline_catalog(self, tid, pg, query=''):
        return None

    def _matches_topic(self, item, provider, topic):
        wanted = self._norm_label(topic)
        if wanted in self._label_parts(item):
            return True
        ref = _offline_db().get('class_by_id', {}).get(provider, {})
        raw = str(item.get('sourceId') or item.get('id') or '')
        if raw.startswith(provider + ':'):
            raw = raw[len(provider) + 1:]
        raw = raw.split('@', 1)[0]
        labels = str(ref.get(raw) or '')
        return bool(labels) and wanted in {self._norm_label(x) for x in re.split(r'[,，、/；;|]+', labels)}

    def _native_catalog(self, tid, pg, query=''):
        tid = str(tid)
        pg = max(int(pg or 1), 1)
        site = getattr(self, 'site_source', 'hongguo')
        if ':' in tid:
            display_src, category = tid.split(':', 1)
            if display_src != site:
                raise RuntimeError('分類不屬於目前頻道: ' + tid)
            if category.startswith('topic:'):
                query = category[len('topic:'):]
                category = ''
        else:
            display_src, category = self._NATIVE_MAP.get(tid, (tid, ''))
        provider = self._OFFLINE_ALIASES.get(display_src, display_src)
        key = (tid, pg, str(query or ''))
        now = time.time()
        cached = self._catalog_cache.get(key)
        if cached and now - cached[0] < 120:
            return cached[1], cached[2]
        req = {'action': 'catalog', 'source': provider, 'page': pg}
        if category:
            req['category'] = category
        if query:
            req['query'] = str(query)
        try:
            data = _native.request(req)
        except Exception as e:
            raise RuntimeError('線上 catalog source=%s category=%s: %s' %
                               (provider, category or '<default>', e))
        if isinstance(data, list):
            data = {'items': data, 'page': pg, 'hasMore': False}
        if not isinstance(data, dict):
            raise RuntimeError('線上 catalog 格式錯誤: ' + type(data).__name__)
        if ':topic:' in tid:
            topic = tid.split(':topic:', 1)[1]
            raw = data.get('items') or []
            data = dict(data)
            data['items'] = [r for r in raw if isinstance(r, dict) and self._matches_topic(r, provider, topic)]
        self._catalog_cache[key] = (now, data, provider)
        return data, provider

    def homeContent(self, filter):
        src = getattr(self, 'site_source', 'hongguo')
        classes = [{'type_id': src, 'type_name': '全部片庫'}]
        names = {'全部', '全部片庫', 'all'}
        db = _offline_db()
        reference = self._OFFLINE_ALIASES.get(src, src)
        seen = {src}
        seen_names = {'全部片庫'}
        for e in db.get('categories', {}).get(reference, []):
            if not isinstance(e, dict):
                continue
            cid = str(e.get('id') or '').strip()
            name = str(e.get('name') or '').strip()
            if not cid or not name or name.lower() in names:
                continue
            key = src + ':' + cid
            if key not in seen:
                classes.append({'type_id': key, 'type_name': name})
                seen.add(key)
                seen_names.add(self._norm_label(name))
        if src in ('guanguo', 'huangdou', 'hongguo', 'huangju', 'fanguo', 'xifan'):
            for name in db.get('topics', {}).get(reference, []):
                key = src + ':topic:' + name
                if key not in seen and self._norm_label(name) not in seen_names:
                    classes.append({'type_id': key, 'type_name': name})
                    seen.add(key)
                    seen_names.add(self._norm_label(name))
        if src in ('piguo', 'niuguo', 'heguo', 'yaguo', 'huangdou'):
            if self._norm_label('未分類') not in seen_names:
                classes.append({'type_id': src + ':topic:未分類', 'type_name': '未分類'})
        if self.prefer_native and len(classes) <= 1:
            try:
                data, _ = self._native_catalog(src, 1)
                for item in self._extract_native_categories(data, src):
                    if item['type_id'] not in seen:
                        classes.append(item)
                        seen.add(item['type_id'])
            except Exception:
                pass
        return {'class': classes, 'filters': {}}

    def homeVideoContent(self):
        if not self.prefer_native:
            return {'list': []}
        try:
            data, provider = self._native_catalog(getattr(self, 'site_source', 'hongguo'), 1)
            return {'list': self._native_vods({'items': (data.get('items') or [])[:18]}, provider,
                                              origin_tid=getattr(self, 'site_source', 'hongguo'), origin_page=1)}
        except Exception:
            return {'list': []}

    @staticmethod
    def _native_remark(d):
        try:
            n = int(d.get("episodes") or 0)
        except Exception:
            n = 0
        if n > 0:
            return "共%d集" % n
        heat = str(d.get("heat") or "").strip()
        if heat:
            return heat
        status = str(d.get("releaseStatus") or "").strip()
        if status and status.lower() not in ("unknown", "null", "none"):
            return status
        return ""

    @staticmethod
    def _episode_no(ch, fallback):
        v = ch.get("currentEpisode") if isinstance(ch, dict) else None
        if isinstance(v, dict):
            for k in ("episode", "episodeNo", "currentEpisode", "number", "num", "index"):
                if k in v:
                    try:
                        x = int(v.get(k))
                        return x if x > 0 else fallback
                    except Exception:
                        pass
        if isinstance(v, (int, float)):
            x = int(v)
            return x if x > 0 else fallback
        if isinstance(v, str):
            t = v.strip()
            try:
                obj = json.loads(t)
                if obj is not v:
                    return Spider._episode_no({"currentEpisode": obj}, fallback)
            except Exception:
                pass
            m = re.search(r"(\d+)", t)
            if m:
                try:
                    x = int(m.group(1))
                    return x if x > 0 else fallback
                except Exception:
                    pass
        title = str((ch or {}).get("title") or (ch or {}).get("name") or "")
        m = re.search(r"(\d+)", title)
        if m:
            try:
                x = int(m.group(1))
                return x if x > 0 else fallback
            except Exception:
                pass
        return fallback

    @staticmethod
    def _as_positive_int(v):
        if isinstance(v, bool) or v is None:
            return 0
        if isinstance(v, (int, float)):
            try:
                n = int(v)
                return n if n > 0 else 0
            except Exception:
                return 0
        if isinstance(v, str):
            m = re.search(r"(\d+)", v)
            if m:
                try:
                    n = int(m.group(1))
                    return n if n > 0 else 0
                except Exception:
                    pass
        if isinstance(v, dict):
            for k in ("value", "count", "total", "episodes", "episodeCount", "totalEpisode"):
                if k in v:
                    n = Spider._as_positive_int(v.get(k))
                    if n:
                        return n
        return 0

    @staticmethod
    def _detail_total(detail_drama, catalog_drama, fallback):
        for obj in (detail_drama or {}, catalog_drama or {}):
            for k in ("episodes", "totalEpisode", "total_episode", "episodeCount", "episode_count", "chapterCount", "chapter_count", "total"):
                n = Spider._as_positive_int(obj.get(k)) if isinstance(obj, dict) else 0
                if n:
                    return n
        return int(fallback or 0)

    @staticmethod
    def _detail_cover(detail_drama, data, drama):
        for obj in (detail_drama or {}, data or {}, drama or {}):
            if not isinstance(obj, dict):
                continue
            for k in ("cover", "coverUrl", "cover_url", "image", "imageUrl", "image_url", "img", "pic", "picture", "poster", "thumb", "thumbnail"):
                v = obj.get(k)
                if isinstance(v, str) and v.strip():
                    return v.strip()
                if isinstance(v, dict):
                    for sk in ("url", "src", "uri"):
                        sv = v.get(sk)
                        if isinstance(sv, str) and sv.strip():
                            return sv.strip()
        return ""

    @staticmethod
    def _cover_is_expired(url, leeway=45):
        if not isinstance(url, str) or 'auth_key=' not in url:
            return False
        try:
            from urllib.parse import parse_qs
            auth = (parse_qs(urlparse(url).query).get('auth_key') or [''])[0]
            deadline = auth.split('-', 1)[0]
            return deadline.isdigit() and int(deadline) <= time.time() + leeway
        except Exception:
            return False

    @staticmethod
    def _cover_from_online_reply(reply):
        if not isinstance(reply, dict):
            return ''
        objs = [reply]
        for field in ('Drama', 'drama', 'data', 'detail', 'info'):
            obj = reply.get(field)
            if isinstance(obj, dict):
                objs.append(obj)
        for obj in objs:
            url = Spider._detail_cover(obj, {}, {}).strip()
            if url and not Spider._cover_is_expired(url):
                if url.startswith('//'):
                    url = 'https:' + url
                return url
        return ''

    def _online_poster(self, drama, cover, src):
        if src != 'huangguoai' or not self._cover_is_expired(cover):
            return cover
        sid = str(drama.get('sourceId') or drama.get('id') or '')
        if not sid:
            return cover
        key = (src, sid)
        cache = getattr(self, '_poster_cache', None)
        if cache is None:
            cache = {}
            self._poster_cache = cache
        cached = cache.get(key)
        if cached and time.time() - cached[0] < 120:
            return cached[1] or cover
        refreshed = ''
        try:
            clean = {k: v for k, v in drama.items() if not k.startswith('__tvbox_')}
            clean['source'] = src
            refreshed = self._cover_from_online_reply(_native.request({'action': 'detail', 'source': src, 'drama': clean}))
        except Exception:
            pass
        cache[key] = (time.time(), refreshed)
        return refreshed or cover

    def _native_vods(self, data, used_source, origin_tid='', origin_page=1):
        items = data.get('items', []) if isinstance(data, dict) else (data or [])
        vods = []
        for item in items:
            if not isinstance(item, dict):
                continue
            d = dict(item)
            src = str(d.get('source') or used_source or '')
            if src.startswith('hongguo-') or src in ('real-drama', 'comic-drama', 'ai-drama', 'hot-drama'):
                src = 'hongguo'
            if src == 'xifan':
                src = 'fanguo'
            d['source'] = src
            d['__tvbox_catalog_live'] = 'v2.5.5'
            if origin_tid:
                d['__tvbox_origin_tid'] = str(origin_tid)
            if origin_page:
                d['__tvbox_origin_page'] = int(origin_page)
            sid = str(d.get('sourceId') or d.get('id') or '')
            if not sid:
                continue
            cover = self._detail_cover(d, {}, {})
            if cover.startswith('http://') and (urlparse(cover).hostname or '') in ('img.novel.wsljf.xyz',):
                cover = 'https://' + cover[len('http://'):]
            if src == 'huangguoai':
                cover = self._online_poster(d, cover, src)
                if cover:
                    d['cover'] = cover
            vods.append({
                'vod_id': 'N.' + _pack(d),
                'vod_name': str(d.get('title') or d.get('name') or sid),
                'vod_pic': cover,
                'vod_remarks': self._native_remark(d) or str(used_source),
            })
        return vods

    def _web_category(self, tid, pg):
        if tid == "hot-drama":
            url = BASE + "/rank/hot-drama"
        else:
            url = BASE + "/category/" + str(tid)
            if int(pg or 1) > 1:
                url += "?" + urlencode({"page": int(pg)})
        html = _http_get(url, referer=BASE + "/")
        items = _parse_cards(html)
        vods = []
        for d in items:
            vods.append({
                "vod_id": "HG." + d["id"],
                "vod_name": d["title"],
                "vod_pic": d.get("pic", ""),
                "vod_remarks": "紅果",
            })
        return vods

    def categoryContent(self, tid, pg, filter, extend):
        try:
            pg = max(1, int(pg or 1))
        except Exception:
            pg = 1
        tid = str(tid)
        site = getattr(self, 'site_source', 'hongguo')
        if tid != site and not tid.startswith(site + ':'):
            return {'list': [], 'page': pg, 'pagecount': pg, 'limit': 0, 'total': 0,
                    'msg': '分類不屬於目前頻道: ' + tid}
        if not self.prefer_native:
            return {'list': [], 'page': pg, 'pagecount': pg, 'limit': 0, 'total': 0,
                    'msg': '需要 Android ARM64 線上原生核心（離線資料只用於分類）'}
        try:
            data, provider = self._native_catalog(tid, pg)
            return self._format_catalog(data, provider, pg, origin_tid=tid)
        except Exception as e:
            return {'list': [], 'page': pg, 'pagecount': pg, 'limit': 0, 'total': 0,
                    'msg': '線上分類取得失敗: ' + str(e)}

    def _format_catalog(self, data, used, pg, offline=False, origin_tid=""):
        if offline:
            return {'list': [], 'page': int(pg), 'pagecount': int(pg), 'limit': 0, 'total': 0,
                    'msg': '離線資料不能作為片單或播放來源'}
        vods = self._native_vods(data, used, origin_tid=origin_tid, origin_page=pg)
        more = bool(data.get('hasMore')) if isinstance(data, dict) else False
        page = int(data.get('page') or pg) if isinstance(data, dict) else int(pg)
        total = int(data.get('total') or data.get('totalCount') or
                    (page + (1 if more else 0)) * max(len(vods), 1)) if isinstance(data, dict) else len(vods)
        return {'list': vods, 'page': page, 'pagecount': page + (1 if more else 0),
                'limit': len(vods), 'total': total, 'source': 'apk-native:' + used}

    @staticmethod
    def _online_intro(*objs):
        bad = ('apk native direct (no decryptionkey)', 'apk native → ffmpeg cenc decrypt',
               'apk native -> ffmpeg cenc decrypt')
        for o in objs:
            if not isinstance(o, dict):
                continue
            for k in ('description', 'desc', 'intro', 'introduction', 'synopsis', 'summary', 'content', 'vod_content'):
                v = o.get(k)
                if isinstance(v, str) and v.strip() and not any(x in v.lower() for x in bad):
                    return v.strip()
        return ''

    @staticmethod
    def _native_chapters(payload, detail):
        for obj in (payload, detail):
            if not isinstance(obj, dict):
                continue
            for key in ('chapters', 'Chapters', 'chapterList', 'chapter_list', 'episodeList', 'episode_list', 'episodes'):
                v = obj.get(key)
                if isinstance(v, list) and any(isinstance(e, dict) for e in v):
                    return v
                if isinstance(v, dict):
                    for nested in ('items', 'list', 'chapters', 'episodes'):
                        items = v.get(nested)
                        if isinstance(items, list) and any(isinstance(e, dict) for e in items):
                            return items
        return []

    @staticmethod
    def _same_online_title(a, b):
        def norm(t):
            return re.sub(r"[\s\W_]+", "", str(t or "")).casefold()
        return bool(norm(a) and norm(a) == norm(b))

    @staticmethod
    def _native_drama_id(d):
        if not isinstance(d, dict):
            return ''
        sid = str(d.get('sourceId') or '')
        if not sid:
            sid = str(d.get('id') or '')
            source = str(d.get('source') or '')
            if sid.startswith(source + ':'):
                sid = sid[len(source) + 1:]
        return sid.split('@', 1)[0]

    @staticmethod
    def _chapter_has_identity(ch):
        if not isinstance(ch, dict):
            return False
        return any(ch.get(k) not in (None, '', [], {}) for k in
                   ('id', 'sourceId', 'chapterId', 'chapter_id', 'videoUrl', 'video_url',
                    'playUrl', 'play_url', 'url', 'currentEpisode', 'episodeNo', 'episodeIndex'))

    def _online_detail(self, drama):
        if not isinstance(drama, dict):
            raise RuntimeError('線上 Drama 非物件')
        source = str(drama.get('source') or self._OFFLINE_ALIASES.get(self.site_source, self.site_source))
        sid = self._native_drama_id(drama)
        if not sid:
            raise RuntimeError('原生 catalog 未提供影片來源 ID')
        origin_tid = str(drama.get('__tvbox_origin_tid') or '')
        try:
            origin_page = max(1, min(999, int(drama.get('__tvbox_origin_page') or 1)))
        except (ValueError, TypeError):
            origin_page = 1
        original = {k: v for k, v in drama.items() if not k.startswith('__tvbox_')}
        original['source'] = source
        errors = []
        attempted = set()

        def chapters_from_online(payload):
            if not isinstance(payload, dict):
                return [], {}, {}
            inner = payload.get('data')
            if isinstance(inner, dict) and not self._native_chapters(payload, payload.get('Drama') or payload.get('drama') or {}):
                payload = inner
            meta = payload.get('Drama') or payload.get('drama') or {}
            if not isinstance(meta, dict):
                meta = {}
            chapters = [ch for ch in self._native_chapters(payload, meta) if self._chapter_has_identity(ch)]
            return chapters, meta, payload

        def attempt(label, obj):
            obj = {k: v for k, v in obj.items() if not k.startswith('__tvbox_')}
            obj['source'] = source
            marker = (str(obj.get('sourceId') or ''), str(obj.get('id') or ''))
            if marker in attempted:
                return None
            attempted.add(marker)
            try:
                payload = _native.request({'action': 'detail', 'source': source, 'drama': obj})
                chapters, meta, payload = chapters_from_online(payload)
                if chapters:
                    return payload, obj, meta, chapters
                keys = ','.join(sorted(map(str, payload.keys()))[:10]) if isinstance(payload, dict) else type(payload).__name__
                errors.append('%s：detail 成功但章節為空 (欄位:%s)' % (label, keys))
            except Exception as e:
                errors.append('%s：%s' % (label, str(e)[:155]))
            return None

        result = attempt('原始線上片單', original)
        if result:
            return result
        raw = str(original.get('sourceId') or '')
        if raw and '@' in raw and source == 'xingguo':
            obj = dict(original)
            obj['sourceId'] = sid
            obj['id'] = source + ':' + sid
            result = attempt('星果數字影片 ID', obj)
            if result:
                return result
        if raw and str(original.get('id') or '') not in (raw, source + ':' + raw):
            obj = dict(original)
            obj['id'] = source + ':' + raw
            result = attempt('來源前綴 ID', obj)
            if result:
                return result

        lookups = []
        if origin_tid and (origin_tid == self.site_source or origin_tid.startswith(self.site_source + ':')):
            category = origin_tid.split(':', 1)[1] if ':' in origin_tid else ''
            if not category.startswith('topic:'):
                req = {'action': 'catalog', 'source': source, 'page': origin_page}
                if category:
                    req['category'] = category
                lookups.append(('原分類線上片單', req))
        if not lookups:
            lookups.append(('線上首頁片單', {'action': 'catalog', 'source': source, 'page': 1}))
        title = str(original.get('title') or original.get('name') or '').strip()
        if source == 'hongguo' and title:
            lookups.append(('紅果線上片名搜尋', {'action': 'catalog', 'source': source, 'page': 1, 'query': title}))
        lookupseen = set()
        for label, req in lookups:
            reqmark = (str(req.get('category') or ''), str(req.get('query') or ''), int(req['page']))
            if reqmark in lookupseen:
                continue
            lookupseen.add(reqmark)
            try:
                fetched = _native.request(req)
                if isinstance(fetched, list):
                    items = fetched
                elif isinstance(fetched, dict):
                    items = fetched.get('items') or fetched.get('list') or []
                else:
                    items = []
                same = []
                same_title = 0
                foreign = 0
                for r in items:
                    if not isinstance(r, dict):
                        continue
                    if str(r.get('source') or source) != source:
                        foreign += 1
                        continue
                    if title and self._same_online_title(title, r.get('title') or r.get('name')):
                        same_title += 1
                    if self._native_drama_id(r) == sid:
                        same.append(r)
                errors.append('%s：%d 筆，原 ID 相符 %d，片名相同 %d，來源不同 %d' %
                              (label, len(items), len(same), same_title, foreign))
                for r in same[:2]:
                    r = dict(r)
                    r['source'] = source
                    ch, meta, payload = chapters_from_online(r)
                    if ch:
                        return {'Drama': r, 'chapters': ch}, r, r, ch
                    merged = dict(original)
                    merged.update({k: v for k, v in r.items() if v is not None})
                    res = attempt(label + '更新後詳情', merged)
                    if res:
                        return res
            except Exception as e:
                errors.append('%s：%s' % (label, str(e)[:155]))
        if source != 'hongguo':
            errors.append('片名搜尋未重試：此來源的 native catalog(query) 尚未證實會呼叫真正搜尋接口')

        chapters, meta, payload = chapters_from_online(original)
        if chapters:
            return {'Drama': original, 'chapters': chapters}, original, original, chapters
        raise RuntimeError('線上來源 %s 詳情未取得有效章節 (id=%s)。\n%s' %
                           (source, sid[:44], '\n'.join(errors)[:1500]))

    def detailContent(self, array):
        vid = array[0] if isinstance(array, (list, tuple)) else array
        s = str(vid)
        if s.startswith('N.'):
            if not self.prefer_native:
                return {'list': [{'vod_id': s, 'vod_name': '需 Android ARM64 原生核心',
                                  'vod_play_from': '原生抽出', 'vod_play_url': '',
                                  'vod_content': '離線資料僅提供分類，不提供詳情或播放。'}]}
            drama = {}
            try:
                drama = _unpack(s[2:])
                if not isinstance(drama, dict):
                    raise ValueError('Drama payload 格式不正確')
                if drama.pop('__tvbox_catalog_live', None) not in ('v2.5.1', 'v2.5.2', 'v2.5.3', 'v2.5.4', 'v2.5.5'):
                    raise ValueError('舊版離線影片 ID 已停用，請回分類重新取得線上片單')
                source = str(drama.get('source') or '')
                if not source:
                    raise ValueError('缺少線上 source')
                key = source + ':' + str(drama.get('sourceId') or drama.get('id') or '')
                cached = self._detail_cache.get(key)
                if cached and time.time() - cached[0] < 300:
                    data, actual, metadata, chapters = cached[1]
                else:
                    data, actual, metadata, chapters = self._online_detail(drama)
                    self._detail_cache[key] = (time.time(), (data, actual, metadata, chapters))
                plays = []
                for i, ch in enumerate(chapters):
                    if not isinstance(ch, dict):
                        continue
                    epno = self._episode_no(ch, i + 1)
                    title = str(ch.get('title') or ch.get('name') or '').strip()
                    if source == 'niuguo':
                        title = '第%d集' % (i + 1)
                    elif not title or title.lower() == 'unknown':
                        title = '第%d集' % epno
                    title = title.replace('$', '＄').replace('#', '＃')
                    info = {'d': actual, 'c': ch, 'i': i}
                    plays.append((title, info))
                if not plays:
                    raise RuntimeError('線上 detail 沒有可用集數')
                route_count = 10
                for obj in (metadata, data, actual):
                    if isinstance(obj, dict) and obj.get('routeCount') is not None:
                        try:
                            route_count = max(1, min(10, int(obj['routeCount'])))
                        except (ValueError, TypeError):
                            pass
                        break
                line_names = ['線路%d' % i for i in range(1, route_count + 1)]
                line_episodes = []
                for route_index in range(route_count):
                    line_episodes.append('#'.join(title + '$NP.' + _pack(dict(info, r=route_index))
                                                  for title, info in plays))
                title = str(metadata.get('title') or metadata.get('name') or data.get('title') or
                            data.get('name') or drama.get('title') or '短劇')
                total = self._detail_total(metadata, actual, len(plays))
                return {'list': [{'vod_id': s, 'vod_name': title,
                                  'vod_pic': self._detail_cover(metadata, data, actual),
                                  'vod_content': self._online_intro(metadata, data, actual),
                                  'vod_remarks': '共%d集' % (max(total, len(plays))),
                                  'vod_play_from': '$$$'.join(line_names),
                                  'vod_play_url': '$$$'.join(line_episodes)}]}
            except Exception as e:
                src = str(drama.get('source') or '') if isinstance(drama, dict) else ''
                did = str(drama.get('sourceId') or drama.get('id') or '') if isinstance(drama, dict) else ''
                return {'list': [{'vod_id': s, 'vod_name': '線上原生詳情失敗',
                                  'vod_pic': self._detail_cover(drama, {}, {}),
                                  'vod_content': '原生 detail: %s\nsource=%s\nid=%s\n說明：僅使用線上原生片單及章節，未使用離線影片。' % (e, src, did[:100]),
                                  'vod_play_from': '原生抽出-無可用章節', 'vod_play_url': ''}]}
        if s.startswith('HG.'):
            try:
                sid = s[3:]
                page = BASE + '/detail?' + urlencode({'series_id': sid})
                info = _detail_info(_http_get(page, referer=BASE + '/'), sid)
                plays = []
                for i, ep in enumerate(info.get('episodes') or []):
                    num = ep.get('num') or i + 1
                    plays.append('第%d集$HGP.%s' % (num, _pack({'s': sid, 'e': ep.get('eid', ''),
                                                                'p': ep.get('page', ''), 'a': 0})))
                return {'list': [{'vod_id': s, 'vod_name': info['title'], 'vod_pic': info['pic'],
                                  'vod_content': info['desc'], 'vod_remarks': '共%d集' % len(plays),
                                  'vod_play_from': '紅果Web', 'vod_play_url': '#'.join(plays)}]}
            except Exception as e:
                return {'list': [{'vod_id': s, 'vod_name': '紅果Web詳情失敗', 'vod_content': str(e),
                                  'vod_play_url': ''}]}
        return {'list': [{'vod_id': s, 'vod_name': '無效影片 ID',
                          'vod_content': '需要線上原生 catalog 回傳的影片 ID，請重新開啟分類。',
                          'vod_play_url': ''}]}

    def searchContent(self, key, quick, pg="1"):
        try:
            pg = int(pg or 1)
        except Exception:
            pg = 1
        keyword = str(key or "").strip()
        if not keyword:
            return {"list": []}

        if self.prefer_native:
            try:
                data, used = self._native_catalog(getattr(self, "site_source", "hongguo"), pg, query=keyword)
                vods = self._native_vods(data, used)
                if vods:
                    more = bool(data.get("hasMore")) if isinstance(data, dict) else False
                    return {"list": vods, "page": pg, "pagecount": pg + (1 if more else 0),
                            "limit": len(vods), "total": len(vods), "source": "apk-native:" + used}
            except Exception:
                if self.native_only:
                    return {"list": [], "page": pg, "pagecount": pg, "limit": 0, "total": 0,
                            "msg": "APK 原生搜尋失敗"}

        if self.native_only:
            return {"list": [], "page": pg, "pagecount": pg, "limit": 0,
                    "total": 0, "msg": "線上原生搜尋無結果（不使用離線片庫）"}

        candidates = [
            BASE + "/search/?" + urlencode({"keyword": keyword}),
            BASE + "/search/?" + urlencode({"query": keyword}),
            BASE + "/search/?" + urlencode({"wd": keyword}),
            BASE + "/search/" + quote(keyword),
        ]
        last = None
        for u in candidates:
            try:
                html = _http_get(u, referer=BASE + "/")
                cards = _parse_cards(html)
                if cards:
                    vods = [{"vod_id": "HG." + d["id"], "vod_name": d["title"], "vod_pic": d.get("pic", ""), "vod_remarks": "紅果"} for d in cards]
                    return {"list": vods, "page": pg, "pagecount": pg + 1, "limit": len(vods), "total": len(vods)}
            except Exception as e:
                last = e
        return {"list": [], "page": pg, "pagecount": pg, "limit": 0, "total": 0, "msg": "搜尋無結果" + ((": %s" % last) if last else "")}

    def playerContent(self, flag, id, vipFlags):
        sid = str(id or "")
        if sid.startswith("NP."):
            if not self.prefer_native:
                return {"parse": 1, "url": "", "header": {},
                        "msg": "此播放 ID 需要 Android ARM64 APK 原生核心"}
            try:
                p = _unpack(sid[3:])
                selected = p.get('r', 0)
                try:
                    route_index = int(selected)
                except (TypeError, ValueError):
                    route_index = 0
                if route_index < 0 or route_index > 9:
                    raise ValueError('不支援的原生線路編號: %s' % selected)
                if str(flag or '').startswith('線路'):
                    try:
                        flag_route = int(str(flag)[2:]) - 1
                        if 0 <= flag_route <= 9:
                            route_index = flag_route
                    except ValueError:
                        pass
                req = {
                    "action": "resolve",
                    "drama": p.get("d") or {},
                    "chapter": p.get("c") or {},
                    "index": int(p.get("i") or 0),
                    "quality": 0,
                    "route": route_index,
                    "sequence": _native.next_sequence(),
                }
                d = p.get("d") or {}
                if d.get("source"):
                    req["source"] = d.get("source")
                started = time.time()
                try:
                    data = _native.request(req) or {}
                except Exception as first_e:
                    if "context canceled" in str(first_e).lower() and time.time() - started < 2.0:
                        req["sequence"] = _native.next_sequence()
                        data = _native.request(req) or {}
                    else:
                        raise
                u = data.get("url") or (p.get("c") or {}).get("videoUrl") or ""
                if u:
                    try:
                        native_count = data.get('routeCount')
                        if native_count is not None and route_index >= int(native_count):
                            return {'parse': 1, 'url': '', 'header': {},
                                    'msg': '此影片原生僅有 %s 條線路；線路%s 不支援' %
                                           (native_count, route_index + 1)}
                    except (TypeError, ValueError):
                        pass
                    hdr = data.get("headers") or {}
                    key = data.get("decryptionKey") or data.get("key") or ""
                    fmt = ""
                    probe = {}
                    key_info = {"ready": False, "key_len": len(str(key or "").strip()), "kid_hex": "", "kid_source": "", "media_probe": {}}
                    if self.plan_diag:
                        fmt, probe = _probe_native_media(u, hdr, timeout=3)
                        key_info = _native_clear_key_info(data, u, hdr)
                    key_info = _native_clear_key_info(data, u, hdr)
                    key = data.get("decryptionKey") or data.get("key") or ""
                    if self.plan_diag:
                        host = urlparse(str(u)).netloc
                        keys = ",".join(sorted([str(k) for k in data.keys()])) if isinstance(data, dict) else type(data).__name__
                        mp = key_info.get("media_probe") or {}
                        pssh_txt = ";".join(mp.get("pssh") or []) or "<none>"
                        scheme_txt = ",".join(mp.get("schemes") or []) or "<none>"
                        ff = _ffmpeg.status()
                        msg = ("NativePlan host=%s format=%s local=%s keyLen=%d "
                               "kid=%s kidSrc=%s drmReady=%s mp4Bytes=%s mp4First=%s "
                               "scheme=%s pssh=%s ffmpegReady=%s ffmpegErr=%s "
                               "ct=%s fields=%s probe=%s") % (
                            host, fmt or "<auto>", data.get("local"), key_info.get("key_len", 0),
                            (key_info.get("kid_hex") or "<none>"), key_info.get("kid_source") or "<none>",
                            key_info.get("ready"), mp.get("bytes", 0), mp.get("first") or "",
                            scheme_txt, pssh_txt, ff.get("ok"), ff.get("error") or "<none>",
                            probe.get("contentType") or "", keys,
                            mp.get("error") or probe.get("error") or "OK")
                        return {"parse": 1, "url": "", "header": {}, "msg": msg}

                    if not key:
                        if not fmt:
                            fmt, probe = _probe_native_media(u, hdr, timeout=3)
                        out = {"parse": 0, "url": u, "header": hdr}
                        if fmt:
                            out["format"] = fmt
                        return out

                    clear_path, cache_hit, rc = _ffmpeg.decrypt_to_mp4(u, key, hdr, p, data)
                    out = {
                        "parse": 0,
                        "url": "file://" + clear_path,
                        "header": {},
                        "format": "video/mp4",
                    }
                    if data.get("quality") is not None:
                        out["quality"] = data.get("quality")
                    if data.get("routeCount") is not None:
                        out["routeCount"] = data.get("routeCount")
                        try:
                            if route_index >= int(data['routeCount']):
                                return {'parse': 1, 'url': '', 'header': {},
                                        'msg': '此影片原生僅有 %s 條線路；線路%s 不支援' %
                                               (data['routeCount'], route_index + 1)}
                        except (ValueError, TypeError):
                            pass
                    return out
                return {"parse": 1, "url": "", "header": {}, "msg": "APK 原生 resolve 未取得 URL"}
            except Exception as e:
                seq = req.get("sequence") if "req" in locals() and isinstance(req, dict) else "?"
                line_name = '線路%d' % (route_index + 1) if 'route_index' in locals() else str(flag or '原生線路')
                return {"parse": 1, "url": "", "header": {}, "msg": "%s APK 原生 resolve 錯誤: %s (sequence=%s)" % (line_name, e, seq)}

        if sid.startswith("http://") or sid.startswith("https://"):
            return {"parse": 0 if self.isVideoFormat(sid) else 1, "url": sid, "header": {"User-Agent": UA}}

        try:
            if not sid.startswith("HGP."):
                raise RuntimeError("無效播放 id")
            p = _unpack(sid[4:])
            series_id = str(p.get("s") or "")
            episode_id = str(p.get("e") or "")
            accessible = int(p.get("a") or 0)
            page = p.get("p") or (BASE + "/player/" + series_id + (("/" + episode_id) if episode_id else ""))
            html = _http_get(page, referer=BASE + "/detail?series_id=" + series_id)
            media = _extract_media_from_html(html)
            if not media:
                media = _fallback_play_api(series_id, episode_id)
            headers = {"User-Agent": UA, "Referer": page}
            if media:
                return {"parse": 0, "url": media, "header": headers}
            return {"parse": 1, "url": page, "header": headers, "msg": "此集頁面未提供 main_url；可能是官網尚未開放，交由播放器解析"}
        except Exception as e:
            return {"parse": 1, "url": "", "header": {"User-Agent": UA}, "msg": "播放解析失敗: %s" % e}