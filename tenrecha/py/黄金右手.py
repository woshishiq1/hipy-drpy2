# -*- coding: utf-8 -*-
"""
黄金右手 - 四壳通用Python Spider
站点: https://akb.hjys9.wiki/hjys/
结构: 自定义CMS，videoBox列表，/vodtype/{cid}.html分类，/{id}.html详情，rawUrl直出m3u8
分类URL: /vodtype/{cid}.html（根路径）
详情URL: /{vod_id}.html（简单格式）
底部导航: /label/hot.html（总排行榜）/ /label/hot_day.html（日排行榜）/ /label/new.html（最新上传）
热门标签: /s/{标签名}.html（几百个标签，做成二级筛选filters）
封面: style里的background-image
标题: span.title
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
    domain = "https://akb.hjys9.wiki"
    siteName = "黄金右手"
    
    # 分类硬编码（13个主分类 + 3个底部导航子分类）
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
        # 底部导航子分类
        {"type_id": "label_hot", "type_name": "总排行榜"},
        {"type_id": "label_hot_day", "type_name": "日排行榜"},
        {"type_id": "label_new", "type_name": "最新上传"},
    ]
    
    # 热门标签（前100个，做成二级筛选filters）
    HOT_TAGS = [
        "人妻", "熟女", "巨乳", "美乳", "爆乳", "贫乳", "制服", "护士", "老师", "学生",
        "OL", "空姐", "女教师", "女上司", "人妻秘书", "人母", "未亡人", "强奸", "乱伦", "近亲",
        "继父", "继母", "公公", "婆婆", "岳母", "儿子", "女儿", "继女", "邻居", "同事",
        "同学", "医生", "警察", "小学生", "初中生", "高中生", "大学生", "JK", "萝莉", "少女",
        "老熟女", "六十路", "五十路", "美尻", "巨尻", "美脚", "美腿", "黑人", "白人", "亚洲",
        "中出", "口交", "肛交", "乳交", "足交", "骑乘", "后入", "女仆", "教师", "空姐",
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
    
    # ==================== 解析列表（videoBox结构） ====================
    def _parse_list(self, html):
        videos = []
        seen_ids = set()
        
        # 找所有videoBox项（a标签形式）
        items = re.findall(r'<a class="videoBox[^"]*"[^>]*href="\s*/(\d+)\.html"[^>]*>(.*?)</a>', html, re.S)
        
        for vod_id, item_html in items:
            try:
                if vod_id in seen_ids:
                    continue
                seen_ids.add(vod_id)
                
                # 标题：从span.title提取
                vod_name = ""
                title_match = re.search(r'<span class="title">(.*?)</span>', item_html, re.S)
                if title_match:
                    vod_name = self._strip_tags(title_match.group(1)).strip()
                
                if not vod_name or len(vod_name) < 3:
                    continue
                
                # 封面：从style里的background-image提取
                vod_pic = ""
                pic_match = re.search(r'background-image:\s*url\(([^)]+)\)', item_html)
                if pic_match:
                    vod_pic = pic_match.group(1).strip('"\' ')
                
                if not vod_pic:
                    # 备用：找img标签
                    img_match = re.search(r'<img[^>]*src="([^"]+\.(?:jpg|jpeg|png))"', item_html)
                    if img_match:
                        vod_pic = img_match.group(1)
                
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
            # 主分类下都有热门标签筛选，底部导航没有
            if not cat["type_id"].startswith("label_"):
                filters[cat["type_id"]] = [
                    {
                        "key": "tag",
                        "name": "热门标签",
                        "value": [{"n": t, "v": t} for t in self.HOT_TAGS[:50]],
                    }
                ]
        return {"class": classes, "filters": filters}
    
    # ==================== 2. categoryContent ====================
    def categoryContent(self, tid, pg, filter=False, extend=None):
        pg = int(pg) if pg else 1
        
        # 如果有标签筛选，走标签搜索页
        if extend and "tag" in extend:
            tag = extend.get("tag", "")
            if tag:
                url = f"{self.domain}/s/{tag}.html"
                if pg > 1:
                    url = f"{self.domain}/s/{tag}/page/{pg}.html"
                html = self._fetch(url)
                videos = self._parse_list(html)
                return {
                    "page": pg,
                    "pagecount": pg,
                    "limit": 30,
                    "total": len(videos),
                    "list": videos,
                }
        
        # 底部导航子分类
        if tid == "label_hot":
            url = f"{self.domain}/label/hot.html"
        elif tid == "label_hot_day":
            url = f"{self.domain}/label/hot_day.html"
        elif tid == "label_new":
            url = f"{self.domain}/label/new.html"
        else:
            # 普通分类页
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
            "limit": 30,
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
                
                # 标题（title标签，去掉前缀）
                vod_name = f"视频{vod_id}"
                title_match = re.search(r'<title>(.*?)</title>', html, re.S)
                if title_match:
                    vod_name = self._strip_tags(title_match.group(1))
                    # 去掉前缀（正在播放...）
                    vod_name = re.sub(r'^正在播放[:：]', '', vod_name)
                    vod_name = vod_name.strip()
                
                if not vod_name or vod_name == self.siteName:
                    vod_name = f"视频{vod_id}"
                
                # 封面
                pic_match = re.search(r'(?:data-original|data-src|src)="([^"]+\.(?:jpg|jpeg|png))"', html)
                vod_pic = pic_match.group(1) if pic_match else ""
                
                # 播放线路
                vod_play_from = "黄金右手"
                vod_play_url = f"第1集${m3u8_url}"
                
                detail = {
                    "vod_id": vod_id,
                    "vod_name": vod_name,
                    "vod_pic": vod_pic,
                    "vod_remarks": "黄金右手",
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
    print("黄金右手 Spider v1.1 自测（加底部导航子分类）")
    print("=" * 60)
    
    print("\n[1] homeContent:")
    home = sp.homeContent()
    print(f"  分类数: {len(home.get('class', []))}")
    for c in home.get("class", []):
        print(f"    {c['type_id']:15s}  {c['type_name']}")
    
    print("\n[2] categoryContent (id=20, page=1):")
    cat = sp.categoryContent("20", 1)
    print(f"  视频数: {len(cat.get('list', []))}")
    for v in cat.get("list", [])[:2]:
        print(f"    {v['vod_id']}: {v['vod_name'][:40]}")
    
    print("\n[3] categoryContent (id=label_hot, page=1):")
    cat2 = sp.categoryContent("label_hot", 1)
    print(f"  总排行榜视频数: {len(cat2.get('list', []))}")
    
    print("\n[4] categoryContent (id=label_new, page=1):")
    cat3 = sp.categoryContent("label_new", 1)
    print(f"  最新上传视频数: {len(cat3.get('list', []))}")
    
    if cat.get("list"):
        first_id = cat["list"][0]["vod_id"]
        print(f"\n[5] detailContent (id={first_id}):")
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
