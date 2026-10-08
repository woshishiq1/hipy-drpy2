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
        self.siteUrl = "https://vintagepornfun.com"
        self.tgGroup = "https://t.me/tvshare23"
        self.brandActor = "🦋 TG群: @tvshare23"
        self.brandDirector = "🦋 蝴蝶影视"
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
            return {"code": 0, "text": "", "err": "URL为空"}
        if target_url.startswith("/"):
            target_url = self.siteUrl + target_url

        headers = {
            "User-Agent": self._ua,
            "Referer": referer if referer else (self.siteUrl + "/"),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
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

    def homeContent(self, filter=False):
        classes = [
            {"type_name": "50s 经典", "type_id": "50s-porn"},
            {"type_name": "60s 经典", "type_id": "60s-porn"},
            {"type_name": "70s 经典", "type_id": "70s-porn"},
            {"type_name": "80s 经典", "type_id": "80s-porn"},
            {"type_name": "90s 经典", "type_id": "90s-porn"},
            {"type_name": "美洲经典", "type_id": "american-vintage-porn"},
            {"type_name": "亚洲复古", "type_id": "asian-vintage-porn"},
            {"type_name": "巴西经典", "type_id": "brazilian-vintage-porn"},
            {"type_name": "经典老片", "type_id": "classic-porn-movies"},
            {"type_name": "丹麦经典", "type_id": "danish-vintage-porn"},
            {"type_name": "荷兰经典", "type_id": "dutch-vintage-porn"},
            {"type_name": "法国浪漫", "type_id": "french-vintage-porn"},
            {"type_name": "德国经典", "type_id": "german-vintage-porn"},
            {"type_name": "黄金时代", "type_id": "golden-age-of-porn"},
            {"type_name": "印度复古", "type_id": "indian-vintage-porn"},
            {"type_name": "意大利经典", "type_id": "italian-vintage-porn"},
            {"type_name": "日本怀旧", "type_id": "japanese-vintage-porn"},
            {"type_name": "怀旧恶搞", "type_id": "vintage-parody-porn"},
            {"type_name": "复古电影", "type_id": "vintage-porn-movies"},
            {"type_name": "轻度柔和", "type_id": "vintage-softcore-movies"}
        ]
        return {"class": classes}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        slug = str(tid).strip("/")
        try:
            page_num = max(1, int(str(pg).strip() or 1))
        except Exception:
            page_num = 1

        if page_num == 1:
            target_url = "%s/category/%s/" % (self.siteUrl, slug)
        else:
            target_url = "%s/category/%s/page/%d/" % (self.siteUrl, slug, page_num)

        res = self._fetch(target_url)
        html_text = res.get("text", "")

        vod_list = []
        seen = set()

        pattern = r'(<a[^>]+href=["\'](https?://vintagepornfun\.com/\d{4}/\d{2}/\d{2}/[^"\']+)["\'][^>]*>[\s\S]*?</a>)'
        items = re.findall(pattern, html_text, re.I)

        for block, href in items:
            clean_href = href.strip()
            if clean_href in seen:
                continue
            seen.add(clean_href)

            title_m = re.search(r'title=["\']([^"\']+)["\']', block)
            if not title_m:
                title_m = re.search(r'alt=["\']([^"\']+)["\']', block)
            title = self._unesc(title_m.group(1)) if title_m else "经典影像"

            pic_m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', block, re.I)
            pic = pic_m.group(1).strip() if pic_m else ""

            b64_href = base64.urlsafe_b64encode(clean_href.encode("utf-8")).decode("utf-8").rstrip("=")
            safe_id = "v_" + b64_href

            vod_list.append({
                "vod_id": safe_id,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": "原版正片"
            })

        has_next = bool(re.search(r'class=["\'][^"\']*next[^"\']*["\']|/page/%d/' % (page_num + 1), html_text, re.I))

        return {
            "page": page_num,
            "pagecount": page_num + 1 if has_next else page_num,
            "limit": len(vod_list) if vod_list else 20,
            "total": 999 if has_next else len(vod_list),
            "list": vod_list
        }

    def detailContent(self, ids):
        raw_id = ids[0] if isinstance(ids, (list, tuple)) else str(ids)

        target_url = ""
        if str(raw_id).startswith("v_"):
            clean_b64 = raw_id[2:]
            pad_len = len(clean_b64) % 4
            if pad_len:
                clean_b64 += "=" * (4 - pad_len)
            try:
                target_url = base64.urlsafe_b64decode(clean_b64.encode("utf-8")).decode("utf-8")
            except Exception:
                target_url = ""

        if not target_url:
            target_url = raw_id if raw_id.startswith("http") else "%s/%s" % (self.siteUrl, raw_id.lstrip("/"))

        res = self._fetch(target_url)
        html_text = res.get("text", "")

        title_m = re.search(r'<h1[^>]*>(.*?)</h1>', html_text, re.S | re.I)
        vod_name = self._unesc(re.sub(r'<[^>]+>', '', title_m.group(1))) if title_m else "经典视频"

        pic_m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html_text, re.I)
        vod_pic = pic_m.group(1).strip() if pic_m else ""

        all_iframes = re.findall(r'<iframe[^>]+src=["\']([^"\']+)["\']', html_text, re.I)
        valid_iframes = []
        for u in all_iframes:
            u_clean = u.strip()
            if u_clean.startswith("//"):
                u_clean = "https:" + u_clean
            if "whitetrafsa" in u_clean or not u_clean.startswith("http"):
                continue
            if u_clean not in valid_iframes:
                valid_iframes.append(u_clean)

        dood_lines = []
        other_lines = []
        for ifr in valid_iframes:
            if "d000d" in ifr or "dood" in ifr:
                dood_lines.append(ifr)
            else:
                other_lines.append(ifr)
        sorted_iframes = dood_lines + other_lines

        play_items = []
        for idx, ifr in enumerate(sorted_iframes):
            domain = urllib.parse.urlparse(ifr).netloc or ("线路%d" % (idx + 1))
            play_items.append("%s$%s" % (domain, ifr))

        play_url_str = "#".join(play_items) if play_items else "线路探测$%s" % target_url

        desc_content = (
            "【🔥 官方交流群: %s】\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "• 影片名称: %s\n"
            "• 播放源状态: 已解析出 %d 条真实正片播放线路\n"
            "• 默认线路: d000d.com（已自动置顶为默认首选播放）\n"
            "• 品牌专区: 蝴蝶影视致力于为您带来原生极速观影体验。"
        ) % (self.tgGroup, vod_name, len(valid_iframes))

        return {
            "list": [{
                "vod_id": raw_id,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_actor": self.brandActor,
                "vod_director": self.brandDirector,
                "vod_remarks": "共 %d 条线路" % len(valid_iframes),
                "vod_content": desc_content,
                "vod_play_from": "原生专线",
                "vod_play_url": play_url_str
            }]
        }

    def playerContent(self, flag, id, vipFlags):
        url = id.strip()
        if ".mp4" in url.lower() or ".m3u8" in url.lower():
            return {
                "parse": 0,
                "playUrl": "",
                "url": url,
                "header": json.dumps({"User-Agent": self._ua, "Referer": self.siteUrl + "/"})
            }

        res = self._fetch(url, referer=self.siteUrl + "/")
        iframe_html = res.get("text", "")

        m_direct = re.search(r'(https?://[^\s"\'<>]+\.(?:mp4|m3u8)[^\s"\'<>]*)', iframe_html, re.I)
        if m_direct:
            return {
                "parse": 0,
                "playUrl": "",
                "url": m_direct.group(1),
                "header": json.dumps({"User-Agent": self._ua, "Referer": url})
            }

        m_pass = re.search(r'/pass_md5/[^"\']+', iframe_html)
        if m_pass:
            domain = urllib.parse.urlparse(url).netloc
            pass_url = "https://" + domain + m_pass.group(0)
            token_resp = self._fetch(pass_url, referer=url)
            prefix = token_resp.get("text", "").strip()
            if prefix:
                token = m_pass.group(0).split("/")[-1]
                final_stream = prefix + "1234567890?token=" + token
                return {
                    "parse": 0,
                    "playUrl": "",
                    "url": final_stream,
                    "header": json.dumps({"User-Agent": self._ua, "Referer": url})
                }

        return {
            "parse": 1,
            "playUrl": "",
            "url": url,
            "header": json.dumps({"User-Agent": self._ua, "Referer": self.siteUrl + "/"})
        }

    def searchContent(self, key, quick, pg="1"):
        try:
            page_num = max(1, int(str(pg).strip() or 1))
        except Exception:
            page_num = 1
        encoded_key = urllib.parse.quote(str(key))
        target_url = "%s/page/%d/?s=%s" % (self.siteUrl, page_num, encoded_key) if page_num > 1 else "%s/?s=%s" % (self.siteUrl, encoded_key)

        res = self._fetch(target_url)
        html_text = res.get("text", "")

        vod_list = []
        seen = set()
        pattern = r'(<a[^>]+href=["\'](https?://vintagepornfun\.com/\d{4}/\d{2}/\d{2}/[^"\']+)["\'][^>]*>[\s\S]*?</a>)'
        items = re.findall(pattern, html_text, re.I)

        for block, href in items:
            clean_href = href.strip()
            if clean_href in seen:
                continue
            seen.add(clean_href)

            title_m = re.search(r'title=["\']([^"\']+)["\']', block)
            if not title_m:
                title_m = re.search(r'alt=["\']([^"\']+)["\']', block)
            title = self._unesc(title_m.group(1)) if title_m else "经典视频"

            pic_m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', block, re.I)
            pic = pic_m.group(1).strip() if pic_m else ""

            b64_href = base64.urlsafe_b64encode(clean_href.encode("utf-8")).decode("utf-8").rstrip("=")
            vod_list.append({
                "vod_id": "v_" + b64_href,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": "搜索结果"
            })

        return {"page": page_num, "pagecount": page_num + 1 if len(vod_list) >= 10 else page_num, "list": vod_list}
