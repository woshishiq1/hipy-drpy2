#coding=utf-8
#!/usr/bin/python
import sys
import json
import time
import random
import requests
import threading
from uuid import uuid4
from urllib.parse import quote

def _local_device_id():
    try:
        from java import jclass
        ActivityThread = jclass('android.app.ActivityThread')
        SettingsSecure = jclass('android.provider.Settings$Secure')
        context = ActivityThread.currentApplication()
        value = SettingsSecure.getString(context.getContentResolver(), 'android_id')
        if value and str(value) != '9774d56d682e549c':
            return 'android-' + str(value)
        prefs = context.getSharedPreferences('emby_device_identity', 0)
        value = prefs.getString('device_id', '')
        if not value:
            value = 'local-' + str(uuid4())
            prefs.edit().putString('device_id', value).apply()
        return str(value)
    except Exception:
        return 'session-' + str(uuid4())

sys.path.append('..')
from base.spider import Spider

class Spider(Spider):
    def getName(self):
        return "EMBY"

    def init(self, extend):
        self.direct_credential_lock = threading.Lock()
        self.direct_usage_lock = threading.Lock()
        try:
            extendDict = json.loads(extend)
            self.credentialUrl = extendDict['server'].strip('/')
            self.usageUrl = str(extendDict.get('usage') or '').strip('/')
            self.baseUrl = self.credentialUrl
            self.username = extendDict['username']
            self.password = extendDict['password']
            self.proxy = extendDict['proxy']
            self.thread = extendDict['thread'] if 'thread' in extendDict else 0
            self.device_id = _local_device_id()
            self.client = extendDict.get('client', 'Hills Windows')
            self.device_name = extendDict.get('device_name', 'My Computer')
            self.client_version = extendDict.get('client_version', '0.3.2')
            self.direct_expires_at = 0
            self.direct_usage_recorded = False
        except:
            self.credentialUrl = ''
            self.usageUrl = ''
            self.direct_expires_at = 0
            self.baseUrl = ''
            self.username = ''
            self.password = ''
            self.proxy = ''
            self.thread = 0
            self.device_id = _local_device_id()
            self.client = 'Hills Windows'
            self.device_name = 'My Computer'
            self.client_version = '0.3.2'
            self.direct_usage_recorded = False
        
        # 初始化header
        self.header = {
            "User-Agent": f"{self.client}/{self.client_version}".replace(' ', '-'),  # 替换空格为连字符
            "X-Emby-Client": self.client,
            "X-Emby-Device-Name": self.device_name,
            "X-Emby-Device-Id": self.device_id,
            "X-Emby-Client-Version": self.client_version
        }
        
        # 初始化播放会话字典
        self.play_sessions = {}

    def _load_direct_credential(self):
        with self.direct_credential_lock:
            now = int(time.time())
            if self.direct_expires_at > now + 300 and self.baseUrl and self.username and self.password:
                return

            cache_key = 'emby_direct_' + self.credentialUrl + '_' + self.device_id
            cached = self.getCache(cache_key)
            cached_valid = isinstance(cached, dict) and int(cached.get('expires_at') or 0) > now + 300
            try:
                response = requests.get(
                    self.credentialUrl,
                    headers={
                        'X-Emby-Device-Id': self.device_id,
                        'X-Emby-Client': self.client,
                        'X-Emby-Device-Name': self.device_name,
                        'X-Emby-Client-Version': self.client_version
                    },
                    timeout=30
                )
                response.raise_for_status()
                credential = response.json()
                self.baseUrl = str(credential['server']).rstrip('/')
                self.username = str(credential['username'])
                self.password = str(credential['password'])
                self.direct_expires_at = int(credential['expires_at'])
                self.setCache(cache_key, credential)
                return
            except Exception:
                if not cached_valid:
                    raise

            if cached_valid:
                self.baseUrl = str(cached.get('server') or '').rstrip('/')
                self.username = str(cached.get('username') or '')
                self.password = str(cached.get('password') or '')
                if self.baseUrl and self.username and self.password:
                    self.direct_expires_at = int(cached.get('expires_at') or 0)
                    return

    def _record_direct_usage(self):
        if not self.usageUrl or self.direct_usage_recorded:
            return
        with self.direct_usage_lock:
            if self.direct_usage_recorded:
                return
            response = requests.post(
                self.usageUrl,
                headers={
                    'X-Emby-Device-Id': self.device_id,
                    'X-Emby-Client': self.client,
                    'X-Emby-Device-Name': self.device_name,
                    'X-Emby-Client-Version': self.client_version
                },
                timeout=30
            )
            response.raise_for_status()
            self.direct_usage_recorded = True

    def destroy(self):
        # 清理所有播放会话
        for session_id in list(self.play_sessions.keys()):
            self._record_playback_stop(session_id)
        self.play_sessions.clear()

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def _format_size(self, value):
        try:
            size = int(float(value or 0))
        except (TypeError, ValueError):
            return ''
        if size <= 0:
            return ''
        units = ('B', 'KB', 'MB', 'GB', 'TB')
        index = 0
        amount = float(size)
        while amount >= 1024 and index < len(units) - 1:
            amount /= 1024.0
            index += 1
        return f'{int(amount)} {units[index]}' if index == 0 else f'{amount:.1f} {units[index]}'

    def _format_bitrate(self, value):
        try:
            bitrate = float(value or 0)
        except (TypeError, ValueError):
            return ''
        if bitrate <= 0:
            return ''
        if bitrate >= 1000000:
            return f'{bitrate / 1000000:.1f} Mbps'
        if bitrate >= 1000:
            return f'{bitrate / 1000:.0f} kbps'
        return f'{int(bitrate)} bps'

    def _format_frame_rate(self, value):
        raw = str(value or '').strip()
        if not raw:
            return ''
        try:
            if '/' in raw:
                numerator, denominator = raw.split('/', 1)
                rate = float(numerator) / float(denominator)
            else:
                rate = float(raw)
        except (TypeError, ValueError, ZeroDivisionError):
            return ''
        if rate <= 0:
            return ''
        return f'{rate:.3f}'.rstrip('0').rstrip('.')

    def _media_source(self, item):
        for source in item.get('MediaSources') or []:
            if isinstance(source, dict):
                return source
        return {}

    def _poster_size(self, item):
        source = self._media_source(item)
        return self._format_size(source.get('Size') or item.get('Size'))

    def _poster_remark(self, item):
        year = item.get('ProductionYear')
        return str(year) if year else ''

    def _poster_url(self, item, access_token):
        image_tag = (item.get('ImageTags') or {}).get('Primary')
        if not image_tag:
            return ''
        return f'{self.baseUrl}/emby/Items/{item["Id"]}/Images/Primary?maxWidth=400&tag={quote(str(image_tag))}&quality=90&api_key={quote(access_token)}'

    def _media_text(self, item):
        source = self._media_source(item)
        streams = source.get('MediaStreams') or item.get('MediaStreams') or []
        video = next((stream for stream in streams if isinstance(stream, dict) and stream.get('Type') == 'Video'), {})
        size = self._format_size(source.get('Size') or item.get('Size'))
        codec = str(video.get('Codec') or '').upper()
        container = str(source.get('Container') or item.get('Container') or '').upper()
        width = video.get('Width')
        height = video.get('Height')
        resolution = f'{width}x{height}' if width and height else ''
        frame_rate = self._format_frame_rate(video.get('RealFrameRate') or video.get('AverageFrameRate'))
        bitrate = self._format_bitrate(video.get('BitRate') or source.get('Bitrate') or item.get('Bitrate') or item.get('BitRate'))

        lines = ['媒体信息']
        if size:
            lines.append(f'大小: {size}')
        video_info = ' · '.join(part for part in (codec, resolution, f'{frame_rate} fps' if frame_rate else '') if part)
        if video_info:
            lines.append(f'视频: {video_info}')
        if bitrate:
            lines.append(f'码率: {bitrate}')
        if container:
            lines.append(f'封装: {container}')
        return '\n'.join(lines) if len(lines) > 1 else ''

    def homeContent(self, filter):
        try:
            embyInfos = self.getAccessToken()
        except:
            return {'msg': '获取Emby服务器信息出错'}

        header = self.header.copy()
        header['Content-Type'] = "application/json; charset=UTF-8"
        url = f"{self.baseUrl}/emby/Users/{embyInfos['User']['Id']}/Views"
        params = {
            "X-Emby-Client": self.client,
            "X-Emby-Device-Name": self.device_name,
            "X-Emby-Device-Id": self.device_id,
            "X-Emby-Client-Version": self.client_version,
            "X-Emby-Token": embyInfos['AccessToken']
        }
        r = requests.get(url, params=params, headers=header, timeout=120, proxies={"http": self.proxy, "https": self.proxy})
        typeInfos = r.json()["Items"]
        classList = []
        for typeInfo in typeInfos:
            if "播放列表" in typeInfo['Name'] or '相机' in typeInfo['Name']:
                continue
            classList.append({"type_name": typeInfo['Name'], "type_id": typeInfo['Id']})
        result = {'class': classList}
        return result

    def homeVideoContent(self):
        return {}

    def categoryContent(self, cid, page, filter, ext):
        try:
            self._record_direct_usage()
            embyInfos = self.getAccessToken()
        except:
            return {'list': [], 'msg': '获取Emby服务器信息出错'}

        result = {}
        page = int(page)
        header = self.header.copy()
        header['Content-Type'] = "application/json; charset=UTF-8"
        url = f"{self.baseUrl}/emby/Users/{embyInfos['User']['Id']}/Items"
        params = {
            "X-Emby-Client": self.client,
            "X-Emby-Device-Name": self.device_name,
            "X-Emby-Device-Id": self.device_id,
            "X-Emby-Client-Version": self.client_version,
            "X-Emby-Token": embyInfos['AccessToken'],
            "SortBy": "DateLastContentAdded,SortName",
            "IncludeItemTypes": "Movie,Series",
            "SortOrder": "Descending",
            "ParentId": cid,
            "Recursive": "true",
            "Limit": "30",
            "ImageTypeLimit": 1,
            "StartIndex": str((page - 1) * 30),
            "EnableImageTypes": "Primary,Backdrop,Thumb,Banner",
            "Fields": "BasicSyncInfo,CanDelete,Container,PrimaryImageAspectRatio,ProductionYear,CommunityRating,Status,CriticRating,EndDate,Path,MediaSources,Size",
            "EnableUserData": "true"
        }
        r = requests.get(url, params=params, headers=header, timeout=120, proxies={"http": self.proxy, "https": self.proxy})
        videoList = r.json()['Items']
        videos = []
        for video in videoList:
            name = self.cleanText(video['Name'])
            videos.append({
                "vod_id": video['Id'],
                "vod_name": name,
                "vod_pic": self._poster_url(video, embyInfos['AccessToken']),
                "vod_year": self._poster_size(video),
                "vod_remarks": self._poster_remark(video)
            })
        result['list'] = videos
        result['page'] = page
        result['pagecount'] = page + 1 if page * 30 < int(r.json()['TotalRecordCount']) else page
        result['limit'] = len(videos)
        result['total'] = int(r.json()['TotalRecordCount']) if "TotalRecordCount" in r.json() else 0
        return result

    def detailContent(self, did):
        try:
            self._record_direct_usage()
            embyInfos = self.getAccessToken()
        except:
            return {'list': [], 'msg': '获取Emby服务器信息出错'}

        header = self.header.copy()
        header['Content-Type'] = "application/json; charset=UTF-8"
        url = f"{self.baseUrl}/emby/Users/{embyInfos['User']['Id']}/Items/{did[0]}"
        params = {
            "X-Emby-Client": self.client,
            "X-Emby-Device-Name": self.device_name,
            "X-Emby-Device-Id": self.device_id,
            "X-Emby-Client-Version": self.client_version,
            "X-Emby-Token": embyInfos['AccessToken'],
            "Fields": "MediaSources,MediaStreams,Container,Size,Path"
        }
        r = requests.get(url, params=params, headers=header, timeout=120, proxies={"http": self.proxy, "https": self.proxy})
        videoInfos = r.json()
        overview = videoInfos.get('Overview', '').replace('\xa0', ' ').replace('\n\n', '\n').strip()
        media_text = self._media_text(videoInfos)
        vod = {
            "vod_id": did[0],
            "vod_name": videoInfos['Name'],
            "vod_pic": self._poster_url(videoInfos, embyInfos['AccessToken']),
            "type_name": videoInfos['Genres'][0] if len(videoInfos['Genres']) > 0 else '',
            "vod_year": self._poster_size(videoInfos),
            "vod_remarks": self._poster_remark(videoInfos),
            "vod_content": '\n\n'.join(part for part in (media_text, overview) if part),
            "vod_play_from": "EMBY"
        }
        playUrl = ''
        if not videoInfos['IsFolder']:
            playUrl += f"{videoInfos['Name'].strip()}${videoInfos['Id']}#"
        else:
            url = f"{self.baseUrl}/emby/Shows/{did[0]}/Seasons"
            params.update(
                {
                    "UserId": embyInfos['User']['Id'],
                    "EnableImages": "true",
                    "Fields": "BasicSyncInfo,CanDelete,Container,PrimaryImageAspectRatio,ProductionYear,CommunityRating",
                    "EnableUserData": "true",
                    "EnableTotalRecordCount": "false"
                }
            )
            r = requests.get(url, params=params, headers=header, timeout=120, proxies={"http": self.proxy, "https": self.proxy})
            if r.status_code == 200:
                playInfos = r.json()['Items']
                for playInfo in playInfos:
                    url = f"{self.baseUrl}/emby/Shows/{playInfo['Id']}/Episodes"
                    params.update(
                        {
                            "SeasonId": playInfo['Id'],
                            "Fields": "BasicSyncInfo,CanDelete,CommunityRating,PrimaryImageAspectRatio,ProductionYear,Overview"
                        }
                    )
                    r = requests.get(url, params=params, headers=header, timeout=120, proxies={"http": self.proxy, "https": self.proxy})
                    videoList = r.json()['Items']
                    for video in videoList:
                        playUrl += f"{playInfo['Name'].replace('#', '-').replace('$', '|').strip()}|{video['Name'].strip()}${video['Id']}#"
            else:
                url = f"{self.baseUrl}/emby/Users/{embyInfos['User']['Id']}/Items"
                params = {
                    "ParentId": did[0],
                    "Fields": "BasicSyncInfo,CanDelete,Container,PrimaryImageAspectRatio,ProductionYear,CommunityRating,CriticRating",
                    "ImageTypeLimit": "1",
                    "StartIndex": "0",
                    "EnableUserData": "true",
                    "X-Emby-Client": self.client,
                    "X-Emby-Device-Name": self.device_name,
                    "X-Emby-Device-Id": self.device_id,
                    "X-Emby-Client-Version": self.client_version,
                    "X-Emby-Token": embyInfos['AccessToken']
                }
                r = requests.get(url, params=params, headers=header, timeout=120, proxies={"http": self.proxy, "https": self.proxy})
                videoList = r.json()['Items']
                for video in videoList:
                    playUrl += f"{video['Name'].replace('#', '-').replace('$', '|').strip()}${video['Id']}#"
        vod['vod_play_url'] = playUrl.strip('#')
        result = {'list': [vod]}
        return result

    def searchContent(self, key, quick, pg="1"):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, keywords, quick, page):
        try:
            embyInfos = self.getAccessToken()
        except:
            return {'list': [], 'msg': '获取Emby服务器信息出错'}
        page = int(page)
        header = self.header.copy()
        header['Content-Type'] = "application/json; charset=UTF-8"
        url = f"{self.baseUrl}/emby/Users/{embyInfos['User']['Id']}/Items"
        params = {
            "X-Emby-Client": self.client,
            "X-Emby-Device-Name": self.device_name,
            "X-Emby-Device-Id": self.device_id,
            "X-Emby-Client-Version": self.client_version,
            "X-Emby-Token": embyInfos['AccessToken'],
            "SortBy": "SortName",
            "SortOrder": "Ascending",
            "Fields": "BasicSyncInfo,CanDelete,Container,PrimaryImageAspectRatio,ProductionYear,Status,EndDate,MediaSources,Size",
            "StartIndex": str(((page-1)*50)),
            "EnableImageTypes": "Primary,Backdrop,Thumb",
            "ImageTypeLimit": "1",
            "Recursive": "true",
            "SearchTerm": keywords,
            "IncludeItemTypes": "Movie,Series,BoxSet",
            "GroupProgramsBySeries": "true",
            "Limit": "50",
            "EnableTotalRecordCount": "true"
        }
        r = requests.get(url, params=params, headers=header, timeout=120, proxies={"http": self.proxy, "https": self.proxy})

        videos = []
        vodList = r.json()['Items']
        for vod in vodList:
            sid = vod['Id']
            name = self.cleanText(vod['Name'])
            pic = self._poster_url(vod, embyInfos['AccessToken'])
            videos.append({
                "vod_id": sid,
                "vod_name": name,
                "vod_pic": pic,
                "vod_year": self._poster_size(vod),
                "vod_remarks": self._poster_remark(vod)
            })
        result = {'list': videos}
        return result

    def playerContent(self, flag, pid, vipFlags):
        try:
            self._record_direct_usage()
            embyInfos = self.getAccessToken()
        except:
            return {'list': [], 'msg': '获取Emby服务器信息出错'}

        header = self.header.copy()
        header['Content-Type'] = "application/json; charset=UTF-8"
        
        # 获取播放信息
        url = f"{self.baseUrl}/emby/Items/{pid}/PlaybackInfo"
        params = {
            "UserId": embyInfos['User']['Id'],
            "IsPlayback": "false",
            "AutoOpenLiveStream": "false",
            "StartTimeTicks": 0,
            "MaxStreamingBitrate": "2147483647",
            "X-Emby-Client": self.client,
            "X-Emby-Device-Name": self.device_name,
            "X-Emby-Device-Id": self.device_id,
            "X-Emby-Client-Version": self.client_version,
            "X-Emby-Token": embyInfos['AccessToken']
        }
        data = "{\"DeviceProfile\":{\"SubtitleProfiles\":[{\"Method\":\"Embed\",\"Format\":\"ass\"},{\"Format\":\"ssa\",\"Method\":\"Embed\"},{\"Format\":\"subrip\",\"Method\":\"Embed\"},{\"Format\":\"sub\",\"Method\":\"Embed\"},{\"Method\":\"Embed\",\"Format\":\"pgssub\"},{\"Format\":\"subrip\",\"Method\":\"External\"},{\"Method\":\"External\",\"Format\":\"sub\"},{\"Method\":\"External\",\"Format\":\"ass\"},{\"Format\":\"ssa\",\"Method\":\"External\"},{\"Method\":\"External\",\"Format\":\"vtt\"},{\"Method\":\"External\",\"Format\":\"ass\"},{\"Format\":\"ssa\",\"Method\":\"External\"}],\"CodecProfiles\":[{\"Codec\":\"h264\",\"Type\":\"Video\",\"ApplyConditions\":[{\"Property\":\"IsAnamorphic\",\"Value\":\"true\",\"Condition\":\"NotEquals\",\"IsRequired\":false},{\"IsRequired\":false,\"Value\":\"high|main|baseline|constrained baseline\",\"Condition\":\"EqualsAny\",\"Property\":\"VideoProfile\"},{\"IsRequired\":false,\"Value\":\"80\",\"Condition\":\"LessThanEqual\",\"Property\":\"VideoLevel\"},{\"IsRequired\":false,\"Value\":\"true\",\"Condition\":\"NotEquals\",\"Property\":\"IsInterlaced\"}]},{\"Codec\":\"hevc\",\"ApplyConditions\":[{\"Property\":\"IsAnamorphic\",\"Value\":\"true\",\"Condition\":\"NotEquals\",\"IsRequired\":false},{\"IsRequired\":false,\"Value\":\"high|main|main 10\",\"Condition\":\"EqualsAny\",\"Property\":\"VideoProfile\"},{\"Property\":\"VideoLevel\",\"Value\":\"175\",\"Condition\":\"LessThanEqual\",\"IsRequired\":false},{\"IsRequired\":false,\"Value\":\"true\",\"Condition\":\"NotEquals\",\"Property\":\"IsInterlaced\"}],\"Type\":\"Video\"}],\"MaxStreamingBitrate\":40000000,\"TranscodingProfiles\":[{\"Container\":\"ts\",\"AudioCodec\":\"aac,mp3,wav,ac3,eac3,flac,opus\",\"VideoCodec\":\"hevc,h264,mpeg4\",\"BreakOnNonKeyFrames\":true,\"Type\":\"Video\",\"MaxAudioChannels\":\"6\",\"Protocol\":\"hls\",\"Context\":\"Streaming\",\"MinSegments\":2}],\"DirectPlayProfiles\":[{\"Container\":\"mov,mp4,mkv,hls,webm\",\"Type\":\"Video\",\"VideoCodec\":\"h264,hevc,dvhe,dvh1,h264,hevc,hev1,mpeg4,vp9\",\"AudioCodec\":\"aac,mp3,wav,ac3,eac3,flac,truehd,dts,dca,opus,pcm,pcm_s24le\"}],\"ResponseProfiles\":[{\"MimeType\":\"video/mp4\",\"Type\":\"Video\",\"Container\":\"m4v\"}],\"ContainerProfiles\":[],\"MusicStreamingTranscodingBitrate\":40000000,\"MaxStaticBitrate\":40000000}}"
        r = requests.post(url, params=params, data=data, headers=header, timeout=120, proxies={"http": self.proxy, "https": self.proxy})
        
        # 获取播放URL
        media_sources = r.json()['MediaSources']
        if not media_sources:
            return {'list': [], 'msg': '没有可用的媒体源'}
            
        # 使用第一个媒体源
        media_source = media_sources[0]
        direct_stream_url = media_source.get('DirectStreamUrl')
        
        if not direct_stream_url:
            return {'list': [], 'msg': '无法获取播放URL'}
            
        url = self.baseUrl + direct_stream_url
        
        # 记录播放开始
        try:
            session_id = self._record_playback_start(embyInfos, pid, media_source)
            # 启动播放进度更新线程
            self._start_progress_updater(embyInfos, pid, media_source, session_id)
        except Exception as e:
            print(f"记录播放开始失败: {e}")
        
        if int(self.thread) > 0:
            try:
                self.fetch('http://127.0.0.1:7777', timeout=120)
            except:
                self.fetch('http://127.0.0.1:9978/go')
            url = f'http://127.0.0.1:7777/?url={quote(url)}&thread={self.thread}'
            
        result = {
            "url": url,
            "header": self.header,
            "parse": 0
        }
        return result

    def _record_playback_start(self, embyInfos, item_id, media_source):
        """记录播放开始"""
        header = self.header.copy()
        header['Content-Type'] = "application/json; charset=UTF-8"
        
        # 添加认证头
        header.update({
            "X-Emby-Client": self.client,
            "X-Emby-Device-Name": self.device_name,
            "X-Emby-Device-Id": self.device_id,
            "X-Emby-Client-Version": self.client_version,
            "X-Emby-Token": embyInfos['AccessToken']
        })
        
        # 生成唯一的会话ID
        session_id = f"session_{int(time.time())}_{random.randint(1000, 9999)}"
        
        # 构建播放开始数据
        play_data = {
            "ItemId": item_id,
            "MediaSourceId": media_source.get('Id'),
            "CanSeek": True,
            "IsPaused": False,
            "IsMuted": False,
            "PositionTicks": 0,
            "PlayMethod": "DirectStream",
            "PlaySessionId": session_id,
            "LiveStreamId": None,
            "AudioStreamIndex": 1,
            "SubtitleStreamIndex": -1,
            "VolumeLevel": 100,
            "PlaybackStartTimeTicks": int(time.time() * 10000000)
        }
        
        # 发送播放开始请求
        play_url = f"{self.baseUrl}/Sessions/Playing"
        try:
            response = requests.post(
                play_url, 
                json=play_data, 
                headers=header, 
                timeout=5, 
                proxies={"http": self.proxy, "https": self.proxy}
            )
            if response.status_code == 200 or response.status_code == 204:
                print(f"播放开始记录成功: {response.status_code}")
                # 保存会话信息
                self.play_sessions[session_id] = {
                    'embyInfos': embyInfos,
                    'item_id': item_id,
                    'media_source': media_source,
                    'start_time': time.time(),
                    'last_update': time.time()
                }
                return session_id
            else:
                print(f"播放开始记录失败: {response.status_code}, {response.text}")
                return None
        except Exception as e:
            print(f"播放开始记录请求异常: {e}")
            return None

    def _record_playback_progress(self, embyInfos, item_id, media_source, session_id, position_seconds):
        """记录播放进度"""
        header = self.header.copy()
        header['Content-Type'] = "application/json; charset=UTF-8"
        
        # 添加认证头
        header.update({
            "X-Emby-Client": self.client,
            "X-Emby-Device-Name": self.device_name,
            "X-Emby-Device-Id": self.device_id,
            "X-Emby-Client-Version": self.client_version,
            "X-Emby-Token": embyInfos['AccessToken']
        })
        
        # 构建播放进度数据
        progress_data = {
            "ItemId": item_id,
            "MediaSourceId": media_source.get('Id'),
            "PositionTicks": int(position_seconds * 10000000),  # 转换为ticks
            "IsPaused": False,
            "PlaySessionId": session_id,
            "EventName": "timeupdate"
        }
        
        # 发送播放进度请求
        progress_url = f"{self.baseUrl}/Sessions/Playing/Progress"
        try:
            response = requests.post(
                progress_url, 
                json=progress_data, 
                headers=header, 
                timeout=5, 
                proxies={"http": self.proxy, "https": self.proxy}
            )
            if response.status_code == 200 or response.status_code == 204:
                print(f"播放进度更新成功: {position_seconds}秒")
                return True
            else:
                print(f"播放进度更新失败: {response.status_code}, {response.text}")
                return False
        except Exception as e:
            print(f"播放进度更新请求异常: {e}")
            return False

    def _record_playback_stop(self, session_id):
        """记录播放停止"""
        if session_id not in self.play_sessions:
            return False
            
        session_info = self.play_sessions[session_id]
        embyInfos = session_info['embyInfos']
        item_id = session_info['item_id']
        media_source = session_info['media_source']
        total_duration = time.time() - session_info['start_time']
        
        header = self.header.copy()
        header['Content-Type'] = "application/json; charset=UTF-8"
        
        # 添加认证头
        header.update({
            "X-Emby-Client": self.client,
            "X-Emby-Device-Name": self.device_name,
            "X-Emby-Device-Id": self.device_id,
            "X-Emby-Client-Version": self.client_version,
            "X-Emby-Token": embyInfos['AccessToken']
        })
        
        # 构建播放停止数据
        stop_data = {
            "ItemId": item_id,
            "MediaSourceId": media_source.get('Id'),
            "PositionTicks": int(total_duration * 10000000),  # 转换为ticks
            "PlaySessionId": session_id
        }
        
        # 发送播放停止请求
        stop_url = f"{self.baseUrl}/Sessions/Playing/Stopped"
        try:
            response = requests.post(
                stop_url, 
                json=stop_data, 
                headers=header, 
                timeout=5, 
                proxies={"http": self.proxy, "https": self.proxy}
            )
            if response.status_code == 200 or response.status_code == 204:
                print(f"播放停止记录成功: 总时长 {total_duration:.1f}秒")
                # 移除会话信息
                if session_id in self.play_sessions:
                    del self.play_sessions[session_id]
                return True
            else:
                print(f"播放停止记录失败: {response.status_code}, {response.text}")
                return False
        except Exception as e:
            print(f"播放停止记录请求异常: {e}")
            return False

    def _start_progress_updater(self, embyInfos, item_id, media_source, session_id):
        """启动播放进度更新线程"""
        if not session_id:
            return
            
        def progress_updater():
            try:
                start_time = time.time()
                last_update = start_time
                
                # 每30秒更新一次播放进度
                while session_id in self.play_sessions:
                    current_time = time.time()
                    elapsed = current_time - start_time
                    
                    # 每30秒更新一次进度
                    if current_time - last_update >= 30:
                        self._record_playback_progress(
                            embyInfos, item_id, media_source, session_id, elapsed
                        )
                        last_update = current_time
                    
                    # 检查是否超过最大持续时间（2小时）
                    if elapsed >= 7200:  # 2小时
                        break
                        
                    time.sleep(5)  # 每5秒检查一次
                
                # 播放结束，记录停止
                if session_id in self.play_sessions:
                    self._record_playback_stop(session_id)
                    
            except Exception as e:
                print(f"播放进度更新线程异常: {e}")
                # 确保在异常情况下也尝试记录播放停止
                if session_id in self.play_sessions:
                    self._record_playback_stop(session_id)
        
        # 启动线程
        thread = threading.Thread(target=progress_updater, daemon=True)
        thread.start()

    def localProxy(self, params):
        pass

    def getAccessToken(self):
        if self.credentialUrl and self.direct_expires_at <= int(time.time()) + 300:
            self._load_direct_credential()
        key = f"emby_{self.baseUrl}_{self.username}_{self.password}"
        embyInfos = self.getCache(key)
        if embyInfos:
            return embyInfos

        header = self.header.copy()
        header['Content-Type'] = "application/json; charset=UTF-8"
        
        auth_data = {
            "Username": self.username,
            "Pw": self.password
        }
        
        r = requests.post(
            f"{self.baseUrl}/emby/Users/AuthenticateByName", 
            json=auth_data, 
            headers=header, 
            timeout=120, 
            proxies={"http": self.proxy, "https": self.proxy}
        )
        embyInfos = r.json()
        self.setCache(key, embyInfos)
        return embyInfos

    def cleanText(self, text):
        # 清理文本中的特殊字符
        if not text:
            return ""
        return text.replace("\n", " ").replace("\r", " ").replace("\t", " ").strip()
