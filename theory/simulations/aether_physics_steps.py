"""
AETHER 显示物理 · 逐步攻克（2026-10-24）
五个瓶颈逐一推导极限、寻找机制、数值验证：
  S1 悬浮深度与对焦（定理 4：对焦线索窗口；视锥上限；双子瞳孔视网膜仿真）
  S2 视角（偏振光栅全局偏置 + 逐色发光点补偿）
  S3 亮度、对比度、户外（光展量红利、方向保持的偏振回收）
  S4 多人（自由度守恒）
  S5 功耗与散热闭合
运行：python3 aether_physics_steps.py   → figs/st*.png, results_steps.json
"""
import json, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(HERE, "figs"); os.makedirs(FIG, exist_ok=True)
f_ = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
if os.path.exists(f_):
    font_manager.fontManager.addfont(f_); plt.rcParams["font.family"] = ["WenQuanYi Zen Hei", "DejaVu Sans"]
plt.rcParams.update({"axes.unicode_minus": False, "figure.dpi": 130, "axes.grid": True,
                     "grid.alpha": .25, "font.size": 10})
C = ["#2a6fdb", "#d1495b", "#2e9e5b", "#e09f3e", "#6c4ab6", "#555555"]
R = {}

LAM = 0.55e-3          # mm
DP = 4.0               # 瞳孔直径 mm
A_SHORT, A_LONG = 27.0, 42.8   # 卡片半宽 mm
DOF_D = 0.3            # 人眼景深 ±0.3 D

# ---------------------------------------------------------------- S1
def h_vac(d_mm, tol=DOF_D):
    d = d_mm / 1000
    return 1000 * tol * d * d / (1 + tol * d)

def p_star(d, N, delta):
    """条件 B 的最小透镜/像素间距：p + λd/p + dδ ≤ D/N 的较小根"""
    b = DP / N - d * delta
    disc = b * b - 4 * d * LAM
    if disc < 0: return np.nan
    return (b - np.sqrt(disc)) / 2

def h_focus_min(d, N, p):
    """条件 A：p ≤ D h /(N(d−h))  →  h ≥ N d p /(D + N p)"""
    return N * d * p / (DP + N * p)

def delta_max(d, N, p):
    return (DP / N - p - d * LAM / p) / d

S1 = {"h_vac_mm": {f"d{d}": round(h_vac(d), 1) for d in (300, 400, 500, 700)}}
rows = []
for d in (300, 400, 500):
    for p in (0.10, 0.15, 0.20, 0.25, 0.30):
        dm = delta_max(d, 2, p)
        rows.append({"d_mm": d, "p_mm": p,
                     "h_focus_min_mm": round(h_focus_min(d, 2, p), 1),
                     "delta_max_mrad": round(1e3 * dm, 2) if dm > 0 else None,
                     "beamlet_etendue_1D_um": round(1e3 * (p * dm + LAM), 3) if dm > 0 else None,
                     "beam_at_pupil_mm": round(p + d * LAM / p, 2)})
S1["focus_window"] = rows
# 视锥上限：半径 r 的物体在观看角 θ 下完整可见
S1["frustum_h_max_mm"] = {f"r{r}_th{t}": round((A_SHORT - r) / np.tan(np.radians(t)), 1)
                          for r in (5, 10) for t in (10, 15, 20, 25)}

# 图 st1a：(h, p) 平面上的两个窗口
fig, axs = plt.subplots(1, 2, figsize=(11, 4.2))
ax = axs[0]
p = np.linspace(0.05, 0.6, 300)
for d, c in ((300, C[0]), (400, C[1]), (500, C[2])):
    hf = h_focus_min(d, 2, p)
    ok = delta_max(d, 2, p) > 0
    ax.plot(p[ok], hf[ok], color=c, lw=2, label=f"d={d/10:.0f} cm：对焦线索下限 h_min(p)")
    ax.axhline(h_vac(d), color=c, ls="--", lw=1)
    ax.text(0.47, h_vac(d) + 1, f"景深等价上限 {h_vac(d):.0f} mm", color=c, fontsize=8)
    pr = p[~ok]
    if len(pr): ax.axvspan(0.05, pr.max(), color=c, alpha=.06)
ax.annotate("d=40 cm、p≈0.15–0.2 mm：\n两窗口重叠 → 0 到视锥上限无缝", xy=(0.18, 38), xytext=(0.3, 12), fontsize=8,
            arrowprops=dict(arrowstyle="->", lw=.8))
ax.text(0.06, 122, "阴影：衍射使光束在瞳孔处无法分开（条件 B 不成立）", fontsize=7, color=C[5])
ax.set_xlabel("透镜/像素间距 p (mm)"); ax.set_ylabel("悬浮高度 h (mm)")
ax.set_ylim(0, 130); ax.set_xlim(0.05, 0.6)
ax.set_title("定理 4：对焦线索窗口（实线以上）与景深等价窗口（虚线以下）", fontsize=9)
ax.legend(fontsize=7, loc="lower right")
ax = axs[1]
th = np.linspace(5, 40, 200)
for r, c in ((0, C[5]), (5, C[0]), (10, C[1])):
    ax.plot(th, (A_SHORT - r) / np.tan(np.radians(th)), color=c, lw=2, label=f"物体半径 {r} mm（短轴）")
ax.plot(th, (A_LONG - 10) / np.tan(np.radians(th)), color=C[1], lw=1, ls=":", label="半径 10 mm（长轴）")
ax.axhline(43, color=C[2], ls="--", lw=1); ax.text(30, 46, "AETHER-1 上限 ~43 mm", color=C[2], fontsize=8)
ax.set_ylim(0, 200); ax.set_xlabel("观看者偏离法线角 θ (°)"); ax.set_ylabel("完整可见的最大悬浮高度 (mm)")
ax.set_title("孔径锥给出的悬浮上限（与光学方案无关）", fontsize=9); ax.legend(fontsize=8)
fig.tight_layout(); fig.savefig(os.path.join(FIG, "st1_float_windows.png")); plt.close(fig)

# 视网膜仿真：眼睛对焦在何处时像最清晰？
def retinal_rms(zf_D, d, h, mode, pix=0.15, n=4000, rng=np.random.default_rng(1)):
    """一维几何+衍射：眼在原点，卡面在 d，体素在 d−h（距离眼）。返回视网膜角弥散 RMS (mrad)。"""
    zf = 1000 / zf_D  # mm
    if mode == "gen1":   # 每只眼一张卡面图像，光充满瞳孔
        u = rng.uniform(-DP / 2, DP / 2, n)
        x = rng.uniform(-pix / 2, pix / 2, n)
        ang = (x - u) / d + u / zf
        return 1e3 * np.std(ang)
    # 超多视：N=2 个子瞳孔时隙，每个时隙从子瞳孔中心渲染
    w = pix + LAM * d / pix
    angs = []
    for uk in (-DP / 4, DP / 4):
        xk = -uk * h / (d - h)
        u = uk + rng.uniform(-w / 2, w / 2, n)
        x = xk + rng.uniform(-pix / 2, pix / 2, n)
        a = (x - u) / d + u / zf + rng.normal(0, LAM / w / 2.355, n)   # 子孔径衍射
        angs.append(a)
    return 1e3 * np.std(np.concatenate(angs))

fig, ax = plt.subplots(figsize=(6.4, 4))
d = 400.0
zD = np.linspace(1.5, 4.5, 121)
res = {}
for h, c in ((20, C[0]), (60, C[1]), (90, C[4])):
    g1 = [retinal_rms(z, d, h, "gen1") for z in zD]
    sm = [retinal_rms(z, d, h, "smv") for z in zD]
    ax.plot(zD, g1, color=c, ls="--", lw=1)
    ax.plot(zD, sm, color=c, lw=2, label=f"h={h} mm：体素 {1000/(d-h):.2f} D")
    ax.axvline(1000 / (d - h), color=c, lw=.6, ls=":")
    res[f"h{h}"] = {"voxel_D": round(1000 / (d - h), 3),
                    "gen1_best_D": round(float(zD[np.argmin(g1)]), 3),
                    "smv_best_D": round(float(zD[np.argmin(sm)]), 3)}
ax.axvline(1000 / d, color="k", lw=.8); ax.text(1000 / d + .03, ax.get_ylim()[1] * .9 if False else 9, "卡面 2.5 D", fontsize=8)
ax.set_xlabel("眼睛对焦距离 (屈光度 D)"); ax.set_ylabel("视网膜弥散 RMS (mrad)")
ax.set_ylim(0, 10)
ax.set_title("双子瞳孔超多视（实线）把清晰点从卡面（虚线）拉到体素上\n d = 40 cm，像素 0.15 mm", fontsize=9)
ax.legend(fontsize=8); fig.tight_layout(); fig.savefig(os.path.join(FIG, "st1_retina.png")); plt.close(fig)
S1["retina_d400"] = res
R["S1"] = S1

# ---------------------------------------------------------------- S2
# 偏振光栅（PG）两级：切向分量相加  sinθ_out = sinθ_in + s1·λ/Λ1 + s2·λ/Λ2
B1, B2 = 0.2115, 0.423            # 在 λ0 = 550 nm 处的正弦偏置
LAM0 = 550.0
biases = sorted({s1 * B1 + s2 * B2 for s1 in (-1, 1) for s2 in (-1, 1)})
LOCAL_MAX = np.sin(np.radians(25))
def w80_local(th_in_deg, base):  # 第一代透镜：0°→base，25°→base+1.5°（取自 aether_mp_sim 非球面结果的趋势）
    return base + 1.5 * (abs(th_in_deg) / 25) ** 2

def window_width(th_out_deg, base, fwhm_nm):
    """返回 (偏置, 局部入射角, 出射角宽度 °)。选择使 |θ_in| 最小的偏置。"""
    so = np.sin(np.radians(th_out_deg))
    best = None
    for b in biases:
        si = so - b
        if abs(si) <= LOCAL_MAX + 1e-9:
            if best is None or abs(si) < abs(best[1]): best = (b, si)
    if best is None: return None
    b, si = best
    th_in = np.degrees(np.arcsin(si)); co = np.cos(np.radians(th_out_deg))
    geo = w80_local(th_in, base) * np.cos(np.radians(th_in)) / co        # 光展量守恒的角放大
    disp = np.degrees(abs(b) * fwhm_nm / LAM0 / co)                         # 色带内残余色散
    return b, th_in, float(np.hypot(geo, disp)), geo, disp

D_VIEW, IPD, CORE, TRACK = 500.0, 63.0, 20.0, 8.0
def spill_ok(w_deg, d=D_VIEW):
    spill_half = CORE / 2 + d * np.tan(np.radians(w_deg)) / 2
    return spill_half, spill_half <= IPD - 2 * TRACK

S2 = {"biases_sin": [round(b, 4) for b in biases],
      "Lambda_um": {"stage1": round(LAM0 / 1000 / B1, 3), "stage2": round(LAM0 / 1000 / B2, 3)}}
th_out = np.arange(0, 66, 1.0)
fig, axs = plt.subplots(1, 2, figsize=(11, 4.2))
cases = [("第一代透镜 4.9° + 白光 CF（60 nm）", 4.9, 60, C[5]),
         ("第一代透镜 4.9° + 量子点（30 nm）", 4.9, 30, C[0]),
         ("双片透镜 3.0° + 量子点（30 nm）", 3.0, 30, C[2]),
         ("双片透镜 3.0° + 微LED（20 nm）", 3.0, 20, C[4])]
S2["max_angle_deg"] = {}
for name, base, fw, c in cases:
    ws, oks = [], []
    for t in th_out:
        r = window_width(t, base, fw)
        if r is None: ws.append(np.nan); oks.append(False); continue
        ws.append(r[2]); oks.append(spill_ok(r[2])[1])
    ws = np.array(ws); oks = np.array(oks)
    axs[0].plot(th_out, ws, color=c, lw=2, label=name)
    lim = th_out[oks].max() if oks.all() is False or True else None
    # 连续可用的最大角度
    k = 0
    while k < len(oks) and oks[k]: k += 1
    S2["max_angle_deg"][name] = float(th_out[k - 1])
w_lim = np.degrees(np.arctan(2 * (IPD - 2 * TRACK - CORE / 2) / D_VIEW))
axs[0].axhline(w_lim, color=C[1], ls="--"); axs[0].text(2, w_lim + .3, f"不串眼上限 {w_lim:.1f}°（50 cm）", color=C[1], fontsize=8)
axs[0].set_xlabel("观看方向 θ_out (°)"); axs[0].set_ylabel("单眼光窗角宽 (°)")
axs[0].set_title("全局偏置后光窗宽度：光展量角放大 + 残余色散", fontsize=9); axs[0].legend(fontsize=7)
axs[0].set_ylim(0, 16)
# 逐色补偿：同一观看方向，RGB 需要的局部入射角
ax = axs[1]
for lamc, c, nm in ((630, C[1], "R 630"), (530, C[2], "G 530"), (460, C[0], "B 460")):
    req = []
    for t in th_out:
        so = np.sin(np.radians(t)); best = None
        for b in biases:
            si = so - b * lamc / LAM0
            if abs(si) <= LOCAL_MAX + 0.05:
                if best is None or abs(si) < abs(best): best = si
        req.append(np.degrees(np.arcsin(best)) if best is not None else np.nan)
    ax.plot(th_out, req, color=c, lw=2, label=nm)
ax.set_xlabel("观看方向 θ_out (°)"); ax.set_ylabel("该颜色应点亮的局部方向 θ_in (°)")
ax.set_title("逐色发光点选择抵消光栅色散（同一偏置下 RGB 选不同发光点）", fontsize=9)
ax.legend(fontsize=8); fig.tight_layout(); fig.savefig(os.path.join(FIG, "st2_bias_steering.png")); plt.close(fig)
# 偏置后孔径锥：平放卡片在各方向的悬浮上限（物体半径 5 mm）
S2["flat_float_h_mm_r5"] = {f"th{t}": {"short": round((A_SHORT - 5) / np.tan(np.radians(t)), 1),
                                       "long": round((A_LONG - 5) / np.tan(np.radians(t)), 1)} for t in (30, 45, 55)}
S2["efficiency"] = {"PG_per_stage": 0.95, "stages": 2, "HWP_FLC": 0.98, "total": round(0.95 ** 2 * 0.98 ** 2, 3),
                    "zero_order_leak_per_stage": 0.01}
R["S2"] = S2

# ---------------------------------------------------------------- S3
GEN1_PEAK_PER_NIT = 18518.5 / 250   # 第一代：发光峰值 / 观看亮度（4 时隙，LCD 6%，挡光墙等）
scen = {"室内 500 lx": (500, 250), "明亮室内 10 klx": (1e4, 600), "户外阴天 30 klx": (3e4, 1200), "直射阳光 100 klx": (1e5, 2000)}
R_DIFF = 0.005
S3 = {"etendue_dividend": round(np.pi / (np.radians(6.0) ** 2), 0), "rows": []}
for k, (E, L) in scen.items():
    Lbg = R_DIFF * E / np.pi
    for name, gain in (("第一代", 1.0), ("+方向保持偏振回收 ×1.6", 1.6)):
        peak = L * GEN1_PEAK_PER_NIT / gain
        S3["rows"].append({"scene": k, "variant": name, "target_cd_m2": L, "bg_cd_m2": round(Lbg, 1),
                           "ACR": round((L + Lbg) / Lbg, 1), "emitter_peak_cd_m2": round(peak),
                           "OLED_ok(<25k)": peak < 25000, "uLED_ok(<1e6)": peak < 1e6})
# 回收增益：反射式偏振片把另一偏振反射回透镜 → 聚焦回同一发光点 → 阴极反射 + λ/4 双程旋偏 → 原方向射出
Rc, Rp, Tq = 0.80, 0.95, 0.97     # 阴极反射率、反射偏振片效率、λ/4 往返透过
g = 0.5
loop = 0.5 * Rp * Rc * Tq * Tq
S3["recycle_gain"] = round((0.5 + loop * (1 / (1 - 0))) / 0.5 if False else (0.5 + 0.5 * Rp * Rc * Tq ** 2) / 0.5, 2)
# 光通量与功率（只与送进瞳孔的光通量有关，与光束细窄无关）
eff = {"白光 OLED（50 lm/W）": 50, "小尺寸微LED（20 lm/W）": 20}
S3["emit_power_W"] = {f"{n}@{L}": round(0.6723 * L / 250 / e, 3) for n, e in eff.items() for L in (250, 600, 2000)}
R["S3"] = S3

fig, ax = plt.subplots(figsize=(6.4, 3.8))
Ls = np.logspace(1.5, 3.6, 100)
ax.loglog(Ls, Ls * GEN1_PEAK_PER_NIT, color=C[5], lw=2, label="第一代叠层")
ax.loglog(Ls, Ls * GEN1_PEAK_PER_NIT / 1.6, color=C[0], lw=2, label="+ 方向保持偏振回收")
ax.axhspan(1, 2.5e4, color=C[3], alpha=.08); ax.text(40, 1.5e4, "OLED 峰值可持续区", fontsize=8, color=C[3])
ax.axhline(1e6, color=C[4], ls="--"); ax.text(40, 1.2e6, "微LED 量级", fontsize=8, color=C[4])
for k, (E, L) in scen.items():
    ax.axvline(L, color=C[1], lw=.6, ls=":"); ax.text(L * 1.03, 3e3, k, rotation=90, fontsize=7, color=C[1])
ax.set_ylim(1e3, 5e6); ax.set_xlabel("观看到的亮度 (cd/m²)"); ax.set_ylabel("方向层发光峰值 (cd/m²)")
ax.set_title("亮度瓶颈在发光点峰值亮度，不在功率", fontsize=9); ax.legend(fontsize=8)
fig.tight_layout(); fig.savefig(os.path.join(FIG, "st3_brightness.png")); plt.close(fig)

# ---------------------------------------------------------------- S4
P_VIEW = 462240; F_MIN = 60
mods = [("LCD 240 Hz（第一代）", 1, 462240, 240), ("快速 LCD 480 Hz", 1, 462240, 480),
        ("双层 LCD 因式分解 240 Hz", 2, 462240, 240), ("双层 LCD 480 Hz", 2, 462240, 480),
        ("铁电 LC 3 kHz 位平面（8 位灰度）", 1, 462240, 3000 / 8)]
S4 = {"rows": [{"modulator": n, "eyes_max": int(L * dof * f // (P_VIEW * F_MIN)),
                "viewers_max": int(L * dof * f // (P_VIEW * F_MIN)) // 2} for n, L, dof, f in mods]}
S4["gen3_emissive"] = "自由度 = 1.5e8 个发光点，同时服务所有眼睛；上限变为功率（每增加一人 +2 份光通量）"
R["S4"] = S4

# ---------------------------------------------------------------- S5
gen1 = {"方向层发光": 0.013, "方向层驱动": 0.30, "LCD+驱动 240 Hz": 0.25, "红外相机+照明": 0.30,
        "SoC 追踪+渲染": 0.70, "无线": 0.15}
gen2 = {"方向层发光（微LED，室内 250）": 0.034, "方向层驱动（微LED 稀疏点亮）": 0.25, "LCD+驱动 480 Hz": 0.35,
        "偏振光栅 FLC 半波片 ×2": 0.02, "红外相机+照明（广角）": 0.35, "SoC 追踪+8 路渲染": 0.80, "无线": 0.15}
def tot(b): s = sum(b.values()); return s * 1.12
S5 = {"gen1_W": round(tot(gen1), 2), "gen2_indoor_W": round(tot(gen2), 2)}
g2o = dict(gen2); g2o["方向层发光（微LED，室内 250）"] = 0.269   # 2000 cd/m²
S5["gen2_outdoor_W"] = round(tot(g2o), 2)
S5["thermal_limit_W_dT15"] = 2.15
g2a = dict(gen2); g2a["LCD+驱动 480 Hz"] = 0.25; g2a["SoC 追踪+8 路渲染"] = 0.70
S5["gen2_adaptive_le2viewers_W"] = round(tot(g2a), 2)      # ≤2 人时 LCD 降回 240 Hz、渲染 4 路
S5["sun_absorbed_W"] = round(1000 * 85.6e-3 * 54e-3 * 0.9, 2)  # 直射阳光 1000 W/m²、正面吸收 0.9
S5["heat_capacity_J_per_K"] = 60 * 0.9                       # 约 60 g 整机，平均比热约 0.9 J/gK（估计）
S5["gen2_budget"] = gen2
R["S5"] = S5

with open(os.path.join(HERE, "results_steps.json"), "w") as f:
    json.dump(R, f, ensure_ascii=False, indent=1)
print(json.dumps(R, ensure_ascii=False, indent=1))
