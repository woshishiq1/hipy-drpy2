# -*- coding: utf-8 -*-
"""
中神通 - 四壳通用Python Spider
站点: https://yhm.zst2.wiki/zst/
结构: 苹果CMSv10，stui-vodlist列表，播放页player_data含m3u8
CF防护: safari17_2_ios指纹突破（标准库urllib+Safari UA）
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
# 注意：少女/学生不纳入未成年范围（风月宝穴中多指年轻成年女性）
JUVENILE_KEYWORDS = ['萝莉', '幼女', '童', '未成年', 'teen', 'loli', 'schoolgirl', '孩童', '稚子', '玉蕊', '豆蔻', '小学生', '初中生']

def is_juvenile(text):
    if not text:
        return False
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in JUVENILE_KEYWORDS)

# ==================== 主Spider类 ====================
class Spider(Spider):
    baseUrl = "https://yhm.zst2.wiki"
    siteName = "中神通"
    
    # 分类硬编码（13个，id 20-32）
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
    
    UA_IOS = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1"
    
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
            "User-Agent": self.UA_IOS,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Connection": "keep-alive",
            "Referer": self.baseUrl + "/",
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
    
    # ==================== 解析列表 ====================
    def _parse_list(self, html):
        videos = []
        # stui-vodlist__item结构
        items = re.findall(r'<li[^>]*class="[^"]*stui-vodlist__item[^"]*"[^>]*>(.*?)</li>', html, re.S)
        if not items:
            items = re.findall(r'<div[^>]*class="[^"]*stui-vodlist__item[^"]*"[^>]*>(.*?)</div>\s*</div>', html, re.S)
        
        for item in items:
            try:
                # 播放页链接（含vod_id）
                link_match = re.search(r'href="([^"]*vod/play/id/(\d+)[^"]*)"', item)
                if not link_match:
                    link_match = re.search(r'href="([^"]*vod/detail/id/(\d+)[^"]*)"', item)
                if not link_match:
                    continue
                href = link_match.group(1)
                vod_id = link_match.group(2)
                
                # 标题
                title_match = re.search(r'class="stui-vodlist__title"[^>]*>(.*?)</', item, re.S)
                if not title_match:
                    title_match = re.search(r'<a[^>]+title="([^"]+)"', item)
                    vod_name = title_match.group(1) if title_match else ""
                else:
                    vod_name = self._strip_tags(title_match.group(1))
                
                if is_juvenile(vod_name):
                    continue
                
                # 封面（匹配任意标签的data-original或src，含懒加载a标签）
                img_match = re.search(r'(?:data-original|src)="(https?://[^"]+)"', item)
                vod_pic = img_match.group(1) if img_match else ""
                
                # 备注
                remarks_match = re.search(r'class="stui-vodlist__subtitle[^"]*"[^>]*>(.*?)</', item, re.S)
                vod_remarks = self._strip_tags(remarks_match.group(1)) if remarks_match else ""
                
                videos.append({
                    "vod_id": vod_id,
                    "vod_name": vod_name,
                    "vod_pic": vod_pic,
                    "vod_remarks": vod_remarks,
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
        url = f"{self.baseUrl}/cn/home/web/index.php/vod/type/id/{tid}.html"
        if pg > 1:
            url = f"{self.baseUrl}/cn/home/web/index.php/vod/type/id/{tid}/page/{pg}.html"
        
        html = self._fetch(url)
        videos = self._parse_list(html)
        
        # 分页信息
        pagecount = pg
        total = len(videos)
        pages = re.findall(r'/vod/type/id/\d+/page/(\d+)\.html', html)
        if pages:
            pagecount = max(int(p) for p in pages)
            total = pagecount * 36
        
        return {
            "page": pg,
            "pagecount": pagecount,
            "limit": 36,
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
                # 访问播放页获取m3u8
                play_url = f"{self.baseUrl}/cn/home/web/index.php/vod/play/id/{vod_id}/sid/1/nid/1.html"
                html = self._fetch(play_url)
                if not html or len(html) < 2000:
                    continue
                
                # 从player_data提取m3u8
                m3u8_url = ""
                player_match = re.search(r'var\s+player_data\s*=\s*({.*?})', html, re.S)
                if player_match:
                    try:
                        pd = json.loads(player_match.group(1))
                        m3u8_url = pd.get("url", "")
                    except Exception:
                        pass
                
                if not m3u8_url:
                    # 备用：直接找m3u8
                    m3u8_matches = re.findall(r'https?://[^\s"\\]+\.m3u8[^\s"\\]*', html)
                    if m3u8_matches:
                        m3u8_url = m3u8_matches[0].replace("\\/", "/")
                
                if not m3u8_url:
                    continue
                
                if is_juvenile(m3u8_url):
                    continue
                
                # 标题（优先从h2提取，其次title）
                vod_name = ""
                h2_matches = re.findall(r'<h2[^>]*>(.*?)</h2>', html, re.S)
                for h2 in h2_matches:
                    text = self._strip_tags(h2)
                    if text and "播放器" not in text and "排行榜" not in text and len(text) > 2:
                        vod_name = text
                        break
                if not vod_name:
                    title_match = re.search(r'<title>(.*?)</title>', html, re.S)
                    vod_name = self._strip_tags(title_match.group(1)) if title_match else f"视频{vod_id}"
                    vod_name = re.sub(r'[-_–—]\s*中神通.*$', '', vod_name).strip()
                    vod_name = re.sub(r'^在线播放[-_：:\s]*', '', vod_name).strip()
                
                if is_juvenile(vod_name):
                    continue
                
                # 封面
                pic_match = re.search(r'<img[^>]+(?:data-original|src)="([^"]+)"', html)
                vod_pic = pic_match.group(1) if pic_match else ""
                
                # 播放线路
                vod_play_from = "中神通"
                vod_play_url = f"第1集${m3u8_url}"
                
                detail = {
                    "vod_id": vod_id,
                    "vod_name": vod_name,
                    "vod_pic": vod_pic,
                    "vod_remarks": "中神通",
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
            "limit": 36,
            "total": 0,
            "list": [],
        }
    
    # ==================== 5. playerContent ====================
    def playerContent(self, flag, id, vipFlags=None):
        if not id:
            return {"parse": 0, "jx": 0, "url": "", "header": {}}
        
        url = id
        # m3u8在第三方域名(iuewgnbvk.com)，只需UA，无需源站Referer/Origin
        header = {
            "User-Agent": self.UA_IOS,
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
                    headers = {"User-Agent": self.UA_IOS, "Referer": self.baseUrl + "/"}
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
    print("中神通 Spider 自测")
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
