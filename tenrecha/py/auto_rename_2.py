import os
import re

# ==================== 設定區 ====================
TARGET = r"C:\gitlab\recha\py\tuntun"

# 要刪除的符號（包含空格）
SYMBOLS = [' ', '🦋', '🔞','🍀TG@hshsjk9','@hshsjk9']

# 是否清理開頭/結尾空格（即使系統不允許，還是檢查一下）
TRIM_SPACES = True

# 是否處理子目錄
RECURSIVE = True

# 是否顯示詳細訊息
VERBOSE = True
# =============================================

def clean_filenames(folder, symbols, recursive=True):
    """清理檔案名稱中的特殊符號"""
    count = 0
    
    try:
        for item in os.listdir(folder):
            old_path = os.path.join(folder, item)
            
            if os.path.isfile(old_path):
                new_name = item
                
                # 1. 刪除指定符號
                for sym in symbols:
                    new_name = new_name.replace(sym, '')
                
                # 2. 清理開頭和結尾的空格（額外處理）
                if TRIM_SPACES:
                    new_name = new_name.strip()
                
                # 3. 將多個連續空格變成一個（可選）
                # new_name = re.sub(' +', ' ', new_name)
                
                # 4. 檢查是否需要重新命名
                if new_name != item and new_name:
                    new_path = os.path.join(folder, new_name)
                    
                    if not os.path.exists(new_path):
                        try:
                            os.rename(old_path, new_path)
                            if VERBOSE:
                                print(f"✅ {item} → {new_name}")
                            count += 1
                        except Exception as e:
                            print(f"❌ 重新命名失敗: {item} - {e}")
                    else:
                        print(f"⚠️  跳過: {new_name} 已存在")
                elif not new_name:
                    print(f"⚠️  跳過: {item} (新名稱為空)")
                else:
                    if VERBOSE:
                        print(f"⏭️  跳過: {item} (無需修改)")
            
            elif os.path.isdir(old_path) and recursive:
                count += clean_filenames(old_path, symbols, recursive)
                
    except Exception as e:
        print(f"⚠️  錯誤: {e}")
    
    return count

def check_problematic_filenames(folder):
    """檢查是否有以空格開頭/結尾的檔案"""
    problem_files = []
    
    try:
        for item in os.listdir(folder):
            # 檢查開頭或結尾是否有空格
            if item.startswith(' ') or item.endswith(' '):
                problem_files.append(item)
                
            # 如果是目錄且遞迴處理
            item_path = os.path.join(folder, item)
            if os.path.isdir(item_path):
                problem_files.extend(check_problematic_filenames(item_path))
    except Exception as e:
        print(f"⚠️  檢查時發生錯誤: {e}")
    
    return problem_files

if __name__ == "__main__":
    if not os.path.exists(TARGET):
        print(f"❌ 資料夾不存在: {TARGET}")
        print("請修改 TARGET 變數")
    else:
        print(f"開始處理: {TARGET}")
        print(f"要刪除的符號: {SYMBOLS}")
        
        # 先檢查是否有問題檔案
        print("\n🔍 檢查是否有特殊檔案名稱...")
        problem_files = check_problematic_filenames(TARGET)
        
        if problem_files:
            print(f"⚠️  發現 {len(problem_files)} 個可能有問題的檔案:")
            for f in problem_files[:10]:  # 只顯示前10個
                print(f"   - '{f}'")
            if len(problem_files) > 10:
                print(f"   ... 還有 {len(problem_files) - 10} 個")
        else:
            print("✅ 沒有發現以空格開頭/結尾的檔案")
        
        # 執行清理
        print("\n開始清理檔案名稱...")
        total = clean_filenames(TARGET, SYMBOLS, RECURSIVE)
        print(f"\n🎉 完成! 共重新命名 {total} 個檔案")