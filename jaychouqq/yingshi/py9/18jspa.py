import sys
import json
import ssl
import gzip
import zlib
import re
import urllib.request
import urllib.parse
import html

try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider(object):
        pass

class Spider(BaseSpider):
    def __init__(self):
        self.site_url = "https://t3.18j61.cc"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "keep-alive"
        }

    def init(self, extend=""):
        pass

    def _fetch(self, url, headers=None):
        req_headers = dict(self.headers)
        if headers:
            req_headers.update(headers)
        req = urllib.request.Request(url, headers=req_headers)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
                raw = resp.read()
                encoding = resp.headers.get("Content-Encoding", "").lower()
                final_url = resp.geturl()
                status_code = resp.getcode()
                if "gzip" in encoding:
                    raw = gzip.decompress(raw)
                elif "deflate" in encoding:
                    raw = zlib.decompress(raw)
                text = ""
                for charset in ["utf-8", "gbk", "gb2312", "iso-8859-1"]:
                    try:
                        text = raw.decode(charset)
                        break
                    except Exception:
                        continue
                return status_code, final_url, text
        except Exception as e:
            return 0, url, str(e)

    def homeContent(self, filter):
        result = {}
        classes = [
            {"type_id": "1", "type_name": "国产"},
            {"type_id": "2", "type_name": "日韩"},
            {"type_id": "3", "type_name": "欧美"},
            {"type_id": "4", "type_name": "伦理"},
            {"type_id": "5", "type_name": "动漫"},
            {"type_id": "6", "type_name": "另类"},
            {"type_id": "9", "type_name": "成人AI"}
        ]
        
        sort_values = [
            {"n": "最近更新", "v": "time"},
            {"n": "今日热播", "v": "hits_day"},
            {"n": "今日点赞", "v": "up_day"},
            {"n": "好评榜", "v": "up"}
        ]

        filters = {
            "1": [
                {
                    "key": "sub_id",
                    "name": "子分类",
                    "value": [
                        {"n": "全部", "v": "1"},
                        {"n": "国产自拍", "v": "11"},
                        {"n": "吃瓜黑料", "v": "12"},
                        {"n": "探花现场", "v": "13"},
                        {"n": "乱伦系列", "v": "14"},
                        {"n": "国产av", "v": "15"},
                        {"n": "福利姬", "v": "16"},
                        {"n": "自慰诱惑", "v": "17"},
                        {"n": "成人主播", "v": "18"}
                    ]
                },
                {"key": "by", "name": "排序", "value": sort_values}
            ],
            "2": [
                {
                    "key": "sub_id",
                    "name": "子分类",
                    "value": [
                        {"n": "全部", "v": "2"},
                        {"n": "无码中字", "v": "19"},
                        {"n": "JAV自拍", "v": "20"},
                        {"n": "中文字幕", "v": "21"},
                        {"n": "jav无码", "v": "22"},
                        {"n": "AV解说", "v": "23"}
                    ]
                },
                {"key": "by", "name": "排序", "value": sort_values}
            ],
            "3": [
                {
                    "key": "sub_id",
                    "name": "子分类",
                    "value": [
                        {"n": "全部", "v": "3"},
                        {"n": "欧美大片", "v": "24"},
                        {"n": "黑人专区", "v": "25"},
                        {"n": "留学生", "v": "26"}
                    ]
                },
                {"key": "by", "name": "排序", "value": sort_values}
            ],
            "4": [
                {
                    "key": "sub_id",
                    "name": "子分类",
                    "value": [
                        {"n": "全部", "v": "4"},
                        {"n": "港台三级", "v": "27"},
                        {"n": "日韩三级", "v": "28"},
                        {"n": "欧美三级", "v": "29"}
                    ]
                },
                {"key": "by", "name": "排序", "value": sort_values}
            ],
            "5": [
                {
                    "key": "sub_id",
                    "name": "子分类",
                    "value": [
                        {"n": "全部", "v": "5"},
                        {"n": "3D动漫", "v": "30"},
                        {"n": "次元动漫", "v": "31"}
                    ]
                },
                {"key": "by", "name": "排序", "value": sort_values}
            ],
            "6": [
                {
                    "key": "sub_id",
                    "name": "子分类",
                    "value": [
                        {"n": "全部", "v": "6"},
                        {"n": "男同GAY", "v": "32"},
                        {"n": "女同百合", "v": "33"},
                        {"n": "伪娘", "v": "34"},
                        {"n": "SM重口", "v": "35"},
                        {"n": "东南亚", "v": "45"}
                    ]
                },
                {"key": "by", "name": "排序", "value": sort_values}
            ],
            "9": [
                {
                    "key": "sub_id",
                    "name": "子分类",
                    "value": [
                        {"n": "全部", "v": "9"},
                        {"n": "AI短剧", "v": "36"},
                        {"n": "明星脸", "v": "37"},
                        {"n": "成人漫剧", "v": "46"}
                    ]
                },
                {"key": "by", "name": "排序", "value": sort_values}
            ]
        }

        result["class"] = classes
        result["filters"] = filters
        return result

    def homeVideoContent(self):
        return {"list": []}

    def _parse_vod_list(self, html_data):
        cards = []
        if not html_data:
            return cards

        item_blocks = re.findall(r'<li[^>]*>(.*?)</li>', html_data, re.I | re.S)
        if not item_blocks:
            item_blocks = re.findall(r'<div[^>]*class=["\'][^"\']*(?:vodlist_item|video-item|box-item|item)[^"\']*["\'][^>]*>(.*?)</div>\s*</div>', html_data, re.I | re.S)

        seen_ids = set()
        for block in item_blocks:
            v_link = re.search(r'href=["\'](/v/[^"\']+)["\']', block, re.I)
            if not v_link:
                continue
            clean_href = v_link.group(1).strip()
            if clean_href in seen_ids:
                continue

            title = ""
            t_match = re.search(r'<(?:a|div|span|h\d)[^>]*class=["\'][^"\']*(?:vodlist_title|title|name)[^"\']*["\'][^>]*>(.*?)</(?:a|div|span|h\d)>', block, re.I | re.S)
            if t_match:
                title = re.sub(r'<[^>]+>', '', t_match.group(1)).strip()

            if not title:
                title_attrs = re.findall(r'title=["\']([^"\']+)["\']', block, re.I)
                for t in title_attrs:
                    t_c = t.strip()
                    if len(t_c) > len(title) and t_c not in ["首页", "短视频", "演员", "标签", "图文", "黑料"]:
                        title = t_c

            if not title:
                a_texts = re.findall(r'<a[^>]+href=["\']/v/[^"\']+["\'][^>]*>(.*?)</a>', block, re.I | re.S)
                for at in a_texts:
                    at_clean = re.sub(r'<[^>]+>', '', at).strip()
                    if len(at_clean) > len(title):
                        title = at_clean

            if not title:
                continue

            title = html.unescape(title)

            pic = ""
            pic_match = re.search(r'(?:data-original|data-src|src)=["\']([^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)["\']', block, re.I)
            if pic_match:
                pic = pic_match.group(1).strip()
                if not pic.startswith("http"):
                    pic = urllib.parse.urljoin(self.site_url, pic)

            remarks_raw = ""
            rem_match = re.search(r'<span[^>]*class=["\'][^"\']*(?:pic-text|duration|remarks|tag)[^"\']*["\'][^>]*>(.*?)</span>', block, re.I | re.S)
            if rem_match:
                remarks_raw = re.sub(r'<[^>]+>', '', rem_match.group(1)).strip()

            if remarks_raw:
                remarks = "蝴蝶影视 | %s" % remarks_raw
            else:
                remarks = "蝴蝶影视"

            seen_ids.add(clean_href)
            cards.append({
                "vod_id": clean_href,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remarks,
                "vod_actor": "🦋 TG群: @tvshare23",
                "vod_director": "🦋 蝴蝶影视",
                "style": {"type": "rect", "ratio": 1.78}
            })

        if not cards:
            matches = re.findall(r'<a[^>]+href=["\'](/v/[^"\']+)["\'][^>]*title=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html_data, re.I | re.S)
            for href, t_attr, inner_html in matches:
                clean_href = href.strip()
                if clean_href in seen_ids:
                    continue
                t_clean = html.unescape(t_attr.strip())
                if not t_clean or len(t_clean) <= 4:
                    continue
                
                pic = ""
                p_m = re.search(r'(?:data-original|data-src|src)=["\']([^"\']+)["\']', inner_html, re.I)
                if p_m:
                    pic = p_m.group(1).strip()
                    if not pic.startswith("http"):
                        pic = urllib.parse.urljoin(self.site_url, pic)
                
                seen_ids.add(clean_href)
                cards.append({
                    "vod_id": clean_href,
                    "vod_name": t_clean,
                    "vod_pic": pic,
                    "vod_remarks": "蝴蝶影视",
                    "vod_actor": "🦋 TG群: @tvshare23",
                    "vod_director": "🦋 蝴蝶影视",
                    "style": {"type": "rect", "ratio": 1.78}
                })

        return cards

    def categoryContent(self, tid, pg, filter, extend):
        actual_tid = tid
        if extend and "sub_id" in extend and extend["sub_id"]:
            actual_tid = extend["sub_id"]
        
        sort_by = "time"
        if extend and "by" in extend and extend["by"]:
            sort_by = extend["by"]
        
        pg_int = int(pg) if str(pg).isdigit() else 1
        
        if sort_by == "time":
            if pg_int <= 1:
                req_url = "%s/t/%s/" % (self.site_url, actual_tid)
            else:
                req_url = "%s/show/%s/page/%s/" % (self.site_url, actual_tid, pg_int)
        else:
            if pg_int <= 1:
                req_url = "%s/show/%s/by/%s/" % (self.site_url, actual_tid, sort_by)
            else:
                req_url = "%s/show/%s/by/%s/page/%s/" % (self.site_url, actual_tid, sort_by, pg_int)

        code, final_url, html_data = self._fetch(req_url)
        cards = self._parse_vod_list(html_data)

        return {
            "list": cards,
            "page": pg_int,
            "pagecount": pg_int + 1 if len(cards) >= 15 else pg_int,
            "limit": len(cards),
            "total": 9999
        }

    def detailContent(self, ids):
        vod_id = ids[0] if isinstance(ids, list) else ids
        detail_url = urllib.parse.urljoin(self.site_url, vod_id)
        code, final_url, html_data = self._fetch(detail_url)

        title = ""
        t_m = re.search(r'<h1[^>]*>(.*?)</h1>', html_data, re.I | re.S)
        if t_m:
            title = re.sub(r'<[^>]+>', '', t_m.group(1)).strip()

        pic = ""
        p_m = re.search(r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)["\']', html_data, re.I)
        if p_m:
            pic = p_m.group(1).strip()
        else:
            p_m2 = re.search(r'<img[^>]+(?:data-original|data-src|src)=["\']([^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)["\']', html_data, re.I)
            if p_m2:
                pic = p_m2.group(1).strip()
        if pic and not pic.startswith("http"):
            pic = urllib.parse.urljoin(self.site_url, pic)

        direct_play_url = ""
        m3u8_matches = re.findall(r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', html_data, re.I)
        for m in m3u8_matches:
            if "sample" not in m and "test" not in m:
                direct_play_url = m
                break

        if not direct_play_url:
            mp4_matches = re.findall(r'["\'](https?://[^"\']+\.mp4[^"\']*)["\']', html_data, re.I)
            for m in mp4_matches:
                if "sample" not in m and "test" not in m:
                    direct_play_url = m
                    break

        if not direct_play_url:
            art_match = re.search(r'url\s*:\s*["\']([^"\']+)["\']', html_data, re.I)
            if art_match:
                candidate = art_match.group(1).strip()
                if "sample" not in candidate and "test" not in candidate:
                    direct_play_url = candidate

        if not direct_play_url and pic:
            inferred_m3u8 = re.sub(r'poster\d*\.(?:webp|jpg|png)', 'index.m3u8', pic)
            if inferred_m3u8 != pic:
                direct_play_url = inferred_m3u8

        play_sources = ["蝴蝶专线"]
        play_urls = ["正片$" + (direct_play_url if direct_play_url else detail_url)]

        vod = {
            "vod_id": vod_id,
            "vod_name": title if title else "蝴蝶影视",
            "vod_pic": pic,
            "type_name": "蝴蝶精选",
            "vod_year": "",
            "vod_area": "",
            "vod_remarks": "蝴蝶影视",
            "vod_actor": "🦋 TG群: @tvshare23",
            "vod_director": "蝴蝶影视",
            "vod_content": "🦋 官方交流群: @tvshare23 | 请勿相信视频内任何广告！",
            "vod_play_from": "$$$".join(play_sources),
            "vod_play_url": "$$$".join(play_urls)
        }

        return {"list": [vod]}

    def playerContent(self, flag, id, vipFlags):
        headers = {
            "User-Agent": self.headers["User-Agent"],
            "Referer": self.site_url + "/"
        }
        return {
            "parse": 0,
            "url": id,
            "header": headers
        }

    def searchContent(self, key, quick, pg="1"):
        pg_int = int(pg) if str(pg).isdigit() else 1
        encoded_key = urllib.parse.quote(key)
        if pg_int <= 1:
            search_url = "%s/s/wd/%s/" % (self.site_url, encoded_key)
        else:
            search_url = "%s/s/wd/%s/page/%s/" % (self.site_url, encoded_key, pg_int)

        code, final_url, html_data = self._fetch(search_url)
        cards = self._parse_vod_list(html_data)

        return {
            "list": cards,
            "page": pg_int,
            "pagecount": pg_int + 1 if len(cards) >= 15 else pg_int,
            "limit": len(cards),
            "total": 9999
        }

    def action(self, action):
        return {}

    def liveContent(self):
        return {}

    def localProxy(self, params):
        return []

    def manualVideoCheck(self):
        return False

    def isVideoFormat(self, url):
        return False

    def destroy(self):
        pass