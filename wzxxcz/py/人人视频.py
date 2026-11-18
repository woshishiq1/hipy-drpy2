# coding=utf-8
"""
彩虹影视（追剧神器） www.zhengdasifuyuan.com | TVBox Python 爬虫
站点结构（线上实证 2026-11-18，服务端渲染 HTML 采集站，模板 s10）:
  - 首页:   /
  - 分类:   /marathon/<tid>_<page>.html
            （tid: 1 电影 / 2 电视剧 / 3 综艺 / 4 动漫 / 34 短剧）
  - 搜索:   /search/<URL编码关键词>.html
  - 详情:   /have/<id>.html
      · 片名 h1；副标题(拼音) h1 后首个 muted <p>
      · 评分 绿色 bg-green-500 span（豆瓣 8.0，取数字）
      · 年份/地区：评分所在 flex 内后两个 text-muted-foreground span
      · 状态备注：左上角 rounded font-medium div（全28集 / 已完结 / 第24集已完结）
      · 元信息：label span「导演：/主演：/类型：」+ 值 span（短剧可能无导演）
      · 简介：h3「剧情简介」后 div > p
      · 线路：button data-source="<sid>"，文本为线路名，顺序即站点按钮顺序
      · 选集：div#episodes-<sid> 内 a[href=/player/<vid>-<sid>-<nid>.html][data-idx=nid]
        集名文本 01 / 第01集；选集按集号正序、按集号去重
  - 播放:   /player/<vid>-<sid>-<nid>.html
      · 内联脚本 parts=["b64片段", ...]，拼接后 atob(base64) 即 m3u8 直链；
        站点自身再包一层 /jx/index.html?url=<encodeURIComponent(直链)>，
        爬虫直接取解码后的裸 m3u8 直链 parse=0 播放，失败再交客户端嗅探兜底。

站点防护与通过机制（线上实证 2026-11-18）:
  分类墙 /marathon/ 与搜索 /search/ 首次访问会 302 到应用层图片验证码
  /verify_captcha.jsp，答对一次后放行标记只存在服务端 PHPSESSID 会话内，
  同会话后续分类 / 搜索即 200；服务端校验大小写不敏感。
  爬虫内置“取图 → 识别 → 提交 → 复用会话”闭环：
    · 识别器可插拔，优先 ddddocr（运行环境已安装时直接生效，实测 5/5 放行）；
    · 环境无 OCR 引擎时不崩溃，分类 / 搜索返回空，首页 / 详情 / 播放不受影响。
  另有 5001 字节“安全校验”硬拦页（Action Drop Connection，无挑战 cookie），
  属站点风控，爬虫侧不做绕过。
"""
import re
import sys
import json
import time
import base64
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

        def reset_session(self):
            """关闭并丢弃复用坏连接的会话，下次请求重建新连接。"""
            try:
                if self._session is not None:
                    self._session.close()
            except Exception:
                pass
            self._session = None

        def fetch(self, url, headers=None, **kw):
            timeout = kw.pop('timeout', 15)
            r = self._sess.get(url, headers=headers, timeout=timeout, **kw)
            r.encoding = 'utf-8'
            return r

        def log(self, *a, **kw):
            try:
                print("[caihong]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.zhengdasifuyuan.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = ""

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# ===================== 分类（对齐站点导航 /marathon/<tid>_1.html）=====================
# 一级大类 + 电视剧站点二级子分类（tid 均为站点真实路由）
CLASSES = [
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "2",  "type_name": "电视剧"},
    {"type_id": "3",  "type_name": "综艺"},
    {"type_id": "4",  "type_name": "动漫"},
    {"type_id": "34", "type_name": "短剧"},
    {"type_id": "13", "type_name": "国产剧"},
    {"type_id": "14", "type_name": "港剧"},
    {"type_id": "15", "type_name": "欧美剧"},
    {"type_id": "16", "type_name": "日剧"},
    {"type_id": "20", "type_name": "台剧"},
    {"type_id": "21", "type_name": "泰剧"},
    {"type_id": "25", "type_name": "韩剧"},
    {"type_id": "46", "type_name": "海外剧"},
]

# ===== 各分类站点真实筛选选项（取自放行分类页快照，值必须与站点原值逐字一致）=====
_GENRE = {
    "1": ["喜剧", "爱情", "恐怖", "动作", "科幻", "剧情", "战争", "警匪", "犯罪",
          "动画", "奇幻", "武侠", "冒险", "枪战", "悬疑", "惊悚", "经典", "青春",
          "文艺", "微电影", "古装", "历史", "运动", "农村", "儿童", "网络电影"],
    "2": ["古装", "战争", "青春偶像", "喜剧", "家庭", "犯罪", "动作", "奇幻", "剧情",
          "历史", "经典", "乡村", "情景", "商战", "网剧", "其他"],
    "3": ["选秀", "情感", "访谈", "播报", "旅游", "音乐", "美食", "纪实", "曲艺",
          "生活", "游戏互动", "财经", "求职"],
    "4": ["情感", "科幻", "热血", "推理", "搞笑", "冒险", "萝莉", "校园", "动作",
          "机战", "运动", "战争", "少年", "少女", "社会", "原创", "亲子", "益智",
          "励志", "其他"],
    "34": ["都市", "赘婿", "战神", "古代言情", "现代言情", "历史", "脑洞", "玄幻",
           "电视节目", "搞笑", "网剧", "喜剧", "萌宝", "神豪", "致富", "奇幻脑洞",
           "超能", "强者回归", "甜宠", "励志", "豪门恩怨", "复仇", "长生", "神医",
           "马甲", "亲情", "小人物", "奇幻", "无敌", "现实", "重生", "闪婚", "职场商战",
           "穿越", "年代", "权谋", "高手下山", "悬疑", "家国情仇", "虐恋", "古装",
           "时空之旅", "玄幻仙侠", "欢喜冤家", "传承觉醒", "情感", "逆袭", "家庭"],
}
_AREA = {
    "1": ["大陆", "香港", "台湾", "美国", "法国", "英国", "日本", "韩国", "德国",
          "泰国", "印度", "意大利", "西班牙", "加拿大", "其他"],
    "2": ["内地", "韩国", "香港", "台湾", "日本", "美国", "泰国", "英国", "新加坡", "其他"],
    "3": ["内地", "港台", "日韩", "欧美"],
    "4": ["国产", "日本", "欧美", "其他"],
    "34": ["大陆", "香港", "台湾", "美国", "韩国", "日本", "泰国", "新加坡", "马来西亚",
           "印度", "英国", "法国", "加拿大", "西班牙", "俄罗斯", "其它"],
}
_LANG = {
    "1": ["国语", "英语", "粤语", "闽南语", "韩语", "日语", "法语", "德语", "其它"],
    "2": ["国语", "英语", "粤语", "闽南语", "韩语", "日语", "其它"],
    "3": ["国语", "英语", "粤语", "闽南语", "韩语", "日语", "其它"],
    "4": ["国语", "英语", "粤语", "闽南语", "韩语", "日语", "其它"],
    "34": ["国语", "英语", "粤语", "闽南语", "韩语", "日语", "法语", "德语", "其它"],
}
_YEAR = [str(y) for y in range(2026, 1999, -1)]
_RES = ["正片", "预告片", "花絮"]

# 电视剧二级子分类复用电视剧筛选
_ALIAS_FILTER_TID = {"13": "2", "14": "2", "15": "2", "16": "2",
                     "20": "2", "21": "2", "25": "2", "46": "2"}


def _opts(values):
    return [{"n": "全部", "v": ""}] + [{"n": x, "v": x} for x in values]


FILTERS = {}
for c in CLASSES:
    tid = c["type_id"]
    base = _ALIAS_FILTER_TID.get(tid, tid)
    FILTERS[tid] = [
        {"key": "genre", "name": "类型", "value": _opts(_GENRE.get(base, []))},
        {"key": "area",  "name": "地区", "value": _opts(_AREA.get(base, []))},
        {"key": "lang",  "name": "语言", "value": _opts(_LANG.get(base, []))},
        {"key": "year",  "name": "年份", "value": _opts(_YEAR)},
        {"key": "res",   "name": "资源", "value": _opts(_RES)},
    ]

# ===================== 正则 =====================
_RE_HREF = re.compile(r'href="(/have/(\d+)\.html)"', re.I)
_RE_IMG = re.compile(r'data-original="([^"]*)"', re.I)
_RE_H4 = re.compile(r'<h4[^>]*>([\s\S]*?)</h4>', re.I)
# 卡片左上黑底状态标签（第12集已完结 / 正片 / 更新至HD）
_RE_STATUS_CARD = re.compile(r'bg-black/70[\s\S]*?>([\s\S]*?)</div>', re.I)
# 详情海报左上状态标签（第24集已完结 / 已完结 / 全28集）
_RE_REMARK = re.compile(r'bg-primary text-white[\s\S]*?>([\s\S]*?)</div>', re.I)
_RE_H1 = re.compile(r'<h1[^>]*>([\s\S]*?)</h1>', re.I)
_RE_SUBTITLE = re.compile(r'<p[^>]*text-muted-foreground[^>]*>([^<]*)</p>', re.I)
_RE_SCORE = re.compile(r'bg-green-500[^>]*>([\s\S]*?)</span>', re.I)
_RE_MUTED = re.compile(r'<span[^>]*text-muted-foreground[^>]*>([^<]*)</span>', re.I)
_RE_LABEL = re.compile(
    r'<span[^>]*shrink-0[^>]*>(导演|主演|类型|地区|年份|语言)：</span>\s*'
    r'<span[^>]*>([\s\S]*?)</span>', re.I)
_RE_INTRO = re.compile(
    r'剧情简介</h3>\s*<div[^>]*>\s*<p[^>]*>([\s\S]*?)</p>', re.S | re.I)
_RE_META_DESC = re.compile(
    r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', re.I)
_RE_BTN = re.compile(
    r'<button[^>]*data-source="(\d+)"[^>]*>([\s\S]*?)</button>', re.I)
_RE_EP_BOX = re.compile(r'<div id="episodes-(\d+)"[^>]*>([\s\S]*?)(?=<div id="episodes-|$)', re.I)
_RE_EP_A = re.compile(
    r'<a[^>]*href="(/player/\d+-\d+-\d+\.html)"[^>]*data-idx="(\d+)"[^>]*>([\s\S]*?)</a>', re.I)
_RE_EP_A_FALLBACK = re.compile(
    r'<a[^>]*href="(/player/\d+-(\d+)-(\d+)\.html)"[^>]*>([\s\S]*?)</a>', re.I)
_RE_PARTS = re.compile(r'parts\s*=\s*\[([^\]]*)\]', re.S)
_RE_STREAM = re.compile(r'https?://[^"\\\s]*(?:m3u8|mp4)[^"\\\s]*', re.I)


class Spider(Spider):

    def getName(self):
        return "彩虹影视"

    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}

        self.site_url = (self.extend.get("site") or HOST).rstrip("/")
        self.headers = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": self.site_url + "/",
            "Upgrade-Insecure-Requests": "1",
        }
        self.default_pic = DEFAULT_PIC
        self._play_cache = {}
        # 验证码会话状态：答对一次后同 PHPSESSID 会话内复用
        self._captcha_ok = False
        self._ocr = None
        self._ocr_tried = False
        self.log("init: site=%s" % self.site_url)

    # ---------------- 基础工具 ----------------
    def _low_session(self):
        """取底层 requests 会话（兼容基类 _session / _sess 两种暴露方式）。"""
        s = getattr(self, "_session", None)
        if s is None and hasattr(self, "_sess"):
            try:
                s = self._sess
            except Exception:
                s = None
        return s

    def _is_captcha_page(self, text):
        if not text:
            return False
        return ("verify_captcha" in text or "请输入验证码" in text
                or ('captcha.jsp' in text and 'name="captcha"' in text))

    def _is_upstream_error(self, text):
        if not text:
            return True
        low = text.lower()
        return any(k in low for k in (
            "upstream connect error", "connection timeout", "connection reset",
            "bad gateway", "service unavailable", "reset reason",
            "<title>503", "<title>502", "<title>429", "安全校验", "verify_captcha"))

    def _reset_session(self):
        """best-effort 关闭复用坏连接的会话，下次请求重建新连接。"""
        # 会话 cookie 一并丢弃，验证码放行标记随之失效，需重新过验
        self._captcha_ok = False
        try:
            if hasattr(self, "reset_session"):
                self.reset_session()
                return
            sess = getattr(self, "_session", None) or getattr(self, "_sess", None)
            if sess is not None:
                try:
                    sess.close()
                except Exception:
                    pass
            self._session = None
        except Exception:
            pass

    def _load_ocr(self):
        """懒加载 OCR 引擎；环境未安装 ddddocr 时返回 None（不报错崩溃）。"""
        if self._ocr_tried:
            return self._ocr
        self._ocr_tried = True
        try:
            import ddddocr
            self._ocr = ddddocr.DdddOcr(show_ad=False)
            self.log("OCR 引擎 ddddocr 已加载")
        except Exception as e:
            self._ocr = None
            self.log("OCR 引擎不可用: %s" % e)
        return self._ocr

    def _ocr_captcha(self, img_bytes):
        ocr = self._load_ocr()
        if ocr is None or not img_bytes:
            return ""
        try:
            code = ocr.classification(img_bytes) or ""
            # 仅保留字母数字，取前 4 位；服务端校验大小写不敏感
            return re.sub(r"[^A-Za-z0-9]", "", code)[:4]
        except Exception as e:
            self.log("OCR 识别失败: %s" % e)
            return ""

    def _target_path(self, url):
        u = url.replace(self.site_url, "", 1)
        if not u.startswith("/"):
            u = "/" + u
        return u

    def _solve_captcha(self, target_url):
        """同会话：取验证码图 → 识别 → 提交 → 302 放行。成功后会话内复用。"""
        if self._captcha_ok:
            return True
        sess = self._low_session()
        if sess is None:
            self.log("无底层会话，无法过验")
            return False
        target_path = self._target_path(target_url)

        for attempt in range(2):
            try:
                # 先访问目标种入 PHPSESSID（被 302 到验证码页，cookie 已写入会话）
                sess.get(target_url, headers=self.headers, timeout=12, verify=False)
                img = sess.get(self.site_url + "/captcha.jsp",
                               headers=self.headers, timeout=12, verify=False).content
                code = self._ocr_captcha(img)
                if not code:
                    self.log("验证码识别为空，无法自动通过")
                    return False

                post_url = (self.site_url + "/verify_captcha.jsp?redirect="
                            + urllib.parse.quote(target_path, safe=""))
                rsp = sess.post(post_url, data={"captcha": code},
                                headers=self.headers, allow_redirects=False,
                                timeout=12, verify=False)
                if rsp.status_code == 302:
                    self._captcha_ok = True
                    self.log("验证码通过: %s" % code)
                    return True
                self.log("验证码被拒: %s (HTTP %s)" % (code, rsp.status_code))
            except Exception as e:
                self.log("验证码流程异常: %s" % e)
            time.sleep(0.6 * (attempt + 1))
        return False

    def _fetch(self, url, timeout=15, headers=None):
        def _once():
            h = dict(self.headers)
            if headers:
                h.update(headers)
            rsp = self.fetch(url, headers=h, timeout=timeout)
            if hasattr(rsp, "text"):
                return rsp.text or ""
            if hasattr(rsp, "content"):
                return rsp.content.decode("utf-8", "ignore")
            return str(rsp)

        text = ""
        for attempt in range(3):
            try:
                text = _once()
            except Exception as e:
                self.log("fetch FAIL %s -> %s" % (url, e))
                text = ""

            # 命中验证码页：同会话自动过验，成功后重新取一次
            if text and self._is_captcha_page(text):
                if self._solve_captcha(url):
                    try:
                        text = _once()
                    except Exception as e:
                        self.log("过验后重试 FAIL %s -> %s" % (url, e))
                        text = ""
                else:
                    self.log("验证码未能自动通过，本列表返回空")
                    return ""

            if text and not self._is_upstream_error(text):
                return text
            self._reset_session()
            time.sleep(0.8 * (attempt + 1))
        return text

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
        s = re.sub(r"<br\s*/?>", "\n", str(s), flags=re.I)
        s = re.sub(r"<[^>]+>", "", s)
        s = (s.replace("&nbsp;", " ").replace("\xa0", " ")
              .replace("&amp;", "&").replace("&quot;", '"')
              .replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">"))
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n{2,}", "\n", s)
        return s.strip()

    def _is_placeholder_pic(self, pic):
        if not pic:
            return True
        low = pic.lower()
        for bad in ("placeholder", "default", "blank", "loading", "none.gif",
                    "empty.png", "data:image/gif", "load.svg"):
            if bad in low:
                return True
        return False

    # ---------------- 列表卡片解析 ----------------
    def _parse_cards(self, html):
        videos = []
        seen = set()
        if not html:
            return videos

        hits = []
        for m in _RE_HREF.finditer(html):
            href, vid = m.group(1), m.group(2)
            if vid in seen:
                continue
            seen.add(vid)
            hits.append((m.start(), href, vid))

        for pos, href, vid in hits:
            block = html[max(0, pos - 200):pos + 1700]

            # 海报：块内首个 data-original；片名：h4 优先，img alt 兜底（不强求二者顺序）
            pic = ""
            mp = _RE_IMG.search(block)
            if mp:
                pic = mp.group(1)

            title = ""
            # 片名：底部 hover 层 p 优先，h4 次之，img alt 兜底
            mt = re.search(r'<p[^>]*font-medium[^>]*>([\s\S]*?)</p>', block, re.I)
            if mt:
                title = self._clean(mt.group(1))
            if not title:
                mh = _RE_H4.search(block)
                if mh:
                    title = self._clean(mh.group(1))
            if not title:
                ma = re.search(r'<img[^>]*?alt="([^"]*)"', block, re.I)
                if ma:
                    title = self._clean(ma.group(1))
            title = self._clean(title)

            pic = self._fix_url(pic)
            if self._is_placeholder_pic(pic):
                pic = self.default_pic

            # 备注：优先左上黑底状态标签（第12集已完结 / 正片 / 更新至HD）；
            # 缺失时兜底右上角标（首页年份 / 分类评分）
            mrem = _RE_STATUS_CARD.search(block)
            remarks = self._clean(mrem.group(1)) if mrem else ""
            if not remarks:
                mr2 = re.search(r'bg-primary/90[\s\S]*?>([\s\S]*?)</div>', block)
                if mr2:
                    remarks = self._clean(mr2.group(1))

            if not title:
                continue
            videos.append({
                "vod_id": href,
                "vod_name": title[:100],
                "vod_pic": pic,
                "vod_remarks": remarks,
                "vod_subtitle": "",
            })
        return videos

    def _page_count(self, html):
        if not html:
            return 1
        pages = [int(x) for x in re.findall(r'/marathon/\d+_(\d+)(?:/|\.html)', html)]
        pages += [int(x) for x in re.findall(r'/search/[^/"]+/(\d+)\.html', html)]
        if pages:
            return max(1, max(pages))
        return 1

    # ---------------- 首页 / 分类 / 搜索 ----------------
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        html = self._fetch(self.site_url + "/")
        videos = self._parse_cards(html)
        self.log("home: %d 条" % len(videos))
        return {"list": videos}

    def _filter_slug(self, extend):
        # 站点筛选槽位：题材-地区-语言-年份-资源 + 尾部 3 个空占位，空槽留空
        slots = [extend.get("genre", ""), extend.get("area", ""), extend.get("lang", ""),
                 extend.get("year", ""), extend.get("res", ""), "", "", ""]
        return "-".join(slots)

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

        # 站点分类路由：
        #   无筛选第 1 页  /marathon/<tid>_1.html
        #   筛选 / 分页     /marathon/<tid>_<page>/<题材>-<地区>-<语言>-<年份>-<资源>---.html
        base = "%s/marathon/%s_%d" % (self.site_url, str(tid), page)
        if extend or page > 1:
            url = "%s/%s.html" % (base, self._filter_slug(extend))
        else:
            url = base + ".html"
        self.log("category: %s" % url)

        html = self._fetch(url)
        videos = self._parse_cards(html)
        pagecount = self._page_count(html)
        self.log("  最终: %d 条, 总页数 %d" % (len(videos), pagecount))
        return {
            "list": videos, "page": page, "pagecount": pagecount,
            "limit": 30, "total": pagecount * 30,
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        keyword = urllib.parse.quote(str(key or "").strip())
        # 站点搜索分页：第 1 页 /search/<kw>.html，其后 /search/<kw>/<page>.html
        if page <= 1:
            url = "%s/search/%s.html" % (self.site_url, keyword)
        else:
            url = "%s/search/%s/%d.html" % (self.site_url, keyword, page)
        self.log("search: %s" % url)
        html = self._fetch(url)
        videos = self._parse_cards(html)
        self.log("  搜索结果: %d 条" % len(videos))
        return {
            "list": videos, "page": page,
            "pagecount": self._page_count(html) or 1,
            "limit": 30, "total": len(videos),
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------------- 详情字段提取 ----------------
    def _meta_fields(self, html):
        """提取导演/主演/类型/地区/年份/语言 label 字段。"""
        out = {"director": "", "actor": "", "classify": "",
               "area": "", "year": "", "lang": ""}
        keymap = {"导演": "director", "主演": "actor", "类型": "classify",
                  "地区": "area", "年份": "year", "语言": "lang"}
        for m in _RE_LABEL.finditer(html):
            label = self._clean(m.group(1)).rstrip("：:")
            val = self._clean(m.group(2))
            k = keymap.get(label)
            if k and val:
                out[k] = re.sub(r"\s*,\s*", ", ", val)
        return out

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0])
        url = vod_id if vod_id.startswith("http") else self._fix_url(vod_id)
        self.log("detail: %s" % url)

        html = self._fetch(url)
        if not html:
            return {"list": []}

        # 片名
        name = ""
        mh = _RE_H1.search(html)
        if mh:
            name = self._clean(mh.group(1))
        if not name:
            mt = re.search(r"<title>(.*?)</title>", html, re.S)
            if mt:
                name = self._clean(mt.group(1).split("_")[0].split("-")[0])
        name = name or vod_id

        # 副标题（拼音）
        subtitle = ""
        ms = _RE_SUBTITLE.search(html)
        if ms:
            subtitle = self._clean(ms.group(1))

        # 海报
        pic = self.default_pic
        mp = _RE_IMG.search(html)
        if mp:
            pic = self._fix_url(mp.group(1))
            if self._is_placeholder_pic(pic):
                pic = self.default_pic

        # 评分（绿色 span，豆瓣 8.0 -> 8.0）
        score = ""
        msc = _RE_SCORE.search(html)
        if msc:
            raw = self._clean(msc.group(1))
            md = re.search(r"([0-9]+(?:\.[0-9]+)?)", raw)
            if md:
                score = md.group(1)

        # 年份 / 地区（评分所在 flex 内后两个 muted span）
        year, area = "", ""
        mi = html.find("bg-green-500")
        if mi >= 0:
            seg = html[mi:mi + 600]
            muted = [self._clean(x) for x in _RE_MUTED.findall(seg)]
            muted = [x for x in muted if x and not x.endswith("：") and x != "导演："]
            if len(muted) >= 1:
                year = muted[0]
            if len(muted) >= 2:
                area = muted[1]

        # 状态备注
        remarks = ""
        mrem = _RE_REMARK.search(html)
        if mrem:
            remarks = self._clean(mrem.group(1))

        # label 字段
        meta = self._meta_fields(html)
        if not meta["year"]:
            meta["year"] = year
        if not meta["area"]:
            meta["area"] = area
        director, actor = meta["director"], meta["actor"]
        classify, lang = meta["classify"], meta["lang"]

        # 简介
        content = ""
        mint = _RE_INTRO.search(html)
        if mint:
            content = self._clean(mint.group(1))
        if not content:
            mdesc = _RE_META_DESC.search(html)
            if mdesc:
                content = self._clean(mdesc.group(1))
        content = (INTRO_PREFIX + "\n" + content) if content else INTRO_PREFIX

        # ===== 线路（按钮顺序即站点顺序）=====
        buttons = {}
        for m in _RE_BTN.finditer(html):
            sid, name_line = m.group(1), self._clean(m.group(2))
            buttons[sid] = name_line or ("线路%s" % sid)

        # ===== 选集分组（容器 episodes-<sid>），按集号正序、去重 =====
        groups = {}
        order = []
        for mb in _RE_EP_BOX.finditer(html):
            sid, box = mb.group(1), mb.group(2)
            if sid not in order:
                order.append(sid)
            eps = []
            seen_nid = set()
            for ma in _RE_EP_A.finditer(box):
                href, nid, ep_name = ma.group(1), ma.group(2), self._clean(ma.group(3))
                if nid in seen_nid:
                    continue
                seen_nid.add(nid)
                eps.append((int(nid), ep_name or ("第%s集" % str(int(nid) + 1).zfill(2)), href))
            if not eps:
                # 兜底：无 data-idx 的链接
                for ma in _RE_EP_A_FALLBACK.finditer(box):
                    href, sid2, nid, ep_name = ma.group(1), ma.group(2), ma.group(3), self._clean(ma.group(4))
                    if nid in seen_nid:
                        continue
                    seen_nid.add(nid)
                    eps.append((int(nid), ep_name or ("第%s集" % str(int(nid) + 1).zfill(2)), href))
            eps.sort(key=lambda x: x[0])  # 正序
            groups[sid] = eps

        # 容器缺省时，按链接 sid 聚合兜底
        if not groups:
            agg = {}
            for ma in _RE_EP_A_FALLBACK.finditer(html):
                href, sid, nid, ep_name = ma.group(1), ma.group(2), ma.group(3), self._clean(ma.group(4))
                agg.setdefault(sid, {})
                if nid not in agg[sid]:
                    agg[sid][nid] = (int(nid), ep_name or ("第%s集" % str(int(nid) + 1).zfill(2)), href)
            for sid, d in agg.items():
                groups[sid] = sorted(d.values(), key=lambda x: x[0])
                if sid not in order:
                    order.append(sid)

        # 线路顺序：按钮 data-source 顺序优先，其次容器出现顺序
        sid_order = [s for s in buttons.keys()]
        for s in order:
            if s not in sid_order:
                sid_order.append(s)

        play_from, play_url = [], []
        for sid in sid_order:
            eps = groups.get(sid)
            if not eps:
                continue
            line_name = buttons.get(sid) or ("线路%s" % sid)
            lines = ["%s$%s" % (ep_name, href) for _, ep_name, href in eps]
            base, i = line_name, 2
            while line_name in play_from:
                line_name = "%s(%d)" % (base, i)
                i += 1
            play_from.append(line_name)
            play_url.append("#".join(lines))

        if not play_from:
            self.log("  未解析到选集")
            return {"list": []}

        vod = {
            "vod_id": vod_id,
            "vod_name": name[:100],
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_score": score,
            "vod_remarks": remarks or ("%d条线路" % len(play_from)),
            "vod_area": meta["area"] or area,
            "vod_year": meta["year"] or year,
            "vod_lang": lang,
            "vod_classify": classify,
            "type_name": classify,
            "vod_alias": subtitle,
            "vod_update": remarks,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }
        return {"list": [vod]}

    # ---------------- 播放 ----------------
    def _decode_parts(self, html):
        """parts=["b64",...] 拼接后 base64 解码，返回裸 m3u8/mp4 直链。"""
        if not html:
            return ""
        m = _RE_PARTS.search(html)
        if not m:
            return ""
        parts = re.findall(r'"([^"]*)"', m.group(1))
        if not parts:
            return ""
        raw = "".join(parts).strip()
        # 补齐 base64 padding 到 4 的倍数
        raw += "=" * (-len(raw) % 4)
        try:
            decoded = base64.b64decode(raw).decode("utf-8", "ignore")
        except Exception:
            return ""
        decoded = decoded.strip()
        if decoded.startswith("http") and _RE_STREAM.search(decoded):
            return decoded
        return ""

    def _extract_stream(self, html):
        if not html:
            return ""
        stream = self._decode_parts(html)
        if stream:
            return stream
        # 兜底：页面直接出现裸 m3u8/mp4
        m = _RE_STREAM.search(html.replace("\\/", "/"))
        if m:
            url = m.group(0)
            if "zhengdasifuyuan.com" not in url:
                return url
        return ""

    def playerContent(self, flag, id, vipFlags):
        play_page = id if str(id).startswith("http") else self._fix_url(id)
        self.log("player: %s" % play_page)

        now = int(time.time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 600:
                return res

        header = {"User-Agent": UA, "Referer": self.site_url + "/"}

        # 传入本身已是裸直链，直接放行
        if _RE_STREAM.search(play_page):
            res = {"parse": 0, "playUrl": "", "url": play_page, "header": header}
            self._play_cache[play_page] = (now, res)
            return res

        stream = ""
        if "/player/" in play_page:
            html = self._fetch(play_page)
            stream = self._extract_stream(html)

        if stream:
            res = {"parse": 0, "playUrl": "", "url": stream, "header": header}
            self._play_cache[play_page] = (now, res)
            self.log("  => 直链 parse=0 %s" % stream[:140])
            return res

        # 兜底：交客户端嗅探播放页
        res = {"parse": 1, "playUrl": "", "url": play_page, "header": header}
        self._play_cache[play_page] = (now, res)
        self.log("  => 嗅探兜底 parse=1 %s" % play_page[:120])
        return res

    # ---------------- 其他契约方法 ----------------
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
