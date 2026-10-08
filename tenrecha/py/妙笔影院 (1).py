# -*- coding: utf-8 -*-
"""
妙笔影院 - 四壳通用Python Spider
站点: https://ezq.mbyy5.pics/mbyy/
结构: 自定义CMS，fs_news_left_img列表，详情页rawUrl直出m3u8
分类URL: /vodtype/{cid}.html（根路径）
详情URL: /{vod_id}.html（简单格式）
封面: fs_news_left_img里的img标签
标题: post-title里的a标签
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
    domain = "https://ezq.mbyy5.pics"
    siteName = "妙笔影院"
    
    # 分类硬编码（13个）
    CATEGORIES = [
        {"type_id": "20", "type_name": "国产精品"},
        {"type_id": "21", "type_name": "精品三级"},
        {"type_id": "22", "type_name": "主播大秀"},
        {"type_id": "23", "type_name": "抖阴视频"},
        {"type_id": "24", "type_name": "女神学生"},
        {"type_id": "25", "type_name": "美熟少妇"},
        {"type_id": "26", "type_name": "娇妻素人"},
        {"type_id": "27", "type_name": "空姐模特"},
        {"type_id": "28", "type_name": "国产乱伦"},
        {"type_id": "29", "type_name": "自慰群交"},
        {"type_id": "30", "type_name": "野合车震"},
        {"type_id": "31", "type_name": "职场同事"},
        {"type_id": "32", "type_name": "国产名人"},
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
    
    # ==================== 解析列表（fs_news_left_img结构） ====================
    def _parse_list(self, html):
        videos = []
        seen_ids = set()
        
        # 找所有fs_news_left_img项
        items = re.findall(r'<div class="fs_news_left_img">(.*?)</div>\s*</div>', html, re.S)
        
        for item_html in items:
            try:
                # 找vod_id
                id_match = re.search(r'href="/(\d+)\.html"', item_html)
                if not id_match:
                    continue
                vod_id = id_match.group(1)
                
                if vod_id in seen_ids:
                    continue
                seen_ids.add(vod_id)
                
                # 标题：优先从a标签的title属性提取
                vod_name = ""
                title_attr = re.search(r'<a[^>]*title="([^"]+)"', item_html)
                if title_attr:
                    vod_name = title_attr.group(1).strip()
                
                if not vod_name:
                    # 从post-title里找
                    title_match = re.search(r'<div class="post-title">.*?<a[^>]*>(.*?)</a>', item_html, re.S)
                    if title_match:
                        vod_name = self._strip_tags(title_match.group(1)).strip()
                
                if not vod_name or len(vod_name) < 3:
                    continue
                
                # 清理标题：去掉重复部分（网站标题是"前半段 title后半段"重复的）
                if " title" in vod_name:
                    parts = vod_name.split(" title")
                    if parts[0].strip() == parts[1].strip():
                        vod_name = parts[0].strip()
                    else:
                        # 取前半段
                        vod_name = parts[0].strip()
                
                vod_name = re.sub(r'\s+', ' ', vod_name)
                
                # 封面：从img标签提取
                vod_pic = ""
                pic_match = re.search(r'<img[^>]*src="([^"]+\.(?:jpg|jpeg|png))"', item_html)
                if not pic_match:
                    pic_match = re.search(r'<img[^>]*data-original="([^"]+\.(?:jpg|jpeg|png))"', item_html)
                if pic_match:
                    vod_pic = pic_match.group(1)
                    # 相对路径转绝对路径
                    if vod_pic.startswith("/"):
                        vod_pic = self.domain + vod_pic
                
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
        # 分类页URL（根路径）
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
            "limit": 24,
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
                # 详情页URL（简单格式）
                detail_url = f"{self.domain}/{vod_id}.html"
                html = self._fetch(detail_url)
                if not html or len(html) < 1000:
                    continue
                
                # 从rawUrl提取m3u8
                m3u8_url = ""
                rawurl_match = re.search(r'(?:const|let|var)\s+rawUrl\s*=\s*[\'"]([^\'"]+)[\'"]', html, re.I)
                if rawurl_match:
                    m3u8_url = rawurl_match.group(1)
                
                if not m3u8_url:
                    # 备用：直接找m3u8
                    m3u8_matches = re.findall(r'https?://[^\s"\'\\]+\.m3u8[^\s"\'\\]*', html)
                    for m in m3u8_matches:
                        if 'sharer' not in m and 'balecao' not in m:
                            m3u8_url = m
                            break
                
                if not m3u8_url:
                    continue
                
                # 标题（title标签，去掉后缀）
                vod_name = f"视频{vod_id}"
                title_match = re.search(r'<title>(.*?)</title>', html, re.S)
                if title_match:
                    vod_name = self._strip_tags(title_match.group(1))
                    # 去掉前缀（正在播放:）
                    vod_name = re.sub(r'^正在播放[:：]', '', vod_name)
                    # 去掉后缀（-精品三级-妙笔影院...）
                    vod_name = re.sub(r'[-_–—].*?妙笔影院.*$', '', vod_name)
                    # 清理重复部分（网站标题是"前半段 title后半段"重复的）
                    if " title" in vod_name:
                        parts = vod_name.split(" title")
                        if parts[0].strip() == parts[1].strip():
                            vod_name = parts[0].strip()
                        else:
                            vod_name = parts[0].strip()
                    vod_name = re.sub(r'\s+', ' ', vod_name).strip()
                
                if not vod_name or vod_name == self.siteName:
                    vod_name = f"视频{vod_id}"
                
                # 封面
                pic_match = re.search(r'(?:data-original|data-src|src)="([^"]+\.(?:jpg|jpeg|png))"', html)
                vod_pic = pic_match.group(1) if pic_match else ""
                
                # 播放线路
                vod_play_from = "妙笔影院"
                vod_play_url = f"第1集${m3u8_url}"
                
                detail = {
                    "vod_id": vod_id,
                    "vod_name": vod_name,
                    "vod_pic": vod_pic,
                    "vod_remarks": "妙笔影院",
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
            "limit": 24,
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
    print("妙笔影院 Spider 自测")
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
