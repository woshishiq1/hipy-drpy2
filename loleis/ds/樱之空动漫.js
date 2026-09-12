/*
@header({
  searchable: 2,
  filterable: 0,
  quickSearch: 0,
  title: '樱之空动漫',
  类型: '影视',
  lang: 'ds',
})
*/

var rule = {
    title: '樱之空动漫',
    host: 'https://skr.skr1.cc:666',
    url: '/vodshow/fyclass--------fypage---/',
    searchUrl: '/vodsearch/**----------fypage---/',
    detailUrl: '/voddetail/fyid/',
    模板: 'mx',
    searchable: 2,
    quickSearch: 0,
    filterable: 0,
    headers: {
        'User-Agent': 'MOBILE_UA',
        'Referer': 'https://skr.skr1.cc:666/'
    },
    class_name: '日漫&国漫&美漫&电影&综艺&短剧&大陆剧&港台剧&海外剧',
    class_url: '46&47&85&84&91&92&81&82&83',
    class_parse: '',
    play_parse: true,
    double: false,
    推荐: '.cbox_list&&ul&&li;a&&alt;a&&data-original;.pic_text&&Text;a&&href',
    一级: '.vodlist_wi&&li;center a&&Text;a&&data-original;.pic_text&&Text;a&&href',
    二级: async function () {
        let { input, pdfh, pdfa, pd } = this;
        let html = await request(input);
        let vod = {
            vod_id: input,
            vod_name: pdfh(html, '.vodlist_thumb&&alt') || '片名',
            vod_pic: pd(html, '.vodlist_thumb&&data-original', input),
            type_name: '类型',
            vod_year: '年份',
            vod_area: '地区',
            vod_remarks: '更新信息',
            vod_actor: '主演',
            vod_director: '导演',
            vod_content: (pdfh(html, '.content_desc&&Text') || '').replace(/\s*展开全部\s*$/g, '').trim()
        };

        let tabNodes = pdfa(html, '.play_source_tab&&a');
        let listNodes = pdfa(html, '.content_playlist');
        let from = [];
        let urls = [];

        for (let i = 0; i < listNodes.length; i++) {
            let tabName = '';
            if (tabNodes[i]) {
                tabName = (pdfh(tabNodes[i], 'a&&alt') || pdfh(tabNodes[i], 'body&&Text') || '').replace(//g, '').replace(/\d+$/g, '').replace(/\s+/g, ' ').trim();
            }
            if (!tabName) {
                tabName = '线路' + (i + 1);
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
                from.push(tabName);
                urls.push(arr.join('#'));
            }
        }

        vod.vod_play_from = from.join('$$$');
        vod.vod_play_url = urls.join('$$$');
        return vod;
    },
    搜索: async function () {
        let { input, pdfa, pdfh, pd } = this;
        let html = await request(input);
        let items = pdfa(html, '.searchlist_item');
        return items.map(it => ({
            vod_id: pd(it, '.vodlist_thumb&&href', input),
            vod_name: (pdfh(it, 'h4.vodlist_title&&Text') || '').replace(/^(日漫|国漫|美漫|电影|综艺|短剧|大陆剧|港台剧|海外剧|桜剧|桜歌|桜漫)/, '').trim(),
            vod_pic: pd(it, '.vodlist_thumb&&data-original', input),
            vod_remarks: pdfh(it, '.pic_text&&Text').trim()
        }));
    }
};
