#!/usr/bin/python
# coding=utf-8
import re, json, requests, base64, socket, time
from urllib.parse import quote, unquote, urlencode
from base.spider import Spider
try:
    from Crypto.Cipher import AES
    from base64 import b64encode
except Exception:
    AES = None
    b64encode = None

_doh_cache = {}
_doh_last = {}
_doh_resolving = False
_orig_getaddrinfo = socket.getaddrinfo
_fallback_ips = {}
_doh_ttl = 300


def _doh_lookup(host):
    global _doh_resolving
    now = time.time()
    if host in _doh_cache and now - _doh_last.get(host, 0) < _doh_ttl:
        return _doh_cache[host]
    if _doh_resolving:
        return _fallback_ips.get(host, "")
    ip = ""
    _doh_resolving = True
    try:
        for srv in ("https://doh.pub/dns-query", "https://dns.alidns.com/resolve", "https://dns.google/resolve", "https://cloudflare-dns.com/dns-query"):
            try:
                r = requests.get(srv, params={"name": host, "type": "A"},
                                 headers={"Accept": "application/dns-json"}, timeout=3, verify=False)
                if r.status_code == 200:
                    for ans in r.json().get("Answer", []):
                        d = ans.get("data", "")
                        if ans.get("type") == 1 and re.match(r"^\d+\.\d+\.\d+\.\d+$", d):
                            ip = d
                            break
                if ip:
                    break
            except Exception:
                continue
    finally:
        _doh_resolving = False
    if not ip:
        ip = _fallback_ips.get(host, "")
    _doh_cache[host] = ip
    _doh_last[host] = now
    return ip


def _patched_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    if isinstance(host, str) and not _doh_resolving:
        ip = _doh_lookup(host)
        if ip:
            return _orig_getaddrinfo(ip, port, family, type, proto, flags)
    return _orig_getaddrinfo(host, port, family, type, proto, flags)

class Spider(Spider):
    def __init__(self):
        super().__init__()
        self.name = "黄果短剧"
        self.host = "https://huangguoai.com"
        self.header = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Referer": self.host,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9"
        }
        self.cat_map = [
            {"type_id": "ai-duanju", "type_name": "AI成人短剧", "path": "/ai-duanju/", "api": "ai-duanju",
             "tabs": [{"v": "latest", "n": "最新更新", "q": "sort=latest"},
                      {"v": "hot", "n": "当前热播", "q": ""},
                      {"v": "original", "n": "独家原创", "q": "is_original=1"},
                      {"v": "random", "n": "随机推荐", "q": "sort=random&size=20"}]},
            {"type_id": "ai-manju", "type_name": "AI成人漫剧", "path": "/ai-manju/", "api": "ai-manju",
             "tabs": [{"v": "latest", "n": "最新更新", "q": "sort=latest"},
                      {"v": "hot", "n": "当前热播", "q": ""},
                      {"v": "original", "n": "独家原创", "q": "is_original=1"},
                      {"v": "random", "n": "随机推荐", "q": "sort=random&size=20"}]},
            {"type_id": "ai-huanlian", "type_name": "AI换脸", "path": "/ai-huanlian/", "api": "ai-huanlian",
             "tabs": [{"v": "latest", "n": "最新更新", "q": "sort=latest"},
                      {"v": "hot", "n": "当前热播", "q": ""},
                      {"v": "original", "n": "独家原创", "q": "is_original=1"},
                      {"v": "random", "n": "随机推荐", "q": "sort=random&size=20"}]},
            {"type_id": "ai-mogai", "type_name": "AI魔改", "path": "/ai-mogai/", "api": "ai-mogai",
             "tabs": [{"v": "latest", "n": "最新更新", "q": "sort=latest"},
                      {"v": "hot", "n": "当前热播", "q": ""},
                      {"v": "original", "n": "独家原创", "q": "is_original=1"},
                      {"v": "random", "n": "随机推荐", "q": "sort=random&size=20"}]},
            {"type_id": "topic", "type_name": "专题", "path": "/topics/", "kind": "topic"},
            {"type_id": "rank", "type_name": "排行榜", "path": "/ranks/hot/", "kind": "rank",
             "tabs": [{"v": "hot", "n": "热播榜", "path": "/ranks/hot/"},
                      {"v": "potential", "n": "潜力榜", "path": "/ranks/potential/"},
                      {"v": "recommend", "n": "推荐榜", "path": "/ranks/recommend/"}]},
            {"type_id": "chigua", "type_name": "黄果吃瓜", "path": "/chigua/", "kind": "chigua",
             "tabs": [{"v": "latest", "n": "最新吃瓜", "path": "/chigua/"},
                      {"v": "remen", "n": "热门吃瓜", "path": "/chigua/remen/"},
                      {"v": "yuanchuang", "n": "AI原创", "path": "/chigua/yuanchuang/"}]}
        ]
        self.key = bytes(int(c) for c in "102_53_100_57_54_53_100_102_55_53_51_51_54_50_55_48".split("_"))
        self.iv = bytes(int(c) for c in "57_55_98_54_48_51_57_52_97_98_99_50_102_98_101_49".split("_"))
        self.filter_map = {"": {}}
        self.fallback_ips = {}
        _fallback_ips.update(self.fallback_ips)
        socket.getaddrinfo = _patched_getaddrinfo
        self._pin_host(self.host)

    def getName(self):
        return self.name

    def init(self, extend=""):
        pass

    def getHtml(self, url):
        for attempt in range(3):
            for kw in ({"verify": False}, {}):
                try:
                    r = requests.get(url, headers=self.header, timeout=15, **kw)
                    if r.status_code == 200:
                        return r.text
                except (TypeError, ValueError):
                    continue
                except Exception:
                    pass
        return ""

    def fix_url(self, url):
        if not url:
            return ""
        url = url.replace("\\u0026", "&").replace("&amp;", "&")
        if url.startswith("/proxy?") or url.startswith("/local/") or url.startswith("http://127.0.0.1"):
            return url
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return self.host + url
        return url

    def _pin_host(self, url):
        try:
            m = re.search(r'https?://([^/?#]+)', url)
            if m:
                _doh_lookup(m.group(1))
        except Exception:
            pass

    def proc_pic(self, pic):
        if not pic:
            return ""
        pic = self.fix_url(pic)
        if "127.0.0.1" in pic or "local://" in pic or pic.startswith("data:"):
            return pic
        try:
            b = self.getProxyUrl()
            if "?" not in b:
                b += "?do=py"
            return b + "&url=" + quote(pic)
        except Exception:
            return "http://127.0.0.1:9978/proxy?do=py&url=" + quote(pic)

    def extract_cards(self, html, link_prefix="detail"):
        result = []
        seen = set()
        matches = list(re.finditer(r'data-track-id="(\d+)"', html))
        for i, m in enumerate(matches):
            try:
                start = m.start()
                end = matches[i + 1].start() if i + 1 < len(matches) else min(start + 3000, len(html))
                chunk = html[start:end]
                vod_id = m.group(1)
                if vod_id in seen:
                    continue
                link = re.search(r'href="(/%s/%s/)"' % (link_prefix, re.escape(vod_id)), chunk)
                if not link:
                    link = re.search(r'href="(/%s/%s)"' % (link_prefix, re.escape(vod_id)), chunk)
                if not link:
                    continue
                seen.add(vod_id)
                title = re.search(r'data-track-title="([^"]*)"', chunk)
                vod_name = title.group(1) if title else ""
                if not vod_name:
                    t = re.search(r'alt="([^"]*)"', chunk)
                    vod_name = t.group(1) if t else ""
                if not vod_name:
                    h = re.search(r'<h2[^>]*>.*?<a[^>]*>([^<]+)</a>', chunk, re.S)
                    vod_name = h.group(1).strip() if h else ""
                pic = re.search(r'data-src="(https?://[^"]*)"', chunk)
                if not pic:
                    pic = re.search(r'<img[^>]*data-src="([^"]+)"', chunk)
                vod_pic = self.proc_pic(pic.group(1) if pic else "")
                ep = re.search(r'hg-drama-card__episode[^>]*>([^<]*)', chunk)
                vod_remarks = ep.group(1).strip() if ep else ""
                if not vod_remarks:
                    score = re.search(r'hg-drama-card__score[^>]*>([^<]*)', chunk)
                    vod_remarks = score.group(1).strip() if score else ""
                if vod_name and vod_id:
                    result.append({
                        "vod_id": vod_id,
                        "vod_name": vod_name,
                        "vod_pic": vod_pic,
                        "vod_remarks": vod_remarks
                    })
            except Exception:
                continue
        return result

    def extract_rank(self, html):
        result = []
        seen = set()
        for m in re.finditer(r'<div class="hg-rank-item"[^>]*data-track-id="(\d+)"', html):
            try:
                start = m.start()
                vod_id = m.group(1)
                if vod_id in seen:
                    continue
                chunk = html[start:start + 2500]
                seen.add(vod_id)
                link = re.search(r'href="(/detail/%s/)"' % re.escape(vod_id), chunk)
                if not link:
                    continue
                title = re.search(r'data-track-title="([^"]*)"', chunk)
                vod_name = title.group(1) if title else ""
                pic = re.search(r'data-src="(https?://[^"]*)"', chunk)
                vod_pic = self.proc_pic(pic.group(1) if pic else "")
                heat = re.search(r'hg-rank-item__heat-value[^>]*>([^<]*)', chunk)
                vod_remarks = heat.group(1).strip() if heat else ""
                if vod_name:
                    result.append({
                        "vod_id": vod_id,
                        "vod_name": vod_name,
                        "vod_pic": vod_pic,
                        "vod_remarks": vod_remarks
                    })
            except Exception:
                continue
        return result

    def extract_topics(self, html):
        result = []
        for m in re.finditer(r'<a class="hg-topic-card" href="(/topics/[^"]*/)"', html):
            try:
                start = m.start()
                chunk = html[start:start + 900]
                title = re.search(r'hg-topic-card__title[^>]*>([^<]*)', chunk)
                vod_name = title.group(1).strip() if title else ""
                meta = re.search(r'hg-topic-card__meta[^>]*>\s*<span>([^<]*)</span>', chunk)
                vod_remarks = meta.group(1).strip() if meta else ""
                pic = re.search(r'data-src="(https?://[^"]*)"', chunk)
                vod_pic = self.proc_pic(pic.group(1) if pic else "")
                if vod_name:
                    result.append({
                        "vod_id": m.group(1),
                        "vod_name": vod_name,
                        "vod_pic": vod_pic,
                        "vod_remarks": vod_remarks
                    })
            except Exception:
                continue
        return result

    def extract_posts(self, html):
        result = []
        seen = set()
        for m in re.finditer(r'<a class="hg-post-card" href="(/archives/(\d+)/)"', html):
            try:
                start = m.start()
                pid = m.group(2)
                if pid in seen:
                    continue
                seen.add(pid)
                chunk = html[start:start + 1500]
                title = re.search(r'<h3>([^<]*)</h3>', chunk)
                vod_name = title.group(1).strip() if title else ""
                pic = re.search(r'data-src="(https?://[^"]*)"', chunk)
                vod_pic = self.proc_pic(pic.group(1) if pic else "")
                meta = re.search(r'hg-post-card__cat[^>]*>([^<]*)', chunk)
                vod_remarks = meta.group(1).strip() if meta else ""
                if vod_name:
                    result.append({
                        "vod_id": m.group(1),
                        "vod_name": vod_name,
                        "vod_pic": vod_pic,
                        "vod_remarks": vod_remarks
                    })
            except Exception:
                continue
        return result

    def parse_api_list(self, items):
        result = []
        for it in items:
            try:
                vid = str(it.get("id") or "")
                if not vid:
                    continue
                name = (it.get("title") or "").strip()
                if not name:
                    continue
                score = it.get("score") or 0
                remark = ""
                if it.get("is_finished"):
                    remark = "全%d集" % (it.get("total_episodes") or 0)
                else:
                    ec = it.get("episode_count") or 0
                    if ec:
                        remark = "更新至%d集" % ec
                if score:
                    remark = ("%s %.1f分" % (remark, score)).strip()
                if it.get("is_original"):
                    remark = ("黄果原创 " + remark).strip()
                result.append({
                    "vod_id": vid,
                    "vod_name": name,
                    "vod_pic": self.proc_pic(it.get("cover") or ""),
                    "vod_remarks": remark
                })
            except Exception:
                continue
        return result

    def homeContent(self, filter):
        result = {"class": [], "filters": {}}
        for cat in self.cat_map:
            result["class"].append({"type_id": cat["type_id"], "type_name": cat["type_name"]})
            tabs = cat.get("tabs")
            if tabs:
                result["filters"][cat["type_id"]] = [{"key": "sub", "name": "子分类", "value": [{"n": t["n"], "v": t["v"]} for t in tabs]}]
        result["list"] = self.homeVideoContent().get("list", [])
        return result

    def homeVideoContent(self):
        result = {"list": []}
        html = self.getHtml(self.host)
        if not html:
            return result
        cards = self.extract_cards(html)
        seen = set()
        unique = []
        for c in cards:
            if c["vod_id"] not in seen:
                seen.add(c["vod_id"])
                unique.append(c)
        result["list"] = unique[:20]
        return result

    def get_tab(self, filter, extend):
        for d in (filter, extend):
            if isinstance(d, dict):
                if d.get("sub"):
                    return d.get("sub")
                inner = d.get("filter")
                if isinstance(inner, dict) and inner.get("sub"):
                    return inner.get("sub")
        return ""

    def categoryContent(self, tid, pg, filter, extend):
        result = {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}
        page = int(pg) if pg else 1
        if tid and str(tid).startswith("folder_topic_"):
            return self.topicFolderList(tid, page)
        cat = next((c for c in self.cat_map if c["type_id"] == tid or c["type_name"] == tid), None)
        if not cat:
            return result
        kind = cat.get("kind", "")
        tab = self.get_tab(filter, extend)
        if kind == "topic":
            html = self.getHtml(self.host + cat["path"].rstrip("/") + "/")
            if not html:
                return result
            topics = self.extract_topics(re.sub(r'<template[\s\S]*?</template>', '', html))
            for t in topics:
                fid = "folder_topic_" + base64.urlsafe_b64encode(t["vod_id"].encode("utf-8")).decode("utf-8")
                result["list"].append({
                    "vod_id": fid,
                    "vod_name": t["vod_name"],
                    "vod_pic": t["vod_pic"],
                    "vod_remarks": t["vod_remarks"] or "进入专辑",
                    "vod_tag": "folder"
                })
            result["page"] = page
            result["limit"] = len(result["list"]) if result["list"] else 20
            return result
        if kind == "rank":
            tabs = cat.get("tabs") or []
            tc = next((t for t in tabs if t["v"] == tab), tabs[0] if tabs else None)
            if not tc:
                return result
            html = self.getHtml(self.host + tc["path"])
            if not html:
                return result
            result["list"] = self.extract_rank(html)
            result["page"] = page
            return result
        if kind == "chigua":
            tabs = cat.get("tabs") or []
            tc = next((t for t in tabs if t["v"] == tab), tabs[0] if tabs else None)
            if not tc:
                return result
            base = tc["path"].rstrip("/")
            if page <= 1:
                url = self.host + base + "/"
            else:
                url = self.host + base + "/%d/" % page
            html = self.getHtml(url)
            if not html:
                return result
            result["list"] = self.extract_posts(re.sub(r'<template[\s\S]*?</template>', '', html))
            total_m = re.search(r'共 (\d+) 条', html)
            if total_m:
                result["total"] = int(total_m.group(1))
            page_m = re.search(r'第 (\d+)/(\d+) 页', html)
            if page_m:
                result["page"] = int(page_m.group(1))
                result["pagecount"] = int(page_m.group(2))
            result["limit"] = len(result["list"]) if result["list"] else 20
            return result
        tabs = cat.get("tabs") or []
        tc = next((t for t in tabs if t["v"] == tab), tabs[0] if tabs else None)
        if not tc:
            return result
        url = "%s/api/videos/category/%s?page=%d" % (self.host, cat.get("api", cat["type_id"]), page)
        if tc.get("q"):
            url += "&" + tc["q"]
        html = self.getHtml(url)
        if not html:
            return result
        try:
            data = json.loads(html)
        except Exception:
            data = None
        if data and isinstance(data.get("data"), dict):
            d = data["data"]
            result["list"] = self.parse_api_list(d.get("items") or [])
            pgd = d.get("pagination") or {}
            result["page"] = pgd.get("page") or page
            result["pagecount"] = pgd.get("pages") or 1
            result["total"] = pgd.get("total") or 0
            result["limit"] = pgd.get("size") or 20
        return result

    def detailContent(self, ids):
        result = {"list": []}
        vid = ids[0] if isinstance(ids, list) else ids
        if isinstance(vid, str) and vid.startswith("folder_topic_"):
            return self.topicFolderDetail(vid)
        if isinstance(vid, str) and (vid.startswith("/topics/") or vid.startswith("/archives/")):
            if vid.startswith("/topics/"):
                return self.topicDetail(vid)
            return self.postDetail(vid)
        m = re.search(r'(\d+)', vid)
        if not m:
            return result
        vid = m.group(1)
        html = self.getHtml("%s/detail/%s/" % (self.host, vid))
        if not html:
            return result
        vod = {"vod_id": vid}
        title = re.search(r'<title>([^|<]*)', html)
        if title:
            vod["vod_name"] = re.sub(r'\s*-\s*(短剧视频在线观看|黄果短剧|短剧).*$', '', title.group(1).strip()).strip() or vid
        else:
            vod["vod_name"] = vid
        pic = re.search(r'(?:data-src|src)="(https?://pic[^"]*)"', html)
        if pic:
            vod["vod_pic"] = self.proc_pic(pic.group(1))
        else:
            vod["vod_pic"] = ""
        eps = re.findall(r'<a[^>]*href="(/video/%s(?:/ep-\d+)?/)"[^>]*data-ep-id="(\d+)"[^>]*>(.*?)</a>' % re.escape(vid), html, re.S)
        if eps:
            ep_map = {}
            for href, eid, name in eps:
                ep_map[int(eid)] = (href, re.sub(r'<[^>]+>', '', name).strip())
            play_urls = []
            for eid in sorted(ep_map.keys()):
                href, name = ep_map[eid]
                label = name if name else "第%02d集" % eid
                play_urls.append("%s$%s" % (label, self.fix_url(href)))
            vod["vod_play_from"] = "黄果短剧"
            vod["vod_play_url"] = "#".join(play_urls)
        else:
            data = None
            dm = re.search(r'<script id="videoInitialData" type="application/json">(.*?)</script>', html, re.S)
            if dm:
                try:
                    data = json.loads(dm.group(1).replace("\\u0026", "&"))
                except Exception:
                    data = None
            if data and data.get("epPlaySrcs"):
                vod["vod_pic"] = self.proc_pic(data.get("coverSrc")) or vod["vod_pic"]
                eps = data.get("epPlaySrcs") or {}
                play_urls = []
                for ep_id in sorted(eps.keys(), key=lambda x: int(x)):
                    play_urls.append("第%02d集$%s" % (int(ep_id), self.proxy_play(eps[ep_id])))
                vod["vod_play_from"] = "黄果短剧"
                vod["vod_play_url"] = "#".join(play_urls)
            else:
                vod["vod_play_from"] = "黄果短剧"
                vod["vod_play_url"] = "第01集$/video/%s/" % vid
        result["list"] = [vod]
        return result

    def topicFolderList(self, tid, page):
        result = {"list": [], "page": page, "pagecount": 1, "limit": 20, "total": 0}
        try:
            path = base64.urlsafe_b64decode(tid[len("folder_topic_"):].encode("utf-8")).decode("utf-8")
        except Exception:
            return result
        html = self.getHtml(self.fix_url(path))
        if not html:
            return result
        cards = self.extract_cards(re.sub(r'<template[\s\S]*?</template>', '', html))
        seen = set()
        unique = []
        for c in cards:
            if c["vod_id"] not in seen:
                seen.add(c["vod_id"])
                unique.append(c)
        result["list"] = unique
        result["limit"] = len(unique) if unique else 20
        return result

    def topicFolderDetail(self, tid):
        result = {"list": []}
        try:
            path = base64.urlsafe_b64decode(tid[len("folder_topic_"):].encode("utf-8")).decode("utf-8")
        except Exception:
            return result
        html = self.getHtml(self.fix_url(path))
        if not html:
            return result
        cards = self.extract_cards(re.sub(r'<template[\s\S]*?</template>', '', html))
        seen = set()
        unique = []
        for c in cards:
            if c["vod_id"] not in seen:
                seen.add(c["vod_id"])
                unique.append(c)
        if not unique:
            return result
        title = re.search(r'<title>([^<]*)', html)
        name = title.group(1).strip() if title else "专辑"
        name = re.sub(r'\s*[·\-]\s*黄果短剧.*$', '', name).strip() or "专辑"
        vod = {
            "vod_id": tid,
            "vod_name": name,
            "vod_pic": unique[0]["vod_pic"],
            "vod_remarks": "专辑目录",
            "vod_content": "目录入口，点击播放进入视频列表",
            "vod_play_from": "目录",
            "vod_play_url": "打开$" + tid
        }
        result["list"] = [vod]
        return result

    def topicDetail(self, vid):
        result = {"list": []}
        html = self.getHtml(self.fix_url(vid))
        if not html:
            return result
        cards = self.extract_cards(re.sub(r'<template[\s\S]*?</template>', '', html))
        seen = set()
        unique = []
        for c in cards:
            if c["vod_id"] not in seen:
                seen.add(c["vod_id"])
                unique.append(c)
        result["list"] = unique
        return result

    def postDetail(self, vid):
        result = {"list": []}
        html = self.getHtml(self.fix_url(vid))
        if not html:
            return result
        vod = {"vod_id": vid}
        title = re.search(r'<h1[^>]*>([^<]*)', html)
        if title:
            vod["vod_name"] = title.group(1).strip()
        else:
            t = re.search(r'<title>([^<]*)', html)
            vod["vod_name"] = t.group(1).strip() if t else vid
        pic = re.search(r'data-src="(https?://pic[^\"]*)"', html)
        if pic:
            vod["vod_pic"] = self.proc_pic(pic.group(1))
        else:
            vod["vod_pic"] = ""
        players = re.findall(r'class="post-video-player"[^>]*data-src="([^"]*)"', html)
        if players:
            play_urls = []
            for idx, src in enumerate(players, 1):
                play_urls.append("第%02d集$%s" % (idx, self.proxy_play(src.replace("\\u0026", "&"))))
            vod["vod_play_from"] = "黄果短剧"
            vod["vod_play_url"] = "#".join(play_urls)
        else:
            m3u8s = re.findall(r'(https?://[^\s"<>\\]*\.m3u8[^\s"<>\\]*)', html)
            if m3u8s:
                seen = []
                for u in m3u8s:
                    u = u.replace("\\u0026", "&")
                    if u not in seen:
                        seen.append(u)
                vod["vod_play_from"] = "黄果短剧"
                vod["vod_play_url"] = "#".join("第%02d集$%s" % (i + 1, self.proxy_play(u)) for i, u in enumerate(seen))
            else:
                vod["vod_play_from"] = "黄果短剧"
                vod["vod_play_url"] = "第01集$" + vid
        result["list"] = [vod]
        return result

    def searchContent(self, key, quick, pg):
        result = {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}
        page = int(pg) if pg else 1
        url = "%s/search/?keyword=%s" % (self.host, quote(key))
        if page > 1:
            url += "&page=%d" % page
        html = self.getHtml(url)
        if not html:
            return result
        result["list"] = self.extract_cards(re.sub(r'<template[\s\S]*?</template>', '', html))
        total = re.search(r'data-track-search-total="(\d+)"', html)
        if total:
            result["total"] = int(total.group(1))
        result["page"] = page
        return result

    def playerContent(self, flag, id, vipFlags):
        result = {"parse": 0, "playUrl": "", "url": "", "header": ""}
        if isinstance(id, str) and id.startswith("folder_topic_"):
            return {"parse": 1, "url": id, "header": {}}
        play_url = self.fix_url(id) if id else ""
        if play_url.startswith("/proxy?") or play_url.startswith("/local/") or play_url.startswith("http://127.0.0.1"):
            result["url"] = play_url
            result["header"] = json.dumps({"User-Agent": self.header["User-Agent"], "Referer": self.host})
            return result
        if 'm3u8' in play_url or '.mp4' in play_url:
            result["url"] = self.proxy_play(play_url)
            result["header"] = json.dumps({"User-Agent": self.header["User-Agent"], "Referer": self.host})
            return result
        if re.fullmatch(r'\d+', play_url):
            d = self.detailContent([play_url])
            if d["list"]:
                first = d["list"][0].get("vod_play_url", "").split("#")[0]
                if "$" in first:
                    play_url = self.fix_url(first.split("$", 1)[1])
        if play_url.startswith("/proxy?") or play_url.startswith("/local/") or play_url.startswith("http://127.0.0.1"):
            result["url"] = play_url
            result["header"] = json.dumps({"User-Agent": self.header["User-Agent"], "Referer": self.host})
            return result
        html = self.getHtml(play_url)
        if not html:
            return result
        m3u8 = ""
        m = re.search(r'"videoSrc"\s*:\s*"([^"]*)"', html)
        if m:
            m3u8 = m.group(1).replace("\\u0026", "&")
        if not m3u8:
            m = re.search(r'<video[^>]*>\s*<source[^>]*src="([^"]*)"', html)
            if m:
                m3u8 = m.group(1)
        if not m3u8:
            m = re.search(r'(https?://[^\s"<>\\]*\.m3u8[^\s"<>\\]*)', html)
            if m:
                m3u8 = m.group(1).replace("\\u0026", "&")
        result["url"] = self.proxy_m3u8_url(m3u8) if m3u8 else ""
        result["header"] = json.dumps({"User-Agent": self.header["User-Agent"], "Referer": self.host})
        return result

    def proxy_m3u8_url(self, url):
        return self._proxy_base("m3u8", url)

    def proxy_ts_url(self, url):
        return self._proxy_base("ts", url)

    def proxy_key_url(self, url):
        return self._proxy_base("key", url)

    def _proxy_base(self, typ, url):
        b = self.getProxyUrl()
        if "?" not in b:
            b += "?do=py"
        return b + "&type=" + typ + "&url=" + quote(url)

    def proxy_play(self, url):
        url = self.fix_url(url)
        if url.startswith("/proxy?") or url.startswith("/local/") or url.startswith("http://127.0.0.1"):
            return url
        if "m3u8" in url.lower():
            return self.proxy_m3u8_url(url)
        return url

    def _proxy_m3u8(self, url):
        try:
            r = requests.get(url, headers=self.header, timeout=20, verify=False)
            if r.status_code != 200:
                return [502, "text/plain", "err:%d" % r.status_code]
            text = r.text
            host_base = re.match(r'https?://[^/]+', url)
            host_base = host_base.group(0) if host_base else ""
            path_dir = url[:url.rfind("/") + 1] if "/" in url else ""
            lines = []
            for line in text.split("\n"):
                s = line.strip()
                if not s:
                    continue
                if s.startswith("#"):
                    if 'URI="' in s:
                        mm = re.search(r'URI="([^"]*)"', s)
                        if mm:
                            u = mm.group(1)
                            if u.startswith("//"):
                                u = "https:" + u
                            elif u.startswith("/"):
                                u = host_base + u
                            elif not re.match(r'https?://', u):
                                u = path_dir + u
                            s = s[:mm.start(1)] + self.proxy_key_url(u) + s[mm.end(1):]
                    lines.append(s)
                    continue
                if re.match(r'https?://', s):
                    turl = s
                elif s.startswith("//"):
                    turl = "https:" + s
                elif s.startswith("/"):
                    turl = host_base + s
                else:
                    turl = path_dir + s
                lines.append(self.proxy_ts_url(turl))
            return [200, "application/vnd.apple.mpegurl", "\n".join(lines).encode("utf-8")]
        except Exception:
            return [502, "text/plain", "err"]

    def _proxy_ts(self, url):
        try:
            r = requests.get(url, headers=self.header, timeout=20, verify=False)
            if r.status_code != 200:
                return [502, "text/plain", "err:%d" % r.status_code]
            return [200, "video/mp2t", r.content]
        except Exception:
            return [502, "text/plain", "err"]

    def _proxy_key(self, url):
        try:
            r = requests.get(url, headers=self.header, timeout=20, verify=False)
            if r.status_code != 200:
                return [502, "text/plain", "err:%d" % r.status_code]
            return [200, "application/octet-stream", r.content]
        except Exception:
            return [502, "text/plain", "err"]

    def _proxy_pic(self, url):
        try:
            r = requests.get(url, headers=self.header, timeout=15, verify=False)
            ct = r.content
            if ct[:3] == b"\xff\xd8\xff":
                return [200, "image/jpeg", ct]
            if ct[:8] == b"\x89PNG\r\n\x1a\n":
                return [200, "image/png", ct]
            if ct[:4] == b"RIFF" and ct[8:12] == b"WEBP":
                return [200, "image/webp", ct]
            if ct[:3] == b"GIF":
                return [200, "image/gif", ct]
            if AES and len(ct) % 16 == 0:
                dec = AES.new(self.key, AES.MODE_CBC, self.iv).decrypt(ct)
                if dec[:3] == b"\xff\xd8\xff":
                    return [200, "image/jpeg", dec]
                if dec[:8] == b"\x89PNG\r\n\x1a\n":
                    return [200, "image/png", dec]
                if dec[:4] == b"RIFF" and dec[8:12] == b"WEBP":
                    return [200, "image/webp", dec]
                if dec[:3] == b"GIF":
                    return [200, "image/gif", dec]
                return [200, "image/jpeg", dec]
            return [200, "image/jpeg", ct]
        except Exception:
            return [404, "text/plain", "err"]

    def localProxy(self, param):
        if not param:
            return [404, "text/plain", "nf"]
        typ = param.get("type") or ""
        url = param.get("url") or param.get("pic") or ""
        if not url:
            return [404, "text/plain", "nf"]
        url = unquote(url)
        if typ == "m3u8":
            return self._proxy_m3u8(url)
        if typ == "ts":
            return self._proxy_ts(url)
        if typ == "key":
            return self._proxy_key(url)
        return self._proxy_pic(url)