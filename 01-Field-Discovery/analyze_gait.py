#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
课题 08：多姿态步态加速度特征提取与阈值判别
纯标准库实现（无需 numpy / matplotlib），直接读取 Phyphox 导出的 Raw Data.csv。

用法：
    python analyze_gait.py                    # 分析同目录 raw_data/task08 下四段数据
    python analyze_gait.py --dir <目录>        # 指定数据目录
    python analyze_gait.py --trim 2           # 头尾各裁掉 2 秒（默认 2）

输出：
    features.csv          四段数据的特征表
    task08_waveform.svg   三轴波形对比图（可直接在 GitHub 里显示）
"""

import argparse
import csv
import math
import os

SEGMENTS = [
    ("01_still", "静止", "#495057"),
    ("02_walk", "慢走", "#1c7ed6"),
    ("03_stairs", "上下楼梯", "#f08c00"),
    ("04_run", "快跑", "#d6336c"),
]

AXES = [("x", 1, "#d9480f"), ("y", 2, "#1c7ed6"), ("z", 3, "#2f9e44")]


def read_phyphox(path):
    """读取 Phyphox 的 Raw Data.csv，返回 [(t, ax, ay, az), ...]"""
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        r = csv.reader(f)
        next(r)  # 跳过表头
        for rec in r:
            if len(rec) >= 4:
                try:
                    rows.append((float(rec[0]), float(rec[1]),
                                 float(rec[2]), float(rec[3])))
                except ValueError:
                    continue
    return rows


def mean(v):
    return sum(v) / len(v)


def std(v):
    m = mean(v)
    return math.sqrt(sum((a - m) ** 2 for a in v) / len(v))


def smooth(v, win):
    """滑动平均，win 为窗口点数（奇数）"""
    if win < 3:
        return list(v)
    h = win // 2
    n = len(v)
    out = []
    for i in range(n):
        lo = max(0, i - h)
        hi = min(n, i + h + 1)
        out.append(sum(v[lo:hi]) / (hi - lo))
    return out


def step_rate(mag, fs):
    """
    估计步频（步/秒）：对 |a| 去趋势后做带滞回的峰值计数。
    判定条件：相邻峰间隔 >= 0.25 s，峰值突出量 > 0.3 倍标准差。
    """
    if not mag:
        return 0.0
    sm = smooth(mag, max(3, int(fs * 0.04)))          # 40ms 平滑
    det = [a - b for a, b in zip(sm, smooth(sm, max(5, int(fs * 0.4))))]  # 去慢变趋势
    sd = std(det)
    if sd < 0.15:
        return 0.0
    hi_th = 0.5 * sd
    lo_th = -0.5 * sd
    peaks, state, last = 0, "low", -10.0
    for i, v in enumerate(det):
        t = i / fs
        if state == "low" and v > hi_th:
            if t - last >= 0.25:
                peaks += 1
                last = t
            state = "high"
        elif state == "high" and v < lo_th:
            state = "low"
    return peaks / (len(det) / fs)


def analyze(rowset, trim, fs):
    """对一段数据做裁剪并计算全部特征"""
    t0, t1 = rowset[0][0], rowset[-1][0]
    lo, hi = t0 + trim, t1 - trim
    seg = [r for r in rowset if lo <= r[0] <= hi]
    if len(seg) < 10:
        seg = rowset
    mag = [math.sqrt(r[1] ** 2 + r[2] ** 2 + r[3] ** 2) for r in seg]
    feat = {
        "n": len(seg),
        "duration": seg[-1][0] - seg[0][0],
        "mag_mean": mean(mag),
        "mag_std": std(mag),
        "mag_max": max(mag),
        "mag_pp": max(mag) - min(mag),
        "rate": step_rate(mag, fs),
    }
    for name, idx, _ in AXES:
        v = [r[idx] for r in seg]
        feat["%s_mean" % name] = mean(v)
        feat["%s_std" % name] = std(v)
        feat["%s_pp" % name] = max(v) - min(v)
    return feat, seg


def classify(feat):
    """
    阈值判别规则（由四段实测数据标定，见 task08_report.md）
    主判据：|a| 的波动程度 std_|a|
    """
    s, r = feat["mag_std"], feat["rate"]
    if s < 1.5:
        return "静止"
    if s < 3.5:
        return "慢走"
    if s < 7.0:
        return "上下楼梯"
    return "快跑"


def svg_panel(title, seg, fs, w, h, pad_l, idx_y, vmax=None):
    """生成一个状态的三轴波形面板（vmax 为统一纵轴半幅，便于跨面板比较）"""
    t0, t1 = seg[0][0], seg[-1][0]
    span = max(t1 - t0, 1e-6)
    vals = [[r[i] for r in seg] for i in (1, 2, 3)]
    if vmax is None:
        vmax = max(max(abs(x) for x in v) for v in vals)
        vmax = max(vmax, 11.0)
    vmin = -vmax
    plot_w, plot_h = w - pad_l - 20, h - 46

    def px(t):
        return pad_l + (t - t0) / span * plot_w

    def py(v):
        return 32 + (vmax - v) / (vmax - vmin) * plot_h

    out = ['<g>']
    out.append('<text x="8" y="20" font-size="15" font-weight="600" fill="#212529">%s</text>' % title)
    out.append('<rect x="%d" y="32" width="%d" height="%d" fill="#fbfbfc" stroke="#e9ecef"/>'
               % (pad_l, plot_w, plot_h))
    # 网格线与纵轴刻度
    for gv in (-20, -10, 0, 10, 20):
        if vmin <= gv <= vmax:
            y = py(gv)
            out.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="#e9ecef" stroke-dasharray="3 3"/>'
                       % (pad_l, y, pad_l + plot_w, y))
            out.append('<text x="%d" y="%.1f" font-size="10" fill="#868e96" text-anchor="end">%d</text>'
                       % (pad_l - 6, y + 3, gv))
    # 三轴折线（等间隔抽稀到约 900 点）
    step = max(1, len(seg) // 900)
    for (name, _, color), v in zip(AXES, vals):
        pts = []
        for i in range(0, len(seg), step):
            pts.append("%.1f,%.1f" % (px(seg[i][0]), py(v[i])))
        out.append('<polyline fill="none" stroke="%s" stroke-width="1.1" '
                   'stroke-linejoin="round" points="%s"/>' % (color, " ".join(pts)))
    # 横轴刻度
    for k in range(0, 5):
        tt = t0 + span * k / 4
        out.append('<text x="%.1f" y="%d" font-size="10" fill="#868e96" text-anchor="middle">%.0fs</text>'
                   % (px(tt), 32 + plot_h + 14, tt - t0))
    # 图例（放在右上角，避免与标题重叠）
    lx = w - 170
    for name, _, color in AXES:
        out.append('<line x1="%d" y1="20" x2="%d" y2="20" stroke="%s" stroke-width="2.2"/>'
                   % (lx, lx + 16, color))
        out.append('<text x="%d" y="24" font-size="11" fill="#495057">%s</text>' % (lx + 20, name))
        lx += 52
    out.append('</g>')
    return "\n".join(out)


def make_svg(results, path):
    W, H = 1180, 210
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
             'viewBox="0 0 %d %d" font-family="-apple-system,Segoe UI,Microsoft YaHei,sans-serif">'
             % (W, H * len(results) + 54, W, H * len(results) + 54),
             '<rect width="100%" height="100%" fill="#ffffff"/>',
             '<text x="8" y="26" font-size="17" font-weight="700" fill="#212529">'
             '课题 08 · 四姿态三轴加速度波形对比（含重力，采样率 400 Hz）</text>',
             '<text x="8" y="46" font-size="11" fill="#868e96">'
             '纵轴单位 m/s²；静止时三轴基本水平（|a|≈9.8），跑动时出现大振幅周期性冲击</text>']
    # 统一纵轴半幅，保证四个面板量程一致、可直接比高低
    gmax = 11.0
    for _, seg, _, _ in results:
        for i in (1, 2, 3):
            gmax = max(gmax, max(abs(r[i]) for r in seg))
    gmax = math.ceil(gmax * 1.06 / 5.0) * 5.0   # 留 6% 余量，避免峰值贴边
    for i, (title, seg, fs, feat) in enumerate(results):
        g = svg_panel(title, seg, fs, W, H, 46, i, vmax=gmax)
        parts.append('<g transform="translate(0,%d)">%s</g>' % (54 + i * H, g))
    parts.append('</svg>')
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                  "raw_data", "task08"))
    ap.add_argument("--trim", type=float, default=2.0)
    args = ap.parse_args()

    results, table = [], []
    print("=" * 78)
    print("课题 08 · 多姿态步态加速度特征")
    print("=" * 78)
    for dirname, label, color in SEGMENTS:
        path = os.path.join(args.dir, dirname, "Raw Data.csv")
        if not os.path.isfile(path):
            print("[!] 缺少数据：%s（跳过）" % path)
            continue
        rows = read_phyphox(path)
        dur = rows[-1][0] - rows[0][0]
        fs = (len(rows) - 1) / dur if dur > 0 else 400.0
        feat, seg = analyze(rows, args.trim, fs)
        feat["label"] = label
        feat["seg"] = dirname
        pred = classify(feat)
        feat["pred"] = pred
        results.append(("%s（%s）" % (label, dirname), seg, fs, feat))
        table.append(feat)
        print("\n[%s] %s" % (label, dirname))
        print("  原始 %d 点 / %.1f s，采样率 %.0f Hz；裁剪头尾各 %.0f s 后剩 %d 点"
              % (len(rows), dur, fs, args.trim, feat["n"]))
        print("  |a| 均值 %.2f，波动(std) %.2f，峰值 %.1f，步频 %.2f 步/秒"
              % (feat["mag_mean"], feat["mag_std"], feat["mag_max"], feat["rate"]))
        print("  三轴 std：x %.2f  y %.2f  z %.2f"
              % (feat["x_std"], feat["y_std"], feat["z_std"]))
        print("  判别结果：%s" % pred)

    # 特征表
    out_csv = os.path.join(args.dir, "..", "..", "features.csv")
    cols = ["seg", "label", "n", "duration", "mag_mean", "mag_std", "mag_max", "mag_pp", "rate",
            "x_mean", "x_std", "y_mean", "y_std", "z_mean", "z_std", "pred"]
    with open(out_csv, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in table:
            w.writerow(["%s" % (round(r[c], 4) if isinstance(r[c], float) else r[c]) for c in cols])
    print("\n特征表已写出：%s" % os.path.normpath(out_csv))

    # 波形图
    if results:
        svg_path = os.path.join(args.dir, "..", "..", "task08_waveform.svg")
        make_svg(results, svg_path)
        print("波形图已写出：%s" % os.path.normpath(svg_path))

    # 判别汇总
    ok = sum(1 for r in table if r["pred"] == r["label"])
    print("\n阈值判别：%d/%d 段与人工标注一致" % (ok, len(table)))


if __name__ == "__main__":
    main()
