#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""项目三 · 分层盲测分类与混淆矩阵

零第三方依赖。按工况分层留出最后 N 组作为盲测集（录前不参与调参），
训练集标准化后取类中心，用最近欧氏距离判别。

用法（在 02-20Days-Challenge/ 目录下）：
    python src/classify.py --features features.csv --report classification_report.md
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import sys

FEATURES_BASIC = [
    "dominant_hz", "centroid_hz", "rms", "zcr", "low_ratio", "high_ratio",
]
META_COLS = {"file", "condition", "run", "sample_rate", "frames"}


def pick_features(header, mode):
    """mode: 'basic' 只用最初 6 项；'all' 用 features.csv 里全部数值列；
    其他按逗号分隔的字段名。"""
    if mode == "basic":
        return list(FEATURES_BASIC)
    if mode == "all":
        return [c for c in header if c not in META_COLS]
    return [c.strip() for c in mode.split(",") if c.strip()]


def load(path, features):
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        sys.exit("features.csv 是空的")
    missing = [k for k in ["file", "condition", "run"] + features if k not in rows[0]]
    if missing:
        sys.exit("features.csv 缺字段：%s" % ", ".join(missing))
    for r in rows:
        r["run"] = int(r["run"])
        for k in features:
            r[k] = float(r[k])
    return rows


def split(rows, blind_per_cond):
    by_cond = {}
    for r in rows:
        by_cond.setdefault(r["condition"], []).append(r)
    train, blind = [], []
    for cond in sorted(by_cond):
        group = sorted(by_cond[cond], key=lambda r: r["run"])
        if len(group) <= blind_per_cond:
            sys.exit("%s 只有 %d 组，不足以留出 %d 组盲测" % (
                cond, len(group), blind_per_cond))
        train.extend(group[:-blind_per_cond])
        blind.extend(group[-blind_per_cond:])
    return train, blind, sorted(by_cond)


def standardize(train, features):
    stats = []
    for k in features:
        vals = [r[k] for r in train]
        mean = sum(vals) / len(vals)
        var = sum((v - mean) ** 2 for v in vals) / len(vals)
        stats.append((mean, math.sqrt(var) or 1.0))
    return stats


def vector(row, stats, features):
    return [(row[k] - mean) / sd for k, (mean, sd) in zip(features, stats)]


def centers(train, stats, conds, features):
    out = {}
    for cond in conds:
        group = [r for r in train if r["condition"] == cond]
        vecs = [vector(r, stats, features) for r in group]
        out[cond] = [sum(v[i] for v in vecs) / len(vecs) for i in range(len(features))]
    return out


def predict(row, stats, center_map, features):
    v = vector(row, stats, features)
    return min(center_map, key=lambda c: sum(
        (v[i] - center_map[c][i]) ** 2 for i in range(len(v))))


def main():
    ap = argparse.ArgumentParser(description="分层盲测分类与混淆矩阵")
    ap.add_argument("--features", default="features.csv")
    ap.add_argument("--report", default="classification_report.md")
    ap.add_argument("--blind", type=int, default=3, help="每工况留出的盲测组数")
    ap.add_argument("--feature-set", default="basic",
                    help="basic=最初 6 项 / all=features.csv 全部数值列 / 或逗号分隔字段名")
    args = ap.parse_args()

    if not os.path.isfile(args.features):
        sys.exit("找不到特征文件：%s（先跑 fft_features.py）" % args.features)

    with open(args.features, "r", encoding="utf-8-sig", newline="") as fh:
        header = next(csv.reader(fh))
    features = pick_features(header, args.feature_set)
    rows = load(args.features, features)
    train, blind, conds = split(rows, args.blind)
    stats = standardize(train, features)
    center_map = centers(train, stats, conds, features)

    results = [(r, predict(r, stats, center_map, features)) for r in blind]
    correct = sum(1 for r, p in results if r["condition"] == p)
    acc = correct / len(results) if results else 0.0

    matrix = {t: {p: 0 for p in conds} for t in conds}
    for r, p in results:
        matrix[r["condition"]][p] += 1

    lines = []
    lines.append("# 盲测分类报告")
    lines.append("")
    lines.append("- 特征文件：`%s`" % args.features)
    lines.append("- 分层方式：每工况按 run 编号留最后 %d 组作盲测，其余训练" % args.blind)
    lines.append("- 训练集 %d 组 / 盲测集 %d 组" % (len(train), len(blind)))
    lines.append("- 判别方法：训练集体征标准化 → 类中心 → 最近欧氏距离")
    lines.append("- 特征维度：%d 项（%s）" % (len(features), ", ".join(features)))
    lines.append("- **总体准确率：%.1f%%（%d/%d）**" % (acc * 100, correct, len(results)))
    lines.append("")
    lines.append("## 混淆矩阵（行 = 真实工况，列 = 预测工况）")
    lines.append("")
    lines.append("| 真实 \\ 预测 | " + " | ".join(conds) + " | 该工况准确率 |")
    lines.append("|" + "---|" * (len(conds) + 2))
    for t in conds:
        total = sum(matrix[t].values())
        hit = matrix[t][t]
        cells = [str(matrix[t][p]) for p in conds]
        lines.append("| %s | %s | %.1f%% |" % (
            t, " | ".join(cells), (hit / total * 100) if total else 0.0))
    lines.append("")
    lines.append("## 误判明细")
    lines.append("")
    wrong = [(r, p) for r, p in results if r["condition"] != p]
    if wrong:
        lines.append("| 文件 | 真实 | 预测 | 主频Hz | 谱质心Hz | 高频比 |")
        lines.append("|---|---|---|---|---|---|")
        for r, p in wrong:
            lines.append("| %s | %s | %s | %s | %s | %s |" % (
                r["file"], r["condition"], p,
                r["dominant_hz"], r["centroid_hz"], r["high_ratio"]))
    else:
        lines.append("本次无误判。")
    lines.append("")
    lines.append("> 盲测样本在调参前预留，未参与训练。若后续改了特征或滤波，")
    lines.append("> 请在 `iterations/` 记录改动依据，并重新生成本表做对比。")
    lines.append("")
    lines.append("## 这份准确率能说明什么、不能说明什么")
    lines.append("")
    lines.append("- **能说明**：5 个工况的频谱形态确实不同，用 %d 项特征做类中心判别，"
                 % len(features))
    lines.append("  在未参与训练的切片上能分对 %d/%d。" % (correct, len(results)))
    lines.append("- **不能说明**：每个工况的 15 段切片来自**同一段 3 分钟连续录音**，")
    lines.append("  切片之间相隔仅十几秒，环境底噪、风扇温升、手机位置几乎不变。")
    lines.append("  因此盲测集与训练集并非完全独立，准确率偏乐观。")
    lines.append("- 真正严格的验证需要**重新录制**一批同工况样本（不同日期、不同摆放），")
    lines.append("  当前未做，列为项目局限，不宣称「换一台同类风扇也能认」。")

    with open(args.report, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    print("总体准确率 %.1f%% (%d/%d)" % (acc * 100, correct, len(results)))
    print("报告已写入 %s" % args.report)
    for t in conds:
        total = sum(matrix[t].values())
        print("  %s: %d/%d" % (t, matrix[t][t], total))


if __name__ == "__main__":
    main()
