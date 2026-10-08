# -*- coding: utf-8 -*-
import json
import sys
import re
import html as html_parser
from bs4 import BeautifulSoup
from urllib.parse import quote

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):
    def init(self, extend=""):
        self.host = "https://91av.club"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': f'{self.host}/',
        }

    def getName(self):
        return "久夜AV"

    def homeContent(self, filter):
        classes = [
            {'type_name': '91视频', 'type_id': '1'},
            {'type_name': '小视频', 'type_id': '2'},
            {'type_name': '日本片', 'type_id': '3'},
            {'type_name': '欧美片', 'type_id': '4'},
            {'type_name': '卡通片', 'type_id': '5'},
            {'type_name': '国产片', 'type_id': '6'}
        ]

        sort_options = [
            {"n": "最新", "v": "time"},
            {"n": "最热", "v": "hits"},
            {"n": "评分", "v": "score"},
        ]
        
        filter_options_map = {
            '1': [
                {"n": "全部", "v": ""},
                {"n": "最近更新", "v": "最近更新"},
                {"n": "当前最热", "v": "当前最热"},
                {"n": "最近加精", "v": "最近加精"},
                {"n": "最近得分", "v": "最近得分"},
                {"n": "本月收藏", "v": "本月收藏"},
                {"n": "收藏最多", "v": "收藏最多"},
                {"n": "本月最热", "v": "本月最热"},
                {"n": "上月最热", "v": "上月最热"}
            ],
            '2': [
                {"n": "全部", "v": ""},
                {"n": "美女", "v": "美女"}, 
                {"n": "御姐", "v": "御姐"}, 
                {"n": "甜美", "v": "甜美"}, 
                {"n": "清纯", "v": "清纯"}, 
                {"n": "熟女", "v": "熟女"}, 
                {"n": "人妻", "v": "人妻"}, 
                {"n": "小姐", "v": "小姐"},
                {"n": "丝袜", "v": "丝袜"}, 
                {"n": "美腿", "v": "美腿"}, 
                {"n": "美臀", "v": "美臀"}, 
                {"n": "自拍", "v": "自拍"}, 
                {"n": "偷拍", "v": "偷拍"}
            ],
            '3': [
                {"n": "全部", "v": ""},
                {"n": "甜美", "v": "甜美"}, 
                {"n": "清纯", "v": "清纯"}, 
                {"n": "熟女", "v": "熟女"},
                {"n": "学生", "v": "学生"}, 
                {"n": "人妻", "v": "人妻"},
                {"n": "女仆", "v": "女仆"}, 
                {"n": "白领", "v": "白领"},
                {"n": "小姐", "v": "小姐"}, 
                {"n": "泳装", "v": "泳装"},
                {"n": "运动", "v": "运动"}, 
                {"n": "丝袜", "v": "丝袜"}, 
                {"n": "双飞", "v": "双飞"},
                {"n": "群交", "v": "群交"},
                {"n": "乱伦", "v": "乱伦"},
                {"n": "强奸", "v": "强奸"},
                {"n": "轮奸", "v": "轮奸"}, 
                {"n": "道具", "v": "道具"}, 
                {"n": "调教", "v": "调教"}
            ],
            '4': [ 
                {"n": "全部", "v": ""},
                {"n": "甜美", "v": "甜美"}, 
                {"n": "清纯", "v": "清纯"}, 
                {"n": "熟女", "v": "熟女"},
                {"n": "学生", "v": "学生"}, 
                {"n": "人妻", "v": "人妻"},                
                {"n": "无毛", "v": "无毛"},
                {"n": "嫩穴", "v": "嫩穴"},
                {"n": "巨根", "v": "巨根"}, 
                {"n": "双飞", "v": "双飞"},
                {"n": "群交", "v": "群交"},
                {"n": "乱伦", "v": "乱伦"}
            ],
            '5': [
                {"n": "全部", "v": ""},
                {"n": "纯爱", "v": "纯爱"}, 
                {"n": "NTR", "v": "NTR"}, 
                {"n": "后宫", "v": "后宫"},
                {"n": "调教", "v": "调教"}, 
                {"n": "乱伦", "v": "乱伦"}, 
                {"n": "凌辱", "v": "凌辱"},
                {"n": "精灵", "v": "精灵"}, 
                {"n": "校园", "v": "校园"}, 
                {"n": "人妻", "v": "人妻"}
            ],
            '6': [
                {"n": "全部", "v": ""},
                {"n": "美女", "v": "美女"}, 
                {"n": "甜美", "v": "甜美"}, 
                {"n": "清纯", "v": "清纯"}, 
                {"n": "人妻", "v": "人妻"},
                {"n": "教师", "v": "教师"},
                {"n": "护士", "v": "护士"}, 
                {"n": "白领", "v": "白领"},
                {"n": "无毛", "v": "无毛"},
                {"n": "双飞", "v": "双飞"},
                {"n": "群交", "v": "群交"}, 
                {"n": "乱伦", "v": "乱伦"},
                {"n": "强奸", "v": "强奸"}, 
                {"n": "迷奸", "v": "迷奸"},
                {"n": "调教", "v": "调教"},
                {"n": "剧情", "v": "剧情"}
            ]
        }

        filters = {}
        for item in classes:
            tid = item['type_id']
            filter_opts = filter_options_map.get(tid, [{"n": "全部", "v": ""}])
            filters[tid] = [
                {"key": "class", "name": "喜好", "value": filter_opts},
                {"key": "by", "name": "排序", "value": sort_options}
            ]

        return {'class': classes, 'filters': filters}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg)
        cls = extend.get('class', '')
        by = extend.get('by', 'time')

        path = f"/vodshow/{tid}"
        if cls:
            path += f"/class/{quote(cls)}"
        path += f"/by/{by}"
        if page > 1:
            path += f"/page/{page}"

        url = f"{self.host}{path}.html"

        try:
            html = self.fetch(url, headers=self.headers).text
            vods = self.parse_vod_list(html)
            return {'list': vods, 'page': page, 'pagecount': 999}
        except Exception:
            return {'list': []}

    def parse_vod_list(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        vods = []
        for item in soup.select('.public-list-box'):
            a_tag = item.select_one('a.public-list-exp')
            if not a_tag:
                continue
            href = a_tag.get('href', '')
            if not href:
                continue
            vid_match = re.search(r'/vodplay/(\d+)-', href)
            if not vid_match:
                continue
            vid = vid_match.group(1)
            title = a_tag.get('title', '').strip()
            if not title:
                continue

            img_tag = a_tag.find('img')
            pic = ''
            if img_tag and img_tag.get('data-src'):
                pic = img_tag['data-src']
            elif img_tag and img_tag.get('src'):
                pic = img_tag['src']

            if pic and not pic.startswith('http'):
                pic = self.host + pic

            vods.append({
                "vod_id": vid,
                "vod_name": html_parser.unescape(title),
                "vod_pic": pic,
                "vod_remarks": ""
            })
        return vods

    def detailContent(self, ids):
        vid = ids[0]
        url = f"{self.host}/vodplay/{vid}-1-1.html"

        try:
            html = self.fetch(url, headers=self.headers).text

            play_url = ""
            url_match = re.search(r'["\']url["\']\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']', html)
            if url_match:
                play_url = url_match.group(1).replace("\\/", "/")

            title_match = re.search(r'<title>(.*?)</title>', html)
            title = title_match.group(1).split('-')[0].strip() if title_match else "视频播放"

            player_base = "https://player.91av.club/player/index.php?code=VIPNODM&if=1"
            encoded_title = quote(title)
            full_play_url = f"{player_base}&url={play_url}&tittle={encoded_title}"

            pic_match = re.search(r'["\']vod_pic["\']\s*:\s*["\']([^"\']+)["\']', html)
            pic = pic_match.group(1).replace("\\/", "/") if pic_match else ""

            if not play_url:
                return {'list': []}

            return {'list': [{
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_play_from": "久夜AV",
                "vod_play_url": f"网页${full_play_url}"
            }]}
        except Exception:
            return {'list': []}

    def searchContent(self, key, quick, pg="1", extend=None):
        url = f"{self.host}/vodsearch/{quote(key)}/page/{pg}.html"
        try:
            html = self.fetch(url, headers=self.headers).text
            return {'list': self.parse_vod_list(html), 'page': int(pg)}
        except:
            return {'list': []}

    def playerContent(self, flag, id, vipFlags):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://91av.club/',
            'Origin': 'https://91av.club'
        }
        return {
            'parse': 1,
            'url': id,
            'header': headers
        }