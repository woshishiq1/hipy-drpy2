# coding=utf-8
"""
星帆影视 xingfan.cc | TVBox Python 爬虫 
关键机关(全部死磕源码+实测破解):
  1. 拼音 slug 路由站(meiju 模板, Alpine.js 渲染, 无 PoW 无验证盾)
     - 大分类: /dianying/ /dianshiju/ /dongman/ /zongyi/, 分页 /{tid}/index-{N}.html
     - 筛选路由: /vodlist/{tid}_{题材}_{地区}_{年份}_{字母}_{排序}_{页}.html
       (7 段下划线拼接; 页1 可省略页码段, N>=2 为 _{N}; 全空+页1 = {tid}______1)
  2. 子分类(国产剧/香港剧/.../动作片/喜剧片/...)是独立页面, 其 slug 可直接
     用于 vodlist 路由(如 /vodlist/guocanju_dushi_____1.html) → TVBox 里做成
     "子类"筛选行, 选中即换 tid
  3. 播放为聚合播放器(zanpiancms_player):
     - 播放页内嵌 var zanpiancms_player = {"url":"base64票","apiurl":"//php.playerla.com/mjplay/?id=",...}
     - iframe = apiurl + 票 → YunPlayer(artplayer+hls) 页
     - YunPlayer 页 #line-list 里 data-url 列出全部真实 m3u8(带临时 token)
       → 取第一条(与站点默认线路一致) parse=0 直链返回; m3u8 无 Referer 即 200
  4. ⚠️ 剧集顺序: 站点部分影片 DOM 倒序(第40集在前), 详情解析后必须按
     nid(线路-集.html 数字)升序排序 — 保证 TVBox 里全部正序
  5. 副标题: 详情页播放列表状态行 "全8集 · 热播中"; 简介加指定前缀
  6. 影片数量(页头"精选 N 部"声明, 与尾页×24 一致):
     电视剧 13715(572页) / 电影 13465(562页) / 动漫 87(4页) / 综艺 0(空分类) = 全站 27267 部
"""
import re
import sys
import json
import time
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
            timeout = kw.pop('timeout', 15)
            r = self._sess.get(url, headers=headers, timeout=timeout, **kw)
            r.encoding = 'utf-8'
            return r

        def log(self, *a, **kw):
            try:
                print("[xingfan]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.xingfan.cc"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# ===================== 分类（与站点导航完全一致, slug 线上实证） =====================
CLASSES = [
    {"type_id": "dianying",  "type_name": "电影"},
    {"type_id": "dianshiju", "type_name": "电视剧"},
    {"type_id": "dongman",   "type_name": "动漫"},
    {"type_id": "zongyi",    "type_name": "综艺"},
]

# 子分类(站点导航独立页, slug 直接可用作 vodlist tid) — 每大类一行"子类"筛选
_SUBCAT = {
    "dianshiju": [("国产剧", "guocanju"), ("香港剧", "xianggangju"),
                  ("欧美剧", "oumeiju"), ("日本剧", "ribenju"),
                  ("海外剧", "haiwaiju"), ("台湾剧", "taiwanju"),
                  ("韩国剧", "hanguoju"), ("泰国剧", "taiguoju")],
    "dianying":  [("动作片", "dongzuopian"), ("喜剧片", "xijupian"),
                  ("爱情片", "aiqingpian"), ("科幻片", "kehuanpian"),
                  ("恐怖片", "kongbupian"), ("战争片", "zhanzhengpian"),
                  ("剧情片", "juqingpian"), ("纪录片", "jilupian"),
                  ("动画片", "donghuapian")],
}

# 题材行(f1, 站点各分类 f-chip 逐项照抄, v=站点拼音段)
_TYPES = {
    "dianshiju": ["都市", "生活", "家庭", "青春", "爱情", "剧情", "喜剧", "年代",
                  "战争", "偶像", "励志", "时装", "言情", "校园", "刑侦", "农村",
                  "军事", "军旅", "谍战", "古装", "武侠", "犯罪", "罪案", "悬疑",
                  "推理", "破案", "冒险", "惊悚", "商战", "历史", "神话", "穿越",
                  "科幻", "少女", "动漫", "热血", "旅游", "时尚", "真人秀", "职场",
                  "动画", "文艺", "歌舞", "抗战", "恐怖", "音乐", "奇幻", "游戏",
                  "益智", "传奇", "情感", "童话", "搞笑", "预告", "动作", "灾难",
                  "近代革命", "脱口秀", "近代传奇", "美食", "经典", "玄幻",
                  "真人剧", "传记", "伦理", "网络剧", "未知", "魔幻"],
    "dianying": ["喜剧", "动作", "科幻", "魔幻", "爱情", "言情", "剧情", "动画",
                 "冒险", "青春", "古装", "罪案", "灾难", "歌舞", "犯罪", "励志",
                 "文艺", "生活", "原声", "历史", "谍战", "穿越", "军旅", "家庭",
                 "预告", "益智", "偶像", "搞笑", "热血", "经典", "童话", "刑侦",
                 "推理", "音乐", "校园", "神话", "都市", "职场", "美食", "旅游",
                 "恐怖", "战争", "记录", "奇幻", "明星", "武侠", "其它", "时尚",
                 "少女", "竞技", "商战", "游戏", "惊悚", "悬疑", "纪录", "伦理",
                 "戏曲", "短片"],
    "dongman": ["冒险", "热血", "搞笑", "少女", "恋爱", "魔幻", "推理", "神魔",
                "竞技", "游戏", "益智", "机战", "宠物", "格斗", "魔法", "亲子",
                "励志", "青春", "都市", "惊悚", "经典", "童话", "真人", "校园",
                "文艺", "生活", "古装", "科幻", "未知", "动画", "剧情", "犯罪",
                "动漫", "历史", "悬疑", "歌舞", "家庭", "武侠", "音乐", "战争",
                "喜剧", "恐怖", "偶像", "罪案", "真人秀", "言情", "美食", "灾难",
                "奇幻"],
    "zongyi": ["真人秀", "脱口秀", "选秀", "歌舞", "音乐", "晚会", "情感", "时尚",
               "访谈", "美食", "益智", "游戏", "财经", "旅游", "职场", "生活",
               "社会", "新闻", "娱乐", "历史", "文化", "人物", "军事", "看点",
               "少儿", "故事", "纪实", "体育", "偶像", "热血", "文艺", "经典",
               "青春", "冒险", "都市", "搞笑", "励志", "喜剧", "悬疑", "推理",
               "未知"],
}
# 题材中文名 → 站点拼音段(从站点 f-chip 链接逐项提取, 中文与拼音一一对应)
_TYPE_SLUG = {
    "dianshiju": {"都市": "dushi", "生活": "shenghuo", "家庭": "jiating",
                  "青春": "qingchun", "爱情": "aiqing", "剧情": "juqing",
                  "喜剧": "xiju", "年代": "niandai", "战争": "zhanzheng",
                  "偶像": "ouxiang", "励志": "lizhi", "时装": "shizhuang",
                  "言情": "yanqing", "校园": "xiaoyuan", "刑侦": "xingzhen",
                  "农村": "nongcun", "军事": "junshi", "军旅": "junlv",
                  "谍战": "diezhan", "古装": "guzhuang", "武侠": "wuxia",
                  "犯罪": "fanzui", "罪案": "zuian", "悬疑": "xuanyi",
                  "推理": "tuili", "破案": "poan", "冒险": "maoxian",
                  "惊悚": "jingsong", "商战": "shangzhan", "历史": "lishi",
                  "神话": "shenhua", "穿越": "chuanyue", "科幻": "kehuan",
                  "少女": "shaonv", "动漫": "dongman", "热血": "rexue",
                  "旅游": "lvyou", "时尚": "shishang", "真人秀": "zhenrenxiu",
                  "职场": "zhichang", "动画": "donghua", "文艺": "wenyi",
                  "歌舞": "gewu", "抗战": "kangzhan", "恐怖": "kongbu",
                  "音乐": "yinle", "奇幻": "qihuan", "游戏": "youxi",
                  "益智": "yizhi", "传奇": "chuanqi", "情感": "qinggan",
                  "童话": "tonghua", "搞笑": "gaoxiao", "预告": "yugao",
                  "动作": "dongzuo", "灾难": "zainan",
                  "近代革命": "jindaigeming", "脱口秀": "tuokouxiu",
                  "近代传奇": "jindaichuanqi", "美食": "meishi",
                  "经典": "jingdian", "玄幻": "xuanhuan", "真人剧": "zhenrenju",
                  "传记": "chuanji", "伦理": "lunli", "网络剧": "wangluoju",
                  "未知": "weizhi", "魔幻": "mohuan"},
    "dianying": {"喜剧": "xiju", "动作": "dongzuo", "科幻": "kehuan",
                 "魔幻": "mohuan", "爱情": "aiqing", "言情": "yanqing",
                 "剧情": "juqing", "动画": "donghua", "冒险": "maoxian",
                 "青春": "qingchun", "古装": "guzhuang", "罪案": "zuian",
                 "灾难": "zainan", "歌舞": "gewu", "犯罪": "fanzui",
                 "励志": "lizhi", "文艺": "wenyi", "生活": "shenghuo",
                 "原声": "yuansheng", "历史": "lishi", "谍战": "diezhan",
                 "穿越": "chuanyue", "军旅": "junlv", "家庭": "jiating",
                 "预告": "yugao", "益智": "yizhi", "偶像": "ouxiang",
                 "搞笑": "gaoxiao", "热血": "rexue", "经典": "jingdian",
                 "童话": "tonghua", "刑侦": "xingzhen", "推理": "tuili",
                 "音乐": "yinle", "校园": "xiaoyuan", "神话": "shenhua",
                 "都市": "dushi", "职场": "zhichang", "美食": "meishi",
                 "旅游": "lvyou", "恐怖": "kongbu", "战争": "zhanzheng",
                 "记录": "jilu1", "奇幻": "qihuan", "明星": "mingxing",
                 "武侠": "wuxia", "其它": "qita", "时尚": "shishang",
                 "少女": "shaonv", "竞技": "jingji", "商战": "shangzhan",
                 "游戏": "youxi", "惊悚": "jingsong", "悬疑": "xuanyi",
                 "纪录": "jilu", "伦理": "lunli", "戏曲": "xiqu",
                 "短片": "duanpian"},
    "dongman": {"冒险": "maoxian", "热血": "rexue", "搞笑": "gaoxiao",
                "少女": "shaonv", "恋爱": "lianai", "魔幻": "mohuan",
                "推理": "tuili", "神魔": "shenmo", "竞技": "jingji",
                "游戏": "youxi", "益智": "yizhi", "机战": "jizhan",
                "宠物": "chongwu", "格斗": "gedou", "魔法": "mofa",
                "亲子": "qinzi", "励志": "lizhi", "青春": "qingchun",
                "都市": "dushi", "惊悚": "jingsong", "经典": "jingdian",
                "童话": "tonghua", "真人": "zhenren", "校园": "xiaoyuan",
                "文艺": "wenyi", "生活": "shenghuo", "古装": "guzhuang",
                "科幻": "kehuan", "未知": "weizhi", "动画": "donghua",
                "剧情": "juqing", "犯罪": "fanzui", "动漫": "dongman",
                "历史": "lishi", "悬疑": "xuanyi", "歌舞": "gewu",
                "家庭": "jiating", "武侠": "wuxia", "音乐": "yinle",
                "战争": "zhanzheng", "喜剧": "xiju", "恐怖": "kongbu",
                "偶像": "ouxiang", "罪案": "zuian", "真人秀": "zhenrenxiu",
                "言情": "yanqing", "美食": "meishi", "灾难": "zainan",
                "奇幻": "qihuan"},
    "zongyi": {"真人秀": "zhenrenxiu", "脱口秀": "tuokouxiu", "选秀": "xuanxiu",
               "歌舞": "gewu", "音乐": "yinle", "晚会": "wanhui",
               "情感": "qinggan", "时尚": "shishang", "访谈": "fangtan",
               "美食": "meishi", "益智": "yizhi", "游戏": "youxi",
               "财经": "caijing", "旅游": "lvyou", "职场": "zhichang",
               "生活": "shenghuo", "社会": "shehui", "新闻": "xinwen",
               "娱乐": "yule", "历史": "lishi", "文化": "wenhua",
               "人物": "renwu", "军事": "junshi", "看点": "kandian",
               "少儿": "shaoer", "故事": "gushi", "纪实": "jishi",
               "体育": "tiyu", "偶像": "ouxiang", "热血": "rexue",
               "文艺": "wenyi", "经典": "jingdian", "青春": "qingchun",
               "冒险": "maoxian", "都市": "dushi", "搞笑": "gaoxiao",
               "励志": "lizhi", "喜剧": "xiju", "悬疑": "xuanyi",
               "推理": "tuili", "未知": "weizhi"},
}

# 地区行(f2, 站点 f-chip 逐项一致, 四分类相同)
_AREAS = [("大陆", "Dalu"), ("港台", "Gangtai"), ("日韩", "Rihan"),
          ("欧美", "Oumei"), ("香港", "HongKong"), ("台湾", "Taiwan"),
          ("美国", "USA"), ("韩国", "Hanguo"), ("日本", "Japan"),
          ("泰国", "Thailand"), ("新加坡", "Singapore"),
          ("马来西亚", "Malaysia"), ("印度", "India"), ("英国", "England"),
          ("法国", "France"), ("加拿大", "Canada"), ("其它", "Qita")]

_YEARS = [{"n": "全部", "v": ""}] + \
         [{"n": str(y), "v": str(y)} for y in range(2026, 2014, -1)]

_LETTERS = [{"n": "全部", "v": ""}] + \
           [{"n": c, "v": c} for c in
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ"]

_SORTS = [{"n": "最新", "v": "addtime"},
          {"n": "最热", "v": "hits"},
          {"n": "评分", "v": "gold"}]

FILTERS = {}
for _c in CLASSES:
    _tid = _c["type_id"]
    _fl = []
    if _tid in _SUBCAT:
        _fl.append({"key": "cat", "name": "子类",
                    "value": [{"n": "全部", "v": ""}] +
                             [{"n": n, "v": s} for n, s in _SUBCAT[_tid]]})
    _fl.append({"key": "type", "name": "题材",
                "value": [{"n": "全部", "v": ""}] +
                         [{"n": n, "v": _TYPE_SLUG[_tid].get(n, n)}
                          for n in _TYPES.get(_tid, [])]})
    _fl.append({"key": "area", "name": "地区",
                "value": [{"n": "全部", "v": ""}] +
                         [{"n": n, "v": s} for n, s in _AREAS]})
    _fl.append({"key": "year", "name": "年份", "value": _YEARS})
    _fl.append({"key": "letter", "name": "字母", "value": _LETTERS})
    _fl.append({"key": "sort", "name": "排序", "value": _SORTS})
    FILTERS[_tid] = _fl


# ===================== 正则 =====================
# 列表卡片(三种结构统一以"详情链接+img alt"为锚):
#   首页: <article class="proto-rim"...><a href="/cat/slug/" class="block">...<img alt=名>
#   分类页: <a href="/cat/slug/" class="proto-rim group">...<img alt=名>...备注p
#   搜索页: <a href="/cat/slug/" class="rim-card...">...<img alt=名>
# 备注: 分类页卡片有 <p class="text-[11px] text-white/55 truncate">第X集 / 共X集</p>
_RE_CARD = re.compile(
    r'href="(/[a-z]+/[a-z0-9\-]+/)"'
    r'[\s\S]{0,600}?'
    r'<img[^>]*?(?:data-src|src)="([^"]+)"[^>]*?alt="([^"]*)"'
    r'(?:[\s\S]{0,1400}?text-white/55 truncate">([^<]{0,60})</p>)?',
    re.S | re.I)
_RE_HREF = re.compile(r'href="(/[a-z]+/[a-z0-9\-]+/)"', re.I)

# 详情页
_RE_H1 = re.compile(r'<h1[^>]*>([\s\S]*?)</h1>', re.I)
_RE_TITLE_TAG = re.compile(r'<title>([^<]*)</title>', re.I)
_RE_OG_IMG = re.compile(
    r'property="og:image"[^>]*content="([^"]+)"', re.I)
_RE_IMG_ALT = re.compile(
    r'<img[^>]*?class="[^"]*mxu-ar23-cover[^"]*"[^>]*>', re.I)
_RE_INTRO = re.compile(
    r'剧情简介</h3>\s*<p[^>]*>([\s\S]*?)</p>', re.S | re.I)
_RE_META_DESC = re.compile(
    r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', re.I)
# 元信息: <span class="text-white/25 font-500">导演</span><p ...>值</p>
_RE_META = re.compile(
    r'text-white/25 font-500">([\u4e00-\u9fa5]{2,4})</span>\s*'
    r'<p[^>]*>([\s\S]*?)</p>', re.S | re.I)
_RE_VTAG = re.compile(r'class="vtag[^"]*"[^>]*>([^<]{1,12})<', re.I)
# 状态行: 全8集 · 热播中 (播放列表头部)
_RE_STATUS = re.compile(r'全?\s*(\d+)\s*集\s*·\s*([\u4e00-\u9fa5]{1,8})', re.I)
# 单集总数(独立 span): 8集
_RE_EPS_N = re.compile(r'>(\d+)集\s*<', re.I)

# 线路 tab: data-tab-target="detail_line_N">线路名
_RE_LINE_TAB = re.compile(
    r'data-tab-target="detail_line_(\d+)">([^<]{1,20})<', re.I)
# 剧集块: <div id="detail_line_N" ...> ... <a href="/cat/slug/L-E.html" class="episode-link">第XX集</a>
_RE_LINE_BLOCK = re.compile(
    r'<div id="detail_line_(\d+)"[^>]*class="block"[\s\S]*?</div>\s*</div>', re.S)
_RE_EP = re.compile(
    r'href="(/[a-z]+/[a-z0-9\-]+/(\d+)-(\d+)\.html)"[^>]*class="episode-link"[^>]*>([^<]*)</a>', re.I)
_RE_EP_LOOSE = re.compile(
    r'href="(/[a-z]+/[a-z0-9\-]+/(\d+)-(\d+)\.html)"[^>]*>([^<]{1,20})</a>', re.I)

# 播放页: zanpiancms_player
_RE_PLAYER = re.compile(
    r'var\s+zanpiancms_player\s*=\s*(\{[^;]+\})\s*;', re.S)
# YunPlayer 聚合页: data-url='m3u8'
_RE_LINE_URL = re.compile(r"data-url='([^']+)'", re.I)
_RE_ANY_M3U8 = re.compile(r'https?://[^\s"\'<>]+?\.m3u8[^\s"\'<>]*', re.I)

# 分页: /{tid}/index-N.html 或 /vodlist/..._{N}.html
_RE_PAGE_NUM = re.compile(r'index-(\d+)\.html', re.I)
_RE_PAGE_VOD = re.compile(r'(/vodlist/[\s\S]*?_)(\d+)(\.html)', re.I)


class Spider(Spider):

    def getName(self):
        return "星帆影视"

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
            "Referer": self.site_url + "/",
        }
        self._play_cache = {}
        self.log("init: site=%s" % self.site_url)

    def _fetch(self, url, timeout=60, headers=None):
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
              .replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">")
              .replace("&ldquo;", "“").replace("&rdquo;", "”")
              .replace("&middot;", "·"))
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n{2,}", "\n", s)
        return s.strip()

    def _extract_videos(self, html):
        videos = []
        seen = set()
        if not html:
            self.log("  HTML 为空")
            return videos

        matches = _RE_CARD.findall(html)
        self.log("  完整卡片: %d 条" % len(matches))

        if matches:
            for href, pic, alt, prb in matches:
                href = href.replace("&amp;", "&")
                if href in seen:
                    continue
                seen.add(href)
                videos.append({
                    "vod_id":      href,
                    "vod_name":    self._clean(alt)[:100],
                    "vod_pic":     self._fix_url(pic.replace("&amp;", "&")),
                    "vod_remarks": self._clean(prb or ""),
                })
            return videos

        hrefs = _RE_HREF.findall(html)
        self.log("  兜底: href=%d" % len(hrefs))
        for href in hrefs:
            if href in seen:
                continue
            seen.add(href)
            videos.append({
                "vod_id":      href,
                "vod_name":    href.strip("/").split("/")[-1],
                "vod_pic":     "",
                "vod_remarks": "",
            })
        return videos

    def _page_count(self, html):
        """真实末页 = 尾页链接的页号(与页头"精选 N 部"/24 一致)。"""
        if not html:
            return 1
        try:
            pages = [int(p) for p in _RE_PAGE_NUM.findall(html)]
            if pages:
                return max(pages)
            for m in _RE_PAGE_VOD.finditer(html):
                try:
                    pages.append(int(m.group(2)))
                except Exception:
                    pass
            if pages:
                return max(pages)
        except Exception:
            pass
        return 1

    def _build_vodlist_path(self, tid, page, vtype="", area="",
                            year="", letter="", sort=""):
        """与站点完全同构的筛选路由(段序照站点 f-chip 链接实测):
        /vodlist/{tid}_{题材}_{地区}_{年份}_{字母}_{排序}_{页}.html
        tid 可被子类 slug 覆盖(如 guocanju); 页1 与站点一致带 _1。"""
        q = urllib.parse.quote
        path = "/vodlist/%s_%s_%s_%s_%s_%s_%d.html" % (
            q(str(tid)),
            q(str(vtype or "")),
            q(str(area or "")),
            q(str(year or "")),
            q(str(letter or "")),
            q(str(sort or "")),
            int(page) if page else 1)
        return path

    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        url = self.site_url + "/"
        html = self._fetch(url)
        self.log("home HTML 长度: %d" % len(html))
        videos = self._extract_videos(html)
        self.log("  最终: %d 条" % len(videos))
        return {"list": videos}

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

        # 子类筛选: 选中即换 tid(站点导航子类页 slug 直接可用)
        cur_tid = extend.get("cat") or tid
        url = self.site_url + self._build_vodlist_path(
            cur_tid, page,
            vtype=extend.get("type") or "",
            area=extend.get("area") or "",
            year=extend.get("year") or "",
            letter=extend.get("letter") or "",
            sort=extend.get("sort") or "")
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
        page = int(pg) if pg else 1
        keyword = urllib.parse.quote(key)
        if page > 1:
            url = "%s/search/%s-%d.html" % (self.site_url, keyword, page)
        else:
            url = "%s/search/%s.html" % (self.site_url, keyword)
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

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0])
        url = vod_id if vod_id.startswith("http") else self._fix_url(vod_id)
        self.log("detail: %s" % url)

        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))
        if not html:
            return {"list": []}

        # ===== 标题 =====
        name = ""
        try:
            m = _RE_H1.search(html)
            if m:
                name = self._clean(m.group(1))
        except Exception:
            pass
        if not name:
            try:
                m = _RE_TITLE_TAG.search(html)
                if m:
                    name = self._clean(
                        m.group(1).split("_")[0].split("-")[0])
            except Exception:
                pass
        name = re.sub(r"\s*[(（]\d{4}[)）]\s*$", "", name).strip() or vod_id

        # ===== 封面(og:image 为站点正式字段) =====
        pic = ""
        try:
            m = _RE_OG_IMG.search(html)
            if m:
                pic = self._fix_url(m.group(1))
        except Exception:
            pass

        # ===== 元信息(通用 span>导演/主演/年份/地区/类型/语言) =====
        metas = {}
        try:
            for mm in _RE_META.finditer(html):
                metas[mm.group(1)] = self._clean(mm.group(2))
        except Exception:
            pass
        actor = metas.get("主演", "")
        director = metas.get("导演", "")
        vod_year = metas.get("年份", "")
        vod_area = metas.get("地区", "")
        vod_lang = metas.get("语言", "")

        # 类型: hero 区 vtag 首个是子类(如 欧美剧), 其余为题材
        vtags = []
        try:
            for vm in _RE_VTAG.finditer(html):
                t = self._clean(vm.group(1))
                if t and t not in vtags:
                    vtags.append(t)
        except Exception:
            pass
        vod_class = metas.get("类型", "") or ",".join(vtags[:5])

        # ===== 简介 =====
        content = ""
        try:
            m = _RE_INTRO.search(html)
            if m:
                content = self._clean(m.group(1))
        except Exception:
            pass
        if not content:
            try:
                m = _RE_META_DESC.search(html)
                if m:
                    content = self._clean(m.group(1))
            except Exception:
                pass
        if content:
            content = INTRO_PREFIX + "\n" + content
        else:
            content = INTRO_PREFIX

        # ===== 副标题(播放列表状态行: 全8集 · 热播中) =====
        remarks = ""
        try:
            m = _RE_STATUS.search(html)
            if m:
                remarks = "全%s集 · %s" % (m.group(1), m.group(2))
            else:
                m2 = _RE_EPS_N.search(html)
                if m2:
                    remarks = "全%s集" % m2.group(1)
        except Exception:
            pass

        # ===== 线路与剧集 =====
        # 线路名 tab: data-tab-target="detail_line_N">线路名
        line_names = {}
        try:
            for tm in _RE_LINE_TAB.finditer(html):
                line_names[tm.group(1)] = self._clean(tm.group(2))
        except Exception:
            pass

        # 剧集块: 按 detail_line_N 分块; 站点 DOM 可能倒序 → 按 nid 升序重排
        boxes = []
        try:
            blocks = re.split(r'<div id="detail_line_', html)
            for bi, part in enumerate(blocks[1:], 1):
                eps = _RE_EP.findall(part) or _RE_EP_LOOSE.findall(part)
                if eps:
                    # ⚠️ 用户硬性要求: 集数正序 — 按线路号+集号数字升序
                    eps = sorted(eps, key=lambda e: (int(e[1]), int(e[2])))
                    boxes.append((str(bi), eps))
        except Exception as e:
            self.log("  剧集解析失败: %s" % e)
        self.log("  线路box: %s" % [(ln, len(eps)) for ln, eps in boxes])

        if not boxes:
            return {"list": []}

        play_from = []
        play_url = []
        for ln, eps in boxes:
            alias = line_names.get(ln) or ("线路%s" % ln)
            play_from.append(alias)
            play_url.append("#".join(
                "%s$%s" % (self._clean(n) or ("第%02d集" % int(e[2])), h)
                for h, _l, _e, n in eps))

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_remarks": remarks or ("%d条线路" % len(boxes)),
            "type_name": vod_class,
            "vod_area": vod_area,
            "vod_year": vod_year,
            "vod_lang": vod_lang,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url":  "$$$".join(play_url),
        }]}

    # -------- 播放 --------
    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith("http") else self._fix_url(id)
        self.log("player: %s" % play_page)

        now = int(time.time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 600:
                return res

        header = {"User-Agent": UA}

        # ---- 1) 播放页: zanpiancms_player → 聚合票 ----
        html = self._fetch(play_page)
        ticket, apiurl = "", ""
        if html:
            m = _RE_PLAYER.search(html)
            if m:
                try:
                    d = json.loads(m.group(1).replace("\\/", "/"))
                    ticket = str(d.get("url") or "")
                    apiurl = str(d.get("apiurl") or "")
                except Exception:
                    pass
        self.log("  ticket=%s apiurl=%s" % (ticket, apiurl[:60] if apiurl else "-"))

        # ---- 2) YunPlayer 聚合页: data-url 列表(与站点默认线路一致取第一条) ----
        if ticket and apiurl:
            if apiurl.startswith("//"):
                apiurl = "https:" + apiurl
            elif apiurl.startswith("/"):
                apiurl = self.site_url + apiurl
            mj_url = apiurl + urllib.parse.quote(ticket)
            mj_html = self._fetch(mj_url, headers={
                "User-Agent": UA,
                "Referer": self.site_url + "/",
                "Accept": "text/html,*/*",
            })
            real_url = ""
            if mj_html:
                urls = _RE_LINE_URL.findall(mj_html)
                if urls:
                    # 站点 YunPlayer 线路1 即默认播放线路
                    for u in urls:
                        u = u.replace("&amp;", "&")
                        if u.startswith("http"):
                            real_url = u
                            break
                if not real_url:
                    ms = _RE_ANY_M3U8.findall(mj_html)
                    if ms:
                        real_url = ms[0].replace("&amp;", "&")
            if real_url:
                self.log("  => 聚合直链: %s" % real_url[:130])
                res = {"parse": 0, "playUrl": "", "url": real_url,
                       "header": header}
                self._play_cache[play_page] = (now, res)
                return res

        # ---- 3) 兜底: 交 TVBox 嗅探 ----
        res = {"parse": 1, "playUrl": "", "url": play_page,
               "header": {"User-Agent": UA, "Referer": self.site_url + "/"}}
        self._play_cache[play_page] = (now, res)
        return res

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
            content = getattr(rsp, "content", None)
            if content is None:
                content = str(rsp).encode("utf-8", "ignore")
            ctype = ""
            try:
                ctype = rsp.headers.get("Content-Type", "") or ""
            except Exception:
                ctype = ""
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
