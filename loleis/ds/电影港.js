/*
@header({
  searchable: 1,
  filterable: 0,
  quickSearch: 0,
  title: '[磁]电影港',
  author: 'EylinSir',
  '类型': '影视',
  logo: 'https://www.dyg123.net/favicon.ico',
  lang: 'ds'
})
*/

var rule = {
    类型: '影视',
    author: 'EylinSir',
    title: '[磁]电影港',
    host: 'https://www.dyg123.net',
    homeUrl: '/',
    url: '/e/action/ListInfo.php?fyfilter',
    logo: 'https://www.dyg123.net/favicon.ico',
    filter_url: 'classid={{fl.cateId or "fyclass"}}&page=(fypage-1)&line=30&tempid=1&orderby={{fl.by or "newstime"}}',
    searchUrl: '/e/search/index.php',
    detailUrl: '',
    searchable: 1, 
    quickSearch: 0, 
    filterable: 0, 
    timeout: 5000,
    limit: 20,
    headers: {'User-Agent': MOBILE_UA},
    class_name: '电影&剧集&综艺&动画&短剧',
    class_url: '1&20&31&30&32',
    filter: 'H4sIAAAAAAAAA6vmUgACJUMlq2gwCwSqlbJTK5WslJITS1I9U5R0lPISc1OB/Ocbdz+d1w3klyXmlAIFoquV8oDCT1tXvGxeARIGcgyVanWgwl0rnuyd87yzHSpjhJCZNudp53KEjDFc5nnHxmfNrQgZE4TM8olPd+5GyJgiTOtcjqLHDC7zrHHCs4ZpCBlzhEzHjCe7OhEyhgip57tWPd07FUnKQqk2tlYHI3CSKhEB86xv0tNd/RgB82xOw7NpG6Dm5KWWF5dkApXDLHqya9ezDVOgsvl5yTmZydkgq8A2xUIsVDIyoFbEAE2Ch9jsvcBAg4kjYuzZ9KUv569EkkJEzLM1y5/v60OSMhnIUDHGmlzpZDfWGKGT3UYDYDdXLQAMhqvHJAQAAA==',
    推荐: '*',
    
    一级: async function () {
        return rule.getVodList(await fetch(this.input));
    },

    搜索: async function () {
        let {input, KEY, HOST} = this;
        let VODS = [];
        let html = await fetch(input, {
            headers: {...rule.headers, "Content-Type": "application/x-www-form-urlencoded; charset=utf-8"},
            method: 'POST',
            body: `keyboard=${KEY}&submit=搜索&show=title&tempid=1`
        });
        VODS.push(...rule.getVodList(html));
        let searchId = rule.cutStr(html, 'searchid=', '"', '');
        if (searchId) {
            let nextHtml = await fetch(`${HOST || rule.host}/e/search/result/index.php?page=1&searchid=${searchId}`);
            VODS.push(...rule.getVodList(nextHtml));
        }
        return VODS;
    },

    二级: async function () {
        let {input, HOST} = this;
        let [id, kname, kpic, kremarks] = input.split('@');
        let html = await fetch(id);
        const clean = (s) => {
            if (!s) return '';
            try { s = decodeURIComponent(s); } catch (e) {}
            return s.replace(/<[^>]+>|&nbsp;|\s+|手机版|-在线免费观看-|电影港(?:\(DS\))?/g, '').trim();
        };
        let kdetail = pdfh(html, '.ct-l').split('<strong>')[0];
        let finalName = clean(pdfh(html, 'title')) || clean(kname);
        let tabs = [
            ...(pdfa(html, 'strong:has(span)').map((it, i) => rule.cutStr(it, '【', '】', `磁力线${i + 1}`))),
            ...(pdfa(html, '#tab81').map(it => pdfh(it, 'body&&Text')))
        ];
        let urls = [
            ...(pdfa(html, 'tbody').map(item => 
                pdfa(item, 'a').map(it => pdfh(it, 'body&&Text') + '$' + pdfh(it, 'a&&href')).join('#')
            )),
            ...(pdfa(html, '.videourl').map(item => 
                pdfa(item, 'a').map(it => pdfh(it, 'body&&Text') + '$' + pd(it, 'a&&href', HOST || rule.host)).join('#')
            ))
        ];

        return {
            vod_id: id,
            vod_name: finalName,
            vod_pic: kpic,
            type_name: rule.cutStr(kdetail, '◎类别', '◎', '类型'),
            vod_remarks: clean(kremarks),
            vod_year: rule.cutStr(kdetail, '◎年代', '◎', '1000'),
            vod_area: rule.cutStr(kdetail, '◎产地', '◎', '地区'),
            vod_lang: rule.cutStr(kdetail, '◎语言', '◎', '语言'),
            vod_director: rule.cutStr(kdetail, '◎导演', '◎', '导演'),
            vod_actor: rule.cutStr(kdetail, '◎演员', '</p>', '') || rule.cutStr(kdetail, '◎主演', '</p>', '主演'),
            vod_content: clean(rule.cutStr(kdetail, '◎简介£>', '</p>', '')) || finalName,
            vod_play_from: tabs.join('$$$'),
            vod_play_url: urls.join('$$$')
        };
    },

    play_parse: true,
    lazy: async function () {
        let {input} = this;
        if (/^magnet/.test(input)) return { jx: 0, parse: 0, url: input };
        let url = input;
        try {
            let html = await fetch(input);
            let realUrl = rule.cutStr(html, "a:'", "'", '');
            if (!/m3u8|mp4|mkv/.test(realUrl)) {
                let iframeSrc = rule.cutStr(html, '<iframe£src="', '"', '');
                if (iframeSrc) {
                    let iframeHtml = await fetch(iframeSrc);
                    realUrl = getHome(iframeSrc) + rule.cutStr(iframeHtml, 'url = "', '"', '');
                }
            }
            if (/m3u8|mp4|mkv/.test(realUrl)) url = realUrl;
        } catch (e) {}
        
        return { jx: 0, parse: 1, url: url, header: rule.headers };
    },

    getVodList: function(html) {
        let list = pdfa(html, '.m1') || [];
        return list.map(it => {
            let name = rule.cutStr(it, 'alt="', '"', '名称');
            let pic = rule.cutStr(it, 'data-original="', '"', '图片');
            let remark = rule.cutStr(it, 'other">', '</p>', '状态');
            try { remark = decodeURIComponent(remark).replace(/<[^>]+>|&nbsp;/g, '').trim(); } catch(e) {}
            return {
                vod_name: name,
                vod_pic: pic,
                vod_remarks: remark,
                vod_id: `${rule.cutStr(it, 'href="', '"', 'Id')}@${name}@${pic}@${remark}`
            };
        });
    },

    cutStr: function(str, pre, suf, def = '') {
        try {
            if (!str) return def;
            let esc = s => s.replace(/[.*+?${}()|[\]\\/^]/g, '\\$&').replace(/£/g, '[^]*?');
            let reg = new RegExp(`${esc(pre)}([^]*?)${esc(suf)}`);
            let res = str.match(reg)?.[1] ?? def;
            return res.replace(/<[^>]+>|&nbsp;|\s+/g, ' ').trim();
        } catch { return def; }
    }
};