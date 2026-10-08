# -*- coding: utf-8 -*-
"""
十区影视 - 四壳通用Python Spider（v1.1修复版）
站点: 从跳转站解析出的10个独立域名
结构: 自定义CMS，视频信息直接编码在URL里（?v=m3u8&b=封面图）
列表URL: https://{domain}/index.php/{type}/type/id/{id}.html
视频URL: /html/dcdc/{乱码标题}.html?v={m3u8}&b={封面图}
封面: img.lazy的data-original属性
标题: p.km-script标签
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
    siteName = "十区影视"
    
    # 10个区的配置（每个区对应不同域名）
    QU_CONFIG = {
        "13": {"name": "一区", "domain": "618026.xyz", "type": "vod", "id": "13"},
        "1":  {"name": "二区", "domain": "618315.xyz", "type": "vod", "id": "1"},
        "66": {"name": "三区", "domain": "618126.xyz", "type": "vod", "id": "66"},
        "5":  {"name": "四区", "domain": "618156.xyz", "type": "art", "id": "5"},
        "2":  {"name": "五区", "domain": "618407.xyz", "type": "vod", "id": "2"},
        "44": {"name": "六区", "domain": "618250.xyz", "type": "vod", "id": "44"},
        "40": {"name": "七区", "domain": "618614.xyz", "type": "vod", "id": "40"},
        "66b": {"name": "八区", "domain": "618695.xyz", "type": "vod", "id": "66"},
        "35": {"name": "九区", "domain": "618736.xyz", "type": "vod", "id": "35"},
        "27": {"name": "漫画", "domain": "618768.xyz", "type": "art", "id": "27"},
    }
    
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
    
    # ==================== 解析列表（vodbox + xowe-thumb-bl两种模板） ====================
    def _parse_list(self, html):
        videos = []
        seen_urls = set()
        
        # 模板1: vodbox（一区/二区/三区/八区）
        items1 = re.findall(r'<a class="vodbox"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.S)
        for href, item_html in items1:
            try:
                m3u8_url = ""
                cover_url = ""
                
                # 提取m3u8：支持多种参数名 v/kd/id/m
                m3u8_url = ""
                for param in ["v", "kd", "id", "m"]:
                    match = re.search(rf'[?&]{param}=([^&]+)', href)
                    if match:
                        m3u8_url = urllib.parse.unquote(match.group(1))
                        break
                
                # 提取b参数（封面图）
                b_match = re.search(r'[?&]b=([^&]+)', href)
                if b_match:
                    cover_url = urllib.parse.unquote(b_match.group(1))
                
                if not m3u8_url:
                    continue
                
                # 标题：从p.km-script提取
                vod_name = ""
                title_match = re.search(r'<p class="km-script">(.*?)</p>', item_html, re.S)
                if title_match:
                    vod_name = self._strip_tags(title_match.group(1)).strip()
                
                if not vod_name or len(vod_name) < 3:
                    vod_name = f"视频{len(videos)+1}"
                
                # 封面：优先从img的data-original提取，备用从b参数
                vod_pic = ""
                pic_match = re.search(r'<img[^>]*data-original="([^"]+\.(?:jpg|jpeg|png))"', item_html)
                if pic_match:
                    vod_pic = pic_match.group(1)
                elif cover_url:
                    vod_pic = cover_url
                
                vod_id = m3u8_url
                if vod_id in seen_urls:
                    continue
                seen_urls.add(vod_id)
                
                videos.append({
                    "vod_id": vod_id,
                    "vod_name": vod_name,
                    "vod_pic": vod_pic,
                    "vod_remarks": "",
                })
            except Exception:
                continue
        
        # 模板2: xowe-thumb-bl（四区/其他区）
        # 直接找所有 /html/*.html?m= 格式的链接
        items2 = re.findall(r'href="(/html/[^"]+\.html\?m=([^&"]+)[^"]*)"', html)
        for href, m3u8_path in items2:
            try:
                m3u8_url = urllib.parse.unquote(m3u8_path)
                
                # 从href找标题（从父元素里找）
                vod_name = ""
                # 找xowe-thumb-name
                name_match = re.search(r'xowe-thumb-name[^"]*">(.*?)</div>', html, re.S)
                if name_match:
                    vod_name = self._strip_tags(name_match.group(1)).strip()
                
                if not vod_name or len(vod_name) < 3:
                    vod_name = f"视频{len(videos)+1}"
                
                # 封面：从img的data-cover提取
                vod_pic = ""
                pic_match = re.search(r'data-cover="([^"]+\.(?:jpg|jpeg|png))"', html)
                if pic_match:
                    vod_pic = pic_match.group(1)
                
                vod_id = href
                if vod_id in seen_urls:
                    continue
                seen_urls.add(vod_id)
                
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
        for tid, cfg in self.QU_CONFIG.items():
            classes.append({
                "type_id": tid,
                "type_name": cfg["name"],
            })
        return {"class": classes, "filters": {}}
    
    # ==================== 2. categoryContent ====================
    def categoryContent(self, tid, pg, filter=False, extend=None):
        pg = int(pg) if pg else 1
        
        # 根据tid选择对应的区配置
        qu_cfg = self.QU_CONFIG.get(tid)
        if not qu_cfg:
            return {
                "page": pg,
                "pagecount": pg,
                "limit": 20,
                "total": 0,
                "list": [],
            }
        
        domain = qu_cfg["domain"]
        vtype = qu_cfg["type"]
        vid = qu_cfg["id"]
        
        url = f"https://{domain}/index.php/{vtype}/type/id/{vid}.html"
        if pg > 1:
            url = f"https://{domain}/index.php/{vtype}/type/id/{vid}-{pg}.html"
        
        html = self._fetch(url)
        videos = self._parse_list(html)
        
        return {
            "page": pg,
            "pagecount": pg,
            "limit": 20,
            "total": len(videos),
            "list": videos,
        }
    
    # ==================== 3. detailContent（直接返回m3u8） ====================
    def detailContent(self, ids):
        if isinstance(ids, str):
            ids = [ids]
        if not isinstance(ids, (list, tuple)):
            ids = [str(ids)]
        
        list_data = []
        for m3u8_url in ids:
            try:
                m3u8_url = str(m3u8_url).strip()
                if not m3u8_url:
                    continue
                
                vod_id = m3u8_url
                vod_name = f"视频{len(list_data)+1}"
                vod_pic = ""
                
                vod_play_from = "十区影视"
                vod_play_url = f"第1集${m3u8_url}"
                
                detail = {
                    "vod_id": vod_id,
                    "vod_name": vod_name,
                    "vod_pic": vod_pic,
                    "vod_remarks": "十区影视",
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
            "limit": 20,
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
    print("十区影视 Spider v1.1 自测（每个区独立域名）")
    print("=" * 60)
    
    print("\n[1] homeContent:")
    home = sp.homeContent()
    print(f"  分类数: {len(home.get('class', []))}")
    for c in home.get("class", []):
        print(f"    {c['type_id']:5s}  {c['type_name']}")
    
    # 测试每个区
    print("\n[2] 测试每个区的视频数:")
    for tid, cfg in sp.QU_CONFIG.items():
        cat = sp.categoryContent(tid, 1)
        count = len(cat.get("list", []))
        print(f"  {cfg['name']:5s} ({cfg['domain']}): {count} 个视频")
    
    print("\n" + "=" * 60)
    print("自测完成!")
