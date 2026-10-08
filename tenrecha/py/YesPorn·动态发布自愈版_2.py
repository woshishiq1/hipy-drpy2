#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import re
import json
import base64
import html as html_lib
import urllib.request
import urllib.parse
import http.cookiejar
import gzip
import zlib
import ssl

try:
    from base.spider import Spider as SpiderBase
except ImportError:
    class SpiderBase(object):
        def getCache(self, key): return None
        def setCache(self, key, value): "fail"
        def delCache(self, key): "fail"

class Spider(SpiderBase):
    def __init__(self):
        super(Spider, self).__init__()
        # 发布导航站双活入口与默认兜底主站
        self.navUrls = ["https://x99dh.cc", "https://x99dh.one"]
        self.defaultHost = "https://cn.yesporn.ws"
        self.siteUrl = self.defaultHost
        self.baseHost = self.defaultHost
        self.siteName = "YesPorn"
        self.tgGroup = "https://t.me/+3t5XRPPo9mlkZDRl"
        self.brandActor = "📺TG群: https://t.me/+3t5XRPPo9mlkZDRl"
        self.brandDirector = "📺ZakaTV"
        self._ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        self.options = {}

        self.ctx = ssl.create_default_context()
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE

        self.cj = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cj),
            urllib.request.HTTPSHandler(context=self.ctx)
        )

    def init(self, extend=""):
        if isinstance(extend, dict):
            self.options = extend
        elif extend:
            try:
                self.options = json.loads(extend)
            except Exception:
                self.options = {}

        # 启动优先从本地持久化缓存读取最新解析到的有效主站
        cached_site = self.getCache("yesporn_dynamic_site_url")
        if cached_site and cached_site.startswith("http"):
            self.baseHost = cached_site.strip().rstrip("/")
            self.siteUrl = self.baseHost
        else:
            self._refresh_site_url()
        return True

    def getName(self):
        return "YesPorn·动态发布自愈版"

    def isVideoFormat(self, url):
        low = (url or "").lower()
        return any(k in low for k in (".m3u8", ".mp4", ".flv", ".mkv", ".avi", ".ts", ".mpd", "index.png"))

    def manualVideoCheck(self):
        return False

    # 核心：复用 X99 导航站 Base64+URL二次反解与矩阵探测引擎，精准提取 YesPorn
    def _refresh_site_url(self):
        headers = {
            "User-Agent": self._ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate"
        }

        for nav in self.navUrls:
            text = ""
            try:
                req = urllib.request.Request(nav, headers=headers)
                with self.opener.open(req, timeout=8) as resp:
                    raw = resp.read()
                    enc = getattr(resp, "headers", {}).get("Content-Encoding", "")
                    if raw.startswith(b"\x1f\x8b") or enc == "gzip":
                        raw = gzip.decompress(raw)
                    text = raw.decode("utf-8", errors="ignore")
            except urllib.error.HTTPError as e:
                try:
                    raw = e.read()
                    if raw.startswith(b"\x1f\x8b"):
                        raw = gzip.decompress(raw)
                    text = raw.decode("utf-8", errors="ignore")
                except Exception:
                    text = ""
            except Exception:
                continue

            if not text:
                continue

            # 扫描并反解页面内嵌入的长 Base64 数据块
            b64_blocks = re.findall(r'["\']([A-Za-z0-9+/=]{100,})["\']', text)
            for b in b64_blocks:
                try:
                    decoded = base64.b64decode(b).decode("utf-8", errors="ignore")
                    unquoted = urllib.parse.unquote(decoded)
                    if "[" in unquoted and self.siteName.lower() in unquoted.lower():
                        site_list = json.loads(unquoted)
                        for item in site_list:
                            name = item.get("name", "").strip().lower()
                            if name == self.siteName.lower():
                                cand_urls = []
                                main_url = item.get("url", "")
                                if main_url:
                                    cand_urls.append(main_url)
                                for u_obj in item.get("urls", []):
                                    u = u_obj.get("url", "")
                                    if u and u not in cand_urls:
                                        cand_urls.append(u)

                                # 提取根域名并发送轻量验活
                                for c_url in cand_urls:
                                    parsed = urllib.parse.urlparse(c_url)
                                    base = "%s://%s" % (parsed.scheme, parsed.netloc)
                                    chk = self._fetch(base + "/latest-updates/", check_host=False)
                                    if chk.get("code") == 200:
                                        self.baseHost = base
                                        self.siteUrl = base
                                        self.setCache("yesporn_dynamic_site_url", base)
                                        return True
                except Exception:
                    continue

        return False

    def _fetch(self, target_url, referer="", check_host=True):
        if not target_url:
            return {"code": 0, "text": "", "err": "", "final_url": ""}
        if target_url.startswith("//"):
            target_url = "https:" + target_url
        elif target_url.startswith("/"):
            target_url = self.baseHost + target_url

        headers = {
            "User-Agent": self._ua,
            "Referer": referer if referer else (self.baseHost + "/"),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }

        last_err = ""
        domain_retried = False

        for attempt in range(2):
            try:
                req = urllib.request.Request(target_url, headers=headers)
                with self.opener.open(req, timeout=15) as resp:
                    code = resp.getcode()
                    final_url = resp.geturl()
                    raw = resp.read()
                    enc = getattr(resp, "headers", {}).get("Content-Encoding", "")
                    if raw.startswith(b"\x1f\x8b") or enc == "gzip":
                        raw = gzip.decompress(raw)
                    elif enc == "deflate":
                        try:
                            raw = zlib.decompress(raw)
                        except Exception:
                            raw = zlib.decompress(raw, -zlib.MAX_WBITS)
                    try:
                        text = raw.decode("utf-8")
                    except Exception:
                        text = raw.decode("latin1", errors="ignore")
                    return {"code": code, "text": text, "err": "", "final_url": final_url}
            except urllib.error.HTTPError as e:
                last_err = "HTTP %s" % e.code
                if e.code in (404, 451, 502, 503) and check_host and not domain_retried:
                    old_host = urllib.parse.urlparse(self.baseHost).netloc
                    self.delCache("yesporn_dynamic_site_url")
                    if self._refresh_site_url():
                        domain_retried = True
                        new_host = urllib.parse.urlparse(self.baseHost).netloc
                        target_url = target_url.replace(old_host, new_host)
                        continue
                if e.code in (451, 403, 429) and attempt == 0:
                    continue
                err_raw = ""
                try:
                    err_raw = e.read().decode("utf-8", errors="ignore")
                except Exception:
                    pass
                return {"code": e.code, "text": err_raw, "err": str(e), "final_url": target_url}
            except Exception as e:
                last_err = str(e)
                if check_host and not domain_retried:
                    old_host = urllib.parse.urlparse(self.baseHost).netloc
                    self.delCache("yesporn_dynamic_site_url")
                    if self._refresh_site_url():
                        domain_retried = True
                        new_host = urllib.parse.urlparse(self.baseHost).netloc
                        target_url = target_url.replace(old_host, new_host)
                        continue
                if attempt == 0:
                    continue
                return {"code": -1, "text": "", "err": str(e), "final_url": target_url}

        return {"code": -1, "text": "", "err": last_err, "final_url": target_url}

    # 1. 首页：纯内存静态组装
    def homeContent(self, filter):
        result = {
            "class": [
                {"type_name": "🔥最新更新", "type_id": "/latest-updates/"},
                {"type_name": "⭐最高评分", "type_id": "/top-rated/"},
                {"type_name": "👀最受欢迎", "type_id": "/most-popular/"},
                {"type_name": "👑Reality Kings", "type_id": "/channels/realitykings-x0njpa/"},
                {"type_name": "🔞Bangbros", "type_id": "/channels/bangbros-x0njpa/"},
                {"type_name": "💎Pure Taboo", "type_id": "/channels/puretaboo-g7g6z5/"}
            ]
        }
        if filter:
            result["filters"] = {}
        return result

    def homeVideoContent(self):
        res = self.categoryContent("/latest-updates/", "1", False, {})
        return {"list": res.get("list", [])}

    # 2. 分类列表：容器作用域精准切片提取
    def categoryContent(self, tid, pg, filter, extend):
        del filter
        extend = extend if isinstance(extend, dict) else {}
        route = str(tid).strip()
        page_int = int(pg) if str(pg).isdigit() else 1

        clean_route = route.rstrip("/")
        if page_int > 1:
            req_url = "%s%s/%d/" % (self.baseHost, clean_route, page_int)
        else:
            req_url = "%s%s/" % (self.baseHost, clean_route)

        res = self._fetch(req_url)
        html_text = res.get("text", "")
        if not html_text:
            return {"page": page_int, "pagecount": 1, "limit": 0, "total": 0, "list": []}

        blocks = html_text.split('class="thumb thumb_rel item')
        vod_list = []

        for blk in blocks[1:]:
            href_m = re.search(r'href=["\']([^"\']+/video/(\d+)/[^"\']*)["\']', blk, re.I)
            title_m = re.search(r'title=["\']([^"\']+)["\']', blk, re.I)
            img_m = re.search(r'(?:data-webp|data-original)=["\']([^"\']+)["\']', blk, re.I)
            duration_m = re.search(r'class=["\']item-time[^"\']*["\'][^>]*>([\s\S]*?)</div>', blk, re.I)

            if href_m and title_m:
                vod_url = href_m.group(1).strip()
                vid = href_m.group(2).strip()
                title = title_m.group(1).strip()
                pic = img_m.group(1).strip() if img_m else ""
                
                remarks = ""
                if duration_m:
                    remarks = re.sub(r'<[^>]+>', '', duration_m.group(1)).strip()

                v_identifier = "%s|%s" % (vod_url, vid)

                vod_list.append({
                    "vod_id": v_identifier,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": remarks,
                    "style": {"type": "rect", "ratio": 1.78}
                })

        page_count = page_int + 1 if len(vod_list) >= 20 else page_int
        if page_count < 1:
            page_count = 1

        return {
            "page": page_int,
            "pagecount": page_count,
            "limit": len(vod_list),
            "total": 9999,
            "list": vod_list
        }

    # 3. 详情页：直接挂接 Embed 独立内核播放直通线
    def detailContent(self, ids):
        raw_id = ids[0] if isinstance(ids, (list, tuple)) else str(ids)
        target_token = str(raw_id).strip()

        if "|" in target_token:
            parts = target_token.split("|")
            target_url = parts[0]
            vid = parts[1]
        else:
            target_url = target_token
            vid_m = re.search(r'/video/(\d+)/', target_url)
            vid = vid_m.group(1) if vid_m else ""

        res = self._fetch(target_url)
        html_text = res.get("text", "")
        if not html_text:
            return {"list": []}

        title_m = re.search(r'<h1[^>]*>([\s\S]*?)</h1>', html_text, re.I)
        vod_name = re.sub(r'<[^>]+>', '', title_m.group(1)).strip() if title_m else ""
        if not vod_name:
            t_m = re.search(r'<title>(.*?)</title>', html_text, re.I)
            vod_name = t_m.group(1).split("-")[0].strip() if t_m else "精彩视频"

        pic_m = re.search(r'poster\s*:\s*[\'"]([^\'"]+)[\'"]', html_text, re.I)
        if not pic_m:
            pic_m = re.search(r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)["\']', html_text, re.I)
        vod_pic = pic_m.group(1).strip() if pic_m else ""

        intro_desc = (
            "【📺官方交流群: %s】\n"
            "【当前发布域名: %s】\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "温馨提示：若播放卡顿或加载较慢，请尝试切换代理节点。\n"
            "影片标题：%s"
        ) % (self.tgGroup, self.baseHost, vod_name)
        escaped_desc = intro_desc.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        if vid:
            embed_play_url = "%s/embed/%s" % (self.baseHost, vid)
        else:
            embed_play_url = target_url

        play_str = "正片高清$%s" % embed_play_url

        return {
            "list": [{
                "vod_id": target_token,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_actor": self.brandActor,
                "vod_director": self.brandDirector,
                "vod_remarks": "HD高清",
                "vod_content": escaped_desc,
                "vod_play_from": "Zaka专线",
                "vod_play_url": play_str
            }]
        }

    # 4. 播放器：parse=1 启动 TVBox 原生嗅探器精准拦截动态正片流
    def playerContent(self, flag, id, vipFlags):
        headers = {
            "User-Agent": self._ua,
            "Referer": self.baseHost + "/",
            "Accept": "*/*"
        }
        return {
            "parse": 1,
            "jx": 0,
            "url": str(id).strip(),
            "header": headers
        }

    # 5. 搜索功能
    def searchContent(self, key, quick, pg="1"):
        page_int = int(pg) if str(pg).isdigit() else 1
        encoded_key = urllib.parse.quote(key)
        
        if page_int > 1:
            search_url = "%s/search/%s/%d/" % (self.baseHost, encoded_key, page_int)
        else:
            search_url = "%s/search/%s/" % (self.baseHost, encoded_key)

        res = self._fetch(search_url)
        html_text = res.get("text", "")
        if not html_text:
            return {"page": page_int, "pagecount": 1, "limit": 0, "total": 0, "list": []}

        blocks = html_text.split('class="thumb thumb_rel item')
        vod_list = []

        for blk in blocks[1:]:
            href_m = re.search(r'href=["\']([^"\']+/video/(\d+)/[^"\']*)["\']', blk, re.I)
            title_m = re.search(r'title=["\']([^"\']+)["\']', blk, re.I)
            img_m = re.search(r'(?:data-webp|data-original)=["\']([^"\']+)["\']', blk, re.I)
            duration_m = re.search(r'class=["\']item-time[^"\']*["\'][^>]*>([\s\S]*?)</div>', blk, re.I)

            if href_m and title_m:
                vod_url = href_m.group(1).strip()
                vid = href_m.group(2).strip()
                title = title_m.group(1).strip()
                pic = img_m.group(1).strip() if img_m else ""
                
                remarks = ""
                if duration_m:
                    remarks = re.sub(r'<[^>]+>', '', duration_m.group(1)).strip()

                v_identifier = "%s|%s" % (vod_url, vid)

                vod_list.append({
                    "vod_id": v_identifier,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": remarks,
                    "style": {"type": "rect", "ratio": 1.78}
                })

        return {
            "page": page_int,
            "pagecount": page_int + 1 if len(vod_list) >= 20 else page_int,
            "limit": len(vod_list),
            "total": 9999,
            "list": vod_list
        }

    def action(self, action):
        if action == "toast":
            return {"msg": "当前有效主站: %s" % self.baseHost}
        return {"msg": "YesPorn生产蜘蛛运行正常"}

    def liveContent(self):
        return ""

    def localProxy(self, params):
        return [404, "text/plain; charset=utf-8", "Proxy not configured"]

    def destroy(self):
        self.options = {}