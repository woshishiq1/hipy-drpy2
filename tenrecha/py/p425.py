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
        self.siteUrl = "https://idl.dfswh5.top"
        self.tgGroup = "https://t.me/+3t5XRPPo9mlkZDRl"
        self.brandActor = "📺TG群: https://t.me/+3t5XRPPo9mlkZDRl"
        self.brandDirector = "📺ZakaTV"
        self._ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

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
        if target_url.startswith("/"):
            target_url = self.siteUrl + target_url

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
        except Exception as e:
            return {"code": -1, "text": "", "err": str(e)}

    def homeContent(self, *args, **kwargs):
        return {
            "class": [
                {"type_name": "人妻熟女", "type_id": "/vodtype/1.html"},
                {"type_name": "强奸乱伦", "type_id": "/vodtype/2.html"},
                {"type_name": "制服师生", "type_id": "/vodtype/3.html"},
                {"type_name": "网红主播", "type_id": "/vodtype/4.html"},
                {"type_name": "偷拍自拍", "type_id": "/vodtype/20.html"},
                {"type_name": "自慰自淫", "type_id": "/vodtype/21.html"},
                {"type_name": "国产专区", "type_id": "/vodtype/22.html"},
                {"type_name": "虐待同性", "type_id": "/vodtype/23.html"},
                {"type_name": "日韩精品", "type_id": "/vodtype/24.html"},
                {"type_name": "欧美性爱", "type_id": "/vodtype/25.html"},
                {"type_name": "卡通动漫", "type_id": "/vodtype/26.html"},
                {"type_name": "三级伦理", "type_id": "/vodtype/27.html"}
            ]
        }

    def categoryContent(self, tid, pg, *args, **kwargs):
        target_url = "%s%s" % (self.siteUrl, tid if tid.startswith("/") else ("/" + tid))
        if int(pg) > 1:
            target_url = target_url.replace(".html", "-%s.html" % pg)

        res = self._fetch(target_url)
        html_text = res.get("text", "")

        items = re.findall(r'<li[^>]*>([\s\S]*?)</li>', html_text, re.I)
        if not items:
            items = re.findall(r'<div[^>]+class=["\'][^"\']*vodlist_item[^"\']*["\'][^>]*>([\s\S]*?)</div>', html_text, re.I)

        videos = []
        for block in items:
            link_match = re.search(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*title=["\']([^"\']+)["\']', block, re.I)
            if not link_match:
                link_match = re.search(r'<a[^>]+title=["\']([^"\']+)["\'][^>]*href=["\']([^"\']+)["\']', block, re.I)
                if link_match:
                    href = link_match.group(2)
                    title = link_match.group(1)
                else:
                    continue
            else:
                href = link_match.group(1)
                title = link_match.group(2)

            clean_title = title.strip()
            if clean_title in ("首页", "导航") or not clean_title:
                continue
            if "http" in href and self.siteUrl not in href:
                continue
            if "vodtype" in href or "label" in href:
                continue

            clean_url = href if href.startswith("http") else (self.siteUrl + (href if href.startswith("/") else "/" + href))
            
            payload = {"url": clean_url, "name": clean_title}
            safe_id = "v_" + base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8").rstrip("=")

            pic_match = re.search(r'data-(?:original|src)=["\']([^"\']+)["\']', block, re.I)
            if not pic_match:
                pic_match = re.search(r'src=["\']([^"\']+)["\']', block, re.I)
            
            pic_url = pic_match.group(1) if pic_match else ""
            if pic_url and not pic_url.startswith("http"):
                pic_url = self.siteUrl + (pic_url if pic_url.startswith("/") else "/" + pic_url)

            videos.append({
                "vod_id": safe_id,
                "vod_name": clean_title,
                "vod_pic": pic_url if pic_url else "https://dummyimage.com/400x600/1a1a1a/ffffff.png&text=VOD",
                "vod_remarks": "高清"
            })

        if not videos:
            blocks = re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*title=["\']([^"\']+)["\'][^>]*>([\s\S]*?)</a>', html_text, re.I)
            for href, title, inner_html in blocks:
                clean_title = title.strip()
                if clean_title in ("首页", "导航") or not clean_title:
                    continue
                if "vodtype" in href or "label" in href:
                    continue
                clean_url = href if href.startswith("http") else (self.siteUrl + (href if href.startswith("/") else "/" + href))
                payload = {"url": clean_url, "name": clean_title}
                safe_id = "v_" + base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8").rstrip("=")
                
                pic_match = re.search(r'data-(?:original|src)=["\']([^"\']+)["\']', inner_html, re.I)
                if not pic_match:
                    pic_match = re.search(r'src=["\']([^"\']+)["\']', inner_html, re.I)
                pic_url = pic_match.group(1) if pic_match else ""
                if pic_url and not pic_url.startswith("http"):
                    pic_url = self.siteUrl + (pic_url if pic_url.startswith("/") else "/" + pic_url)

                videos.append({
                    "vod_id": safe_id,
                    "vod_name": clean_title,
                    "vod_pic": pic_url if pic_url else "https://dummyimage.com/400x600/1a1a1a/ffffff.png&text=VOD",
                    "vod_remarks": "高清"
                })

        if not videos:
            videos.append({
                "vod_id": "v_empty",
                "vod_name": "暂无视频",
                "vod_pic": "",
                "vod_remarks": "空"
            })

        return {
            "page": int(pg),
            "pagecount": 99,
            "limit": 20,
            "total": 999,
            "list": videos
        }

    def detailContent(self, ids):
        raw_id = ids[0] if isinstance(ids, (list, tuple)) else str(ids)
        real_url = self.siteUrl
        vod_name = "视频详情"
        
        try:
            if raw_id.startswith("v_") and raw_id != "v_empty":
                b64_str = raw_id[2:]
                pad = len(b64_str) % 4
                if pad:
                    b64_str += "=" * (4 - pad)
                decoded_bytes = base64.urlsafe_b64decode(b64_str.encode("utf-8"))
                try:
                    payload = json.loads(decoded_bytes.decode("utf-8"))
                    if isinstance(payload, dict):
                        real_url = payload.get("url", self.siteUrl)
                        vod_name = payload.get("name", "视频详情")
                    else:
                        real_url = decoded_bytes.decode("utf-8")
                except Exception:
                    real_url = decoded_bytes.decode("utf-8")
        except Exception:
            pass

        vod_pic = ""
        play_url_str = "在线播放$%s" % real_url

        try:
            res = self._fetch(real_url)
            html_text = res.get("text", "")

            pic_match = re.search(r'<img[^>]+class=["\'][^"\']*vod-img[^"\']*["\'][^>]+src=["\']([^"\']+)["\']', html_text, re.I)
            if not pic_match:
                pic_match = re.search(r'<img[^>]+src=["\']([^"\']+\.(?:jpg|png|webp)[^"\']*)["\']', html_text, re.I)
            if pic_match:
                vod_pic = pic_match.group(1)
                if vod_pic and not vod_pic.startswith("http"):
                    vod_pic = self.siteUrl + (vod_pic if vod_pic.startswith("/") else "/" + vod_pic)

            raw_content = ""
            content_match = re.search(r'简介：(.*?)</p>', html_text, re.I)
            if content_match:
                raw_content = content_match.group(1)
            else:
                desc_match = re.search(r'class="vod_content"[^>]*>([\s\S]*?)</div>', html_text, re.I)
                if desc_match:
                    raw_content = desc_match.group(1)

            clean_content = self._unesc(re.sub(r'<[^>]+>', '', raw_content)).strip()

            custom_notice = "【💡 温馨提示：视频加载如遇卡顿请尝试切换线路或快进。】"
            group_info = "【🔥 官方交流群: %s】" % self.tgGroup

            if clean_content:
                vod_content = "%s\n\n%s\n\n%s" % (group_info, custom_notice, clean_content)
            else:
                vod_content = "%s\n\n%s\n\n暂无详细简介，欢迎加入TG群获取最新资源！" % (group_info, custom_notice)

            escaped_content = vod_content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

            play_urls = []
            play_links = re.findall(r'<a[^>]+href=["\']([^"\']*?/vodplay/[^"\']+)["\'][^>]*>([\s\S]*?)</a>', html_text, re.I)
            for p_href, p_title in play_links:
                clean_p_title = self._unesc(re.sub(r'<[^>]+>', '', p_title))
                play_urls.append("%s$%s" % (clean_p_title if clean_p_title else "正片", p_href))

            if not play_urls:
                m3u8_matches = re.findall(r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', html_text, re.I)
                for idx, m_url in enumerate(m3u8_matches):
                    play_urls.append("线路%d$%s" % (idx + 1, m_url))

            if play_urls:
                play_url_str = "#".join(play_urls)
        except Exception:
            escaped_content = "【🔥 官方交流群: %s】\n\n【💡 温馨提示：视频加载如遇卡顿请尝试切换线路或快进。】" % self.tgGroup

        return {
            "list": [{
                "vod_id": raw_id,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_actor": self.brandActor,
                "vod_director": self.brandDirector,
                "vod_remarks": "高清正片",
                "vod_content": escaped_content,
                "vod_play_from": "ZakaTV",
                "vod_play_url": play_url_str
            }]
        }

    def playerContent(self, flag, id, vipFlags):
        stream_url = str(id).strip()
        if not self.isVideoFormat(stream_url):
            try:
                res = self._fetch(stream_url)
                html_text = res.get("text", "")
                player_match = re.search(r'var\s+player_aaaa\s*=\s*(\{.*?\});', html_text, re.S)
                if player_match:
                    p_json = json.loads(player_match.group(1))
                    raw_url = p_json.get("url", "")
                    encrypt = p_json.get("encrypt", 0)
                    if encrypt == 1:
                        raw_url = urllib.parse.unquote(raw_url)
                    elif encrypt == 2:
                        pad = len(raw_url) % 4
                        if pad:
                            raw_url += "=" * (4 - pad)
                        raw_url = base64.b64decode(raw_url.encode("utf-8")).decode("utf-8")
                    if raw_url and self.isVideoFormat(raw_url):
                        stream_url = raw_url
                
                if not self.isVideoFormat(stream_url):
                    m_match = re.search(r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', html_text, re.I)
                    if m_match:
                        stream_url = m_match.group(1)
            except Exception:
                pass

        return {
            "parse": 0,
            "playUrl": "",
            "url": stream_url,
            "header": json.dumps({"User-Agent": self._ua, "Referer": self.siteUrl + "/"})
        }

    def searchContent(self, key, quick, pg="1"):
        return {"list": []}