# coding=utf-8
# !/usr/bin/python

import sys
import requests
import re
import json
import html  # 【新增】引入html库处理 &quot; 和 &#x... 这种乱码
from bs4 import BeautifulSoup

sys.path.append('..')
try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider: pass

class Spider(BaseSpider):
    # ================= 配置常量 =================
    SITE_URL = "http://m.xiaobanzhu.com"
    DEFAULT_COVER = "https://imgs-qn.51miz.com/preview/element/00/01/03/32/E-1033200-8BF22C08.jpg"
    
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 7.1.1; Mi Note 3 Build/NMF26X; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/61.0.3163.98 Mobile Safari/537.36",
        "Referer": SITE_URL
    }

    def getName(self): return "第一版主"
    def init(self, extend=""): pass
    def isVideoFormat(self, url): return False
    def manualVideoCheck(self): pass

    # ================= 工具方法 =================

    def _get_full_url(self, url):
        if not url: return ""
        if url.startswith("http"): return url
        if not url.startswith("/"): url = "/" + url
        return self.SITE_URL + url

    def _get_req(self, url):
        try:
            resp = requests.get(self._get_full_url(url), headers=self.HEADERS, timeout=10)
            resp.encoding = 'gbk'
            return resp.text
        except: return ""

    def _post_req(self, url, data):
        try:
            resp = requests.post(self._get_full_url(url), data=data, headers=self.HEADERS, timeout=10)
            resp.encoding = 'gbk'
            return resp.text
        except: return ""

    def _get_cover(self, book_id):
        return self.DEFAULT_COVER

    # ================= 业务逻辑 =================

    def homeContent(self, filter):
        cats = [
            ("日点击榜", "/top/dayvisit_{pg}/"), ("周点击榜", "/top/weekvisit_{pg}/"),
            ("月点击榜", "/top/monthvisit_{pg}/"), ("总点击榜", "/top/allvisit_{pg}/"),
            ("总收藏榜", "/top/goodnum_{pg}/"), ("字数排行", "/top/size_{pg}/"),
            ("总推荐榜", "/top/allvote_{pg}/"), ("最新入库", "/top/postdate_{pg}/"),
            ("最近更新", "/top/lastupdate_{pg}/"), ("玄幻小说", "/sort/1_{pg}/"),
            ("修真小说", "/sort/2_{pg}/"), ("都市小说", "/sort/3_{pg}/"),
            ("穿越小说", "/sort/4_{pg}/"), ("藏经阁", "/sort/5_{pg}/"),
            ("科幻小说", "/sort/6_{pg}/"), ("其他小说", "/sort/7_{pg}/")
        ]
        return {'class': [{"type_name": c[0], "type_id": c[1]} for c in cats], 'filters': {}}

    def homeVideoContent(self):
        return {'list': []}

    def categoryContent(self, tid, pg, filter, extend):
        html_txt = self._get_req(tid.format(pg=pg))
        soup = BeautifulSoup(html_txt, 'html.parser')
        videos = []
        
        for item in soup.select('.line'):
            try:
                links = item.select('a')
                if len(links) < 2: continue
                
                b_url = links[1]['href']
                b_name = links[1].get_text().strip()
                author = links[2].get_text().strip() if len(links) > 2 else ""
                cover = self.DEFAULT_COVER
                
                real_id = f"{b_url}@@{b_name}@@{cover}@@{author}"
                
                videos.append({
                    "vod_id": real_id,
                    "vod_name": b_name,
                    "vod_pic": cover,
                    "vod_remarks": author
                })
            except: pass
        return {'list': videos, 'page': pg, 'pagecount': 999, 'limit': 20, 'total': 9999}

    def searchContent(self, key, quick, pg="1"):
        try: s_key = key.encode('gbk')
        except: s_key = key.encode('gbk', errors='ignore')
        
        html_txt = self._post_req("/s.php", {"type": "articlename", "s": s_key, "submit": ""})
        soup = BeautifulSoup(html_txt, 'html.parser')
        videos = []
        
        for item in soup.select('.line'):
            try:
                links = item.select('a')
                if len(links) < 2: continue
                
                b_url = links[1]['href']
                b_name = links[1].get_text().strip()
                author = links[2].get_text().strip() if len(links) > 2 else ""
                cover = self.DEFAULT_COVER
                
                real_id = f"{b_url}@@{b_name}@@{cover}@@{author}"
                
                videos.append({
                    "vod_id": real_id,
                    "vod_name": b_name,
                    "vod_pic": cover,
                    "vod_remarks": author
                })
            except: pass
        return {'list': videos, 'page': 1}

    def detailContent(self, ids):
        raw_id = ids[0]
        url, name, pic, actor = "", "", "", ""
        
        if "@@" in raw_id:
            parts = raw_id.split("@@")
            url = parts[0]
            name = parts[1] if len(parts) > 1 else ""
            pic = parts[2] if len(parts) > 2 else ""
            actor = parts[3] if len(parts) > 3 else ""
        else:
            url = raw_id
            pic = self.DEFAULT_COVER

        html_txt = self._get_req(url)
        soup = BeautifulSoup(html_txt, 'html.parser')
        
        vod = {
            "vod_id": raw_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_actor": actor,
            "type_name": "",
            "vod_content": "暂无简介",
            "vod_play_from": "第一版主"
        }
        
        try:
            info_div = soup.select_one('.block_txt2')
            if info_div:
                t = info_div.select_one('h2 a')
                if t: vod["vod_name"] = t.get_text().strip()
                
                for p in info_div.select('p'):
                    txt = p.get_text().strip()
                    if "类别" in txt: vod["type_name"] = txt.split("：")[-1].strip()
                    if "状态" in txt: vod["vod_remarks"] = txt.split("：")[-1].strip()
            
            intro = soup.select_one('.intro_info')
            if intro: vod["vod_content"] = intro.get_text().replace("内容简介：", "").strip()
            
        except: pass

        chapter_list = []
        toc_url = ""
        for a in soup.select('a'):
            if "查看目录" in a.get_text():
                toc_url = a['href']
                break
        
        curr_url = self._get_full_url(toc_url) if toc_url else self._get_full_url(url)
        processed = set()
        
        for _ in range(20):
            if not curr_url or curr_url in processed: break
            processed.add(curr_url)
            
            t_html = self._get_req(curr_url)
            t_soup = BeautifulSoup(t_html, 'html.parser')
            
            for c in t_soup.select('.chapter li a, ul li a'):
                href = c.get('href')
                if not href or "javascript" in href or href == "#": continue
                full_c_url = self._get_full_url(href)
                chapter_list.append(f"{c.get_text().strip()}${full_c_url}")
            
            next_url = None
            for a in t_soup.select('a'):
                if "下一页" in a.get_text():
                    nh = a.get('href')
                    if nh and not nh.startswith('javascript'):
                        next_url = self._get_full_url(nh)
                    break
            
            if next_url and next_url != curr_url: curr_url = next_url
            else: break

        vod['vod_play_url'] = "#".join(chapter_list)
        return {"list": [vod]}

    def playerContent(self, flag, id, vipFlags):
        try:
            content_parts = []
            cur_url = id
            title = ""
            
            for i in range(15):
                if not cur_url: break
                html_txt = self._get_req(cur_url)
                soup = BeautifulSoup(html_txt, 'html.parser')
                
                if i == 0:
                    h = soup.select_one('h1, h2, .title')
                    if h: title = h.get_text().strip()
                
                div = soup.select_one('#nr1')
                if div:
                    # 移除显性的HTML标签
                    [s.decompose() for s in div(["script", "style", "a", "div"])]
                    
                    # 获取文本
                    txt = div.get_text("\n", strip=True)
                    
                    # === 修复步骤 1：处理HTML实体编码（&quot; 和 &#x...）===
                    # 执行两次，因为有时候会出现 &amp;#x... 这种双重编码
                    txt = html.unescape(txt)
                    txt = html.unescape(txt)
                    
                    # === 修复步骤 2：正则清理垃圾内容 ===
                    
                    # 清理 "Ref=..." 这种残留代码
                    txt = re.sub(r'Ref="[^"]+".*?com', '', txt, flags=re.IGNORECASE)
                    
                    # 清理 "最新找回4F..." 这种解码后的广告
                    # 只要行内包含 "最新找回" 或 "4F4F4F" 就整行删除
                    txt = re.sub(r'.*最新找回.*', '', txt)
                    txt = re.sub(r'.*4F4F4F.*', '', txt)
                    
                    # 清理原有的分页标记和提示
                    txt = re.sub(r'(本章未完.*|请点击下一页.*)', '', txt)
                    txt = re.sub(r'-->>\(第\d+/\d+页\)[（\(]?', '', txt)
                    
                    content_parts.append(txt)
                
                next_u = None
                for a in soup.select('a'):
                    if "下一页" in a.get_text():
                        href = a.get('href')
                        if href and "_" in href and not href.startswith("javascript"):
                             next_u = self._get_full_url(href)
                        break
                
                if next_u and next_u != cur_url: cur_url = next_u
                else: break

            result_data = {
                'title': title or '章节正文',
                'content': '\n'.join(content_parts)
            }
            json_str = json.dumps(result_data, ensure_ascii=False)

            return {
                "parse": 0,
                "playUrl": "",
                "url": f"novel://{json_str}",
                "header": ""
            }
        except Exception as e:
            err_data = json.dumps({'title': '错误', 'content': str(e)}, ensure_ascii=False)
            return {"parse": 0, "playUrl": "", "url": f"novel://{err_data}", "header": ""}
