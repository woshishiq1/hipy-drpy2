# -*- coding: utf-8 -*-
"""
東網視頻 onTV · https://tv.on.cc/?section=683
列表: /ontv/xml/Group/{year}/{section}_{year}.xml
详情: /ontv/xml/Metadata/Video/{YYYYMM}/{vid}.xml
播放: https://video-cdn.on.cc/Video/{YYYYMM}/{vid}_{hd|ipad|iphone}.mp4|m3u8?t=
"""
import json
import re
import sys
import time
from urllib.parse import quote

try:
    import requests
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except Exception:
    requests = None

sys.path.append("..")
try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider(object):
        def init(self, extend=""):
            pass

SITE = "https://tv.on.cc"
FEED = "https://tv.on.cc/ontv"
CDN = "https://video-cdn.on.cc"
UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/16.6 Mobile/15E148 Safari/604.1"
)

FALLBACK = [
    ("683", "東呼即應"),
    ("20209001", "繽FUN星網"),
    ("313", "我撐港超聯"),
    ("398", "魅力港籃"),
    ("390", "體育世界"),
    ("389", "完全足球"),
    ("463", "體完再睇"),
    ("482", "創藝夢飛翔"),
    ("216", "產經視頻"),
    ("218", "至Hit交易日"),
    ("469", "中環剝花生"),
    ("307", "塞錢入你袋"),
    ("595", "財經Focus"),
    ("736", "樓市Mentions")
]


class Spider(BaseSpider):
    def init(self, extend=""):
        self.session = None
        if requests is not None:
            self.session = requests.Session()
            self.session.headers.update({
                "User-Agent": UA,
                "Referer": SITE + "/",
                "Accept-Language": "zh-HK,zh;q=0.9",
            })
            self.session.verify = False
        self._sec_cache = None
        self._feed_map = {"20209001": "536", "20180001": "498", "20209000": "542", "20200101": "531", "20200103": "579"}

    def getName(self):
        return "東網視頻"

    def isVideoFormat(self, url):
        u = str(url or "").lower()
        return any(x in u for x in (".m3u8", ".mp4", ".flv"))

    def manualVideoCheck(self):
        return False

    def destroy(self):
        try:
            if self.session:
                self.session.close()
        except Exception:
            pass

    def _get(self, url, timeout=15):
        try:
            if self.session is not None:
                r = self.session.get(url, timeout=timeout)
                return (r.content or b"").decode("utf-8-sig", "ignore")
            import urllib.request
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": SITE + "/"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8-sig", "ignore")
        except Exception as e:
            print("get err", e)
            return ""

    def _years(self):
        y = time.localtime().tm_year
        return [y, y - 1, y - 2]

    def _parse_videos(self, xml):
        out = []
        for m in re.finditer(r'<video\s+createTime=["\'](\d+)["\']\s*>([^<]+)</video>', xml or "", re.I):
            vid = m.group(2).strip()
            if vid:
                out.append({"id": vid, "createTime": m.group(1)})
        return out

    def _yyyymm(self, vid, create_time=""):
        m = re.search(r'(?:OCM|OBK|SPT|ONV)?(\d{2})(\d{2})(\d{2})-', str(vid or ""))
        if m:
            yy = int(m.group(1))
            year = 1900 + yy if yy >= 70 else 2000 + yy
            return "%04d%s" % (year, m.group(2))
        if create_time:
            try:
                t = time.localtime(int(create_time))
                return time.strftime("%Y%m", t)
            except Exception:
                pass
        return time.strftime("%Y%m")

    def _parse_meta(self, xml):
        out = {"title": "", "desc": "", "thumb": "", "updateTime": ""}
        if not xml:
            return out
        m = re.search(r'<title>\s*<!\[CDATA\[(.*?)\]\]>\s*</title>', xml, re.S) or re.search(r'<title>([^<]+)</title>', xml)
        if m:
            out["title"] = m.group(1).strip()
        m = re.search(r'<description>\s*<!\[CDATA\[(.*?)\]\]>\s*</description>', xml, re.S)
        if m:
            out["desc"] = re.sub(r'\s+', ' ', m.group(1)).strip()[:300]
        m = re.search(r'<thumbnailUrlList>[\s\S]*?<url[^>]*>([^<]+)</url>', xml, re.I)
        if m:
            out["thumb"] = m.group(1).strip()
        m = re.search(r'<updateTime>(\d+)</updateTime>', xml)
        if m:
            out["updateTime"] = m.group(1)
        return out

    def _thumb(self, path, yyyymm, vid):
        if path and path.startswith("http"):
            return path
        if path and path.startswith("/"):
            return SITE + path
        if vid:
            return "%s/cms/src/thumbnail/%s/%s.jpg" % (SITE, yyyymm, vid)
        return SITE + "/img/ontv_logo.png"

    def _load_sections(self):
        if self._sec_cache:
            return self._sec_cache
        txt = self._get(SITE + "/config/section.js")
        out = []
        self._feed_map = {
            "20209001": "536",
            "20180001": "498",
            "20209000": "542",
            "20200101": "531",
            "20200103": "579",
        }
        try:
            data = json.loads(txt.encode("utf-8").decode("utf-8-sig").strip())
            seen = set()
            for s in data:
                sid = str(s.get("id") or "")
                feed = str(s.get("tvFeedId") or sid)
                if sid:
                    self._feed_map[sid] = feed
                if sid and sid not in seen and s.get("hidden") != "true":
                    seen.add(sid)
                    out.append({"type_id": sid, "type_name": s.get("name") or sid})
                for sub in s.get("subSection") or []:
                    ssid = str(sub.get("id") or "")
                    if not ssid or ssid in seen:
                        continue
                    # 子栏目即使 hidden 也加入（缤FUN 等）
                    self._feed_map[ssid] = ssid
                    seen.add(ssid)
                    pname = (s.get("name") or "")
                    sname = sub.get("name") or ssid
                    label = ("%s·%s" % (pname, sname)) if pname and pname != sname else sname
                    out.append({"type_id": ssid, "type_name": label})
        except Exception:
            out = [{"type_id": a, "type_name": b} for a, b in FALLBACK]
        self._sec_cache = out
        return out

    def _resolve_feed(self, section_id):
        sid = str(section_id or "")
        fm = getattr(self, "_feed_map", None) or {}
        if not fm:
            self._load_sections()
            fm = getattr(self, "_feed_map", {}) or {}
        return str(fm.get(sid) or sid)

    def _load_section_videos(self, section_id):
        feed_id = self._resolve_feed(section_id)
        allv = []
        for y in self._years():
            xml = self._get("%s/xml/Group/%s/%s_%s.xml" % (FEED, y, feed_id, y))
            allv.extend(self._parse_videos(xml))
        mp = {}
        for v in allv:
            vid = v["id"]
            if vid not in mp or int(v["createTime"]) > int(mp[vid]["createTime"]):
                mp[vid] = v
        out = list(mp.values())
        out.sort(key=lambda x: int(x["createTime"]), reverse=True)
        return out

    def homeContent(self, filter=False):
        return {"class": self._load_sections(), "filters": {}}

    def homeVideoContent(self):
        videos = []
        for v in self._load_section_videos("683")[:12]:
            ym = self._yyyymm(v["id"], v["createTime"])
            meta = self._parse_meta(self._get("%s/xml/Metadata/Video/%s/%s.xml" % (FEED, ym, v["id"])))
            videos.append({
                "vod_id": "%s|%s" % (v["id"], v["createTime"]),
                "vod_name": meta["title"] or v["id"],
                "vod_pic": self._thumb(meta["thumb"], ym, v["id"]),
                "vod_remarks": "東網視頻",
                "style": {"type": "rect", "ratio": 1.78},
            })
        return {"list": videos}

    def categoryContent(self, tid, pg=1, filter=False, extend=None):
        page = max(1, int(pg or 1))
        allv = self._load_section_videos(str(tid or "683"))
        ps = 20
        chunk = allv[(page - 1) * ps: page * ps]
        videos = []
        for v in chunk:
            ym = self._yyyymm(v["id"], v["createTime"])
            meta = self._parse_meta(self._get("%s/xml/Metadata/Video/%s/%s.xml" % (FEED, ym, v["id"])))
            videos.append({
                "vod_id": "%s|%s" % (v["id"], v["createTime"]),
                "vod_name": meta["title"] or v["id"],
                "vod_pic": self._thumb(meta["thumb"], ym, v["id"]),
                "vod_remarks": "點播",
                "style": {"type": "rect", "ratio": 1.78},
            })
        pc = max(1, (len(allv) + ps - 1) // ps)
        return {"list": videos, "page": page, "pagecount": pc, "limit": ps, "total": len(allv)}

    def detailContent(self, ids):
        raw = str((ids[0] if ids else "") or "").strip()
        parts = raw.split("|")
        vid, ct = parts[0], (parts[1] if len(parts) > 1 else "")
        if not vid:
            return {"list": []}
        ym = self._yyyymm(vid, ct)
        meta = self._parse_meta(self._get("%s/xml/Metadata/Video/%s/%s.xml" % (FEED, ym, vid)))
        t = meta.get("updateTime") or ct or str(int(time.time()))
        lines = []
        for name, q, ext in [
            ("高清m3u8", "hd", "m3u8"),
            ("标清m3u8", "ipad", "m3u8"),
            ("流畅m3u8", "iphone", "m3u8"),
            ("高清MP4", "hd", "mp4"),
            ("标清MP4", "ipad", "mp4"),
            ("流畅MP4", "iphone", "mp4"),
        ]:
            lines.append("%s$%s/Video/%s/%s_%s.%s?t=%s" % (name, CDN, ym, vid, q, ext, t))
        return {"list": [{
            "vod_id": raw,
            "vod_name": meta["title"] or vid,
            "vod_pic": self._thumb(meta["thumb"], ym, vid),
            "vod_content": meta.get("desc") or "",
            "vod_remarks": "東網視頻",
            "vod_play_from": "onTV",
            "vod_play_url": "#".join(lines),
            "style": {"type": "rect", "ratio": 1.78},
        }]}

    def playerContent(self, flag, id, vipFlags=None):
        head = {"User-Agent": UA, "Referer": SITE + "/", "Origin": SITE, "Accept": "*/*"}
        play = str(id or "").strip()
        if "$" in play:
            play = play.split("$")[-1].strip()
        return {"parse": 0, "jx": 0, "url": play, "header": head}

    def searchContent(self, key, quick=False, pg=1):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick=False, pg=1):
        key = str(key or "").strip()
        if not key:
            return {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}
        out = []
        for sid in ("683", "20180001", "687"):
            for v in self._load_section_videos(sid)[:25]:
                ym = self._yyyymm(v["id"], v["createTime"])
                meta = self._parse_meta(self._get("%s/xml/Metadata/Video/%s/%s.xml" % (FEED, ym, v["id"])))
                title = meta["title"] or v["id"]
                if key in title:
                    out.append({
                        "vod_id": "%s|%s" % (v["id"], v["createTime"]),
                        "vod_name": title,
                        "vod_pic": self._thumb(meta["thumb"], ym, v["id"]),
                        "vod_remarks": "東網",
                        "style": {"type": "rect", "ratio": 1.78},
                    })
                if len(out) >= 30:
                    break
            if len(out) >= 30:
                break
        return {"list": out, "page": 1, "pagecount": 1, "limit": 30, "total": len(out)}


if __name__ == "__main__":
    sp = Spider()
    sp.init()
    print("home", [c["type_name"] for c in sp.homeContent()["class"][:5]])
    r = sp.categoryContent("683", 1)
    print("cat", len(r["list"]), r["list"][0]["vod_name"] if r["list"] else None)
    if r["list"]:
        d = sp.detailContent([r["list"][0]["vod_id"]])
        print("detail", d["list"][0]["vod_play_url"][:120])
        p = sp.playerContent("x", d["list"][0]["vod_play_url"].split("#")[0].split("$")[-1])
        print("play", p.get("url")[:100])
