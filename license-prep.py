#!/usr/bin/env python3
"""
license-prep.py — 按 missions.md 要求处理 data/input.xlsx：

1. 从 data\\input.xlsx 读取
2. 用 Token Usage 的 Email 匹配 Cursor Licenses 的 Users_to_add（不区分大小写），
   追加 Total Prompts 列和 On-Demand Spend 列
3. 在扩展后的 Cursor Licenses 上按 Total Prompts 升序排序，先将所有 monthly-spend-limit 视为 0，
   再经两轮循环赋值：
   第一轮（On-Demand Spend 设底值）：
     >50→100, >20→80, >10→40, >2→20，否则 0
   第二轮（Total Prompts 叠加）：
     <300 不变, <600 +40, <1000 +100, <1500 +150, <2000 +200, >=2000 直接设为 250
4. 结果保存到新表「Cursor Licenses New」（不修改原表）

Environment: Python 3.12，与项目其他 .py 共用同一虚拟环境。
"""

from pathlib import Path
import openpyxl

INPUT_PATH = Path(__file__).resolve().parent / "data" / "input.xlsx"


def find_col(header_row, name_candidates):
    """在首行中查找列名（不区分大小写），支持多个候选名。"""
    for cell in header_row:
        val = (cell.value or "").strip()
        for candidate in name_candidates:
            if val.lower() == candidate.lower():
                return cell.column
    return None


def to_number(val, default=0):
    """将单元格值转为数字，失败时返回 default。"""
    if val is None:
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def main():
    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"输入文件不存在: {INPUT_PATH}")

    wb = openpyxl.load_workbook(INPUT_PATH, data_only=True)

    # --- 1) 从 Token Usage 读取 Email -> (Total Prompts, On-Demand Spend) ---
    if "Token Usage" not in wb.sheetnames:
        raise ValueError("工作簿中未找到工作表 'Token Usage'")
    ws_token = wb["Token Usage"]
    header_token = list(next(ws_token.iter_rows(min_row=1, max_row=1)))

    col_email_t = find_col(header_token, ["Email"])
    col_total_t = find_col(header_token, ["Total Prompts", "Total Prompots"])
    col_spend_t = find_col(header_token, ["On-Demand Spend"])

    if col_email_t is None or col_total_t is None:
        raise ValueError("'Token Usage' 中未找到 'Email' 或 'Total Prompts' 列")
    if col_spend_t is None:
        raise ValueError("'Token Usage' 中未找到 'On-Demand Spend' 列")

    email_data = {}   # email_lower -> {"total": int, "spend": float}
    for row in ws_token.iter_rows(min_row=2):
        email = (row[col_email_t - 1].value or "").strip()
        if not email:
            continue
        email_data[email.lower()] = {
            "total": int(to_number(row[col_total_t - 1].value)),
            "spend": to_number(row[col_spend_t - 1].value),
        }

    # --- 2) 读取 Cursor Licenses，匹配并追加两列 ---
    if "Cursor Licenses" not in wb.sheetnames:
        raise ValueError("工作簿中未找到工作表 'Cursor Licenses'")
    ws_lic  = wb["Cursor Licenses"]
    max_col = ws_lic.max_column
    header_lic = list(next(ws_lic.iter_rows(min_row=1, max_row=1, max_col=max_col)))

    col_users = find_col(header_lic, ["Users_to_add"])
    col_spend = find_col(header_lic, ["monthly-spend-limit"])
    if col_users is None:
        raise ValueError("'Cursor Licenses' 中未找到 'Users_to_add' 列")
    if col_spend is None:
        raise ValueError("'Cursor Licenses' 中未找到 'monthly-spend-limit' 列")

    # 读入数据行，跳过 Users_to_add 为空的行（含 Excel 追踪的空行）
    # 每条记录：(row_vals, total_prompts, ondemand_spend)
    data_rows = []
    for r in range(2, ws_lic.max_row + 1):
        row_vals = [ws_lic.cell(row=r, column=c).value for c in range(1, max_col + 1)]
        user = (row_vals[col_users - 1] or "").strip()
        if not user:
            continue
        info          = email_data.get(user.lower(), {})
        total_prompts = info.get("total", 0)
        spend         = info.get("spend", 0)
        data_rows.append((row_vals, total_prompts, spend))

    # --- 3) 按 Total Prompts 升序排序（x[1] = total_prompts）---
    data_rows.sort(key=lambda x: (x[1], (x[0][col_users - 1] or "")))

    # --- 4) 两轮循环计算 monthly-spend-limit ---
    limits = []
    for _, total_prompts, spend in data_rows:

        # 第一轮：On-Demand Spend (>) 设底值
        if spend > 50:
            base = 100
        elif spend > 20:
            base = 80
        elif spend > 10:
            base = 40
        elif spend > 2:
            base = 20
        else:
            base = 0

        # 第二轮：Total Prompts 叠加（>=2000 直接覆盖为 250）
        if total_prompts < 300:
            final = base           # 不变
        elif total_prompts < 600:
            final = base + 40
        elif total_prompts < 1000:
            final = base + 100
        elif total_prompts < 1500:
            final = base + 150
        elif total_prompts < 2000:
            final = base + 200
        else:
            final = 250            # 直接设为 250，不再叠加

        limits.append(final)

    # --- 5) 写出到新表「Cursor Licenses New」（不修改原表）---
    wb2 = openpyxl.load_workbook(INPUT_PATH, data_only=False)
    if "Cursor Licenses New" in wb2.sheetnames:
        del wb2["Cursor Licenses New"]
    ws_new = wb2.create_sheet("Cursor Licenses New")

    # 表头：原表头 + Total Prompts + On-Demand Spend
    for c, cell in enumerate(header_lic, start=1):
        ws_new.cell(row=1, column=c, value=cell.value)
    col_total_new = max_col + 1
    col_spend_new = max_col + 2
    ws_new.cell(row=1, column=col_total_new, value="Total Prompts")
    ws_new.cell(row=1, column=col_spend_new, value="On-Demand Spend")

    for row_idx, ((row_vals, total_prompts, spend), limit_val) in enumerate(
        zip(data_rows, limits), start=2
    ):
        for c, val in enumerate(row_vals, start=1):
            ws_new.cell(row=row_idx, column=c, value=limit_val if c == col_spend else val)
        ws_new.cell(row=row_idx, column=col_total_new, value=total_prompts)
        ws_new.cell(row=row_idx, column=col_spend_new, value=spend)

    wb2.save(INPUT_PATH)
    print("结果已写入工作表「Cursor Licenses New」，文件:", INPUT_PATH)


if __name__ == "__main__":
    main()
