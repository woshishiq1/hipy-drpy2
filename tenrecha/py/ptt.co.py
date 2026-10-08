# -*- coding: utf-8 -*-
# 无聊自制 · ptt.co（多级分类版 + 完整剧集提取 + 播放修复）
# 修复：正确提取所有剧集，并支持直接播放

import sys
import re
import json
import requests
from urllib.parse import urljoin, quote, urlencode

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):
    def getName(self):
        return "ptt.co"

    def init(self, extend=""):
        self.host = "https://ptt.co"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.host + "/",
        })

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url

    def manualVideoCheck(self):
        return False

    def _fetch(self, url):
        try:
            r = self.session.get(url, timeout=15)
            r.encoding = "utf-8"
            return r.text
        except Exception as e:
            print(f"[ptt.co] 请求失败: {url} -> {e}")
            return ""

    def _abs_url(self, url):
        if not url:
            return ""
        if url.startswith(("http://", "https://")):
            return url
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return self.host + url
        return self.host + "/" + url

    def _clean(self, text):
        if not text:
            return ""
        return re.sub(r"\s+", " ", text.strip())

    # ---------- 生成分类列表（组合筛选） ----------
    def homeContent(self, filter=False):
        combos = [
            {"id": "1__33", "name": "📽️ 伦理电影"},
            {"id": "1_18_33", "name": "🇯🇵 日本伦理电影"},
            {"id": "1_17_33", "name": "🇰🇷 韩国伦理电影"},
            {"id": "1_18", "name": "🇯🇵 日本电影"},
            {"id": "3_18", "name": "🇯🇵 日剧"},
            {"id": "3_17", "name": "🇰🇷 韩剧"},
            {"id": "3_2", "name": "🇨🇳 大陆剧"},
            {"id": "4", "name": "🎬 全部动漫"},
            {"id": "2", "name": "🎤 综艺"},
            {"id": "66", "name": "📱 短剧"},
        ]
        classes = [{"type_id": c["id"], "type_name": c["name"]} for c in combos]
        return {"class": classes}

    def homeVideoContent(self):
        return self.categoryContent("1_18_33", "1", False, {})

    # ---------- 分类列表 ----------
    def categoryContent(self, tid, pg, filter=False, extend=None):
        pg = int(pg) if pg else 1
        parts = str(tid).split("_")
        type_id = parts[0] if parts else "1"
        area_id = parts[1] if len(parts) > 1 else ""
        cat_id = parts[2] if len(parts) > 2 else ""
        year = parts[3] if len(parts) > 3 else ""

        base_path = f"/p/{type_id}"
        if cat_id:
            base_path += f"/c/{cat_id}"
        params = {}
        if area_id:
            params["area_id"] = area_id
        if year:
            params["year"] = year
        if pg > 1:
            params["page"] = pg
        query = urlencode(params) if params else ""
        url = self.host + base_path + ("?" + query if query else "")

        html = self._fetch(url)
        if not html:
            return {"list": [], "page": pg, "pagecount": 1, "limit": 0, "total": 0}

        items = self._parse_list(html)
        pagecount = self._extract_pagecount(html, pg)

        return {
            "list": items,
            "page": pg,
            "pagecount": max(pagecount, pg),
            "limit": len(items) or 20,
            "total": max(pagecount, pg) * (len(items) or 20),
        }

    def _parse_list(self, html):
        videos = []
        seen = set()
        for card in re.finditer(
            r'<div class="col-xl-2 col-lg-2 col-md-2 col-sm-3 col-4 item.*?">(.*?)</div>\s*</div>',
            html, re.S
        ):
            card_html = card.group(1)
            link = re.search(r'<a class="visited" href="([^"]+)"', card_html)
            if not link:
                continue
            href = link.group(1)
            vod_id_match = re.search(r'/(\d+)', href)
            vod_id = vod_id_match.group(1) if vod_id_match else href
            if vod_id in seen:
                continue
            seen.add(vod_id)

            title_match = re.search(r'<div class="lines lines2">.*?<a[^>]*>(.*?)</a>', card_html, re.S)
            title = self._clean(title_match.group(1)) if title_match else ""

            img_match = re.search(r'<img[^>]+src="([^"]+)"', card_html)
            pic = img_match.group(1) if img_match else ""
            pic = self._abs_url(pic)

            remarks = []
            year_match = re.search(r'<span class="badge badge-dark">([^<]+)</span>', card_html)
            if year_match:
                remarks.append(year_match.group(1).strip())
            type_match = re.search(r'<span class="badge badge-success">([^<]+)</span>', card_html)
            if type_match:
                remarks.append(type_match.group(1).strip())
            remark = " ".join(remarks)

            videos.append({
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remark,
            })
        return videos

    def _extract_pagecount(self, html, current):
        nums = re.findall(r'<li class="page-item"><a class="page-link"[^>]*>(\d+)</a></li>', html)
        if nums:
            return max(int(x) for x in nums)
        if "page-item next" in html:
            return current + 1
        return current

    # ---------- 详情（修复：提取所有剧集） ----------
    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = ids[0]
        if not vod_id.isdigit():
            m = re.search(r'/(\d+)', vod_id)
            if m:
                vod_id = m.group(1)
            else:
                return {"list": []}

        url = f"{self.host}/{vod_id}"
        html = self._fetch(url)
        if not html:
            return {"list": []}

        # 标题
        title = ""
        title_match = re.search(r'<title>(.*?)</title>', html)
        if title_match:
            title = self._clean(title_match.group(1).split("-")[0])

        # 封面
        pic = ""
        og_img = re.search(r'<meta property="og:image" content="([^"]+)"', html)
        if og_img:
            pic = self._abs_url(og_img.group(1))
        if not pic:
            img_match = re.search(r'<img[^>]+src="([^"]+)"', html)
            if img_match:
                pic = self._abs_url(img_match.group(1))

        # ---- 提取剧集列表（核心修复） ----
        episodes = self._extract_episodes(html, vod_id)
        if not episodes:
            # 兜底：尝试提取单个播放地址
            single_url = self._extract_play_url(html)
            if single_url:
                episodes = [{"name": "第1集", "url": single_url}]

        if episodes:
            play_url = "#".join([f"{ep['name']}${ep['url']}" for ep in episodes])
            play_from = "ptt.co"
        else:
            play_url = ""
            play_from = "ptt.co"

        vod = {
            "vod_id": vod_id,
            "vod_name": title or f"视频{vod_id}",
            "vod_pic": pic,
            "vod_content": "",
            "vod_play_from": play_from,
            "vod_play_url": play_url,
        }
        return {"list": [vod]}

    def _extract_episodes(self, html, vod_id):
        """
        从详情页提取所有剧集链接
        返回 [{"name": "第1集", "url": "/507093/1/57"}, ...]
        """
        episodes = []

        # 方法1：匹配 <a class="seq border" href="...">数字</a>
        # 这是本网站的主要剧集列表
        seq_pattern = r'<a\s+class="seq\s+border[^"]*"\s+href="([^"]+)"[^>]*>(\d+)</a>'
        matches = re.findall(seq_pattern, html, re.S)
        for href, num in matches:
            # 只取数字，生成剧集名称
            name = f"第{num}集"
            # href 可能是相对路径，补全域名
            if not href.startswith('http'):
                href = self._abs_url(href)
            episodes.append({"name": name, "url": href})

        # 如果没找到，尝试其他结构（如 ul.episode）
        if not episodes:
            ul_pattern = r'<ul[^>]*class="[^"]*episode[^"]*"[^>]*>(.*?)</ul>'
            ul_match = re.search(ul_pattern, html, re.S)
            if ul_match:
                ul_html = ul_match.group(1)
                for a in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', ul_html, re.S):
                    url = a.group(1)
                    name = self._clean(a.group(2))
                    if url and name:
                        if not url.startswith('http'):
                            url = self._abs_url(url)
                        episodes.append({"name": name, "url": url})

        # 去重（保留顺序）
        seen = set()
        unique = []
        for ep in episodes:
            key = ep["url"]
            if key not in seen:
                seen.add(key)
                unique.append(ep)
        return unique

    def _extract_play_url(self, html):
        # 从页面提取单个播放地址（用于兜底）
        patterns = [
            r'<video[^>]+src="([^"]+)"',
            r'<source[^>]+src="([^"]+)"',
            r'<iframe[^>]+src="([^"]+)"',
            r'player_aaaa\s*=\s*(\{.*?\})',
            r'player_data\s*=\s*(\{.*?\})',
            r'(https?://[^\s"\']+\.(?:m3u8|mp4)[^\s"\']*)',
        ]
        for pat in patterns:
            m = re.search(pat, html, re.S)
            if m:
                if pat.endswith('\\}'):
                    try:
                        data = json.loads(m.group(1))
                        url = data.get("url", "")
                        if url:
                            return self._abs_url(url)
                    except:
                        pass
                else:
                    url = m.group(1)
                    if url.startswith("//"):
                        return "https:" + url
                    if url.startswith("http"):
                        return url
                    if url.startswith("/"):
                        return self.host + url
                    return url
        return ""

    # ---------- 播放器（修复：直接请求剧集页面提取 m3u8） ----------
    def playerContent(self, flag, id, vipFlags=None):
        result = {"parse": 0, "playUrl": "", "url": "", "header": {}}

        # 如果 id 是相对路径或完整 URL，先补全
        if "/" in id and not id.startswith("http"):
            id = self._abs_url(id)

        # 如果已经是视频格式，直接返回
        if self.isVideoFormat(id):
            result["url"] = id
            result["header"] = {"User-Agent": "Mozilla/5.0", "Referer": self.host + "/"}
            return result

        # 否则，请求该页面（可能是剧集页）提取 m3u8
        html = self._fetch(id)
        if html:
            # 尝试提取 video source
            m3u8 = self._extract_play_url(html)
            if m3u8:
                result["url"] = m3u8
                result["header"] = {"User-Agent": "Mozilla/5.0", "Referer": self.host + "/"}
                return result

        # 实在不行返回解析模式（交给外部解析）
        result["parse"] = 1
        result["url"] = id
        return result

    def searchContent(self, key, quick=False, pg="1"):
        pg = int(pg) if pg else 1
        enc_key = quote(key)
        url = f"{self.host}/search?q={enc_key}"
        if pg > 1:
            url += f"&page={pg}"
        html = self._fetch(url)
        if not html:
            return {"list": [], "page": pg, "pagecount": 1, "limit": 0, "total": 0}
        items = self._parse_list(html)
        pagecount = self._extract_pagecount(html, pg)
        return {
            "list": items,
            "page": pg,
            "pagecount": max(pagecount, pg),
            "limit": len(items) or 20,
            "total": max(pagecount, pg) * (len(items) or 20),
        }

    def localProxy(self, param):
        pass