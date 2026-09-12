import { Crypto, load, _ } from 'assets://js/lib/cat.js';

let siteUrl = 'https://gaoqingju.com';
let siteKey = '';
let siteType = 0;

let headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'Referer': 'https://gaoqingju.com/'
};

async function request(reqUrl, postData, agentSp, get) {
    let res = await req(reqUrl, {
        method: get ? 'get' : 'post',
        headers: headers,
        data: postData || {},
        postType: get ? '' : 'form',
    });
    return res.content;
}

async function init(cfg) {
    siteKey = cfg.skey;
    siteType = cfg.stype;
}

async function home(filter) {
    let classes = [
        { type_id: 'movie', type_name: '电影' },
        { type_id: 'tv', type_name: '电视剧' },
        { type_id: 'manga', type_name: '动漫' },
        { type_id: 'jilu', type_name: '纪录片' }
    ];

    let filterObj = genFilterObj();
    return JSON.stringify({
        class: classes,
        filters: filterObj
    });
}

async function homeVod() {
    let html = await request(siteUrl, null, null, true);
    const $ = load(html);
    let videos = [];
    
    $('.grid > a.group').each((i, n) => {
        let pic = $(n).find('img').attr('src') || '';
        if (pic.startsWith('/')) {
            pic = siteUrl + pic;
        }
        videos.push({
            vod_id: $(n).attr('href'),
            vod_name: $(n).find('h3').text().trim(),
            vod_pic: pic,
            vod_remarks: $(n).find('.absolute.top-2.right-2').text().trim() || $(n).find('.absolute.bottom-0 p').text().trim()
        });
    });

    return JSON.stringify({
        list: videos,
    });
}

async function category(tid, pg, filter, extend) {
    let url = `${siteUrl}/index/${tid}.html`;
    
    if (extend && Object.keys(extend).length > 0) {
        let id = extend['id'] || 't';
        let area = extend['area'] || 'a';
        let year = extend['year'] || 'y';
        let clazz = extend['class'] || 's';
        
        if (tid === 'tv') {
            let status = extend['status'] || 'n';
            url = `${siteUrl}/index/${tid}-${id}-${area}-${year}-${clazz}-${status}.html`;
        } else {
            url = `${siteUrl}/index/${tid}-${id}-${area}-${year}-${clazz}.html`;
        }
    }
    
    if (pg && pg > 1) {
        url += `?page=${pg}`;
    }

    let videos = await getVideos(url);
    return JSON.stringify({
        list: videos,
    });
}

async function detail(id) {
    try {
        let url = id.startsWith('http') ? id : siteUrl + id;
        const html = await request(url, null, null, true);
        const $ = load(html);
        
        let title = $('h1.text-4xl').text().trim();
        let pic = $('.aspect-poster img').attr('src') || '';
        if (pic.startsWith('/')) {
            pic = siteUrl + pic;
        }
        
        let director = '';
        let actor = '';
        
        $('div.mb-6.space-y-2 > p').each((i, el) => {
            let text = $(el).text();
            if (text.includes('导演:')) director = text.replace('导演:', '').trim();
            if (text.includes('主演:')) actor = text.replace('主演:', '').trim();
        });

        let content = $('h3:contains("剧情简介")').next('p').text().trim();
        
        let fromList = [];
        let urlList = [];

        let containers = $('[x-ref="episodesContainer"], [x-ref="backupEpisodesContainer"]');
        
        if (containers.length > 0) {
            containers.each((idx, container) => {
                let sourceName = idx === 0 ? '在线播放' : '在线播放' + (idx + 1);
                let currentUrls = [];
                
                $(container).find('a').each((i, n) => {
                    let name = $(n).text().replace(/\s+/g, '').trim();
                    let link = $(n).attr('href');
                    if (link) {
                        currentUrls.push(`${name}$${link}`);
                    }
                });
                
                if (currentUrls.length > 0) {
                    fromList.push(sourceName);
                    urlList.push(currentUrls.join('#'));
                }
            });
        } else {
            let backupUrls = [];
            $('.bg-gray-900\\/50 a').each((i, n) => {
                let name = $(n).text().replace(/\s+/g, '').trim();
                let link = $(n).attr('href');
                if (link) {
                    backupUrls.push(`${name}$${link}`);
                }
            });
            if (backupUrls.length > 0) {
                fromList.push('在线播放');
                urlList.push(backupUrls.join('#'));
            }
        }

        const video = {
            vod_id: id,
            vod_name: title,
            vod_pic: pic,
            vod_actor: actor,
            vod_director: director,
            vod_content: content,
            vod_play_from: fromList.join('$$$'),
            vod_play_url: urlList.join('$$$'),
        };

        return JSON.stringify({ list: [video] });
    } catch (e) {
       console.error(e);
    }
    return null;
}

async function search(wd, quick, pg) {
    let url = `${siteUrl}/index/search/get_search_data.html?keyword=${encodeURIComponent(wd)}`;
    if (pg && pg > 1) url += `&page=${pg}`;
    
    let videos = await getVideos(url);
    return JSON.stringify({
        list: videos,
    });
}

async function play(flag, id, flags) {
    let url = id.startsWith('http') ? id : siteUrl + id;
    const html = await request(url, null, null, true);
    
    let playUrlMatch = html.match(/let\s+playUrl\s*=\s*['"](.*?)['"]/);
    let rawUrl = playUrlMatch ? playUrlMatch[1] : '';
    let finalUrl = rawUrl;

    if (rawUrl.includes('target=')) {
        try {
            let urlObj = new URL(rawUrl);
            let targetBase64 = urlObj.searchParams.get('target');
            if (targetBase64) {
                finalUrl = base64Decode(targetBase64);
            }
        } catch (e) {
            console.error(e);
        }
    }

    return JSON.stringify({
        parse: 0,
        url: finalUrl,
    });
}

async function getVideos(url) {
    const html = await request(url, null, null, true);
    const $ = load(html);
    let videos = [];
    
    $('.grid > div.group a').each((i, n) => {
        let id = $(n).attr('href');
        let name = $(n).find('h3').text().trim();
        let pic = $(n).find('img').attr('src') || '';
        if (pic.startsWith('/')) {
            pic = siteUrl + pic;
        }
        let remark = $(n).find('.absolute.top-2.right-2').text().trim();
        
        videos.push({
            vod_id: id,
            vod_name: name,
            vod_pic: pic,
            vod_remarks: remark,
        });
    });
    return videos;
}

function base64Encode(text) {
    return Crypto.enc.Base64.stringify(Crypto.enc.Utf8.parse(text));
}

function base64Decode(text) {
    return Crypto.enc.Utf8.stringify(Crypto.enc.Base64.parse(text));
}

function genFilterObj() {
    return {
        'movie': [
            { key: 'id', name: '类型', value: [{n:'全部',v:'t'},{n:'动作片',v:'3'},{n:'恐怖片',v:'4'},{n:'剧情片',v:'5'},{n:'战争片',v:'6'},{n:'爱情片',v:'9'},{n:'科幻片',v:'10'},{n:'惊悚片',v:'11'},{n:'犯罪片',v:'12'},{n:'悬疑片',v:'13'},{n:'喜剧片',v:'29'}] },
            { key: 'year', name: '年份', value: [{n:'全部',v:'y'},{n:'2026',v:'2026'},{n:'2025',v:'2025'},{n:'2024',v:'2024'},{n:'2023',v:'2023'},{n:'2022',v:'2022'},{n:'2021',v:'2021'}] }
        ],
        'tv': [
            { key: 'id', name: '地区', value: [{n:'全部',v:'t'},{n:'国产剧',v:'18'},{n:'港台剧',v:'19'},{n:'欧美剧',v:'20'},{n:'韩剧',v:'21'},{n:'日剧',v:'40'}] },
            { key: 'year', name: '年份', value: [{n:'全部',v:'y'},{n:'2026',v:'2026'},{n:'2025',v:'2025'},{n:'2024',v:'2024'},{n:'2023',v:'2023'},{n:'2022',v:'2022'}] },
            { key: 'status', name: '状态', value: [{n:'全部',v:'n'},{n:'连载中',v:'2'},{n:'已完结',v:'1'}] }
        ],
        'manga': [
            { key: 'id', name: '分类', value: [{n:'全部',v:'t'},{n:'中国',v:'8'},{n:'日本',v:'34'},{n:'韩国',v:'35'},{n:'欧美',v:'37'}] }
        ],
        'jilu': [
            { key: 'id', name: '分类', value: [{n:'全部',v:'t'},{n:'中国',v:'8'},{n:'日本',v:'34'},{n:'韩国',v:'35'},{n:'欧美',v:'37'}] }
        ]
    };
}

export function __jsEvalReturn() {
    return {
        init: init,
        home: home,
        homeVod: homeVod,
        category: category,
        detail: detail,
        play: play,
        search: search,
    };
}