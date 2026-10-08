# -*- coding: utf-8 -*-
"""
Cosplaytele (cosplaytele.com) - COS·涩涩 Spider
站点: WordPress(Flatsome 主题)
注意: 该站 TLS 对 curl_cffi 会 SSL_ERROR_SYSCALL 断连，必须用标准 requests
列表: /category/{cosplay,cosplay-ero,cosplay-nude,video-cosplayy,genshin-impact,...}/
      分页 /page/N/；榜单 /24-hours/ /3-day/ /7-day/
      卡片 div.post-item → .post-title a + img
详情: /SLUG/  正文图 /wp-content/uploads/YYYY/MM/NAME-N_result.webp
搜索: /?s=KEYWORD
"""
import re, json, requests
try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        def init(self, extend=""): pass
        def destroy(self): pass
        def getName(self): return ""
        def homeContent(self, filter=False): return {"class": []}
        def homeVideoContent(self, tid="", pg="1", filter=False, extend=None): return {"list": []}
        def categoryContent(self, tid, pg="1", filter=False, extend=None): return {"list": []}
        def detailContent(self, ids): return {"list": []}
        def searchContent(self, key, quick=False, pg="1"): return {"list": []}
        def playerContent(self, flag, id, vipFlags=None): return {"parse": 1, "url": "", "header": {}, "content": ""}
        def localProxy(self, params): return []

from bs4 import BeautifulSoup

BASE = "https://cosplaytele.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": BASE + "/",
}

# 一级分类（带图标）
CATS = [
    ("category/cosplay", "🎭 Cosplay"),
    ("category/cosplay-ero", "💋 Cosplay Ero"),
    ("category/cosplay-nude", "🔞 Cosplay Nude"),
    ("category/video-cosplayy", "🎥 Video Cosplay"),
    ("24-hours", "🔥 24小时热门"),
    ("3-day", "⭐ 3天热门"),
    ("7-day", "💎 7天热门"),
    ("best-cosplayer", "🏆 最佳Coser"),
    ("category/genshin-impact", "⚔️ 原神"),
    ("category/azur-lane", "⚓ 碧蓝航线"),
    ("category/fate-grand-order", "🗡️ Fate/GO"),
]

# 二级筛选：作品
WORKS = [
    ("category/genshin-impact", "⚔️ 原神"),
    ("category/azur-lane", "⚓ 碧蓝航线"),
    ("category/fate-grand-order", "🗡️ Fate/GO"),
    ("category/cosplay-ero", "💋 Ero"),
    ("category/cosplay-nude", "🔞 Nude"),
    ("category/video-cosplayy", "🎥 Video"),
]


def _get(url, referer=None, timeout=25):
    """该站握手拒绝 curl_cffi，仅用标准 requests"""
    h = dict(HEADERS)
    if referer:
        h["Referer"] = referer
    try:
        return requests.get(url, headers=h, timeout=timeout)
    except Exception:
        return None


def _pic(node):
    if node is None:
        return ""
    img = node.find("img")
    if img is None:
        return ""
    v = img.get("src") or img.get("data-src") or img.get("data-lazy") or ""
    if v.startswith("//"):
        v = "https:" + v
    elif v.startswith("/"):
        v = BASE + v
    return re.sub(r"-\d+x\d+(\.\w+)$", r"\1", v)


class Spider(BaseSpider):
    def getName(self):
        return "Cosplaytele"

    def init(self, extend=""):
        self.base_url = BASE
        self._cache = {}
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.session.trust_env = False

    def destroy(self):
        if self.session:
            self.session.close()
            self.session = None

    # 关键：声明非视频，宿主才走图片相册而不是流嗅探
    def isVideoFormat(self, url):
        return True

    def manualVideoCheck(self):
        return True

    CHUNK = 150

    def _album_eps(self, token, n):
        if n <= self.CHUNK:
            return "查看图集(%d张)$%s|1" % (n, token)
        eps = []
        for i in range(0, n, self.CHUNK):
            g = i // self.CHUNK + 1
            eps.append("第%d组(%d-%d)$%s|%d" % (g, i + 1, min(i + self.CHUNK, n), token, g))
        return "#".join(eps)

    def homeContent(self, filter=False):
        result = {"class": [{"type_id": t, "type_name": n} for t, n in CATS]}
        if filter:
            work_f = [{
                "key": "work",
                "name": "🎮 作品",
                "value": [{"n": "全部", "v": ""}] + [{"n": n, "v": v} for v, n in WORKS],
            }]
            result["filters"] = {t: work_f for t, _ in CATS}
        return result

    def homeVideoContent(self, tid="", pg="1", filter=False, extend=None):
        return self.categoryContent("category/cosplay", "1")

    def _parse_items(self, soup, remark="🖼️"):
        out, seen = [], set()
        # 分类页主列表在 #post-list 内（同页热门/随机推荐区块也用 .post-item，会串味）
        # 榜单页(24-hours/3-day/7-day/best-cosplayer)没有 #post-list → 回退全页
        scope = soup.select_one("#post-list") or soup
        for d in scope.select(".post-item"):
            a = d.select_one(".post-title a") or d.find("a", href=True)
            if not a:
                continue
            href = a.get("href", "")
            if href.startswith("/"):
                href = BASE + href
            m = re.search(r"cosplaytele\.com/([a-zA-Z0-9\-_%]+)/?$", href)
            if not m:
                continue
            slug = m.group(1)
            if slug in seen or slug in ("category", "page", "tag"):
                continue
            seen.add(slug)
            title = a.get_text(strip=True)
            if not title:
                continue
            # 标题里的 "62 photos" / "3 videos" → 备注
            pm = re.search(r"(\d+)\s*photos?", title, re.I)
            vm = re.search(r"(\d+)\s*videos?", title, re.I)
            bits = []
            if pm:
                bits.append(pm.group(1) + "P")
            if vm:
                bits.append("🎥" + vm.group(1))
            out.append({
                "vod_id": slug,
                "vod_name": re.sub(r'\s*[“"].*?[”"]\s*$', "", title)[:90],
                "vod_pic": _pic(d),
                "vod_remarks": " ".join(bits) if bits else remark,
                "type_name": "COS",
            })
        return out

    def categoryContent(self, tid, pg="1", filter=False, extend=None):
        result = {"list": [], "page": str(pg), "pagecount": 9999, "limit": 24, "total": 999999}
        pg_int = int(pg) if str(pg).isdigit() else 1
        if extend and isinstance(extend, dict) and extend.get("work"):
            tid = extend["work"]
        try:
            url = f"{BASE}/{tid.strip('/')}/"
            if pg_int > 1:
                url += f"page/{pg_int}/"
            r = _get(url, referer=BASE + "/")
            if r is None or r.status_code != 200:
                return result
            soup = BeautifulSoup(r.text, "html.parser")
            result["list"] = self._parse_items(soup)
        except Exception as e:
            print(f"[cosplaytele] categoryContent error: {e}")
        return result

    def detailContent(self, ids, filter=False):
        vid = ids[0] if isinstance(ids, (list, tuple)) and ids else ids
        vid = str(vid).strip().strip("[]'\"")
        slug = vid.rstrip("/").split("/")[-1]
        try:
            r = _get(f"{BASE}/{slug}/", referer=BASE + "/")
            if r is None or r.status_code != 200:
                return {"list": []}
            soup = BeautifulSoup(r.text, "html.parser")

            vod_name = soup.title.get_text(strip=True) if soup.title else slug
            vod_name = re.sub(r"\s*-\s*Cosplaytele\s*$", "", vod_name).strip()

            # 正文图：_result 后缀是本站压制的图集图，排除主题/图标
            entry = soup.select_one(".entry-content") or soup
            images = []
            for img in entry.find_all("img"):
                for attr in ("src", "data-src", "data-lazy"):
                    v = img.get(attr, "")
                    if not v or "wp-content/uploads" not in v:
                        continue
                    if "_result" not in v:
                        continue
                    if v.startswith("//"):
                        v = "https:" + v
                    v = re.sub(r"-\d+x\d+(\.\w+)$", r"\1", v)
                    if v not in images:
                        images.append(v)
                    break
            if not images:
                for v in re.findall(r"https://cosplaytele\.com/wp-content/uploads/[^\s\"'<>]+?_result\.(?:webp|jpg|jpeg|png)", r.text):
                    if v not in images:
                        images.append(v)

            # 按 -N_result 序号排
            def _k(u):
                m = re.search(r"-(\d+)_result", u)
                return int(m.group(1)) if m else 0
            images.sort(key=_k)

            # 视频
            videos = list(dict.fromkeys(
                re.findall(r"https?://[^\s\"'<>]+\.(?:mp4|m3u8)", r.text)))

            cats = [a.get_text(strip=True) for a in soup.find_all("a", href=re.compile(r"/category/"))]
            cats = list(dict.fromkeys([c for c in cats if c]))[:5]

            self._cache[slug] = images
            play_from = "图集"
            play_url = self._album_eps(slug, len(images))
            if videos:
                play_from += "$$$视频"
                play_url += "$$$" + "#".join(f"视频{i+1}${u}" for i, u in enumerate(videos))

            return {"list": [{
                "vod_id": slug,
                "vod_name": vod_name,
                "vod_pic": images[0] if images else "",
                "vod_remarks": f"{len(images)}张" + (f" 🎥{len(videos)}" if videos else ""),
                "type_name": "COS",
                "vod_actor": " / ".join(cats),
                "vod_content": "",
                "vod_play_from": play_from,
                "vod_content_type": "image",
                "vod_play_url": play_url,
            }]}
        except Exception as e:
            print(f"[cosplaytele] detailContent error: {e}")
            return {"list": []}

    def searchContent(self, key, quick=False, pg="1"):
        result = {"list": [], "page": str(pg)}
        try:
            pg_int = int(pg) if str(pg).isdigit() else 1
            kw = requests.utils.quote(str(key))
            url = f"{BASE}/page/{pg_int}/?s={kw}" if pg_int > 1 else f"{BASE}/?s={kw}"
            r = _get(url, referer=BASE + "/")
            if r is None or r.status_code != 200:
                return result
            soup = BeautifulSoup(r.text, "html.parser")
            result["list"] = self._parse_items(soup, remark="🔍")
        except Exception as e:
            print(f"[cosplaytele] searchContent error: {e}")
        return result

    def playerContent(self, flag, id, vipFlags=None):
        """pics:// 相册协议 —— 漫画式连续看图，不走视频流"""
        raw = str(id or "")
        token, _, grp = raw.partition("|")
        try:
            grp = int(grp or 1)
        except Exception:
            grp = 1
        images = self._cache.get(token)
        if not images:
            self.detailContent([token])
            images = self._cache.get(token) or []
        hdr = json.dumps({"User-Agent": HEADERS["User-Agent"], "Referer": BASE + "/"})
        if not images:
            return {"parse": 0, "playUrl": "", "url": "", "header": hdr}
        if len(images) > self.CHUNK:
            images = images[(grp - 1) * self.CHUNK: grp * self.CHUNK]
        return {
            "parse": 0,
            "playUrl": "",
            "url": "pics://" + "&&".join(images),
            "header": hdr,
            "contentType": "image",
            "format": "",
        }

    def localProxy(self, params):
        return []
