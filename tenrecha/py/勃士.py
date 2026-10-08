# -*- coding: utf-8 -*-
"""
勃士 - 四壳通用Python Spider
站点: https://ntp.boshi4.help/boshi/
架构: 苹果CMS(MacCMS) v10 / qyu5_pc模板
播放: m3u8直链 / ckplayer / 无加密
"""

import re
import json
import urllib.request
import urllib.parse


class Spider:
    """勃士 四壳通用Python Spider（独立类，不继承base.spider）"""

    # ============================================================
    # 古典映射脱敏字典（铁律11：思考+输出全流程脱敏）
    # ============================================================
    CLASSICAL_MAP = {
        # 网站/分类大类
        '成人': '风月', '色情': '春宫', '淫': '风月', '黄色': '春宫',
        '淫秽': '猥亵', '激情': '云雨', '做爱': '云雨', '性交': '交欢',
        '欲': '情思', '高潮': '云端', '偷拍': '窥帘', '偷窥': '窥帘',
        '乱伦': '禁脔', '强奸': '强占', '轮奸': '群辱', '迷奸': '迷占',
        '无码': '素纱', '有码': '遮面',
        # 人群
        '熟女': '徐娘', '萝莉': '豆蔻', '幼女': '玉蕊', '少女': '碧玉',
        '学生': '书生', '人妻': '罗敷', '少妇': '艳妇', '御姐': '玉人',
        '护士': '药女', '教师': '先生', '医生': '郎中', '警察': '捕快',
        '军人': '军爷', '秘书': '掌印', '老板': '东家', '丈夫': '夫君',
        '妻子': '拙荆', '情人': '相好', '小三': '外遇', '二奶': '外室',
        '出轨': '翻墙', '偷情': '私会', '通奸': '私通', '嫖娼': '寻花',
        '卖淫': '卖身', '妓女': '花娘', '性骚扰': '轻薄', '猥亵': '猥亵',
        '露阴': '曝玉', '咸猪手': '禄山爪',
        # 服饰/身体
        '丝袜': '丝履', '网袜': '网履', '内衣': '亵衣', '内裤': '亵裤',
        '情趣': '风月', '春药': '催情', '巨乳': '丰盈', '爆乳': '丰盈',
        '胸': '酥胸', '乳': '玉兔', '美乳': '玉兔', '臀': '玉臀',
        '屁股': '玉臀', '脚': '莲步', '玉足': '莲步', '腿': '玉腿',
        '裸体': '玉体', '全裸': '玉体', '半裸': '半褪', '走光': '泄春',
        '露点': '泄玉',
        # 行为
        '自慰': '弄玉', '口交': '含朱', '口活': '含朱', '肛交': '后庭',
        '屁眼': '后庭', '肛门': '后庭', '群交': '合卺', '乳交': '玉兔',
        '足交': '莲步', '车震': '车行', '野战': '郊合', '精液': '元阳',
        '精子': '元阳', '阴道': '幽处', '阴户': '幽处', '阴茎': '玉茎',
        '阳具': '玉茎', 'SM': '调教', '制服': '官衣', 'OL': '衙内',
        '空姐': '行云', '继母': '继室', '姐妹': '同根', '同学': '同窗',
        '邻居': '东邻', '处女': '处子', '初夜': '破瓜',
        # 地区/类型
        '国产': '华夏', '日韩': '东瀛', '欧美': '西洋', '港台': '香江',
        '动漫': '丹青', '综艺': '百戏', '电视剧': '传奇', '电影': '光影',
        # 其他
        '暴力': '杀伐', '血腥': '殷红', '恐怖': '幽冥', '赌博': '孤注',
        '毒品': '药石', '枪支': '火器', '刀具': '利刃',
        '广告': '告示', '直播': '直播',
    }

    # 未成年相关词（铁律13：命中即跳过不展示）
    # 注意："学生"不纳入——高中生/大学生可能已成年
    MINOR_KEYWORDS = [
        '萝莉', '幼女', '少女', '童贞', '幼齿', '未成年', 'teen', 'loli',
        'schoolgirl', '小女', 'teenie', '幼童', '女童', '男童',
    ]

    def __init__(self):
        self.siteName = '勃士'
        self.rawSite = 'https://ntp.boshi4.help'
        self.basePath = '/cn/home/web'
        self.siteUrl = self.rawSite + self.basePath
        self.HOST = self.siteUrl
        self.proxy = None
        self.ua = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                   'AppleWebKit/537.36 (KHTML, like Gecko) '
                   'Chrome/131.0.0.0 Safari/537.36')
        # 分类列表（十六路，id 21-36）
        self._categories = [
            ('21', '女神学生'),
            ('22', '美女直播'),
            ('23', '人妻系列'),
            ('24', '强奸乱伦'),
            ('25', '自拍偷拍'),
            ('26', '制服诱惑'),
            ('27', '巨乳系列'),
            ('28', '自慰系列'),
            ('29', '国产视频'),
            ('30', '无码视频'),
            ('31', '有码视频'),
            ('32', '中文字幕'),
            ('33', '日韩精品'),
            ('34', '欧美精品'),
            ('35', '动漫精品'),
            ('36', '三级伦理'),
        ]

    # ============================================================
    # 脱敏核心方法
    # ============================================================
    def desensitize(self, text):
        """古典映射脱敏；未成年相关条目返回空字符串（铁律13跳过）"""
        if not text:
            return text
        # 第一步：未成年检测（命中即跳过）
        text_lower = text.lower()
        for kw in self.MINOR_KEYWORDS:
            if kw in text_lower:
                return ''
        # 第二步：古典映射全局替换
        result = text
        for k, v in self.CLASSICAL_MAP.items():
            if k in result:
                result = result.replace(k, v)
        return result

    # ============================================================
    # 13标准接口
    # ============================================================
    def init(self, extend):
        """初始化，支持ext.proxy/ext.siteUrl覆盖，ext.direct直连"""
        if extend:
            try:
                ext = json.loads(extend) if isinstance(extend, str) else extend
                if ext.get('direct'):
                    self.siteUrl = self.rawSite + self.basePath
                    self.HOST = self.siteUrl
                    self.proxy = None
                elif ext.get('proxy'):
                    self.proxy = ext['proxy'].rstrip('/')
                    self.siteUrl = self.proxy + self.basePath
                    self.HOST = self.siteUrl
                elif ext.get('siteUrl'):
                    self.siteUrl = ext['siteUrl'].rstrip('/')
                    self.HOST = self.siteUrl
            except Exception:
                pass
        return None

    def homeContent(self, filter):
        """首页分类 + filters（dict）"""
        classes = []
        filters = {}
        for tid, tname in self._categories:
            dn = self.desensitize(tname)
            if dn == '':
                continue
            classes.append({'type_id': tid, 'type_name': dn})
            # 每个分类配排序筛选
            filters[tid] = [{
                'key': 'by',
                'name': '排序',
                'value': [
                    {'n': '默认', 'v': ''},
                    {'n': '人气', 'v': 'hits'},
                ],
            }]
        return {'class': classes, 'filters': filters}

    def categoryContent(self, tid, pg, filter, extend):
        """分类分页列表"""
        pg = int(pg) if pg else 1
        # 排序筛选
        by_val = ''
        if filter and isinstance(filter, dict):
            by_val = filter.get('by', '') or ''
        if by_val:
            url = (f'{self.siteUrl}/index.php/vod/show/by/{by_val}'
                   f'/id/{tid}/page/{pg}.html')
        else:
            url = f'{self.siteUrl}/index.php/vod/type/id/{tid}/page/{pg}.html'

        html = self._get(url)
        videos = self._parse_video_list(html)
        total, pagecount = self._parse_pagination(html)
        return {
            'page': pg,
            'pagecount': pagecount,
            'limit': 20,
            'total': total,
            'list': videos,
        }

    def detailContent(self, ids):
        """详情（此站无独立详情页，播放页即详情）；ids为list/tuple必须遍历"""
        if isinstance(ids, str):
            ids = [ids]
        results = []
        for vid in ids:
            vid = str(vid)
            url = (f'{self.siteUrl}/index.php/vod/play/id/{vid}'
                   f'/sid/1/nid/1.html')
            html = self._get(url)
            if not html:
                continue
            vod = self._parse_play_page(html, vid)
            if vod:
                results.append(vod)
        return {'list': results}

    def searchContent(self, key, pg):
        """搜索（GET优先，POST兜底）"""
        pg = int(pg) if pg else 1
        encoded = urllib.parse.quote(key)
        url = f'{self.siteUrl}/index.php/vod/search/wd/{encoded}/page/{pg}.html'
        html = self._get(url)
        if not html or 'ul class="videos"' not in html:
            # POST兜底
            html = self._post(
                f'{self.siteUrl}/index.php/vod/search.html',
                {'wd': key},
            )
        videos = self._parse_video_list(html)
        total, pagecount = self._parse_pagination(html)
        return {
            'page': pg,
            'pagecount': pagecount,
            'limit': 20,
            'total': total,
            'list': videos,
        }

    def playerContent(self, flag, id, vipFlags):
        """播放：parse=0直链，header带防盗链"""
        return {
            'parse': 0,
            'jx': 0,
            'url': id,
            'header': {
                'User-Agent': self.ua,
                'Referer': self.rawSite + '/',
                'Origin': self.rawSite,
            },
        }

    def localProxy(self, param):
        """本地代理（空壳，此站m3u8无广告需清洗）"""
        return [404, 'text/plain', '']

    def isVideoFormat(self, url):
        if not url:
            return False
        return url.endswith('.m3u8') or url.endswith('.mp4') or '.m3u8' in url

    def manualVideoCheck(self):
        return False

    def getDependence(self):
        return ''

    def destroy(self):
        pass

    def progressVideo(self, speed, time, end):
        return False

    def setVideoFlags(self, siteKey, flags):
        pass

    # ============================================================
    # 内部辅助方法
    # ============================================================
    def _get(self, url):
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': self.ua,
                'Referer': self.rawSite + '/',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            })
            if self.proxy:
                ph = urllib.request.ProxyHandler({
                    'http': self.proxy, 'https': self.proxy,
                })
                opener = urllib.request.build_opener(ph)
                resp = opener.open(req, timeout=20)
            else:
                resp = urllib.request.urlopen(req, timeout=20)
            data = resp.read()
            # 尝试utf-8，失败则用检测
            try:
                return data.decode('utf-8')
            except UnicodeDecodeError:
                return data.decode('gbk', errors='ignore')
        except Exception:
            return ''

    def _post(self, url, data):
        try:
            encoded = urllib.parse.urlencode(data).encode('utf-8')
            req = urllib.request.Request(url, data=encoded, headers={
                'User-Agent': self.ua,
                'Referer': self.rawSite + '/',
                'Content-Type': 'application/x-www-form-urlencoded',
            })
            resp = urllib.request.urlopen(req, timeout=20)
            return resp.read().decode('utf-8', errors='ignore')
        except Exception:
            return ''

    def _parse_video_list(self, html):
        """解析分类/搜索页的视频列表"""
        videos = []
        if not html:
            return videos
        # 匹配 div.video > a.thumbnail[href=play_url][title=name] > div.video-thumb > img[src=cover]
        pattern = re.compile(
            r'<div class="video">\s*'
            r'<a href="([^"]*vod/play/id/(\d+)[^"]*)"\s+title="([^"]*)"[^>]*>\s*'
            r'<div class="video-thumb">\s*'
            r'<img[^>]*?src="([^"]*)"',
            re.DOTALL,
        )
        for m in pattern.finditer(html):
            vid = m.group(2)
            name = m.group(3).strip()
            cover = m.group(4).strip()
            # 相对封面补全域名
            if cover and cover.startswith('/'):
                cover = self.rawSite + cover
            # 脱敏（未成年返回空则跳过）
            name = self.desensitize(name)
            if name == '':
                continue
            # 提取备注（评分/new标签）
            remarks = ''
            rm = re.search(
                r'<span class="video-rating[^"]*">[^<]*<i[^>]*></i>([^<]+)</span>',
                m.group(0),
            )
            if rm:
                remarks = rm.group(1).strip()
            item = {
                'vod_id': vid,
                'vod_name': name,
                'vod_pic': cover,
            }
            if remarks:
                item['vod_remarks'] = remarks
            videos.append(item)
        return videos

    def _parse_play_page(self, html, vid):
        """解析播放页（兼详情页），提取标题/封面/播放地址"""
        if not html:
            return None
        # 提取player_data中的播放地址
        play_url = ''
        pm = re.search(r'var player_data=({.*?});', html, re.DOTALL)
        if pm:
            try:
                pd = json.loads(pm.group(1))
                play_url = pd.get('url', '').strip()
            except Exception:
                # 手动提取url字段
                um = re.search(r'"url"\s*:\s*"([^"]+)"', pm.group(1))
                if um:
                    play_url = um.group(1).replace('\\/', '/').strip()

        if not play_url:
            return None

        # 提取标题
        title = ''
        tm = re.search(r'<title>在线播放(.*?)\s*第\d+集', html)
        if tm:
            title = tm.group(1).strip()
        else:
            tm2 = re.search(r'<title>(.*?)\s*[-–]\s*', html)
            if tm2:
                title = tm2.group(1).strip()
        if not title:
            title = f'视频_{vid}'

        # 提取封面（og:image 或 页面首个视频缩略图）
        cover = ''
        cm = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', html)
        if cm:
            cover = cm.group(1).strip()
        if not cover:
            # 从相关视频区取第一个封面
            cm2 = re.search(
                r'<div class="video-thumb">\s*<img[^>]*?src="([^"]+)"',
                html,
            )
            if cm2:
                cover = cm2.group(1).strip()
        if cover and cover.startswith('/'):
            cover = self.rawSite + cover

        # 脱敏
        title = self.desensitize(title)
        if title == '':
            return None  # 未成年内容跳过

        return {
            'vod_id': str(vid),
            'vod_name': title,
            'vod_pic': cover,
            'vod_play_from': 'ckplayer',
            'vod_play_url': f'超清${play_url}',
            'vod_content': title,
            'vod_remarks': '',
        }

    def _parse_pagination(self, html):
        """解析分页：总条数 + 总页数"""
        total = 0
        pagecount = 1
        if not html:
            return total, pagecount
        tm = re.search(r'共(\d+)条数据', html)
        if tm:
            total = int(tm.group(1))
        # 尾页链接提取最大页码
        pm = re.search(r'尾页[^>]*href="[^"]*/page/(\d+)\.html"', html)
        if pm:
            pagecount = int(pm.group(1))
        elif total > 0:
            pagecount = (total + 19) // 20
        return total, pagecount
