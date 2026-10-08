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
        self.siteUrl = "https://rzj.ynxj9.work/"
        self.tgGroup = "https://t.me/tvshare23"
        self.brandActor = "🦋 TG群: @tvshare23"
        self.brandDirector = "🦋 蝴蝶影视"
        
        # 采纳已验证的安卓移动端 UA 确保畅通
        self._ua = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Mobile Safari/537.36"

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
        low = (url or "").lower()
        return any(k in low for k in (".m3u8", ".mp4", ".flv", ".mkv", ".avi", ".ts"))

    def manualVideoCheck(self):
        return False

    def _fetch(self, target_url, referer=""):
        if not target_url:
            return {"code": 0, "text": "", "err": "URL 为空"}
        
        if target_url.startswith("http"):
            pass
        elif target_url.startswith("/"):
            base_root = re.match(r'(https?://[^/]+)', self.siteUrl).group(1)
            target_url = base_root + target_url
        else:
            target_url = self.siteUrl.rstrip("/") + "/" + target_url

        headers = {
            "User-Agent": self._ua,
            "Referer": referer if referer else (self.siteUrl + "/"),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "Connection": "close"
        }

        try:
            req = urllib.request.Request(target_url, headers=headers)
            with self.opener.open(req, timeout=12) as resp:
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
            return {"code": e.code, "text": "", "err": "HTTPError: %s" % str(e)}
        except Exception as e:
            return {"code": -1, "text": "", "err": str(e)}

    def _unesc(self, s):
        try:
            return html_lib.unescape(s or "").strip()
        except Exception:
            return (s or "").strip()

    def _get_matched(self, pattern, text, default=""):
        try:
            match = re.search(pattern, text, re.I | re.S)
            if match:
                return match.group(1)
        except Exception:
            pass
        return default

    # 1. 首页：纯内存毫秒级返回
    def homeContent(self, *args, **kwargs):
        classes = [
            {"type_name": "女神学生", "type_id": "vodtype/21.html"},
            {"type_name": "美女直播", "type_id": "vodtype/22.html"},
            {"type_name": "人妻系列", "type_id": "vodtype/23.html"},
            {"type_name": "强奸乱伦", "type_id": "vodtype/24.html"},
            {"type_name": "自拍偷拍", "type_id": "vodtype/25.html"},
            {"type_name": "制服诱惑", "type_id": "vodtype/26.html"},
            {"type_name": "巨乳系列", "type_id": "vodtype/27.html"},
            {"type_name": "自慰系列", "type_id": "vodtype/28.html"},
            {"type_name": "国产视频", "type_id": "vodtype/29.html"},
            {"type_name": "无码视频", "type_id": "vodtype/30.html"},
            {"type_name": "有码视频", "type_id": "vodtype/31.html"},
            {"type_name": "中文字幕", "type_id": "vodtype/32.html"},
            {"type_name": "日韩精品", "type_id": "vodtype/33.html"},
            {"type_name": "欧美精品", "type_id": "vodtype/34.html"},
            {"type_name": "动漫精品", "type_id": "vodtype/35.html"},
            {"type_name": "三级伦理", "type_id": "vodtype/36.html"}
        ]
        return {"class": classes}

    # 2. 列表页
    def categoryContent(self, tid, pg, *args, **kwargs):
        slug = str(tid).strip()
        page_url = slug
        if int(pg) > 1:
            base_no_ext = page_url[:-5] if page_url.endswith(".html") else page_url
            page_url = "%s-%s.html" % (base_no_ext, pg)

        res = self._fetch(page_url)
        html_text = res.get("text", "")

        videos = []
        items = re.findall(r'(<a[^>]+class=["\'][^"\']*videopic[^"\']*["\'][\s\S]*?<\/div>\s*<\/div>)', html_text, re.I)
        if not items:
            items = re.findall(r'(<div[^>]+class=["\'][^"\']*(?:col-md|col-sm|item)[^"\']*["\'][\s\S]*?<\/div>\s*<\/div>\s*<\/div>)', html_text, re.I)

        for item in items:
            href_m = re.search(r'href=["\']([^"\']+\.html)["\']', item, re.I)
            bg_m = re.search(r'background:\s*url\(([^)]+)\)', item, re.I)
            title_m = re.search(r'class=["\'][^"\']*title[^"\']*["\'][\s\S]*?title=["\']([^"\']+)["\']', item, re.I)
            if not title_m:
                title_m = re.search(r'class=["\'][^"\']*title[^"\']*["\'][\s\S]*?>([^<]+)<\/a>', item, re.I)

            if href_m:
                href = href_m.group(1)
                if "vodtype" in href or "page" in href:
                    continue

                title = self._unesc(title_m.group(1)) if title_m else "未知视频"
                
                pic = ""
                if bg_m:
                    pic = bg_m.group(1).strip("'\"")
                    if pic.startswith("/"):
                        base_root = re.match(r'(https?://[^/]+)', self.siteUrl).group(1)
                        pic = base_root + pic

                safe_id = "v_" + base64.urlsafe_b64encode(href.encode("utf-8")).decode("utf-8").rstrip("=")

                videos.append({
                    "vod_id": safe_id,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": "高清"
                })

        return {
            "page": int(pg),
            "pagecount": 99,
            "limit": 20,
            "total": len(videos) * 20 if videos else 0,
            "list": videos
        }

    # 3. 详情页：精准修复标题提取（优先从网页标题 <title> 或详情面板中获取）
    def detailContent(self, ids):
        raw_id = ids[0] if isinstance(ids, (list, tuple)) else str(ids)
        detail_url = self.siteUrl

        if str(raw_id).startswith("v_"):
            try:
                b64_str = raw_id[2:]
                pad = len(b64_str) % 4
                if pad:
                    b64_str += "=" * (4 - pad)
                detail_url = base64.urlsafe_b64decode(b64_str.encode("utf-8")).decode("utf-8")
            except Exception:
                pass

        res = self._fetch(detail_url)
        html_text = res.get("text", "")

        # 修复点：优先从 <title> 提取（通常格式如 “视频名 - 欲女心经”）或者从正文大标题提取
        page_title = self._get_matched(r'<title>(.*?)</title>', html_text, "")
        if page_title:
            # 去除后缀如 " - 欲女心经"
            vod_name = page_title.split("-")[0].split("_")[0].strip()
        else:
            # 备用：从面包屑或详情 h2/h3 中取
            h_match = self._get_matched(r'<h[23][^>]*>(.*?)</h[23]>', html_text, "")
            vod_name = self._unesc(re.sub(r'<[^>]+>', '', h_match)) if h_match else "未知视频"

        if not vod_name:
            vod_name = "未知视频"

        # 提取海报
        bg_m = re.search(r'background:\s*url\(([^)]+)\)', html_text, re.I)
        vod_pic = ""
        if bg_m:
            vod_pic = bg_m.group(1).strip("'\"")
            if vod_pic.startswith("/"):
                base_root = re.match(r'(https?://[^/]+)', self.siteUrl).group(1)
                vod_pic = base_root + vod_pic

        # 简介提取
        raw_content = self._get_matched(r'简介：(.*?)</p>', html_text, "")
        clean_content = self._unesc(re.sub(r'<[^>]+>', '', raw_content)).strip()
        
        custom_notice = "【💡 温馨提示：视频加载如遇卡顿请尝试切换线路或快进。】"
        group_info = "【🔥 官方交流群: %s】" % self.tgGroup
        
        if clean_content:
            vod_content = "%s\n\n%s\n\n%s" % (group_info, custom_notice, clean_content)
        else:
            vod_content = "%s\n\n%s\n\n暂无详细简介，欢迎加入TG群获取最新资源！" % (group_info, custom_notice)

        escaped_desc = vod_content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        # 提取 m3u8 直链
        raw_url_match = re.search(r'const\s+rawUrl\s*=\s*["\']([^"\']+\.m3u8[^"\']*)["\']', html_text, re.I)
        if not raw_url_match:
            raw_url_match = re.search(r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', html_text, re.I)

        play_url = raw_url_match.group(1) if raw_url_match else "http://127.0.0.1"

        return {
            "list": [{
                "vod_id": raw_id,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_actor": self.brandActor,
                "vod_director": self.brandDirector,
                "vod_remarks": "高清直连",
                "vod_content": escaped_desc,
                "vod_play_from": "高速线路",
                "vod_play_url": "正片播放$%s" % play_url
            }]
        }

    # 4. 播放器
    def playerContent(self, flag, id, vipFlags):
        stream_url = str(id).strip()
        if stream_url.startswith("/"):
            base_root = re.match(r'(https?://[^/]+)', self.siteUrl).group(1)
            stream_url = base_root + stream_url

        return {
            "parse": 0,
            "playUrl": "",
            "url": stream_url,
            "header": json.dumps({"User-Agent": self._ua, "Referer": self.siteUrl})
        }

    # 5. 搜索支持
    def searchContent(self, key, quick, pg="1"):
        search_url = "%sindex.php/vod/search.html?wd=%s" % (self.siteUrl, urllib.parse.quote(key))
        res = self._fetch(search_url)
        html_text = res.get("text", "")

        videos = []
        items = re.findall(r'(<a[^>]+class=["\'][^"\']*videopic[^"\']*["\'][\s\S]*?<\/div>\s*<\/div>)', html_text, re.I)
        for item in items:
            href_m = re.search(r'href=["\']([^"\']+\.html)["\']', item, re.I)
            bg_m = re.search(r'background:\s*url\(([^)]+)\)', item, re.I)
            title_m = re.search(r'class=["\'][^"\']*title[^"\']*["\'][\s\S]*?title=["\']([^"\']+)["\']', item, re.I)

            if href_m:
                href = href_m.group(1)
                title = self._unesc(title_m.group(1)) if title_m else "搜索视频"
                pic = bg_m.group(1).strip("'\"") if bg_m else ""
                if pic.startswith("/"):
                    base_root = re.match(r'(https?://[^/]+)', self.siteUrl).group(1)
                    pic = base_root + pic

                safe_id = "v_" + base64.urlsafe_b64encode(href.encode("utf-8")).decode("utf-8").rstrip("=")
                videos.append({
                    "vod_id": safe_id,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": "搜索结果"
                })

        return {"list": videos}