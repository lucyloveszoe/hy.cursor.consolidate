"""
content-supersearch.py
在指定目录中递归搜索 TXT 和 CSV 文件，查找包含特定关键词的文件，
并支持一键打开文件到匹配位置。

用法：
    python content-supersearch.py [目录] [关键词]
    python content-supersearch.py          # 交互式输入
"""

import os
import sys
import argparse
import subprocess
import platform
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

# ── 终端颜色（无需额外依赖，使用 ANSI 转义码）──────────────────────────────
class Color:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    CYAN    = "\033[96m"
    WHITE   = "\033[97m"
    DIM     = "\033[2m"

def _ansi_supported() -> bool:
    """Windows 10 1511+ 支持 ANSI；其他平台默认支持。"""
    if platform.system() == "Windows":
        return os.environ.get("ANSICON") is not None or (
            hasattr(sys.stdout, "fileno") and os.get_terminal_size
            and "WT_SESSION" in os.environ  # Windows Terminal
            or "TERM_PROGRAM" in os.environ
        )
    return True

USE_COLOR = _ansi_supported()

def c(color: str, text: str) -> str:
    if USE_COLOR:
        return f"{color}{text}{Color.RESET}"
    return text


# ── 数据结构 ────────────────────────────────────────────────────────────────
@dataclass
class Match:
    line_num: int          # 1-indexed
    col_num: int           # 0-indexed char position within line
    line_text: str         # 匹配行的原始内容


@dataclass
class FileResult:
    path: Path
    encoding: str
    matches: list[Match] = field(default_factory=list)

    @property
    def match_count(self) -> int:
        return len(self.matches)


# ── 编码检测 ────────────────────────────────────────────────────────────────
ENCODINGS = ["utf-8-sig", "utf-8", "utf-16", "utf-16-le", "utf-16-be", "gbk", "gb2312", "big5", "latin-1"]

def read_lines(path: Path) -> tuple[Optional[list[str]], str]:
    """
    尝试多种编码读取文件，返回 (行列表, 成功的编码名称)。
    失败时返回 (None, "")。
    """
    for enc in ENCODINGS:
        try:
            with path.open("r", encoding=enc, errors="strict") as f:
                lines = f.readlines()
            return lines, enc
        except (UnicodeDecodeError, UnicodeError):
            continue
        except OSError as e:
            print(c(Color.RED, f"  [读取错误] {path}: {e}"))
            return None, ""
    return None, ""


# ── 核心搜索逻辑 ────────────────────────────────────────────────────────────
def search_file(path: Path, keyword: str, case_sensitive: bool) -> Optional[FileResult]:
    """在单个文件中搜索关键词，返回 FileResult 或 None（无匹配或读取失败）。"""
    print(path)
    lines, enc = read_lines(path)
    if lines is None:
        return None

    kw = keyword if case_sensitive else keyword.lower()
    result = FileResult(path=path, encoding=enc)

    for line_idx, raw_line in enumerate(lines):
        text = raw_line.rstrip("\n\r")
        haystack = text if case_sensitive else text.lower()

        col = 0
        search_from = 0
        while True:
            pos = haystack.find(kw, search_from)
            if pos == -1:
                break
            result.matches.append(Match(
                line_num=line_idx + 1,
                col_num=pos,
                line_text=text,
            ))
            search_from = pos + len(kw)

    return result if result.matches else None


def search_directory(
    root: Path,
    keyword: str,
    case_sensitive: bool,
    extensions: tuple[str, ...] = (".txt", ".csv"),
) -> list[FileResult]:
    """递归搜索目录，返回所有包含关键词的文件结果列表。"""
    results: list[FileResult] = []
    files = [p for ext in extensions for p in root.rglob(f"*{ext}") if p.is_file()]
    files.sort()

    total = len(files)
    if total == 0:
        return results

    print(c(Color.DIM, f"\n  正在扫描 {total} 个文件..."))

    for i, path in enumerate(files, 1):
        # 进度提示（每 50 个文件或最后一个）
        if i % 50 == 0 or i == total:
            print(c(Color.DIM, f"  [{i}/{total}] {path.name}"), end="\r")

        fr = search_file(path, keyword, case_sensitive)
        if fr:
            results.append(fr)

    print(" " * 60, end="\r")  # 清除进度行
    return results


# ── 结果展示 ────────────────────────────────────────────────────────────────
CONTEXT_CHARS = 60  # 每行最多显示的字符数（关键词居中）

def _highlight_line(text: str, keyword: str, case_sensitive: bool) -> str:
    """在行文本中高亮关键词（仅高亮第一个匹配）。"""
    kw_lower = keyword if case_sensitive else keyword.lower()
    text_lower = text if case_sensitive else text.lower()
    pos = text_lower.find(kw_lower)
    if pos == -1 or not USE_COLOR:
        return text[:CONTEXT_CHARS * 2]

    # 截取上下文窗口
    start = max(0, pos - CONTEXT_CHARS // 2)
    end = min(len(text), pos + len(keyword) + CONTEXT_CHARS // 2)
    prefix = ("…" if start > 0 else "") + text[start:pos]
    match  = text[pos:pos + len(keyword)]
    suffix = text[pos + len(keyword):end] + ("…" if end < len(text) else "")

    return prefix + c(Color.YELLOW + Color.BOLD, match) + suffix


def display_results(results: list[FileResult], keyword: str, case_sensitive: bool) -> None:
    """以清晰的格式打印所有匹配结果。"""
    if not results:
        print(c(Color.RED, "\n  未找到任何匹配文件。"))
        return

    total_matches = sum(r.match_count for r in results)
    print(c(Color.GREEN, f"\n  找到 {len(results)} 个文件，共 {total_matches} 处匹配：\n"))

    for idx, fr in enumerate(results, 1):
        # 文件标题行
        rel = fr.path
        print(c(Color.CYAN + Color.BOLD,
                f"  [{idx:>3}] {rel}") +
              c(Color.DIM, f"  ({fr.encoding}, {fr.match_count} 处匹配)"))

        # 最多显示前 5 条匹配
        show = fr.matches[:5]
        for m in show:
            line_info = c(Color.DIM, f"        行 {m.line_num:>5}, 列 {m.col_num + 1:>4}  │  ")
            content   = _highlight_line(m.line_text.strip(), keyword, case_sensitive)
            print(line_info + content)

        if fr.match_count > 5:
            print(c(Color.DIM, f"        … 还有 {fr.match_count - 5} 处匹配未显示"))
        print()


# ── 打开文件 ────────────────────────────────────────────────────────────────
def open_file(path: Path) -> None:
    """用系统默认程序打开文件。"""
    system = platform.system()
    try:
        if system == "Windows":
            os.startfile(str(path))
        elif system == "Darwin":
            subprocess.run(["open", str(path)], check=True)
        else:
            subprocess.run(["xdg-open", str(path)], check=True)
        print(c(Color.GREEN, f"  已打开：{path}"))
    except Exception as e:
        print(c(Color.RED, f"  打开失败：{e}"))
        print(c(Color.DIM,  f"  文件路径：{path}"))


def interactive_open(results: list[FileResult]) -> None:
    """显示选择菜单，让用户选择要打开的文件。"""
    print(c(Color.WHITE + Color.BOLD,
            "  输入编号打开对应文件（多个用逗号分隔，'a' 全部打开，Enter 退出）："), end=" ")

    try:
        choice = input().strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return

    if not choice:
        return

    if choice.lower() == "a":
        for fr in results:
            open_file(fr.path)
        return

    for part in choice.split(","):
        part = part.strip()
        if not part.isdigit():
            print(c(Color.RED, f"  无效输入：{part!r}，请输入数字编号"))
            continue
        num = int(part)
        if 1 <= num <= len(results):
            open_file(results[num - 1].path)
        else:
            print(c(Color.RED, f"  编号 {num} 超出范围（1–{len(results)}）"))


# ── 程序入口 ────────────────────────────────────────────────────────────────
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="在 TXT/CSV 文件中递归搜索关键词",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python content-supersearch.py C:\\Documents 报告
  python content-supersearch.py D:\\Data 2024 --case-sensitive
  python content-supersearch.py                     # 交互式模式
""",
    )
    parser.add_argument("directory", nargs="?", help="搜索目录路径")
    parser.add_argument("keyword",   nargs="?", help="搜索关键词")
    parser.add_argument(
        "--case-sensitive", "-c",
        action="store_true",
        default=False,
        help="区分大小写（默认不区分）",
    )
    parser.add_argument(
        "--ext", "-e",
        nargs="+",
        default=[".txt", ".csv"],
        help="要搜索的文件扩展名（默认：.txt .csv）",
    )
    return parser.parse_args()


def prompt_input(prompt: str) -> str:
    """带颜色的输入提示。"""
    print(c(Color.CYAN + Color.BOLD, prompt), end=" ")
    return input().strip()


def main() -> None:
    # Windows 终端启用 ANSI 颜色
    if platform.system() == "Windows":
        os.system("")  # 激活 ANSI 转义码支持

    args = parse_args()

    print(c(Color.CYAN + Color.BOLD, "\n╔══════════════════════════════════╗"))
    print(c(Color.CYAN + Color.BOLD,   "║     Content SuperSearch v1.0     ║"))
    print(c(Color.CYAN + Color.BOLD,   "╚══════════════════════════════════╝"))

    # 获取搜索目录
    dir_str = args.directory
    while not dir_str:
        dir_str = prompt_input("\n搜索目录：")

    root = Path(dir_str).expanduser().resolve()
    if not root.exists():
        print(c(Color.RED, f"\n  错误：目录不存在 → {root}"))
        sys.exit(1)
    if not root.is_dir():
        print(c(Color.RED, f"\n  错误：路径不是目录 → {root}"))
        sys.exit(1)

    # 获取关键词
    keyword = args.keyword
    while not keyword:
        keyword = prompt_input("搜索关键词：")

    # 确保扩展名带点
    extensions = tuple(
        e if e.startswith(".") else f".{e}"
        for e in args.ext
    )

    case_sensitive = args.case_sensitive
    mode_label = "区分大小写" if case_sensitive else "不区分大小写"

    print(c(Color.DIM, f"\n  目录：{root}"))
    print(c(Color.DIM, f"  关键词：{keyword!r}  [{mode_label}]"))
    print(c(Color.DIM, f"  扩展名：{', '.join(extensions)}"))

    # 执行搜索
    results = search_directory(root, keyword, case_sensitive, extensions)

    # 展示结果
    display_results(results, keyword, case_sensitive)

    # 交互式打开
    if results:
        interactive_open(results)

    print(c(Color.DIM, "\n  搜索完成。再见！\n"))


if __name__ == "__main__":
    main()
