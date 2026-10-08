# coding: utf-8
# Lvmao影院爬虫
# 站点: https://www.baptbo.vip/
# 类型: 成人影视站
# 特点: 详情页直接提供m3u8地址

import json
import re
from urllib.parse import urljoin, urlparse

from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://www.baptbo.vip"
        self.classes = [
            {"type_id": "1", "type_name": "大陆"},
            {"type_id": "2", "type_name": "日韩"},
            {"type_id": "3", "type_name": "欧美"},
            {"type_id": "4", "type_name": "动画"},
            {"type_id": "5", "type_name": "三级"},
        ]
        self.filters = {
            "1": [],
            "2": [],
            "3": [],
            "4": [],
            "5": [],
        }
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36",
            "Referer": self.host + "/",
        }
        # m3u8_analyzer取证结论：无广告特征，直接返回原始直链
        self.NEED_CLEAN = False

    def getName(self):
        return "Lvmao影院"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        # 从首页HTML解析推荐内容
        url = self.host + "/"
        html = self._fetch_html(url)
        if not html:
            return {"list": []}
        items = self._parse_list(html)
        return {"list": items}
    def _fetch_html(self, url):
        try:
            r = self.fetch(url, headers=self.headers, timeout=15, verify=False)
            if r is None:
                self.log({"_fetch_html": "r is None", "url": url})
                return ""
            if hasattr(r, 'text') and r.text:
                return r.text
            if hasattr(r, 'content') and r.content:
                try:
                    return r.content.decode('utf-8', errors='ignore')
                except:
                    pass
            self.log({"_fetch_html": "empty", "url": url, "type": str(type(r))})
            return ""
        except Exception as e:
            self.log({"_fetch_html": "exception", "url": url, "error": str(e)})
            return ""
    def _parse_list(self, html):
        items = []
        # 匹配所有 /vd/数字/ 的链接
        pattern = r'<a\s+href="?/vd/(\d+)/"?[^>]*>(.*?)</a>'
        for m in re.finditer(pattern, html, re.S):
            vid = m.group(1)
            inner = m.group(2)
            
            # 提取标题：找 card-title 或直接取文本
            title = ""
            title_match = re.search(r'<div[^>]*class="?[^"]*card-title[^"]*"?[^>]*>(.*?)</div>', inner, re.S)
            if title_match:
                title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
            if not title:
                # 尝试从纯文本提取（去掉标签）
                text = re.sub(r'<[^>]+>', ' ', inner).strip()
                # 如果文本长度合理，取最后一段（通常是标题）
                parts = [p.strip() for p in text.split() if p.strip()]
                if parts:
                    title = parts[-1] if len(parts) > 1 else " ".join(parts)
            
            # 提取图片
            pic = ""
            img_match = re.search(r'<img[^>]*(?:data-src|src)="?([^"\s>]+)"?[^>]*>', inner, re.S)
            if img_match:
                pic = img_match.group(1)
            
            if vid and title:
                items.append({
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": "",
                })
        return items
    def categoryContent(self, tid, pg, filter, extend):
        page = pg or "1"
        # 修正：使用 tid 构建分类URL
        if page == "1":
            url = f"{self.host}/category/{tid}/"
        else:
            url = f"{self.host}/category/{tid}/page/{page}/"
        self.log({"category": "url", "url": url})
        try:
            r = self.fetch(url, headers=self.headers, timeout=15, verify=False)
            self.log({"category": "fetch_result", "r_is_none": r is None, "has_text": hasattr(r, 'text') if r else False})
            if r and hasattr(r, 'text'):
                html = r.text
                self.log({"category": "html_len", "len": len(html)})
                if html:
                    items = self._parse_list(html)
                    self.log({"category": "items_count", "count": len(items)})
                    return {
                        "list": items,
                        "page": int(page),
                        "pagecount": 999,
                        "limit": 20,
                        "total": 999,
                    }
        except Exception as e:
            self.log({"category": "exception", "error": str(e)})
        return {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}
    @staticmethod
    def _norm_ids(ids):
        if ids is None:
            return ""
        if isinstance(ids, (list, tuple)):
            if not ids:
                return ""
            ids = ids[0]
        if isinstance(ids, bytes):
            ids = ids.decode("utf-8", errors="ignore")
        return str(ids).strip()

    def _skeleton(self, vid, title="", pic="", remarks="解析中"):
        return {"list": [{
            "vod_id": vid,
            "vod_name": title or "未知标题",
            "vod_pic": pic or "",
            "vod_remarks": remarks,
            "vod_content": "",
            "vod_play_from": "播放",
            "vod_play_url": f"播放${vid}",
        }]}

    def detailContent(self, ids):
        vid = self._norm_ids(ids)
        if not vid:
            return {"list": []}
        
        if "|$|" in vid:
            parts = vid.split("|$|")
            if len(parts) >= 5 and parts[4]:
                return {"list": [{
                    "vod_id": vid,
                    "vod_name": parts[1],
                    "vod_pic": parts[2],
                    "vod_remarks": parts[3],
                    "vod_content": parts[3],
                    "vod_play_from": "直链",
                    "vod_play_url": "播放$%s" % parts[4],
                }]}

        title = pic = desc = ""
        try:
            url = "%s/vd/%s/" % (self.host, vid)
            html = self._fetch_html(url)
            if not html:
                return self._skeleton(vid)

            # 标题
            title_match = re.search(r'<div[^>]*class="?[^"]*text-lg[^"]*font-bold[^"]*"?[^>]*>(.*?)</div>', html, re.S)
            if title_match:
                title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
            else:
                og_match = re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"', html)
                if og_match:
                    title = og_match.group(1).strip()

            # 封面
            pic_match = re.search(r'data-poster="?([^"\s>]+)"?', html)
            if pic_match:
                pic = pic_match.group(1)
            else:
                meta_match = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', html)
                if meta_match:
                    pic = meta_match.group(1)

            # 分类标签
            tags = []
            for m in re.finditer(r'<a[^>]*href="/category/[^"]*"[^>]*>([^<]+)</a>', html):
                tags.append(m.group(1).strip())
            desc = ", ".join(tags) if tags else ""

            # 播放地址：从 player-wrap data-m3u8 提取
            play_url = ""
            # 方法1: 直接搜索 data-m3u8
            m3u8_match = re.search(r'data-m3u8="?([^"\s>]+)"?', html)
            if m3u8_match:
                play_url = m3u8_match.group(1)
            # 方法2: 搜索 player-wrap 标签内的 m3u8
            if not play_url:
                wrap_match = re.search(r'<div[^>]*id="player-wrap"[^>]*data-m3u8="?([^"\s>]+)"?', html, re.S)
                if wrap_match:
                    play_url = wrap_match.group(1)
            # 方法3: 搜索任何 m3u8 链接
            if not play_url:
                m3u8_pattern = r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*'
                m3u8_matches = re.findall(m3u8_pattern, html)
                if m3u8_matches:
                    play_url = m3u8_matches[0]

            if play_url:
                from_str = "播放"
                url_str = "播放$%s" % play_url
            else:
                return self._skeleton(vid, title, pic)

            return {"list": [{
                "vod_id": vid,
                "vod_name": title or "未知标题",
                "vod_pic": pic or "",
                "vod_remarks": "",
                "vod_content": desc,
                "vod_actor": "",
                "vod_director": "",
                "vod_play_from": from_str,
                "vod_play_url": url_str,
            }]}

        except Exception as e:
            return self._skeleton(vid, title, pic)
    def searchContent(self, key, quick, pg="1"):
        # 搜索页: /search/?keyword=xxx
        url = f"{self.host}/search/?keyword={key}"
        html = self._fetch_html(url)
        if not html:
            return {"list": [], "page": 1}
        items = self._parse_list(html)
        return {"list": items, "page": int(pg)}

    def playerContent(self, flag, id, vipFlags):
        ua = self.headers.get("User-Agent", "")
        play_url = str(id or "").strip()
        
        # 如果id是"名称$地址"格式，提取地址部分
        if play_url and "$" in play_url:
            parts = play_url.split("$", 1)
            if len(parts) == 2:
                play_url = parts[1]
        
        # 补全协议
        if play_url and not play_url.startswith("http"):
            if not play_url.startswith("//"):
                play_url = "https://" + play_url
        
        # 直链检测
        if play_url and play_url.startswith("http"):
            # m3u8_analyzer取证结论：无广告特征，直接返回原始直链
            return {"parse": 0, "url": play_url, "header": {"User-Agent": ua}}
        
        # 无法提取直链，降级到播放页
        return {"parse": 1, "url": play_url or "", "header": {"User-Agent": ua, "Referer": self.host + "/"}}

    def recommendContent(self, ids, pg):
        # 相关推荐从详情页获取
        vid = self._norm_ids(ids) if ids else ""
        if not vid:
            return {"list": []}
        try:
            url = f"{self.host}/vd/{vid}/"
            html = self._fetch_html(url)
            if not html:
                return {"list": []}
            items = self._parse_list(html)
            return {"list": items}
        except Exception:
            return {"list": []}

    def destroy(self):
        pass