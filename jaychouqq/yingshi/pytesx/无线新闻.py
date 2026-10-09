# -*- coding: utf-8 -*-
"""
无线新闻 TVB News · https://news.tvb.com/tc
直播 / 新闻栏目 / 节目分集 · 直出 m3u8
"""
import json
import sys
import time

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

SITE = "https://news.tvb.com"
API = SITE + "/app"
UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/16.6 Mobile/15E148 Safari/604.1"
)
LANG = "zh_hk"
CARD = {"type": "rect", "ratio": 1.78}


class Spider(BaseSpider):
    def init(self, extend=""):
        self.session = None
        if requests is not None:
            self.session = requests.Session()
            self.session.headers.update({
                "User-Agent": UA,
                "Referer": SITE + "/tc",
                "Accept-Language": "zh-HK,zh;q=0.9",
            })
            self.session.verify = False

    def getName(self):
        return "无线新闻"

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
                return r.json() if r.content else {}
            import urllib.request
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": SITE + "/tc", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8", "ignore"))
        except Exception as e:
            print("get err", e)
            return {}

    def _post(self, url, body=None, timeout=15):
        try:
            data = json.dumps(body or {}).encode("utf-8")
            if self.session is not None:
                r = self.session.post(url, data=data, headers={"Content-Type": "application/json"}, timeout=timeout)
                return r.json() if r.content else {}
            import urllib.request
            req = urllib.request.Request(url, data=data, method="POST", headers={
                "User-Agent": UA, "Referer": SITE + "/tc",
                "Content-Type": "application/json", "Accept": "application/json",
            })
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8", "ignore"))
        except Exception as e:
            print("post err", e)
            return {}

    def _title(self, obj):
        if not obj:
            return ""
        if isinstance(obj, str):
            return obj
        if isinstance(obj, dict):
            return obj.get("zh_hk") or obj.get("zh_cn") or obj.get("en") or obj.get("title_hk") or obj.get("title") or ""
        return str(obj)

    def _cover(self, cover):
        if not cover:
            return ""
        if isinstance(cover, str):
            return cover
        if isinstance(cover, list) and cover:
            c = cover[0]
            return (c.get("url") if isinstance(c, dict) else str(c)) or ""
        if isinstance(cover, dict):
            return cover.get("url") or ""
        return ""

    def _brief_article(self, n):
        if not n or n.get("id") is None:
            return None
        return {
            "vod_id": "article|%s" % n["id"],
            "vod_name": self._title(n) or n.get("title_hk") or n.get("title") or str(n["id"]),
            "vod_pic": self._cover(n.get("cover")) or n.get("video_cover_url") or "",
            "vod_remarks": "视频" if n.get("is_video") else (n.get("time_ago") or n.get("display_time") or ""),
            "style": CARD,
        }

    def _brief_episode(self, e):
        if not e:
            return None
        eid = e.get("episode_id") or e.get("id")
        pid = e.get("program_id")
        if not eid or not pid:
            return None
        title = self._title(e.get("title")) or e.get("program_title_hk") or e.get("program_title") or str(eid)
        return {
            "vod_id": "episode|%s|%s" % (pid, eid),
            "vod_name": title,
            "vod_pic": e.get("cover_image") or "",
            "vod_remarks": e.get("public_at") or "",
            "style": CARD,
        }

    def _brief_live(self, ch):
        if not ch:
            return None
        return {
            "vod_id": "live|%s" % (ch.get("channel_id") or ch.get("id")),
            "vod_name": ch.get("name_hk") or ch.get("name") or str(ch.get("channel_id") or ch.get("id")),
            "vod_pic": ch.get("cover_image_url") or "",
            "vod_remarks": "直播中" if ch.get("live_status") == 1 else "直播",
            "style": CARD,
        }

    def homeContent(self, filter=False):
        classes = [{"type_id": "live", "type_name": "直播频道"}]
        j = self._get(API + "/public/homepage/pc?lang=%s&limit=5" % LANG)
        for z in ((j.get("data") or {}).get("zones") or []):
            nid = z.get("navigation_id")
            name = z.get("navigation_name_hk") or z.get("navigation_name") or str(nid)
            if nid is not None:
                classes.append({"type_id": "nav_%s" % nid, "type_name": name})
        classes.append({"type_id": "latest", "type_name": "最新分集"})
        j2 = self._get(API + "/public/episode-categories")
        for c in ((j2.get("data") or {}).get("categories") or []):
            if c and c.get("id") is not None:
                classes.append({"type_id": "epi_%s" % c["id"], "type_name": c.get("name_hk") or c.get("name") or str(c["id"])})
        return {"class": classes, "filters": {}}

    def homeVideoContent(self):
        videos = []
        j = self._get(API + "/public/live/channels")
        for ch in ((j.get("data") or {}).get("channels") or [])[:6]:
            v = self._brief_live(ch)
            if v:
                videos.append(v)
        j2 = self._get(API + "/public/homepage/pc?lang=%s&limit=10" % LANG)
        for z in ((j2.get("data") or {}).get("zones") or []):
            for n in z.get("news") or []:
                v = self._brief_article(n)
                if v:
                    videos.append(v)
                if len(videos) >= 30:
                    break
            if len(videos) >= 30:
                break
        return {"list": videos}

    def categoryContent(self, tid, pg=1, filter=False, extend=None):
        tid = str(tid or "live")
        videos = []
        if tid == "live":
            j = self._get(API + "/public/live/channels")
            for ch in ((j.get("data") or {}).get("channels") or []):
                v = self._brief_live(ch)
                if v:
                    videos.append(v)
        elif tid == "latest" or tid.startswith("epi_"):
            path = API + "/public/programs/lists"
            if tid.startswith("epi_"):
                path += "?episode_category_id=%s" % tid[4:]
            j = self._get(path)
            for L in ((j.get("data") or {}).get("lists") or []):
                for e in L.get("episodes") or []:
                    v = self._brief_episode(e)
                    if v:
                        videos.append(v)
        elif tid.startswith("nav_"):
            nid = tid[4:]
            j = self._get(API + "/public/homepage/pc?lang=%s&limit=30" % LANG)
            for z in ((j.get("data") or {}).get("zones") or []):
                if str(z.get("navigation_id")) == str(nid):
                    for n in z.get("news") or []:
                        v = self._brief_article(n)
                        if v:
                            videos.append(v)
                    break
        return {"list": videos, "page": 1, "pagecount": 1, "limit": len(videos) or 20, "total": len(videos)}

    def detailContent(self, ids):
        raw = str((ids[0] if ids else "") or "").strip()
        parts = raw.split("|")
        kind = parts[0] if parts else ""
        if kind == "live":
            cid = parts[1] if len(parts) > 1 else ""
            j = self._get(API + "/public/live/channels")
            ch = None
            for c in ((j.get("data") or {}).get("channels") or []):
                if str(c.get("channel_id")) == str(cid) or str(c.get("id")) == str(cid):
                    ch = c
                    break
            return {"list": [{
                "vod_id": raw,
                "vod_name": (ch.get("name_hk") or ch.get("name") if ch else cid),
                "vod_pic": (ch.get("cover_image_url") if ch else "") or "",
                "vod_content": (ch.get("description_hk") or ch.get("description") if ch else "") or "TVB 直播",
                "vod_remarks": "直播",
                "vod_play_from": "TVB直播",
                "vod_play_url": "直播$%s" % raw,
                "style": CARD,
            }]}
        if kind == "article":
            aid = parts[1]
            j = self._get(API + "/public/homepage/content/article/%s?lang=%s" % (aid, LANG))
            d = j.get("data") or {}
            play = ("正片$%s" % raw) if d.get("video_url") else ("暂无视频$%s" % raw)
            return {"list": [{
                "vod_id": raw,
                "vod_name": self._title(d) or d.get("title_hk") or d.get("title") or aid,
                "vod_pic": self._cover(d.get("cover")) or d.get("video_cover_url") or "",
                "vod_content": (d.get("summary_hk") or d.get("summary") or "")[:300],
                "vod_remarks": "视频新闻" if d.get("is_video") else "图文",
                "vod_play_from": "TVB新闻",
                "vod_play_url": play,
                "style": CARD,
            }]}
        if kind == "episode":
            pid, eid = parts[1], parts[2]
            j = self._get(API + "/public/programs/%s/episodes/%s" % (pid, eid))
            d = j.get("data") or {}
            ep, prog = d.get("episode") or {}, d.get("program") or {}
            title = self._title(ep.get("title")) or self._title(prog.get("title")) or eid
            return {"list": [{
                "vod_id": raw,
                "vod_name": title,
                "vod_pic": ep.get("cover_image") or prog.get("cover_image") or "",
                "vod_content": self._title(ep.get("description")) or self._title(prog.get("description")) or "",
                "vod_remarks": ep.get("public_at") or "",
                "vod_play_from": "TVB节目",
                "vod_play_url": "正片$%s" % raw,
                "style": CARD,
            }]}
        return {"list": []}

    def playerContent(self, flag, id, vipFlags=None):
        head = {"User-Agent": UA, "Referer": SITE + "/tc", "Origin": SITE, "Accept": "*/*"}
        raw = str(id or "").strip()
        if "$" in raw:
            raw = raw.split("$")[-1].strip()
        parts = raw.split("|")
        kind = parts[0] if parts else ""
        url = ""
        if kind == "live" and len(parts) > 1:
            j = self._post(API + "/public/live/stream/%s" % parts[1], {})
            url = ((j.get("data") or {}).get("stream_url")) or ""
            if not url:
                j2 = self._get(API + "/public/live/channels")
                for c in ((j2.get("data") or {}).get("channels") or []):
                    if str(c.get("channel_id")) == str(parts[1]) and c.get("stream_url"):
                        url = c["stream_url"]
                        break
        elif kind == "article" and len(parts) > 1:
            j = self._get(API + "/public/homepage/content/article/%s?lang=%s" % (parts[1], LANG))
            url = ((j.get("data") or {}).get("video_url")) or ""
        elif kind == "episode" and len(parts) > 2:
            j = self._get(API + "/public/programs/%s/episodes/%s" % (parts[1], parts[2]))
            vi = (((j.get("data") or {}).get("episode") or {}).get("video_info")) or {}
            url = vi.get("video_url") or ""
        return {"parse": 0, "jx": 0, "url": url, "header": head}

    def searchContent(self, key, quick=False, pg=1):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick=False, pg=1):
        key = str(key or "").strip()
        page = max(1, int(pg or 1))
        if not key:
            return {"list": [], "page": page, "pagecount": 1, "limit": 20, "total": 0}
        videos = []
        j = self._get(API + "/public/search/more?q=%s&type=all&page=%s&per_page=20" % (
            requests.utils.quote(key) if requests else key, page))
        items = ((j.get("data") or {}).get("items")) or []
        for it in items:
            if it.get("episode_id") or (it.get("program_id") and it.get("id")):
                v = self._brief_episode(it)
            else:
                v = self._brief_article(it)
            if v:
                videos.append(v)
        if not videos:
            j2 = self._get(API + "/public/homepage/pc?lang=%s&limit=30" % LANG)
            for z in ((j2.get("data") or {}).get("zones") or []):
                for n in z.get("news") or []:
                    t = self._title(n) or n.get("title") or ""
                    if key in t:
                        v = self._brief_article(n)
                        if v:
                            videos.append(v)
        return {"list": videos, "page": page, "pagecount": page, "limit": 20, "total": len(videos)}


if __name__ == "__main__":
    sp = Spider()
    sp.init()
    print("home", [c["type_name"] for c in sp.homeContent()["class"][:8]])
    r = sp.categoryContent("live", 1)
    print("live", len(r["list"]), r["list"][0]["vod_name"] if r["list"] else None)
    if r["list"]:
        d = sp.detailContent([r["list"][0]["vod_id"]])
        p = sp.playerContent("x", d["list"][0]["vod_play_url"].split("$")[-1])
        print("play", (p.get("url") or "")[:100])
    r2 = sp.categoryContent("latest", 1)
    print("latest", len(r2["list"]))
    if r2["list"]:
        d2 = sp.detailContent([r2["list"][0]["vod_id"]])
        p2 = sp.playerContent("x", d2["list"][0]["vod_play_url"].split("$")[-1])
        print("ep play", (p2.get("url") or "")[:100])
