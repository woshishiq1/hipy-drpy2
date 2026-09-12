/*
@header({
  searchable: 2,
  filterable: 0,
  quickSearch: 0,
  title: '[漫]橘子动漫',
  类型: '动漫',
  lang: 'ds',
})
*/

var rule = {
    类型: '动漫',
    title: '[漫]橘子动漫',
    host: 'https://www.mgnacg.com',
    homeUrl: '/',
    url: '/category/fyclass--------fypage---/',
    searchUrl: '/index.php/ajax/suggest?mid=1&wd=**&limit=50',
    detailUrl: '/media/fyid/',
    searchable: 2,
    quickSearch: 0,
    filterable: 0,
    headers: {
        'User-Agent': 'MOBILE_UA',
        'Referer': 'https://www.mgnacg.com/'
    },
    timeout: 10000,
    class_name: '动漫&剧场版',
    class_url: '1&2',
    play_parse: true,
    lazy: async function () {
        let { input } = this;
        return { parse: 1, jx: 0, url: input };
    },
    推荐: 'body .public-list-box;a.time-title&&Text;img.gen-movie-img&&data-src;.public-list-prb&&Text;a.public-list-exp&&href',
    一级: async function () {
        let { MY_CATE, MY_PAGE } = this;
        let tid = MY_CATE || '1';
        let pg = MY_PAGE || 1;

        let cateUrl = HOST + '/category/' + tid + '-----------/';
        let html = await request(cateUrl);
        let uidMatch = html.match(/Pop\.Uid\s*=\s*["']([A-F0-9]+)["']/i);
        let uid = uidMatch ? uidMatch[1] : 'DCC147D11943AF75';
        let t = Math.floor(Date.now() / 1000).toString();
        let key = md5('DS' + t + uid);

        let api = HOST + '/index.php/api/vod';
        let body = 'type=' + tid + '&class=&area=&lang=&version=&state=&letter=&page=' + pg + '&time=' + t + '&key=' + key;
        let html2 = await post(api, {
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'Referer': cateUrl
            },
            body: body
        });
        let json = JSON.parse(html2);
        return (json.list || []).map(it => ({
            vod_id: it.vod_id || it.id,
            vod_name: it.vod_name || it.name,
            vod_pic: it.vod_pic || it.pic,
            vod_remarks: it.vod_remarks || (it.vod_serial ? ('第' + it.vod_serial + '集') : '')
        }));
    },
    二级: async function () {
        let { input, pdfh, pdfa, pd } = this;
        let html = await request(input);
        let vod = {
            vod_id: input,
            vod_name: pdfh(html, 'h3.slide-info-title&&Text') || '片名',
            vod_pic: pd(html, '.detail-pic img&&data-src', input),
            type_name: '动漫',
            vod_year: '年份',
            vod_area: '地区',
            vod_remarks: '',
            vod_actor: '主演',
            vod_director: '导演',
            vod_content: pdfh(html, '#height_limit&&Text') || '简介'
        };

        let rawTabs = pdfa(html, '.anthology-tab .swiper-wrapper a');
        let listNodes = pdfa(html, '.anthology-list-box');
        let validTabs = [];
        let playList = [];

        for (let i = 0; i < listNodes.length; i++) {
            let rawTab = rawTabs[i] || '';
            let rawTabText = rawTab ? pdfh(rawTab, 'body&&Text').replace(/\s+/g, ' ').trim() : '';
            let tabName = rawTabText.replace(/\d+$/, '').replace(/（已下线）/g, '').trim();
            if (!tabName || /已下线/.test(rawTabText)) {
                continue;
            }
            let eps = pdfa(listNodes[i], 'li');
            let arr = [];
            eps.forEach(ep => {
                let name = pdfh(ep, 'a&&Text').trim();
                let url = pd(ep, 'a&&href', input);
                if (name && url) {
                    arr.push(name + '$' + url);
                }
            });
            if (arr.length > 0) {
                validTabs.push(tabName);
                playList.push(arr.join('#'));
            }
        }

        vod.vod_play_from = validTabs.join('$$$');
        vod.vod_play_url = playList.join('$$$');
        return vod;
    },
    搜索: 'json:list;name;pic;;id'
};
