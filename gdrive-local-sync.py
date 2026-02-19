"""
gdrive-local-sync.py
将 Google Drive 指定文件夹同步到本地目录。

用法：
    python gdrive-local-sync.py <drive_folder_url> <local_path>

    drive_folder_url  Google Drive 文件夹 URL，例如：
                      https://drive.google.com/drive/folders/1Ha6PP7eFc9lHnmp870-WAITeBq21I6E4
    local_path        本地目标目录，例如：D:\\MyDriveBackup

凭据配置（二选一）：
    方式 A（推荐）：设置环境变量
        set GDRIVE_CREDENTIALS=C:\\path\\to\\credentials.json
    方式 B：将 credentials.json 放在脚本同目录下

Token 自动保存在：~/.gdrive_token.json（仅你的系统账号可读）
"""

import os
import re
import sys
import json
import stat
import argparse
from pathlib import Path
from typing import Optional

# Google API
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

# ── 常量 ────────────────────────────────────────────────────────────────────
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

# token 存在用户主目录，不进项目
TOKEN_PATH = Path.home() / ".gdrive_token.json"

# Google Docs 原生格式 → 导出 MIME + 本地扩展名
EXPORT_FORMATS: dict[str, tuple[str, str]] = {
    "application/vnd.google-apps.document":     ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx"),
    "application/vnd.google-apps.spreadsheet":  ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",      ".xlsx"),
    "application/vnd.google-apps.presentation": ("application/vnd.openxmlformats-officedocument.presentationml.presentation", ".pptx"),
    "application/vnd.google-apps.drawing":      ("image/png",  ".png"),
    "application/vnd.google-apps.script":       ("application/vnd.google-apps.script+json", ".json"),
    "application/vnd.google-apps.form":         (None, None),   # 表单无法导出，跳过
    "application/vnd.google-apps.site":         (None, None),   # 网站无法导出，跳过
    "application/vnd.google-apps.folder":       (None, None),   # 文件夹本身跳过
}

# ── 终端颜色 ────────────────────────────────────────────────────────────────
class C:
    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    DIM    = "\033[2m"
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    RED    = "\033[91m"
    CYAN   = "\033[96m"

def colored(color: str, text: str) -> str:
    if sys.stdout.isatty() or os.environ.get("FORCE_COLOR"):
        return f"{color}{text}{C.RESET}"
    return text


# ── 凭据 & 认证 ─────────────────────────────────────────────────────────────
def find_credentials() -> Path:
    """按优先级查找 credentials.json：环境变量 > 脚本同目录。"""
    env_path = os.environ.get("GDRIVE_CREDENTIALS")
    if env_path:
        p = Path(env_path)
        if p.exists():
            return p
        print(colored(C.RED, f"[错误] 环境变量 GDRIVE_CREDENTIALS 指向的文件不存在：{p}"))
        sys.exit(1)

    local = Path(__file__).parent / "credentials.json"
    if local.exists():
        return local

    print(colored(C.RED, "\n[错误] 找不到 Google OAuth 凭据文件。"))
    print("请执行以下任一操作：")
    print("  A) 设置环境变量：set GDRIVE_CREDENTIALS=C:\\path\\to\\credentials.json")
    print("  B) 将 credentials.json 放在脚本同目录下")
    print("\n获取 credentials.json 的步骤请参阅 README.md")
    sys.exit(1)


def get_credentials() -> Credentials:
    """获取（或刷新）OAuth token，首次运行会弹出浏览器授权。"""
    creds: Optional[Credentials] = None

    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print(colored(C.DIM, "  [认证] 刷新 token..."))
            creds.refresh(Request())
        else:
            creds_file = find_credentials()
            print(colored(C.CYAN, f"  [认证] 使用凭据文件：{creds_file}"))
            print(colored(C.YELLOW, "  [认证] 即将打开浏览器，请登录并授权..."))
            flow = InstalledAppFlow.from_client_secrets_file(str(creds_file), SCOPES)
            creds = flow.run_local_server(port=0, open_browser=True)

        # 保存 token，设为仅当前用户可读
        TOKEN_PATH.write_text(creds.to_json())
        _set_private(TOKEN_PATH)
        print(colored(C.GREEN, f"  [认证] Token 已保存到：{TOKEN_PATH}"))

    return creds


def _set_private(path: Path) -> None:
    """将文件权限设为仅所有者可读写（600）。"""
    try:
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except Exception:
        pass  # Windows 上 chmod 支持有限，忽略


# ── URL 解析 ─────────────────────────────────────────────────────────────────
def extract_folder_id(url_or_id: str) -> str:
    """从 Drive URL 或裸 ID 中提取文件夹 ID。"""
    # 支持格式：
    #   https://drive.google.com/drive/folders/FOLDER_ID
    #   https://drive.google.com/drive/u/0/folders/FOLDER_ID
    #   FOLDER_ID（直接传 ID）
    match = re.search(r"/folders/([a-zA-Z0-9_-]+)", url_or_id)
    if match:
        return match.group(1)
    # 如果本身就是 ID（只含字母数字下划线连字符）
    if re.fullmatch(r"[a-zA-Z0-9_-]+", url_or_id):
        return url_or_id
    print(colored(C.RED, f"[错误] 无法从以下内容解析 Google Drive 文件夹 ID：\n  {url_or_id}"))
    sys.exit(1)


# ── Drive 文件列举 ───────────────────────────────────────────────────────────
def list_folder(service, folder_id: str) -> list[dict]:
    """列出文件夹内所有文件（含文件夹），自动分页。"""
    items = []
    page_token = None
    query = f"'{folder_id}' in parents and trashed = false"

    while True:
        resp = service.files().list(
            q=query,
            fields="nextPageToken, files(id, name, mimeType, size)",
            pageToken=page_token,
            pageSize=1000,
        ).execute()
        items.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    return items


# ── 同步逻辑 ─────────────────────────────────────────────────────────────────
class SyncStats:
    def __init__(self):
        self.downloaded = 0
        self.skipped    = 0
        self.exported   = 0
        self.failed     = 0
        self.unsupported = 0

    def summary(self) -> str:
        return (
            f"下载 {self.downloaded} 个，"
            f"导出 Google 格式 {self.exported} 个，"
            f"跳过（已是最新）{self.skipped} 个，"
            f"不支持导出 {self.unsupported} 个，"
            f"失败 {self.failed} 个"
        )


def _sanitize_filename(name: str) -> str:
    """清理文件名中 Windows 不允许的字符（换行符、制表符、及 \/:*?"<>| ）。"""
    # 去除首尾空白和换行
    name = name.strip()
    # 替换 Windows 文件名非法字符
    for ch in '\n\r\t\x00':
        name = name.replace(ch, "")
    for ch in r'\/:*?"<>|':
        name = name.replace(ch, "_")
    return name or "unnamed"


def sync_folder(service, folder_id: str, local_dir: Path, stats: SyncStats, depth: int = 0) -> None:
    """递归同步 Drive 文件夹到本地目录。"""
    local_dir.mkdir(parents=True, exist_ok=True)
    indent = "  " * depth

    items = list_folder(service, folder_id)

    for item in items:
        name     = _sanitize_filename(item["name"])
        mime     = item["mimeType"]
        file_id  = item["id"]
        drive_size = int(item.get("size", -1))  # Google 原生格式没有 size 字段

        # ── 子文件夹：递归处理 ──
        if mime == "application/vnd.google-apps.folder":
            print(colored(C.CYAN, f"{indent}📁 {name}/"))
            sync_folder(service, file_id, local_dir / name, stats, depth + 1)
            continue

        # ── Google 原生格式：导出 ──
        if mime in EXPORT_FORMATS:
            export_mime, export_ext = EXPORT_FORMATS[mime]
            if export_mime is None:
                print(colored(C.DIM, f"{indent}  ⚠  {name}  [不支持导出，跳过]"))
                stats.unsupported += 1
                continue

            local_path = local_dir / (name + export_ext)
            print(colored(C.DIM, f"{indent}  ↓  {name}{export_ext}  [Google 格式→导出]"), end=" ", flush=True)

            try:
                request = service.files().export_media(fileId=file_id, mimeType=export_mime)
                _download_to_file(request, local_path)
                print(colored(C.GREEN, "✓"))
                stats.exported += 1
            except Exception as e:
                print(colored(C.RED, f"✗ {e}"))
                stats.failed += 1
            continue

        # ── 普通文件：对比大小后下载 ──
        local_path = local_dir / name

        if local_path.exists() and drive_size >= 0:
            local_size = local_path.stat().st_size
            if local_size == drive_size:
                print(colored(C.DIM, f"{indent}  =  {name}  [跳过，大小相同]"))
                stats.skipped += 1
                continue

        size_label = f"{drive_size/1024:.1f} KB" if drive_size >= 0 else "未知大小"
        print(colored(C.DIM, f"{indent}  ↓  {name}  [{size_label}]"), end=" ", flush=True)

        try:
            request = service.files().get_media(fileId=file_id)
            _download_to_file(request, local_path)
            print(colored(C.GREEN, "✓"))
            stats.downloaded += 1
        except Exception as e:
            print(colored(C.RED, f"✗ {e}"))
            stats.failed += 1


def _download_to_file(request, dest: Path) -> None:
    """将 Drive API media 请求流式写入本地文件。"""
    import io
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request, chunksize=10 * 1024 * 1024)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    dest.write_bytes(buf.getvalue())


# ── 入口 ─────────────────────────────────────────────────────────────────────
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="将 Google Drive 文件夹同步到本地",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python gdrive-local-sync.py https://drive.google.com/drive/folders/1Ha6PP7... D:\\MyBackup
  python gdrive-local-sync.py 1Ha6PP7eFc9lHnmp870-WAITeBq21I6E4 D:\\MyBackup

凭据配置：
  set GDRIVE_CREDENTIALS=C:\\secrets\\credentials.json
  python gdrive-local-sync.py <url> <local_path>
""",
    )
    parser.add_argument("folder_url",  help="Google Drive 文件夹 URL 或文件夹 ID")
    parser.add_argument("local_path",  help="本地目标目录（不存在时自动创建）")
    return parser.parse_args()


def main() -> None:
    # Windows 启用 ANSI 颜色
    if sys.platform == "win32":
        os.system("")

    args = parse_args()

    folder_id  = extract_folder_id(args.folder_url)
    local_root = Path(args.local_path).expanduser().resolve()

    print(colored(C.CYAN + C.BOLD, "\n╔═══════════════════════════════════════╗"))
    print(colored(C.CYAN + C.BOLD,   "║     Google Drive Local Sync v1.0      ║"))
    print(colored(C.CYAN + C.BOLD,   "╚═══════════════════════════════════════╝"))
    print(colored(C.DIM,  f"\n  Drive 文件夹 ID : {folder_id}"))
    print(colored(C.DIM,  f"  本地目标目录    : {local_root}\n"))

    # 认证
    creds   = get_credentials()
    service = build("drive", "v3", credentials=creds)

    # 验证文件夹存在
    try:
        meta = service.files().get(fileId=folder_id, fields="name, mimeType").execute()
        if meta["mimeType"] != "application/vnd.google-apps.folder":
            print(colored(C.RED, f"[错误] 该 ID 不是文件夹：{meta['name']}"))
            sys.exit(1)
        print(colored(C.BOLD, f"  同步文件夹：{meta['name']}\n"))
    except Exception as e:
        print(colored(C.RED, f"[错误] 无法访问文件夹（ID: {folder_id}）：{e}"))
        print("请确认：1) 文件夹 ID 正确  2) 你的 Google 账号有权限访问该文件夹")
        sys.exit(1)

    # 执行同步
    stats = SyncStats()
    try:
        sync_folder(service, folder_id, local_root, stats)
    except KeyboardInterrupt:
        print(colored(C.YELLOW, "\n\n  [中断] 用户取消，已同步部分文件。"))

    # 摘要
    print(colored(C.BOLD, f"\n  ✅ 同步完成：{stats.summary()}"))
    print(colored(C.DIM,  f"  本地路径：{local_root}\n"))


if __name__ == "__main__":
    main()
