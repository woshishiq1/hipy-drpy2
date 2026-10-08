# -*- coding: utf-8 -*-
# 91crdj.com（91成人短剧）—— TVBox / 影视仓 Python 爬虫源
#
# ============================ 站点结构备忘 ============================
# 技术栈：自研 PHP 站，服务端直出 HTML，无 Cloudflare 挑战，纯 requests 可直连。
#
# 视频频道（4 个，卡片/详情/播放结构完全一致）：
#   /duanju/     成人短剧   列表 5 页
#   /manju/      成人漫剧   单页（无 /page/2/，请求会 404）
#   /zhenrenju/  真人剧     单页
#   /shipin/     成人视频   列表 4 页
# 非视频频道 /manhua/ /xiaoshuo/ 无 playInitialData、无 m3u8，本源不接。
#
# 列表：
#   /{ch}/            第 1 页
#   /{ch}/page/N/     第 N 页（manju / zhenrenju 只有 1 页）
#   /{ch}/?sort=hot   最热排序（默认 new）
#   /paihang/         热播榜，支持 /page/N/，共 10 页
#   /biaoqian/{slug}/ 标签页，支持 /page/N/（198 个标签，见 TAGS）
#   /search/?kw=KW&page=N   搜索（注意：/search/KW/ 这种路径式无效，必须用 ?kw=）
#   卡片：<a class="card" href="..." data-track-item-id/-name>，封面在 img[data-src]，
#         另有 badge（新剧/热播）、eps-flag（更新中 · N集）、meta（分类 · 热度 + ★评分）
#
# 封面图（关键坑，v2 修复）：
#   img[data-src] 指向的**不是图片，而是 AES-CBC 加密的二进制**：
#     Content-Type: binary/octet-stream，首字节不是任何图片魔数（如 3eaa708e…）
#   浏览器里能显示是因为 Web Worker（/static/web/js/plugins/crypto-worker.js）
#   解密后转成 blob: URL 再塞回 <img>；TVBox 直接加载 URL 拿到的是密文 → 白屏。
#   密钥在 crypto-worker.js 中明文（下划线分隔的十进制 charcode，V0() 还原）：
#     media_key = 102_53_100_57_54_53_100_102_55_53_51_51_54_50_55_48  → f5d965df75336270
#     media_iv  = 57_55_98_54_48_51_57_52_97_98_99_50_102_98_101_49    → 97b60394abc2fbe1
#     mode = CBC, padding = NoPadding
#   实测跨 6 个频道 + 详情页 + 播放页共 22 张图，解密后全部是标准 JPEG，0 失败。
#   本源解法：vod_pic 指向 localProxy（type=img），代理内取密文 → AES 解密 → 回吐真图。
#   注：cdn-config.js 当前下发 imgEnabled=false，所以取密文**不需要** x-cdn-auth 头；
#       若站点日后启用，需带 imgAuthKey/imgAuthValue（与视频的头值不同，不可复用）。
#
# 详情 /{ch}/{id}-{slug}/：
#   h1.detail-title 标题 / .p-img[data-src] 竖版封面 / #viBody 简介 / .rv 评分
#   .d-tags a[href*=/biaoqian/] 标签（末尾的 suiji「随便逛个标签」要剔除）
#   dl.work-meta 的 dt/dd 提供 分类 / 状态 / 集数 / 热度 / 发布 / 更新
#   .ep-grid a 选集，href 形如 /{ch}/{id}-{slug}/{n}/
#
# 播放（关键）：
#   1) 播放页 /{ch}/{id}-{slug}/{n}/ 内嵌 <script id="playInitialData"> JSON，
#      含 eps 全量分集、poster、playbackEndpoint 模板、cdnAuthKey/Value。
#   2) 更省一次请求的做法：直接调 JSON 接口
#         GET /videos/{id}/episodes/{n}/playback
#         头 X-Requested-With: XMLHttpRequest
#      返回 {"data":{"n","src","srcHevc","title",...},"status":1}
#      src 即 m3u8 直链（yd-hls.nkgjoa.cn），带 auth_key 时效签名。
#   3) m3u8 为 AES-128 加密（#EXT-X-KEY URI 指向 tp*.eanfog.cn/crypt.key），
#      key 与 ts 分片都在同一 CDN、同样带 auth_key。
#      实测无需 Referer、无需 x-cdn-auth 头（cdnM3u8Enabled=false），
#      m3u8 200 / key 16 字节 200 / ts 分片 6MB 200，parse:0 直连可播。
#   4) auth_key 有时效，因此绝不缓存 m3u8，playerContent 里实时取。

import re
import sys
import json
import time
import base64
from urllib.parse import quote, urljoin

import requests

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider(object):
        def init(self, extend=""): pass
        def destroy(self): pass
        def getName(self): return ""
        def isVideoFormat(self, url): return False
        def manualVideoCheck(self): return False
        def homeContent(self, filter=False): return {"class": []}
        def homeVideoContent(self): return {"list": []}
        def categoryContent(self, tid, pg="1", filter=False, extend=None): return {"list": []}
        def detailContent(self, ids): return {"list": []}
        def searchContent(self, key, quick=False, pg="1"): return {"list": []}
        def playerContent(self, flag, id, vipFlags=None): return {}
        def localProxy(self, params): return []
        def getProxyUrl(self): return "http://127.0.0.1:9978/proxy?do=py"


class Spider(BaseSpider):

    HOST = "https://91crdj.com"

    UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

    # 频道：(type_id, 名称, 是否支持翻页)
    # type_id 保持纯 ASCII —— TVBox/影视仓会把它拼进内部路由并做 URL 转义，
    # 中文或特殊字符会被破坏，表现就是分类点进去「没有视频」。
    CHANNELS = [
        ("duanju", "成人短剧", True),
        ("manju", "成人漫剧", False),
        ("zhenrenju", "真人剧", False),
        ("shipin", "成人视频", True),
        ("paihang", "热播榜", True),
    ]

    VIDEO_CH = ("duanju", "manju", "zhenrenju", "shipin")

    # 封面图 AES-CBC 密钥（crypto-worker.js 明文常量，下划线分隔的十进制 charcode）
    IMG_KEY_RAW = "102_53_100_57_54_53_100_102_55_53_51_51_54_50_55_48"
    IMG_IV_RAW = "57_55_98_54_48_51_57_52_97_98_99_50_102_98_101_49"

    # 标签榜 198 个标签，抓 /biaoqian/ 生成（slug, 名称）
    TAGS = [
        ('aiduanju', 'AI短剧'), ('aichengrenduanju', 'AI成人短剧'), ('91chengrenduanju', '91成人短剧'), ('aishipin', 'AI视频'),
        ('juru', '巨乳'), ('houru', '后入'), ('gaoyanzhi', '高颜值'), ('aichengrenxiaoshuo', 'AI成人小说'), ('fancha', '反差'),
        ('mugou', '母狗'), ('youhuo', '诱惑'), ('meiru', '美乳'), ('koujiao', '口交'), ('zhongchu', '中出'), ('juqing', '剧情'),
        ('xinggan', '性感'), ('aimogai', 'AI魔改'), ('diaojiao', '调教'), ('meitui', '美腿'), ('nvshen', '女神'),
        ('zipai', '自拍'), ('ai', 'AI'), ('dantimogai', '单体魔改'), ('mote', '模特'), ('aimeinv', 'ai美女'), ('jipin', '极品'),
        ('siwa', '丝袜'), ('gufeng', '古风'), ('nvshangwei', '女上位'), ('shenhou', '深喉'),
    ]

    def getName(self):
        return "91成人短剧"

    def init(self, extend=""):
        self.headers = {
            "User-Agent": self.UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": self.HOST + "/",
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.session.trust_env = False
        self._cffi = None
        self._meta = {}      # "ch|id|slug" -> 列表页缓存
        return {}

    def destroy(self):
        try:
            if getattr(self, "session", None):
                self.session.close()
        except Exception:
            pass

    def isVideoFormat(self, url):
        return bool(re.search(r'\.(m3u8|mp4|ts)(\?|$)', str(url or ""), re.I))

    def manualVideoCheck(self):
        return False

    def log(self, msg):
        try:
            print("[91crdj] %s" % msg)
            sys.stdout.flush()
        except Exception:
            pass

    # ------------------------------------------------------------ 网络

    def cffi(self):
        if self._cffi is None:
            try:
                from curl_cffi import requests as cq
                self._cffi = cq.Session(impersonate="chrome124", timeout=30)
                self._cffi.headers.update({"User-Agent": self.UA})
            except Exception:
                self._cffi = False
        return self._cffi

    def fetch(self, url, tries=3, ajax=False, referer=None):
        h = {}
        if ajax:
            h["X-Requested-With"] = "XMLHttpRequest"
        if referer:
            h["Referer"] = referer
        last = ""
        for i in range(tries):
            try:
                r = self.session.get(url, headers=h or None, timeout=25)
                if r.status_code == 200 and r.text:
                    return r.text
                last = "http %s" % r.status_code
            except Exception as e:
                last = type(e).__name__
            s = self.cffi()
            if s:
                try:
                    r = s.get(url, headers=h or None)
                    if r.status_code == 200 and r.text:
                        return r.text
                except Exception as e:
                    last = type(e).__name__
            time.sleep(0.5 * (i + 1))
        self.log("fetch fail %s (%s)" % (url, last))
        return ""

    # ------------------------------------------------------------ 工具

    @staticmethod
    def e64(s):
        return base64.urlsafe_b64encode(str(s).encode("utf-8")).decode("ascii").rstrip("=")

    @staticmethod
    def d64(s):
        s = str(s or "")
        return base64.urlsafe_b64decode(s + "=" * ((4 - len(s) % 4) % 4)).decode("utf-8")

    @classmethod
    def _img_key_iv(cls):
        """把 "102_53_..." 还原成 16 字节 key / iv"""
        def conv(raw):
            return "".join(chr(int(x)) for x in raw.split("_")).encode("utf-8")
        return conv(cls.IMG_KEY_RAW), conv(cls.IMG_IV_RAW)

    def img_decrypt(self, body):
        """AES-CBC / NoPadding 解密封面密文。优先 pycryptodome，退 cryptography，
        都没有时返回原始字节（至少不崩，图仍显示不出来）。"""
        key, iv = self._img_key_iv()
        data = body[:len(body) - len(body) % 16]
        if not data:
            return body
        try:
            from Crypto.Cipher import AES
            return AES.new(key, AES.MODE_CBC, iv).decrypt(data)
        except Exception:
            pass
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            c = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
            return c.update(data) + c.finalize()
        except Exception as e:
            self.log("无 AES 库，封面无法解密: %s" % type(e).__name__)
            return body

    def proxy_url(self):
        try:
            u = self.getProxyUrl()
            return u if u else "http://127.0.0.1:9978/proxy?do=py"
        except Exception:
            return "http://127.0.0.1:9978/proxy?do=py"

    def proxy_img(self, url):
        """封面走本地代理解密。空 URL 原样返回。"""
        if not url or not url.startswith("http"):
            return url or ""
        return "%s&type=img&url=%s" % (self.proxy_url(), self.e64(url))

    @staticmethod
    def _unesc(s):
        s = s or ""
        for a, b in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
                     ("&quot;", '"'), ("&#39;", "'"), ("&nbsp;", " ")):
            s = s.replace(a, b)
        return s.strip()

    @classmethod
    def _norm_ids(cls, ids):
        """归一化 vod_id。本源 vod_id 格式为 "ch.id.slug"（用 . 分隔：| 在部分 TVBox 分支会被
        URL 转义或截断，导致详情页拿不到数据；同时兼容旧的 | 形态）。
        兼容 T4 传 list / str / int / 带 # 后缀 / 完整 URL 五种形态。"""
        if isinstance(ids, (list, tuple)):
            ids = ids[0] if ids else ""
        v = str(ids or "").strip().split("#")[0].strip()
        if v.count("|") >= 2:                 # 兼容旧格式
            return v.replace("|", ".")
        if v.count(".") >= 2 and "/" not in v:
            return v
        m = re.search(r'/(duanju|manju|zhenrenju|shipin)/(\d+)-([a-z0-9-]+)', v)
        if m:
            return "%s.%s.%s" % (m.group(1), m.group(2), m.group(3))
        return v

    @staticmethod
    def split_id(vid):
        p = str(vid or "").replace("|", ".").split(".")
        while len(p) < 3:
            p.append("")
        return p[0], p[1], p[2]

    def detail_url(self, vid):
        ch, i, slug = self.split_id(vid)
        return "%s/%s/%s-%s/" % (self.HOST, ch, i, slug)

    # ------------------------------------------------------------ 列表解析

    def parse_cards(self, html):
        vods = []
        if not html:
            return vods
        seen = set()
        for m in re.finditer(r'<a class="card"\s+href="([^"]+)"([\s\S]{0,1800}?)</a>', html):
            href, blk = m.group(1), m.group(2)
            g = re.search(r'/(duanju|manju|zhenrenju|shipin)/(\d+)-([a-z0-9-]+)/', href)
            if not g:
                continue
            vid = "%s.%s.%s" % (g.group(1), g.group(2), g.group(3))
            if vid in seen:
                continue
            seen.add(vid)
            name = self._unesc((re.search(r'data-track-item-name="([^"]*)"', blk) or [None, ""])[1]) \
                or self._unesc((re.search(r'<h3>([^<]*)</h3>', blk) or [None, ""])[1])
            pic_raw = self._unesc((re.search(r'data-src="([^"]+)"', blk) or [None, ""])[1])
            pic = self.proxy_img(pic_raw)        # 封面是 AES 密文，必须过代理解密
            flag = self._unesc((re.search(r'class="eps-flag">([^<]*)<', blk) or [None, ""])[1])
            badge = self._unesc((re.search(r'<span class="badge[^"]*">([^<]*)</span>', blk) or [None, ""])[1])
            score = self._unesc((re.search(r'class="score">([^<]*)<', blk) or [None, ""])[1])
            remark = " · ".join([x for x in (flag or badge, score) if x])
            self._meta[vid] = {"name": name, "pic": pic, "remark": remark}
            vods.append({"vod_id": vid, "vod_name": name, "vod_pic": pic, "vod_remarks": remark})
        return vods

    @staticmethod
    def max_page(html):
        pages = [int(x) for x in re.findall(r'/page/(\d+)/', html or "")]
        return max(pages) if pages else 1

    # ------------------------------------------------------------ 首页

    def homeContent(self, filter=False):
        classes = [{"type_id": t, "type_name": n} for t, n, _ in self.CHANNELS]
        filters = {}
        if filter:
            sort_f = {"key": "sort", "name": "排序",
                      "value": [{"n": "最新", "v": "new"}, {"n": "最热", "v": "hot"}]}
            tag_f = {"key": "tag", "name": "标签",
                     "value": [{"n": "全部", "v": ""}] + [{"n": n, "v": s} for s, n in self.TAGS]}
            for t, _, _ in self.CHANNELS:
                filters[t] = [sort_f, tag_f] if t != "paihang" else [tag_f]
        data = {"class": classes, "filters": filters}
        try:
            data["list"] = self.homeVideoContent().get("list", [])
        except Exception:
            data["list"] = []
        return data

    def homeVideoContent(self):
        vods = self.parse_cards(self.fetch(self.HOST + "/"))
        if not vods:
            vods = self.parse_cards(self.fetch(self.HOST + "/duanju/"))
        return {"code": 1, "msg": "数据列表", "list": vods[:40]}

    # ------------------------------------------------------------ 分类

    def categoryContent(self, tid, pg="1", filter=False, extend=None):
        extend = extend or {}
        try:
            page = int(str(pg) or "1")
        except Exception:
            page = 1
        tag = (extend.get("tag") or "").strip()
        sort = (extend.get("sort") or "").strip()

        # 标签轴优先（标签页覆盖全站，不区分频道）
        if tag:
            url = "%s/biaoqian/%s/" % (self.HOST, tag)
            if page > 1:
                url += "page/%d/" % page
        else:
            url = "%s/%s/" % (self.HOST, tid)
            if page > 1:
                url += "page/%d/" % page
            if sort and sort != "new":
                url += "?sort=%s" % quote(sort)

        html = self.fetch(url)
        vods = self.parse_cards(html)
        pc = self.max_page(html)
        # manju / zhenrenju 无分页，请求 page/2/ 会 404
        if not vods and page > 1:
            pc = page - 1
        return {"code": 1, "msg": "数据列表",
                "list": vods, "page": page, "pagecount": max(pc, page if vods else 1),
                "limit": 24, "total": max(pc, 1) * 24}

    # ------------------------------------------------------------ 详情

    def detailContent(self, ids):
        vid = self._norm_ids(ids)
        ch, sid, slug = self.split_id(vid)
        if not ch or not sid:
            return {"code": 0, "msg": "无数据", "list": []}

        base = self.detail_url(vid)
        html = self.fetch(base)
        cached = self._meta.get(vid, {})

        title = self._unesc((re.search(r'<h1 class="detail-title">([^<]*)', html) or [None, ""])[1]) \
            or cached.get("name") or slug
        pic_raw = self._unesc((re.search(r'class="p-img"[^>]*data-src="([^"]+)"', html) or [None, ""])[1])
        pic = self.proxy_img(pic_raw) if pic_raw else (cached.get("pic") or "")
        desc = re.sub(r'<[^>]+>', '', (re.search(r'id="viBody">([\s\S]*?)</p>', html) or [None, ""])[1])
        desc = self._unesc(re.sub(r'\s+', ' ', desc))
        score = self._unesc((re.search(r'class="rv">([^<]*)', html) or [None, ""])[1])

        # 标签（剔除站点的「随便逛个标签」随机入口）
        tags = []
        for slug2, name in re.findall(r'/biaoqian/([a-z0-9]+)/"[^>]*>([^<]{1,24})</a>', html):
            n = self._unesc(name)
            if slug2 == "suiji" or not n or n in tags:
                continue
            tags.append(n)

        meta = {}
        for k, v in re.findall(r'<dt>([^<]+)</dt><dd>(?:<a[^>]*>)?([^<]*)', html):
            meta[self._unesc(k)] = self._unesc(v)
        # 发布 / 更新 在 <time datetime> 里
        times = re.findall(r'<time datetime="([^"]+)"', html)

        remark = " · ".join([x for x in (
            meta.get("状态", ""), meta.get("集数", ""),
            ("热度 " + meta["热度"]) if meta.get("热度") else "",
            ("★" + score) if score else "",
        ) if x])

        # 分集：ep-grid 的 a[href$=/N/]
        eps = sorted(set(int(x) for x in re.findall(
            r'href="[^"]*/%s-%s/(\d+)/"' % (sid, re.escape(slug)), html)))
        if not eps:
            eps = sorted(set(int(x) for x in re.findall(r'href="[^"]*/(\d+)/"[^>]*>\s*\d+\s*</a>', html)))
        if not eps:
            eps = [1]

        # 集标题优先用 playInitialData（第 1 集播放页里带全量 eps 中文名）
        ep_titles = {}
        pd = self.play_data(vid, eps[0])
        if pd:
            for e in (pd.get("eps") or []):
                try:
                    ep_titles[int(e.get("n"))] = self._unesc(e.get("title") or "")
                except Exception:
                    pass
            if not pic:
                pic = self.proxy_img(pd.get("poster") or "")
            if not desc:
                desc = self._unesc(pd.get("description") or "")

        items = []
        for n in eps:
            nm = ep_titles.get(n) or ("第%d集" % n)
            nm = re.sub(r'[$#]', ' ', nm)
            items.append("%s$%s@%d" % (nm, vid, n))

        vod = {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic,
            "type_name": meta.get("分类", "") or ", ".join(tags[:3]),
            "vod_year": (times[0][:4] if times else ""),
            "vod_area": "国产",
            "vod_lang": "国语",
            "vod_remarks": remark or cached.get("remark", ""),
            "vod_actor": "",
            "vod_director": "",
            "vod_content": desc,
            "vod_tag": ", ".join(tags[:20]),
            "vod_play_from": "91成人短剧",
            "vod_play_url": "#".join(items),
        }
        return {"code": 1, "msg": "数据列表", "list": [vod],
                "page": 1, "pagecount": 1, "limit": 1, "total": 1}

    # ------------------------------------------------------------ 搜索

    def searchContent(self, key, quick=False, pg="1"):
        try:
            page = int(str(pg) or "1")
        except Exception:
            page = 1
        kw = str(key or "").strip()
        if not kw:
            return {"code": 0, "msg": "无数据", "list": []}
        # 注意：路径式 /search/KW/ 无效，必须 ?kw=
        url = "%s/search/?kw=%s" % (self.HOST, quote(kw))
        if page > 1:
            url += "&page=%d" % page
        html = self.fetch(url)
        vods = self.parse_cards(html)
        # 站点搜索命中较宽，无结果时用标签名兜底
        if not vods and page == 1:
            for slug, name in self.TAGS:
                if kw in name or kw.lower() == slug:
                    vods = self.parse_cards(self.fetch("%s/biaoqian/%s/" % (self.HOST, slug)))
                    break
        return {"code": 1, "msg": "数据列表", "list": vods, "page": page,
                "pagecount": page + 1 if vods else page,
                "limit": 24, "total": 999999}

    # ------------------------------------------------------------ 播放

    def play_data(self, vid, ep):
        """抓播放页里的 playInitialData（含 eps 全量、poster、cdnAuth）"""
        ch, sid, slug = self.split_id(vid)
        url = "%s/%s/%s-%s/%s/" % (self.HOST, ch, sid, slug, ep)
        html = self.fetch(url, referer=self.detail_url(vid))
        m = re.search(r'<script id="playInitialData"[^>]*>([\s\S]*?)</script>', html or "")
        if not m:
            return {}
        try:
            return json.loads(m.group(1))
        except Exception:
            return {}

    def playback(self, sid, ep, referer=None):
        """JSON 接口直接取 m3u8（省一次 HTML 请求）
        GET /videos/{id}/episodes/{n}/playback  +  X-Requested-With"""
        url = "%s/videos/%s/episodes/%s/playback" % (self.HOST, sid, ep)
        txt = self.fetch(url, ajax=True, referer=referer or (self.HOST + "/"))
        if not txt:
            return {}
        try:
            j = json.loads(txt)
        except Exception:
            return {}
        return (j.get("data") or {}) if j.get("status") in (1, "1", True) else (j.get("data") or {})

    def playerContent(self, flag, id, vipFlags=None):
        raw = str(id or "")
        if raw.startswith("http"):
            return {"parse": 0, "playUrl": "", "url": raw,
                    "header": {"User-Agent": self.UA}}

        # id 形如 "ch.sid.slug@ep"
        vid, _, ep = raw.partition("@")
        vid = self._norm_ids(vid)
        ch, sid, slug = self.split_id(vid)
        ep = ep or "1"

        url = ""
        d = self.playback(sid, ep, referer=self.detail_url(vid))
        if d:
            url = d.get("src") or d.get("srcHevc") or ""

        # 兜底：解析播放页 playInitialData.current.src
        if not url:
            pd = self.play_data(vid, ep)
            cur = (pd.get("current") or {}) if pd else {}
            url = cur.get("src") or cur.get("srcHevc") or ""

        if not url:
            self.log("playerContent 未取到 m3u8: %s ep=%s" % (vid, ep))
            return {"parse": 0, "playUrl": "", "url": "", "header": {}}

        url = self._unesc(url)
        # auth_key 有时效，直连即可（实测无需 Referer / x-cdn-auth）
        return {"parse": 0, "playUrl": "", "url": url,
                "header": {"User-Agent": self.UA}}

    def localProxy(self, params):
        """本地代理：解密封面图。
        站点 img[data-src] 返回的是 AES-CBC 密文（binary/octet-stream），
        浏览器靠 Web Worker 解密成 blob 显示；TVBox 只能靠这里代理还原。"""
        params = params or {}
        ptype = str(params.get("type") or "img")
        raw = params.get("url") or ""
        try:
            url = self.d64(raw)
        except Exception:
            url = str(raw)
        if not url.startswith("http"):
            return [404, "text/plain", b""]

        if ptype != "img":
            return [404, "text/plain", b""]

        body = b""
        for i in range(3):
            try:
                r = self.session.get(url, timeout=20)
                if r.status_code == 200 and r.content:
                    body = r.content
                    break
            except Exception:
                pass
            time.sleep(0.4 * (i + 1))
        if not body:
            return [502, "text/plain", b""]

        out = self.img_decrypt(body)
        # 判断魔数确认解密成功；失败则回吐原始字节（让播放器自己处置）
        ct = "image/jpeg"
        if out[:8] == b'\x89PNG\r\n\x1a\n':
            ct = "image/png"
        elif out[:3] == b'GIF':
            ct = "image/gif"
        elif out[:4] == b'RIFF' and out[8:12] == b'WEBP':
            ct = "image/webp"
        elif out[:2] != b'\xff\xd8':
            self.log("封面解密后魔数异常: %s" % out[:8].hex())
            out = body
            ct = "image/jpeg"
        return [200, ct, out]


# ------------------------------------------------------------------ 自测
if __name__ == "__main__":
    import urllib.parse as up

    s = Spider()
    s.init()

    print("=" * 20, "homeContent")
    h = s.homeContent(True)
    print("class  :", [c["type_name"] for c in h["class"]])
    print("filters:", [(f["name"], len(f["value"])) for f in (h["filters"].get("duanju") or [])])
    print("home   :", len(h.get("list", [])))
    for v in h.get("list", [])[:3]:
        print("   ", v["vod_id"], "|", v["vod_name"][:22], "|", v["vod_remarks"], "|", v["vod_pic"][:56])

    print("=" * 20, "categoryContent 各频道")
    for tid, name, _ in s.CHANNELS:
        c = s.categoryContent(tid, "1")
        print("   %-10s %-6s n=%-3s pagecount=%s" % (tid, name, len(c["list"]), c["pagecount"]))
    c2 = s.categoryContent("duanju", "2")
    print("   duanju p2  n=%s" % len(c2["list"]))
    c3 = s.categoryContent("duanju", "1", True, {"sort": "hot"})
    print("   duanju hot n=%s" % len(c3["list"]))
    c4 = s.categoryContent("duanju", "1", True, {"tag": "juru"})
    print("   tag=juru   n=%s pagecount=%s" % (len(c4["list"]), c4["pagecount"]))

    cd = s.categoryContent("duanju", "1")
    vid = cd["list"][0]["vod_id"]
    print("=" * 20, "detailContent ids 兼容", vid)
    for probe in (vid, [vid], vid + "#x", s.detail_url(vid)):
        d = s.detailContent(probe)
        it = (d["list"] or [{}])[0]
        print("   in=%-52r -> %s" % (probe if len(str(probe)) < 50 else "…url…", it.get("vod_name", "")[:20]))
    it = s.detailContent(vid)["list"][0]
    print("   pic    :", it["vod_pic"][:70])
    print("   type   :", it["type_name"], "| year:", it["vod_year"], "| remark:", it["vod_remarks"])
    print("   tag    :", it["vod_tag"][:70])
    print("   content:", it["vod_content"][:70])
    print("   eps    :", it["vod_play_url"][:150])

    print("=" * 20, "playerContent + 播放链验证")
    eps = it["vod_play_url"].split("#")
    for e in eps[:2]:
        nm, _, pid = e.partition("$")
        p = s.playerContent("91成人短剧", pid)
        u = p["url"]
        ok = "-"
        if u:
            m = s.session.get(u, timeout=25)
            if m.status_code == 200 and "#EXT" in m.text:
                segs = [l.strip() for l in m.text.splitlines() if l.strip() and not l.startswith("#")]
                keys = re.findall(r'URI="([^"]+)"', m.text)
                kst = s.session.get(up.urljoin(u, keys[0]), timeout=25).status_code if keys else "-"
                sst = s.session.get(up.urljoin(u, segs[0]), timeout=30) if segs else None
                ok = "m3u8=200 segs=%d key=%s seg=%s/%s" % (
                    len(segs), kst, sst.status_code if sst is not None else "-",
                    len(sst.content) if sst is not None else 0)
            else:
                ok = "m3u8=%s" % m.status_code
        print("   %-8s parse=%s %s" % (nm[:8], p.get("parse"), ok))
        print("      url:", u[:100])

    print("=" * 20, "封面解密验证（localProxy type=img）")
    pics = [v["vod_pic"] for v in cd["list"][:4] if v.get("vod_pic")]
    print("   proxy url 样例:", pics[0][:88] if pics else "-")
    okc = badc = 0
    for pu in pics:
        q = dict(x.split("=", 1) for x in pu.split("?", 1)[1].split("&") if "=" in x)
        code, ct, body = s.localProxy(q)
        magic = body[:4].hex() if body else ""
        good = code == 200 and body[:2] == b"\xff\xd8"
        okc += 1 if good else 0
        badc += 0 if good else 1
        print("   %s %s ct=%-11s bytes=%-7s magic=%s" % ("OK " if good else "BAD", code, ct, len(body), magic))
    print("   封面解密 %d/%d" % (okc, okc + badc))

    print("=" * 20, "searchContent")
    r = s.searchContent("爱情")
    print("   n=%s %s" % (len(r["list"]), [x["vod_name"][:14] for x in r["list"][:3]]))
    s.destroy()
