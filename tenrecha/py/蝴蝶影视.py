# coding=utf-8

import sys
sys.path.append('..')

from base.spider import Spider
import re
import json
import html as html_lib
from urllib.parse import quote, unquote, parse_qs, urlparse

class Spider(Spider):

    def getName(self):
        return "蝴蝶影视"

    def init(self, extend=""):
        self.host = "https://6182104.xyz"
        self.tgGroup = "https://t.me/tvshare23"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': self.host + '/'
        }
        self.api_host = "https://h5.xxoo459.org"
        self.api_host_fallback = "https://h5.xxoo475.org"
        
        self.cateManual = {
            "一区": "13",
            "二区": "14",
            "三区": "40",
            "四区": "22",
            "五区": "6",
            "六区": "8",
            "七区": "9",
            "八区": "20",
            "九区": "21",
            "漫画": "7"
        }

    # ===== XOR 128 解密核心[cite: 1] =====
    def decrypt(self, text):
        if not text:
            return ""
        return ''.join([chr(128 ^ ord(ch)) for ch in text])

    def _unesc(self, s):
        try:
            return html_lib.unescape(s or "").strip()
        except Exception:
            return (s or "").strip()

    def _get_matched(self, pattern, text, default=""):
        try:
            m = re.search(pattern, text, re.DOTALL)
            if m:
                return m.group(1)
        except Exception:
            pass
        return default

    # ===== 从 URL 路径提取并解密标题[cite: 1] =====
    def extract_title_from_path(self, parsed):
        path = unquote(parsed.path)
        m = re.search(r'/html/dcdc/(.+?)\.html', path)
        if m:
            try:
                return self.decrypt(m.group(1))
            except Exception:
                return m.group(1)
        return ""

    # ===== 获取分类页 URL[cite: 1] =====
    def get_cate_url(self, tid, pg=1, wd=None):
        if wd:
            return "%s/index.php/vod/type/id/%s/wd/%s/page/%d.html" % (self.host, tid, quote(wd), pg)
        else:
            return "%s/index.php/vod/type/id/%s/page/%d.html" % (self.host, tid, pg)

    # ===== 解析视频列表页[cite: 1] =====
    def parse_list(self, html):
        videos = []
        total_pages = 1
        m = re.search(r"totalPages='(\d+)'", html)
        if m:
            total_pages = int(m.group(1))

        pattern = r'<a[^>]*href="([^"]*\/html\/dcdc\/[^"]+)"[^>]*>(.*?)</a>'
        matches = re.findall(pattern, html, re.DOTALL)

        for href, inner in matches:
            try:
                href = href.replace('&amp;', '&')
                parsed = urlparse(href)
                params = parse_qs(parsed.query)
                b_url = params.get('b', [''])[0]

                pic = b_url
                if not pic:
                    img_match = re.search(r'data-original="([^"]+)"', inner)
                    if img_match:
                        pic = img_match.group(1)

                title = ""
                km_match = re.search(r'<(?:p|span)[^>]*class="[^"]*km-script[^"]*"[^>]*>(.*?)</(?:p|span)>', inner, re.DOTALL)
                if km_match:
                    title = self.decrypt(km_match.group(1).strip())
                
                if not title:
                    title = self.extract_title_from_path(parsed)
                if not title:
                    title = "高清精彩正片"

                vod_id = href if href.startswith('http') else self.host + href
                videos.append({
                    "vod_id": vod_id,
                    "vod_name": title,
                    "vod_pic": pic if pic else "https://img.meituan.net/video/ea1bb086d18160e6465a4ade60212d6b1150.ico",
                    "vod_remarks": "高清正片"
                })
            except Exception:
                continue

        return videos, total_pages

    # ===== 首页内容与子分类名称解密渲染 =====
    def homeContent(self, filter=False):
        result = {}
        classes = []
        for k in self.cateManual:
            classes.append({"type_name": k, "type_id": self.cateManual[k]})
        result['class'] = classes
        
        filters = {}
        for tid in self.cateManual.values():
            try:
                url = self.get_cate_url(tid, 1)
                rsp = self.fetch(url, headers=self.headers)
                html = rsp.text
                sub_values = [{"n": "全部", "v": tid}]
                
                sub_matches = re.findall(r'href=["\']([^"\']*?/vod/type/id/(\d+)\.html)["\'][^>]*>([\s\S]*?)</a>', html)
                seen_sub = set()
                for sub_href, sub_tid, sub_inner in sub_matches:
                    if sub_tid not in seen_sub and sub_tid != tid:
                        seen_sub.add(sub_tid)
                        sub_name_match = re.search(r'<(?:p|span)[^>]*class="[^"]*km-script[^"]*"[^>]*>(.*?)</(?:p|span)>', sub_inner, re.DOTALL)
                        if sub_name_match:
                            sub_name = self.decrypt(sub_name_match.group(1).strip())
                        else:
                            sub_name = re.sub(r'<[^>]+>', '', sub_inner).strip()
                            sub_name = self.decrypt(sub_name) if sub_name else ("子分类 %s" % sub_tid)
                        
                        sub_values.append({"n": sub_name if sub_name else "子分类 %s" % sub_tid, "v": sub_tid})
                        
                filters[tid] = [{"key": "sub", "name": "子分类", "value": sub_values}]
            except Exception:
                filters[tid] = [{"key": "sub", "name": "子分类", "value": [{"n": "全部", "v": tid}]}]
                
        result['filters'] = filters
        try:
            url = self.get_cate_url("13", 1)
            rsp = self.fetch(url, headers=self.headers)
            videos, _ = self.parse_list(rsp.text)
            result['list'] = videos
        except Exception:
            result['list'] = []
        return result

    def homeVideoContent(self):
        try:
            url = self.get_cate_url("13", 1)
            rsp = self.fetch(url, headers=self.headers)
            videos, _ = self.parse_list(rsp.text)
            return {'list': videos}
        except Exception:
            return {'list': []}

    # ===== 分类内容 =====
    def categoryContent(self, tid, pg, filter=False, extend=""):
        result = {}
        page = int(pg) if pg else 1
        
        f = {}
        if filter and isinstance(filter, dict):
            f.update(filter)
        if extend and isinstance(extend, dict):
            f.update(extend)
            
        cur = f.get("sub") or tid
        cur = str(cur) if str(cur).isdigit() else tid

        try:
            url = self.get_cate_url(cur, page)
            rsp = self.fetch(url, headers=self.headers)
            videos, total_pages = self.parse_list(rsp.text)
            
            if not videos and page == 1:
                url_fallback = self.get_cate_url("13", 1)
                rsp_fallback = self.fetch(url_fallback, headers=self.headers)
                videos, total_pages = self.parse_list(rsp_fallback.text)

            result['list'] = videos
            result['page'] = page
            result['pagecount'] = total_pages
            result['limit'] = len(videos)
            result['total'] = total_pages * max(len(videos), 1)
        except Exception:
            try:
                url_fallback = self.get_cate_url("13", 1)
                rsp_fallback = self.fetch(url_fallback, headers=self.headers)
                videos, total_pages = self.parse_list(rsp_fallback.text)
                result['list'] = videos
            except Exception:
                result['list'] = []
            result['page'] = page
            result['pagecount'] = 1
            result['limit'] = 0
            result['total'] = 0
        return result

    # ===== 通过 m 参数 API 获取真实 m3u8 =====
    def get_m3u8_by_mk(self, mk):
        for api_host in [self.api_host, self.api_host_fallback]:
            try:
                api_url = "%s/api/v2/vod/reqplay/%s" % (api_host, mk)
                rsp = self.fetch(api_url, headers=self.headers)
                data = json.loads(rsp.text)
                if data.get('retcode') == 3:
                    vod_url = data.get('data', {}).get('httpurl_preview', '')
                else:
                    vod_url = data.get('data', {}).get('httpurl', '')
                if not vod_url:
                    httpurls = data.get('data', {}).get('httpurls', [])
                    if httpurls and isinstance(httpurls, list):
                        vod_url = httpurls[0].get('httpurl', '')
                if vod_url and vod_url.endswith('?300'):
                    vod_url = vod_url[:-4]
                if vod_url:
                    return vod_url
            except Exception:
                continue
        return ""

    # ===== 详情内容与自定义简介渲染[cite: 1] =====
    def detailContent(self, array):
        vod_id = array[0] if array else ""
        result = {}
        try:
            vod_id = vod_id.replace('&amp;', '&')
            parsed = urlparse(vod_id)
            params = parse_qs(parsed.query)
            v_url = params.get('v', [''])[0]
            m_url = params.get('m', [''])[0]
            b_url = params.get('b', [''])[0]

            if v_url:
                m3u8_url = v_url
            elif m_url:
                m3u8_url = self.get_m3u8_by_mk(m_url)
            else:
                m3u8_url = ""

            title = self.extract_title_from_path(parsed)
            if not title:
                title = "高清精彩视频"

            # 安全抓取详情页真实简介
            clean_content = ""
            try:
                target_url = vod_id if vod_id.startswith('http') else self.host + vod_id
                detail_html = self.fetch(target_url, headers=self.headers, timeout=5)
                if detail_html and detail_html.text:
                    raw_content = self._get_matched(r'简介：(.*?)</p>', detail_html.text, "")
                    clean_content = self._unesc(re.sub(r'<[^>]+>', '', raw_content)).strip()
            except Exception:
                pass

            custom_notice = "【💡 温馨提示：视频加载如遇卡顿请尝试切换线路或快进。】"
            group_info = "【🔥 官方交流群: %s】" % self.tgGroup

            if clean_content:
                vod_content = "%s\n\n%s\n\n%s" % (group_info, custom_notice, clean_content)
            else:
                vod_content = "%s\n\n%s\n\n暂无详细简介，欢迎加入TG群获取最新资源！" % (group_info, custom_notice)

            play_from = "在线播放"
            play_url = title + "$" + m3u8_url

            vod = {
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": b_url,
                "type_name": "高清专区",
                "vod_year": "2026",
                "vod_area": "内部",
                "vod_remarks": "正片",
                "vod_actor": "🦋 TG群: @tvshare23",
                "vod_director": "🦋 蝴蝶影视",
                "vod_content": vod_content,
                "vod_play_from": play_from,
                "vod_play_url": play_url
            }
            result['list'] = [vod]
        except Exception:
            result['list'] = []
        return result

    # ===== 搜索内容 =====
    def searchContent(self, key, quick, pg="1"):
        result = {}
        try:
            page = int(pg) if pg else 1
            url = self.get_cate_url("13", page, key)
            rsp = self.fetch(url, headers=self.headers)
            videos, total_pages = self.parse_list(rsp.text)
            result['list'] = videos
            result['page'] = page
            result['pagecount'] = total_pages
        except Exception:
            result['list'] = []
        return result

    # ===== 播放内容 =====
    def playerContent(self, flag, id, vipFlags):
        return {
            "parse": 0,
            "playUrl": "",
            "url": id,
            "header": {
                "User-Agent": self.headers['User-Agent'],
                "Referer": self.host + "/"
            }
        }

    def isVideoFormat(self, url):
        if re.search(r'\.(m3u8|mp4|flv|avi|mkv|rmvb|wmv)(\?|#|$)', url, re.IGNORECASE):
            return True
        return False

    def manualVideoCheck(self):
        return False

    def verifyLiveUrl(self, url):
        return url
