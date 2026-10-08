import re
import requests
from urllib.parse import quote
from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def getName(self):
        return "一抖阁"

    def init(self, extend=""):
        self.host="https://yidouge.com"
        self.headers={
            "User-Agent":"Mozilla/5.0 (Linux; Android 13; Mobile) AppleWebKit/537.36 Chrome/124.0.0.0 Mobile Safari/537.36",
            "Referer":self.host+"/",
            "Cookie":"gv_age_verified=1",
        }
        self.session=requests.Session()
        self.session.headers.update(self.headers)

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def destroy(self):
        return "Destroy"

    def _html(self, url):
        return self.session.get(url if url.startswith("http") else self.host+url,timeout=12).text

    def _text(self, s):
        return re.sub(r"\s+"," ",re.sub(r"<[^>]+>","",s or "")).strip()

    def _pic(self, url):
        if not url:
            return ""
        url=url.strip()
        if url.startswith("//"):
            url="https:"+url
        if "images.weserv.nl" in url:
            return url
        if url.endswith(".webp") or "webp" in url.lower():
            return "https://images.weserv.nl/?url="+url+"&output=jpg"
        return url

    def _list(self, html):
        out=[]
        seen=set()
        # 普通单集卡片
        for block in re.findall(r'<article class="video-card"[^>]*>(.*?)</article>',html,re.S|re.I):
            lm=re.search(r'<a class="video-card__link" href="([^"]+)"',block,re.I)
            if not lm:
                lm=re.search(r'<a class="video-card__body-link" href="([^"]+)"',block,re.I)
            if not lm or lm.group(1) in seen:
                continue
            seen.add(lm.group(1))
            tm=re.search(r'<h2 class="video-card__title">([^<]+)</h2>',block,re.I)
            im=re.search(r'<img[^>]+src="([^"]+)"',block,re.I)
            dm=re.search(r'<span class="video-card__duration">([^<]+)</span>',block,re.I)
            out.append({
                "vod_id":lm.group(1),
                "vod_name":self._text(tm.group(1)) if tm else "",
                "vod_pic":self._pic(im.group(1)) if im else "",
                "vod_remarks":self._text(dm.group(1)) if dm else "",
            })
        # 合集卡片
        for block in re.findall(r'<article class="video-card ydg-author-collection-card"[^>]*>(.*?)</article>',html,re.S|re.I):
            lm=re.search(r'class="ydg-author-collection-link">\s*<a[^>]+href="([^"]+)"',block,re.S|re.I)
            if not lm or lm.group(1) in seen:
                continue
            seen.add(lm.group(1))
            tm=re.search(r'<strong class="ydg-author-collection-title">([^<]+)</strong>',block,re.I)
            im=re.search(r'<img[^>]+src="([^"]+)"',block,re.I)
            nm=re.search(r'共\s*(\d+)\s*部',block,re.I)
            out.append({
                "vod_id":lm.group(1),
                "vod_name":self._text(tm.group(1)) if tm else "",
                "vod_pic":self._pic(im.group(1)) if im else "",
                "vod_remarks":"合集·共{}部".format(nm.group(1)) if nm else "合集",
            })
        return out

    def _cats(self, html):
        cats=[]
        seen=set()
        for m in re.finditer(r'<a class="category-parent-link[^"]*"\s+href="([^"]+)"[^>]*>\s*<span>([^<]+)</span>',html,re.I):
            href=m.group(1)
            if href in seen:
                continue
            seen.add(href)
            cats.append({"type_name":self._text(m.group(2)),"type_id":href})
        return cats

    def homeContent(self, filter):
        try:
            html=self._html("/")
            cats=self._cats(html)
            vods=self._list(html)
        except requests.RequestException:
            cats=[]
            vods=[]
        return {"class":cats,"list":vods}

    def homeVideoContent(self):
        try:
            return {"list":self._list(self._html("/"))}
        except requests.RequestException:
            return {"list":[]}

    def categoryContent(self, tid, pg, filter, extend):
        pg=int(pg or 1)
        base=tid.rstrip("/")
        path=base if pg==1 else base+"/page/{}/".format(pg)
        try:
            vods=self._list(self._html(path))
        except requests.RequestException:
            vods=[]
        return {"page":pg,"pagecount":pg+1 if vods else pg,"limit":len(vods),"total":999999 if vods else 0,"list":vods}

    def detailContent(self, ids):
        vid=str(ids[0]).strip() if isinstance(ids,list) else str(ids).strip()
        if not vid.startswith("http"):
            vid=self.host+vid
        try:
            html=self._html(vid)
        except requests.RequestException:
            html=""

        name=re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)',html,re.I)
        pic=re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',html,re.I)
        desc=re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']*)',html,re.I)

        # 合集页：进入后拆出多集
        if "/creator/" in vid:
            episodes=self._list(html)
            parts=[]
            for i,v in enumerate(episodes,1):
                title=v.get("vod_name") or ("第{}集".format(i))
                parts.append("{}${}".format(title,v.get("vod_id")))
            vod={
                "vod_id":vid,
                "vod_name":self._text(name.group(1)) if name else vid,
                "vod_pic":self._pic(pic.group(1)) if pic else (episodes[0].get("vod_pic") if episodes else ""),
                "type_name":"",
                "vod_year":"",
                "vod_content":desc.group(1).strip() if desc else "",
                "vod_play_from":"合集",
                "vod_play_url":"#".join(parts),
            }
            return {"list":[vod]}

        vod={
            "vod_id":vid,
            "vod_name":self._text(name.group(1)) if name else vid,
            "vod_pic":self._pic(pic.group(1)) if pic else "",
            "type_name":"",
            "vod_year":"",
            "vod_content":desc.group(1).strip() if desc else "",
            "vod_play_from":"一抖阁",
            "vod_play_url":"播放${}".format(vid),
        }
        return {"list":[vod]}

    def searchContent(self, key, quick, pg="1"):
        pg=int(pg or 1)
        wd=quote(str(key),safe="")
        path="/?s={}&post_type=video".format(wd) if pg==1 else "/?s={}&post_type=video&paged={}".format(wd,pg)
        try:
            vods=self._list(self._html(path))
        except requests.RequestException:
            vods=[]
        return {"page":pg,"pagecount":pg+1 if vods else pg,"limit":len(vods),"total":999999 if vods else 0,"list":vods}

    def playerContent(self, flag, id, vipFlags):
        page=str(id).strip()
        if not page.startswith("http"):
            page=self.host+page
        try:
            html=self._html(page)
        except requests.RequestException:
            html=""
        url=""
        for m in re.finditer(r'<script type="application/ld\+json"[^>]*>(.*?)</script>',html,re.S|re.I):
            data=m.group(1).strip()
            if '"contentUrl"' not in data:
                continue
            cm=re.search(r'"contentUrl"\s*:\s*"([^"]+)"',data)
            if cm:
                url=cm.group(1)
            break
        return {"parse":0 if url else 1,"playUrl":"","url":url or page,"header":self.headers}
