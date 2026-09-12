/*
@header({
  searchable: 1,
  filterable: 1,
  quickSearch: 1,
  title: '梨园[戏]',
  lang: 'cat',
})
*/
let host = 'https://fly.daoran.tv';

let siteName = '梨园行', siteKey = '', siteType = 0;

let UA = {
    'User-Agent': 'okhttp/3.12.10',
    'Connection': 'Keep-Alive',
    'Content-Type': 'application/json',
    'md5': 'SkvyrWqK9QHTdCT12Rhxunjx+WwMTe9y4KwgeASFDhbYabRSPskR0Q=='
};

let cate_remove = ['分类排除', '首页', '推荐'];

function init(cfg) {
    siteName = cfg.skey?.split('_')[1] || cfg.skey || '梨园行';
    siteKey = cfg.skey;
    siteType = cfg.stype;
    
    let ext = cfg.ext !== undefined ? cfg.ext : cfg;
    if (typeof ext === 'string' && ext.trim() !== '') {
        host = ext.trim();
    } else if (typeof ext === 'object') {
        host = ext.host || ext.hosturl || ext.url || ext.site || host;
        if (ext.cate_remove !== undefined) {
            cate_remove = Array.isArray(ext.cate_remove) ? ext.cate_remove : cate_remove;
        }
    }
}

function safeJSONParse(str, defaultValue = {}) {
    if (!str || typeof str === 'object') return str || defaultValue;
    try {
        return JSON.parse(str);
    } catch {
        return defaultValue;
    }
}

async function request(url, options = {}) {
    const reqHeaders = { ...UA, ...options.headers };
    let postType = reqHeaders['Content-Type']?.includes('json') ? 'json' :
        reqHeaders['Content-Type']?.includes('form') ? 'form' : '';

    try {
        const response = await req(url, {
            method: options.method || 'GET',
            headers: reqHeaders,
            data: options.data,
            postType: postType,
            timeout: options.timeout || 15000
        });
        return response?.content || response?.data || response;
    } catch {
        return null;
    }
}

async function home(filter) {
    const classNames = '豫剧&黄梅戏&越剧&京剧&评剧&曲剧&坠子&秦腔&河北梆子&潮剧&粤剧&沪剧&二夹弦&昆曲&河南琴书&淮剧&单弦&西秦戏&婺剧&上党梆子&白字戏&河南大鼓书&越调&滇剧&太康道情&民族音乐&扬剧&其他&曲艺晚会&二人台&北路梆子&彩调&乐腔&老年大学&吕剧&天津时调&戏曲&柳琴戏&京韵大鼓&皮影戏&湘剧&四平调&琼剧&锡剧&评书&绍剧&京东大鼓&庐剧&话剧&西河大鼓&莆仙戏&花鼓戏&川剧&相声&宛梆&晋中秧歌&采茶戏&蒲剧&汉剧&闽剧&晋剧&北京琴书&山歌剧&吉剧&正字戏&赣剧&麦田乡韾&楚剧&大平调&保定老调';
    const classUrls = 'yuju&hmx&yueju&jingju&pingju&quju&hnzz&qinq&hbbz&chaoju&gddx&huju&ejx&kunqu&hnqs&huaiju&danxian&xqx&wuju&SDBZ&bzx&hndgs&yued&dianju&tkdq&MZYY&yangju&other&else&ERT&blbz&caidiao&lq&WK&lvjv&tjsd&xq&liuqx&jydg&pyx&xj&spd&qiongju&xiju&pingshu&shaojv&jddg&luju&huaju&xhdg&huagx&chuanju&xiang&wb&jzyg&caichaxi&pujv&hj&minju&jinju&bjqs&sgj&jiju&zzx&gj&chuju&dpd&bdld';
    
    const names = classNames.split('&');
    const urls = classUrls.split('&');
    
    const classes = [];
    for (let i = 0; i < names.length && i < urls.length; i++) {
        const typeName = names[i];
        const isBad = cate_remove.some(word => typeName.includes(word));
        if (!isBad) {
            classes.push({ type_id: urls[i], type_name: typeName });
        }
    }
    
    const filters = {};
    classes.forEach(cls => { filters[cls.type_id] = []; });
    
    return JSON.stringify({ class: classes, filters: filters });
}

async function homeVod() {
    const data = {
        "cur": 1, "free": 0, "orderby": "hot", "pageSize": 50, "resType": 1, "sect": [],
        "tagId": 0, "userId": "5af3139f6f73ae8a360402f381b94221", "channel": "yingyongbao",
        "item": "y9", "nodeCode": "001000", "project": "lyhxcx",
        "sign": "MmhTLnUjLLHi48rk9zwBANI3OX3f5EffDpHK7XK6pDakUevGnPah7dcDppuBR90yYbrerbCKxbFwSBTeysxD8g=="
    };

    const html = await request(`${host}/API_ROP/search/album/list`, { method: 'POST', data: data });
    const list = safeJSONParse(html).pb.dataList;
    const videos = list.map(item => ({
        vod_id: `https://zheshiyitaiojialianjie.com?${item.code}`,
        vod_name: item.name,
        vod_pic: `https://ottphoto.daoran.tv/HD/${item.imgsec}`,
        vod_remarks: item.des || '戏曲'
    }));
    
    return JSON.stringify({ list: videos });
}

async function category(tid, pg, filter, extend) {
    const data = {
        "cur": pg || 1, "free": 0, "orderby": "play", "pageSize": 50, "resType": 1,
        "sect": tid, "tagId": 0, "userId": "5af3139f6f73ae8a360402f381b94221",
        "channel": "yingyongbao", "item": "y9", "nodeCode": "001000", "project": "lyhxcx",
        "sign": "MmhTLnUjLLHi48rk9zwBANI3OX3f5EffDpHK7XK6pDakUevGnPah7dcDppuBR90yYbrerbCKxbFwSBTeysxD8g=="
    };

    const html = await request(`${host}/API_ROP/search/album/screen`, { method: 'POST', data: data });
    const list = safeJSONParse(html).pb.dataList;
    const videos = list.map(item => ({
        vod_id: `https://zheshiyitaiojialianjie.com?${item.code}`,
        vod_name: item.name,
        vod_pic: `https://ottphoto.daoran.tv/HD/${item.imgsec}`,
        vod_remarks: item.des || '戏曲'
    }));
    
    return JSON.stringify({
        list: videos,
        page: pg || 1,
        pagecount: 1,
        limit: 20,
        total: videos.length
    });
}

async function detail(id) {
    const code = id.split('?')[1];
    const data = {
        "albumCode": code, "cur": 1, "pageSize": 100,
        "userId": "5af3139f6f73ae8a360402f381b94221", "channel": "oppo", "item": "y9",
        "nodeCode": "001000", "project": "lyhxcx",
        "sign": "MmhTLnUjLLHi48rk9zwBANI3OX3f5EffDpHK7XK6pDakUevGnPah7dcDppuBR90yonrdMsz0hMVGJ92jA6Flzw=="
    };
    
    const html = await request(`${host}/API_ROP/album/res/list`, { method: 'POST', data: data });
    const response = safeJSONParse(html);
    const list = response.pb.dataList;
    const album = response.album;
    
    const playUrls = [];
    list.forEach(it => {
        playUrls.push(`${it.name}$https://zheshiyitaiojialianjie.com?${it.code}`);
    });
    
    const vod = {
        vod_id: id,
        vod_name: album.name,
        vod_pic: 'https://img0.baidu.com/it/u=4079405848,3806507810&fm=253&fmt=auto&app=138&f=JPEG?w=500&h=750',
        vod_content: album.des || '暂无简介',
        vod_remarks: "戏曲",
        vod_play_from: '梨园行',
        vod_play_url: playUrls.join('$$$')
    };
    
    return JSON.stringify({ list: [vod] });
}

async function play(flag, id, flags) {
    const code = id.split('?')[1];
    const data = {
        "item": "o3", "mask": 0, "nodeCode": "001000", "project": "lyhxcx",
        "px": 2, "resCode": code, "userId": "5af3139f6f73ae8a360402f381b94221"
    };
    
    const html = await request(`${host}/API_ROP/play/get/playurl`, { method: 'POST', data: data });
    const parsed = safeJSONParse(html);
    const url = parsed.playUrls.hd;
    
    return JSON.stringify({ parse: 0, url: url, header: {} });
}

async function search(wd, quick, pg = "1") {
    const data = JSON.stringify({
        "cur": pg || 1, "free": 0, "keyword": wd, "nodeCode": "001000",
        "orderby": "hot", "pageSize": 200, "project": "lyhxcx", "px": 2,
        "sect": [], "userId": "5af3139f6f73ae8a360402f381b94221"
    });
    
    const html = await request(`${host}/API_ROP/search/album/list`, { method: 'POST', data: data });
    const list = safeJSONParse(html).pb.dataList;
    const videos = list.map(item => ({
        vod_id: `https://zheshiyitaiojialianjie.com?${item.code}`,
        vod_name: item.name,
        vod_pic: 'https://img0.baidu.com/it/u=4079405848,3806507810&fm=253&fmt=auto&app=138&f=JPEG?w=500&h=750',
        vod_remarks: item.des || ''
    }));
    
    return JSON.stringify({
        list: videos,
        page: parseInt(pg),
        pagecount: 1,
        limit: 20,
        total: videos.length
    });
}

export function __jsEvalReturn() {
    return { init, home, homeVod, category, detail, play, search };
}