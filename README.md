# hy.cursor.consolidate

存放所有小工具、Cursor 提示词和实用脚本。

---

## 工具列表

### content-supersearch.py — 文件内容超级搜索

在指定目录中递归搜索 TXT/CSV 文件，找到包含关键词的文件并显示精确位置，支持一键打开。

**功能：**
- 递归搜索指定目录的所有 `.txt` 和 `.csv` 文件
- 完美支持中文（自动检测 UTF-8、GBK、Big5 等编码）
- 精确显示匹配位置（行号 + 列号）+ 高亮关键词
- 输入编号一键用系统程序打开文件

**用法：**
```powershell
# 激活虚拟环境
.\.venv\Scripts\Activate.ps1

# 命令行模式（目录 + 关键词）
python content-supersearch.py C:\Documents 报告

# 交互式模式（逐步提示输入）
python content-supersearch.py

# 区分大小写搜索
python content-supersearch.py D:\Data keyword --case-sensitive

# 搜索额外扩展名
python content-supersearch.py D:\Data keyword --ext .txt .csv .log
```

---

### license-prep.py — Cursor License 用量分析

从 `data\input.xlsx` 读取许可证和用量数据，匹配邮箱、计算 monthly-spend-limit 并输出新表。

**用法：**
```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python license-prep.py
```

---

## 环境配置

Python 3.12 + 共用虚拟环境，详见 `environment.md`。
