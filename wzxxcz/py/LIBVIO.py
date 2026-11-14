# coding=utf-8
"""
LIBVIO libvio.cam | TVBox Python 爬虫
关键:
  - 站点是 MacCMS10 + libvio 模板，带 UA + Referer 直取即可
  - 列表/筛选入口 /show/{12 槽位}.html
    槽位顺序: 分类-地区-排序-类型-语言-空-空-空-页码-空-空-年份
  - 分类沿用站点 5 大类，站内“分类”子类(动作/喜剧... = /show/6..)走筛选首行
  - 详情页按 h3 线路标题 + 其下选集 ul 的顺序输出线路与剧集
  - 副标题取卡片 .pic-text text-right
  - 简介添加指定前缀
  - 播放: 播放页 player_aaaa 的 encrypt=1/2 可直接解；
    encrypt=3 走站点 artplayer 的 smartplay 换源，响应 AES-CBC 本地解密
"""
import re
import sys
import json
import time
import base64
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
            method = (kw.pop('method', 'GET') or 'GET').upper()
            timeout = kw.pop('timeout', 15)
            data = kw.pop('data', None)
            if method == 'POST':
                r = self._sess.post(url, headers=headers, data=data, timeout=timeout, **kw)
            else:
                r = self._sess.get(url, headers=headers, timeout=timeout, **kw)
            r.encoding = 'utf-8'
            return r

        def log(self, *a, **kw):
            try:
                print("[libvio]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.libvio.cam"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/template/libvio/statics/img/load.png"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# smartplay 换源接口与解密用料（取自站点 artplayer 页明文）
SMART_API = "https://hd.ticktockwow.com/smartplay-cache/api/webvideo_ty.php"
SMART_SALT = "RY7e48naFXPsLJC"

CLASSES = [
    {"type_id": "1", "type_name": "电影"},
    {"type_id": "2", "type_name": "电视剧"},
    {"type_id": "3", "type_name": "纪录片"},
    {"type_id": "4", "type_name": "动漫"},
    {"type_id": "5", "type_name": "综艺"},
]

_SORTS = [
    {"n": "时间", "v": "time"},
    {"n": "人气", "v": "hits"},
    {"n": "评分", "v": "score"},
]

_F_T1 = {
    "class": [("动作", "6"), ("喜剧", "7"), ("爱情", "8"), ("科幻", "9"),
              ("恐怖", "10"), ("剧情", "11"), ("战争", "12")],
    "type": ["爱情", "奇幻", "喜剧", "动作", "科幻", "武侠", "冒险", "惊悚",
             "恐怖", "犯罪", "动画", "剧情", "悬疑", "战争", "家庭", "运动",
             "灾难", "传记", "历史", "短片", "西部", "纪录片", "歌舞", "古装",
             "音乐", "剧情片", "儿童", "真人秀"],
    "area": ["大陆", "香港", "台湾", "日本", "美国", "英国", "韩国", "西班牙",
             "泰国", "法国", "丹麦", "智利", "土耳其", "德国", "瑞典", "印度",
             "新西兰", "爱尔兰", "比利时", "希腊", "澳大利亚", "芬兰", "巴西",
             "俄罗斯", "加拿大", "意大利", "其它"],
    "year": ["2026", "2025", "2024", "2023", "2022", "2021", "2020", "2019",
             "2018", "2017", "2016", "2015", "2014", "2013", "2012", "2011"],
    "lang": ["国语", "粤语", "日语", "英语", "韩语", "夏威夷语", "法语", "德语",
             "丹麦语", "西班牙语", "耳其语", "印地语", "芬兰语", "四川乐山话",
             "俄语", "意大利语", "汉语普通话", "闽南语", "其它"],
}

_F_T2 = {
    "class": [("国产剧", "13"), ("港台剧", "14"), ("日韩剧", "15"), ("海外剧", "16")],
    "type": ["喜剧", "科幻", "悬疑", "欧美", "剧情", "奇幻", "古装", "动作",
             "犯罪", "冒险", "惊悚", "恐怖", "历史", "爱情", "音乐", "家庭",
             "国产", "运动", "动画", "西部", "战争", "传记", "灾难", "纪录片",
             "短片", "海外", "真人秀"],
    "area": ["美国", "韩国", "英国", "日本", "大陆", "台湾", "德国", "哥伦比亚",
             "意大利", "西班牙", "丹麦", "挪威", "法国", "香港", "泰国", "其它"],
    "year": ["2026", "2025", "2024", "2023", "2022", "2021", "2020", "2019",
             "2018", "2017", "2016", "2015", "2014", "2013", "2012", "2011"],
    "lang": ["英语", "韩语", "日语", "国语", "德语", "西班牙语", "意大利语",
             "那不勒", "挪威语", "其它"],
}

_F_T3 = {
    "class": [],
    "type": ["科幻", "纪录片", "欧美", "犯罪", "记录", "喜剧", "真人秀", "音乐",
             "歌舞", "动画", "历史", "传记", "悬疑", "运动", "短片", "剧情",
             "家庭", "冒险", "灾难"],
    "area": ["大陆", "英国", "日本", "韩国", "美国", "其它"],
    "year": ["2026", "2025", "2024", "2023", "2022", "2021", "2020", "2019",
             "2018", "2017", "2016", "2015", "2014", "2013", "2012", "2011", "2010"],
    "lang": ["国语", "英语", "粤语", "闽南语", "韩语", "日语", "其它"],
}

_F_T4 = {
    "class": [("国产动漫", "24"), ("日韩动漫", "25"), ("港台动漫", "26"), ("欧美动漫", "27")],
    "type": ["动画", "日韩动漫", "喜剧", "剧情", "科幻", "家庭", "奇幻", "冒险",
             "欧美动漫", "动作", "悬疑", "犯罪", "爱情", "惊悚", "灾难", "音乐",
             "恐怖", "战争", "运动", "歌舞", "古装", "历史", "短片", "国产动漫",
             "战斗"],
    "area": ["大陆", "日本", "美国", "韩国", "西班牙", "其它"],
    "year": ["2026", "2025", "2024", "2023", "2022", "2021", "2020", "2019",
             "2018", "2017", "2016", "2015", "2014", "2013", "2012", "2011"],
    "lang": ["日语", "英语", "国语", "韩语", "其它"],
}

_F_T5 = {
    "class": [("大陆综艺", "17"), ("港台综艺", "18"), ("日韩综艺", "20"), ("欧美综艺", "21")],
    "type": [],
    "area": [],
    "year": ["2026", "2025", "2024", "2023", "2022", "2021", "2020", "2019",
             "2018", "2017", "2016", "2015", "2014", "2013", "2012", "2011"],
    "lang": [],
}

_F_MAP = {"1": _F_T1, "2": _F_T2, "3": _F_T3, "4": _F_T4, "5": _F_T5}


def _opts(names):
    out = [{"n": "全部", "v": ""}]
    for x in names:
        out.append({"n": x, "v": x})
    return out


def _build_filters():
    filters = {}
    for c in CLASSES:
        tid = c["type_id"]
        f = _F_MAP[tid]
        rows = []
        cls = f["class"]
        if cls:
            rows.append({"key": "class", "name": "分类",
                         "value": [{"n": "全部", "v": ""}] +
                                  [{"n": n, "v": v} for n, v in cls]})
        else:
            rows.append({"key": "class", "name": "分类",
                         "value": [{"n": "全部", "v": ""}]})
        rows.append({"key": "type", "name": "类型", "value": _opts(f["type"])})
        rows.append({"key": "area", "name": "地区", "value": _opts(f["area"])})
        rows.append({"key": "year", "name": "年份", "value": _opts(f["year"])})
        rows.append({"key": "lang", "name": "语言", "value": _opts(f["lang"])})
        rows.append({"key": "sort", "name": "排序", "value": list(_SORTS)})
        filters[tid] = rows
    return filters


FILTERS = _build_filters()

# ===================== 正则 =====================
_RE_COMMENT = re.compile(r"<!--[\s\S]*?-->", re.S)
_RE_TAG = re.compile(r"<[^>]+>")
_RE_PAGECOUNT = re.compile(r'class="active num"><a>(\d+)/(\d+)</a>')
_RE_H1 = re.compile(r'<h1 class="title">([\s\S]*?)</h1>', re.S)
_RE_DETAIL_PIC = re.compile(
    r'<a class="pic" href="[^"]*" title="[^"]*">\s*'
    r'<img[^>]*?data-original="([^"]*)"', re.S)
_RE_DATA_TYPE = re.compile(
    r'类型：([\s\S]*?) / 地区：([\s\S]*?) / 年份：([\s\S]*?) / 上映：([^<]*)')
_RE_ACTOR_DIR = re.compile(r'主演：([\s\S]*?) / 导演：([\s\S]*?)</p>')
_RE_SCORE = re.compile(r'<span class="douban"[^>]*>([\d.]+)</span>')
_RE_INTRO_FULL = re.compile(r'<span class="detail-content"[^>]*>([\s\S]*?)</span>')
_RE_INTRO_SKETCH = re.compile(r'<span class="detail-sketch"[^>]*>([\s\S]*?)</span>')
_RE_LINE = re.compile(
    r'<h3[^>]*>([\s\S]*?)</h3>[\s\S]{0,300}?'
    r'<ul class="stui-content__playlist[\s\S]*?</ul>', re.S)
_RE_LINE_A = re.compile(r'<a href="([^"]+)"[^>]*>([\s\S]*?)</a>', re.S)
_RE_PLAYER_AA = re.compile(
    r"var player_aaaa=(\{[\s\S]*?\})\s*(?:;)?\s*</script>")
_RE_PAGE_VKEY = re.compile(r'const playPageUrl\s*=\s*"([^"]*)"')
_RE_PAGE_CODE = re.compile(r'const secretKeySeed\s*=\s*"([^"]*)"')
_RE_PAGE_TS = re.compile(r'const timestamp\s*=\s*"([^"]*)"')


# ===================== AES-128-CBC 解密（纯 Python，供 smartplay 响应使用）=====
_SB = [
0x63,0x7c,0x77,0x7b,0xf2,0x6b,0x6f,0xc5,0x30,0x01,0x67,0x2b,0xfe,0xd7,0xab,0x76,
0xca,0x82,0xc9,0x7d,0xfa,0x59,0x47,0xf0,0xad,0xd4,0xa2,0xaf,0x9c,0xa4,0x72,0xc0,
0xb7,0xfd,0x93,0x26,0x36,0x3f,0xf7,0xcc,0x34,0xa5,0xe5,0xf1,0x71,0xd8,0x31,0x15,
0x04,0xc7,0x23,0xc3,0x18,0x96,0x05,0x9a,0x07,0x12,0x80,0xe2,0xeb,0x27,0xb2,0x75,
0x09,0x83,0x2c,0x1a,0x1b,0x6e,0x5a,0xa0,0x52,0x3b,0xd6,0xb3,0x29,0xe3,0x2f,0x84,
0x53,0xd1,0x00,0xed,0x20,0xfc,0xb1,0x5b,0x6a,0xcb,0xbe,0x39,0x4a,0x4c,0x58,0xcf,
0xd0,0xef,0xaa,0xfb,0x43,0x4d,0x33,0x85,0x45,0xf9,0x02,0x7f,0x50,0x3c,0x9f,0xa8,
0x51,0xa3,0x40,0x8f,0x92,0x9d,0x38,0xf5,0xbc,0xb6,0xda,0x21,0x10,0xff,0xf3,0xd2,
0xcd,0x0c,0x13,0xec,0x5f,0x97,0x44,0x17,0xc4,0xa7,0x7e,0x3d,0x64,0x5d,0x19,0x73,
0x60,0x81,0x4f,0xdc,0x22,0x2a,0x90,0x88,0x46,0xee,0xb8,0x14,0xde,0x5e,0x0b,0xdb,
0xe0,0x32,0x3a,0x0a,0x49,0x06,0x24,0x5c,0xc2,0xd3,0xac,0x62,0x91,0x95,0xe4,0x79,
0xe7,0xc8,0x37,0x6d,0x8d,0xd5,0x4e,0xa9,0x6c,0x56,0xf4,0xea,0x65,0x7a,0xae,0x08,
0xba,0x78,0x25,0x2e,0x1c,0xa6,0xb4,0xc6,0xe8,0xdd,0x74,0x1f,0x4b,0xbd,0x8b,0x8a,
0x70,0x3e,0xb5,0x66,0x48,0x03,0xf6,0x0e,0x61,0x35,0x57,0xb9,0x86,0xc1,0x1d,0x9e,
0xe1,0xf8,0x98,0x11,0x69,0xd9,0x8e,0x94,0x9b,0x1e,0x87,0xe9,0xce,0x55,0x28,0xdf,
0x8c,0xa1,0x89,0x0d,0xbf,0xe6,0x42,0x68,0x41,0x99,0x2d,0x0f,0xb0,0x54,0xbb,0x16]
_INV = [0] * 256
for _i, _v in enumerate(_SB):
    _INV[_v] = _i
_RCON = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1b, 0x36]


def _xt(a):
    return ((a << 1) ^ 0x1b) & 0xff if a & 0x80 else ((a << 1) & 0xff)


def _gmul(a, b):
    r = 0
    while b:
        if b & 1:
            r ^= a
        a = _xt(a)
        b >>= 1
    return r & 0xff


def _aes_expand(key):
    nk = len(key) // 4
    nr = nk + 6
    w = [list(key[i * 4:i * 4 + 4]) for i in range(nk)]
    for i in range(nk, (nr + 1) * 4):
        t = list(w[i - 1])
        if i % nk == 0:
            t = t[1:] + t[:1]
            t = [_SB[b] for b in t]
            t[0] ^= _RCON[i // nk - 1]
        elif nk > 6 and i % nk == 4:
            t = [_SB[b] for b in t]
        w.append([w[i - nk][j] ^ t[j] for j in range(4)])
    return w, nr


def _aes_dec_block(w, nr, blk):
    s = [[blk[4 * c + r] ^ w[nr * 4 + c][r] for c in range(4)] for r in range(4)]
    for rnd in range(nr - 1, -1, -1):
        s = [[s[r][(c - r) % 4] for c in range(4)] for r in range(4)]
        s = [[_INV[b] for b in row] for row in s]
        s = [[s[r][c] ^ w[rnd * 4 + c][r] for c in range(4)] for r in range(4)]
        if rnd:
            out = [[0] * 4 for _ in range(4)]
            for c in range(4):
                a0, a1, a2, a3 = s[0][c], s[1][c], s[2][c], s[3][c]
                out[0][c] = _gmul(a0, 14) ^ _gmul(a1, 11) ^ _gmul(a2, 13) ^ _gmul(a3, 9)
                out[1][c] = _gmul(a0, 9) ^ _gmul(a1, 14) ^ _gmul(a2, 11) ^ _gmul(a3, 13)
                out[2][c] = _gmul(a0, 13) ^ _gmul(a1, 9) ^ _gmul(a2, 14) ^ _gmul(a3, 11)
                out[3][c] = _gmul(a0, 11) ^ _gmul(a1, 13) ^ _gmul(a2, 9) ^ _gmul(a3, 14)
            s = out
    return bytes(s[r][c] for c in range(4) for r in range(4))


def _aes_cbc_decrypt(key, iv, data):
    w, nr = _aes_expand(key)
    prev = iv
    out = b""
    for i in range(0, len(data) - len(data) % 16, 16):
        blk = data[i:i + 16]
        dec = _aes_dec_block(w, nr, blk)
        out += bytes(a ^ b for a, b in zip(dec, prev))
        prev = blk
    return out


class Spider(Spider):

    def getName(self):
        return "LIBVIO"

    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}

        self.site_url = (self.extend.get("site") or HOST).rstrip("/")
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
        self._kind_cache = {}
        self.log("init: site=%s" % self.site_url)

    # ---------- 基础 ----------
    def _fetch(self, url, timeout=20, headers=None):
        try:
            h = dict(self.headers)
            if headers:
                h.update(headers)
            rsp = self.fetch(url, headers=h, timeout=timeout)
            if hasattr(rsp, "text"):
                return rsp.text or ""
            if hasattr(rsp, "content"):
                return rsp.content.decode("utf-8", "ignore")
            return str(rsp)
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
        s = _RE_TAG.sub("", s)
        s = (s.replace("&nbsp;", " ").replace("\xa0", " ")
              .replace("&amp;", "&").replace("&quot;", '"')
              .replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">"))
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n{2,}", "\n", s)
        return s.strip()

    # ---------- 列表 ----------
    def _build_show_url(self, tid, page, ext):
        seg = [
            str(tid),
            ext.get("area") or "",
            ext.get("sort") or "time",
            ext.get("type") or "",
            ext.get("lang") or "",
            "", "", "",
            str(page) if page > 1 else "",
            "", "",
            ext.get("year") or "",
        ]
        return "%s/show/%s.html" % (self.site_url, "-".join(seg))

    def _page_count(self, html):
        m = _RE_PAGECOUNT.search(html)
        if m:
            try:
                return int(m.group(2))
            except Exception:
                return 1
        return 1

    def _extract_videos(self, html):
        videos = []
        seen = set()
        if not html:
            self.log("  HTML 为空")
            return videos

        html = _RE_COMMENT.sub("", html)
        for ch in html.split('class="stui-vodlist__box"')[1:]:
            m = re.search(
                r'href="/detail/(\d+)\.html" title="([^"]*)"[\s\S]{0,400}?'
                r'data-original="([^"]*)"', ch, re.S)
            if not m:
                continue
            vid, name, pic = m.group(1), m.group(2), m.group(3)
            if vid in seen:
                continue
            seen.add(vid)
            remarks = ""
            rm = re.search(r'<span class="pic-text text-right">([\s\S]*?)</span>', ch)
            if rm:
                remarks = self._clean(rm.group(1))
            videos.append({
                "vod_id": "/detail/%s.html" % vid,
                "vod_name": self._clean(name),
                "vod_pic": self._fix_url(pic) or self.default_pic,
                "vod_remarks": remarks,
            })
        self.log("  卡片: %d 条" % len(videos))
        return videos

    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        html = self._fetch(self.site_url + "/")
        self.log("home HTML 长度: %d" % len(html))
        return {"list": self._extract_videos(html)}

    def categoryContent(self, tid, pg, filter, extend):
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

        # 站点“分类”=子分类 id，直接替换 type_id；“类型”走 URL 槽位4
        sub_type = extend.get("class") or ""
        if sub_type:
            tid = sub_type

        url = self._build_show_url(tid, page, extend)
        self.log("category: %s" % url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))

        videos = self._extract_videos(html)
        pagecount = self._page_count(html)
        self.log("  最终: %d 条, 总页数: %d" % (len(videos), pagecount))

        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 12, "total": pagecount * 12,
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        kw = urllib.parse.quote(key)
        if page <= 1:
            url = "%s/search/%s-------------.html" % (self.site_url, kw)
        else:
            url = "%s/search/%s----------%d---.html" % (self.site_url, kw, page)
        self.log("search: %s" % url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))
        return {
            "list": self._extract_videos(html), "page": page,
            "pagecount": self._page_count(html),
            "limit": 12, "total": 999,
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------- 详情 ----------
    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0])
        url = vod_id if vod_id.startswith("http") else self._fix_url(vod_id)
        self.log("detail: %s" % url)

        html = self._fetch(url, timeout=25)
        self.log("  HTML 长度: %d" % len(html))
        if not html:
            return {"list": []}
        html = _RE_COMMENT.sub("", html)

        name = ""
        m = _RE_H1.search(html)
        if m:
            name = self._clean(m.group(1))
        if not name:
            m = re.search(r"<title>(.*?)</title>", html, re.S)
            if m:
                name = self._clean(m.group(1).split("-")[0])
        name = re.sub(r"\s*(高清|HD|BD)\s*$", "", name).strip() or vod_id

        pic = self.default_pic
        m = _RE_DETAIL_PIC.search(html)
        if m:
            pic = self._fix_url(m.group(1)) or self.default_pic

        vod_type = area = year = release = ""
        m = _RE_DATA_TYPE.search(html)
        if m:
            vod_type = self._clean(m.group(1))
            area = self._clean(m.group(2))
            year = self._clean(m.group(3))
            release = self._clean(m.group(4))

        director = ""
        actor = ""
        m = _RE_ACTOR_DIR.search(html)
        if m:
            actor = re.sub(r"\s*,\s*", ", ", self._clean(m.group(1)))
            director = self._clean(m.group(2))

        score = ""
        m = _RE_SCORE.search(html)
        if m:
            score = m.group(1)

        # 简介（优先全量 detail-content）
        content = ""
        m = _RE_INTRO_FULL.search(html)
        if m:
            content = self._clean(m.group(1))
        if not content:
            m = _RE_INTRO_SKETCH.search(html)
            if m:
                content = self._clean(m.group(1))
        content = INTRO_PREFIX + "\n" + content if content else INTRO_PREFIX

        # 线路 + 选集（完全按站点 h3 顺序）
        play_from = []
        play_url = []
        for m in _RE_LINE.finditer(html):
            line_name = self._clean(m.group(1))
            eps = []
            for a in _RE_LINE_A.finditer(m.group(0)):
                href = self._fix_url(a.group(1))
                ep = self._clean(a.group(2)) or str(len(eps) + 1)
                eps.append("%s$%s" % (ep, href))
            if not eps:
                continue
            play_from.append(line_name or ("线路%d" % (len(play_from) + 1)))
            play_url.append("#".join(eps))

        self.log("  线路: %s" % play_from)
        if not play_from:
            return {"list": []}

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_score": score,
            "vod_area": area,
            "vod_year": year,
            "vod_remarks": "",
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }]}

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith("http") else self._fix_url(id)
        self.log("player: %s" % play_page)

        now = int(time.time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 600:
                return res

        html = self._fetch(play_page)
        data = self._player_data(html)

        # 明文直链线路（encrypt=0/1/2）
        direct = self._direct_url(data)
        if direct:
            res = {
                "parse": 0, "playUrl": "", "url": direct,
                "header": {"User-Agent": UA, "Referer": self.site_url + "/"},
            }
            self._play_cache[play_page] = (now, res)
            self.log("  => 直链: %s" % direct[:160])
            return res

        # encrypt=3：走站点 artplayer 的 smartplay 换源（网盘线路除外）
        if self._player_kind((data or {}).get("from")) == "artplayer":
            direct = self._smartplay(play_page, data)
        else:
            direct = ""
        if direct:
            res = {
                "parse": 0, "playUrl": "", "url": direct,
                "header": {"User-Agent": UA, "Referer": self.site_url + "/"},
            }
            self._play_cache[play_page] = (now, res)
            self.log("  => smartplay 直链: %s" % direct[:160])
            return res

        # 兜底：把站点自己的播放器页交给 App 嗅探（WebView 解析可自行取链）
        fb = play_page
        if str((data or {}).get("encrypt") or "") == "3" and (data or {}).get("url"):
            nxt = (data or {}).get("link_next") or ""
            fb = "%s/static/player/artplayer/?url=%s%s" % (
                self.site_url, data["url"],
                ("&next=" + (self.site_url + nxt) if nxt else ""))
        res = {"parse": 1, "playUrl": "", "url": fb,
               "header": {"User-Agent": UA, "Referer": play_page}}
        self._play_cache[play_page] = (now, res)
        self.log("  => 兜底嗅探: %s" % fb[:120])
        return res

    def _player_data(self, html):
        if not html:
            return {}
        m = _RE_PLAYER_AA.search(html)
        if not m:
            return {}
        try:
            return json.loads(m.group(1).replace("\\/", "/"))
        except Exception:
            return {}

    def _direct_url(self, data):
        if not data:
            return ""
        raw = data.get("url") or ""
        enc = str(data.get("encrypt") or "0")
        if not raw:
            return ""
        try:
            if enc == "1":
                raw = urllib.parse.unquote(raw)
            elif enc == "2":
                raw = urllib.parse.unquote(base64.b64decode(
                    raw + "=" * ((4 - len(raw) % 4) % 4)).decode("utf-8", "ignore"))
            elif enc != "0":
                return ""
        except Exception:
            return ""
        if raw.startswith("http") and (".m3u8" in raw or ".mp4" in raw):
            return raw
        return ""

    def _player_kind(self, frm):
        """读 /static/player/{from}.js 判断播放器类型：artplayer / pan / 空"""
        frm = (frm or "").strip()
        if not frm:
            return ""
        if frm in self._kind_cache:
            return self._kind_cache[frm]
        kind = ""
        js = self._fetch("%s/static/player/%s.js" % (self.site_url, frm), timeout=15)
        if js:
            if "artplayer" in js:
                kind = "artplayer"
            elif "pan.html" in js:
                kind = "pan"
        self._kind_cache[frm] = kind
        return kind

    def _post_json(self, url, payload, headers):
        """POST JSON：宿主 fetch → requests → 标准库 urllib，三路兜底"""
        body = json.dumps(payload)
        # 1) 宿主 fetch（部分宿主不支持 method/data）
        try:
            rsp = self.fetch(url, headers=headers, timeout=8,
                             method="POST", data=body)
            return rsp.text if hasattr(rsp, "text") else str(rsp)
        except Exception as e:
            self.log("  post#fetch 失败: %s" % e)
        # 2) requests
        try:
            import requests
            r = requests.post(url, headers=headers, data=body, timeout=8)
            return r.text or ""
        except Exception as e:
            self.log("  post#requests 失败: %s" % e)
        # 3) 标准库 urllib（Chaquopy 一定有）
        try:
            import ssl
            import urllib.request
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(
                url, data=body.encode("utf-8"), headers=headers, method="POST")
            rsp = urllib.request.urlopen(req, timeout=8, context=ctx)
            return rsp.read().decode("utf-8", "ignore")
        except Exception as e:
            self.log("  post#urllib 失败: %s" % e)
        return ""

    def _api_call(self, params, headers):
        """先 POST JSON；不是 JSON（网关报错页）就再用 GET 查询串试一次"""
        body = self._post_json(SMART_API, params, headers)
        if body and body.strip()[:1] in ("{", "["):
            return body
        try:
            h = dict(headers)
            h.pop("Content-Type", None)
            rsp = self.fetch("%s?%s" % (SMART_API, urllib.parse.urlencode(params)),
                             headers=h, timeout=8)
            g = rsp.text if hasattr(rsp, "text") else str(rsp)
            if g and g.strip()[:1] in ("{", "["):
                self.log("  api#get 命中")
                return g
            return g or body
        except Exception as e:
            self.log("  api#get 失败: %s" % e)
        return body

    def _api_pick(self, ret):
        """宽松取地址：code 允许 0/200/缺省，地址允许在 url/data/playurl"""
        if isinstance(ret, list) and ret:
            ret = ret[0]
        if not isinstance(ret, dict):
            return "", "响应不是对象"
        code = ret.get("code")
        if code is None:
            code = 0
        if str(code) not in ("0", "200"):
            msg = ret.get("msg") or ret.get("message") or ""
            return "", "code=%s %s" % (code, msg)
        url = ret.get("url") or ""
        if not url:
            d = ret.get("data")
            if isinstance(d, dict):
                url = d.get("url") or d.get("playurl") or d.get("playUrl") or ""
            elif isinstance(d, str):
                url = d
        if not url:
            url = ret.get("playurl") or ret.get("playUrl") or ""
        if not url:
            return "", "无 url 字段(%s)" % ",".join(list(ret.keys())[:6])
        return url, "ok"

    def _smartplay(self, play_page, data):
        """encrypt=3：页面给 vkey/code/timestamp，接口换真实地址，AES-CBC 本地解密"""
        blob = (data or {}).get("url") or ""
        if not blob:
            return ""
        nxt = (data or {}).get("link_next") or ""

        for attempt in (1, 2):
            page_url = "%s/static/player/artplayer/?url=%s%s" % (
                self.site_url, blob,
                ("&next=" + (self.site_url + nxt) if nxt else ""))
            page = self._fetch(page_url, timeout=25, headers={"Referer": play_page})

            mv = _RE_PAGE_VKEY.search(page or "")
            mc = _RE_PAGE_CODE.search(page or "")
            mt = _RE_PAGE_TS.search(page or "")
            if not (mv and mc and mt):
                self.log("  smartplay#%d: 播放器页参数缺失(页长%d)" % (attempt, len(page or "")))
                continue

            now = int(time.time())
            t0 = time.time()
            body = self._api_call({
                "vkey": mv.group(1),
                "code": mc.group(1),
                "t": now,
                "signature": hashlib.md5(str(now).encode()).hexdigest(),
            }, {
                "User-Agent": UA,
                "Content-Type": "application/json",
                "Origin": self.site_url,
                "Referer": page_url,
            })
            if not body:
                self.log("  smartplay#%d: 接口无响应" % attempt)
                if time.time() - t0 > 12:
                    self.log("  接口不通(%.1fs)，不再重试" % (time.time() - t0))
                    break
                continue

            try:
                ret = json.loads(body)
            except Exception:
                self.log("  smartplay#%d: 响应非 JSON %s" % (attempt, (body or "")[:120]))
                continue

            url, why = self._api_pick(ret)
            if not url:
                self.log("  smartplay#%d: 取链失败 %s" % (attempt, why))
                continue

            if not url.startswith("http"):
                url = self._smart_decrypt(url, mt.group(1))

            if "/T/" in url:
                url = url.split("/T/", 1)[0]
            if "/fallbackurl/" in url:
                url = url.split("/fallbackurl/", 1)[0].strip()

            if url.startswith("http"):
                self.log("  smartplay#%d: 拿到地址 %s" % (attempt, url[:120]))
                return url
            self.log("  smartplay#%d: 地址不可直用 %s" % (attempt, url[:100]))

        return ""

    def _smart_decrypt(self, cipher, timestamp):
        """key=md5(timestamp+salt)[16:], iv=md5(timestamp+salt)[:16], AES-CBC/Pkcs7"""
        try:
            mat = hashlib.md5((str(timestamp) + SMART_SALT).encode("utf-8")).hexdigest()
            key = mat[16:].encode("utf-8")
            iv = mat[:16].encode("utf-8")
            raw = base64.b64decode(cipher + "=" * ((4 - len(cipher) % 4) % 4))
            pt = _aes_cbc_decrypt(key, iv, raw)
            if pt:
                pad = pt[-1]
                if 0 < pad < 17 and pt[-pad:] == bytes([pad]) * pad:
                    pt = pt[:-pad]
            return pt.decode("utf-8", "ignore").strip()
        except Exception as e:
            self.log("  smartplay: 解密失败 %s" % e)
            return ""

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()
