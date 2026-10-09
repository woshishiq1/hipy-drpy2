# -*- coding: utf-8 -*-
import json
import re
import ssl
import urllib.request
import urllib.parse
import gzip
import zlib

try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider(object):
        pass


class Spider(BaseSpider):

    def __init__(self):
        super(Spider, self).__init__()
        self.site_url = "https://ukqfm.myacetweay.buzz/chu/"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "keep-alive",
            "Referer": "https://ukqfm.myacetweay.buzz/chu/"
        }

    def init(self, extend=""):
        pass

    def homeContent(self, filter):
        classes = [
            {"type_id": "18", "type_name": "精品综合A"},
            {"type_id": "48", "type_name": "精品综合B"},
            {"type_id": "61", "type_name": "精品综合C"},
            {"type_id": "132", "type_name": "精品综合D"},
            {"type_id": "160", "type_name": "成人动漫"},
            {"type_id": "1", "type_name": "国产专区"},
            {"type_id": "2", "type_name": "日本专区"},
            {"type_id": "5", "type_name": "欧美专区"},
            {"type_id": "6", "type_name": "传媒自拍"}
        ]

        filters = {
            "18": [
                {
                    "key": "sub_id",
                    "name": "细分子类",
                    "value": [
                        {"n": "全部", "v": ""},
                        {"n": "日韩无码", "v": "19"},
                        {"n": "强奸乱伦", "v": "20"},
                        {"n": "欧美精品", "v": "21"},
                        {"n": "人妻系列", "v": "22"},
                        {"n": "中文字幕", "v": "23"},
                        {"n": "动漫精品", "v": "24"},
                        {"n": "日韩精品", "v": "25"},
                        {"n": "伦理影片", "v": "26"},
                        {"n": "制服诱惑", "v": "27"},
                        {"n": "自拍偷拍", "v": "28"},
                        {"n": "3P合辑", "v": "29"},
                        {"n": "AV明星", "v": "30"},
                        {"n": "巨乳系列", "v": "31"},
                        {"n": "颜射系列", "v": "32"},
                        {"n": "口交视频", "v": "33"},
                        {"n": "自慰系列", "v": "34"},
                        {"n": "国产精品", "v": "35"},
                        {"n": "SM重味", "v": "36"},
                        {"n": "教师学生", "v": "37"},
                        {"n": "大秀视频", "v": "38"}
                    ]
                }
            ],
            "48": [
                {
                    "key": "sub_id",
                    "name": "细分子类",
                    "value": [
                        {"n": "全部", "v": ""},
                        {"n": "国产精品", "v": "49"},
                        {"n": "华语AV", "v": "50"},
                        {"n": "黑料吃瓜", "v": "51"},
                        {"n": "欧美", "v": "52"},
                        {"n": "禁漫", "v": "53"},
                        {"n": "学生", "v": "54"},
                        {"n": "乱伦", "v": "55"},
                        {"n": "探花", "v": "56"},
                        {"n": "日本有码", "v": "57"},
                        {"n": "日本无码", "v": "58"},
                        {"n": "主播网红", "v": "59"},
                        {"n": "日本素人", "v": "60"}
                    ]
                }
            ],
            "61": [
                {
                    "key": "sub_id",
                    "name": "细分子类",
                    "value": [
                        {"n": "全部", "v": ""},
                        {"n": "精品推荐", "v": "62"},
                        {"n": "国产色情", "v": "63"},
                        {"n": "主播直播", "v": "64"},
                        {"n": "亚洲无码", "v": "65"},
                        {"n": "中文字幕", "v": "66"},
                        {"n": "巨乳美乳", "v": "67"},
                        {"n": "人妻熟女", "v": "68"},
                        {"n": "欧美精品", "v": "69"},
                        {"n": "强奸乱伦", "v": "70"},
                        {"n": "萝莉少女", "v": "71"},
                        {"n": "亚洲有码", "v": "72"},
                        {"n": "伦理三级", "v": "73"},
                        {"n": "成人动漫", "v": "74"},
                        {"n": "自拍偷拍", "v": "75"},
                        {"n": "制服丝袜", "v": "76"},
                        {"n": "口交颜射", "v": "77"},
                        {"n": "日本精品", "v": "78"},
                        {"n": "Cosplay", "v": "79"},
                        {"n": "素人自拍", "v": "80"},
                        {"n": "台湾辣妹", "v": "81"}
                    ]
                }
            ],
            "132": [
                {
                    "key": "sub_id",
                    "name": "细分子类",
                    "value": [
                        {"n": "全部", "v": ""},
                        {"n": "日韩无码", "v": "133"},
                        {"n": "国产精品", "v": "134"},
                        {"n": "日韩精品", "v": "135"},
                        {"n": "欧美精品", "v": "136"},
                        {"n": "动漫精品", "v": "137"},
                        {"n": "自拍偷拍", "v": "138"},
                        {"n": "伦理影片", "v": "139"},
                        {"n": "中文字幕", "v": "140"},
                        {"n": "人妻系列", "v": "141"},
                        {"n": "制服诱惑", "v": "142"},
                        {"n": "强奸乱伦", "v": "143"},
                        {"n": "AV明星", "v": "144"},
                        {"n": "SM重味", "v": "145"},
                        {"n": "巨乳系列", "v": "146"},
                        {"n": "颜射系列", "v": "147"},
                        {"n": "口交视频", "v": "148"},
                        {"n": "自慰系列", "v": "149"},
                        {"n": "教师学生", "v": "150"},
                        {"n": "大秀视频", "v": "151"},
                        {"n": "明星换脸", "v": "152"}
                    ]
                }
            ],
            "1": [
                {
                    "key": "sub_id",
                    "name": "细分子类",
                    "value": [
                        {"n": "全部", "v": ""},
                        {"n": "国产传媒", "v": "1"},
                        {"n": "国产主播", "v": "3"},
                        {"n": "91大神", "v": "4"},
                        {"n": "日本有码", "v": "7"},
                        {"n": "日本无码", "v": "8"},
                        {"n": "动漫肉番", "v": "10"},
                        {"n": "女同性恋", "v": "11"},
                        {"n": "中文字幕", "v": "12"},
                        {"n": "强奸乱伦", "v": "13"},
                        {"n": "熟女人妻", "v": "14"},
                        {"n": "制服诱惑", "v": "15"},
                        {"n": "AV解说", "v": "16"},
                        {"n": "女星换脸", "v": "17"},
                        {"n": "欧美精品", "v": "444"}
                    ]
                }
            ]
        }

        return {
            "class": classes,
            "filters": filters
        }

    def homeVideoContent(self):
        return {"list": []}

    def _fetch(self, url):
        try:
            ctx = ssl._create_unverified_context()
        except Exception:
            ctx = None

        req = urllib.request.Request(url, headers=self.headers)
        try:
            if ctx:
                resp = urllib.request.urlopen(req, context=ctx, timeout=12)
            else:
                resp = urllib.request.urlopen(req, timeout=12)

            headers_dict = dict(resp.info())
            raw_data = resp.read()

            content_encoding = headers_dict.get("Content-Encoding", "").lower()
            if "gzip" in content_encoding:
                try:
                    html_content = gzip.decompress(raw_data).decode("utf-8", "ignore")
                except Exception:
                    html_content = raw_data.decode("utf-8", "ignore")
            elif "deflate" in content_encoding:
                try:
                    html_content = zlib.decompress(raw_data).decode("utf-8", "ignore")
                except Exception:
                    html_content = raw_data.decode("utf-8", "ignore")
            else:
                html_content = raw_data.decode("utf-8", "ignore")

            return {
                "success": True,
                "status_code": resp.getcode(),
                "real_url": resp.geturl(),
                "html": html_content
            }
        except Exception as e:
            return {
                "success": False,
                "status_code": 0,
                "real_url": "",
                "error": str(e),
                "html": ""
            }

    def _parse_vod_list(self, html, base_url):
        vod_list = []
        item_blocks = re.findall(r'(<li[^>]*class=[\'"][^\'"]*(?:item|col)[^\'"]*[\'"][^>]*>[\s\S]*?</li>)', html, re.I)
        if not item_blocks:
            item_blocks = re.findall(r'(<div[^>]*class=[\'"][^\'"]*(?:item|col)[^\'"]*[\'"][^>]*>[\s\S]*?</div>)', html, re.I)

        for block in item_blocks:
            if "openPage(" in block or "heiliaomimi" in block or "javascript:void(0)" in block:
                continue

            detail_m = re.search(r'href=[\'"]([^\'"]*(?:/voddetail/|\.html\?id=)(\d+)[^\'"]*)[\'"]', block, re.I)
            if not detail_m:
                continue
            v_id = detail_m.group(2)

            raw_img_m = re.search(r'(<img[^>]+>)', block, re.I)
            raw_img_tag = raw_img_m.group(1) if raw_img_m else ""

            v_pic = ""
            attr_patterns = [
                r'data-original=[\'"]([^\'"]+)[\'"]',
                r'data-src=[\'"]([^\'"]+)[\'"]',
                r'data-echo=[\'"]([^\'"]+)[\'"]',
                r'data-bg=[\'"]([^\'"]+)[\'"]',
                r'data-url=[\'"]([^\'"]+)[\'"]',
                r'src=[\'"]([^\'"]+)[\'"]'
            ]

            if raw_img_tag:
                for pat in attr_patterns:
                    m = re.search(pat, raw_img_tag, re.I)
                    if m:
                        candidate_pic = m.group(1).strip()
                        if candidate_pic and not candidate_pic.endswith("favicon.ico") and not candidate_pic.startswith("data:image"):
                            v_pic = candidate_pic
                            break

                if not v_pic:
                    fallback_m = re.search(r'src=[\'"]([^\'"]+)[\'"]', raw_img_tag, re.I)
                    if fallback_m:
                        v_pic = fallback_m.group(1).strip()

            if v_pic:
                if v_pic.startswith("//"):
                    v_pic = "https:" + v_pic
                elif v_pic.startswith("/"):
                    v_pic = urllib.parse.urljoin(base_url, v_pic)

            title_m = re.search(r'alt=[\'"]([^\'"]+)[\'"]', block, re.I)
            if not title_m:
                title_m = re.search(r'title=[\'"]([^\'"]+)[\'"]', block, re.I)
            v_name = title_m.group(1).strip() if title_m else ""
            if not v_name:
                text_m = re.search(r'<a[^>]+href=[^>]+>([^<]+)</a>', block, re.I)
                v_name = text_m.group(1).strip() if text_m else "视频 %s" % v_id

            remarks_m = re.search(r'<small>([0-9]{2}:[0-9]{2}(?::[0-9]{2})?)</small>', block, re.I)
            if remarks_m:
                v_remarks = "蝴蝶影视 | %s" % remarks_m.group(1).strip()
            else:
                v_remarks = "蝴蝶影视 | 高清"

            vod_list.append({
                "vod_id": v_id,
                "vod_name": v_name,
                "vod_pic": v_pic,
                "vod_remarks": v_remarks,
                "style": {"type": "rect", "ratio": 1.78}
            })

        return vod_list

    def categoryContent(self, tid, pg, filter, extend):
        actual_tid = tid
        if extend and isinstance(extend, dict) and extend.get("sub_id"):
            actual_tid = extend.get("sub_id")

        page_num = int(pg) if str(pg).isdigit() else 1

        candidate_urls = []
        if page_num <= 1:
            candidate_urls.append("https://ukqfm.myacetweay.buzz/chu/vodtype/%s.html" % actual_tid)
            candidate_urls.append("https://ukqfm.myacetweay.buzz/vodtype/%s.html" % actual_tid)
            candidate_urls.append("https://ukqfm.myacetweay.buzz/vodtype/%s/" % actual_tid)
        else:
            candidate_urls.append("https://ukqfm.myacetweay.buzz/chu/vodtype/%s-%d.html" % (actual_tid, page_num))
            candidate_urls.append("https://ukqfm.myacetweay.buzz/vodtype/%s-%d.html" % (actual_tid, page_num))
            candidate_urls.append("https://ukqfm.myacetweay.buzz/vodtype/%s-%d/" % (actual_tid, page_num))

        html = ""
        success_url = ""

        for u in candidate_urls:
            res = self._fetch(u)
            if res.get("success") and len(res.get("html", "")) > 500:
                html = res.get("html", "")
                success_url = res.get("real_url", u)
                break

        vod_list = self._parse_vod_list(html, success_url if success_url else self.site_url) if html else []

        return {
            "page": page_num,
            "pagecount": page_num + 1 if len(vod_list) >= 12 else page_num,
            "limit": 20,
            "total": 999,
            "list": vod_list
        }

    def detailContent(self, ids):
        vod_id = ids[0] if isinstance(ids, list) else ids

        detail_urls = [
            "https://ukqfm.myacetweay.buzz/voddetail/%s.html" % vod_id,
            "https://ukqfm.myacetweay.buzz/chu/voddetail/%s.html" % vod_id
        ]

        html = ""
        success_url = ""
        for u in detail_urls:
            res = self._fetch(u)
            if res.get("success") and len(res.get("html", "")) > 500:
                html = res.get("html", "")
                success_url = res.get("real_url", u)
                break

        title = ""
        pic = ""
        type_name = "蝴蝶专区"
        year = "2026"
        area = "华语"
        content_desc = "蝴蝶影视官方正版资源，关注TG群: @tvshare23 获取最新动态与防失联地址。"

        play_tabs = []
        play_lists = []

        if html:
            title_m = re.search(r'<h1[^>]*>([^<]+)</h1>', html, re.I)
            if title_m:
                title = title_m.group(1).strip()
            else:
                title_alt = re.search(r'<title>([^-<]+)', html, re.I)
                title = title_alt.group(1).strip() if title_alt else "正片 %s" % vod_id

            img_m = re.search(r'<div[^>]*class=[\'"][^\'"]*poster[^\'"]*[\'"][^>]*>[\s\S]*?<img[^>]+(?:data-original|data-src|src)=[\'"]([^\'"]+)[\'"]', html, re.I)
            if not img_m:
                img_m = re.search(r'<img[^>]+class=[\'"][^\'"]*lazy[^\'"]*[\'"][^>]+(?:data-original|data-src|src)=[\'"]([^\'"]+)[\'"]', html, re.I)
            if img_m:
                pic = img_m.group(1).strip()
                if pic.startswith("//"):
                    pic = "https:" + pic
                elif pic.startswith("/"):
                    pic = urllib.parse.urljoin(success_url, pic)

            desc_m = re.search(r'<div[^>]*class=[\'"][^\'"]*(?:desc|content|detail-content)[^\'"]*[\'"][^>]*>([\s\S]*?)</div>', html, re.I)
            if desc_m:
                clean_desc = re.sub(r'<[^>]+>', '', desc_m.group(1)).strip()
                if clean_desc:
                    content_desc = "🦋 蝴蝶影视 | TG群: @tvshare23\n" + clean_desc

            type_m = re.search(r'<a[^>]+href=[\'"][^\'"]*vodtype/(\d+)[^\'"]*[\'"][^>]*>([^<]+)</a>', html, re.I)
            if type_m:
                type_name = type_m.group(2).strip()

            play_urls_raw = re.findall(r'<a[^>]+href=[\'"]([^\'"]*vodplay/([^\'"]+)\.html)[^\'"]*[\'"][^>]*>([^<]*)</a>', html, re.I)

            episodes = []
            if play_urls_raw:
                for full_href, play_param, ep_title in play_urls_raw:
                    ep_name = ep_title.strip() if ep_title.strip() else "正片"
                    full_play_url = urllib.parse.urljoin(success_url, full_href)
                    episodes.append("%s$%s" % (ep_name, full_play_url))
            else:
                btn_m = re.search(r'<a[^>]+href=[\'"]([^\'"]*vodplay/[^\'"]*)[\'"]', html, re.I)
                if btn_m:
                    single_url = urllib.parse.urljoin(success_url, btn_m.group(1))
                    episodes.append("高清正片$%s" % single_url)
                else:
                    episodes.append("高清正片$https://ukqfm.myacetweay.buzz/vodplay/%s-1-1.html" % vod_id)

            play_tabs.append("蝴蝶秒播云")
            play_lists.append("#".join(episodes))

        vod_detail = {
            "vod_id": vod_id,
            "vod_name": title,
            "vod_pic": pic,
            "type_name": type_name,
            "vod_year": year,
            "vod_area": area,
            "vod_remarks": "蝴蝶影视 | 高清原画",
            "vod_actor": "🦋 TG群: @tvshare23",
            "vod_director": "🦋 蝴蝶影视",
            "vod_content": content_desc,
            "vod_play_from": "$$$".join(play_tabs) if play_tabs else "蝴蝶秒播云",
            "vod_play_url": "$$$".join(play_lists) if play_lists else "高清正片$https://ukqfm.myacetweay.buzz/vodplay/%s-1-1.html" % vod_id
        }

        return {"list": [vod_detail]}

    def playerContent(self, flag, id, vipFlags):
        play_url = id
        res = self._fetch(play_url)
        play_html = res.get("html", "")

        target_m3u8 = ""

        if play_html:
            cfg_m = re.search(r'var\s+player_data\s*=\s*(\{[\s\S]*?\});', play_html, re.I)
            if not cfg_m:
                cfg_m = re.search(r'var\s+player_aaaa\s*=\s*(\{[\s\S]*?\});', play_html, re.I)

            if cfg_m:
                cfg_str = cfg_m.group(1)
                url_m = re.search(r'[\'"]url[\'"]\s*:\s*[\'"]([^\'"]+)[\'"]', cfg_str)
                if url_m:
                    target_m3u8 = url_m.group(1).replace("\\/", "/")

            if not target_m3u8:
                m3u8_matches = re.findall(r'[\'"](https?://[^\'"]+\.m3u8[^\'"]*)[\'"]', play_html, re.I)
                if m3u8_matches:
                    target_m3u8 = m3u8_matches[0]

        final_url = target_m3u8 if target_m3u8 else play_url
        need_parse = 0 if target_m3u8 else 1

        return {
            "parse": need_parse,
            "playUrl": "",
            "url": final_url,
            "header": json.dumps({
                "User-Agent": self.headers["User-Agent"],
                "Referer": play_url
            })
        }

    def searchContent(self, key, quick, pg="1"):
        page_num = int(pg) if str(pg).isdigit() else 1
        encoded_key = urllib.parse.quote(key)
        
        search_urls = [
            "https://ukqfm.myacetweay.buzz/vodsearch/%s----------%d---.html" % (encoded_key, page_num),
            "https://ukqfm.myacetweay.buzz/chu/vodsearch/%s----------%d---.html" % (encoded_key, page_num)
        ]

        html = ""
        success_url = ""
        for u in search_urls:
            res = self._fetch(u)
            if res.get("success") and len(res.get("html", "")) > 500:
                html = res.get("html", "")
                success_url = res.get("real_url", u)
                break

        vod_list = self._parse_vod_list(html, success_url if success_url else self.site_url) if html else []

        return {
            "page": page_num,
            "pagecount": page_num + 1 if len(vod_list) >= 12 else page_num,
            "limit": 20,
            "total": 999,
            "list": vod_list
        }

    def action(self, action):
        return {}

    def liveContent(self):
        return {}

    def localProxy(self, params):
        return [200, "text/plain; charset=utf-8", ""]

    def manualVideoCheck(self):
        return False

    def isVideoFormat(self, url):
        return False

    def destroy(self):
        pass