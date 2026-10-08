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
        def __init__(self, *args, **kwargs):
            self.t4_api = kwargs.get("t4_api", "")
        def getCache(self, key): return None
        def setCache(self, key, value): return "fail"
        def delCache(self, key): return "fail"
        def getProxyUrl(self, flag=False): return getattr(self, "t4_api", "")


# =====================================================================
# 纯 Python 标准库内置 AES-128-CBC 解密引擎
# =====================================================================
class _PureAES128CBC(object):
    S_BOX = [
        0x63, 0x7c, 0x77, 0x7b, 0xf2, 0x6b, 0x6f, 0xc5, 0x30, 0x01, 0x67, 0x2b, 0xfe, 0xd7, 0xab, 0x76,
        0xca, 0x82, 0xc9, 0x7d, 0xfa, 0x59, 0x47, 0xf0, 0xad, 0xd4, 0xa2, 0xaf, 0x9c, 0xa4, 0x72, 0xc0,
        0xb7, 0xfd, 0x93, 0x26, 0x36, 0x3f, 0xf7, 0xcc, 0x34, 0xa5, 0xe5, 0xf1, 0x71, 0xd8, 0x31, 0x15,
        0x04, 0xc7, 0x23, 0xc3, 0x18, 0x96, 0x05, 0x9a, 0x07, 0x12, 0x80, 0xe2, 0xeb, 0x27, 0xb2, 0x75,
        0x09, 0x83, 0x2c, 0x1a, 0x1b, 0x6e, 0x5a, 0xa0, 0x52, 0x3b, 0xd6, 0xb3, 0x29, 0xe3, 0x2f, 0x84,
        0x53, 0xd1, 0x00, 0xed, 0x20, 0xfc, 0xb1, 0x5b, 0x6a, 0xcb, 0xbe, 0x39, 0x4a, 0x4c, 0x58, 0xcf,
        0xd0, 0xef, 0xaa, 0xfb, 0x43, 0x4d, 0x33, 0x85, 0x45, 0xf9, 0x02, 0x7f, 0x50, 0x3c, 0x9f, 0xa8,
        0x51, 0xa3, 0x40, 0x8f, 0x92, 0x9d, 0x38, 0xf5, 0xbc, 0xb6, 0xda, 0x21, 0x10, 0xff, 0xf3, 0xd2,
        0xcd, 0x0c, 0x13, 0xec, 0x5f, 0x97, 0x44, 0x17, 0xc4, 0xa7, 0x7e, 0x3d, 0x64, 0x5d, 0x19, 0x73,
        0x60, 0x81, 0x4f, 0xdc, 0x22, 0x2a, 0x90, 0x88, 0x46, 0xee, 0xb8, 0x14, 0xde, 0x5e, 0x0b, 0xdb,
        0xe0, 0x32, 0x3a, 0x0a, 0x49, 0x06, 0x24, 0x5c, 0xc2, 0xd3, 0xac, 0x62, 0x91, 0x95, 0xe4, 0x79,
        0xe7, 0xc8, 0x37, 0x6d, 0x8d, 0xd5, 0x4e, 0xa9, 0x6c, 0x56, 0xf4, 0xea, 0x65, 0x7a, 0xae, 0x08,
        0xba, 0x78, 0x25, 0x2e, 0x1c, 0xa6, 0xb4, 0xc6, 0xe8, 0xdd, 0x74, 0x1f, 0x4b, 0xbd, 0x8b, 0x8a,
        0x70, 0x3e, 0xb5, 0x66, 0x48, 0x03, 0xf6, 0x0e, 0x61, 0x35, 0x57, 0xb9, 0x86, 0xc1, 0x1d, 0x9e,
        0xe1, 0xf8, 0x98, 0x11, 0x69, 0xd9, 0x8e, 0x94, 0x9b, 0x1e, 0x87, 0xe9, 0xce, 0x55, 0x28, 0xdf,
        0x8c, 0xa1, 0x89, 0x0d, 0xbf, 0xe6, 0x42, 0x68, 0x41, 0x99, 0x2d, 0x0f, 0xb0, 0x54, 0xbb, 0x16
    ]
    INV_S_BOX = [0] * 256
    R_CON = [0x00, 0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1b, 0x36]

    for i in range(256):
        INV_S_BOX[S_BOX[i]] = i

    @staticmethod
    def _xtime(a):
        return (((a << 1) ^ 0x1B) & 0xFF) if (a & 0x80) else (a << 1)

    @classmethod
    def _mul(cls, a, b):
        res = 0
        for _ in range(8):
            if b & 1:
                res ^= a
            a = cls._xtime(a)
            b >>= 1
        return res

    def __init__(self, key, iv):
        self.key = list(key)
        self.iv = list(iv)
        self.w = self._key_expansion(self.key)

    def _key_expansion(self, key):
        w = [0] * 44
        for i in range(4):
            w[i] = (key[4 * i] << 24) | (key[4 * i + 1] << 16) | (key[4 * i + 2] << 8) | key[4 * i + 3]
        for i in range(4, 44):
            temp = w[i - 1]
            if i % 4 == 0:
                temp = ((temp << 8) & 0xFFFFFFFF) | (temp >> 24)
                temp = (
                    (self.S_BOX[(temp >> 24) & 0xFF] << 24) |
                    (self.S_BOX[(temp >> 16) & 0xFF] << 16) |
                    (self.S_BOX[(temp >> 8) & 0xFF] << 8) |
                    self.S_BOX[temp & 0xFF]
                )
                temp ^= (self.R_CON[i // 4] << 24)
            w[i] = w[i - 4] ^ temp
        return w

    def _inv_sub_bytes(self, s):
        for r in range(4):
            for c in range(4):
                s[r][c] = self.INV_S_BOX[s[r][c]]

    def _inv_shift_rows(self, s):
        s[1][0], s[1][1], s[1][2], s[1][3] = s[1][3], s[1][0], s[1][1], s[1][2]
        s[2][0], s[2][1], s[2][2], s[2][3] = s[2][2], s[2][3], s[2][0], s[2][1]
        s[3][0], s[3][1], s[3][2], s[3][3] = s[3][1], s[3][2], s[3][3], s[3][0]

    def _inv_mix_columns(self, s):
        for c in range(4):
            u0, u1, u2, u3 = s[0][c], s[1][c], s[2][c], s[3][c]
            s[0][c] = self._mul(0x0e, u0) ^ self._mul(0x0b, u1) ^ self._mul(0x0d, u2) ^ self._mul(0x09, u3)
            s[1][c] = self._mul(0x09, u0) ^ self._mul(0x0e, u1) ^ self._mul(0x0b, u2) ^ self._mul(0x0d, u3)
            s[2][c] = self._mul(0x0d, u0) ^ self._mul(0x09, u1) ^ self._mul(0x0e, u2) ^ self._mul(0x0b, u3)
            s[3][c] = self._mul(0x0b, u0) ^ self._mul(0x0d, u1) ^ self._mul(0x09, u2) ^ self._mul(0x0e, u3)

    def _add_round_key(self, s, rnd):
        for c in range(4):
            word = self.w[rnd * 4 + c]
            s[0][c] ^= (word >> 24) & 0xFF
            s[1][c] ^= (word >> 16) & 0xFF
            s[2][c] ^= (word >> 8) & 0xFF
            s[3][c] ^= word & 0xFF

    def _decrypt_block(self, block):
        state = [[block[r + 4 * c] for c in range(4)] for r in range(4)]
        self._add_round_key(state, 10)
        for rnd in range(9, 0, -1):
            self._inv_shift_rows(state)
            self._inv_sub_bytes(state)
            self._add_round_key(state, rnd)
            self._inv_mix_columns(state)
        self._inv_shift_rows(state)
        self._inv_sub_bytes(state)
        self._add_round_key(state, 0)
        return bytes([state[r][c] for c in range(4) for r in range(4)])

    def decrypt(self, ciphertext):
        iv = list(self.iv)
        out = bytearray()
        for i in range(0, len(ciphertext), 16):
            blk = ciphertext[i:i + 16]
            if len(blk) < 16:
                break
            dec_blk = self._decrypt_block(blk)
            xored = bytes([dec_blk[k] ^ iv[k] for k in range(16)])
            out.extend(xored)
            iv = list(blk)
        if out:
            pad = out[-1]
            if 0 < pad <= 16:
                if out[-pad:] == bytes([pad]) * pad:
                    return bytes(out[:-pad])
        return bytes(out)


# =====================================================================
# 蜂蜜影视生产级蜘蛛实现
# =====================================================================
class Spider(SpiderBase):
    AES_KEY = b"f5d965df75336270"
    AES_IV = b"97b60394abc2fbe1"

    AD_KEYWORDS = {
        "app", "911爆料app", "下载app", "官方推荐", "加入911", "章鱼导航", "欲洛降临",
        "七夕活动", "911暑期活动", "回家的路", "投稿方式", "常见问题", "广告商务",
        "所有标签", "关于我们", "官方tg群", "官方推特", "ai换脸脱衣", "广告", "商务合作"
    }

    DOMAIN_POOL = [
        "https://d10cq29fdobmmg.cloudfront.net",
        "https://barely.jysznvsj.cc",
        "https://abopf.jysznvsj.cc",
        "https://catch.belwfufv.cc",
        "https://911bla.com",
        "https://911bl16.com",
        "https://911bl.com"
    ]

    def __init__(self, *args, **kwargs):
        super(Spider, self).__init__(*args, **kwargs)
        self.t4_api = kwargs.get("t4_api", "")
        self.siteUrl = self.DOMAIN_POOL[0]
        self.tgGroup = "https://t.me/tvshare23"
        self.brandActor = "🦋 TG群: @tvshare23"
        self.brandDirector = "🦋 蝴蝶影视"
        self._ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1"
        self.options = {}

        self.categories = [
            {"type_id": "category/jrgb", "type_name": "今日大瓜"},
            {"type_id": "category/aidj", "type_name": "AI短剧"},
            {"type_id": "category/shijiebei", "type_name": "优先投放区"},
            {"type_id": "category/mrds", "type_name": "每日大赛"},
            {"type_id": "category/hjsq", "type_name": "海角社区"},
            {"type_id": "category/crfys", "type_name": "午夜剧场"},
            {"type_id": "category/dmhv", "type_name": "动漫天堂"},
            {"type_id": "category/sgpjs", "type_name": "水果派解说"},
            {"type_id": "category/rmgb", "type_name": "独家爆料"}
        ]

        self.ctx = ssl.create_default_context()
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE

        self.cj = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cj),
            urllib.request.HTTPSHandler(context=self.ctx)
        )

    def init(self, extend=""):
        if isinstance(extend, dict):
            self.options = extend
        elif extend:
            try:
                self.options = json.loads(extend)
            except Exception:
                self.options = {}

        cached_url = self.getCache("active_site_url")
        if cached_url and str(cached_url) not in ("fail", "None", ""):
            self.siteUrl = str(cached_url)
        return True

    def getName(self):
        return "蝴蝶生产级蜘蛛·911爆料网"

    def isVideoFormat(self, url):
        return bool(re.search(r'\.(?:m3u8|mp4|flv|m4a|ts)(?:$|[?#])', str(url or ''), re.I))

    def manualVideoCheck(self):
        return False

    def destroy(self):
        self.options = {}

    def _fix_url(self, url):
        if not url:
            return ""
        url = str(url).strip()
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("http://") or url.startswith("https://"):
            return url
        return urllib.parse.urljoin(self.siteUrl, url)

    # 动态探测宿主注入的 localProxy 基础地址
    def _proxy_base(self):
        try:
            f = getattr(self, "getProxyUrl", None)
            if callable(f):
                u = f(True) or f()
                if u:
                    return u
        except Exception:
            pass
        return getattr(self, "t4_api", "") or ""

    # 核心：图片路径包装与代理转发链接生成
    def _fix_pic(self, pic):
        if not pic:
            return self.siteUrl + "/usr/themes/Mirages/images/home-cover-placeholder-v2.png"

        pic = str(pic).strip()
        if "type=img" in pic and "url=" in pic:
            return pic

        m = re.search(r"loadBannerDirect\(['\"]([^'\"]+)['\"]", pic)
        if m:
            pic = m.group(1).strip()

        pic_url = self._fix_url(pic)
        if not pic_url or pic_url.startswith("data:image"):
            return self.siteUrl + "/usr/themes/Mirages/images/home-cover-placeholder-v2.png"

        low = pic_url.lower()
        if any(x in low for x in ("loading", "blank", "1px", "default.gif")):
            return self.siteUrl + "/usr/themes/Mirages/images/home-cover-placeholder-v2.png"

        base = self._proxy_base()
        if base:
            sep = "&" if "?" in base else "?"
            if "do=" not in base:
                base = base + sep + "do=py"
                sep = "&"
            return "%s%stype=img&url=%s" % (base, sep, urllib.parse.quote(pic_url, safe=''))

        # 如果宿主未注入 proxy_base，追加 Android Glide 防盗链识别头
        if "@Referer=" not in pic_url:
            pic_url += "@Referer=%s/&User-Agent=%s" % (self.siteUrl, urllib.parse.quote(self._ua))
        return pic_url

    def _request_raw(self, target_url, referer=""):
        headers = {
            "User-Agent": self._ua,
            "Referer": referer if referer else (self.siteUrl + "/"),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "close"
        }
        req = urllib.request.Request(target_url, headers=headers)
        with self.opener.open(req, timeout=10) as resp:
            raw = resp.read()
            if raw.startswith(b"\x1f\x8b"):
                raw = gzip.decompress(raw)
            elif getattr(resp, "headers", {}).get("Content-Encoding") == "deflate":
                try:
                    raw = zlib.decompress(raw)
                except Exception:
                    raw = zlib.decompress(raw, -zlib.MAX_WBITS)
            return resp.getcode(), raw

    def _fetch(self, path_or_url):
        if not path_or_url:
            return ""
        if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
            candidates = [path_or_url]
        else:
            clean_path = path_or_url if path_or_url.startswith("/") else ("/" + path_or_url)
            candidates = ["%s%s" % (h, clean_path) for h in self.DOMAIN_POOL]

        for target in candidates[:3]:
            try:
                code, raw = self._request_raw(target)
                if code == 200:
                    try:
                        return raw.decode("utf-8")
                    except Exception:
                        return raw.decode("latin1", errors="ignore")
            except Exception:
                continue
        return ""

    def homeContent(self, filter):
        result = {"class": self.categories}
        if filter:
            result["filters"] = {}
        return result

    def homeVideoContent(self):
        return self.categoryContent("category/jrgb", "1", False, {})

    # 提取真实三联图属性
    def _extract_pic_from_block(self, b):
        script_m = re.search(r"loadBannerDirect\(['\"]([^'\"]+)['\"]", b)
        if script_m:
            return script_m.group(1).strip()

        # 优先提取 z-image-loader-url 等自定义属性
        for attr in ("z-image-loader-url", "data-xkrkllgl", "data-original", "data-src", "data-cover"):
            m = re.search(r'%s=["\']([^"\']+)["\']' % attr, b, re.I)
            if m:
                val = m.group(1).strip()
                if val and not val.startswith("data:image") and "placeholder" not in val.lower():
                    return val

        meta_m = re.search(r'<meta[^>]+itemprop=["\'](?:image|thumbnailUrl)["\'][^>]+content=["\']([^"\']+)["\']', b, re.I)
        if meta_m and meta_m.group(1).strip():
            return meta_m.group(1).strip()

        bg_m = re.search(r'background-image\s*:\s*url\([\'"]?([^\'")]+)[\'"]?\)', b, re.I)
        if bg_m:
            val = bg_m.group(1).strip()
            if not val.startswith("data:image") and "placeholder" not in val.lower():
                return val

        return ""

    def categoryContent(self, tid, pg, filter, extend):
        del filter
        extend = extend if isinstance(extend, dict) else {}
        slug = str(tid or "category/jrgb").strip("/")
        if not slug.startswith("category/"):
            slug = "category/%s" % slug

        page_num = int(pg) if str(pg).isdigit() and int(pg) > 0 else 1
        req_url = "/%s/%s/" % (slug, page_num) if page_num > 1 else "/%s/" % slug

        html_text = self._fetch(req_url)
        blocks = []
        if "<article" in html_text:
            for b in html_text.split("<article")[1:]:
                cut_b = b.split("</article>")[0]
                if "post-list-ad" in cut_b or ('rel="sponsored"' in cut_b):
                    continue
                blocks.append("<article" + cut_b)

        result_list = []
        for b in blocks:
            link_m = re.search(r'href=["\']([^"\']*/archives/\d+[^"\']*)["\']', b, re.I)
            if not link_m:
                continue
            href = link_m.group(1).strip()

            title = ""
            h_title = re.search(r'<h[23][^>]*>(?:<a[^>]*>)?([^<]+)(?:</a>)?</h[23]>', b, re.I)
            if h_title:
                clean = h_title.group(1).strip()
                if "loadBanner" not in clean and len(clean) > 2:
                    title = clean

            if not title:
                t_m = re.search(r'title=["\']([^"\']+)["\']', b, re.I)
                if t_m and "loadBanner" not in t_m.group(1) and len(t_m.group(1).strip()) > 2:
                    title = t_m.group(1).strip()

            if not title or any(kw in title.lower() for kw in self.AD_KEYWORDS):
                continue

            remarks = ""
            date_m = re.search(r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})', b)
            if date_m:
                remarks = date_m.group(1).strip()

            raw_pic = self._extract_pic_from_block(b)
            final_pic = self._fix_pic(raw_pic)

            result_list.append({
                "vod_id": self._fix_url(href),
                "vod_name": html_lib.unescape(title),
                "vod_pic": final_pic,
                "vod_remarks": remarks,
                "style": {"type": "rect", "ratio": 1.78}
            })

        return {
            "page": page_num,
            "pagecount": page_num + 1 if len(result_list) >= 10 else page_num,
            "limit": len(result_list) if result_list else 20,
            "total": 9999 if result_list else 0,
            "list": result_list
        }

    def detailContent(self, ids):
        raw_id = ids[0] if isinstance(ids, (list, tuple)) else str(ids)
        target_url = self._fix_url(raw_id)
        html_text = self._fetch(target_url)

        title = ""
        t_m = re.search(r'<h1[^>]*>([\s\S]*?)</h1>', html_text, re.I)
        if t_m:
            title = re.sub(r'<[^>]+>', '', t_m.group(1)).strip()

        content = "暂无简介"
        c_m = re.search(r'<div[^>]+class=["\'][^"\']*(?:post-content|entry-content)[^"\']*["\'][^>]*>([\s\S]*?)</div>', html_text, re.I)
        if c_m:
            raw_c = re.sub(r'<(?:script|style|div)[^>]*>[\s\S]*?</(?:script|style|div)>', '', c_m.group(1), flags=re.I)
            clean_c = re.sub(r'<[^>]+>', '', raw_c).strip()
            if clean_c:
                content = re.sub(r'\s+', ' ', clean_c)[:250]

        play_url = ""
        cover_pic = ""

        config_m = re.search(r'data-config=(["\'])([\s\S]*?)\1', html_text, re.I)
        if config_m:
            raw_cfg = html_lib.unescape(html_lib.unescape(config_m.group(2).strip()))
            try:
                cfg_obj = json.loads(raw_cfg)
                v_obj = cfg_obj.get("video", {})
                if isinstance(v_obj, dict):
                    play_url = v_obj.get("url", "")
                    cover_pic = v_obj.get("pic", "")
            except Exception:
                pass

        if not play_url:
            for direct_m in re.finditer(r'(https?://[^\s"\'<>]+\.(?:m3u8|mp4)[^\s"\'<>]*)', html_text, re.I):
                cand = direct_m.group(1).replace(r"\/", "/").replace("\\", "").strip()
                if "advert" not in cand:
                    play_url = cand
                    break

        if not cover_pic:
            og_m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html_text, re.I)
            if og_m and "placeholder" not in og_m.group(1):
                cover_pic = og_m.group(1).strip()

        brand_desc = (
            "【🔥 官方交流群: %s】\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "%s"
        ) % (self.tgGroup, content)
        escaped_desc = brand_desc.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        vod_play_url = "正片直链$%s" % play_url if play_url else "在线播放$%s" % target_url

        return {
            "list": [{
                "vod_id": raw_id,
                "vod_name": html_lib.unescape(title) if title else "精彩视频",
                "vod_pic": self._fix_pic(cover_pic),
                "vod_actor": self.brandActor,
                "vod_director": self.brandDirector,
                "vod_remarks": "高清正片",
                "vod_content": escaped_desc,
                "vod_play_from": "蝴蝶专线",
                "vod_play_url": vod_play_url
            }]
        }

    def playerContent(self, flag, id, vipFlags):
        play_id = str(id or "").strip()
        if "$" in play_id:
            play_id = play_id.split("$")[-1].strip()
        play_id = urllib.parse.unquote(play_id).replace(r'\/', '/').replace('\\', '').strip()

        return {
            "parse": 0,
            "jx": 0,
            "url": play_id,
            "header": {
                "User-Agent": self._ua,
                "Referer": self.siteUrl + "/"
            }
        }

    def searchContent(self, key, quick, pg="1"):
        page_num = int(pg) if str(pg).isdigit() and int(pg) > 0 else 1
        query = urllib.parse.quote(str(key or "").strip())
        req_url = "/search/%s/%s/" % (query, page_num) if page_num > 1 else "/search/%s/" % query

        html_text = self._fetch(req_url)
        blocks = []
        if "<article" in html_text:
            for b in html_text.split("<article")[1:]:
                cut_b = b.split("</article>")[0]
                if "post-list-ad" in cut_b or ('rel="sponsored"' in cut_b):
                    continue
                blocks.append("<article" + cut_b)

        result_list = []
        for b in blocks:
            link_m = re.search(r'href=["\']([^"\']*/archives/\d+[^"\']*)["\']', b, re.I)
            if not link_m:
                continue
            href = link_m.group(1).strip()

            title = ""
            h_title = re.search(r'<h[23][^>]*>(?:<a[^>]*>)?([^<]+)(?:</a>)?</h[23]>', b, re.I)
            if h_title:
                clean = h_title.group(1).strip()
                if "loadBanner" not in clean and len(clean) > 2:
                    title = clean

            if not title:
                continue

            remarks = ""
            date_m = re.search(r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})', b)
            if date_m:
                remarks = date_m.group(1).strip()

            raw_pic = self._extract_pic_from_block(b)

            result_list.append({
                "vod_id": self._fix_url(href),
                "vod_name": html_lib.unescape(title),
                "vod_pic": self._fix_pic(raw_pic),
                "vod_remarks": remarks,
                "style": {"type": "rect", "ratio": 1.78}
            })

        return {
            "page": page_num,
            "pagecount": page_num + 1 if len(result_list) >= 10 else page_num,
            "limit": len(result_list) if result_list else 20,
            "total": 9999 if result_list else 0,
            "list": result_list
        }

    # 本地代理拦截器：支持各种参数格式并执行解密
    def localProxy(self, params):
        url = params.get("url") or params.get("img") or ""
        if isinstance(url, list):
            url = url[0] if url else ""
        if not url:
            return [400, "text/plain", b""]

        url = urllib.parse.unquote(str(url)).strip()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": self._ua, "Referer": self.siteUrl + "/"})
            with self.opener.open(req, timeout=8) as resp:
                content = resp.read()

            is_magic = (
                content.startswith(b"\xff\xd8\xff") or
                content.startswith(b"\x89PNG") or
                content.startswith(b"GIF8") or
                (content[:4] == b"RIFF" and content[8:12] == b"WEBP")
            )

            is_enc = ("/xiao/" in url) or ("/upload" in url) or (not is_magic)
            if is_enc:
                try:
                    cipher = _PureAES128CBC(self.AES_KEY, self.AES_IV)
                    dec = cipher.decrypt(content)
                    if (dec.startswith(b"\xff\xd8\xff") or dec.startswith(b"\x89PNG") or
                            dec.startswith(b"GIF8") or (dec[:4] == b"RIFF" and dec[8:12] == b"WEBP")):
                        content = dec
                except Exception:
                    pass

            mime = "jpeg"
            if content.startswith(b"\x89PNG"):
                mime = "png"
            elif content.startswith(b"GIF8"):
                mime = "gif"
            elif content[:4] == b"RIFF" and content[8:12] == b"WEBP":
                mime = "webp"

            return [200, "image/" + mime, content]
        except Exception as e:
            return [500, "text/plain", str(e).encode("utf-8")]

    def action(self, action):
        if action == "toast":
            return {"msg": "蝴蝶生产级蜘蛛运行正常"}
        return {"msg": "未配置 action"}

    def liveContent(self):
        return ""
