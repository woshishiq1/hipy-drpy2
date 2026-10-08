#coding=utf-8
#!/usr/bin/python
import sys
sys.path.append('..')
import json
import re

from base.spider import Spider

class Spider(Spider):
	def getName(self):
		return "91Porn"

	def init(self, extend):
		self.baseUrl = "https://91porn.com"
		self.header = {
			"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
			"Accept-Language": "zh-CN,zh;q=0.9",
			"Referer": self.baseUrl + "/index.php"
		}
		self.cookies = {}
		
		# ✨ 核心改造：动态从 config.json 的 ext 参数中读取配置
		self.username = ""
		self.password = ""
		self.email = ""
		
		try:
			if extend:
				extendDict = json.loads(extend) if isinstance(extend, str) else extend
				self.username = str(extendDict.get('username', '')).strip()
				self.password = str(extendDict.get('password', '')).strip()
				self.email = str(extendDict.get('email', '')).strip()
		except Exception:
			pass
			
		self.is_ready = False

	def safe_bypass_and_verify(self):
		if self.is_ready:
			return True
		try:
			rsp = self.fetch(self.baseUrl + "/email_verify.php", headers=self.header, timeout=5)
			self.cookies.update(rsp.cookies.get_dict())
			self.cookies['language'] = 'cn_CN'
			self.cookies['CNAM'] = '1'
			
			# 如果外部没有配置邮箱，则直接作为普通游客会话放行
			if not self.email:
				self.is_ready = True
				return True
				
			post_data = {"email": self.email, "recover": "Submit", "submit": "true"}
			v_hd = self.header.copy()
			v_hd["Content-Type"] = "application/x-www-form-urlencoded"
			v_hd["Referer"] = self.baseUrl + "/email_verify.php"
			
			rsp_v = self.post(self.baseUrl + "/email_verify.php", data=post_data, headers=v_hd, cookies=self.cookies, timeout=5)
			self.cookies.update(rsp_v.cookies.get_dict())
			self.is_ready = True
			return True
		except Exception:
			self.is_ready = True
		return False

	def homeContent(self, filter):
		result = {}
		classList = [
			{"type_name": "今日排行", "type_id": "hot"},
			{"type_name": "最近更新", "type_id": "rp"},
			{"type_name": "本月最热", "type_id": "md"}
		]
		result['class'] = classList
		return result

	def homeVideoContent(self):
		return {'list': []}

	def categoryContent(self, cid, page, filter, ext):
		self.safe_bypass_and_verify()
		result = {'page': int(page), 'pagecount': 1, 'limit': 0, 'total': 0, 'list': []}
		page = int(page)
		
		url = self.baseUrl + "/v.php?category=" + cid + "&page=" + str(page)
		if cid == "hot":
			url = self.baseUrl + "/index.php"
		elif cid == "rp":
			url = self.baseUrl + "/v.php?next=watch&page=" + str(page)
			
		try:
			rsp = self.fetch(url, headers=self.header, cookies=self.cookies, timeout=5)
			html = self.html(rsp.text)
			items = html.xpath("//div[contains(@class, 'well')]")
			videos = []
			for item in items:
				try:
					a_tag = item.xpath(".//a[contains(@href, 'view_video.php')]")
					if not a_tag:
						continue
					href = a_tag[0].get('href', '')
					v_match = re.search(r'viewkey=([a-zA-Z0-9]+)', href)
					if not v_match:
						continue
					vod_id = v_match.group(1)
					
					name_nodes = item.xpath(".//span[contains(@class, 'video-title')]/text()")
					vod_name = name_nodes[0].strip() if name_nodes else "精彩视频"
					
					img_nodes = item.xpath(".//img[contains(@class, 'img-responsive')]/@src")
					vod_pic = img_nodes[0].strip() if img_nodes else ""
					if vod_pic.startswith('//'):
						vod_pic = "https:" + vod_pic
						
					remark_nodes = item.xpath(".//span[@class='duration']/text()")
					vod_remarks = remark_nodes[0].strip() if remark_nodes else "完整版"
					
					videos.append({"vod_id": vod_id, "vod_name": self.cleanText(self.removeHtmlTags(vod_name)), "vod_pic": vod_pic, "vod_remarks": vod_remarks})
				except:
					continue
			result['list'] = videos
			result['limit'] = len(videos)
			result['pagecount'] = page + 1 if len(videos) >= 10 else page
		except Exception:
			pass
		return result

	def detailContent(self, did):
		self.safe_bypass_and_verify()
		tid = did[0]
		url = self.baseUrl + "/view_video.php?viewkey=" + tid
		try:
			rsp = self.fetch(url, headers=self.header, cookies=self.cookies, timeout=5)
			html_text = rsp.text.replace('&amp;', '&')
			root = self.html(html_text)
			
			title_nodes = root.xpath("//h4[contains(@class, 'login_register_header')]/text() | //title/text()")
			title = title_nodes[0].strip().replace(" - 91porn", "").strip() if title_nodes else "精彩视频"
			
			cover_nodes = root.xpath("//video/@poster")
			cover_pic = cover_nodes[0] if cover_nodes else ""
			
			real_video_url = ""
			strencode_match = re.search(r'strencode2\([\"\']([^\"\'\)]+)[\"\']\)', html_text)
			if strencode_match:
				ciphertext = strencode_match.group(1)
				
				try:
					from urllib.parse import unquote
					decrypted_html = unquote(ciphertext)
				except:
					import urllib
					decrypted_html = urllib.unquote(ciphertext)
					
				src_match = re.search(r"src=['\"]([^'\"]+)['\"]", decrypted_html)
				if src_match:
					real_video_url = src_match.group(1)

			if not real_video_url:
				src_nodes = root.xpath("//video/source/@src | //video/@src")
				if src_nodes:
					real_video_url = src_nodes[0]

			if not real_video_url:
				real_video_url = url
				
			vod = {"vod_id": tid, "vod_name": self.cleanText(self.removeHtmlTags(title)), "vod_pic": cover_pic, "type_name": "在线视频", "vod_content": "资源解析就绪", "vod_play_from": "91Porn秒解流", "vod_play_url": "直连资源源$" + real_video_url}
			return {'list': [vod]}
		except Exception:
			pass
		return {'list': []}

	def playerContent(self, flag, pid, vipFlags):
		need_parse = 1 if "view_video.php" in pid else 0
		return {"url": pid, "header": self.header, "parse": need_parse}

	def searchContent(self, key, quick):
		return {'list': []}

	def searchContentPage(self, key, quick, page):
		return {'list': []}

	def isVideoFormat(self, url):
		pass

	def manualVideoCheck(self):
		pass

	def localProxy(self, params):
		return None

	def destroy(self):
		pass