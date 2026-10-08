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
        self.siteUrl = "https://ukqfm.myacetweay.buzz"
        self.homePath = "/chu/"
        self.tgGroup = "https://t.me/tvshare23"
        self.brandActor = "🦋 TG群: @tvshare23"
        self.brandDirector = "🦋 蝴蝶影视"
        self._ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

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

        # 固化分类列表
        self.classList = [
            {"type_id": "1", "type_name": "国产传媒"},
            {"type_id": "2", "type_name": "国产视频"},
            {"type_id": "6", "type_name": "传媒自拍"},
            {"type_id": "160", "type_name": "成人动漫"},
            {"type_id": "9", "type_name": "日韩主播"},
            {"type_id": "3", "type_name": "国产主播"},
            {"type_id": "4", "type_name": "91大神"},
            {"type_id": "5", "type_name": "热门事件"},
            {"type_id": "7", "type_name": "日本有码"},
            {"type_id": "8", "type_name": "日本无码"},
            {"type_id": "10", "type_name": "动漫肉番"},
            {"type_id": "11", "type_name": "女同性恋"},
            {"type_id": "12", "type_name": "中文字幕"},
            {"type_id": "13", "type_name": "强奸乱伦"},
            {"type_id": "14", "type_name": "熟女人妻"},
            {"type_id": "15", "type_name": "制服诱惑"},
            {"type_id": "16", "type_name": "AV解说"},
            {"type_id": "17", "type_name": "女星换脸"},
            {"type_id": "444", "type_name": "欧美精品"}
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
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
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

        # 匹配所有包含 voddetail 的 <a> 标签块
        a_tags = re.findall(r'<a[^>]+href=["\']([^"\']*/voddetail/(\d+)/[^"\']*)["\'][^>]*>([\s\S]*?)</a>', html, re.I)
        for href, vod_id, inner_html in a_tags:
            # 过滤纯文本链接，确保卡片带有图片
            img_match = re.search(r'<img[^>]+>', inner_html, re.I)
            if not img_match:
                continue

            if vod_id in seen_ids:
                continue
            seen_ids.add(vod_id)

            img_tag = img_match.group(0)

            # 提取封面
            pic = ""
            data_src = re.search(r'data-src=["\']([^"\']+)["\']', img_tag, re.I)
            data_orig = re.search(r'data-original=["\']([^"\']+)["\']', img_tag, re.I)
            src = re.search(r'src=["\']([^"\']+)["\']', img_tag, re.I)

            if data_src:
                pic = data_src.group(1)
            elif data_orig:
                pic = data_orig.group(1)
            elif src:
                pic = src.group(1)

            # 过滤占位图
            if pic and ("data:image" in pic or "load.png" in pic or "placeholder" in pic or "dancing.gif" in pic):
                pic = ""

            # 提取标题
            title = ""
            m_title_attr = re.search(r'title=["\']([^"\']+)["\']', inner_html, re.I)
            m_alt = re.search(r'alt=["\']([^"\']+)["\']', img_tag, re.I)
            if m_title_attr:
                title = m_title_attr.group(1)
            elif m_alt:
                title = m_alt.group(1)
            else:
                clean_inner = re.sub(r'<[^>]+>', '', inner_html).strip()
                title = clean_inner

            # 提取副标题 remarks
            remarks = ""
            aux_match = re.search(r'<span[^>]+class=["\'][^"\']*item-auxiliary[^"\']*["\'][^>]*>[\s\S]*?<small[^>]*>([\s\S]*?)</small>', inner_html, re.I)
            if aux_match:
                remarks = re.sub(r'<[^>]+>', '', aux_match.group(1)).strip()
            else:
                tag_match = re.search(r'class=["\'][^"\']*(?:tag|duration|remarks)[^"\']*["\'][^>]*>([\s\S]*?)<', inner_html, re.I)
                if tag_match:
                    remarks = re.sub(r'<[^>]+>', '', tag_match.group(1)).strip()

            clean_title = self._unesc(re.sub(r'<[^>]+>', '', title)).strip()
            if clean_title:
                list_data.append({
                    "vod_id": self._encode_id(vod_id),
                    "vod_name": clean_title,
                    "vod_pic": self._fix_url(pic.strip()),
                    "vod_remarks": self._unesc(remarks)
                })

        return list_data

    def _parse_page_count(self, html):
        pages = re.findall(r'/vodtype/\d+-(\d+)/', html)
        last_page = 1
        for p in pages:
            try:
                val = int(p)
                if val > last_page:
                    last_page = val
            except Exception:
                pass
        return last_page

    def _extract_play_url(self, vid):
        play_page_url = "%s/vodplay/%s-1-1/" % (self.siteUrl, vid)
        res = self._fetch(play_page_url, referer=self.siteUrl + "/")
        html_text = res.get("text", "")

        # 匹配 player_data JSON 对象
        m = re.search(r'player_data\s*=\s*(\{[\s\S]+?\})\s*;?\s*</script>', html_text, re.I)
        if not m:
            m = re.search(r'player_data\s*=\s*(\{[^<]+\})', html_text, re.I)

        if m:
            try:
                raw_json = m.group(1).strip().rstrip(";")
                player_data = json.loads(raw_json)
                raw_url = player_data.get("url", "")
                encrypt = str(player_data.get("encrypt", "0"))

                if encrypt == "1":
                    raw_url = urllib.parse.unquote(raw_url)
                elif encrypt == "2":
                    try:
                        raw_url = urllib.parse.unquote(base64.b64decode(raw_url).decode("utf-8", errors="ignore"))
                    except Exception:
                        pass

                raw_url = raw_url.replace(r"\/", "/")
                if raw_url:
                    return "播放$" + raw_url
            except Exception:
                pass

        # 正则兜底提取直链
        m_stream = re.search(r'https?://[^"\'\s<>\\]+\.(?:m3u8|mp4)[^"\'\s<>\\]*', html_text)
        if m_stream:
            return "播放$" + m_stream.group(0).replace(r"\/", "/")

        return ""

    # 1. 首页：纯内存静态返回
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
            req_url = "%s/vodtype/%s-%d/" % (self.siteUrl, tid_str, pg_int)
        else:
            req_url = "%s/vodtype/%s/" % (self.siteUrl, tid_str)

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

    # 3. 详情页
    def detailContent(self, ids):
        raw_id_param = ids[0] if isinstance(ids, (list, tuple)) else str(ids)
        real_id = self._decode_id(raw_id_param)

        detail_url = "%s/voddetail/%s/" % (self.siteUrl, real_id)
        res = self._fetch(detail_url, referer=self.siteUrl + "/")
        html_text = res.get("text", "")

        # 标题提取
        vod_name = ""
        m_name = re.search(r'<div[^>]+class=["\'][^"\']*detail-info-wrapper[^"\']*["\'][^>]*>[\s\S]*?<h[12][^>]*>([\s\S]*?)</h[12]>', html_text, re.I)
        if m_name:
            vod_name = re.sub(r'<[^>]+>', '', m_name.group(1)).strip()
        if not vod_name:
            m_h = re.search(r'<h[12][^>]*>([\s\S]*?)</h[12]>', html_text, re.I)
            if m_h:
                vod_name = re.sub(r'<[^>]+>', '', m_h.group(1)).strip()
        if not vod_name:
            m_title = re.search(r'<title>(.*?)</title>', html_text, re.I)
            if m_title:
                vod_name = re.sub(r'\s*[-—–]\s*[^-]*$', '', m_title.group(1)).strip()

        # 封面提取
        vod_pic = ""
        m_cover = re.search(r'<div[^>]+class=["\'][^"\']*detail-image-wrapper[^"\']*["\'][^>]*>[\s\S]*?<img[^>]+>', html_text, re.I)
        img_tag = m_cover.group(0) if m_cover else ""
        if not img_tag:
            m_img = re.search(r'<img[^>]+(?:data-src|data-original)=["\'][^"\']+["\'][^>]*>', html_text, re.I)
            if m_img:
                img_tag = m_img.group(0)

        if img_tag:
            d_src = re.search(r'data-src=["\']([^"\']+)["\']', img_tag, re.I)
            d_orig = re.search(r'data-original=["\']([^"\']+)["\']', img_tag, re.I)
            d_s = re.search(r'src=["\']([^"\']+)["\']', img_tag, re.I)
            if d_src:
                vod_pic = d_src.group(1)
            elif d_orig:
                vod_pic = d_orig.group(1)
            elif d_s:
                vod_pic = d_s.group(1)

        # 简介提取
        clean_content = ""
        m_desc = re.search(r'<div[^>]+class=["\'][^"\']*(?:content|vod-content|desc|description|summary|detail-content)[^"\']*["\'][^>]*>([\s\S]*?)</div>', html_text, re.I)
        if m_desc:
            clean_content = re.sub(r'<[^>]+>', '', m_desc.group(1)).strip()

        # 规范简介排版
        custom_notice = "【💡 温馨提示：视频加载如遇卡顿请尝试切换线路或快进。】"
        group_info = "【🔥 官方交流群: %s】" % self.tgGroup
        if clean_content:
            vod_content = "%s\n\n%s\n\n%s" % (group_info, custom_notice, clean_content)
        else:
            vod_content = "%s\n\n%s\n\n暂无详细简介，欢迎加入TG群获取最新资源！" % (group_info, custom_notice)

        # 逆向解析二级播放页真实直链
        vod_play_url = self._extract_play_url(real_id)

        return {
            "list": [{
                "vod_id": raw_id_param,
                "vod_name": self._unesc(vod_name) if vod_name else "未知片名",
                "vod_pic": self._fix_url(vod_pic.strip()),
                "vod_type_name": "",
                "vod_year": "",
                "vod_area": "",
                "vod_remarks": "",
                "vod_actor": self.brandActor,
                "vod_director": self.brandDirector,
                "vod_content": vod_content,
                "vod_play_from": "8K精品视频",
                "vod_play_url": vod_play_url if vod_play_url else "在线播放$http://127.0.0.1"
            }]
        }

    # 4. 播放器：保持 parse: 0，纯净直连
    def playerContent(self, flag, id, vipFlags):
        play_url = str(id).strip()
        return {
            "parse": 0,
            "playUrl": "",
            "url": play_url,
            "header": json.dumps({
                "User-Agent": self._ua,
                "Referer": self.siteUrl + "/"
            })
        }

    # 5. 搜索模块
    def searchContent(self, key, quick, pg="1"):
        wd = (key or "").strip()
        if not wd:
            return {"list": [], "page": 1, "pagecount": 1, "limit": 0, "total": 0}

        pg_int = 1
        try:
            pg_int = int(pg)
        except Exception:
            pass

        search_url = "%s/vodsearch/%s-------------.html" % (self.siteUrl, urllib.parse.quote(wd))
        res = self._fetch(search_url, referer=self.siteUrl + "/")
        html_text = res.get("text", "")

        vod_list = self._parse_list_html(html_text)

        return {
            "list": vod_list,
            "page": pg_int,
            "pagecount": 1,
            "limit": len(vod_list),
            "total": len(vod_list)
        }