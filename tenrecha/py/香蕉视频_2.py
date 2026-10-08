# -*- coding: utf-8 -*-
# 香蕉视频 (xxoo473.org) Python Spider
#
# 实测边界 (2026-08-05):
#   【免费视频】/api/vod/reqplay/{id} -> data.httpurl 直链 m3u8，游客可播
#   【VIP 视频】reqplay 返回 retcode:5 VIP独享 -> 用 preview_url 上溯:
#       preview m3u8 的 #EXT-X-KEY URI 形如
#       https://{cdn}/{date}/{token}/{bitrate}kb/hls/key.key
#       推导 master: 取 pathname 前两段 -> https://{cdn}/{date}/{token}/index.m3u8
#       实测 master/media/key 全部匿名 200（预览流泄漏模式）
#   【分类】/api/init -> globalData.hotcategories (12个, url 为 listing-{10参数})
#   【列表】/api/v2/vod/listing-{9参数}-{page}  (无 .html 后缀，带后缀会 307 到前端)
#   【搜索】/api/search?wd=&page=&free=1
#   【首页】/api/vod/latest
#   认证头: X-Cookie-Auth 来自 init 的 globalData.xxx_api_auth (明文 hex)
#
# extend 参数可覆盖站点域名（域名会变）。

import json
import re
from urllib.parse import quote

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        pass

try:
    import requests
except ImportError:
    requests = None

DEFAULT_HOST = "https://h5.xxoo473.org"
UA = (
    "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
)


class Spider(BaseSpider):
    def init(self, extend=""):
        self.host = (extend or DEFAULT_HOST).strip().rstrip("/")
        self.session = requests.Session() if requests else None
        if self.session:
            self.session.headers = {
                "User-Agent": UA,
                "Accept": "application/json",
                "x-channel": "h5",
                "x-system": "H5",
                "x-version": "1.0.0",
            }
        self._token = None
        self._classes = None

    def __init__(self):
        try:
            super().__init__()
        except Exception:
            pass
        self.init()

    def getName(self):
        return "香蕉视频"

    # ─────────────────────────── 基础 ───────────────────────────

    def _fetch_json(self, path, params=None):
        if not self.session:
            return {}
        self._ensure_token()
        try:
            r = self.session.get(self.host + path, params=params, timeout=15)
            if r.status_code != 200:
                return {}
            return r.json()
        except Exception:
            return {}

    def _ensure_token(self):
        if self._token is not None:
            return
        try:
            r = self.session.get(self.host + "/api/init", timeout=15)
            d = r.json()
            gd = (d.get("data") or {}).get("globalData") or {}
            self._token = gd.get("xxx_api_auth") or ""
            if self._token:
                self.session.headers["X-Cookie-Auth"] = self._token
        except Exception:
            self._token = ""

    def _get_classes(self):
        if self._classes is not None:
            return self._classes
        d = self._fetch_json("/api/init")
        cats = ((d.get("data") or {}).get("globalData") or {}).get("hotcategories") or []
        classes = []
        for c in cats:
            m = re.search(r"vod/listing-([0-9-]+)\.html", str(c.get("url") or ""))
            if not m:
                continue
            params = m.group(1)  # 10 段: ...-{page}，去掉最后一段做 tid
            tid = params.rsplit("-", 1)[0]
            classes.append({"type_id": tid, "type_name": c.get("catename", "")})
        self._classes = classes
        return classes

    def _rows_to_vods(self, rows):
        out = []
        for r in rows or []:
            out.append({
                "vod_id": str(r.get("vodid") or ""),
                "vod_name": r.get("title") or "",
                "vod_pic": r.get("coverpic") or "",
                "vod_remarks": self._remark(r),
            })
        return out

    @staticmethod
    def _remark(r):
        parts = []
        if r.get("duration"):
            parts.append(r.get("duration"))
        if r.get("yearname"):
            parts.append(r.get("yearname"))
        if r.get("definition") and str(r.get("definition")) not in ("0", ""):
            parts.append("高清")
        if str(r.get("isvip")) not in ("0", ""):
            parts.append("VIP")
        return " ".join(parts)

    # ─────────────────────────── TVBox 契约 ───────────────────────────

    def homeContent(self, filter=False):
        classes = self._get_classes()
        d = self._fetch_json("/api/vod/latest")
        rows = ((d.get("data") or {}).get("vodrows")) or []
        vods = self._rows_to_vods(rows)
        return {"class": classes, "list": vods}

    def homeVideoContent(self):
        d = self._fetch_json("/api/vod/latest")
        rows = ((d.get("data") or {}).get("vodrows")) or []
        return {"list": self._rows_to_vods(rows)}

    def categoryContent(self, tid, pg=1, filter=False, extend=None):
        # tid = "cateid-areaid-yearid-definition-duration-freetype-mosaic-langvoice-orderby"
        d = self._fetch_json("/api/v2/vod/listing-%s-%s" % (tid, pg))
        rows = ((d.get("data") or {}).get("vodrows")) or []
        return {"list": self._rows_to_vods(rows), "page": pg, "pagecount": 9999}

    def searchContent(self, key, quick=False, pg="1"):
        d = self._fetch_json("/api/search", {"wd": key, "page": pg, "free": 1})
        rows = ((d.get("data") or {}).get("vodrows")) or []
        return {"list": self._rows_to_vods(rows)}

    def detailContent(self, ids):
        vid = str(ids[0] if isinstance(ids, list) else ids)
        d = self._fetch_json("/api/vod/show/" + vid)
        row = ((d.get("data") or {}).get("vodrow")) or {}
        if not row:
            return {"list": []}
        vod = {
            "vod_id": vid,
            "vod_name": row.get("title") or "",
            "vod_pic": row.get("coverpic") or "",
            "vod_content": row.get("intro") or "",
            "vod_year": row.get("yearname") or "",
            "vod_area": row.get("areaname") or "",
            "vod_actor": ", ".join(
                t.get("tagname", "") for t in (row.get("actor_tags") or [])
                if t.get("tagtype") == "0"
            ),
            "vod_play_from": "香蕉",
            "vod_play_url": "香蕉$%s" % vid,
        }
        return {"list": [vod]}

    def playerContent(self, flag, id, vipFlags=None):
        vid = str(id)
        # 1) 免费路径: reqplay
        d = self._fetch_json("/api/vod/reqplay/" + vid)
        if d.get("retcode") == 0:
            httpurl = ((d.get("data") or {}).get("httpurl")) or ""
            if httpurl:
                return {"parse": 0, "playUrl": httpurl, "header": {"User-Agent": UA}}
        # 2) VIP 路径: preview 上溯
        leaked = self._escalate_preview(vid)
        if leaked:
            return {"parse": 0, "playUrl": leaked, "header": {"User-Agent": UA}}
        return {"parse": 0, "playUrl": ""}

    def _escalate_preview(self, vid):
        """preview m3u8 -> #EXT-X-KEY URI -> master 推导 -> 验证"""
        d = self._fetch_json("/api/vod/show/" + vid)
        row = ((d.get("data") or {}).get("vodrow")) or {}
        preview = row.get("preview_url") or ""
        if not preview:
            return None
        try:
            r = self.session.get(preview, timeout=15)
            if r.status_code != 200:
                return None
            text = r.text
            m = re.search(r'#EXT-X-KEY:[^\n]*URI="([^"]+)"', text, re.I)
            if not m:
                return None
            key_uri = m.group(1)
            if key_uri.startswith("http"):
                abs_key = key_uri
            else:
                from urllib.parse import urljoin
                abs_key = urljoin(preview, key_uri)
            u = abs_key.split("/")
            # https://{cdn}/{d1}/{d2}/... -> {d1}/{d2}/index.m3u8
            if len(u) >= 6:
                master = "/".join(u[:3]) + "/" + u[3] + "/" + u[4] + "/index.m3u8"
            else:
                master = re.sub(r"/\d+kb/hls/key\.key.*$", "/index.m3u8", abs_key, flags=re.I)
                master = re.sub(r"/hls/key\.key.*$", "/index.m3u8", master, flags=re.I)
                master = re.sub(r"/key\.key.*$", "/index.m3u8", master, flags=re.I)
            mr = self.session.get(master, timeout=15)
            if (
                mr.status_code == 200
                and "#EXTM3U" in mr.text
                and re.search(r"EXT-X-STREAM-INF|#EXTINF", mr.text, re.I)
            ):
                return master
        except Exception:
            pass
        return None
