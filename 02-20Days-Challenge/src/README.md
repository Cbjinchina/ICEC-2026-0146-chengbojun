# src 脚本清单

**零第三方依赖**，只用 Python 标准库（`wave` / `struct` / `math` / `csv`）。本机 Python 3.13 直接可跑，不用 `pip install`，断网也能复现全部结果。

| 文件 | 作用 | 状态 |
|---|---|---|
| `fft_features.py` | 读 `process_logs/raw/*.wav` → 分帧 Hanning 窗 → 自实现 radix-2 FFT → 输出 `features.csv`（主频、谱质心、RMS、过零率、低/高频能量比） | 已就绪 |
| `classify.py` | 每工况按 run 编号分层留出最后 3 组作盲测 → 训练集标准化 + 类中心最近邻 → 输出混淆矩阵与准确率报告 | 已就绪 |
| `ingest_audio.py` | 手机录音（M4A/MP3）→ 转码 16-bit WAV → 首尾各裁 1 s → 均分 15 段，同时输出 `manifest.csv`（时长/RMS/峰值/削波） | 已就绪 |
| `patch_condition.py` | **只替换某一个工况**的切片（重录后不用整体重跑），旧片段自动 `.bak` 备份 | 已就绪 |
| `add_noise.py` | 按目标 SNR 离线合成高斯白噪声（固定随机种子，可复现），替代现场录噪声 | 已就绪 |
| `plot_waveforms.py` | 课题 08 三轴波形图（与阶段一复用） | 可选，待编写 |

## 复现命令

在 `02-20Days-Challenge/` 目录下：

```
python src/fft_features.py --input process_logs/raw --output features.csv
python src/classify.py --features features.csv --report classification_report.md
```

`fft_features.py` 会在终端打印各工况特征均值，采完数据先跑这条，一眼就能看出 5 种工况有没有区分度——如果均值挤在一起，先回去调整工况设置（比如胶带量、遮挡面积），别急着调模型。

## 前提与约定

- WAV 必须是 **16-bit PCM**，单/双声道都可以（双声道自动取均值）；文件名 `cond01_run01.wav` … `cond05_run15.wav`。
- 每个文件取中间最多 8 帧（每帧 2048 点）做平均，避开开头结尾的开关噪声。
- 不符合命名或格式的文件会被**明确列出并跳过**，不会静默丢弃；被跳过的文件要写进 `process_logs/raw/sampling_notes.md`。
- 盲测集按 run 编号固定留出，调参前就确定，不许事后把错分样本挪回训练集。
- 每次改脚本都要有对应 commit，并在 `iterations/` 写清改动依据。

## 自检说明

脚本已用**合成正弦信号**验证过链路可跑（主频识别 50.8 Hz / 89.8 Hz，对应理论 50 / 90 Hz）。合成音频仅用于验证代码，测完即删除，**绝不作为实测数据进入仓库**；`features.csv` 与 `classification_report.md` 必须由本人真实采集的 75 组 WAV 重新生成。
