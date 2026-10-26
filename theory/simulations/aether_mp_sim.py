"""
Project AETHER — 量产方案的数值检验
1) 卡片尺度下的调节（对焦）失配：真实光场是否必要？
2) 方向层（条纹发光层 + 柱透镜）的二维光线追迹：转向角范围、角分辨率、透过率
3) 眼动追踪的时延/精度容差
4) 功耗、散热、带宽闭环
运行：python3 aether_mp_sim.py   输出：figs/mp_*.png 与 results_mp.json
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
C = ["#1f5f8b", "#c0582b", "#3d8b5a", "#8a5fbf", "#7a7a7a"]
R = {}
CARD = (85.6e-3, 54.0e-3)

# ---------------------------------------------------------------------------
# 1 调节失配 ΔD = 1/(d-h) - 1/d ；人眼景深约 ±0.3 D（瞳孔 3–4 mm），舒适区约 ±0.5 D
# ---------------------------------------------------------------------------
h = np.linspace(0, 0.10, 300)
fig, ax = plt.subplots(figsize=(6.4, 3.6))
for i, d in enumerate([0.30, 0.40, 0.50, 0.70]):
    ax.plot(h*1e3, 1/(d-h)-1/d, color=C[i], lw=2, label=f"观看距离 {d*100:.0f} cm")
ax.axhspan(0, 0.3, color=C[2], alpha=.12); ax.text(62, 0.22, "人眼景深内（±0.3 D）：分辨不出", fontsize=8, color=C[2])
ax.axhline(0.5, color=C[1], lw=1, ls="--"); ax.text(62, 0.53, "舒适区边界 0.5 D", fontsize=8, color=C[1])
ax.set_ylim(0, 1.0); ax.set_xlabel("像点离卡面高度 h (mm)"); ax.set_ylabel("对焦失配 ΔD (屈光度)")
ax.set_title("图 A  逐眼光线方案与真实光场的对焦差别", fontsize=10); ax.legend(fontsize=8, loc="upper left")
fig.savefig(os.path.join(FIG, "mp_accommodation.png"), bbox_inches="tight", facecolor="white"); plt.close(fig)
hmax = {}
for d in (0.3, 0.4, 0.5, 0.7):
    # 求 ΔD = 0.3 时的 h
    hmax[f"d{int(d*100)}cm_h_at_0.3D_mm"] = float(d - 1/(1/d+0.3))*1e3
    hmax[f"d{int(d*100)}cm_h_at_0.5D_mm"] = float(d - 1/(1/d+0.5))*1e3
R["accommodation"] = hmax

# ---------------------------------------------------------------------------
# 2 方向层光线追迹：发光条纹 → 透明基板 (n) → 周期柱透镜（非球面）→ 空气
# ---------------------------------------------------------------------------
n_l = 1.49
def make_lens(P, Rr, k):
    s0 = sag(P/2, Rr, k)
    t = n_l*Rr/(n_l-1) - s0          # 发光面放在近轴焦面上
    return dict(P=P, R=Rr, k=k, s0=s0, t=t)
def sag(r, Rr, k):
    return r**2/(Rr*(1+np.sqrt(np.maximum(1-(1+k)*r**2/Rr**2, 0))))
def dsag(r, Rr, k):
    return r/(Rr*np.sqrt(np.maximum(1-(1+k)*r**2/Rr**2, 1e-12)))
def surf(x, L):
    xc = np.round(x/L["P"])*L["P"]; r = x-xc
    return L["t"]+L["s0"]-sag(r, L["R"], L["k"]), -dsag(r, L["R"], L["k"]), xc
def trace(x0, phi, L):
    """x0: 发光点位置；phi: 介质内光线与法线夹角。返回出射角、打到的透镜中心、是否透出"""
    tp = np.tan(phi)
    lo = np.full_like(phi, L["t"]); hi = np.full_like(phi, L["t"]+L["s0"])
    for _ in range(45):
        mid = (lo+hi)/2
        F, _, _ = surf(x0+mid*tp, L)
        above = mid > F
        hi = np.where(above, mid, hi); lo = np.where(above, lo, mid)
    z = (lo+hi)/2; x = x0+z*tp
    _, dF, xc = surf(x, L)
    nx, nz = -dF, np.ones_like(dF); nn = np.hypot(nx, nz); nx, nz = nx/nn, nz/nn
    dx, dz = np.sin(phi), np.cos(phi)
    cosi = dx*nx+dz*nz
    s = 1-n_l**2*(1-cosi**2); ok = s > 0
    cost = np.sqrt(np.maximum(s, 0))
    ox = n_l*dx+(cost-n_l*cosi)*nx; oz = n_l*dz+(cost-n_l*cosi)*nz
    # 菲涅耳透过率（非偏振平均）
    ci, ct = np.clip(cosi, 0, 1), cost
    rs = ((n_l*ci-ct)/(n_l*ci+ct))**2; rp = ((n_l*ct-ci)/(n_l*ct+ci))**2
    T = np.where(ok, 1-(rs+rp)/2, 0)
    return np.degrees(np.arctan2(ox, oz)), xc, T

def stripe_response(x0, e, L, nphi=4001, nsub=9):
    phis = np.radians(np.linspace(-80, 80, nphi))
    out_a, out_w, out_lens = [], [], []
    for xs in x0+np.linspace(-e/2, e/2, nsub):
        a, xc, T = trace(np.full_like(phis, xs), phis, L)
        out_a.append(a); out_w.append(T*np.cos(phis)); out_lens.append(np.round(xc/L["P"]).astype(int))
    return np.concatenate(out_a), np.concatenate(out_w), np.concatenate(out_lens)

def evaluate(L, e, targets):
    rows = []
    xs = np.linspace(0, 1.6*L["P"], 321)     # 发光条纹相对 0 号透镜中心的偏移
    med = []
    for x0 in xs:
        a, w, ln = stripe_response(-x0, e, L, nphi=801, nsub=3)
        m = (ln == 0) & (w > 0)
        med.append(np.average(a[m], weights=w[m]) if w[m].sum() > 0 else np.nan)
    med = np.array(med)
    for tt in targets:
        i = np.nanargmin(np.abs(med-tt)); x0 = xs[i]
        a, w, ln = stripe_response(-x0, e, L)
        m0 = (ln == 0) & (w > 0)
        aa, ww = a[m0], w[m0]
        o = np.argsort(aa); aa, ww = aa[o], ww[o]; cw = np.cumsum(ww)/ww.sum()
        w80 = np.interp(0.9, cw, aa)-np.interp(0.1, cw, aa)
        eff = ww.sum()/w.sum() if w.sum() > 0 else 0
        rows.append(dict(target=float(tt), x0_um=float(x0*1e6), center=float(np.average(aa, weights=ww)),
                         w80_deg=float(w80), frac_through_lens0=float(eff)))
    return rows

targets = np.arange(0, 26, 5)
e = 25e-6
def make_g1(Rr, k, dt):
    L = make_lens(1.0e-3, Rr, k); L["t"] += dt*Rr; return L
designs = {"球面 R=0.51 mm": make_g1(0.51e-3, 0.0, 0.0),
           "非球面 k=-0.2（选定）": make_g1(0.51e-3, -0.2, -0.12)}
DR = {name: evaluate(L, e, targets) for name, L in designs.items()}
R["steering"] = {name: dict(lens={k: float(v) for k, v in designs[name].items()}, rows=DR[name]) for name in DR}
fig, axs = plt.subplots(1, 2, figsize=(10, 3.7))
for i, name in enumerate(DR):
    rows = DR[name]
    axs[0].plot([r["center"] for r in rows], [r["w80_deg"] for r in rows], "o-", color=C[i], lw=2, ms=4, label=name)
    axs[1].plot([r["center"] for r in rows], [r["frac_through_lens0"]*100 for r in rows], "o-", color=C[i], lw=2, ms=4, label=name)
axs[0].axhline(np.degrees(0.063/0.5), color=C[1], ls="--", lw=1)
axs[0].text(1, np.degrees(0.063/0.5)+0.3, "50 cm 处双眼间距张角 7.2°", fontsize=8, color=C[1])
axs[0].set_xlabel("出射方向 (°)"); axs[0].set_ylabel("一个 25 µm 发光点的 80% 能量角宽 (°)")
axs[0].set_title("角分辨率随转向角的退化", fontsize=9); axs[0].legend(fontsize=8)
axs[1].set_xlabel("出射方向 (°)"); axs[1].set_ylabel("经本透镜出射的比例（一维）(%)")
axs[1].set_title("光效（含菲涅耳与全反射损失）", fontsize=9)
fig.suptitle("图 B  方向背光光线追迹：透镜 1.0 mm，R = 0.51 mm，n = 1.49，带挡光墙，发光点 25 µm", fontsize=10, y=1.0)
fig.tight_layout(); fig.savefig(os.path.join(FIG, "mp_steering.png"), bbox_inches="tight", facecolor="white"); plt.close(fig)

# 光线示意图
L = designs["非球面 k=-0.2（选定）"]
fig, ax = plt.subplots(figsize=(6.4, 3.4))
xx = np.linspace(-1.5*L["P"], 1.5*L["P"], 900); F, _, _ = surf(xx, L)
ax.plot(xx*1e3, F*1e3, color="k", lw=1.2); ax.axhline(0, color="k", lw=1)
for tt, col in [(0, C[0]), (15, C[2]), (25, C[1])]:
    row = [r for r in DR["非球面 k=-0.2（选定）"] if r["target"] == tt][0]
    x0 = -row["x0_um"]*1e-6
    phis = np.radians(np.linspace(-60, 60, 61))
    a, xc, T = trace(np.full_like(phis, x0), phis, L)
    sel = (np.round(xc/L["P"]) == 0) & (T > 0)
    for ph, aa in zip(phis[sel][::3], a[sel][::3]):
        tp = np.tan(ph); lo, hi = L["t"], L["t"]+L["s0"]
        for _ in range(40):
            mid = (lo+hi)/2; Fm, _, _ = surf(np.array([x0+mid*tp]), L)
            lo, hi = (lo, mid) if mid > Fm[0] else (mid, hi)
        zh = (lo+hi)/2; xh = x0+zh*tp
        ax.plot([x0*1e3, xh*1e3], [0, zh*1e3], color=col, lw=.6)
        ax.plot([xh*1e3, xh*1e3+1.2*np.sin(np.radians(aa))], [zh*1e3, zh*1e3+1.2*np.cos(np.radians(aa))], color=col, lw=.6)
    ax.plot(x0*1e3, 0, "o", color=col, ms=4, label=f"转向 {tt}°")
ax.set_aspect("equal"); ax.set_xlim(-1.6, 1.6); ax.set_ylim(-0.1, 3.0)
ax.set_xlabel("x (mm)"); ax.set_ylabel("z (mm)"); ax.legend(fontsize=8, loc="upper left")
ax.set_title("图 C  同一透镜下，点亮不同位置的发光点即改变出射方向", fontsize=10)
fig.savefig(os.path.join(FIG, "mp_raytrace.png"), bbox_inches="tight", facecolor="white"); plt.close(fig)

# ---------------------------------------------------------------------------
# 3 眼动追踪容差（逐眼时分复用；每个时隙只有一只眼的光窗被点亮）
# ---------------------------------------------------------------------------
d = 0.5; pupil = 4e-3; ipd = 63e-3
w80 = max(r["w80_deg"] for r in DR["非球面 k=-0.2（选定）"])
blur = np.radians(w80)*d                 # 光窗边缘的模糊宽度
core = 20e-3                             # 光窗核心宽度：瞳孔 + 跟踪余量
half_footprint = core/2 + blur/2
R["tracking"] = dict(w80_max_deg=float(w80), blur_mm=blur*1e3, window_core_mm=core*1e3,
                     spill_half_width_mm=half_footprint*1e3, other_eye_distance_mm=ipd*1e3,
                     crosstalk_free=bool(half_footprint < ipd-pupil/2),
                     margin_mm=(core-pupil)/2*1e3,
                     latency_ms_head_0p3=(core-pupil)/2/0.3*1e3, latency_ms_head_0p6=(core-pupil)/2/0.6*1e3,
                     fov_half_deg=25)

# ---------------------------------------------------------------------------
# 4 Gen-1 功耗 / 带宽 / 散热闭环（辐亮度守恒模型）
# ---------------------------------------------------------------------------
A = CARD[0]*CARD[1]
L_eye = 250.0                       # 观看亮度 cd/m²
T_lcd = 0.06                        # 彩色 LCD 透过率
tau = 0.9                           # 透镜透过
slots = 4                           # 4 只眼（2 人）时分复用
L_peak = L_eye/(T_lcd*tau)*slots    # 发光点峰值亮度
e_pitch = 25e-6
lit_per_lens = 4                    # 每个透镜每只眼点亮 2×2 个发光点
n_lens = (CARD[0]/1e-3)*(CARD[1]/1e-3)
A_lit = lit_per_lens*e_pitch**2*n_lens
flux_avg = np.pi*L_peak*A_lit       # 每个时隙一只眼；时间平均 = 一只眼的峰值通量
eff_oled = 50.0                     # lm/W，叠层白光 OLED（保守）
emitters = (CARD[0]/e_pitch)*(CARD[1]/e_pitch)
R["gen1"] = dict(steering_emitters=emitters, steering_ppi=25.4e-3/e_pitch, lenses=n_lens,
                 lcd_pixels=(CARD[0]/0.1e-3)*(CARD[1]/0.1e-3),
                 lcd_Gbps_240Hz=(CARD[0]/0.1e-3)*(CARD[1]/0.1e-3)*240*24/1e9,
                 L_peak_cd_m2=L_peak, flux_avg_lm=flux_avg, steer_emission_W=flux_avg/eff_oled)
budget = {"方向背光发光 (白光 OLED)": flux_avg/eff_oled, "方向背光 LTPS 驱动 (7.4M 点, 240 Hz)": 0.30,
          "彩色 LCD + 驱动 (240 Hz，无普通背光)": 0.25, "两颗全局快门红外相机 + 红外 LED": 0.30,
          "SoC：眼/手追踪 + 4 路渲染": 0.70, "Wi-Fi/蓝牙": 0.15}
budget["电源转换损耗 (~12%)"] = 0.12*sum(budget.values())
R["gen1"]["power_budget_W"] = budget; R["gen1"]["power_total_W"] = sum(budget.values())
batt_Wh = 650*(CARD[0]*CARD[1]*3e-3*1e3)
R["gen1"]["battery_Wh_3mm"] = batt_Wh; R["gen1"]["runtime_h"] = batt_Wh/sum(budget.values())
A_surf = 2*A + 2*(CARD[0]+CARD[1])*9e-3
R["gen1"]["thermal_dT_K"] = sum(budget.values())/(A_surf*12.5)

with open(os.path.join(HERE, "results_mp.json"), "w") as fp:
    json.dump(R, fp, indent=1, ensure_ascii=False, default=float)
print(json.dumps(R, indent=1, ensure_ascii=False, default=float))
