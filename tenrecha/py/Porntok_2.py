#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import json
import base64
import html as html_lib
import urllib.request
import urllib.parse
from urllib.parse import urljoin, quote, unquote
import http.cookiejar
import gzip
import zlib
import ssl

try:
    from base.spider import Spider as SpiderBase
except ImportError:
    class SpiderBase(object):
        def getCache(self, key): return None
        def setCache(self, key, value): return "fail"
        def delCache(self, key): return "fail"

def format_remarks(brand="ZakaTV", meta=""):
    clean_meta = str(meta or "").strip()
    clean_meta = re.sub(r"[\r\n\t]+", " ", clean_meta).strip()
    if clean_meta:
        return "%s | %s" % (brand, clean_meta)
    return brand

class Spider(SpiderBase):
    def __init__(self):
        super(Spider, self).__init__()
        self.siteUrl = "https://porntok.io"
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

        self.categories = [
            {"type_name": "🔥 精选热推 (For You)", "type_id": "all"},
            {"type_name": "🌸 亚洲精选 (Asian)", "type_id": "asian"},
            {"type_name": "🔞 熟女诱惑 (MILF)", "type_id": "milf"},
            {"type_name": "💦 绝顶内射 (Cumshots)", "type_id": "cumshots"},
            {"type_name": "🍑 丰乳巨乳 (Big Tits)", "type_id": "big-tits"},
            {"type_name": "🎯 后庭狂热 (Anal)", "type_id": "anal"},
            {"type_name": "🎭 动漫二次元 (Hentai)", "type_id": "hentai-animated"},
            {"type_name": "💃 拉美尤物 (Latina)", "type_id": "latina"},
            {"type_name": "✨ 业余自拍 (Amateur)", "type_id": "amateur"},
            {"type_name": "🍫 黑人野性 (Ebony)", "type_id": "ebony"},
            {"type_name": "👗 角色扮演 (Cosplay)", "type_id": "cosplay"},
            {"type_name": "👠 恋物癖好 (Fetish)", "type_id": "fetish"},
            {"type_name": "👩‍🦰 绝色红发 (Redhead)", "type_id": "redhead"},
            {"type_name": "🐘 印度风情 (Indian)", "type_id": "indian"},
            {"type_name": "🍔 丰满肉感 (BBW)", "type_id": "bbw"},
            {"type_name": "🏳️‍🌈 彩虹男同 (Gay)", "type_id": "gay"},
            {"type_name": "📱 TikTok 精选", "type_id": "discover:tiktok porn"},
            {"type_name": "🎞️ 热门 Reels", "type_id": "discover:porn reels"},
            {"type_name": "⚡ 超短爆爽", "type_id": "discover:short porn videos"}
        ]

    def init(self, extend=""):
        if isinstance(extend, dict):
            self.options = extend
        elif extend:
            try:
                self.options = json.loads(extend)
            except Exception:
                self.options = {}
        return True

    def getName(self):
        return "Porntok"

    def isVideoFormat(self, url):
        low = (url or "").lower()
        return any(k in low for k in (".m3u8", ".mp4", ".flv", ".mkv", ".avi", ".ts", ".mpd", "index.png"))

    def manualVideoCheck(self):
        return False

    def _fetch(self, target_url, referer=""):
        if not target_url:
            return {"code": 0, "text": "", "bytes": b"", "err": "", "final_url": ""}
        if target_url.startswith("//"):
            target_url = "https:" + target_url
        elif target_url.startswith("/"):
            target_url = self.siteUrl + target_url

        headers = {
            "User-Agent": self._ua,
            "Referer": referer if referer else (self.siteUrl + "/"),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive"
        }

        last_err = ""
        for attempt in range(2):
            try:
                req = urllib.request.Request(target_url, headers=headers)
                with self.opener.open(req, timeout=10) as resp:
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
                last_err = "HTTP %s" % e.code
                if e.code in (451, 403, 429) and attempt == 0:
                    continue
                err_raw = ""
                try:
                    err_raw = e.read().decode("utf-8", errors="ignore")
                except Exception:
                    pass
                return {"code": e.code, "text": err_raw, "bytes": b"", "err": str(e), "final_url": target_url}
            except Exception as e:
                last_err = str(e)
                if attempt == 0:
                    continue
                return {"code": -1, "text": "", "bytes": b"", "err": str(e), "final_url": target_url}

        return {"code": -1, "text": "", "bytes": b"", "err": last_err, "final_url": target_url}

    def _fetch_videos(self, cat_slug, page_num):
        if cat_slug.startswith("discover:"):
            query_word = cat_slug.split(":", 1)[1]
            url = "/api/videos?q=%s&page=%d" % (quote(query_word), page_num)
        elif cat_slug and cat_slug != "all":
            url = "/api/videos?category=%s&page=%d" % (cat_slug, page_num)
        else:
            url = "/api/videos?page=%d" % page_num

        res = self._fetch(url)
        try:
            data = json.loads(res.get("text", ""))
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                for k in ("videos", "data", "items", "results"):
                    if isinstance(data.get(k), list):
                        return data[k]
        except Exception:
            pass
        return []

    def homeContent(self, filter):
        result = {
            "class": self.categories
        }
        if filter:
            result["filters"] = {}
        return result

    def homeVideoContent(self):
        return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        del filter, extend
        cat_slug = str(tid).strip("/")
        page_num = 1
        try:
            page_num = int(pg)
        except Exception:
            page_num = 1

        v_list = self._fetch_videos(cat_slug, page_num)
        items = []

        for idx, item in enumerate(v_list):
            v_id = str(item.get("id", ""))
            raw_title = item.get("title") or ""
            cat_display = item.get("category") or "短视频"
            title = raw_title if raw_title else ("%s #%s" % (cat_slug.upper(), v_id))
            pic = item.get("thumbnail_url") or item.get("preview_url") or ""

            pack_id = "pack@@%s@@%d@@%d@@%s" % (cat_slug, page_num, idx, v_id)

            remarks = format_remarks("ZakaTV", cat_display)
            items.append({
                "vod_id": pack_id,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remarks,
                "style": {"type": "rect", "ratio": 1.78}
            })

        return {
            "page": page_num,
            "pagecount": 999,
            "limit": 50,
            "total": 9999,
            "list": items
        }

    def detailContent(self, ids):
        raw_id = ids[0] if isinstance(ids, (list, tuple)) else str(ids)

        cat_slug = "all"
        page_num = 1
        offset = 0
        target_vid = ""

        if raw_id.startswith("pack@@"):
            parts = raw_id.split("@@")
            if len(parts) >= 5:
                cat_slug = parts[1]
                page_num = int(parts[2])
                offset = int(parts[3])
                target_vid = parts[4]

        cur_list = self._fetch_videos(cat_slug, page_num)

        selected_video = None
        remaining_cur_page = []

        if 0 <= offset < len(cur_list):
            selected_video = cur_list[offset]
            remaining_cur_page = cur_list[offset + 1:]
        else:
            for idx, it in enumerate(cur_list):
                if str(it.get("id")) == str(target_vid):
                    selected_video = it
                    remaining_cur_page = cur_list[idx + 1:]
                    break

        if not selected_video and cur_list:
            selected_video = cur_list[0]
            remaining_cur_page = cur_list[1:]

        preloaded_stream = []
        if selected_video:
            preloaded_stream.append(selected_video)
        preloaded_stream.extend(remaining_cur_page)

        for next_p in range(page_num + 1, page_num + 5):
            nxt_list = self._fetch_videos(cat_slug, next_p)
            if not nxt_list:
                break
            preloaded_stream.extend(nxt_list)

        play_episodes = []
        for item in preloaded_stream:
            v_url = item.get("path") or ""
            if not v_url:
                continue
            play_episodes.append("$%s" % v_url)

        play_url_str = "#".join(play_episodes)

        first_title = selected_video.get("title") if selected_video else "Porntok"
        first_pic = selected_video.get("thumbnail_url") if selected_video else ""

        full_desc = (
            "【🔥 官方交流群: %s】\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "• 模式特性: 抖音式全自动无底洞沉浸短视频流\n"
            "• 本次已预取装载: %d 部连续视频\n"
            "• 遥控器操作指引: 播完自动切下一条，或按【下键】/【右键】秒切下一条视频（已去除一切弹窗，纯净全屏无感切集）！"
        ) % (self.tgGroup, len(preloaded_stream))

        return {
            "list": [{
                "vod_id": raw_id,
                "vod_name": first_title,
                "vod_pic": first_pic,
                "vod_actor": self.brandActor,
                "vod_director": self.brandDirector,
                "vod_remarks": "已装配 %d 条" % len(preloaded_stream),
                "vod_content": full_desc.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"),
                "vod_play_from": "📺Zaka抖音连刷线",
                "vod_play_url": play_url_str
            }]
        }

    def playerContent(self, flag, id, vipFlags):
        clean_url = str(id).strip()
        return {
            "parse": 0,
            "jx": 0,
            "url": clean_url,
            "header": {
                "User-Agent": self._ua,
                "Referer": self.siteUrl + "/"
            }
        }

    def searchContent(self, key, quick, pg="1"):
        page_num = 1
        try:
            page_num = int(pg)
        except Exception:
            page_num = 1

        v_list = self._fetch_videos("discover:" + str(key).strip(), page_num)
        items = []

        for idx, item in enumerate(v_list):
            v_id = str(item.get("id", ""))
            title = item.get("title") or ("%s #%s" % (key, v_id))
            pic = item.get("thumbnail_url") or item.get("preview_url") or ""
            pack_id = "pack@@discover:%s@@%d@@%d@@%s" % (key, page_num, idx, v_id)

            items.append({
                "vod_id": pack_id,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": "ZakaTV",
                "style": {"type": "rect", "ratio": 1.78}
            })

        return {
            "page": page_num,
            "pagecount": 999,
            "limit": 50,
            "total": 9999,
            "list": items
        }

    def action(self, action):
        return {"msg": "ok"}

    def liveContent(self):
        return ""

    def localProxy(self, params):
        return [404, "text/plain; charset=utf-8", "Proxy not configured"]

    def destroy(self):
        self.options = {}