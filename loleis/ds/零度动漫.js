/*
@header({
  searchable: 2,
  filterable: 0,
  quickSearch: 0,
  title: '零度动漫',
  类型: '动漫',
  lang: 'ds',
})
*/

var rule = {
    类型: '动漫',
    title: '零度动漫',
    host: 'https://m.zerolh.com',
    homeUrl: '/',
    url: '/liebiao/fyclass.html',
    searchUrl: '/search.asp?page=fypage&searchword=**&searchtype=-1',
    encoding: 'gb18030',
    搜索编码: 'gb18030',
    searchable: 2,
    quickSearch: 0,
    filterable: 0,
    headers: {
        'User-Agent': 'MOBILE_UA'
    },
    timeout: 10000,
    class_name: '日本动漫&国产动漫&欧美动漫&港台动漫&TV版&OVA版&剧场版&特典版&动态漫画&动漫电影&真人版',
    class_url: '721&722&723&724&tv&ova&juchang&tedian&dongtai&dianying&zhenren',
    play_parse: true,
    lazy: async function () {
        let { input } = this;
        return { parse: 1, jx: 0, url: input };
    },
    推荐: 'section.box_3 .list_3 li;a&&title;img&&src;i&&Text;a&&href',
    一级: 'section.box_3 .list_3 li;a&&title;img&&src;i&&Text;a&&href',
    二级: async function () {
        let { input, pdfh, pdfa, pd } = this;
        let html = await request(input);
        let vod = {
            vod_id: input,
            vod_name: pdfh(html, '.picIntro .intro strong&&Text'),
            vod_pic: pd(html, '.picIntro .pic img&&src', input),
            type_name: pdfh(html, '.picIntro .intro .emTit:eq(2)&&Text'),
            vod_year: pdfh(html, '.picIntro .intro .emTit:eq(5)&&Text'),
            vod_area: pdfh(html, '.picIntro .intro .emTit:eq(4)&&Text'),
            vod_remarks: pdfh(html, '.picIntro .intro .emTit:eq(1)&&Text'),
            vod_actor: '主演',
            vod_director: '导演',
            vod_content: pdfh(html, '.jianjie ul span&&Text')
        };
        let plays = pdfa(html, '#playtab .arconix-toggle-content ul li');
        let arr = [];
        plays.forEach(it => {
            let name = pdfh(it, 'a&&Text').trim();
            let url = pd(it, 'a&&href', input);
            if (name && url) arr.push(name + '$' + url);
        });
        vod.vod_play_from = arr.length ? '默认线路' : '';
        vod.vod_play_url = arr.length ? arr.join('#') : '';
        return vod;
    },
    搜索: '.list_1 .book-li;.book-title&&Text;.book-cover&&src;.book-desc&&Text;a.book-layout&&href'
};
