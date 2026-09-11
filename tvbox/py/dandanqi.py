# -*- coding: utf-8 -*-
import re
import os
import sys
import json
import time
import requests
from urllib.parse import quote
from lxml import etree
try:
    import urllib3
    urllib3.disable_warnings()
except Exception:
    pass
# 可选依赖：真实 Chrome TLS 指纹（站点反爬会识别 requests 指纹）
try:
    from curl_cffi import requests as chttp
except Exception:
    chttp = None
# 可选依赖：验证码 OCR（TVBox/Fongmi chaquo 环境通常预装 ddddocr+onnxruntime）
try:
    import ddddocr
except Exception:
    ddddocr = None
sys.path.append('..')
try:
    from base.spider import Spider as BaseSpider
except Exception:
    from spider import Spider as BaseSpider


class Spider(BaseSpider):
    # 反爬/验证码页特征关键词
    VERIFY_KWS = ("系统安全验证", "安全验证", "验证码", "请输入访问验证码", "captcha", "访问此数据需要")
    # 分类：电影/剧集/综艺/动漫（mxtheme 模板 /type/xxx.html）
    TYPES = {"dianying": "电影", "juji": "剧集", "zongyi": "综艺", "dongman": "动漫"}
    SITE_NAMES = ("蛋蛋奇", "系统安全验证", "页面访问验证", "网站提示")

    def getName(self):
        return "蛋蛋奇"

    def init(self, extend=""):
        # 最新入口优先；.vip 为导航页发现的新域名
        self.host = "https://www.dandanqi.cc"
        self.hosts = ["https://www.dandanqi.vip", "https://www.dandanqi.cc", "https://dandanqi.cc", "https://www.dandanqi.com", "https://www.dandanqi.pro", "https://www.dandanqi.fun", "https://www.dandanqi.me"]
        self._captcha_sign = ""
        self._last_verify = 0
        self._sign_file = ""
        try:
            import tempfile
            self._sign_file = os.path.join(tempfile.gettempdir(), "dandanqi_sign.txt")
        except Exception:
            self._sign_file = ""
        # TVBox/Android: 尝试应用缓存目录（chaquo 可写）
        for base in ("/data/user/0/com.fongmi.vodplus/cache", "/data/user/0/com.fongmi.tv/cache"):
            try:
                if os.path.isdir(base) and os.access(base, os.W_OK):
                    self._sign_file = os.path.join(base, "dandanqi_sign.txt")
                    break
            except Exception:
                continue
        try:
            o = json.loads(extend) if extend else {}
            if isinstance(o, dict) and o.get("host"):
                self.host = o["host"]
                self.hosts = [o["host"]] + self.hosts
            # 可传入已人工验证的 cookie（captcha_login_sign）直接跳过验证码
            if isinstance(o, dict) and o.get("captcha"):
                self._captcha_sign = str(o["captcha"])
        except Exception:
            pass
        # 从本地缓存加载 sign（上次验证成功持久化）
        try:
            if not self._captcha_sign and self._sign_file:
                with open(self._sign_file, "r") as f:
                    s = f.read().strip()
                    if s:
                        self._captcha_sign = s
        except Exception:
            pass
        # 必须用移动 UA：站点 PC UA 会被 JS 重定向到 404.html
        self.ua = "Mozilla/5.0 (Linux; Android 12; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
        self.headers = {"User-Agent": self.ua, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Accept-Language": "zh-CN,zh;q=0.9", "Referer": self.host + "/", "Cookie": "accessAuth=ok"}
        self._ocr = None
        self._ocr_beta = None
        if ddddocr is not None:
            try:
                self._ocr_beta = ddddocr.DdddOcr(show_ad=False, beta=True)
                self._ocr = self._ocr_beta
            except Exception:
                self._ocr_beta = None
                try:
                    self._ocr = ddddocr.DdddOcr(show_ad=False)
                except Exception:
                    self._ocr = None

    def _fix(self, u):
        if not u:
            return ""
        u = u.strip()
        if u.startswith("//"):
            return "https:" + u
        if u.startswith("/"):
            return self.host + u
        return u

    def _is_verify(self, html):
        """判断页面是否为验证码/反爬拦截页"""
        if not html:
            return False
        t = html[:3000].lower()
        for kw in self.VERIFY_KWS:
            if kw in t:
                return True
        return False

    def _is_valid_page(self, html):
        """页面是否包含真实视频内容（排除验证码/404/过短页）"""
        if not html or self._is_verify(html):
            return False
        if len(html) < 1500:
            return False
        if "404 not found" in html[:600].lower():
            return False
        return True

    def _has_vod_content(self, html):
        """页面是否含真实视频结构（详情/播放/分类链接等）"""
        low = (html or "").lower()
        if "/detail/" in low or "/play/" in low or re.search(r"/type/[a-z]+\.html", low):
            return True
        if "detail-title" in low or "module-play-list" in low or "stui-vodlist" in low:
            return True
        return False

    # ---------- 网络层 ----------
    def _get_http(self):
        """返回带真实 Chrome TLS 指纹的 http 客户端"""
        if chttp is not None:
            return chttp
        return requests

    def _new_session(self):
        """创建持久 session（自动管理 PHPSESSID/cookies）"""
        if chttp is not None:
            s = chttp.Session(impersonate="chrome120")
            s.headers.update(self._req_headers())
            return s
        s = requests.Session()
        s.headers.update(self._req_headers())
        return s

    def _req_headers(self, referer=None):
        h = dict(self.headers)
        if referer:
            h["Referer"] = referer
        if self._captcha_sign:
            h["Cookie"] = "accessAuth=ok; captcha_login_sign=" + self._captcha_sign
        elif "Cookie" in h and not self._captcha_sign:
            # 无 sign 时不强制 Cookie，避免干扰 session 的 PHPSESSID 管理
            h.pop("Cookie", None)
        return h

    def _fetch_raw(self, url, timeout=8):
        """GET 请求，返回响应对象或 None"""
        try:
            if chttp is not None:
                return chttp.get(url, impersonate="chrome120", headers=self._req_headers(), timeout=timeout, verify=False, allow_redirects=True)
            return requests.get(url, headers=self._req_headers(), timeout=timeout, verify=False, allow_redirects=True)
        except Exception:
            return None

    def _fetch(self, url, timeout=8):
        r = self._fetch_raw(url, timeout=timeout)
        if r is None:
            return ""
        try:
            r.encoding = "utf-8"
            return r.text or ""
        except Exception:
            return ""

    def _pass_captcha(self):
        """
        自动过 /captcha.php 图片验证码（4位字母，OCR 识别后 POST）。
        - 优先 ddddocr（TVBox/Fongmi chaquo 环境预装）
        - 使用持久 Session 管理 PHPSESSID
        - 双模型/多图重试提高成功率
        - 成功后保存 captcha_login_sign 供后续请求使用（5分钟免验证）
        """
        if not self._ocr:
            # 无 OCR 能力时尝试用已有 sign（ext 传入或上次成功）
            return bool(self._captcha_sign)
        now = time.time()
        if self._captcha_sign and now - self._last_verify < 300:
            return True
        self._last_verify = now
        host = self.host
        try:
            s = self._new_session()
            if chttp is None:
                s.get(host + "/", headers=self._req_headers(), timeout=8, verify=False)
            else:
                s.get(host + "/", timeout=8, verify=False)
        except Exception:
            pass
        for _ in range(12):
            try:
                if chttp is not None:
                    r = s.get(host + "/captcha.php?type=code", timeout=8, verify=False)
                else:
                    r = s.get(host + "/captcha.php?type=code", headers=self._req_headers(), timeout=8, verify=False)
            except Exception:
                time.sleep(0.3)
                continue
            if r is None or r.status_code != 200 or not r.content:
                time.sleep(0.3)
                continue
            # OCR：同一张图用两个模型各识别一次，任一成功即用
            candidates = []
            for ocr_model in (self._ocr,):
                try:
                    c1 = self._ocr.classification(r.content) or ""
                    c1 = re.sub(r"[^a-zA-Z0-9]", "", c1)
                    if len(c1) >= 4:
                        candidates.append(c1[:4])
                    if self._ocr_beta and self._ocr_beta is not self._ocr:
                        c2 = self._ocr_beta.classification(r.content) or ""
                        c2 = re.sub(r"[^a-zA-Z0-9]", "", c2)
                        if len(c2) >= 4:
                            candidates.append(c2[:4])
                    break
                except Exception:
                    break
            if not candidates:
                continue
            # 依次尝试各候选
            for code in dict.fromkeys(candidates):
                try:
                    if chttp is not None:
                        r2 = s.post(host + "/captcha.php",
                                    headers={"Content-Type": "application/x-www-form-urlencoded", "Referer": host + "/"},
                                    data="type=verify&check=" + code, timeout=8, verify=False)
                    else:
                        r2 = s.post(host + "/captcha.php",
                                    headers={**self._req_headers(), "Content-Type": "application/x-www-form-urlencoded", "Referer": host + "/"},
                                    data="type=verify&check=" + code, timeout=8, verify=False)
                except Exception:
                    continue
                try:
                    j = json.loads(r2.text)
                    if j.get("code") == 1:
                        # 提取 captcha_login_sign（session cookie）
                        try:
                            ck = s.cookies.get_dict() if hasattr(s, "cookies") else {}
                            if "captcha_login_sign" in ck:
                                self._captcha_sign = ck["captcha_login_sign"]
                            else:
                                # 从 Set-Cookie / 响应头兜底提取
                                for hk, hv in (getattr(r2, "headers", {}) or {}).items():
                                    if isinstance(hv, str) and "captcha_login_sign" in hv:
                                        m = re.search(r"captcha_login_sign=([^;]+)", hv)
                                        if m:
                                            self._captcha_sign = m.group(1)
                        except Exception:
                            pass
                        if self._captcha_sign:
                            self.headers["Cookie"] = "accessAuth=ok; captcha_login_sign=" + self._captcha_sign
                            # 持久化 sign：后续请求/TVBox 重启后免重复 OCR
                            try:
                                if self._sign_file:
                                    with open(self._sign_file, "w") as f:
                                        f.write(self._captcha_sign)
                            except Exception:
                                pass
                        return True
                except Exception:
                    pass
            time.sleep(0.3)
        return bool(self._captcha_sign)

    def _get(self, url):
        # 已有有效 sign 时直接用（免验证）
        if self._captcha_sign:
            html = self._fetch(url)
            if not self._is_verify(html):
                if (html and len(html) > 1500) or not url.startswith(self.host):
                    return html
            # sign 失效或页面仍验证码 → 重新过验证
        else:
            html = self._fetch(url)
            if self._is_verify(html) and self._ocr is not None:
                # 命中验证码页 → 自动过验证后重试
                self._pass_captcha()
                if self._captcha_sign:
                    time.sleep(0.3)
                    html = self._fetch(url)
        if self._is_verify(html):
            html = ""
        # 主域名有正常内容（>1500字节）就直接返回
        if (html and len(html) > 1500) or not url.startswith(self.host):
            return html
        # 被验证码拦截时同站备用域名大概率同样拦截，直接放弃避免超时
        if html and self._is_verify(html):
            return ""
        # 仅当主域名过短/404 时才尝试备用域名（限制数量+短超时）
        tried = 0
        for h in self.hosts:
            if h == self.host:
                continue
            tried += 1
            if tried > 2:
                break
            try:
                t = self._fetch(url.replace(self.host, h, 1), timeout=4)
                if self._is_verify(t):
                    continue
                if self._is_valid_page(t) and "404 Not Found" not in t[:600]:
                    self.host = h
                    self.headers["Referer"] = h + "/"
                    if self._captcha_sign:
                        self.headers["Cookie"] = "accessAuth=ok; captcha_login_sign=" + self._captcha_sign
                    return t
            except Exception:
                continue
        return html

    # ---------- ID 解析（mxtheme 模板） ----------
    def _tid(self, href):
        """/type/dianying.html -> dianying"""
        m = re.search(r"/type/([a-z0-9]+)\.html", href or "")
        if m:
            return m.group(1)
        m = re.search(r"/show/id/(\d+)", href or "")
        if m:
            return m.group(1)
        m = re.search(r"/vod(?:show|type)/(\d+)", href or "")
        if m:
            return m.group(1)
        m = re.search(r"/type/id/(\d+)", href or "")
        return m.group(1) if m else ""

    def _vid(self, href):
        """/detail/128575.html -> 128575"""
        m = re.search(r"/detail/(\d+)", href or "")
        if m:
            return m.group(1)
        m = re.search(r"/detail/id/(\d+)", href or "")
        if m:
            return m.group(1)
        m = re.search(r"/voddetail/(\d+)", href or "")
        if m:
            return m.group(1)
        m = re.search(r"/id/(\d+)\.html", href or "")
        return m.group(1) if m else ""

    # ---------- 列表卡片 ----------
    def _cards(self, html):
        out, seen = [], set()
        if not html or self._is_verify(html):
            return out
        try:
            tree = etree.HTML(html)
        except Exception:
            tree = None
        if tree is not None:
            for a in tree.xpath('//a[contains(@href,"/detail/")]'):
                try:
                    href = a.get("href", "") or ""
                    vid = self._vid(href)
                    if not vid or vid in seen:
                        continue
                    img = a.xpath(".//img")
                    name, pic = "", ""
                    if img:
                        pic = img[0].get("data-original", "") or img[0].get("data-src", "") or img[0].get("src", "") or ""
                        name = (img[0].get("alt", "") or img[0].get("title", "") or "").strip()
                    if not name:
                        name = "".join(a.xpath("string(.)")).strip().split("\n")[0].strip()
                    if not name:
                        continue
                    seen.add(vid)
                    item = {"vod_id": vid, "vod_name": name, "vod_pic": self._fix(pic)}
                    rm = "".join(a.xpath('.//span[contains(@class,"pic-text") or contains(@class,"remark") or contains(@class,"state") or contains(@class,"pic-tag")]//text()')).strip()
                    if not rm:
                        p = a.getparent()
                        if p is not None:
                            rm = "".join(p.xpath('.//span[contains(@class,"pic-text") or contains(@class,"remark") or contains(@class,"state") or contains(@class,"pic-tag")]//text()')).strip()
                    if rm:
                        item["vod_remarks"] = rm
                    out.append(item)
                except Exception:
                    continue
        if not out:
            try:
                for m in re.finditer(r'<a[^>]+href="([^"]*/detail/[^"]*)"[^>]*>(.*?)</a>', html, re.S | re.I):
                    try:
                        href, inner = m.group(1), m.group(2)
                        vid = self._vid(href)
                        if not vid or vid in seen:
                            continue
                        pm = re.search(r'(?:data-original|data-src|src)="([^"]+)"', inner)
                        pic = pm.group(1) if pm else ""
                        am = re.search(r'(?:alt|title)="([^"]+)"', inner)
                        name = am.group(1).strip() if am else re.sub(r"<.*?>", "", inner).strip().split("\n")[0].strip()
                        if not name:
                            continue
                        seen.add(vid)
                        out.append({"vod_id": vid, "vod_name": name, "vod_pic": self._fix(pic)})
                    except Exception:
                        continue
            except Exception:
                pass
        return out

    # ---------- 导航分类 ----------
    def _nav(self, html):
        out, seen = [], set()
        try:
            tree = etree.HTML(html or "")
            if tree is not None:
                for a in tree.xpath('//a[contains(@href,"/type/")]'):
                    try:
                        href = a.get("href", "") or ""
                        tid = self._tid(href)
                        if not tid or tid in seen:
                            continue
                        name = self.TYPES.get(tid, "")
                        if not name:
                            name = "".join(a.xpath(".//text()")).strip()
                        if not name or len(name) > 8:
                            continue
                        if re.search(r"(首页|主页|最新|排行|留言|APP|下载|资讯|专题)", name):
                            continue
                        seen.add(tid)
                        out.append({"type_id": tid, "type_name": name})
                    except Exception:
                        continue
        except Exception:
            pass
        if not out:
            out = [{"type_id": k, "type_name": v} for k, v in self.TYPES.items()]
        return out

    def _filters(self, classes):
        f = {}
        try:
            areas = ["大陆", "香港", "台湾", "韩国", "日本", "美国", "泰国", "英国"]
            years = ["2026", "2025", "2024", "2023", "2022", "2021", "2020"]
            for c in classes:
                f[c["type_id"]] = [{"key": "area", "name": "地区", "value": [{"n": "全部", "v": ""}] + [{"n": x, "v": x} for x in areas]}, {"key": "year", "name": "年份", "value": [{"n": "全部", "v": ""}] + [{"n": x, "v": x} for x in years]}, {"key": "by", "name": "排序", "value": [{"n": "最新", "v": "time"}, {"n": "最热", "v": "hits"}, {"n": "评分", "v": "score"}]}]
        except Exception:
            pass
        return f

    def _pagecount(self, html, pg):
        try:
            # mxtheme: /type/dianying-2.html
            ms = [int(x) for x in re.findall(r"/type/[a-z0-9]+-(\d+)\.html", html or "")]
            if ms:
                return max(ms + [int(pg or 1)])
            ms = [int(x) for x in re.findall(r"/page/(\d+)\.html", html or "")]
            if ms:
                return max(ms + [int(pg or 1)])
            ms = [int(x) for x in re.findall(r"page[\"'=: ]+(\d+)", html or "")]
            if ms:
                return max(ms + [int(pg or 1)])
            ms = [int(x) for x in re.findall(r"/(?:page|p)/(\d+)", html or "")]
            if ms:
                return max(ms + [int(pg or 1)])
            m = re.search(r"共\s*(\d+)\s*页", html or "")
            if m:
                return max(int(m.group(1)), int(pg or 1))
        except Exception:
            pass
        return int(pg or 1)

    # ---------- 主接口 ----------
    def homeContent(self, filter):
        html = self._get(self.host + "/")
        cls = self._nav(html)
        ret = {"class": cls, "list": self._cards(html), "filters": {}}
        if filter:
            ret["filters"] = self._filters(cls)
        return ret

    def homeVideoContent(self):
        html = self._get(self.host + "/")
        if html and not self._has_vod_content(html):
            return {"list": []}
        return {"list": self._cards(html)}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        extend = extend or {}
        area = quote(str(extend.get("area", "") or ""))
        year = quote(str(extend.get("year", "") or ""))
        by = str(extend.get("by", "") or "")
        # mxtheme 模板：/type/{tid}-{pg}.html 或 /type/{tid}.html
        urls = []
        if tid in self.TYPES:
            if pg and pg > 1:
                urls.append(self.host + "/type/" + str(tid) + "-" + str(pg) + ".html")
                urls.append(self.host + "/type/" + str(tid) + "/page/" + str(pg) + ".html")
            urls.append(self.host + "/type/" + str(tid) + ".html")
        else:
            urls = [self.host + "/index.php/vod/show/id/" + str(tid) + "/page/" + str(pg) + ".html", self.host + "/vodshow/" + str(tid) + "--------" + str(pg) + "---.html", self.host + "/type/" + str(tid) + ".html"]
        if area or year or by:
            urls.insert(0, self.host + "/index.php/vod/show/area/" + (area if area else "all") + "/by/" + (by if by else "time") + "/id/" + str(tid) + "/page/" + str(pg) + "/year/" + (year if year else "all") + ".html")
        items, html = [], ""
        for u in urls:
            html = self._get(u)
            items = self._cards(html)
            if items:
                break
            if html and not self._has_vod_content(html):
                break
        pc = self._pagecount(html, pg)
        return {"page": pg, "pagecount": pc, "limit": 24, "total": pc * 24, "list": items}

    def detailContent(self, ids):
        vid = str(ids[0]) if ids else ""
        result = {"list": []}
        if not vid:
            return result
        urls = [vid] if vid.startswith("http") else [self.host + "/detail/" + vid + ".html", self.host + "/index.php/vod/detail/id/" + vid + ".html", self.host + "/voddetail/" + vid + ".html"]
        html = ""
        for u in urls:
            html = self._get(u)
            if html and not self._is_verify(html) and "404 Not Found" not in html[:600] and len(html) > 1500:
                break
        if not html or self._is_verify(html):
            return result
        try:
            tree = etree.HTML(html)
        except Exception:
            return result
        if tree is None:
            return result
        name = "".join(tree.xpath('//h1//text() | //*[contains(@class,"detail-title")]//text() | //*[contains(@class,"video-info-title")]//text()')).strip()
        if not name:
            m = re.search(r"<title>([^<]+)</title>", html)
            if m:
                name = re.split(r"[-_|]", m.group(1))[0].strip()
        if not name or self._is_verify(name):
            return result
        pic = ""
        for xp in ['//*[contains(@class,"detail-pic")]//img/@data-original', '//*[contains(@class,"detail-pic")]//img/@src', '//meta[@property="og:image"]/@content', '//img[contains(@class,"lazyload")]/@data-original']:
            try:
                v = tree.xpath(xp)
                if v and v[0].strip():
                    pic = v[0].strip()
                    break
            except Exception:
                continue
        actor = "".join(tree.xpath('//*[contains(text(),"主演")]/following-sibling::*[1]//text() | //*[contains(text(),"主演")]/parent::*//text() | //*[contains(@class,"actor")]//text() | //*[contains(@class,"video-info-actor")]//text()')).strip() or self.regStr(r"主演[：:]\s*([^<&\n]+)", html).strip()
        director = "".join(tree.xpath('//*[contains(text(),"导演")]/following-sibling::*[1]//text() | //*[contains(text(),"导演")]/parent::*//text() | //*[contains(@class,"director")]//text() | //*[contains(@class,"video-info-director")]//text()')).strip() or self.regStr(r"导演[：:]\s*([^<&\n]+)", html).strip()
        year = "".join(tree.xpath('//*[contains(@class,"year")]//text() | //*[contains(@class,"video-info-year")]//text()')).strip() or self.regStr(r"((?:19|20)\d{2})", html).strip()
        area = "".join(tree.xpath('//*[contains(text(),"地区")]/following-sibling::*[1]//text() | //*[contains(text(),"地区")]/parent::*//text()')).strip()
        vtype = "".join(tree.xpath('//*[contains(text(),"类型")]/following-sibling::*[1]//text() | //*[contains(text(),"类型")]/parent::*//text()')).strip()
        des = "".join(tree.xpath('//*[contains(@class,"detail-content") or contains(@class,"video-info-content") or contains(@class,"vod-content") or contains(@class,"content")]//text()')).strip()[:2000]
        # 播放列表：按线路分组（h3/h2 行 + play 链接列表）
        tabs, fro, purl = [], [], []
        # 方式1：module-play-list 结构
        ttabs = [t.strip() for t in tree.xpath('//*[contains(@class,"module-tab-item")]/span/text() | //*[contains(@class,"module-tab-item")]/text()') if t.strip()]
        lists = tree.xpath('//*[contains(@class,"module-play-list")]') or tree.xpath('//*[contains(@class,"play-list")]')
        for i, lst in enumerate(lists):
            eps = []
            for a in lst.xpath(".//a"):
                try:
                    t = "".join(a.xpath(".//text()")).strip()
                    h = self._fix(a.get("href", "") or "")
                    if t and h:
                        eps.append(t + "$" + h)
                except Exception:
                    continue
            if eps:
                fro.append(ttabs[i] if i < len(ttabs) else "线路" + str(i + 1))
                purl.append("#".join(eps))
        # 方式2：mxtheme 结构（ul/li > a，前有线路标题）
        if not purl:
            blocks = tree.xpath('//ul[.//a[contains(@href,"/play/")]]')
            for i, ul in enumerate(blocks):
                eps = []
                for a in ul.xpath(".//a[contains(@href,'/play/')]"):
                    try:
                        t = "".join(a.xpath(".//text()")).strip()
                        h = self._fix(a.get("href", "") or "")
                        if t and h:
                            eps.append(t + "$" + h)
                    except Exception:
                        continue
                if eps:
                    # 找线路名：该 ul 所在块内前面的标题（h2/h3/h4/div[class*=title]）
                    lbl = ""
                    for node in ul.xpath("preceding-sibling::*[self::h2 or self::h3 or self::h4 or self::h5 or contains(@class,'title')][1]"):
                        txt = "".join(node.xpath(".//text()")).strip()
                        if txt:
                            lbl = txt[:20]
                    if not lbl:
                        # 向上两级找标题
                        for anc in ul.xpath("ancestor::*[contains(@class,'block') or contains(@class,'main') or contains(@class,'play')][1]"):
                            for node in anc.xpath("preceding-sibling::*[self::h2 or self::h3 or self::h4 or self::h5 or contains(@class,'title')][1]"):
                                txt = "".join(node.xpath(".//text()")).strip()
                                if txt:
                                    lbl = txt[:20]
                    fro.append(lbl or "线路" + str(i + 1))
                    purl.append("#".join(eps))
        # 方式3：所有 /play/ 链接合并为单线路
        if not purl:
            eps = []
            for a in tree.xpath('//a[contains(@href,"/play/")]'):
                try:
                    t = "".join(a.xpath(".//text()")).strip()
                    h = self._fix(a.get("href", "") or "")
                    if t and h:
                        eps.append(t + "$" + h)
                except Exception:
                    continue
            if eps:
                fro, purl = ["播放"], ["#".join(eps)]
        # 反爬兜底：无播放源且名称是站点名 → 判定为拦截页；
        # 或页面含导航/收藏/防走失特征且无播放源 → 同样拦截
        if not purl:
            low = (html or "").lower()
            nav_pat = re.search(r"(Ctrl\+D|收藏本页|防走失|打不开提示|请输入访问验证码|访问此数据|最新地址|浏览器访问)", low)
            if (name.strip() in self.SITE_NAMES) or nav_pat:
                return result
        vod = {"vod_id": vid, "vod_name": name, "vod_pic": self._fix(pic), "vod_actor": actor, "vod_director": director, "vod_year": year, "vod_area": area, "vod_type": vtype, "vod_content": des, "vod_play_from": "$$$".join(fro), "vod_play_url": "$$$".join(purl)}
        result["list"].append(vod)
        return result

    def searchContent(self, key, quick, pg="1"):
        pg = int(pg or 1)
        q = quote(str(key))
        items = []
        for u in [self.host + "/search/" + q + "-------------.html", self.host + "/index.php/vod/search.html?wd=" + q + "&page=" + str(pg), self.host + "/index.php/vod/search.html?wd=" + q]:
            items = self._cards(self._get(u))
            if items:
                break
        return {"list": items, "page": pg}

    def searchContentPage(self, key, quick, page):
        return self.searchContent(key, quick, page)

    def _playurl(self, html):
        try:
            # 仅提取真实 http(s) 播放地址；加密串（无协议头）不属于可直接播放的 URL
            m = re.search(r'player_aaaa\s*=\s*\{.*?"url"\s*:\s*"((?:[^"\\]|\\.)*)"', html or "", re.S)
            if m:
                u = m.group(1).replace("\\/", "/").replace("\\u003a", ":").replace("\\u0026", "&")
                if u.startswith(("http://", "https://", "//")) and u not in ("did", "null", "undefined"):
                    return u
            m = re.search(r'MacPlayerConfig\s*=\s*\{.*?player_data\s*=\s*\{.*?"url"\s*:\s*"((?:[^"\\]|\\.)*)"', html or "", re.S)
            if m:
                u = m.group(1).replace("\\/", "/")
                if u.startswith(("http://", "https://", "//")) and u not in ("did", "null"):
                    return u
            m = re.search(r'player_data\s*=\s*\{.*?"url"\s*:\s*"((?:[^"\\]|\\.)*)"', html or "", re.S)
            if m:
                u = m.group(1).replace("\\/", "/")
                if u.startswith(("http://", "https://", "//")) and u not in ("did", "null"):
                    return u
            m = re.search(r'"url"\s*:\s*"(https?[^"]+\.m3u8[^"]*)"', html or "")
            if m:
                return m.group(1).replace("\\/", "/")
            m = re.search(r'"url"\s*:\s*"(https?[^"]+\.mp4[^"]*)"', html or "")
            if m:
                return m.group(1).replace("\\/", "/")
            m = re.search(r'var\s+now\s*=\s*["\']([^"\']+)["\']', html or "")
            if m and m.group(1).startswith("http"):
                return m.group(1)
            m = re.search(r'(https?[^"\'\s\\]+\.m3u8[^"\'\s\\]*)', html or "")
            if m:
                return m.group(1)
            m = re.search(r'(https?[^"\'\s\\]+\.mp4[^"\'\s\\]*)', html or "")
            if m:
                return m.group(1)
        except Exception:
            pass
        return ""

    def _iframe(self, html):
        try:
            m = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', html or "", re.I)
            if m:
                return self._fix(m.group(1))
        except Exception:
            pass
        return ""

    def playerContent(self, flag, id, vipFlags):
        pid = id or ""
        if pid.startswith("http"):
            page = pid
        elif pid.startswith("/"):
            page = self.host + pid
        else:
            page = self.host + "/play/" + pid + ".html"
        html = self._get(page)
        if self._is_verify(html):
            return {"parse": 1, "url": page}
        url = self._playurl(html)
        if url and (url.startswith("http") or url.startswith("//")):
            return {"parse": 0, "url": self._fix(url), "header": {"User-Agent": self.ua, "Referer": page, "Cookie": "accessAuth=ok"}}
        fr = self._iframe(html)
        if fr:
            url = self._playurl(self._get(fr))
            if url:
                return {"parse": 0, "url": self._fix(url), "header": {"User-Agent": self.ua, "Referer": fr}}
        if url and not url.startswith("http"):
            return {"parse": 0, "url": url, "header": {"User-Agent": self.ua, "Referer": page}}
        # 播放器 URL 为加密串（encrypt 0/1/2 需 JS 解密）：
        # 若页面含 player_aaaa 配置，说明是 JS 播放器站 → 返回原页面让 TVBox 内嵌解析
        if "player_aaaa=" in (html or "") or "MacPlayer" in (html or ""):
            return {"parse": 1, "url": page, "header": {"User-Agent": self.ua, "Referer": page, "Cookie": "accessAuth=ok"}}
        return {"parse": 1, "url": page}

    def isVideoFormat(self, url):
        u = (url or "").lower()
        return ".m3u8" in u or ".mp4" in u or ".m4v" in u or ".flv" in u or ".ts" in u or ".webm" in u or ".mov" in u or ".mpd" in u

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return None

    def getDependence(self):
        return []

    def destroy(self):
        return None