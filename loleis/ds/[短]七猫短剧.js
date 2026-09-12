/*
@header({
  searchable: 1,
  filterable: 1,
  quickSearch: 0,
  title: '七猫短剧',
  '类型': '短剧',
  lang: 'ds'
})
*/

const h_ost = 'https://api-store.qmplaylet.com';
const h_ost1 = 'https://api-read.qmplaylet.com';
const keys = 'd3dGiJc651gSQ8w1';
const char_map = {
    '+': 'P', '/': 'X', '0': 'M', '1': 'U', '2': 'l', '3': 'E', '4': 'r', '5': 'Y', '6': 'W', '7': 'b', '8': 'd', '9': 'J',
    'A': '9', 'B': 's', 'C': 'a', 'D': 'I', 'E': '0', 'F': 'o', 'G': 'y', 'H': '_', 'I': 'H', 'J': 'G', 'K': 'i', 'L': 't',
    'M': 'g', 'N': 'N', 'O': 'A', 'P': '8', 'Q': 'F', 'R': 'k', 'S': '3', 'T': 'h', 'U': 'f', 'V': 'R', 'W': 'q', 'X': 'C',
    'Y': '4', 'Z': 'p', 'a': 'm', 'b': 'B', 'c': 'O', 'd': 'u', 'e': 'c', 'f': '6', 'g': 'K', 'h': 'x', 'i': '5', 'j': 'T',
    'k': '-', 'l': '2', 'm': 'z', 'n': 'S', 'o': 'Z', 'p': '1', 'q': 'V', 'r': 'v', 's': 'j', 't': 'Q', 'u': '7', 'v': 'D',
    'w': 'w', 'x': 'n', 'y': 'L', 'z': 'e'
};

// 公共函数：获取请求头配置（减少重复代码）
async function getCommonRequestOptions(ruleHeaders) {
    let formDatas = await getHeaderX();
    // 合并公共请求头与规则中的请求头
    let headers = { ...formDatas, ...ruleHeaders };
    return { method: 'GET', headers };
}

async function getQmParamsAndSign() {
    try {
        let sessionId = Math.floor(Date.now()).toString(); // 确保无小数点，纯整数字符串
        let data = {
            "static_score": "0.8", "uuid": "00000000-7fc7-08dc-0000-000000000000",
            "device-id": "20250220125449b9b8cac84c2dd3d035c9052a2572f7dd0122edde3cc42a70",
            "mac": "", "sourceuid": "aa7de295aad621a6", "refresh-type": "0", "model": "22021211RC",
            "wlb-imei": "", "client-id": "aa7de295aad621a6", "brand": "Redmi", "oaid": "",
            "oaid-no-cache": "", "sys-ver": "12", "trusted-id": "", "phone-level": "H",
            "imei": "", "wlb-uid": "aa7de295aad621a6", "session-id": sessionId // 动态参数对齐
        };
        let jsonStr = JSON.stringify(data, null, 0); // 禁用缩进，确保无空格
        console.log('[调试] JSON序列化结果:', jsonStr);
        // 2.3 Base64编码：对齐Python base64.b64encode（处理UTF-8字符）
        let utf8Encoded = encodeURIComponent(jsonStr); // 转UTF-8编码
        let base64Str = btoa(unescape(utf8Encoded)); // 对齐Python b64encode
        console.log('[调试] Base64编码结果:', base64Str); // 调试：对比Python的encoded
        // 2.4 字符映射：逐字符替换，确保无遗漏
        let qmParams = '';
        for (let c of base64Str) {
            qmParams += char_map[c] || c;
        }
        console.log('[调试] qm-params结果:', qmParams);
        // 2.5 签名参数拼接：
        let paramsStr = `AUTHORIZATION=app-version=10001application-id=com.duoduo.readchannel=unknownis-white=net-env=5platform=androidqm-params=${qmParams}reg=${keys}`;
        console.log('[调试] 签名原始字符串:', paramsStr);
        // 2.6 计算MD5签名
        let sign = await md5(paramsStr);
        console.log('[调试] 生成的sign:', sign);
        return { qmParams, sign };
    } catch (e) {
        console.error('[错误] qm-params/sign生成失败:', e);
        throw e; // 抛出错误，避免传递无效参数
    }
}

async function getHeaderX() {
    let { qmParams, sign } = await getQmParamsAndSign();
    return {
        'net-env': '5', 'reg': '', 'channel': 'unknown', 'is-white': '', 'platform': 'android',
        'application-id': 'com.duoduo.read', 'authorization': '', 'app-version': '10001',
        'user-agent': 'webviewversion/0', 'qm-params': qmParams, // 确保键名正确
        'sign': sign // 确保键名正确
    };
}

var rule = {
    title: '七猫短剧',
    类型: '短剧',
    host: h_ost,
    homeUrl: '/api/v1/playlet/index?tag_id=0&playlet_privacy=1&operation=1',
    searchUrl: '/api/v1/playlet/search?keyword=fykey&page=fypage',
    url: '/api/v1/playlet/index?tag_id=fyclass&page=fypage',
    headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.87 Safari/537.36'
    },
    timeout: 5000,
    filterable: 1,
    limit: 90,
    multi: 1,
    searchable: 1,
    play_parse: true,
    search_match: true,

    class_parse: async function() {
        let signString = `operation=1playlet_privacy=1tag_id=0${keys}`;
        let apiSign = md5(signString);
        let url = `${h_ost}/api/v1/playlet/index?tag_id=0&playlet_privacy=1&operation=1&sign=${apiSign}`;

        // 调用公共函数获取请求配置
        let options = await getCommonRequestOptions(rule.headers);
        let html = await request(url, options);
        let data = JSON.parse(html);

        let classList = [];
        let duoxuan = ['0', '1', '2', '3', '4']; // 分类筛选维度
        for (let duo of duoxuan) {
            let tags = data?.data?.tag_categories?.[Number(duo)]?.tags || [];
            for (let vod of tags) {
                classList.push({
                    type_id: String(vod.tag_id),
                    type_name: vod.tag_name || ''
                });
            }
        }
        return { class: classList, filters: {} };
    },

    一级: async function() {
        let { MY_CATE, MY_PAGE } = this;
        let cid = MY_CATE || 0;
        let page = MY_PAGE || 1;
        let signString;

        if (page === 1) {
            signString = `operation=1playlet_privacy=1tag_id=${cid}${keys}`;
        } else {
            signString = `next_id=${page}operation=1playlet_privacy=1tag_id=${cid}${keys}`;
        }
        let sign = md5(signString);
        console.log('[调试] 一级列表sign:', sign);

        // 构造分页URL
        let url = page === 1 ?
            `${h_ost}/api/v1/playlet/index?tag_id=${cid}&playlet_privacy=1&operation=1&sign=${sign}` :
            `${h_ost}/api/v1/playlet/index?tag_id=${cid}&next_id=${page}&playlet_privacy=1&operation=1&sign=${sign}`;

        // 调用公共函数获取请求配置
        let options = await getCommonRequestOptions(rule.headers);
        let html = await request(url, options);
        let data = JSON.parse(html);
        let videoList = data?.data?.list || [];

        let videos = videoList.map(vod => ({
            title: vod.title || '未知标题',
            img: vod.image_link || '',
            desc: `${vod.tags} ${vod.total_episode_num}集 ${vod.hot_value}`,
            url: encodeURIComponent(vod.playlet_id)
        }));
        return setResult(videos);
    },

    二级: async function() {
        let { orId } = this;
        let did = decodeURIComponent(orId);
        let signString = `playlet_id=${did}${keys}`;
        let sign = md5(signString);
        console.log('[调试] 详情接口sign:', sign);

        let detailUrl = `${h_ost1}/player/api/v1/playlet/info?playlet_id=${did}&sign=${sign}`;
        // 调用公共函数获取请求配置
        let options = await getCommonRequestOptions(rule.headers);
        let html = await request(detailUrl, options);

        let data = JSON.parse(html).data;
        // 构造播放地址列表：排序$地址拼接
        let play_url = data.play_list.map(it => `${it.sort}$${it.video_url}`).join('#');
        return {
            vod_name: data.title || "未知标题",
            vod_pic: data.image_link || "未知图片",
            vod_actor: "",
            vod_remarks: `${data.tags} ${data.total_episode_num}集`,
            vod_content: `${data.intro}` || "未知剧情",
            vod_play_from: '七猫短剧',
            vod_play_url: play_url
        };
    },

    搜索: async function() {
        let { KEY, MY_PAGE } = this;
        let page = MY_PAGE || 1;
        let d = [];
        let trackId = 'ec1280db127955061754851657967';

        let signString = `extend=page=${page}read_preference=0track_id=${trackId}wd=${KEY}${keys}`;
        let sign = md5(signString);
        console.log('[调试] 搜索接口sign:', sign);
        let encodedKey = encodeURIComponent(KEY);
        let url = `${h_ost}/api/v1/playlet/search?extend=&page=${page}&wd=${encodedKey}&read_preference=0&track_id=${trackId}&sign=${sign}`;

        // 调用公共函数获取请求配置
        let options = await getCommonRequestOptions(rule.headers);
        let html = await request(url, options);

        let data = JSON.parse(html);
        let videoList = data?.data?.list || [];
        videoList.forEach((vod) => {
            let cleanTitle = (vod.title || '').replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim();

            if (rule.search_match && !new RegExp(KEY, "i").test(cleanTitle)) {
                console.log(`[调试] 排除不符合搜索关键词的名称: ${cleanTitle}`);
                return;
            }

            d.push({
                title: cleanTitle,
                img: vod.image_link || '',
                desc: `${vod.total_num}`,
                url: encodeURIComponent(vod.id)
            });
        });

        return setResult(d);
    },

    lazy: async function() {
        let { input } = this;
        console.log('[调试] 播放地址:', input);
        return { parse: 0, url: input };
    }
};
