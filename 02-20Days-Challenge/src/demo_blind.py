#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
demo_blind.py —— 录盲测视频用：逐条判决并打印，屏幕上一眼能看清

做的事和 classify.py 完全一样（同样的盲测划分、同样的标准化、同样的类中心），
只是把结果一条一条打印出来，方便手机横屏拍摄时观众看清"真实 vs 预测"。

用法（在 02-20Days-Challenge/ 目录下）：
    python src/demo_blind.py --features features.csv --each 1

  --each N   每个工况抽 N 段盲测样本（默认 1，即 5 条；N=2 则 10 条）
  --seed K   抽样随机种子（默认 2026，固定种子=可复现）
  --slow     每条之间停 1.2 秒，方便拍摄时看清
"""

import argparse
import csv
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from classify import (FEATURES_BASIC, META_COLS, pick_features, load,  # noqa: E402
                      split, standardize, centers, predict)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--features", default="features.csv")
    ap.add_argument("--feature-set", default="all")
    ap.add_argument("--blind", type=int, default=3)
    ap.add_argument("--each", type=int, default=1, help="每工况抽几段")
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--slow", action="store_true", help="每条之间停 1.2 秒")
    args = ap.parse_args()

    if not os.path.isfile(args.features):
        sys.exit("找不到特征文件：%s" % args.features)

    with open(args.features, "r", encoding="utf-8-sig", newline="") as fh:
        header = next(csv.reader(fh))
    features = pick_features(header, args.feature_set)
    rows = load(args.features, features)
    train, blind, conds = split(rows, args.blind)
    stats = standardize(train, features)
    cmap = centers(train, stats, conds, features)

    by_cond = {}
    for r in blind:
        by_cond.setdefault(r["condition"], []).append(r)
    random.seed(args.seed)
    picked = []
    for c in conds:
        group = sorted(by_cond.get(c, []), key=lambda r: r["file"])
        picked.extend(random.sample(group, min(args.each, len(group))))

    print("=" * 62)
    print(" 盲测演示：%d 段样本均未参与训练（每工况最后 %d 组留出）" % (len(picked), args.blind))
    print(" 特征 %d 项 · 判别：类中心最近邻 · 种子 %d" % (len(features), args.seed))
    print("=" * 62)
    hit = 0
    for i, r in enumerate(picked, 1):
        p = predict(r, stats, cmap, features)
        ok = p == r["condition"]
        hit += ok
        print("[%d/%d] %-18s 真实 %-8s → 预测 %-8s %s"
              % (i, len(picked), r["file"], r["condition"], p, "✔" if ok else "✘"))
        print("       主频 %.1f Hz  谱质心 %.0f Hz  高频比 %.3f"
              % (r["dominant_hz"], r["centroid_hz"], r["high_ratio"]))
        if args.slow:
            time.sleep(1.2)
    print("-" * 62)
    print("本次抽中 %d 段，判对 %d 段，准确率 %.1f%%" % (len(picked), hit, hit * 100.0 / len(picked)))
    print("（注：这是抽样演示，正式指标见 classification_report.md 的全部 15 段盲测）")


if __name__ == "__main__":
    main()
