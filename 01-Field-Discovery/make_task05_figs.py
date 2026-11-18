#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
课题 05：生成实测尺寸图与改造示意（纯标准库，输出 SVG）
用法：python make_task05_figs.py
输出：task05_fig_ladder.svg / task05_fig_rack.svg
"""

import math
import os

INK = "#212529"
SUB = "#868e96"
LINE = "#343a40"
GRID = "#dee2e6"
WALL = "#f1f3f5"
STEEL = "#ced4da"
RED = "#c92a2a"
BLUE = "#1c7ed6"
GREEN = "#2f9e44"
ORANGE = "#e8590c"

FONT = "-apple-system,Segoe UI,Microsoft YaHei,sans-serif"


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def text(x, y, s, size=12, fill=INK, anchor="start", weight="400"):
    return ('<text x="%.1f" y="%.1f" font-size="%g" fill="%s" text-anchor="%s" '
            'font-weight="%s">%s</text>' % (x, y, size, fill, anchor, weight, esc(s)))


def line(x1, y1, x2, y2, stroke=LINE, w=1.6, dash=None):
    d = ' stroke-dasharray="%s"' % dash if dash else ""
    return ('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="%g"%s/>'
            % (x1, y1, x2, y2, stroke, w, d))


def rect(x, y, w, h, fill="none", stroke=LINE, sw=1.6, dash=None, rx=0):
    d = ' stroke-dasharray="%s"' % dash if dash else ""
    return ('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%g" fill="%s" '
            'stroke="%s" stroke-width="%g"%s/>' % (x, y, w, h, rx, fill, stroke, sw, d))


def arrow(x, y, ang, color=INK, size=6):
    a = math.radians(ang)
    pts = [(x, y),
           (x - size * math.cos(a - 0.42), y - size * math.sin(a - 0.42)),
           (x - size * math.cos(a + 0.42), y - size * math.sin(a + 0.42))]
    return '<polygon points="%s" fill="%s"/>' % (" ".join("%.1f,%.1f" % q for q in pts), color)


def dim_h(x1, x2, y, label, color=BLUE, below=False):
    o = [line(x1, y, x2, y, color, 1.15),
         line(x1, y - 5, x1, y + 5, color, 1.15),
         line(x2, y - 5, x2, y + 5, color, 1.15),
         arrow(x1, y, 180, color, 5), arrow(x2, y, 0, color, 5)]
    o.append(text((x1 + x2) / 2, y + 16 if below else y - 7, label, 12, color, "middle", "600"))
    return "".join(o)


def dim_v(y1, y2, x, label, color=BLUE, left=True):
    o = [line(x, y1, x, y2, color, 1.15),
         line(x - 5, y1, x + 5, y1, color, 1.15),
         line(x - 5, y2, x + 5, y2, color, 1.15),
         arrow(x, y1, 90, color, 5), arrow(x, y2, 270, color, 5)]
    o.append(text(x - 8 if left else x + 8, (y1 + y2) / 2 + 4, label, 12, color,
                  "end" if left else "start", "600"))
    return "".join(o)


def leader(x1, y1, x2, y2, label, color=RED, at="tip"):
    """虚线引线 + 箭头；文字默认放在箭头端（at="tip"），可选尾端（at="tail"）"""
    ang = math.degrees(math.atan2(y2 - y1, x2 - x1))
    o = [line(x1, y1, x2, y2, color, 1.05, "5 3"), arrow(x2, y2, ang, color, 5)]
    if at == "tail":
        o.append(text(x1 + 7, y1 - 6, label, 11.5, color, "start", "600"))
    else:
        to_right = x2 >= x1
        o.append(text(x2 + (9 if to_right else -9), y2 - 7, label, 11.5, color,
                      "start" if to_right else "end", "600"))
    return "".join(o)


def marker(x, y, num, color=RED):
    return ('<circle cx="%.1f" cy="%.1f" r="9" fill="%s"/>' % (x, y, color)
            + text(x, y + 4, str(num), 11.5, "#ffffff", "middle", "700"))


# ---------------------------------------------------------------- 图 1 直梯
def fig_ladder(path):
    W, H = 1040, 700
    S = 2.35
    gy, top_y = 545, 545 - 170 * S          # 170cm 梯段
    cab_x, cab_w = 340, 150
    foot_x = cab_x - 15 * S                 # 梯脚（水平后退 15cm）
    gap = 30 * S                            # 踏杆间距 30cm

    def xt(y):
        t = (gy - y) / (gy - top_y)
        return foot_x + (cab_x - foot_x) * t

    o = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" '
         'font-family="%s">' % (W, H, W, H, FONT),
         '<rect width="100%" height="100%" fill="#ffffff"/>',
         text(24, 34, "图 1　宿舍上床直梯 · 实测侧视尺寸图", 19, INK, "start", "700"),
         text(24, 56, "单位 cm　｜　图示为示意，尺寸以标注为准　｜　实测五档踏杆、无侧向扶手", 11.5, SUB)]

    # 地面
    o.append(line(60, gy, 560, gy, LINE, 2.2))
    for x in range(60, 556, 16):
        o.append(line(x, gy, x - 7, gy + 7, "#adb5bd", 1))
    o.append(text(548, gy + 22, "地面", 11, SUB, "end"))

    # 柜体剖面
    o.append(rect(cab_x, top_y, cab_w, gy - top_y, WALL, LINE, 1.8))
    o.append(text(cab_x + cab_w / 2, top_y + 28, "柜体 / 床架", 12.5, "#495057", "middle", "600"))
    o.append(text(cab_x + cab_w / 2, top_y + 46, "（前立面）", 10.5, SUB, "middle"))
    o.append(line(cab_x, top_y - 22, cab_x, gy, "#adb5bd", 1, "6 4"))

    # 梯段立柱
    for dx in (-5, 5):
        o.append(line(foot_x + dx, gy, cab_x + dx, top_y, "#495057", 2.8))
    # 五档踏杆
    for k in range(1, 6):
        y = gy - k * gap
        cx = xt(y)
        o.append(rect(cx - 11, y - 3, 22, 6.5, STEEL, "#495057", 1.2))

    # 尺寸
    o.append(dim_v(top_y, gy, 78, "170", BLUE, True))
    o.append(dim_v(gy - 2 * gap, gy - gap, 148, "30", BLUE, False))
    o.append(dim_h(cab_x, foot_x, gy + 34, "15", BLUE, True))
    # 踏杆踩踏宽（放大引线）
    ry = gy - 3 * gap
    o.append(leader(xt(ry) - 12, ry - 2, 196, 330, "踏杆踩踏宽 6", RED, "tip"))

    # 倾角弧
    r = 74
    a2 = math.radians(95)
    o.append('<path d="M %.1f %.1f A %d %d 0 0 1 %.1f %.1f" fill="none" stroke="%s" stroke-width="1.3"/>'
             % (foot_x - r, gy, r, r, foot_x + r * math.cos(a2), gy - r * math.sin(a2), RED))
    bx = foot_x + (r + 20) * math.cos(math.radians(137))
    by = gy - (r + 20) * math.sin(math.radians(137))
    o.append(text(bx, by, "85.0°", 14, RED, "middle", "700"))
    o.append(text(bx, by + 15, "标准 65~75°", 10, RED, "middle"))

    # 编号标记
    o.append(marker(xt(gy - 4.6 * gap) - 26, gy - 4.6 * gap - 10, 1))
    o.append(marker(foot_x - 52, gy - 96, 2))

    # 图例（画在图下方空白处）
    o.append(rect(60, 600, 460, 78, "#fff5f5", "#ffc9c9", 1))
    o.append(text(74, 622, "① 无侧向扶手", 12, RED, "start", "700"))
    o.append(text(74, 640, "全线仅两根立柱可抓，攀爬时上身后仰，无横向支撑点。", 11, "#495057"))
    o.append(text(74, 664, "② 倾角 85.0°，每升高 1 m 仅前进 8.8 cm，膝盖易顶柜面。", 11, RED, "start", "700"))

    # ---- 右：改造示意 ----
    ox = 600
    o.append(line(580, 40, 580, H - 40, GRID, 1, "5 5"))
    o.append(text(ox, 66, "改造示意 · 预算 95 元", 17, INK, "start", "700"))
    o.append(text(ox, 86, "不动原结构，只做附件加装；倾角保持 85°。", 11.5, SUB))

    gy3, top3 = 470, 210
    cx0, cw = 800, 96
    fx3 = cx0 - 26
    o.append(line(ox, gy3, 1000, gy3, LINE, 2))
    o.append(rect(cx0, top3, cw, gy3 - top3, WALL, LINE, 1.6))
    o.append(text(cx0 + cw / 2, top3 + 22, "柜体", 11.5, "#495057", "middle"))
    for dx in (-4, 4):
        o.append(line(fx3 + dx, gy3, cx0 + dx, top3, "#495057", 2.4))
    yy = gy3 - 46
    while yy > top3 + 8:
        cx = fx3 + (cx0 - fx3) * ((gy3 - yy) / (gy3 - top3))
        o.append(rect(cx - 10, yy - 3, 20, 5.5, STEEL, "#495057", 1))
        o.append(rect(cx - 9, yy - 3.5, 18, 2, ORANGE, ORANGE, 0.5))
        yy -= 46

    # 扶手（平行外移 15cm）
    dx_, dy_ = cx0 - fx3, top3 - gy3
    L = math.hypot(dx_, dy_)
    nx, ny = dy_ / L, -dx_ / L
    off = 30
    o.append(line(fx3 + nx * off, gy3 + ny * off, cx0 + nx * off, top3 + ny * off, GREEN, 3.4))
    o.append(line(fx3 + nx * off - 12, gy3 + ny * off, fx3 + nx * off + 12, gy3 + ny * off, GREEN, 3.4))
    o.append(text(620, 250, "加装 U 形扶手", 11.5, GREEN, "start", "700"))
    o.append(text(620, 266, "Ø25 PVC 管 + 管夹", 10.5, GREEN))

    # 过渡踏板（把 30cm 第一档拆成 15+15）
    o.append(rect(fx3 - 78, gy3 - 24, 62, 8, "#ffe8cc", ORANGE, 1.4))
    o.append(text(fx3 - 84, gy3 - 18, "15 cm 过渡踏板", 11, ORANGE, "end", "600"))
    o.append(leader(cx0 - 2, gy3 - 196, cx0 + 128, gy3 - 214, "踏杆贴防滑砂条", ORANGE, "tip"))

    # 结论条
    o.append(rect(ox, 520, 410, 96, "#f1f8ff", "#a5d8ff", 1))
    o.append(text(ox + 14, 544, "改造边界（为什么不改倾角）", 12, BLUE, "start", "700"))
    o.append(text(ox + 14, 566, "要达 75° 需梯脚前移 30.6 cm，将侵占宿舍通道；", 11, "#495057"))
    o.append(text(ox + 14, 584, "故倾角保持 85°，仅从侧向支撑与足底摩擦入手。", 11, "#495057"))
    o.append(text(ox + 14, 604, "扶手 36 + 管夹 14 + 防滑条 15 + 踏板 22 + 辅料 8 = 95 元", 11, ORANGE, "start", "600"))

    o.append("</svg>")
    open(path, "w", encoding="utf-8").write("\n".join(o))


# ---------------------------------------------------------------- 图 2 晾衣杆
def fig_rack(path):
    W, H = 1040, 560
    S = 4.0                                  # px per cm
    o = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" '
         'font-family="%s">' % (W, H, W, H, FONT),
         '<rect width="100%" height="100%" fill="#ffffff"/>',
         text(24, 34, "图 2　窗侧晾衣杆 · 衣物与窗面干涉（现状 / 改造）", 19, INK, "start", "700"),
         text(24, 56, "侧视示意，单位 cm　｜　杆件离地约 3 m，须借助撑衣杆操作　｜　实测：挂衣后衣物侧缘与窗框接触", 11.5, SUB)]

    def panel(ox, title, moved, note):
        gy = 452
        win_x = ox + 300
        half = 4.0 * S                       # 衣物总厚 8cm 的一半
        rod_x = win_x - half - (10 * S if moved else 0)
        out = [text(ox, 96, title, 15, INK, "start", "700")]
        out.append(line(ox - 12, gy, ox + 440, gy, LINE, 2))
        # 顶面 + 窗
        out.append(line(ox - 12, 118, ox + 440, 118, GRID, 1.2, "6 4"))
        out.append(text(ox - 8, 110, "顶面（杆件贴近天棚）", 10.5, SUB))
        out.append(rect(win_x, 118, 12, gy - 118, "#e7f5ff", LINE, 1.4))
        out.append(text(win_x + 20, gy - 8, "窗 / 推拉门", 10.5, SUB))
        # 晾衣杆
        out.append('<circle cx="%.1f" cy="152" r="7.5" fill="%s" stroke="%s" stroke-width="1.6"/>'
                   % (rod_x, STEEL, LINE))
        out.append(text(rod_x - 13, 144, "晾衣杆 Ø2.5", 10.5, "#495057", "end"))
        # 衣架
        out.append('<path d="M %.1f 160 L %.1f 184 L %.1f 184" fill="none" stroke="%s" stroke-width="1.6"/>'
                   % (rod_x, rod_x - 11, rod_x + 11, "#495057"))
        out.append(line(rod_x - 13, 184, rod_x + 13, 184, "#495057", 1.6))
        # 衣服（梯形）
        bl, br = rod_x - half, rod_x + half
        out.append('<path d="M %.1f 186 L %.1f 336 L %.1f 336 L %.1f 186 Z" fill="#f8f9fa" '
                   'stroke="%s" stroke-width="1.5"/>' % (bl, bl + 7, br - 7, br, "#495057"))
        out.append(text(rod_x, 262, "衣", 13, SUB, "middle"))
        if not moved:
            out.append(line(br - 3, 190, br - 3, 330, RED, 2.6, "5 3"))
            out.append(text(br + 20, 206, "衣物侧缘与窗框接触", 11.5, RED, "start", "700"))
            out.append(text(br + 20, 226, "实测间隙 ≈ 0", 12.5, RED, "start", "700"))
        else:
            out.append(dim_h(br + 4, win_x, 352, "净空 10", GREEN, True))
            out.append(text(win_x + 20, 292, "衣物不再贴窗", 11.5, GREEN, "start", "700"))
        out.append(text(ox, 500, note, 11.5, SUB))
        return "".join(out)

    o.append(panel(36, "现状：衣物贴窗、蹭灰蹭水", False,
                   "杆件距窗框不足一衣之厚，挂衣即接触玻璃与窗框。"))
    o.append(line(512, 80, 512, 520, GRID, 1, "5 5"))
    o.append(panel(548, "改造后：杆件平行外移 10 cm", True,
                   "加长角码支架，杆件整体外移，原孔位不变。"))
    o.append("</svg>")
    open(path, "w", encoding="utf-8").write("\n".join(o))


if __name__ == "__main__":
    d = os.path.dirname(os.path.abspath(__file__))
    fig_ladder(os.path.join(d, "task05_fig_ladder.svg"))
    fig_rack(os.path.join(d, "task05_fig_rack.svg"))
    print("已生成 task05_fig_ladder.svg / task05_fig_rack.svg")
