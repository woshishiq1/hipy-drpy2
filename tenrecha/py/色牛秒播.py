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
        # 多域名故障轮询池
        self.domains = [
            "https://8.seniu1086.cc:8888",
            "https://8.seniu1085.cc:8888",
            "https://8.seniu958.cc:8888",
            "https://8.seniu959.cc:8888"
        ]
        self.currentDomain = "https://8.seniu1086.cc:8888"

        # 品牌版权规范
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
            {"type_id": "6",  "type_name": "国产传媒"},
            {"type_id": "7",  "type_name": "偷拍自拍"},
            {"type_id": "35", "type_name": "绿帽偷情"},
            {"type_id": "36", "type_name": "JK萝莉"},
            {"type_id": "37", "type_name": "强奸迷奸"},
            {"type_id": "38", "type_name": "网红主播"},
            {"type_id": "39", "type_name": "吃瓜黑料"},
            {"type_id": "10", "type_name": "日韩无码"},
            {"type_id": "11", "type_name": "中文字幕"},
            {"type_id": "12", "type_name": "日韩杂类"},
            {"type_id": "19", "type_name": "欧美无码"},
            {"type_id": "20", "type_name": "黑白专区"},
            {"type_id": "23", "type_name": "少女动漫"},
            {"type_id": "30", "type_name": "网爆黑料"}
        ]
        self.filters = {}

    def init(self, extend=""):
        return True

    def isVideoFormat(self, url):
        low = (url or "").lower()
        return any(k in low for k in (".m3u8", ".mp4", ".flv", ".mkv", ".avi", ".ts"))

    def manualVideoCheck(self):
        return False

    def _fetch(self, target_url, referer="", raw_bytes=False):
        if not target_url:
            return {"code": 0, "text": "", "bytes": b"", "err": "URL 为空"}
        if target_url.startswith("/"):
            target_url = self.currentDomain + target_url

        headers = {
            "User-Agent": self._ua,
            "Referer": referer if referer else (self.currentDomain + "/"),
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
                if raw_bytes:
                    return {"code": code, "bytes": raw, "err": ""}
                try:
                    text = raw.decode("utf-8")
                except Exception:
                    text = raw.decode("latin1", errors="ignore")
                return {"code": code, "text": text, "bytes": raw, "err": ""}
        except urllib.error.HTTPError as e:
            err_body = ""
            try:
                raw_err = e.read()
                if raw_err.startswith(b"\x1f\x8b"):
                    raw_err = gzip.decompress(raw_err)
                err_body = raw_err.decode("utf-8", errors="ignore")
            except Exception:
                pass
            return {"code": e.code, "text": err_body, "bytes": b"", "err": "HTTPError: %s" % str(e)}
        except Exception as e:
            return {"code": -1, "text": "", "bytes": b"", "err": "Exception: %s" % str(e)}

    def _is_landing_page(self, html):
        return ("发布页" in html) and (("enter-maomi" in html) or ("enter-link" in html))

    # 多域名故障轮询与假封面穿透
    def _fetch_html(self, path):
        domain_list = [self.currentDomain] + [d for d in self.domains if d != self.currentDomain]
        for domain in domain_list:
            full_url = domain + path if path.startswith("/") else (domain + "/" + path)
            res = self._fetch(full_url, referer=domain + "/")
            html_text = res.get("text", "")
            if html_text and not self._is_landing_page(html_text):
                if domain != self.currentDomain:
                    self.currentDomain = domain
                return html_text
        return ""

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
            return self.currentDomain + u
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

    def _format_duration(self, seconds):
        try:
            sec = int(seconds)
            if sec <= 0:
                return ""
            h = sec // 3600
            m = (sec % 3600) // 60
            s = sec % 60
            if h > 0:
                return "%d:%02d:%02d" % (h, m, s)
            return "%d:%02d" % (m, s)
        except Exception:
            return ""

    # .dat 加密封面代理 URL 生成
    def _proxy_image_url(self, url):
        if not url:
            return ""
        full_url = self._fix_url(url)
        if ".dat" not in full_url:
            return full_url
        b64_url = base64.urlsafe_b64encode(full_url.encode("utf-8")).decode("utf-8").rstrip("=")
        return "http://127.0.0.1:9978/proxy?do=js&url=%s" % b64_url

    def _parse_list_html(self, html):
        list_data = []
        seen_ids = set()

        # 匹配包含 /play/ 的 a 标签卡片块
        cards = re.findall(r'<a[^>]+href=["\']([^"\']*/play/[^"\']*)["\'][^>]*>([\s\S]*?)</a>', html, re.I)
        for href, inner in cards:
            vod_id = href.strip()
            if not vod_id or vod_id in seen_ids:
                continue

            # 提取标题
            title = ""
            m_rt = re.search(r'class=["\'][^"\']*rank-title[^"\']*["\'][^>]*>([\s\S]*?)</', inner, re.I)
            if m_rt:
                title = re.sub(r'<[^>]+>', '', m_rt.group(1)).strip()
            if not title:
                m_t = re.search(r'title=["\']([^"\']+)["\']', inner, re.I)
                if m_t:
                    title = m_t.group(1)
            if not title:
                title = re.sub(r'<[^>]+>', '', inner).strip()

            # 提取封面
            pic = ""
            m_orig = re.search(r'data-original=["\']([^"\']+)["\']', inner, re.I)
            m_src = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', inner, re.I)
            if m_orig:
                pic = m_orig.group(1)
            elif m_src:
                pic = m_src.group(1)

            vod_pic = self._proxy_image_url(pic)

            # 提取时长 / remarks
            remarks = ""
            m_dur = re.search(r'secondsToHMS\((\d+)\)', inner)
            if m_dur:
                remarks = self._format_duration(m_dur.group(1))
            if not remarks:
                m_hits = re.search(r'class=["\'][^"\']*pre-hits[^"\']*["\'][^>]*>[\s\S]*?<span[^>]*>([\s\S]*?)</span>', inner, re.I)
                if m_hits:
                    remarks = re.sub(r'[\s\u00a0]', '', re.sub(r'<[^>]+>', '', m_hits.group(1)))

            clean_title = self._unesc(title)
            if clean_title:
                seen_ids.add(vod_id)
                list_data.append({
                    "vod_id": self._encode_id(vod_id),
                    "vod_name": clean_title,
                    "vod_pic": vod_pic,
                    "vod_remarks": self._unesc(remarks)
                })

        page_count = 1
        m_total = re.search(r'var\s+total\s*=\s*parseInt\((\d+)\)', html)
        if m_total:
            try:
                page_count = int(m_total.group(1))
            except Exception:
                pass

        return {"list": list_data, "pagecount": page_count}

    # 1. 首页：纯内存毫秒级返回，零网络阻塞
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
        path = "/type/%s" % tid_str
        if pg_int > 1:
            path += "/%d" % pg_int

        html_text = self._fetch_html(path)
        parsed = self._parse_list_html(html_text)

        vod_list = parsed.get("list", [])
        page_count = parsed.get("pagecount", 1)

        return {
            "list": vod_list,
            "page": pg_int,
            "pagecount": page_count,
            "limit": len(vod_list),
            "total": page_count * 20
        }

    # 3. 详情页
    def detailContent(self, ids):
        raw_id_param = ids[0] if isinstance(ids, (list, tuple)) else str(ids)
        real_path = self._decode_id(raw_id_param)

        if real_path.startswith("http"):
            real_path = re.sub(r'^https?://[^/]+', '', real_path)
        if not real_path.startswith("/"):
            real_path = "/" + real_path

        html_text = self._fetch_html(real_path)

        # 提取标题
        vod_name = ""
        m_title = re.search(r'class=["\'][^"\']*video-title[^"\']*["\'][^>]*>([\s\S]*?)</', html_text, re.I)
        if m_title:
            vod_name = re.sub(r'<[^>]+>', '', m_title.group(1)).strip()
        if not vod_name:
            m_t = re.search(r'<title>(.*?)</title>', html_text, re.I)
            if m_t:
                vod_name = re.sub(r'\s*[-—–]\s*[^-]*$', '', m_t.group(1)).strip()

        # 提取封面
        vod_pic = ""
        m_orig = re.search(r'data-original=["\']([^"\']+)["\']', html_text, re.I)
        m_src = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', html_text, re.I)
        if m_orig:
            vod_pic = self._proxy_image_url(m_orig.group(1))
        elif m_src:
            vod_pic = self._proxy_image_url(m_src.group(1))

        # 规范简介排版
        custom_notice = "【💡 温馨提示：视频加载如遇卡顿请尝试切换线路或快进。】"
        group_info = "【🔥 官方交流群: %s】" % self.tgGroup
        vod_content = "%s\n\n%s\n\n暂无详细简介，欢迎加入TG群获取最新资源！" % (group_info, custom_notice)

        # 选集与播放路径
        vod_play_url = "正片$%s" % real_path

        return {
            "list": [{
                "vod_id": raw_id_param,
                "vod_name": self._unesc(vod_name) if vod_name else "未知片名",
                "vod_pic": vod_pic,
                "vod_type_name": "",
                "vod_year": "",
                "vod_area": "",
                "vod_remarks": "",
                "vod_actor": self.brandActor,
                "vod_director": self.brandDirector,
                "vod_content": vod_content,
                "vod_play_from": "色牛秒播",
                "vod_play_url": vod_play_url
            }]
        }

    # 4. 播放器：多重正则逆向 m3u8 直链，绝不开启 parse: 1
    def playerContent(self, flag, id, vipFlags):
        play_target = str(id).strip()

        # 已经是直链
        if play_target.startswith("http") and (".m3u8" in play_target):
            return {
                "parse": 0,
                "playUrl": "",
                "url": play_target,
                "header": json.dumps({
                    "User-Agent": self._ua,
                    "Referer": self.currentDomain + "/"
                })
            }

        path = play_target
        if path.startswith("http"):
            path = re.sub(r'^https?://[^/]+', '', path)
        if not path.startswith("/"):
            path = "/" + path

        html_text = self._fetch_html(path)

        # 规则 1: var url = "(...m3u8...)"
        m1 = re.search(r'var\s+url\s*=\s*["\'](https?:[^"\']+\.m3u8[^"\']*)["\']', html_text, re.I)
        if m1:
            return {
                "parse": 0,
                "playUrl": "",
                "url": m1.group(1).replace(r"\/", "/"),
                "header": json.dumps({"User-Agent": self._ua, "Referer": self.currentDomain + "/"})
            }

        # 规则 2: "(...m3u8...)"
        m2 = re.search(r'["\'](https?:[^"\']+\.m3u8[^"\']*)["\']', html_text, re.I)
        if m2:
            return {
                "parse": 0,
                "playUrl": "",
                "url": m2.group(1).replace(r"\/", "/"),
                "header": json.dumps({"User-Agent": self._ua, "Referer": self.currentDomain + "/"})
            }

        # 规则 3: 正则全局提取流地址
        m3 = re.search(r'(https?:\\?/\\?/[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html_text, re.I)
        if m3:
            return {
                "parse": 0,
                "playUrl": "",
                "url": m3.group(1).replace(r"\/", "/"),
                "header": json.dumps({"User-Agent": self._ua, "Referer": self.currentDomain + "/"})
            }

        # 规则 4: iframe 直链提取
        m_iframe = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', html_text, re.I)
        if m_iframe:
            return {
                "parse": 0,
                "playUrl": "",
                "url": self._fix_url(m_iframe.group(1)),
                "header": json.dumps({"User-Agent": self._ua, "Referer": self.currentDomain + "/"})
            }

        return {
            "parse": 0,
            "playUrl": "",
            "url": self.currentDomain + path,
            "header": json.dumps({"User-Agent": self._ua, "Referer": self.currentDomain + "/"})
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

        path = "/search/%s" % urllib.parse.quote(wd)
        html_text = self._fetch_html(path)

        parsed = self._parse_list_html(html_text)
        vod_list = parsed.get("list", [])
        page_count = parsed.get("pagecount", 1)

        return {
            "list": vod_list,
            "page": pg_int,
            "pagecount": page_count,
            "limit": len(vod_list),
            "total": page_count * 20
        }

    # 6. TVBox 原生封面代理接口（处理 .dat base64 图片文件）
    def localProxy(self, param):
        url = ""
        if isinstance(param, dict):
            url = param.get("url", "")
        elif isinstance(param, str):
            url = param

        if not url:
            return [500, "text/plain", b""]

        decoded_url = ""
        try:
            pad = len(url) % 4
            padded = url + ("=" * (4 - pad) if pad else "")
            decoded_url = base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8")
        except Exception:
            try:
                decoded_url = urllib.parse.unquote(url)
            except Exception:
                decoded_url = url

        if not decoded_url.startswith("http"):
            decoded_url = url

        res = self._fetch(decoded_url, referer=self.currentDomain + "/", raw_bytes=True)
        raw_bytes = res.get("bytes", b"")
        if not raw_bytes:
            return [500, "text/plain", b""]

        clean_text = raw_bytes.strip().replace(b"\r", b"").replace(b"\n", b"").replace(b" ", b"")

        # 解码 Base64 文本还原原始图片流
        img_bytes = b""
        try:
            img_bytes = base64.b64decode(clean_text)
        except Exception:
            try:
                # 兜底：解两层 base64
                dec_once = base64.b64decode(clean_text)
                img_bytes = base64.b64decode(dec_once)
            except Exception:
                img_bytes = raw_bytes

        if not img_bytes:
            return [500, "text/plain", b""]

        # 识别 MIME 类型
        mime = "image/webp"
        if img_bytes.startswith(b"RIFF") and b"WEBP" in img_bytes[:16]:
            mime = "image/webp"
        elif img_bytes.startswith(b"\xff\xd8\xff"):
            mime = "image/jpeg"
        elif img_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            mime = "image/png"
        elif img_bytes.startswith(b"GIF8"):
            mime = "image/gif"

        return [200, mime, img_bytes]