# -*- coding: utf-8 -*-
import sys
import json
import ssl
import gzip
import zlib
import re
import base64
from urllib import request, parse, error

try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider(object):
        pass

class Spider(BaseSpider):

    def __init__(self):
        super(Spider, self).__init__()
        self.site_url = "https://chengguodj.com"

    def init(self, extend=""):
        pass

    def _get_ssl_ctx(self):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx

    def _fetch(self, url, headers=None, data=None):
        req_headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6.1 Mobile/15E148 Safari/604.1",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Referer": self.site_url + "/"
        }
        if headers:
            req_headers.update(headers)
        
        req = request.Request(url, headers=req_headers, data=data)
        ctx = self._get_ssl_ctx()
        try:
            with request.urlopen(req, context=ctx, timeout=10) as resp:
                raw = resp.read()
                encoding = resp.headers.get("Content-Encoding", "").lower()
                if "gzip" in encoding:
                    try:
                        raw = gzip.decompress(raw)
                    except Exception:
                        pass
                elif "deflate" in encoding:
                    try:
                        raw = zlib.decompress(raw)
                    except Exception:
                        pass
                charset = resp.headers.get_content_charset() or "utf-8"
                return {
                    "code": resp.getcode(),
                    "final_url": resp.geturl(),
                    "headers": dict(resp.headers),
                    "body": raw.decode(charset, errors="replace")
                }
        except error.HTTPError as e:
            return {
                "code": e.code,
                "final_url": e.geturl() if hasattr(e, "geturl") else url,
                "headers": dict(e.headers) if hasattr(e, "headers") else {},
                "body": e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else ""
            }
        except Exception as e:
            return {
                "code": -1,
                "final_url": url,
                "headers": {},
                "body": str(e)
            }

    def _proxy_img(self, raw_url):
        if not raw_url:
            return ""
        u = raw_url.replace("\\u002F", "/").replace("\\u002f", "/").replace("\\/", "/").strip().strip('\'"')
        if not u.startswith("http"):
            u = parse.urljoin(self.site_url, u)
        try:
            b64 = base64.urlsafe_b64encode(u.encode("utf-8")).decode("ascii").rstrip("=")
            return "%s/_img/%s" % (self.site_url, b64)
        except Exception:
            return u

    def homeContent(self, filter):
        return {
            "class": [
                {"type_id": "yuanchuang", "type_name": "原创短剧"},
                {"type_id": "mogai", "type_name": "魔改短剧"},
                {"type_id": "manju", "type_name": "漫剧"},
                {"type_id": "zhenren", "type_name": "真人短剧"},
                {"type_id": "aiduanju", "type_name": "AI短剧"},
                {"type_id": "browse", "type_name": "片库索引"}
            ],
            "filters": {}
        }

    def homeVideoContent(self):
        return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        p = int(pg)
        cat_url = "%s/%s" % (self.site_url, tid) if p <= 1 else "%s/%s/page-%d" % (self.site_url, tid, p)

        res = self._fetch(cat_url)
        body = res.get("body", "")

        vod_list = []
        seen_ids = set()

        nuxt_m = re.search(r'<script[^>]+id=["\']__NUXT_DATA__["\'][^>]*>([\s\S]*?)</script>', body)
        if nuxt_m:
            try:
                arr = json.loads(nuxt_m.group(1).strip())
                for item in arr:
                    if isinstance(item, dict) and "title" in item and ("slug" in item or "detail_route" in item):
                        t_idx = item.get("title")
                        title = arr[t_idx] if isinstance(t_idx, int) and t_idx < len(arr) else t_idx
                        if not title or not isinstance(title, str):
                            continue

                        d_route = item.get("detail_route")
                        drama_path = arr[d_route] if isinstance(d_route, int) and d_route < len(arr) else d_route
                        if not drama_path:
                            slug_val = item.get("slug")
                            slug = arr[slug_val] if isinstance(slug_val, int) and slug_val < len(arr) else slug_val
                            if slug:
                                drama_path = "/drama/%s" % slug

                        if not drama_path or drama_path in seen_ids:
                            continue

                        final_pic = ""
                        cover_obj = item.get("cover")
                        if isinstance(cover_obj, int) and cover_obj < len(arr):
                            cover_obj = arr[cover_obj]

                        if isinstance(cover_obj, dict):
                            u_idx = cover_obj.get("url")
                            raw_u = arr[u_idx] if isinstance(u_idx, int) and u_idx < len(arr) else u_idx
                            if raw_u and isinstance(raw_u, str):
                                final_pic = self._proxy_img(raw_u)

                        eps_val = item.get("total_episode_count") or item.get("published_episode_count") or item.get("latest_episode_number")
                        if isinstance(eps_val, int) and eps_val < len(arr) and not isinstance(arr[eps_val], (dict, list)):
                            eps_num = arr[eps_val]
                        else:
                            eps_num = eps_val
                        remarks = "蝴蝶影视 · %s集" % eps_num if eps_num else "蝴蝶影视"

                        seen_ids.add(drama_path)
                        vod_list.append({
                            "vod_id": drama_path,
                            "vod_name": title,
                            "vod_pic": final_pic,
                            "vod_remarks": remarks,
                            "vod_actor": "🦋 TG群: @tvshare23",
                            "vod_director": "🦋 蝴蝶影视"
                        })
            except Exception:
                pass

        return {
            "page": p,
            "pagecount": p + 1 if len(vod_list) >= 12 else p,
            "limit": len(vod_list),
            "total": 999,
            "list": vod_list
        }

    def detailContent(self, ids):
        drama_id = ids[0]
        detail_url = parse.urljoin(self.site_url, drama_id) if not drama_id.startswith("http") else drama_id

        res = self._fetch(detail_url)
        body = res.get("body", "")

        vod_name = ""
        title_m = re.search(r'<title>([^<]+)</title>', body, re.IGNORECASE)
        if title_m:
            vod_name = title_m.group(1).split("-")[0].replace("在线观看", "").strip()

        pic = ""
        wlw_m = re.search(r'["\'](https?://[^"\']*wlwvch\.cn[^"\']+)["\']', body)
        if wlw_m:
            pic = self._proxy_img(wlw_m.group(1))

        desc = ""
        desc_m = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']', body, re.IGNORECASE)
        if desc_m:
            desc = desc_m.group(1).strip()

        content_str = "【🦋 蝴蝶影视·官方交流群 @tvshare23】\n\n%s" % (desc if desc else "暂无简介")

        slug = drama_id.strip("/").split("/")[-1]

        episodes = []
        nuxt_m = re.search(r'<script[^>]+id=["\']__NUXT_DATA__["\'][^>]*>([\s\S]*?)</script>', body)
        if nuxt_m:
            try:
                arr = json.loads(nuxt_m.group(1).strip())
                for item in arr:
                    if isinstance(item, dict) and "total_episode_count" in item:
                        tot = item.get("total_episode_count")
                        tot_num = arr[tot] if isinstance(tot, int) and tot < len(arr) else tot
                        if isinstance(tot_num, int) and tot_num > 0:
                            for ep_i in range(1, tot_num + 1):
                                episodes.append("第%d集$/play/%s/%d" % (ep_i, slug, ep_i))
                            break
            except Exception:
                pass

        if not episodes:
            play_links = re.findall(r'href=["\'](/play/[^"\']+)["\']', body, re.IGNORECASE)
            seen_eps = set()
            for p_link in play_links:
                p_link = p_link.strip()
                if p_link in seen_eps:
                    continue
                seen_eps.add(p_link)
                ep_num = p_link.split("/")[-1]
                ep_title = "第%s集" % ep_num if ep_num.isdigit() else ep_num
                episodes.append("%s$%s" % (ep_title, p_link))

        if not episodes:
            total_m = re.search(r'(\d+)[\s]*(?:集|话|部)', body)
            max_ep = int(total_m.group(1)) if total_m else 1
            for i in range(1, max_ep + 1):
                episodes.append("第%d集$/play/%s/%d" % (i, slug, i))

        vod = {
            "vod_id": drama_id,
            "vod_name": vod_name if vod_name else "短剧详情",
            "vod_pic": pic,
            "vod_type": "短剧",
            "vod_year": "2026",
            "vod_area": "大陆",
            "vod_remarks": "蝴蝶影视 · %d集" % len(episodes),
            "vod_actor": "🦋 TG群: @tvshare23",
            "vod_director": "🦋 蝴蝶影视",
            "vod_content": content_str,
            "vod_play_from": "橙果短剧",
            "vod_play_url": "#".join(episodes)
        }

        return {"list": [vod]}

    def playerContent(self, flag, id, vipFlags):
        play_path = id if id.startswith("/") else "/" + id
        play_url = parse.urljoin(self.site_url, play_path)

        res = self._fetch(play_url)
        body = res.get("body", "")

        video_url = ""

        nuxt_m = re.search(r'<script[^>]+id=["\']__NUXT_DATA__["\'][^>]*>([\s\S]*?)</script>', body)
        if nuxt_m:
            try:
                arr = json.loads(nuxt_m.group(1).strip())
                for item in arr:
                    if isinstance(item, str) and ".m3u8" in item and item.startswith("http"):
                        video_url = item
                        break
            except Exception:
                pass

        if not video_url:
            m3u8_m = re.search(r'["\'](https?://[^"\'\s<>\\]+\.m3u8[^"\'\s<>\\]*)["\']', body)
            if m3u8_m:
                video_url = m3u8_m.group(1).replace("\\u002F", "/").replace("\\/", "/")

        if video_url:
            return {
                "parse": 0,
                "playUrl": "",
                "url": video_url,
                "header": {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Referer": self.site_url + "/"
                }
            }

        return {"parse": 0, "playUrl": "", "url": ""}

    def searchContent(self, key, quick, pg="1"):
        p = int(pg)
        search_url = "%s/search?keyword=%s" % (self.site_url, parse.quote(key)) if p <= 1 else "%s/search?keyword=%s&page=%d" % (self.site_url, parse.quote(key), p)

        res = self._fetch(search_url)
        body = res.get("body", "")

        vod_list = []
        seen_ids = set()

        nuxt_m = re.search(r'<script[^>]+id=["\']__NUXT_DATA__["\'][^>]*>([\s\S]*?)</script>', body)
        if nuxt_m:
            try:
                arr = json.loads(nuxt_m.group(1).strip())
                for item in arr:
                    if isinstance(item, dict) and "title" in item and ("slug" in item or "detail_route" in item):
                        t_idx = item.get("title")
                        title = arr[t_idx] if isinstance(t_idx, int) and t_idx < len(arr) else t_idx
                        if not title or not isinstance(title, str):
                            continue

                        d_route = item.get("detail_route")
                        drama_path = arr[d_route] if isinstance(d_route, int) and d_route < len(arr) else d_route
                        if not drama_path:
                            slug_val = item.get("slug")
                            slug = arr[slug_val] if isinstance(slug_val, int) and slug_val < len(arr) else slug_val
                            if slug:
                                drama_path = "/drama/%s" % slug

                        if not drama_path or drama_path in seen_ids:
                            continue

                        final_pic = ""
                        cover_obj = item.get("cover")
                        if isinstance(cover_obj, int) and cover_obj < len(arr):
                            cover_obj = arr[cover_obj]

                        if isinstance(cover_obj, dict):
                            u_idx = cover_obj.get("url")
                            raw_u = arr[u_idx] if isinstance(u_idx, int) and u_idx < len(arr) else u_idx
                            if raw_u and isinstance(raw_u, str):
                                final_pic = self._proxy_img(raw_u)

                        eps_val = item.get("total_episode_count") or item.get("published_episode_count") or item.get("latest_episode_number")
                        if isinstance(eps_val, int) and eps_val < len(arr) and not isinstance(arr[eps_val], (dict, list)):
                            eps_num = arr[eps_val]
                        else:
                            eps_num = eps_val
                        remarks = "蝴蝶影视 · %s集" % eps_num if eps_num else "蝴蝶影视"

                        seen_ids.add(drama_path)
                        vod_list.append({
                            "vod_id": drama_path,
                            "vod_name": title,
                            "vod_pic": final_pic,
                            "vod_remarks": remarks,
                            "vod_actor": "🦋 TG群: @tvshare23",
                            "vod_director": "🦋 蝴蝶影视"
                        })
            except Exception:
                pass

        return {
            "page": p,
            "pagecount": p + 1 if len(vod_list) >= 12 else p,
            "limit": len(vod_list),
            "total": 999,
            "list": vod_list
        }

    def action(self, action):
        return {}

    def liveContent(self):
        return ""

    def localProxy(self, params):
        return [404, "text/plain", b""]

    def manualVideoCheck(self):
        return False

    def isVideoFormat(self, url):
        return False

    def destroy(self):
        pass
