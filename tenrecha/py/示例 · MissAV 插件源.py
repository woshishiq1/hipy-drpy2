# -*- coding: utf-8 -*-
"""
示例插件 · MissAV 插件源（TVBox py 插件写法示范）
—— 结构就是标准 TVBox py 插件：class Spider + homeContent/categoryContent/detailContent/searchContent/playerContent
—— 换站点只要改 API_BASE 和几个解析函数；上传到后台「Python 插件」区即生效。
"""
import json
import re
import urllib.parse
import urllib.request

try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider(object):
        pass

API_BASE = "https://missav.ws.ystv.top"
SYNC_KEY = "WYphbj3KdcrlFZatLDq-J18SNNAflolb"
COVER_BASE = "https://fourhoi.com/"
PAGE_SIZE = 48


def fnv32(s):
    h = 0x811c9dc5
    for b in s.encode("utf-8"):
        h ^= b
        h = (h * 0x01000193) & 0xFFFFFFFF
    return "%08x" % h


def fmt_dur(sec):
    try:
        sec = int(sec)
    except Exception:
        return ""
    if not sec:
        return ""
    h, m, s = sec // 3600, (sec % 3600) // 60, sec % 60
    return ("%d:%02d:%02d" % (h, m, s)) if h else ("%d:%02d" % (m, s))


class Spider(BaseSpider):
    name = "示例 · MissAV 插件源"

    def __init__(self):
        self.timeout = 20

    def init(self, extend=""):
        cfg = {}
        try:
            if extend:
                cfg = json.loads(extend) if str(extend).strip().startswith("{") else {}
        except Exception:
            cfg = {}
        self.base = str(cfg.get("api") or API_BASE).rstrip("/")
        self.key = str(cfg.get("key") or SYNC_KEY)
        return self

    # ---------- 统一请求层 ----------
    def _get(self, path):
        url = self.base + path
        req = urllib.request.Request(url, headers={
            "x-sync-key": self.key,
            "accept": "application/json",
            "User-Agent": "ZakaTVPySpider/1.0",
        })
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace"))

    def _cat_file(self, kind, name):
        return "%s_%s" % (kind, fnv32("%s|%s" % (kind, name)))

    def _map(self, row):
        slug = row[0] if len(row) > 0 else ""
        return {
            "vod_id": slug,
            "vod_name": row[1] if len(row) > 1 else slug,
            "vod_pic": COVER_BASE + urllib.parse.quote(slug) + "/cover-t.jpg",
            "vod_remarks": fmt_dur(row[2] if len(row) > 2 else 0),
        }

    # ---------- 分类 ----------
    def homeContent(self, filter):
        cats = []
        try:
            news = self._get("/data/cats_new.json") or []
        except Exception:
            news = []
        for x in news[:20]:
            cats.append({"type_id": "new|" + str(x[0]), "type_name": "专题 · " + str(x[0])})
        for kind, label, limit in (("genres", "", 400), ("makers", "片商 · ", 300), ("labels", "厂牌 · ", 80)):
            try:
                arr = self._get("/data/cats_%s.json" % kind) or []
            except Exception:
                arr = []
            for x in arr[:limit]:
                cats.append({"type_id": kind + "|" + str(x[0]), "type_name": label + str(x[0])})
        return {"class": cats}

    def categoryContent(self, tid, pg, filter, extend):
        pg = max(1, int(pg or 1))
        if "|" not in str(tid):
            return {"page": pg, "pagecount": 1, "total": 0, "list": []}
        kind, name = str(tid).split("|", 1)
        first = self._get("/data/c/%s.json" % self._cat_file(kind, name))
        total = int(first.get("t") or len(first.get("i") or []))
        chunk = int(first.get("chunk") or 0)
        items = first.get("i") or []
        base = 0
        if chunk and total > len(items) and pg > 1:
            need = ((pg - 1) * PAGE_SIZE) // chunk + 1
            if need > 1:
                try:
                    nxt = self._get("/data/c/%s_%d.json" % (self._cat_file(kind, name), need))
                    if nxt.get("i"):
                        items = nxt["i"]
                        base = ((pg - 1) * PAGE_SIZE // chunk) * chunk
                except Exception:
                    pass
        start = (pg - 1) * PAGE_SIZE - base
        return {
            "page": pg,
            "pagecount": max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE),
            "total": total,
            "list": [self._map(r) for r in items[start:start + PAGE_SIZE]],
        }

    # ---------- 详情 ----------
    def detailContent(self, ids):
        slug = ids[0] if isinstance(ids, list) else ids
        dmap = self._get("/data/d/%s.json" % fnv32(slug)[:3])
        rec = (dmap or {}).get(slug)
        if not rec:
            return {"list": []}
        title = slug.upper()
        cat_name = ""
        try:
            if rec.get("c"):
                cat = self._get("/data/c/%s.json" % rec["c"])
                cat_name = cat.get("n") or ""
                for x in (cat.get("i") or []):
                    if x and x[0] == slug:
                        title = x[1] or title
                        break
        except Exception:
            pass
        tags = [t.strip() for t in re.sub(r'[\[\]"]', "", str(rec.get("g") or "")).split(",") if t.strip()]
        content = "\n".join(filter(None, [
            ("分类：%s" % cat_name) if cat_name else "",
            ("演员：%s" % rec.get("a")) if rec.get("a") else "",
            ("发行：%s" % rec.get("dt")) if rec.get("dt") else "",
            ("标签：%s" % " / ".join(tags)) if tags else "",
        ]))
        lines, eps = [], []
        if rec.get("p1"):
            lines.append("1080P")
            eps.append("1080P$" + rec["p1"])
        if rec.get("p7"):
            lines.append("720P")
            eps.append("720P$" + rec["p7"])
        return {"list": [{
            "vod_id": slug,
            "vod_name": title,
            "vod_pic": COVER_BASE + urllib.parse.quote(slug) + "/cover-n.jpg",
            "vod_remarks": cat_name,
            "vod_content": content,
            "vod_play_from": "$$$".join(lines),
            "vod_play_url": "$$$".join(eps),
        }]}

    # ---------- 搜索 ----------
    def searchContent(self, key, quick, pg="1"):
        kw = str(key or "").strip()
        if not kw:
            return {"list": []}
        pre = re.sub(r"[^0-9a-z]", "", kw.lower())[:2] or "zz"
        try:
            rows = self._get("/data/s/%s.json" % pre) or []
        except Exception:
            rows = []
        low = kw.lower()
        hits = [r for r in rows if low in str(r[0]).lower() or low in str(r[1]).lower()]
        return {"list": [self._map(r) for r in hits[:240]]}

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags):
        url = str(id or "")
        if not url.startswith("http"):
            dmap = self._get("/data/d/%s.json" % fnv32(url)[:3])
            rec = (dmap or {}).get(url) or {}
            url = rec.get("p7") if flag == "720P" else rec.get("p1")
        return {
            "parse": 0,
            "playUrl": "",
            "url": url or "",
            "header": {"Referer": "https://missav.ws/"},
        }
