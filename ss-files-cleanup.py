"""
ss-files-cleanup.py
====================
功能：
  任务1 — 前缀清洗：扫描指定目录（含子目录）所有文件，匹配 CSV 中前缀（最长匹配，
          忽略大小写/全半角），将前缀从文件名中删除；重名则加 _copy1、_copy2...
  任务2 — 相似分组：对重命名后的文件用 jieba 中文分词，计算词组重叠率，
          重叠率 ≥ 30% 的文件归入同一子文件夹（001、002...），
          无法配对的文件留在原位。

用法：
  python ss-files-cleanup.py <目标目录> [--prefixes <CSV路径>] [--threshold 0.3]

示例：
  python ss-files-cleanup.py "D:/Videos" --prefixes "data/ss-files-cleanup-prefixes2Remove.csv"
"""

import os
import re
import sys
import csv
import shutil
import unicodedata
import argparse
from pathlib import Path
from collections import defaultdict
from itertools import combinations

# ── 尝试导入 jieba，提前友好报错 ──────────────────────────────────────────────
try:
    import jieba
    jieba.setLogLevel(20)  # 关闭 jieba 初始化日志
except ImportError:
    print("❌ 缺少依赖 jieba，请先运行：pip install jieba")
    sys.exit(1)

# ─────────────────────────────────────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────────────────────────────────────

def normalize(text: str) -> str:
    """全角→半角、统一为小写，用于比较（不修改实际文件名）。"""
    # 全角转半角
    result = unicodedata.normalize("NFKC", text)
    return result.lower()


def load_prefixes(csv_path: str) -> list[str]:
    """从 CSV 读取前缀列表，去除空行，按长度降序排列（最长优先匹配）。"""
    prefixes = []
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        for row in csv.reader(f):
            for cell in row:
                cell = cell.strip()
                if cell:
                    prefixes.append(cell)
    # 按长度降序 → 最长前缀优先
    prefixes.sort(key=len, reverse=True)
    return prefixes


def find_longest_prefix(filename: str, prefixes: list[str]) -> str | None:
    """
    在 filename 中查找最长匹配前缀（已按长度降序排列）。
    忽略大小写和全半角差异。
    返回原始前缀字符串，未匹配则返回 None。
    """
    norm_filename = normalize(filename)
    for prefix in prefixes:
        norm_prefix = normalize(prefix)
        if norm_filename.startswith(norm_prefix):
            return prefix
    return None


def safe_new_name(directory: Path, new_name: str) -> str:
    """
    检查目标目录中是否已存在 new_name，若存在则附加 _copy1、_copy2...
    返回最终安全的文件名（含扩展名）。
    """
    stem = Path(new_name).stem
    suffix = Path(new_name).suffix
    candidate = new_name
    counter = 1
    while (directory / candidate).exists():
        candidate = f"{stem}_copy{counter}{suffix}"
        counter += 1
    return candidate


def collect_files(root: Path) -> list[Path]:
    """递归收集 root 下所有文件（不含目录本身）。"""
    files = []
    for p in root.rglob("*"):
        if p.is_file():
            files.append(p)
    return files


# ─────────────────────────────────────────────────────────────────────────────
# 任务1：前缀清洗
# ─────────────────────────────────────────────────────────────────────────────

def phase1_preview(files: list[Path], prefixes: list[str]) -> list[tuple[Path, Path]]:
    """
    预览阶段：计算所有需要重命名的 (旧路径, 新路径) 对。
    不修改文件系统。
    """
    plan = []  # [(old_path, new_path)]
    # 用于在同一父目录内跟踪已规划的新文件名，避免重名
    reserved: dict[Path, set[str]] = defaultdict(set)

    for old_path in files:
        matched_prefix = find_longest_prefix(old_path.name, prefixes)
        if matched_prefix is None:
            continue  # 无需重命名

        norm_prefix = normalize(matched_prefix)
        norm_name = normalize(old_path.name)
        # 用原始文件名做切割，并去除开头多余空格
        new_name_raw = old_path.name[len(matched_prefix):].lstrip()
        if not new_name_raw.strip():
            # 去掉前缀后为空，跳过
            continue

        parent = old_path.parent
        # 考虑已规划的文件名（避免同批次内的重名）
        existing_names = {f.name for f in parent.iterdir() if f.is_file()} | reserved[parent]
        # 临时把旧文件名从冲突集合中移除（它本身会被重命名）
        existing_names.discard(old_path.name)

        final_name = new_name_raw
        stem = Path(new_name_raw).stem
        suffix = Path(new_name_raw).suffix
        counter = 1
        while final_name in existing_names:
            final_name = f"{stem}_copy{counter}{suffix}"
            counter += 1

        reserved[parent].add(final_name)
        new_path = parent / final_name
        plan.append((old_path, new_path))

    return plan


def phase1_execute(plan: list[tuple[Path, Path]]) -> list[Path]:
    """
    执行重命名。返回重命名后的新路径列表（用于任务2）。
    """
    new_paths = []
    for old_path, new_path in plan:
        old_path.rename(new_path)
        new_paths.append(new_path)
    return new_paths


# ─────────────────────────────────────────────────────────────────────────────
# 任务2：相似分组
# ─────────────────────────────────────────────────────────────────────────────

def tokenize(filename: str) -> set[str]:
    """
    用 jieba 对文件名（去掉扩展名）分词，返回长度 ≥ 2 的词组集合。
    同时也保留原始完整词用于匹配。
    """
    stem = Path(filename).stem
    # 去除常见分隔符，让 jieba 更准确
    cleaned = re.sub(r"[，。！？、；：\u201c\u201d\u2018\u2019「」【】《》\[\]()（）\-_\s]+", " ", stem)
    words = set(jieba.cut(cleaned, cut_all=False))
    # 只保留长度 ≥ 2 的有意义词
    return {w.strip() for w in words if len(w.strip()) >= 2}


def jaccard(set_a: set, set_b: set) -> float:
    """Jaccard 相似度 = |交集| / |并集|。"""
    if not set_a and not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union


def build_groups(files: list[Path], threshold: float) -> dict[int, list[Path]]:
    """
    对文件列表进行相似度聚类（贪心合并）。
    返回 {组号: [文件路径列表]}，组号从 1 开始。
    只保留 size ≥ 2 的组（单独文件留在原处）。
    """
    if not files:
        return {}

    # 提前计算每个文件的词组集合
    tokens: dict[Path, set[str]] = {f: tokenize(f.name) for f in files}

    # Union-Find（并查集）实现贪心合并
    parent = {f: f for f in files}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[rx] = ry

    # 两两比较，满足阈值则合并
    file_list = list(files)
    for i in range(len(file_list)):
        for j in range(i + 1, len(file_list)):
            a, b = file_list[i], file_list[j]
            sim = jaccard(tokens[a], tokens[b])
            if sim >= threshold:
                union(a, b)

    # 汇总分组
    groups_raw: dict[Path, list[Path]] = defaultdict(list)
    for f in files:
        groups_raw[find(f)].append(f)

    # 过滤掉只有1个文件的组
    result = {}
    group_id = 1
    for members in groups_raw.values():
        if len(members) >= 2:
            result[group_id] = members
            group_id += 1

    return result


def phase2_preview(
    all_files: list[Path], groups: dict[int, list[Path]]
) -> list[tuple[Path, Path]]:
    """
    预览阶段：计算所有需要移动的 (旧路径, 新路径) 对。
    子文件夹格式：{parent}/{nnn}/filename
    """
    plan = []
    # 统计每个根目录下已用的组号
    dir_group_counter: dict[Path, int] = defaultdict(int)
    # 记录每个根目录下 group_id → folder_name 的映射
    dir_group_folder: dict[tuple[Path, int], str] = {}

    for group_id, members in groups.items():
        # 同一组内的文件可能分散在不同子目录，按父目录分别处理
        by_parent: dict[Path, list[Path]] = defaultdict(list)
        for f in members:
            by_parent[f.parent].append(f)

        for parent, files_in_parent in by_parent.items():
            key = (parent, group_id)
            if key not in dir_group_folder:
                dir_group_counter[parent] += 1
                n = dir_group_counter[parent]
                dir_group_folder[key] = f"{n:03d}"
            folder_name = dir_group_folder[key]
            target_dir = parent / folder_name
            for f in files_in_parent:
                plan.append((f, target_dir / f.name))

    return plan


def phase2_execute(plan: list[tuple[Path, Path]]) -> None:
    """执行文件移动，自动创建子目录。"""
    for old_path, new_path in plan:
        new_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(old_path), str(new_path))


# ─────────────────────────────────────────────────────────────────────────────
# 打印预览表格
# ─────────────────────────────────────────────────────────────────────────────

def print_preview_table(plan: list[tuple[Path, Path]], root: Path, title: str) -> None:
    """以表格形式打印预览，路径相对于 root 显示。"""
    print(f"\n{'═'*70}")
    print(f"  {title}（共 {len(plan)} 个文件）")
    print(f"{'═'*70}")
    if not plan:
        print("  （无需操作）")
        return
    for old_path, new_path in plan:
        try:
            old_rel = old_path.relative_to(root)
        except ValueError:
            old_rel = old_path
        try:
            new_rel = new_path.relative_to(root)
        except ValueError:
            new_rel = new_path
        print(f"  【原】{old_rel}")
        print(f"  【新】{new_rel}")
        print(f"  {'─'*60}")


def print_group_preview(
    groups: dict[int, list[Path]], plan: list[tuple[Path, Path]], root: Path
) -> None:
    """打印分组预览，按组显示。"""
    print(f"\n{'═'*70}")
    print(f"  任务2 — 相似分组预览（共 {len(groups)} 组，{len(plan)} 个文件将被移动）")
    print(f"{'═'*70}")
    if not groups:
        print("  （无相似文件组，所有文件留在原位）")
        return
    # 建立 old_path → new_path 的映射
    move_map = {old: new for old, new in plan}
    for group_id, members in groups.items():
        print(f"\n  📁 第 {group_id} 组（{len(members)} 个文件）")
        for f in members:
            new_path = move_map.get(f, f)
            try:
                new_rel = new_path.relative_to(root)
            except ValueError:
                new_rel = new_path
            print(f"    → {new_rel}")


# ─────────────────────────────────────────────────────────────────────────────
# 主程序
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="SS Files Cleanup — 前缀清洗 + 相似文件分组"
    )
    parser.add_argument("target_dir", help="要处理的目标目录路径")
    parser.add_argument(
        "--prefixes",
        default=str(Path(__file__).parent / "data" / "ss-files-cleanup-prefixes2Remove.csv"),
        help="前缀 CSV 文件路径（默认：data/ss-files-cleanup-prefixes2Remove.csv）",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.3,
        help="相似度阈值（Jaccard，默认 0.3 即 30%%）",
    )
    args = parser.parse_args()

    root = Path(args.target_dir).resolve()
    if not root.is_dir():
        print(f"❌ 目标目录不存在：{root}")
        sys.exit(1)

    prefixes_path = Path(args.prefixes).resolve()
    if not prefixes_path.is_file():
        print(f"❌ 前缀 CSV 文件不存在：{prefixes_path}")
        sys.exit(1)

    print(f"\n🚀 SS Files Cleanup 启动")
    print(f"   目标目录：{root}")
    print(f"   前缀文件：{prefixes_path}")
    print(f"   相似度阈值：{args.threshold:.0%}")

    # ── 加载前缀 ──────────────────────────────────────────────────────────────
    prefixes = load_prefixes(str(prefixes_path))
    print(f"   已加载 {len(prefixes)} 条前缀规则")

    # ════════════════════════════════════════════════════════════════════════
    # 任务1：前缀清洗
    # ════════════════════════════════════════════════════════════════════════
    print(f"\n{'━'*70}")
    print("  📋 任务1 — 前缀清洗：扫描文件中……")
    all_files = collect_files(root)
    print(f"  共发现 {len(all_files)} 个文件")

    plan1 = phase1_preview(all_files, prefixes)
    print_preview_table(plan1, root, "任务1 — 前缀清洗预览")

    if plan1:
        answer = input("\n❓ 确认执行以上重命名操作？[y/N] ").strip().lower()
        if answer == "y":
            renamed_paths = phase1_execute(plan1)
            print(f"✅ 任务1 完成：成功重命名 {len(renamed_paths)} 个文件")
        else:
            print("⏭️  已跳过任务1，使用原始文件名继续……")
            renamed_paths = []  # 不执行重命名，但继续用原文件做任务2
    else:
        print("\n✅ 任务1：没有需要重命名的文件")
        renamed_paths = []

    # ════════════════════════════════════════════════════════════════════════
    # 任务2：相似分组
    # ════════════════════════════════════════════════════════════════════════
    print(f"\n{'━'*70}")
    print("  📋 任务2 — 相似分组：重新扫描文件中……")
    all_files_after = collect_files(root)
    print(f"  共发现 {len(all_files_after)} 个文件")
    print("  ⏳ 正在分词和计算相似度（文件较多时可能需要几秒）……")

    groups = build_groups(all_files_after, args.threshold)
    plan2 = phase2_preview(all_files_after, groups)
    print_group_preview(groups, plan2, root)

    if plan2:
        answer = input("\n❓ 确认执行以上分组移动操作？[y/N] ").strip().lower()
        if answer == "y":
            phase2_execute(plan2)
            print(f"✅ 任务2 完成：{len(groups)} 组，{len(plan2)} 个文件已移动到子文件夹")
        else:
            print("⏭️  已跳过任务2")
    else:
        print("\n✅ 任务2：没有发现相似文件组，所有文件留在原位")

    print(f"\n🎉 全部完成！\n")


if __name__ == "__main__":
    main()
