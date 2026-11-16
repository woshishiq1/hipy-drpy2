# coding=utf-8
"""
果果短剧 app.ggduanju.com | TVBox Python 爬虫
后端: baidu.com.ifengying.cn  (index.php/dsv1.{接口})
响应: AES-128-CBC / PKCS7 / base64, key=iv=EFCD8D3D1DAA31F4
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

        def fetch(self, url, params=None, headers=None, timeout=15, **kw):
            r = self._sess.get(url, params=params, headers=headers,
                               timeout=timeout, **kw)
            r.encoding = 'utf-8'
            return r

        def post(self, url, data=None, json=None, headers=None,
                 timeout=15, **kw):
            r = self._sess.post(url, data=data, json=json, headers=headers,
                                timeout=timeout, **kw)
            r.encoding = 'utf-8'
            return r

        def log(self, *a, **kw):
            try:
                print("[ggduanju]", *a)
            except Exception:
                pass

    Spider = _BaseSpider

try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad as _unpad
    _HAS_CRYPTO = True
except Exception:
    _HAS_CRYPTO = False


HOST = "https://app.ggduanju.com"
API_HOST = "https://baidu.com.ifengying.cn"
API_PREFIX = "/index.php/dsv1."
AES_KEY = b"EFCD8D3D1DAA31F4"
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
      "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 "
      "Mobile/15E148 Safari/604.1")
DEFAULT_PIC = HOST + "/img/logo1.png"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

# 兜底分类（以站点 config.head_nav / type 实时返回为准）
_FALLBACK_CLASSES = [
    {"type_id": "netflix", "type_name": "Netflix"},
    {"type_id": "1", "type_name": "短剧"},
    {"type_id": "2", "type_name": "电影"},
    {"type_id": "3", "type_name": "电视剧"},
    {"type_id": "4", "type_name": "动漫"},
    {"type_id": "han", "type_name": "韩剧"},
]

# 兜底线路别名（以站点 config.player.play 实时返回为准）
_LINE_FALLBACK = {
    "dyttm3u8": "天堂线路",
    "1080zyk": "幼稚线路",
    "bfzym3u8": "暴风线路",
    "ffm3u8": "非凡线路",
    "modum3u8": "魔都线路",
    "tym3u8": "天涯线路",
    "wwm3u8": "望望线路",
}

_ROW_LABELS = {"class": "类型", "area": "地区", "year": "年份", "lang": "语言"}


class Spider(Spider):

    def getName(self):
        return "果果短剧"

    # ---------- 基础 ----------
    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}
        self.site_url = (self.extend.get("site") or HOST).rstrip("/")
        self.api_host = (self.extend.get("api") or API_HOST).rstrip("/")
        self.headers = {
            "User-Agent": UA,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": self.site_url + "/",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        self.default_pic = DEFAULT_PIC
        self._cfg = None
        self._line_names = dict(_LINE_FALLBACK)
        self._play_cache = {}
        self._load_config()

    def _api_url(self, endpoint):
        return self.api_host + API_PREFIX + endpoint

    def _decrypt(self, text):
        if not text or not isinstance(text, str):
            return {}
        text = text.strip()
        if not _HAS_CRYPTO:
            self.log("  缺少 pycryptodome, 无法解密响应")
            return {}
        try:
            ct = base64.b64decode(text)
            pt = _unpad(AES.new(AES_KEY, AES.MODE_CBC, AES_KEY).decrypt(ct), 16)
            return json.loads(pt.decode("utf-8", "ignore"))
        except Exception as e:
            self.log("  解密失败: %s" % e)
            return {}

    def _request(self, method, endpoint, params=None, timeout=20):
        params = params or {}
        url = self._api_url(endpoint)
        for i in range(3):
            try:
                if method.upper() == "POST":
                    rsp = self.post(url, data=params, headers=self.headers,
                                    timeout=timeout)
                else:
                    rsp = self.fetch(url, params=params, headers=self.headers,
                                     timeout=timeout)
                text = getattr(rsp, "text", "") or ""
                if text:
                    return self._decrypt(text)
            except Exception as e:
                self.log("  请求重试 %d/%d %s: %s" % (i + 1, 3, endpoint, e))
            time.sleep(1 + i)
        return {}

    def _load_config(self):
        try:
            d = self._request("GET", "api/config", {"token": ""})
            if d.get("code") == 0 and isinstance(d.get("data"), dict):
                self._cfg = d["data"]
                play = (self._cfg.get("player") or {}).get("play") or {}
                for flag, conf in play.items():
                    if isinstance(conf, dict) and conf.get("name"):
                        self._line_names[str(flag)] = conf["name"]
        except Exception as e:
            self.log("  配置加载失败: %s" % e)
        if not self._cfg:
            self._cfg = {}

    # ---------- 工具 ----------
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
        s = (s.replace("\xa0", " ").replace("&nbsp;", " ")
              .replace("&amp;", "&").replace("&quot;", '"')
              .replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">")
              .replace("&ldquo;", "“").replace("&rdquo;", "”")
              .replace("&hellip;", "…"))
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n{2,}", "\n", s)
        return s.strip(" \n,，")

    def _drop_seo(self, text):
        if not text:
            return ""
        keep = []
        for line in text.split("\n"):
            t = line.strip()
            if not t:
                continue
            if ("完整版免费在线观看地址" in t or "分享给你的小伙伴" in t
                    or self.site_url in t or self.api_host in t):
                continue
            keep.append(t)
        return "\n".join(keep).strip()

    def _line_name(self, flag):
        flag = (flag or "").strip()
        return self._line_names.get(flag) or self._clean(flag)

    def _nav_id(self, url, key):
        if url and "?" in url:
            q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
            if q.get("id"):
                return q["id"][0]
        if key and "|" in key:
            return key.split("|", 1)[1]
        return ""

    def _card(self, c):
        if not isinstance(c, dict) or not c.get("vod_id"):
            return None
        pic = c.get("vod_pic") or c.get("vod_pic_thumb") or ""
        return {
            "vod_id": str(c["vod_id"]),
            "vod_name": self._clean(c.get("vod_name")),
            "vod_pic": self._fix_url(pic) if pic else self.default_pic,
            "vod_remarks": self._clean(c.get("vod_remarks")),
        }

    def _cards(self, lst):
        out, seen = [], set()
        for c in lst or []:
            card = self._card(c)
            if not card or card["vod_id"] in seen:
                continue
            seen.add(card["vod_id"])
            out.append(card)
        return out

    def _custom_cards(self, cid):
        d = self._request("POST", "custom", {"id": cid, "token": ""})
        widgets = d.get("data") if isinstance(d.get("data"), list) else []
        cards = []
        for w in widgets or []:
            if isinstance(w, dict):
                cards.extend(w.get("list", []) or [])
        return self._cards(cards)

    # ---------- 分类 / 筛选 ----------
    def _classes(self):
        nav = (self._cfg.get("config") or {}).get("head_nav") or []
        out = []
        for n in nav:
            name = self._clean(n.get("name"))
            cid = self._nav_id(n.get("url") or "", n.get("key") or "")
            if not cid or cid == "tuijian" or not name:
                continue
            out.append({"type_id": cid, "type_name": name})
        if out:
            try:
                nav_map = {self._nav_id(x.get("url") or "", x.get("key") or ""):
                           int(x.get("weight") or 0) for x in nav}
                out.sort(key=lambda x: nav_map.get(x["type_id"], 0), reverse=True)
            except Exception:
                pass
            return out
        return _FALLBACK_CLASSES

    def _filters(self):
        filters = {}
        webf = (self._cfg.get("web") or {}).get("filter", {}) or {}
        for t in (self._cfg.get("type") or []):
            if t.get("type_mid") != 1:
                continue
            tid = str(t["type_id"])
            ext = {}
            if t.get("type_extend"):
                try:
                    ext = json.loads(t["type_extend"])
                except Exception:
                    ext = {}
            rows = []
            enabled = [k.strip() for k in str(webf.get(tid, "")).split(",") if k.strip()]
            for k in enabled:
                opts = [x.strip() for x in str(ext.get(k, "")).split(",") if x.strip()]
                if not opts:
                    continue
                rows.append({
                    "key": k,
                    "name": _ROW_LABELS.get(k, k),
                    "value": [{"n": "全部", "v": ""}] +
                             [{"n": o, "v": o} for o in opts],
                })
            rows.append({"key": "by", "name": "排序",
                         "value": [{"n": "最新", "v": "time"},
                                   {"n": "最热", "v": "hits"}]})
            filters[tid] = rows
        return filters

    def homeContent(self, filter=False):
        return {"class": self._classes(), "filters": self._filters()}

    def homeVideoContent(self):
        cards = self._custom_cards("tuijian")
        self.log("home 卡片: %d 条" % len(cards))
        if not cards:
            d = self._request("POST", "vod/show", {"page": 0, "token": ""})
            cards = self._cards(d.get("list"))
        return {"list": cards}

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

        # 专题频道（Netflix / 韩剧 等）走 custom 小部件
        if not str(tid).isdigit():
            cards = self._custom_cards(str(tid))
            self.log("  频道 %s: %d 条" % (tid, len(cards)))
            return {"list": cards, "page": page, "pagecount": 1,
                    "limit": len(cards) or 40, "total": len(cards)}

        body = {"id": str(tid), "page": page - 1, "token": ""}
        for k in ("class", "area", "year", "lang", "by"):
            if extend.get(k):
                body[k] = extend[k]

        self.log("category: id=%s %s" % (tid, body))
        d = self._request("POST", "vod/show", body)
        cards = self._cards(d.get("list"))
        pagecount = int(d.get("pagecount") or 1)
        total = int(d.get("total") or 0)
        self.log("  最终: %d 条, 总页数: %d, 总数: %d" % (len(cards), pagecount, total))
        return {
            "list": cards, "page": page, "pagecount": pagecount,
            "limit": int(d.get("limit") or 40), "total": total or pagecount * 40,
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        body = {"wd": key, "page": page - 1, "token": ""}
        self.log("search: wd=%s" % key)
        d = self._request("POST", "vod/search", body)
        cards = self._cards(d.get("list"))
        pagecount = int(d.get("pagecount") or 1)
        self.log("  结果: %d 条, 总页数: %d" % (len(cards), pagecount))
        return {
            "list": cards, "page": page, "pagecount": pagecount,
            "limit": int(d.get("limit") or 10), "total": int(d.get("total") or 0),
        }

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ---------- 详情 / 播放 ----------
    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = str(ids[0])
        vid = vod_id if vod_id.isdigit() else vod_id.rstrip("/").split("/")[-1]
        self.log("detail: " + vid)
        d = self._request("GET", "vod/player",
                          {"id": vid, "token": "", "paw": "", "remember": ""})
        info = d.get("info") or {}
        if not info:
            self.log("  详情为空")
            return {"list": []}

        name = self._clean(info.get("vod_name")) or vid
        pic = info.get("vod_pic") or info.get("vod_pic_thumb") or ""
        remarks = self._clean(info.get("vod_remarks"))
        director = re.sub(r"\s+", " ", self._clean(info.get("vod_director"))).strip()
        actor = re.sub(r"\s+", " ", self._clean(info.get("vod_actor"))).strip()
        area = self._clean(info.get("vod_area"))
        year = self._clean(info.get("vod_year"))
        type_name = self._clean(info.get("vod_class"))

        score = info.get("vod_douban_score") or info.get("vod_score") or ""
        if str(score) in ("0", "0.0", "0.00", "", "0.0分"):
            score = ""
        else:
            score = str(score)

        content = self._clean(info.get("vod_content")) or self._clean(info.get("vod_blurb"))
        content = self._drop_seo(content)
        content = INTRO_PREFIX + "\n" + content if content else INTRO_PREFIX

        play_from, play_url = self._parse_play(info)
        if not play_from:
            return {"list": []}

        return {"list": [{
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": self._fix_url(pic) if pic else self.default_pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_area": area,
            "vod_year": year,
            "vod_score": score,
            "vod_remarks": remarks,
            "vod_type": type_name,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }]}

    def _parse_play(self, info):
        play_from, play_url = [], []

        # 标准 MacCMS legacy 字段
        from_lines = str(info.get("vod_play_from") or "").split("$$$")
        url_lines = str(info.get("vod_play_url") or "").split("$$$")
        for i, line_flag in enumerate(from_lines):
            if i >= len(url_lines):
                break
            eps = [e for e in str(url_lines[i]).split("#") if e]
            if not eps:
                continue
            alias = self._line_name(line_flag) or "线路%d" % (len(play_from) + 1)
            play_from.append(alias)
            play_url.append("#".join(eps))

        # 兜底: vod_play_list 结构
        if not play_from:
            pl = info.get("vod_play_list")
            if isinstance(pl, dict):
                items = pl.values()
            elif isinstance(pl, list):
                items = pl
            else:
                items = []
            for ln in items:
                if not isinstance(ln, dict):
                    continue
                urls = ln.get("urls") or ln.get("url") or []
                if isinstance(urls, str):
                    urls = [urls]
                eps = []
                for u in urls:
                    if isinstance(u, dict):
                        ep = self._clean(u.get("name") or u.get("title") or "")
                        url = u.get("url") or u.get("origin") or ""
                    else:
                        ep, url = "", str(u)
                    if not url:
                        continue
                    if not ep:
                        ep = "第%d集" % (len(eps) + 1)
                    eps.append("%s$%s" % (ep, self._fix_url(url)))
                if eps:
                    alias = self._line_name(ln.get("sid")) or "线路%d" % (len(play_from) + 1)
                    play_from.append(alias)
                    play_url.append("#".join(eps))

        return play_from, play_url

    def playerContent(self, flag, id, vipFlags):
        play_page = id if str(id).startswith("http") else self._fix_url(id)
        self.log("player: " + play_page)
        now = int(time.time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 600:
                return res

        if str(play_page).startswith("http") and (
                ".m3u8" in play_page or ".mp4" in play_page):
            res = {
                "parse": 0, "playUrl": "", "url": play_page,
                "header": {"User-Agent": UA, "Referer": self.site_url + "/"},
            }
            self._play_cache[play_page] = (now, res)
            return res

        # 兜底: 嗅探播放页
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
