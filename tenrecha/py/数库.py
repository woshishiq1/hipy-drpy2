#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, sqlite3, json, re
from base.spider import Spider

# 保留这两个基础配置，删除 DB_DIRS
DEFAULT_COVER = "https://cloud.7so.top/f/p8PPHA/%E5%90%88%E9%9B%86.png"
MOVIE_ICON = "https://img.icons8.com/color/512/movie.png"

class Spider(Spider):
    # ==========================================================================
    # 💎 【统一路径管理】 彻底废弃 DB_DIRS，只保留这一个扫描入口
    # ==========================================================================
    SCAN_DIR_LIST = SCAN_DIR_LIST = [
                "bh", "tvbox",       #电视📺专用文件夹，把db文件放在这里# 👈 u盘也用这个文件夹                                          
                "lz", "纯福利", "私藏视频",  "江湖",         # 👈 前面加#关闭   这里可以修改任意大佬包名 
                "VodPlus", "peekpili/php-scripts"                       #同上
          ]
    MAX_DEPTH = 3 
    VIRTUAL_PAGE_SIZE = 500 # 虚拟分类每页显示条数（可根据设备性能微调）
    FOLDER_ICON = "https://cloud.7so.top/f/p8PPHA/%E5%90%88%E9%9B%86.png"
    
    def getName(self):
        return "数库"
        
    def init(self, extend=""):
        self.inited = True
        self.databases = {}
        self._db_cache = {}
        self.sub_icons = {} # 即使不用，也要初始化防止报错
        
        # 1. 自动探测根目录（内部存储 + 外部挂载点）
        self.scan_roots = ["/storage/emulated/0", "/sdcard"]
        try:
            if os.path.exists("/storage"):
                for s in os.listdir("/storage"):
                    if s not in ["self", "emulated", "knox", "sdcard0", "runtime", "container"]:
                        full_s = os.path.join("/storage", s)
                        if os.path.isdir(full_s) and full_s not in self.scan_roots:
                            self.scan_roots.append(full_s)
        except Exception: 
            pass
        
        # 2. 执行受控深度扫描（只在规定路径内搜索）
        for root in self.scan_roots:
            for sub in self.SCAN_DIR_LIST:
                target_dir = os.path.join(root, sub)
                if os.path.exists(target_dir):
                    self._scan_with_depth(target_dir, 1)

    def _scan_with_depth(self, current_dir, current_depth):
        """严格3级递归扫描"""
        if current_depth > self.MAX_DEPTH:
            return
        try:
            for file in os.listdir(current_dir):
                full_path = os.path.join(current_dir, file)
                if os.path.isdir(full_path):
                    self._scan_with_depth(full_path, current_depth + 1)
                elif file.endswith(".db"):
                    abs_path = os.path.abspath(full_path)
                    db_key = f"auto_{file}"
                    
                    # ✂️ 【无损切除后缀】 
                    clean_name = file.rsplit('.db', 1)[0] if file.lower().endswith('.db') else file
                    
                    # 🏷️ 【智能提取文件名自带的条数标记】 兼容类似 "短视频(0.8m~5.2万条)" 的规则
                    count_file_str = ""
                    match = re.search(r"(\([^\)]+\万条\))|(\([^\)]+\条\))", clean_name)
                    if match:
                        count_file_str = match.group(0)
                        clean_name = clean_name.replace(count_file_str, "") # 清理多余名称显示
                    
                    if db_key in self.databases:
                        parent_name = os.path.basename(os.path.dirname(abs_path))
                        db_key = f"auto_{parent_name}_{file}"
                        clean_name = f"{parent_name}_{clean_name}"
                        
                    self.databases[db_key] = {
                        "name": clean_name, 
                        "path": abs_path,
                        "count_file_str": count_file_str # 存入结构包内
                    }
        except Exception:
            pass

    def _get_connection(self, db_key):
        """分类/详情/搜索 都会调用此函数，必须确保从 self.databases 取值"""
        db_info = self.databases.get(db_key)
        if not db_info: return None
        path = db_info.get("path", "")
        if not path or not os.path.exists(path): return None
        
        try:
            conn = sqlite3.connect(path)
            conn.row_factory = sqlite3.Row
            # 🚀 安卓6专用的二进制优化，防止大文件拖慢查询
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode = OFF;")
            cursor.execute("PRAGMA synchronous = OFF;")
            cursor.execute("PRAGMA mmap_size = 268435456;") 
            return conn
        except: return None

    def _is_exclusive_db(self, conn):
        try:
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='video_actress'")
            return cur.fetchone() is not None
        except:
            return False

    def _has_table(self, conn, table_name):
        try:
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
            return cur.fetchone() is not None
        except:
            return False

    def _get_auto_mapping(self, conn):
        """盲扫核心：智能嗅探普通DB的可用表名及核心字段"""
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
            tables = [row[0] for row in cursor.fetchall()]
            if not tables: return None
            
            target_table = tables[0]
            for t in tables:
                if t.lower() in ["vod", "video", "movies", "data"]:
                    target_table = t
                    break
                    
            cursor.execute(f"PRAGMA table_info(`{target_table}`);")
            columns = [row[1].lower() for row in cursor.fetchall()]
            field_mapping = {"id": "id", "name": "name", "pic": "pic", "urls": "urls"}
            for col in columns:
                if col in ["vod_id", "movie_id", "uuid"]: field_mapping["id"] = col
                if col in ["vod_name", "title", "movie_name"]: field_mapping["name"] = col
                if col in ["vod_pic", "cover", "image"]: field_mapping["pic"] = col
                if col in ["vod_play_url", "url", "links"]: field_mapping["urls"] = col
            return {"table_name": target_table, "field_mapping": field_mapping}
        except: return None

    # ==================== 首页 ====================
    def homeContent(self, filter):
        classes = []
        for db_key, db_info in self.databases.items():
            # 使用从扫描器里已经洗干净、隐藏了后缀的干净名字
            name = db_info.get("name", "未知库")
            
            # 如果文件名自带了手动标记统计，优先使用
            count_str = db_info.get("count_file_str", "")
            
            # 如果没有手动标记，则判断是否为专属数据库，执行原有的动态条数查询
            if not count_str:
                conn = self._get_connection(db_key)
                if conn:
                    try:
                        if self._is_exclusive_db(conn):
                            cur = conn.cursor()
                            cur.execute("SELECT COUNT(*) FROM videos")
                            total = cur.fetchone()[0]
                            count_str = f" ({total})"
                    except:
                        pass
                    finally:
                        conn.close()
                        
            classes.append({
                "type_id": db_key,
                "type_name": f"{name}{count_str}",
                "type_pic": DEFAULT_COVER,
                "pic": DEFAULT_COVER,
                "icon": DEFAULT_COVER,
                "vod_pic": DEFAULT_COVER
            })
        return {"class": classes}

    # ==================== 分类 ====================
    def categoryContent(self, tid, pg, filter, extend):
        parts = tid.split('$')
        db_key = parts[0]
        conn = self._get_connection(db_key)
        if not conn:
            return {"list": []}

        # 检查是否点击了普通库衍生出的虚拟分段
        is_virtual = len(parts) > 1 and "VIRTUAL" in parts[1]

        # ⚡ 核心修复：如果进入的是演员专属库，且没有触发普通库的虚拟分页拦截
        if self._is_exclusive_db(conn) and not is_virtual:
            # 直接透传完整的 parts 数组给演员分类函数，确保 class_id 不会丢失，图片和列表全部流出
            result = self._exclusive_category(conn, db_key, parts, pg)
        else:
            # 普通数据库，或者被拦截到的虚拟页码，走升级版的自适应虚拟分类
            result = self._legacy_category(conn, db_key, parts, pg)
            
        conn.close()
        return result

    def _legacy_category(self, conn, db_key, parts, pg):
        """保障底层拉取安全的虚拟分类层"""
        curr_path = parts[1] if len(parts) > 1 else ""
        
        auto_info = self._get_auto_mapping(conn)
        if not auto_info: return {"list": []}
        
        table = auto_info["table_name"]
        mapping = auto_info["field_mapping"]

        # 1. 响应点击：如果是被拦截到的分段虚拟文件夹
        if "VIRTUAL" in curr_path:
            v_page = int(curr_path.split('_')[-1]) # 解析出段落索引
            limit = self.VIRTUAL_PAGE_SIZE
            offset = v_page * limit
            # 透传调用你原有的下一级列表提取函数，数据完美流出
            return self._legacy_fetch_video_list(conn, db_key, table, mapping, None, None, 1, limit, offset)

        # 2. 繁殖分段：读取普通库的总体规模
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
        total_count = cursor.fetchone()[0]

        # 如果数量庞大，将其拆解为虚拟分段文件夹，实现老硬件秒开
        if total_count > self.VIRTUAL_PAGE_SIZE:
            vod_list = []
            pages = (total_count + self.VIRTUAL_PAGE_SIZE - 1) // self.VIRTUAL_PAGE_SIZE
            for i in range(pages):
                start = i * self.VIRTUAL_PAGE_SIZE + 1
                end = min((i + 1) * self.VIRTUAL_PAGE_SIZE, total_count)
                vod_list.append({
                    "vod_id": f"{db_key}$VIRTUAL_{i}",
                    "vod_name": f"📦 数据分段 {i+1} ({start}-{end}条 / 共{total_count}条)",
                    "vod_pic": self.FOLDER_ICON,
                    "vod_tag": "folder"
                })
            return {"page": 1, "pagecount": 1, "limit": total_count, "list": vod_list}
            
        # 3. 体积较小则不分段，直接送去列表函数加载显示
        return self._legacy_fetch_video_list(conn, db_key, table, mapping, None, None, pg, 500, 0)

    def _exclusive_category(self, conn, db_key, parts, pg):
        class_id = parts[1] if len(parts) > 1 else ""
        sub_name = parts[2] if len(parts) > 2 else ""

        if not class_id:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM actor_ranking")
            actor_rank_cnt = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM video_ranking")
            video_rank_cnt = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM video_actress")
            actress_cnt = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM videos")
            video_total = cur.fetchone()[0]

            vod_list = [
                {"vod_id": f"{db_key}$actor_ranking", "vod_name": f"演员榜 ({actor_rank_cnt})", "vod_pic": DEFAULT_COVER, "vod_tag": "folder"},
                {"vod_id": f"{db_key}$video_ranking", "vod_name": f"影片榜 ({video_rank_cnt})", "vod_pic": DEFAULT_COVER, "vod_tag": "folder"},
                {"vod_id": f"{db_key}$actress", "vod_name": f"AV女优库 ({actress_cnt})", "vod_pic": DEFAULT_COVER, "vod_tag": "folder"},
                {"vod_id": f"{db_key}$video_cate", "vod_name": f"AV影片库 ({video_total})", "vod_pic": DEFAULT_COVER, "vod_tag": "folder"},
            ]
            return {"page": 1, "pagecount": 2, "limit": 20, "list": vod_list}

        if class_id == "actress":
            if not sub_name:
                return self._list_actresses(conn, db_key, pg)
            else:
                return self._list_videos_by_actress(conn, db_key, sub_name, pg)

        elif class_id == "video_cate":
            if not sub_name:
                cur = conn.cursor()
                cur.execute("SELECT main_category, COUNT(*) as cnt FROM video_category GROUP BY main_category ORDER BY cnt DESC")
                rows = cur.fetchall()
                limit = 20
                page = int(pg)
                start = (page - 1) * limit
                paged = rows[start:start+limit]
                vod_list = []
                for r in paged:
                    cat = r[0]
                    cnt = r[1]
                    vod_list.append({
                        "vod_id": f"{db_key}$video_cate${cat}",
                        "vod_name": f"{cat} ({cnt})",
                        "vod_pic": DEFAULT_COVER,
                        "vod_tag": "folder"
                    })
                return {"page": page, "pagecount": page+1, "limit": limit, "list": vod_list}
            else:
                return self._list_videos_by_category(conn, db_key, sub_name, pg)

        elif class_id == "actor_ranking":
            if not sub_name:
                return self._list_actor_ranking(conn, db_key, pg)
            else:
                return self._list_videos_by_actress(conn, db_key, sub_name, pg)

        elif class_id == "video_ranking":
            if not sub_name:
                return self._list_video_ranking(conn, db_key, pg)
            else:
                return self._list_videos_by_category(conn, db_key, sub_name, pg)

        elif class_id == "tag":
            if not sub_name:
                return self._list_categories(conn, db_key, pg, "video_cate")
            else:
                return self._list_videos_by_category(conn, db_key, sub_name, pg)

        return {"list": []}

    def _list_actresses(self, conn, db_key, pg):
        cur = conn.cursor()
        cur.execute("""
            SELECT a.name, a.avatar, COUNT(va.vod_id) as cnt
            FROM actresses a
            LEFT JOIN video_actress va ON a.cate_id = va.cate_id
            GROUP BY a.cate_id HAVING cnt > 0
            ORDER BY cnt DESC
        """)
        rows = cur.fetchall()
        return self._paginate_dirs(rows, pg, db_key, "actress")

    def _list_actor_ranking(self, conn, db_key, pg):
        cur = conn.cursor()
        cur.execute("""
            SELECT a.name, a.avatar, COUNT(ar.vod_id) as cnt
            FROM actresses a
            JOIN actor_ranking ar ON a.cate_id = ar.cate_id
            GROUP BY a.cate_id
            ORDER BY cnt DESC
        """)
        rows = cur.fetchall()
        if not rows:
            return self._list_actresses(conn, db_key, pg)
        return self._paginate_dirs(rows, pg, db_key, "actor_ranking")

    def _list_video_ranking(self, conn, db_key, pg):
        cur = conn.cursor()
        cur.execute("""
            SELECT v.title, v.pic_url, COUNT(vr.vod_id) as cnt
            FROM videos v
            JOIN video_ranking vr ON v.vod_id = vr.vod_id
            GROUP BY v.vod_id
            ORDER BY cnt DESC
            LIMIT 100
        """)
        rows = cur.fetchall()
        if not rows:
            cur.execute("SELECT title, pic_url, 1 as cnt FROM videos ORDER BY created_at DESC LIMIT 100")
            rows = cur.fetchall()
        limit = 20
        page = int(pg)
        start = (page - 1) * limit
        paged = rows[start:start+limit]
        vod_list = []
        for r in paged:
            name = r[0]
            pic = r[1] if r[1] else MOVIE_ICON
            vod_list.append({
                "vod_id": f"{db_key}$video_ranking${name}",
                "vod_name": name,
                "vod_pic": pic,
                "vod_tag": "video"
            })
        return {"page": page, "pagecount": page+1, "limit": limit, "list": vod_list}

    def _list_categories(self, conn, db_key, pg, cat_type="video_cate"):
        cur = conn.cursor()
        cur.execute("SELECT main_category, COUNT(*) as cnt FROM video_category GROUP BY main_category ORDER BY cnt DESC")
        rows = cur.fetchall()
        limit = 20
        page = int(pg)
        start = (page - 1) * limit
        paged = rows[start:start+limit]
        vod_list = []
        for r in paged:
            cat = r[0]
            cnt = r[1]
            vod_list.append({
                "vod_id": f"{db_key}${cat_type}${cat}",
                "vod_name": f"{cat} ({cnt})",
                "vod_pic": DEFAULT_COVER,
                "vod_tag": "folder"
            })
        return {"page": page, "pagecount": page+1, "limit": limit, "list": vod_list}

    def _list_videos_by_category(self, conn, db_key, category_val, pg):
        limit = 20
        page = int(pg)
        offset = (page - 1) * limit
        cur = conn.cursor()
        cur.execute("""
            SELECT v.vod_id, v.title, v.pic_url, v.vod_remarks
            FROM videos v
            JOIN video_category vc ON v.vod_id = vc.vod_id
            WHERE vc.main_category = ?
            LIMIT ? OFFSET ?
        """, (category_val, limit, offset))
        rows = cur.fetchall()
        vod_list = []
        for r in rows:
            pic = r[2] if r[2] else MOVIE_ICON
            vod_list.append({
                "vod_id": f"{db_key}#ID#{r[0]}",
                "vod_name": r[1] or r[0],
                "vod_pic": pic,
                "vod_remarks": r[3] or ""
            })
        return {"page": page, "pagecount": page+1, "limit": limit, "list": vod_list}

    def _list_videos_by_actress(self, conn, db_key, actress_name, pg):
        limit = 20
        page = int(pg)
        offset = (page - 1) * limit
        cur = conn.cursor()
        cur.execute("""
            SELECT v.vod_id, v.title, v.pic_url, v.vod_remarks
            FROM videos v
            JOIN video_actress va ON v.vod_id = va.vod_id
            JOIN actresses a ON va.cate_id = a.cate_id
            WHERE a.name = ?
            LIMIT ? OFFSET ?
        """, (actress_name, limit, offset))
        rows = cur.fetchall()
        vod_list = []
        for r in rows:
            pic = r[2] if r[2] else MOVIE_ICON
            vod_list.append({
                "vod_id": f"{db_key}#ID#{r[0]}",
                "vod_name": r[1] or r[0],
                "vod_pic": pic,
                "vod_remarks": r[3] or ""
            })
        return {"page": page, "pagecount": page+1, "limit": limit, "list": vod_list}

    def _paginate_dirs(self, rows, pg, db_key, cat_type):
        limit = 20
        page = int(pg)
        start = (page - 1) * limit
        paged = rows[start:start + limit]
        vod_list = []
        for r in paged:
            name = r[0]
            avatar = r[1] or ""
            cnt = r[2]
            pic = avatar if avatar else DEFAULT_COVER
            vod_list.append({
                "vod_id": f"{db_key}${cat_type}${name}",
                "vod_name": f"{name} ({cnt})",
                "vod_pic": pic,
                "vod_tag": "folder"
            })
        return {"page": page, "pagecount": page + 1, "limit": limit, "list": vod_list}

    # ==================== 旧版数据库兼容 ====================
    def _legacy_category(self, conn, db_key, parts, pg):
        curr_path = parts[1] if len(parts) > 1 else ""
        cache_key = f"tree_{db_key}"
        if cache_key not in self._db_cache:
            auto_info = self._get_auto_mapping(conn)
            if not auto_info:
                return {"list": []}
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA table_info(`{auto_info['table_name']}`)")
            all_cols = [str(r[1]) for r in cursor.fetchall()]
            filter_field = "type_name" if "type_name" in all_cols else auto_info["field_mapping"]["category_field"]
            cursor.execute(f"SELECT `{filter_field}`, COUNT(*) FROM `{auto_info['table_name']}` WHERE `{filter_field}` IS NOT NULL GROUP BY `{filter_field}`")
            raw_data = cursor.fetchall()
            type_counts = {str(row[0]): row[1] for row in raw_data}
            avatar_map = {}
            if "actress_avatar" in all_cols:
                try:
                    cursor.execute(
                        f"SELECT `{filter_field}`, `actress_avatar` FROM `{auto_info['table_name']}` "
                        "WHERE `actress_avatar` IS NOT NULL AND `actress_avatar` != ''"
                    )
                    for row in cursor.fetchall():
                        cat_val = str(row[0])
                        avatar_url = row[1]
                        if cat_val not in avatar_map:
                            avatar_map[cat_val] = avatar_url
                except: pass
            self._db_cache[cache_key] = {
                "types": list(type_counts.keys()),
                "counts": type_counts,
                "field": filter_field,
                "table": auto_info['table_name'],
                "mapping": auto_info['field_mapping'],
                "avatar_map": avatar_map
            }

        db_data = self._db_cache[cache_key]
        all_vals = db_data["types"]
        all_counts = db_data["counts"]
        avatar_map = db_data.get("avatar_map", {})
        sub_dirs_info = {}
        for val in all_vals:
            count = all_counts.get(val, 0)
            if curr_path == "":
                d = val.split('/')[0]
                sub_dirs_info[d] = sub_dirs_info.get(d, 0) + count
            elif val.startswith(curr_path + "/"):
                suffix = val[len(curr_path):].lstrip('/')
                if suffix:
                    d = f"{curr_path}/{suffix.split('/')[0]}"
                    sub_dirs_info[d] = sub_dirs_info.get(d, 0) + count

        limit = 20
        offset = (int(pg) - 1) * limit
        if not sub_dirs_info:
            return self._legacy_fetch_video_list(conn, db_key, db_data["table"], db_data["mapping"],
                                                 db_data["field"], curr_path if curr_path else None, pg, limit, offset)
        if len(sub_dirs_info) == 1:
            single_dir = list(sub_dirs_info.keys())[0]
            has_deeper = any(v.startswith(single_dir + "/") for v in all_vals)
            if not has_deeper:
                return self._legacy_fetch_video_list(conn, db_key, db_data["table"], db_data["mapping"],
                                                     db_data["field"], single_dir, pg, limit, offset)

        sorted_dirs = sorted(sub_dirs_info.keys(), key=lambda d: (-sub_dirs_info[d], d))
        paged_dirs = sorted_dirs[offset : offset + limit]
        vod_list = []
        for d in paged_dirs:
            display_name = d.split('/')[-1]
            num = sub_dirs_info[d]
            pic = avatar_map.get(d) or self.sub_icons.get(d) or self.sub_icons.get(display_name) or DEFAULT_COVER
            vod_list.append({
                "vod_id": f"{db_key}${d}",
                "vod_name": f"{display_name} ({num})",
                "vod_pic": pic,
                "vod_tag": "folder",
                "style": {"type": "rect", "ratio": 1.8}
            })
        return {"page": int(pg), "pagecount": int(pg) + 1, "limit": limit, "list": vod_list}
#
    def _get_auto_mapping(self, conn):
        try:
            cursor = conn.cursor()
            # 1. 自动获取库里所有的表名
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            tables = [row[0] for row in cursor.fetchall()]
            
            # 2. 按照优先级匹配可能的视频表
            target_table = next((t for t in ["videos", "vod_unified_data", "cj", "vod", "data", "video_detail"] if t in tables), None)
            
            # 3. 如果一个都不认识，就抓第一个表（暴力破解，保证出数据）
            if not target_table and tables:
                target_table = tables[0]
            
            if not target_table: return None
            
            # 4. 自动匹配字段（id, title, pic 等）
            cursor.execute(f"PRAGMA table_info(`{target_table}`)")
            cols = [str(r[1]) for r in cursor.fetchall()]
            
            mapping = {}
            field_candidates = {
                "vod_id": ["id", "vod_id", "uuid", "guid", "vid"],
                "vod_name": ["name", "vod_name", "title", "subject", "display_name"],
                "vod_pic": ["image", "vod_pic", "pic", "pic_url", "thumbnail", "img", "cover"],
                "vod_play_url": ["play_url", "vod_play_url", "url", "link", "m3u8_url"],
                "vod_remarks": ["vod_remarks", "remarks", "note", "desc"],
                "category_field": ["type_name", "category_id", "class_name", "cate_name", "actress_id", "tag", "type"],
                "vod_actor": ["vod_actor", "actor", "star", "actress", "artist", "performer"],
                "vod_content": ["vod_content", "description", "summary", "intro", "detail", "content"],
                "vod_pubdate": ["vod_pubdate", "pubdate", "release_date", "date"],
                "vod_area": ["vod_area", "area", "region", "country"],
                "vod_year": ["vod_year", "year"],
                "vod_tags": ["vod_tags", "tags", "keywords", "label"],
                "vod_play_from": ["vod_play_from", "play_from", "source"]
            }
            for target_field, candidates in field_candidates.items():
                matches = [cand for cand in candidates if cand in cols]
                mapping[target_field] = matches[0] if matches else None
            return {"table_name": target_table, "field_mapping": mapping}
        except:
            return None
#
    def _legacy_fetch_video_list(self, conn, db_key, table_name, mapping, filter_field, category_val, pg, limit, offset):
        cursor = conn.cursor()
        vod_list = []
        f_id = mapping.get("vod_id") or "rowid"
        f_name = mapping.get("vod_name") or "rowid"
        f_pic = mapping.get("vod_pic") or "''"
        f_rem = mapping.get("vod_remarks") or "''"
        try:
            if category_val is not None:
                sql = f"SELECT `{f_id}`, `{f_name}`, `{f_pic}`, `{f_rem}` FROM `{table_name}` WHERE `{filter_field}` = ? LIMIT ? OFFSET ?"
                cursor.execute(sql, (category_val, limit, offset))
            else:
                sql = f"SELECT `{f_id}`, `{f_name}`, `{f_pic}`, `{f_rem}` FROM `{table_name}` LIMIT ? OFFSET ?"
                cursor.execute(sql, (limit, offset))
            for row in cursor.fetchall():
                pic = str(row[2]) if row[2] else ""
                if not pic:
                    pic = MOVIE_ICON
                vod_list.append({
                    "vod_id": f"{db_key}#ID#{row[0]}",
                    "vod_name": str(row[1]),
                    "vod_pic": pic,
                    "vod_remarks": str(row[3]) if len(row) > 3 else ""
                })
        except:
            pass
        finally:
            conn.close()
        return {"page": int(pg), "pagecount": int(pg) + 1, "limit": limit, "list": vod_list}

    # ==================== 播放地址修复工具（唯一新增的方法） ====================
    def _fix_v_encoded_url(self, raw_url):
        """将数据库里 V 替换 / 的错误编码还原成真实链接"""
        if not raw_url:
            return raw_url
        # 去掉可能的高清前缀
        for prefix in ["高清$ ", "高清$", "高清 ", "高清"]:
            if raw_url.startswith(prefix):
                raw_url = raw_url[len(prefix):]
                break
        # 处理 V 替换问题: 先保护 ://V 恢复为 ://  ，再替换剩余 V 为 /
        url = raw_url.replace('://V', '://')
        url = url.replace('V', '/')
        return url

    # ♦==================== 详情 ====================
    def detailContent(self, ids):
        mid = ids[0]
        if '#ID#' in mid:
            parts = mid.split('#ID#')
            db_key, real_id = parts[0], parts[1]
        elif '#NAME#' in mid:
            parts = mid.split('#NAME#')
            db_key, vod_name = parts[0], parts[1]
            real_id = vod_name
        else:
            return {"list": []}
        conn = self._get_connection(db_key)
        if not conn:
            return {"list": []}
        if self._is_exclusive_db(conn):
            return self._exclusive_detail(conn, db_key, real_id)
        return self._legacy_detail(conn, db_key, real_id)

    def _legacy_detail(self, conn, db_key, real_id):
        auto_info = self._get_auto_mapping(conn)
        if not auto_info:
            conn.close()
            return {"list": []}
        table_name = auto_info["table_name"]
        mapping = auto_info["field_mapping"]
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        id_col = mapping.get("vod_id") or "rowid"
        cursor.execute(f"SELECT * FROM `{table_name}` WHERE `{id_col}` = ?", (real_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return {"list": []}
        def get_val(m_key):
            real_col = mapping.get(m_key)
            return str(row[real_col]) if (real_col and real_col in row.keys() and row[real_col] is not None) else ""
        raw_play_url = get_val("vod_play_url")
        play_url = raw_play_url.split('$$$')[-1] if '$$$' in raw_play_url else raw_play_url
        # 修复成真实链接
        play_url = self._fix_v_encoded_url(play_url)
        vod = {
            "vod_id": f"{db_key}#ID#{real_id}",
            "vod_name": get_val("vod_name"),
            "vod_pic": get_val("vod_pic"),
            "vod_actor": get_val("vod_actor") or get_val("category_field"),
            "vod_director": "",
            "vod_remarks": get_val("vod_remarks"),
            "vod_pubdate": get_val("vod_pubdate"),
            "vod_area": get_val("vod_area"),
            "vod_year": get_val("vod_year"),
            "vod_tags": get_val("vod_tags"),
            "vod_content": get_val("vod_content") or get_val("vod_remarks"),
            "vod_play_from": get_val("vod_play_from") or "自动识别",
            "vod_play_url": play_url,
            "type_name": get_val("category_field") or get_val("type_name")
        }
        conn.close()
        return {"list": [vod]}

    def _exclusive_detail(self, conn, db_key, vid_or_name):
        cur = conn.cursor()
        cur.execute("SELECT * FROM videos WHERE vod_id = ? OR title = ?", (vid_or_name, vid_or_name))
        row = cur.fetchone()
        if not row:
            conn.close()
            return {"list": []}
        vod_id = row["vod_id"]
        actors, tags = "", ""
        try:
            cur.execute("SELECT a.name FROM actresses a JOIN video_actress va ON a.cate_id = va.cate_id WHERE va.vod_id = ?", (vod_id,))
            actors = ",".join([r[0] for r in cur.fetchall()])
            cur.execute("SELECT t.tag_name FROM tags t JOIN video_tag vt ON t.tag_name = vt.tag_name WHERE vt.vod_id = ?", (vod_id,))
            tags = ",".join([r[0] for r in cur.fetchall()])
        except:
            pass
        raw_play = row["m3u8_url"] or row["vod_play_url"] or ""
        # 修复成真实链接
        play_url = self._fix_v_encoded_url(raw_play)
        conn.close()
        return {"list": [{
            "vod_id": f"{db_key}#ID#{vod_id}",
            "vod_name": row["title"] or vid_or_name,
            "vod_pic": row["pic_url"] or "",
            "vod_actor": actors,
            "vod_director": "whos.tv",
            "vod_remarks": row["vod_remarks"] or "",
            "vod_pubdate": row["vod_pubdate"] or "",
            "vod_area": row["vod_area"] or "",
            "vod_year": row["vod_year"] or "",
            "vod_tags": tags,
            "vod_content": row["vod_content"] or "",
            "vod_play_from": row["vod_play_from"] or "whos.tv",
            "vod_play_url": play_url,
            "type_name": row["type_name"] or "影片"
        }]}

    # ==================== 播放 ====================
    def playerContent(self, flag, id, vipFlags):
        playurl = id.split("|")[0]
        # 播放器内再做一次修复，确保万无一失
        playurl = self._fix_v_encoded_url(playurl)

        headers = {
            "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9; MIbox PRO Build/PI)"
        }

        if playurl.strip().lower().endswith('.m3u8'):
            try:
                from urllib.parse import urlparse
                parsed = urlparse(playurl)
                referer = f"{parsed.scheme}://{parsed.netloc}/"
                headers["Referer"] = referer
            except:
                pass

        return {"parse": 0, "url": playurl, "header": headers}

    # ==================== 搜索 ====================
    def searchContent(self, key, quick, pg="1"):
        search_list = []
        limit = 20
        for db_key in self.databases:
            conn = self._get_connection(db_key)
            if not conn:
                continue
            try:
                if self._is_exclusive_db(conn):
                    cur = conn.cursor()
                    cur.execute("SELECT vod_id, title, pic_url, vod_remarks FROM videos WHERE title LIKE ? LIMIT ?", (f"%{key}%", limit))
                    for row in cur.fetchall():
                        pic = row[2] if row[2] else MOVIE_ICON
                        search_list.append({
                            "vod_id": f"{db_key}#ID#{row[0]}",
                            "vod_name": f"[{os.path.splitext(self.databases[db_key]['name'])[0]}] {row[1]}",
                            "vod_pic": pic,
                            "vod_remarks": row[3] or ""
                        })
                else:
                    auto = self._get_auto_mapping(conn)
                    if not auto:
                        conn.close()
                        continue
                    table = auto["table_name"]
                    mapping = auto["field_mapping"]
                    search_fields = [mapping.get("vod_name")] if mapping.get("vod_name") else []
                    if not search_fields:
                        conn.close()
                        continue
                    cursor = conn.cursor()
                    where_clauses = [f"`{field}` LIKE ?" for field in search_fields]
                    sql_where = " OR ".join(where_clauses)
                    f_id = mapping.get("vod_id") or "rowid"
                    f_name = mapping.get("vod_name")
                    f_pic = mapping.get("vod_pic") or "''"
                    f_rem = mapping.get("vod_remarks") or "''"
                    sql = f"SELECT `{f_id}`, `{f_name}`, `{f_pic}`, `{f_rem}` FROM `{table}` WHERE {sql_where} LIMIT {limit}"
                    params = [f"%{key}%"] * len(search_fields)
                    cursor.execute(sql, params)
                    for row in cursor.fetchall():
                        pic = str(row[2]) if row[2] and row[2] != "None" else ""
                        if not pic:
                            pic = MOVIE_ICON
                        search_list.append({
                            "vod_id": f"{db_key}#ID#{row[0]}",
                            "vod_name": f"[{os.path.splitext(self.databases[db_key]['name'])[0]}] {row[1]}",
                            "vod_pic": pic,
                            "vod_remarks": str(row[3]) if len(row) > 3 else ""
                        })
            except:
                pass
            finally:
                conn.close()
        return {"list": search_list, "page": pg}