/*
@header({
  searchable: 2,
  filterable: 0,
  quickSearch: 0,
  title: '漫神',
  类型: '影视',
  lang: 'dr2',
})
*/

var rule = {
        title: '漫神',
        host: 'https://www.yydsmh.com',
        // host: 'https://m.mhkami.com',
        url: '/manga-lists/9/fyclass/3/fypage.html',
        searchUrl: '/api/front/index/search;post;key=**',
        searchable: 2,
        quickSearch: 0,
        headers: {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
            'X-Requested-With': 'XMLHttpRequest',
        },
    timeout: 5000,
    class_name: '长条&大女主&百合&耽美&纯爱&後宫&韩漫&奇幻&轻小说&生活&悬疑&格斗&搞笑&伪娘&竞技&职场&萌系&冒险&治愈&都市&霸总&神鬼&侦探&爱情&古风&欢乐向&科幻&穿越&性转换&校园&美食&剧情&热血&节操&励志&异世界&历史&战争&恐怖',
    class_url: '%E9%95%BF%E6%9D%A1&%E5%A4%A7%E5%A5%B3%E4%B8%BB&%E7%99%BE%E5%90%88&%E8%80%BD%E7%BE%8E&%E7%BA%AF%E7%88%B1&%E5%BE%8C%E5%AE%AB&%E9%9F%A9%E6%BC%AB&%E5%A5%87%E5%B9%BB&%E8%BD%BB%E5%B0%8F%E8%AF%B4&%E7%94%9F%E6%B4%BB&%E6%82%AC%E7%96%91&%E6%A0%BC%E6%96%97&%E6%90%9E%E7%AC%91&%E4%BC%AA%E5%A8%98&%E7%AB%9E%E6%8A%80&%E8%81%8C%E5%9C%BA&%E8%90%8C%E7%B3%BB&%E5%86%92%E9%99%A9&%E6%B2%BB%E6%84%88&%E9%83%BD%E5%B8%82&%E9%9C%B8%E6%80%BB&%E7%A5%9E%E9%AC%BC&%E4%BE%A6%E6%8E%A2&%E7%88%B1%E6%83%85&%E5%8F%A4%E9%A3%8E&%E6%AC%A2%E4%B9%90%E5%90%91&%E7%A7%91%E5%B9%BB&%E7%A9%BF%E8%B6%8A&%E6%80%A7%E8%BD%AC%E6%8D%A2&%E6%A0%A1%E5%9B%AD&%E7%BE%8E%E9%A3%9F&%E5%89%A7%E6%83%85&%E7%83%AD%E8%A1%80&%E8%8A%82%E6%93%8D&%E5%8A%B1%E5%BF%97&%E5%BC%82%E4%B8%96%E7%95%8C&%E5%8E%86%E5%8F%B2&%E6%88%98%E4%BA%89&%E6%81%90%E6%80%96',
    play_parse: true,
    lazy: `js:
                var html = request(input);
                var items = pdfa(html, '.acgn-reader-chapter__item');
                var pics = [];
                items.forEach(function(it) {
                    var src = pdfh(it, 'img&&src');
                    if(src) pics.push(src);
                });
                input = {parse: 0, url: 'pics://' + pics.join('&&'), header: rule.headers};
            `,
    limit: 6,
    推荐: '.pos-wrap li.js_cell;h3.title&&Text;img.bg&&src;p.new&&Text;a&&href',
    double: true,
    一级: '.acgn-comic-list .acgn-item;h3.acgn-title&&Text;img&&src;.acgn-chapter&&Text;a.acgn-thumbnail&&href',
    二级: {
        title: 'h1.title&&Text',
        img: 'meta[property="og:image"]&&content',
        desc: '#js_comciDesc .desc-content&&Text',
        content: '.desc-content&&Text',
        tabs: '',
        lists: '#j_chapter_list li',
        list_text: 'a&&title',
        list_url: 'a&&href'
    },
    搜索: 'json:data;name;cover;lastchapter;info_url',
}