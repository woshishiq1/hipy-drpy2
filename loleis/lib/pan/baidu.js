/**
 * 百度网盘处理类 
 * 提供分享链接解析、文件列表获取、播放链接生成功能
 * 
 * @module BaiduHandler
 * @author 优雅
 * @since 1.0.0
 */

import { Crypto as CryptoJS } from 'assets://js/lib/cat.js';

// 全局调试开关
let DEBUG = globalThis.baidu_debug || 0;

/**
 * 日志输出
 */
function log(tag, message) {
    if (!DEBUG) return;
    console.log(`【百度-${tag}】 ${message}`);
}

class BaiduHandler {
    /**
     * 初始化百度网盘处理器
     * 配置正则表达式、请求头、API地址等基础参数
     */
    constructor() {
        // 百度分享链接正则表达式 - 匹配标准分享链接和提取密码
        this.regex = /https:\/\/pan\.baidu\.com\/s\/([^?&#]+)(?:\?.*?pwd=([^&]+))?/;
        
        // 基础请求头配置
        this.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
            'Referer': 'https://pan.baidu.com/',
            "Connection": "keep-alive",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh,en-GB;q=0.9,en-US;q=0.8,en;q=0.7,zh-CN;q=0.6"
        };
        
        // 百度网盘API基础地址
        this.api = 'https://pan.baidu.com';
        
        // 应用ID - 用于API请求标识
        this.app_id = 250528;
        
        // 视图模式 - 1表示列表视图
        this.view_mode = 1;
        
        // 渠道标识
        this.channel = 'chunlei';
        
        // 清晰度类型定义
        this.type = ["M3U8_AUTO_4K", "M3U8_AUTO_2K", "M3U8_AUTO_1080", "M3U8_AUTO_720", "M3U8_AUTO_480"];
    }

    /**
     * 获取百度Cookie
     * 从全局变量 baidu_cookie 中读取
     * @returns {string} 百度Cookie字符串
     */
    get cookie() {
        return globalThis.baidu_cookie || '';
    }
    
    /**
     * 设置百度Cookie
     * 存储到全局变量 baidu_cookie 中
     * @param {string} value - Cookie字符串
     */
    set cookie(value) {
        globalThis.baidu_cookie = value;
    }

    /**
     * 延时函数
     */
    delay(ms) {
        return new Promise((resolve) => setTimeout(resolve, ms));
    }

    /**
     * 统一请求函数
     * @param {string} url - 请求地址
     * @param {object} options - 请求配置
     * @param {number} retries - 重试次数
     * @param {string} requestType - 请求类型标识
     */
    async request(url, options, retries = 2, requestType = '未知') {
        log('请求', `【${requestType}】 ${options.method || 'GET'} ${url.substring(0, 100)}${url.length > 100 ? '...' : ''}`);
        if (DEBUG && options.data) {
            const dataStr = JSON.stringify(options.data);
            log('请求数据', `【${requestType}】 ${dataStr.substring(0, 300)}`);
        }
        
        for (let i = 0; i <= retries; i++) {
            try {
                const response = await req(url, options);
                log('响应', `【${requestType}】 ${response.code || response.status || 'unknown'}`);
                
                if (response.content) {
                    try {
                        return JSON.parse(response.content);
                    } catch {
                        return { content: response.content, status: response.status };
                    }
                }
                return { status: response.status };
            } catch (error) {
                log('错误', `【${requestType}】 失败 (${i + 1}/${retries + 1}): ${error?.message || error}`);
                if (i === retries) {
                    return { 
                        error: true, 
                        code: -1, 
                        message: '请求失败: ' + (error?.message || '未知错误')
                    };
                }
                await this.delay(100);
            }
        }
    }

    /**
     * 格式化文件大小
     * 将字节数转换为人类可读的格式 (B, KB, MB, GB, TB)
     * @param {number} bytes - 文件大小（字节）
     * @returns {string} 格式化后的文件大小
     */
    formatFileSize(bytes) {
        if (!bytes) return '0 B';
        const units = ['B', 'KB', 'MB', 'GB', 'TB'];
        let i = 0;
        let size = bytes;
        while (size >= 1024 && i < units.length - 1) {
            size /= 1024;
            i++;
        }
        return size.toFixed(2) + ' ' + units[i];
    }

    /**
     * 对象转查询字符串
     * 将对象转换为URL查询参数格式
     * @param {Object} obj - 要转换的对象
     * @returns {string} URL查询字符串
     */
    objectToQuery(obj) {
        return Object.entries(obj)
            .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
            .join('&');
    }

    /**
     * 解析分享链接
     * 从分享URL中提取surl和密码
     * @param {string} url - 百度分享链接
     * @returns {Object|null} 包含surl和pwd的对象，解析失败返回null
     */
    getShareData(url) {
        const matches = this.regex.exec(url);
        if (!matches || !matches[1]) return null;
        return { surl: matches[1], pwd: matches[2] || '' };
    }
    
    /**
     * 获取随机密钥(randsk)并返回独立Cookie
     * 验证分享密码并获取访问凭证
     * @param {Object} shareData - 分享数据，包含surl和pwd
     * @returns {Object|null} 包含randsk和cookie的对象，失败返回null
     */
    async getRandsk(shareData) {
        // 注意：verify接口需要去掉开头的1
        const shorturl = shareData.surl.replace(/^1+/, '');
        const timestamp = Date.now();
        const baseCookie = this.cookie;
        const verUrl = `${this.api}/share/verify?t=${timestamp}&surl=${shorturl}`;
        
        // 准备两种数据格式
        const formData = { pwd: shareData.pwd || '' };
        const postData = `pwd=${encodeURIComponent(shareData.pwd || '')}`;
        const dataFormats = [
            { data: formData, type: 'object' },
            { data: postData, type: 'string' }
        ];
        
        for (const format of dataFormats) {
            try {
                const result = await this.request(verUrl, {
                    method: 'POST',
                    headers: {
                        ...this.headers,
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'Cookie': baseCookie
                    },
                    data: format.data
                }, 3, '验证分享密码');
                
                if (!result.error && result.errno === 0 && result.randsk) {
                    const randsk = result.randsk;
                    const BDCLND = `BDCLND=${randsk}`;
                    
                    // 构建独立Cookie，不修改全局
                    let independentCookie;
                    if (!baseCookie.includes('BDCLND')) {
                        independentCookie = baseCookie + (baseCookie ? '; ' : '') + BDCLND;
                    } else {
                        independentCookie = baseCookie.replace(/BDCLND=[^;]+/, BDCLND);
                    }
                    
                    return { randsk, cookie: independentCookie };
                }
            } catch (error) {
                log('Randsk', `${format.type}格式失败: ${error.message}`);
            }
        }
        
        log('Randsk', `所有数据格式都失败`);
        return null;
    }

    /**
     * 获取分享文件列表
     * 获取分享链接根目录的文件和目录列表
     * @param {Object} shareData - 分享数据，包含surl和pwd
     * @returns {Object|null} 包含list、uk、shareid、title、cookie的对象，失败返回null
     */
    async getShareList(shareData) {
        const shorturl = shareData.surl.replace(/^1+/, '');
        const randskResult = await this.getRandsk(shareData);
        if (!randskResult) return null;
        
        const headers = { ...this.headers, 'Cookie': randskResult.cookie };
        
        const listUrl = `${this.api}/share/list?` + this.objectToQuery({
            web: 5,
            app_id: this.app_id,
            desc: 1,
            showempty: 0,
            page: 1,
            num: 100,
            order: 'time',
            shorturl: shorturl,
            root: 1,
            view_mode: this.view_mode,
            channel: this.channel,
            clienttype: 0
        });
        
        const listResult = await this.request(listUrl, {
            method: 'GET',
            headers: headers
        }, 3, '获取分享列表');
        
        if (listResult.error || listResult.errno !== 0) {
            log('分享列表', `获取失败: errno=${listResult.errno}`);
            return null;
        }
        
        return {
            list: listResult.list,
            uk: listResult.uk,
            shareid: listResult.share_id,
            title: listResult.title,
            cookie: randskResult.cookie
        };
    }

    /**
     * 获取指定路径下的文件列表
     * 递归获取子目录中的文件
     * @param {string} path - 目录路径
     * @param {Object} shareInfo - 分享信息，包含uk和shareid
     * @param {Object} shareData - 分享数据，包含surl和pwd
     * @returns {Array} 文件列表
     */
    async getSharepath(path, shareInfo, shareData) {
        const randskResult = await this.getRandsk(shareData);
        if (!randskResult) return [];
        
        const headers = { ...this.headers, 'Cookie': randskResult.cookie };
        
        const dirUrl = `${this.api}/share/list?` + this.objectToQuery({
            is_from_web: true,
            uk: shareInfo.uk,
            shareid: shareInfo.shareid,
            order: 'name',
            desc: 0,
            showempty: 0,
            view_mode: this.view_mode,
            page: 1,
            num: 100,
            dir: path,
            channel: this.channel,
            app_id: this.app_id
        });
        
        const dirResult = await this.request(dirUrl, {
            method: 'GET',
            headers: headers
        }, 3, `获取目录列表-${path}`);
        
        if (dirResult.error || dirResult.errno !== 0) return [];
        return dirResult.list || [];
    }

    /**
     * 从文件项中提取视频信息
     * 提取文件名、路径、缩略图、大小等信息
     * @param {Object} item - 文件项
     * @param {Object} shareInfo - 分享信息
     * @param {Object} shareData - 分享数据
     * @returns {Object} 视频信息对象
     */
    extractVideoInfo(item, shareInfo, shareData) {
        const fileName = item.server_filename || item.path.split('/').pop();
        
        // 提取缩略图
        let thumbnail = '';
        if (item.thumbs) {
            thumbnail = item.thumbs.url || item.thumbs.icon || '';
        } else if (item.icon) {
            thumbnail = item.icon;
        }
        
        return {
            name: fileName,
            path: item.path.replaceAll('#', '\0'),
            uk: shareInfo.uk,
            shareid: shareInfo.shareid,
            fsid: item.fs_id || item.fsid,
            surl: shareData.surl,
            size: item.size,
            thumbnail: thumbnail
        };
    }

    /**
     * 获取分享中的视频文件列表 - 主入口方法
     * 递归获取分享中的所有视频文件
     * @param {Object} shareData - 分享数据，包含surl和pwd
     * @returns {Array} 视频文件列表
     */
    async getFilesByShareUrl(shareData) {
        log('文件列表', `开始获取`);
        if (!shareData || !shareData.surl) return [];
        
        const listResult = await this.getShareList(shareData);
        if (!listResult || !listResult.list) return [];
        
        const shareInfo = {
            uk: listResult.uk,
            shareid: listResult.shareid
        };
        
        let dirs = [];
        let videos = [];
        
        // 处理根目录文件
        listResult.list.map(item => {
            if (item.category === '6' || item.category === 6) {
                dirs.push(item.path);
            }
            if (item.category === '1' || item.category === 1) {
                videos.push(this.extractVideoInfo(item, shareInfo, shareData));
            }
        });
        
        // 处理子目录
        if (dirs.length > 0) {
            const results = await Promise.all(dirs.map(async (path) => {
                const dirItems = await this.getSharepath(path, shareInfo, shareData);
                if (dirItems.length === 0) return [];
                
                let subDirs = [];
                let subVideos = [];
                
                dirItems.map(item => {
                    if (item.category === '6' || item.category === 6) {
                        subDirs.push(item.path);
                    }
                    if (item.category === '1' || item.category === 1) {
                        subVideos.push(this.extractVideoInfo(item, shareInfo, shareData));
                    }
                });
                
                // 处理更深层目录
                if (subDirs.length > 0) {
                    const deeperResults = await Promise.all(subDirs.map(subPath => 
                        this.getSharepath(subPath, shareInfo, shareData)
                    ));
                    
                    deeperResults.forEach(deeperItems => {
                        deeperItems.forEach(item => {
                            if (item.category === '1' || item.category === 1) {
                                subVideos.push(this.extractVideoInfo(item, shareInfo, shareData));
                            }
                        });
                    });
                }
                
                return subVideos;
            }));
            
            results.flat().forEach(video => videos.push(video));
        }
        
        log('文件列表', `找到 ${videos.length} 个视频`);
        return videos;
    }

    /**
     * 获取用户UID
     * 通过百度MBD接口获取用户唯一标识
     * @returns {string} 用户UID
     */
    async getUid() {
        const headers = { ...this.headers, 'Cookie': this.cookie };
        
        const result = await this.request('https://mbd.baidu.com/userx/v1/info/get?appname=baiduboxapp&fields=%20%20%20%20%20%20%20%20%5B%22bg_image%22,%22member%22,%22uid%22,%22avatar%22,%20%22avatar_member%22%5D&client&clientfrom&lang=zh-cn&tpl&ttt', {
            method: 'GET',
            headers: headers
        }, 3, '获取用户UID');
        
        return result.data?.fields?.uid || result.data?.uid || result.uid || '';
    }

    /**
     * SHA1哈希计算
     * 使用CryptoJS进行SHA1加密
     * @param {string} message - 待加密字符串
     * @returns {string} SHA1哈希值（十六进制）
     */
    sha1(message) {
        return CryptoJS.SHA1(message).toString(CryptoJS.enc.Hex);
    }

    /**
     * 获取签名
     * 用于Web版播放链接的签名验证
     * @param {Object} shareData - 分享数据，包含surl（完整surl，带开头的1）
     * @returns {Promise<string|null>} 签名字符串，失败返回null
     */
    async getSign(shareData) {
        // 注意：tplconfig接口需要完整的surl（带开头的1）
        const url = `${this.api}/share/tplconfig?surl=${shareData.surl}&fields=Espace_info,card_info,sign,timestamp&view_mode=${this.view_mode}&channel=${this.channel}&web=1&app_id=${this.app_id}`;
        const headers = { ...this.headers, 'Cookie': this.cookie };
        const data = await this.request(url, { headers }, 3, '获取签名');
        
        if (data.error || data.errno !== 0 || !data.data) {
            log('签名', `获取失败`);
            return null;
        }
        
        return data.data.sign;
    }

    /**
     * 获取文件的直链地址（App版）
     * 生成百度网盘App接口的播放直链
     * @param {string} path - 文件路径
     * @param {string} uk - 用户uk
     * @param {string} shareid - 分享ID
     * @param {string} fsid - 文件fsid
     * @param {Object} shareData - 分享数据，包含surl和pwd
     * @returns {string|null} 播放直链，失败返回null
     */
    async getAppShareUrl(path, uk, shareid, fsid, shareData) {
        path = path.replaceAll('\0', '#');
        
        const randskResult = await this.getRandsk(shareData);
        if (!randskResult) return null;
        
        const uid = await this.getUid();
        if (!uid) return null;

        // 构建App接口请求头
        const headers = { 
            ...this.headers, 
            'Cookie': randskResult.cookie,
            "User-Agent": 'netdisk;P2SP;2.2.91.136;android-android;'
        };
        
        const devuid = "73CED981D0F186D12BC18CAE1684FFD5|VSRCQTF6W";
        const time = String(Date.now());

        const bdussMatch = randskResult.cookie.match(/BDUSS=(.+?);/);
        if (!bdussMatch) return null;
        
        const BDUSS = bdussMatch[1];

        // 计算签名
        const rand = this.sha1(
            this.sha1(BDUSS) + 
            uid + 
            "ebrcUYiuxaZv2XGu7KIYKxUrqfnOfpDF" + 
            time + 
            devuid + 
            "11.30.2ae5821440fab5e1a61a025f014bd8972"
        );

        const url = this.api + "/share/list?" + this.objectToQuery({
            shareid, 
            uk, 
            fid: fsid,
            sekey: randskResult.randsk,
            origin: 'dlna',
            devuid,
            clienttype: 1,
            channel: 'android_12_zhao_bd-netdisk_1024266h',
            version: '11.30.2',
            time,
            rand
        });
        
        const result = await this.request(url, {
            method: "GET",
            headers: headers
        }, 3, '获取App直链');
        
        if (result.error || result.errno !== 0 || !result.list?.length) return null;
        return result.list[0].dlink;
    }

    /**
     * 获取Web版播放链接
     * 返回不同清晰度的播放链接数组
     * 使用流程: 先通过getFilesByShareUrl获取视频信息，然后用其中的uk、shareid、fsid和shareData调用此方法
     * 
     * @param {string} path - 文件路径（支持\0转义的路径）
     * @param {string} uk - 用户UK
     * @param {string} shareid - 分享ID
     * @param {string} fsid - 文件ID
     * @param {Object} shareData - 分享数据，包含surl（完整surl，带开头的1）
     * @returns {Promise<Array>} 播放链接数组，每个元素包含{name, url}，name为清晰度名称
     */
    async getWebPlayUrls(path, uk, shareid, fsid, shareData) {
        // 还原被替换的#字符
        path = path.replace(/\0/g, '#');
        // 获取签名
        const sign = await this.getSign(shareData);
        if (!sign) return [];
        
        const timestamp = Math.floor(Date.now() / 1000);
        const urls = [];
        
        // 生成不同清晰度的播放链接
        this.type.forEach(type => {
            const urlInfo = {
                name: type.replace('M3U8_AUTO_', ''),
                url: `${this.api}/share/streaming?channel=${this.channel}&uk=${uk}&fid=${fsid}&sign=${sign}&timestamp=${timestamp}&shareid=${shareid}&type=${type}&vip=0&jsToken&isplayer=1&check_blue=1&adToken`
            };
            urls.push(urlInfo);
        });
        
        return urls;
    }
}

export const Baidu = new BaiduHandler();