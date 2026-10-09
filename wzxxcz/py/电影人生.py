# coding=utf-8
"""
电影人生 dyrs360.cc | TVBox Python 爬虫 (V1.8 并发+重试版)
关键:
  - 破解服务端 SHA1 PoW 挑战 (attack_key)
  - 解析 /api/m3u8 302 跳转到 box.dyrs.com.de 的 master m3u8
  - 提取子 m3u8（分片URL为绝对路径，TVBox 可直接播放）
  - 支持电影/电视剧/综艺/动漫/短剧
  - 详情页逐条线路抓取剧集, 补全 JSON-LD 元数据
  - 新增: 多线程并发抓取所有线路 + 3次重试
"""
import re
import sys
import json
import time
import hashlib
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.append('..')

try:
    from base.spider import Spider
except ImportError:
    import requests as _rq
    try:
        import urllib3
        urllib3.disable_warnings()
    except Exception:
        pass

    class _BaseSpider:
        def __init__(self):
            self._session = None

        @property
        def _sess(self):
            if self._session is None:
                self._session = _rq.Session()
                self._session.verify = False
                adapter = _rq.adapters.HTTPAdapter(
                    pool_connections=10, pool_maxsize=10, max_retries=0)
                self._session.mount('https://', adapter)
                self._session.mount('http://', adapter)
            return self._session

        def fetch(self, url, headers=None, **kw):
            timeout = kw.pop('timeout', 15)
            r = self._sess.get(url, headers=headers, timeout=timeout, **kw)
            r.encoding = 'utf-8'
            return r

        def log(self, *a, **kw):
            try:
                print("[dyrs]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


# ========== 站点配置 ==========
HOST = "https://dyrs360.cc"
SION_ID = "6ac70c04fee28ec2343bb752"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/template/wzzycc/light.png"
BOX_HOST = "https://box.dyrs.com.de"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# ========== 分类 ==========
CLASSES = [
    {"type_id": "dianying",  "type_name": "电影"},
    {"type_id": "dianshiju", "type_name": "电视剧"},
    {"type_id": "zongyi",    "type_name": "综艺"},
    {"type_id": "dongman",   "type_name": "动漫"},
    {"type_id": "duanju",    "type_name": "短剧"},
]

_SORTS = [{"n": "默认", "v": ""},
          {"n": "热度最高", "v": "play_hot"},
          {"n": "豆瓣评分", "v": "group_douban"}]

_YEARS = [{"n": "全部", "v": ""}] + \
         [{"n": str(y), "v": str(y)} for y in range(2026, 1999, -1)]

_AREAS = [
    {"n": "全部", "v": ""},
    {"n": "中国大陆", "v": "中国大陆"}, {"n": "美国", "v": "美国"},
    {"n": "日本", "v": "日本"}, {"n": "英国", "v": "英国"},
    {"n": "中国香港", "v": "中国香港"}, {"n": "法国", "v": "法国"},
    {"n": "韩国", "v": "韩国"}, {"n": "加拿大", "v": "加拿大"},
    {"n": "印度", "v": "印度"}, {"n": "德国", "v": "德国"},
    {"n": "意大利", "v": "意大利"}, {"n": "中国台湾", "v": "中国台湾"},
]

_FILTERS_MAP = {
    "dianying":  ["全部", "剧情", "喜剧", "动作", "爱情", "惊悚", "犯罪", "恐怖",
                  "悬疑", "冒险", "奇幻", "科幻", "院线", "家庭", "历史", "战争",
                  "纪录片", "古装", "音乐", "动画", "传记", "武侠", "运动", "西部", "短片"],
    "dianshiju": ["全部", "剧情", "喜剧", "爱情", "犯罪", "悬疑", "家庭", "古装",
                  "惊悚", "动作", "奇幻", "科幻", "都市", "历史", "战争", "冒险",
                  "武侠", "恐怖", "青春", "传记", "谍战", "情感", "纪录", "军旅", "时装"],
    "zongyi":    ["全部", "真人秀", "脱口秀", "国产综艺", "喜剧", "晚会", "综艺",
                  "音乐", "纪录", "游戏", "生活", "港台综艺", "日韩综艺", "剧情",
                  "文化", "相声", "情感", "悬疑", "欧美综艺", "美食", "竞技"],
    "dongman":   ["全部", "动画", "冒险", "喜剧", "奇幻", "剧情", "科幻", "动作",
                  "儿童", "悬疑", "都市", "家庭", "国漫", "日常", "爱情", "玄幻",
                  "日漫", "音乐", "治愈", "短片", "古风", "犯罪", "武侠", "运动", "校园"],
    "duanju":    ["全部", "AI漫剧", "短剧", "剧情", "爱情", "爽文", "古装", "短片",
                  "悬疑", "喜剧", "奇幻", "都市", "玄幻", "犯罪", "家庭", "穿越",
                  "惊悚", "武侠", "科幻", "动作", "冒险", "恐怖", "青春", "历史"],
}

FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    FILTERS[tid] = [
        {"key": "class", "name": "分类",
         "value": [{"n": x, "v": "" if x == "全部" else x}
                   for x in _FILTERS_MAP.get(tid, ["全部"])]},
        {"key": "area", "name": "地区", "value": _AREAS},
        {"key": "year", "name": "年份", "value": _YEARS},
        {"key": "sort_field", "name": "排序", "value": _SORTS},
    ]


# ========== 正则 ==========
_RE_CARD = re.compile(
    r'href="(/(?:movie|tv)/[^"?]+?\.html)[^"]*"[^>]*title="([^"]*)"'
    r'[\s\S]{0,400}?<img[^>]*?(?:data-src|src)="([^"]+)"',
    re.S | re.I)

_RE_HREF = re.compile(r'href="(/(?:movie|tv)/[^"?]+?\.html)', re.I)
_RE_IMG = re.compile(
    r'<img[^>]*?alt="([^"]*)"[^>]*?(?:data-src|src)="([^"]+)"',
    re.S | re.I)

_RE_EPISODE_A = re.compile(r'<a\s+href="([^"]+)"([^>]*?)>(.*?)</a>', re.S | re.I)
_RE_DATA_ORIGIN = re.compile(r'data-origin="([^"]+)"', re.I)
_RE_DATA_TITLE = re.compile(r'data-title="([^"]+)"', re.I)
_RE_BTN_TITLE = re.compile(r'<button[^>]*>([^<]+)</button>', re.I)

_RE_PLAYER_AA = re.compile(r"aa\s*:\s*JSON\.parse\('(.*?)'\)", re.S)

_RE_H1 = re.compile(r'<h1[^>]*>([\s\S]*?)</h1>', re.I)
_RE_TITLE = re.compile(r'<title>(.*?)</title>', re.S | re.I)

_RE_PIC_ID = re.compile(r'/img/id/[A-Za-z0-9]+\.(?:jpg|png|webp)', re.I)

_RE_INTRO = re.compile(
    r'<span\s+class="font-bold text-\[#ff3347\] mr-1">简介:</span>\s*'
    r'([\s\S]*?)</div>', re.S | re.I)
_RE_INTRO_DIV = re.compile(
    r'<div[^>]*class="[^"]*text-\[#555\][^"]*reset-style[^"]*"[^>]*>'
    r'([\s\S]*?)</div>', re.S | re.I)
_RE_META_DESC = re.compile(
    r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']',
    re.I)

_RE_JSON_LD = re.compile(
    r'<script\s+type="application/ld\+json">\s*([\s\S]*?)\s*</script>',
    re.S | re.I)

_RE_DIRECTOR = re.compile(
    r'<span\s+class="text-\[#2e2e2e\]\s+font-bold">导演</span>\s*'
    r'<span[^>]*>([^<]*)</span>', re.S | re.I)
_RE_ACTOR = re.compile(
    r'<span\s+class="text-\[#2e2e2e\]\s+font-bold">主演</span>\s*'
    r'<span[^>]*>([\s\S]*?)</span>', re.S | re.I)

_RE_PAGE_LINK = re.compile(r'page=(\d+)', re.I)

_RE_POW_HASH = re.compile(r"var\s+hash\s*=\s*['\"]([a-f0-9]{40})['\"]")
_RE_POW_TARGET = re.compile(r"var\s+target\s*=\s*['\"]([a-f0-9]{40})['\"]")

_LINE_PRIORITY = ["超级线路", "王者TV加速", "lzm3u8", "1080zyk", "modum3u8",
                  "bfzym3u8", "dyttm3u8", "ffm3u8", "jsm3u8", "mtm3u8", "wztv"]
_LINE_ALIAS = {
    "超级线路": "超级线路", "王者TV加速": "王者TV加速",
    "lzm3u8": "量子M3U8", "1080zyk": "1080资源",
    "modum3u8": "魔都M3U8", "bfzym3u8": "暴风资源",
    "dyttm3u8": "电影天堂", "ffm3u8": "非凡M3U8",
    "jsm3u8": "极速M3U8", "mtm3u8": "茅台M3U8", "wztv": "王者TV",
}


class Spider(Spider):

    def getName(self):
        return "电影人生"

    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}

        self.site_url = (self.extend.get("site") or HOST).rstrip("/")
        self.sion_id  = self.extend.get("sion_id") or SION_ID
        self.headers = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": self.site_url + "/",
            "Upgrade-Insecure-Requests": "1",
        }
        self.default_pic = DEFAULT_PIC
        self._play_cache = {}
        self._warmed = False
        self._executor = ThreadPoolExecutor(max_workers=10)
        self.log("init: site=%s sid=%s" % (self.site_url, self.sion_id))

    # ================= PoW =================
    def _warm_up(self):
        if self._warmed:
            return
        try:
            self._fetch(self.site_url + "/?sion_id=" + self.sion_id, timeout=15)
            self._warmed = True
            self.log("预热完成")
        except Exception as e:
            self.log("预热失败: %s" % e)

    def _solve_pow(self, html):
        m1 = _RE_POW_HASH.search(html)
        m2 = _RE_POW_TARGET.search(html)
        if not m1 or not m2:
            return None

        hash_prefix = m1.group(1)
        target = m2.group(1)

        max_i = 10 * 1000 * 1000
        start = time.time()
        prefix_b = hash_prefix.encode()

        for i in range(max_i):
            s = hashlib.sha1(prefix_b + str(i).encode()).hexdigest()
            if s == target:
                self.log("PoW 破解成功: i=%d 耗时=%.2fs" % (i, time.time() - start))
                return i
            if (i + 1) % 1000000 == 0:
                if time.time() - start > 60:
                    self.log("PoW 超时")
                    return None
        return None

    def _fetch(self, url, timeout=60, headers=None):
        try:
            h = dict(self.headers)
            if headers:
                h.update(headers)
            rsp = self.fetch(url, headers=h, timeout=timeout)
            text = ""
            if hasattr(rsp, "text"):
                text = rsp.text or ""
            elif hasattr(rsp, "content"):
                text = rsp.content.decode("utf-8", "ignore")

            if ("正在检测" in text) or ("sha1(hash" in text and "attack_key" in text):
                self.log("⚠️ 遇到 PoW 挑战, 开始破解...")
                attack_key = self._solve_pow(text)
                if attack_key is not None:
                    sep = "&" if "?" in url else "?"
                    new_url = url + sep + "attack_key=" + str(attack_key)
                    rsp2 = self.fetch(new_url, headers=h, timeout=timeout)
                    if hasattr(rsp2, "text"):
                        text = rsp2.text or ""
                    elif hasattr(rsp2, "content"):
                        text = rsp2.content.decode("utf-8", "ignore")
            return text
        except Exception as e:
            self.log("fetch FAIL %s -> %s" % (url, e))
            return ""

    def _fix_url(self, url):
        if not url:
            return ""
        url = url.strip().replace("&amp;", "&")
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("http"):
            return url
        if url.startswith("/"):
            return self.site_url + url
        return urllib.parse.urljoin(self.site_url + "/", url)

    def _clean(self, s):
        if not s:
            return ""
        s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
        s = re.sub(r"<[^>]+>", "", s)
        s = (s.replace("&nbsp;", " ").replace("\xa0", " ")
              .replace("&amp;", "&").replace("&quot;", '"')
              .replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">"))
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n{2,}", "\n", s)
        return s.strip()

    # ================= 列表提取 =================
    def _extract_videos(self, html):
        videos = []
        seen = set()
        if not html:
            return videos

        matches = _RE_CARD.findall(html)
        self.log("  完整卡片: %d 条" % len(matches))

        if matches:
            for href, alt, pic in matches:
                href = href.replace("&amp;", "&")
                if href in seen:
                    continue
                seen.add(href)
                videos.append({
                    "vod_id":      href,
                    "vod_name":    self._clean(alt)[:100],
                    "vod_pic":     self._fix_url(pic) or self.default_pic,
                    "vod_remarks": "",
                })
            return videos

        hrefs = _RE_HREF.findall(html)
        imgs = _RE_IMG.findall(html)
        self.log("  兜底: href=%d img=%d" % (len(hrefs), len(imgs)))

        if hrefs and imgs:
            for i, href in enumerate(hrefs):
                if href in seen:
                    continue
                seen.add(href)
                alt, pic = ("", "")
                if i < len(imgs):
                    alt, pic = imgs[i]
                videos.append({
                    "vod_id":      href,
                    "vod_name":    self._clean(alt)[:100] or href,
                    "vod_pic":     self._fix_url(pic) or self.default_pic,
                    "vod_remarks": "",
                })
            return videos

        for href in hrefs:
            if href in seen:
                continue
            seen.add(href)
            videos.append({
                "vod_id":      href,
                "vod_name":    href.split("/")[-1].split("-")[0],
                "vod_pic":     self.default_pic,
                "vod_remarks": "",
            })
        return videos

    def _page_count(self, html):
        if not html:
            return 1
        pages = _RE_PAGE_LINK.findall(html)
        if pages:
            try:
                return max(int(p) for p in pages) + 1
            except Exception:
                pass
        return 9999

    # ================= TVBox 接口 =================
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        self._warm_up()
        url = "%s/?sion_id=%s" % (self.site_url, self.sion_id)
        html = self._fetch(url)
        self.log("home HTML 长度: %d" % len(html))
        videos = self._extract_videos(html)
        return {"list": videos}

    def categoryContent(self, tid, pg, filter, extend):
        self._warm_up()
        page = int(pg) if pg else 1
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        if not extend:
            extend = {}

        for k in list(extend.keys()):
            if extend[k] in ("", None, "全部"):
                del extend[k]

        params = {
            "page": page - 1,
            "sion_id": self.sion_id,
        }
        if extend.get("class"):
            params["class"] = extend["class"]
        if extend.get("year"):
            params["year"] = extend["year"]
        if extend.get("area"):
            params["area"] = extend["area"]
        if extend.get("sort_field"):
            params["sort_field"] = extend["sort_field"]

        url = "%s/%s.html?%s" % (self.site_url, tid,
                                 urllib.parse.urlencode(params))
        self.log("category: %s" % url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))

        videos = self._extract_videos(html)
        pagecount = self._page_count(html)
        self.log("  最终: %d 条, 总页数: %d" % (len(videos), pagecount))

        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 24, "total": pagecount * 24,
        }

    def searchContent(self, key, quick, pg="1"):
        self._warm_up()
        page = int(pg) if pg else 1
        keyword = urllib.parse.quote(key)
        url = "%s/s?name=%s&sion_id=%s&page=%d" % (
            self.site_url, keyword, self.sion_id, page - 1)
        self.log("search: %s" % url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))
        videos = self._extract_videos(html)
        return {
            "list": videos, "page": page,
            "pagecount": self._page_count(html),
            "limit": 24, "total": 999,
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ================= 详情 (并发加速版) =================
    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0])
        base_url = vod_id if vod_id.startswith("http") else self._fix_url(vod_id)
        self.log("detail: %s" % base_url)

        html = self._fetch(base_url)
        self.log("  HTML 长度: %d" % len(html))
        if not html:
            return {"list": []}

        # ---------- 元信息 ----------
        meta = {
            "name": "", "alternateName": "", "genre": "", "year": "",
            "region": "", "director": "", "actors": [],
            "description": "", "pic": "", "rating": "",
        }

        json_ld_raw = _RE_JSON_LD.search(html)
        if json_ld_raw:
            try:
                ld = json.loads(json_ld_raw.group(1))
                meta["name"] = ld.get("name", "")
                meta["alternateName"] = ld.get("alternateName", "")
                meta["genre"] = ", ".join(ld.get("genre", [])) if isinstance(ld.get("genre"), list) else ld.get("genre", "")
                if ld.get("releaseDate"):
                    meta["year"] = str(ld["releaseDate"]).split("-")[0]
                meta["region"] = ld.get("countryOfOrigin", "")
                if ld.get("director"):
                    meta["director"] = ld["director"].get("name", "") if isinstance(ld["director"], dict) else str(ld["director"])
                if ld.get("actor"):
                    meta["actors"] = [a.get("name", "") for a in ld["actor"]] if isinstance(ld["actor"], list) else [str(ld["actor"])]
                meta["description"] = ld.get("description", "")
                meta["pic"] = ld.get("image", "")
                if ld.get("aggregateRating"):
                    meta["rating"] = str(ld["aggregateRating"].get("ratingValue", ""))
                self.log("  JSON-LD 解析成功")
            except Exception as e:
                self.log("  JSON-LD 解析失败: %s" % e)

        if not meta["name"]:
            m = _RE_H1.search(html)
            if m:
                meta["name"] = self._clean(m.group(1))
        if not meta["name"]:
            m = _RE_TITLE.search(html)
            if m:
                meta["name"] = self._clean(m.group(1).split("_")[0].split("-")[0])
        meta["name"] = re.sub(r"\s*\(\d{4}\)\s*$", "", meta["name"]).strip() or vod_id

        if not meta["pic"]:
            m = _RE_PIC_ID.search(html)
            if m:
                meta["pic"] = self.site_url + m.group(0)
        if not meta["pic"]:
            meta["pic"] = self.default_pic

        if not meta["description"]:
            m = _RE_INTRO.search(html)
            if m:
                meta["description"] = self._clean(m.group(1))
        if not meta["description"]:
            m = _RE_INTRO_DIV.search(html)
            if m:
                meta["description"] = self._clean(m.group(1))
        if not meta["description"]:
            m = _RE_META_DESC.search(html)
            if m:
                meta["description"] = self._clean(m.group(1))

        if not meta["director"]:
            m = _RE_DIRECTOR.search(html)
            if m:
                meta["director"] = self._clean(m.group(1))

        if not meta["actors"]:
            m = _RE_ACTOR.search(html)
            if m:
                raw = self._clean(m.group(1))
                meta["actors"] = [a.strip() for a in re.split(r"[,，、\s]+", raw) if a.strip()]

        intro_parts = []
        if meta["alternateName"]:
            intro_parts.append("别名：%s" % meta["alternateName"])
        if meta["genre"]:
            intro_parts.append("类型：%s" % meta["genre"])
        if meta["year"]:
            intro_parts.append("年份：%s" % meta["year"])
        if meta["region"]:
            intro_parts.append("地区：%s" % meta["region"])
        if meta["rating"]:
            intro_parts.append("评分：%s" % meta["rating"])
        if meta["director"]:
            intro_parts.append("导演：%s" % meta["director"])
        if meta["actors"]:
            intro_parts.append("主演：%s" % "、".join(meta["actors"]))

        content = INTRO_PREFIX + "\n"
        if intro_parts:
            content += "\n".join(intro_parts) + "\n\n"
        if meta["description"]:
            content += meta["description"]

        # ---------- 提取线路 ----------
        origin_map = {}
        try:
            pattern_tab = re.compile(
                r'<a\s+href="([^"]*?[?&]origin=([^"&]+)[^"]*?)"[^>]*>\s*'
                r'<button[^>]*data-origin="([^"]+)"',
                re.S | re.I)
            for m in pattern_tab.finditer(html):
                href = m.group(1).replace("&amp;", "&")
                o_url = urllib.parse.unquote(m.group(2))
                o_btn = m.group(3)
                origin = o_btn or o_url
                if not href.startswith("http"):
                    href = self.site_url + href
                origin_map[origin] = href
        except Exception as e:
            self.log("  originTabs 解析失败: %s" % e)

        # 兜底：从剧集 href 里反推 origin
        if not origin_map:
            base_path = base_url.split("?")[0]
            sion_match = re.search(r'sion_id=([^&]+)', base_url)
            sion = sion_match.group(1) if sion_match else self.sion_id
            seen_o = set()
            for m in re.finditer(r'data-origin="([^"]+)"', html):
                o = m.group(1)
                if o and o not in seen_o:
                    seen_o.add(o)
                    origin_map[o] = "%s?origin=%s&sion_id=%s" % (
                        base_path, urllib.parse.quote(o), sion)

        self.log("  发现 %d 条线路: %s" % (len(origin_map), list(origin_map.keys())))

        # ---------- 默认线路：从详情页直接解析 ----------
        groups = {}
        default_eps = self._parse_episodes_from_html(html, target_origin=None)
        if default_eps:
            default_origin = ""
            for ep_name, ep_href in default_eps:
                m = re.search(r'origin=([^&]+)', ep_href)
                if m:
                    default_origin = urllib.parse.unquote(m.group(1))
                    break
            if not default_origin:
                m = re.search(r'data-origin="([^"]+)"[^>]*data-title="', html)
                if m:
                    default_origin = m.group(1)
            if default_origin:
                groups[default_origin] = default_eps
                self.log("  默认线路 [%s]: %d 集" % (default_origin, len(default_eps)))

        # ---------- 剩余线路：并发抓取 + 3次重试 ----------
        tasks = [(o, h) for o, h in origin_map.items() if o not in groups]
        if tasks:
            self.log("  🚀 并发抓取 %d 条线路（3次重试）..." % len(tasks))
            future_map = {
                self._executor.submit(self._fetch_line_with_retry, o, h): o
                for o, h in tasks
            }
            for fut in as_completed(future_map):
                origin = future_map[fut]
                try:
                    eps = fut.result()
                    if eps:
                        groups[origin] = eps
                        self.log("    ✅ [%s] %d 集" % (origin, len(eps)))
                    else:
                        self.log("    ⚠️ [%s] 无剧集" % origin)
                except Exception as e:
                    self.log("    ❌ [%s] 异常: %s" % (origin, e))

        self.log("  最终剧集: %s" % {k: len(v) for k, v in groups.items()})

        if not groups:
            return {"list": []}

        def _origin_key(x):
            if x in _LINE_PRIORITY:
                return _LINE_PRIORITY.index(x)
            return 999

        sorted_origins = sorted(groups.keys(), key=_origin_key)

        play_from = []
        play_url = []
        for origin in sorted_origins:
            eps = groups[origin]
            alias = _LINE_ALIAS.get(origin, origin)
            play_from.append(alias)
            play_url.append("#".join("%s$%s" % (n, h) for n, h in eps))

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": meta["name"],
            "vod_pic": meta["pic"],
            "vod_content": content,
            "vod_actor": "、".join(meta["actors"]),
            "vod_director": meta["director"],
            "vod_remarks": "%d条线路" % len(groups),
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url":  "$$$".join(play_url),
        }]}

    # ============ 单线路抓取（带3次重试） ============
    def _fetch_line_with_retry(self, origin, href):
        """单线路抓取 + 解析，最多重试3次"""
        max_retries = 3
        last_err = ""
        for attempt in range(max_retries + 1):
            try:
                sub_html = self._fetch(href)
                if not sub_html:
                    raise RuntimeError("empty response")
                eps = self._parse_episodes_from_html(sub_html, target_origin=origin)
                if not eps:
                    eps = self._parse_episodes_from_html(sub_html, target_origin=None)
                if eps:
                    if attempt > 0:
                        self.log("    [%s] 第%d次请求成功" % (origin, attempt + 1))
                    return eps
                else:
                    raise RuntimeError("no episodes parsed")
            except Exception as e:
                last_err = str(e)
                if attempt < max_retries:
                    wait = 0.3 * (attempt + 1)
                    self.log("    [%s] 第%d次失败(%s), %.1fs 后重试..."
                             % (origin, attempt + 1, e, wait))
                    time.sleep(wait)
                else:
                    self.log("    [%s] 重试 %d 次仍失败: %s" % (origin, max_retries, last_err))
        return []

    # ============ 从 HTML 解析剧集 ============
    def _parse_episodes_from_html(self, html, target_origin=None):
        eps = []
        try:
            for m in _RE_EPISODE_A.finditer(html):
                href = m.group(1)
                attrs = m.group(2)
                inner = m.group(3)

                mo = _RE_DATA_ORIGIN.search(attrs)
                if not mo:
                    continue
                origin = mo.group(1)
                if target_origin and origin != target_origin:
                    continue

                href = href.replace("&amp;", "&")
                if href.startswith("/"):
                    href = self.site_url + href

                ep_name = ""
                mt = _RE_DATA_TITLE.search(attrs)
                if mt:
                    ep_name = self._clean(mt.group(1))
                if not ep_name:
                    mt = _RE_BTN_TITLE.search(inner)
                    if mt:
                        ep_name = self._clean(mt.group(1))
                if not ep_name:
                    ep_name = "第%s集" % (len(eps) + 1)

                eps.append((ep_name, href))
        except Exception as e:
            self.log("    _parse_episodes err: %s" % e)
        return eps

    # ================= 播放 (保持原样，已验证能播) =================
    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith("http") else self._fix_url(id)
        self.log("player: %s" % play_page)

        now = int(time.time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 600:
                return res

        html = self._fetch(play_page)
        api_url = self._extract_api_m3u8(html) if html else ""
        self.log("  api_url: %s" % (api_url[:200] if api_url else "EMPTY"))

        if api_url:
            if api_url.startswith("http") and ".m3u8" in api_url.lower():
                res = {
                    "parse": 0,
                    "playUrl": "",
                    "url": api_url,
                    "header": {"User-Agent": UA, "Referer": self.site_url + "/"},
                }
                self._play_cache[play_page] = (now, res)
                return res

            if api_url.startswith("/"):
                api_url = self.site_url + api_url

            real_m3u8 = self._resolve_to_real_m3u8(api_url, referer=play_page)
            if real_m3u8:
                res = {
                    "parse": 0,
                    "playUrl": "",
                    "url": real_m3u8,
                    "header": {
                        "User-Agent": UA,
                        "Referer": BOX_HOST + "/",
                    },
                }
                self._play_cache[play_page] = (now, res)
                self.log("  => 直链 m3u8: %s" % real_m3u8[:160])
                return res

        res = {"parse": 1, "playUrl": "", "url": play_page,
               "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}
        self._play_cache[play_page] = (now, res)
        return res

    def _extract_api_m3u8(self, html):
        if not html:
            return ""
        m = _RE_PLAYER_AA.search(html)
        if not m:
            m2 = re.search(r'(/api/m3u8\?[^"\'\\\s]+)', html)
            if m2:
                return m2.group(1).replace("&amp;", "&")
            return ""
        raw = m.group(1)
        raw = (raw.replace("\\\\u0026", "&").replace("\\u0026", "&")
                  .replace("\\\\u0022", '"').replace("\\u0022", '"')
                  .replace("\\/", "/"))
        try:
            aa = json.loads(raw)
            return aa.get("url", "")
        except Exception:
            m2 = re.search(r'"url"\s*:\s*"([^"]+)"', raw)
            return m2.group(1) if m2 else ""

    def _resolve_to_real_m3u8(self, api_url, referer=None):
        try:
            try:
                rsp = self.fetch(api_url, headers={
                    "User-Agent": UA,
                    "Referer": referer or (self.site_url + "/"),
                    "Accept": "text/html,application/json,*/*",
                }, timeout=15, allow_redirects=False)
            except TypeError:
                rsp = self.fetch(api_url, headers={
                    "User-Agent": UA,
                    "Referer": referer or (self.site_url + "/"),
                    "Accept": "text/html,application/json,*/*",
                }, timeout=15)
        except Exception as e:
            self.log("resolve#1 fail: %s" % e)
            return ""

        loc = ""
        if hasattr(rsp, "headers"):
            loc = (rsp.headers.get("Location", "") or
                   rsp.headers.get("location", ""))

        if not loc:
            text = ""
            try:
                text = rsp.text if hasattr(rsp, "text") else ""
            except Exception:
                pass
            if "#EXTM3U" in text:
                self.log("api 直接返回 m3u8")
                return api_url
            return ""

        if loc.startswith("//"):
            loc = "https:" + loc
        loc = loc.replace("&amp;", "&")
        self.log("  box master: %s" % loc[:150])

        try:
            rsp2 = self.fetch(loc, headers={
                "User-Agent": UA,
                "Referer": api_url,
                "Accept": "*/*",
            }, timeout=15)
            text2 = ""
            if hasattr(rsp2, "text"):
                text2 = rsp2.text or ""
            elif hasattr(rsp2, "content"):
                text2 = rsp2.content.decode("utf-8", "ignore")
        except Exception as e:
            self.log("resolve#2 fail: %s" % e)
            return loc

        if "#EXTM3U" not in text2:
            self.log("  master 无 m3u8 头, 直接返回 master URL")
            return loc

        lines = [ln.strip() for ln in text2.split("\n") if ln.strip()]
        for i, line in enumerate(lines):
            if line.startswith("#EXT-X-STREAM-INF"):
                if i + 1 < len(lines):
                    sub = lines[i + 1].strip()
                    if sub.startswith("http"):
                        full = sub
                    elif sub.startswith("/"):
                        full = BOX_HOST + sub
                    else:
                        full = BOX_HOST + "/" + sub
                    self.log("  子 m3u8: %s" % full[:160])
                    return full

        self.log("  无子 m3u8, 返回 master")
        return loc

    def localProxy(self, param):
        try:
            url = ""
            if isinstance(param, dict):
                url = param.get("url", "")
            else:
                for pair in str(param).split("&"):
                    if "=" in pair:
                        k, v = pair.split("=", 1)
                        if k == "url":
                            url = v
            if not url:
                return [200, "image/jpeg", b"", ""]
            url = urllib.parse.unquote(url) if "%" in url else url
            url = self._fix_url(url)
            rsp = self.fetch(url, headers={
                "User-Agent": UA, "Referer": self.site_url + "/"}, timeout=15)
            content = rsp.content
            ctype = rsp.headers.get("Content-Type", "image/jpeg")
            if not ctype.startswith("image/"):
                ctype = "image/jpeg"
            return [200, ctype, content, ""]
        except Exception:
            return [200, "image/jpeg", b"", ""]

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url or url.startswith("http")

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()
