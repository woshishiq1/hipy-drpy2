/**
 * 夸克网盘处理工具
 * 
 * 提供夸克网盘分享链接解析、文件下载、流媒体播放等功能。
 * 
 * @module QuarkPanHandler
 * @author 优雅
 * @since 1.0.0
 */

// 全局调试开关
let DEBUG = globalThis.quark_debug || 0;

/**
 * 日志输出
 */
function log(tag, message) {
    if (!DEBUG) return;
    console.log(`【夸克-${tag}】 ${message}`);
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
 * 夸克网盘处理类
 */
class QuarkHandler {
    constructor() {
        // 夸克分享链接正则表达式 - 匹配标准分享链接和提取密码
        this.regex = /https:\/\/pan\.quark\.cn\/s\/([^?&#]+)(?:\?.*?pwd=([^&]+))?/;
        // 请求参数
        this.pr = 'pr=ucpro&fr=pc';
        // 基础请求头
        this.baseHeader = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) quark-cloud-drive/2.5.20 Chrome/100.0.4896.160 Electron/18.3.5.4-b478491100 Safari/537.36 Channel/pckk_other_ch',
            'Referer': 'https://pan.quark.cn',
            'Content-Type': 'application/json'
        };
        // API基础URL
        this.apiUrl = 'https://drive.quark.cn/1/clouddrive/';
        // 分享令牌缓存
        this.shareTokenCache = {};
        // 保存目录名称
        this.saveDirName = 'drpy';
        // 保存目录ID
        this.saveDirId = null;
        // 字幕文件扩展名
        this.subtitleExts = ['.srt', '.ass', '.scc', '.stl', '.ttml'];
        // 视频文件扩展名
        this.videoExts = ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mpg', '.mpeg', '.ts', '.m3u8'];
        // 视频扩展名开关（1=启用判断，0=禁用）
        this.videoExtsEnabled = 0;
        
        // Cookie存储
        this._cookie = '';
        
        // 上次刷新时间
        this.lastRefreshTime = 0;
        this.refreshInterval = 1 * 24 * 60 * 60 * 1000;
        
        // 刷新锁
        this._isRefreshing = false;
        this._refreshPromise = null;
        
        // 播放地址临时缓存（20分钟）
        this.urlCache = {};
        this.cacheTTL = 20 * 60 * 1000;
    }

    /**
     * 获取Cookie
     */
    get cookie() {
        if (this._cookie) return this._cookie;
        if (globalThis.quark_cookie) this._cookie = globalThis.quark_cookie;
        return this._cookie;
    }

    /**
     * 设置Cookie
     */
    set cookie(value) {
        this._cookie = value || '';
        if (value) globalThis.quark_cookie = value;
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
     * 确保Cookie有效
     */
    async ensureValidCookie() {
        const CACHE_TIME = 1 * 24 * 60 * 60 * 1000;
        const now = Date.now();
        const timeSinceLastRefresh = now - this.lastRefreshTime;
        
        const needRefresh = () => {
            if (this.lastRefreshTime === 0) return true;
            if (timeSinceLastRefresh >= CACHE_TIME) return true;
            if (!this.cookie || !this.cookie.includes('__puus=')) return true;
            return false;
        };
        
        if (!needRefresh()) {
            return true;
        }
        
        log('Cookie', `开始刷新...`);
        const originalCookie = this.cookie;
        const success = await this.refreshQuarkCookie();
        
        if (success && this.cookie && this.cookie.includes('__puus=')) {
            this.lastRefreshTime = now;
            log('Cookie', `刷新成功`);
            return true;
        }
        
        this.cookie = originalCookie;
        if (originalCookie && originalCookie.includes('__puus=')) {
            return true;
        }
        
        log('Cookie', `无效`);
        return false;
    }

    /**
     * 刷新夸克Cookie
     */
    async refreshQuarkCookie() {
        if (this._isRefreshing) return await this._refreshPromise;
        
        this._isRefreshing = true;
        this._refreshPromise = (async () => {
            if (!this.cookie) return false;
            
            try {
                const url = `${this.apiUrl}file/sort?pr=ucpro&fr=pc&uc_param_str=&pdir_fid=0&_page=1&_size=50&_fetch_total=1&_fetch_sub_dirs=0&_sort=file_type:asc,updated_at:desc`;
                const resp = await req(url, {
                    method: "GET",
                    headers: {
                        "User-Agent": this.baseHeader['User-Agent'],
                        Origin: 'https://pan.quark.cn',
                        Referer: 'https://pan.quark.cn/',
                        Cookie: this.cookie
                    }
                });
                
                const setCookie = resp.headers?.['set-cookie'] || resp.headers?.['Set-Cookie'];
                if (setCookie) {
                    this.cookie = this.mergeCookies(this.cookie, setCookie);
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
     * 合并Cookie
     */
    mergeCookies(oldCookie, setCookie) {
        const oldCookies = {};
        if (oldCookie) {
            oldCookie.split(';').forEach(part => {
                const trimmed = part.trim();
                if (trimmed) {
                    const eqIndex = trimmed.indexOf('=');
                    if (eqIndex > 0) {
                        oldCookies[trimmed.substring(0, eqIndex)] = trimmed.substring(eqIndex + 1);
                    }
                }
            });
        }
        
        const cookieArray = Array.isArray(setCookie) ? setCookie : [setCookie];
        for (const item of cookieArray) {
            const cookiePart = item.split(';')[0].trim();
            const eqIndex = cookiePart.indexOf('=');
            if (eqIndex > 0) {
                oldCookies[cookiePart.substring(0, eqIndex)] = cookiePart.substring(eqIndex + 1);
            }
        }
        
        return Object.entries(oldCookies).map(([key, value]) => `${key}=${value}`).join('; ');
    }

    /**
     * 解析分享链接
     * 从分享URL中提取shareId和密码
     * @param {string} url - 夸克分享链接
     * @returns {Object|null} 包含shareId、folderId、sharePwd的对象，解析失败返回null
     */
    getShareData(url) {
        const matches = this.regex.exec(url);
        if (!matches || !matches[1]) return null;
        
        let shareId = matches[1];
        if (shareId.indexOf("?") > 0) shareId = shareId.split('?')[0];
        const passCode = matches[2] || '';
        
        return { shareId: shareId, folderId: '0', sharePwd: passCode };
    }

    /**
     * 初始化夸克
     */
    async initQuark(db, cfg) {
        if (cfg?.quark_cookie) this.cookie = cfg.quark_cookie;
        if (cfg?.quark_videoExtsEnabled !== undefined) this.videoExtsEnabled = cfg.quark_videoExtsEnabled;
        if (this.lastRefreshTime === 0) this.lastRefreshTime = Date.now();
        await this.ensureValidCookie();
        log('初始化', `完成, videoExtsEnabled=${this.videoExtsEnabled}`);
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
        
        const url = `${this.apiUrl}file/sort?pdir_fid=${this.saveDirId}&_page=1&_size=200&_sort=file_type:asc,updated_at:desc&${this.pr}`;
        const listData = await this.request(url, { method: 'GET', headers: this.getHeaders() }, 3, '清理目录-获取列表');
        
        if (listData.code && listData.code !== 200 && listData.code !== 0) {
            log('清理目录', `失败: code=${listData.code}`);
            return { error: true, code: listData.code, message: ERROR_CODES[listData.code]?.message || '获取目录文件列表失败' };
        }
        
        if (listData.data?.list?.length > 0) {
            const deleteUrl = `${this.apiUrl}file/delete?${this.pr}`;
            const deleteResult = await this.request(deleteUrl, {
                method: 'POST',
                data: { action_type: 2, filelist: listData.data.list.map(v => v.fid), exclude_fids: [] },
                headers: this.getHeaders()
            }, 3, '清理目录-删除文件');
            
            if (deleteResult.code && deleteResult.code !== 200 && deleteResult.code !== 0) {
                log('清理目录', `删除失败: code=${deleteResult.code}`);
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
        
        const url = `${this.apiUrl}file/sort?pdir_fid=0&_page=1&_size=200&_sort=file_type:asc,updated_at:desc&${this.pr}`;
        const listData = await this.request(url, { method: 'GET', headers: this.getHeaders() }, 3, '创建目录-获取根目录');
        
        if (listData.code && listData.code !== 200 && listData.code !== 0) {
            const errorMsg = ERROR_CODES[listData.code]?.message || listData.message || '获取目录列表失败';
            log('目录', `获取失败: code=${listData.code}`);
            return { error: true, code: listData.code, message: errorMsg };
        }
        
        if (listData.message && listData.code !== 200 && listData.code !== 0) {
            return { error: true, code: listData.code || -1, message: listData.message };
        }
        
        if (listData.data?.list) {
            for (const item of listData.data.list) {
                if (item.file_name === this.saveDirName && item.dir === true) {
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
            const createUrl = `${this.apiUrl}file?${this.pr}`;
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
     * 获取分享令牌
     */
    async getShareToken(shareData) {
        if (!this.shareTokenCache[shareData.shareId]) {
            const url = `${this.apiUrl}share/sharepage/token?${this.pr}`;
            const result = await this.request(url, {
                method: 'POST',
                data: { pwd_id: shareData.shareId, passcode: shareData.sharePwd || '' },
                headers: this.getHeaders()
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
        await this.ensureValidCookie();
        
        const shareData = typeof shareInfo === 'string' ? this.getShareData(shareInfo) : shareInfo;
        if (!shareData) return [];
        
        await this.getShareToken(shareData);
        if (!this.shareTokenCache[shareData.shareId]) return [];
        
        const videos = [];
        const subtitles = [];
        
        const listFile = async (shareId, folderId, page = 1) => {
            const prePage = 200;
            const url = `${this.apiUrl}share/sharepage/detail?pwd_id=${shareId}&stoken=${encodeURIComponent(this.shareTokenCache[shareId].stoken)}&pdir_fid=${folderId}&force=0&_page=${page}&_size=${prePage}&_sort=file_type:asc,file_name:asc&${this.pr}`;
            const listData = await this.request(url, { method: 'GET', headers: this.getHeaders() }, 3, `获取文件列表-${folderId}-p${page}`);
            
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
                        // 禁用扩展名判断，只依赖夸克分类
                        isVideo = item.obj_category === 'video';
                    }
                    
                    if (isVideo) {
                        item.stoken = this.shareTokenCache[shareData.shareId].stoken;
                        item.formatted_size = this.formatFileSize(item.size);
                        item.thumbnail = item.thumbnail || item.big_thumbnail || '';
                        item.file_type = 'video';
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
     * 保存文件到个人网盘
     */
    async saveDirect(shareId, stoken, fileId, fileToken) {
        const dirResult = await this.createSaveDir(false);
        if (dirResult.error) {
            return { error: true, code: dirResult.code, message: dirResult.message };
        }
        
        if (!stoken) {
            await this.getShareToken({ shareId });
            if (!this.shareTokenCache[shareId]) {
                return { error: true, code: -2, message: '获取分享令牌失败' };
            }
            stoken = this.shareTokenCache[shareId].stoken;
        }
        
        const saveUrl = `${this.apiUrl}share/sharepage/save?${this.pr}`;
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
                const taskUrl = `${this.apiUrl}task?task_id=${saveResult.data.task_id}&retry_index=${retry}&${this.pr}`;
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
            const saveFileId = await this.saveDirect(shareId, stoken, fileId, fileToken);
            if (!saveFileId || saveFileId.error) {
                log('转码', `转存失败: ${saveFileId?.message || '未知错误'}`);
                return null;
            }
            
            // 请求转码画质
            const url = `${this.apiUrl}file/v2/play?${this.pr}`;
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
                
                // 异步删除临时文件
                this.delay(3000).then(() => {
                    this.deleteFile(saveFileId).catch(e => {});
                });
                
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
        const deleteUrl = `${this.apiUrl}file/delete?${this.pr}`;
        await this.request(deleteUrl, {
            method: 'POST',
            data: { action_type: 2, filelist: [fileId], exclude_fids: [] },
            headers: this.getHeaders()
        }, 3, '删除临时文件');
    }

    /**
     * 获取下载令牌
     */
    async getToken() {
        let t = Math.floor(Date.now() / 1e3);
        let data = {
            "conversation_id": "300000" + t,
            "conversation_type": 3,
            "msg_id": t + "000"
        };
        
        const headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) quark-cloud-drive/3.23.2 Chrome/112.0.5615.165 Electron/24.1.3.8 Safari/537.36 Channel/pckk_other_ch',
            'Content-Type': 'application/json',
            'origin': 'https://pan.quark.cn',
            'referer': 'https://pan.quark.cn/'
        };
        
        const response = await req('https://drive-social-api.quark.cn/1/clouddrive/chat/conv/file/acquire_dl_token?pr=ucpro&fr=pc&sys=darwin&ve=3.19', {
            method: 'POST',
            headers: { ...headers, 'Cookie': this.cookie },
            data: data
        });
        if (response.code == 200 && response.content) {
            const result = JSON.parse(response.content);
            return result.data?.token;
        }
        return null;
    }

    /**
     * 获取无限画质链接
     */
    async getUrl(shareId, stoken, fileId, fileToken) {
        const token = await this.getToken();
        if (!token) return null;
        
        let data = {
            "fids": [fileId],
            "fids_token": [fileToken],
            "pwd_id": shareId,
            "stoken": stoken,
            "speedup_session": "",
            "token": token
        };
        
        const headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) quark-cloud-drive/3.20.0 Chrome/112.0.5615.165 Electron/24.1.3.8 Safari/537.36 Channel/pckk_other_ch',
            'Content-Type': 'application/json'
        };
        
        const response = await req('https://drive-pc.quark.cn/1/clouddrive/file/download?pr=ucpro&fr=pc', {
            method: 'POST',
            headers: { ...headers, 'Cookie': this.cookie },
            data: data
        });
        
        if (response.code == 200 && response.content) {
            const result = JSON.parse(response.content);
            if (result.data && Array.isArray(result.data)) {
                return result.data.map(item => ({
                    name: item.video_max_resolution || '原画',
                    url: item.download_url
                }));
            }
        }
        return null;
    }

    /**
     * 获取下载链接
     */
    async getDownload(shareId, stoken, fileId, fileToken, clean = false) {
        // 先检查缓存
        const cachedResult = this.getCachedUrl(shareId, fileId);
        if (cachedResult) return cachedResult;
        
        await this.ensureValidCookie();
        
        const dirResult = await this.createSaveDir(clean);
        if (dirResult.error) {
            return { error: true, code: dirResult.code, message: dirResult.message };
        }
        
        const saveFileId = await this.saveDirect(shareId, stoken, fileId, fileToken);
        
        // 检查保存是否失败，直接返回 saveDirect 的错误信息
        if (saveFileId && saveFileId.error) {
            return saveFileId;
        }
        
        if (!saveFileId) {
            return {
                error: true,
                code: -1,
                message: '文件转存失败，请检查分享链接是否有效'
            };
        }
        
        const url = `${this.apiUrl}file/download?${this.pr}`;
        const result = await this.request(url, {
            method: 'POST',
            data: { fids: [saveFileId] },
            headers: this.getHeaders()
        }, 3, '获取下载链接');
        
        // 检查错误码
        if (result.code && result.code !== 200 && result.code !== 0) {
            log('下载', `失败: code=${result.code}`);
            return {
                error: true,
                code: result.code,
                message: ERROR_CODES[result.code]?.message || '获取下载链接失败'
            };
        }
        
        if (result.data?.task_resp?.code) {
            return {
                error: true,
                code: result.data.task_resp.code,
                message: result.data.task_resp.message || '获取下载链接失败'
            };
        }
        
        const downloadResult = result.data?.[0] || null;
        
        if (downloadResult) {
            this.setCachedUrl(shareId, fileId, downloadResult);
            return downloadResult;
        }
        
        return {
            error: true,
            code: -2,
            message: '获取下载链接失败，请稍后重试'
        };
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

export const Quark = new QuarkHandler();