# -*- coding: utf-8 -*-
import json
import sys
import time
import requests
sys.path.append('..')
from base.spider import Spider


class Spider(Spider):
    """
    配置示例：
    {
        "key": "kuwo_listen",
        "name": "听了么[听]",
        "type": 3,
        "api": ".所在路径/听了么.py",
        "searchable": 1,
        "quickSearch": 1,
        "filterable": 1,
        "changeable": 1
    }
    """

    def init(self, extend=""):
        pass

    def getName(self):
        return "听了么[听]"

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def destroy(self):
        pass

    def homeContent(self, filter):
        result = {}
        classes = [
            {'type_id': 'hot', 'type_name': '热门歌单'},
            {'type_id': 'new', 'type_name': '新歌推荐'}
        ]
        result['class'] = classes
        result['filters'] = {}
        return result

    def homeVideoContent(self):
        url = 'http://wapi.kuwo.cn/api/pc/classify/playlist/getRcmPlayList?loginUid=0&loginSid=0&appUid=76039576&rn=30&order=hot&pn=1'
        try:
            res = self.fetch(url)
            data = res.json()
            data_list = data.get('data', {}).get('data', []) or data.get('data', []) or []
            vods = self._parse_playlist(data_list, 'hot')
            return {'list': vods}
        except Exception as e:
            print(f"homeVideoContent error: {e}")
            return {'list': []}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            api_url = f"http://wapi.kuwo.cn/api/pc/classify/playlist/getRcmPlayList?loginUid=0&loginSid=0&appUid=76039576&rn=30&order={tid}&pn={pg}&_={int(time.time()*1000)}"
            res = self.fetch(api_url)
            data = res.json()
            data_list = data.get('data', {}).get('data', []) or data.get('data', []) or []
            vods = self._parse_playlist(data_list, tid)
            return {
                'list': vods,
                'page': pg,
                'pagecount': 999,
                'limit': 30,
                'total': 999999
            }
        except Exception as e:
            print(f"categoryContent error: {e}")
            return {'list': [], 'page': pg, 'pagecount': 0, 'limit': 30, 'total': 0}

    def detailContent(self, ids):
        try:
            pid = ids[0].strip()
            api_url = f"http://nplserver.kuwo.cn/pl.svc?op=getlistinfo&pid={pid}&pn=0&rn=200&encode=utf8&keyset=pl2012&identity=kuwo&pcmp4=1&vipver=MUSIC_9.1.1.2_BCS2&newver=1"
            res = self.fetch(api_url)
            d = res.json()
            
            music_list = d.get('musiclist', [])
            play_arr = []
            artist_pic_arr = []
            
            for it in music_list:
                rid = str(it.get('id', '')) if it.get('id') is not None else ''
                song = str(it.get('name', it.get('SONGNAME', it.get('displaysongname', ''))))
                artist = str(it.get('artist', it.get('ARTIST', it.get('FARTIST', it.get('displayartistname', '')))))
                albumpic = it.get('albumpic', '')
                artist_pic = it.get('artistPic', '')
                
                if rid:
                    display_name = f"{song} [{artist}]" if artist else song
                    play_arr.append(f"{display_name}${rid}&&{albumpic}&&{artist_pic}")
                    artist_pic_arr.append(artist_pic)
            
            vod = {
                'vod_id': pid,
                'vod_name': d.get('name', d.get('title', '酷我歌单')),
                'vod_pic': d.get('pic', d.get('img', '')),
                'vod_content': d.get('info', d.get('desc', '')),
                'vod_play_from': '酷我歌单',
                'vod_play_pic': '#'.join(artist_pic_arr),
                'vod_play_pic_ratio': 1.5,
                'vod_play_url': '#'.join(play_arr)
            }
            return {'list': [vod]}
        except Exception as e:
            print(f"detailContent error: {e}")
            return {'list': []}

    def playerContent(self, flag, id, vipFlags):
        try:
            parts = id.split('&&')
            first_part = parts[0] if len(parts) > 0 else ''
            first_parts = first_part.split('$')
            song_id = first_parts[1] if len(first_parts) > 1 else first_parts[0]
            
            album_pic = parts[1] if len(parts) > 1 else ''
            artist_pic = parts[2] if len(parts) > 2 else ''
            pic_url = album_pic or artist_pic
            
            # 检查是否是直接链接
            if any(ext in song_id.lower() for ext in ['.m3u8', '.mp4', '.m4a', '.mp3', '.aac']):
                return {
                    'parse': 0,
                    'jx': 0,
                    'url': song_id,
                    'pic': pic_url
                }
            
            # 获取歌曲播放地址
            url = self._get_song_url(song_id, '320kmp3')
            if not url:
                url = self._get_song_url(song_id, '128kmp3')
            
            # 获取歌词
            lrc = self._get_lyric(song_id)
            
            return {
                'parse': 0,
                'jx': 0,
                'url': url,
                'pic': pic_url,
                'cover': album_pic,
                'lrc': lrc
            }
        except Exception as e:
            print(f"playerContent error: {e}")
            return {'parse': 0, 'jx': 0, 'url': '', 'pic': ''}

    def searchContent(self, key, quick, pg="1"):
        try:
            search_url = f"https://search.kuwo.cn/r.s?client=kt&all={key}&pn=0&rn=20&vipver=1&ft=music&encoding=utf8&rformat=json&mobi=1"
            res = self.fetch(search_url)
            
            # 处理可能的非JSON响应
            content = res.text
            if content.startswith('try{'):
                content = content[4:]
            if content.endswith('}catch(e){}'):
                content = content[:-11]
            if content.startswith('jsonp'):
                content = content.split('(', 1)[1].rsplit(')', 1)[0]
            
            json_data = json.loads(content)
            data_list = []
            
            abslist = json_data.get('abslist', [])
            for it in abslist:
                music_rid = it.get('MUSICRID', '')
                if music_rid:
                    song_id = music_rid.replace('MUSIC_', '')
                    pic_url = it.get('hts_MVPIC', '')
                    song_name = it.get('NAME', '未知歌曲')
                    artist = it.get('ARTIST', '')
                    display_name = f"{song_name} - {artist}" if artist else song_name
                    
                    data_list.append({
                        'vod_name': display_name,
                        'vod_id': song_id,
                        'vod_pic': pic_url,
                        'vod_remarks': '酷我音乐',
                        'type_name': 'search'
                    })
            
            return {'list': data_list, 'page': pg}
        except Exception as e:
            print(f"searchContent error: {e}")
            return {'list': [], 'page': pg}

    def localProxy(self, param):
        pass

    def _parse_playlist(self, data_list, type_name):
        """解析歌单列表数据"""
        vods = []
        for it in data_list:
            name = it.get('name', it.get('title', '未命名歌单'))
            vid = str(it.get('id', it.get('pid', '')))
            pic = it.get('img', it.get('pic', it.get('cover', 'https://p1.music.126.net/SUeqMM8HOIpHv9Nhl9qt9w==/109951165647004069.jpg')))
            remarks = it.get('info', it.get('uname', it.get('userName', '')))
            
            vods.append({
                'vod_name': name,
                'vod_id': vid,
                'vod_pic': pic,
                'vod_remarks': remarks,
                'type_name': type_name
            })
        return vods

    def _get_song_url(self, rid, br):
        """获取歌曲播放地址"""
        try:
            api_url = f"http://nmobi.kuwo.cn/mobi.s?f=web&user=0&source=kwplayerhd_ar_4.3.0.8_tianbao_T1A_qirui.apk&type=convert_url_with_sign&rid={rid}&br={br}"
            res = self.fetch(api_url)
            data = res.json()
            return data.get('data', {}).get('url', '').strip()
        except Exception:
            return ''

    def _get_lyric(self, rid):
        """获取歌词"""
        try:
            url = f"http://m.kuwo.cn/newh5/singles/songinfoandlrc?musicId={rid}"
            res = self.fetch(url)
            json_data = res.json()
            lrclist = json_data.get('data', {}).get('lrclist', [])
            if not lrclist:
                return ''
            
            lrc_lines = []
            for item in lrclist:
                time_val = float(item.get('time', 0))
                minute = int(time_val // 60)
                second = int(time_val % 60)
                millisecond = int((time_val % 1) * 100)
                lrc_lines.append(f"[{minute:02d}:{second:02d}.{millisecond:02d}]{item.get('lineLyric', '')}")
            return '\n'.join(lrc_lines)
        except Exception:
            return ''

    def fetch(self, url, headers=None, timeout=10):
        """请求方法"""
        default_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Referer': 'http://www.kuwo.cn/'
        }
        if headers:
            default_headers.update(headers)
        response = requests.get(url, headers=default_headers, timeout=timeout)
        return response