import sys
import ssl
import time
import json
import re
import urllib.request
import urllib.parse
from http.cookiejar import CookieJar

try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider(object):
        pass

class Spider(BaseSpider):
    def __init__(self):
        self.site_url = "https://licefor.aisydj.cc"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
        }
        self.cookie_jar = CookieJar()
        self.opener = self._build_opener()

    def _build_opener(self):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        https_handler = urllib.request.HTTPSHandler(context=ctx)
        cookie_handler = urllib.request.HTTPCookieProcessor(self.cookie_jar)
        return urllib.request.build_opener(https_handler, cookie_handler)

    def _fetch(self, url, retry=2, referer=None):
        headers = dict(self.headers)
        if referer:
            headers["Referer"] = referer
        for i in range(retry + 1):
            try:
                req = urllib.request.Request(url, headers=headers)
                with self.opener.open(req, timeout=12) as resp:
                    final_url = resp.geturl()
                    status_code = resp.getcode()
                    headers_dict = dict(resp.headers)
                    body_bytes = resp.read()
                    charset = "utf-8"
                    content_type = headers_dict.get("Content-Type", "")
                    if "charset=" in content_type:
                        charset = content_type.split("charset=")[-1].strip()
                    try:
                        html = body_bytes.decode(charset, errors="ignore")
                    except Exception:
                        html = body_bytes.decode("utf-8", errors="ignore")
                    return {
                        "status_code": status_code,
                        "final_url": final_url,
                        "headers": headers_dict,
                        "html": html
                    }
            except Exception as e:
                if i == retry:
                    raise e

    def init(self, extend=""):
        pass

    def homeContent(self, filter):
        classes = [
            {"type_id": "AIchengrenduanju", "type_name": "AI成人短剧"},
            {"type_id": "AIchengrenmanju", "type_name": "AI成人漫剧"},
            {"type_id": "AImogai", "type_name": "AI魔改"},
            {"type_id": "AIhuanlian", "type_name": "AI换脸"}
        ]

        sort_filter = {
            "key": "by",
            "name": "排序",
            "value": [
                {"n": "最新上线", "v": "time"},
                {"n": "按热度", "v": "hits"},
                {"n": "评分最高", "v": "score"}
            ]
        }

        filters = {}
        for c in classes:
            filters[c["type_id"]] = [sort_filter]

        return {
            "class": classes,
            "filters": filters
        }

    def homeVideoContent(self):
        return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        sort_by = ""
        if extend and isinstance(extend, dict):
            sort_by = extend.get("by", "")

        base_path = "/aidj/%s/" % tid

        if sort_by:
            if page > 1:
                url = "%s%sby/%s/page/%d/" % (self.site_url, base_path, sort_by, page)
            else:
                url = "%s%sby/%s/" % (self.site_url, base_path, sort_by)
        else:
            if page > 1:
                url = "%s%spage/%d/" % (self.site_url, base_path, page)
            else:
                url = "%s%s" % (self.site_url, base_path)

        res = self._fetch(url)
        html = res.get("html", "")

        vod_list = []
        card_blocks = re.findall(r'<a[^>]*href=["\'](/detail/\d+/?)["\'][^>]*>(.*?)</a>', html, re.I | re.S)

        seen_ids = set()
        for href, inner_html in card_blocks:
            id_match = re.search(r'/detail/(\d+)', href)
            if not id_match:
                continue
            vod_id = id_match.group(1)
            if vod_id in seen_ids:
                continue
            seen_ids.add(vod_id)

            title_match = re.search(r'(?:title=["\']([^"\']+)["\']|alt=["\']([^"\']+)["\'])', inner_html, re.I)
            if not title_match:
                title_match = re.search(r'<div[^>]*class=["\'][^"\']*(?:title|name)[^"\']*["\'][^>]*>(.*?)</div>', inner_html, re.I | re.S)
            vod_name = ""
            if title_match:
                vod_name = title_match.group(1) or (title_match.group(2) if len(title_match.groups()) > 1 else "")
                vod_name = re.sub(r'<[^>]+>', '', vod_name).strip()

            img_match = re.search(r'(?:data-src|src)=["\']([^"\']+)["\']', inner_html, re.I)
            vod_pic = img_match.group(1).strip() if img_match else ""
            if vod_pic.startswith("//"):
                vod_pic = "https:" + vod_pic

            remark_match = re.search(r'<span[^>]*class=["\'][^"\']*(?:badge|tag|note|remarks|time|duration|score)[^"\']*["\'][^>]*>(.*?)</span>', inner_html, re.I | re.S)
            raw_remark = re.sub(r'<[^>]+>', '', remark_match.group(1)).strip() if remark_match else ""

            if raw_remark:
                vod_remarks = "蝴蝶影视 | %s" % raw_remark
            else:
                vod_remarks = "蝴蝶影视"

            if vod_name:
                vod_list.append({
                    "vod_id": vod_id,
                    "vod_name": vod_name,
                    "vod_pic": vod_pic,
                    "vod_remarks": vod_remarks
                })

        page_count = page
        max_page_matches = re.findall(r'/page/(\d+)/', html)
        if max_page_matches:
            found_pages = [int(p) for p in max_page_matches]
            page_count = max(max(found_pages), page + 1)
        elif len(vod_list) >= 15:
            page_count = page + 1

        return {
            "page": page,
            "pagecount": page_count,
            "limit": len(vod_list) if vod_list else 20,
            "total": page_count * 20,
            "list": vod_list
        }

    def detailContent(self, ids):
        vod_id = ids[0] if isinstance(ids, list) else ids
        detail_url = "%s/detail/%s/" % (self.site_url, vod_id)

        try:
            res = self._fetch(detail_url)
            html = res.get("html", "")

            title_m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.I | re.S)
            if not title_m:
                title_m = re.search(r'<title[^>]*>(.*?)</title>', html, re.I | re.S)
            vod_name = re.sub(r'<[^>]+>', '', title_m.group(1)).strip() if title_m else "短剧_%s" % vod_id

            pic_m = re.search(r'<div[^>]*class=["\'][^"\']*poster[^"\']*["\'][^>]*>.*?src=["\']([^"\']+)["\']', html, re.I | re.S)
            if not pic_m:
                pic_m = re.search(r'<meta[^>]*property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']', html, re.I)
            vod_pic = pic_m.group(1).strip() if pic_m else ""
            if vod_pic.startswith("//"):
                vod_pic = "https:" + vod_pic

            desc_m = re.search(r'<div[^>]*class=["\'][^"\']*(?:desc|content|intro|detail-text)[^"\']*["\'][^>]*>(.*?)</div>', html, re.I | re.S)
            raw_desc = re.sub(r'<[^>]+>', '', desc_m.group(1)).strip() if desc_m else ""

            episodes = []
            ep_matches = re.findall(r'<a[^>]*href=["\'](/play/[^"\']+)["\'][^>]*>(.*?)</a>', html, re.I | re.S)
            if ep_matches:
                for ep_href, ep_name in ep_matches:
                    clean_name = re.sub(r'<[^>]+>', '', ep_name).strip()
                    episodes.append("%s$%s" % (clean_name or "播放", ep_href))
            else:
                episodes.append("正片$/play/%s-1-1/" % vod_id)

        except Exception:
            vod_name = "短剧_%s" % vod_id
            vod_pic = ""
            raw_desc = ""
            episodes = ["正片$/play/%s-1-1/" % vod_id]

        play_from = "蝴蝶影视"
        play_url = "#".join(episodes)
        vod_content = "🦋 TG群: @tvshare23\n%s" % (raw_desc if raw_desc else "AI 精品短剧，畅享高清视界。")

        return {
            "list": [
                {
                    "vod_id": vod_id,
                    "vod_name": vod_name,
                    "vod_pic": vod_pic,
                    "type_name": "短剧",
                    "vod_year": "2026",
                    "vod_area": "中国",
                    "vod_actor": "🦋 TG群: @tvshare23",
                    "vod_director": "🦋 蝴蝶影视",
                    "vod_content": vod_content,
                    "vod_play_from": play_from,
                    "vod_play_url": play_url
                }
            ]
        }

    def playerContent(self, flag, id, vipFlags):
        if id.startswith("/"):
            play_page_url = "%s%s" % (self.site_url, id)
        elif id.startswith("http"):
            play_page_url = id
        else:
            play_page_url = "%s/play/%s/" % (self.site_url, id)

        final_play_url = ""
        header = {
            "User-Agent": self.headers["User-Agent"],
            "Referer": play_page_url
        }

        try:
            res = self._fetch(play_page_url, referer="%s/" % self.site_url)
            html = res.get("html", "")

            pd_match = re.search(r'var\s+player_data\s*=\s*(\{.*?\})</script>', html, re.I | re.S)
            if pd_match:
                pd = json.loads(pd_match.group(1))
                raw_url_val = pd.get("url", "")
                if "|" in raw_url_val:
                    parts = raw_url_val.split("|")
                    vid = parts[0].strip()
                    vep = parts[1].strip()
                    api_url = "%s/huangguo.php?ac=play&id=%s&ep=%s&_=%d" % (
                        self.site_url,
                        urllib.parse.quote(vid),
                        urllib.parse.quote(vep),
                        int(time.time() * 1000)
                    )
                    api_res = self._fetch(api_url, referer=play_page_url)
                    api_data = json.loads(api_res.get("html", "{}"))
                    if api_data.get("code") == 1 and api_data.get("url"):
                        target_stream = api_data["url"]
                        final_play_url = "%s/hgmedia.php?url=%s" % (self.site_url, urllib.parse.quote(target_stream))

            if not final_play_url:
                stream_matches = re.findall(r'["\'](https?:[^"\']+\.(?:m3u8|mp4)[^"\']*)["\']', html, re.I)
                if stream_matches:
                    final_play_url = stream_matches[0]

        except Exception:
            final_play_url = ""

        return {
            "parse": 0,
            "playUrl": "",
            "url": final_play_url,
            "header": header
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        encoded_key = urllib.parse.quote(key)
        if page > 1:
            search_url = "%s/vod/search/page/%d/wd/%s/" % (self.site_url, page, encoded_key)
        else:
            search_url = "%s/vod/search/wd/%s/" % (self.site_url, encoded_key)

        vod_list = []
        try:
            res = self._fetch(search_url)
            html = res.get("html", "")
            card_blocks = re.findall(r'<a[^>]*href=["\'](/detail/\d+/?)["\'][^>]*>(.*?)</a>', html, re.I | re.S)

            seen_ids = set()
            for href, inner_html in card_blocks:
                id_match = re.search(r'/detail/(\d+)', href)
                if not id_match:
                    continue
                vod_id = id_match.group(1)
                if vod_id in seen_ids:
                    continue
                seen_ids.add(vod_id)

                title_match = re.search(r'(?:title=["\']([^"\']+)["\']|alt=["\']([^"\']+)["\'])', inner_html, re.I)
                if not title_match:
                    title_match = re.search(r'<div[^>]*class=["\'][^"\']*(?:title|name)[^"\']*["\'][^>]*>(.*?)</div>', inner_html, re.I | re.S)
                vod_name = ""
                if title_match:
                    vod_name = title_match.group(1) or (title_match.group(2) if len(title_match.groups()) > 1 else "")
                    vod_name = re.sub(r'<[^>]+>', '', vod_name).strip()

                img_match = re.search(r'(?:data-src|src)=["\']([^"\']+)["\']', inner_html, re.I)
                vod_pic = img_match.group(1).strip() if img_match else ""
                if vod_pic.startswith("//"):
                    vod_pic = "https:" + vod_pic

                remark_match = re.search(r'<span[^>]*class=["\'][^"\']*(?:badge|tag|note|remarks|time|duration|score)[^"\']*["\'][^>]*>(.*?)</span>', inner_html, re.I | re.S)
                raw_remark = re.sub(r'<[^>]+>', '', remark_match.group(1)).strip() if remark_match else ""

                if raw_remark:
                    vod_remarks = "蝴蝶影视 | %s" % raw_remark
                else:
                    vod_remarks = "蝴蝶影视"

                if vod_name:
                    vod_list.append({
                        "vod_id": vod_id,
                        "vod_name": vod_name,
                        "vod_pic": vod_pic,
                        "vod_remarks": vod_remarks
                    })
        except Exception:
            vod_list = []

        return {
            "page": page,
            "pagecount": page + 1 if len(vod_list) >= 15 else page,
            "limit": len(vod_list) if vod_list else 20,
            "total": 100,
            "list": vod_list
        }

    def action(self, action):
        return ""

    def liveContent(self):
        return ""

    def localProxy(self, params):
        return [200, "text/plain;charset=utf-8", ""]

    def manualVideoCheck(self):
        return False

    def isVideoFormat(self, url):
        return False

    def destroy(self):
        pass