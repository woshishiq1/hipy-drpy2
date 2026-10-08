#coding=utf-8
import sys
sys.path.append('..')
from base.spider import Spider
import json
import requests
import re
import urllib.parse

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except:
    HAS_BS4 = False

class Spider(Spider):
    def __init__(self):
        self.siteUrl = "https://weishitv.xyz"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Referer": "https://weishitv.xyz/"
        }

    def getName(self):
        return "威视TV"

    def init(self, extend=""):
        if extend:
            self.siteUrl = extend.rstrip('/')
        pass

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def _getHtml(self, url):
        try:
            rsp = requests.get(url, headers=self.headers, timeout=10, verify=False)
            rsp.encoding = 'utf-8'
            return rsp.text
        except Exception as e:
            print(f"[威视TV] request error: {e}")
            return ""

    def _parseList(self, html):
        videos = []
        if HAS_BS4:
            root = BeautifulSoup(html, 'html.parser')
            boxes = root.select('.public-list-box')
            for box in boxes:
                try:
                    a_tag = box.select_one('a.public-list-exp')
                    if not a_tag:
                        continue
                    href = a_tag.get('href', '')
                    m = re.search(r'/id/(\d+)', href)
                    if not m:
                        continue
                    vid = m.group(1)
                    title = a_tag.get('title', '')
                    img = box.select_one('img.gen-movie-img')
                    pic = ""
                    if img:
                        pic = img.get('data-src') or img.get('src') or ''
                        if 'base64' in pic:
                            pic = img.get('data-src') or ''
                    remark = ""
                    remark_tag = box.select_one('.public-list-prb')
                    if remark_tag:
                        remark = remark_tag.get_text(strip=True)
                    score_tag = box.select_one('.public-prt')
                    if score_tag:
                        score = score_tag.get_text(strip=True)
                        if score and remark:
                            remark = f"{score} | {remark}"
                        elif score:
                            remark = score
                    videos.append({
                        "vod_id": vid,
                        "vod_name": title,
                        "vod_pic": pic,
                        "vod_remarks": remark
                    })
                except:
                    continue
        else:
            # 正则降级方案
            items = re.findall(r'<a[^>]*class="public-list-exp"[^>]*href="([^"]*)/id/(\d+)\.html"[^>]*title="([^"]*)"[^>]*>.*?<img[^>]*class="[^"]*gen-movie-img[^"]*"[^>]*(?:data-src|src)="([^"]*)"[^>]*>.*?(?:<span[^>]*class="[^"]*public-prt[^"]*"[^>]*>([^<]*)</span>)?.*?(?:<span[^>]*class="[^"]*public-list-prb[^"]*"[^>]*>([^<]*)</span>)?', html, re.S)
            for item in items:
                href_pre, vid, title, pic, score, remark = item
                remark = remark.strip()
                score = score.strip()
                if score and remark:
                    remark = f"{score} | {remark}"
                elif score:
                    remark = score
                videos.append({
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": remark
                })
        return videos

    def homeContent(self, filter):
        result = {}
        classes = [
            {"type_id": "1", "type_name": "电影"},
            {"type_id": "2", "type_name": "剧集"},
            {"type_id": "3", "type_name": "综艺"},
            {"type_id": "4", "type_name": "动漫"}
        ]
        result['class'] = classes

        videos = []
        html = self._getHtml(self.siteUrl)
        if html:
            if HAS_BS4:
                root = BeautifulSoup(html, 'html.parser')
                # 轮播图
                slides = root.select('.slid-e-list-box')
                seen = set()
                for slide in slides:
                    try:
                        title_tag = slide.select_one('.this-desc-title')
                        if not title_tag:
                            continue
                        title = title_tag.get_text(strip=True)
                        if title in seen:
                            continue
                        seen.add(title)
                        link_tag = slide.select_one('.slid-e-bnt a[href*="/vod/play/id/"]')
                        if not link_tag:
                            continue
                        href = link_tag.get('href')
                        m = re.search(r'/id/(\d+)', href)
                        if not m:
                            continue
                        vid = m.group(1)
                        pic = ""
                        bg_div = slide.select_one('.slid-e-bj[style*="background-image"]')
                        if bg_div:
                            style = bg_div.get('style', '')
                            m_pic = re.search(r'url\((.*?)\)', style)
                            if m_pic:
                                pic = m_pic.group(1).strip('"\'')
                        remark = ""
                        remark_tag = slide.select_one('.focus-item-label-original')
                        if remark_tag:
                            remark = remark_tag.get_text(strip=True)
                        videos.append({
                            "vod_id": vid,
                            "vod_name": title,
                            "vod_pic": pic,
                            "vod_remarks": remark
                        })
                    except:
                        continue

                # 精选推荐（去重）
                boxes = root.select('.public-list-box.public-pic-a')
                for box in boxes[:12]:
                    try:
                        a_tag = box.select_one('a.public-list-exp')
                        if not a_tag:
                            continue
                        href = a_tag.get('href', '')
                        m = re.search(r'/id/(\d+)', href)
                        if not m:
                            continue
                        vid = m.group(1)
                        if vid in [v['vod_id'] for v in videos]:
                            continue
                        title = a_tag.get('title', '')
                        img = box.select_one('img.gen-movie-img')
                        pic = img.get('data-src') or img.get('src') if img else ''
                        if pic and 'base64' in pic:
                            pic = img.get('data-src') if img else ''
                        remark = ""
                        remark_tag = box.select_one('.public-list-prb')
                        if remark_tag:
                            remark = remark_tag.get_text(strip=True)
                        score_tag = box.select_one('.public-prt')
                        if score_tag:
                            score = score_tag.get_text(strip=True)
                            if score and remark:
                                remark = f"{score} | {remark}"
                            elif score:
                                remark = score
                        videos.append({
                            "vod_id": vid,
                            "vod_name": title,
                            "vod_pic": pic,
                            "vod_remarks": remark
                        })
                    except:
                        continue
            else:
                videos = self._parseList(html)[:20]

        result['list'] = videos
        return result

    def homeVideoContent(self):
        res = self.homeContent(False)
        return {"list": res.get('list', [])}

    def categoryContent(self, tid, pg, filter, extend):
        result = {}
        url = f"{self.siteUrl}/index.php/vod/show/id/{tid}/page/{pg}.html"
        html = self._getHtml(url)
        videos = self._parseList(html) if html else []

        # 分页推断
        pagecount = int(pg) + 1
        if html:
            # 如果没有"下一页"或下一页被禁用，则当前是最后一页
            if 'swiper-button-next' in html and 'swiper-button-disabled' in html:
                # 尝试找最大页码
                pages = re.findall(r'page/(\d+)\.html', html)
                if pages:
                    pagecount = max([int(p) for p in pages])
                else:
                    pagecount = int(pg)
            else:
                pagecount = int(pg) + 1

        result = {
            "page": int(pg),
            "pagecount": pagecount,
            "limit": 20,
            "total": pagecount * 20,
            "list": videos
        }
        return result

    def detailContent(self, array):
        result = {}
        tid = array[0]
        url = f"{self.siteUrl}/index.php/vod/detail/id/{tid}.html"
        html = self._getHtml(url)
        if not html:
            return {"list": []}

        title = ""
        pic = ""
        content = ""
        year = ""
        area = ""
        actor = ""
        director = ""
        type_name = ""
        remarks = ""

        if HAS_BS4:
            root = BeautifulSoup(html, 'html.parser')
            title_tag = root.select_one('.this-info-title h1')
            if title_tag:
                title = title_tag.get_text(strip=True)
            else:
                img_tag = root.select_one('.this-info-img img')
                if img_tag:
                    title = img_tag.get('alt', '').replace('封面图', '')

            img_tag = root.select_one('.this-info-img img')
            if img_tag:
                pic = img_tag.get('data-src') or img_tag.get('src') or ''

            desc_tag = root.select_one('.this-desc-text')
            if desc_tag:
                content = desc_tag.get_text(strip=True)

            info_items = root.select('.this-info-item')
            for item in info_items:
                text = item.get_text(strip=True)
                if '年代' in text or '年份' in text:
                    year = text.split('：', 1)[-1] if '：' in text else text
                elif '地区' in text:
                    area = text.split('：', 1)[-1] if '：' in text else text
                elif '主演' in text:
                    actor = text.split('：', 1)[-1] if '：' in text else text
                elif '导演' in text:
                    director = text.split('：', 1)[-1] if '：' in text else text
                elif '类型' in text:
                    type_name = text.split('：', 1)[-1] if '：' in text else text
                elif '状态' in text or '更新' in text:
                    remarks = text.split('：', 1)[-1] if '：' in text else text

            # 播放列表解析
            play_from = []
            play_url = []

            # 尝试获取线路名
            tabs = root.select('.play-title li') or root.select('.tab-item') or root.select('[id^="tab_"]')
            boxes = root.select('.play-box') or root.select('.anthology-list') or root.select('.anthology-list-box')

            if boxes:
                for idx, box in enumerate(boxes):
                    from_name = f"线路{idx+1}"
                    if idx < len(tabs):
                        tab_text = tabs[idx].get_text(strip=True)
                        if tab_text:
                            from_name = tab_text
                    play_from.append(from_name)
                    urls = []
                    links = box.select('a[href*="/vod/play/"]')
                    for link in links:
                        name = link.get_text(strip=True)
                        href = link.get('href', '')
                        if href.startswith('/'):
                            href = self.siteUrl + href
                        urls.append(f"{name}${href}")
                    play_url.append("#".join(urls))
            else:
                # 兜底：直接抓取所有播放链接
                links = root.select('a[href*="/vod/play/id/"]')
                if links:
                    play_from = ["默认线路"]
                    urls = []
                    for link in links:
                        name = link.get_text(strip=True)
                        href = link.get('href', '')
                        if href.startswith('/'):
                            href = self.siteUrl + href
                        urls.append(f"{name}${href}")
                    play_url = ["#".join(urls)]
        else:
            # 正则解析详情
            m_title = re.search(r'<h1[^>]*>(.*?)</h1>', html)
            if m_title:
                title = re.sub(r'<[^>]+>', '', m_title.group(1)).strip()
            m_pic = re.search(r'<div[^>]*class="[^"]*this-info-img[^"]*"[^>]*>.*?<img[^>]*(?:data-src|src)="([^"]*)"[^>]*>', html, re.S)
            if m_pic:
                pic = m_pic.group(1)
            m_desc = re.search(r'<div[^>]*class="[^"]*this-desc-text[^"]*"[^>]*>(.*?)</div>', html, re.S)
            if m_desc:
                content = re.sub(r'<[^>]+>', '', m_desc.group(1)).strip()
            # 播放链接兜底
            play_from = ["默认线路"]
            links = re.findall(r'<a[^>]*href="(/index\.php/vod/play/id/\d+/sid/\d+/nid/\d+\.html)"[^>]*>(.*?)</a>', html)
            urls = []
            for href, name in links:
                name = re.sub(r'<[^>]+>', '', name).strip()
                urls.append(f"{name}${self.siteUrl}{href}")
            play_url = ["#".join(urls)]

        vod = {
            "vod_id": tid,
            "vod_name": title,
            "vod_pic": pic,
            "vod_remarks": remarks,
            "vod_year": year,
            "vod_area": area,
            "vod_actor": actor,
            "vod_director": director,
            "vod_content": content,
            "type_name": type_name,
            "vod_play_from": "$$$".join(play_from) if play_from else "默认线路",
            "vod_play_url": "$$$".join(play_url) if play_url else ""
        }
        result = {"list": [vod]}
        return result

    def searchContent(self, key, quick):
        url = f"{self.siteUrl}/index.php/vod/search.html?wd={urllib.parse.quote(key)}"
        html = self._getHtml(url)
        videos = self._parseList(html) if html else []
        return {"list": videos}

    def playerContent(self, flag, id, vipFlags):
        result = {}
        try:
            if not id.startswith('http'):
                id = self.siteUrl + id
            result = {
                "parse": 1,
                "url": id,
                "header": json.dumps(self.headers)
            }
        except Exception as e:
            print(f"[威视TV] playerContent error: {e}")
            result = {"parse": 0, "url": ""}
        return result

    config = {
        "player": {},
        "filter": {}
    }
    header = {}

    def localProxy(self, param):
        action = {
            'url': '',
            'header': '',
            'param': '',
            'type': 'string',
            'after': ''
        }
        return [200, "video/MP2T", action, ""]
