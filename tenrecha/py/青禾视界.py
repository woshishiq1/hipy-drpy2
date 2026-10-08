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
        self.siteUrl = "https://msdtcd6h.student29.xyz"
        self.tgGroup = "https://t.me/tvshare23"
        self.brandActor = "🦋 TG群: @tvshare23"
        self.brandDirector = "🦋 蝴蝶影视"
        self._ua = "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"

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

        # 固化 32 个分类
        self.classList = [
            {"type_id": "55",  "type_name": "偷拍自拍"},
            {"type_id": "63",  "type_name": "国产制作"},
            {"type_id": "58",  "type_name": "乱伦三观"},
            {"type_id": "60",  "type_name": "嫖妓过程"},
            {"type_id": "57",  "type_name": "淫乱学妹"},
            {"type_id": "65",  "type_name": "黑料打烊"},
            {"type_id": "61",  "type_name": "主播网红"},
            {"type_id": "80",  "type_name": "高清无码"},
            {"type_id": "81",  "type_name": "中文字幕"},
            {"type_id": "20",  "type_name": "媚黑母狗"},
            {"type_id": "25",  "type_name": "3D动漫"},
            {"type_id": "26",  "type_name": "剧情故事"},
            {"type_id": "105", "type_name": "麻豆视频"},
            {"type_id": "106", "type_name": "91制片厂"},
            {"type_id": "107", "type_name": "天美传媒"},
            {"type_id": "108", "type_name": "蜜桃传媒"},
            {"type_id": "110", "type_name": "星空传媒"},
            {"type_id": "111", "type_name": "精东影业"},
            {"type_id": "112", "type_name": "乐播传媒"},
            {"type_id": "113", "type_name": "兔子先生"},
            {"type_id": "92",  "type_name": "国产精品"},
            {"type_id": "93",  "type_name": "华语AV"},
            {"type_id": "94",  "type_name": "黑料吃瓜"},
            {"type_id": "95",  "type_name": "欧美精品"},
            {"type_id": "96",  "type_name": "动漫禁漫"},
            {"type_id": "97",  "type_name": "学生合集"},
            {"type_id": "98",  "type_name": "乱伦精品"},
            {"type_id": "99",  "type_name": "探花约炮"},
            {"type_id": "100", "type_name": "日本无码"},
            {"type_id": "101", "type_name": "日本有码"},
            {"type_id": "102", "type_name": "主播网红"},
            {"type_id": "103", "type_name": "日本素人"}
        ]
        self.filters = {}

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
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
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
            return {"code": -1, "text": "", "err": "Exception: %s" % str(e)}

    def _unesc(self, s):
        try:
            return html_lib.unescape(s or "").strip()
        except Exception:
            return (s or "").strip()

    def _fix_url(self, u):
        if not u:
            return ""
        if u.startswith("http"):
            return u
        if u.startswith("//"):
            return "https:" + u
        if u.startswith("/"):
            return self.siteUrl + u
        return u

    def _encode_id(self, raw_id):
        safe_str = base64.urlsafe_b64encode(str(raw_id).encode("utf-8")).decode("utf-8").rstrip("=")
        return "v_" + safe_str

    def _decode_id(self, safe_id):
        if not str(safe_id).startswith("v_"):
            return str(safe_id)
        b64_str = str(safe_id)[2:]
        pad = len(b64_str) % 4
        if pad:
            b64_str += "=" * (4 - pad)
        try:
            return base64.urlsafe_b64decode(b64_str.encode("utf-8")).decode("utf-8")
        except Exception:
            return str(safe_id)

    def _parse_list_html(self, html):
        list_data = []
        seen_ids = set()

        # 匹配 <li> 块
        li_blocks = re.findall(r'<li[^>]*>([\s\S]*?)</li>', html, re.I)
        for li in li_blocks:
            m_link = re.search(r'<a[^>]+href=["\']([^"\']*/voddetail/(\d+)\.html)["\'][^>]*>([\s\S]*?)</a>', li, re.I)
            if not m_link:
                continue

            href, vod_id, inner = m_link.group(1), m_link.group(2), m_link.group(3)
            if vod_id in seen_ids:
                continue

            # 提取标题：优先 h2，其次 a[title]，再取文本
            title = ""
            m_h2 = re.search(r'<h2[^>]*>([\s\S]*?)</h2>', li, re.I)
            if m_h2:
                title = re.sub(r'<[^>]+>', '', m_h2.group(1)).strip()
            if not title:
                m_t = re.search(r'title=["\']([^"\']+)["\']', m_link.group(0), re.I)
                if m_t:
                    title = m_t.group(1)
            if not title:
                title = re.sub(r'<[^>]+>', '', inner).strip()

            # 提取封面：优先 data-src，过滤 loading.gif 等占位图
            pic = ""
            m_img = re.search(r'<img[^>]+>', li, re.I)
            if m_img:
                img_tag = m_img.group(0)
                d_src = re.search(r'data-src=["\']([^"\']+)["\']', img_tag, re.I)
                d_orig = re.search(r'data-original=["\']([^"\']+)["\']', img_tag, re.I)
                src = re.search(r'src=["\']([^"\']+)["\']', img_tag, re.I)
                if d_src:
                    pic = d_src.group(1)
                elif d_orig:
                    pic = d_orig.group(1)
                elif src and "loading" not in src.group(1) and "template/" not in src.group(1):
                    pic = src.group(1)

            clean_title = self._unesc(title)
            if clean_title:
                seen_ids.add(vod_id)
                list_data.append({
                    "vod_id": self._encode_id(vod_id),
                    "vod_name": clean_title,
                    "vod_pic": self._fix_url(pic.strip()),
                    "vod_remarks": ""
                })

        # 兜底：直接扫描整个页面的 /voddetail/ 链接
        if not list_data:
            fallback_links = re.findall(r'<a[^>]+href=["\']([^"\']*/voddetail/(\d+)\.html)["\'][^>]*>([\s\S]*?)</a>', html, re.I)
            for href, vod_id, inner in fallback_links:
                if vod_id in seen_ids:
                    continue
                clean_title = self._unesc(re.sub(r'<[^>]+>', '', inner)).strip()
                if clean_title:
                    seen_ids.add(vod_id)
                    list_data.append({
                        "vod_id": self._encode_id(vod_id),
                        "vod_name": clean_title,
                        "vod_pic": "",
                        "vod_remarks": ""
                    })

        return list_data

    def _parse_page_count(self, html):
        pages = re.findall(r'/vodtype/\d+-(\d+)\.html', html)
        last_page = 1
        for p in pages:
            try:
                val = int(p)
                if val > last_page:
                    last_page = val
            except Exception:
                pass
        return last_page

    def _parse_search_page_count(self, html):
        pages = re.findall(r'/vodsearch/.*------------(\d+)---/', html)
        last_page = 1
        for p in pages:
            try:
                val = int(p)
                if val > last_page:
                    last_page = val
            except Exception:
                pass
        return last_page

    def _extract_m3u8_from_play_html(self, html):
        # 匹配 player_aaaa 或 player_data
        m = re.search(r'(?:player_aaaa|player_data)\s*=\s*(\{[\s\S]+?\})\s*;?\s*</script>', html, re.I)
        if not m:
            m = re.search(r'(?:player_aaaa|player_data)\s*=\s*(\{[^\n<]*\})', html, re.I)

        if m:
            try:
                player_data = json.loads(m.group(1))
                video_url = player_data.get("url", "")
                enc = player_data.get("encrypt", 0)

                # encrypt == 1 为 URL 编码
                if (enc == 1 or enc == "1") and video_url:
                    video_url = urllib.parse.unquote(video_url)
                elif (enc == 2 or enc == "2") and video_url:
                    try:
                        video_url = urllib.parse.unquote(base64.b64decode(video_url).decode("utf-8", errors="ignore"))
                    except Exception:
                        pass

                video_url = video_url.replace(r"\/", "/")
                if video_url:
                    return video_url
            except Exception:
                pass

        # 兜底：直接提取包含 m3u8 的 JSON 字段或 URL
        m_json = re.search(r'["\']url["\']\s*:\s*["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', html, re.I)
        if m_json:
            return m_json.group(1).replace(r"\/", "/")

        m_direct = re.search(r'(https?:\\?/\\?/[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html, re.I)
        if m_direct:
            return m_direct.group(1).replace(r"\/", "/")

        return ""

    # 1. 首页：纯内存毫秒级返回
    def homeContent(self, *args, **kwargs):
        return {
            "class": self.classList,
            "filters": self.filters
        }

    # 2. 分类列表页
    def categoryContent(self, tid, pg, *args, **kwargs):
        pg_int = 1
        try:
            pg_int = int(pg)
        except Exception:
            pass

        tid_str = str(tid).strip("/")
        if pg_int > 1:
            req_url = "%s/vodtype/%s-%d.html" % (self.siteUrl, tid_str, pg_int)
        else:
            req_url = "%s/vodtype/%s.html" % (self.siteUrl, tid_str)

        res = self._fetch(req_url, referer=self.siteUrl + "/")
        html_text = res.get("text", "")

        vod_list = self._parse_list_html(html_text)
        page_count = self._parse_page_count(html_text)

        return {
            "list": vod_list,
            "page": pg_int,
            "pagecount": page_count,
            "limit": 20,
            "total": page_count * 20
        }

    # 3. 详情页：二级播放页预解析直链，标准简介排版
    def detailContent(self, ids):
        raw_id_param = ids[0] if isinstance(ids, (list, tuple)) else str(ids)
        real_id = self._decode_id(raw_id_param)

        detail_url = "%s/voddetail/%s.html" % (self.siteUrl, real_id)
        res = self._fetch(detail_url, referer=self.siteUrl + "/")
        html_text = res.get("text", "")

        # 提取标题
        vod_name = ""
        h1_matches = re.findall(r'<h1[^>]*>([\s\S]*?)</h1>', html_text, re.I)
        if len(h1_matches) >= 2:
            vod_name = re.sub(r'<[^>]+>', '', h1_matches[1]).strip()
        elif h1_matches:
            vod_name = re.sub(r'<[^>]+>', '', h1_matches[0]).strip()
        if not vod_name:
            m_title = re.search(r'<title>([^<]+)</title>', html_text, re.I)
            if m_title:
                vod_name = re.sub(r'详情介.*$', '', m_title.group(1)).strip()

        # 提取封面
        vod_pic = ""
        m_upload_pic = re.search(r'<img[^>]+(?:data-src|data-original)=["\']([^"\']*upload/vod/[^"\']+)["\']', html_text, re.I)
        if m_upload_pic:
            vod_pic = m_upload_pic.group(1)
        else:
            m_any_pic = re.search(r'<img[^>]+(?:data-src|data-original)=["\']([^"\']+)["\']', html_text, re.I)
            if m_any_pic:
                vod_pic = m_any_pic.group(1)

        # 提取简介
        clean_content = ""
        m_desc = re.search(r'<div[^>]+class=["\'][^"\']*(?:content|vod_content|detail-content|info)[^"\']*["\'][^>]*>([\s\S]*?)</div>', html_text, re.I)
        if m_desc:
            clean_content = re.sub(r'<[^>]+>', '', m_desc.group(1)).strip()

        # 提取类型
        type_name = ""
        m_type = re.search(r'<div[^>]+class=["\'][^"\']*(?:category|type)[^"\']*["\'][^>]*>([\s\S]*?)</div>', html_text, re.I)
        if m_type:
            type_name = re.sub(r'<[^>]+>', '', m_type.group(1)).strip()

        # 规范简介排版
        custom_notice = "【💡 温馨提示：视频加载如遇卡顿请尝试切换线路或快进。】"
        group_info = "【🔥 官方交流群: %s】" % self.tgGroup
        if clean_content:
            vod_content = "%s\n\n%s\n\n%s" % (group_info, custom_notice, clean_content)
        else:
            vod_content = "%s\n\n%s\n\n暂无详细简介，欢迎加入TG群获取最新资源！" % (group_info, custom_notice)

        # 提取二级选集链接
        play_links = []
        first_play_path = ""
        raw_play_a = re.findall(r'<a[^>]+href=["\']([^"\']*/vodplay/(\d+-\d+-\d+)\.html)["\'][^>]*>([\s\S]*?)</a>', html_text, re.I)
        for href, slug, name_html in raw_play_a:
            ep_name = re.sub(r'<[^>]+>', '', name_html).strip() or "点击播放"
            entry = "%s$%s" % (ep_name, href)
            if entry not in play_links:
                play_links.append(entry)
                if not first_play_path:
                    first_play_path = href

        # 预解析第一集直链
        if play_links and first_play_path:
            full_play_url = self._fix_url(first_play_path)
            res_play = self._fetch(full_play_url, referer=detail_url)
            m3u8_url = self._extract_m3u8_from_play_html(res_play.get("text", ""))
            if m3u8_url:
                ep_name0 = play_links[0].split("$")[0]
                play_links[0] = "%s$%s" % (ep_name0, m3u8_url)

        vod_play_url = "#".join(play_links) if play_links else ("点击播放$/vodplay/%s-1-1.html" % real_id)

        return {
            "list": [{
                "vod_id": raw_id_param,
                "vod_name": self._unesc(vod_name) if vod_name else "未知片名",
                "vod_pic": self._fix_url(vod_pic.strip()),
                "vod_type_name": type_name,
                "vod_year": "",
                "vod_area": type_name,
                "vod_remarks": "",
                "vod_actor": self.brandActor,
                "vod_director": self.brandDirector,
                "vod_content": vod_content,
                "vod_play_from": "学生合集",
                "vod_play_url": vod_play_url
            }]
        }

    # 4. 播放器：安全直连，杜绝嗅探引起的崩溃
    def playerContent(self, flag, id, vipFlags):
        play_id = str(id).strip()

        # 详情页已预解出直链
        if play_id.startswith("http") and (".m3u8" in play_id or ".mp4" in play_id):
            return {
                "parse": 0,
                "playUrl": "",
                "url": play_id,
                "header": json.dumps({
                    "User-Agent": self._ua,
                    "Referer": self.siteUrl + "/",
                    "Origin": self.siteUrl
                })
            }

        full_play_url = self._fix_url(play_id)
        res = self._fetch(full_play_url, referer=self.siteUrl + "/")
        extracted = self._extract_m3u8_from_play_html(res.get("text", ""))

        target_url = extracted if extracted else full_play_url

        return {
            "parse": 0,
            "playUrl": "",
            "url": target_url,
            "header": json.dumps({
                "User-Agent": self._ua,
                "Referer": self.siteUrl + "/",
                "Origin": self.siteUrl
            })
        }

    # 5. 搜索模块：对齐12段搜索路由
    def searchContent(self, key, quick, pg="1"):
        wd = (key or "").strip()
        if not wd:
            return {"list": [], "page": 1, "pagecount": 1, "limit": 0, "total": 0}

        pg_int = 1
        try:
            pg_int = int(pg)
        except Exception:
            pass

        kw_encoded = urllib.parse.quote(wd)
        search_url = "%s/vodsearch/%s------------%d---/" % (self.siteUrl, kw_encoded, pg_int)

        res = self._fetch(search_url, referer=self.siteUrl + "/")
        html_text = res.get("text", "")

        vod_list = self._parse_list_html(html_text)
        page_count = self._parse_search_page_count(html_text)

        return {
            "list": vod_list,
            "page": pg_int,
            "pagecount": page_count,
            "limit": len(vod_list),
            "total": page_count * 20
        }