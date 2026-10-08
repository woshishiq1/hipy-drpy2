# -*- coding: utf-8 -*-
"""
Porn00 - 四壳通用Python Spider
站点: https://www.porn00.tv/
结构: 自定义CMS（英文站），div.item列表，/video/{slug}/详情页，mp4直链带token
分类URL: /latest-vids/、/videos-all/、/popular-vids/、/top-vids/
详情URL: /video/{slug}/
封面: img.thumb.lazy-load的data-original属性
标题: a标签的title属性
播放: mp4直链（480p+720p双线路）
注意: 直连可访问
"""

import re
import json
import urllib.request
import urllib.parse
import urllib.error

# ==================== 双协议兼容基类 ====================
try:
    from base.spider import Spider
except Exception:
    class Spider:
        def __init__(self):
            self.extend = {}
        def init(self, extend):
            self.extend = extend if isinstance(extend, dict) else {}
        def isVideoFormat(self, url):
            return any(url.lower().endswith(ext) for ext in ['.m3u8', '.mp4', '.flv', '.ts'])
        def homeContent(self, filter):
            return {}
        def categoryContent(self, tid, pg, filter, extend):
            return {}
        def detailContent(self, ids):
            return {}
        def searchContent(self, key, quick, pg):
            return {}
        def playerContent(self, flag, id, vipFlags):
            return {}
        def localProxy(self, param):
            return [404, "text/plain", ""]
        def getDependence(self):
            return ""
        def destroy(self):
            pass

# ==================== 主Spider类 ====================
class Spider(Spider):
    domain = "https://www.porn00.tv"
    siteName = "Porn00"
    
    # 分类硬编码（6个主分类）
    CATEGORIES = [
        {"type_id": "latest-vids", "type_name": "最新视频"},
        {"type_id": "videos-all", "type_name": "全部视频"},
        {"type_id": "popular-vids", "type_name": "最受欢迎"},
        {"type_id": "top-vids", "type_name": "最高评分"},
        {"type_id": "categories-list", "type_name": "分类浏览"},
        {"type_id": "pornstars-list", "type_name": "明星列表"},
    ]
    
    UA_CHROME = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    
    def __init__(self):
        super().__init__()
        self.extend = {}
    
    def init(self, extend=""):
        if isinstance(extend, dict):
            self.extend = extend
        elif isinstance(extend, str) and extend.strip():
            try:
                self.extend = json.loads(extend)
            except Exception:
                self.extend = {}
        else:
            self.extend = {}
    
    def getDependence(self):
        return ""
    
    def destroy(self):
        pass
    
    # ==================== HTTP请求 ====================
    def _fetch(self, url, timeout=20):
        headers = {
            "User-Agent": self.UA_CHROME,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
            "Referer": self.domain + "/",
        }
        req = urllib.request.Request(url, headers=headers)
        try:
            resp = urllib.request.urlopen(req, timeout=timeout)
            content = resp.read()
            return content.decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return ""
            try:
                return e.read().decode("utf-8", errors="replace")
            except Exception:
                return ""
        except Exception:
            return ""
    
    def _strip_tags(self, html):
        if not html:
            return ""
        return re.sub(r"<[^>]+>", "", html).strip()
    
    # ==================== 解析列表（div.item结构） ====================
    def _parse_list(self, html):
        videos = []
        seen_ids = set()
        
        # 找所有div.item项
        items = re.findall(r'<div class="item[^"]*">(.*?)</div>\s*</div>', html, re.S)
        
        for item_html in items:
            try:
                # 找视频链接（slug）
                link_match = re.search(r'<a[^>]*href="(https?://www\.porn00\.tv/video/([^/]+)/)"', item_html)
                if not link_match:
                    continue
                video_url = link_match.group(1)
                video_slug = link_match.group(2)
                
                if video_slug in seen_ids:
                    continue
                seen_ids.add(video_slug)
                
                # 标题：优先从a标签的title属性提取
                vod_name = ""
                title_attr = re.search(r'<a[^>]*title="([^"]+)"', item_html)
                if title_attr:
                    vod_name = title_attr.group(1).strip()
                
                if not vod_name or len(vod_name) < 3:
                    continue
                
                # 封面：从img.thumb.lazy-load的data-original提取
                vod_pic = ""
                pic_match = re.search(r'<img[^>]*class="thumb lazy-load"[^>]*data-original="([^"]+\.(?:jpg|jpeg|png|webp))"', item_html)
                if not pic_match:
                    pic_match = re.search(r'data-original="([^"]+\.(?:jpg|jpeg|png|webp))"', item_html)
                if pic_match:
                    vod_pic = pic_match.group(1)
                
                videos.append({
                    "vod_id": video_slug,
                    "vod_name": vod_name,
                    "vod_pic": vod_pic,
                    "vod_remarks": "",
                })
            except Exception:
                continue
        return videos
    
    # ==================== 1. homeContent ====================
    def homeContent(self, filter=False):
        classes = []
        filters = {}
        for cat in self.CATEGORIES:
            classes.append({
                "type_id": cat["type_id"],
                "type_name": cat["type_name"],
            })
            filters[cat["type_id"]] = {}
        return {"class": classes, "filters": filters}
    
    # ==================== 2. categoryContent ====================
    def categoryContent(self, tid, pg, filter=False, extend=None):
        pg = int(pg) if pg else 1
        # 分类页URL
        url = f"{self.domain}/{tid}/"
        if pg > 1:
            url = f"{self.domain}/{tid}/{pg}/"
        
        html = self._fetch(url)
        videos = self._parse_list(html)
        
        # 分页信息
        pagecount = pg
        total = len(videos)
        pages = re.findall(rf'/{tid}/(\d+)', html)
        if pages:
            pagecount = max(int(p) for p in pages if int(p) < 10000)
        
        return {
            "page": pg,
            "pagecount": pagecount,
            "limit": 28,
            "total": total,
            "list": videos,
        }
    
    # ==================== 3. detailContent（直接访问详情页获取mp4） ====================
    def detailContent(self, ids):
        if isinstance(ids, str):
            ids = [ids]
        if not isinstance(ids, (list, tuple)):
            ids = [str(ids)]
        
        list_data = []
        for video_slug in ids:
            try:
                video_slug = str(video_slug).strip()
                # 详情页URL
                detail_url = f"{self.domain}/video/{video_slug}/"
                html = self._fetch(detail_url)
                if not html or len(html) < 1000:
                    continue
                
                # 找mp4直链
                mp4_urls = re.findall(r'https?://[^\s"\'\\]+\.mp4[^\s"\'\\]*', html)
                if not mp4_urls:
                    continue
                
                # 过滤掉预览图（.mp4.jpg）
                mp4_urls = [u for u in mp4_urls if not u.endswith(".jpg")]
                
                if not mp4_urls:
                    continue
                
                # 标题（title标签，去掉后缀）
                vod_name = video_slug
                title_match = re.search(r'<title>(.*?)</title>', html, re.S)
                if title_match:
                    vod_name = self._strip_tags(title_match.group(1))
                    # 去掉后缀（- Porn00）
                    vod_name = re.sub(r'\s*-\s*Porn00\s*$', '', vod_name)
                    vod_name = vod_name.strip()
                
                if not vod_name or vod_name == self.siteName:
                    vod_name = video_slug.replace("-", " ").title()
                
                # 封面
                pic_match = re.search(r'(?:data-original|data-src|src)="([^"]+\.(?:jpg|jpeg|png|webp))"', html)
                vod_pic = pic_match.group(1) if pic_match else ""
                
                # 播放线路（480p + 720p）
                vod_play_from = "Porn00"
                play_urls = []
                for i, mp4_url in enumerate(mp4_urls[:2]):
                    quality = "720p" if "720p" in mp4_url else "480p"
                    play_urls.append(f"第{i+1}集[{quality}]${mp4_url}")
                
                vod_play_url = "#".join(play_urls)
                
                detail = {
                    "vod_id": video_slug,
                    "vod_name": vod_name,
                    "vod_pic": vod_pic,
                    "vod_remarks": "Porn00",
                    "vod_actor": "",
                    "vod_director": "",
                    "vod_content": "",
                    "vod_year": "",
                    "vod_area": "",
                    "vod_tags": "",
                    "vod_douban_score": "",
                    "vod_play_from": vod_play_from,
                    "vod_play_url": vod_play_url,
                }
                list_data.append(detail)
            except Exception:
                continue
        
        return {"list": list_data}
    
    # ==================== 4. searchContent ====================
    def searchContent(self, key, quick=False, pg=1):
        return {
            "page": pg,
            "pagecount": 0,
            "limit": 28,
            "total": 0,
            "list": [],
        }
    
    # ==================== 5. playerContent ====================
    def playerContent(self, flag, id, vipFlags=None):
        if not id:
            return {"parse": 0, "jx": 0, "url": "", "header": {}}
        
        url = id
        header = {
            "User-Agent": self.UA_CHROME,
            "Referer": self.domain + "/",
        }
        return {
            "parse": 0,
            "jx": 0,
            "url": url,
            "header": header,
        }
    
    def localProxy(self, param):
        if not param or "do" not in param:
            return [404, "text/plain", ""]
        do = param.get("do", "")
        if do == "ck":
            url = param.get("url", "")
            if url:
                try:
                    headers = {"User-Agent": self.UA_CHROME}
                    req = urllib.request.Request(url, headers=headers)
                    resp = urllib.request.urlopen(req, timeout=15)
                    content = resp.read()
                    content_type = resp.headers.get("Content-Type", "image/jpeg")
                    return [200, content_type, content]
                except Exception:
                    pass
        return [404, "text/plain", ""]


# ==================== 调试入口 ====================
if __name__ == "__main__":
    import sys
    sp = Spider()
    sp.init("{}")
    
    print("=" * 60)
    print("Porn00 Spider 自测")
    print("=" * 60)
    
    print("\n[1] homeContent:")
    home = sp.homeContent()
    print(f"  分类数: {len(home.get('class', []))}")
    for c in home.get("class", []):
        print(f"    {c['type_id']}: {c['type_name']}")
    
    print("\n[2] categoryContent (id=latest-vids, page=1):")
    cat = sp.categoryContent("latest-vids", 1)
    print(f"  视频数: {len(cat.get('list', []))}")
    for v in cat.get("list", [])[:2]:
        print(f"    {v['vod_id'][:30]}: {v['vod_name'][:40]}")
        print(f"      封面: {v['vod_pic'][:60]}")
    
    if cat.get("list"):
        first_id = cat["list"][0]["vod_id"]
        print(f"\n[3] detailContent (id={first_id[:30]}):")
        detail = sp.detailContent([first_id])
        if detail.get("list"):
            d = detail["list"][0]
            print(f"  标题: {d['vod_name'][:50]}")
            print(f"  播放线路: {d['vod_play_from']}")
            play_urls = d['vod_play_url'].split("#")
            print(f"  播放集数: {len(play_urls)}")
            for pu in play_urls[:2]:
                print(f"    {pu[:100]}")
        else:
            print("  无详情数据")
    
    print("\n" + "=" * 60)
    print("自测完成!")
