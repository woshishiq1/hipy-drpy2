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
        # 站点与多域名配置
        self.siteBase = "https://nzgyz-58190-thndpm.miyoooooo666oom72.top"
        self.siteUrl = "https://nzgyz-58190-thndpm.miyoooooo666oom72.top/yoooooo"
        self.playSiteUrl = "https://nzgyz-58190-thndpm.miyoooooo666oom72.top"
        self.playUrl2 = "https://yb1.yoooooo666oo7.com"

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
            {"type_id": "20", "type_name": "国产"},
            {"type_id": "114", "type_name": "传媒系列"},
            {"type_id": "142", "type_name": "探花系列"},
            {"type_id": "21", "type_name": "日本有码"},
            {"type_id": "26", "type_name": "国产精品"},
            {"type_id": "29", "type_name": "国产自拍"},
            {"type_id": "91", "type_name": "网曝系列"},
            {"type_id": "115", "type_name": "麻豆传媒"},
            {"type_id": "119", "type_name": "天美传媒"},
            {"type_id": "167", "type_name": "综合探花"},
            {"type_id": "143", "type_name": "91沈先生"},
            {"type_id": "157", "type_name": "网红黑料"}
        ]

        year_filter = [
            {"n": "全部", "v": ""},
            {"n": "2026", "v": "2026"},
            {"n": "2025", "v": "2025"},
            {"n": "2024", "v": "2024"},
            {"n": "2023", "v": "2023"},
            {"n": "2022", "v": "2022"},
            {"n": "2021", "v": "2021"},
            {"n": "2020", "v": "2020"}
        ]

        self.filters = {}
        for c in self.classList:
            self.filters[c["type_id"]] = [
                {"key": "year", "name": "年份", "value": year_filter}
            ]

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

        # 修复：防止 /yoooooo 前缀被根路径截断
        if target_url.startswith("/"):
            if not target_url.startswith("/yoooooo"):
                target_url = self.siteUrl + target_url
            else:
                target_url = self.siteBase + target_url

        headers = {
            "User-Agent": self._ua,
            "Referer": referer if referer else (self.siteUrl + "/"),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
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
            return self.siteBase + u
        return u

    def _extract_bg_url(self, style_str):
        if not style_str:
            return ""
        m = re.search(r'url\([\'"]?([^\'")]+)', style_str)
        return m.group(1) if m else ""

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

    def _extract_player_url(self, html_text):
        if not html_text or len(html_text) < 50:
            return ""

        var_names = ["player_aaaa", "player_data"]
        for var_name in var_names:
            start_idx = html_text.find(var_name)
            if start_idx == -1:
                continue
            brace_start = html_text.find("{", start_idx)
            if brace_start == -1:
                continue

            depth = 0
            in_str = False
            esc = False
            end_idx = -1
            for ci in range(brace_start, len(html_text)):
                c = html_text[ci]
                if in_str:
                    if esc:
                        esc = False
                    elif c == '\\':
                        esc = True
                    elif c == '"':
                        in_str = False
                else:
                    if c == '"':
                        in_str = True
                    elif c == '{':
                        depth += 1
                    elif c == '}':
                        depth -= 1
                        if depth == 0:
                            end_idx = ci + 1
                            break

            if end_idx > brace_start:
                try:
                    raw_json = html_text[brace_start:end_idx]
                    player_data = json.loads(raw_json)
                    video_url = player_data.get("url", "")
                    encrypt = str(player_data.get("encrypt", "0"))
                    if encrypt == "1":
                        video_url = urllib.parse.unquote(video_url)
                    elif encrypt == "2":
                        try:
                            video_url = urllib.parse.unquote(base64.b64decode(video_url).decode("utf-8", errors="ignore"))
                        except Exception:
                            pass
                    video_url = video_url.replace(r"\/", "/")
                    if video_url and video_url.startswith("http"):
                        return video_url
                except Exception:
                    pass

        m3u8_match = re.search(r'https?://[^"\'\s<>\\]+\.m3u8[^"\'\s<>\\]*', html_text)
        if m3u8_match:
            return m3u8_match.group(0).replace(r"\/", "/")

        mp4_match = re.search(r'https?://[^"\'\s<>\\]+\.mp4[^"\'\s<>\\]*', html_text)
        if mp4_match:
            return mp4_match.group(0).replace(r"\/", "/")

        return ""

    def _fetch_play_m3u8(self, play_path):
        if not play_path.startswith("/"):
            play_path = "/" + play_path

        domains = [self.playUrl2, self.playSiteUrl]
        for domain in domains:
            full_url = domain + play_path
            res = self._fetch(full_url, referer=domain + "/")
            html_text = res.get("text", "")
            m3u8 = self._extract_player_url(html_text)
            if m3u8:
                return m3u8
        return ""

    # 全局高鲁棒性列表解析：兼顾 class 混淆与排版差异
    def _parse_list_html(self, html_text):
        videos = []
        seen = set()

        # 方案 A: 优先按 movie-list-item 分割
        items = re.findall(r'<div[^>]+class=["\'][^"\']*movie-list-item[^"\']*["\'][^>]*>([\s\S]*?)(?=<div[^>]+class=["\'][^"\']*movie-list-item|$)', html_text, re.I)
        
        # 方案 B: 兜底直接按链接定位区块
        if not items:
            items = re.findall(r'(<a[^>]+href=["\'][^"\']*/voddetail/\d+/[^"\']*["\'][\s\S]*?</a>)', html_text, re.I)

        for item in items:
            # 提取 voddetail 链接与 ID
            href_match = re.search(r'href=["\']([^"\']*/voddetail/(\d+)/[^"\']*)["\']', item, re.I)
            if not href_match:
                continue

            vod_id = href_match.group(2)
            if vod_id in seen:
                continue
            seen.add(vod_id)

            # 提取标题
            title = ""
            title_match = re.search(r'class=["\'][^"\']*movie-title[^"\']*["\'][^>]*title=["\']([^"\']+)["\']', item, re.I)
            if title_match:
                title = title_match.group(1)
            if not title:
                title_tag = re.search(r'class=["\'][^"\']*movie-title[^"\']*["\'][^>]*>([\s\S]*?)</', item, re.I)
                if title_tag:
                    title = re.sub(r'<[^>]+>', '', title_tag.group(1)).strip()
            if not title:
                t_attr = re.search(r'title=["\']([^"\']+)["\']', item, re.I)
                if t_attr:
                    title = t_attr.group(1)

            title = re.sub(r'影片信息$', '', title).strip()

            # 提取封面
            pic = ""
            orig_match = re.search(r'data-original=["\']([^"\']+)["\']', item, re.I)
            if orig_match:
                pic = orig_match.group(1)
            else:
                src_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', item, re.I)
                if src_match and not src_match.group(1).startswith("data:"):
                    pic = src_match.group(1)
                else:
                    style_match = re.search(r'style=["\']([^"\']+)["\']', item, re.I)
                    if style_match:
                        pic = self._extract_bg_url(style_match.group(1))
                        if "/template/" in pic:
                            pic = ""

            # 提取评分
            rating_match = re.search(r'class=["\'][^"\']*movie-rating[^"\']*["\'][^>]*>([\s\S]*?)<', item, re.I)
            rating = rating_match.group(1).strip() if rating_match else ""
            remarks = ("%s分" % rating) if rating else ""

            if title:
                videos.append({
                    "vod_id": self._encode_id(vod_id),
                    "vod_name": self._unesc(title),
                    "vod_pic": self._fix_url(pic),
                    "vod_remarks": remarks
                })

        return videos

    # 1. 首页：纯内存静态返回
    def homeContent(self, *args, **kwargs):
        return {
            "class": self.classList,
            "filters": self.filters
        }

    # 2. 分类列表页：双重域名与安全路径拼装
    def categoryContent(self, tid, pg, *args, **kwargs):
        pg_int = 1
        try:
            pg_int = int(pg)
        except Exception:
            pass

        tid_str = str(tid).strip("/")

        year = ""
        if kwargs.get("extend"):
            year = kwargs["extend"].get("year", "")
        elif len(args) > 1 and isinstance(args[1], dict):
            year = args[1].get("year", "")

        # 严格按照 siteUrl (/yoooooo) 构造准确完整路径
        if year:
            req_url = "%s/s/year/%s/page/%d/" % (self.siteUrl, year, pg_int)
        else:
            req_url = "%s/t/%s/page/%d/" % (self.siteUrl, tid_str, pg_int)

        # 优先从主站请求
        res = self._fetch(req_url, referer=self.siteUrl + "/")
        html_text = res.get("text", "")

        # 若主站无数据或遭遇拦截，自动 fallback 切换至备用源
        if not html_text or len(html_text) < 500:
            if year:
                req_url = "%s/s/year/%s/page/%d/" % (self.playUrl2, year, pg_int)
            else:
                req_url = "%s/t/%s/page/%d/" % (self.playUrl2, tid_str, pg_int)
            res = self._fetch(req_url, referer=self.playUrl2 + "/")
            html_text = res.get("text", "")

        vod_list = self._parse_list_html(html_text)

        return {
            "list": vod_list,
            "page": pg_int,
            "pagecount": 999 if len(vod_list) >= 15 else pg_int,
            "limit": 30,
            "total": 9999
        }

    # 3. 详情页
    def detailContent(self, ids):
        raw_id_param = ids[0] if isinstance(ids, (list, tuple)) else str(ids)
        real_id = self._decode_id(raw_id_param)

        detail_url = "%s/voddetail/%s/" % (self.playUrl2, real_id)
        res = self._fetch(detail_url, referer=self.playUrl2 + "/")
        html_text = res.get("text", "")

        # 备用源失败则试主站根域
        if not html_text or len(html_text) < 500:
            detail_url = "%s/voddetail/%s/" % (self.playSiteUrl, real_id)
            res = self._fetch(detail_url, referer=self.playSiteUrl + "/")
            html_text = res.get("text", "")

        vod_name = ""
        m_h1 = re.search(r'<h1[^>]*>([\s\S]*?)</h1>', html_text, re.I)
        if m_h1:
            vod_name = re.sub(r'<[^>]+>', '', m_h1.group(1)).strip()

        vod_pic = ""
        orig_match = re.search(r'data-original=["\']([^"\']+)["\']', html_text, re.I)
        if orig_match:
            vod_pic = orig_match.group(1)
        else:
            style_match = re.search(r'style=["\']([^"\']*background-image:[^"\']+)["\']', html_text, re.I)
            if style_match:
                vod_pic = self._extract_bg_url(style_match.group(1))

        vod_year = ""
        m_year = re.search(r'/s/year/(\d+)/', html_text)
        if m_year:
            vod_year = m_year.group(1)

        class_links = re.findall(r'/s/class/([^/]+)/', html_text)
        classes = []
        seen_class = set()
        for cl in class_links:
            if cl not in seen_class:
                seen_class.add(cl)
                try:
                    classes.append(urllib.parse.unquote(cl))
                except Exception:
                    classes.append(cl)
        vod_class = ",".join(classes)

        vod_remarks = ""
        m_status = re.search(r'状态：([^<]+)', html_text)
        if m_status:
            vod_remarks = m_status.group(1).strip()

        clean_content = ""
        p_matches = re.findall(r'<p[^>]*>([\s\S]*?)</p>', html_text, re.I)
        for p_text in p_matches:
            c_text = re.sub(r'<[^>]+>', '', p_text).strip()
            if len(c_text) > 15 and ("状态：" not in c_text) and ("播放" not in c_text):
                clean_content = re.sub(r'^aaa', '', c_text).strip()
                break

        custom_notice = "【💡 温馨提示：视频加载如遇卡顿请尝试切换线路或快进。】"
        group_info = "【🔥 官方交流群: %s】" % self.tgGroup
        if clean_content:
            vod_content = "%s\n\n%s\n\n%s" % (group_info, custom_notice, clean_content)
        else:
            vod_content = "%s\n\n%s\n\n暂无详细简介，欢迎加入TG群获取最新资源！" % (group_info, custom_notice)

        play_links = []
        seen_sid = set()
        sid_links = re.findall(r'<a[^>]+href=["\']([^"\']*/v/\d+/sid/(\d+)/nid/\d+/[^"\']*)["\'][^>]*>([\s\S]*?)</a>', html_text, re.I)
        for href, sid, text in sid_links:
            if sid in seen_sid:
                continue
            seen_sid.add(sid)
            c_text = re.sub(r'<[^>]+>', '', text).strip()
            if not c_text:
                c_text = "播放"
            play_links.append({"text": c_text, "href": href})

        if not play_links:
            btn_links = re.findall(r'<a[^>]+class=["\'][^"\']*btn[^"\']*["\'][^>]*href=["\']([^"\']*/v/[^"\']*)["\']', html_text, re.I)
            for href in btn_links:
                play_links.append({"text": "播放", "href": href})

        play_from_list = []
        play_url_list = []
        for item in play_links:
            m3u8_url = self._fetch_play_m3u8(item["href"])
            play_from_list.append(item["text"])
            if m3u8_url:
                play_url_list.append("%s$%s" % (item["text"], m3u8_url))
            else:
                play_url_list.append("%s$%s" % (item["text"], item["href"]))

        return {
            "list": [{
                "vod_id": raw_id_param,
                "vod_name": self._unesc(vod_name),
                "vod_pic": self._fix_url(vod_pic),
                "vod_type_name": vod_class,
                "vod_year": vod_year,
                "vod_area": vod_class,
                "vod_remarks": self._unesc(vod_remarks),
                "vod_actor": self.brandActor,
                "vod_director": self.brandDirector,
                "vod_content": vod_content,
                "vod_play_from": "$$$".join(play_from_list) if play_from_list else "66乐园",
                "vod_play_url": "$$$".join(play_url_list) if play_url_list else "在线播放$http://127.0.0.1"
            }]
        }

    # 4. 播放器：parse 保持 0，杜绝闪退
    def playerContent(self, flag, id, vipFlags):
        play_id = str(id).strip()

        if play_id.startswith("http") and (".m3u8" in play_id or ".mp4" in play_id):
            return {
                "parse": 0,
                "playUrl": "",
                "url": play_id,
                "header": json.dumps({
                    "User-Agent": self._ua,
                    "Referer": self.playSiteUrl + "/"
                })
            }

        if play_id.startswith("http"):
            return {
                "parse": 0,
                "playUrl": "",
                "url": play_id,
                "header": json.dumps({
                    "User-Agent": self._ua,
                    "Referer": self.siteUrl + "/"
                })
            }

        m3u8_url = self._fetch_play_m3u8(play_id)
        if m3u8_url:
            return {
                "parse": 0,
                "playUrl": "",
                "url": m3u8_url,
                "header": json.dumps({
                    "User-Agent": self._ua,
                    "Referer": self.playSiteUrl + "/"
                })
            }

        play_path = play_id if play_id.startswith("/") else ("/" + play_id)
        return {
            "parse": 0,
            "playUrl": "",
            "url": self.playUrl2 + play_path,
            "header": json.dumps({
                "User-Agent": self._ua,
                "Referer": self.playUrl2 + "/"
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

        search_url = "%s/s/%s/page/%d/" % (self.siteUrl, urllib.parse.quote(wd), pg_int)
        res = self._fetch(search_url, referer=self.siteUrl + "/")
        html_text = res.get("text", "")

        if not html_text or len(html_text) < 500:
            search_url = "%s/s/%s/page/%d/" % (self.playUrl2, urllib.parse.quote(wd), pg_int)
            res = self._fetch(search_url, referer=self.playUrl2 + "/")
            html_text = res.get("text", "")

        vod_list = self._parse_list_html(html_text)

        return {
            "list": vod_list,
            "page": pg_int,
            "pagecount": pg_int if len(vod_list) < 15 else (pg_int + 1),
            "limit": len(vod_list),
            "total": 9999
        }