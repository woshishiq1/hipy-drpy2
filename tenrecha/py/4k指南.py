"""
遇事不决，可问春风，春风不语，即随本心，本心坚定，何须春风！春风自有春风愁，可找鸟叔解君忧！
"""
#coding=utf-8
#!/usr/bin/python
import sys
sys.path.append('..') 
from base.spider import Spider
import re
import urllib.request
class Spider(Spider):  # 元类 默认的元类 type
	hostUrl='https://4kzn.com'
	def getName(self):
		return "4k指南"
	def init(self,extend=""):
		print("============{0}============".format(extend))
		pass
	def isVideoFormat(self,url):
		pass
	def manualVideoCheck(self):
		pass
	def homeContent(self,filter):
		result = {}
		cateManual = {
			'剧集':'juji',
			'电影':'dianying',
			"豆瓣Top250": "top250"
		}
		classes = []
		for k in cateManual:
			classes.append({
				'type_name': k,
				'type_id': cateManual[k]
			})

		result['class'] = classes
		if (filter):
			result['filters'] = self.config['filter']
		return result
	def homeVideoContent(self):
		res= self.fetch(self.hostUrl)
		html = self.html(res.text)
		aList = html.xpath("//a[@class='item-image']")
		videos = self.custom_list(aList=aList)
		videos=[v for v in videos if v['vod_name'].find('合集') < 0]
		result = {
			'list':videos
		}
		return result
	def categoryContent(self,tid,pg,filter,extend):
		result = {}
		videos=[]
		#https://4kzn.com/books/top250/page/2
		url='{0}/books/{1}/page/{2}'.format(self.hostUrl,tid,pg)
		req=self.fetch(url)
		htmlTxt=req.text
		html = self.html(htmlTxt)
		aList = html.xpath("//a[@class='item-image']")
		videos = self.custom_list(aList=aList)
		pagecount=self.custom_GetPage(html.xpath('//a[contains(string(.), "加载更多")]/@href'))
		limit = len(videos)
		result['list'] = videos
		result['page'] = pg
		result['pagecount'] = pagecount
		result['limit'] = limit
		result['total'] = 10000
		return result
	def detailContent(self,array):
		result = {}
		temporary = array[0].split('###')
		title=temporary[0]
		pic=temporary[-1]
		vodItems=[]
		playList=[]
		vod_play_from=['网盘']
		url=temporary[1]
		req=self.fetch(url)
		htmlTxt=req.text
		html = self.html(htmlTxt)
		temporary= html.xpath("//div[@class='site-go mt-3']")
		for v in temporary:
			vodItems=self.custom_EpisodesList(v.xpath('./a'))
			joinStr = "#".join(vodItems)
			playList.append(joinStr)
		type_name=vod_year=vod_area=vod_remarks=vod_actor=vod_director=vod_content=''
		try:
			temporary= html.xpath("//div[@class='panel-body single']/p/text()")
			for vod in temporary:
				if vod.find('类型:')>-1:
					type_name=vod.replace('类型:','').strip()
				elif vod.find('地区:')>-1:
					vod_area=vod.replace('地区:','').strip()
				elif vod.find('上映日期:')>-1:
					vod_year=vod.replace('上映日期:','').strip()
				elif vod.find('主演:')>-1:
					vod_actor=vod.replace('主演:','').strip()
				elif vod.find('导演:')>-1:
					vod_director=vod.replace('导演:','').strip()
				elif vod.find('语言:')>-1:
					vod_remarks=vod.replace('语言:','').strip()
				elif vod.find(':')<0:
					vod_content=vod.strip()
		except Exception as e:
			vod_content=e
		vod = {
			"vod_id":array[0],
			"vod_name":title,
			"vod_pic":pic,
			"type_name":type_name,
			"vod_year":vod_year,
			"vod_area":vod_area,
			"vod_remarks":'',
			"vod_actor":vod_actor,
			"vod_director":vod_director,
			"vod_content":vod_content
		}
		vod['vod_play_from'] =  "$$$".join(vod_play_from)
		vod['vod_play_url'] = "$$$".join(playList)
		result = {
			'list':[
				vod
			]
		}
		return result
	searchpage=1
	def searchContent(self,key,quick,pg=1):
		if int(pg)==1:
			self.searchpage=1
		if int(pg)>self.searchpage:
			return {'list':[]}
		url='{1}/page/{2}?post_type=book&s={0}'.format(urllib.parse.quote(key),self.hostUrl,pg)
		req=self.fetch(url)
		htmlTxt=req.text
		html = self.html(htmlTxt)
		aList = html.xpath("//a[@class='item-image']")
		videos = self.custom_list(aList=aList)
		self.searchpage=self.custom_GetPage(html.xpath('//div[@class="posts-nav mb-4"]/a/@href'))
		result = {
			'list':videos
		}
		return result
	def playerContent(self,flag,id,vipFlags):
		result = {}
		parse=1
		result["parse"] = parse#0=直接播放、1=嗅探
		result["playUrl"] =''
		result["url"] = id
		result["header"] = ''
		return result


	config = {
		"player": {},
		"filter": {}
		}
	header = {
	    'User-Agent': 'Mozilla/5.0 (Linux; U; Android 8.0.0; zh-cn; Mi Note 2 Build/OPR1.170623.032) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/61.0.3163.128 Mobile Safari/537.36 XiaoMi/MiuiBrowser/10.1.1'
        }
	def localProxy(self,param):
		return [200, "video/MP2T", action, ""]
	#-----------------------------------------------自定义函数-----------------------------------------------
	#分类取结果
	def custom_list(self,aList):
		videos = []
		for vod in aList:
			title=vod.xpath('./img/@alt')[0]
			url=vod.xpath('./@href')[0]
			img=vod.xpath('./img/@data-src')[0]
			vod_id='{0}###{1}###{2}'.format(title,url,img)
			videos.append({
				"vod_id":vod_id,
				"vod_name":title,
				"vod_pic":img
			})	
		return videos
	#正则取文本
	def custom_RegexGetText(self,Text,RegexText,Index):
		returnTxt=""
		Regex=re.search(RegexText, Text, re.M|re.S)
		if Regex is None:
			returnTxt=""
		else:
			returnTxt=Regex.group(Index)
		return returnTxt	
		#取总页数
	def custom_GetPage(self,nodes):
		pagecount=1
		try:
			temporary=self.custom_RegexGetText(nodes[-1],'page/(\\d+?)(\\?|$)',1)
			pagecount=int(temporary)
		except:
			pass
		return pagecount
		#取集数
	def custom_EpisodesList(self,nodes):
		videos = []
		for vod in nodes:
			url='push://{0}'.format(vod.xpath('./@href')[0])
			title='夸克网盘' if url.find('quark')>0 else '合集'
			videos.append('{1}${0}'.format(url,title))
		return videos
	