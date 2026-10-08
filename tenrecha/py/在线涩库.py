#!/usr/bin/python
# -*- coding: utf-8 -*-
import sys, requests, re, json, base64
from bs4 import BeautifulSoup
from urllib.parse import quote

class Spider():
    def __init__(self):
        self.host = "https://dottaia.lol"
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Referer': self.host,
        }

    def getDependence(self):
        return []

    def init(self, extend=""):
        try: self.session.get(self.host, headers=self.headers, timeout=5)
        except: pass

    def homeContent(self, filter):
        result = {'class': [], 'list': [], 'filters': {}}
        try:
            res = self.session.get(self.host + "/cn", headers=self.headers)
            res.encoding = 'utf-8'
            soup = BeautifulSoup(res.text, 'html.parser')
            seen = set()
            for a in soup.select('a[href*="/cn/tag/"]'):
                href = a.get('href', '')
                name = a.text.strip()
                m = re.search(r'/cn/tag/(.+)', href)
                if m and name and name not in seen:
                    seen.add(name)
                    result['class'].append({"type_name": name, "type_id": quote(m.group(1))})
            result['list'] = self._parse_list(soup)
        except: pass
        return result

    def homeVideoContent(self):
        return self.homeContent(False)

    def _parse_list(self, soup):
        items = []
        seen = set()
        for card in soup.select('.movie-card'):
            try:
                a = card.find('a', href=re.compile(r'/cn/movie/'))
                if not a: continue
                href = a.get('href', '')
                vid = href.split('/movie/')[-1] if '/movie/' in href else href
                if not vid or vid in seen: continue
                seen.add(vid)
                img = card.find('img')
                pic = img.get('data-src') or img.get('src') or '' if img else ''
                if pic and not pic.startswith('http'): pic = self.host + pic
                name = ''
                h5 = card.find('h5')
                if h5:
                    name = h5.get('data-full-title') or h5.text.strip()
                if not name:
                    name = a.get('title', '')
                items.append({"vod_id": vid, "vod_name": name, "vod_pic": pic})
            except: continue
        return items

    def categoryContent(self, tid, pg, filter, extend):
        url = f"{self.host}/cn/tag/{tid}"
        if pg and int(pg) > 1: url += f"?page={pg}"
        try:
            res = self.session.get(url, headers=self.headers)
            res.encoding = 'utf-8'
            soup = BeautifulSoup(res.text, 'html.parser')
            v_list = self._parse_list(soup)
            return {"list": v_list, "page": int(pg), "pagecount": 99, "limit": len(v_list), "total": 999}
        except:
            return {"list": [], "page": int(pg)}

    def detailContent(self, ids):
        result = {"list": []}
        for vid in ids:
            try:
                url = f"{self.host}/cn/movie/{vid}"
                res = self.session.get(url, headers=self.headers)
                res.encoding = 'utf-8'
                soup = BeautifulSoup(res.text, 'html.parser')
                name = soup.select_one('h1')
                name = name.text.strip() if name else soup.title.text.split('-')[0].strip() if soup.title else vid
                pic = ""
                ld = soup.select_one('script[type="application/ld+json"]')
                if ld:
                    try:
                        d = json.loads(ld.string)
                        pic = d.get('thumbnailUrl', '')
                    except: pass
                if not pic:
                    img = soup.select_one('img[uk-cover]')
                    if img: pic = img.get('src', '')
                from_list, url_list = [], []
                ls = soup.select_one('select.line-select')
                opts = ls.find_all('option') if ls else []
                if not opts:
                    opts = soup.select('option')
                for opt in opts:
                    val = opt.get('value', '')
                    txt = opt.text.strip()
                    if val == 'no' or txt in ('English', '简体中文', '繁體中文', '720P'): continue
                    if not val: continue
                    from_list.append(txt)
                    url_list.append(f"高清${vid}|{val}")
                if not from_list:
                    from_list.append("默认")
                    url_list.append(f"高清${vid}")
                result["list"].append({
                    "vod_id": vid,
                    "vod_name": name,
                    "vod_pic": pic,
                    "vod_play_from": "$$$".join(from_list),
                    "vod_play_url": "$$$".join(["#".join(url_list)])
                })
            except: continue
        return result

    def searchContent(self, key, quick, pg=1):
        url = f"{self.host}/cn/search?q={quote(key)}"
        if pg and int(pg) > 1: url += f"&page={pg}"
        try:
            res = self.session.get(url, headers=self.headers)
            res.encoding = 'utf-8'
            soup = BeautifulSoup(res.text, 'html.parser')
            return {"list": self._parse_list(soup)}
        except: return {"list": []}

    def playerContent(self, flag, id, vipFlags):
        parts = id.split("|")
        vid = parts[0]
        url = f"{self.host}/cn/movie/{vid}"
        try:
            self.headers['Referer'] = url
            res = self.session.get(url, headers=self.headers)
            html = res.text
            m3u8 = re.search(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', html)
            if m3u8:
                return {"parse": 0, "url": m3u8.group(1).replace('\\/', '/'), "header": dict(self.headers)}
            match = re.search(r'player_aaaa\s*=\s*(\{.*?\})', html)
            if match:
                v_url = json.loads(match.group(1)).get('url', '')
                if not any(x in v_url for x in ['.m3u8', '.mp4', 'http']) and len(v_url) > 20:
                    v_url = base64.b64decode(v_url).decode('utf-8')
                return {"parse": 0 if '.m3u8' in v_url.lower() or '.mp4' in v_url.lower() else 1, "url": v_url, "header": dict(self.headers)}
        except: pass
        return {"parse": 1, "url": url, "header": dict(self.headers)}