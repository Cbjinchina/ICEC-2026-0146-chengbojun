#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
patch_condition.py —— 只替换某一个工况的切片，不动其他工况

用途：某个工况（比如 c03 扇叶失衡）重录后，不必把 5 条录音全部重跑一遍，
      只把新的那条切片覆盖到 process_logs/raw/ 里对应的 condNN_run*.wav。

用法：
  python src/patch_condition.py --input "2026年11月22日 17点30分.m4a" --cond 3
  可选：--runs 15（切几段，默认与既有管线一致）
        --output process_logs/raw
        --dry-run 只打印不写盘

切片规则与 ingest_audio.py 完全一致：首尾各裁 1 s，剩余时长均分 --runs 段。
旧片段先备份（.bak）再覆盖，出问题可回滚。
"""

import argparse
import glob
import os
import re
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ingest_audio import (COND_NAMES, find_ffmpeg, to_wav, read_pcm,  # noqa: E402
                          write_pcm, seg_stats, plan_starts, EDGE_TRIM)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="新的那一条录音文件")
    ap.add_argument("--cond", type=int, required=True, help="工况序号（见 COND_NAMES）")
    ap.add_argument("--output", default="process_logs/raw", help="切片目录")
    ap.add_argument("--runs", type=int, default=15, help="切几段（默认 15）")
    ap.add_argument("--trim", type=float, default=EDGE_TRIM, help="首尾各裁秒数")
    ap.add_argument("--ffmpeg", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.cond not in COND_NAMES:
        sys.exit("工况号必须是 %s 之一" % sorted(COND_NAMES))
    if not os.path.isfile(args.input):
        sys.exit("文件不存在：%s" % args.input)

    ffmpeg = find_ffmpeg(args.ffmpeg)
    tmpdir = tempfile.mkdtemp(prefix="patch_")
    try:
        wav = os.path.join(tmpdir, "conv.wav")
        to_wav(ffmpeg, args.input, wav)
        samples, sr = read_pcm(wav)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    dur = len(samples) / float(sr)
    lo = int(args.trim * sr)
    hi = int((dur - args.trim) * sr)
    if hi - lo < sr:
        lo, hi = 0, len(samples)
    span = hi - lo
    starts, seg_len = plan_starts(lo, span, span // max(args.runs, 1), args.runs)

    print("源：%s" % os.path.basename(args.input))
    print("　%.1fs @%dHz → 有效 %.1fs，切 %d 段 × %.1fs"
          % (dur, sr, span / float(sr), len(starts), seg_len / float(sr)))
    print("　覆盖工况 %d「%s」" % (args.cond, COND_NAMES[args.cond]))

    os.makedirs(args.output, exist_ok=True)
    old = sorted(glob.glob(os.path.join(args.output, "cond%02d_run*.wav" % args.cond)))
    print("　旧片段 %d 个" % len(old))

    written, clips, weak = 0, [], []
    for k, st in enumerate(starts):
        seg = samples[st:st + seg_len]
        if len(seg) < sr // 2:
            continue
        name = "cond%02d_run%02d.wav" % (args.cond, k + 1)
        dst = os.path.join(args.output, name)
        if args.dry_run:
            print("　[dry] %s" % name)
            continue
        if old and re.match(r"cond%02d_run" % args.cond, os.path.basename(dst)) and os.path.isfile(dst):
            shutil.copy2(dst, dst + ".bak")
        write_pcm(dst, seg, sr)
        written += 1
        rms, peak, clip = seg_stats(seg)
        db_rms = 20 * __import__("math").log10(max(rms / 32768.0, 1e-9))
        if clip > 0:
            clips.append((name, clip))
        if db_rms < -55:
            weak.append((name, db_rms))
        print("　✓ %s  %.1f dBFS RMS  峰值 %.1f dBFS" % (name, db_rms,
              20 * __import__("math").log10(max(peak / 32768.0, 1e-9))))

    if args.dry_run:
        return
    extra = sorted(glob.glob(os.path.join(args.output, "cond%02d_run*.wav" % args.cond)))[written:]
    for p in extra:
        os.remove(p)
        print("　− 删除多余片段 %s" % os.path.basename(p))

    print("\n完成：写入 %d 段，删除多余 %d 段" % (written, len(extra)))
    if clips:
        print("⚠ 削波片段：%s" % ", ".join("%s(%d点)" % c for c in clips[:6]))
    if weak:
        print("⚠ 电平过低：%s" % ", ".join("%s(%.1f)" % w for w in weak[:6]))


if __name__ == "__main__":
    main()
