# coding=utf-8
# ================== 影视·正经·豆花电影 · TVBox ==================
# 🏷️ 源头：豆花电影网 https://dhvideo.cc （PHP 模板站 douhua，App 端同名）
# 👤 作者：小橙子  |  📅 2026-10-29
# 🏷️ 平台：TVBox / 影视仓  ·  csp_Spider
# 🔍 站型：PHP 服务端渲染 + 前置防火墙（PoW 挑战 429） + box.dyrs.com.de 中继
# 🎬 关键：① 破解服务端 SHA1 PoW 挑战（var hash + var target → attack_key）
#         ② 播放页 window.xg_video_player_doc.aa.url → 302 到 box master m3u8
#         ③ 递归取最高码率子 m3u8 → POST /api/clean（gzip 原文）→ 换取官方 /api/clean/httpurl 直链
# 📦 内容：电影 / 电视剧 / 综艺 / 动漫 / 短剧（多线路 7~11 条）
# ==========================================================
import re
import sys
import json
import time
import gzip
import hashlib
import urllib.parse

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

    class _BaseSpider(object):
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

        def post(self, url, data=None, files=None, headers=None, **kw):
            timeout = kw.pop('timeout', 15)
            r = self._sess.post(url, data=data, files=files,
                                headers=headers, timeout=timeout, **kw)
            r.encoding = 'utf-8'
            return r

        def log(self, *a, **kw):
            try:
                print("[douhua]", *a)
            except Exception:
                pass

    Spider = _BaseSpider

# ---------------- 站点常量 ----------------
HOST = "https://dhvideo.cc"
SION_ID = "6ac4b6643b9fea31774d1157"
BOX_HOST = "https://box.dyrs.com.de"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")
PLAY_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
           "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/template/douhua/douhua.me.png"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# 频道（站点真实路径 = /{type_id}.html）
CLASSES = [
    {"type_id": "dianying",  "type_name": "电影"},
    {"type_id": "dianshiju", "type_name": "电视剧"},
    {"type_id": "zongyi",    "type_name": "综艺"},
    {"type_id": "dongman",   "type_name": "动漫"},
    {"type_id": "duanju",    "type_name": "短剧"},
]

# 排序：站点只有这两项（默认 / 热度最高）
_SORTS = [{"n": "默认", "v": ""},
          {"n": "热度最高", "v": "play_hot"}]

# 年份：站点原样给的是 2026 → 2000 逐年份 + 十年段 + "更早"
_YEARS = [{"n": "全部", "v": ""}] + \
         [{"n": str(y), "v": str(y)} for y in range(2026, 1999, -1)] + \
         [{"n": "2020年代", "v": "2020年代"},
          {"n": "2010年代", "v": "2010年代"},
          {"n": "2000年代", "v": "2000年代"},
          {"n": "90年代",   "v": "90年代"},
          {"n": "80年代",   "v": "80年代"},
          {"n": "更早",     "v": "更早"}]

_AREAS = [
    {"n": "全部", "v": ""},
    {"n": "中国大陆", "v": "中国大陆"}, {"n": "美国", "v": "美国"},
    {"n": "日本", "v": "日本"}, {"n": "韩国", "v": "韩国"},
    {"n": "英国", "v": "英国"}, {"n": "法国", "v": "法国"},
    {"n": "中国香港", "v": "中国香港"}, {"n": "中国台湾", "v": "中国台湾"},
    {"n": "泰国", "v": "泰国"}, {"n": "印度", "v": "印度"},
    {"n": "德国", "v": "德国"}, {"n": "意大利", "v": "意大利"},
    {"n": "加拿大", "v": "加拿大"}, {"n": "澳大利亚", "v": "澳大利亚"},
    {"n": "俄罗斯", "v": "俄罗斯"}, {"n": "西班牙", "v": "西班牙"},
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
for _c in CLASSES:
    _tid = _c["type_id"]
    FILTERS[_tid] = [
        {"key": "class", "name": "类型",
         "value": [{"n": x, "v": "" if x == "全部" else x}
                   for x in _FILTERS_MAP.get(_tid, ["全部"])]},
        {"key": "area", "name": "地区", "value": _AREAS},
        {"key": "year", "name": "年份", "value": _YEARS},
        {"key": "sort_field", "name": "排序", "value": _SORTS},
    ]

# ---------------- 正则 ----------------
# 列表卡片：按「一个影片一个块」切分。
# 站方三种结构（首页 banner / 分类网格 / 搜索网格）都是
#   <div class="flex flex-col gap-2 group ..."> <a href="/tv/xxx.html?..."> <img alt data-src> ...
# 关键：链接 href 的影片 hash 必须与封面 /img/id/<同一 hash>.jpg 对得上，
# 否则 banner 与网格混排时会把封面串到隔壁影片上 → 以块内第一条 href + 块内 img 为准。
_RE_TPL_BLOCK = re.compile(
    r'<div class="flex flex-col gap-2 group[^"]*"[\s\S]*?/div>\s*(?=<div class="flex flex-col gap-2 group|</section>|$)',
    re.I)
_RE_ANY_BLOCK = re.compile(
    r'<div class="[^"]*(?:flex flex-col gap-2 group|swiper-slide)[^"]*"[\s\S]*?(?=<div class="[^"]*(?:flex flex-col gap-2 group|swiper-slide)|</section>|$)',
    re.I)
_RE_BLOCK_HREF = re.compile(r'href="(/(?:movie|tv)/[^"?]+?\.html)', re.I)
_RE_BLOCK_NAME = re.compile(
    r'<h3[^>]*>[\s\S]{0,200}?<a[^>]*>([^<]+)</a>', re.I)
_RE_BLOCK_IMG = re.compile(
    r'<img[^>]*?alt="([^"]*)"[^>]*?(?:data-src|src)="([^"]*)"', re.S | re.I)
_RE_BLOCK_REMARK = re.compile(
    r'absolute top-2 right-2[\s\S]{0,300}?<span[^>]*>\s*([^<]{1,24}?)\s*</span>',
    re.I)
_RE_BLOCK_TYPE = re.compile(
    r'<div class="truncate">([^<]*)</div>\s*<span>(\d{4})</span>', re.I)
_RE_HREF = re.compile(r'href="(/(?:movie|tv)/[^"?]+?\.html)', re.I)
_RE_IMG = re.compile(
    r'<img[^>]*?alt="([^"]*)"[^>]*?(?:data-src|src)="([^"]*)"',
    re.S | re.I)
# 卡片底部：类型 + 年份
_RE_CARD_TYPE = re.compile(
    r'<div class="truncate">([^<]*)</div>\s*<span>(\d{4})</span>', re.I)
# 左上角评分 / 右上角备注（1080p / 14集）
_RE_BADGE = re.compile(
    r'absolute top-2 (right|left)-2[\s\S]{0,400}?<span[^>]*>\s*([^<]{1,24}?)\s*</span>',
    re.I)

# 剧集：兼容有 / 无 data-title（短剧只有 <button>第01集</button>）
_RE_EPISODE_A = re.compile(
    r'<a\s+href="([^"]+)"([^>]*?)>(.*?)</a>',
    re.S | re.I)
_RE_DATA_ORIGIN = re.compile(r'data-origin="([^"]+)"', re.I)
_RE_DATA_TITLE = re.compile(r'data-title="([^"]+)"', re.I)
_RE_BTN_TITLE = re.compile(r'<button[^>]*>([^<]+)</button>', re.I)

_RE_PLAYER_AA = re.compile(r"aa\s*:\s*JSON\.parse\('(.*?)'\)", re.S)
_RE_H1 = re.compile(r'<h1[^>]*>([\s\S]*?)</h1>', re.I)
_RE_PIC_ID = re.compile(r'/img/id/[A-Za-z0-9]+\.(?:jpg|png|webp)', re.I)

# 简介提取（多层兜底）
_RE_INTRO = re.compile(
    r'<span\s+class="font-bold text-\[#ff3347\] mr-1">简介:</span>\s*'
    r'([\s\S]*?)</div>', re.S | re.I)
_RE_INTRO_DIV = re.compile(
    r'<div[^>]*class="[^"]*text-\[#555\][^"]*reset-style[^"]*"[^>]*>'
    r'([\s\S]*?)</div>', re.S | re.I)
_RE_META_DESC = re.compile(
    r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', re.I)

# 元信息正则
# 导演：<div><span class="text-[#2e2e2e] font-bold">导演</span><span class="text-[#666]">
#        <a href="/dianshiju.html?director=秦榛">秦榛</a></span></div>
_RE_DIRECTOR = re.compile(
    r'<span[^>]*font-bold[^>]*>\s*(?:导演|导演:)\s*</span>\s*'
    r'<span[^>]*>([\s\S]*?)</span>', re.I)
_RE_ACTOR = re.compile(
    r'<span[^>]*font-bold[^>]*>\s*(?:主演|主演:)\s*</span>\s*'
    r'<span[^>]*>([\s\S]*?)</span>', re.I)
# 评分：封面左上角 vk-badge（右上角是同结构但写「14集」的备注位）
_RE_SCORE = re.compile(
    r'absolute top-2 left-2 vk-badge[^>]*>\s*([\d.]+)\s*<', re.I)
_RE_YEAR = re.compile(
    r'<h1[^>]*>[\s\S]*?</h1>\s*<span[^>]*>\s*\((\d{4})\)\s*</span>', re.I)
_RE_HOT = re.compile(
    r'([\d,]+)\s*\(电视剧排名:\s*(\d+),\s*总排名:\s*(\d+)\)', re.I)
_RE_HOT2 = re.compile(
    r'([\d,]+)\s*\(电影排名:\s*(\d+),\s*总排名:\s*(\d+)\)', re.I)
_RE_TOTAL = re.compile(r'共有(\d+)条视频')

# PoW 挑战页特征
_RE_POW_HASH = re.compile(r"var\s+hash\s*=\s*['\"]([a-f0-9]{40})['\"]")
_RE_POW_TARGET = re.compile(r"var\s+target\s*=\s*['\"]([a-f0-9]{40})['\"]")
_POW_MARK = ("正在检测", "sha1(hash")

# 线路优先级 / 中文别名（站点 origin 原文 → 展示名）
_LINE_PRIORITY = ["vip", "xiguam3u8", "1080zyk", "wztv", "bfzym3u8", "dyttm3u8",
                  "ffm3u8", "lzm3u8", "modum3u8", "jsm3u8", "mtm3u8"]
_LINE_ALIAS = {
    "vip":      "超级线路",
    "xiguam3u8": "西瓜M3U8",
    "modum3u8": "魔都M3U8",
    "jsm3u8":   "极速M3U8",
    "mtm3u8":   "茅台M3U8",
    "1080zyk":  "1080资源",
    "lzm3u8":   "量子M3U8",
    "bfzym3u8": "暴风资源",
    "dyttm3u8": "电影天堂",
    "ffm3u8":   "非凡M3U8",
    "wztv":     "王者TV",
}


class Spider(Spider):

    def getName(self):
        return "豆花电影"

    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}

        self.site_url = (self.extend.get("site") or HOST).rstrip("/")
        self.sion_id = self.extend.get("sion_id") or SION_ID
        self.box_host = (self.extend.get("box") or BOX_HOST).rstrip("/")
        self.headers = {
            "User-Agent": UA,
            "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
                       "image/avif,image/webp,*/*;q=0.8"),
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": self.site_url + "/",
            "Upgrade-Insecure-Requests": "1",
        }
        self.default_pic = DEFAULT_PIC
        self._play_cache = {}
        self._warmed = False
        self._pow_seen = 0          # 已用掉多少个挑战（统计用）
        self.log("init: site=%s sid=%s" % (self.site_url, self.sion_id))

    # ================= 预热 =================
    def _warm_up(self):
        """首屏必须走一次首页，服务端才会下发 sion_id 会话 cookie；
        PoW 的 attack_key 校验是绑会话的，无 cookie 时永远 429。"""
        if self._warmed:
            return
        try:
            self._fetch_simple(self.site_url + "/", timeout=15)
            self._warmed = True
            self.log("预热完成")
        except Exception as e:
            self.log("预热失败: %s" % e)

    def _fetch_simple(self, url, timeout=15):
        try:
            return self.fetch(url, headers=self.headers, timeout=timeout)
        except Exception as e:
            self.log("fetch FAIL %s -> %s" % (url, e))
            return None

    # ================= PoW 挑战 =================
    def _is_pow(self, text):
        if not text:
            return False
        return _POW_MARK[0] in text and _POW_MARK[1] in text

    def _solve_pow(self, html):
        """服务端 front-end PoW：sha1(hash + i) === target，i 即 attack_key。
        哈希串只由 hash 前缀 + 十进制 i 拼成，纯 CPU 位运算，10 万级内必中。"""
        m1 = _RE_POW_HASH.search(html)
        m2 = _RE_POW_TARGET.search(html)
        if not m1 or not m2:
            self.log("PoW: 未找到 hash/target")
            return None

        hash_prefix = m1.group(1)
        target = m2.group(1)
        self.log("PoW: hash=%s target=%s" % (hash_prefix[:16], target[:16]))

        max_i = 10 * 1000 * 1000
        start = time.time()
        prefix_b = hash_prefix.encode()

        for i in range(max_i):
            s = hashlib.sha1(prefix_b + str(i).encode()).hexdigest()
            if s == target:
                cost = time.time() - start
                self.log("PoW 破解成功: i=%d 耗时=%.2fs" % (i, cost))
                return i
            if (i + 1) % 1000000 == 0:
                cost = time.time() - start
                self.log("PoW 进度: %d 万, 已耗时 %.1fs" % ((i + 1) // 10000, cost))
                if cost > 60:
                    self.log("PoW 超时 (>60s)")
                    return None

        self.log("PoW 未在范围内破解")
        return None

    def _fetch(self, url, timeout=60, headers=None, _depth=0):
        """带 PoW 穿越的 GET。挑战 → 求 key → 带 attack_key 重放（最多 3 轮）。"""
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
            else:
                text = str(rsp)

            if not self._is_pow(text):
                return text

            if _depth >= 3:
                self.log("PoW 挑战超过 3 轮，放弃")
                return text

            self.log("⚠️ 遇到 PoW 挑战, 开始破解...")
            attack_key = self._solve_pow(text)
            if attack_key is None:
                self.log("PoW 破解失败")
                return text

            self._pow_seen += 1
            sep = "&" if "?" in url else "?"
            # 已带旧 key 的地址要替换而不是追加（服务端只认最后一个）
            new_url = re.sub(r"([?&])attack_key=[^&]*", r"\1", url)
            new_url = new_url + ("&" if "?" in new_url else "?") + \
                "attack_key=" + str(attack_key)
            self.log("带 attack_key 重新请求: %s" % str(attack_key))
            text2 = self._fetch(new_url, timeout=timeout, headers=headers,
                                _depth=_depth + 1)
            self.log("PoW 后 HTML 长度: %d" % len(text2 or ""))
            return text2
        except Exception as e:
            self.log("fetch FAIL %s -> %s" % (url, e))
            return ""

    # ================= 工具 =================
    def _fix_url(self, url):
        if not url:
            return ""
        url = url.strip()
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

    def _is_url(self, u):
        return bool(u) and len(u) > 10 and "://" in u and \
            bool(urllib.parse.urlparse(u).hostname)

    def _pic(self, pic):
        pic = (pic or "").strip()
        if not pic:
            return self.default_pic
        return self._fix_url(pic)

    # ================= 列表解析 =================
    def _extract_videos(self, html):
        videos = []
        seen = set()
        if not html:
            self.log("  HTML 为空")
            return videos

        for block in _RE_ANY_BLOCK.findall(html):
            mh = _RE_BLOCK_HREF.search(block)
            if not mh:
                continue
            href = mh.group(1).replace("&amp;", "&")
            if href in seen:
                continue

            mi = _RE_BLOCK_IMG.search(block)
            alt, pic = ("", "")
            if mi:
                alt, pic = mi.group(1), mi.group(2)

            name = self._clean(alt)
            if not name:
                mn = _RE_BLOCK_NAME.search(block)
                if mn:
                    name = self._clean(mn.group(1))
            if not name:
                continue

            seen.add(href)
            item = {
                "vod_id":      href,
                "vod_name":    name[:100],
                "vod_pic":     self._pic(pic),
                "vod_remarks": "",
            }
            mr = _RE_BLOCK_REMARK.search(block)
            if mr:
                remark = self._clean(mr.group(1))
                if remark and len(remark) <= 20 and not remark.isdigit():
                    item["vod_remarks"] = remark
            mt = _RE_BLOCK_TYPE.search(block)
            if mt:
                item["type_name"] = self._clean(mt.group(1))
                item["vod_year"] = mt.group(2)
            videos.append(item)

        self.log("  块解析: %d 条" % len(videos))
        if videos:
            return videos

        # 兜底：href 与 img 分开抽（结构变异时仍能出数据）
        hrefs = _RE_HREF.findall(html)
        imgs = _RE_IMG.findall(html)
        self.log("  兜底分开: href=%d img=%d" % (len(hrefs), len(imgs)))

        if hrefs and imgs:
            for i, href in enumerate(hrefs):
                href = href.replace("&amp;", "&")
                if href in seen:
                    continue
                seen.add(href)
                alt, pic = ("", "")
                if i < len(imgs):
                    alt, pic = imgs[i]
                videos.append({
                    "vod_id":      href,
                    "vod_name":    self._clean(alt)[:100] or href,
                    "vod_pic":     self._pic(pic),
                    "vod_remarks": "",
                })
            return videos

        for href in hrefs:
            href = href.replace("&amp;", "&")
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

    def _page_count(self, html, page, per=24):
        if not html:
            return 1
        m = _RE_TOTAL.search(html)
        if m:
            try:
                total = int(m.group(1))
                if total > 0:
                    return max(1, (total + per - 1) // per)
            except Exception:
                pass
        pages = re.findall(r'page=(\d+)', html)
        if pages:
            try:
                return max(int(p) for p in pages) + 1
            except Exception:
                pass
        return max(1, page)

    # ================= 首页 =================
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        self._warm_up()
        url = "%s/?sion_id=%s" % (self.site_url, self.sion_id)
        html = self._fetch(url)
        self.log("home HTML 长度: %d" % len(html))
        return {"list": self._extract_videos(html)}

    # ================= 分类 =================
    def categoryContent(self, tid, pg, filter, extend):
        self._warm_up()
        page = int(pg) if str(pg).isdigit() else 1
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
            "page": page - 1,                       # ★站方 page 从 0 起
            "sort_field": extend.get("sort_field") or "",
            "sion_id": self.sion_id,
        }
        if extend.get("class"):
            params["class"] = extend["class"]
        if extend.get("year"):
            params["year"] = extend["year"]
        if extend.get("area"):
            params["area"] = extend["area"]

        qs = urllib.parse.urlencode({k: v for k, v in params.items() if v != ""})
        url = "%s/%s.html?%s" % (self.site_url, tid, qs)
        self.log("category: %s" % url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))

        videos = self._extract_videos(html)
        per = len(videos) if videos else 24
        pagecount = self._page_count(html, page, per)
        self.log("  最终: %d 条, 总页数: %d" % (len(videos), pagecount))

        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": per, "total": pagecount * per,
        }

    # ================= 搜索 =================
    def searchContent(self, key, quick, pg="1"):
        self._warm_up()
        page = int(pg) if str(pg).isdigit() else 1
        keyword = urllib.parse.quote(key)
        url = "%s/s.html?name=%s&page=%d&sion_id=%s" % (
            self.site_url, keyword, page - 1, self.sion_id)
        self.log("search: %s" % url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))
        videos = self._extract_videos(html)
        per = len(videos) if videos else 24
        return {
            "list": videos, "page": page,
            "pagecount": self._page_count(html, page, per),
            "limit": per, "total": per * self._page_count(html, page, per),
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ================= 详情 =================
    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0] if isinstance(ids, (list, tuple)) else ids)
        url = vod_id if vod_id.startswith("http") else self._fix_url(vod_id)
        self.log("detail: %s" % url)

        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))
        if not html:
            return {"list": []}

        # ---- 标题 ----
        name = ""
        try:
            m = _RE_H1.search(html)
            if m:
                name = self._clean(m.group(1))
        except Exception:
            pass
        if not name:
            try:
                m = re.search(r"<title>(.*?)</title>", html, re.S)
                if m:
                    name = self._clean(m.group(1).split("_")[0].split("-")[0])
            except Exception:
                pass
        name = re.sub(r"\s*\(\d{4}\)\s*$", "", name).strip() or vod_id

        # ---- 封面 ----
        pic = self.default_pic
        try:
            m = _RE_PIC_ID.search(html)
            if m:
                pic = self.site_url + m.group(0)
        except Exception:
            pass

        # ---- 简介（三层兜底，最后统一加前缀）----
        content = ""
        for _re_intro in (_RE_INTRO, _RE_INTRO_DIV, _RE_META_DESC):
            try:
                m = _re_intro.search(html)
                if m:
                    content = self._clean(m.group(1))
                    if content:
                        break
            except Exception:
                pass

        if content:
            content = INTRO_PREFIX + "\n" + content
        else:
            content = INTRO_PREFIX

        # ---- 元信息 ----
        director = ""
        try:
            m = _RE_DIRECTOR.search(html)
            if m:
                director = self._clean(re.sub(r"<[^>]+>", ",", m.group(1)))
                director = re.sub(r"[,\s]{2,}", ", ", director).strip(", ")
        except Exception:
            pass

        actor = ""
        try:
            m = _RE_ACTOR.search(html)
            if m:
                actor = self._clean(re.sub(r"<[^>]+>", ",", m.group(1)))
                actor = re.sub(r"[,\s]{2,}", ", ", actor).strip(", ")
        except Exception:
            pass

        score = ""
        try:
            m = _RE_SCORE.search(html)
            if m:
                score = m.group(1)
        except Exception:
            pass

        year = ""
        try:
            m = _RE_YEAR.search(html)
            if m:
                year = m.group(1)
        except Exception:
            pass

        hot_info = ""
        try:
            m = _RE_HOT.search(html) or _RE_HOT2.search(html)
            if m:
                hot_info = "热度%s (排名%s)" % (m.group(1), m.group(2))
        except Exception:
            pass

        # ---- 剧集（兼容有 / 无 data-title）----
        groups = {}
        try:
            for m in _RE_EPISODE_A.finditer(html):
                href = m.group(1)
                attrs = m.group(2)
                inner = m.group(3)

                mo = _RE_DATA_ORIGIN.search(attrs)
                if not mo:
                    continue
                origin = mo.group(1)
                if not origin:
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
                    ep_name = "第%s集" % (len(groups.get(origin, [])) + 1)

                groups.setdefault(origin, []).append((ep_name, href))
        except Exception as e:
            self.log("  剧集解析失败: %s" % e)

        # 去重（同一集可能被 tab 与列表各渲染一次）
        for origin in list(groups.keys()):
            uniq = []
            seen_href = set()
            for ep_name, href in groups[origin]:
                if href in seen_href:
                    continue
                seen_href.add(href)
                uniq.append((ep_name, href))
            groups[origin] = uniq

        self.log("  剧集: %s" % {k: len(v) for k, v in groups.items()})

        if not groups:
            return {"list": []}

        sorted_origins = sorted(
            groups.keys(),
            key=lambda x: (_LINE_PRIORITY.index(x)
                           if x in _LINE_PRIORITY else 999))

        play_from = []
        play_url = []
        for origin in sorted_origins:
            eps = groups[origin]
            if not eps:
                continue
            alias = _LINE_ALIAS.get(origin, origin)
            play_from.append(alias)
            play_url.append("#".join("%s$%s" % (n, h) for n, h in eps))

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_score": score,
            "vod_year": year,
            "vod_remarks": hot_info or ("%d条线路" % len(play_from)),
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url":  "$$$".join(play_url),
        }]}

    # ================= 播放 =================
    def playerContent(self, flag, id, vipFlags=None):
        play_page = id if str(id).startswith("http") else self._fix_url(id)
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
            # ========== 情况 A：aa.url 直接就是 m3u8 直链（部分短剧源）==========
            if api_url.startswith("http") and ".m3u8" in api_url.lower():
                self.log("  => 直链 m3u8 (无需转换): %s" % api_url[:200])
                real = self._follow_index(api_url)
                res = {
                    "parse": 0,
                    "playUrl": "",
                    "url": real,
                    "header": {
                        "User-Agent": PLAY_UA,
                        "Referer": self.site_url + "/",
                    },
                }
                self._play_cache[play_page] = (now, res)
                return res

            # ========== 情况 B：/api/m3u8?... → box 中继 → clean 洗白 ==========
            if api_url.startswith("/"):
                api_url = self.site_url + api_url

            real_m3u8 = self._resolve_to_real_m3u8(api_url, referer=play_page)
            if real_m3u8:
                res = {
                    "parse": 0,
                    "playUrl": "",
                    "url": real_m3u8,
                    "header": {
                        "User-Agent": PLAY_UA,
                        "Referer": self.site_url + "/",
                    },
                }
                self._play_cache[play_page] = (now, res)
                self.log("  => 直链 m3u8: %s" % real_m3u8[:160])
                return res

        # 兜底：交给 TVBox 嗅探
        res = {"parse": 1, "playUrl": "", "url": play_page,
               "header": {"User-Agent": PLAY_UA,
                          "Referer": self.site_url + "/"}}
        self._play_cache[play_page] = (now, res)
        return res

    def _follow_index(self, m3u8_url):
        """直链线路常见「index.m3u8 里只放一条子 m3u8」，探测器不解嵌套会黑屏。
        这里下钻一层（最多 2 层），拿回真正带 ts 分片的那一层。"""
        cur = m3u8_url
        for _ in range(2):
            try:
                rsp = self.fetch(cur, headers={
                    "User-Agent": PLAY_UA,
                    "Referer": self.site_url + "/",
                    "Accept": "*/*",
                }, timeout=15)
                text = rsp.text if hasattr(rsp, "text") else ""
            except Exception as e:
                self.log("  follow fail: %s" % e)
                return cur
            if not text or "#EXTM3U" not in text:
                return cur
            subs = [ln.strip() for ln in text.split("\n")
                    if ln.strip() and not ln.strip().startswith("#")]
            if not subs:
                return cur
            nxt = subs[0]
            if not nxt.lower().split("?")[0].endswith(".m3u8"):
                return cur
            if nxt.startswith("http"):
                full = nxt
            elif nxt.startswith("/"):
                pu = urllib.parse.urlparse(cur)
                full = "%s://%s%s" % (pu.scheme, pu.netloc, nxt)
            else:
                full = cur.rsplit("/", 1)[0] + "/" + nxt
            if full == cur:
                return cur
            self.log("  下钻子 m3u8: %s" % full[:160])
            cur = full
        return cur

    def _extract_api_m3u8(self, html):
        """播放页内嵌 window.xg_video_player_doc = { aa: JSON.parse('...') }，
        里面的 url 形如 /api/m3u8?origin=超级线路&url=<集 hash>。"""
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
        """三步洗白：
        1) /api/m3u8 → 302 → box.dyrs.com.de/api/super（master）
        2) master 里取最高带宽子 m3u8，抓回原文
        3) POST /api/clean（url + origin + gzip(原文)）→ 官方 /api/clean/httpurl 直链
        """
        origin = ""
        try:
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(api_url).query)
            origin = (qs.get("origin") or [""])[0]
        except Exception:
            pass

        # ---- 1) master ----
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

        master_url = ""
        master_text = ""
        if not loc:
            text = ""
            try:
                text = rsp.text if hasattr(rsp, "text") else ""
            except Exception:
                text = ""
            if "#EXTM3U" not in text:
                # 没跳转也没 m3u8：可能是 PoW 或接口已换，放弃走嗅探
                self.log("  api 无跳转无 m3u8")
                return ""
            master_url = api_url
            master_text = text
            self.log("api 直接返回 m3u8")
        else:
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
                master_text = ""
                if hasattr(rsp2, "text"):
                    master_text = rsp2.text or ""
                elif hasattr(rsp2, "content"):
                    master_text = rsp2.content.decode("utf-8", "ignore")
            except Exception as e:
                self.log("resolve#2 fail: %s" % e)
                return loc
            master_url = loc
            if "#EXTM3U" not in master_text:
                self.log("  master 无 m3u8 头")
                return loc

        # ---- 2) 取最高码率子 m3u8（没有子流则 master 本身就是正片）----
        final_url, final_text = self._pick_best_stream(master_url, master_text)
        if not final_text or "#EXTM3U" not in final_text:
            self.log("  无可用 m3u8 文本")
            return ""

        # ---- 3) /api/clean 洗白 ----
        clean = self._clean_m3u8(final_url, final_text, origin)
        if clean:
            self.log("  clean 直链: %s" % clean[:160])
            return clean

        self.log("  clean 失败，回退原始子 m3u8")
        return final_url

    def _pick_best_stream(self, master_url, text):
        """按 BANDWIDTH 降序取子流；相对路径按 master 的 host 拼。"""
        if not text:
            return master_url, ""
        base = urllib.parse.urlparse(master_url)
        root = "%s://%s" % (base.scheme, base.netloc)
        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
        cands = []
        for i, line in enumerate(lines):
            if not line.startswith("#EXT-X-STREAM-INF"):
                continue
            m = re.search(r"BANDWIDTH=(\d+)", line, re.I)
            bw = int(m.group(1)) if m else 0
            if i + 1 >= len(lines):
                continue
            sub = lines[i + 1]
            if sub.startswith("http"):
                full = sub
            elif sub.startswith("/"):
                full = root + sub
            else:
                full = root + "/" + sub
            cands.append((bw, full))

        if not cands:
            return master_url, text

        cands.sort(key=lambda x: -x[0])
        self.log("  子 m3u8: %s" % cands[0][1][:160])
        try:
            rsp = self.fetch(cands[0][1], headers={
                "User-Agent": UA,
                "Referer": master_url,
                "Accept": "*/*",
            }, timeout=15)
            sub_text = rsp.text if hasattr(rsp, "text") else ""
        except Exception as e:
            self.log("  子 m3u8 抓取失败: %s" % e)
            return cands[0][1], ""

        # 极少数源是「两级 master」，再往下钻一层（最多 2 次）
        if sub_text and "#EXT-X-STREAM-INF" in sub_text:
            return self._pick_best_stream(cands[0][1], sub_text)
        return cands[0][1], sub_text

    def _clean_m3u8(self, m3u8_url, content, origin):
        """站点 player 的同款流程：gzip 原 m3u8 → POST /api/clean
        → 返回 https://host/api/clean/httpurl?id=xxx，该地址可直连且 ts 已补全域名。"""
        try:
            blob = gzip.compress(content.encode("utf-8"))
        except Exception:
            try:
                import zlib
                blob = zlib.compress(content.encode("utf-8"))
            except Exception:
                blob = content.encode("utf-8")

        data = {
            "url": m3u8_url,
            "origin": origin or "",
            "httpurl": "1",
        }
        files = {
            "original": ("original.gz", blob, "application/gzip"),
        }
        h = {
            "User-Agent": PLAY_UA,
            "Referer": self.site_url + "/player.html?host=%s" %
                       urllib.parse.urlparse(self.site_url).hostname,
            "Origin": self.site_url,
            "Accept": "*/*",
        }
        for _ in range(2):
            try:
                rsp = self.post(self.site_url + "/api/clean", data=data,
                                files=files, headers=h, timeout=20)
                txt = (rsp.text or "").strip()
                if txt.startswith("http"):
                    return txt
                self.log("  clean 返回异常: %s" % txt[:80])
            except Exception as e:
                self.log("  clean 异常: %s" % e)
            time.sleep(0.3)
        return ""

    # ================= 图片代理 =================
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
            if not str(ctype).startswith("image/"):
                ctype = "image/jpeg"
            return [200, ctype, content, ""]
        except Exception:
            return [200, "image/jpeg", b"", ""]

    # ================= 契约 =================
    def isVideoFormat(self, url):
        if not url:
            return False
        return ".m3u8" in url or ".mp4" in url or url.startswith("http")

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()
