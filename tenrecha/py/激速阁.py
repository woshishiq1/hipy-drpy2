# -*- coding: utf-8 -*-
"""
激速阁 - 四壳通用Python Spider
站点: https://eky.jsg4.work/jsg/
结构: 苹果CMSv10变种，blog-item列表，详情页硬编码m3u8
CF防护: safari17_2_ios指纹突破（标准库urllib+Safari iOS UA）
"""

import re
import json
import urllib.request
import urllib.parse
import urllib.error
import gzip
import io

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
# 注意："少女"不纳入未成年范围（风月宝穴中多指年轻成年女性）
# "学生"不纳入未成年范围（高中生/大学生可能已成年，铁律13边界说明）
JUVENILE_KEYWORDS = ['萝莉', '幼女', '童', '未成年', 'teen', 'loli', 'schoolgirl', '孩童', '稚子', '玉蕊', '豆蔻', '小学生', '初中生', '幼女']

def is_juvenile(text):
    """检查文本是否包含未成年相关关键词，包含则跳过"""
    if not text:
        return False
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in JUVENILE_KEYWORDS)

# ==================== 主Spider类 ====================
class Spider(Spider):
    # 站点配置
    baseUrl = "https://eky.jsg4.work"
    siteName = "激速阁"
    
    # 分类硬编码（铁律：禁止兜底，必须与网站实际分类一致）
    # 16个平级分类，id 21-36
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
    
    # Safari iOS UA（CF穿透）
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
    
    # ==================== HTTP请求（标准库urllib + Safari iOS UA） ====================
    def _fetch(self, url, timeout=20):
        """发送HTTP请求，自动处理gzip，Safari iOS指纹突破CF"""
        headers = {
            "User-Agent": self.UA_IOS,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Referer": self.baseUrl + "/",
        }
        req = urllib.request.Request(url, headers=headers)
        try:
            resp = urllib.request.urlopen(req, timeout=timeout)
            content = resp.read()
            # 处理gzip
            if resp.headers.get("Content-Encoding") == "gzip":
                try:
                    content = gzip.decompress(content)
                except Exception:
                    pass
            return content.decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return ""
            try:
                content = e.read()
                if e.headers.get("Content-Encoding") == "gzip":
                    content = gzip.decompress(content)
                return content.decode("utf-8", errors="replace")
            except Exception:
                return ""
        except Exception:
            return ""
    
    # ==================== 解析工具 ====================
    def _strip_tags(self, html):
        """去除HTML标签"""
        if not html:
            return ""
        return re.sub(r"<[^>]+>", "", html).strip()
    
    def _parse_list(self, html):
        """解析视频列表（blog-item结构）"""
        videos = []
        # 匹配blog-item块
        items = re.findall(r'<div class="blog-item">(.*?)</div>\s*</div>', html, re.S)
        for item in items:
            try:
                # 详情页链接
                link_match = re.search(r'<a[^>]+href="([^"]+)"', item)
                if not link_match:
                    continue
                href = link_match.group(1)
                # 提取vod_id（如 /1147866.html -> 1147866）
                vid_match = re.search(r'/(\d+)\.html', href)
                if not vid_match:
                    continue
                vod_id = vid_match.group(1)
                
                # 标题
                title_match = re.search(r'class="post-title[^"]*"[^>]*>(.*?)</', item, re.S)
                vod_name = self._strip_tags(title_match.group(1)) if title_match else ""
                
                # 未成年过滤（铁律13）
                if is_juvenile(vod_name):
                    continue
                
                # 封面
                img_match = re.search(r'<img[^>]+src="([^"]+)"', item)
                vod_pic = img_match.group(1) if img_match else ""
                
                # 备注/年份（从meta中提取）
                meta_match = re.findall(r'class="fa fa-(?:eye|comments|calendar)[^"]*"[^>]*>[^<]*</i>\s*([^<]+)', item)
                vod_remarks = ""
                if meta_match:
                    vod_remarks = meta_match[0].strip()
                
                videos.append({
                    "vod_id": vod_id,
                    "vod_name": vod_name,
                    "vod_pic": vod_pic,
                    "vod_remarks": vod_remarks,
                })
            except Exception:
                continue
        return videos
    
    def _parse_total(self, html):
        """从分页信息中提取总页数/总数"""
        # 尝试匹配分页链接中的最大页码
        pages = re.findall(r'/vodtype/\d+-(\d+)\.html', html)
        if pages:
            max_page = max(int(p) for p in pages)
            return max_page * 90, max_page  # 每页90个
        return 0, 1
    
    # ==================== 1. homeContent ====================
    def homeContent(self, filter=False):
        classes = []
        filters = {}
        
        for cat in self.CATEGORIES:
            classes.append({
                "type_id": cat["type_id"],
                "type_name": cat["type_name"],
            })
            # 每个分类的筛选项（空dict，铁律要求filters为dict）
            filters[cat["type_id"]] = {}
        
        result = {
            "class": classes,
            "filters": filters,
        }
        return result
    
    # ==================== 2. categoryContent ====================
    def categoryContent(self, tid, pg, filter=False, extend=None):
        pg = int(pg) if pg else 1
        url = f"{self.baseUrl}/vodtype/{tid}-{pg}.html"
        html = self._fetch(url)
        
        videos = self._parse_list(html)
        total, pagecount = self._parse_total(html)
        if pagecount < pg:
            pagecount = pg
        
        result = {
            "page": pg,
            "pagecount": pagecount,
            "limit": 90,
            "total": total,
            "list": videos,
        }
        return result
    
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
                url = f"{self.baseUrl}/{vod_id}.html"
                html = self._fetch(url)
                if not html or len(html) < 2000:
                    continue
                
                # 标题
                title_match = re.search(r'<title>(.*?)</title>', html, re.S)
                vod_name = self._strip_tags(title_match.group(1)) if title_match else ""
                # 清理标题：去掉"正在播放:"前缀和"-分类名"后缀
                vod_name = re.sub(r'^正在播放[:：]\s*', '', vod_name)
                vod_name = re.sub(r'[-_–—]\s*(?:激速阁|女神学生|美女直播|人妻系列|强奸乱伦|自拍偷拍|制服诱惑|巨乳系列|自慰系列|国产视频|无码视频|有码视频|中文字幕|日韩精品|欧美精品|动漫精品|三级伦理).*$', '', vod_name).strip()
                
                # 未成年过滤（铁律13）
                if is_juvenile(vod_name):
                    continue
                
                # 封面（优先从详情页的大图提取）
                vod_pic = ""
                pic_match = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', html)
                if pic_match:
                    vod_pic = pic_match.group(1)
                if not vod_pic:
                    all_imgs = re.findall(r'<img[^>]+src="(https?://[^"]+\.(?:jpg|jpeg|png|webp))"', html)
                    if all_imgs:
                        vod_pic = all_imgs[0]
                
                # 播放地址（详情页硬编码rawUrl）
                play_urls = []
                raw_urls = re.findall(r"rawUrl\s*=\s*['\"]([^'\"]+)['\"]", html)
                for i, m3u8_url in enumerate(raw_urls):
                    # 未成年过滤（检查URL中是否有未成年关键词）
                    if is_juvenile(m3u8_url):
                        continue
                    play_urls.append(f"第{i+1}集${m3u8_url}")
                
                if not play_urls:
                    # 备用：直接找m3u8地址
                    m3u8_matches = re.findall(r'https?://[^\s"\']+\.m3u8[^\s"\']*', html)
                    for i, m3u8_url in enumerate(m3u8_matches):
                        if is_juvenile(m3u8_url):
                            continue
                        play_urls.append(f"第{i+1}集${m3u8_url}")
                
                if not play_urls:
                    continue
                
                # 播放线路（单线路）
                vod_play_from = "激速阁"
                vod_play_url = "#".join(play_urls)
                
                # 详情描述
                content_match = re.search(r'class="(?:vod_content|detail-content|desc)[^"]*"[^>]*>(.*?)</', html, re.S)
                vod_content = self._strip_tags(content_match.group(1)) if content_match else ""
                
                # 年份/地区
                year_match = re.search(r'(\d{4})', vod_name)
                vod_year = year_match.group(1) if year_match else ""
                
                detail = {
                    "vod_id": vod_id,
                    "vod_name": vod_name,
                    "vod_pic": vod_pic,
                    "vod_remarks": "激速阁",
                    "vod_actor": "",
                    "vod_director": "",
                    "vod_content": vod_content,
                    "vod_year": vod_year,
                    "vod_area": "",
                    "vod_tags": "",
                    "vod_douban_score": "",
                    "vod_play_from": vod_play_from,
                    "vod_play_url": vod_play_url,
                }
                list_data.append(detail)
            except Exception:
                continue
        
        result = {"list": list_data}
        return result
    
    # ==================== 4. searchContent ====================
    def searchContent(self, key, quick=False, pg=1):
        """搜索功能（站点搜索404，返回空列表）"""
        result = {
            "page": pg,
            "pagecount": 0,
            "limit": 90,
            "total": 0,
            "list": [],
        }
        return result
    
    # ==================== 5. playerContent ====================
    def playerContent(self, flag, id, vipFlags=None):
        """播放内容解析（直连m3u8，parse=0）"""
        if not id:
            return {"parse": 0, "jx": 0, "url": "", "header": {}}
        
        # id就是m3u8地址（从detailContent的vod_play_url中提取）
        url = id
        
        # 防盗链Header
        header = {
            "User-Agent": self.UA_IOS,
            "Referer": self.baseUrl + "/",
            "Origin": self.baseUrl,
        }
        
        result = {
            "parse": 0,
            "jx": 0,
            "url": url,
            "header": header,
        }
        return result
    
    # ==================== 6. localProxy（封面代理，可选） ====================
    def localProxy(self, param):
        """本地代理（封面图代理，可选实现）"""
        if not param or "do" not in param:
            return [404, "text/plain", ""]
        
        do = param.get("do", "")
        if do == "ck":
            # 封面代理
            url = param.get("url", "")
            if url:
                try:
                    headers = {
                        "User-Agent": self.UA_IOS,
                        "Referer": self.baseUrl + "/",
                    }
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
    print("激速阁 Spider 自测")
    print("=" * 60)
    
    # 1. homeContent
    print("\n[1] homeContent:")
    home = sp.homeContent()
    print(f"  分类数: {len(home.get('class', []))}")
    print(f"  filters类型: {type(home.get('filters')).__name__}")
    for c in home.get("class", [])[:3]:
        print(f"    {c['type_id']}: {c['type_name']}")
    
    # 2. categoryContent
    print("\n[2] categoryContent (id=23, page=1):")
    cat = sp.categoryContent("23", 1)
    print(f"  视频数: {len(cat.get('list', []))}")
    print(f"  page: {cat.get('page')}, pagecount: {cat.get('pagecount')}, total: {cat.get('total')}")
    for v in cat.get("list", [])[:2]:
        print(f"    {v['vod_id']}: {v['vod_name'][:40]}")
    
    # 3. detailContent
    if cat.get("list"):
        first_id = cat["list"][0]["vod_id"]
        print(f"\n[3] detailContent (id={first_id}):")
        detail = sp.detailContent([first_id])
        if detail.get("list"):
            d = detail["list"][0]
            print(f"  标题: {d['vod_name'][:50]}")
            print(f"  封面: {d['vod_pic'][:60]}")
            print(f"  播放线路: {d['vod_play_from']}")
            play_urls = d['vod_play_url'].split("#")
            print(f"  播放集数: {len(play_urls)}")
            for pu in play_urls[:2]:
                print(f"    {pu[:80]}")
        else:
            print("  无详情数据")
    
    # 4. playerContent
    if detail.get("list"):
        first_play = detail["list"][0]["vod_play_url"].split("#")[0]
        m3u8_url = first_play.split("$", 1)[1] if "$" in first_play else first_play
        print(f"\n[4] playerContent:")
        player = sp.playerContent("激速阁", m3u8_url)
        print(f"  parse: {player.get('parse')}, jx: {player.get('jx')}")
        print(f"  url: {player.get('url', '')[:80]}")
        print(f"  header keys: {list(player.get('header', {}).keys())}")
    
    print("\n" + "=" * 60)
    print("自测完成!")
