# -*- coding: utf-8 -*-
import re
import sys
import json as _json
sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    def getName(self):
        return "樱花动漫"

    def init(self, extend=""):
        pass

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    BASE_URL = "https://www.dmvvv.com"

    def getHeaders(self):
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.dmvvv.com/"
        }

    def _get(self, url):
        import http.client, ssl
        from urllib.parse import urlparse, quote
        parsed = urlparse(url)
        # path 部分只对非 ASCII 字符编码，query 部分保持原样不再二次编码
        path = quote(parsed.path, safe='/:@!$&\'()*+,;=')
        if parsed.query:
            path = path + '?' + parsed.query
        ctx = ssl.create_default_context()
        conn = http.client.HTTPSConnection(parsed.netloc, timeout=15, context=ctx)
        conn.request("GET", path, headers=self.getHeaders())
        resp = conn.getresponse()
        data = resp.read().decode('utf-8', errors='ignore')
        conn.close()
        return data

    def _parse_id(self, ids):
        """兼容 spider_runner 传入未解析的 JSON 字符串"""
        if isinstance(ids, list) and len(ids) > 0:
            vid = ids[0]
            if isinstance(vid, str) and vid.startswith('['):
                try:
                    vid = _json.loads(vid + (']' if not vid.endswith(']') else ''))[0]
                except Exception:
                    vid = vid.lstrip('["\'').rstrip('"\']')
        elif isinstance(ids, str):
            try:
                vid = _json.loads(ids)[0]
            except Exception:
                vid = ids.strip('[]"\'')
        else:
            vid = str(ids)
        return vid

    def _li_em(self, html, label):
        m = re.search(r'<span>' + re.escape(label) + r'：</span><em>([^<]+)</em>', html)
        return m.group(1).strip() if m else ""

    def _li_plain(self, html, label):
        m = re.search(r'<span>' + re.escape(label) + r'：</span>([^<]+)', html)
        return m.group(1).strip() if m else ""

    def _parse_home_list(self, html):
        videos = []
        items = re.findall(
            r'<li>\s*<a href="(/detail/\d+/)"[^>]*title="([^"]+)"[^>]*>.*?'
            r'data-original="([^"]+)".*?<p>([^<]*)</p>',
            html, re.DOTALL
        )
        for href, title, cover, remarks in items:
            videos.append({
                "vod_id":      href,
                "vod_name":    title.strip(),
                "vod_pic":     cover.strip(),
                "vod_remarks": remarks.strip(),
            })
        return videos

    # ==================== homeContent ====================
    def homeContent(self, filter):
        classes = [
            {"type_id": "guoman", "type_name": "国产动漫"},
            {"type_id": "riman",  "type_name": "日本动漫"},
            {"type_id": "oman",   "type_name": "欧美动漫"},
            {"type_id": "dmfilm", "type_name": "动漫电影"},
        ]
        return {"class": classes, "filters": {}}

    # ==================== homeVideoContent ====================
    def homeVideoContent(self):
        try:
            html = self._get(self.BASE_URL + "/")
            videos = self._parse_home_list(html)
            seen = set()
            unique = []
            for v in videos:
                if v["vod_id"] not in seen:
                    seen.add(v["vod_id"])
                    unique.append(v)
            return {"list": unique}
        except Exception as e:
            return {"list": []}

    # ==================== categoryContent ====================
    def _parse_page_count(self, html, tid=None):
        """解析分页区域，提取总页数"""
        if tid:
            m = re.findall(r'/type/' + re.escape(tid) + r'/(\d+)/', html)
            if m:
                return max(int(x) for x in m)
        m2 = re.findall(r'/type/[^/]+/(\d+)/', html)
        if m2:
            return max(int(x) for x in m2)
        m3 = re.findall(r'[?&]page(?:no)?=(\d+)', html)
        if m3:
            return max(int(x) for x in m3)
        return None

    def categoryContent(self, tid, pg, filter, extend):
        try:
            pg = int(pg) if pg else 1
            if pg <= 1:
                url = self.BASE_URL + "/type/" + tid + "/"
            else:
                url = self.BASE_URL + "/type/" + tid + "/" + str(pg) + "/"
            html = self._get(url)
            videos = self._parse_home_list(html)
            max_pg = self._parse_page_count(html, tid)
            if max_pg is None:
                max_pg = pg + 1 if len(videos) >= 36 else pg
            return {
                "list": videos,
                "page": pg,
                "pagecount": max_pg,
                "limit": 36,
                "total": max_pg * 36,
            }
        except Exception as e:
            return {"list": []}

    # ==================== detailContent ====================
    def detailContent(self, ids):
        vid = self._parse_id(ids)
        try:
            html = self._get(self.BASE_URL + vid)

            # 标题
            title = ""
            t = re.search(r'<div class="detail">.*?<h2>([^<]+)</h2>', html, re.DOTALL)
            if t:
                title = t.group(1).strip()
            if not title:
                t2 = re.search(r'<title>([^<]+)', html)
                if t2:
                    title = t2.group(1).split('-')[0].strip()

            # 封面
            cover = ""
            c = re.search(r'<div class="cover">\s*<img[^>]+data-original="([^"]+)"', html)
            if c:
                cover = c.group(1)

            # 基本信息
            remarks   = self._li_em(html, "状态")
            year      = self._li_plain(html, "年份")
            area      = self._li_plain(html, "地区")
            type_name = self._li_plain(html, "类型")
            actor     = self._li_plain(html, "主演")
            desc      = ""
            d = re.search(r'class="blurb"[^>]*>.*?<span>[^<]+</span>(.*?)</li>', html, re.DOTALL)
            if d:
                desc = re.sub(r'<[^>]+>', '', d.group(1)).strip()

            # 播放列表
            tab_names = re.findall(r'<i class="iconfont icon-shipin"></i>([^<]+)</a>', html)
            row_blocks = re.findall(r'<div class="row"[^>]*>\s*<ul>(.*?)</ul>\s*</div>', html, re.DOTALL)

            sources_from = []
            sources_url  = []
            for i, block in enumerate(row_blocks):
                tab_name = tab_names[i].strip() if i < len(tab_names) else ("线路" + str(i + 1))
                links = re.findall(r'<a href="(/play/[^"]+)"[^>]*>([^<]+)</a>', block)
                if not links:
                    continue
                episodes = [ep.strip() + "$" + href for href, ep in links]
                sources_from.append(tab_name)
                sources_url.append("#".join(episodes))

            vod = {
                "vod_id":        vid,
                "vod_name":      title,
                "vod_pic":       cover,
                "vod_year":      year,
                "vod_area":      area,
                "vod_type":      type_name,
                "vod_actor":     actor,
                "vod_remarks":   remarks,
                "vod_content":   desc,
                "vod_play_from": "$$$".join(sources_from),
                "vod_play_url":  "$$$".join(sources_url),
            }
            return {"list": [vod]}
        except Exception as e:
            return {"list": []}

    # ==================== searchContent ====================
    def searchContent(self, keyword, quick=False, pg=1):
        try:
            from urllib.parse import quote
            kw = quote(keyword)
            pg = int(pg) if pg else 1
            if pg <= 1:
                url = self.BASE_URL + "/search/?wd=" + kw
            else:
                url = self.BASE_URL + "/search/?wd=" + kw + "&pageno=" + str(pg)
            html = self._get(url)
            videos = []
            # 先按 li 切割，再从每个 li 内提取字段
            lis = re.findall(r'<li>\s*<a class="cover".*?</li>', html, re.DOTALL)
            for li in lis:
                href_m  = re.search(r'<a class="cover" href="(/detail/\d+/)"', li)
                title_m = re.search(r'title="([^"]+)"', li)
                cover_m = re.search(r'data-original="([^"]+)"', li)
                remarks_m = re.search(r'<div class="item"><span>状态：</span>([^<]*)', li)
                if not href_m or not title_m:
                    continue
                videos.append({
                    "vod_id":      href_m.group(1),
                    "vod_name":    title_m.group(1).strip(),
                    "vod_pic":     cover_m.group(1).strip() if cover_m else "",
                    "vod_remarks": remarks_m.group(1).strip() if remarks_m else "",
                })
            # 解析总数计算总页数：找到 <em>N</em> 部影视作品
            total_m = re.search(r'找到\s*<em>(\d+)</em>', html)
            if total_m:
                total_count = int(total_m.group(1))
                max_pg = (total_count + 11) // 12
            else:
                # 备用：从 pageno 链接取最大页码
                pnos = re.findall(r'pageno=(\d+)', html)
                max_pg = max(int(x) for x in pnos) if pnos else (pg + 1 if len(videos) >= 12 else pg)
            return {
                "list":      videos,
                "page":      pg,
                "pagecount": max_pg,
                "limit":     12,
                "total":     max_pg * 12,
            }
        except Exception as e:
            return {"list": []}

    # ==================== playerContent ====================
    def playerContent(self, flag, id, vipFlags):
        try:
            url = id if id.startswith("http") else self.BASE_URL + id
            html = self._get(url)
            # Artplayer: url: 'https://xxx.m3u8'
            m = re.search(r"url:\s*'(https?://[^']+)'", html)
            if m:
                return {
                    "parse": 0,
                    "url": m.group(1),
                    "header": {
                        "User-Agent": self.getHeaders()["User-Agent"],
                        "Referer": self.BASE_URL + "/"
                    }
                }
            # 兜底匹配 m3u8
            m2 = re.search(r'(https?://[^\s\'"]+\.m3u8(?:\?[^\s\'">]*)?)', html)
            if m2:
                return {"parse": 0, "url": m2.group(1), "header": self.getHeaders()}
            return {"parse": 0, "url": id, "header": self.getHeaders()}
        except Exception as e:
            return {"parse": 0, "url": id, "header": self.getHeaders()}
