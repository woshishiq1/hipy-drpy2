# -*- coding: utf-8 -*-
# ============ MyAv.py v6 | 71us 模板 v7.5 结构 ============
# 站点: xn--bxrcd59ffag.v03.mp23.top (MyAv成人视频) | 自研PHP非标站
# 13接口=init/homeContent/categoryContent/detailContent/searchContent/playerContent/localProxy/isVideoFormat/manualVideoCheck/getDependence/destroy/progressVideo/setVideoFlags
# 四壳通用: TVBox/T4(只认555五接口) / 海阔/影视仓1.x(额外调扩展钩子) / 独立加载(无base.spider走兜底)
# 站点要点: atob(b64)混淆渲染/列表list.php页码游标密文(不可逆,链式翻页)/播放decodeBinaryString=bin->chr->b64->b64/搜索code+hash两步法
# ★分隔符铁律: $=名称/地址 | #=选集 | $$$=线路; 严禁$$或$连选集; 线路名与地址$$$段数必须相等
# ★链路策略v4: 资源默认直连输出, 仅403/防盗链/KEY404/需特殊头才走 localProxy 兜底
import sys, re, json, time, base64, hashlib, threading, http.server, socket, struct
from urllib.parse import urljoin, quote, unquote
from concurrent.futures import ThreadPoolExecutor
import requests

sys.path.append('..')
try:
    from base.spider import Spider
except ImportError:
    class Spider:
        def fetch(self, url, headers=None, **kw):
            kw.pop('timeout', None)
            r = requests.get(url, headers=headers, timeout=15, **kw)
            r.encoding = 'utf-8'
            return r

# ============ ★ CONFIG ============
HOSTS = ['https://xn--bxrcd59ffag.v03.mp23.top']  # ★ 主域(失效换新)
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
CATEGORIES = {'1': '日本精品', '2': '韩国御姐', '3': '闷骚护', '4': '野外露出', '5': '萝莉少女', '6': '网红流出', '7': '欧美精品', '8': '制服丝袜', '9': '亚洲有码', '10': '风情旗袍', '11': '恋腿狂魔', '12': '香港伦理', '13': '日本无码', '14': '成人动漫', '15': '精品推荐', '16': '人妻熟女', '17': '网红主播', '18': '欧美情色', '19': '闷骚护士', '20': '欺辱凌辱', '21': '女优系列', '22': '国产情色', '23': '素人自拍', '24': '91探花', '25': '古装扮演', '26': '自拍偷拍', '27': '长腿丝袜', '28': '网曝门', '29': '国产色情', '30': '中文字幕', '31': '瑜伽裤', '32': '多人多P', '33': '主播直播', '34': '国模私拍', '35': '巨乳美乳', '36': '强奸乱伦', '37': 'AV明星', '38': '韩国伦理', '39': '邻家人妻', '40': '口交颜射', '41': '东南亚AV', '42': '唯美港姐', '43': '兽耳系列', '44': '可爱学生', '45': '台湾辣妹', '46': '剧情介绍', '47': 'Cosplay', '48': '女同性恋', '49': '男同性恋', '50': '亚洲无码', '51': '伦理三级', '52': 'AV明星1', '53': '传媒出品', '54': '过膝袜', '55': '大桥未久'}
SEED = {
    '1': 'ZQltuOlljHgRpfJpmthKYIsgkGq6c8ZCQKNg3CJy_NbTj_JfnCErjIu7ksHRTEALhdWK1RMqFAPnyx_rVGQ7gg==',
    '2': 'wqe4zh6yg0suyl0M7HiAA5SLjgJAFVh-TnJw9mp0sID17ESd6zNVwgfFbFUW-TrRuPQfz2b_gV1C9ZT1TQHMwg==',
    '3': 'o0KiQNJ7ioHSACvdtAHJ-5ON107VIfFSpNfagkXasn1QynZv0I_mq-AZpEqWqYIojSfH7IKnpVEhqTgLqclrJQ==',
    '4': 'Lof8nm207syAUum4_oBcY1KhI-fQtcA3EeGULyiDoFraDSE-TOK5av-ifmuM1plLgMy2R5q-TWNx-mIlrXphIQ==',
    '5': '290L_2f5k6b2AlJghefMMBCSbySTT8Ws1qe90_--4fdV0-cV26JuVgUsnl29iY3aGxoA36NMQf-JAxHE-rV7Mg==',
    '6': 'Q6ixlj-Zoj5OLykb_zWkmBjRXcBEb7nQUeBsdfWCIaTsWFVxdBOoV76-4juw5Ymvj3HidolUnsBDnlXlDktzRg==',
    '7': 'fRZmCPnAp_KPpJjhclmdiq369AGj1BfsUMp3ruJfIG31F5z4CY9yxbCEVqligLplSrsaxiVE2QrPtL2-v9ugDQ==',
    '8': 'mYnjC3yinEDsq6-opdWqCLNH5Zq9sItL2KcSZJtrQpeiJfUcB74eMB1Dt__tcM9cFxPcCrJDzYU228GzPjy1-g==',
    '9': 'jgTqwXbL5L5NeIuFRL01q_IsQ0u41YV8qwPOgkPf89DEE_ahyEBlhiMjBeXuxuUb9V_qKkbJG2Zd1Q1KYgXdUA==',
    '10': '50X87iYnbn3cnTbmcQxBCCVuSX_a00KTHmj-7myOuhP0F-uSn_Ms32W_ZWs7MnliqlxIRWmTjNxTNoYOzKRXFA==',
    '11': 'dqtdEFEZcjAdQ9k-UPN_1aJGzmfTb6qECBEzW80DPdBUUiJNsgeS0SMkS32xOBMUy0zpgld-puYe3k8wzlUuTg==',
    '12': 'VwGlXD8WchPrcEu8U7_xm4taTuWfmc1gaCmaZ5l3RlUeVlh8J3IVhU8gBUqwDkoxetGNjuLjDeu5iF9m8tIZ4A==',
    '13': 'dPNEBIWoZ7O2A7I86XpToenAXAtR8uanKd1V1XJEV2y_cdIhmvvBBVpzzyUh_sOXxZESfaa8JZJea7UABf216A==',
    '14': 'DJqE0zIVJUTenk3gmzzirEH8wuRhyEJChbTIw4A7Y2-TWHhMAQepGj56GKa3EKCWFIqZYPuNasaFubcPKihuyQ==',
    '15': 'NSopWanaB5TZulFyZaXNOu8VOttEFIS6uLi9nTqmprOOzI8iCB3uRSF669JBk1YBUUAVftw51s39yQD9_fvTsQ==',
    '16': 'Xzb4Sej8TubLz5aj9NNiYvXE3BSpqmenM60I15nQzGZb7Omg5coh_dostV4XtTUEnZ8-WR2lgnWlpIYE0BNW2w==',
    '17': 'qIOO-_QAM4zy2lK16llzGgPQJd9IGwiNWbFW1Assgya-06VNRXJaaWhhe1yzVnh8BLgqrPiQkTp_sWRaOJYamw==',
    '18': 'cZ1zjHkiVHGjLIa_j9aBykCBtQmS8ylre6UGDeciKF9JqRrUCPWGk-LjfMdAN_fiv7lMv1zfAQq-x-lFzxfm1Q==',
    '19': 'o0KiQNJ7ioHSACvdtAHJ-5ON107VIfFSpNfagkXasn1QynZv0I_mq-AZpEqWqYIojSfH7IKnpVEhqTgLqclrJQ==',
    '20': 'YgaQVd9Z55JTRXsdVcO-lIBUKCfuEpsk-zKs5Vr4_Z0WmxCZ2Z1ub73pHfR3us4vISE-oQpqZX5BdsKQH7xE9w==',
    '21': 'DInkZebRsHLFvQjL_mhZU5PIbs592mL0dL9uDREerpqRVBuimKgeG-tH3L55C14Ygfoub0d6t1ElU1bw49rMTA==',
    '22': 'jwcfjNAQCvW71QJcSM_bG2fu9XqaRm1vC3xLVvf4nxUYYhvCucfmNGfi2G4vqxTYRYcT0COVgABNYpMXXfmQVA==',
    '23': 'o-G9tsS05twJTe6iTA_ZKzpI8NftmUJlB8330nF3JAp1P4Vuk3b5Os29IVbi54gfNHSsc4sfgT9X1PLHGa953w==',
    '24': 'wPTcPztSqHNwqMR3wrW_Vmx60Y0pAih3NJaQZ3m3e3mpjqmY7uWeyTa-C5bqTFuuJouzVvPMr_JYWJal5xzMMA==',
    '25': 'fKdL2-T4TLRhND1jLezJpgPn9t84il7uyPRCVLnQ-ZR7QWEmdhXc7La45psT7B6eOhpkaZuguy_Km6K9ICvIlg==',
    '26': 'sRoGhJehAsLzcR4ZZQwfMYd6tmpX9pCzzvVE_xoyjNVfQu6G6T0MRyjTPlYBT0cSRX2qACZfZWNfB_S01-syEg==',
    '27': 'iEYNk_cEGR5YrFtHLPlsKnVLst6yUkISO2Dy0sRdrelLvhsQeRbpMkDDv6HkAuEwcp_JdF23Ywf5r1-BA3aCmg==',
    '28': 'jujM9UoqzGjUNX--BqpQhT3bk29zKKknRf1wHBMTzNP2JEDJM9QlYIT9Nq5lOT7RvbSzhtraIkAgf6YRWDMtEA==',
    '29': 'FDMXIxks3e2kMRw_AxGXXLpjk2nnmmXYF87FH3atA9mz_p22d_6XmEYV7sUY65FuiGnJarAuJt37ie8Fg11zfw==',
    '30': 'hKm8NOAx2cwTDPjjGJLMfI2BY52mXPJ2CmA2JlqlKGlkRET0zizvZrGNStXUUHjSClQGPUNuzRQtMQEJsPH6-g==',
    '31': 'i-lauZZ7_GV1rZDut8XTj62QzqMNy1xwEjZ46u9Ajd05BiOGjsYOck7NZBf7t4re5sPXw5Pj0TrtL5-cQ1AHww==',
    '32': 'H84DAn4rBflKbmAJgS13Ko6-yhihPgZyPLvQfwi2iFvKM2MRXksa23fnKrjr7ecNWvA6oGXfGTaQ1NZ1FnAXwQ==',
    '33': '84ZrsuMvrr38BZT6_BWIR_Dz778i7ugxlbeFlmJbE3ENp1-JSBm2Fm7ax8F8m__w_AcXmPmXyHcT5hyLPqYENg==',
    '34': 'Xvrnf0100zgmRoSnlwOd96XxtCIB3MVXmDRlIAGPIFhHoaYc2tvczaiwhHh8vsnS8fCd4IEkzdzRLmt80QZ3_A==',
    '35': 'Cos7XUu5tK-eNrjG0LtcAU8WVlrBdDnVVcx-13eKGSa-34lsd6B8FocdqdUGdSFkM8m3kTtKnF9P3KOAQGk-bA==',
    '36': 'BWckNG_VT9FV4rNQ-kKfbcW_A7jdk9lhn6f0AAPwjGJagN4wlsn_m53oU1A-AzMSDizwzcypjcPe_AxBRpNqGg==',
    '37': 'cLzZ8Z-zWqQjfQ1AIDLpGRxZoj4kQfSQf2ya_FSXB7a_wuMESDOyvio2StGXJ2k6v0cmi8gCZdZ50vS3E2tWhA==',
    '38': 'sgDjZY7KkhFNVMtIXTVegziD-5pq054JinD_5XDUHn4X17ZuEkXYurT-f4zfXDOBcwdPjmmS78eNvpRf18iAAw==',
    '39': 'ed3Qydg5amNI5gqjwHW9ClRgUFMDdHHE19MroaeVfY5RC49AwEhDHDSw0TCaBCbw3q6m7bMUA6BLwNc_xioB7w==',
    '40': '1dwCqvVjGTSJByD7cLvTAwrYNY2SIj79Vh6l_sZ1iGdyPGris7Tuxvtf-wWG_797qIZU5rBG4FPObE3VZh6UMA==',
    '41': 'VMuu2r__hv95ymhc21UHi11paEteUIWlB_wDCuiVGqrOxJawfWyC7pDqsESHIBagzwX1wd8Z7a_2ZljBiZok6g==',
    '42': 'tZ3J6ptMaphU6w1dzjABzkJhXw67cF_oOqKrO8GKtm6hAkInWG8sLN14634prwD5N5PqFrZX-bcjQE38eI8TfQ==',
    '43': 'BziiLnO9YOj_V7q63zPngynS7rDZ10mVH5XNhdltaYrOY18zrJ6Gv9idXovYtPzg28WViKgiou2eBKgMDmr25g==',
    '44': 'UzLepCG02-2ghTLk2hczL9aHoad1_8yS3FwSx42ex8cIfBIwUnK8MQXvV6GZ1Lrt-9ss_RhhF2_m9thcvi25fw==',
    '45': 'SeOrHGp1jvNEuhzBxCrdEV3TYFaAWF_mLnl9ipm43NnumCLUPBVKbezOv1y_m9mqorS1fdissuCO_DDro8J2eQ==',
    '46': 'yJhroGnb3RePlkxAgr8Ah3PjR_A4XWhNLFhIaJtHuRQoi84hMbUr94YSH05qXk6jcXxfUzVSy8X-nZjsrzw4qg==',
    '47': 'KNX9_GhRw2K-Jnyw-tjSHlsGPlRzk2-rAZON8J4PB_nZPTU5SDrlHvJq-n9Ns0489C_wfogXdbPgsb1XS6xnOg==',
    '48': 'l6yrq87mKUq3J_LCnv8p_wCJfMwfP_K0ZJUDss96zFyeOKv7O8RHiHRLkSIMTPs0fqiQL2eYd-q25fECGbynmw==',
    '49': '4NAHsoSc44dePhMA0dGCwZe9qJokqVvtVyHbXQguQYoPdMUc0BuR0k_pbN4XLJW0xxorbkO0R2uNP80Ux4KlYQ==',
    '50': 'tvndC6ZDEwmtOa_jYif4cCvXYDlu7muO4OojkU79AV3zyw91Fn9-6ckxm2VEwf4ZyrVv95o6bo41RT4l_A2t0Q==',
    '51': 'xBhyX4cqNOX4OMMZ64n7n_sUSEzIIgemCeKRljGPqtpbKWteRgDsf9yU3Sq5WD3IuwzhCHl5ID0Rc1vNKmKARQ==',
    '52': 'DUR4QVElzQ5ZKEjGzIgarVXpOjkolRKWjMYqGoaPMnDoHYqYbByTOkJAEUON5Lki73sXzjgHMr_XmH2WYu2MqA==',
    '53': 'JJLVAWy4SVVtLyZcNqcT7I__oEUsU9bZQbTsoDancQJ7_8Jf4LOdQ8_v2CgQ7fQyuGpUGfS--fvo3WpeTmQnnw==',
    '54': 'OXUS896NeeQWNWyLUBObAMvXh0fPnvpiyUj-n4gauNpcoTCSF0snfqVm085CuHHAzR8xHigaD2l7TPsmcsP9Vg==',
    '55': 'hbuD_GFMZjtH6_IoGFAsqe2TXfMe-xfHR_VPToSVziAjZP2Yi5pDDJDHMZ_cokagvsXnEde6iJE0E2sHiIKnxA==',
}
PK = ''  # ★ 接口密钥(无)
REFERER = ''  # ★ 防盗链Referer(空=用self.base)
PIC_REFERER = ''  # ★ 图片防盗链Referer(空=无)
FD_ZONE = 0  # ★ 分片区段(71us .fd协议用, 无则0)
PROBE = 0  # ★ 详情多线路实测排序 1/0 (MyAv单线路)
SITE_KEY = 'MyAv'  # ★ 壳源标识
VIDEO_EXTS = 'm3u8|mp4|flv|ts'  # ★ isVideoFormat判定

# ============ AES 纯Python引擎(Crypto不可用时降级) ============
SBOX = [99, 124, 119, 123, 242, 107, 111, 197, 48, 1, 103, 43, 254, 215, 171, 118, 202, 130, 201, 125, 250, 89, 71, 240, 173, 212, 162, 175, 156, 164, 114, 192, 183, 253, 147, 38, 54, 63, 247, 204, 52, 165, 229, 241, 113, 216, 49, 21, 4, 199, 35, 195, 24, 150, 5, 154, 7, 18, 128, 226, 235, 39, 178, 117, 9, 131, 44, 26, 27, 110, 90, 160, 82, 59, 214, 179, 41, 227, 47, 132, 83, 209, 0, 237, 32, 252, 177, 91, 106, 203, 190, 57, 74, 76, 88, 207, 208, 239, 170, 251, 67, 77, 51, 133, 69, 249, 2, 127, 80, 60, 159, 168, 81, 163, 64, 143, 146, 157, 56, 245, 188, 182, 218, 33, 16, 255, 243, 210, 205, 12, 19, 236, 95, 151, 68, 23, 196, 167, 126, 61, 100, 93, 25, 115, 96, 129, 79, 220, 34, 42, 144, 136, 70, 238, 184, 20, 222, 94, 11, 219, 224, 50, 58, 10, 73, 6, 36, 92, 194, 211, 172, 98, 145, 149, 228, 121, 231, 200, 55, 109, 141, 213, 78, 169, 108, 86, 244, 234, 101, 122, 174, 8, 186, 120, 37, 46, 28, 166, 180, 198, 232, 221, 116, 31, 75, 189, 139, 138, 112, 62, 181, 102, 72, 3, 246, 14, 97, 53, 87, 185, 134, 193, 29, 158, 225, 248, 152, 17, 105, 217, 142, 148, 155, 30, 135, 233, 206, 85, 40, 223, 140, 161, 137, 13, 191, 230, 66, 104, 65, 153, 45, 15, 176, 84, 187, 22]
IS = [0] * 256
for _i, _v in enumerate(SBOX):
    IS[_v] = _i
RCON = [1, 2, 4, 8, 16, 32, 64, 128, 27, 54, 108, 216, 171, 77]
G2 = [0] * 256
G3 = [0] * 256
for _i in range(256):
    _t = _i << 1
    if _i & 128:
        _t ^= 0x11b
    G2[_i] = _t
    G3[_i] = G2[_i] ^ _i


def _ke(k):
    nk = len(k) // 4
    nr = nk + 6
    w = [list(k[4 * i:4 * i + 4]) for i in range(nk)]
    for i in range(nk, 4 * (nr + 1)):
        t = w[i - 1][:]
        if i % nk == 0:
            t = t[1:] + t[:1]
            t = [SBOX[b] for b in t]
            t[0] ^= RCON[i // nk - 1]
        elif nk > 6 and i % nk == 4:
            t = [SBOX[b] for b in t]
        w.append([w[i - nk][j] ^ t[j] for j in range(4)])
    return w


def _enc(b, w):
    s = [[b[r + 4 * c] for c in range(4)] for r in range(4)]
    def add(r):
        for i in range(4):
            for j in range(4):
                s[i][j] ^= w[r * 4 + j][i]
    def sub():
        for i in range(4):
            for j in range(4):
                s[i][j] = SBOX[s[i][j]]
    def sh():
        for r in range(1, 4):
            s[r] = s[r][r:] + s[r][:r]
    def mx():
        for c in range(4):
            a = [s[r][c] for r in range(4)]
            s[0][c] = G2[a[0]] ^ G3[a[1]] ^ a[2] ^ a[3]
            s[1][c] = a[0] ^ G2[a[1]] ^ G3[a[2]] ^ a[3]
            s[2][c] = a[0] ^ a[1] ^ G2[a[2]] ^ G3[a[3]]
            s[3][c] = G3[a[0]] ^ a[1] ^ a[2] ^ G2[a[3]]
    add(0)
    nr = len(w) // 4 - 1
    for rnd in range(1, nr):
        sub()
        sh()
        mx()
        add(rnd)
    sub()
    sh()
    add(nr)
    return bytes(s[r][c] for c in range(4) for r in range(4))


def _gm(a, b):
    p = 0
    for _ in range(8):
        if b & 1:
            p ^= a
        a = (a << 1) ^ 0x11b if a & 0x80 else a << 1
        b >>= 1
    return p & 0xff


def _dec(b, w):
    s = [[b[r + 4 * c] for c in range(4)] for r in range(4)]
    def add(r):
        for i in range(4):
            for j in range(4):
                s[i][j] ^= w[r * 4 + j][i]
    def isub():
        for i in range(4):
            for j in range(4):
                s[i][j] = IS[s[i][j]]
    def ish():
        for r in range(1, 4):
            s[r] = s[r][-r:] + s[r][:-r]
    def imx():
        for c in range(4):
            a = [s[r][c] for r in range(4)]
            s[0][c] = _gm(a[0], 14) ^ _gm(a[1], 11) ^ _gm(a[2], 13) ^ _gm(a[3], 9)
            s[1][c] = _gm(a[0], 9) ^ _gm(a[1], 14) ^ _gm(a[2], 11) ^ _gm(a[3], 13)
            s[2][c] = _gm(a[0], 13) ^ _gm(a[1], 9) ^ _gm(a[2], 14) ^ _gm(a[3], 11)
            s[3][c] = _gm(a[0], 11) ^ _gm(a[1], 13) ^ _gm(a[2], 9) ^ _gm(a[3], 14)
    nr = len(w) // 4 - 1
    add(nr)
    for rnd in range(nr - 1, 0, -1):
        ish()
        isub()
        add(rnd)
        imx()
    ish()
    isub()
    add(0)
    return bytes(s[r][c] for c in range(4) for r in range(4))


def aes_ecb(data, key, mode=1):
    w = _ke(key)
    out = b''
    if mode:
        pad = 16 - len(data) % 16
        data += bytes([pad]) * pad
        for i in range(0, len(data), 16):
            out += _enc(data[i:i + 16], w)
    else:
        for i in range(0, len(data), 16):
            out += _dec(data[i:i + 16], w)
        if out and 0 < out[-1] <= 16:
            out = out[:-out[-1]]
    return out


def aes_cbc(data, key, iv, enc=1):
    w = _ke(key)
    out = b''
    prev = iv
    if enc:
        pad = 16 - len(data) % 16
        data += bytes([pad]) * pad
        for i in range(0, len(data), 16):
            blk = bytes(data[i + j] ^ prev[j] for j in range(16))
            ct = _enc(blk, w)
            out += ct
            prev = ct
    else:
        for i in range(0, len(data), 16):
            blk = _dec(data[i:i + 16], w)
            out += bytes(blk[j] ^ prev[j] for j in range(16))
            prev = data[i:i + 16]
        if out and 0 < out[-1] <= 16:
            out = out[:-out[-1]]
    return out


# ============ 站点解码工具(atob双层混淆) ============
def _bd(s):
    try:
        return base64.b64decode(s).decode('utf-8', 'ignore')
    except:
        try:
            return base64.urlsafe_b64decode(s + '=' * (-len(s) % 4)).decode('utf-8', 'ignore')
        except:
            return ''


def _blocks(html):
    out = []
    for m in re.finditer(r'atob\("([^"]+)"\)', html):
        d = _bd(m.group(1))
        if d:
            out.append(d)
    return out


def _clean(s):
    s = re.sub(r'<[^>]+>', '', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip()


class Spider(Spider):
    def init(self, extend=''):
        self.base = HOSTS[0].rstrip('/')
        if extend and 'http' in extend:
            self.base = extend.strip().rstrip('/')
        self.ua = UA
        self.pk = PK
        self.ref = REFERER or self.base
        self.types = dict(CATEGORIES)
        self.filters = {}
        self._seed = dict(SEED)
        self._pgc = {}  # 游标缓存 {tid:{pn:游标id}}
        self._pc = {}  # 播放缓存 {cid:url}
        self._c = {}  # 通用缓存
        self._tried = False  # 动态分类防抖
        self._srv = None
        self._t0 = 0.0  # 全局请求节流(站点高频风控防御)
        self.s = requests.Session()
        self.s.headers.update({'User-Agent': self.ua, 'Accept-Language': 'zh-CN,zh;q=0.9'})

    # ========== 网络(session保搜索code/hash一次性态) ==========
    def _get(self, url, params=None, headers=None, timeout=10000):
        try:
            gap = time.time() - self._t0
            if gap < 3.5:
                time.sleep(3.5 - gap)
            self._t0 = time.time()
            hd = headers or {'Referer': self.ref}
            r = self.s.get(url, params=params, headers=hd, timeout=timeout, verify=False)
            return r.text if r.status_code == 200 else ''
        except Exception:
            return ''

    # ========== 容灾: 多HOST轮询(主域失效时用) ==========
    def _host_get(self, path, params=None):
        for h in HOSTS:
            t = self._get(h.rstrip('/') + path, params)
            if t:
                return t
        return ''

    # ========== 动态分类增强(cat.php抓到>55才替换, 失败静默) ==========
    def _ensure_types(self):
        if self._tried:
            return
        self._tried = True
        try:
            t = self._get(self.base + '/cat.php', {'tag': '6Wvt3eOMji5M_tHU6HuewA=='}, timeout=8000)
            if not t:
                return
            j = '\n'.join(_blocks(t))
            types, seed = {}, {}
            i = 0
            for m in re.finditer(r'<a[^>]+href="/list\.php\?id=([^"]+)"[^>]*>([^<]{1,40})</a>', j):
                nm = _clean(m.group(2))
                if not nm or len(nm) > 30 or nm == '分类标签' or nm in types.values():
                    continue
                i += 1
                types[str(i)] = nm
                seed[str(i)] = m.group(1)
            if len(types) > len(self.types):
                self.types = types
                self._seed = seed
                self._pgc = {}
        except Exception:
            pass

    # ========== 首页 ==========
    def homeContent(self, filter=False):
        r = {'class': [{'type_id': k, 'type_name': v} for k, v in self.types.items()]}
        if filter and self.filters:
            r['filters'] = self.filters
        r['list'] = self.homeVideoContent().get('list', [])
        return r

    def homeVideoContent(self):
        for u, p in ((self.base + '/index.php', {'page': 1}),
                     (self.base + '/list.php', {'id': self._seed.get('1', '')}),
                     (self.base + '/list.php', {'id': self._seed.get('15', '')})):
            items = self._items(self._get(u, p))
            if items:
                return {'list': items}
        return {'list': []}

    # ========== 分类(游标链式翻页, 预取next) ==========
    def categoryContent(self, tid, pg=1, filter=False, extend=''):
        try:
            pn = max(int(str(pg)), 1)
        except:
            pn = 1
        tid = str(tid).split('|')[0]
        if tid not in self._seed:
            return {'page': pn, 'pagecount': 1, 'limit': 48, 'total': 0, 'list': []}
        cache = self._pgc.setdefault(tid, {1: self._seed[tid]})
        if pn not in cache:
            cur = max(cache.keys())
            while cur < pn:
                h = self._get(self.base + '/list.php', {'id': cache[cur]})
                nid = self._next_id(h)
                if not nid:
                    cache[cur + 1] = cache[cur]
                    break
                cache[cur + 1] = nid
                cur += 1
        if pn not in cache:
            cache[pn] = cache[max(cache.keys())]
        html = self._get(self.base + '/list.php', {'id': cache[pn]})
        items = self._items(html)
        if not items and self._maxpage(html) > 1:  # 风控挖空页防御: 等5s重试一次
            time.sleep(5)
            html = self._get(self.base + '/list.php', {'id': cache[pn]})
            items = self._items(html)
        nid = self._next_id(html)
        if nid and pn + 1 not in cache:
            cache[pn + 1] = nid
        return {'list': items, 'page': pn, 'pagecount': self._maxpage(html), 'limit': 48, 'total': len(items)}

    def _next_id(self, html):
        ids = re.findall(r'class="next-page"[^>]*>\s*<a[^>]*href="/list\.php\?id=([^"]+)"[^>]*>下一页</a>', html)
        return ids[-1] if ids else ''

    def _maxpage(self, html):
        m = re.search(r'最大页(\d+)', html)
        return int(m.group(1)) if m else 1

    # ========== 列表解析(atob块解码后提取, 双模板兼容) ==========
    def _items(self, html):
        joined = '\n'.join(_blocks(html))
        if 'cont.php?id=' not in joined:
            return []
        pics = dict(re.findall(r'<a[^>]+href="/cont\.php\?id=([A-Za-z0-9_\-]+==)"[^>]*>\s*<img[^>]+data-src="([^"]+)"', joined))
        items = []
        for m in re.finditer(r'<h3[^>]*>\s*<a[^>]*href="/cont\.php\?id=([A-Za-z0-9_\-]+==)"[^>]*>(.*?)</a>\s*</h3>((?:(?!cont\.php\?id=).)*)', joined, re.S):
            cid = m.group(1)
            name = _clean(m.group(2))
            dm = re.search(r'(\d{4}-\d{2}-\d{2})', m.group(3))
            date = dm.group(1) if dm else ''
            if not name:  # 新模板h3标题被挖空: 图片+日期兜底
                pic = pics.get(cid, '')
                nm = re.search(r'/pic\d*/\S*?/(\d{4}-\d{2}-\d{2})/(\d+)-(\d+)/', pic)
                if nm:
                    name = nm.group(2) + '-' + nm.group(3)
                else:
                    name = cid[-10:].rstrip('=')
                if date:
                    name = date[:7] + '-' + name
            items.append({'vod_id': cid, 'vod_name': name, 'vod_pic': pics.get(cid, ''),
                          'vod_remarks': date, 'vod_year': date[:4] if date else ''})
            if len(items) >= 24:
                break
        return items

    def _pic(self, u):
        if not u:
            return ''
        if u.startswith('//'):
            u = 'https:' + u
        return u  # 直连优先; 403时 localProxy 兜底

    def _cover(self, html):
        m = re.search(r'data-src="([^"]+)"', '\n'.join(_blocks(html)))
        return m.group(1) if m else ''

    def _title(self, html):
        m = re.search(r'var decodedContent\s*=\s*decodeURIComponent\(escape\(atob\("([^"]+)"\)\)\)', html, re.S)
        if m:
            t = _clean(_bd(m.group(1)))
            if t:
                return t
        for b in _blocks(html):
            if '<' not in b and len(b) > 5 and re.search(r'[\u4e00-\u9fff]', b):
                return _clean(b)
        return ''

    # ========== 详情 ==========
    def detailContent(self, ids, quick='1'):
        cid = str(ids[0] if isinstance(ids, list) else ids or '')
        if not cid:
            return {'list': []}
        html = self._get(self.base + '/cont.php', {'id': cid})
        if not html:
            return {'list': []}
        url = self._parse_play(html, self.base + '/cont.php?id=' + cid)
        if url:
            self._pc[cid] = url
        name = self._title(html)
        d = {'vod_id': cid, 'vod_name': name or cid, 'vod_pic': self._pic(self._cover(html)),
             'vod_year': '', 'vod_area': '', 'vod_class': '', 'vod_director': '',
             'vod_actor': '', 'vod_content': '', 'vod_remarks': '',
             'vod_play_from': 'myav', 'vod_play_url': ('正片$' + url) if url else '正片$'}
        return {'list': [d]}

    # ========== 搜索(code+hash两步法, session保态) ==========
    def searchContent(self, key, quick=False, pg='1'):
        try:
            pn = max(int(str(pg)), 1)
        except:
            pn = 1
        kw = quote(str(key))
        params = {'s': kw}
        try:
            t = self._get(self.base + '/search.php')  # 走统一节流
            c = re.search(r'name="code" value="(\d+)"', t)
            hs = re.search(r'name="hash" value="([0-9a-f]{32})"', t)
            if c and hs:
                params.update({'code': c.group(1), 'hash': hs.group(1)})
        except Exception:
            pass
        html = self._get(self.base + '/search.php', params)
        items = self._items(html)
        return {'list': items, 'page': pn, 'pagecount': 1, 'limit': 48, 'total': len(items)}

    # ========== 播放: 直连优先 → 双层解密 → VIP插槽 ==========
    def playerContent(self, flag, id, vipFlags=None):
        u = str(id) if id else str(flag)
        if '://' in u:
            return {'parse': 0, 'url': u}  # 直连
        if u in self._pc:
            return {'parse': 0, 'url': self._pc[u]}
        if len(u) > 8:
            url = self._parse_play(self._get(self.base + '/cont.php', {'id': u}), '')
            if url:
                self._pc[u] = url
                return {'parse': 0, 'url': url}
        return {'parse': 0, 'url': u}

    def _parse_play(self, h, page_url):
        if not h:
            return ''
        for d in self._dec_all(h):
            mm = re.search(r'src="([^"]+)"', d)
            if mm and '://' in mm.group(1):
                return mm.group(1)
        m = re.search(r'<source[^>]+src="(https?://[^"]+)"', h)
        return m.group(1) if m else ''

    def _dec_all(self, html):
        out = []
        for m in re.finditer(r"decodeBinaryString\(['\"]([01]+)['\"]\)", html):
            bs = m.group(1)
            s1 = ''.join(chr(int(bs[i:i + 8], 2)) for i in range(0, len(bs) - 7, 8))
            try:
                d = _bd(s1)
                out.append(_bd(d))
            except Exception:
                pass
        return out

    def _dec(self, u, page_url=''):
        u = u.strip()
        if '://' in u or not u:
            return u
        if re.fullmatch(r'[01]{32,}', u):  # 二进制串兜底解码
            s1 = ''.join(chr(int(u[i:i + 8], 2)) for i in range(0, len(u) - 7, 8))
            try:
                return _bd(_bd(s1))
            except Exception:
                pass
        return ''

    def _vip_try(self, page_url, h, vipFlags):
        return ''  # 站点无VIP体系

    # ========== 四壳13接口扩展钩子(v7.5) ==========
    def isVideoFormat(self, url):
        if not url:
            return False
        if '.m3u8' in url:
            return True
        return bool(re.search(r'\.(?:%s)(?:\?|$)' % VIDEO_EXTS, str(url), re.I))

    def manualVideoCheck(self):
        return False

    def getDependence(self):
        return ''

    def destroy(self):
        try:
            self._c.clear()
            self._pc.clear()
            self._pgc.clear()
            self._srv = None
            self.s.close()
        except Exception:
            pass

    def progressVideo(self, speed, time, end):
        return False

    def setVideoFlags(self, siteKey, flags):
        try:
            self._siteKey = siteKey or SITE_KEY
            self._vflags = flags or {}
        except Exception:
            pass

    # ========== 本地代理(9979-9988): m3u8 KEY/分片重写 + 图片转码 ==========
    def localProxy(self, param):
        p = param.split('url=', 1)[-1] if 'url=' in param else param
        p = unquote(p) if '%' in p else p
        if re.search(r'\.(jpe?g|png|webp|gif)(\?|$)', p, re.I):
            return self._img(p)
        if '.m3u8' in p:
            return self._rewrite_m3u8(p)
        try:
            r = self.s.get(p, headers={'User-Agent': self.ua, 'Referer': self.ref}, timeout=20000, verify=False)
            if r.status_code != 200:
                return {'code': r.status_code, 'content': b'', 'headers': {}}
            return {'code': 200, 'content': r.content, 'headers': {'Content-Type': r.headers.get('Content-Type', 'application/octet-stream')}}
        except Exception:
            return {'code': 404, 'content': b'', 'headers': {}}

    def _rewrite_m3u8(self, url):
        try:
            r = self.s.get(url, headers={'User-Agent': self.ua, 'Referer': self.ref}, timeout=20000, verify=False)
            if r.status_code != 200:
                return {'code': r.status_code, 'content': b'', 'headers': {}}
            body = r.text
        except Exception:
            return {'code': 404, 'content': b'', 'headers': {}}
        base = url.rsplit('/', 1)[0] + '/'
        origin = re.match(r'https?://[^/]+', url)
        origin = origin.group(0) if origin else ''
        out = []
        for ln in body.splitlines():
            if ln.startswith('#EXT-X-KEY'):
                m = re.search(r'URI="([^"]+)"', ln)
                if m:
                    ku = m.group(1)
                    if ku.startswith('/'):
                        ku = origin + ku
                    elif not ku.startswith('http'):
                        ku = base + ku
                    ln = ln.replace('URI="%s"' % m.group(1), 'URI="%s"' % ('proxy?url=' + quote(ku, safe='')))
            elif ln.startswith('http'):
                ln = 'proxy?url=' + quote(ln, safe='')
            elif ln.startswith('/') and not ln.startswith('//'):
                ln = 'proxy?url=' + quote(origin + ln, safe='')
            out.append(ln)
        return {'code': 200, 'content': '\n'.join(out), 'headers': {'Content-Type': 'application/vnd.apple.mpegurl'}}

    def _img(self, u):
        try:
            r = self.s.get(u, headers={'User-Agent': self.ua, 'Referer': PIC_REFERER or self.ref}, timeout=15000, verify=False)
            data, ct = r.content, r.headers.get('Content-Type', 'image/jpeg')
            if data[:4] == b'RIFF' or 'webp' in ct:
                try:
                    from PIL import Image
                    import io
                    buf = io.BytesIO()
                    Image.open(io.BytesIO(data)).convert('RGB').save(buf, 'JPEG', quality=85)
                    data, ct = buf.getvalue(), 'image/jpeg'
                except Exception:
                    ct = 'image/webp'
            return {'code': 200, 'content': data, 'headers': {'Content-Type': ct}}
        except Exception:
            return {'code': 404, 'content': b'', 'headers': {}}
