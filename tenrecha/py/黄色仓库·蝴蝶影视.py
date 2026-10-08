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
from urllib.parse import quote, unquote
import http.cookiejar
import gzip
import zlib
import ssl

try:
    from base.spider import Spider as SpiderBase
except ImportError:
    class SpiderBase(object):
        def __init__(self):
            self.extend = ""

        def getCache(self, key):
            return None

        def setCache(self, key, value):
            return "fail"

        def delCache(self, key):
            return "fail"


def clean_html_text(raw_html):
    txt = re.sub(r"<[^>]*>", "", raw_html or "")
    txt = html_lib.unescape(txt)
    return re.sub(r"[\r\n\t\s]+", " ", txt).strip()


def format_remarks(brand="蝴蝶影视", meta=""):
    clean_meta = str(meta or "").strip()
    clean_meta = re.sub(r"[\r\n\t]+", " ", clean_meta).strip()
    if clean_meta:
        if any(k in clean_meta for k in ("部", "集", "话")):
            return "%s · %s" % (brand, clean_meta)
        return "%s | %s" % (brand, clean_meta)
    return brand


class Spider(SpiderBase):
    def __init__(self):
        super(Spider, self).__init__()
        self.defaultHost = "https://www.69ck.nl"
        self.baseHost = self.defaultHost
        self.navUrls = ["https://x99dh.cc", "https://x99dh.one"]
        self.targetSiteNames = ["黄色仓库", "hsck", "69ck"]
        self.tgGroup = "https://t.me/tvshare23"
        self.brandActor = "🦋 TG群: @tvshare23"
        self.brandDirector = "蝴蝶影视"
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

        self.categories = [
            {"type_id": "麻豆", "type_name": "麻豆传媒"},
            {"type_id": "91制片厂", "type_name": "91制片厂"},
            {"type_id": "蜜桃影像", "type_name": "蜜桃影像"},
            {"type_id": "果冻传媒", "type_name": "果冻传媒"},
            {"type_id": "星空无限", "type_name": "星空无限"},
            {"type_id": "天美传媒", "type_name": "天美传媒"},
            {"type_id": "精东影业", "type_name": "精东影业"},
            {"type_id": "皇家华人", "type_name": "皇家华人"},
            {"type_id": "糖心Vlog", "type_name": "糖心Vlog"},
            {"type_id": "萝莉社", "type_name": "萝莉社"},
            {"type_id": "性视界", "type_name": "性视界传媒"},
            {"type_id": "草霉视频", "type_name": "草霉视频"},
            {"type_id": "玩偶姐姐", "type_name": "玩偶姐姐"},
            {"type_id": "爱豆传媒", "type_name": "爱豆传媒"},
            {"type_id": "91茄子", "type_name": "91茄子"},
            {"type_id": "扣扣传媒", "type_name": "扣扣传媒"},
            {"type_id": "SA国际传媒", "type_name": "SA国际传媒"},
            {"type_id": "杏吧", "type_name": "杏吧原创"},
            {"type_id": "大象传媒", "type_name": "大象传媒"},
            {"type_id": "乌托邦", "type_name": "乌托邦"},
            {"type_id": "69传媒", "type_name": "69传媒"},
            {"type_id": "成人头条", "type_name": "成人头条"},
            {"type_id": "乌鸦传媒", "type_name": "乌鸦传媒"},
            {"type_id": "香蕉视频", "type_name": "香蕉视频"}
        ]

    def init(self, extend=""):
        if isinstance(extend, dict):
            self.options = extend
        elif extend:
            try:
                self.options = json.loads(extend)
            except Exception:
                self.options = {}

        ext_host = self.options.get("siteUrl") or self.options.get("host")
        if ext_host:
            self.defaultHost = ext_host.rstrip("/")

        self._get_active_host()
        return True

    def getName(self):
        return "黄色仓库·蝴蝶影视"

    def isVideoFormat(self, url):
        low = (url or "").lower()
        return any(k in low for k in (".m3u8", ".mp4", ".flv", ".mkv", ".avi", ".ts", ".mpd", "index.png"))

    def manualVideoCheck(self):
        return False

    def _resolve_nav_sites(self):
        headers = {
            "User-Agent": self._ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate"
        }

        for nav in self.navUrls:
            try:
                req = urllib.request.Request(nav, headers=headers)
                with self.opener.open(req, timeout=8) as resp:
                    raw = resp.read()
                    enc = getattr(resp, "headers", {}).get("Content-Encoding", "")
                    if raw.startswith(b"\x1f\x8b") or enc == "gzip":
                        raw = gzip.decompress(raw)
                    elif enc == "deflate":
                        try:
                            raw = zlib.decompress(raw)
                        except Exception:
                            raw = zlib.decompress(raw, -zlib.MAX_WBITS)
                    text = raw.decode("utf-8", errors="ignore")
            except Exception:
                text = ""

            if not text:
                continue

            b64_blocks = re.findall(r'["\']([A-Za-z0-9+/=]{100,})["\']', text)
            for b in b64_blocks:
                try:
                    decoded = base64.b64decode(b).decode("utf-8", errors="ignore")
                    unquoted = urllib.parse.unquote(decoded)
                    if any(k in unquoted for k in self.targetSiteNames) and "[" in unquoted:
                        site_list = json.loads(unquoted)
                        for item in site_list:
                            name_raw = str(item.get("name", "")).strip().lower()
                            if any(k in name_raw for k in ["黄色仓库", "hsck", "69ck"]):
                                cand_urls = []
                                main_url = item.get("url", "")
                                if main_url:
                                    cand_urls.append(main_url)
                                for u_obj in item.get("urls", []):
                                    u = u_obj.get("url", "")
                                    if u and u not in cand_urls:
                                        cand_urls.append(u)

                                for c_url in cand_urls:
                                    parsed = urllib.parse.urlparse(c_url)
                                    base = "%s://%s" % (parsed.scheme, parsed.netloc)
                                    chk = self._fetch(base + "/enter", check_host=False, timeout=5)
                                    if chk.get("code") == 200:
                                        return base
                except Exception:
                    continue

        return self.defaultHost

    def _get_active_host(self):
        cached_host = self.getCache("hsck_live_host")
        if cached_host and cached_host.startswith("http"):
            self.baseHost = cached_host
            return self.baseHost

        new_host = self._resolve_nav_sites()
        self.baseHost = new_host if new_host else self.defaultHost
        self.setCache("hsck_live_host", self.baseHost)
        return self.baseHost

    def _fetch(self, target_url, referer="", data=None, extra_headers=None, timeout=8, check_host=True):
        if not target_url:
            return {"code": 0, "text": "", "bytes": b"", "err": "", "final_url": ""}

        if target_url.startswith("//"):
            target_url = "https:" + target_url
        elif target_url.startswith("/"):
            target_url = self.baseHost + target_url

        headers = {
            "User-Agent": self._ua,
            "Referer": referer if referer else (self.baseHost + "/enter"),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive"
        }
        if extra_headers:
            headers.update(extra_headers)

        post_bytes = None
        if data is not None:
            if isinstance(data, dict):
                post_bytes = urllib.parse.urlencode(data).encode("utf-8")
            elif isinstance(data, str):
                post_bytes = data.encode("utf-8")
            else:
                post_bytes = data

        last_err = ""
        for attempt in range(2):
            try:
                req = urllib.request.Request(target_url, data=post_bytes, headers=headers)
                with self.opener.open(req, timeout=timeout) as resp:
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
                    return {"code": code, "text": text, "bytes": raw, "err": "", "final_url": final_url}
            except urllib.error.HTTPError as e:
                last_err = "HTTP %s: %s" % (e.code, e.reason)
                if e.code in (404, 451, 500, 502, 503) and check_host and attempt == 0:
                    self.delCache("hsck_live_host")
                    self._get_active_host()
                    target_url = re.sub(r"^https?://[^/]+", self.baseHost, target_url)
                    headers["Referer"] = self.baseHost + "/enter"
                    continue
                err_raw = ""
                try:
                    err_raw = e.read().decode("utf-8", errors="ignore")
                except Exception:
                    pass
                return {"code": e.code, "text": err_raw, "bytes": b"", "err": last_err, "final_url": target_url}
            except Exception as e:
                last_err = "%s: %s" % (type(e).__name__, str(e))
                if attempt == 0 and check_host:
                    self.delCache("hsck_live_host")
                    self._get_active_host()
                    target_url = re.sub(r"^https?://[^/]+", self.baseHost, target_url)
                    headers["Referer"] = self.baseHost + "/enter"
                    continue
                return {"code": -1, "text": "", "bytes": b"", "err": last_err, "final_url": target_url}

        return {"code": -1, "text": "", "bytes": b"", "err": last_err, "final_url": target_url}

    def homeContent(self, filter):
        result = {
            "class": self.categories
        }
        if filter:
            result["filters"] = {}
        return result

    def homeVideoContent(self):
        first_tid = self.categories[0]["type_id"]
        return self.categoryContent(first_tid, "1", False, {})

    def categoryContent(self, tid, pg, filter, extend):
        del filter, extend
        page_no = int(pg) if str(pg).isdigit() and int(pg) > 0 else 1
        kw = str(tid).strip()
        if not kw:
            kw = "麻豆"

        req_url = "%s/index.php/vod/search.html?wd=%s&page=%d" % (self.baseHost, quote(kw), page_no)
        res = self._fetch(req_url, referer=self.baseHost + "/enter")
        html = res.get("text", "")

        clean_scope = re.sub(r"<(?:header|nav|footer)[^>]*>[\s\S]*?</(?:header|nav|footer)>", "", html, flags=re.I)

        card_blocks = []
        for tag in ["li", "div"]:
            matches = re.findall(r"(<" + tag + r'[^>]+class=["\'][^"\']*(?:item|vod|box|video|col|card)[^"\']*["\'][^>]*>[\s\S]*?</' + tag + r">)", clean_scope, re.I)
            if len(matches) >= 4:
                card_blocks = matches
                break

        if not card_blocks:
            card_blocks = re.findall(r'(<div[^>]+class=["\'][^"\']*stui-vodlist__box[^"\']*["\'][^>]*>[\s\S]*?</div>)', clean_scope, re.I)

        vod_list = []
        seen_ids = set()

        for block in card_blocks:
            href_m = re.search(r'href=["\']([^"\']*(?:detail|play)[^"\']*)["\']', block, re.I)
            if not href_m:
                continue
            href = href_m.group(1).strip()

            id_m = re.search(r"/id/(\d+)", href)
            if not id_m:
                continue
            vid = id_m.group(1)
            if vid in seen_ids:
                continue
            seen_ids.add(vid)

            title_m = re.search(r'title=["\']([^"\']+)["\']', block, re.I)
            if not title_m:
                title_m = re.search(r'<(?:h\d|span|p|a)[^>]*class=["\'][^"\']*title[^"\']*["\'][^>]*>([\s\S]*?)</(?:h\d|span|p|a)>', block, re.I)
            if not title_m:
                title_m = re.search(r"<(?:h\d|span|p|a)[^>]*>([\s\S]*?)</(?:h\d|span|p|a)>", block, re.I)
            raw_title = clean_html_text(title_m.group(1)) if title_m else ""
            vod_name = raw_title if (raw_title and raw_title not in ("目录", "首页", "播放")) else ("视频 " + vid)

            pic_m = re.search(r'(?:data-original|data-src|data-echo|src)=["\']([^"\']+)["\']', block, re.I)
            pic = pic_m.group(1).strip() if pic_m else ""
            if pic and not pic.startswith("http"):
                pic = urllib.parse.urljoin(self.baseHost, pic)

            raw_duration = ""
            dur_m = re.search(r'(?:class=["\'][^"\']*(?:pic-text|duration|time|len|badge|label)[^"\']*["\'][^>]*>|>)\s*(\d{1,2}:\d{2}(?::\d{2})?)\s*<', block, re.I)
            if dur_m:
                raw_duration = dur_m.group(1).strip()

            if not raw_duration:
                any_time_m = re.search(r"\b(\d{1,2}:\d{2}:\d{2}|\d{1,2}:\d{2})\b", block)
                if any_time_m:
                    raw_duration = any_time_m.group(1).strip()

            if not raw_duration:
                text_tag_m = re.search(r'class=["\'][^"\']*(?:pic-text|tag|label)[^"\']*["\'][^>]*>([\s\S]*?)<', block, re.I)
                if text_tag_m:
                    tag_txt = clean_html_text(text_tag_m.group(1))
                    if 0 < len(tag_txt) <= 8 and not any(x in tag_txt for x in ("http", "www")):
                        raw_duration = tag_txt

            final_remarks = format_remarks(brand=self.brandDirector, meta=raw_duration)

            vod_list.append({
                "vod_id": vid,
                "vod_name": vod_name,
                "vod_pic": pic,
                "vod_remarks": final_remarks,
                "style": {"type": "rect", "ratio": 1.78}
            })

        has_next = len(card_blocks) >= 15
        total_pages = (page_no + 1) if has_next else page_no

        return {
            "page": page_no,
            "pagecount": total_pages,
            "limit": len(vod_list),
            "total": len(vod_list) * total_pages,
            "list": vod_list
        }

    def detailContent(self, ids):
        raw_id = ids[0] if isinstance(ids, (list, tuple)) else str(ids)
        clean_id = re.sub(r"^[a-zA-Z_]+", "", raw_id)
        if not clean_id:
            clean_id = str(raw_id)

        detail_url = "%s/index.php/vod/detail/id/%s.html" % (self.baseHost, clean_id)
        res = self._fetch(detail_url, referer=self.baseHost + "/enter")
        html = res.get("text", "")

        vod_name = ""
        meta_t_m = re.search(r"<title>([\s\S]*?)</title>", html, re.I)
        if meta_t_m:
            raw_meta_t = clean_html_text(meta_t_m.group(1))
            vod_name = re.split(r"详情介绍|在线观看|迅雷下载|-", raw_meta_t)[0].strip()

        if not vod_name or vod_name in ("目录", "首页", "播放"):
            h_tags = re.findall(r"<(?:h1|h2|h3)[^>]*>([\s\S]*?)</(?:h1|h2|h3)>", html, re.I)
            for ht in h_tags:
                clean_h = clean_html_text(ht)
                if clean_h and clean_h not in ("目录", "首页", "播放") and "喜欢看" not in clean_h and "播放器" not in clean_h:
                    vod_name = clean_h
                    break

        if not vod_name:
            vod_name = "视频 " + clean_id

        pic_m = re.search(r'(?:data-original|data-src|src)=["\']([^"\']+\.(?:png|jpg|webp)[^"\']*)["\']', html, re.I)
        vod_pic = pic_m.group(1) if pic_m else ""
        if vod_pic and not vod_pic.startswith("http"):
            vod_pic = urllib.parse.urljoin(self.baseHost, vod_pic)

        play_links = re.findall(r'<a[^>]+href=["\']([^"\']*(?:/vod/play/[^"\']+))["\'][^>]*>([\s\S]*?)</a>', html, re.I)
        play_routes = []
        if play_links:
            for pl_h, pl_t in play_links:
                c_name = clean_html_text(pl_t) or "正片"
                c_name = c_name.replace("$", "").replace("#", "")
                c_url = pl_h.strip()
                if not c_url.startswith("http"):
                    c_url = self.baseHost + c_url
                play_routes.append("%s$%s" % (c_name, c_url))
        else:
            auto_play_url = "%s/index.php/vod/play/id/%s/sid/1/nid/1.html" % (self.baseHost, clean_id)
            play_routes.append("正片$%s" % auto_play_url)

        ep_meta = "%d集全" % len(play_routes) if len(play_routes) > 1 else "正片"
        detail_remarks = format_remarks(brand=self.brandDirector, meta=ep_meta)

        full_desc = (
            "【🔥 官方交流群: %s】\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "【当前接入节点】: %s\n"
            "【片名】: %s\n"
            "【线路说明】: 原生高清直出，智能域名动态防失联调度保活"
        ) % (self.tgGroup, self.baseHost, vod_name)

        return {
            "list": [{
                "vod_id": clean_id,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_actor": self.brandActor,
                "vod_director": self.brandDirector,
                "vod_remarks": detail_remarks,
                "vod_content": full_desc.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"),
                "vod_play_from": "蝴蝶专线",
                "vod_play_url": "#".join(play_routes)
            }]
        }

    def playerContent(self, flag, id, vipFlags):
        del flag, vipFlags
        play_url = str(id).strip()

        id_m = re.search(r"/id/(\d+)", play_url)
        vid = id_m.group(1) if id_m else ""
        sid_m = re.search(r"/sid/(\d+)", play_url)
        sid = sid_m.group(1) if sid_m else "1"
        nid_m = re.search(r"/nid/(\d+)", play_url)
        nid = nid_m.group(1) if nid_m else "1"

        ref_detail = "%s/index.php/vod/detail/id/%s.html" % (self.baseHost, vid) if vid else (self.baseHost + "/enter")

        post_data = {"id": vid, "sid": sid, "nid": nid}
        ajax_headers = {
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
        }

        res = self._fetch(play_url, referer=ref_detail, data=post_data, extra_headers=ajax_headers, timeout=6)
        html = res.get("text", "")

        real_m3u8 = ""

        if_match = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', html, re.I)
        if if_match:
            iframe_src = if_match.group(1)
            v_url_m = re.search(r"[?&]video_url=([^&\"'<>]+)", iframe_src)
            if v_url_m:
                real_m3u8 = unquote(v_url_m.group(1))

        if not real_m3u8:
            p_m = re.search(r"var\s+player_aaaa\s*=\s*(\{[\s\S]*?\});", html)
            if p_m:
                try:
                    p_dict = json.loads(p_m.group(1))
                    raw_u = p_dict.get("url", "")
                    enc = str(p_dict.get("encrypt", "0"))
                    if enc == "1":
                        real_m3u8 = unquote(raw_u)
                    elif enc == "2":
                        real_m3u8 = base64.b64decode(raw_u).decode("utf-8")
                    else:
                        real_m3u8 = raw_u
                except Exception:
                    pass

        if not real_m3u8:
            m_all = re.findall(r"https?://[^\s\"'<>]+(?:\.m3u8|/index\.m3u8)[^\s\"'<>]*", html)
            if m_all:
                real_m3u8 = m_all[0]

        if real_m3u8 and real_m3u8.startswith("//"):
            real_m3u8 = "https:" + real_m3u8

        play_headers = {
            "User-Agent": self._ua,
            "Referer": "https://player.centercdn.top/",
            "Origin": "https://player.centercdn.top"
        }

        return {
            "parse": 0,
            "playUrl": "",
            "url": real_m3u8 if real_m3u8 else play_url,
            "header": play_headers
        }

    def searchContent(self, key, quick, pg="1"):
        return self.categoryContent(key, pg, False, {})

    def action(self, action):
        return {"msg": "ok"}

    def liveContent(self):
        return ""

    def localProxy(self, params):
        return [404, "text/plain; charset=utf-8", "Proxy not configured"]

    def destroy(self):
        self.options = {}
