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
        pass


class Spider(SpiderBase):
    def __init__(self):
        super(Spider, self).__init__()
        self.siteUrl = "https://www.freepornvideos.xxx"
        self.tgGroup = "https://t.me/tvshare23"
        self.brandActor = "🦋 TG群: @tvshare23"
        self.brandDirector = "🦋 蝴蝶影视"
        self._ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"

        self.cj = http.cookiejar.CookieJar()
        self.ctx = self._create_safe_ssl_context()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cj),
            urllib.request.HTTPSHandler(context=self.ctx)
        )

    def _create_safe_ssl_context(self):
        try:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            ctx.set_ciphers('DEFAULT:!DH:!aNULL:!eNULL')
            return ctx
        except Exception:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            return ctx

    def init(self, extend=""):
        return True

    def isVideoFormat(self, url):
        low = (url or "").lower()
        return any(k in low for k in (".m3u8", ".mp4", ".flv", ".mkv", ".avi", ".ts"))

    def manualVideoCheck(self):
        return False

    def _fetch(self, target_url, referer=""):
        if not target_url:
            return {"code": 0, "text": "", "err": "URL 为空"}
        if target_url.startswith("/"):
            target_url = self.siteUrl + target_url

        headers = {
            "User-Agent": self._ua,
            "Referer": referer if referer else (self.siteUrl + "/zh/latest-updates/"),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "Connection": "close"
        }

        try:
            req = urllib.request.Request(target_url, headers=headers)
            with self.opener.open(req, timeout=15) as resp:
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
                return {"code": code, "text": text, "err": ""}
        except urllib.error.HTTPError as e:
            err_body = ""
            try:
                raw_err = e.read()
                if raw_err.startswith(b"\x1f\x8b"):
                    raw_err = gzip.decompress(raw_err)
                err_body = raw_err.decode("utf-8", errors="ignore")
            except Exception:
                pass
            return {"code": e.code, "text": err_body, "err": "HTTPError: %s" % str(e)}
        except Exception as e:
            first_err = str(e)
            try:
                fallback_ctx = ssl._create_unverified_context()
                req2 = urllib.request.Request(target_url, headers=headers)
                with urllib.request.urlopen(req2, context=fallback_ctx, timeout=15) as resp2:
                    code2 = resp2.getcode()
                    raw2 = resp2.read()
                    if raw2.startswith(b"\x1f\x8b"):
                        raw2 = gzip.decompress(raw2)
                    try:
                        text2 = raw2.decode("utf-8")
                    except Exception:
                        text2 = raw2.decode("latin1", errors="ignore")
                    return {"code": code2, "text": text2, "err": "降级成功"}
            except Exception as e2:
                return {"code": -1, "text": "", "err": "通道1: %s | 通道2: %s" % (first_err, str(e2))}

    def _unesc(self, s):
        try:
            return html_lib.unescape(s or "").strip()
        except Exception:
            return (s or "").strip()

    # 1. 首页：纯内存静态固化
    def homeContent(self, *args, **kwargs):
        return {
            "class": [
                {"type_name": "Nubiles", "type_id": "/zh/networks/nubiles-porn-com/"},
                {"type_name": "Brazzers", "type_id": "/zh/networks/brazzers-com/"},
                {"type_name": "最新视频", "type_id": "/zh/latest-updates/"},
                {"type_name": "最佳视频", "type_id": "/zh/top-rated/"},
                {"type_name": "热门影片", "type_id": "/zh/most-popular/"},
                {"type_name": "MYLF", "type_id": "/zh/networks/mylf-com/"}
            ]
        }

    # 2. 分类列表页：保持原跑通逻辑完全不动
    def categoryContent(self, tid, pg, *args, **kwargs):
        slug = str(tid).strip()
        page_idx = int(pg) if str(pg).isdigit() and int(pg) > 0 else 1

        if not slug.startswith("/"):
            slug = "/" + slug
        if not slug.endswith("/"):
            slug = slug + "/"

        if page_idx > 1:
            req_url = "%s%s/" % (slug, page_idx)
        else:
            req_url = slug

        res = self._fetch(req_url)
        html_text = res.get("text", "")

        item_blocks = re.findall(r'(<a[^>]+href=["\'][^"\']*/videos/[^"\']+["\'][^>]*>[\s\S]*?</a>)', html_text, re.I)

        cards = []
        seen_urls = set()

        for blk in item_blocks:
            href_m = re.search(r'href=["\']([^"\']+)["\']', blk, re.I)
            if not href_m:
                continue
            raw_href = href_m.group(1).split("?")[0].strip()

            if not raw_href.startswith("http"):
                if not raw_href.startswith("/"):
                    raw_href = "/" + raw_href
            else:
                raw_href = raw_href.replace(self.siteUrl, "")

            if raw_href in seen_urls:
                continue

            title = ""
            t_m = re.search(r'title=["\']([^"\']+)["\']', blk, re.I)
            if t_m:
                title = t_m.group(1).strip()
            if not title:
                alt_m = re.search(r'alt=["\']([^"\']+)["\']', blk, re.I)
                if alt_m:
                    title = alt_m.group(1).strip()
            if not title:
                clean_inner = re.sub(r'<[^>]+>', '', blk).strip()
                if clean_inner:
                    title = clean_inner.split("\n")[0].strip()

            pic_url = ""
            for attr in ("data-src", "data-original", "data-webp", "src"):
                pic_m = re.search(r'%s=["\']([^"\']+)["\']' % attr, blk, re.I)
                if pic_m:
                    val = pic_m.group(1).strip()
                    if val and not val.startswith("data:"):
                        pic_url = val
                        break

            if pic_url.startswith("//"):
                pic_url = "https:" + pic_url
            elif pic_url.startswith("/"):
                pic_url = self.siteUrl + pic_url

            duration = ""
            dur_m = re.search(r'class=["\'][^"\']*duration[^"\']*["\'][^>]*>([^<]+)</span>', blk, re.I)
            if dur_m:
                duration = dur_m.group(1).strip()

            if title and pic_url:
                seen_urls.add(raw_href)
                safe_vid = "v_" + base64.urlsafe_b64encode(raw_href.encode("utf-8")).decode("utf-8").rstrip("=")
                cards.append({
                    "vod_id": safe_vid,
                    "vod_name": title,
                    "vod_pic": pic_url,
                    "vod_remarks": duration if duration else "高清"
                })

        return {
            "page": page_idx,
            "pagecount": 999,
            "limit": len(cards),
            "total": 9999,
            "list": cards
        }

    # 3. 详情页：精准提取 videojs 初始化配置与多清晰度直链
    def detailContent(self, ids):
        raw_id = ids[0] if isinstance(ids, (list, tuple)) else str(ids)

        detail_url = ""
        if str(raw_id).startswith("v_"):
            try:
                b64_str = raw_id[2:]
                pad = len(b64_str) % 4
                if pad:
                    b64_str += "=" * (4 - pad)
                detail_url = base64.urlsafe_b64decode(b64_str.encode("utf-8")).decode("utf-8")
            except Exception:
                detail_url = str(raw_id)
        else:
            detail_url = str(raw_id)

        target_req_url = detail_url
        if target_req_url.startswith("/"):
            target_req_url = self.siteUrl + target_req_url

        res = self._fetch(target_req_url, referer=self.siteUrl + "/zh/latest-updates/")
        html_text = res.get("text", "")

        # 1. 标题提取
        t_match = re.search(r'<title>(.*?)</title>', html_text, re.I)
        raw_title = t_match.group(1) if t_match else "精选视频"
        vod_name = self._unesc(re.sub(r'\s*-\s*FreePornVideos.*', '', raw_title).strip())

        # 2. 封面提取
        pic_m = re.search(r'poster=["\']([^"\']+)["\']', html_text, re.I)
        if not pic_m:
            pic_m = re.search(r'property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html_text, re.I)
        vod_pic = pic_m.group(1).strip() if pic_m else ""

        # 3. 核心：解析直链（针对 video.js / HTML5 标签 / 内联 JS）
        media_sources = []
        seen_urls = set()

        def add_stream(label, u):
            clean_u = u.replace('\\/', '/').strip()
            if clean_u.startswith("//"):
                clean_u = "https:" + clean_u
            # 过滤掉预览图或明显非视频
            if clean_u and clean_u not in seen_urls and not clean_u.endswith((".jpg", ".png", ".jpeg", ".webp")):
                seen_urls.add(clean_u)
                media_sources.append((label, clean_u))

        # 模式 A: <source src="..." label="..."> 标签
        for s_blk in re.findall(r'<source[^>]+>', html_text, re.I):
            u_m = re.search(r'src=["\']([^"\']+)["\']', s_blk, re.I)
            if u_m:
                lbl_m = re.search(r'(?:title|res|label)=["\']([^"\']+)["\']', s_blk, re.I)
                lbl = lbl_m.group(1) if lbl_m else "直链"
                add_stream(lbl, u_m.group(1))

        # 模式 B: JS 中初始化的 video_url / video_alt_url / sources 数组
        # 兼容: src: 'https://...mp4', label: '720p'
        js_sources = re.findall(r'src\s*:\s*["\']([^"\']+\.(?:mp4|m3u8)[^"\']*)["\'][^}]*?(?:label|res|type)?\s*:\s*["\']?([^"\'}\s,]+)?', html_text, re.I)
        for s_url, s_lbl in js_sources:
            label = s_lbl if s_lbl and len(s_lbl) < 10 else "高清播放"
            add_stream(label, s_url)

        # 模式 C: 经典视频参数匹配
        param_matches = re.findall(r'["\']?(?:video_url|videoUrl|hlsUrl|format_\d+p|quality_\d+p)["\']?\s*[:=]\s*["\']([^"\']+\.(?:mp4|m3u8)[^"\']*)["\']', html_text, re.I)
        for p_u in param_matches:
            lbl = "在线播放"
            if "2160" in p_u or "4k" in p_u.lower():
                lbl = "4K超清"
            elif "1080" in p_u:
                lbl = "1080P"
            elif "720" in p_u:
                lbl = "720P"
            elif "480" in p_u:
                lbl = "480P"
            elif ".m3u8" in p_u:
                lbl = "HLS自适应"
            add_stream(lbl, p_u)

        # 模式 D: 全文泛匹配兜底（排除 preview 预览片）
        if not media_sources:
            all_vids = re.findall(r'["\'](https?://[^"\']+\.(?:mp4|m3u8)[^"\']*)["\']', html_text, re.I)
            for av in all_vids:
                if not any(k in av.lower() for k in ("preview", "thumb", ".jpg", ".png")):
                    add_stream("极速直连", av)

        play_items = []
        for name, p_url in media_sources:
            play_items.append("%s$%s" % (name, p_url))

        # 4. 组装规范简介
        custom_notice = "【💡 温馨提示：视频加载如遇卡顿请尝试切换线路或快进。】"
        group_info = "【🔥 官方交流群: %s】" % self.tgGroup
        
        diag_lines = [
            group_info,
            custom_notice,
            "• 成功捕获播放线路: %s 条" % len(play_items)
        ]
        
        # 如果依然没有抓到直链，截取包含 video 的代码片段到简介，便于秒查
        if not play_items:
            diag_lines.append("\n【直链诊断：页面中包含 video 的脚本段】:")
            video_scripts = []
            for line in html_text.splitlines():
                if any(w in line.lower() for w in ("videojs(", "sources:", "file:", "video_url")):
                    clean_l = line.strip()
                    if 10 < len(clean_l) < 200:
                        video_scripts.append(clean_l)
                if len(video_scripts) >= 5:
                    break
            diag_lines.append("\n".join(video_scripts) if video_scripts else "未扫描到 videojs 关键词行")
        else:
            diag_lines.append("• 原画与多分辨率直链已挂载，可直接播放。")

        vod_content = "\n\n".join(diag_lines)
        escaped_content = vod_content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        return {
            "list": [{
                "vod_id": raw_id,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_actor": self.brandActor,
                "vod_director": self.brandDirector,
                "vod_remarks": "%s条线路" % len(play_items) if play_items else "探针诊断中",
                "vod_content": escaped_content,
                "vod_play_from": "蝴蝶直连",
                "vod_play_url": "#".join(play_items) if play_items else "诊断中$http://127.0.0.1"
            }]
        }

    # 4. 播放器直连
    def playerContent(self, flag, id, vipFlags):
        return {
            "parse": 0,
            "playUrl": "",
            "url": str(id).strip(),
            "header": json.dumps({
                "User-Agent": self._ua,
                "Referer": self.siteUrl + "/",
                "Origin": self.siteUrl
            })
        }

    def searchContent(self, key, quick, pg="1"):
        return {"list": []}