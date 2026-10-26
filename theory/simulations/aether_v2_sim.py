# -*- coding: utf-8 -*-
"""
AETHER v2.0「互易光孔」推演模拟（2026-10-25）
覆盖：
  F1 一个孔的可见性：任意角度看见的条件（推广孔径定理）与孔径大小
  F2 广播光场的深度—角度权衡（定理 6）与逐眼锐化
  F3 互易孔的视网膜回射找人（定理 7）信噪比
  F4 能量—厚度定律（定理 8）与日用能量
  F5 同一孔对表面投影的分辨率上限
运行：python3 aether_v2_sim.py  → results_v2.json, figs/v2_*.png
所有器件参数为估计值，注释里写明来源或假设。
"""
import json, math, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

f_ = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
if os.path.exists(f_):
    font_manager.fontManager.addfont(f_); plt.rcParams["font.family"] = ["WenQuanYi Zen Hei", "DejaVu Sans"]
plt.rcParams.update({"axes.unicode_minus": False, "figure.dpi": 130, "axes.grid": True,
                     "grid.alpha": .25, "font.size": 10, "mathtext.fontset": "custom", "mathtext.rm": "DejaVu Sans", "mathtext.it": "DejaVu Sans:italic", "mathtext.bf": "DejaVu Sans:bold", "mathtext.default": "rm"})
from matplotlib.ticker import FuncFormatter
_fmt = FuncFormatter(lambda v, _: (f"{v:g}" if 1e-3 <= v < 1e5 else f"{v:.0e}".replace("e+0", "e").replace("e-0", "e-")))
def fixlog(ax):
    for a, sc in ((ax.xaxis, ax.get_xscale()), (ax.yaxis, ax.get_yscale())):
        if sc == "log": a.set_major_formatter(_fmt); a.set_minor_formatter(FuncFormatter(lambda v, _: ""))
_save = matplotlib.figure.Figure.savefig
def _savefix(self, *a, **k):
    for ax in self.axes: fixlog(ax)
    return _save(self, *a, **k)
matplotlib.figure.Figure.savefig = _savefix
C = ["#1f5f8b", "#b4532a", "#2f7a4f", "#7a4fa0", "#c49a1c", "#5b6670"]
HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(HERE, "figs"); os.makedirs(FIG, exist_ok=True)
R = {}

# ---------------- 基本几何 ----------------
CARD = (85.6, 54.0)            # ISO/IEC 7810 ID-1
AP = (84.0, 52.0)              # v2.1 无边框全卡光孔，四周只留约 0.8–1 mm 框（v2.0 为 76×44）
A_ap = AP[0] * AP[1] * 1e-6    # m^2
R["aperture_mm"] = AP; R["aperture_m2"] = A_ap

# ---------------- F1 可见性 ----------------
def visible_fraction(h, r, W, H, n=181):
    """体素在孔中心正上方高度 h（mm，负值=孔后方），半径 r。
    方向 (θ,φ) 可见 ⇔ 从体素沿该方向反向延长的直线（以及半径 r 的整个物体）穿过矩形孔。
    返回上半球立体角中可见的比例（按 cosθ 加权=按“看见孔的视线”计）以及纯立体角比例。"""
    th = np.linspace(0, np.pi / 2 * 0.999, n); ph = np.linspace(0, 2 * np.pi, 2 * n)
    T, P = np.meshgrid(th, ph, indexing="ij")
    dx = abs(h) * np.tan(T) * np.cos(P); dy = abs(h) * np.tan(T) * np.sin(P)
    ok = (np.abs(dx) + r <= W / 2) & (np.abs(dy) + r <= H / 2)
    dOm = np.sin(T)
    return float((ok * dOm).sum() / dOm.sum())

hs = np.linspace(0, 80, 81)
holes = {"v2.1 无边框光孔 84×52 mm": AP, "v2.0 光孔 76×44 mm": (76, 44), "小孔 Ø10 mm（≈10×10）": (10, 10), "小孔 Ø3 mm": (3, 3)}
fig, ax = plt.subplots(1, 2, figsize=(10.5, 4.0))
R["F1"] = {}
for i, (k, (W, H)) in enumerate(holes.items()):
    r = min(5, W / 2 * 0.3)
    fr = [visible_fraction(h, r, W, H) for h in hs]
    ax[0].plot(hs, np.array(fr) * 100, color=C[i], label=f"{k}，物体 r={r:g} mm")
    R["F1"][k] = {f"h{int(h)}": round(fr[int(h)] * 100, 1) for h in (0, 5, 10, 20, 40, 60)}
ax[0].set_xlabel("悬浮高度 h（mm，孔前或孔后对称）"); ax[0].set_ylabel("上半球中能完整看到物体的方向 %")
ax[0].set_title("F1a 只要视线穿过孔就看得见：孔越大，浮得越高仍看得见", fontsize=9)
ax[0].legend(fontsize=7)
# F1b 给定观看角，最大悬浮
ths = np.radians(np.linspace(1, 85, 85))
for i, (k, (W, H)) in enumerate(list(holes.items())[:3]):
    r = min(5, W / 2 * 0.3)
    hmax = np.clip((min(W, H) / 2 - r) / np.tan(ths), 0, 200)
    hmaxL = np.clip((max(W, H) / 2 - r) / np.tan(ths), 0, 200)
    ax[1].plot(np.degrees(ths), hmax, color=C[i], label=f"{k} 短轴方向")
    ax[1].plot(np.degrees(ths), hmaxL, color=C[i], ls="--", lw=1, label=f"{k} 长轴方向")
ax[1].set_ylim(0, 120); ax[1].set_xlabel("观看方向偏离孔法线的角度 θ（°）"); ax[1].set_ylabel("该方向上能完整看到的最大悬浮 h（mm）")
ax[1].set_title("F1b h ≤ (W/2 - r)/tanθ；θ→90° 时只剩孔平面上的内容", fontsize=9)
ax[1].legend(fontsize=6.5)
fig.tight_layout(); fig.savefig(os.path.join(FIG, "v2_f1_visibility.png")); plt.close(fig)
R["F1"]["hmax_short_axis_84x52_r5"] = {f"{a}deg": round((AP[1] / 2 - 5) / math.tan(math.radians(a)), 1) for a in (15, 30, 45, 60, 75)}

# ---------------- F2 广播光场（定理 6） ----------------
# 直接发光光场：每个透镜（间距 p）下 k×k 个发光点（间距 e），透镜 F 数 N≈1，局部视场 ±θL。
# 每个发光点的光束角 Δθ ≈ e/f，f = N·p。广播清晰深度 h* = p/Δθ（体素模糊 = max(p, h·Δθ)）。
# 立体视觉距离上限 d_st = IPD/Δθ（光束宽度超过两眼间距后，两眼收到同一值）。
IPD = 63.0
def lf_design(p, e, N=1.0, G=9):
    f = N * p; dth = e / f            # rad
    k = p / e
    hstar = p / dth
    d_st = IPD / dth / 1000           # m
    n_em = (AP[0] / e) * (AP[1] / e)          # e 以 mm 计
    rays_frame = n_em * G
    return dict(p_mm=p, e_um=e * 1e3, f_mm=f, dtheta_deg=math.degrees(dth), k=k, h_sharp_mm=hstar,
                beam_at_40cm_mm=dth * 400, stereo_max_m=d_st, emitters=n_em, rays_per_frame=rays_frame,
                blur_at_20mm=max(p, 20 * dth), blur_at_40mm=max(p, 40 * dth))
designs = {"Ω-1（第一代）": lf_design(0.15, 0.004), "Ω-2（ISO 版）": lf_design(0.12, 0.003)}
R["F2"] = {k: {kk: (round(vv, 4) if isinstance(vv, float) else vv) for kk, vv in v.items()} for k, v in designs.items()}
fig, ax = plt.subplots(1, 2, figsize=(10.5, 4.0))
dth = np.linspace(0.2, 6, 200)
for i, p in enumerate([0.1, 0.15, 0.2, 0.3]):
    ax[0].plot(dth, p / np.radians(dth), color=C[i], label=f"透镜间距 p = {p} mm")
for k, v in list(designs.items())[:2]:
    ax[0].plot(v["dtheta_deg"], v["h_sharp_mm"], "o", color="k"); ax[0].annotate(k, (v["dtheta_deg"], v["h_sharp_mm"]), textcoords="offset points", xytext=(6, 4), fontsize=8)
ax[0].axhline(43, color=C[2], ls=":"); ax[0].text(3.2, 45, "逐眼锐化：被发现的观看者清晰到 43 mm（定理 3，d=40 cm）", fontsize=7, color=C[2])
ax[0].set_yscale("log"); ax[0].set_xlabel("单个发光点光束角 Δθ（°）"); ax[0].set_ylabel("广播模式清晰深度 h* = p/Δθ（mm）")
ax[0].set_title("F2a 定理 6：广播光场的清晰深度只由 p/Δθ 决定", fontsize=9); ax[0].legend(fontsize=7)
for i, p in enumerate([0.1, 0.15, 0.2]):
    e = np.linspace(0.0015, 0.012, 100)
    n = (AP[0] / e) * (AP[1] / e)
    ax[1].plot(e * 1e3, n, color=C[i], label=f"p={p} mm（任意 p，发光点数只由 e 决定）" if i == 0 else None)
    break
for k, v in list(designs.items())[:2]:
    ax[1].plot(v["e_um"], v["emitters"], "o", color="k"); ax[1].annotate(f"{k}\n{v['emitters']:.2e} 点，Δθ={v['dtheta_deg']:.2f}°", (v["e_um"], v["emitters"]), textcoords="offset points", xytext=(8, 0), fontsize=7)
ax[1].axhline(3660 * 3200 * 2, color=C[5], ls=":"); ax[1].text(6.5, 3660 * 3200 * 2 * 1.15, "Vision Pro 两片 micro-OLED 合计", fontsize=7, color=C[5])
ax[1].set_yscale("log"); ax[1].set_xlabel("发光点间距 e（µm）"); ax[1].set_ylabel("76×44 mm 光孔所需发光点数")
ax[1].set_title("F2b 发光点数 = 孔面积 / e²（与透镜间距无关）", fontsize=9); ax[1].legend(fontsize=7)
fig.tight_layout(); fig.savefig(os.path.join(FIG, "v2_f2_broadcast.png")); plt.close(fig)

# ---------------- F3 视网膜回射找人（定理 7） ----------------
# 互易：发光点与探测点共用同一微透镜。看得到孔的眼睛，其瞳孔把孔发出的光经视网膜回射回同一批透镜。
def retro_snr(d, L=250.0, mod=0.10, Rret=0.06, T=0.033, Lbg=50.0, pupil=5e-3, eta=0.6, fill=0.15, cap=0.3, dth=math.radians(1.53)):
    lam_e = 3.6e-19 * 0.85      # J/光子（红光约 630 nm 偏 0.85×绿光能量）
    K = 400.0                   # lm/W 红光近似（630 nm 时 V≈0.26 → 683×0.26≈180；取保守混合 400 用于白光内容中的红分量估计）
    Om = A_ap / d ** 2
    E = L * Om                                  # lx 于瞳孔
    Ppup = E * math.pi * (pupil / 2) ** 2 / K   # W
    S = Ppup * mod * Rret * 0.8 * cap * fill / lam_e * eta   # 电子/s（锁相信号）
    # 背景：每个透镜指向该方向的探测点看到 Δθ² 立体角的人脸/房间
    Bg = Lbg * A_ap * dth ** 2 * fill / K / lam_e * eta
    s = S * T; n = math.sqrt(Bg * T + S * T)
    return s / n
ds = np.linspace(0.25, 2.5, 100)
fig, ax = plt.subplots(figsize=(6.4, 3.8))
R["F3"] = {}
for i, (lab, kw) in enumerate({"室内 250 cd/m²，调制 10%，33 ms": {}, "调制 3%（更隐蔽）": {"mod": 0.03}, "暗室背景 5 cd/m²": {"Lbg": 5.0}, "户外背景 2000 cd/m²，显示 1500": {"Lbg": 2000.0, "L": 1500.0}}.items()):
    sn = [retro_snr(d, **kw) for d in ds]
    ax.plot(ds, sn, color=C[i], label=lab)
    R["F3"][lab] = {f"{d}m": round(retro_snr(d, **kw), 1) for d in (0.3, 0.5, 1.0, 2.0)}
ax.axhline(5, color="k", ls=":"); ax.text(1.6, 5.6, "可靠检测 SNR≈5", fontsize=8)
ax.set_yscale("log"); ax.set_xlabel("观看距离 d（m）"); ax.set_ylabel("瞳孔回射锁相信噪比")
ax.set_title("F3 定理 7：孔用自己的光找到瞳孔（无相机）。SNR ∝ L·A/d²", fontsize=9); ax.legend(fontsize=7)
fig.tight_layout(); fig.savefig(os.path.join(FIG, "v2_f3_retro.png")); plt.close(fig)

# ---------------- F4 无电池能源（定理 8 → 定理 9） ----------------
A_rx = 80 * 49 * 1e-6    # m^2 背面接收面积
A_card = CARD[0] * CARD[1] * 1e-6
# 各模式功耗（W，估计值）
P = {
 "休眠（反向散射收通知，显示关）": dict(display=0.0, sense=0.0001, compute=0.0002, radio=0.00005, conv=0.00005),
 "待机（eDRX 蜂窝 + 唤醒无线电）": dict(display=0.0, sense=0.0008, compute=0.0012, radio=0.0015, conv=0.0005),
 "极简私密（文字/通知，只点亮主人方向）": dict(display=0.01, sense=0.012, compute=0.03, radio=0.02, conv=0.01),
 "私密 2D/3D（只照亮主人瞳孔）": dict(display=0.03, sense=0.04, compute=0.18, radio=0.06, conv=0.04),
 "共享 2D（孔面图像，任意角度）": dict(display=0.19, sense=0.03, compute=0.18, radio=0.06, conv=0.05),
 "共享 3D 广播（9 偏置态，被发现者逐眼锐化）": dict(display=0.47, sense=0.06, compute=0.30, radio=0.10, conv=0.10),
 "蜂窝通话（面板发声）": dict(display=0.0, sense=0.01, compute=0.08, radio=0.25, conv=0.04),
}
Ptot = {k: sum(v.values()) for k, v in P.items()}
# 定理 8 保留为数字：ISO 卡内 0.30 mm 电池 350 Wh/L
E_iso = 80 * 49 * 1e-2 * 0.30 / 10 * 350 / 1000
# 定理 9：可获得功率 = 能流密度 × 接收面积 × 转换效率
src = {
 # 自然环境
 "体温温差发电（手持，约 20 µW/cm²×10 cm²）": ("自然", 20e-6 * 10),
 "环境射频（城市背景约 1 mW/m²）": ("自然", 1e-3 * A_card * 0.3),
 "室内 500 lx 钙钛矿 PV": ("自然", 500 / 300 * 0.35 * A_rx),
 "办公 2,000 lx PV": ("自然", 2000 / 300 * 0.387 * A_rx),
 "户外阳光 PV（背面朝天约一半时间）": ("自然", 1000 * 0.25 * A_rx * 0.5),
 # 人造能量场
 "远场射频，按 ICNIRP 公众限值 10 W/m² 满功率（整流 50%）": ("人造", 10 * A_card * 0.5),
 "房间级磁准静态谐振腔（东京大学 2021；手机实测约 5 W，卡片线圈估计）": ("人造", 1.0),
 "红外光束供能（Wi-Charge 类，估计）": ("人造", 1.0),
 "接触式表面磁共振": ("人造", 5.0),
}
R["F4"] = {"P_modes_W": {k: round(v, 4) for k, v in Ptot.items()}, "P_breakdown": P,
           "battery_iso_Wh_theorem8": round(E_iso, 2), "sources_W": {k: round(v[1], 5) for k, v in src.items()}}
# 缓冲：超级电容（非电池），0.25 mm × 80×49 mm，3 Wh/L（估计）
E_buf_J = 80 * 49 * 1e-2 * 0.025 * 3 / 1000 * 3600
R["F4"]["buffer_J"] = round(E_buf_J, 1)
R["F4"]["buffer_seconds"] = {k: round(E_buf_J / v, 1) for k, v in Ptot.items() if v > 0.005}
R["F4"]["buffer_standby_h"] = round(E_buf_J / Ptot["待机（eDRX 蜂窝 + 唤醒无线电）"] / 3600, 2)
R["F4"]["buffer_sleep_h"] = round(E_buf_J / Ptot["休眠（反向散射收通知，显示关）"] / 3600, 1)
fig, ax = plt.subplots(figsize=(10.5, 4.6))
names = list(src.keys()); vals = [src[n][1] for n in names]
cols = [C[2] if src[n][0] == "自然" else C[0] for n in names]
ax.barh(names, vals, color=cols); ax.set_xscale("log"); ax.set_xlim(5e-6, 20); ax.set_ylim(-1.0, len(names) - 0.5)
ax.tick_params(axis="y", labelsize=7.5)
for k, c, ls in (("待机（eDRX 蜂窝 + 唤醒无线电）", C[1], ":"), ("极简私密（文字/通知，只点亮主人方向）", C[3], "--"),
                 ("私密 2D/3D（只照亮主人瞳孔）", C[4], "--"), ("共享 3D 广播（9 偏置态，被发现者逐眼锐化）", C[5], "-")):
    ax.axvline(Ptot[k], color=c, ls=ls, lw=1.2)
    ax.text(Ptot[k] * 1.08, -0.95, k.split("（")[0], fontsize=7, color=c, rotation=90, va="bottom")
ax.set_xlabel("一张卡能拿到的功率（W，对数）；绿色=自然环境，蓝色=人造能量场")
ax.set_title("F4 定理 9：没有电池时，能不能用由环境能流密度决定。自然环境里只有阳光能驱动显示", fontsize=9)
fig.tight_layout(); fig.savefig(os.path.join(FIG, "v2_f4_energy.png")); plt.close(fig)
hconv = 12.5; Asurf = 2 * CARD[0] * CARD[1] * 1e-6
R["F4"]["thermal_W_at_dT10"] = round(hconv * Asurf * 10, 2)
R["F4"]["thermal_W_at_dT15"] = round(hconv * Asurf * 15, 2)

# ---------------- F6 大孔的改良 ----------------
r6 = 5.0
cfg = {"单卡无边框 84×52（短轴）": 52, "单卡无边框 84×52（长轴）": 84,
       "两卡并排拼孔 170×52（长轴）": 170, "四卡 2×2 拼孔 170×106（短轴）": 106}
fig, ax = plt.subplots(1, 2, figsize=(10.5, 4.0))
R["F6"] = {}
ths6 = np.radians(np.linspace(5, 85, 81))
for i, (k, W) in enumerate(cfg.items()):
    hm = (W / 2 - r6) / np.tan(ths6)
    ax[0].plot(np.degrees(ths6), np.clip(hm, 0, 300), color=C[i], label=k)
    R["F6"][k] = {f"{a}deg": round((W / 2 - r6) / math.tan(math.radians(a)), 1) for a in (15, 30, 45, 60)}
ax[0].plot(np.degrees(ths6), np.clip((44 / 2 - r6) / np.tan(ths6), 0, 300), color="k", ls=":", label="v2.0 光孔 76×44（短轴）")
ax[0].set_ylim(0, 200); ax[0].set_xlabel("观看角 θ（°）"); ax[0].set_ylabel("该方向最大悬浮 h（mm），r=5 mm")
ax[0].set_title("F6a 无边框 + 多卡拼孔：悬浮上限随孔宽线性增加", fontsize=9); ax[0].legend(fontsize=7)
# 全球面可见：单面 vs 双面（孔平面内容）
hs6 = np.linspace(0, 40, 41)
one = np.array([visible_fraction(h, r6, AP[0], AP[1]) for h in hs6]) * 50
ax[1].plot(hs6, one, color=C[0], label="单面光孔（只有正面半球）")
ax[1].plot(hs6, one * 2, color=C[1], label="双面光孔（正反各一个孔，立起来全球面）")
ax[1].set_ylim(0, 105); ax[1].set_xlabel("悬浮高度 h（mm）"); ax[1].set_ylabel("整个球面中能看到的方向 %")
ax[1].set_title("F6b 双面光孔：卡片立着时前后两边的人都能看", fontsize=9); ax[1].legend(fontsize=7)
R["F6"]["sphere_pct_single_h0_h10_h20"] = [round(one[0], 1), round(one[10], 1), round(one[20], 1)]
fig.tight_layout(); fig.savefig(os.path.join(FIG, "v2_f6_aperture.png")); plt.close(fig)

# ---------------- F5 表面投影分辨率 ----------------
lam = 550e-9
def proj_px(z, p, e, f):
    return max(p, lam * z / p, z * e / f)    # m
zs = np.linspace(0.05, 1.5, 200)
fig, ax = plt.subplots(figsize=(6.4, 3.8))
cases = {"Ω-1：e=4 µm、f=0.15 mm（几何发散主导）": (0.15e-3, 4e-6, 0.15e-3),
         "近单模发光点 e=0.5 µm（第三代）": (0.15e-3, 0.5e-6, 0.15e-3),
         "近单模 + 投影时 4×4 透镜相干合成（研究）": (0.6e-3, 0.5e-6, 0.6e-3)}
R["F5"] = {}
for i, (k, (p, e, f)) in enumerate(cases.items()):
    s = np.array([proj_px(z, p, e, f) for z in zs]) * 1e3
    ax.plot(zs * 100, s, color=C[i], label=k)
    R["F5"][k] = {f"{int(z*100)}cm_px_mm": round(proj_px(z, p, e, f) * 1e3, 2) for z in (0.1, 0.3, 1.0)}
    w = 0.35 * 0.3   # 30 cm 处投影宽度：约 0.7 z
    R["F5"][k]["px_across_at_30cm_200mm_wide"] = int(200 / (proj_px(0.3, p, e, f) * 1e3))
ax.set_yscale("log"); ax.set_xlabel("到投影表面的距离 z（cm）"); ax.set_ylabel("投影像素尺寸（mm）")
ax.axhline(1.0, color="k", ls=":"); ax.text(80, 1.1, "1 mm（键盘、图标够用；正文不够）", fontsize=7)
ax.set_title("F5 同一孔把光场聚焦到桌面/手掌/墙：像素 = max(p, λz/p, z·e/f)", fontsize=9); ax.legend(fontsize=7)
fig.tight_layout(); fig.savefig(os.path.join(FIG, "v2_f5_projection.png")); plt.close(fig)

# ---------------- 其他关键数字 ----------------
# 广播 3D 光通量与发光功率
L_in = 250; L_out = 2000
phi = lambda L: math.pi * L * A_ap * math.sin(math.radians(62)) ** 2   # 只发到 ±62° 锥内
R["light"] = {"shared_lm_250nit": round(phi(L_in), 2), "shared_lm_2000nit": round(phi(L_out), 2),
              "shared_W_at_20lmW_250": round(phi(L_in) / 20, 3), "shared_W_at_20lmW_2000": round(phi(L_out) / 20, 3)}
# 私密模式：光只进两只瞳孔附近的光束（每透镜每眼 ≈ 2×2 发光点 / k² ）
k = designs["Ω-1（第一代）"]["k"]
R["light"]["private_fraction_of_shared"] = round(2 * 4 / (k * k * 9), 5)
R["light"]["private_W_2000nit"] = round(phi(L_out) / 20 * R["light"]["private_fraction_of_shared"], 4)
# 定理 5'：直接发光光场的同时观看人数
R["theorem5p"] = {"eyes_max_per_state": int(k * k), "note": "每只眼占约 2×2 个方向，互不重叠的眼数 ≈ k²/4（每偏置态）"}
R["theorem5p"]["eyes_practical"] = int(k * k / 4)
# 手指同光线配准：30 mm 高度横向采样
R["touch"] = {"lateral_sample_at_30mm_mm": round(30 * math.radians(designs["Ω-1（第一代）"]["dtheta_deg"]), 2),
              "baseline_mm": AP[0], "depth_res_at_30mm_mm_est": round(30 ** 2 * math.radians(designs["Ω-1（第一代）"]["dtheta_deg"]) / AP[0] / 4, 3)}
json.dump(R, open(os.path.join(HERE, "results_v2.json"), "w"), ensure_ascii=False, indent=1)
print(json.dumps(R, ensure_ascii=False, indent=1))

# ---------------- v2.2：2 mm 卡内全天电池 + 能量卡套 ----------------
E_card = 80 * 49 * 1e-2 * 1.55 / 10 * 600 / 1000         # Wh，1.55 mm 软包，600 Wh/L（v2.4，3 mm 双孔）
E_sleeve = 15.0; eta_sleeve = 0.75                          # 卡套 15 Wh，卡套→卡无线传输效率
E_day = 19.5 * Ptot["待机（eDRX 蜂窝 + 唤醒无线电）"] + 2.2 * Ptot["私密 2D/3D（只照亮主人瞳孔）"] + 1.0 * Ptot["共享 2D（孔面图像，任意角度）"] \
        + 0.8 * Ptot["共享 3D 广播（9 偏置态，被发现者逐眼锐化）"] + 0.5 * Ptot["蜂窝通话（面板发声）"]
R["v22"] = {"E_card_Wh": round(E_card, 2), "E_day_Wh": round(E_day, 2), "card_days": round(E_card / E_day, 2),
            "card_days_if_power_x2": round(E_card / E_day / 2, 2),
            "runtime_h": {k: round(E_card / v, 1) for k, v in Ptot.items() if v > 0.005},
            "standby_days": round(E_card / Ptot["待机（eDRX 蜂窝 + 唤醒无线电）"] / 24, 1),
            "sleeve_recharges": round(E_sleeve * eta_sleeve / E_card, 1),
            "total_days_card_plus_sleeve": round((E_card + E_sleeve * eta_sleeve) / E_day, 1),
            "total_days_if_power_x2": round((E_card + E_sleeve * eta_sleeve) / E_day / 2, 1),
            "sleeve_thickness_mm_at_650WhL_92x58": round(E_sleeve / 0.65 / (9.2 * 5.8) * 10, 1),
            "charge_min_at_5W_eff75": round(E_card / (5 * 0.75) * 60)}
json.dump(R, open(os.path.join(HERE, "results_v2.json"), "w"), ensure_ascii=False, indent=1)
print(json.dumps(R["v22"], ensure_ascii=False))
