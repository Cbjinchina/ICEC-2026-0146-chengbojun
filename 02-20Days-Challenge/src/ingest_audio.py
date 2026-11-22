#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ingest_audio.py —— 把手机录音（M4A/MP3/WAV）批量转码并切片成分析用 WAV

两种模式：
  A. 精简模式（默认）：每个工况只录 1 条长音频，自动切成 15 段
       python src/ingest_audio.py --input "D:/icec/raw_audio" --output process_logs/raw
  B. 多次采模式：每个工况录 5 条，每条切 3 段
       python src/ingest_audio.py ... --files-per-cond 5 --chunks 3

命名规则：condXX_runYY.wav（XX=工况号，YY=1..15）
依赖：ffmpeg（自动搜索本机已装版本，可用 --ffmpeg 指定）
"""

import argparse
import csv
import math
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import wave

EDGE_TRIM = 1.0     # 首尾各裁掉 1 s，避开按键瞬态
# 工况序号 = 录音时间顺序。c03 改用 2 档后为保证单变量对照，补录了 2 档正常基线，
# 故由 5 类变为 6 类（三个档位的正常基线 + 三种故障）。
COND_NAMES = {
    1: "正常-1档",
    2: "正常-4档",
    3: "扇叶失衡",
    4: "正常-2档",
    5: "进气受阻",
}
AUDIO_EXT = (".m4a", ".mp3", ".wav", ".aac", ".amr", ".ogg", ".flac", ".opus")

FFMPEG_CANDIDATES = [
    r"C:\Program Files (x86)\ACLOS\Cross\recorder-release\ffmpeg.exe",
    r"C:\Program Files\ACLOS\Cross\recorder-release\ffmpeg.exe",
    r"C:\ffmpeg\bin\ffmpeg.exe",
    r"D:\ffmpeg\bin\ffmpeg.exe",
    r"D:\Apps\ffmpeg\bin\ffmpeg.exe",
]


def find_ffmpeg(explicit=None):
    if explicit:
        if os.path.isfile(explicit):
            return explicit
        sys.exit("指定的 ffmpeg 不存在：%s" % explicit)
    for p in FFMPEG_CANDIDATES:
        if os.path.isfile(p):
            return p
    found = shutil.which("ffmpeg")
    if found:
        return found
    sys.exit("未找到 ffmpeg。请用 --ffmpeg 指定路径")


def to_wav(ffmpeg, src, dst):
    """任意格式 -> 16-bit 单声道 WAV（保持原始采样率，不重采样）"""
    cmd = [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-i", src, "-ac", "1", "-c:a", "pcm_s16le", dst,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not os.path.isfile(dst):
        raise RuntimeError("转码失败：%s\n%s" % (os.path.basename(src), r.stderr.strip()[:400]))


def read_pcm(path):
    with wave.open(path, "rb") as w:
        n, sr, ch, sw = w.getnframes(), w.getframerate(), w.getnchannels(), w.getsampwidth()
        raw = w.readframes(n)
    if sw != 2:
        raise RuntimeError("非 16-bit：%s" % path)
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


def seg_stats(samples):
    if not samples:
        return 0.0, 0.0, 0
    n = len(samples)
    rms = math.sqrt(sum(x * x for x in samples) / n)
    peak = max(abs(x) for x in samples)
    clip = sum(1 for x in samples if abs(x) >= 32700)
    return rms, peak, clip


def plan_starts(lo, span, seg_len, chunks):
    """在 [lo, lo+span] 内均匀排布 chunks 个长度为 seg_len 的片段起点"""
    if seg_len > span:
        seg_len = span // max(chunks, 1)
    max_start = span - seg_len
    if chunks <= 1 or max_start <= 0:
        return [lo], seg_len
    return [lo + int(max_start * k / (chunks - 1)) for k in range(chunks)], seg_len


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="原始录音目录")
    ap.add_argument("--output", required=True, help="切片 WAV 输出目录")
    ap.add_argument("--manifest", default=None, help="清单 CSV（默认 <output>/manifest.csv）")
    ap.add_argument("--files-per-cond", type=int, default=1, help="每个工况几个原始录音（默认 1）")
    ap.add_argument("--chunks", type=int, default=15, help="每个录音切几段（默认 15）")
    ap.add_argument("--segment-sec", type=float, default=10.0,
                    help="每段时长秒；0 表示均分（默认 10）")
    ap.add_argument("--trim", type=float, default=EDGE_TRIM, help="首尾各裁掉秒数（默认 1）")
    ap.add_argument("--ffmpeg", default=None)
    args = ap.parse_args()

    ffmpeg = find_ffmpeg(args.ffmpeg)
    src_dir = args.input
    if not os.path.isdir(src_dir):
        sys.exit("目录不存在：%s" % src_dir)

    files = [
        os.path.join(src_dir, f)
        for f in os.listdir(src_dir)
        if f.lower().endswith(AUDIO_EXT) and not f.startswith(".")
    ]
    files.sort(key=lambda p: os.path.getmtime(p))
    if not files:
        sys.exit("目录里没有音频文件：%s" % src_dir)

    expect = args.files_per_cond * len(COND_NAMES)
    print("发现 %d 个录音（预期 %d 个 ＝ %d 工况 × %d）" % (len(files), expect, len(COND_NAMES), args.files_per_cond))
    if len(files) != expect:
        print("⚠ 数量与预期不符！工况归属可能错位，请核对。")

    os.makedirs(args.output, exist_ok=True)
    manifest_path = args.manifest or os.path.join(args.output, "manifest.csv")
    rows = []
    total = 0

    tmpdir = tempfile.mkdtemp(prefix="ingest_")
    try:
        for idx, src in enumerate(files):
            cond = idx // args.files_per_cond + 1
            if cond > len(COND_NAMES):
                print("跳过（超出 %d 工况）：%s" % (len(COND_NAMES), os.path.basename(src)))
                continue
            run_base = (idx % args.files_per_cond) * args.chunks

            tmp_wav = os.path.join(tmpdir, "conv_%02d.wav" % idx)
            try:
                to_wav(ffmpeg, src, tmp_wav)
                samples, sr = read_pcm(tmp_wav)
            except Exception as e:
                print("✗ %s -> %s" % (os.path.basename(src), e))
                rows.append([idx + 1, cond, COND_NAMES[cond], os.path.basename(src),
                             "", "", "", "", "", "", "转码失败"])
                continue

            dur = len(samples) / float(sr)
            lo = int(args.trim * sr)
            hi = int((dur - args.trim) * sr)
            if hi - lo < sr:          # 太短，退化为整段
                lo, hi = 0, len(samples)
            span = hi - lo
            seg_len = int(args.segment_sec * sr) if args.segment_sec else span // args.chunks
            if seg_len <= 0:
                seg_len = span // args.chunks
            starts, seg_len = plan_starts(lo, span, seg_len, args.chunks)

            print("[%d] %-30s %6.1fs @%dHz -> 工况%d %s，切 %d 段 × %.1fs"
                  % (idx + 1, os.path.basename(src)[:30], dur, sr, cond,
                     COND_NAMES[cond], len(starts), seg_len / float(sr)))

            for k, st in enumerate(starts):
                seg = samples[st:st + seg_len]
                if len(seg) < sr // 2:
                    continue
                run = run_base + k + 1
                name = "cond%02d_run%02d.wav" % (cond, run)
                write_pcm(os.path.join(args.output, name), seg, sr)
                rms, peak, clip = seg_stats(seg)
                rows.append([
                    idx + 1, cond, COND_NAMES[cond], os.path.basename(src),
                    "%.2f" % dur, name, "%.2f" % (len(seg) / float(sr)),
                    "%.1f" % (20 * math.log10(max(rms / 32768.0, 1e-9))),
                    "%.1f" % (20 * math.log10(max(peak / 32768.0, 1e-9))), clip, "",
                ])
                total += 1
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    with open(manifest_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["源序号", "工况", "工况名", "源文件", "源时长s", "切片文件",
                    "切片时长s", "RMS_dBFS", "峰值_dBFS", "削波点数", "备注"])
        w.writerows(rows)

    print("\n完成：生成 %d 段，清单 -> %s" % (total, manifest_path))

    clip_rows = [r for r in rows if r[5] and r[9] and int(r[9]) > 0]
    if clip_rows:
        print("⚠ %d 段削波（峰值触顶），建议降低增益重录：" % len(clip_rows))
        for r in clip_rows[:6]:
            print("   %s  削波 %s 点，峰值 %s dBFS" % (r[5], r[9], r[8]))
    weak = [r for r in rows if r[5] and r[7] and float(r[7]) < -55]
    if weak:
        print("⚠ %d 段电平过低（RMS < -55 dBFS）：" % len(weak))
        for r in weak[:6]:
            print("   %s  RMS %s dBFS" % (r[5], r[7]))


if __name__ == "__main__":
    main()
