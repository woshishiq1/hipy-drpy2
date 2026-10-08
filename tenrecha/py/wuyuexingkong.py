#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
══════════════════════════════════════════════════════════════════
星空影院 (xkyy123.cc) TVBox 生产级全功能正式版
══════════════════════════════════════════════════════════════════
"""

import sys
import os
import re
import json
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
        def __init__(self):
            pass


class Spider(SpiderBase):
    def __init__(self):
        super(Spider, self).__init__()
        self.siteUrl = "https://www.xkyy123.cc"
        self.tgGroup = "https://t.me/tvshare23"

        self.ctx = ssl.create_default_context()
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE
        try:
            self.ctx.set_ciphers('DEFAULT@SECLEVEL=1')
        except Exception:
            pass

        self.cj = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cj),
            urllib.request.HTTPSHandler(context=self.ctx)
        )

    def init(self, extend=""):
        return True

    def isVideoFormat(self, url):
        if not url:
            return False
        clean = url.lower().split("?")[0]
        return any(clean.endswith(ext) or ext in clean for ext in [".m3u8", ".mp4", ".ts", ".flv", ".mov", ".m4v"])

    def manualVideoCheck(self):
        return False

    def _clean_url(self, raw_url):
        if not raw_url:
            return ""
        s = raw_url.strip()
        s = s.replace(r"\/", "/")
        while "&amp;" in s:
            s = s.replace("&amp;", "&")
        return s

    def _fetch(self, url, referer=None, timeout=12):
        if not url:
            return ""
        parsed = urllib.parse.urlparse(url)
        host = parsed.netloc if parsed.netloc else "www.xkyy123.cc"
        ref = referer if referer else (self.siteUrl + "/")

        headers = {
            "Host": host,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Referer": ref,
            "Sec-Ch-Ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
            "Connection": "close"
        }

        def decode_stream(raw_bytes, enc):
            if raw_bytes.startswith(b"\x1f\x8b"):
                try:
                    return gzip.decompress(raw_bytes)
                except Exception:
                    return zlib.decompress(raw_bytes, 16 + zlib.MAX_WBITS)
            elif enc == "deflate":
                try:
                    return zlib.decompress(raw_bytes)
                except Exception:
                    pass
            return raw_bytes

        try:
            req = urllib.request.Request(url, headers=headers)
            with self.opener.open(req, timeout=timeout) as resp:
                data = decode_stream(resp.read(), resp.headers.get("Content-Encoding"))
                try:
                    return data.decode("utf-8")
                except Exception:
                    return data.decode("gbk", errors="ignore")
        except Exception:
            return ""

    def _fix_url(self, path):
        if not path:
            return ""
        if path.startswith("http://") or path.startswith("https://"):
            return path
        if path.startswith("//"):
            return "https:" + path
        return self.siteUrl.rstrip("/") + "/" + path.lstrip("/")

    # ══════════════════════════════════════════════════════════
    # 1. 首页分类
    # ══════════════════════════════════════════════════════════
    def homeContent(self, *args, **kwargs):
        classes = [
            {"type_name": "国产", "type_id": "/t/1.html"},
            {"type_name": "自拍", "type_id": "/t/6.html"},
            {"type_name": "无码", "type_id": "/t/24.html"},
            {"type_name": "有码", "type_id": "/t/50.html"},
            {"type_name": "中字", "type_id": "/t/25.html"},
            {"type_name": "欧美", "type_id": "/t/26.html"},
            {"type_name": "动漫", "type_id": "/t/27.html"},
            {"type_name": "传媒", "type_id": "/t/9.html"},
            {"type_name": "探花", "type_id": "/t/5.html"},
            {"type_name": "反差婊", "type_id": "/t/10.html"},
            {"type_name": "网爆门", "type_id": "/t/11.html"},
            {"type_name": "偷拍", "type_id": "/t/12.html"}
        ]
        return {"class": classes}

    # ══════════════════════════════════════════════════════════
    # 2. 列表解析：精准提取背景图海报与卡片数据
    # ══════════════════════════════════════════════════════════
    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = int(pg)
        except Exception:
            page = 1

        clean_path = tid.strip()
        # MacCMS 常见分页路由格式: /t/1-2.html 或 /t/1.html?page=2
        if page > 1:
            if ".html" in clean_path:
                target_url = self._fix_url(clean_path.replace(".html", "-%d.html" % page))
            else:
                target_url = self._fix_url("%s?page=%d" % (clean_path.rstrip("/"), page))
        else:
            target_url = self._fix_url(clean_path)

        html = self._fetch(target_url)
        videos = []
        seen = set()

        if html:
            card_items = re.findall(r'(<div[^>]*class=["\'][^"\']*card[^"\']*["\'][\s\S]*?</div>\s*</div>)', html, re.I)
            if not card_items:
                card_items = re.findall(r'(<a[^>]+class=["\'][^"\']*pic[^"\']*["\'][^>]*>[\s\S]*?</a>)', html, re.I)

            for c in card_items:
                m_href = re.search(r'href=["\'](/s/\d+\.html)["\']', c)
                if not m_href:
                    m_href = re.search(r'href=["\']([^"\']+/s/\d+\.html)["\']', c)
                if not m_href:
                    continue

                v_url = self._fix_url(m_href.group(1))
                if v_url in seen:
                    continue

                # 提取标题
                m_title = re.search(r'title=["\']([^"\']+)["\']', c)
                v_title = m_title.group(1).strip() if m_title else ""
                if not v_title:
                    m_alt = re.search(r'alt=["\']([^"\']+)["\']', c)
                    v_title = m_alt.group(1).strip() if m_alt else "高清视频"

                # 提取背景图海报
                m_pic = re.search(r'background-image:\s*url\((["\']?)(https?://[^"\'\)]+)\1\)', c, re.I)
                v_pic = m_pic.group(2).strip() if m_pic else ""

                # 提取评分/分数备注
                remarks = []
                m_score = re.search(r'class=["\']badge-score["\'][^>]*>([\s\S]*?)</span>', c)
                if m_score:
                    remarks.append(re.sub(r'<[^>]+>', '', m_score.group(1)).strip() + "分")

                seen.add(v_url)
                videos.append({
                    "vod_id": v_url,
                    "vod_name": v_title,
                    "vod_pic": v_pic,
                    "vod_remarks": " · ".join(remarks) if remarks else "高清"
                })

        has_more = len(videos) >= 12
        return {
            "list": videos,
            "page": page,
            "pagecount": page + 1 if has_more else page,
            "limit": len(videos),
            "total": 9999
        }

    # ══════════════════════════════════════════════════════════
    # 3. 详情解析：构建分集播放列表
    # ══════════════════════════════════════════════════════════
    def detailContent(self, ids):
        vod_url = ids[0]
        html = self._fetch(vod_url)

        title = "星空影视"
        pic = ""
        desc = ""
        play_list = []

        if html:
            # 标题
            t_m = re.search(r'<title>(.*?)</title>', html, re.I | re.S)
            if t_m:
                title = t_m.group(1).split("-")[0].strip()

            # 海报
            m_pic = re.search(r'background-image:\s*url\((["\']?)(https?://[^"\'\)]+)\1\)', html, re.I)
            if m_pic:
                pic = m_pic.group(2).strip()
            else:
                og_m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html)
                if og_m:
                    pic = og_m.group(1).strip()

            # 简介
            d_m = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']', html)
            if d_m:
                desc = d_m.group(1).strip()

            # 选集提取：抓取形如 <a class="line-play" href="/s-p/339182-1-1.html">HD高清1线</a>
            line_plays = re.findall(r'<a[^>]+class=["\']line-play["\'][^>]+href=["\']([^"\']+)["\'][^>]*>([\s\S]*?)</a>', html, re.I)
            if not line_plays:
                line_plays = re.findall(r'<a[^>]+href=["\']([^"\']+/s-p/[^"\']+)["\'][^>]*>([\s\S]*?)</a>', html, re.I)

            seen_ep = set()
            for ep_h, ep_t in line_plays:
                clean_t = re.sub(r'<[^>]+>', '', ep_t).strip()
                clean_h = self._fix_url(ep_h.strip())
                if not clean_t or clean_h in seen_ep:
                    continue
                seen_ep.add(clean_h)
                play_list.append("%s$%s" % (clean_t, clean_h))

        if not play_list:
            play_list.append("正片$" + vod_url)

        full_content = "【🔥官方交流群: %s】\n\n%s" % (self.tgGroup, desc if desc else "星空影院高清在线播放")

        return {
            "list": [{
                "vod_id": vod_url,
                "vod_name": title,
                "vod_pic": pic,
                "vod_actor": "🦋 TG群: @tvshare23 (点击【简介】获取更多)",
                "vod_director": "🦋 蝴蝶影视",
                "vod_remarks": "关注TG不迷路",
                "vod_content": full_content,
                "vod_play_from": "🦋 官方TG: @tvshare23",
                "vod_play_url": "#".join(play_list)
            }]
        }

    # ══════════════════════════════════════════════════════════
    # 4. 播放地址直出：抓取播放页 player_data 变量提取 m3u8
    # ══════════════════════════════════════════════════════════
    def playerContent(self, flag, id, vipFlags):
        play_url = self._fix_url(id.strip())
        html = self._fetch(play_url)

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Referer": self.siteUrl + "/",
            "Origin": self.siteUrl
        }

        # 1. 优先从 player_data 变量中提取 url 字段
        m_data = re.search(r'var\s+player_data\s*=\s*(\{[\s\S]*?\});', html)
        if m_data:
            try:
                json_str = m_data.group(1)
                data_dict = json.loads(json_str)
                raw_url = data_dict.get("url", "").strip()
                clean_stream = self._clean_url(raw_url)
                if clean_stream and self.isVideoFormat(clean_stream):
                    return {
                        "parse": 0,
                        "url": clean_stream,
                        "header": json.dumps(headers)
                    }
            except Exception:
                pass

        # 2. 备选：全局扫描 m3u8 直链
        m3u8_matches = re.findall(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html)
        if m3u8_matches:
            target_stream = self._clean_url(m3u8_matches[0])
            return {
                "parse": 0,
                "url": target_stream,
                "header": json.dumps(headers)
            }

        return {
            "parse": 1,
            "url": play_url,
            "header": json.dumps(headers)
        }

    # ══════════════════════════════════════════════════════════
    # 5. 搜索功能
    # ══════════════════════════════════════════════════════════
    def searchContent(self, key, quick, pg="1"):
        try:
            page = int(pg)
        except Exception:
            page = 1

        query = urllib.parse.quote(key)
        # 根据前置探针暴露的搜素路由: /sou/-.html 或 /search?wd=
        search_path = "/sou/%s.html" % query
        if page > 1:
            search_path = "/sou/%s-%d.html" % (query, page)

        return self.categoryContent(search_path, pg, False, {})
