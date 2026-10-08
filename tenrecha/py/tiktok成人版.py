#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
══════════════════════════════════════════════════════════════════
tiktvod01.xyz 正式版 (精准中文标题与双轨直出完整版)
官方交流群：https://t.me/tvshare23
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
        self.siteUrl = "https://tiktvod01.xyz"
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

    def _fetch(self, url, referer=None, timeout=12):
        if not url:
            return ""
        parsed = urllib.parse.urlparse(url)
        host = parsed.netloc if parsed.netloc else "tiktvod01.xyz"
        ref = referer if referer else (self.siteUrl + "/")

        headers = {
            "Host": host,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Referer": ref,
            "Connection": "keep-alive"
        }
        try:
            req = urllib.request.Request(url, headers=headers)
            with self.opener.open(req, timeout=timeout) as resp:
                data = resp.read()
                if data.startswith(b"\x1f\x8b"):
                    try:
                        data = gzip.decompress(data)
                    except Exception:
                        data = zlib.decompress(data, 16 + zlib.MAX_WBITS)
                elif resp.headers.get("Content-Encoding") == "deflate":
                    try:
                        data = zlib.decompress(data)
                    except Exception:
                        pass

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
            {"type_name": "国产传媒", "type_id": "/vodtype/domestic-media/"},
            {"type_name": "日本AV", "type_id": "/vodtype/japanese-av/"},
            {"type_name": "无码视频", "type_id": "/vodtype/uncensored-video/"},
            {"type_name": "中文字幕", "type_id": "/vodtype/chinese-subtitles/"}
        ]
        return {"class": classes}

    # ══════════════════════════════════════════════════════════
    # 2. 分类内容列表 (卡片槽级精准提取中文真实片名)
    # ══════════════════════════════════════════════════════════
    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = int(pg)
        except Exception:
            page = 1

        base_path = tid.strip()
        if page > 1:
            target_url = self._fix_url("%spage/%d/" % (base_path.rstrip("/"), page))
        else:
            target_url = self._fix_url(base_path)

        html = self._fetch(target_url)
        videos = []
        seen = set()

        if html:
            # 划定卡片槽位区块，包含图片与文字标题部分
            card_blocks = re.findall(
                r'(<(?:div|li|article)[^>]*>[\s\S]*?<a[^>]+href=["\'](/vodplay/[^"\']+)["\'][\s\S]*?</(?:div|li|article)>)',
                html,
                re.S
            )

            for block_html, play_href in card_blocks:
                full_play_url = self._fix_url(play_href)
                if full_play_url in seen:
                    continue

                # 1. 提取真实封面图
                pic = ""
                for attr in ["data-src", "src", "data-original"]:
                    m_pic = re.search(r'%s=["\']([^"\']+)["\']' % attr, block_html)
                    if m_pic:
                        c_pic = m_pic.group(1).strip()
                        if c_pic and not c_pic.startswith("data:") and not any(k in c_pic.lower() for k in ["logo", "icon", ".svg"]):
                            pic = c_pic
                            break

                if not pic:
                    continue

                # 2. 提取真实中文片名
                title = ""

                # 优先寻找跟随的文字节点 (h1-h4, p, span, 或带文本的独立 a 链接)
                # 排除纯数字、分类词和播放量标记
                tag_texts = re.findall(r'<(?:p|span|h[1-4]|a)[^>]*>([^<]+)</(?:p|span|h[1-4]|a)>', block_html)
                for txt in tag_texts:
                    clean_t = txt.strip()
                    # 必须包含中文字符，且排除已知噪音词
                    if re.search(r'[\u4e00-\u9fa5]', clean_t):
                        if not any(k in clean_t for k in ["国产传媒", "日本AV", "无码视频", "中文字幕", "P.", "播放"]):
                            title = clean_t
                            break

                # 备选寻找 title / alt 属性
                if not title:
                    m_title = re.search(r'title=["\']([^"\']+)["\']', block_html)
                    if m_title and re.search(r'[\u4e00-\u9fa5]', m_title.group(1)):
                        title = m_title.group(1).strip()

                if not title:
                    m_alt = re.search(r'alt=["\']([^"\']+)["\']', block_html)
                    if m_alt and re.search(r'[\u4e00-\u9fa5]', m_alt.group(1)):
                        title = m_alt.group(1).strip()

                # 若仍无法匹配到中文，格式化 URL slug 作为后备
                if not title:
                    slug = play_href.rstrip("/").split("/")[-1]
                    title = slug.replace("-", " ")

                # 3. 提取副标题/时长
                remark = ""
                m_rem = re.search(r'<(?:span|div|em|i)[^>]*class=["\'][^"\']*(?:duration|tag|badge|remarks)[^"\']*["\'][^>]*>(.*?)</', block_html, re.S)
                if m_rem:
                    clean_rem = re.sub(r'<[^>]+>', '', m_rem.group(1)).strip()
                    if clean_rem and len(clean_rem) <= 10:
                        remark = clean_rem

                seen.add(full_play_url)
                full_pic = self._fix_url(pic)
                if full_pic and "@" not in full_pic:
                    full_pic += "@Referer=" + self.siteUrl + "/"

                videos.append({
                    "vod_id": full_play_url,
                    "vod_name": title,
                    "vod_pic": full_pic,
                    "vod_remarks": remark if remark else ("P.%d" % page)
                })

        has_more = len(videos) > 0
        return {
            "list": videos,
            "page": page,
            "pagecount": page + 1 if has_more else page,
            "limit": len(videos),
            "total": 9999
        }

    # ══════════════════════════════════════════════════════════
    # 3. 详情解析 (优先 ld+json 原生标题与 m3u8 直链)
    # ══════════════════════════════════════════════════════════
    def detailContent(self, ids):
        vod_url = ids[0]
        html = self._fetch(vod_url)

        title = "影片详情"
        pic = ""
        desc = ""
        m3u8_url = ""

        if html:
            # 1. 优先提取 ld+json 原生标准信息
            ld_match = re.search(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>([\s\S]*?)</script>', html)
            if ld_match:
                try:
                    ld_data = json.loads(ld_match.group(1).strip())
                    if "name" in ld_data and ld_data["name"]:
                        title = ld_data["name"]
                    if "thumbnailUrl" in ld_data and ld_data["thumbnailUrl"]:
                        pic = ld_data["thumbnailUrl"]
                    if "description" in ld_data:
                        desc = ld_data["description"]
                    if "embedUrl" in ld_data and ld_data["embedUrl"]:
                        embed = ld_data["embedUrl"]
                        if "$" in embed:
                            m3u8_url = embed.split("$")[-1].strip()
                        else:
                            m3u8_url = embed.strip()
                except Exception:
                    pass

            # 2. 从 player_aaaa 提取直链
            if not m3u8_url or not self.isVideoFormat(m3u8_url):
                pa_match = re.search(r'player_aaaa\s*=\s*\{.*?"url"\s*:\s*"([^"]+)".*?\}', html, re.S)
                if pa_match:
                    raw_u = pa_match.group(1).replace("\\/", "/")
                    if self.isVideoFormat(raw_u):
                        m3u8_url = raw_u

            # 3. 扫描页面中的 m3u8 链接
            if not m3u8_url or not self.isVideoFormat(m3u8_url):
                all_m3u8 = re.findall(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html)
                for mu in all_m3u8:
                    clean_mu = mu.replace("\\/", "/").strip()
                    if not any(k in clean_mu.lower() for k in ["ad", "adv", "preview"]):
                        m3u8_url = clean_mu
                        break

            # 兜底片名
            if not title or title == "影片详情":
                t_m = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']', html)
                if t_m:
                    title = t_m.group(1).split("|")[0].strip()

            if not pic:
                p_m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html)
                if p_m:
                    pic = p_m.group(1)

        play_target = m3u8_url if m3u8_url else vod_url
        play_url = "正片$" + play_target

        pic_url = self._fix_url(pic) if pic else ""
        if pic_url and "@" not in pic_url:
            pic_url += "@Referer=" + self.siteUrl + "/"

        full_content = "【🔥官方交流群: %s】\n\n%s" % (self.tgGroup, desc if desc else "暂无剧情简介")

        return {
            "list": [{
                "vod_id": vod_url,
                "vod_name": title,
                "vod_pic": pic_url,
                "vod_actor": "🦋 TG群: @tvshare23 (点击【简介】获取链接)",
                "vod_director": "🦋 蝴蝶影视",
                "vod_remarks": "关注TG不迷路",
                "vod_content": full_content,
                "vod_play_from": "🦋 官方TG: @tvshare23",
                "vod_play_url": play_url
            }]
        }

    # ══════════════════════════════════════════════════════════
    # 4. 播放地址直出
    # ══════════════════════════════════════════════════════════
    def playerContent(self, flag, id, vipFlags):
        if self.isVideoFormat(id):
            parsed_media = urllib.parse.urlparse(id)
            media_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Origin": "%s://%s" % (parsed_media.scheme, parsed_media.netloc),
                "Referer": self.siteUrl + "/"
            }
            return {
                "parse": 0,
                "url": id,
                "header": json.dumps(media_headers)
            }

        html = self._fetch(id)
        ld_m = re.search(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>([\s\S]*?)</script>', html)
        if ld_m:
            try:
                data = json.loads(ld_m.group(1).strip())
                if "embedUrl" in data:
                    raw_embed = data["embedUrl"]
                    u = raw_embed.split("$")[-1].strip() if "$" in raw_embed else raw_embed.strip()
                    if self.isVideoFormat(u):
                        parsed_u = urllib.parse.urlparse(u)
                        return {
                            "parse": 0,
                            "url": u,
                            "header": json.dumps({
                                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                                "Origin": "%s://%s" % (parsed_u.scheme, parsed_u.netloc),
                                "Referer": self.siteUrl + "/"
                            })
                        }
            except Exception:
                pass

        all_m3u8 = re.findall(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html)
        if all_m3u8:
            real_url = all_m3u8[0].replace("\\/", "/").strip()
            parsed_u = urllib.parse.urlparse(real_url)
            return {
                "parse": 0,
                "url": real_url,
                "header": json.dumps({
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                    "Origin": "%s://%s" % (parsed_u.scheme, parsed_u.netloc),
                    "Referer": self.siteUrl + "/"
                })
            }

        return {
            "parse": 1,
            "url": id,
            "header": ""
        }

    # ══════════════════════════════════════════════════════════
    # 5. 搜索
    # ══════════════════════════════════════════════════════════
    def searchContent(self, key, quick, pg="1"):
        query = urllib.parse.quote(key)
        url = "%s/vodsearch/?wd=%s" % (self.siteUrl, query)
        return self.categoryContent(url, pg, False, {})