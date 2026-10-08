#!/usr/bin/python
# -*- coding: utf-8 -*-
import sys, re, json, base64, urllib.request, urllib.parse

class Spider:
    def __init__(self):
        pass

    def getName(self):
        return "18CM视频站"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.host = "https://186416.xyz"
        self.ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        self.headers = {
            'User-Agent': self.ua,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': self.host,
        }
        self.limit = 24

    def _ensure_init(self):
        if not hasattr(self, 'host'):
            self.init()

    def _fetch(self, url):
        self._ensure_init()
        try:
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.read().decode('utf-8', errors='ignore')
        except Exception as e:
            return None

    def _parse_video_list(self, html, limit=None):
        """
        只提取主内容区域的视频列表，排除推荐区域
        """
        items = []
        if not html:
            return items
        
        # 截取主内容区域：从 "分类：xxx" 之后到分页导航之前
        # 找到 "分类：" 标记，从此处开始提取
        main_start = html.find('分类：')
        if main_start == -1:
            main_start = 0
        
        # 找到 "最新發佈影片" 或 "标签" 或 "熱門推薦"，作为结束标记
        end_markers = ['最新發佈影片', '标签', '熱門推薦', 'Join 18CM']
        main_end = len(html)
        for marker in end_markers:
            pos = html.find(marker, main_start)
            if pos != -1 and pos < main_end:
                main_end = pos
        
        main_html = html[main_start:main_end]
        
        # 匹配 article.post 块
        pattern = r'<article[^>]*class="[^"]*post[^"]*"[^>]*>(.*?)</article>'
        blocks = re.findall(pattern, main_html, re.DOTALL)
        
        for block in blocks:
            try:
                title = ""
                m = re.search(r'<a[^>]*title="([^"]*)"', block)
                if m:
                    title = m.group(1)
                if not title:
                    m = re.search(r'<a[^>]*>([^<]*)</a>', block)
                    if m:
                        title = m.group(1).strip()
                if not title:
                    continue
                title = re.sub(r'[-|_\s]*(18CM|18cm|免费|高清|在线|观看|完整版|无码).*$', '', title, flags=re.I).strip()
                
                link = ""
                m = re.search(r'<a[^>]*href="([^"]*)"', block)
                if m:
                    link = m.group(1)
                    if not link.startswith('http'):
                        link = urllib.parse.urljoin(self.host, link)
                
                pic = ""
                m = re.search(r'<img[^>]*(?:data-src|src)="([^"]*)"', block)
                if m:
                    pic = m.group(1)
                    if not pic.startswith('http'):
                        pic = urllib.parse.urljoin(self.host, pic)
                
                remarks = ""
                m = re.search(r'<span[^>]*class="[^"]*views[^"]*"[^>]*>([^<]*)</span>', block)
                if m:
                    remarks = m.group(1).strip()
                
                if link and title:
                    vod_id_match = re.search(r'/(\d+)/?$', link)
                    if vod_id_match:
                        vod_id = vod_id_match.group(1)
                    else:
                        vod_id = link.split('/')[-1] or link
                    
                    items.append({
                        "vod_id": vod_id,
                        "vod_name": title,
                        "vod_pic": pic,
                        "vod_remarks": remarks or ""
                    })
                    if limit and len(items) >= limit:
                        break
            except:
                continue
        return items

    def _parse_total_pages(self, html):
        max_page = 1
        if not html:
            return max_page
        nums = re.findall(r'<a[^>]*>\s*(\d+)\s*</a>', html)
        for n in nums:
            if n.isdigit() and int(n) > max_page:
                max_page = int(n)
        m = re.search(r'共\s*(\d+)\s*页', html)
        if m:
            max_page = int(m.group(1))
        return max_page if max_page >= 1 else 1

    def homeContent(self, filter):
        self._ensure_init()
        result = {
            'class': [
                
                {"type_name": "国产", "type_id": "%e5%9c%8b%e7%94%a2av/"},
                {"type_name": "网红", "type_id": "%e9%a1%94%e5%80%bc%e7%b6%b2%e7%b4%85/"},
                {"type_name": "探花", "type_id": "%e6%8e%a2%e8%8a%b1%e7%b4%84%e7%82%ae/"},
                {"type_name": "日韩", "type_id": "%e6%97%a5%e9%9f%93%e8%a6%96%e9%a0%bb/"},
                {"type_name": "中字", "type_id": "%e4%b8%ad%e6%96%87%e5%ad%97%e5%b9%95/"},
                {"type_name": "主播", "type_id": "%e4%b8%bb%e6%92%ad%e7%9b%b4%e6%92%ad/"},
                {"type_name": "FC2", "type_id": "fc2/"},
                {"type_name": "动漫", "type_id": "%e5%8b%95%e6%bc%ab/"},
                {"type_name": "嫩妹", "type_id": "%e5%ab%a9%e5%a6%b9/"},
                {"type_name": "欧美", "type_id": "%e6%ad%90%e7%be%8e/"},
            ]
        }
        html = self._fetch(self.host)
        if html:
            result['list'] = self._parse_video_list(html, self.limit)
        else:
            result['list'] = []
        return result

    def homeVideoContent(self):
        return self.homeContent(False)

    def categoryContent(self, tid, pg, filter, extend):
        self._ensure_init()
        pg = int(pg) if pg else 1
        if tid:
            if '%' not in tid:
                tid = urllib.parse.quote(tid)
            clean_tid = tid.rstrip('/')
            if pg == 1:
                url = urllib.parse.urljoin(self.host, "/%s/" % clean_tid)
            else:
                url = urllib.parse.urljoin(self.host, "/%s/page/%s/" % (clean_tid, pg))
        else:
            if pg == 1:
                url = urllib.parse.urljoin(self.host, "/")
            else:
                url = urllib.parse.urljoin(self.host, "/page/%s/" % pg)
        
        html = self._fetch(url)
        if html:
            v_list = self._parse_video_list(html, self.limit)
            total_pages = self._parse_total_pages(html)
            return {
                "list": v_list,
                "page": pg,
                "pagecount": total_pages,
                "limit": len(v_list),
                "total": 0
            }
        return {"list": [], "page": pg, "pagecount": 1, "limit": 0, "total": 0}

    def searchContent(self, key, quick, pg=1):
        self._ensure_init()
        search_url = urllib.parse.urljoin(self.host, "/?s=%s" % urllib.parse.quote(key))
        html = self._fetch(search_url)
        if html:
            return {"list": self._parse_video_list(html, self.limit)}
        return {"list": []}

    def detailContent(self, ids):
        self._ensure_init()
        if not ids:
            return {"list": []}
        vod_id = ids[0]
        if vod_id.isdigit():
            url = urllib.parse.urljoin(self.host, "/?p=%s" % vod_id)
        elif vod_id.startswith('http'):
            url = vod_id
        else:
            url = urllib.parse.urljoin(self.host, "/%s/" % vod_id)
        html = self._fetch(url)
        if not html:
            return {"list": []}
        
        vod_name = "未知标题"
        m = re.search(r'<h1[^>]*class="entry-title"[^>]*>([^<]*)</h1>', html)
        if m:
            vod_name = m.group(1).strip()
        if not vod_name or vod_name == "未知标题":
            m = re.search(r'<title>([^<]*)</title>', html)
            if m:
                vod_name = m.group(1).strip()
                vod_name = re.sub(r'[-–]18CM.*$', '', vod_name).strip()
        
        vod_pic = ""
        m = re.search(r'<img[^>]*class="[^"]*post-thumbnail[^"]*"[^>]*(?:data-src|src)="([^"]*)"', html)
        if not m:
            m = re.search(r'<img[^>]*(?:data-src|src)="([^"]*)"[^>]*class="[^"]*wp-post-image[^"]*"', html)
        if m:
            vod_pic = m.group(1)
            if not vod_pic.startswith('http'):
                vod_pic = urllib.parse.urljoin(self.host, vod_pic)
        
        vod_content = ""
        m = re.search(r'<div[^>]*class="entry-content"[^>]*>(.*?)</div>', html, re.DOTALL)
        if m:
            vod_content = re.sub(r'<[^>]+>', ' ', m.group(1)).strip()
            vod_content = re.sub(r'\s+', ' ', vod_content)[:200]
        
        play_url = ""
        m = re.search(r'<iframe[^>]*src="([^"]*)"', html)
        if m:
            iframe_src = m.group(1)
            q_m = re.search(r'q=([^&]+)', iframe_src)
            if q_m:
                try:
                    q_value = q_m.group(1)
                    decoded = base64.b64decode(q_value).decode('utf-8')
                    video_html = urllib.parse.unquote(decoded)
                    src_m = re.search(r'src="([^"]+)"', video_html)
                    if src_m:
                        play_url = src_m.group(1)
                except:
                    pass
            if not play_url and iframe_src.startswith('http'):
                play_url = iframe_src
        
        tags = re.findall(r'<a[^>]*rel="tag"[^>]*>([^<]*)</a>', html)
        vod_actor = ','.join(tags[:5]) if tags else ""
        
        vod_list = [{
            "vod_id": vod_id,
            "vod_name": vod_name,
            "vod_pic": vod_pic,
            "vod_content": vod_content,
            "vod_actor": vod_actor,
            "vod_play_from": "18CM",
            "vod_play_url": "正片$%s" % play_url if play_url else "正片$"
        }]
        return {"list": vod_list}

    def playerContent(self, flag, id, vipFlags):
        self._ensure_init()
        if id.startswith('http'):
            return {"url": id}
        return {"url": urllib.parse.urljoin(self.host, id)}