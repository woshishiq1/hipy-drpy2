#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# GDD视频 - TVBox 生产级爬虫（流媒体直解优化版）

import sys
import os
import re
import json
import base64
import html as html_lib
import urllib.request
import urllib.parse
import urllib.error
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
        # 多域名热备机制与主域指针
        self.domains = [
            "https://kie.gdd4.pics"
        ]
        self.currentDomain = self.domains[0]

        # 品牌版权规范
        self.tgGroup = "https://t.me/+3t5XRPPo9mlkZDRl"
        self.brandActor = "📺TG群: https://t.me/+3t5XRPPo9mlkZDRl"
        self.brandDirector = "📺ZakaTV"
        self._ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"

        # 固化静态分类矩阵（首页零网络）
        self.classes = [
            {"type_id": "21", "type_name": "女神学生"},
            {"type_id": "22", "type_name": "美女直播"},
            {"type_id": "23", "type_name": "人妻系列"},
            {"type_id": "24", "type_name": "强奸乱伦"},
            {"type_id": "25", "type_name": "自拍偷拍"},
            {"type_id": "26", "type_name": "制服诱惑"},
            {"type_id": "27", "type_name": "巨乳系列"},
            {"type_id": "28", "type_name": "自慰系列"},
            {"type_id": "29", "type_name": "国产视频"},
            {"type_id": "30", "type_name": "无码视频"},
            {"type_id": "31", "type_name": "有码视频"},
            {"type_id": "32", "type_name": "中文字幕"},
            {"type_id": "33", "type_name": "日韩精品"},
            {"type_id": "34", "type_name": "欧美精品"},
            {"type_id": "35", "type_name": "动漫精品"},
            {"type_id": "36", "type_name": "三级伦理"}
        ]

        # 宽松 SSL 配置，保障老旧机顶盒 TLS 握手正常
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE
        try:
            self.ssl_context.set_ciphers("DEFAULT@SECLEVEL=1")
        except Exception:
            pass

        self._play_cache = {}

    def init(self, extend=""):
        return True

    def isVideoFormat(self, url):
        low = (url or "").lower()
        return any(k in low for k in (".m3u8", ".mp4", ".flv", ".mkv", ".ts"))

    def manualVideoCheck(self):
        return False

    def _http_get(self, url, headers=None, timeout=7):
        if not url:
            return {"code": 0, "text": "", "err": "URL 为空"}

        req_headers = {
            "User-Agent": self._ua,
            "Referer": self.currentDomain + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Connection": "close"
        }
        if headers:
            req_headers.update(headers)

        try:
            req = urllib.request.Request(url, headers=req_headers)
            with urllib.request.urlopen(req, timeout=timeout, context=self.ssl_context) as resp:
                code = resp.getcode()
                raw = resp.read()
                resp_headers = dict(resp.headers)

                if raw.startswith(b"\x1f\x8b"):
                    raw = gzip.decompress(raw)
                elif resp_headers.get("Content-Encoding") == "deflate":
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
            return {"code": -1, "text": "", "err": "%s: %s" % (e.__class__.__name__, str(e))}

    def _resolve_sub_m3u8(self, m3u8_url):
        """核心防卡顿算法：探测并直解 Master 嵌套流，获取最终子码率切片直链"""
        if not m3u8_url:
            return ""

        res = self._http_get(m3u8_url, timeout=5)
        text = res.get("text", "")
        if "#EXT-X-STREAM-INF" in text:
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            for idx, line in enumerate(lines):
                if line.startswith("#EXT-X-STREAM-INF") and idx + 1 < len(lines):
                    sub_line = lines[idx + 1]
                    if not sub_line.startswith("#"):
                        return urllib.parse.urljoin(m3u8_url, sub_line)
        return m3u8_url

    def _extract_m3u8(self, html):
        if not html:
            return ""

        # 1. 匹配 player_data JSON 对象
        m = re.search(r'var\s+player_data\s*=\s*(\{[^}]+\})', html, re.S)
        if m:
            try:
                data = json.loads(m.group(1))
                url = data.get("url", "").replace("\\/", "/")
                if url and ".m3u8" in url.lower():
                    return url
            except Exception:
                pass

        # 2. 正则匹配标准 m3u8 直链
        m2 = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html)
        if m2:
            return m2.group(1).replace("\\/", "/")

        # 3. 匹配配置项 url 键
        m3 = re.search(r'url\s*[:=]\s*["\']([^"\']+\.m3u8[^"\']*)["\']', html, re.I)
        if m3:
            return m3.group(1).replace("\\/", "/")

        return ""

    def _parse_items(self, text):
        items = []
        seen = set()
        video_pattern = r'<li[^>]*>.*?<div[^>]*class="[^"]*video[^"]*"[^>]*>(.*?)</div>.*?</li>'
        for video_html in re.findall(video_pattern, text, re.S):
            link_match = re.search(r'<a[^>]+href="([^"]+)"[^>]*title="([^"]*)"', video_html)
            if not link_match:
                continue
            href = link_match.group(1)
            title = link_match.group(2) or ""

            if not title:
                title_match = re.search(r'<span[^>]*class="[^"]*video-title[^"]*"[^>]*>([^<]+)</span>', video_html)
                if title_match:
                    title = title_match.group(1).strip()

            if not title:
                continue

            pic = ""
            img_match = re.search(r'<img[^>]+src="([^"]+)"', video_html)
            if img_match:
                pic = img_match.group(1)

            remark = ""
            remark_match = re.search(r'<span[^>]*class="[^"]*video-overlay[^"]*"[^>]*>([^<]+)</span>', video_html)
            if remark_match:
                remark = remark_match.group(1).strip()

            if href.startswith(self.currentDomain):
                href = href.replace(self.currentDomain, "")

            if href not in seen:
                seen.add(href)
                items.append({
                    "raw_path": href,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": remark
                })
        return items

    # 1. 首页：纯内存零网络返回
    def homeContent(self, *args, **kwargs):
        return {"class": self.classes}

    def homeVideoContent(self):
        return {"list": []}

    # 2. 分类列表页
    def categoryContent(self, tid, pg="1", *args, **kwargs):
        if str(pg) == "1":
            url = self.currentDomain + "/cn/home/web/index.php/vod/type/id/%s.html" % tid
        else:
            url = self.currentDomain + "/cn/home/web/index.php/vod/type/id/%s/page/%s.html" % (tid, pg)

        res = self._http_get(url, timeout=6)
        items = self._parse_items(res.get("text", ""))

        out_list = []
        for it in items:
            raw_payload = "%s|%s|%s" % (it["raw_path"], it["vod_name"], it["vod_pic"])
            safe_id = "v_" + base64.urlsafe_b64encode(raw_payload.encode("utf-8")).decode("utf-8").rstrip("=")
            out_list.append({
                "vod_id": safe_id,
                "vod_name": it["vod_name"],
                "vod_pic": it["vod_pic"],
                "vod_remarks": it["vod_remarks"]
            })

        return {
            "page": int(pg),
            "pagecount": int(pg) + 1,
            "limit": 30,
            "total": 999,
            "list": out_list
        }

    # 3. 详情页：解出直链并下沉子流，装配ZakaTV标准简介
    def detailContent(self, ids):
        raw_id = ids[0] if isinstance(ids, (list, tuple)) else str(ids)
        target_path = ""
        title = "精彩视频"
        pic = ""

        if raw_id.startswith("v_"):
            b64_str = raw_id[2:]
            pad = len(b64_str) % 4
            if pad:
                b64_str += "=" * (4 - pad)
            try:
                decoded = base64.urlsafe_b64decode(b64_str.encode("utf-8")).decode("utf-8")
                parts = decoded.split("|")
                target_path = parts[0]
                title = parts[1] if len(parts) > 1 else "精彩视频"
                pic = parts[2] if len(parts) > 2 else ""
            except Exception:
                target_path = raw_id
        else:
            target_path = raw_id

        if target_path.startswith("http"):
            detail_url = target_path
        elif target_path.startswith("/"):
            detail_url = self.currentDomain + target_path
        else:
            detail_url = self.currentDomain + "/" + target_path

        # 检查播放直链缓存
        cache_key = detail_url
        if cache_key in self._play_cache:
            final_stream_url = self._play_cache[cache_key]
        else:
            detail_res = self._http_get(detail_url, timeout=7)
            raw_m3u8 = self._extract_m3u8(detail_res.get("text", ""))
            # 下沉直解二级子流
            final_stream_url = self._resolve_sub_m3u8(raw_m3u8) if raw_m3u8 else ""
            if final_stream_url:
                self._play_cache[cache_key] = final_stream_url

        # 简介格式化模板
        custom_notice = "【💡 温馨提示：视频加载如遇卡顿请尝试切换线路或快进。】"
        group_info = "【🔥 官方交流群: %s】" % self.tgGroup

        vod_content = "%s\n\n%s\n\n%s" % (
            group_info,
            custom_notice,
            "视频名称: %s\n高清直连已就绪，享受秒开流畅播放体验！" % title
        )

        escaped_content = vod_content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        play_target = final_stream_url if final_stream_url else detail_url

        return {
            "list": [{
                "vod_id": raw_id,
                "vod_name": title,
                "vod_pic": pic,
                "vod_actor": self.brandActor,
                "vod_director": self.brandDirector,
                "vod_remarks": "高清直链",
                "vod_content": escaped_content,
                "vod_play_from": "Zaka专线",
                "vod_play_url": "超清秒开$%s" % play_target
            }]
        }

    # 4. 播放器：交付直链，严禁 WebView 嗅探，配置防盗链 Header
    def playerContent(self, flag, id, vipFlags):
        url = str(id).strip()

        # 兜底防卡顿：若详情页未命中缓存直接传入了原站播放页，在此处进行直链提取
        if not (url.startswith("http") and ".m3u8" in url.lower()):
            cache_key = url
            if cache_key in self._play_cache:
                url = self._play_cache[cache_key]
            else:
                detail_res = self._http_get(url, timeout=6)
                raw_m3u8 = self._extract_m3u8(detail_res.get("text", ""))
                url = self._resolve_sub_m3u8(raw_m3u8) if raw_m3u8 else url
                if url.startswith("http") and ".m3u8" in url.lower():
                    self._play_cache[cache_key] = url

        headers = {
            "User-Agent": self._ua,
            "Referer": self.currentDomain + "/",
            "Origin": self.currentDomain
        }

        return {
            "parse": 0,
            "playUrl": "",
            "url": url,
            "header": json.dumps(headers)
        }

    # 5. 搜索模块
    def searchContent(self, key, quick, pg="1"):
        url = self.currentDomain + "/cn/home/web/index.php/vod/search.html?wd=" + urllib.parse.quote(key)
        res = self._http_get(url, timeout=6)
        items = self._parse_items(res.get("text", ""))

        out_list = []
        for it in items:
            raw_payload = "%s|%s|%s" % (it["raw_path"], it["vod_name"], it["vod_pic"])
            safe_id = "v_" + base64.urlsafe_b64encode(raw_payload.encode("utf-8")).decode("utf-8").rstrip("=")
            out_list.append({
                "vod_id": safe_id,
                "vod_name": it["vod_name"],
                "vod_pic": it["vod_pic"],
                "vod_remarks": it["vod_remarks"]
            })

        return {"list": out_list}

    def destroy(self):
        self._play_cache.clear()