/**
 * UC网盘处理工具
 * 
 * 提供UC网盘分享链接解析、文件下载等功能。
 * 
 * @module UCPanHandler
 * @author 优雅
 * @since 1.0.0
 */

import { Crypto as CryptoJS } from 'assets://js/lib/cat.js';

// 全局调试开关
let DEBUG = globalThis.uc_debug || 0;

/**
 * 日志输出
 */
function log(tag, message) {
    if (!DEBUG) return;
    console.log(`【UC-${tag}】 ${message}`);
}

// 错误码定义
const ERROR_CODES = {
    // 空间相关
    32003: { message: "网盘空间不足，请清理空间或开通会员" },
    32008: { message: "存储配额已用完" },
    
    // 认证相关
    31001: { message: "未登录或Cookie已失效，请重新获取Cookie" },
    31002: { message: "登录态已过期，请重新登录" },
    32004: { message: "Cookie已失效，请重新获取" },
    32011: { message: "登录态已过期" },
    32012: { message: "认证失败，请检查Cookie" },
    32014: { message: "账号异常，请重新登录" },
    
    // 限流相关
    32001: { message: "请求过于频繁，请稍后再试" },
    32002: { message: "操作频率过高" },
    
    // 文件相关
    32005: { message: "文件不存在" },
    32006: { message: "文件已被删除" },
    32007: { message: "文件格式不支持" },
    
    // 分享相关
    32009: { message: "分享链接已失效" },
    32010: { message: "提取码错误" },
    32013: { message: "分享文件已被删除" }
};

/**
 * UC网盘处理类
 */
class UCHandler {
    constructor() {
        // UC分享链接正则表达式 - 匹配标准分享链接和提取密码
        this.regex = /https:\/\/drive\.uc\.cn\/s\/([^?&#]+)(?:\?.*?pwd=([^&]+))?/;
        // 请求参数
        this.pr = 'pr=UCBrowser&fr=pc';
        // 基础请求头
        this.baseHeader = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) uc-cloud-drive/1.8.5 Chrome/100.0.4896.160 Electron/18.3.5.16-b62cf9c50d Safari/537.36 Channel/ucpan_other_ch',
            'Referer': 'https://drive.uc.cn/',
            'Origin': 'https://drive.uc.cn',
           'Content-Type': 'application/json'
        };
        // API基础URL
        this.apiUrl = 'https://pc-api.uc.cn/1/clouddrive';
        // 分享令牌缓存
        this.shareTokenCache = {};
        // 保存目录名称
        this.saveDirName = 'drpy';
        // 保存目录ID
        this.saveDirId = null;
        // 保存文件ID缓存
        this.saveFileIdCaches = {};
        // 字幕文件扩展名
        this.subtitleExts = ['.srt', '.ass', '.scc', '.stl', '.ttml'];
        // 视频文件扩展名
        this.videoExts = ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mpg', '.mpeg', '.ts', '.m3u8'];
        // 视频扩展名开关（1=启用判断，0=禁用）
        this.videoExtsEnabled = 0;
        
        // Cookie和Token存储
        this._cookie = "";
        this._token = "";
        
        // Token和Cookie有效期记录
        this.tokenExpireTime = 0;
        this.cookieExpireTime = 0;
        
        // 播放地址临时缓存（20分钟）
        this.urlCache = {};
        this.cacheTTL = 20 * 60 * 1000;
        
        // 上次刷新时间
        this.lastRefreshTime = 0;
        this.refreshInterval = 4 * 24 * 60 * 60 * 1000;
        
        // UC TV配置
        this.ucConfig = {
            api: "https://open-api-drive.uc.cn",
            clientID: "5acf882d27b74502b7040b0c65519aa7",
            signKey: "l3srvtd7p42l0d0x1u8d7yc8ye9kki4d",
            appVer: "1.6.8",
            channel: "UCTVOFFICIALWEB",
            deviceID: "07b48aaba8a739356ab8107b5e230ad4"
        }
        
        // 刷新锁
        this._isRefreshing = false;
        this._refreshPromise = null;
    }

    /**
     * 获取Cookie
     */
    get cookie() {
        if (this._cookie && this.cookieExpireTime > Date.now()) {
            return this._cookie;
        }
        if (globalThis.uc_cookie) {
            this._cookie = globalThis.uc_cookie;
            this.cookieExpireTime = Date.now() + 7 * 24 * 60 * 60 * 1000;
        }
        return this._cookie;
    }

    /**
     * 设置Cookie
     */
    set cookie(value) {
        this._cookie = value || '';
        if (value) {
            this.cookieExpireTime = Date.now() + 7 * 24 * 60 * 60 * 1000;
            globalThis.uc_cookie = value;
        }
    }

    /**
     * 获取Token
     */
    get token() {
        if (this._token && this.tokenExpireTime > Date.now()) {
            return this._token;
        }
        if (globalThis.uc_token) {
            this._token = globalThis.uc_token;
            try {
                const parts = this._token.split('.');
                if (parts.length >= 2) {
                    const payload = JSON.parse(CryptoJS.enc.Base64.parse(parts[1]).toString(CryptoJS.enc.Utf8));
                    this.tokenExpireTime = payload.exp * 1000;
                }
            } catch (e) {}
        }
        return this._token;
    }

    /**
     * 设置Token
     */
    set token(value) {
        this._token = value || '';
        if (value) {
            try {
                const parts = value.split('.');
                if (parts.length >= 2) {
                    const payload = JSON.parse(CryptoJS.enc.Base64.parse(parts[1]).toString(CryptoJS.enc.Utf8));
                    this.tokenExpireTime = payload.exp * 1000;
                }
            } catch (e) {}
            globalThis.uc_token = value;
        }
    }

    /**
     * 获取请求头
     */
    getHeaders() {
        return { ...this.baseHeader, Cookie: this.cookie };
    }
    
    /**
     * 延时函数
     */
    delay(ms) {
        return new Promise((resolve) => setTimeout(resolve, ms));
    }

    /**
     * 获取缓存的播放地址
     */
    getCachedUrl(shareId, fileId) {
        const cacheKey = `${shareId}_${fileId}`;
        const cached = this.urlCache[cacheKey];
        if (cached && (Date.now() - cached.timestamp) < this.cacheTTL) {
            return cached.urls;
        }
        if (cached) delete this.urlCache[cacheKey];
        return null;
    }

    /**
     * 设置缓存的播放地址
     */
    setCachedUrl(shareId, fileId, urls) {
        const cacheKey = `${shareId}_${fileId}`;
        this.urlCache[cacheKey] = { urls: urls, timestamp: Date.now() };
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
                        code: 31001, 
                        message: ERROR_CODES[31001]?.message || '未登录或Cookie已失效，请重新获取Cookie' 
                    };
                }
                await this.delay(100);
            }
        }
    }

    /**
     * 初始化UC
     */
    async initUC(db, cfg) {
        if (cfg?.uc_cookie) this.cookie = cfg.uc_cookie;
        if (cfg?.uc_token) this.token = cfg.uc_token;
        if (cfg?.uc_videoExtsEnabled !== undefined) this.videoExtsEnabled = cfg.uc_videoExtsEnabled;
        if (this.lastRefreshTime === 0) this.lastRefreshTime = Date.now();
        await this.ensureTokenAndCookie();
        log('初始化', `完成, videoExtsEnabled=${this.videoExtsEnabled}`);
    }

    /**
     * 解析分享链接
     * 从分享URL中提取shareId和密码
     * @param {string} url - UC分享链接
     * @returns {Object|null} 包含shareId、folderId、passCode的对象，解析失败返回null
     */
    getShareData(url) {
        const matches = this.regex.exec(url);
        if (!matches || !matches[1]) return null;
        
        let shareId = matches[1];
        if (shareId.indexOf("?") > 0) shareId = shareId.split('?')[0];
        // public=1 表示无密码，否则使用正则捕获的密码
        let passCode = matches[2] || '';
        // 如果URL中有public=1参数，则密码为空
        if (url.includes('public=1')) {
            passCode = '';
        }
        
        return { shareId: shareId, folderId: '0', passCode: passCode };
    }

    /**
     * 获取分享令牌
     */
    async getShareToken(shareData) {
        if (!this.shareTokenCache[shareData.shareId]) {
            const url = `${this.apiUrl}/share/sharepage/token?${this.pr}`;
            const result = await this.request(url, {
                method: 'POST',
                data: { pwd_id: shareData.shareId, passcode: shareData.passCode || '' },
                headers: this.baseHeader
            }, 3, '获取分享令牌');
            if (result.data?.stoken) {
                this.shareTokenCache[shareData.shareId] = result.data;
            } else {
                log('分享令牌', `获取失败: ${shareData.shareId}`);
            }
        }
    }

    /**
     * 通过分享链接获取文件列表
     */
    async getFilesByShareUrl(shareInfo) {
        log('文件列表', `开始获取`);
        const shareData = typeof shareInfo === 'string' ? this.getShareData(shareInfo) : shareInfo;
        if (!shareData) return [];
        
        await this.getShareToken(shareData);
        if (!this.shareTokenCache[shareData.shareId]) return [];
        
        const videos = [];
        const subtitles = [];
        
        const listFile = async (shareId, folderId, page = 1) => {
            const prePage = 200;
            const url = `${this.apiUrl}/share/sharepage/detail?pwd_id=${shareId}&stoken=${encodeURIComponent(this.shareTokenCache[shareId].stoken)}&pdir_fid=${folderId}&force=0&_page=${page}&_size=${prePage}&_sort=file_type:asc,file_name:asc&${this.pr}`;
            const listData = await this.request(url, { method: 'GET', headers: this.baseHeader }, 3, `获取文件列表-${folderId}-p${page}`);
            
            if (!listData.data?.list) return;
            
            const items = listData.data.list;
            const subDir = [];
            
            for (const item of items) {
                const fileName = item.file_name || '';
                if (item.dir === true) {
                    subDir.push(item);
                } else if (item.file === true && item.size >= 1024 * 1024 * 5) {
                    // 判断是否为视频文件
                    let isVideo = false;
                    
                    // 如果启用视频扩展名判断
                    if (this.videoExtsEnabled === 1) {
                        const isVideoExt = this.videoExts.some(ext => fileName.toLowerCase().endsWith(ext));
                        isVideo = item.obj_category === 'video' || isVideoExt;
                    } else {
                        // 禁用扩展名判断，只依赖UC分类
                        isVideo = item.obj_category === 'video';
                    }
                    
                    if (isVideo) {
                        item.stoken = this.shareTokenCache[shareData.shareId].stoken;
                        item.formatted_size = this.formatFileSize(item.size);
                        if (!item.share_fid_token && item.fid_token) item.share_fid_token = item.fid_token;
                        if (!item.share_fid_token) item.share_fid_token = item.fid;
                        videos.push(item);
                    }
                } else if (item.type === 'file' && this.subtitleExts.some(x => fileName.endsWith(x))) {
                    subtitles.push(item);
                }
            }
            
            if (page < Math.ceil(listData.metadata?._total / prePage)) {
                await listFile(shareId, folderId, page + 1);
            }
            for (const dir of subDir) {
                await listFile(shareId, dir.fid);
            }
        };
        
        await listFile(shareData.shareId, shareData.folderId);
        
        if (subtitles.length > 0) {
            videos.forEach(item => {
                const matchSubtitle = this.findBestLCS(item, subtitles);
                if (matchSubtitle.bestMatch) item.subtitle = matchSubtitle.bestMatch.target;
            });
        }
        
        log('文件列表', `找到 ${videos.length} 个视频`);
        return videos;
    }

    /**
     * 最长公共子序列
     */
    lcs(str1, str2) {
        if (!str1 || !str2) return { length: 0, sequence: '', offset: 0 };
        let sequence = '';
        const str1Length = str1.length, str2Length = str2.length;
        const num = Array(str1Length).fill().map(() => Array(str2Length).fill(0));
        let maxlen = 0, lastSubsBegin = 0, thisSubsBegin = null;
        for (let i = 0; i < str1Length; i++) {
            for (let j = 0; j < str2Length; j++) {
                if (str1[i] === str2[j]) {
                    num[i][j] = (i === 0 || j === 0) ? 1 : 1 + num[i - 1][j - 1];
                    if (num[i][j] > maxlen) {
                        maxlen = num[i][j];
                        thisSubsBegin = i - num[i][j] + 1;
                        if (lastSubsBegin === thisSubsBegin) {
                            sequence += str1[i];
                        } else {
                            lastSubsBegin = thisSubsBegin;
                            sequence = str1.substr(lastSubsBegin, i + 1 - lastSubsBegin);
                        }
                    }
                }
            }
        }
        return { length: maxlen, sequence: sequence, offset: thisSubsBegin };
    }

    /**
     * 查找最佳匹配
     */
    findBestLCS(mainItem, targetItems) {
        const results = [];
        let bestMatchIndex = 0;
        for (let i = 0; i < targetItems.length; i++) {
            const currentLCS = this.lcs(mainItem.name || mainItem.file_name, targetItems[i].name || targetItems[i].file_name);
            results.push({ target: targetItems[i], lcs: currentLCS });
            if (currentLCS.length > results[bestMatchIndex].lcs.length) bestMatchIndex = i;
        }
        return { allLCS: results, bestMatch: results[bestMatchIndex], bestMatchIndex: bestMatchIndex };
    }

    /**
     * 格式化文件大小
     */
    formatFileSize(bytes) {
        if (!bytes || bytes == 0) return '0 B';
        const units = ['B', 'KB', 'MB', 'GB', 'TB'];
        let i = 0, size = bytes;
        while (size >= 1024 && i < units.length - 1) { size /= 1024; i++; }
        return size.toFixed(2) + ' ' + units[i];
    }

    /**
     * 清理保存目录
     */
    async clearSaveDir() {
        if (!this.saveDirId) return { success: true };
        
        const url = `${this.apiUrl}/file/sort?pdir_fid=${this.saveDirId}&_page=1&_size=200&_sort=file_type:asc,updated_at:desc&${this.pr}`;
        const listData = await this.request(url, { method: 'GET', headers: this.getHeaders() }, 3, '清理目录-获取列表');
        
        if (listData.code && listData.code !== 200 && listData.code !== 0) {
            return { error: true, code: listData.code, message: ERROR_CODES[listData.code]?.message || '获取目录文件列表失败' };
        }
        
        if (listData.data?.list?.length > 0) {
            const deleteUrl = `${this.apiUrl}/file/delete?${this.pr}`;
            const deleteResult = await this.request(deleteUrl, {
                method: 'POST',
                data: { action_type: 2, filelist: listData.data.list.map(v => v.fid), exclude_fids: [] },
                headers: this.getHeaders()
            }, 3, '清理目录-删除文件');
            
            if (deleteResult.code && deleteResult.code !== 200 && deleteResult.code !== 0) {
                return { error: true, code: deleteResult.code, message: ERROR_CODES[deleteResult.code]?.message || '清理目录失败' };
            }
        }
        
        return { success: true };
    }

    /**
     * 创建保存目录
     */
    async createSaveDir(clean) {
        if (this.saveDirId) {
            if (clean) {
                const clearResult = await this.clearSaveDir();
                if (clearResult && clearResult.error) return clearResult;
            }
            return { success: true, dirId: this.saveDirId };
        }
        
        const url = `${this.apiUrl}/file/sort?pdir_fid=0&_page=1&_size=200&_sort=file_type:asc,updated_at:desc&${this.pr}`;
        const listData = await this.request(url, { method: 'GET', headers: this.getHeaders() }, 3, '创建目录-获取根目录');
        
        if (!listData.code && !listData.data?.list) {
            return { error: true, code: 31001, message: ERROR_CODES[31001]?.message || '未登录或Cookie已失效，请重新获取Cookie' };
        }
        // 检查是否有错误码
        if (listData.code && listData.code !== 200 && listData.code !== 0) {
            const errorMsg = ERROR_CODES[listData.code]?.message || listData.message || '获取目录列表失败';
            log('目录', `获取失败: code=${listData.code}`);
            return { error: true, code: listData.code, message: errorMsg };
        }
        
        // 检查是否有错误信息
        if (listData.message && listData.code !== 200 && listData.code !== 0) {
            return { error: true, code: listData.code || -1, message: listData.message };
        }
        
        if (listData.data?.list) {
            for (const item of listData.data.list) {
                if (item.file_name === this.saveDirName) {
                    this.saveDirId = item.fid;
                    if (clean) {
                        const clearResult = await this.clearSaveDir();
                        if (clearResult && clearResult.error) return clearResult;
                    }
                    return { success: true, dirId: this.saveDirId };
                }
            }
        }
    
        if (!this.saveDirId) {
            const createUrl = `${this.apiUrl}/file?${this.pr}`;
            const create = await this.request(createUrl, {
                method: 'POST',
                data: { pdir_fid: '0', file_name: this.saveDirName, dir_path: '', dir_init_lock: false },
                headers: this.getHeaders()
            }, 3, '创建目录-新建目录');
            
            if (create.code && create.code !== 200 && create.code !== 0) {
                const errorMsg = ERROR_CODES[create.code]?.message || create.message || '创建目录失败';
                log('目录', `创建失败: code=${create.code}`);
                return { error: true, code: create.code, message: errorMsg };
            }
            
            if (create.data?.fid) {
                this.saveDirId = create.data.fid;
                log('目录', `创建成功，ID: ${this.saveDirId}`);
                return { success: true, dirId: this.saveDirId };
            }
        }
        
        return { error: true, code: -1, message: '创建保存目录失败' };
    }
    
    /**
     * 保存文件到个人网盘
     */
    async save(shareId, stoken, fileId, fileToken, clean) {
        const dirResult = await this.createSaveDir(clean);
        if (dirResult.error) {
            return { error: true, code: dirResult.code, message: dirResult.message };
        }
        
        if (clean) Object.keys(this.saveFileIdCaches).forEach(key => delete this.saveFileIdCaches[key]);
        
        if (!stoken) {
            await this.getShareToken({ shareId });
            if (!this.shareTokenCache[shareId]) {
                return { error: true, code: -2, message: '获取分享令牌失败' };
            }
            stoken = this.shareTokenCache[shareId].stoken;
        }
        
        const saveUrl = `${this.apiUrl}/share/sharepage/save?${this.pr}`;
        const saveResult = await this.request(saveUrl, {
            method: 'POST',
            data: {
                fid_list: [fileId],
                fid_token_list: [fileToken],
                to_pdir_fid: this.saveDirId,
                pwd_id: shareId,
                stoken: stoken,
                pdir_fid: '0',
                scene: 'link'
            },
            headers: this.getHeaders()
        }, 3, '保存文件');
        
        // 检查错误
        if (saveResult.code && saveResult.code !== 200 && saveResult.code !== 0) {
            log('保存', `失败: code=${saveResult.code}`);
            return { error: true, code: saveResult.code, message: ERROR_CODES[saveResult.code]?.message || '保存文件失败' };
        }
        
        if (saveResult.data?.task_resp?.code) {
            return { error: true, code: saveResult.data.task_resp.code, message: saveResult.data.task_resp.message || '保存文件失败' };
        }
        
        if (saveResult.data?.task_id) {
            if (saveResult.data.task_resp?.data?.save_as?.save_as_top_fids?.length > 0) {
                return saveResult.data.task_resp.data.save_as.save_as_top_fids[0];
            }
            for (let retry = 0; retry < 10; retry++) {
                await this.delay(1000);
                const taskUrl = `${this.apiUrl}/task?task_id=${saveResult.data.task_id}&retry_index=${retry}&${this.pr}`;
                const taskResult = await this.request(taskUrl, { method: 'GET', headers: this.getHeaders() }, 3, `查询保存任务-${retry+1}`);
                if (taskResult.code && taskResult.code !== 200 && taskResult.code !== 0) {
                    return { error: true, code: taskResult.code, message: ERROR_CODES[taskResult.code]?.message || '查询任务状态失败' };
                }
                if (taskResult.data?.save_as?.save_as_top_fids?.length > 0) {
                    return taskResult.data.save_as.save_as_top_fids[0];
                }
            }
        }
        
        return { error: true, code: -3, message: '保存文件超时，请稍后重试' };
    }

    /**
     * 刷新Token
     */
    async refreshToken() {
        if (this._isRefreshing) return await this._refreshPromise;
        
        this._isRefreshing = true;
        this._refreshPromise = (async () => {
            const currentToken = this.token;
            if (!currentToken) return false;
            
            try {
                const timestamp = Math.floor(Date.now() / 1000).toString() + '000';
                const deviceID = this.ucConfig.deviceID;
                const reqId = this.generateReqId(deviceID, timestamp);
                const data = {
                    req_id: reqId, app_ver: this.ucConfig.appVer, device_id: deviceID,
                    device_brand: "OPPO", platform: "tv", device_name: "PCRT00",
                    device_model: "PCRT00", build_device: "aosp", build_product: "PCRT00",
                    device_gpu: "Adreno%20(TM)%20640", activity_rect: "%7B%7D",
                    channel: this.ucConfig.channel, refresh_token: currentToken
                };
                const resp = await req('http://api.extscreen.com/ucdrive/token', {
                    method: 'POST',
                    headers: {
                        'User-Agent': 'Mozilla/5.0 (Linux; U; Android 7.1.2; zh-cn; PCRT00 Build/N2G47O) AppleWebKit/533.1 (KHTML, like Gecko) Mobile Safari/533.1',
                        'Connection': 'Keep-Alive', 'Content-Type': 'application/json',
                        'Cookie': 'sl-session=VIaxTAKF8mdJBhU2uda0zA=='
                    },
                    data: data
                });
                if (resp.code == 200 && resp.content) {
                    const result = JSON.parse(resp.content);
                    if (result.data?.access_token) {
                        this.token = result.data.access_token;
                        log('Token', `刷新成功`);
                        return true;
                    }
                }
                return false;
            } catch (error) {
                return false;
            }
        })();
        
        try {
            return await this._refreshPromise;
        } finally {
            this._isRefreshing = false;
            this._refreshPromise = null;
        }
    }

    /**
     * 刷新Cookie
     */
    async refreshCookie() {
        if (this._isRefreshing) return await this._refreshPromise;
        
        this._isRefreshing = true;
        this._refreshPromise = (async () => {
            const currentCookie = this.cookie;
            if (!currentCookie) return false;
            
            try {
                const resp = await this.request('https://pc-api.uc.cn/1/clouddrive/config?pr=UCBrowser&fr=pc', {
                    method: "GET",
                    headers: {
                        "User-Agent": this.baseHeader['User-Agent'],
                        Origin: 'https://drive.uc.cn',
                        Referer: 'https://drive.uc.cn/',
                        Cookie: currentCookie
                    }
                }, 3, '刷新Cookie');
                const setCookie = resp.headers?.['set-cookie'] || resp.headers?.['Set-Cookie'];
                if (!setCookie) return false;
                
                const cookieObject = {};
                const cookieParts = Array.isArray(setCookie) ? setCookie : [setCookie];
                for (const part of cookieParts) {
                    const match = part.match(/([^=;]+)=([^;]+)/);
                    if (match) cookieObject[match[1].trim()] = match[2].trim();
                }
                if (cookieObject.__puus) {
                    const oldCookies = {};
                    currentCookie.split(';').forEach(part => {
                        const trimmed = part.trim();
                        const eqIndex = trimmed.indexOf('=');
                        if (eqIndex > 0) oldCookies[trimmed.substring(0, eqIndex)] = trimmed.substring(eqIndex + 1);
                    });
                    const newCookie = Object.entries({
                        __pus: oldCookies.__pus, __puus: cookieObject.__puus,
                    }).map(([key, value]) => `${key}=${value}`).join('; ');
                    this.cookie = newCookie;
                    log('Cookie', `刷新成功`);
                    return true;
                }
                return false;
            } catch (error) {
                return false;
            }
        })();
        
        try {
            return await this._refreshPromise;
        } finally {
            this._isRefreshing = false;
            this._refreshPromise = null;
        }
    }

    /**
     * 验证Token是否有效
     */
    async validToken() {
        if (!this.token) return false;
        if (this.tokenExpireTime > Date.now()) return true;
        log('Token', `已过期`);
        return false;
    }

    /**
     * 验证Cookie是否有效
     */
    async validCookie() {
        const currentCookie = this.cookie;
        if (!currentCookie) return false;
        try {
            const resp = await this.request('https://pc-api.uc.cn/1/clouddrive/config?pr=UCBrowser&fr=pc', {
                method: "GET",
                headers: {
                    "User-Agent": this.baseHeader['User-Agent'],
                    Origin: 'https://drive.uc.cn',
                    Referer: 'https://drive.uc.cn/',
                    Cookie: currentCookie
                }
            }, 1, '验证Cookie');
            if (resp.code == 200 || resp.status == 200) return true;
            return false;
        } catch (error) {
            return false;
        }
    }

    /**
     * 确保Token和Cookie有效
     */
    async ensureTokenAndCookie() {
        const needRefresh = () => {
            if (this.lastRefreshTime === 0) return true;
            if (Date.now() - this.lastRefreshTime >= this.refreshInterval) return true;
            return false;
        };
        
        if (!needRefresh()) {
            const tokenValid = await this.validToken();
            const cookieValid = await this.validCookie();
            if (tokenValid && cookieValid) return true;
        }
        
        const tokenResult = await this.refreshToken();
        const cookieResult = await this.refreshCookie();
        
        if (tokenResult || cookieResult) {
            this.lastRefreshTime = Date.now();
            return true;
        }
        
        return false;
    }

    /**
     * 生成设备ID
     */
    generateDeviceID(timestamp) {
        return CryptoJS.MD5(timestamp).toString().slice(0, 16);
    }

    /**
     * 生成请求ID
     */
    generateReqId(deviceID, timestamp) {
        return CryptoJS.MD5(deviceID + timestamp).toString().slice(0, 16);
    }

    /**
     * 获取下载链接
     */
    async getDownload(shareId, stoken, fileId, fileToken, clean = false) {
        // 先检查缓存
        const cachedResult = this.getCachedUrl(shareId, fileId);
        if (cachedResult) return cachedResult;
        
        await this.ensureTokenAndCookie();
        
        if (!this.saveFileIdCaches[fileId]) {
            const saveResult = await this.save(shareId, stoken, fileId, fileToken, clean);
            if (saveResult && saveResult.error) return saveResult;
            if (!saveResult) return { error: true, code: -1, message: '文件转存失败' };
            this.saveFileIdCaches[fileId] = saveResult;
        }
        
        let result = null;
        
        // 尝试获取无限画质链接
        if (this.token) {
            const timestamp = Math.floor(Date.now() / 1000).toString() + '000';
            const deviceID = this.ucConfig.deviceID;
            const reqId = this.generateReqId(deviceID, timestamp);
            const x_pan_token = CryptoJS.SHA256('GET&/file&' + timestamp + '&' + this.ucConfig.signKey).toString();
            const params = {
                req_id: reqId, access_token: this.token, app_ver: this.ucConfig.appVer,
                device_id: deviceID, device_brand: 'Xiaomi', platform: 'tv',
                device_name: 'M2004J7AC', device_model: 'M2004J7AC',
                build_device: 'M2004J7AC', build_product: 'M2004J7AC',
                device_gpu: 'Adreno (TM) 550', activity_rect: '{}',
                channel: this.ucConfig.channel, method: 'streaming',
                group_by: 'source', fid: this.saveFileIdCaches[fileId],
                resolution: 'low,normal,high,super,2k,4k', support: 'dolby_vision'
            };
            const urlParams = Object.entries(params).map(([k, v]) => `${k}=${encodeURIComponent(v)}`).join('&');
            const url = `https://open-api-drive.uc.cn/file?${urlParams}`;
            
            const response = await req(url, {
                method: 'GET', headers: {
                    'User-Agent': 'Mozilla/5.0 (Linux; U; Android 9; zh-cn; RMX1931 Build/PQ3A.190605.05081124) AppleWebKit/533.1 (KHTML, like Gecko) Mobile Safari/533.1',
                    'Connection': 'Keep-Alive', 'x-pan-tm': timestamp,
                    'x-pan-token': x_pan_token, 'content-type': 'text/plain;charset=UTF-8',
                    'x-pan-client-id': this.ucConfig.clientID, 'Cookie': this.cookie
                }
            });
            
            if (response.code == 200 && response.content) {
                const jsonData = JSON.parse(response.content);
                if (jsonData.data?.video_info) {
                    result = jsonData.data.video_info.map(item => ({ name: item.resolution, url: item.url }));
                }
            }
        }
        
        // 降级获取普通下载链接
        if (!result) {
            const url = `${this.apiUrl}/file/download?${this.pr}`;
            const downResult = await this.request(url, {
                method: 'POST',
                data: { fids: [this.saveFileIdCaches[fileId]] },
                headers: this.getHeaders()
            }, 3, '获取下载链接');
            
            if (downResult.code && downResult.code !== 200 && downResult.code !== 0) {
                return { error: true, code: downResult.code, message: ERROR_CODES[downResult.code]?.message || '获取下载链接失败' };
            }
            
            const downloadData = downResult.data?.[0];
            if (downloadData) {
                result = [{ name: "原画", url: downloadData.download_url }];
            }
        }
        
        if (result) {
            this.setCachedUrl(shareId, fileId, result);
            return result;
        }
        
        return { error: true, code: -2, message: '获取下载链接失败，请稍后重试' };
    }

    /**
     * 获取直播转码播放地址
     */
    async getLiveTranscoding(shareId, stoken, fileId, fileToken) {
        // 先检查缓存
        const cacheKey = `${shareId}_${fileId}_transcoding`;
        const cachedResult = this.urlCache[cacheKey];
        if (cachedResult && (Date.now() - cachedResult.timestamp) < this.cacheTTL) {
            return cachedResult.urls;
        }
        
        try {
            // 转存文件
            const saveFileId = await this.save(shareId, stoken, fileId, fileToken, true);
            if (!saveFileId || saveFileId.error) {
                log('转码', `转存失败: ${saveFileId?.message || '未知错误'}`);
                return null;
            }
            
            // 请求转码画质
            const url = `${this.apiUrl}/file/v2/play?${this.pr}`;
            const result = await this.request(url, {
                method: 'POST',
                data: {
                    fid: saveFileId,
                    resolutions: 'normal,low,high,super,2k,4k',
                    supports: 'fmp4'
                },
                headers: this.getHeaders()
            }, 3, '获取转码地址');
            
            const videoList = result.data?.video_list || null;
            if (videoList && videoList.length > 0) {
                // 缓存播放地址
                this.urlCache[cacheKey] = { urls: videoList, timestamp: Date.now() };
                return videoList;
            } else {
                return null;
            }
        } catch (error) {
            log('转码', `异常: ${error.message}`);
            return null;
        }
    }

    /**
     * 删除文件
     */
    async deleteFile(fileId) {
        if (!fileId) return;
        const deleteUrl = `${this.apiUrl}/file/delete?${this.pr}`;
        await this.request(deleteUrl, {
            method: 'POST',
            data: { action_type: 2, filelist: [fileId], exclude_fids: [] },
            headers: this.getHeaders()
        }, 3, '删除临时文件');
    }

    /**
     * 获取懒加载结果
     */
    async getLazyResult(downCache, mediaProxyUrl) {
        const urls = [];
        if (Array.isArray(downCache)) {
            downCache.forEach(it => {
                if (it && it.url) urls.push(it.name, it.url + "#isVideo=true##fastPlayMode##threads=10#");
            });
        } else if (downCache?.download_url) {
            urls.push("原画", downCache.download_url + "#isVideo=true##fastPlayMode##threads=10#");
        } else if (downCache?.error) {
            return { parse: 0, url: [], error: downCache.message };
        }
        return { parse: 0, url: urls };
    }

    /**
     * 测试URL支持性
     */
    async testSupport(url, headers) {
        try {
            const resp = await req(url, {
                method: 'GET',
                headers: { ...this.baseHeader, ...headers, 'Range': 'bytes=0-0' }
            });
            
            if (resp.code === 206 || resp.code === 200) {
                const isAccept = resp.headers?.['accept-ranges'] === 'bytes';
                const contentRange = resp.headers?.['content-range'];
                const contentLength = parseInt(resp.headers?.['content-length'] || '0');
                const isSupport = isAccept || !!contentRange || contentLength === 1 || resp.status === 200;
                return [isSupport, resp.headers || {}];
            }
            return [false, null];
        } catch {
            return [false, null];
        }
    }
}

export const UC = new UCHandler();