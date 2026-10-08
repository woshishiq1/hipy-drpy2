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
        self.siteUrl = "https://ozzc.18jtoday8m4.buzz"
        self.tgGroup = "https://t.me/tvshare23"
        self.brandActor = "🦋 TG群: @tvshare23"
        self.brandDirector = "🦋 蝴蝶影视"
        self._ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

        # SSL 与连接池配置，适配低版本 Android 盒子
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

        # 固化静态分类列表
        self.classList = [
            {"type_id": "424", "type_name": "麻豆视频"},
            {"type_id": "425", "type_name": "91制片厂"},
            {"type_id": "426", "type_name": "天美传媒"},
            {"type_id": "427", "type_name": "蜜桃传媒"},
            {"type_id": "428", "type_name": "皇家华人"},
            {"type_id": "429", "type_name": "星空传媒"},
            {"type_id": "430", "type_name": "精东影业"},
            {"type_id": "431", "type_name": "大象传媒"},
            {"type_id": "432", "type_name": "91茄子"},
            {"type_id": "433", "type_name": "性视界传媒"},
            {"type_id": "434", "type_name": "兔子先生"},
            {"type_id": "435", "type_name": "杏吧原创"},
            {"type_id": "436", "type_name": "玩偶姐姐"},
            {"type_id": "437", "type_name": "香蕉传媒"},
            {"type_id": "438", "type_name": "SA国际传媒"},
            {"type_id": "439", "type_name": "EDmosaic"},
            {"type_id": "440", "type_name": "PsychoPorn"},
            {"type_id": "441", "type_name": "糖心Vlog"},
            {"type_id": "442", "type_name": "葫芦影业"},
            {"type_id": "443", "type_name": "果冻传媒"},
            {"type_id": "2", "type_name": "国产视频"},
            {"type_id": "3", "type_name": "国产主播"},
            {"type_id": "4", "type_name": "91大神"},
            {"type_id": "5", "type_name": "热门事件"},
            {"type_id": "6", "type_name": "传媒自拍"},
            {"type_id": "7", "type_name": "日本有码"},
            {"type_id": "8", "type_name": "日本无码"},
            {"type_id": "9", "type_name": "日韩主播"},
            {"type_id": "10", "type_name": "动漫肉番"},
            {"type_id": "11", "type_name": "女同性恋"},
            {"type_id": "12", "type_name": "中文字幕"},
            {"type_id": "15", "type_name": "制服诱惑"},
            {"type_id": "16", "type_name": "AV解说"},
            {"type_id": "19", "type_name": "日韩无码"},
            {"type_id": "21", "type_name": "欧美精品"},
            {"type_id": "24", "type_name": "动漫精品"},
            {"type_id": "25", "type_name": "日韩精品"},
            {"type_id": "28", "type_name": "自拍偷拍"},
            {"type_id": "30", "type_name": "AV明星"},
            {"type_id": "31", "type_name": "巨乳系列"},
            {"type_id": "33", "type_name": "口交视频"},
            {"type_id": "35", "type_name": "国产精品"},
            {"type_id": "36", "type_name": "SM重味"},
            {"type_id": "49", "type_name": "国产精品2"},
            {"type_id": "51", "type_name": "黑料吃瓜"},
            {"type_id": "52", "type_name": "欧美"},
            {"type_id": "54", "type_name": "学生"},
            {"type_id": "71", "type_name": "萝莉少女"},
            {"type_id": "74", "type_name": "成人动漫"},
            {"type_id": "79", "type_name": "Cosplay"},
            {"type_id": "155", "type_name": "国产自拍"},
            {"type_id": "165", "type_name": "映画传媒"},
            {"type_id": "274", "type_name": "国产自拍2"},
            {"type_id": "275", "type_name": "主播诱惑"},
            {"type_id": "276", "type_name": "探花约炮"},
            {"type_id": "278", "type_name": "网曝吃瓜"},
            {"type_id": "279", "type_name": "抖阴短片"},
            {"type_id": "280", "type_name": "传媒剧情"},
            {"type_id": "297", "type_name": "国产视频2"},
            {"type_id": "348", "type_name": "亚洲情色"},
            {"type_id": "387", "type_name": "网红主播"},
            {"type_id": "388", "type_name": "国产传媒"},
            {"type_id": "389", "type_name": "探花系列"},
            {"type_id": "419", "type_name": "3D动漫"},
            {"type_id": "422", "type_name": "OnlyFans"}
        ]

        sort_filter = [
            {"n": "全部", "v": ""},
            {"n": "最新", "v": "time"},
            {"n": "热门", "v": "hits"}
        ]

        self.filters = {}
        for c in self.classList:
            self.filters[c["type_id"]] = [
                {"key": "sort", "name": "排序", "value": sort_filter}
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

    def _fix_pic(self, u):
        return self._fix_url(u)

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
        
        # 匹配 <section class="item-box"> 块
        sections = re.findall(r'<section[^>]+class=["\'][^"\']*item-box[^"\']*["\'][^>]*>([\s\S]*?)</section>', html, re.I)
        for sec in sections:
            # 提取图片: data-src -> src
            pic = ""
            img_match = re.search(r'<img[^>]+class=["\'][^"\']*lazy-image[^"\']*["\'][^>]*>', sec, re.I)
            if not img_match:
                img_match = re.search(r'<img[^>]+>', sec, re.I)
            if img_match:
                img_tag = img_match.group(0)
                data_src = re.search(r'data-src=["\']([^"\']+)["\']', img_tag, re.I)
                src = re.search(r'src=["\']([^"\']+)["\']', img_tag, re.I)
                if data_src:
                    pic = data_src.group(1)
                elif src:
                    pic = src.group(1)

            # 提取链接 a.img-box
            a_match = re.search(r'<a[^>]+class=["\'][^"\']*img-box[^"\']*["\'][^>]*href=["\']([^"\']+)["\'][^>]*>', sec, re.I)
            href = a_match.group(1) if a_match else ""
            if not href:
                a_fallback = re.search(r'<a[^>]+href=["\'](/voddetail/[^"\']+)["\'][^>]*>', sec, re.I)
                href = a_fallback.group(1) if a_fallback else ""

            # 提取标题: title 属性优先，否则取 h2 内文本
            title = ""
            if a_match:
                t_attr = re.search(r'title=["\']([^"\']+)["\']', a_match.group(0), re.I)
                if t_attr:
                    title = t_attr.group(1)
            if not title:
                h2_match = re.search(r'<h2[^>]*>[\s\S]*?<a[^>]*>([\s\S]*?)</a>', sec, re.I)
                if h2_match:
                    title = re.sub(r'<[^>]+>', '', h2_match.group(1)).strip()

            # 提取副标题 remarks
            remarks = ""
            aux_match = re.findall(r'<small[^>]*>([\s\S]*?)</small>', sec, re.I)
            if aux_match:
                remarks = re.sub(r'<[^>]+>', '', aux_match[-1]).strip()

            # 提取 vod_id
            vod_id = ""
            m_id = re.search(r'/voddetail/(\d+)/', href)
            if m_id:
                vod_id = m_id.group(1)
            elif "/voddetail/" in href:
                clean_h = href.replace("/voddetail/", "").strip("/")
                vod_id = clean_h

            if not vod_id or vod_id in seen_ids:
                continue
            seen_ids.add(vod_id)

            list_data.append({
                "vod_id": self._encode_id(vod_id),
                "vod_name": self._unesc(title),
                "vod_pic": self._fix_pic(pic.strip()),
                "vod_remarks": self._unesc(remarks)
            })

        return list_data

    def _extract_page_count(self, html):
        m = re.search(r'共\d+条数据.*?当前\d+/(\d+)页', html)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                pass
        m = re.search(r'/vodtype/\d+-(\d+)/.*?laypage_next', html)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                pass
        return 1

    def _extract_search_page_count(self, html):
        m = re.search(r'共\d+条数据.*?当前\d+/(\d+)页', html)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                pass
        m = re.search(r'/vodsearch/[^"]+-(\d+)---/.*?laypage_next', html)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                pass
        return 1

    def _extract_m3u8_from_play_html(self, html):
        # 1. 匹配 player_data
        m_data = re.search(r'var\s+player_data\s*=\s*(\{[\s\S]+?\})\s*;?\s*</script>', html, re.I)
        if m_data:
            m_url = re.search(r'"url"\s*:\s*"([^"]+)"', m_data.group(1))
            if m_url:
                return m_url.group(1).replace(r"\/", "/")

        # 2. 匹配 player_aaaa
        m_aaaa = re.search(r'var\s+player_aaaa\s*=\s*(\{[\s\S]+?\})\s*;?\s*</script>', html, re.I)
        if m_aaaa:
            m_url = re.search(r'"url"\s*:\s*"([^"]+)"', m_aaaa.group(1))
            if m_url:
                return m_url.group(1).replace(r"\/", "/")

        # 3. 正则捕获 m3u8 直链
        m_direct = re.search(r'(https?:\\?/\\?/[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html, re.I)
        if m_direct:
            return m_direct.group(1).replace(r"\/", "/")

        return ""

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

        # 统一使用 vodtype 路由
        if pg_int > 1:
            req_url = "%s/vodtype/%s-%d/" % (self.siteUrl, tid_str, pg_int)
        else:
            req_url = "%s/vodtype/%s/" % (self.siteUrl, tid_str)

        res = self._fetch(req_url, referer=self.siteUrl + "/vodtype/" + tid_str + "/")
        html_text = res.get("text", "")

        vod_list = self._parse_list_html(html_text)
        page_count = self._extract_page_count(html_text)

        return {
            "list": vod_list,
            "page": pg_int,
            "pagecount": page_count,
            "limit": 20,
            "total": page_count * 20
        }

    # 3. 详情页：逆向直解播放链接，规范排版
    def detailContent(self, ids):
        raw_id_param = ids[0] if isinstance(ids, (list, tuple)) else str(ids)
        real_id = self._decode_id(raw_id_param)

        detail_url = "%s/voddetail/%s/" % (self.siteUrl, real_id)
        res = self._fetch(detail_url, referer=self.siteUrl + "/")
        html_text = res.get("text", "")

        # 提取标题
        title = ""
        m_title = re.search(r'<div[^>]+class=["\'][^"\']*detail-info-wrapper[^"\']*["\'][^>]*>[\s\S]*?<h1[^>]+class=["\'][^"\']*f-20[^"\']*["\'][^>]*>([\s\S]*?)</h1>', html_text, re.I)
        if m_title:
            title = re.sub(r'<[^>]+>', '', m_title.group(1)).strip()
        if not title:
            m_h1 = re.search(r'<div[^>]+class=["\'][^"\']*detail-info-wrapper[^"\']*["\'][^>]*>[\s\S]*?<h1[^>]*>([\s\S]*?)</h1>', html_text, re.I)
            if m_h1:
                title = re.sub(r'<[^>]+>', '', m_h1.group(1)).strip()

        # 提取封面
        pic = ""
        m_img_sec = re.search(r'<div[^>]+class=["\'][^"\']*detail-image-wrapper[^"\']*["\'][^>]*>[\s\S]*?<img[^>]+>', html_text, re.I)
        if m_img_sec:
            img_tag = m_img_sec.group(0)
            data_src = re.search(r'data-src=["\']([^"\']+)["\']', img_tag, re.I)
            src = re.search(r'src=["\']([^"\']+)["\']', img_tag, re.I)
            if data_src:
                pic = data_src.group(1)
            elif src:
                pic = src.group(1)

        # 提取更新日期/年份
        date_str = ""
        m_h6 = re.search(r'<div[^>]+class=["\'][^"\']*detail-info-wrapper[^"\']*["\'][^>]*>[\s\S]*?<h6[^>]*>([\s\S]*?)</h6>', html_text, re.I)
        if m_h6:
            date_str = re.sub(r'<[^>]+>', '', m_h6.group(1)).strip()
        vod_year = date_str[:4] if len(date_str) >= 4 and date_str[:4].isdigit() else ""

        # 提取分类名称
        type_name = ""
        m_type = re.search(r'<div[^>]+class=["\'][^"\']*detail-info-type[^"\']*["\'][^>]*>[\s\S]*?<a[^>]+title=["\']([^"\']+)["\']', html_text, re.I)
        if m_type:
            type_name = m_type.group(1).strip()

        # 提取简介
        clean_content = ""
        m_desc = re.search(r'<div[^>]+class=["\'][^"\']*detail-info-wrapper[^"\']*["\'][^>]*>[\s\S]*?<div[^>]+class=["\'][^"\']*tx-text[^"\']*["\'][^>]*>[\s\S]*?<p[^>]*>([\s\S]*?)</p>', html_text, re.I)
        if m_desc:
            clean_content = re.sub(r'<[^>]+>', '', m_desc.group(1)).strip()

        # 提取标签
        tags = re.findall(r'<a[^>]+href=["\'][^"\']*/vodshow/[^"\']*["\'][^>]*>([\s\S]*?)</a>', html_text, re.I)
        tag_list = []
        for t in tags:
            ct = re.sub(r'<[^>]+>', '', t).strip()
            if ct:
                tag_list.append(ct)
        if tag_list:
            clean_content = ("%s 标签: %s" % (clean_content, " ".join(tag_list))).strip()

        # 标准简介格式化
        custom_notice = "【💡 温馨提示：视频加载如遇卡顿请尝试切换线路或快进。】"
        group_info = "【🔥 官方交流群: %s】" % self.tgGroup
        if clean_content:
            vod_content = "%s\n\n%s\n\n%s" % (group_info, custom_notice, clean_content)
        else:
            vod_content = "%s\n\n%s\n\n暂无详细简介，欢迎加入TG群获取最新资源！" % (group_info, custom_notice)

        # 提取播放页链接
        play_path = ""
        m_play = re.search(r'<div[^>]+class=["\'][^"\']*detail-info-wrapper[^"\']*["\'][^>]*>[\s\S]*?<a[^>]+href=["\']([^"\']*/vodplay/[^"\']*)["\']', html_text, re.I)
        if m_play:
            play_path = m_play.group(1)
        else:
            m_play_fb = re.search(r'<a[^>]+href=["\']([^"\']*/vodplay/[^"\']*)["\']', html_text, re.I)
            if m_play_fb:
                play_path = m_play_fb.group(1)

        # 深入二级播放页预解析直链
        m3u8_direct = ""
        if play_path:
            full_play_url = self._fix_url(play_path)
            play_res = self._fetch(full_play_url, referer=detail_url)
            m3u8_direct = self._extract_m3u8_from_play_html(play_res.get("text", ""))

        vod_play_url = ""
        if m3u8_direct:
            vod_play_url = "在线播放$" + m3u8_direct
        elif play_path:
            vod_play_url = "在线播放$" + self._fix_url(play_path)

        return {
            "list": [{
                "vod_id": raw_id_param,
                "vod_name": self._unesc(title),
                "vod_pic": self._fix_pic(pic.strip()),
                "vod_type_name": type_name,
                "vod_year": vod_year,
                "vod_area": type_name,
                "vod_remarks": self._unesc(date_str),
                "vod_actor": self.brandActor,
                "vod_director": self.brandDirector,
                "vod_content": vod_content,
                "vod_play_from": "18J今天",
                "vod_play_url": vod_play_url
            }]
        }

    # 4. 播放器：安全纯净直连，彻底禁用 parse: 1
    def playerContent(self, flag, id, vipFlags):
        play_url = str(id).strip()

        # 若详情页未解出 m3u8，进入播放页提取直链
        if not play_url.startswith("http") or ".m3u8" not in play_url:
            full_url = self._fix_url(play_url)
            res = self._fetch(full_url, referer=self.siteUrl + "/")
            html_text = res.get("text", "")
            extracted = self._extract_m3u8_from_play_html(html_text)
            if extracted:
                play_url = extracted
            else:
                m_iframe = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', html_text, re.I)
                if m_iframe:
                    play_url = self._fix_url(m_iframe.group(1))

        return {
            "parse": 0,
            "playUrl": "",
            "url": play_url,
            "header": json.dumps({
                "User-Agent": self._ua,
                "Referer": self.siteUrl + "/"
            })
        }

    # 5. 搜索模块：对齐14段搜索路由
    def searchContent(self, key, quick, pg="1"):
        wd = (key or "").strip()
        if not wd:
            return {"page": 1, "pagecount": 1, "limit": 0, "total": 0, "list": []}

        pg_int = 1
        try:
            pg_int = int(pg)
        except Exception:
            pass

        kw_encoded = urllib.parse.quote(wd)
        search_url = "%s/vodsearch/%s----------%d---/" % (self.siteUrl, kw_encoded, pg_int)

        res = self._fetch(search_url, referer="%s/luckily/" % self.siteUrl)
        html_text = res.get("text", "")

        vod_list = self._parse_list_html(html_text)
        page_count = self._extract_search_page_count(html_text)

        return {
            "list": vod_list,
            "page": pg_int,
            "pagecount": page_count,
            "limit": len(vod_list),
            "total": page_count * 20
        }