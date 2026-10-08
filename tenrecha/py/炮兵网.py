# -*- coding: utf-8 -*-
"""
炮兵网 - 四壳通用Python Spider
站点: https://mef.pbw7.quest/pbw/
结构: 苹果CMS标准格式，img-list dis列表，详情页vod/play/id/{id}/sid/1/nid/1.html，player_data.url直出m3u8
分类URL: /cn/home/web/index.php/vod/type/id/{cid}.html（完整路径）
详情URL: /cn/home/web/index.php/vod/play/id/{vod_id}/sid/1/nid/1.html
封面: img-list dis里的img标签（data-original懒加载）
标题: h3标签里的a标签
注意: 需要代理访问
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
    domain = "https://mef.pbw7.quest"
    siteName = "炮兵网"
    base_path = "/cn/home/web/index.php"
    
    # 分类硬编码（12个）
    CATEGORIES = [
        {"type_id": "1", "type_name": "乱伦"},
        {"type_id": "2", "type_name": "出轨"},
        {"type_id": "3", "type_name": "制服"},
        {"type_id": "4", "type_name": "自慰"},
        {"type_id": "5", "type_name": "偷拍"},
        {"type_id": "20", "type_name": "自拍"},
        {"type_id": "21", "type_name": "国产"},
        {"type_id": "22", "type_name": "同性"},
        {"type_id": "23", "type_name": "日韩"},
        {"type_id": "24", "type_name": "欧美"},
        {"type_id": "25", "type_name": "三级"},
        {"type_id": "26", "type_name": "动漫"},
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
    
    # ==================== HTTP请求（TVBox壳内自动走全局代理） ====================
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
    
    # ==================== 解析列表（img-list结构） ====================
    def _parse_list(self, html):
        videos = []
        seen_ids = set()
        
        # 找img-list里的li标签
        # 先找ul.img-list的内容
        list_match = re.search(r'<ul class="img-list[^"]*">(.*?)</ul>', html, re.S)
        if not list_match:
            return videos
        
        list_html = list_match.group(1)
        
        # 找每个li标签（每个li是一个视频项）
        items = re.findall(r'<li>(.*?)</li>', list_html, re.S)
        
        for item_html in items:
            try:
                # 找vod_id
                id_match = re.search(r'vod/play/id/(\d+)', item_html)
                if not id_match:
                    continue
                vod_id = id_match.group(1)
                
                if vod_id in seen_ids:
                    continue
                seen_ids.add(vod_id)
                
                # 标题：从h2标签里找
                vod_name = ""
                h2_match = re.search(r'<h2>(.*?)</h2>', item_html, re.S)
                if h2_match:
                    vod_name = self._strip_tags(h2_match.group(1)).strip()
                
                if not vod_name:
                    # 从a标签的title属性
                    title_match = re.search(r'title="([^"]+)"', item_html)
                    if title_match:
                        vod_name = title_match.group(1).strip()
                
                if not vod_name or len(vod_name) < 3:
                    continue
                
                # 封面：从src提取
                vod_pic = ""
                pic_match = re.search(r'<img[^>]*src="([^"]+\.(?:jpg|jpeg|png))"', item_html)
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
        # 分类页URL（完整路径）
        url = f"{self.domain}{self.base_path}/vod/type/id/{tid}.html"
        if pg > 1:
            url = f"{self.domain}{self.base_path}/vod/type/id/{tid}/page/{pg}.html"
        
        html = self._fetch(url)
        videos = self._parse_list(html)
        
        # 分页信息
        pagecount = pg
        total = len(videos)
        pages = re.findall(r'/vod/type/id/\d+/page/(\d+)\.html', html)
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
                # 详情页URL（完整路径）
                detail_url = f"{self.domain}{self.base_path}/vod/play/id/{vod_id}/sid/1/nid/1.html"
                html = self._fetch(detail_url)
                if not html or len(html) < 1000:
                    continue
                
                # 从player_data提取m3u8
                m3u8_url = ""
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
                
                # 标题（title标签，去掉后缀）
                vod_name = f"视频{vod_id}"
                title_match = re.search(r'<title>(.*?)</title>', html, re.S)
                if title_match:
                    vod_name = self._strip_tags(title_match.group(1))
                    # 去掉后缀
                    vod_name = re.sub(r'[-_–—].*?炮兵网.*$', '', vod_name)
                    vod_name = re.sub(r'[-_–—]第\d+集.*$', '', vod_name)
                    vod_name = vod_name.strip()
                
                if not vod_name or vod_name == self.siteName:
                    vod_name = f"视频{vod_id}"
                
                # 封面
                pic_match = re.search(r'(?:data-original|data-src|src)="([^"]+\.(?:jpg|jpeg|png))"', html)
                vod_pic = pic_match.group(1) if pic_match else ""
                
                # 播放线路
                vod_play_from = "炮兵网"
                vod_play_url = f"第1集${m3u8_url}"
                
                detail = {
                    "vod_id": vod_id,
                    "vod_name": vod_name,
                    "vod_pic": vod_pic,
                    "vod_remarks": "炮兵网",
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
    print("炮兵网 Spider 自测")
    print("=" * 60)
    
    print("\n[1] homeContent:")
    home = sp.homeContent()
    print(f"  分类数: {len(home.get('class', []))}")
    for c in home.get("class", [])[:3]:
        print(f"    {c['type_id']}: {c['type_name']}")
    
    print("\n[2] categoryContent (id=1, page=1):")
    cat = sp.categoryContent("1", 1)
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
