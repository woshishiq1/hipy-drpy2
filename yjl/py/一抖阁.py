import re
import requests
from urllib.parse import quote
from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def getName(self):
        return "一抖阁"

    def init(self, extend=""):
        self.host = "https://yidouge.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 13; Mobile) AppleWebKit/537.36 Chrome/124.0.0.0 Mobile Safari/537.36",
            "Referer": self.host + "/",
            "Cookie": "gv_age_verified=1",
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def destroy(self):
        return "Destroy"

    def _html(self, url):
        try:
            return self.session.get(url if url.startswith("http") else self.host + url, timeout=15).text
        except Exception:
            return ""

    def _text(self, s):
        if not s:
            return ""
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s)).strip()

    def _pic(self, url):
        if not url:
            return ""
        url = url.strip()
        if url.startswith("//"):
            url = "https:" + url
        if "images.weserv.nl" in url:
            return url
        if url.endswith(".webp") or "webp" in url.lower():
            return "https://images.weserv.nl/?url=" + url + "&output=jpg"
        return url

    def _list(self, html):
        out = []
        seen = set()
        if not html:
            return out
        # 普通单集卡片
        for block in re.findall(r'<article class="video-card"[^>]*>(.*?)</article>', html, re.S | re.I):
            lm = re.search(r'<a class="video-card__link" href="([^"]+)"', block, re.I)
            if not lm:
                lm = re.search(r'<a class="video-card__body-link" href="([^"]+)"', block, re.I)
            if not lm or lm.group(1) in seen:
                continue
            seen.add(lm.group(1))
            tm = re.search(r'<h2 class="video-card__title">([^<]+)</h2>', block, re.I)
            im = re.search(r'<img[^>]+src="([^"]+)"', block, re.I)
            dm = re.search(r'<span class="video-card__duration">([^<]+)</span>', block, re.I)
            out.append({
                "vod_id": lm.group(1),
                "vod_name": self._text(tm.group(1)) if tm else "",
                "vod_pic": self._pic(im.group(1)) if im else "",
                "vod_remarks": self._text(dm.group(1)) if dm else "",
            })
        # 合集卡片
        for block in re.findall(r'<article class="video-card ydg-author-collection-card"[^>]*>(.*?)</article>', html, re.S | re.I):
            lm = re.search(r'class="ydg-author-collection-link">\s*<a[^>]+href="([^"]+)"', block, re.S | re.I)
            if not lm or lm.group(1) in seen:
                continue
            seen.add(lm.group(1))
            tm = re.search(r'<strong class="ydg-author-collection-title">([^<]+)</strong>', block, re.I)
            im = re.search(r'<img[^>]+src="([^"]+)"', block, re.I)
            nm = re.search(r'共\s*(\d+)\s*部', block, re.I)
            out.append({
                "vod_id": lm.group(1),
                "vod_name": self._text(tm.group(1)) if tm else "",
                "vod_pic": self._pic(im.group(1)) if im else "",
                "vod_remarks": "合集·共{}部".format(nm.group(1)) if nm else "合集",
            })
        return out

    def _cats(self, html):
        cats = []
        seen = set()
        if not html:
            return cats
        for m in re.finditer(r'<a class="category-parent-link[^"]*"\s+href="([^"]+)"[^>]*>\s*<span>([^<]+)</span>', html, re.I):
            href = m.group(1)
            if href in seen:
                continue
            seen.add(href)
            cats.append({"type_name": self._text(m.group(2)), "type_id": href})
        return cats

    def homeContent(self, filter):
        html = self._html("/")
        cats = self._cats(html)
        vods = self._list(html)
        return {"class": cats, "list": vods}

    def homeVideoContent(self):
        html = self._html("/")
        return {"list": self._list(html)}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        base = tid.rstrip("/")
        path = base if pg == 1 else base + "/page/{}/".format(pg)
        vods = self._list(self._html(path))
        return {
            "page": pg,
            "pagecount": pg + 1 if vods else pg,
            "limit": len(vods),
            "total": 999999 if vods else 0,
            "list": vods
        }

    def detailContent(self, ids):
        vid = str(ids[0]).strip() if isinstance(ids, list) else str(ids).strip()
        if not vid.startswith("http"):
            vid = self.host + vid
        html = self._html(vid)
        if not html:
            return {"list": []}

        name = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)', html, re.I)
        pic = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', html, re.I)
        desc = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']*)', html, re.I)

        vod_name = self._text(name.group(1)) if name else vid
        vod_pic = self._pic(pic.group(1)) if pic else ""
        vod_content = desc.group(1).strip() if desc else ""

        # 合集页：进入后拆出多集
        if "/creator/" in vid:
            episodes = self._list(html)
            parts = []
            for i, v in enumerate(episodes, 1):
                title = v.get("vod_name") or ("第{}集".format(i))
                parts.append("{}${}".format(title, v.get("vod_id")))
            if not parts:
                parts = ["播放${}".format(vid)]
            vod = {
                "vod_id": vid,
                "vod_name": vod_name,
                "vod_pic": vod_pic or (episodes[0].get("vod_pic") if episodes else ""),
                "type_name": "",
                "vod_year": "",
                "vod_content": vod_content,
                "vod_play_from": "合集",
                "vod_play_url": "#".join(parts),
            }
            return {"list": [vod]}

        vod = {
            "vod_id": vid,
            "vod_name": vod_name,
            "vod_pic": vod_pic,
            "type_name": "",
            "vod_year": "",
            "vod_content": vod_content,
            "vod_play_from": "一抖阁",
            "vod_play_url": "播放${}".format(vid),
        }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        pg = int(pg or 1)
        wd = quote(str(key), safe="")
        path = "/?s={}&post_type=video".format(wd) if pg == 1 else "/?s={}&post_type=video&paged={}".format(wd, pg)
        vods = self._list(self._html(path))
        return {
            "page": pg,
            "pagecount": pg + 1 if vods else pg,
            "limit": len(vods),
            "total": 999999 if vods else 0,
            "list": vods
        }

    def playerContent(self, flag, id, vipFlags):
        page = str(id).strip()
        if not page.startswith("http"):
            page = self.host + page
        html = self._html(page)
        url = ""
        # 方法1: 从 ld+json 提取
        for m in re.finditer(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S | re.I):
            data = m.group(1).strip()
            if '"contentUrl"' not in data and '"embedUrl"' not in data:
                continue
            cm = re.search(r'"contentUrl"\s*:\s*"([^"]+)"', data)
            if cm:
                url = cm.group(1)
                break
        # 方法2: 从页面直接找 mp4
        if not url:
            mp4_match = re.search(r'https?://[^\s"\'<>]+\.mp4[^\s"\'<>]*', html, re.I)
            if mp4_match:
                url = mp4_match.group(0)
        # 方法3: 从 goon player config 找
        if not url:
            cfg = re.search(r'var GoonPlayerConfig\s*=\s*({.*?});', html, re.S)
            if cfg:
                try:
                    import json
                    cdata = json.loads(cfg.group(1))
                    # 尝试从API获取视频源
                except Exception:
                    pass
        return {
            "parse": 0 if url else 1,
            "playUrl": "",
            "url": url or page,
            "header": self.headers
        }
