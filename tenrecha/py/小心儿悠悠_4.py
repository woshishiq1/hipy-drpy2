from base.spider import Spider
import requests
import json
import sys

sys.path.append('..')

host = "https://api.drama.9ddm.com"
headers = {
    'Content-Type': 'application/json;charset=utf-8'
}

class Spider(Spider):
    def getName(self):
        return "小心儿悠悠"

    def init(self, extend):
        self.common_params = {
            'version_code': '1600',
            'version_name': '1.6.0',
            'device_name': 'PJA110',
            'device_type': 'phone',
            'is_first_day': 'false',
            'is_first_24h': 'false',
            'app_launch_way': 'icon',
            'default_homepage': 'drama_library',
            'device_owning_firm': 'OnePlus',
            'font_scale': 'default',
            'os_type': '1',
            'clientInfo': '9BBBC7EC6D9045E6BD3B6E6B95A71D9Dd66169e46a7d8de8d766bce0d0e0df57'
        }

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def homeContent(self, filter):
        try:
            url = host + "/drama/home/shortVideoTags"
            response = requests.get(url, headers=headers, timeout=5, params=self.common_params)
            data = response.json()

            classes = []
            filters = {}
            
            tags = data.get("tags", [])
            audiences = data.get("audiences", [])
            orders = data.get("orders", ["最热", "最新"])
            
            for tag in tags:
                classes.append({
                    "type_id": tag,
                    "type_name": tag
                })
                
                filter_list = [
                    {
                        "key": "audience",
                        "name": "受众",
                        "value": [{"n": "全部", "v": ""}]
                    },
                    {
                        "key": "order",
                        "name": "排序",
                        "value": [{"n": "全部", "v": ""}]
                    }
                ]
                
                for audience in audiences:
                    filter_list[0]["value"].append({
                        "n": audience,
                        "v": audience
                    })
                
                for order in orders:
                    filter_list[1]["value"].append({
                        "n": order,
                        "v": order
                    })
                
                filters[tag] = filter_list

            return {
                "class": classes,
                "filters": filters
            }
        except Exception as e:
            return {"class": []}

    def homeVideoContent(self):
        return self.categoryContent("", "1", False, {})

    def categoryContent(self, tid, pg, filter, ext):
        videos = []
        try:
            page = int(pg) if pg else 1
            audience = ext.get("audience", "") if ext else ""
            order = ext.get("order", "") if ext else ""

            post_data = {
                "audience": audience,
                "page": page,
                "pageSize": 30,
                "searchWord": "",
                "subject": tid
            }
            
            if order:
                if order == "最热":
                    post_data["order"] = "hot"
                elif order == "最新":
                    post_data["order"] = "new"

            url = host + "/drama/home/search"
            response = requests.post(url, headers=headers, data=json.dumps(post_data), 
                                     timeout=5, params=self.common_params)
            data = response.json()

            for item in data.get("data", []):
                upper_left_label = item.get("upperLeftCornerLabel", "")
                view_count = item.get("viewCount", 0)
                episode_count = item.get("episodeCount", 0)
                
                if upper_left_label:
                    vod_year = upper_left_label
                else:
                    vod_year = str(item.get("publishDate", ""))
                
                remarks_parts = []
                if view_count:
                    if view_count >= 10000:
                        remarks_parts.append(f"{view_count/10000:.1f}万播放")
                    else:
                        remarks_parts.append(f"{view_count}播放")
                if episode_count:
                    remarks_parts.append(f"{episode_count}集")
                vod_remarks = " · ".join(remarks_parts) if remarks_parts else "null"
                
                videos.append({
                    "vod_id": item["oneId"],
                    "vod_name": item["title"],
                    "vod_pic": item["vertPoster"],
                    "vod_year": vod_year,
                    "vod_remarks": vod_remarks
                })

        except Exception as e:
            pass

        return {
            'list': videos,
            'page': pg,
            'pagecount': 9999,
            'limit': 90,
            'total': 999999
        }

    def detailContent(self, ids):
        try:
            vid = ids[0]
            url = host + "/drama/home/shortVideoDetail"
            params = {
                "oneId": vid,
                "page": 1,
                "pageSize": 1000
            }
            params.update(self.common_params)
            response = requests.get(url, headers=headers, timeout=5, params=params)
            data = response.json()

            video_data = data.get("data", [])
            if not video_data:
                return {}

            first_episode = video_data[0]

            actors = []
            short_play_tags = []
            description = ""
            episode_count = 0
            view_count = 0
            
            try:
                search_url = host + "/drama/home/search"
                post_data = {
                    "audience": "",
                    "page": 1,
                    "pageSize": 1,
                    "searchWord": first_episode["title"],
                    "subject": ""
                }
                search_response = requests.post(search_url, headers=headers, 
                                                data=json.dumps(post_data), timeout=5,
                                                params=self.common_params)
                search_data = search_response.json()
                
                if search_data.get("data"):
                    for item in search_data["data"]:
                        if item.get("oneId") == vid:
                            description = item.get("description", "")
                            actors = item.get("actors", [])
                            short_play_tags = item.get("shortPlayTag", [])
                            episode_count = item.get("episodeCount", len(video_data))
                            view_count = item.get("viewCount", 0)
                            break
            except:
                pass

            if not episode_count:
                episode_count = len(video_data)
            if not view_count:
                view_count = first_episode.get("collectionCount", 0)

            try:
                actor_items = data.get("actorItems", [])
                if actor_items and isinstance(actor_items, list):
                    actor_blocks = []
                    for actor in actor_items:
                        name = actor.get("name", "")
                        role = actor.get("rolePlayingName", "")
                        brief = actor.get("briefIntroduction", "")
                        if name:
                            lines = [f"{name} 饰演 {role}"]
                            if brief:
                                lines.append(brief)
                            actor_blocks.append("\n".join(lines))
                    if actor_blocks:
                        brief_text = "\n\n演员信息：\n" + "\n\n".join(actor_blocks)
                        description += brief_text
            except:
                pass

            remarks_parts = []
            if view_count:
                if view_count >= 10000:
                    remarks_parts.append(f"▶️{view_count/10000:.1f}万")
                else:
                    remarks_parts.append(f"▶️{view_count}")
            if episode_count:
                remarks_parts.append(f"共{episode_count}集")
                    
            vod_remarks = " · ".join(remarks_parts) if remarks_parts else "null"

            play_urls = []
            for episode in video_data:
                episode_index = episode.get('playOrder', 1)
                clarity_list = episode.get('videoClarityList', [])
                quality_info = {}
                
                if clarity_list and isinstance(clarity_list, list):
                    for item in clarity_list:
                        name = item.get('name', '')
                        url = item.get('url', '')
                        if name and url:
                            if '1080' in name:
                                quality_info['super'] = url
                            elif '720' in name:
                                quality_info['high'] = url
                            elif '480' in name:
                                quality_info['normal'] = url
                            else:
                                quality_info[name] = url
                
                play_urls.append(f"第{episode_index}集${json.dumps(quality_info, ensure_ascii=False)}")

            vod = {
                "vod_id": vid,
                "vod_name": first_episode["title"],
                "vod_pic": first_episode["vertPoster"],
                "vod_year": str(first_episode.get("publishDate", "")),
                "vod_remarks": vod_remarks,
                "vod_content": description,
                "vod_play_from": "围观短剧",
                "vod_play_url": "#".join(play_urls),
                "vod_actor": " · ".join(actors) if actors else "null",
                "type_name": " · ".join(short_play_tags) if short_play_tags else "null"
            }

            return {'list': [vod]}
        except Exception as e:
            return {}

    def playerContent(self, flag, id, vipFlags):
        try:
            quality_data = json.loads(id)
            if not isinstance(quality_data, dict):
                quality_data = {}
        except:
            quality_data = {}

        urls = []
        priority_keys = ['super', 'high', 'normal']
        name_map = {'super': '超清', 'high': '高清', 'normal': '流畅'}
        
        for key in priority_keys:
            if key in quality_data and quality_data[key]:
                urls.append(name_map.get(key, key))
                urls.append(quality_data[key])
        
        if not urls:
            for k, v in quality_data.items():
                if v and isinstance(v, str):
                    urls.append(k)
                    urls.append(v)
                    break
        
        if urls:
            return {
                "parse": 0,
                "playUrl": '',
                "url": urls,
                "header": headers
            }
        
        return {
            "parse": 0,
            "playUrl": '',
            "url": id,
            "header": headers
        }

    def searchContent(self, key, quick, pg="1"):
        videos = []
        try:
            page = int(pg) if pg else 1

            post_data = {
                "audience": "",
                "page": page,
                "pageSize": 30,
                "searchWord": key,
                "subject": ""
            }

            url = host + "/drama/home/search"
            response = requests.post(url, headers=headers, data=json.dumps(post_data), 
                                     timeout=5, params=self.common_params)
            data = response.json()

            for item in data.get("data", []):
                upper_left_label = item.get("upperLeftCornerLabel", "")
                view_count = item.get("viewCount", 0)
                episode_count = item.get("episodeCount", 0)
                
                if upper_left_label:
                    vod_year = upper_left_label
                else:
                    vod_year = str(item.get("publishDate", ""))
                
                remarks_parts = []
                if view_count:
                    if view_count >= 10000:
                        remarks_parts.append(f"{view_count/10000:.1f}万播放")
                    else:
                        remarks_parts.append(f"{view_count}播放")
                if episode_count:
                    remarks_parts.append(f"{episode_count}集")
                vod_remarks = " · ".join(remarks_parts) if remarks_parts else "null"
                
                videos.append({
                    "vod_id": item["oneId"],
                    "vod_name": item["title"],
                    "vod_pic": item["vertPoster"],
                    "vod_year": vod_year,
                    "vod_remarks": vod_remarks
                })

        except Exception as e:
            pass

        return {
            'list': videos,
            'page': pg,
            'pagecount': 9999,
            'limit': 30,
            'total': 999999
        }

    def searchContentPage(self, key, quick, pg):
        return self.searchContent(key, quick, pg)

    def localProxy(self, params):
        return None