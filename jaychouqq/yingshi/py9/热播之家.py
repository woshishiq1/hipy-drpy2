import urllib.request
import urllib.parse
import json
import ssl
import re
import gzip
import zlib
import html
import base64

try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider(object):
        pass

class Spider(BaseSpider):

    def init(self, extend=""):
        self.site_url = "https://www.rebozj.cc"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "keep-alive"
        }

    def _fetch(self, url, headers=None):
        if not headers:
            headers = self.headers
        req = urllib.request.Request(url, headers=headers)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        try:
            with urllib.request.urlopen(req, timeout=12, context=ctx) as resp:
                status_code = resp.getcode()
                final_url = resp.geturl()
                content_encoding = resp.headers.get("Content-Encoding", "").lower()
                raw = resp.read()
                if content_encoding == "gzip":
                    html_data = gzip.decompress(raw).decode("utf-8", "ignore")
                elif content_encoding == "deflate":
                    html_data = zlib.decompress(raw).decode("utf-8", "ignore")
                else:
                    try:
                        html_data = raw.decode("utf-8")
                    except Exception:
                        html_data = raw.decode("gbk", "ignore")
                return {
                    "code": status_code,
                    "final_url": final_url,
                    "html": html_data,
                    "headers": dict(resp.headers)
                }
        except Exception:
            return {
                "code": 0,
                "error": "",
                "html": "",
                "final_url": url,
                "headers": {}
            }

    def _decode_maccms_url(self, raw_url, encrypt_type):
        if not raw_url:
            return ""
        if encrypt_type == 0 or encrypt_type == 1:
            try:
                return urllib.parse.unquote(raw_url)
            except Exception:
                return raw_url
        elif encrypt_type == 2:
            try:
                return base64.b64decode(raw_url).decode("utf-8")
            except Exception:
                return raw_url
        elif encrypt_type == 3:
            try:
                decoded = urllib.parse.unquote(raw_url)
                if decoded.startswith("http"):
                    return decoded
                return base64.b64decode(raw_url).decode("utf-8")
            except Exception:
                return raw_url
        return raw_url

    def homeContent(self, filter):
        classes = [
            {"type_id": "1", "type_name": "电影"},
            {"type_id": "2", "type_name": "电视剧"},
            {"type_id": "4", "type_name": "动漫"},
            {"type_id": "5", "type_name": "综艺"},
            {"type_id": "3", "type_name": "纪录片"}
        ]

        filters = {
            "1": [
                {
                    "key": "sub_type",
                    "name": "类型",
                    "value": [
                        {"n": "全部", "v": "1"},
                        {"n": "动作", "v": "6"},
                        {"n": "喜剧", "v": "7"},
                        {"n": "爱情", "v": "8"},
                        {"n": "科幻", "v": "9"},
                        {"n": "恐怖", "v": "10"},
                        {"n": "剧情", "v": "11"},
                        {"n": "战争", "v": "12"}
                    ]
                }
            ],
            "2": [
                {
                    "key": "sub_type",
                    "name": "类型",
                    "value": [
                        {"n": "全部", "v": "2"},
                        {"n": "国产剧", "v": "13"},
                        {"n": "港台剧", "v": "14"},
                        {"n": "日韩剧", "v": "15"},
                        {"n": "海外剧", "v": "16"}
                    ]
                }
            ],
            "4": [
                {
                    "key": "sub_type",
                    "name": "类型",
                    "value": [
                        {"n": "全部", "v": "4"},
                        {"n": "国产动漫", "v": "24"},
                        {"n": "日韩动漫", "v": "25"},
                        {"n": "港台动漫", "v": "26"},
                        {"n": "欧美动漫", "v": "27"}
                    ]
                }
            ],
            "5": [
                {
                    "key": "sub_type",
                    "name": "类型",
                    "value": [
                        {"n": "全部", "v": "5"},
                        {"n": "大陆综艺", "v": "17"},
                        {"n": "港台综艺", "v": "18"},
                        {"n": "日韩综艺", "v": "20"},
                        {"n": "欧美综艺", "v": "21"}
                    ]
                }
            ]
        }

        return {
            "class": classes,
            "filters": filters,
            "list": []
        }

    def homeVideoContent(self):
        return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        target_tid = tid
        if extend and "sub_type" in extend:
            sub_val = extend["sub_type"]
            if sub_val:
                target_tid = str(sub_val)

        if page == 1:
            req_url = "%s/type/%s.html" % (self.site_url, target_tid)
        else:
            req_url = "%s/type/%s-%d.html" % (self.site_url, target_tid, page)

        res = self._fetch(req_url)
        raw_html = res.get("html", "")

        if not raw_html or res.get("code") == 404:
            alt_url = "%s/type/%s/page/%d.html" % (self.site_url, target_tid, page)
            alt_res = self._fetch(alt_url)
            if alt_res.get("code") == 200:
                raw_html = alt_res.get("html", "")

        vod_list = []
        card_items = re.findall(r'<li[^>]*stui-vodlist__item[\s\S]*?</li>', raw_html)
        if not card_items:
            card_items = re.findall(r'<a[^>]+class=["\'][^"\']*stui-vodlist__thumb[^"\']*["\'][^>]*>[\s\S]*?</a>', raw_html)

        for card in card_items:
            href_m = re.search(r'href=["\']([^"\']+)["\']', card)
            if not href_m:
                continue
            href = href_m.group(1)
            id_m = re.search(r'/detail/(\d+)\.html', href)
            if not id_m:
                id_m = re.search(r'(\d+)', href)
                if not id_m:
                    continue
            vod_id = id_m.group(1)

            title_m = re.search(r'title=["\']([^"\']+)["\']', card)
            vod_name = title_m.group(1).strip() if title_m else ""
            if not vod_name:
                text_m = re.search(r'<h4[^>]*>([\s\S]*?)</h4>', card)
                if text_m:
                    vod_name = re.sub(r'<[^>]+>', '', text_m.group(1)).strip()

            pic_m = re.search(r'data-original=["\']([^"\']+)["\']', card) or re.search(r'src=["\']([^"\']+)["\']', card)
            vod_pic = pic_m.group(1).strip() if pic_m else ""
            vod_pic = html.unescape(vod_pic)
            if vod_pic.startswith("//"):
                vod_pic = "https:" + vod_pic
            elif vod_pic.startswith("/"):
                vod_pic = self.site_url + vod_pic

            remarks_m = re.search(r'<span[^>]+pic-text[^>]*>([\s\S]*?)</span>', card)
            raw_remarks = re.sub(r'<[^>]+>', '', remarks_m.group(1)).strip() if remarks_m else ""
            raw_remarks = re.sub(r'\s+', ' ', raw_remarks)
            vod_remarks = ("蝴蝶影视 | %s" % raw_remarks) if raw_remarks else "蝴蝶影视"

            vod_list.append({
                "vod_id": vod_id,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_remarks": vod_remarks
            })

        return {
            "page": page,
            "pagecount": page + 1 if len(vod_list) >= 12 else page,
            "limit": 20,
            "total": 9999,
            "list": vod_list
        }

    def detailContent(self, ids):
        vod_id = ids[0] if isinstance(ids, list) else str(ids)
        detail_url = "%s/detail/%s.html" % (self.site_url, vod_id)
        res = self._fetch(detail_url)
        raw_html = res.get("html", "")

        title_m = re.search(r'<h1[^>]*>([\s\S]*?)</h1>', raw_html)
        vod_name = re.sub(r'<[^>]+>', '', title_m.group(1)).strip() if title_m else ""

        pic_m = re.search(r'<div[^>]*stui-content__thumb[\s\S]*?<img[^>]+data-original=["\']([^"\']+)["\']', raw_html)
        if not pic_m:
            pic_m = re.search(r'<div[^>]*stui-content__thumb[\s\S]*?<img[^>]+src=["\']([^"\']+)["\']', raw_html)
        vod_pic = pic_m.group(1).strip() if pic_m else ""
        vod_pic = html.unescape(vod_pic)
        if vod_pic.startswith("//"):
            vod_pic = "https:" + vod_pic
        elif vod_pic.startswith("/"):
            vod_pic = self.site_url + vod_pic

        year_m = re.search(r'年份[：:]\s*([0-9]{4})', raw_html)
        vod_year = year_m.group(1) if year_m else ""

        desc_m = re.search(r'<span[^>]*class=["\']detail-content[^"\']*["\'][^>]*>([\s\S]*?)</span>', raw_html)
        if not desc_m:
            desc_m = re.search(r'<p[^>]*class=["\']desc[^"\']*["\'][^>]*>([\s\S]*?)</p>', raw_html)
        raw_desc = re.sub(r'<[^>]+>', '', desc_m.group(1)).strip() if desc_m else ""
        vod_content = "🦋 关注TG交流群：@tvshare23\n" + raw_desc

        tab_list = re.findall(r'<a[^>]+href=["\']#playlist(\d+)["\'][^>]*>([\s\S]*?)</a>', raw_html)
        pan_keywords = ["网盘", "夸克", "百度", "阿里", "迅雷", "UC", "115"]

        from_list = []
        url_list = []

        for p_idx, t_name in tab_list:
            clean_tab_name = re.sub(r'<[^>]+>', '', t_name).strip()

            is_pan = False
            for kw in pan_keywords:
                if kw in clean_tab_name:
                    is_pan = True
                    break
            if is_pan:
                continue

            pane_pattern = r'<div[^>]+id=["\']playlist%s["\'][\s\S]*?</div>\s*</div>' % p_idx
            pane_match = re.search(pane_pattern, raw_html)
            pane_content = pane_match.group(0) if pane_match else ""

            if not pane_content:
                pane_fallback = re.search(r'<div[^>]+id=["\']playlist%s["\'][\s\S]*?</ul>' % p_idx, raw_html)
                pane_content = pane_fallback.group(0) if pane_fallback else ""

            ep_matches = re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>([\s\S]*?)</a>', pane_content)
            ep_sub_list = []
            for href, ep_name in ep_matches:
                clean_ep = re.sub(r'<[^>]+>', '', ep_name).strip()
                if clean_ep and href and "javascript" not in href:
                    clean_href = href if href.startswith("http") else (self.site_url + href)
                    ep_sub_list.append("%s$%s" % (clean_ep, clean_href))

            if ep_sub_list:
                from_list.append("🦋 %s" % clean_tab_name)
                url_list.append("#".join(ep_sub_list))

        if not from_list:
            all_ep_matches = re.findall(r'<a[^>]+href=["\'](/play/[^"\']+)["\'][^>]*>([\s\S]*?)</a>', raw_html)
            ep_sub_list = []
            for href, ep_name in all_ep_matches:
                clean_ep = re.sub(r'<[^>]+>', '', ep_name).strip()
                if not clean_ep:
                    clean_ep = "正片"
                clean_href = self.site_url + href
                ep_sub_list.append("%s$%s" % (clean_ep, clean_href))
            if ep_sub_list:
                from_list.append("🦋 蓝光专线")
                url_list.append("#".join(ep_sub_list))

        return {
            "list": [
                {
                    "vod_id": vod_id,
                    "vod_name": vod_name,
                    "vod_pic": vod_pic,
                    "type_name": "",
                    "vod_year": vod_year,
                    "vod_area": "",
                    "vod_remarks": "蝴蝶影视",
                    "vod_actor": "🦋 TG群: @tvshare23",
                    "vod_director": "🦋 蝴蝶影视",
                    "vod_content": vod_content,
                    "vod_play_from": "$$$".join(from_list),
                    "vod_play_url": "$$$".join(url_list)
                }
            ]
        }

    def playerContent(self, flag, id, vipFlags):
        play_page_url = id if id.startswith("http") else (self.site_url + id)
        res = self._fetch(play_page_url)
        play_html = res.get("html", "")

        player_data_match = re.search(r'var\s+player_aaaa\s*=\s*(\{[\s\S]*?\});', play_html)
        target_stream_url = ""
        encrypt_type = 0

        if player_data_match:
            try:
                p_data = json.loads(player_data_match.group(1))
                target_stream_url = p_data.get("url", "")
                encrypt_type = int(p_data.get("encrypt", 0))
            except Exception:
                pass

        real_target_url = self._decode_maccms_url(target_stream_url, encrypt_type)

        direct_play = 0
        if real_target_url.endswith(".m3u8") or ".m3u8?" in real_target_url or real_target_url.endswith(".mp4") or ".mp4?" in real_target_url:
            direct_play = 0
        else:
            direct_play = 1

        return {
            "parse": direct_play,
            "url": real_target_url if real_target_url else play_page_url,
            "header": {
                "User-Agent": self.headers["User-Agent"],
                "Referer": self.site_url + "/"
            }
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        enc_key = urllib.parse.quote(key)
        search_url = "%s/search/-------------.html?wd=%s&page=%d" % (self.site_url, enc_key, page)
        res = self._fetch(search_url)
        raw_html = res.get("html", "")

        vod_list = []
        card_items = re.findall(r'<li[^>]*stui-vodlist__item[\s\S]*?</li>', raw_html)
        if not card_items:
            card_items = re.findall(r'<a[^>]+class=["\'][^"\']*stui-vodlist__thumb[^"\']*["\'][^>]*>[\s\S]*?</a>', raw_html)

        for card in card_items:
            href_m = re.search(r'href=["\']([^"\']+)["\']', card)
            if not href_m:
                continue
            href = href_m.group(1)
            id_m = re.search(r'/detail/(\d+)\.html', href)
            if not id_m:
                id_m = re.search(r'(\d+)', href)
                if not id_m:
                    continue
            vod_id = id_m.group(1)

            title_m = re.search(r'title=["\']([^"\']+)["\']', card)
            vod_name = title_m.group(1).strip() if title_m else ""
            if not vod_name:
                text_m = re.search(r'<h4[^>]*>([\s\S]*?)</h4>', card)
                if text_m:
                    vod_name = re.sub(r'<[^>]+>', '', text_m.group(1)).strip()

            pic_m = re.search(r'data-original=["\']([^"\']+)["\']', card) or re.search(r'src=["\']([^"\']+)["\']', card)
            vod_pic = pic_m.group(1).strip() if pic_m else ""
            vod_pic = html.unescape(vod_pic)
            if vod_pic.startswith("//"):
                vod_pic = "https:" + vod_pic
            elif vod_pic.startswith("/"):
                vod_pic = self.site_url + vod_pic

            remarks_m = re.search(r'<span[^>]+pic-text[^>]*>([\s\S]*?)</span>', card)
            raw_remarks = re.sub(r'<[^>]+>', '', remarks_m.group(1)).strip() if remarks_m else ""
            raw_remarks = re.sub(r'\s+', ' ', raw_remarks)
            vod_remarks = ("蝴蝶影视 | %s" % raw_remarks) if raw_remarks else "蝴蝶影视"

            vod_list.append({
                "vod_id": vod_id,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_remarks": vod_remarks
            })

        return {
            "page": page,
            "pagecount": page + 1 if len(vod_list) >= 10 else page,
            "limit": 20,
            "total": 9999,
            "list": vod_list
        }

    def action(self, action):
        return {}

    def liveContent(self):
        return ""

    def localProxy(self, params):
        return [200, "text/plain", ""]

    def manualVideoCheck(self):
        return False

    def isVideoFormat(self, url):
        return False

    def destroy(self):
        pass