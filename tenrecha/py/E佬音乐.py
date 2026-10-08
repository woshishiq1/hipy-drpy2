# -*- coding: utf-8 -*-
import json
import sys
import re
import base64
import requests
import urllib.parse
import urllib3

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
sys.path.append('..')
from base.spider import Spider

class Spider(Spider):
    def init(self, extend=""):
        self.host = "https://fy-musicbox-api.mu-jie.cc"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 14; 22127RK46C Build/UKQ1.230804.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/143.0.7499.192 Mobile Safari/537.36',
            'Referer': 'https://mu-jie.cc/musicBox/'
        }

    def getName(self):
        return "E佬音乐"

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def _req(self, url):
        try:
            return requests.get(url, headers=self.headers, verify=False, timeout=15).json()
        except:
            return {}

    # ================= 核心修复：变量名统一，防止报错 =================
    def lrc2ssa(self, lrc_str):
        if not lrc_str:
            return ""
        
        lines = []
        # 优化正则：兼容有无毫秒的情况 [00:00.00] 或 [00:00]
        pattern = re.compile(r'\[(\d{2}):(\d{2})(\.\d+)?\](.*)')
        
        for line in lrc_str.split('\n'):
            match = pattern.search(line)
            if match:
                m, s, ms_str, text = match.groups()
                ms = float(ms_str) if ms_str else 0
                start_time = int(m) * 60 + int(s) + ms
                text = text.strip()
                if text: 
                    # 【修复】这里统一使用 'start' 和 'text'
                    lines.append({'start': start_time, 'text': text})
        
        if not lines:
            return ""

        # 补全结束时间
        for i in range(len(lines)):
            if i < len(lines) - 1:
                lines[i]['end'] = lines[i+1]['start']
            else:
                lines[i]['end'] = lines[i]['start'] + 5.0
            
            if lines[i]['end'] - lines[i]['start'] < 0.1:
                lines[i]['end'] = lines[i]['start'] + 2.0

        # SSA 头部：定义样式
        # T_Act/B_Act: 唱的时候 (黄色 &H0000FFFF)
        # T_Wai/B_Wai: 等的时候 (白色 &H00FFFFFF)
        ssa_header = """[Script Info]
ScriptType: v4.00+
Collisions: Normal
PlayResX: 1920
PlayResY: 1080
Timer: 100.0000

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: T_Act,Roboto,80,&H0000FFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,4,2,1,100,50,50,1
Style: T_Wai,Roboto,80,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,4,2,1,100,50,50,1
Style: B_Act,Roboto,80,&H0000FFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,4,2,3,50,100,50,1
Style: B_Wai,Roboto,80,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,4,2,3,50,100,50,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        events = []
        
        def fmt_time(seconds):
            h = int(seconds // 3600)
            m = int((seconds % 3600) // 60)
            s = int(seconds % 60)
            cs = int((seconds * 100) % 100)
            return f"{h}:{m:02}:{s:02}.{cs:02}"

        # 绝对坐标字符串：左上(100,900) / 右下(1820,1030)
        pos_L = r"{\pos(100,900)}"
        pos_R = r"{\pos(1820,1030)}"

        # 3. 轮替逻辑
        for i in range(len(lines)):
            line = lines[i]
            
            # 偶数行(0,2,4) -> Top轨道
            # 奇数行(1,3,5) -> Btm轨道
            is_top = (i % 2 == 0)
            
            # 1. 计算 "等待期" (White)
            if i < 2:
                time_appear = 0
            else:
                # 【关键修复】使用 line['end'] 访问
                time_appear = lines[i-2]['end']
            
            if time_appear < line['start']:
                # 样式选择：T_Wai 或 B_Wai
                style = "T_Wai" if is_top else "B_Wai"
                pos = pos_L if is_top else pos_R
                # 此时不需要 \kf，因为样式本身就是全白
                events.append(f"Dialogue: 0,{fmt_time(time_appear)},{fmt_time(line['start'])},{style},,0,0,0,,{pos}{line['text']}")

            # 2. 计算 "演唱期" (Yellow Gradient)
            dur = int((line['end'] - line['start']) * 100)
            # 样式选择：T_Act 或 B_Act
            style = "T_Act" if is_top else "B_Act"
            pos = pos_L if is_top else pos_R
            # 添加 \kf 特效，配合 T_Act 的黄主色/白次色，实现渐变
            events.append(f"Dialogue: 1,{fmt_time(line['start'])},{fmt_time(line['end'])},{style},,0,0,0,,{pos}{{\kf{dur}}}{line['text']}")

        return ssa_header + "\n".join(events)

    def homeContent(self, filter):
        cats = {}
        cats['theme'] = [{"n": x, "v": x} for x in ["综艺", "影视原声", "ACG", "儿童", "校园", "游戏", "70后", "80后", "90后", "00后", "网络歌曲", "KTV", "经典", "翻唱", "吉他", "钢琴", "器乐", "榜单"]]
        cats['lang'] = [{"n": x, "v": x} for x in ["华语", "欧美", "日语", "韩语", "粤语"]]
        cats['style'] = [{"n": x, "v": x} for x in ["流行", "摇滚", "民谣", "电子", "舞曲", "说唱", "轻音乐", "爵士", "乡村", "R&B/Soul", "古典", "民族", "英伦", "金属", "朋克", "蓝调", "雷鬼", "世界音乐", "拉丁", "New Age", "古风", "后摇", "Bossa Nova"]]
        cats['scene'] = [{"n": x, "v": x} for x in ["清晨", "夜晚", "学习", "工作", "午休", "下午茶", "地铁", "驾车", "运动", "旅行", "散步", "酒吧"]]
        cats['emotion'] = [{"n": x, "v": x} for x in ["怀旧", "清新", "浪漫", "伤感", "治愈", "放松", "孤独", "感动", "兴奋", "快乐", "安静", "思念"]]

        filters = {}
        for key in cats:
            filters[key] = [{"key": "cat", "name": "分类", "value": cats[key]}]

        classes = [
            {'type_name': '热歌推荐', 'type_id': 'rec'},
            {'type_name': '主题', 'type_id': 'theme'},
            {'type_name': '语种', 'type_id': 'lang'},
            {'type_name': '风格', 'type_id': 'style'},
            {'type_name': '场景', 'type_id': 'scene'},
            {'type_name': '情感', 'type_id': 'emotion'}
        ]
        return {'class': classes, 'filters': filters}

    def homeVideoContent(self):
        return {'list': []}

    def categoryContent(self, tid, pg, filter, extend):
        if pg != '1' and int(pg) > 10:
            return {'list': [], 'page': pg}
        
        try:
            url = ""
            if tid == 'rec':
                url = self.host + "/netease/playlist/recommend?limit=30&page=" + pg
            else:
                defaults = {'theme': '综艺', 'lang': '华语', 'style': '流行', 'scene': '清晨', 'emotion': '怀旧'}
                cat = extend.get('cat', defaults.get(tid))
                url = self.host + "/netease/playlist/category?type=" + urllib.parse.quote(cat) + "&limit=30&page=" + pg
            
            j = self._req(url)
            data_list = []
            if isinstance(j, list):
                data_list = j
            elif isinstance(j, dict) and 'data' in j:
                data_list = j['data']
            
            videos = []
            for d in data_list:
                vid = str(d.get('id', ''))
                pic = d.get('coverImgUrl', '')
                if not pic:
                    pic = d.get('pic', '')
                name = d.get('name', '未知标题')
                remark = "播放: " + str(d.get('playCount', 0))
                
                videos.append({
                    'vod_id': vid + "@@" + pic + "@@" + name,
                    'vod_name': name,
                    'vod_pic': pic,
                    'vod_remarks': remark
                })
            return {'list': videos, 'page': int(pg), 'pagecount': 999, 'limit': 30, 'total': 9999}
        except:
            return {'list': [], 'page': 1}

    def detailContent(self, ids):
        try:
            parts = ids[0].split('@@')
            did = parts[0]
            pic = parts[1] if len(parts) > 1 else ""
            name = parts[2] if len(parts) > 2 else "音乐详情"

            vod = {
                'vod_id': ids[0],
                'vod_name': name,
                'vod_pic': pic,
                'type_name': '音乐',
                'vod_play_from': 'E佬聚合'
            }
            
            song_list = []
            data_obj = None

            # 兼容多种列表接口 (榜单/歌单/专辑)
            api_list = [
                self.host + "/api/?source=netease&id=" + did + "&type=toplist",
                self.host + "/meting/?server=netease&type=playlist&id=" + did,
                self.host + "/api/?source=netease&id=" + did + "&type=album"
            ]

            for api in api_list:
                res = self._req(api)
                if not isinstance(res, dict):
                    continue
                if 'code' in res and res['code'] == 200:
                    d = res.get('data')
                    if d and isinstance(d.get('list'), list):
                        data_obj = d
                        song_list = d['list']
                        break
                if 'tracks' in res:
                    data_obj = res
                    song_list = res['tracks']
                    break

            play_list = []
            if song_list:
                new_name = data_obj.get('name')
                if new_name:
                    vod['vod_name'] = new_name
                desc = data_obj.get('description', '')
                if not desc:
                    desc = data_obj.get('desc', '')
                vod['vod_content'] = desc
                new_pic = data_obj.get('pic')
                if not new_pic:
                    new_pic = data_obj.get('coverImgUrl')
                if new_pic:
                    vod['vod_pic'] = new_pic

                for s in song_list:
                    s_name = s.get('name', '')
                    s_artist = s.get('artist', '')
                    if isinstance(s_artist, list):
                        s_artist = "/".join(s_artist)
                    
                    title = s_name + " - " + s_artist
                    title = title.replace('$', ' ').replace('#', ' ')
                    s_id = str(s.get('id', ''))
                    s_pic = s.get('pic', '')
                    play_list.append(title + "$" + s_id + "@@" + s_pic)
            else:
                play_list.append("播放单曲$" + did + "@@" + pic)

            vod['vod_play_url'] = '#'.join(play_list)
            return {'list': [vod]}
        except:
            return {'list': []}

    def searchContent(self, key, quick, pg="1"):
        try:
            videos = []
            encoded_key = urllib.parse.quote(key)

            # 1. 搜索单曲 (song$)
            url_song = self.host + "/netease/search/song/?keywords=" + encoded_key + "&pn=" + pg + "&limit=20"
            data_song = self._req(url_song)
            if isinstance(data_song, list):
                for d in data_song:
                    vid = str(d.get('id', ''))
                    pic = d.get('pic', '')
                    name = d.get('name', '')
                    artist = d.get('artist', '')
                    # 标识为单曲
                    tag_vid = "song$" + vid
                    videos.append({
                        'vod_id': tag_vid + "@@" + pic + "@@" + name,
                        'vod_name': name,
                        'vod_pic': pic,
                        'vod_remarks': artist
                    })

            # 2. 搜索歌单 (playlist$)
            url_playlist = self.host + "/netease/search/playlist/?keywords=" + encoded_key + "&limit=20"
            data_playlist = self._req(url_playlist)
            if isinstance(data_playlist, list):
                for d in data_playlist:
                    vid = str(d.get('id', ''))
                    pic = d.get('coverImgUrl', '')
                    name = d.get('name', '')
                    count = str(d.get('trackCount', 0))
                    # 标识为歌单
                    tag_vid = "playlist$" + vid
                    videos.append({
                        'vod_id': tag_vid + "@@" + pic + "@@" + name,
                        'vod_name': name,
                        'vod_pic': pic,
                        'vod_remarks': "歌单(" + count + "首)"
                    })

            return {'list': videos, 'page': pg}
        except:
            return {'list': [], 'page': pg}

    def playerContent(self, flag, id, vipFlags):
        res = {
            "parse": 0, 
            "jx": 0, 
            "url": "", 
            "pic": "", 
            "cover": "", 
            "lrc": "", 
            "subt": "", 
            "subs": [], 
            "header": self.headers
        }
        
        real_id = id
        if '@@' in id:
            parts = id.split('@@')
            real_id = parts[0]
            res['pic'] = parts[1] if len(parts) > 1 else ""
            res['cover'] = res['pic']
        
        # 去掉搜索时添加的前缀
        if real_id.startswith("song$"):
            real_id = real_id[5:]
        elif real_id.startswith("playlist$"):
            real_id = real_id[9:]
        
        try:
            lrc_url = self.host + "/meting/?server=netease&type=lrc&id=" + real_id
            r = requests.get(lrc_url, headers=self.headers, verify=False, timeout=5)
            lrc_text = r.text
            if isinstance(lrc_text, str) and '[' in lrc_text:
                res['lrc'] = lrc_text
                ssa = self.lrc2ssa(lrc_text)
                if ssa:
                    b64_ssa = base64.b64encode(ssa.encode('utf-8')).decode('utf-8')
                    res['subs'] = [
                        {"name": "KTV", "url": "data:text/x-ssa;base64," + b64_ssa, "format": "text/x-ssa", "selected": True},
                        {"name": "LRC", "data": lrc_text, "format": "application/lrc"}
                    ]
        except:
            pass

        play_url = self.host + "/meting/?server=netease&type=url&id=" + real_id
        res['url'] = ['E佬音质', play_url]
        return res

    def localProxy(self, param):
        pass
