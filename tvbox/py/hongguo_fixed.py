# -*- coding: utf-8 -*-
"""
红果短剧 (hongguo / www.hongguoapp.cn) —— TVBox/FongMi Spider
搜索能力修复版（2026-09-10）：

【故障根因】
  站点首页/详情页可 200 访问，但传统苹果CMS搜索页
  `/vodsearch/-------------.html?wd=xxx` 与 `/index.php/vod/search.html`
  已被 Cloudflare 接管，一律返回 403 "Just a moment..."，
  故旧 searchContent（纯 HTML 搜索页解析）永远拿到空列表。

【修复】
  searchContent/searchContentPage 改走站点自带、无 CF 拦截的
  JSON 接口：`/index.php/ajax/suggest?mid=1&wd=<quote(key)>`
  返回 {"code":1,"page":..,"pagecount":..,"limit":..,"total":..,
        "list":[{"id","name","en","pic"}, ...]}，
  直出 vod_id/vod_name/vod_pic（海螺/conch 模板官方搜索建议接口，
  实测 HTTP 200、家庭宽带/数据中心 IP 均可访问）。

  其余接口保留苹果CMS/conch 常规形态（home/category/detail/player），
  并保留多 URL 兜底 + 正则兜底，保证其它能力不受影响。

接口约定（TVBox/FongMi chaquo python spider）：
  getName / init / homeContent / homeVideoContent / categoryContent /
  detailContent / searchContent / searchContentPage /
  playerContent / isVideoFormat / manualVideoCheck /
  localProxy / getDependence / destroy
"""
import re
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

sys.path.append('..')
try:
    from base.spider import Spider as BaseSpider
except Exception:
    from spider import Spider as BaseSpider


class Spider(BaseSpider):

    def getName(self):
        return "红果"

    def init(self, extend=""):
        self.host = "https://www.hongguoapp.cn"
        self.hosts = ["https://www.hongguoapp.cn"]
        try:
            o = json.loads(extend) if extend else {}
            if isinstance(o, dict) and o.get("host"):
                self.host = o["host"].rstrip("/")
                self.hosts = [self.host] + [h for h in self.hosts if h != self.host]
        except Exception:
            pass
        # 移动 UA：与站点搜索表单页/详情页兼容最好
        self.ua = ("Mozilla/5.0 (Linux; Android 12; SM-G991B) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36")
        self.headers = {
            "User-Agent": self.ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.host + "/",
        }
        self._json_headers = {
            "User-Agent": self.ua,
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.host + "/",
            "X-Requested-With": "XMLHttpRequest",
        }
        self._sess = requests.Session()
        try:
            self._sess.headers.update(self.headers)
        except Exception:
            pass

    # ---------- 基础工具 ----------
    def _fix(self, u):
        if not u:
            return ""
        u = str(u).strip().replace("\\/", "/")
        if u.startswith("//"):
            return "https:" + u
        if u.startswith("/"):
            return self.host + u
        return u

    def _fetch(self, url, timeout=15, headers=None, retries=3):
        """带重试的 HTML 抓取。手机端 DNS 偶发 result_code:408（首次 lookup 失败、
        随后 netd 重试才成功），单发请求极易撞上空窗直接返回空；这里对空结果/
        超时/连接异常做短退避重试，保证 search/detail 在弱网下仍有结果。"""
        last = ""
        for i in range(max(1, int(retries or 1))):
            try:
                r = self._sess.get(url, headers=headers or self.headers,
                                   timeout=timeout, verify=False, allow_redirects=True)
                r.encoding = "utf-8"
                last = r.text or ""
                # CF 拦截页/超短错误页不值得重试，直接返回交由上层判断
                if last and (len(last) > 1500 or "Just a moment" in last[:3000]):
                    return last
            except Exception:
                last = last or ""
            if i < int(retries or 1) - 1:
                try:
                    time.sleep(0.6 * (i + 1))
                except Exception:
                    pass
                continue
        if last and len(last) > 1500:
            return last
        # session 失败则换直连再试一次（排除连接池污染）
        try:
            r = requests.get(url, headers=headers or self.headers,
                             timeout=timeout, verify=False, allow_redirects=True)
            r.encoding = "utf-8"
            return r.text or last
        except Exception:
            return last

    def _fetch_json(self, url, timeout=12, retries=3):
        """取 JSON 接口（带重试）；成功返回 dict，失败返回 {}。
        手机端 DNS 首次 lookup 常报 408，随后才成功——对超时/连接错误/空体/
        非 JSON 均退避重试；HTTP 非 200（如 CF 403）不重试直接判失败。"""
        last_err = ""
        for i in range(max(1, int(retries or 1))):
            try:
                r = self._sess.get(url, headers=self._json_headers,
                                   timeout=timeout, verify=False, allow_redirects=True)
                if r.status_code != 200:
                    return {}
                try:
                    j = r.json()
                except Exception:
                    return {}
                if isinstance(j, dict) and j.get("code") == 1 and isinstance(j.get("list"), list):
                    return j
                return {}
            except Exception as e:
                last_err = repr(e)[:120]
                if i < int(retries or 1) - 1:
                    try:
                        time.sleep(0.8 * (i + 1))
                    except Exception:
                        pass
        # 兜底：换直连再试一次
        try:
            r = requests.get(url, headers=self._json_headers,
                             timeout=timeout, verify=False, allow_redirects=True)
            if r.status_code == 200:
                j = r.json()
                if isinstance(j, dict):
                    return j
        except Exception as e:
            last_err = repr(e)[:120]
        return {}

    def _get(self, url):
        html = self._fetch(url)
        if html and len(html) > 1500:
            return html
        for h in self.hosts:
            if h == self.host:
                continue
            try:
                t = self._fetch(url.replace(self.host, h, 1), timeout=8)
                if t and len(t) > 1500 and "Just a moment" not in t[:2000] \
                        and "404 Not Found" not in t[:600]:
                    self.host = h
                    self.headers["Referer"] = h + "/"
                    self._json_headers["Referer"] = h + "/"
                    return t
            except Exception:
                continue
        return html

    def _is_cf(self, html):
        return bool(html) and ("Just a moment" in html[:3000] or "challenges.cloudflare.com" in html[:8000])

    # ---------- ID 解析（海螺/conch 模板） ----------
    def _tid(self, href):
        m = re.search(r"/vodshow/(\d+)", href or "")
        if m:
            return m.group(1)
        m = re.search(r"/show/id/(\d+)", href or "")
        if m:
            return m.group(1)
        m = re.search(r"/vod(?:show|type)/(\d+)", href or "")
        return m.group(1) if m else ""

    def _vid(self, href):
        m = re.search(r"/voddetail/(\d+)", href or "")
        if m:
            return m.group(1)
        m = re.search(r"/detail/id/(\d+)", href or "")
        if m:
            return m.group(1)
        m = re.search(r"/id/(\d+)\.html", href or "")
        return m.group(1) if m else ""

    # ---------- 列表卡片 ----------
    def _cards(self, html):
        out, seen = [], set()
        if not html or self._is_cf(html):
            return out
        try:
            tree = etree.HTML(html)
        except Exception:
            tree = None
        if tree is not None:
            # 海螺(conch)：快照 <a class="hl-item-thumb" href="/voddetail/xxx.html" title data-original>；
            # 兼容苹果CMS /detail/ 与 /vod/detail 形态 #1
            for a in tree.xpath('//a[contains(@class,"hl-item-thumb") or contains(@href,"/voddetail/") '
                                'or contains(@href,"/vod/detail") or contains(@href,"/detail/")]'):
                try:
                    href = a.get("href", "") or ""
                    vid = self._vid(href)
                    if not vid or vid in seen:
                        continue
                    name = (a.get("title", "") or "").strip()
                    pic = (a.get("data-original", "") or a.get("data-src", "") or "").strip()
                    if not pic:
                        img = a.xpath(".//img")
                        if img:
                            pic = (img[0].get("data-original", "") or img[0].get("data-src", "")
                                   or img[0].get("src", "") or "")
                            if not name:
                                name = (img[0].get("alt", "") or img[0].get("title", "") or "").strip()
                    if not name:
                        # 标题在同 li 的 .hl-item-title > a
                        try:
                            li = a.getparent()
                            if li is not None:
                                t = li.xpath('.//*[contains(@class,"hl-item-title")]//a/text()')
                                if t:
                                    name = t[0].strip()
                        except Exception:
                            pass
                    if not name:
                        name = "".join(a.xpath("string(.)")).strip().split("\n")[0].strip()
                    if not name:
                        continue
                    seen.add(vid)
                    item = {"vod_id": vid, "vod_name": name, "vod_pic": self._fix(pic)}
                    rm = "".join(a.xpath('.//span[contains(@class,"pic-text") or contains(@class,"remark") '
                                         'or contains(@class,"state") or contains(@class,"pic-tag") '
                                         'or contains(@class,"remarks")]//text()')).strip()
                    if not rm:
                        try:
                            li = a.getparent()
                            if li is not None:
                                rm = "".join(li.xpath('.//*[contains(@class,"remarks") or contains(@class,"pic-text")]//text()')).strip()
                        except Exception:
                            pass
                    if rm:
                        item["vod_remarks"] = rm
                    out.append(item)
                except Exception:
                    continue
        if not out:
            try:
                for m in re.finditer(r'<a[^>]+href="([^"]*/voddetail/[^"]*|[^"]*/detail/[^"]*)"[^>]*>(.*?)</a>', html, re.S | re.I):
                    try:
                        href, inner = m.group(1), m.group(2)
                        vid = self._vid(href)
                        if not vid or vid in seen:
                            continue
                        tm = re.search(r'title="([^"]+)"', m.group(0))
                        name = tm.group(1).strip() if tm else ""
                        pm = re.search(r'(?:data-original|data-src|src)="([^"]+)"', m.group(0) + inner)
                        pic = pm.group(1) if pm else ""
                        if not name:
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

    # ---------- 主接口 ----------
    def homeContent(self, filter):
        html = self._get(self.host + "/")
        cls = [{"type_id": "51", "type_name": "短剧"}]
        try:
            tree = etree.HTML(html or "")
            if tree is not None:
                for a in tree.xpath('//a[contains(@href,"/vodshow/") or contains(@href,"/show/id/")]'):
                    try:
                        tid = self._tid(a.get("href", "") or "")
                        name = "".join(a.xpath(".//text()")).strip()
                        if tid and name and len(name) <= 10 and not any(x in name for x in ("首页", "播放", "订阅", "RSS")):
                            if all(c.get("type_id") != tid for c in cls):
                                cls.append({"type_id": tid, "type_name": name})
                    except Exception:
                        continue
        except Exception:
            pass
        return {"class": cls, "list": self._cards(html), "filters": {}}

    def homeVideoContent(self):
        return {"list": self._cards(self._get(self.host + "/"))}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        extend = extend or {}
        tid = str(tid or "51")
        # data JSON 接口：tid=51 + page=N（实测 page 翻页有效），字段齐全；
        # HTML 仅作兜底（/vodshow/51-----------.html 第1页；注意 …1---.html 会"暂无数据"）
        items, pagecount, total = [], pg, pg * 24
        j = self._fetch_json(self.host + "/index.php/ajax/data?mid=1&limit=24&tid=" + quote(tid)
                             + ("&page=" + str(pg) if pg > 1 else ""))
        if j and isinstance(j.get("list"), list) and j.get("list"):
            for it in j["list"]:
                try:
                    vid = str(it.get("vod_id", "") or "")
                    name = str(it.get("vod_name", "") or "").strip()
                    if not vid or not name:
                        continue
                    item = {"vod_id": vid, "vod_name": name, "vod_pic": self._fix(it.get("vod_pic", "") or "")}
                    rm = str(it.get("vod_remarks", "") or "").strip()
                    if rm:
                        item["vod_remarks"] = rm
                    items.append(item)
                except Exception:
                    continue
            try:
                pagecount = int(j.get("pagecount", pg) or pg)
            except Exception:
                pass
            try:
                total = int(j.get("total", 0) or 0)
            except Exception:
                pass
            return {"page": pg, "pagecount": pagecount, "limit": 24,
                    "total": total or pagecount * 24, "list": items}
        html = ""
        for u in [self.host + "/vodshow/" + tid + "-----------.html",
                  self.host + "/index.php/vod/show/id/" + tid + "/page/" + str(pg) + ".html"]:
            html = self._get(u)
            items = self._cards(html)
            if items:
                break
        try:
            ms = [int(x) for x in re.findall(r"第\s*(\d+)\s*页", html or "")]
        except Exception:
            ms = []
        pc = max(ms + [pg]) if ms else pg
        return {"page": pg, "pagecount": pc, "limit": 24, "total": pc * 24, "list": items}

    def detailContent(self, ids):
        vid = str(ids[0]) if ids else ""
        result = {"list": []}
        if not vid:
            return result
        urls = [vid] if vid.startswith("http") else \
            [self.host + "/voddetail/" + vid + ".html",
             self.host + "/index.php/vod/detail/id/" + vid + ".html"]
        html = ""
        for u in urls:
            html = self._get(u)
            if html and not self._is_cf(html) and "404 Not Found" not in html[:600] and len(html) > 1500:
                break
        if not html or self._is_cf(html):
            return result
        try:
            tree = etree.HTML(html)
        except Exception:
            return result
        if tree is None:
            return result
        # 海螺(conch)模板：剧名在 h2.hl-dc-title；兼容 mxtheme 的 h1/detail-title
        name = "".join(tree.xpath('//h2[contains(@class,"hl-dc-title")]//text()')).strip()
        if not name:
            name = "".join(tree.xpath('//h1//text() | //*[contains(@class,"detail-title")]//text() | '
                                      '//*[contains(@class,"video-info-title")]//text()')).strip()
        if not name:
            m = re.search(r"<title>([^<]+)</title>", html)
            if m:
                name = re.split(r"[-_|《]", m.group(1))[0].strip("《 ")
        if not name:
            return result
        pic = ""
        for xp in ['//*[contains(@class,"hl-item-thumb")]/@data-original',
                   '//*[contains(@class,"detail-pic")]//img/@data-original',
                   '//*[contains(@class,"detail-pic")]//img/@src',
                   '//*[@class="hl-topbg-pic"]/@style',
                   '//meta[@property="og:image"]/@content']:
            try:
                v = tree.xpath(xp)
                if v and v[0].strip():
                    pic = v[0].strip()
                    break
            except Exception:
                continue
        actor = "".join(tree.xpath('//*[contains(@class,"video-info-actor")]//text()')).strip()
        if not actor or actor in ("未知", "内详"):
            actor = "".join(tree.xpath('//li[contains(.,"主演")]//a/text()')).strip()
            if not actor:
                actor = self.regStr(r"主演[：:]\s*([^<&\n]+)", html).strip()
        director = "".join(tree.xpath('//*[contains(@class,"video-info-director")]//text()')).strip()
        if not director or director in ("未知", "内详"):
            director = "".join(tree.xpath('//li[contains(.,"导演")]/text() | //li[contains(.,"导演")]//a/text()')).strip()
            if not director or director in ("未知", "内详"):
                director = self.regStr(r"导演[：:]\s*([^<&\n]+)", html).strip()
        year = "".join(tree.xpath('//*[contains(@class,"video-info-year")]//text()')).strip()
        if not year or year in ("未知", "内详"):
            year = "".join(tree.xpath('//li[contains(.,"年份")]//text()')).strip()
            my = re.search(r"((?:19|20)\d{2})", year or "")
            year = my.group(1) if my else self.regStr(r"((?:19|20)\d{2})", html).strip()
        area = "".join(tree.xpath('//*[contains(text(),"地区")]/following-sibling::*[1]//text()')).strip()
        if not area or area in ("未知", "内详"):
            area = "".join(tree.xpath('//li[contains(.,"地区")]//text()')).strip()
            area = re.sub(r"^地区[：:\s]*", "", area).strip()
        vtype = "".join(tree.xpath('//li[contains(.,"类型")]//a/text()')).strip()
        if vtype:
            try:
                vtype = "/".join([t.strip() for t in tree.xpath('//li[contains(.,"类型")]//a/text()') if t.strip()])
            except Exception:
                pass
        des = "".join(tree.xpath('//li[contains(.,"简介")]//text()')).strip()
        des = re.sub(r"^简介[：:\s]*", "", des).strip()
        if not des:
            des = "".join(tree.xpath('//*[contains(@class,"detail-content") or contains(@class,"video-info-content") '
                                     'or contains(@class,"vod-content")]//text()')).strip()[:2000]
        # 播放列表：/vodplay/{vid}-1-{n}.html
        eps = []
        try:
            for a in tree.xpath('//a[contains(@href,"/vodplay/")]'):
                try:
                    t = "".join(a.xpath(".//text()")).strip()
                    h = self._fix(a.get("href", "") or "")
                    if t and h and h not in [e.split("$", 1)[1] for e in eps if "$" in e]:
                        eps.append(t + "$" + h)
                except Exception:
                    continue
        except Exception:
            pass
        if not eps:
            for m in re.finditer(r'href="((?:[^"]*/vodplay/[^"]*\.html))"[^>]*>([^<]{1,30})</a>', html or ""):
                try:
                    eps.append(m.group(2).strip() + "$" + self._fix(m.group(1)))
                except Exception:
                    continue
        vod = {"vod_id": vid, "vod_name": name, "vod_pic": self._fix(pic),
               "vod_actor": actor, "vod_director": director, "vod_year": year,
               "vod_area": area, "vod_content": des,
               "vod_play_from": "红果" if eps else "",
               "vod_play_url": "#".join(eps)}
        result["list"].append(vod)
        return result

    # ---------- 搜索（修复核心） ----------
    def _search_all(self, key, limit=200):
        """suggest JSON 接口一次取全量（limit=200；实测该接口无视 page/pg 翻页参数，
        但 limit 生效：limit=200 时 total=106 的词一次返回全部 106 条）。
        返回 (items, total)。"""
        q = quote(str(key or "").strip())
        if not q:
            return [], 0
        try:
            limit = max(1, min(int(limit or 200), 200))
        except Exception:
            limit = 200
        j = self._fetch_json(self.host + "/index.php/ajax/suggest?mid=1&wd=" + q
                             + "&limit=" + str(limit))
        if not j or j.get("code") != 1 or not isinstance(j.get("list"), list):
            return [], 0
        items = []
        for it in (j.get("list") or []):
            try:
                vid = str(it.get("id", "") or "")
                name = str(it.get("name", "") or "").strip()
                if not vid or not name:
                    continue
                items.append({"vod_id": vid, "vod_name": name,
                              "vod_pic": self._fix(it.get("pic", "") or "")})
            except Exception:
                continue
        try:
            total = int(j.get("total", 0) or 0)
        except Exception:
            total = 0
        return items, total or len(items)

    def _search_json(self, key, pg=1, limit=20):
        """兼容旧签名：取全量后按 pg 切片。"""
        items, total = self._search_all(key)
        pg = max(1, int(pg or 1))
        try:
            limit = max(1, int(limit or 20))
        except Exception:
            limit = 20
        start = (pg - 1) * limit
        page_items = items[start:start + limit]
        try:
            pagecount = max(1, -(-int(total) // limit))
        except Exception:
            pagecount = 1
        return page_items, pg, pagecount, total

    def searchContent(self, key, quick, pg="1"):
        """quick=True（聚合快搜）/False 均走 suggest JSON 全量+本地分页；
        HTML 搜索页仅作兜底（目前被 CF 403 拦截）。
        聚合搜索对本接口有整体超时预算：quick=True 时 limit 取 60 首屏更快、
        失败更快；quick=False（翻页/全量）时 limit=200 取全量。"""
        pg = int(pg or 1)
        try:
            limit = 60 if quick else 200
        except Exception:
            limit = 200
        items, page, pagecount, total = self._search_json(key, pg, limit=limit)
        if items:
            return {"list": items, "page": page, "pagecount": pagecount,
                    "limit": 20, "total": total}
        # 兜底：传统 HTML 搜索页（若将来 CF 放行仍可工作）
        q = quote(str(key or ""))
        for u in [self.host + "/vodsearch/-------------.html?wd=" + q,
                  self.host + "/index.php/vod/search.html?wd=" + q]:
            items = self._cards(self._get(u))
            if items:
                break
        return {"list": items, "page": pg}

    def searchContentPage(self, key, quick, page):
        return self.searchContent(key, quick, page)

    # ---------- 播放 ----------
    def _playurl(self, html):
        try:
            for m in re.finditer(r'player_[a-z0-9]+=(\{.*?\})\s*</script>', html or "", re.S):
                try:
                    obj = json.loads(m.group(1))
                except Exception:
                    continue
                url = obj.get("url") or ""
                if ";" in url:
                    url = url.split(";")[0]
                if isinstance(url, str) and re.search(r'https?://\S+\.m3u8', url):
                    return url
            m = re.search(r'"url"\s*:\s*"(https?[^"]+\.m3u8[^"]*)"', html or "")
            if m:
                return m.group(1).replace("\\/", "/")
            m = re.search(r'"url"\s*:\s*"(https?[^"]+\.mp4[^"]*)"', html or "")
            if m:
                return m.group(1).replace("\\/", "/")
            m = re.search(r'(https?[^"\'\s\\]+\.m3u8[^"\'\s\\]*)', html or "")
            if m:
                return m.group(1)
            m = re.search(r'(https?[^"\'\s\\]+\.mp4[^"\'\s\\]*)', html or "")
            if m:
                return m.group(1)
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
            page = self.host + "/vodplay/" + pid + ".html"
        html = self._get(page)
        if self._is_cf(html):
            return {"parse": 1, "url": page}
        url = self._playurl(html)
        if url and (url.startswith("http") or url.startswith("//")):
            return {"parse": 0, "url": self._fix(url),
                    "header": {"User-Agent": self.ua, "Referer": page}}
        m = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', html or "", re.I)
        if m:
            fr = self._fix(m.group(1))
            url = self._playurl(self._get(fr))
            if url:
                return {"parse": 0, "url": self._fix(url),
                        "header": {"User-Agent": self.ua, "Referer": fr}}
        if "player_" in (html or "") or "MacPlayer" in (html or ""):
            return {"parse": 1, "url": page,
                    "header": {"User-Agent": self.ua, "Referer": page}}
        return {"parse": 1, "url": page}

    def isVideoFormat(self, url):
        u = (url or "").lower()
        return ".m3u8" in u or ".mp4" in u or ".m4v" in u or ".flv" in u \
            or ".ts" in u or ".webm" in u or ".mov" in u or ".mpd" in u

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return None

    def getDependence(self):
        return []

    def destroy(self):
        try:
            self._sess.close()
        except Exception:
            pass
        return None
