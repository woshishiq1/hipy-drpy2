# -*- coding: utf-8 -*-
"""
色中色在线视频 - 四壳通用Python Spider
站点: https://spnhmx.szssp7.autos/szssp/
结构: 苹果CMS变种，li.multi cate2列表+cateimg/mip-img封面+catename标题，详情页/{id}.html，const rawUrl直出m3u8
分类URL: /vodtype/{cid}.html（域名根路径）
详情URL: /{vod_id}.html（域名根路径）
封面: <div class="cateimg"><mip-img src="...">
标题: <div class="catename"><a>标题文本</a></div>
注意: 必须开代理访问（直连HTTP 000）
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

# ==================== 未成年关键词过滤（铁律13） ====================
JUVENILE_KEYWORDS = ['萝莉', '幼女', '童', '未成年', 'teen', 'loli', 'schoolgirl', '孩童', '稚子', '玉蕊', '豆蔻', '小学生', '初中生']

def is_juvenile(text):
    if not text:
        return False
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in JUVENILE_KEYWORDS)

# ==================== 主Spider类 ====================
class Spider(Spider):
    domain = "https://spnhmx.szssp7.autos"
    siteName = "色中色在线视频"
    
    # 分类硬编码（16个）
    CATEGORIES = [
        {"type_id": "20", "type_name": "日韩"},
        {"type_id": "21", "type_name": "偷拍"},
        {"type_id": "22", "type_name": "无码"},
        {"type_id": "23", "type_name": "自拍"},
        {"type_id": "24", "type_name": "巨乳"},
        {"type_id": "25", "type_name": "华人"},
        {"type_id": "26", "type_name": "嫩模"},
        {"type_id": "27", "type_name": "剧情"},
        {"type_id": "28", "type_name": "动漫"},
        {"type_id": "29", "type_name": "熟女"},
        {"type_id": "30", "type_name": "丝袜"},
        {"type_id": "31", "type_name": "三级"},
        {"type_id": "32", "type_name": "欧美"},
        {"type_id": "33", "type_name": "有码"},
        {"type_id": "34", "type_name": "制服"},
        {"type_id": "35", "type_name": "口交"},
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
    
    # ==================== 解析列表（li.multi cate2+cateimg/catename结构） ====================
    def _parse_list(self, html):
        videos = []
        # 匹配 <li class="multi cate2 ...">...</li>
        items = re.findall(r'<li[^>]*class="multi cate2[^"]*"[^>]*>(.*?)</li>', html, re.S)
        
        for item in items:
            try:
                # 提取vod_id（从cateimg里的a标签链接 /{id}.html）
                id_match = re.search(r'<div class="cateimg">\s*<a[^>]*href="/(\d+)\.html"', item)
                if not id_match:
                    id_match = re.search(r'href="/(\d+)\.html"', item)
                if not id_match:
                    continue
                vod_id = id_match.group(1)
                
                # 标题（catename里的a标签文本）
                vod_name = ""
                title_match = re.search(r'<div class="catename">\s*<a[^>]*>(.*?)</a>', item, re.S)
                if title_match:
                    vod_name = self._strip_tags(title_match.group(1))
                
                if not vod_name:
                    # 备用：a标签的title属性
                    a_title = re.search(r'<a[^>]*title="([^"]+)"', item)
                    if a_title:
                        vod_name = a_title.group(1)
                
                if not vod_name:
                    continue
                if is_juvenile(vod_name):
                    continue
                
                # 封面（cateimg里的mip-img的src属性）
                vod_pic = ""
                pic_match = re.search(r'class="cateimg".*?src="([^"]+\.(?:jpg|jpeg|png))"', item, re.S)
                if not pic_match:
                    pic_match = re.search(r'<mip-img[^>]*src="([^"]+\.(?:jpg|jpeg|png))"', item)
                if not pic_match:
                    pic_match = re.search(r'<img[^>]*src="([^"]+\.(?:jpg|jpeg|png))"', item)
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
        # 分类页URL（域名根路径，vodtype格式）
        url = f"{self.domain}/vodtype/{tid}.html"
        if pg > 1:
            url = f"{self.domain}/vodtype/{tid}-{pg}.html"
        
        html = self._fetch(url)
        videos = self._parse_list(html)
        
        # 分页信息
        pagecount = pg
        total = len(videos)
        pages = re.findall(r'/vodtype/\d+-(\d+)\.html', html)
        if pages:
            pagecount = max(int(p) for p in pages)
        
        return {
            "page": pg,
            "pagecount": pagecount,
            "limit": 60,
            "total": total,
            "list": videos,
        }
    
    # ==================== 3. detailContent（直接访问详情页获取m3u8） ====================
    def detailContent(self, ids):
        if isinstance(ids, str):
            ids = [ids]
        if not isinstance(ids, (list, tuple)):
            ids = [str(ids)]
        
        list_data = []
        for vod_id in ids:
            try:
                vod_id = str(vod_id).strip()
                # 详情页URL（域名根路径，/{id}.html）
                detail_url = f"{self.domain}/{vod_id}.html"
                html = self._fetch(detail_url)
                if not html or len(html) < 1000:
                    continue
                
                # 从const rawUrl提取m3u8
                m3u8_url = ""
                raw_match = re.search(r'(?:const|let|var)\s+rawUrl\s*=\s*[\'"]([^\'"]+)[\'"]', html, re.I)
                if raw_match:
                    m3u8_url = raw_match.group(1)
                
                if not m3u8_url:
                    # 备用：player_data
                    pd_match = re.search(r'var\s+player_data\s*=\s*(\{.*?\})', html, re.S)
                    if pd_match:
                        try:
                            pd = json.loads(pd_match.group(1))
                            m3u8_url = pd.get("url", "")
                        except Exception:
                            url_match = re.search(r'"url"\s*:\s*"([^"]+)"', pd_match.group(1))
                            if url_match:
                                m3u8_url = url_match.group(1).replace("\\/", "/")
                
                if not m3u8_url:
                    # 备用：直接找m3u8
                    m3u8_matches = re.findall(r'https?://[^\s"\'\\]+\.m3u8[^\s"\'\\]*', html)
                    for m in m3u8_matches:
                        if 'sharer' not in m and 'balecao' not in m:
                            m3u8_url = m
                            break
                
                if not m3u8_url:
                    continue
                
                if is_juvenile(m3u8_url):
                    continue
                
                # 标题（title标签，去掉"- 色中色在线视频"后缀）
                vod_name = f"视频{vod_id}"
                title_match = re.search(r'<title>(.*?)</title>', html, re.S)
                if title_match:
                    vod_name = self._strip_tags(title_match.group(1))
                    # 去掉 "- 色中色在线视频" 后缀
                    vod_name = re.sub(r'[-_–—]\s*色中色.*$', '', vod_name)
                    vod_name = vod_name.strip()
                
                if not vod_name or vod_name == self.siteName:
                    vod_name = f"视频{vod_id}"
                
                if is_juvenile(vod_name):
                    continue
                
                # 封面
                pic_match = re.search(r'(?:data-original|data-src|src)="([^"]+\.(?:jpg|jpeg|png))"', html)
                vod_pic = pic_match.group(1) if pic_match else ""
                
                # 播放线路
                vod_play_from = "色中色"
                vod_play_url = f"第1集${m3u8_url}"
                
                detail = {
                    "vod_id": vod_id,
                    "vod_name": vod_name,
                    "vod_pic": vod_pic,
                    "vod_remarks": "色中色",
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
            "limit": 60,
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
    print("色中色在线视频 Spider 自测（通过代理访问）")
    print("=" * 60)
    
    print("\n[1] homeContent:")
    home = sp.homeContent()
    print(f"  分类数: {len(home.get('class', []))}")
    for c in home.get("class", [])[:3]:
        print(f"    {c['type_id']}: {c['type_name']}")
    
    print("\n[2] categoryContent (id=20, page=1):")
    cat = sp.categoryContent("20", 1)
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
