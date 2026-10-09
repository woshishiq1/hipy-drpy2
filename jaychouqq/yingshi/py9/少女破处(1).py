# -*- coding: utf-8 -*-
import json
import re
import ssl
import html as html_lib
import urllib.request
import urllib.parse
import gzip
import zlib

try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider(object):
        pass


class Spider(BaseSpider):

    FALLBACK_CLASSES = [
        ("1", "少女自拍"), ("2", "国产乱伦"), ("3", "人妻熟女"), ("4", "探花偷拍"),
        ("5", "制服丝袜"), ("6", "巨乳美胸"), ("7", "主播直播"), ("8", "无码中字"),
        ("9", "欧美高清"), ("10", "三级伦理"), ("11", "成人动漫"), ("12", "麻豆传媒"),
        ("13", "天美传媒"), ("14", "蜜桃传媒"), ("15", "精东影业"), ("16", "皇家华人"),
        ("17", "星空传媒"), ("18", "乐播传媒"), ("19", "乌鸦传媒"), ("20", "大象传媒")
    ]

    def __init__(self):
        super(Spider, self).__init__()
        self.host = "https://83w43wdlty.md-md22.top"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
            "Referer": "https://83w43wdlty.md-md22.top/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "close"
        }

    def getName(self):
        return "少女破处"

    def init(self, extend=""):
        pass

    def destroy(self):
        pass

    def _get(self, url):
        try:
            ctx = ssl._create_unverified_context()
        except Exception:
            ctx = None

        req = urllib.request.Request(url, headers=self.headers)
        for _ in range(3):
            try:
                if ctx:
                    resp = urllib.request.urlopen(req, context=ctx, timeout=8)
                else:
                    resp = urllib.request.urlopen(req, timeout=8)

                raw_data = resp.read()
                encoding = resp.headers.get("Content-Encoding", "").lower()
                if "gzip" in encoding:
                    try:
                        return gzip.decompress(raw_data).decode("utf-8", "ignore")
                    except Exception:
                        return raw_data.decode("utf-8", "ignore")
                elif "deflate" in encoding:
                    try:
                        return zlib.decompress(raw_data).decode("utf-8", "ignore")
                    except Exception:
                        return raw_data.decode("utf-8", "ignore")
                else:
                    return raw_data.decode("utf-8", "ignore")
            except Exception:
                continue
        return ""

    def _decode(self, h):
        if not h:
            return ""
        m = re.search(r'var\s+Words\s*=\s*["\']([^"\']+)["\']', h)
        if not m:
            return h
        raw_words = m.group(1)
        d = re.sub(r'%u([0-9a-fA-F]{4})', lambda x: chr(int(x.group(1), 16)), raw_words)
        return urllib.parse.unquote(d)

    def _abs(self, u):
        if not u:
            return ""
        if u.startswith("http://") or u.startswith("https://"):
            return u
        if u.startswith("//"):
            return "https:" + u
        if u.startswith("/"):
            return self.host + u
        return self.host + "/" + u

    def _cards(self, h):
        lst = []
        seen = set()
        for m in re.finditer(r'<article>(.*?)</article>', h, re.S):
            block = m.group(1)
            um = re.search(r'href=["\'](/detail/\?\d+\.html)["\']', block)
            if not um:
                continue
            vid_m = re.search(r'\?(\d+)\.html', um.group(1))
            if not vid_m:
                continue
            vid = vid_m.group(1)
            if vid in seen:
                continue
            seen.add(vid)

            nm = re.search(r'<cite>([^<]+)</cite>', block)
            if not nm:
                nm = re.search(r'alt=["\']([^"\']+)["\']', block)
            name = html_lib.unescape(nm.group(1).strip()) if nm else ""
            if not name:
                continue

            pm = re.search(r'data-src=["\']([^"\']+)["\']', block)
            if not pm:
                pm = re.search(r'<img[^>]*src=["\']([^"\']+)["\']', block)
            pic = self._abs(pm.group(1)) if pm else ""

            duration_m = re.search(r'<span[^>]*class=["\'][^"\']*(?:duration|time|tag)[^"\']*["\'][^>]*>([^<]+)</span>', block, re.I)
            remarks = "蝴蝶影视 | %s" % duration_m.group(1).strip() if duration_m and duration_m.group(1).strip() else "蝴蝶影视 | 高清"

            lst.append({
                "vod_id": vid,
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": remarks,
                "style": {"type": "rect", "ratio": 1.78}
            })
        return lst

    def homeContent(self, filter):
        cats = []
        seen = set()
        try:
            h = self._decode(self._get(self.host + "/"))
            if h:
                for u, cid, n in re.findall(r'href=["\'](/list/\?(\d+)\.html)["\'][^>]*>([^<]{1,12})</a>', h):
                    name = n.strip()
                    if cid in seen or not name or "更多" in name:
                        continue
                    seen.add(cid)
                    cats.append({"type_id": str(cid), "type_name": html_lib.unescape(name)})
        except Exception:
            pass

        if not cats:
            cats = [{"type_id": str(t), "type_name": str(n)} for t, n in self.FALLBACK_CLASSES]

        return {
            "class": cats,
            "filters": {}
        }

    def homeVideoContent(self):
        return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page_num = int(pg) if str(pg).isdigit() else 1
            if page_num <= 1:
                url = "%s/list/?%s.html" % (self.host, tid)
            else:
                url = "%s/list/?%s-%d.html" % (self.host, tid, page_num)
            h = self._decode(self._get(url))
            lst = self._cards(h)
            return {
                "list": lst,
                "page": page_num,
                "pagecount": page_num + 1 if len(lst) >= 12 else page_num,
                "limit": 20,
                "total": 9999
            }
        except Exception:
            return {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}

    def detailContent(self, ids):
        try:
            vid = ids[0] if isinstance(ids, list) else ids
            url = "%s/detail/?%s.html" % (self.host, vid)
            raw_h = self._get(url)
            h = self._decode(raw_h)

            t = re.search(r'<h1[^>]*>([^<]+)</h1>', h)
            name = html_lib.unescape(t.group(1).strip())[:60] if t else "视频 %s" % vid
            pm = re.search(r'data-src=["\']([^"\']+)["\']', h)
            if not pm:
                pm = re.search(r'<img[^>]*src=["\']([^"\']+)["\']', h)
            pic = self._abs(pm.group(1)) if pm else ""

            episodes = []
            play_matches = re.findall(r'<a[^>]+href=["\'](/play/\?[^"\']+|/video/\?[^"\']+)["\'][^>]*>([^<]*)</a>', h, re.I)
            if play_matches:
                for purl, ptitle in play_matches:
                    ep_title = ptitle.strip() if ptitle.strip() else "正片"
                    episodes.append("%s$%s" % (ep_title, self._abs(purl)))
            else:
                single_play_m = re.search(r'<a[^>]+href=["\'](/play/\?[^"\']+|/video/\?[^"\']+)["\']', h, re.I)
                if single_play_m:
                    episodes.append("高清正片$%s" % self._abs(single_play_m.group(1)))
                else:
                    episodes.append("高清正片$%s/video/?%s-0-0.html" % (self.host, vid))

            vod = {
                "vod_id": vid,
                "vod_name": name,
                "vod_pic": pic,
                "type_name": "蝴蝶专区",
                "vod_year": "2026",
                "vod_area": "华语",
                "vod_remarks": "蝴蝶影视 | 高清原画",
                "vod_actor": "🦋 TG群: @tvshare23",
                "vod_director": "🦋 蝴蝶影视",
                "vod_content": "🦋 蝴蝶影视 | TG群: @tvshare23\n蝴蝶影视官方正版资源，关注TG群获取最新动态与防失联地址。",
                "vod_play_from": "蝴蝶秒播云",
                "vod_play_url": "#".join(episodes)
            }
            return {"list": [vod]}
        except Exception:
            return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        try:
            url = "%s/search.php?searchword=%s" % (self.host, urllib.parse.quote(key, safe=""))
            h = self._decode(self._get(url))
            return {"list": self._cards(h)}
        except Exception:
            return {"list": []}

    def _decode_obfuscated_js(self, h):
        try:
            scripts = re.findall(r'<script(?![^>]*src=)[^>]*>(.*?)</script>', h, re.S)
            for s in scripts:
                s = s.strip()
                if len(s) < 100 or "var b=" not in s:
                    continue
                m = re.search(r'var\s+b\s*=\s*(\{.*?\});', s, re.S)
                if not m:
                    continue
                pairs = re.findall(r'(?:"([^"]+)"|([A-Za-z0-9_]+))\s*:\s*"((?:[^"\\]|\\.)*)"', m.group(1))
                mp = {(qk if qk else bk): v for qk, bk, v in pairs}
                em = re.search(r'var\s+b\s*=\s*a\(`([^`]+)`', s)
                if not em:
                    continue
                dec = "".join(mp.get(c, c) for c in em.group(1))
                mm = re.search(r'https?://[^\s"\'<>]+?\.(?:m3u8|mp4)[^\s"\'<>]*', dec)
                if mm:
                    return mm.group(0)
        except Exception:
            pass
        return ""

    def _parse_player_json(self, h, varname):
        idx = h.find("var %s=" % varname)
        if idx < 0:
            return None
        seg = h[idx:idx + 12000]
        start = seg.find("{")
        if start < 0:
            return None
        depth = 0
        for i, c in enumerate(seg[start:], start):
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(seg[start:i + 1])
                    except Exception:
                        return None
        return None

    def _decode_url(self, url, encrypt):
        if not url:
            return ""
        try:
            if encrypt == 1:
                return urllib.parse.unquote(url)
            if encrypt == 2:
                import base64
                return urllib.parse.unquote(base64.b64decode(urllib.parse.unquote(url)).decode("utf-8", "ignore"))
        except Exception:
            pass
        return url

    def _extract_play_url(self, h):
        for varname in ["player_aaaa", "player_data"]:
            data = self._parse_player_json(h, varname)
            if data and data.get("url"):
                u = self._decode_url(data["url"], data.get("encrypt", 0))
                if u:
                    return u

        m = re.search(r'MacPlayer\.PlayUrl\s*=\s*["\']([^"\']+)["\']', h)
        if m and m.group(1).strip():
            return m.group(1).strip()

        m = re.search(r"var\s+dp_video_url\s*=\s*['\"]([^'\"]+)['\"]", h)
        if m:
            try:
                import base64
                return base64.b64decode(m.group(1)).decode("utf-8", "ignore")
            except Exception:
                pass

        m = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', h)
        if m:
            return m.group(1)

        for m in re.finditer(r'"url"\s*:\s*"([^"]+)"', h):
            u = m.group(1).replace("\\/", "/").replace("\\", "")
            if re.search(r'\.(?:m3u8|mp4)(\?|$)', u) and u.startswith("http"):
                return u

        u = self._decode_obfuscated_js(h)
        if u:
            return u
        return ""

    def playerContent(self, flag, id, vipFlags):
        try:
            raw_h = self._get(id)
            h = self._decode(raw_h)
            url = self._extract_play_url(h)
            if url:
                if url.startswith("/"):
                    url = self._abs(url)
                return {
                    "parse": 0,
                    "playUrl": "",
                    "url": url,
                    "header": json.dumps({"User-Agent": "Mozilla/5.0", "Referer": id})
                }
            return {"parse": 1, "playUrl": "", "url": id}
        except Exception:
            return {"parse": 1, "playUrl": "", "url": id}

    def isVideoFormat(self, url):
        u = url.split("?")[0].lower()
        return u.endswith(".m3u8") or u.endswith(".mp4")

    def localProxy(self, params):
        return [200, "text/plain; charset=utf-8", ""]

    def action(self, action):
        return {}

    def liveContent(self):
        return {}

    def manualVideoCheck(self):
        return False