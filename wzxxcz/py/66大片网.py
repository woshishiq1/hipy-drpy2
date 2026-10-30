# coding=utf-8
"""
66大片网 www.66dpw.vip | TVBox Python 爬虫
关键:
  - 苹果CMS mxpro 模板解析
  - 破解播放页 player_aaaa 的 encrypt=2 地址: base64 -> URL decode
  - 极速线路直出 m3u8 (parse=0), 哔哩哔哩等外链交嗅探 (parse=1)
  - 搜索接口带验证码检测 (返回空并提示)
"""
import re
import sys
import json
import base64
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
                print("[66dpw]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.66dpw.vip"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = "https://www.66dpw.vip/template/mxpro/mxtheme/images/logo.png"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

CLASSES = [
    {"type_id": "1", "type_name": "电影"},
    {"type_id": "3", "type_name": "剧集"},
    {"type_id": "2", "type_name": "动漫"},
    {"type_id": "5", "type_name": "综艺"},
    {"type_id": "4", "type_name": "短剧"},
]

# ===== 站点真实筛选 (www.66dpw.vip/vodshow) =====
# 路径格式: /vodshow/{类型ID}-{地区}-{语言}-{年份}-{字母}-{剧情}-{排序}-{页码}.html
# 说明: 该站筛选页需过一次图形验证码, 爬虫端无法预置会话,
#       因此这里用站点公布的全部筛选项(名称与站内完全一致)拼装路径,
#       未触发验证码时返回真实结果, 触发时自动降级为 vodtype 列表。

_SUB_TYPES = {"1": [["全部", ""], ["科幻片", "8"], ["恐怖片", "9"], ["动作片", "10"], ["战争片", "11"], ["爱情片", "12"], ["喜剧片", "13"], ["剧情片", "14"], ["记录片", "15"]], "2": [["全部", ""], ["大陆番", "16"], ["日本番", "17"], ["韩国番", "18"], ["港台番", "20"], ["欧美番", "21"]], "3": [["全部", ""], ["大陆剧", "22"], ["日本剧", "23"], ["韩国剧", "24"], ["香港剧", "25"], ["台湾剧", "26"], ["欧美剧", "27"]], "5": [["全部", ""], ["大陆综艺", "28"], ["港台综艺", "29"], ["日韩综艺", "30"], ["欧美综艺", "31"]]}

_AREAS = {"1": [["全部", ""], ["大陆", "大陆"], ["香港", "香港"], ["台湾", "台湾"], ["美国", "美国"], ["法国", "法国"], ["英国", "英国"], ["日本", "日本"], ["韩国", "韩国"], ["德国", "德国"], ["泰国", "泰国"], ["印度", "印度"], ["意大利", "意大利"], ["西班牙", "西班牙"], ["加拿大", "加拿大"], ["其他", "其他"]], "2": [["全部", ""], ["内地", "内地"], ["香港", "香港"], ["台湾", "台湾"], ["美国", "美国"], ["法国", "法国"], ["英国", "英国"], ["日本", "日本"], ["韩国", "韩国"], ["德国", "德国"], ["泰国", "泰国"], ["印度", "印度"], ["意大利", "意大利"], ["西班牙", "西班牙"], ["加拿大", "加拿大"], ["其他", "其他"]], "3": [["全部", ""], ["内地", "内地"], ["日本", "日本"], ["韩国", "韩国"], ["香港", "香港"], ["台湾", "台湾"], ["美国", "美国"], ["德国", "德国"], ["法国", "法国"], ["英国", "英国"], ["意大利", "意大利"], ["西班牙", "西班牙"], ["荷兰", "荷兰"], ["瑞典", "瑞典"], ["瑞士", "瑞士"], ["奥地利", "奥地利"], ["比利时", "比利时"], ["丹麦", "丹麦"], ["挪威", "挪威"], ["芬兰等", "芬兰等"], ["澳大利亚", "澳大利亚"], ["新西兰", "新西兰"], ["加拿大", "加拿大"]], "4": [["全部", ""], ["内地", "内地"], ["美国", "美国"], ["德国", "德国"], ["法国", "法国"], ["英国", "英国"], ["意大利", "意大利"], ["西班牙", "西班牙"], ["荷兰", "荷兰"], ["瑞典", "瑞典"], ["瑞士", "瑞士"], ["奥地利", "奥地利"], ["比利时", "比利时"], ["丹麦", "丹麦"], ["挪威", "挪威"], ["芬兰等", "芬兰等"], ["澳大利亚", "澳大利亚"], ["新西兰", "新西兰"], ["加拿大", "加拿大"]], "5": [["全部", ""], ["内地", "内地"], ["香港", "香港"], ["台湾", "台湾"], ["美国", "美国"], ["法国", "法国"], ["英国", "英国"], ["日本", "日本"], ["韩国", "韩国"], ["德国", "德国"], ["泰国", "泰国"], ["印度", "印度"], ["意大利", "意大利"], ["西班牙", "西班牙"], ["加拿大", "加拿大"], ["其他", "其他"]]}

_GENDERS = {"1": [["全部", ""], ["警匪", "警匪"], ["犯罪", "犯罪"], ["动画", "动画"], ["奇幻", "奇幻"], ["武侠", "武侠"], ["冒险", "冒险"], ["枪战", "枪战"], ["悬疑", "悬疑"], ["惊悚", "惊悚"], ["经典", "经典"], ["青春", "青春"], ["文艺", "文艺"], ["微电影", "微电影"], ["古装", "古装"], ["历史", "历史"], ["运动", "运动"], ["农村", "农村"], ["儿童", "儿童"], ["网络电影", "网络电影"]], "2": [["全部", ""], ["热血", "热血"], ["励志", "励志"], ["玄幻", "玄幻"], ["古风", "古风"], ["动态漫", "动态漫"], ["恋爱", "恋爱"], ["青春", "青春"], ["校园", "校园"], ["运动", "运动"], ["科幻", "科幻"], ["冒险", "冒险"], ["魔法", "魔法"], ["日常", "日常"], ["治愈", "治愈"], ["机战", "机战"], ["推理", "推理"], ["都市", "都市"], ["小说改", "小说改"], ["游戏改", "游戏改"], ["漫画改", "漫画改"]], "3": [["全部", ""], ["喜剧", "喜剧"], ["爱情", "爱情"], ["恐怖", "恐怖"], ["动作", "动作"], ["科幻", "科幻"], ["剧情", "剧情"], ["战争", "战争"], ["警匪", "警匪"], ["犯罪", "犯罪"], ["动画", "动画"], ["奇幻", "奇幻"], ["武侠", "武侠"], ["冒险", "冒险"], ["枪战", "枪战"], ["悬疑", "悬疑"], ["惊悚", "惊悚"], ["经典", "经典"], ["青春", "青春"], ["文艺", "文艺"], ["微电视剧", "微电视剧"], ["古装", "古装"], ["历史", "历史"], ["运动", "运动"], ["农村", "农村"], ["儿童", "儿童"], ["网络电视剧", "网络电视剧"], ["其他", "其他"]], "4": [["全部", ""], ["喜剧", "喜剧"], ["爱情", "爱情"], ["恐怖", "恐怖"], ["动作", "动作"], ["科幻", "科幻"], ["剧情", "剧情"], ["战争", "战争"], ["警匪", "警匪"], ["犯罪", "犯罪"], ["动画", "动画"], ["奇幻", "奇幻"], ["武侠", "武侠"], ["冒险", "冒险"], ["枪战", "枪战"], ["悬疑", "悬疑"], ["惊悚", "惊悚"], ["经典", "经典"], ["青春", "青春"], ["文艺", "文艺"], ["微电视剧", "微电视剧"], ["古装", "古装"], ["历史", "历史"], ["运动", "运动"], ["农村", "农村"], ["儿童", "儿童"], ["网络电视剧", "网络电视剧"], ["其他", "其他"]], "5": [["全部", ""], ["偶像", "偶像"], ["舞蹈", "舞蹈"], ["音乐", "音乐"], ["情感", "情感"], ["喜剧", "喜剧"], ["体育", "体育"], ["游戏", "游戏"], ["相声", "相声"], ["婚恋", "婚恋"], ["时尚", "时尚"], ["晚会", "晚会"], ["明星访谈", "明星访谈"], ["亲子", "亲子"], ["生活", "生活"], ["文化", "文化"], ["美食", "美食"], ["旅游", "旅游"], ["溢智", "溢智"]]}

_LANGS = {"1": [["全部", ""], ["国语", "国语"], ["英语", "英语"], ["粤语", "粤语"], ["闽南语", "闽南语"], ["韩语", "韩语"], ["日语", "日语"], ["其它", "其它"]], "2": [["全部", ""], ["国语", "国语"], ["英语", "英语"], ["粤语", "粤语"], ["闽南语", "闽南语"], ["韩语", "韩语"], ["日语", "日语"], ["其它", "其它"]], "3": [["全部", ""], ["国语", "国语"], ["粤语", "粤语"], ["闽南语", "闽南语"], ["日语", "日语"], ["韩语", "韩语"], ["英语", "英语"], ["法语", "法语"], ["德语", "德语"], ["其它", "其它"]], "4": [["全部", ""], ["国语", "国语"], ["英语", "英语"], ["粤语", "粤语"], ["闽南语", "闽南语"], ["韩语", "韩语"], ["日语", "日语"], ["法语", "法语"], ["德语", "德语"], ["其它", "其它"]], "5": [["全部", ""], ["国语", "国语"], ["英语", "英语"], ["粤语", "粤语"], ["闽南语", "闽南语"], ["韩语", "韩语"], ["日语", "日语"], ["法语", "法语"], ["德语", "德语"], ["其它", "其它"]]}

_LETTERS = [["字母", ""]] + [[c, c] for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"] + [["0-9", "0-9"]]
_YEARS = [["全部", ""]] + [[str(y), str(y)] for y in range(2026, 2007, -1)]
_ORDERS = [["时间排序", "time"], ["人气排序", "hits"], ["评分排序", "score"]]

_CLASSES_ALL = [
    {"type_id": "1", "type_name": "电影"},
    {"type_id": "3", "type_name": "剧集"},
    {"type_id": "2", "type_name": "动漫"},
    {"type_id": "5", "type_name": "综艺"},
    {"type_id": "4", "type_name": "短剧"},
]


def _mk_filter(tid):
    fl = []
    if str(tid) in _SUB_TYPES:
        fl.append({"key": "type", "name": "类型",
                   "value": [{"n": n, "v": v} for n, v in _SUB_TYPES[str(tid)]]})
    if str(tid) in _GENDERS:
        fl.append({"key": "class", "name": "剧情",
                   "value": [{"n": n, "v": v} for n, v in _GENDERS[str(tid)]]})
    if str(tid) in _AREAS:
        fl.append({"key": "area", "name": "地区",
                   "value": [{"n": n, "v": v} for n, v in _AREAS[str(tid)]]})
    if str(tid) in _LANGS:
        fl.append({"key": "lang", "name": "语言",
                   "value": [{"n": n, "v": v} for n, v in _LANGS[str(tid)]]})
    fl.append({"key": "year", "name": "年份",
               "value": [{"n": n, "v": v} for n, v in _YEARS]})
    fl.append({"key": "letter", "name": "字母",
               "value": [{"n": n, "v": v} for n, v in _LETTERS]})
    fl.append({"key": "order", "name": "排序",
               "value": [{"n": n, "v": v} for n, v in _ORDERS]})
    return fl


CLASSES = _CLASSES_ALL
FILTERS = {c["type_id"]: _mk_filter(c["type_id"]) for c in CLASSES}



# ===================== 正则 =====================
# 列表卡片: href + title + 备注/人气 + 图片(data-original 或 src)
_RE_CARD = re.compile(
    r'<a\s+href="(/voddetail/\d+\.html)"\s+title="([^"]*)"[^>]*>'
    r'([\s\S]*?)</a>', re.I)
_RE_NOTE = re.compile(r'class="module-item-note">([^<]*)<', re.I)
_RE_DOUBAN = re.compile(r'class="module-item-douban">([^<]*)<', re.I)
_RE_PIC_DATA = re.compile(r'data-original="([^"]+)"', re.I)
_RE_PIC_ANY = re.compile(
    r'<img[^>]*?(?:data-original|data-src|src)="([^"]*)"', re.I | re.S)

_RE_HREF = re.compile(r'href="(/voddetail/\d+\.html)"', re.I)
_RE_IMG = re.compile(
    r'(?:data-original|data-src|src)="([^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"',
    re.I)

# 播放线路标签(按顺序): data-dropdown-value="哔哩哔哩"
_RE_TAB = re.compile(r'data-dropdown-value="([^"]+)"', re.I)
# 播放集数: href="/vodplay/{vid}-{src}-{ep}.html" title="..."<span>..</span>
_RE_PLAY_A = re.compile(
    r'<a[^>]+href="(/vodplay/\d+-(\d+)-\d+\.html)"\s+title="([^"]*)"',
    re.I)
_RE_SPAN = re.compile(r'<span>([^<]*)</span>', re.I)
# 每个播放面板起点(面板顺序 == 标签顺序, 但内部 src 序号可能乱序)
_RE_PANEL = re.compile(r'module-play-list-content', re.I)

# 详情页
_RE_TITLE_TAG = re.compile(r'<title>(.*?)</title>', re.S | re.I)
_RE_H1 = re.compile(r'<h1[^>]*>([\s\S]*?)</h1>', re.I)
_RE_PIC_ID = re.compile(
    r'data-original="(https?://[^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"', re.I)
_RE_INTRO = re.compile(
    r'module-info-introduction-content[^"]*"[^>]*>\s*<p>([\s\S]*?)</p>',
    re.I)
_RE_META_DESC = re.compile(
    r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']',
    re.I)
# 元信息: 每个 module-info-item 块 (内容可能是 div 也可能是 p)
_RE_INFO_ITEM = re.compile(
    r'<div class="module-info-item"[^>]*>\s*'
    r'<span\s+class="module-info-item-title">\s*([^<]*?)\s*</span>\s*'
    r'<(?:div|p)[^>]*class="module-info-item-content"[^>]*>([\s\S]*?)</(?:div|p)>',
    re.I)
# 头部标签区: 年份 / 地区 / 剧情标签 (title 属性或链接文本)
_RE_TAG_LINK = re.compile(
    r'<div class="module-info-tag-link">([\s\S]*?)</div>', re.I)
_RE_A_TEXT = re.compile(r'<a[^>]*?title="([^"]*)"[^>]*>([^<]*)</a>', re.I)

# 播放页 player_aaaa
_RE_PLAYER = re.compile(r'player_aaaa\s*=\s*(\{[\s\S]*?\})\s*[;<]', re.I)

# maccms 验证码页特征
_RE_CAPTCHA = re.compile(r'(系统安全验证|需要输入验证码|ajax/verify_check)')


class Spider(Spider):

    def getName(self):
        return "66大片网"

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
        self._last_captcha = False
        self._play_cache = {}
        self.log("init: site=%s" % self.site_url)

    def _fetch(self, url, timeout=30, headers=None, referer=None):
        try:
            h = dict(self.headers)
            if referer:
                h["Referer"] = referer
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
            if _RE_CAPTCHA.search(text):
                self.log("⚠️ 触发验证码: %s" % url)
                self._last_captcha = True
                return text
            self._last_captcha = False
            return text
        except Exception as e:
            self.log("fetch FAIL %s -> %s" % (url, e))
            self._last_captcha = False
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
              .replace("\t", ""))
        s = re.sub(r"[ \r\f\v]+", " ", s)
        s = re.sub(r"\n{2,}", "\n", s)
        return s.strip()

    # -------- 列表解析 --------
    def _extract_videos(self, html):
        videos = []
        seen = set()
        if not html:
            self.log("  HTML 为空")
            return videos

        matches = _RE_CARD.findall(html)
        self.log("  完整卡片: %d 条" % len(matches))

        if matches:
            for href, title, block in matches:
                if href in seen:
                    continue
                seen.add(href)
                name = self._clean(title)
                pic = ""
                mp = _RE_PIC_DATA.search(block)
                if mp:
                    pic = mp.group(1)
                else:
                    for mi in _RE_PIC_ANY.finditer(block):
                        u = mi.group(1)
                        if u and "load.gif" not in u:
                            pic = u
                            break
                        if u and not pic:
                            pic = u
                remark = ""
                mn = _RE_NOTE.search(block)
                if mn:
                    remark = self._clean(mn.group(1))
                if not remark:
                    md = _RE_DOUBAN.search(block)
                    if md:
                        remark = self._clean(md.group(1))
                videos.append({
                    "vod_id":      href,
                    "vod_name":    name[:100] or href,
                    "vod_pic":     self._fix_url(pic) or self.default_pic,
                    "vod_remarks": remark[:20],
                })
            return videos

        # 兜底: 分开提取
        hrefs = _RE_HREF.findall(html)
        imgs = _RE_IMG.findall(html)
        self.log("  分开: href=%d img=%d" % (len(hrefs), len(imgs)))
        for i, href in enumerate(hrefs):
            if href in seen:
                continue
            seen.add(href)
            pic = imgs[i] if i < len(imgs) else ""
            videos.append({
                "vod_id":      href,
                "vod_name":    href.strip("/").split("/")[-1],
                "vod_pic":     self._fix_url(pic) or self.default_pic,
                "vod_remarks": "",
            })
        return videos

    def _is_list_page(self, html):
        """判断是否为正常列表页(排除验证码页/空页)"""
        if not html or len(html) < 3000:
            return False
        if _RE_CAPTCHA.search(html):
            return False
        return ("module-poster-item" in html) or ("voddetail/" in html)

    def _page_count(self, html):
        if not html:
            return 1
        pages = re.findall(r'/page/(\d+)\.html', html)
        if pages:
            try:
                return max(int(p) for p in pages)
            except Exception:
                pass
        return 9999

    # -------- TVBox 接口 --------
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

        # 站点真实筛选路径: /vodshow/{类型ID}-{地区}-{语言}-{年份}-{字母}-{剧情}-{排序}-{页}.html
        type_id = str(extend.get("type") or tid or "")
        area = str(extend.get("area") or "")
        lang = str(extend.get("lang") or "")
        year = str(extend.get("year") or "")
        letter = str(extend.get("letter") or "")
        gender = str(extend.get("class") or "")
        order = str(extend.get("order") or "")

        def q(s):
            return urllib.parse.quote(s.encode("utf-8")) if s else ""

        # 站点 vodshow 为固定 12 段路径, 段位实测如下:
        # [0]类型ID [1]地区 [2]排序 [3]剧情 [4]语言 [5]字母
        # [6]字母0-9的"9" [7..10]保留 [11]年份
        letter_a, letter_b = "", ""
        if letter == "0-9":
            # 0-9 站内占用 "0"、"9" 两段, 需额外补空段维持 12 段结构
            letter_a, letter_b = "0", "9"
        elif letter:
            letter_a = letter

        segs = [
            type_id,      # 0 类型/子分类ID
            q(area),      # 1 地区
            q(order),     # 2 排序 time/hits/score
            q(gender),    # 3 剧情
            q(lang),      # 4 语言
            q(letter_a),  # 5 字母
            q(letter_b),  # 6 0-9 时的 9
            "", "", "", "",   # 7-10 保留
            q(year),      # 11 年份
        ]
        if letter == "0-9":
            segs.insert(7, "")
        path = "-".join(segs)
        if page > 1:
            path += "-" + str(page)
        url = "%s/vodshow/%s.html" % (self.site_url, path)
        self.log("category(vodshow): %s" % url)

        html = self._fetch(url)
        if not self._is_list_page(html):
            # 触发验证码或返回异常 -> 先回退到 vodtype 列表(不带筛选)
            self.log("  ⚠️ vodshow 被验证码拦截, 回退 vodtype")
            base = "%s/vodtype/%s%s.html" % (
                self.site_url, type_id,
                "" if page <= 1 else "/page/%d" % page)
            html = self._fetch(base)
            self.log("  HTML 长度: %d" % len(html))
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
        # maccms 搜索: /vodsearch/{wd}-------------.html (第 - 页参数位)
        dashes = "-------------"[:11] + ("%d" % page) + "---"
        url = "%s/vodsearch/%s%s.html" % (
            self.site_url, urllib.parse.quote(key), dashes)
        self.log("search: %s" % url)
        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))
        videos = self._extract_videos(html)
        return {
            "list": videos, "page": page,
            "pagecount": self._page_count(html) if videos else page,
            "limit": 24, "total": 999 if videos else page * 24,
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0])
        if re.fullmatch(r"\d+", vod_id):
            vod_id = "/voddetail/%s.html" % vod_id
        url = vod_id if vod_id.startswith("http") else self._fix_url(vod_id)
        self.log("detail: %s" % url)

        html = self._fetch(url)
        self.log("  HTML 长度: %d" % len(html))
        if not html:
            return {"list": []}

        # 标题
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
                    name = self._clean(m.group(1))
            except Exception:
                pass
        # 去掉 "- 66 大片网_..." 后缀与年份
        name = re.split(r"[-_]\s*66\s*大片网", name)[0]
        name = re.sub(r"(大陆番详情介绍|详情介绍|免费在线观看|高清完整版下载)",
                      "", name).strip()
        name = re.sub(r"\s*[\(（]\d{4}[\)）]\s*$", "", name).strip() or vod_id

        # 封面
        pic = self.default_pic
        try:
            m = _RE_PIC_ID.search(html)
            if m:
                pic = m.group(1)
        except Exception:
            pass

        # 简介
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

        # 元信息 (导演/主演/更新/备注/评分)
        director = ""
        actor = ""
        year = ""
        area = ""
        remarks = ""
        updated = ""
        score = ""
        try:
            for k, v in _RE_INFO_ITEM.findall(html):
                key = self._clean(k).rstrip("：:").strip()
                raw = v
                # 用 / 分隔的链接列表 -> 逗号连接
                names = [self._clean(t).strip()
                         for _, t in _RE_A_TEXT.findall(raw)]
                names = [n for n in names if n]
                val = ", ".join(names) if names else self._clean(raw)
                val = re.sub(r"\s*/\s*", ", ", val).strip(", /")
                val = re.sub(r"\s+", " ", val).strip()
                if not val:
                    continue
                if key == "导演":
                    director = val
                elif key == "主演":
                    actor = val
                elif key == "年份":
                    year = val
                elif key == "地区":
                    area = val
                elif key == "备注":
                    remarks = val
                elif key == "更新":
                    updated = val
                elif key in ("评分", "豆瓣"):
                    m = re.search(r"([\d.]+)\s*分", val)
                    if m:
                        score = m.group(1)
        except Exception as e:
            self.log("  元信息解析失败: %s" % e)

        # 头部标签区: 第1块=年份, 第2块=地区, 其余=剧情标签
        try:
            tags = _RE_TAG_LINK.findall(html)
            parsed = []
            for tb in tags:
                items = [self._clean(t or a)
                         for t, a in _RE_A_TEXT.findall(tb)]
                items = [i for i in items if i and i != "/"]
                parsed.append(items)
            if parsed:
                if not year and parsed[0]:
                    first = parsed[0][0]
                    if re.fullmatch(r"\d{4}", first):
                        year = first
                if len(parsed) > 1 and not area and parsed[1]:
                    second = parsed[1][0]
                    if not re.fullmatch(r"\d{4}", second):
                        area = second
        except Exception as e:
            self.log("  标签区解析失败: %s" % e)

        self.log("  元信息: 年=%s 地区=%s 导=%s 演=%s 备注=%s"
                 % (year, area, director[:12], actor[:12], remarks))

        # ===== 线路与剧集 =====
        # 关键: 面板(panel)顺序 == 标签(data-dropdown-value)顺序,
        #       但 panel 内的 src 序号并不按 1,2,3 递增 (实测 2,1,3),
        #       因此必须按 panel 出现顺序配对标签, 不能用 src 序号反推。
        tab_names = [self._clean(t) for t in _RE_TAB.findall(html)]
        tab_names = [t for t in tab_names if t]

        panel_src_order = []   # 面板顺序 -> src 序号
        for pm in _RE_PANEL.finditer(html):
            seg = html[pm.start():pm.start() + 8000]
            me = _RE_PLAY_A.search(seg)
            if me:
                panel_src_order.append(int(me.group(2)))

        groups = {}
        try:
            for m in _RE_PLAY_A.finditer(html):
                href, src_idx, title = m.group(1), int(m.group(2)), m.group(3)
                # 标签内的 span 文本更干净
                seg = html[m.end():m.end() + 200]
                ms = _RE_SPAN.search(seg)
                ep_name = self._clean(ms.group(1)) if ms else ""
                if not ep_name:
                    ep_name = self._clean(title)
                if not ep_name:
                    ep_name = "第%d集" % len(groups.get(src_idx, []))
                href = href.replace("&amp;", "&")
                groups.setdefault(src_idx, []).append((ep_name, href))
        except Exception as e:
            self.log("  剧集解析失败: %s" % e)

        self.log("  剧集: %s" % {k: len(v) for k, v in groups.items()})
        self.log("  面板顺序: %s | 标签: %s" % (panel_src_order, tab_names))

        if not groups:
            return {"list": []}

        # src 序号 -> 线路别名: 优先按面板顺序与标签一一配对
        alias_map = {}
        for i, s in enumerate(panel_src_order):
            if i < len(tab_names) and s not in alias_map:
                alias_map[s] = tab_names[i]
        # 兜底: 剩余 src 用位次/序号命名
        for s in sorted(groups.keys()):
            if s not in alias_map:
                if s - 1 < len(tab_names) and tab_names[s - 1] \
                        not in alias_map.values():
                    alias_map[s] = tab_names[s - 1]
                else:
                    alias_map[s] = "线路%d" % s

        # 线路排序: 可直连的源(极速/量子等)在前,
        #           需第三方解析的外链(腾讯/爱奇艺/优酷/哔哩等)垫底
        _DIRECT_WORDS = ("极速", "量子", "暴风", "非凡", "资源", "天空",
                         "无尽", "红牛", "魔都", "极速云", "m3u8", "线路")
        _VIP_WORDS = ("腾讯", "爱奇艺", "优酷", "芒果", "哔哩", "B站",
                      "bilibili", "搜狐", "乐视", "PPTV", "咪咕", "央视频")

        def _line_key(s):
            name = alias_map.get(s, "")
            if any(w in name for w in _VIP_WORDS):
                return 2
            if any(w in name for w in _DIRECT_WORDS):
                return 0
            return 1

        play_from = []
        play_url = []
        for s in sorted(groups.keys(), key=lambda x: (_line_key(x), x)):
            eps = groups[s]
            alias = alias_map.get(s, "线路%d" % s)
            play_from.append(alias)
            play_url.append("#".join(
                "%s$%s" % (n, self._fix_url(h)) for n, h in eps))

        # 展示备注: 优先站点真实备注(如"22集全"), 其次线路数
        note = remarks or ("%d条线路" % len(groups))

        return {"list": [{
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_year": year,
            "vod_area": area,
            "vod_score": score,
            "vod_remarks": note,
            "vod_pubdate": updated,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url":  "$$$".join(play_url),
        }]}

    # -------- 自动换源 --------
    def _vod_id(self, play_page):
        m = re.search(r"/vodplay/(\d+)-", play_page)
        return m.group(1) if m else ""

    def _ep_index(self, play_page):
        m = re.search(r"/vodplay/\d+-(\d+)-(\d+)\.html", play_page)
        return int(m.group(2)) if m else 0

    def _find_direct_line(self, vod_id, ep_idx):
        """反查同片其它线路, 找到可直连的 m3u8 (优先极速类)"""
        cache_key = "alt:%s" % vod_id
        now = int(time.time())
        if cache_key in self._play_cache:
            ts, cand = self._play_cache[cache_key]
            if now - ts < 1800:
                return self._try_lines(vod_id, ep_idx, cand)
        html = self._fetch("%s/voddetail/%s.html" % (self.site_url, vod_id))
        if not html:
            return ""
        tab_names = [self._clean(t) for t in _RE_TAB.findall(html)]
        tab_names = [t for t in tab_names if t]
        # 面板顺序 -> src 序号
        order = []
        for pm in _RE_PANEL.finditer(html):
            seg = html[pm.start():pm.start() + 8000]
            me = _RE_PLAY_A.search(seg)
            if me:
                order.append(int(me.group(2)))
        cand = []
        for i, s in enumerate(order):
            name = tab_names[i] if i < len(tab_names) else ""
            if any(w in name for w in ("极速", "量子", "暴风", "非凡", "资源",
                                       "天空", "无尽", "红牛", "魔都")):
                cand.insert(0, s)      # 直连源优先
            elif any(w in name for w in ("腾讯", "爱奇艺", "优酷", "芒果",
                                        "哔哩", "B站", "搜狐", "乐视")):
                continue               # VIP 外链跳过
            else:
                cand.append(s)
        self._play_cache[cache_key] = (now, cand)
        self.log("  换源候选: %s" % cand)
        return self._try_lines(vod_id, ep_idx, cand)

    def _try_lines(self, vod_id, ep_idx, cand):
        for s in cand:
            url = "%s/vodplay/%s-%d-%d.html" % (
                self.site_url, vod_id, s, ep_idx)
            h = self._fetch(url, referer=self.site_url + "/")
            if not h:
                continue
            u = self._extract_play_url(h)
            if u and (".m3u8" in u.lower() or ".mp4" in u.lower()):
                return u
        return ""

    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith("http") else self._fix_url(id)
        self.log("player: %s flag=%s" % (play_page, flag))

        now = int(time.time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 600:
                return res

        real_url = ""
        html = self._fetch(play_page, referer=self.site_url + "/")
        if html:
            real_url = self._extract_play_url(html)
        self.log("  real_url: %s" % (real_url[:200] if real_url else "EMPTY"))

        if real_url:
            low = real_url.lower()
            # 外链嗅探 (腾讯/爱奇艺/优酷/芒果/哔哩等非直链)
            if ".m3u8" not in low and ".mp4" not in low \
                    and ".flv" not in low and not real_url.endswith(".mp4"):
                # ★ 自动换源: 本站多数影片有「极速」直连线路,
                #   当前页是 VIP 外链时, 反查同片直链并直接返回
                ep_idx = self._ep_index(play_page)
                vod_id = self._vod_id(play_page)
                if vod_id and ep_idx:
                    alt = self._find_direct_line(vod_id, ep_idx)
                    if alt:
                        self.log("  ★ 自动换源成功: %s" % alt[:120])
                        res = {
                            "parse": 0, "playUrl": "", "url": alt,
                            "header": {"User-Agent": UA,
                                       "Referer": self.site_url + "/"},
                        }
                        self._play_cache[play_page] = (now, res)
                        return res
                res = {
                    "parse": 1, "playUrl": "", "url": real_url,
                    "header": {"User-Agent": UA},
                }
                self._play_cache[play_page] = (now, res)
                return res

            # 直链 m3u8/mp4
            res = {
                "parse": 0,
                "playUrl": "",
                "url": real_url,
                "header": {
                    "User-Agent": UA,
                    "Referer": self.site_url + "/",
                },
            }
            self._play_cache[play_page] = (now, res)
            return res

        # 兜底: 嗅探播放页
        res = {
            "parse": 1, "playUrl": "", "url": play_page,
            "header": {"User-Agent": UA, "Referer": self.site_url + "/"},
        }
        self._play_cache[play_page] = (now, res)
        return res

    def _extract_play_url(self, html):
        """解析 player_aaaa: encrypt=2 时 url 为 base64(URL编码)"""
        if not html:
            return ""
        m = _RE_PLAYER.search(html)
        raw = m.group(1) if m else ""

        url = ""
        if raw:
            try:
                cfg = json.loads(raw.replace("\\/", "/"))
                url = cfg.get("url", "")
                encrypt = int(cfg.get("encrypt", 0) or 0)
                if encrypt == 2 and url:
                    url = urllib.parse.unquote(
                        base64.b64decode(url + "=" * (-len(url) % 4))
                        .decode("utf-8", "ignore"))
                elif encrypt == 1 and url:
                    url = urllib.parse.unquote(url)
            except Exception as e:
                self.log("  player_aaaa 解析失败: %s" % e)
                url = ""

        if not url:
            # 兜底: 找裸 m3u8 / base64 url 字段
            m2 = re.search(r'"url"\s*:\s*"(J[A-Za-z0-9+/=]+)"', html)
            if m2:
                try:
                    url = urllib.parse.unquote(
                        base64.b64decode(m2.group(1) + "===").decode(
                            "utf-8", "ignore"))
                except Exception:
                    url = ""
            if not url:
                m3 = re.search(r'"url"\s*:\s*"([^"]+)"', html)
                if m3:
                    url = m3.group(1).replace("\\/", "/")

        return url.replace("&amp;", "&")

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
                "User-Agent": UA,
                "Referer": self.site_url + "/",
            }, timeout=15)
            content = rsp.content

            # m3u8: 把相对 key / 分片地址改写为绝对地址后返回
            if ".m3u8" in url.lower():
                text = ""
                try:
                    text = rsp.text if hasattr(rsp, "text") else \
                        content.decode("utf-8", "ignore")
                except Exception:
                    text = content.decode("utf-8", "ignore")
                if "#EXTM3U" in text:
                    base = url.rsplit("/", 1)[0] + "/"
                    text = re.sub(
                        r'URI="([^"]+)"',
                        lambda m: 'URI="%s"' % (
                            m.group(1) if m.group(1).startswith("http")
                            else urllib.parse.urljoin(base, m.group(1))),
                        text)
                    # 相对分片行也补全
                    out = []
                    for line in text.splitlines():
                        s = line.strip()
                        if s and not s.startswith("#") \
                                and not s.startswith("http"):
                            line = urllib.parse.urljoin(base, s)
                        out.append(line)
                    return [200, "application/vnd.apple.mpegurl",
                            "\n".join(out), {"User-Agent": UA}]
                return [200, "application/vnd.apple.mpegurl", text,
                        {"User-Agent": UA}]

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
