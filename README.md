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

### youtube-downloader.py — YouTube 视频下载

下载 YouTube 视频（含仅自己可见、会员视频），默认最高画质，同时下载所有语言字幕。

**前置条件：**
- 浏览器已登录 YouTube（Chrome 默认，可用 `--browser` 指定其他）
- 安装 ffmpeg 以获得 1080p/4K 最高画质：`winget install ffmpeg`

**用法：**
```powershell
.\.venv\Scripts\Activate.ps1

# 基本用法（最高画质 + 所有字幕）
python youtube-downloader.py "https://youtu.be/xxxxx" D:\Videos

# 指定浏览器（Edge/Firefox/Brave 等）
python youtube-downloader.py "https://youtu.be/xxxxx" D:\Videos --browser edge

# 限制画质为 1080p
python youtube-downloader.py "https://youtu.be/xxxxx" D:\Videos --quality 1080

# 不下载字幕
python youtube-downloader.py "https://youtu.be/xxxxx" D:\Videos --no-subtitles

# 下载公开视频（不读取 cookies）
python youtube-downloader.py "https://youtu.be/xxxxx" D:\Videos --browser none
```

---

### gdrive-local-sync.py — Google Drive 文件夹同步

将 Google Drive 指定文件夹同步到本地，支持递归子文件夹、Google 原生格式导出。

**前置条件：**
- 设置环境变量：`set GDRIVE_CREDENTIALS=C:\path\to\credentials.json`

**用法：**
```powershell
.\.venv\Scripts\Activate.ps1
set GDRIVE_CREDENTIALS=C:\Users\hany\secrets\credentials.json
python gdrive-local-sync.py "https://drive.google.com/drive/folders/xxx" D:\Backup
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
