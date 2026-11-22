#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
add_noise.py —— 在已录的干净切片上离线叠加高斯白噪声，构造抗噪测试集

用法：
  # 生成 snr20 / snr15 / snr10 / snr5 / snr0 五档子目录
  python src/add_noise.py --input process_logs/raw --output process_logs/noisy --snr 20,15,10,5,0

输出：
  <output>/snr20/cond01_run01.wav ...（文件名与原始切片一致，便于复用同一套分析脚本）
  <output>/noise_manifest.csv

原理：
  噪声按"目标信噪比"反推幅度：noise_rms = signal_rms / 10^(SNR/20)
  SNR 定义在整段信号上（含风扇持续噪声），故为宽带混合信噪比，非纯谱峰信噪比。

局限（须写入报告）：
  高斯白噪声与真实环境噪声（人声、键盘、交通）谱形不同，本测试只能验证
  "对宽带随机噪声的鲁棒性"，不能等同于现场抗噪能力。
"""

import argparse
import csv
import math
import os
import random
import struct
import sys
import wave


def read_pcm(path):
    with wave.open(path, "rb") as w:
        n, sr, ch, sw = w.getnframes(), w.getframerate(), w.getnchannels(), w.getsampwidth()
        raw = w.readframes(n)
    if sw != 2:
        raise RuntimeError("仅支持 16-bit PCM：%s" % path)
    data = list(struct.unpack("<%dh" % (len(raw) // 2), raw))
    if ch > 1:
        data = data[::ch]
    return data, sr


def write_pcm(path, samples, sr):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(struct.pack("<%dh" % len(samples), *samples))


def rms(samples):
    if not samples:
        return 0.0
    return math.sqrt(sum(x * x for x in samples) / len(samples))


def mix_noise(samples, snr_db, rng):
    """按目标 SNR 混入高斯白噪声，返回新样本（已限幅到 int16 范围）"""
    sig_rms = rms(samples)
    if sig_rms <= 0:
        return list(samples)
    noise_rms = sig_rms / (10.0 ** (snr_db / 20.0))
    out = []
    for x in samples:
        v = x + rng.gauss(0.0, noise_rms)
        out.append(-32768 if v < -32768 else (32767 if v > 32767 else int(v)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="干净切片目录（condXX_runYY.wav）")
    ap.add_argument("--output", required=True, help="输出根目录")
    ap.add_argument("--snr", default="20,15,10,5,0", help="目标信噪比(dB)，逗号分隔")
    ap.add_argument("--seed", type=int, default=20261122, help="随机种子（保证可复现）")
    args = ap.parse_args()

    snrs = [float(x) for x in args.snr.replace("，", ",").split(",") if x.strip()]
    files = sorted(f for f in os.listdir(args.input) if f.lower().endswith(".wav"))
    if not files:
        sys.exit("目录里没有 wav：%s" % args.input)

    print("干净切片 %d 个；生成 %d 档信噪比：%s"
          % (len(files), len(snrs), ", ".join("%g dB" % s for s in snrs)))

    rows = []
    for snr in snrs:
        outdir = os.path.join(args.output, "snr%02d" % int(round(snr)) if snr >= 0
                              else os.path.join(args.output, "snrneg%02d" % int(round(-snr))))
        os.makedirs(outdir, exist_ok=True)
        rng = random.Random(args.seed + int(round(snr * 10)))   # 每档独立可复现
        for name in files:
            samples, sr = read_pcm(os.path.join(args.input, name))
            mixed = mix_noise(samples, snr, rng)
            write_pcm(os.path.join(outdir, name), mixed, sr)
            rows.append([name, "%g" % snr, os.path.relpath(os.path.join(outdir, name), args.output),
                         "%.1f" % (20 * math.log10(max(rms(samples) / 32768.0, 1e-9))),
                         "%.1f" % (20 * math.log10(max(rms(mixed) / 32768.0, 1e-9)))])
        print("  ✓ snr%+03d dB -> %s（%d 个）" % (int(round(snr)), outdir, len(files)))

    man = os.path.join(args.output, "noise_manifest.csv")
    with open(man, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["文件", "目标SNR_dB", "输出相对路径", "原始RMS_dBFS", "混合后RMS_dBFS"])
        w.writerows(rows)
    print("\n完成：%d 个噪声文件，清单 -> %s" % (len(rows), man))


if __name__ == "__main__":
    main()
