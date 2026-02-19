"""
youtube-downloader.py
下载 YouTube 视频（含仅自己可见、会员视频），默认最高画质，同时下载字幕。

用法：
    python youtube-downloader.py <URL> <保存目录> [选项]

示例：
    python youtube-downloader.py "https://youtu.be/xxxxx" D:\\Videos
    python youtube-downloader.py "https://youtu.be/xxxxx" D:\\Videos --browser firefox
    python youtube-downloader.py "https://youtu.be/xxxxx" D:\\Videos --no-subtitles
    python youtube-downloader.py "https://youtu.be/xxxxx" D:\\Videos --quality 1080

登录保护说明：
    脚本自动从你的浏览器（默认 Chrome）读取 YouTube cookies，
    无需任何额外配置，只要你的浏览器已登录 YouTube 即可。
"""

import os
import sys
import shutil
import argparse
import platform
from pathlib import Path

import yt_dlp


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


# ── ffmpeg 检测 ──────────────────────────────────────────────────────────────
def check_ffmpeg() -> bool:
    """检查 ffmpeg 是否可用。"""
    return shutil.which("ffmpeg") is not None


# ── 进度钩子 ────────────────────────────────────────────────────────────────
class ProgressLogger:
    """自定义进度显示，替换 yt-dlp 默认输出。"""

    def debug(self, msg: str) -> None:
        pass

    def info(self, msg: str) -> None:
        pass

    def warning(self, msg: str) -> None:
        print(colored(C.YELLOW, f"  [警告] {msg}"))

    def error(self, msg: str) -> None:
        print(colored(C.RED, f"  [错误] {msg}"))


def progress_hook(d: dict) -> None:
    status = d.get("status")

    if status == "downloading":
        filename  = Path(d.get("filename", "")).name
        downloaded = d.get("downloaded_bytes", 0)
        total      = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
        speed      = d.get("speed", 0) or 0
        eta        = d.get("eta", 0) or 0

        if total > 0:
            pct = downloaded / total * 100
            bar_len = 30
            filled  = int(bar_len * downloaded / total)
            bar     = "█" * filled + "░" * (bar_len - filled)
            speed_mb = speed / 1024 / 1024
            print(
                f"\r  [{bar}] {pct:5.1f}%  {speed_mb:.1f} MB/s  ETA {eta}s  ",
                end="",
                flush=True,
            )
        else:
            downloaded_mb = downloaded / 1024 / 1024
            print(f"\r  已下载 {downloaded_mb:.1f} MB  ", end="", flush=True)

    elif status == "finished":
        filename = Path(d.get("filename", "")).name
        total    = d.get("total_bytes") or d.get("downloaded_bytes", 0)
        size_mb  = total / 1024 / 1024
        print(f"\r  {colored(C.GREEN, '✓')} {filename}  ({size_mb:.1f} MB)            ")

    elif status == "error":
        print(colored(C.RED, "\n  ✗ 下载出错"))


# ── 构建 yt-dlp 选项 ────────────────────────────────────────────────────────
def build_ydl_opts(
    output_dir: Path,
    browser: str,
    quality: int,
    subtitles: bool,
    ffmpeg_available: bool,
) -> dict:
    """组装 yt-dlp 下载选项。"""

    # 输出文件名模板：保存到指定目录，文件名 = 标题.扩展名
    outtmpl = str(output_dir / "%(title)s.%(ext)s")

    # 画质选择逻辑
    if ffmpeg_available:
        if quality:
            # 指定分辨率：优先该高度，否则取最接近的
            fmt = (
                f"bestvideo[height<={quality}][ext=mp4]+bestaudio[ext=m4a]/"
                f"bestvideo[height<={quality}]+bestaudio/"
                f"best[height<={quality}]/best"
            )
        else:
            # 无限制：最高画质 mp4+m4a，合并为 mp4
            fmt = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best"
    else:
        # 没有 ffmpeg，只能下载已合并的单文件流（最高 720p）
        fmt = "best"

    opts: dict = {
        "outtmpl":         outtmpl,
        "format":          fmt,
        "merge_output_format": "mp4",
        "logger":          ProgressLogger(),
        "progress_hooks":  [progress_hook],
        "noplaylist":      True,       # 单视频模式，忽略播放列表参数
        "quiet":           True,
        "no_warnings":     False,
        "ignoreerrors":    False,
    }

    # 从浏览器读取 cookies（处理登录保护内容）
    if browser and browser != "none":
        opts["cookiesfrombrowser"] = (browser,)

    # 字幕选项
    if subtitles:
        opts.update({
            "writesubtitles":     True,   # 下载手动上传的字幕
            "writeautomaticsub":  True,   # 下载自动生成字幕（YouTube Auto-Caption）
            "subtitleslangs":     ["all"],  # 所有语言
            "subtitlesformat":    "srt/vtt/best",
            "embedsubtitles":     False,  # 字幕保存为单独文件，方便查看
        })

    # ffmpeg 路径（如果在 PATH 里则自动找到）
    if ffmpeg_available:
        opts["ffmpeg_location"] = shutil.which("ffmpeg")

    return opts


# ── 主下载函数 ───────────────────────────────────────────────────────────────
def download_video(
    url: str,
    output_dir: Path,
    browser: str,
    quality: int,
    subtitles: bool,
) -> bool:
    """执行下载，返回是否成功。"""

    ffmpeg_ok = check_ffmpeg()

    if not ffmpeg_ok:
        print(colored(C.YELLOW,
            "\n  [警告] 未检测到 ffmpeg，将下载已合并的单文件流（最高 720p）。\n"
            "         安装 ffmpeg 后可获得最高画质（1080p/4K）。\n"
            "         安装方法：https://ffmpeg.org/download.html\n"
            "         或 winget install ffmpeg\n"
        ))

    # 先获取视频信息（标题、时长等）
    print(colored(C.DIM, "\n  正在获取视频信息..."))
    info_opts = {"quiet": True, "no_warnings": True, "skip_download": True}
    if browser and browser != "none":
        info_opts["cookiesfrombrowser"] = (browser,)

    try:
        with yt_dlp.YoutubeDL(info_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as e:
        msg = str(e)
        if "Sign in" in msg or "login" in msg.lower() or "private" in msg.lower():
            print(colored(C.RED,
                "\n  [错误] 视频需要登录才能访问。\n"
                f"         当前使用浏览器：{browser}\n"
                "         请确认该浏览器已登录 YouTube，或用 --browser 指定其他浏览器。"
            ))
        else:
            print(colored(C.RED, f"\n  [错误] 无法获取视频信息：{e}"))
        return False
    except Exception as e:
        print(colored(C.RED, f"\n  [错误] {e}"))
        return False

    # 显示视频信息
    title    = info.get("title", "未知标题")
    duration = info.get("duration", 0)
    uploader = info.get("uploader", "未知上传者")
    mins, secs = divmod(duration or 0, 60)

    print(colored(C.BOLD,   f"\n  标题    : {title}"))
    print(colored(C.DIM,    f"  上传者  : {uploader}"))
    print(colored(C.DIM,    f"  时长    : {mins}:{secs:02d}"))
    print(colored(C.DIM,    f"  保存到  : {output_dir}"))
    if subtitles:
        print(colored(C.DIM, "  字幕    : 是（所有语言）"))
    quality_label = f"{quality}p" if quality else "最高画质"
    print(colored(C.DIM,    f"  画质    : {quality_label}"))
    print()

    # 执行下载
    ydl_opts = build_ydl_opts(output_dir, browser, quality, subtitles, ffmpeg_ok)
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return True
    except yt_dlp.utils.DownloadError as e:
        print(colored(C.RED, f"\n  [错误] 下载失败：{e}"))
        return False
    except Exception as e:
        print(colored(C.RED, f"\n  [错误] 意外错误：{e}"))
        return False


# ── 参数解析 ────────────────────────────────────────────────────────────────
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="下载 YouTube 视频（含登录保护内容），默认最高画质",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python youtube-downloader.py "https://youtu.be/xxxxx" D:\\Videos
  python youtube-downloader.py "https://youtu.be/xxxxx" D:\\Videos --browser edge
  python youtube-downloader.py "https://youtu.be/xxxxx" D:\\Videos --quality 1080
  python youtube-downloader.py "https://youtu.be/xxxxx" D:\\Videos --no-subtitles
  python youtube-downloader.py "https://youtu.be/xxxxx" D:\\Videos --browser none

支持的浏览器（--browser）：
  chrome（默认）, edge, firefox, safari, brave, opera, chromium
  none = 不使用 cookies（只能访问公开视频）
""",
    )
    parser.add_argument("url",        help="YouTube 视频 URL")
    parser.add_argument("output_dir", help="保存目录（不存在时自动创建）")
    parser.add_argument(
        "--browser", "-b",
        default="chrome",
        help="从哪个浏览器读取 cookies（默认：chrome）",
    )
    parser.add_argument(
        "--quality", "-q",
        type=int,
        default=0,
        metavar="HEIGHT",
        help="最大视频高度，例如 1080、720（默认：最高可用画质）",
    )
    parser.add_argument(
        "--no-subtitles",
        action="store_true",
        default=False,
        help="不下载字幕",
    )
    return parser.parse_args()


# ── 入口 ────────────────────────────────────────────────────────────────────
def main() -> None:
    if sys.platform == "win32":
        os.system("")  # 启用 Windows ANSI 颜色

    args = parse_args()

    print(colored(C.CYAN + C.BOLD, "\n╔══════════════════════════════════════╗"))
    print(colored(C.CYAN + C.BOLD,   "║     YouTube Downloader v1.0          ║"))
    print(colored(C.CYAN + C.BOLD,   "╚══════════════════════════════════════╝"))

    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    success = download_video(
        url        = args.url,
        output_dir = output_dir,
        browser    = args.browser,
        quality    = args.quality,
        subtitles  = not args.no_subtitles,
    )

    if success:
        print(colored(C.GREEN + C.BOLD, f"\n  ✅ 完成！文件已保存到：{output_dir}\n"))
    else:
        print(colored(C.RED, "\n  ❌ 下载失败，请检查以上错误信息。\n"))
        sys.exit(1)


if __name__ == "__main__":
    main()
