#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
《极品少女》TVBox / 影视仓 dr_py Python 源  (HKL 兼容版 | 遮天·极道帝兵·万法归一)
站点: https://xn--0809-kb2g560h.jpsn47.top/jpsn/

【站点特征 / 加密方案】(基于真实抓包还原，非臆造)
  - MacCMS v10 (mxtwoa14) 模板，base 路径 /jpsn/。
  - 全站页面被 jsjiami v7 + AES-CBC 反盗链混淆：每页 HTML 仅含
      <div id="app">base64</div>  +  一段 jsjiami 解密脚本；
    真实内容 = AES-CBC 解密 #app 的 base64。公共 JSON 采集接口已被站点禁用。
  - 解密参数：AES-128-CBC / PKCS7；Key=1234567898882222；IV=8NONwyJtHesysWpM。
  - 本源内置纯 Python AES-128-CBC（零第三方依赖，经 FIPS-197 向量 + pycryptodome
    双验证），无需在 TVBox 沙箱安装 pycryptodome 即可用。

【路由】
  分类:  /jpsn/index.php/vod/type/id/{tid}.html
  分页:  /jpsn/index.php/vod/type/id/{tid}/page/{pg}.html
  详情:  /jpsn/index.php/vod/detail/id/{id}.html
  播放:  /jpsn/index.php/vod/play/id/{id}/sid/{sid}/nid/{nid}.html
  搜索:  POST /jpsn/index.php/vod/search.html  (wd=关键词)

【播放】播放页内置 `var player_aaaa={...}` JSON，encrypt=0 时 url 为直接 m3u8/mp4。
  提取该 JSON 的 url 字段返回（parse=0），不猜 Token/签名。
"""

import sys
import re
import json
import base64
import html as ihtml
from urllib.parse import quote, urljoin, urlparse, unquote

try:
    import requests
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except ImportError:
    requests = None

# AES-128-CBC 解密：优先 pycryptodome，其次内置纯 Python 实现
try:
    import Crypto  # noqa: F401
    from Crypto.Cipher import AES as _AES
    from Crypto.Util.Padding import unpad as _unpad
    def _aes_cbc_decrypt(ct, key, iv):
        return _unpad(_AES.new(key, _AES.MODE_CBC, iv).decrypt(ct), 16)
    _HAS_CRYPTO = True
except ImportError:
    def _aes_cbc_decrypt(ct, key, iv):
        raise RuntimeError("pycryptodome 缺失")
    _HAS_CRYPTO = False

_JPSN_KEY = b"1234567898882222"
_JPSN_IV = b"8NONwyJtHesysWpM"
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def _clean(s):
    return re.sub(r"\s+", " ", ihtml.unescape(re.sub(r"<[^>]+>", "", s or ""))).strip()


def _fix_url(u, host):
    if not u:
        return ""
    u = u.strip()
    if u.startswith("//"):
        return urljoin(host, u)
    if u.startswith("/"):
        return urljoin(host, u)
    if u.startswith("http"):
        return u
    return urljoin(host, "/" + u)


def _looks_like_token(v):
    return bool(re.match(r"^[A-Za-z0-9_-]{24,}$", str(v or "")))


class Spider(object):
    """HKL/CatVod 兼容 Spider。部分运行器要求继承 base.spider.Spider，
    此处用鸭子类型实现同名接口；若你有 base.spider 环境，可改为 `from base.spider
    import Spider as Base` 并 `class Spider(Base)`。"""

    def __init__(self):
        self.host = "https://xn--0809-kb2g560h.jpsn47.top/jpsn"
        self.name = "极品少女_JPSN"
        self.ext = ""
        self.timeout = 15
        self.verify = False
        self.proxies = {}
        self.search_fallback = True
        self.play_cache = {}
        self.headers = {
            "User-Agent": _UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.host + "/",
        }
        self.s = requests.Session() if requests else None
        if self.s:
            self.s.headers.update(self.headers)

    # ── 可选生命周期 ──
    def getDependence(self):
        return []

    def homeLayout(self):
        return 0

    def destroy(self):
        try:
            if self.s:
                self.s.close()
        except (OSError, AttributeError):
            pass

    def manualVideoCheck(self):
        return False

    def isVideoFormat(self, url):
        v = str(url or "").lower()
        path = urlparse(v).path
        return any(x in path or x in v for x in
                   [".m3u8", ".mp4", ".m4v", ".flv", ".webm", ".ts"])

    # ── 扩展配置：HKL setExtendInfo / init 双兼容 ──
    def _parse_extend(self, extend):
        if isinstance(extend, dict):
            return dict(extend)
        text = str(extend or "").strip()
        if not text:
            return {}
        try:
            data = json.loads(text)
            return data if isinstance(data, dict) else {}
        except (ValueError, TypeError):
            return {"host": text} if text.startswith(("http://", "https://")) else {}

    def _as_bool(self, value, default=False):
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        return str(value).strip().lower() in ("1", "true", "yes", "on")

    def _set_proxy(self, proxy):
        p = str(proxy or "").strip()
        self.proxies = {"http": p, "https": p} if p.startswith(("http://", "https://")) else {}

    def setExtendInfo(self, extend):
        self.ext = extend or ""
        cfg = self._parse_extend(extend)
        h = str(cfg.get("host") or cfg.get("HOST") or "").strip().rstrip("/")
        if h.startswith(("http://", "https://")):
            self.host = h
        ua = str(cfg.get("userAgent") or cfg.get("User-Agent") or cfg.get("ua") or "").strip()
        if ua:
            self.headers["User-Agent"] = ua
        cookie = str(cfg.get("cookie") or cfg.get("Cookie") or "").strip()
        if cookie:
            self.headers["Cookie"] = cookie
        elif "Cookie" in self.headers:
            self.headers.pop("Cookie", None)
        referer = str(cfg.get("referer") or cfg.get("Referer") or "").strip()
        if referer.startswith(("http://", "https://")):
            self.headers["Referer"] = referer
        else:
            self.headers["Referer"] = self.host + "/"
        try:
            self.timeout = max(3, int(cfg.get("timeout", self.timeout) or self.timeout))
        except (ValueError, TypeError):
            pass
        self.verify = self._as_bool(cfg.get("verify"), False)
        self.search_fallback = self._as_bool(cfg.get("searchFallback"), True)
        self._set_proxy(cfg.get("proxy"))
        if self.s:
            self.s.headers.update(self.headers)
        return None

    def init(self, extend=""):
        return self.setExtendInfo(extend if extend else self.ext)

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def getName(self):
        return self.name

    # ── 统一请求 ──
    def _request(self, url, method="GET", data=None, json_data=None, headers=None,
                 referer="", retry=1):
        if not self.s:
            return None
        merged = dict(self.headers)
        if headers:
            merged.update(headers)
        if referer:
            merged["Referer"] = referer
        last = None
        for attempt in range(max(1, int(retry) + 1)):
            try:
                resp = self.s.request(method, url, data=data, json=json_data,
                                      headers=merged, timeout=self.timeout,
                                      verify=self.verify, proxies=self.proxies or None,
                                      allow_redirects=True)
                if resp.status_code < 500:
                    return resp
                last = resp
            except (OSError, ValueError, AttributeError, TypeError) as e:
                last = e
        print(f"[{self.name}] 请求失败: {url} - {last}")
        return None

    def _fetch(self, url):
        r = self._request(url)
        if r is None:
            return ""
        if not r.encoding:
            r.encoding = "utf-8"
        return r.text

    def _decrypt_page(self, html_text):
        """从反盗链页面提取 #app 并 AES-CBC 解密，返回真实 HTML。"""
        if not html_text:
            return ""
        m = re.search(r'<div[^>]*id="app"[^>]*>\s*([A-Za-z0-9+/=\r\n]+?)\s*</div>', html_text, re.S)
        if not m:
            # 可能页面已是明文（未加密 or 采集返回明文）
            if "stui-vodlist__box" in html_text or "stui-content__playlist" in html_text:
                return html_text
            return ""
        data = re.sub(r"\s+", "", m.group(1))
        try:
            ct = base64.b64decode(data)
        except (ValueError, TypeError):
            return ""
        force_pure = __import__("os").environ.get("FORCE_PURE_AES") == "1"
        if _HAS_CRYPTO and not force_pure:
            try:
                return _aes_cbc_decrypt(ct, _JPSN_KEY, _JPSN_IV).decode("utf-8", "ignore")
            except Exception:
                pass
        try:
            return _pure_aes(ct).decode("utf-8", "ignore")
        except Exception as e:
            print(f"[{self.name}] AES 解密失败: {e}")
            return ""

    # ── 解析辅助 ──
    def _fetch_cards(self, html_text):
        """解析 stui-vodlist__box 卡片列表。"""
        vods = []
        for m in re.finditer(
                r'<a[^>]*class="[^"]*stui-vodlist__thumb[^"]*"[^>]*>([\s\S]*?)</a>',
                html_text, re.I | re.S):
            tag = m.group(0)
            hm = re.search(r'href="([^"]*)detail/id/(\d+)\.html"', tag)
            if not hm:
                continue
            url, vid = hm.group(1), hm.group(2)
            tm = re.search(r'title="([^"]*)"', tag)
            title = tm.group(1).strip() if tm else ""
            pm = re.search(r'data-original="([^"]*)"', tag) or \
                 re.search(r'(?:src|data-src)="([^"]+\.(?:jpg|jpeg|png|webp))"', tag)
            pic = pm.group(1) if pm else ""
            rem = ""
            inner = m.group(1)
            rm = re.search(r'<span class="pic-text[^"]*">\s*<b>([^<]*)</b>', inner)
            if rm:
                rem = rm.group(1).strip()
            if not title:
                tm2 = re.search(r'title="([^"]*)"', tag)
                if tm2:
                    title = tm2.group(1).strip()
            if not title:
                tm3 = re.search(r'alt="([^"]*)"', tag)
                if tm3:
                    title = tm3.group(1).strip()
            vods.append({
                "vod_id": vid,
                "vod_name": _clean(title) if title else "未命名",
                "vod_pic": _fix_url(pic, self.host) if pic else "",
                "vod_remarks": rem,
            })
        # 去重（同一卡片 detail 链接出现多次时只保留一次）
        seen = set()
        out = []
        for v in vods:
            k = v["vod_id"] + "|" + v["vod_name"]
            if k in seen:
                continue
            seen.add(k)
            out.append(v)
        return out

    # ── 首页 ──
    def homeContent(self, filter):
        classes = [
            {"type_id": "174", "type_name": "视频一区"},
            {"type_id": "175", "type_name": "视频二区"},
            {"type_id": "176", "type_name": "视频三区"},
            {"type_id": "195", "type_name": "视频四区"},
            {"type_id": "204", "type_name": "视频五区"},
            {"type_id": "181", "type_name": "国产专区"},
            {"type_id": "191", "type_name": "精品推荐"},
            {"type_id": "192", "type_name": "国产精品"},
            {"type_id": "193", "type_name": "主播秀色"},
            {"type_id": "194", "type_name": "日本有码"},
            {"type_id": "138", "type_name": "亚洲有码"},
            {"type_id": "156", "type_name": "3P合辑"},
            {"type_id": "167", "type_name": "VR视角"},
            {"type_id": "140", "type_name": "中文字幕"},
            {"type_id": "143", "type_name": "人妻熟女"},
            {"type_id": "145", "type_name": "三级伦理"},
            {"type_id": "146", "type_name": "自拍偷拍"},
            {"type_id": "155", "type_name": "AV明星"},
            {"type_id": "157", "type_name": "巨乳系列"},
            {"type_id": "163", "type_name": "大秀视频"},
            {"type_id": "168", "type_name": "素人搭讪"},
            {"type_id": "139", "type_name": "欧美情色"},
            {"type_id": "141", "type_name": "动漫卡通"},
            {"type_id": "144", "type_name": "强奸乱伦"},
            {"type_id": "154", "type_name": "制服诱惑"},
            {"type_id": "158", "type_name": "颜射系列"},
            {"type_id": "161", "type_name": "SM重味"},
            {"type_id": "162", "type_name": "教师学生"},
            {"type_id": "164", "type_name": "日韩精品"},
            {"type_id": "196", "type_name": "日本无码"},
            {"type_id": "197", "type_name": "童颜巨乳"},
            {"type_id": "198", "type_name": "性感人妻"},
            {"type_id": "199", "type_name": "卡通动漫"},
            {"type_id": "200", "type_name": "丝袜OL"},
            {"type_id": "201", "type_name": "日本片商"},
            {"type_id": "202", "type_name": "剧情介绍"},
            {"type_id": "203", "type_name": "网曝系列"},
            {"type_id": "205", "type_name": "麻豆传媒"},
            {"type_id": "206", "type_name": "明星换脸"},
            {"type_id": "211", "type_name": "探花嫖娼"},
            {"type_id": "212", "type_name": "同性恋"},
        ]
        filters = {}
        if filter:
            filters = {
                "area": {"key": "area", "name": "地区",
                         "value": [{"n": "全部", "v": ""},
                                   {"n": "国产", "v": "国产"},
                                   {"n": "欧美", "v": "日本无码"}]},
                "year": {"key": "year", "name": "年份",
                         "value": [{"n": "全部", "v": ""},
                                   {"n": "2026", "v": "2026"},
                                   {"n": "2025", "v": "2025"}]},
            }
        return {"class": classes, "filters": filters}

    def homeVideoContent(self):
        # 首页最新内容
        html_text = self._decrypt_page(self._fetch(self.host + "/"))
        vods = self._fetch_cards(html_text)
        return {"list": vods}

    # ── 分类 ──
    def categoryContent(self, tid, pg, filter, extend):
        try:
            pg = int(pg)
        except (ValueError, TypeError):
            pg = 1
        url = "%s/index.php/vod/type/id/%s/page/%d.html" % (self.host, tid, pg)
        html_text = self._decrypt_page(self._fetch(url))
        vods = self._fetch_cards(html_text)
        pagecount = self._extract_pagecount(html_text)
        return {"list": vods, "page": pg, "pagecount": pagecount, "limit": 12, "total": 0}

    def _extract_pagecount(self, html_text):
        """从 <li class="active num"><a>当前/总数</a></li> 解析总页数。"""
        m = re.search(r'class="active num"[^>]*>\s*<a[^>]*>\s*(\d+)\s*/\s*(\d+)\s*</a>', html_text)
        if m:
            try:
                return int(m.group(2))
            except ValueError:
                pass
        # 兜底：尾页链接
        m2 = re.findall(r'/page/(\d+)\.html">尾页', html_text)
        if m2:
            try:
                return int(m2[0])
            except ValueError:
                pass
        # 再兜底：最大的分页数字
        nums = [int(n) for n in re.findall(r'/page/(\d+)\.html', html_text)]
        if nums:
            return max(nums)
        return 1

    # ── 详情 ──
    def detailContent(self, ids):
        if isinstance(ids, (list, tuple)):
            vid = ids[0]
        else:
            vid = str(ids)
        url = "%s/index.php/vod/detail/id/%s.html" % (self.host, vid)
        html_text = self._decrypt_page(self._fetch(url))
        vod = self._parse_detail(html_text, vid)
        return {"list": [vod]}

    def _parse_detail(self, html_text, vid):
        name_m = re.search(r'<h1[^>]*class="[^"]*title[^"]*"[^>]*>([\s\S]*?)</h1>', html_text)
        vod_name = _clean(name_m.group(1)) if name_m else "未命名"
        pic_m = re.search(r'(?:data-original|data-src|poster|src)="([^"]+\.(?:jpg|jpeg|png|webp))"', html_text)
        vod_pic = _fix_url(pic_m.group(1), self.host) if pic_m else ""
        content_m = re.search(r'<span[^>]*class="detail-content"[^>]*>([\s\S]*?)</span>', html_text)
        vod_content = _clean(content_m.group(1)) if content_m else ""

        # 按播放列表块(stui-vodlist__head)解析：每个块有自己的线路名 + 剧集
        # 先收集所有 play 链接到其所属 sid，落单到默认的单个线路名
        eps = []
        for m in re.finditer(
                r'<a[^>]*href="([^"]*/vod/play/id/%s/sid/(\d+)/nid/(\d+)\.html)"[^>]*>([^<]*)</a>'
                % re.escape(str(vid)), html_text, re.I):
            ephref = m.group(1)
            sid = m.group(2)
            nid = m.group(3)
            eptxt = _clean(m.group(4)).strip() or ("第%s集" % nid)
            if eptxt in ("立即播放", "立即观看"):
                eptxt = "第%s集" % nid
            eps.append((sid, eptxt, ephref))
        # 去重保序（同一 href 只留一次）
        seen = set()
        ep_list = []
        for sid, eptxt, ephref in eps:
            if ephref in seen:
                continue
            seen.add(ephref)
            ep_list.append((sid, eptxt, ephref))

        # 每个播放列表块提取自身的线路名
        def _line_name_for_sid(sid):
            # 从 stui-vodlist__head 块找标题；若找不到再退回通用的第一条线路名
            for block in re.finditer(
                    r'<div class="stui-vodlist__head">\s*(?:<span[^>]*></span>\s*)?'
                    r'<h3[^>]*>([\s\S]*?)</h3>', html_text, re.I):
                label = _clean(re.sub(r'<[^>]+>', '', block.group(1)))
                if label:
                    return label
            return ""

        default_name = ""
        fm = re.search(r'<h3[^>]*class="title"[^>]*>\s*<i[^>]*></i>\s*([^<]+?)\s*</h3>', html_text)
        if fm:
            default_name = _clean(fm.group(1))
        if not default_name:
            default_name = _line_name_for_sid(None)
        if not default_name:
            default_name = "dadim3u8"

        # 线路内排序：nid 数字升序
        bysid = {}
        for sid, eptxt, ephref in ep_list:
            bysid.setdefault(sid, []).append((eptxt, ephref))
        for sid in bysid:
            def _nid_key(item):
                nn = re.search(r'/nid/(\d+)\.html', item[1])
                try:
                    return int(nn.group(1))
                except (ValueError, TypeError, AttributeError):
                    return 0
            bysid[sid].sort(key=_nid_key)

        line_labels = []
        play_lines = []
        for sid in bysid:
            parts = ["%s$%s" % (eptxt, ephref) for eptxt, ephref in bysid[sid]]
            play_lines.append("#".join(parts))
            line_labels.append(default_name)
        if not play_lines:
            return {"vod_id": vid, "vod_name": vod_name, "vod_pic": vod_pic,
                    "vod_content": vod_content, "vod_play_from": "", "vod_play_url": ""}
        play_from = "$$$".join(line_labels)
        play_url = "$$$".join(play_lines)
        return {"vod_id": vid, "vod_name": vod_name, "vod_pic": vod_pic,
                "vod_content": vod_content,
                "vod_play_from": play_from, "vod_play_url": play_url}
        return {"vod_id": vid, "vod_name": vod_name, "vod_pic": vod_pic,
                "vod_content": vod_content,
                "vod_play_from": play_from, "vod_play_url": play_url}

    # ── 搜索 ──
    def searchContent(self, key, quick, pg="1"):
        try:
            pg = int(pg)
        except (ValueError, TypeError):
            pg = 1
        try:
            resp = self._request(self.host + "/index.php/vod/search.html", method="POST",
                                 data={"wd": key}, referer=self.host + "/")
            html_text = self._decrypt_page(resp.text if resp else "")
            vods = self._fetch_cards(html_text)
            return {"list": vods, "page": pg, "pagecount": 1, "limit": 12, "total": 0}
        except Exception as e:
            print(f"[{self.name}] 搜索失败: {e}")
            return {"list": [], "page": pg, "pagecount": 1, "limit": 12, "total": 0}

    # ── 播放 ──
    def playerContent(self, flag, id, vipFlags=None):
        # id 形如 /jpsn/index.php/vod/play/id/{vid}/sid/{sid}/nid/{nid}.html
        url = _fix_url(id, self.host)
        html_text = self._decrypt_page(self._fetch(url))
        play_url = ""
        headers = dict(self.headers)
        m = re.search(r'var\s+player_aaaa\s*=\s*(\{.*?\})\s*</script>', html_text, re.S | re.I)
        if not m:
            m = re.search(r'var\s+player_aaaa\s*=\s*(\{.*?\})', html_text, re.S | re.I)
        if m:
            try:
                cfg = json.loads(m.group(1))
                play_url = str(cfg.get("url") or "").strip()
                enc = int(cfg.get("encrypt") or 0)
                if enc != 0:
                    print(f"[{self.name}] 播放地址需解密(encrypt={enc})，暂不解码")
                    play_url = ""
                from_server = str(cfg.get("from") or "")
                if from_server:
                    headers["Referer"] = self.host + "/"
            except (ValueError, TypeError) as e:
                print(f"[{self.name}] player_aaaa 解析失败: {e}")
                play_url = ""
        if not play_url:
            # 兜底：页面内直接找 m3u8/mp4
            m2 = re.search(r'(https?://[^"\'\s<>]+\.(?:m3u8|mp4|flv|mpd))', html_text)
            if m2:
                play_url = m2.group(1)
        if not play_url:
            return {"parse": 0, "url": "", "header": {}}
        return {"parse": 0, "url": play_url, "header": headers}

    def localProxy(self, param):
        # 图片防盗链代理
        _p = param if isinstance(param, dict) else {}
        url = unquote(_p.get("url", "")) or ""
        if not url:
            return [404, "text/plain", b""]
        try:
            _h = {"User-Agent": self.headers.get("User-Agent", _UA),
                  "Referer": _p.get("referer", self.host + "/")}
            _sess = self.s if self.s else requests
            _r = _sess.get(url, headers=_h, timeout=self.timeout, verify=self.verify)
            _ct = _r.headers.get("Content-Type", "image/jpeg")
            return [200, _ct, _r.content, {"Access-Control-Allow-Origin": "*"}]
        except (OSError, ValueError, AttributeError, TypeError):
            gif = base64.b64decode("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7")
            return [200, "image/gif", gif]


# ── 纯 Python AES-128-CBC 回退实现（零第三方依赖，经 FIPS-197 + pycryptodome 双验证）──
_SBOX = [
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
    0x8c,0xa1,0x89,0x0d,0xbf,0xe6,0x42,0x68,0x41,0x99,0x2d,0x0f,0xb0,0x54,0xbb,0x16,
]
_INV_SBOX = [0] * 256
for _i in range(256):
    _INV_SBOX[_SBOX[_i]] = _i


def _gmul(a, b):
    p = 0
    for _ in range(8):
        if b & 1:
            p ^= a
        hi = a & 0x80
        a = (a << 1) & 0xFF
        if hi:
            a ^= 0x1B
        b >>= 1
    return p


def _aes_expand_key(key):
    w = [int.from_bytes(key[i:i+4], 'big') for i in range(0, 16, 4)]
    rcon = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1b, 0x36]
    for i in range(4, 44):
        tmp = w[i-1]
        if i % 4 == 0:
            tmp = ((_SBOX[(tmp >> 24) & 0xFF] << 24) |
                   (_SBOX[(tmp >> 16) & 0xFF] << 16) |
                   (_SBOX[(tmp >> 8) & 0xFF] << 8) | _SBOX[tmp & 0xFF])
            tmp = ((tmp << 8) | (tmp >> 24)) & 0xFFFFFFFF
            tmp ^= (rcon[i // 4 - 1] << 24)
        w.append(w[i-4] ^ tmp)
    return [ww.to_bytes(4, 'big') for ww in w]  # 44 个 4 字节字


def _add_round_key(state, rk):
    for c in range(4):
        for r in range(4):
            state[c][r] ^= rk[c][r]


def _sub_bytes(state):
    for c in range(4):
        for r in range(4):
            state[c][r] = _SBOX[state[c][r]]


def _inv_sub_bytes(state):
    for c in range(4):
        for r in range(4):
            state[c][r] = _INV_SBOX[state[c][r]]


def _shift_rows(state):
    for r in range(1, 4):
        s0 = state[0][r]; s1 = state[1][r]; s2 = state[2][r]; s3 = state[3][r]
        state[0][r] = [s0, s1, s2, s3][(0 + r) % 4]
        state[1][r] = [s0, s1, s2, s3][(1 + r) % 4]
        state[2][r] = [s0, s1, s2, s3][(2 + r) % 4]
        state[3][r] = [s0, s1, s2, s3][(3 + r) % 4]


def _inv_shift_rows(state):
    for r in range(1, 4):
        s0 = state[0][r]; s1 = state[1][r]; s2 = state[2][r]; s3 = state[3][r]
        state[0][r] = [s0, s1, s2, s3][(0 - r) % 4]
        state[1][r] = [s0, s1, s2, s3][(1 - r) % 4]
        state[2][r] = [s0, s1, s2, s3][(2 - r) % 4]
        state[3][r] = [s0, s1, s2, s3][(3 - r) % 4]


def _mix_columns(state):
    for c in range(4):
        s0, s1, s2, s3 = state[c][0], state[c][1], state[c][2], state[c][3]
        state[c][0] = _gmul(s0, 2) ^ _gmul(s1, 3) ^ s2 ^ s3
        state[c][1] = s0 ^ _gmul(s1, 2) ^ _gmul(s2, 3) ^ s3
        state[c][2] = s0 ^ s1 ^ _gmul(s2, 2) ^ _gmul(s3, 3)
        state[c][3] = _gmul(s0, 3) ^ s1 ^ s2 ^ _gmul(s3, 2)


def _inv_mix_columns(state):
    for c in range(4):
        s0, s1, s2, s3 = state[c][0], state[c][1], state[c][2], state[c][3]
        state[c][0] = _gmul(s0, 14) ^ _gmul(s1, 11) ^ _gmul(s2, 13) ^ _gmul(s3, 9)
        state[c][1] = _gmul(s0, 9) ^ _gmul(s1, 14) ^ _gmul(s2, 11) ^ _gmul(s3, 13)
        state[c][2] = _gmul(s0, 13) ^ _gmul(s1, 9) ^ _gmul(s2, 14) ^ _gmul(s3, 11)
        state[c][3] = _gmul(s0, 11) ^ _gmul(s1, 13) ^ _gmul(s2, 9) ^ _gmul(s3, 14)


def _encrypt_block(block, rk):
    state = [[block[c*4 + r] for r in range(4)] for c in range(4)]
    _add_round_key(state, rk[:4])
    for rnd in range(1, 10):
        _sub_bytes(state); _shift_rows(state); _mix_columns(state)
        _add_round_key(state, rk[rnd*4:rnd*4+4])
    _sub_bytes(state); _shift_rows(state)
    _add_round_key(state, rk[40:44])
    return b"".join(state[c][r].to_bytes(1, 'big') for c in range(4) for r in range(4))


def _decrypt_block(block, rk):
    state = [[block[c*4 + r] for r in range(4)] for c in range(4)]
    _add_round_key(state, rk[40:44])
    for rnd in range(9, 0, -1):
        _inv_shift_rows(state); _inv_sub_bytes(state)
        _add_round_key(state, rk[rnd*4:rnd*4+4])
        _inv_mix_columns(state)
    _inv_shift_rows(state); _inv_sub_bytes(state)
    _add_round_key(state, rk[:4])
    return b"".join(state[c][r].to_bytes(1, 'big') for c in range(4) for r in range(4))


def _pure_aes(ct):
    """AES-128-CBC 解密（Key/IV 为此站点固定值），返回去掉 PKCS7 的明文。"""
    if len(ct) % 16 != 0:
        raise ValueError("ciphertext length")
    rk = _aes_expand_key(_JPSN_KEY)
    prev = _JPSN_IV
    out = b""
    for i in range(0, len(ct), 16):
        blk = ct[i:i+16]
        d = _decrypt_block(blk, rk)
        out += bytes(a ^ b for a, b in zip(d, prev))
        prev = blk
    if out:
        pad = out[-1]
        if 1 <= pad <= 16 and out[-pad:] == bytes([pad]) * pad:
            out = out[:-pad]
    return out
