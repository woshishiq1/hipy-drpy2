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
import time

try:
    from base.spider import Spider as SpiderBase
except ImportError:
    class SpiderBase(object):
        def getCache(self, key): return None
        def setCache(self, key, value): return "fail"
        def delCache(self, key): return "fail"


class Spider(SpiderBase):
    def __init__(self):
        super(Spider, self).__init__()
        self.siteUrl = "https://xojav.tv"
        self.tgGroup = "https://t.me/+3t5XRPPo9mlkZDRl"
        self.brandActor = "📺TG群: https://t.me/+3t5XRPPo9mlkZDRl"
        self.brandDirector = "📺ZakaTV"
        self._ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        self.options = {}

        self.ctx = ssl.create_default_context()
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE
        self.cj = http.cookiejar.CookieJar()
        self._init_opener()

        # 固化全量 14 个真实分类（纯内存静态加载，毫秒秒开）
        self.static_classes = [
            {"type_name": "中文字幕", "type_id": "chinese-subtitle"},
            {"type_name": "無碼解放", "type_id": "uncensored"},
            {"type_name": "台灣AV", "type_id": "taiwan-av"},
            {"type_name": "日本AV", "type_id": "jav"},
            {"type_name": "制服誘惑", "type_id": "uniform"},
            {"type_name": "角色劇情", "type_id": "roleplay"},
            {"type_name": "絲襪", "type_id": "pantyhose"},
            {"type_name": "直接開啪", "type_id": "sex-only"},
            {"type_name": "主奴調教", "type_id": "bdsm"},
            {"type_name": "多P群交", "type_id": "groupsex"},
            {"type_name": "進犯", "type_id": "intrusion"},
            {"type_name": "男友視角", "type_id": "pov"},
            {"type_name": "流出", "type_id": "hixxen-cam"},
            {"type_name": "女同歡愉", "type_id": "lesbian"}
        ]

    def _init_opener(self, proxy_url=None):
        handlers = [
            urllib.request.HTTPCookieProcessor(self.cj),
            urllib.request.HTTPSHandler(context=self.ctx)
        ]
        if proxy_url:
            handlers.append(urllib.request.ProxyHandler({
                "http": proxy_url,
                "https": proxy_url
            }))
        self.opener = urllib.request.build_opener(*handlers)

    def init(self, extend=""):
        if isinstance(extend, dict):
            self.options = extend
        elif extend:
            try:
                self.options = json.loads(extend)
            except Exception:
                self.options = {}
        if self.options.get("mirror"):
            self.siteUrl = self.options.get("mirror").rstrip("/")
        if self.options.get("proxy"):
            self._init_opener(self.options.get("proxy"))
        return True

    def getName(self):
        return "XOJAV"

    def isVideoFormat(self, url):
        low = (url or "").lower()
        return any(k in low for k in (".m3u8", ".mp4", ".flv", ".mkv", ".avi", ".ts", ".mpd"))

    def manualVideoCheck(self):
        return False

    def _fetch(self, target_url, referer="", is_ajax=False):
        if not target_url:
            return {"code": 0, "text": "", "err": "", "raw": b""}
        if target_url.startswith("/"):
            target_url = self.siteUrl + target_url

        parsed = urllib.parse.urlparse(target_url)
        headers = {
            "User-Agent": self._ua,
            "Referer": referer if referer else (self.siteUrl + "/"),
            "Origin": self.siteUrl,
            "Host": parsed.netloc,
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "close"
        }
        if is_ajax:
            headers["X-Requested-With"] = "XMLHttpRequest"

        try:
            req = urllib.request.Request(target_url, headers=headers)
            with self.opener.open(req, timeout=8) as resp:
                code = resp.getcode()
                raw = resp.read()
                if raw.startswith(b"\x1f\x8b"):
                    raw = gzip.decompress(raw)
                elif getattr(resp, "headers", {}).get("Content-Encoding") == "deflate":
                    try:
                        raw = zlib.decompress(raw)
                    except Exception:
                        raw = zlib.decompress(raw, -zlib.MAX_WBITS)
                try:
                    text = raw.decode("utf-8")
                except Exception:
                    text = raw.decode("latin1", errors="ignore")
                return {"code": code, "text": text, "err": "", "raw": raw}
        except urllib.error.HTTPError as e:
            return {"code": e.code, "text": "", "err": "HTTP %s" % e.code, "raw": b""}
        except Exception as e:
            return {"code": -1, "text": "", "err": str(e), "raw": b""}

    # 1. 首页：纯内存零网络秒开
    def homeContent(self, filter):
        result = {"class": self.static_classes}
        if filter:
            result["filters"] = {}
        return result

    def homeVideoContent(self):
        return {"list": []}

    # 列表卡片提取（击穿懒加载真实图片，杜绝占位图）
    def _parse_items(self, html_text):
        items = []
        if '/videos/' not in html_text:
            return items

        chunks = html_text.split('/videos/')[1:]
        for chunk in chunks:
            m_vid = re.search(r'^([a-zA-Z0-9_\-]+)', chunk)
            if not m_vid:
                continue
            vid = m_vid.group(1).strip()
            if not vid or vid in ("category", "categories", "tag", "search"):
                continue

            # 标题提取
            m_alt = re.search(r'alt=["\']([^"\']+)["\']', chunk)
            if m_alt and m_alt.group(1).strip():
                name = m_alt.group(1).strip()
            else:
                m_title = re.search(r'class=["\']card-video__title["\'][^>]*>[\s\S]*?<a[^>]*>([\s\S]*?)</a>', chunk, re.I)
                name = re.sub(r'<[^>]+>', '', m_title.group(1)).strip() if m_title else vid

            # 懒加载真实海报穿透提取
            m_pic = re.search(r'data-src=["\']([^"\']+)["\']', chunk, re.I)
            if m_pic:
                pic = m_pic.group(1).strip()
            else:
                m_src = re.search(r'src=["\']([^"\']+)["\']', chunk, re.I)
                pic = m_src.group(1).strip() if m_src else ""

            if pic.startswith("//"):
                pic = "https:" + pic
            elif pic.startswith("/"):
                pic = self.siteUrl + pic

            # 时长
            m_dur = re.search(r'class=["\']card-video__duration["\'][^>]*>([\s\S]*?)</figcaption>', chunk, re.I)
            remarks = re.sub(r'<[^>]+>', '', m_dur.group(1)).strip() if m_dur else "HD"

            if any(it["vod_id"] == "vod/" + vid for it in items):
                continue

            items.append({
                "vod_id": "vod/" + vid,
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": remarks,
                "style": {"type": "rect", "ratio": 1.78}
            })
        return items

    # 2. 分类列表页：采用浏览器真实请求的 function=get_block 异步协议与时间戳机制
    def categoryContent(self, tid, pg, filter, extend):
        del filter, extend
        slug = str(tid).strip("/")
        p = int(pg) if str(pg).isdigit() else 1

        # 第一页直接访问页面标准 URL；第二页及以上采用抓包完全一致的真实参数
        if p <= 1:
            req_url = "%s/categories/%s/" % (self.siteUrl, slug)
            res = self._fetch(req_url)
        else:
            ts = int(time.time() * 1000)
            req_url = (
                "%s/categories/%s/?mode=async&function=get_block"
                "&block_id=list_videos_common_videos_list"
                "&sort_by=release_at&from=%s&_=%s"
            ) % (self.siteUrl, slug, p, ts)
            referer_url = "%s/categories/%s/" % (self.siteUrl, slug)
            res = self._fetch(req_url, referer=referer_url, is_ajax=True)

        html_text = res.get("text", "")
        items = self._parse_items(html_text)

        # 契约安全：数据为空时必须返回 1，防止死锁
        if not items:
            return {"page": p, "pagecount": 1, "limit": 0, "total": 0, "list": []}

        # 放开总页数供 TVBox 无限上拉加载
        pagecount = 465

        return {
            "page": p,
            "pagecount": pagecount,
            "limit": len(items),
            "total": pagecount * len(items),
            "list": items
        }

    # 3. 详情页：智能提取直链与节点健康探活
    def detailContent(self, ids):
        raw_id = ids[0] if isinstance(ids, (list, tuple)) else str(ids)
        vid = raw_id.replace("vod/", "").strip("/")

        detail_url = "%s/videos/%s" % (self.siteUrl, vid)
        res = self._fetch(detail_url)
        html_text = res.get("text", "")

        m_title = re.search(r'<h1[^>]*>([\s\S]*?)</h1>', html_text, re.I)
        title = re.sub(r'<[^>]+>', '', m_title.group(1)).strip() if m_title else vid

        m_pic = re.search(r'property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html_text, re.I)
        pic = m_pic.group(1).strip() if m_pic else ""

        # 提取动态 stream 直链
        m_stream = re.search(r"var\s+stream\s*=\s*['\"]([^'\"]+)['\"]", html_text)
        stream_url = m_stream.group(1).strip() if m_stream else ""

        node_host = urllib.parse.urlparse(stream_url).netloc if stream_url else "未知节点"

        # 毫秒级预检节点存活状态
        is_alive = False
        if stream_url:
            chk = self._fetch(stream_url, referer=self.siteUrl + "/")
            is_alive = (chk.get("code") == 200)

        # 选集挂载
        if is_alive:
            play_from = "XOJAV原画"
            play_url = "正片$%s" % stream_url
            node_tip = "🟢 节点正常，秒开起播"
        else:
            play_from = "XOJAV(节点异常)"
            play_url = "源站证书故障(换一部)$%s" % stream_url
            node_tip = "🔴 存储节点(%s)源站证书故障(Error 526)，站方修复前请选其它影片" % node_host

        desc_content = (
            "【🔥 官方交流群: %s】\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "• 影片番号: %s\n"
            "• 存储节点: %s\n"
            "• 节点状态: %s\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "• 播放模式: 零嗅探纯直链极速交付\n"
            "• 提示: 遇正常节点视频秒开；遇故障节点请更换其他影片观看。"
        ) % (self.tgGroup, vid, node_host, node_tip)

        escaped_desc = desc_content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        return {
            "list": [{
                "vod_id": raw_id,
                "vod_name": title,
                "vod_pic": pic,
                "vod_actor": self.brandActor,
                "vod_director": self.brandDirector,
                "vod_remarks": "1080P/HD",
                "vod_content": escaped_desc,
                "vod_play_from": play_from,
                "vod_play_url": play_url
            }]
        }

    # 4. 播放器：注入防盗链白名单 Header
    def playerContent(self, flag, id, vipFlags):
        url = str(id).strip()
        parsed = urllib.parse.urlparse(url)
        headers = {
            "User-Agent": self._ua,
            "Referer": self.siteUrl + "/",
            "Origin": self.siteUrl,
            "Host": parsed.netloc,
            "Accept": "*/*"
        }
        return {
            "parse": 0,
            "jx": 0,
            "url": url,
            "header": headers
        }

    # 5. 搜索：对齐真实异步搜索协议
    def searchContent(self, key, quick, pg="1"):
        p = int(pg) if str(pg).isdigit() else 1
        query = urllib.parse.quote(str(key).strip())

        if p <= 1:
            search_url = "%s/search/?q=%s" % (self.siteUrl, query)
            res = self._fetch(search_url)
        else:
            ts = int(time.time() * 1000)
            search_url = (
                "%s/search/?mode=async&function=get_block"
                "&block_id=list_videos_common_videos_list"
                "&q=%s&sort_by=release_at&from=%s&_=%s"
            ) % (self.siteUrl, query, p, ts)
            referer_url = "%s/search/?q=%s" % (self.siteUrl, query)
            res = self._fetch(search_url, referer=referer_url, is_ajax=True)

        html_text = res.get("text", "")
        items = self._parse_items(html_text)

        if not items:
            return {"page": p, "pagecount": 1, "limit": 0, "total": 0, "list": []}

        return {
            "page": p,
            "pagecount": 50,
            "limit": len(items),
            "total": 50 * len(items),
            "list": items
        }

    def action(self, action):
        return {"msg": "XOJAV生产级蜘蛛运行正常"}

    def liveContent(self):
        return ""

    def localProxy(self, params):
        return [404, "text/plain; charset=utf-8", "Proxy not configured"]

    def destroy(self):
        self.options = {}