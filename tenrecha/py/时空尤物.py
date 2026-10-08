# -*- coding: utf-8 -*-
"""
时空尤物 - 四壳通用Python Spider
站点: https://bdx.skyw8.boats/skyw/
结构: 自定义CMS，thumb lazy-load列表，/cn/home/web/index.php/vod/type/id/{cid}.html分类，/cn/home/web/index.php/vod/play/id/{vid}/sid/1/nid/1.html播放页，JSON里url字段直出m3u8
分类URL: /cn/home/web/index.php/vod/type/id/{cid}.html（完整路径）
播放页URL: /cn/home/web/index.php/vod/play/id/{vid}/sid/1/nid/1.html（完整路径）
封面: img.thumb lazy-load的data-original属性
标题: a标签的title属性
注意: 直连可访问（不用加代理行）
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
    domain = "https://bdx.skyw8.boats"
    siteName = "时空尤物"
    
    # 分类硬编码（16个）
    CATEGORIES = [
        {"type_id": "21", "type_name": "女神学生"},
        {"type_id": "22", "type_name": "美女直播"},
        {"type_id": "23", "type_name": "人妻系列"},
        {"type_id": "24", "type_name": "强奸乱伦"},
        {"type_id": "25", "type_name": "自拍偷拍"},
        {"type_id": "26", "type_name": "制服诱惑"},
        {"type_id": "27", "type_name": "巨乳系列"},
        {"type_id": "28", "type_name": "自慰系列"},
        {"type_id": "29", "type_name": "国产视频"},
        {"type_id": "30", "type_name": "无码视频"},
        {"type_id": "31", "type_name": "有码视频"},
        {"type_id": "32", "type_name": "中文字幕"},
        {"type_id": "33", "type_name": "日韩精品"},
        {"type_id": "34", "type_name": "欧美精品"},
        {"type_id": "35", "type_name": "动漫精品"},
        {"type_id": "36", "type_name": "三级伦理"},
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
            "Accept-Language": "zh-CN,zh;q=0.9",
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
    
    # ==================== 解析列表（item thumb lazy-load结构） ====================
    def _parse_list(self, html):
        videos = []
        seen_ids = set()
        
        # 找所有视频项（a标签包裹整个item）
        # 结构：<a href="...play/id/123/sid/1/nid/1.html" title="标题">...<img class="thumb lazy-load" data-original="..."/>...</a>
        items = re.findall(r'<a[^>]*href="([^"]*play/id/(\d+)/sid/\d+/nid/\d+\.html)"[^>]*title="([^"]*)"[^>]*>(.*?)</a>', html, re.S)
        
        for href, vod_id, vod_name, item_html in items:
            try:
                if vod_id in seen_ids:
                    continue
                seen_ids.add(vod_id)
                
                vod_name = vod_name.strip()
                if not vod_name or len(vod_name) < 3:
                    continue
                
                # 封面：从img.thumb lazy-load的data-original提取
                vod_pic = ""
                pic_match = re.search(r'<img[^>]*class="thumb lazy-load"[^>]*data-original="([^"]+\.(?:jpg|jpeg|png|webp))"', item_html)
                if pic_match:
                    vod_pic = pic_match.group(1)
                
                videos.append({
                    "vod_id": vod_id,
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
        for cat in self.CATEGORIES:
            classes.append({
                "type_id": cat["type_id"],
                "type_name": cat["type_name"],
            })
        return {"class": classes, "filters": {}}
    
    # ==================== 2. categoryContent ====================
    def categoryContent(self, tid, pg, filter=False, extend=None):
        pg = int(pg) if pg else 1
        
        url = f"{self.domain}/cn/home/web/index.php/vod/type/id/{tid}.html"
        if pg > 1:
            url = f"{self.domain}/cn/home/web/index.php/vod/type/id/{tid}/page/{pg}.html"
        
        html = self._fetch(url)
        videos = self._parse_list(html)
        
        # 分页信息
        pagecount = pg
        total = len(videos)
        pages = re.findall(r'/type/id/\d+/page/(\d+)\.html', html)
        if pages:
            pagecount = max(int(p) for p in pages)
        
        return {
            "page": pg,
            "pagecount": pagecount,
            "limit": 30,
            "total": total,
            "list": videos,
        }
    
    # ==================== 3. detailContent ====================
    def detailContent(self, ids):
        if isinstance(ids, str):
            ids = [ids]
        if not isinstance(ids, (list, tuple)):
            ids = [str(ids)]
        
        list_data = []
        for vod_id in ids:
            try:
                vod_id = str(vod_id).strip()
                play_url = f"{self.domain}/cn/home/web/index.php/vod/play/id/{vod_id}/sid/1/nid/1.html"
                html = self._fetch(play_url)
                if not html or len(html) < 1000:
                    continue
                
                # 从JSON的url字段提取m3u8
                m3u8_url = ""
                json_match = re.search(r'\{"flag":"play".*?"url":"([^"]+)"', html, re.S)
                if json_match:
                    m3u8_url = json_match.group(1).replace("\\/", "/")
                
                if not m3u8_url:
                    # 备用：直接找m3u8
                    m3u8_matches = re.findall(r'https?://[^\s"\'\\]+\.m3u8[^\s"\'\\]*', html)
                    for m in m3u8_matches:
                        if 'sharer' not in m and 'balecao' not in m:
                            m3u8_url = m
                            break
                
                if not m3u8_url:
                    continue
                
                # 标题
                vod_name = f"视频{vod_id}"
                title_match = re.search(r'<title>(.*?)</title>', html, re.S)
                if title_match:
                    vod_name = self._strip_tags(title_match.group(1))
                    vod_name = re.sub(r'^在线播放', '', vod_name)
                    vod_name = re.sub(r' 第\d+集.*$', '', vod_name)
                    vod_name = vod_name.strip()
                
                if not vod_name or vod_name == self.siteName:
                    vod_name = f"视频{vod_id}"
                
                # 封面
                pic_match = re.search(r'(?:data-original|data-src|src)="([^"]+\.(?:jpg|jpeg|png|webp))"', html)
                vod_pic = pic_match.group(1) if pic_match else ""
                
                vod_play_from = "时空尤物"
                vod_play_url = f"第1集${m3u8_url}"
                
                detail = {
                    "vod_id": vod_id,
                    "vod_name": vod_name,
                    "vod_pic": vod_pic,
                    "vod_remarks": "时空尤物",
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
            "limit": 30,
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
    print("时空尤物 Spider 自测")
    print("=" * 60)
    
    print("\n[1] homeContent:")
    home = sp.homeContent()
    print(f"  分类数: {len(home.get('class', []))}")
    for c in home.get("class", []):
        print(f"    {c['type_id']:5s}  {c['type_name']}")
    
    print("\n[2] categoryContent (id=21, page=1):")
    cat = sp.categoryContent("21", 1)
    print(f"  视频数: {len(cat.get('list', []))}")
    for v in cat.get("list", [])[:2]:
        print(f"    {v['vod_id']}: {v['vod_name'][:40]}")
        print(f"      封面: {v['vod_pic'][:60]}")
    
    if cat.get("list"):
        first_id = cat["list"][0]["vod_id"]
        print(f"\n[3] detailContent (id={first_id}):")
        detail = sp.detailContent([first_id])
        if detail.get("list"):
            d = detail["list"][0]
            print(f"  标题: {d['vod_name'][:50]}")
            print(f"  播放线路: {d['vod_play_from']}")
            play_urls = d['vod_play_url'].split("#")
            print(f"  播放集数: {len(play_urls)}")
            for pu in play_urls[:1]:
                print(f"    {pu[:100]}")
        else:
            print("  无详情数据")
    
    print("\n" + "=" * 60)
    print("自测完成!")
