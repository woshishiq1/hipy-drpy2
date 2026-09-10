# -*- coding: utf-8 -*-
import re
import sys
import json
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
    # 反爬/验证码页特征关键词（站点目前会返回“系统安全验证”等拦截页）
    VERIFY_KWS = ("系统安全验证", "安全验证", "验证码", "请输入访问验证码", "captcha", "访问此数据需要")
    def getName(self):
        return "蛋蛋奇"
    def init(self, extend=""):
        # 默认域名优先选用可访问（假验证码可过）的 www.dandanqi.com；
        # 其余为备用源，_get() 会自动轮换跳过验证码页。
        self.host = "https://www.dandanqi.com"
        self.hosts = ["https://www.dandanqi.com", "https://dandanqi.cc", "https://www.dandanqi.cc", "https://www.dandanqi.pro", "https://www.dandanqi.fun", "https://www.dandanqi.me"]
        try:
            o = json.loads(extend) if extend else {}
            if isinstance(o, dict) and o.get("host"):
                self.host = o["host"]
                self.hosts = [o["host"]] + self.hosts
        except Exception:
            pass
        self.ua = "Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
        self.headers = {"User-Agent": self.ua, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Accept-Language": "zh-CN,zh;q=0.9", "Referer": self.host + "/", "Cookie": "accessAuth=ok"}
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
    def _fetch(self, url, timeout=8):
        try:
            r = requests.get(url, headers=self.headers, timeout=timeout, verify=False, allow_redirects=True)
            r.encoding = "utf-8"
            return r.text or ""
        except Exception:
            return ""
    def _is_valid_page(self, html):
        """页面是否包含真实视频内容（排除验证码/404/过短页）"""
        if not html or self._is_verify(html):
            return False
        if len(html) < 1500:
            return False
        low = html.lower()
        if "404 not found" in low[:600]:
            return False
        return True

    def _has_vod_content(self, html):
        """页面是否含真实视频结构（卡片链接/播放列表/详情标题等）"""
        low = (html or "").lower()
        if "voddetail" in low or "vod/detail" in low:
            return True
        if "vodshow" in low or "detail-title" in low or "module-play-list" in low or "module-list" in low or "stui-vodlist" in low:
            return True
        return False

    def _get(self, url):
        html = self._fetch(url)
        verify = self._is_verify(html)
        if verify:
            html = ""
        # 主域名有正常内容（>1500字节）就直接返回；
        # 导航/拦截等无视频页由上层 _cards/_nav/_is_verify 安全处理，
        # 避免触发所有备用域名遍历导致超时。
        if (html and len(html) > 1500) or not url.startswith(self.host):
            return html
        # 被验证码拦截时同站备用域名大概率同样拦截，直接放弃，避免 TVBox 超时
        if verify:
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
                    return t
            except Exception:
                continue
        return html
    def _tid(self, href):
        m = re.search(r"/show/id/(\d+)", href or "")
        if m:
            return m.group(1)
        m = re.search(r"/vod(?:show|type)/(\d+)", href or "")
        if m:
            return m.group(1)
        m = re.search(r"/type/id/(\d+)", href or "")
        return m.group(1) if m else ""
    def _vid(self, href):
        m = re.search(r"/detail/id/(\d+)", href or "")
        if m:
            return m.group(1)
        m = re.search(r"/voddetail/(\d+)", href or "")
        if m:
            return m.group(1)
        m = re.search(r"/id/(\d+)\.html", href or "")
        return m.group(1) if m else ""
    def _cards(self, html):
        out, seen = [], set()
        if not html or self._is_verify(html):
            return out
        try:
            tree = etree.HTML(html)
        except Exception:
            tree = None
        if tree is not None:
            for a in tree.xpath('//a[contains(@href,"/voddetail/") or contains(@href,"/vod/detail")]'):
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
                    rm = "".join(a.xpath('.//span[contains(@class,"pic-text") or contains(@class,"remark") or contains(@class,"state")]//text()')).strip()
                    if not rm:
                        p = a.getparent()
                        if p is not None:
                            rm = "".join(p.xpath('.//span[contains(@class,"pic-text") or contains(@class,"remark") or contains(@class,"state")]//text()')).strip()
                    if rm:
                        item["vod_remarks"] = rm
                    out.append(item)
                except Exception:
                    continue
        if not out:
            try:
                for m in re.finditer(r'<a[^>]+href="([^"]*(?:voddetail|vod/detail)[^"]*)"[^>]*>(.*?)</a>', html, re.S | re.I):
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
    def _nav(self, html):
        out, seen = [], set()
        try:
            tree = etree.HTML(html or "")
            if tree is not None:
                for a in tree.xpath('//a[contains(@href,"/vodshow/") or contains(@href,"/vodtype/") or contains(@href,"/vod/show") or contains(@href,"vod/type")]'):
                    try:
                        href = a.get("href", "") or ""
                        name = "".join(a.xpath(".//text()")).strip()
                        tid = self._tid(href)
                        if not tid or not name or tid in seen or len(name) > 8:
                            continue
                        if re.search(r"(首页|主页|最新|排行|留言|APP|下载|资讯|专题)", name):
                            continue
                        seen.add(tid)
                        out.append({"type_id": tid, "type_name": name})
                    except Exception:
                        continue
        except Exception:
            pass
        return out or [{"type_id": "1", "type_name": "电影"}, {"type_id": "2", "type_name": "电视剧"}, {"type_id": "3", "type_name": "综艺"}, {"type_id": "4", "type_name": "动漫"}]
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
            ms = [int(x) for x in re.findall(r"/page/(\d+)\.html", html or "")]
            if ms:
                return max(ms + [int(pg or 1)])
            ms = [int(x) for x in re.findall(r"page[\"'=: ]+(\d+)", html or "")]
            if ms:
                return max(ms + [int(pg or 1)])
            m = re.search(r"共\s*(\d+)\s*页", html or "")
            if m:
                return max(int(m.group(1)), int(pg or 1))
        except Exception:
            pass
        return int(pg or 1)
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
        urls = [self.host + "/index.php/vod/show/id/" + str(tid) + "/page/" + str(pg) + ".html", self.host + "/vodshow/" + str(tid) + "--------" + str(pg) + "---.html", self.host + "/index.php/vod/show/id/" + str(tid) + "/page/" + str(pg) + "/year/" + (year if year else "all") + ".html", self.host + "/vodtype/" + str(tid) + "-" + str(pg) + ".html"]
        if area or year or by:
            urls.insert(0, self.host + "/index.php/vod/show/area/" + (area if area else "all") + "/by/" + (by if by else "time") + "/id/" + str(tid) + "/page/" + str(pg) + "/year/" + (year if year else "all") + ".html")
        items, html = [], ""
        for u in urls:
            html = self._get(u)
            items = self._cards(html)
            if items:
                break
            # 页面无视频结构（验证码/导航/拦截页）→ 站点当前不可用，立即结束避免超时
            if html and not self._has_vod_content(html):
                break
        pc = self._pagecount(html, pg)
        return {"page": pg, "pagecount": pc, "limit": 24, "total": pc * 24, "list": items}
    def detailContent(self, ids):
        vid = str(ids[0]) if ids else ""
        result = {"list": []}
        if not vid:
            return result
        urls = [vid] if vid.startswith("http") else [self.host + "/index.php/vod/detail/id/" + vid + ".html", self.host + "/voddetail/" + vid + ".html"]
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
        name = "".join(tree.xpath('//h1[contains(@class,"title")]//text() | //*[contains(@class,"detail-title")]//text()')).strip()
        if not name:
            m = re.search(r"<title>([^<]+)</title>", html)
            if m:
                name = re.split(r"[-_|]", m.group(1))[0].strip()
        if not name or self._is_verify(name):
            return result
        pic = ""
        for xp in ['//*[contains(@class,"detail-pic")]//img/@data-original', '//*[contains(@class,"detail-pic")]//img/@src', '//meta[@property="og:image"]/@content']:
            try:
                v = tree.xpath(xp)
                if v and v[0].strip():
                    pic = v[0].strip()
                    break
            except Exception:
                continue
        actor = "".join(tree.xpath('//*[contains(text(),"主演")]/following-sibling::*[1]//text() | //*[contains(@class,"actor")]//text()')).strip() or self.regStr(r"主演[：:]\s*([^<&\n]+)", html).strip()
        director = "".join(tree.xpath('//*[contains(text(),"导演")]/following-sibling::*[1]//text() | //*[contains(@class,"director")]//text()')).strip() or self.regStr(r"导演[：:]\s*([^<&\n]+)", html).strip()
        year = "".join(tree.xpath('//*[contains(@class,"year")]//text()')).strip() or self.regStr(r"((?:19|20)\d{2})", html).strip()
        area = "".join(tree.xpath('//*[contains(text(),"地区")]/following-sibling::*[1]//text()')).strip()
        vtype = "".join(tree.xpath('//*[contains(text(),"类型")]/following-sibling::*[1]//text()')).strip()
        des = "".join(tree.xpath('//*[contains(@class,"detail-content") or contains(@class,"vod-content")]//text()')).strip()[:2000]
        tabs = [t.strip() for t in tree.xpath('//*[contains(@class,"module-tab-item")]/span/text() | //*[contains(@class,"module-tab-item")]/text()') if t.strip()]
        lists = tree.xpath('//*[contains(@class,"module-play-list")]') or tree.xpath('//*[contains(@class,"play-list")]')
        fro, purl = [], []
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
                fro.append(tabs[i] if i < len(tabs) else "线路" + str(i + 1))
                purl.append("#".join(eps))
        if not purl:
            eps = []
            for a in tree.xpath('//a[contains(@href,"/vod/play") or contains(@href,"/vodplay")]'):
                try:
                    t = "".join(a.xpath(".//text()")).strip()
                    h = self._fix(a.get("href", "") or "")
                    if t and h:
                        eps.append(t + "$" + h)
                except Exception:
                    continue
            if eps:
                fro, purl = [tabs[0] if tabs else "播放"], ["#".join(eps)]
        # 反爬兜底：没有任何播放源且名称是站点名/无具体信息 → 判定为导航/拦截页
        site_names = ("蛋蛋奇", "系统安全验证", "页面访问验证", "网站提示")
        if not purl and not des and name.strip() in site_names:
            return result
        vod = {"vod_id": vid, "vod_name": name, "vod_pic": self._fix(pic), "vod_actor": actor, "vod_director": director, "vod_year": year, "vod_area": area, "vod_type": vtype, "vod_content": des, "vod_play_from": "$$$".join(fro), "vod_play_url": "$$$".join(purl)}
        result["list"].append(vod)
        return result
    def searchContent(self, key, quick, pg="1"):
        pg = int(pg or 1)
        q = quote(str(key))
        items = []
        for u in [self.host + "/index.php/vod/search.html?wd=" + q + "&page=" + str(pg), self.host + "/index.php/vod/search.html?wd=" + q, self.host + "/vodsearch/-------------.html?wd=" + q]:
            items = self._cards(self._get(u))
            if items:
                break
        return {"list": items, "page": pg}
    def searchContentPage(self, key, quick, page):
        return self.searchContent(key, quick, page)
    def _playurl(self, html):
        try:
            m = re.search(r'player_aaaa\s*=\s*\{.*?"url"\s*:\s*"((?:[^"\\]|\\.)*)"', html or "", re.S)
            if m:
                u = m.group(1).replace("\\/", "/").replace("\\u003a", ":").replace("\\u0026", "&")
                if u and u not in ("did", "null", "undefined"):
                    return u
            m = re.search(r'MacPlayerConfig\s*=\s*\{.*?player_data\s*=\s*\{.*?"url"\s*:\s*"((?:[^"\\]|\\.)*)"', html or "", re.S)
            if m:
                u = m.group(1).replace("\\/", "/")
                if u and u not in ("did", "null"):
                    return u
            m = re.search(r'player_data\s*=\s*\{.*?"url"\s*:\s*"((?:[^"\\]|\\.)*)"', html or "", re.S)
            if m:
                u = m.group(1).replace("\\/", "/")
                if u and u not in ("did", "null"):
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
            m = re.search(r'(https?[^"\' \s\\]+\.m3u8[^"\' \s\\]*)', html or "")
            if m:
                return m.group(1)
            m = re.search(r'(https?[^"\' \s\\]+\.mp4[^"\' \s\\]*)', html or "")
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
            page = self.host + "/index.php/vod/play/id/" + pid + ".html"
        html = self._get(page)
        if self._is_verify(html):
            return {"parse": 1, "url": page}
        url = self._playurl(html)
        if url and (url.startswith("http") or url.startswith("//")):
            return {"parse": 0, "url": self._fix(url), "header": {"User-Agent": self.ua, "Referer": page}}
        fr = self._iframe(html)
        if fr:
            url = self._playurl(self._get(fr))
            if url:
                return {"parse": 0, "url": self._fix(url), "header": {"User-Agent": self.ua, "Referer": fr}}
        if url and not url.startswith("http"):
            return {"parse": 0, "url": url, "header": {"User-Agent": self.ua, "Referer": page}}
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