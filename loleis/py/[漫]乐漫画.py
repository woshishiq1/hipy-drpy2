"""
@header({
  searchable: 1,
  filterable: 1,
  quickSearch: 1,
  title: '乐乐漫画',
  lang: 'hipy',
})
"""

import sys, re, requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from base.spider import Spider

requests.packages.urllib3.disable_warnings()

class Spider(Spider):
    def getName(self): return "乐乐漫画"

    def init(self, extend=""):
        self.siteUrl = "https://www.lcmhx.asia"
        self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        self.sess = requests.Session()
        self.sess.mount('https://', HTTPAdapter(max_retries=Retry(total=3, status_forcelist=[500, 502, 503, 504])))

    def fetch(self, url):
        try: return self.sess.get(url, headers=self.headers, timeout=10, verify=False)
        except: return None

    def homeContent(self, filter):
        cats = [
            {"type_name": "韩漫", "type_id": "mctype/1"},
            {"type_name": "单行本", "type_id": "mctype/2"},
            {"type_name": "同人志", "type_id": "mctype/3"},
            {"type_name": "Cosplay", "type_id": "mctype/4"},
            {"type_name": "最新", "type_id": "latest"}
        ]
        return {'class': cats}

    def categoryContent(self, tid, pg, filter, extend):
        if tid == 'latest':
            url = f"{self.siteUrl}/{tid}/{pg}"
        else:
            url = f"{self.siteUrl}/{tid}-{pg}"
        return self.postList(url, int(pg))

    def searchContent(self, key, quick, pg=1):
        url = f"{self.siteUrl}/mcsearch/-------/?wd={key}"
        return self.postList(url, int(pg))

    def postList(self, url, pg):
        r = self.fetch(url)
        l = []
        if r and r.ok:
            for m in re.finditer(r'<a[^>]+href=["\'](/mc[^"\']+)["\'][^>]*>(.*?)</a>', r.text, re.S):
                u = m.group(1)
                inner = m.group(2)
                
                img_m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', inner)
                if not img_m: continue
                p = img_m.group(1)
                
                alt_m = re.search(r'alt=["\']([^"\']+)["\']', inner)
                title_m = re.search(r'title=["\']([^"\']+)["\']', m.group(0))
                
                if alt_m and len(alt_m.group(1).strip()) > 1:
                    t = alt_m.group(1).strip()
                elif title_m and len(title_m.group(1).strip()) > 1:
                    t = title_m.group(1).strip()
                else:
                    t = re.sub(r'<[^>]+>', '', inner).strip()
                    
                if not t: t = "未知"
                
                real_u = u if u.startswith("http") else self.siteUrl + u
                real_p = p if p.startswith("http") else self.siteUrl + p
                
                l.append({
                    # 将 URL、标题、图片拼接传参给详情页
                    'vod_id': f"{real_u}@@@{t}@@@{real_p}",
                    'vod_name': t,
                    'vod_pic': real_p,
                    'vod_remarks': '漫画',
                    'style': {"type": "rect", "ratio": 1.33}
                })
                
        # 提取真实URL去重
        seen = set()
        l_uniq = []
        for x in l:
            real_u = x['vod_id'].split('@@@')[0]
            if real_u not in seen:
                seen.add(real_u)
                l_uniq.append(x)
                
        return {'list': l_uniq, 'page': pg, 'pagecount': pg + 1 if len(l_uniq) else pg, 'limit': 20, 'total': 9999}

    def detailContent(self, ids):
        vid = ids[0]
        name = "未知"
        pic = ""
        
        # 从 vod_id 中还原 链接、标题 和 图片
        if "@@@" in vid:
            parts = vid.split("@@@")
            vid = parts[0]
            name = parts[1] if len(parts) > 1 else name
            pic = parts[2] if len(parts) > 2 else pic
            
        r = self.fetch(vid)
        if r and r.ok:
            html = r.text
            
            # 如果没有通过传参拿到标题或封面，则进行网页正则兜底
            if name == "未知":
                name_m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
                name = re.sub(r'<[^>]+>', '', name_m.group(1)).strip() if name_m else "未知"
                
            if not pic:
                pic_m = re.search(r'url\((["\']?)([^)"\']+)\1\)', html)
                if pic_m:
                    pic = pic_m.group(2)
                if pic and not pic.startswith("http"): pic = self.siteUrl + pic
            
            intro = ""
            intro_m = re.search(r'class=["\'][^"\']*v-card__text[^"\']*["\'][^>]*>(.*?)</div>', html, re.S)
            if intro_m:
                intro = re.sub(r'<[^>]+>', '', intro_m.group(1)).strip()
                
            chapters = []
            seen_ch = set()
            
            list_m = re.search(r'class=["\'][^"\']*listmh[^"\']*["\'](.*?)</ul>', html, re.S)
            if list_m:
                for m in re.finditer(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', list_m.group(1), re.S):
                    u = m.group(1)
                    title_m = re.search(r'title=["\']([^"\']+)["\']', m.group(0))
                    t = title_m.group(1).strip() if title_m else re.sub(r'<[^>]+>', '', m.group(2)).strip()
                    if not t: t = "正文"
                    u = u if u.startswith("http") else self.siteUrl + u
                    if u not in seen_ch:
                        chapters.append(f"{t}${u}")
                        seen_ch.add(u)
                        
            if not chapters:
                for m in re.finditer(r'<a[^>]+href=["\'](/mc-[^"\']+)["\'][^>]*>(.*?)</a>', html, re.S):
                    u = m.group(1)
                    t = re.sub(r'<[^>]+>', '', m.group(2)).strip() or "开始阅读"
                    u = u if u.startswith("http") else self.siteUrl + u
                    if u not in seen_ch:
                        chapters.append(f"{t}${u}")
                        seen_ch.add(u)
                        
            if not chapters:
                chapters.append(f"阅读${vid}")
                
            vod = {
                # 为了防止加入收藏/历史记录出问题，返回的 vod_id 必须带有完整拼接信息
                'vod_id': ids[0],
                'vod_name': name,
                'vod_pic': pic,
                'type_name': '漫画',
                'vod_content': intro,
                'vod_play_from': '乐乐漫画',
                'vod_play_url': '#'.join(chapters)
            }
            return {'list': [vod]}
        return {'list': []}

    def playerContent(self, flag, id, vipFlags):
        r = self.fetch(id)
        imgs = []
        if r and r.ok:
            html = r.text
            content_m = re.search(r'class=["\'][^"\']*general_center[^"\']*["\'](.*?)<(?:div class="[^"\']*footer|/body|script)', html, re.S)
            target = content_m.group(1) if content_m else html
            
            for tag in re.finditer(r'<img[^>]+>', target, re.I):
                img_tag = tag.group(0)
                
                src_m = re.search(r'(?:data-src|data-original)=["\']([^"\']+(?:jpg|jpeg|png|webp|gif))["\']', img_tag, re.I)
                if not src_m:
                    src_m = re.search(r'src=["\']([^"\']+(?:jpg|jpeg|png|webp|gif))["\']', img_tag, re.I)
                
                if src_m:
                    u = src_m.group(1)
                    if any(x in u for x in ['avatar', 'logo', 'icon', 'loading', 'lazy', 'default']): continue
                    if not u.startswith("http"): u = self.siteUrl + u
                    if u not in imgs: imgs.append(u)
                    
        return {"parse": 0, "url": "pics://" + "&&".join(imgs) if imgs else "", "header": ""}
