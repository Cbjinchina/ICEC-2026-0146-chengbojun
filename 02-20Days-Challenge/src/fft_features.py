#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""项目三 · 声振信号 FFT 特征提取

零第三方依赖，只用 Python 标准库。断网也能复现全部结果。

用法（在 02-20Days-Challenge/ 目录下）：
    python src/fft_features.py --input process_logs/raw --output features.csv

输入：cond01_run01.wav ... cond05_run15.wav（16-bit PCM WAV，单/双声道均可）
输出：features.csv，一行一个音频文件，字段见 CSV_HEADER
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import re
import struct
import sys
import wave

FRAME_SIZE = 2048          # FFT 帧长，必须是 2 的幂
MAX_FRAMES = 8             # 每个文件取中间最多 8 帧做平均，避开开头/结尾的开关噪声
LOW_HZ = 500.0
HIGH_HZ = 2000.0
NAME_RE = re.compile(r"cond(\d+)[_-]run(\d+)", re.IGNORECASE)

# 八度频带（Hz），用于计算增益无关的频带能量占比
BANDS = [
    ("b_63_125", 63.0, 125.0), ("b_125_250", 125.0, 250.0),
    ("b_250_500", 250.0, 500.0), ("b_500_1k", 500.0, 1000.0),
    ("b_1k_2k", 1000.0, 2000.0), ("b_2k_4k", 2000.0, 4000.0),
    ("b_4k_8k", 4000.0, 8000.0),
]

CSV_HEADER = [
    "file", "condition", "run", "sample_rate", "frames",
    "dominant_hz", "centroid_hz", "rms", "zcr", "low_ratio", "high_ratio",
    "flatness", "tonality", "crest",
    "mod_peak_hz", "mod_depth", "mod_at_rot",
] + [b[0] for b in BANDS]


def read_wav_mono(path):
    """读取 WAV，返回 (float 采样列表, 采样率)。双声道取均值。"""
    with wave.open(path, "rb") as w:
        nch = w.getnchannels()
        sw = w.getsampwidth()
        sr = w.getframerate()
        raw = w.readframes(w.getnframes())
    if sw != 2:
        raise ValueError("仅支持 16-bit PCM WAV，请在录音 App 里导出为 16-bit PCM")
    if nch not in (1, 2):
        raise ValueError("仅支持单声道或双声道")
    count = len(raw) // 2
    vals = struct.unpack("<%dh" % count, raw[: count * 2])
    if nch == 2:
        return [(vals[i] + vals[i + 1]) * 0.5 for i in range(0, count - 1, 2)], sr
    return list(vals), sr


def fft_inplace(re, im):
    """迭代式 Cooley-Tukey radix-2 FFT，原地变换。"""
    n = len(re)
    if n == 0 or n & (n - 1):
        raise ValueError("FFT 长度必须是 2 的幂")
    j = 0
    for i in range(1, n):
        bit = n >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j ^= bit
        if i < j:
            re[i], re[j] = re[j], re[i]
            im[i], im[j] = im[j], im[i]
    length = 2
    while length <= n:
        theta = -2.0 * math.pi / length
        step_re, step_im = math.cos(theta), math.sin(theta)
        half = length // 2
        for start in range(0, n, length):
            w_re, w_im = 1.0, 0.0
            for k in range(half):
                a = start + k
                b = a + half
                v_re = re[b] * w_re - im[b] * w_im
                v_im = re[b] * w_im + im[b] * w_re
                re[b] = re[a] - v_re
                im[b] = im[a] - v_im
                re[a] = re[a] + v_re
                im[a] = im[a] + v_im
                w_re, w_im = (
                    w_re * step_re - w_im * step_im,
                    w_re * step_im + w_im * step_re,
                )
        length <<= 1


def frame_features(frame, sr):
    """从一帧信号提取时域 + 频域特征。"""
    n = len(frame)
    mean = sum(frame) / n
    x = [v - mean for v in frame]                 # 去直流

    rms = math.sqrt(sum(v * v for v in x) / n) / 32768.0
    zcr = sum(1 for i in range(1, n) if (x[i - 1] < 0) != (x[i] < 0)) / (n - 1)

    window = [0.5 - 0.5 * math.cos(2.0 * math.pi * i / (n - 1)) for i in range(n)]
    re = [x[i] * window[i] for i in range(n)]
    im = [0.0] * n
    fft_inplace(re, im)

    mags = [math.hypot(re[i], im[i]) for i in range(n // 2)]
    mags[0] = 0.0                                 # 丢掉 DC
    total = sum(mags)
    if total <= 0:
        d = dict(rms=rms, zcr=zcr, dominant_hz=0.0, centroid_hz=0.0,
                 low_ratio=0.0, high_ratio=0.0, flatness=0.0, tonality=0.0,
                 crest=(max(abs(v) for v in x) / (rms * 32768.0)) if rms > 0 else 0.0)
        for name, _, _ in BANDS:
            d[name] = 0.0
        return d

    bin_hz = sr / n
    peak = max(range(1, len(mags)), key=lambda i: mags[i])
    centroid = sum(i * bin_hz * mags[i] for i in range(1, len(mags))) / total
    low = sum(mags[i] for i in range(1, len(mags)) if i * bin_hz < LOW_HZ)
    high = sum(mags[i] for i in range(1, len(mags)) if i * bin_hz > HIGH_HZ)

    # 谱平坦度：几何均值/算术均值（接近 1 = 噪声状，接近 0 = 音调状）
    eps = 1e-12
    pos = [m for m in mags[1:] if m > 0]
    if pos:
        log_sum = sum(math.log(m + eps) for m in pos)
        flat = math.exp(log_sum / len(pos)) / (sum(pos) / len(pos) + eps)
    else:
        flat = 0.0
    # 谱峰显著性：主峰 / 全谱中位数
    med = sorted(mags[1:])[len(mags[1:]) // 2] if len(mags) > 2 else 1.0
    tonality = mags[peak] / (med + eps)

    out = dict(
        rms=rms,
        zcr=zcr,
        dominant_hz=peak * bin_hz,
        centroid_hz=centroid,
        low_ratio=low / total,
        high_ratio=high / total,
        flatness=flat,
        tonality=tonality,
        crest=(max(abs(v) for v in x) / (rms * 32768.0)) if rms > 0 else 0.0,
    )
    # 各八度频带能量占比（增益无关：不同录音的 AGC 差异被约掉）
    for name, lo, hi in BANDS:
        e = sum(mags[i] for i in range(1, len(mags)) if lo <= i * bin_hz < hi)
        out[name] = e / total
    return out


def modulation_features(samples, sr, base_hz):
    """包络调制分析 —— 转子失衡会让振动幅值按转频周期起伏。

    返回 (调制主频 Hz, 调制深度, 在转频处的相对调制强度)。
    base_hz 为谱主峰频率；三叶风扇转频 ≈ base_hz / 3。
    """
    n = len(samples)
    if n < sr // 10:                       # 至少 0.1 s 才有意义
        return 0.0, 0.0, 0.0
    win = max(int(sr / 200.0), 2)          # 约 200 Hz 低通的滑动平均
    env = []
    acc = 0.0
    for i, x in enumerate(samples):
        acc += abs(x)
        if (i + 1) % win == 0:
            env.append(acc / win)
            acc = 0.0
    if len(env) < 64:
        return 0.0, 0.0, 0.0
    mean_env = sum(env) / len(env)
    if mean_env <= 0:
        return 0.0, 0.0, 0.0
    x = [v - mean_env for v in env]

    size = 1
    while size < len(x):
        size *= 2
    x = x + [0.0] * (size - len(x))
    w = [0.5 - 0.5 * math.cos(2.0 * math.pi * i / (size - 1)) for i in range(size)]
    re = [x[i] * w[i] for i in range(size)]
    im = [0.0] * size
    fft_inplace(re, im)
    mags = [math.hypot(re[i], im[i]) for i in range(size // 2)]
    env_sr = sr / float(win)
    bin_hz = env_sr / size
    lo = max(int(3.0 / bin_hz), 1)
    hi = min(int(80.0 / bin_hz) + 1, len(mags) - 1)
    if hi <= lo:
        return 0.0, 0.0, 0.0
    band = mags[lo:hi]
    pk = max(range(len(band)), key=lambda i: band[i]) + lo
    mod_peak = pk * bin_hz
    depth = math.sqrt(sum(v * v for v in band) * 2.0) / (size * mean_env)

    rot = base_hz / 3.0                     # 三叶 → 转频
    rel = 0.0
    if rot > 1.0:
        k = int(round(rot / bin_hz))
        lo2, hi2 = max(k - 1, lo), min(k + 2, hi)
        if hi2 > lo2:
            peak_mag = max(mags[lo2:hi2])
            med = sorted(band)[len(band) // 2]
            rel = peak_mag / (med + 1e-12)
    return mod_peak, depth, rel


def extract(path):
    samples, sr = read_wav_mono(path)
    if len(samples) < FRAME_SIZE:
        raise ValueError("录音太短，至少需要 %d 个采样点" % FRAME_SIZE)

    need = FRAME_SIZE * MAX_FRAMES
    if len(samples) >= need:
        start = (len(samples) - need) // 2
        block = samples[start:start + need]
    else:
        usable = (len(samples) // FRAME_SIZE) * FRAME_SIZE
        block = samples[:usable]

    frames = [block[i:i + FRAME_SIZE]
              for i in range(0, len(block) - FRAME_SIZE + 1, FRAME_SIZE)]
    feats = [frame_features(f, sr) for f in frames]
    merged = {k: sum(f[k] for f in feats) / len(feats) for k in feats[0]}
    # 调制分析用中间 10 s（整段太长、block 又偏短）
    if len(samples) > sr * 10:
        c = len(samples) // 2
        mod_src = samples[c - sr * 5: c + sr * 5]
    else:
        mod_src = samples
    mp, md, mr = modulation_features(mod_src, sr, merged["dominant_hz"])
    merged["mod_peak_hz"] = mp
    merged["mod_depth"] = md
    merged["mod_at_rot"] = mr
    merged["sample_rate"] = sr
    merged["frames"] = len(frames)
    return merged


def main():
    ap = argparse.ArgumentParser(description="从 WAV 提取 FFT 特征")
    ap.add_argument("--input", default="process_logs/raw", help="原始 WAV 目录")
    ap.add_argument("--output", default="features.csv", help="输出 CSV 路径")
    args = ap.parse_args()

    if not os.path.isdir(args.input):
        sys.exit("找不到输入目录：%s" % args.input)

    files = sorted(f for f in os.listdir(args.input) if f.lower().endswith(".wav"))
    if not files:
        sys.exit("目录里没有 .wav 文件：%s" % args.input)

    rows, errors = [], []
    for name in files:
        m = NAME_RE.search(name)
        if not m:
            errors.append((name, "文件名不符合 condXX_runYY.wav 规则，已跳过"))
            continue
        try:
            f = extract(os.path.join(args.input, name))
        except Exception as exc:
            errors.append((name, str(exc)))
            continue
        rows.append({
            "file": name,
            "condition": "cond%02d" % int(m.group(1)),
            "run": int(m.group(2)),
            "sample_rate": f["sample_rate"],
            "frames": f["frames"],
            "dominant_hz": round(f["dominant_hz"], 2),
            "centroid_hz": round(f["centroid_hz"], 2),
            "rms": round(f["rms"], 6),
            "zcr": round(f["zcr"], 5),
            "low_ratio": round(f["low_ratio"], 5),
            "high_ratio": round(f["high_ratio"], 5),
            "flatness": round(f["flatness"], 5),
            "tonality": round(f["tonality"], 3),
            "crest": round(f["crest"], 3),
            "mod_peak_hz": round(f["mod_peak_hz"], 2),
            "mod_depth": round(f["mod_depth"], 5),
            "mod_at_rot": round(f["mod_at_rot"], 3),
            **{name: round(f[name], 5) for name, _, _ in BANDS},
        })

    if not rows:
        sys.exit("没有成功提取任何文件，请检查 WAV 格式与命名。")

    rows.sort(key=lambda r: (r["condition"], r["run"]))
    with open(args.output, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_HEADER)
        writer.writeheader()
        writer.writerows(rows)

    print("已提取 %d 个文件 -> %s" % (len(rows), args.output))
    print("\n各工况特征均值（一眼看区分度）：")
    print("%-8s %4s %12s %12s %10s" % ("工况", "组数", "主频Hz", "谱质心Hz", "高频比"))
    by_cond = {}
    for r in rows:
        by_cond.setdefault(r["condition"], []).append(r)
    for cond in sorted(by_cond):
        g = by_cond[cond]
        avg = lambda k: sum(float(r[k]) for r in g) / len(g)
        print("%-8s %4d %12.1f %12.1f %10.4f" % (
            cond, len(g), avg("dominant_hz"), avg("centroid_hz"), avg("high_ratio")))

    if errors:
        print("\n跳过的文件（请写进采样说明，别静默丢弃）：")
        for name, why in errors:
            print("  - %s: %s" % (name, why))


if __name__ == "__main__":
    main()
