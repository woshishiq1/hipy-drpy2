# -*- coding: utf-8 -*-
"""
男人本色 Spider —— 适配 https://nanrenbense3564991.xyz/
"""

import sys
import re
import json
import requests
import urllib3
import base64
from urllib.parse import quote, unquote

urllib3.disable_warnings()
sys.path.append('..')
from base.spider import Spider


class Spider(Spider):
    session = requests.Session()
    host = 'https://nanrenbense3564991.xyz'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Referer': 'https://nanrenbense3564991.xyz/',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }

    def getName(self): return "nanrenbense"
    def isVideoFormat(self, url): return bool(url and any(ext in url.lower() for ext in ['.m3u8', '.mp4', '.ts', '.flv']))
    def manualVideoCheck(self): return False
    def destroy(self): pass
    def localProxy(self, param): return [404, 'text/plain', '']

    def init(self, extend=""):
        self.session.verify = False
        self.session.headers.update(self.headers)

    def _fetch(self, url):
        try:
            r = self.session.get(url, timeout=20, allow_redirects=True)
            r.encoding = 'utf-8'
            return r.text if r.status_code == 200 else ''
        except Exception:
            return ''

    def homeContent(self, filter):
        classes = [
            {'type_id': '158',  'type_name': '国产传媒'},
            {'type_id': '1091', 'type_name': '91仓库'},
            {'type_id': '1200', 'type_name': '少女仓库'},
            {'type_id': '1141', 'type_name': '最近加精'},
            {'type_id': '1142', 'type_name': '收藏最多'},
            {'type_id': '1143', 'type_name': '本月最热'},
            {'type_id': '1144', 'type_name': '最近更新'},
            {'type_id': '1145', 'type_name': '91原创'},
            {'type_id': '1114', 'type_name': '传媒国产'},
            {'type_id': '1115', 'type_name': '日韩系列'},
            {'type_id': '1116', 'type_name': '欧美巨屌'},
            {'type_id': '1117', 'type_name': '步兵无码'},
            {'type_id': '1201', 'type_name': '成人动漫'},
            {'type_id': '1160', 'type_name': '国产区'},
            {'type_id': '1161', 'type_name': 'AV区'},
            {'type_id': '1162', 'type_name': '欧美区'},
            {'type_id': '1163', 'type_name': '动漫区'},
            {'type_id': '1164', 'type_name': '网红主播'},
            {'type_id': '1165', 'type_name': '国产传媒②'},
            {'type_id': '1166', 'type_name': '探花系列'},
            {'type_id': '1167', 'type_name': '人妻熟女'},
            {'type_id': '1168', 'type_name': '日本无码'},
            {'type_id': '1169', 'type_name': '美乳巨乳'},
            {'type_id': '1170', 'type_name': '强制侵犯'},
            {'type_id': '1171', 'type_name': '制服诱惑'},
            {'type_id': '1172', 'type_name': '绝色佳人'},
            {'type_id': '1173', 'type_name': '风俗泡泡浴'},
            {'type_id': '1174', 'type_name': '家庭乱伦'},
            {'type_id': '1175', 'type_name': 'AV解说'},
            {'type_id': '1176', 'type_name': '三级电影'},
            {'type_id': '1177', 'type_name': '少女萝莉'},
            {'type_id': '1178', 'type_name': 'SM调教'},
            {'type_id': '1179', 'type_name': '绝顶潮吹'},
            {'type_id': '1180', 'type_name': '魔镜系列'},
            {'type_id': '1181', 'type_name': '时间停止'},
            {'type_id': '1182', 'type_name': '催眠洗脑'},
            {'type_id': '1183', 'type_name': '漫改系列'},
            {'type_id': '1184', 'type_name': '电车痴汉'},
            {'type_id': '1185', 'type_name': '淫欲痴女'},
            {'type_id': '1186', 'type_name': 'AI换脸'},
            {'type_id': '1187', 'type_name': '其他区'},
            {'type_id': '1188', 'type_name': '网曝门'},
            {'type_id': '1189', 'type_name': 'TS专区'},
            {'type_id': '1190', 'type_name': '女性向系列'},
            {'type_id': '1191', 'type_name': '女同性恋'},
            {'type_id': '1192', 'type_name': '男同性恋'},
            {'type_id': '1193', 'type_name': '欧美精品'},
            {'type_id': '1194', 'type_name': '国产自拍'},
            {'type_id': '1195', 'type_name': '日本动漫'},
            {'type_id': '1196', 'type_name': '3D动漫'},
            {'type_id': '1197', 'type_name': '韩国主播'},
            {'type_id': '1198', 'type_name': '泰国风情'},
            {'type_id': '1199', 'type_name': 'OnlyFans'},
            {'type_id': '61',   'type_name': '国产情色'},
            {'type_id': '63',   'type_name': '日本无码②'},
            {'type_id': '65',   'type_name': '日本有码②'},
            {'type_id': '67',   'type_name': '中文字幕②'},
            {'type_id': '69',   'type_name': '网红主播②'},
            {'type_id': '71',   'type_name': '成人动漫②'},
            {'type_id': '73',   'type_name': '欧美情色'},
            {'type_id': '75',   'type_name': '国模私拍'},
            {'type_id': '77',   'type_name': '长腿丝袜'},
            {'type_id': '79',   'type_name': '邻家人妻'},
            {'type_id': '80',   'type_name': '韩国伦理'},
            {'type_id': '81',   'type_name': '香港伦理'},
            {'type_id': '82',   'type_name': '精品推荐②'},
            {'type_id': '83',   'type_name': '原纱央莉'},
            {'type_id': '84',   'type_name': '柚木TINA'},
            {'type_id': '85',   'type_name': '大桥未久'},
            {'type_id': '86',   'type_name': '橘日向'},
            {'type_id': '87',   'type_name': '仁科百华'},
            {'type_id': '88',   'type_name': '天海翼'},
            {'type_id': '89',   'type_name': '小川阿佐美'},
            {'type_id': '90',   'type_name': '樱井莉亚'},
            {'type_id': '91',   'type_name': '长泽梓'},
            {'type_id': '1147', 'type_name': '国产精品③'},
            {'type_id': '1148', 'type_name': '华语AV③'},
            {'type_id': '1149', 'type_name': '黑料吃瓜③'},
            {'type_id': '1150', 'type_name': '欧美③'},
            {'type_id': '1151', 'type_name': '禁漫'},
            {'type_id': '1152', 'type_name': '视频2区'},
            {'type_id': '1153', 'type_name': '学生'},
            {'type_id': '1155', 'type_name': '探花'},
            {'type_id': '1156', 'type_name': '日本无码③'},
            {'type_id': '1157', 'type_name': '日本有码③'},
            {'type_id': '1158', 'type_name': '主播网红③'},
            {'type_id': '1159', 'type_name': '日本素人'},
            {'type_id': '129',  'type_name': '日韩无码④'},
            {'type_id': '130',  'type_name': '强奸乱伦④'},
            {'type_id': '131',  'type_name': '欧美精品④'},
            {'type_id': '132',  'type_name': '国产精品④'},
            {'type_id': '133',  'type_name': '人妻系列④'},
            {'type_id': '134',  'type_name': '中文字幕④'},
            {'type_id': '135',  'type_name': '动漫精品④'},
            {'type_id': '136',  'type_name': '伦理影片④'},
            {'type_id': '137',  'type_name': '日韩精品④'},
            {'type_id': '138',  'type_name': '制服诱惑④'},
            {'type_id': '139',  'type_name': '自拍偷拍④'},
            {'type_id': '140',  'type_name': '有码视频④'},
            {'type_id': '141',  'type_name': '3P合辑④'},
            {'type_id': '142',  'type_name': '巨乳系列④'},
            {'type_id': '143',  'type_name': '颜射系列④'},
            {'type_id': '144',  'type_name': '口交视频④'},
            {'type_id': '145',  'type_name': '自慰系列④'},
            {'type_id': '146',  'type_name': 'SM重味④'},
            {'type_id': '147',  'type_name': '教师学生④'},
            {'type_id': '148',  'type_name': '大秀视频④'},
            {'type_id': '149',  'type_name': '柚木TINA④'},
            {'type_id': '150',  'type_name': '原纱央莉④'},
            {'type_id': '151',  'type_name': '大桥未久④'},
            {'type_id': '152',  'type_name': '橘日向④'},
            {'type_id': '153',  'type_name': '仁科百华④'},
            {'type_id': '154',  'type_name': '天海翼④'},
            {'type_id': '155',  'type_name': '小川阿佐美④'},
            {'type_id': '156',  'type_name': '樱井莉亚④'},
            {'type_id': '157',  'type_name': '长泽梓④'},
            {'type_id': '274',  'type_name': '精品推荐⑤'},
            {'type_id': '275',  'type_name': '国产色情⑤'},
            {'type_id': '276',  'type_name': '主播直播⑤'},
            {'type_id': '277',  'type_name': '亚洲无码⑤'},
            {'type_id': '278',  'type_name': '亚洲有码⑤'},
            {'type_id': '279',  'type_name': '中文字幕⑤'},
            {'type_id': '280',  'type_name': '巨乳美乳⑤'},
            {'type_id': '281',  'type_name': '人妻熟女⑤'},
            {'type_id': '282',  'type_name': '强奸乱伦⑤'},
            {'type_id': '283',  'type_name': '欧美精品⑤'},
            {'type_id': '284',  'type_name': '萝莉少女⑤'},
            {'type_id': '285',  'type_name': '伦理三级⑤'},
            {'type_id': '286',  'type_name': '成人动漫⑤'},
            {'type_id': '287',  'type_name': '自拍偷拍⑤'},
            {'type_id': '288',  'type_name': '制服丝袜⑤'},
            {'type_id': '289',  'type_name': '口交颜射⑤'},
            {'type_id': '290',  'type_name': '日本精品⑤'},
            {'type_id': '291',  'type_name': 'Cosplay⑤'},
            {'type_id': '292',  'type_name': '素人自拍⑤'},
            {'type_id': '293',  'type_name': '台湾辣妹⑤'},
            {'type_id': '294',  'type_name': '韩国御姐⑤'},
            {'type_id': '295',  'type_name': '唯美港姐⑤'},
            {'type_id': '296',  'type_name': '东南亚AV⑤'},
            {'type_id': '297',  'type_name': '欺辱凌辱⑤'},
            {'type_id': '298',  'type_name': '剧情介绍⑤'},
            {'type_id': '299',  'type_name': '多人多P⑤'},
            {'type_id': '300',  'type_name': '91探花⑤'},
            {'type_id': '301',  'type_name': '网红流出⑤'},
            {'type_id': '302',  'type_name': '野外露出⑤'},
            {'type_id': '303',  'type_name': '古装扮演⑤'},
            {'type_id': '304',  'type_name': '女优系列⑤'},
            {'type_id': '305',  'type_name': '可爱学生⑤'},
            {'type_id': '306',  'type_name': '风情旗袍⑤'},
            {'type_id': '307',  'type_name': '兽耳系列⑤'},
            {'type_id': '308',  'type_name': '瑜伽裤⑤'},
            {'type_id': '309',  'type_name': '闷骚护士⑤'},
            {'type_id': '310',  'type_name': '过膝袜⑤'},
            {'type_id': '311',  'type_name': '网曝门⑤'},
            {'type_id': '312',  'type_name': '传媒出品⑤'},
            {'type_id': '313',  'type_name': '女同性恋⑤'},
            {'type_id': '314',  'type_name': '男同性恋⑤'},
            {'type_id': '315',  'type_name': '恋腿狂魔⑤'},
            {'type_id': '1230', 'type_name': '10分钟以上'},
            {'type_id': '1231', 'type_name': '20分钟以上'},
            {'type_id': '6',    'type_name': '亚洲情色(伦)'},
            {'type_id': '7',    'type_name': '国产主播(伦)'},
            {'type_id': '8',    'type_name': '国产自拍(伦)'},
            {'type_id': '9',    'type_name': '无码专区(伦)'},
            {'type_id': '10',   'type_name': '欧美性爱(伦)'},
            {'type_id': '13',   'type_name': '熟女人妻(伦)'},
            {'type_id': '16',   'type_name': '强奸乱伦(伦)'},
            {'type_id': '19',   'type_name': '巨乳美乳(伦)'},
            {'type_id': '22',   'type_name': '中文字幕(伦)'},
            {'type_id': '25',   'type_name': '制服诱惑(伦)'},
            {'type_id': '28',   'type_name': '女同性恋(伦)'},
            {'type_id': '31',   'type_name': '卡通动画(伦)'},
            {'type_id': '34',   'type_name': '视频伦理(伦)'},
            {'type_id': '35',   'type_name': '少女萝莉(伦)'},
            {'type_id': '36',   'type_name': '重口色情(伦)'},
            {'type_id': '37',   'type_name': '人兽性交(伦)'},
            {'type_id': '1140', 'type_name': '福利姬(伦)'},
            {'type_id': '363',  'type_name': '街拍偷拍(图)'},
            {'type_id': '364',  'type_name': '丝袜美腿(图)'},
            {'type_id': '365',  'type_name': '欧美风情(图)'},
            {'type_id': '366',  'type_name': '网友自拍(图)'},
            {'type_id': '367',  'type_name': '卡通漫画(图)'},
            {'type_id': '368',  'type_name': '露出激情(图)'},
            {'type_id': '369',  'type_name': '唯美写真(图)'},
            {'type_id': '370',  'type_name': '女优情报(图)'},
            {'type_id': '11',   'type_name': '暴力虐待(书)'},
            {'type_id': '14',   'type_name': '学生校园(书)'},
            {'type_id': '17',   'type_name': '玄幻仙侠(书)'},
            {'type_id': '20',   'type_name': '明星偶像(书)'},
            {'type_id': '23',   'type_name': '生活都市(书)'},
            {'type_id': '26',   'type_name': '不伦恋情(书)'},
            {'type_id': '29',   'type_name': '经验故事(书)'},
            {'type_id': '32',   'type_name': '科学幻想(书)'},
            {'type_id': '1111', 'type_name': '激情卡漫(图2)'},
            {'type_id': '1112', 'type_name': '性感激情(图2)'},
        ]
        return {'class': classes, 'filters': {}, 'type': '影视'}

    def homeVideoContent(self):
        text = self._fetch(self.host + '/')
        items = self._parse_index_list(text)
        return {
            'list': items[:24],
            'page': 1,
            'pagecount': 2 if len(items) >= 24 else 1,
            'limit': len(items),
            'total': len(items)
        }

    def _parse_index_list(self, text):
        """解析视频/图片/小说列表，兼容首页和分类页的各种HTML变体"""
        items = []
        if not text:
            return items

        # 方案1: 标准li结构解析（兼容class顺序变化、额外class、末尾空格等）
        pattern = re.compile(
            r'<li[^>]*class="[^"]*(?:col-md-2|col-sm-3|col-xs-4)[^"]*"[^>]*>'
            r'(.*?)'
            r'</li>',
            re.S
        )

        for li_match in pattern.finditer(text):
            li_html = li_match.group(1)
            vid = ''
            # 兼容 href="info/xxx.html" 和 href="/info/xxx.html"
            m = re.search(r'href="/?info/(\d+)\.html"', li_html)
            if m:
                vid = m.group(1)
            if not vid:
                continue

            title = ''
            # 先从a标签title属性取（video-pic的a标签或h5里的a标签）
            m = re.search(r'<a[^>]+title="([^"]*)"[^>]*>.*?</a>', li_html, re.S)
            if m:
                title = m.group(1).strip()
            # 再从h5/h4/h3里的a标签纯文本取
            if not title:
                m = re.search(r'<h[3-6][^>]*>.*?<a[^>]*>([^<]+)</a>.*?</h[3-6]>', li_html, re.S)
                if m:
                    title = m.group(1).strip()

            pic = ''
            # 按优先级匹配各种图片格式
            pic_patterns = [
                r'style=["'][^"']*background:\s*url\(["']?([^"'\)]+)["']?\)',
                r'data-original="([^"]+)"',
                r'data-src="([^"]+)"',
                r'<img[^>]+src="([^"]+)"',
            ]
            for pat in pic_patterns:
                m = re.search(pat, li_html)
                if m:
                    pic = m.group(1).strip()
                    # 过滤掉loading图和默认图（不区分大小写）
                    if pic and not any(x in pic.lower() for x in ['loading', 'blank', 'logo', 'icon', 'default.jpg', 'placeholder']):
                        break
                    pic = ''

            remarks = ''
            # 匹配评分/时长等信息
            m = re.search(r'<div\s+align="left">\s*([^<]+)</div>', li_html)
            if m:
                remarks = m.group(1).strip()
            else:
                m = re.search(r'<span[^>]*class="[^"]*(?:time|date|duration|remark|note)[^"]*"[^>]*>([^<]+)</span>', li_html, re.I)
                if m:
                    remarks = m.group(1).strip()

            if vid:
                items.append({
                    'vod_id': vid,
                    'vod_name': title if title else f'视频{vid}',
                    'vod_pic': pic,
                    'vod_remarks': remarks,
                })

        # 方案2: 全局fallback，不依赖li结构，直接抓取所有 info/数字.html
        if not items:
            seen = set()
            # 匹配所有 a 标签中的 info/xxx.html（兼容带/不带前导斜杠）
            all_links = re.findall(
                r'<a[^>]+href="/?info/(\d+)\.html"[^>]*>(.*?)</a>',
                text, re.S
            )
            for vid, a_inner in all_links:
                if vid in seen:
                    continue
                seen.add(vid)

                title = ''
                m = re.search(r'title="([^"]*)"', a_inner)
                if m:
                    title = m.group(1).strip()
                if not title:
                    title = re.sub(r'<[^>]+>', '', a_inner).strip()
                if not title:
                    title = f'未知标题{vid}'

                # 在a标签前后800字符内找图（不依赖a标签内必须有img）
                pos = text.find(f'info/{vid}.html')
                if pos < 0:
                    pos = text.find(f'/info/{vid}.html')
                context = text[max(0, pos-800):pos+800] if pos > 0 else ''

                pic = ''
                for pat in [
                    r'style=["'][^"']*background:\s*url\(["']?([^"'\)]+)["']?\)',
                    r'data-original="([^"]+)"',
                    r'data-src="([^"]+)"',
                    r'<img[^>]+src="([^"]+)"',
                ]:
                    m = re.search(pat, context, re.S)
                    if m:
                        pic = m.group(1).strip()
                        if pic and not any(x in pic.lower() for x in ['loading', 'blank', 'logo', 'icon', 'default.jpg']):
                            break

                items.append({
                    'vod_id': vid,
                    'vod_name': title,
                    'vod_pic': pic,
                    'vod_remarks': '',
                })

        return items

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        tid_str = str(tid)

        # 网站存在两种分类路径格式，必须同时尝试：
        # 格式A: /type/id/xxx.html (大部分视频区)
        # 格式B: /type/xxx.html (91视频区1141-1145、随机推荐等)
        urls = []
        if page == 1:
            urls = [
                f'{self.host}/type/id/{tid_str}.html',
                f'{self.host}/type/{tid_str}.html',
            ]
        else:
            urls = [
                f'{self.host}/type/id/{tid_str}-{page}.html',
                f'{self.host}/type/id/{tid_str}/page/{page}.html',
                f'{self.host}/type/id/{tid_str}_{page}.html',
                f'{self.host}/type/{tid_str}-{page}.html',
                f'{self.host}/type/{tid_str}/page/{page}.html',
                f'{self.host}/type/{tid_str}_{page}.html',
            ]

        text = ''
        for url in urls:
            text = self._fetch(url)
            if text:
                break

        items = self._parse_index_list(text)
        has_next = False
        if text:
            # 多种分页判断（兼容.html后缀和无后缀）
            next_patterns = [
                r'href="[^"]*[/_-]' + str(page + 1) + r'\.html"',
                r'href="[^"]*[/_-]' + str(page + 1) + r'/"',
                r'下一页|下一頁|next\s*page',
                r'pagination.*?' + str(page + 1),
            ]
            for pat in next_patterns:
                if re.search(pat, text, re.I):
                    has_next = True
                    break
            if not has_next and len(items) >= 12:
                has_next = True

        return {
            'list': items,
            'page': page,
            'pagecount': page + 1 if has_next else page,
            'limit': len(items),
            'total': page * len(items) + 1 if has_next else page * len(items)
        }

    def detailContent(self, ids):
        vid = str(ids[0] if isinstance(ids, list) else ids)
        url = f'{self.host}/info/{vid}.html'
        text = self._fetch(url)
        if not text:
            return {'list': []}

        title = ''
        for pat in [r'<h1[^>]*>(.*?)</h1>', r'<h2[^>]*>(.*?)</h2>', r'<title>([^<]+)</title>']:
            m = re.search(pat, text, re.S)
            if m:
                title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
                if title:
                    break
        if not title:
            title = f'视频{vid}'
        title = title.replace('- 男人本色', '').replace('- 男人本色.xyz', '').strip()

        cover = ''
        cover_patterns = [
            r'<div[^>]*class="[^"]*vod-img[^"]*"[^>]*>.*?<img[^>]+(?:data-original|src)="([^"]+)"',
            r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"',
            r'<img[^>]+class="[^"]*img-responsive[^"]*"[^>]+(?:data-original|src)="([^"]+)"',
            r'<div[^>]*class="[^"]*video-pic[^"]*"[^>]*>.*?<img[^>]+(?:data-original|src)="([^"]+)"',
            r'<img[^>]+data-original="([^"]+)"',
            r'<img[^>]+src="([^"]+)"[^>]*class="[^"]*content-img',
            r'style=["'][^"']*background:\s*url\(["']?([^"'\)]+)["']?\)',
        ]
        for pat in cover_patterns:
            m = re.search(pat, text, re.S)
            if m:
                cover = m.group(1)
                if cover and not any(x in cover.lower() for x in ['loading', 'blank', 'logo', 'icon', 'default.jpg']):
                    break

        content = ''
        content_patterns = [
            r'<div[^>]*class="[^"]*vod-content[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*content[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*desc[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*summary[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*intro[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*detail-content[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*stui-content__desc[^"]*"[^>]*>(.*?)</div>',
            r'<span[^>]*class="[^"]*detail-sketch[^"]*"[^>]*>(.*?)</span>',
        ]
        for pat in content_patterns:
            m = re.search(pat, text, re.S)
            if m:
                content = re.sub(r'<[^>]+>', '', m.group(1)).strip()
                if len(content) > 5:
                    break

        remarks = ''
        info_patterns = [
            r'主演[：:]\s*([^<
]+)',
            r'演员[：:]\s*([^<
]+)',
            r'分类[：:]\s*([^<
]+)',
            r'标签[：:]\s*([^<
]+)',
        ]
        for pat in info_patterns:
            m = re.search(pat, text)
            if m:
                remarks = m.group(1).strip()
                if remarks:
                    break

        play_from_list = []
        play_url_list = []
        source_blocks = re.findall(
            r'<div[^>]*class="[^"]*(?:play-list|playlist|stui-play__list|play-box)[^"]*"[^>]*>(.*?)</div>',
            text, re.S
        )
        if not source_blocks:
            source_blocks = re.findall(
                r'<ul[^>]*class="[^"]*(?:play-list|playlist)[^"]*"[^>]*>(.*?)</ul>',
                text, re.S
            )
        if source_blocks:
            for block in source_blocks:
                eps = re.findall(r'<a[^>]+href="([^"]+)"[^>]*>([^<]+)</a>', block)
                if eps:
                    urls = '#'.join([f'{name.strip()}${href}' for href, name in eps])
                    play_url_list.append(urls)
                    play_from_list.append('线路' + str(len(play_from_list) + 1))

        # 图片集详情页处理（激萌漫画、激情图片等）
        if not play_url_list:
            pic_urls = re.findall(
                r'<img[^>]+(?:data-original|src)="([^"]+)"[^>]*class="[^"]*(?:content-img|pic-img|gallery-img|lazy)',
                text, re.S
            )
            if not pic_urls:
                # 更宽松的图片提取
                pic_urls = re.findall(
                    r'<img[^>]+(?:data-original|src)="([^"]+)"[^>]*>',
                    text, re.S
                )
            if pic_urls:
                valid_pics = [u for u in pic_urls if not any(x in u.lower() for x in ['loading', 'blank', 'default.jpg', 'logo'])]
                if valid_pics:
                    pic_str = '#'.join([f'图片{i+1}${url}' for i, url in enumerate(valid_pics)])
                    play_url_list.append(pic_str)
                    play_from_list.append('图片浏览')

        # 小说/iframe/video处理
        if not play_url_list:
            m = re.search(r'<iframe[^>]+src="([^"]+)"', text, re.S)
            if m:
                iframe_src = m.group(1)
                play_url_list.append(f'正片${iframe_src}')
                play_from_list.append('默认线路')
            else:
                m = re.search(r'<video[^>]+src="([^"]+)"', text, re.S)
                if m:
                    play_url_list.append(f'正片${m.group(1)}')
                    play_from_list.append('默认线路')

        if not play_url_list:
            play_url_list.append(f'正片$/info/{vid}.html')
            play_from_list.append('默认线路')

        vod = {
            'vod_id': vid,
            'vod_name': title,
            'vod_pic': cover,
            'vod_content': content,
            'vod_remarks': remarks,
            'vod_play_from': '$$$'.join(play_from_list),
            'vod_play_url': '$$$'.join(play_url_list),
        }
        return {'list': [vod]}

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        encoded_key = quote(key)
        if page == 1:
            url = f'{self.host}/search/{encoded_key}.html'
        else:
            url = f'{self.host}/search/{encoded_key}-{page}.html'
        text = self._fetch(url)
        items = self._parse_index_list(text)
        has_next = False
        if text and (re.search(r'href="[^"]*[/_-]' + str(page + 1) + r'(?:\.html)?["']', text) or
                     re.search(r'下一页|下一頁|next', text, re.I) or
                     len(items) >= 12):
            has_next = True
        return {
            'list': items,
            'page': page,
            'pagecount': page + 1 if has_next else page,
            'limit': len(items),
            'total': page * len(items) + 1 if has_next else page * len(items)
        }

    def playerContent(self, flag, id, vipFlags=None):
        if id.startswith('http'):
            return {
                'parse': 0,
                'url': id,
                'header': {'Referer': self.host + '/', 'User-Agent': self.headers['User-Agent']},
                'position': '0'
            }
        if id.startswith('/'):
            full_url = self.host + id
        else:
            full_url = self.host + '/' + id
        text = self._fetch(full_url)
        m3u8 = ''
        if text:
            for var_name in ['player_aaaa', 'player', 'mac_player', 'player_data', 'cms_player']:
                m = re.search(r'var\s+' + var_name + r'\s*=\s*(\{.*?\})\s*</script>', text, re.S)
                if m:
                    try:
                        player = json.loads(m.group(1))
                        raw_url = player.get('url', '')
                        if raw_url and isinstance(raw_url, str):
                            decoded = raw_url.strip()
                            if re.match(r'^[A-Za-z0-9+/=]{20,}$', decoded):
                                try:
                                    decoded = base64.b64decode(decoded).decode('utf-8')
                                except Exception:
                                    pass
                            if '%' in decoded:
                                try:
                                    decoded = unquote(decoded)
                                except Exception:
                                    pass
                            if decoded.startswith('http'):
                                m3u8 = decoded
                                break
                    except Exception:
                        continue
            if not m3u8:
                m = re.search(r'<iframe[^>]+src="([^"]+)"', text, re.S)
                if m:
                    iframe_src = m.group(1)
                    if iframe_src.startswith('http'):
                        m3u8 = iframe_src
                    else:
                        m3u8 = self.host + ('' if iframe_src.startswith('/') else '/') + iframe_src
            if not m3u8:
                m = re.search(r'["'](https?://[^\s"<>]+?\.(?:m3u8|mp4|ts|flv))["']', text)
                if m:
                    m3u8 = m.group(1)
            if not m3u8:
                m = re.search(r'unescape\(["']([^"']+)["']\)', text)
                if m:
                    try:
                        decoded = unquote(m.group(1))
                        if decoded.startswith('http'):
                            m3u8 = decoded
                    except Exception:
                        pass
            if not m3u8:
                m = re.search(r'<video[^>]+src="([^"]+)"', text, re.S)
                if m:
                    vid_src = m.group(1)
                    if vid_src.startswith('http'):
                        m3u8 = vid_src
            if not m3u8:
                m = re.search(r'var\s+\w+\s*=\s*["'](https?://[^"']+?\.(?:m3u8|mp4))["']', text)
                if m:
                    m3u8 = m.group(1)
        return {
            'parse': 0 if m3u8 else 1,
            'url': m3u8 if m3u8 else full_url,
            'header': {'Referer': self.host + '/', 'User-Agent': self.headers['User-Agent']},
            'position': '0'
        }
