# -*- coding: utf-8 -*-
"""
作者：飞鱼
ppp.porn 爬虫 (XYQHiker 规则转换 Python 适配版)
适配壳子: PeekPro(羊壳) / TVBox / 影视壳 / 猫影视
"""
import sys
import re
import json
import requests
import urllib3
import time
import html
from urllib.parse import quote, urljoin, unquote

urllib3.disable_warnings()
sys.path.append('..')
from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    host = 'https://ppp.porn'
    session = requests.Session()
    _debug = True
    _categories = []

    # 广告过滤词与域名黑名单
    AD_TITLE_FILTER = ['广告', '推广', 'APP', '下载', '注册', '菠菜', '博彩', '棋牌']
    AD_DOMAIN_FILTER = ['doubleclick', 'adservice', 'adsystem', 'adnxs', 'casalemedia', 'fluxtrck']

    def _log(self, msg):
        if self._debug:
            print(f'[ppp.porn] {msg}')

    def getName(self):
        return 'PPP-Porn'

    def isVideoFormat(self, url):
        return url and ('.m3u8' in url or '.mp4' in url or '.ts' in url)

    def manualVideoCheck(self):
        return False

    def destroy(self):
        if hasattr(self, 'session'):
            try:
                self.session.close()
            except:
                pass
            self.session = None

    # ---------- 清洗文本与 HTML 实体 (解决字符乱码/转义问题) ----------
    def _clean_text(self, text):
        if not text:
            return ''
        clean = re.sub(r'<[^>]+>', '', text)
        clean = re.sub(r'&#(\d+);', lambda m: chr(int(m.group(1))), clean)
        clean = re.sub(r'&#x([0-9a-fA-F]+);', lambda m: chr(int(m.group(1), 16)), clean)
        clean = html.unescape(clean)
        clean = html.unescape(clean)
        clean = re.sub(r'\s+', ' ', clean).strip()
        return clean

    def _get_headers(self, referer=None):
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': referer or self.host + '/'
        }

    def _fetch(self, url, referer=None, retries=2):
        for attempt in range(retries):
            try:
                if attempt > 0:
                    time.sleep(1)
                r = self.session.get(url, headers=self._get_headers(referer), timeout=(10, 15), verify=False)
                r.encoding = 'utf-8'
                if r.status_code == 200:
                    return r.text
            except Exception as e:
                self._log(f'请求异常 {e} -> {url}')
                continue
        return ''

    # ---------- 初始化与分类/筛选 ----------
    def init(self, extend=''):
        self._log('正在初始化...')
        self.session = requests.Session()
        self._categories = [
            {'type_id': 'new', 'type_name': '最新'},
            {'type_id': 'hot', 'type_name': '🔥热门🔥'},
            {'type_id': 'categories/china-av', 'type_name': '系列'},
            {'type_id': 'categories/china', 'type_name': '地区'},
            {'type_id': 'categories/cosplay', 'type_name': '主题'},
            {'type_id': 'categories/office-lady', 'type_name': '衣着'}
        ]

    def _get_filters(self):
        return {
            "categories/china-av": [
                {"key": "cateId", "name": "系列", "value": [
                    {"v": "categories/china-av", "n": "中國AV"},
                    {"v": "categories/japan-producer", "n": "日本片商"},
                    {"v": "categories/amateur", "n": "素人自拍"}
                ]}
            ],
            "categories/china": [
                {"key": "cateId", "name": "地区", "value": [
                    {"v": "categories/china", "n": "中國"},
                    {"v": "categories/taiwan", "n": "台灣"},
                    {"v": "categories/japan", "n": "日本"},
                    {"v": "categories/se-asia", "n": "東南亞"},
                    {"v": "categories/korea", "n": "韓國"},
                    {"v": "categories/hongkong", "n": "香港"}
                ]}
            ],
            "categories/cosplay": [
                {"key": "cateId", "name": "主题", "value": [
                    {"v": "categories/cosplay", "n": "Cosplay"},
                    {"v": "categories/streamer", "n": "主播"},
                    {"v": "categories/first-person-pov", "n": "主觀視角"},
                    {"v": "categories/bdsm", "n": "凌辱"},
                    {"v": "categories/drama", "n": "劇情"},
                    {"v": "categories/threesome", "n": "多P"},
                    {"v": "categories/91-tanhua", "n": "探花"},
                    {"v": "categories/leaked", "n": "流出"},
                    {"v": "categories/uncensored", "n": "無碼"},
                    {"v": "categories/lesbian", "n": "百合"},
                    {"v": "categories/exhibitionists", "n": "野外露出"}
                ]}
            ],
            "categories/office-lady": [
                {"key": "cateId", "name": "衣着", "value": [
                    {"v": "categories/office-lady", "n": "OL"},
                    {"v": "categories/acg", "n": "動漫"},
                    {"v": "categories/costume", "n": "古裝"},
                    {"v": "categories/maid", "n": "女僕"},
                    {"v": "categories/student", "n": "學生"},
                    {"v": "categories/cheongsam", "n": "旗袍"},
                    {"v": "categories/kemonomimi", "n": "獸耳"},
                    {"v": "categories/yoga-pants", "n": "瑜伽褲"},
                    {"v": "categories/dolfin-shorts", "n": "真理褲"},
                    {"v": "categories/flight-attendant", "n": "空姐"},
                    {"v": "categories/pantyhose", "n": "絲襪"},
                    {"v": "categories/nurse", "n": "護士"},
                    {"v": "categories/knee-socks", "n": "過膝襪"}
                ]}
            ]
        }

    # ---------- 解析网页 HTML 卡片列表 ----------
    def _parse_item_list(self, html_str, is_home=False):
        items = []
        if not html_str:
            return items

        # 1. 截取卡片包含区域
        if is_home:
            container_match = re.search(r'class="[^"]*max-width-lg[^"]*"[^>]*>(.*?)(?=<footer|</body>|$)', html_str, re.S)
        else:
            container_match = re.search(r'class="[^"]*padding-bottom-md[^"]*"[^>]*>(.*?)(?=<footer|</body>|$)', html_str, re.S)
        
        target_html = container_match.group(1) if container_match else html_str

        # 2. 提取原始视频卡片块 (.item)
        raw_blocks = re.findall(r'<div[^>]+class="[^"]*item[^"]*"[^>]*>(.*?)(?=<div[^>]+class="[^"]*item[^"]*"|$)', target_html, re.S)

        # 3. 拆分卡片内嵌套的 end-sc 隐藏层广告
        sub_blocks = []
        for b in raw_blocks:
            if 'end-sc' in b:
                parts = re.split(r'<style>\s*\.end-sc\s*~\s*\*[^}]*</style>', b)
                sub_blocks.extend(parts)
            else:
                sub_blocks.append(b)

        # 4. 解析每个独立卡片
        for block in sub_blocks:
            link_match = re.search(r'<a[^>]+href="([^"]+)"[^>]*>', block)
            title_match = re.search(r'<h4[^>]*>(.*?)</h4>', block, re.S)

            if not link_match or not title_match:
                continue

            href = link_match.group(1).strip()
            title = self._clean_text(title_match.group(1))

            # --- 过滤规则 1：必须包含 /v/ 或为内部相对路径，排除外链广告 ---
            if not href.startswith('/v/') and not ('ppp.porn/v/' in href):
                continue

            # --- 过滤规则 2：精准提取 figcaption 时长，为 AD 时过滤 ---
            duration_match = re.search(r'class="[^"]*card-video__duration[^"]*"[^>]*>(.*?)</figcaption>', block, re.S)
            duration_text = self._clean_text(duration_match.group(1)) if duration_match else ''
            if duration_text.upper() == 'AD' or 'AD' in duration_text.upper():
                continue

            # --- 过滤规则 3：标题黑名单 ---
            if any(k in title for k in self.AD_TITLE_FILTER):
                continue

            # 封面图提取
            img_match = re.search(r'<img[^>]+data-src="([^"]*)"', block)
            if not img_match:
                img_match = re.search(r'<img[^>]+src="([^"]*)"', block)
            img = img_match.group(1) if img_match else ''
            if img and not img.startswith('http'):
                img = urljoin(self.host, img)

            # --- 准确解析副标题 (⏱️时长 👁️观看量 ❤️点赞数) ---
            remarks_parts = []

            if duration_text:
                remarks_parts.append(f"⏱️{duration_text}")

            nums_raw = re.findall(r'<span[^>]+class="num"[^>]*>(.*?)</span>', block, re.S)
            nums = [self._clean_text(n) for n in nums_raw if self._clean_text(n)]

            if len(nums) >= 2:
                remarks_parts.append(f"👁️{nums[0]}")
                remarks_parts.append(f"❤️{nums[1]}")
            elif len(nums) == 1:
                remarks_parts.append(f"👁️{nums[0]}")
            else:
                stat_match = re.search(r'(\d+(?:\.\d+)?[kmKM]?)\s*觀看', block)
                if stat_match:
                    remarks_parts.append(f"👁️{stat_match.group(1)}")

            remarks = ' '.join(remarks_parts)
            vod_id = href.lstrip('/')

            items.append({
                'vod_id': str(vod_id),
                'vod_name': str(title),
                'vod_pic': str(img),
                'vod_remarks': str(remarks)
            })

        return items

    # ---------- 首页数据 ----------
    def homeContent(self, filter=False):
        try:
            if not self._categories:
                self.init()
            html_str = self._fetch(self.host)
            items = self._parse_item_list(html_str, is_home=True)
            res = {
                'class': self._categories,
                'list': items[:20]
            }
            if filter:
                res['filters'] = self._get_filters()
            return res
        except Exception as e:
            self._log(f'homeContent 异常: {e}')
            return {'class': [], 'list': []}

    def homeVideoContent(self):
        html_str = self._fetch(self.host)
        return {'list': self._parse_item_list(html_str, is_home=True)[:20]}

    # ---------- 分类列表 ----------
    def categoryContent(self, tid, pg, filter=False, extend=None):
        try:
            page = int(pg) if pg else 1
            cate_id = tid

            if extend and isinstance(extend, dict) and 'cateId' in extend:
                cate_id = extend['cateId']

            if cate_id in ('new', 'hot'):
                url = f"{self.host}/{cate_id}/{page}/" if page > 1 else f"{self.host}/{cate_id}/"
            else:
                url = f"{self.host}/{cate_id}/{page}/"

            html_str = self._fetch(url)
            items = self._parse_item_list(html_str, is_home=False)

            total_pages = page + 1 if len(items) >= 10 else page

            return {
                'list': items,
                'page': page,
                'pagecount': total_pages,
                'limit': 20,
                'total': 999
            }
        except Exception as e:
            self._log(f'categoryContent 异常: {e}')
            return {'list': [], 'page': int(pg) if pg else 1, 'pagecount': 1}

    # ---------- 播放直链提取算法 ----------
    def _parse_real_video_url(self, html_str, page_url):
        if not html_str:
            return ''

        stream_match = re.search(r"var\s+stream\s*=\s*['\"]([^'\"]+\.m3u8[^'\"]*)['\"]", html_str)
        if stream_match:
            real_url = stream_match.group(1).replace('\\/', '/')
            return urljoin(page_url, real_url)

        source_match = re.findall(r'<(?:source|video)[^>]+src=["\']([^"\']+)["\']', html_str, re.I)
        for src in source_match:
            src = unquote(src).replace('\\/', '/')
            if '.m3u8' in src or '.mp4' in src:
                return urljoin(page_url, src)

        js_urls = re.findall(r'["\'](https?://[^\s"\'<>]+\.(?:m3u8|mp4)[^\s"\' architectural]*)["\']', html_str)
        for u in js_urls:
            u = u.replace('\\/', '/')
            if not any(ad in u.lower() for ad in self.AD_DOMAIN_FILTER):
                return u

        iframe_match = re.findall(r'<iframe[^>]+src=["\']([^"\']+)["\']', html_str, re.I)
        for iframe_src in iframe_match:
            iframe_url = urljoin(page_url, iframe_src)
            if '.m3u8' in iframe_url or '.mp4' in iframe_url:
                return iframe_url
            
            iframe_html = self._fetch(iframe_url, referer=page_url)
            if iframe_html:
                sub_url = self._parse_real_video_url(iframe_html, iframe_url)
                if sub_url:
                    return sub_url

        return ''

    # ---------- 【重构强化版】详情页数据解析 ----------
    def detailContent(self, ids):
        try:
            vod_id = ids[0] if isinstance(ids, list) else ids
            clean_id = vod_id.lstrip('/')
            url = f"{self.host}/{clean_id}" if not clean_id.startswith('http') else clean_id

            html_str = self._fetch(url)

            if not html_str:
                return {'list': [{'vod_id': str(vod_id), 'vod_name': '加载失败', 'vod_play_from': '手动嗅探', 'vod_play_url': f'正片${url}'}]}

            # 1. 解析标题
            title_m = re.search(r'<h1[^>]*>(.*?)</h1>', html_str, re.S)
            if title_m:
                title = self._clean_text(title_m.group(1))
            else:
                meta_title = re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"', html_str)
                title = self._clean_text(meta_title.group(1)) if meta_title else '视频详情'

            # 2. 解析封面图
            cover_m = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', html_str)
            cover = cover_m.group(1) if cover_m else ''

            # 3. 解析【地区】(从 /categories/taiwan/ 或 video:tag 匹配)
            area_list = ['台灣', '中國', '日本', '東南亞', '韓國', '香港']
            vod_area = ""
            for area in area_list:
                if f'content="{area}"' in html_str or f'>{area}</a>' in html_str:
                    vod_area = area
                    break

            # 4. 解析【演员/模特】(从 /s/模特名/ 链接提取，如“斑斑”)
            actor_m = re.findall(r'<a[^>]+href=["\']/s/([^/"]+)/?["\'][^>]*>(.*?)</a>', html_str, re.S)
            actors = [self._clean_text(a[1]) for a in actor_m if self._clean_text(a[1])]
            vod_actor = " / ".join(list(set(actors))) if actors else "未知"

            # 5. 解析【类型/标签】
            tags = re.findall(r'<a[^>]+href=["\']/categories/[^"]+["\'][^>]*>(.*?)</a>', html_str, re.S)
            clean_tags = [self._clean_text(t) for t in tags if self._clean_text(t) and self._clean_text(t) != vod_area]
            vod_type = " / ".join(list(set(clean_tags))) if clean_tags else "未知"

            # 6. 解析发布时间/年份
            time_m = re.search(r'(\d{4}-\d{2}-\d{2}|\d+\s*(?:天|小时|分钟|月|年)前)', html_str)
            pub_year = time_m.group(1) if time_m else ""

            # 7. 解析剧情简介 (如果网站只有标语则友好标注)
            desc_m = re.search(r'<meta[^>]+name="description"[^>]+content="([^"]+)"', html_str)
            meta_desc = self._clean_text(desc_m.group(1)) if desc_m else ""
            
            # 拼接更丰富的详情描述
            vod_content = f"【简介】{meta_desc}\n【模特】{vod_actor}\n【地区】{vod_area if vod_area else '未知'}\n【标签】{vod_type}"

            # 8. 获取实际播放直链
            real_play_url = self._parse_real_video_url(html_str, url)

            if real_play_url:
                vod_play_from = "📽️直链播放📺"
                vod_play_url = f"正片${real_play_url}"
            else:
                vod_play_from = "📽️官方嗅探📺"
                vod_play_url = f"正片${url}"

            return {'list': [{
                'vod_id': str(vod_id),
                'vod_name': str(title),
                'vod_pic': str(cover),
                'vod_type_name': str(vod_type),         # 类型 (如: 素人自拍 / 劇情 / OL / 絲襪)
                'vod_area': str(vod_area),               # 地区 (如: 台灣)
                'vod_actor': str(vod_actor),             # 演员/模特 (如: 斑斑)
                'vod_director': '暂无',                  # 网页源码未提供导演字段
                'vod_year': str(pub_year),               # 发布年份/相对时间
                'vod_remarks': f"模特:{vod_actor} | 地区:{vod_area}", # 壳子列表展现的标记
                'vod_content': str(vod_content),         # 完整的剧情与元数据简介
                'vod_play_from': vod_play_from,
                'vod_play_url': vod_play_url
            }]}
        except Exception as e:
            self._log(f'detailContent 异常: {e}')
            return {'list': []}

    # ---------- 播放 Header 支持 ----------
    def playerContent(self, flag, id, vipFlags=None):
        if id.startswith('http') and ('.m3u8' in id or '.mp4' in id):
            return {
                'parse': 0,
                'url': id,
                'header': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Referer': self.host + '/'
                }
            }

        return {
            'parse': 1,
            'url': id,
            'header': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': self.host + '/'
            }
        }

    # ---------- 搜索 ----------
    def searchContent(self, key, quick, pg='1'):
        try:
            page = int(pg) if pg else 1
            url = f"{self.host}/search/{quote(key)}/"
            if page > 1:
                url = f"{self.host}/search/{quote(key)}/{page}/"

            html_str = self._fetch(url)
            items = self._parse_item_list(html_str, is_home=False)

            return {
                'list': items,
                'page': page,
                'pagecount': page + 1 if len(items) >= 10 else page
            }
        except Exception as e:
            self._log(f'searchContent 异常: {e}')
            return {'list': [], 'page': 1, 'pagecount': 1}
