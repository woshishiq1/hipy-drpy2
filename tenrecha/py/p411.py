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
        self.siteHost = "https://y5z6a7b8.chamm238.xyz"
        self.tgGroup = "https://t.me/+3t5XRPPo9mlkZDRl"
        self.brandActor = "📺TG群: https://t.me/+3t5XRPPo9mlkZDRl"
        self.brandDirector = "📺ZakaTV"
        self._ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

        self.ctx = ssl.create_default_context()
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE
        try:
            self.ctx.set_ciphers("DEFAULT@SECLEVEL=1")
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
            target_url = self.siteHost + target_url

        headers = {
            "User-Agent": self._ua,
            "Referer": referer if referer else (self.siteHost + "/topic/"),
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

    def _decode_player_url(self, raw_url, encrypt_type):
        if not raw_url:
            return ""
        try:
            if encrypt_type == 1:
                return urllib.parse.unquote(raw_url)
            elif encrypt_type == 2:
                pad = len(raw_url) % 4
                if pad:
                    raw_url += "=" * (4 - pad)
                return urllib.parse.unquote(base64.b64decode(raw_url.encode("utf-8")).decode("utf-8"))
            return urllib.parse.unquote(raw_url)
        except Exception:
            return raw_url

    # 1. 首页：静态秒开，32个原生分类
    def homeContent(self, *args, **kwargs):
        classes = [
            {"type_name": "麻豆视频", "type_id": "6"},
            {"type_name": "91制片厂", "type_id": "7"},
            {"type_name": "天美传媒", "type_id": "8"},
            {"type_name": "蜜桃传媒", "type_id": "9"},
            {"type_name": "皇家华人", "type_id": "10"},
            {"type_name": "星空传媒", "type_id": "11"},
            {"type_name": "精东影业", "type_id": "12"},
            {"type_name": "乐播传媒", "type_id": "20"},
            {"type_name": "兔子先生", "type_id": "21"},
            {"type_name": "杏吧原创", "type_id": "22"},
            {"type_name": "玩偶姐姐", "type_id": "23"},
            {"type_name": "mini传媒", "type_id": "24"},
            {"type_name": "大象传媒", "type_id": "25"},
            {"type_name": "性视界", "type_id": "26"},
            {"type_name": "成人头条", "type_id": "30"},
            {"type_name": "开心鬼传媒", "type_id": "31"},
            {"type_name": "PsychoPorn", "type_id": "37"},
            {"type_name": "糖心Vlog", "type_id": "32"},
            {"type_name": "萝莉社", "type_id": "33"},
            {"type_name": "乌鸦传媒", "type_id": "34"},
            {"type_name": "国产精品", "type_id": "28"},
            {"type_name": "华语AV", "type_id": "29"},
            {"type_name": "黑料吃瓜", "type_id": "35"},
            {"type_name": "学生合集", "type_id": "15"},
            {"type_name": "乱伦精品", "type_id": "59"},
            {"type_name": "探花约炮", "type_id": "60"},
            {"type_name": "日本无码", "type_id": "61"},
            {"type_name": "主播网红", "type_id": "62"},
            {"type_name": "欧美精品", "type_id": "63"},
            {"type_name": "动漫禁漫", "type_id": "64"},
            {"type_name": "日本有码", "type_id": "65"},
            {"type_name": "日本素人", "type_id": "66"}
        ]
        return {"class": classes}

    # 2. 列表页：精准解析封面卡片，过滤分页噪音
    def categoryContent(self, tid, pg, *args, **kwargs):
        c_id = str(tid).strip()
        p = str(pg).strip() if pg else "1"

        if p == "1":
            target_url = "%s/vodtype/%s.html" % (self.siteHost, c_id)
        else:
            target_url = "%s/vodtype/%s-%s.html" % (self.siteHost, c_id, p)

        res = self._fetch(target_url)
        html_text = res.get("text", "")

        card_pattern = r'<a[^>]+href=["\']([^"\']*?/voddetail/[^"\']+)["\'][^>]*>([\s\S]*?)</a>'
        matches = re.findall(card_pattern, html_text, re.I)

        video_list = []
        seen_urls = set()

        for href, inner_html in matches:
            if href in seen_urls:
                continue
            seen_urls.add(href)

            title = ""
            title_m = re.search(r'title=["\']([^"\']+)["\']', inner_html, re.I)
            alt_m = re.search(r'alt=["\']([^"\']+)["\']', inner_html, re.I)
            if title_m:
                title = title_m.group(1)
            elif alt_m:
                title = alt_m.group(1)
            else:
                title = re.sub(r"<[^>]+>", "", inner_html).strip()

            title = self._unesc(title)

            if any(noise in title for noise in ("上一页", "下一页", "尾页", "首页", "第", "页")):
                continue
            if len(title) < 2:
                continue

            pic = ""
            pic_m = re.search(r'(?:data-original|data-src|src)=["\']([^"\']+\.(?:jpg|jpeg|png|webp|gif)[^"\']*)["\']', inner_html, re.I)
            if pic_m:
                pic = pic_m.group(1).strip()
                if pic.startswith("//"):
                    pic = "https:" + pic
                elif pic.startswith("/"):
                    pic = self.siteHost + pic

            remarks = ""
            remarks_m = re.search(r'<span[^>]+class=["\'][^"\']*(?:remarks|note|pic-text|tag)[^"\']*["\'][^>]*>([\s\S]*?)</span>', inner_html, re.I)
            if remarks_m:
                remarks = self._unesc(re.sub(r"<[^>]+>", "", remarks_m.group(1)))

            safe_id = "v_" + base64.urlsafe_b64encode(href.encode("utf-8")).decode("utf-8").rstrip("=")

            video_list.append({
                "vod_id": safe_id,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remarks
            })

        return {
            "page": int(p),
            "pagecount": 99,
            "limit": len(video_list),
            "total": 999,
            "list": video_list
        }

    # 3. 详情页：解密直链与品牌简介定制
    def detailContent(self, ids):
        raw_id = ids[0] if isinstance(ids, (list, tuple)) else str(ids)

        clean_path = ""
        if str(raw_id).startswith("v_"):
            try:
                b64_url = raw_id[2:]
                pad = len(b64_url) % 4
                if pad:
                    b64_url += "=" * (4 - pad)
                clean_path = base64.urlsafe_b64decode(b64_url.encode("utf-8")).decode("utf-8")
            except Exception:
                clean_path = raw_id
        else:
            clean_path = raw_id

        full_detail_url = urllib.parse.urljoin(self.siteHost, clean_path)
        res_detail = self._fetch(full_detail_url)
        html_text = res_detail.get("text", "")

        def get_matched(pattern, text, default=""):
            m = re.search(pattern, text, re.I | re.S)
            return m.group(1) if m else default

        title_m = re.search(r'<title>(.*?)</title>', html_text, re.I)
        vod_title = title_m.group(1).split("-")[0].strip() if title_m else "未知影片"

        pic_m = re.search(r'(?:data-original|data-src|src)=["\']([^"\']+\.(?:jpg|jpeg|png|webp|gif)[^"\']*)["\']', html_text, re.I)
        vod_pic = pic_m.group(1).strip() if pic_m else ""
        if vod_pic.startswith("//"):
            vod_pic = "https:" + vod_pic
        elif vod_pic.startswith("/"):
            vod_pic = self.siteHost + vod_pic

        # 自定义简介结构
        raw_content = get_matched(r'简介：(.*?)</p>', html_text, "")
        clean_content = self._unesc(re.sub(r'<[^>]+>', '', raw_content)).strip()
        
        custom_notice = "【💡 温馨提示：视频加载如遇卡顿请尝试切换线路或快进。】"
        group_info = "【🔥 官方交流群: %s】" % self.tgGroup
        
        if clean_content:
            vod_content = "%s\n\n%s\n\n%s" % (group_info, custom_notice, clean_content)
        else:
            vod_content = "%s\n\n%s\n\n暂无详细简介，欢迎加入TG群获取最新资源！" % (group_info, custom_notice)

        # 提取播放页并解密真实直链
        play_links = re.findall(r'href=["\']([^"\']*?/vodplay/[^"\']+)["\']', html_text, re.I)
        real_stream_url = ""

        if play_links:
            target_play_url = urllib.parse.urljoin(self.siteHost, play_links[0])
            res_play = self._fetch(target_play_url, referer=full_detail_url)
            play_html = res_play.get("text", "")

            p_match = re.search(r'var\s+player_aaaa\s*=\s*(\{[\s\S]*?\});', play_html)
            if p_match:
                try:
                    p_data = json.loads(p_match.group(1))
                    enc_val = int(p_data.get("encrypt", 0))
                    raw_val = p_data.get("url", "")
                    real_stream_url = self._decode_player_url(raw_val, enc_val)
                except Exception:
                    pass

            if not real_stream_url:
                u_m = re.search(r'["\']url["\']\s*:\s*["\']([^"\']+)["\']', play_html)
                enc_m = re.search(r'["\']encrypt["\']\s*:\s*(\d+)', play_html)
                if u_m:
                    enc_val = int(enc_m.group(1)) if enc_m else 0
                    real_stream_url = self._decode_player_url(u_m.group(1), enc_val)

        final_play_url = real_stream_url if real_stream_url.startswith("http") else full_detail_url

        return {
            "list": [{
                "vod_id": raw_id,
                "vod_name": vod_title,
                "vod_pic": vod_pic,
                "vod_actor": self.brandActor,
                "vod_director": self.brandDirector,
                "vod_remarks": "高清直链",
                "vod_content": vod_content,
                "vod_play_from": "Zaka专线",
                "vod_play_url": "正片$%s" % final_play_url
            }]
        }

    # 4. 播放器：后台直连输出，杜绝前端恶意嗅探
    def playerContent(self, flag, id, vipFlags):
        return {
            "parse": 0,
            "playUrl": "",
            "url": str(id).strip(),
            "header": json.dumps({
                "User-Agent": self._ua,
                "Referer": self.siteHost + "/"
            })
        }

    # 5. 搜索保底实现
    def searchContent(self, key, quick, pg="1"):
        return {"list": []}