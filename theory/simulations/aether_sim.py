"""
Project AETHER — 第一性原理数值检验
每一节对应报告中的一个推演步骤。运行：python3 aether_sim.py
输出：figs/*.png 与 results.json
"""
import json, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(HERE, "figs"); os.makedirs(FIG, exist_ok=True)
for f in ["/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"]:
    if os.path.exists(f):
        font_manager.fontManager.addfont(f)
        plt.rcParams["font.family"] = ["WenQuanYi Zen Hei", "DejaVu Sans"]
plt.rcParams.update({"axes.unicode_minus": False, "figure.dpi": 130,
                     "axes.grid": True, "grid.alpha": .25, "font.size": 10})
C = ["#1f5f8b", "#c0582b", "#3d8b5a", "#8a5fbf", "#7a7a7a"]
R = {}

# 常数
c0, h_pl = 2.998e8, 6.626e-34
KM = 683.0                  # lm/W @555 nm
V532 = 0.88                 # 明视觉函数 V(532 nm)
CARD = (85.6e-3, 54.0e-3)   # 卡片尺寸 m

# ---------------------------------------------------------------------------
# S1 干净空气的瑞利散射：一束光在空气里能有多亮？
# ---------------------------------------------------------------------------
lam = 532e-9
N = 2.547e25                        # 分子数密度 m^-3 (15 °C, 1 atm)
n = 1 + 2.78e-4
Fk = 1.05                           # King 修正
sigma = 24*np.pi**3/(lam**4*N**2)*((n**2-1)/(n**2+2))**2*Fk
beta = N*sigma                      # 散射系数 m^-1
a = 0.5e-3                          # 体素尺寸
phase90 = 3/(16*np.pi)              # 瑞利相函数 @90°，sr^-1
# 侧视一条宽度 a 的光束：亮度 L = P·β·p(90°)/a
L_per_W = beta*phase90/a*KM*V532    # cd/m² per W
P_for_100 = 100/L_per_W
R["S1"] = dict(sigma_m2=sigma, beta_per_m=beta, mean_free_path_km=1/beta/1e3,
               frac_scattered_per_voxel=beta*a,
               luminance_cd_m2_per_W=L_per_W, power_for_100cdm2_W=P_for_100)

# 光子-光子散射（QED, Euler-Heisenberg），可见光量级的截面
alpha = 1/137.036; re = 2.818e-15; me_c2 = 0.511e6
E = h_pl*c0/lam/1.602e-19                       # eV
sigma_gg = 0.031*alpha**2*re**2*(E/me_c2)**6     # 低能近似 (973/10125π)α²r_e²(ω/m)^6
R["S1"]["photon_photon_sigma_m2"] = sigma_gg

# ---------------------------------------------------------------------------
# S2 空气击穿等离子体体素（非线性路线）
# ---------------------------------------------------------------------------
I_th = 1e18                 # W/m² (1e14 W/cm²) fs 击穿量级
tau = 100e-15
w = 5e-6                    # 焦斑半径
E_pulse = I_th*tau*np.pi*w**2
voxels, fps = 2000, 20
P_avg = E_pulse*voxels*fps
MPE_800nm_W = 0.4e-3*1.0    # 7 mm 瞳孔、连续暴露近似 Class 1 AEL 量级
R["S2"] = dict(E_pulse_uJ=E_pulse*1e6, avg_power_W=P_avg,
               ratio_to_class1=P_avg/MPE_800nm_W)

# ---------------------------------------------------------------------------
# S3 用声波/热在空气中“写”出光学结构：最大偏折角
# ---------------------------------------------------------------------------
p_ac = 5e3                          # 5 kPa 已是很强的空中超声
dn = (n-1)*p_ac/101325
for f_us in (40e3, 200e3, 1e6):
    lam_s = 343/f_us
    R.setdefault("S3", {})[f"{int(f_us/1e3)}kHz"] = dict(
        dn=dn, grating_deflection_rad=lam/lam_s,
        phase_over_30mm_rad=2*np.pi/lam*dn*0.03)

# ---------------------------------------------------------------------------
# S4 可见性定理：无物质的空中实像，观察方向必须“穿回”卡片孔径
# ---------------------------------------------------------------------------
def visible(P, u):
    """P: 像点 (x,y,z)；u: 指向观察者的单位向量 (z>0)。返回反向射线是否打在卡片上"""
    t = P[2]/u[..., 2]
    x = P[0]-t*u[..., 0]; y = P[1]-t*u[..., 1]
    return (np.abs(x) <= CARD[0]/2) & (np.abs(y) <= CARD[1]/2)

th = np.radians(np.linspace(0.01, 89.9, 400)); ph = np.radians(np.linspace(0, 360, 721))
TH, PH = np.meshgrid(th, ph, indexing="ij")
U = np.stack([np.sin(TH)*np.cos(PH), np.sin(TH)*np.sin(PH), np.cos(TH)], -1)
dOm = np.sin(TH)*(th[1]-th[0])*(ph[1]-ph[0])
fig, axs = plt.subplots(1, 3, subplot_kw=dict(projection="polar"), figsize=(10.5, 3.8))
fig.subplots_adjust(wspace=0.35)
hs = [5e-3, 15e-3, 30e-3]; S4 = {}
for ax, h in zip(axs, hs):
    vis = visible(np.array([0, 0, h]), U)
    ax.pcolormesh(PH, np.degrees(TH), vis, cmap="Blues", vmin=-.3, vmax=1.2, shading="auto")
    ax.set_thetagrids([0, 90, 180, 270], ["长边", "", "", ""]); ax.set_ylim(0, 90); ax.set_yticks([30, 60, 90]); ax.set_yticklabels(["30°", "60°", "90°"])
    ax.set_title(f"像点高度 h = {h*1e3:.0f} mm", pad=12)
    ax.plot(np.radians(np.linspace(0, 360, 200)), np.full(200, 51.3), color=C[1], lw=1.2, ls="--")
    S4[f"h{int(h*1e3)}mm"] = dict(
        hemisphere_fraction=float((vis*dOm).sum()/(2*np.pi)),
        half_angle_short_axis_deg=float(np.degrees(np.arctan(CARD[1]/2/h))),
        half_angle_long_axis_deg=float(np.degrees(np.arctan(CARD[0]/2/h))))
fig.suptitle("图 2  空中实像的可见方向（蓝色）。极径 = 偏离竖直方向的角度；虚线 = 坐着看桌面卡片的典型视线 51°", y=1.02, fontsize=10)
fig.savefig(os.path.join(FIG, "fig2_view_cone.png"), bbox_inches="tight", facecolor="white"); plt.close(fig)
# 物质散射体：4π 可见
R["S4"] = S4

# ---------------------------------------------------------------------------
# S5 孔径光场：分辨率随悬浮高度 z 的退化 + 像素/带宽预算
# ---------------------------------------------------------------------------
z = np.linspace(0, 40e-3, 200)
fig, ax = plt.subplots(figsize=(6.4, 3.6))
S5 = {}
for i, (p, dth) in enumerate([(0.5e-3, np.radians(1.0)), (0.3e-3, np.radians(0.5)), (0.2e-3, np.radians(0.25))]):
    dif = lam/p
    blur = np.sqrt(p**2 + (z*dth)**2 + (z*dif)**2)
    ax.plot(z*1e3, blur*1e3, color=C[i], lw=2, label=f"透镜单元 {p*1e3:.1f} mm，角采样 {np.degrees(dth):.2f}°")
    fov = np.radians(90)
    n_views = (fov/dth)**2
    n_lens = (CARD[0]/p)*(CARD[1]/p)
    sub = p/(fov/dth)
    S5[f"p{p*1e3:.1f}_d{np.degrees(dth):.2f}"] = dict(
        lenslets=n_lens, views_per_lenslet=n_views, subpixels=n_lens*n_views,
        subpixel_pitch_um=sub*1e6, blur_at_30mm_mm=float(np.interp(30e-3, z, blur)*1e3),
        raw_Tbps_60Hz_24bit=n_lens*n_views*60*24/1e12,
        rays_per_pupil_at_500mm=float(4e-3/(0.5*dth)))
ax.set_xlabel("像点离卡面高度 z (mm)"); ax.set_ylabel("体素尺寸 (mm)")
ax.set_title("图 3  孔径光场：体素尺寸随悬浮高度增长", fontsize=10); ax.legend(fontsize=8)
fig.savefig(os.path.join(FIG, "fig3_lightfield_blur.png"), bbox_inches="tight", facecolor="white"); plt.close(fig)
# 相干全息作比较：±45° 视角所需像素
pitch_holo = lam/(2*np.sin(np.radians(45)))
S5["coherent_holo"] = dict(pitch_um=pitch_holo*1e6,
                           pixels=(CARD[0]/pitch_holo)*(CARD[1]/pitch_holo))
# 眼动追踪后只需点亮朝向瞳孔的子像素
S5["eye_tracked_active_fraction"] = 4 * (np.radians(0.5)**2) / (np.radians(90)**2)
R["S5"] = S5

# ---------------------------------------------------------------------------
# S6 声悬浮散射体：卡片尺寸 40 kHz 相控阵的 Gor'kov 势与捕获力
# ---------------------------------------------------------------------------
rho0, cs = 1.2, 343.0
def array_field(f, pitch, nx, ny, A, r_el, focus, twin=True, grid=None):
    k = 2*np.pi*f/cs
    xs = (np.arange(nx)-(nx-1)/2)*pitch; ys = (np.arange(ny)-(ny-1)/2)*pitch
    EX, EY = np.meshgrid(xs, ys, indexing="ij"); EX = EX.ravel(); EY = EY.ravel()
    d_f = np.sqrt((focus[0]-EX)**2+(focus[1]-EY)**2+focus[2]**2)
    phase = -k*d_f + (np.pi*(EX > focus[0]) if twin else 0)   # 双阱：一半阵列反相
    X, Y, Z = grid
    p = np.zeros(X.shape, complex)
    for ex, ey, ph_ in zip(EX, EY, phase):
        dx, dy = X-ex, Y-ey; d = np.sqrt(dx**2+dy**2+Z**2)
        st = np.sqrt(dx**2+dy**2)/d; arg = k*r_el*st+1e-9
        from scipy.special import j1
        D = 2*j1(arg)/arg
        p += A*D/d*np.exp(1j*(k*d+ph_))
    return p, k, len(EX)

def gorkov(p, k, f, rp, rho_p, c_p, h):
    w_ = 2*np.pi*f; V = 4/3*np.pi*rp**3
    f1 = 1-(rho0*cs**2)/(rho_p*c_p**2); f2 = 2*(rho_p-rho0)/(2*rho_p+rho0)
    gx, gy, gz = np.gradient(p, h, h, h)
    v2 = (abs(gx)**2+abs(gy)**2+abs(gz)**2)/(rho0*w_)**2
    U = V*(f1*abs(p)**2/(4*rho0*cs**2) - 3*f2*rho0*v2/8)
    Fx, Fy, Fz = [-g for g in np.gradient(U, h, h, h)]
    return U, Fx, Fy, Fz

f40 = 40e3; h = 0.4e-3
zf = 25e-3
xg = np.arange(-8e-3, 8e-3+h/2, h); zg = np.arange(zf-8e-3, zf+8e-3+h/2, h)
X, Y, Z = np.meshgrid(xg, xg, zg, indexing="ij")
p, k, nel = array_field(f40, 10.0e-3, 8, 5, A=8.0, r_el=4.5e-3, focus=(0, 0, zf), grid=(X, Y, Z))
rp = 0.75e-3; rho_p = 30.0; c_p = 900.0     # 发泡聚苯乙烯小球 1.5 mm
U, Fx, Fy, Fz = gorkov(p, k, f40, rp, rho_p, c_p, h)
m = rho_p*4/3*np.pi*rp**3; W = m*9.81
ix0 = len(xg)//2
# 在 x 方向（双阱分界方向）和 z 方向的恢复力曲线
Fx_line = Fx[:, ix0, :]; Fz_line = Fz[ix0, ix0, :]
# 找势能极小点（阱心）
Uc = U[ix0-5:ix0+6, ix0-5:ix0+6, :]
iz = np.argmin(U[ix0, ix0, :]); z_trap = zg[iz]
Fx_c = Fx[:, ix0, iz]; Fz_c = Fz[ix0, ix0, :]
F_lat = float(np.max(np.abs(Fx_c))); F_ax = float(np.max(-Fz_c[iz:]))  # 向下拉回
p_max = float(abs(p).max())
a_lat = F_lat/m
v_R10 = np.sqrt(a_lat*0.4*10e-3)   # 0.4 安全系数, 弯曲半径 10 mm
S6 = dict(elements=nel, p_max_Pa=p_max, SPL_dB=20*np.log10(p_max/np.sqrt(2)/20e-6),
          bead_mass_ug=m*1e9, weight_uN=W*1e6, F_lateral_uN=F_lat*1e6, F_axial_restore_uN=F_ax*1e6,
          lateral_over_weight=F_lat/W, a_lat_m_s2=a_lat, v_curve_R10mm=v_R10, z_trap_mm=z_trap*1e3)
# POV 体素预算
for npart in (1, 4, 16):
    for v in (0.5, 1.0, 2.0):
        S6[f"voxels_per_frame_N{npart}_v{v}"] = npart*v*(1/20)/1e-3   # 20 Hz、1 mm 体素
R["S6"] = S6

fig, axs = plt.subplots(1, 2, figsize=(10, 3.8))
ext = [xg[0]*1e3, xg[-1]*1e3, zg[0]*1e3, zg[-1]*1e3]
im = axs[0].imshow((U[:, ix0, :].T*1e9), origin="lower", extent=ext, aspect="equal", cmap="viridis")
axs[0].plot(0, z_trap*1e3, "w+", ms=10)
axs[0].set_xlabel("x (mm)"); axs[0].set_ylabel("离卡面高度 z (mm)")
axs[0].set_title("Gor'kov 势 U (nJ)，白十字为阱心", fontsize=9); fig.colorbar(im, ax=axs[0], shrink=.8)
axs[1].plot(xg*1e3, Fx_c*1e6, color=C[0], lw=2, label="横向力 Fx（过阱心）")
axs[1].plot((zg-z_trap)*1e3, Fz_c*1e6, color=C[1], lw=2, label="轴向力 Fz（过阱心）")
axs[1].axhline(-W*1e6, color=C[4], ls="--", lw=1, label=f"小球重量 {W*1e6:.2f} µN")
axs[1].set_xlabel("离阱心位移 (mm)"); axs[1].set_ylabel("力 (µN)")
axs[1].set_title("恢复力 vs 位移", fontsize=9); axs[1].legend(fontsize=8)
fig.suptitle("图 4  卡片尺寸 40 kHz 阵列（8×5 单元）在 25 mm 高度形成的双阱", fontsize=10, y=1.0)
fig.tight_layout(); fig.savefig(os.path.join(FIG, "fig4_acoustic_trap.png"), bbox_inches="tight", facecolor="white"); plt.close(fig)

# 空气超声吸收（ISO 9613-1，20 °C，50 % RH）—— 卡片尺度路径允许更高频率
def iso9613(f, T=293.15, RH=50, pa=101.325):
    T0, T01, pr = 293.15, 273.16, 101.325
    C_ = -6.8346*(T01/T)**1.261+4.6151
    hmol = RH*10**C_*(pa/pr)
    frO = pa/pr*(24+4.04e4*hmol*(0.02+hmol)/(0.391+hmol))
    frN = pa/pr*(T/T0)**-0.5*(9+280*hmol*np.exp(-4.170*((T/T0)**(-1/3)-1)))
    return 8.686*f**2*((1.84e-11*(pr/pa)*(T/T0)**0.5) + (T/T0)**-2.5*(
        0.01275*np.exp(-2239.1/T)/(frO+f**2/frO) + 0.1068*np.exp(-3352/T)/(frN+f**2/frN)))
fr = np.logspace(np.log10(20e3), np.log10(1e6), 200)
R["S6_absorption_dB_per_m"] = {f"{int(f/1e3)}kHz": float(iso9613(f)) for f in (40e3, 100e3, 200e3, 300e3, 500e3)}
fig, ax = plt.subplots(figsize=(6.4, 3.4))
ax.loglog(fr/1e3, iso9613(fr)*0.05, color=C[0], lw=2, label="5 cm 路径损耗")
ax.loglog(fr/1e3, iso9613(fr)*1.0, color=C[4], lw=1.5, ls="--", label="1 m 路径损耗（房间尺度）")
ax.axhline(3, color=C[1], lw=1); ax.text(22, 3.4, "3 dB", color=C[1], fontsize=8)
ax.set_xlabel("超声频率 (kHz)"); ax.set_ylabel("空气吸收 (dB)")
ax.set_title("图 5  空气对超声的吸收：卡片尺度（5 cm）可以用到 ~300 kHz", fontsize=10); ax.legend(fontsize=8)
fig.savefig(os.path.join(FIG, "fig5_us_absorption.png"), bbox_inches="tight", facecolor="white"); plt.close(fig)

# ---------------------------------------------------------------------------
# S7 亮度/功耗预算
# ---------------------------------------------------------------------------
L_target = 300            # cd/m²，室内可读
S_img = 20e-4             # 可见像表面投影面积 20 cm²
half = np.radians(50)
Phi_full = L_target*S_img*np.pi*np.sin(half)**2         # lm，不追踪眼睛
eff_sys = 15              # lm/W 系统电光效率（微LED+透镜+驱动损耗，保守）
Phi_eye = L_target*S_img*np.pi*np.sin(np.radians(1.5))**2*2  # 每只眼约 ±1.5° 出射锥 × 2 眼
# 声悬浮体素照明：小球亮度需要补偿 POV 占空比
duty = (1e-3/1.0)/(1/20)
L_bead = 100/duty
E_bead = np.pi*L_bead/0.9                    # lux
spot = np.pi*(1.5e-3)**2
P_illum_W = E_bead*spot/300                  # 白光 ~300 lm/W
R["S7"] = dict(lightfield_flux_lm=Phi_full, lightfield_optical_power_W=Phi_full/eff_sys,
               lightfield_eyetracked_flux_lm=Phi_eye, lightfield_eyetracked_W=Phi_eye/eff_sys,
               bead_duty=duty, bead_luminance_needed=L_bead, bead_illuminance_lux=E_bead,
               bead_illum_optical_W=P_illum_W)

# ---------------------------------------------------------------------------
# S8 热预算：卡片能持续消耗多少功率？
# ---------------------------------------------------------------------------
A_surf = 2*CARD[0]*CARD[1] + 2*(CARD[0]+CARD[1])*8e-3
h_tot = 7 + 5.5           # 自然对流 + 辐射 W/m²K
for dT in (10, 15, 20):
    R.setdefault("S8", {})[f"dT{dT}K_max_W"] = A_surf*h_tot*dT
R["S8"]["area_cm2"] = A_surf*1e4
batt_Wh = 650*(CARD[0]*CARD[1]*4e-3*1e3)   # 650 Wh/L × 体积(L)，4 mm 厚电池
R["S8"]["battery_Wh_4mm"] = batt_Wh

with open(os.path.join(HERE, "results.json"), "w") as fp:
    json.dump(R, fp, indent=1, ensure_ascii=False, default=float)
print(json.dumps(R, indent=1, ensure_ascii=False, default=lambda x: float(x)))

# ---------------------------------------------------------------------------
# S9 声场功耗：每个单元的辐射声功率（含指向性），以及力-功率标度律
# ---------------------------------------------------------------------------
from scipy.special import j1 as _j1
k40 = 2*np.pi*40e3/cs; th_ = np.linspace(1e-4, np.pi/2, 4000)
arg_ = k40*4.5e-3*np.sin(th_); D_ = 2*_j1(arg_)/arg_
W_el = np.trapezoid((8.0*D_)**2/(2*rho0*cs)*2*np.pi*np.sin(th_), th_)
eta_ea = 0.2   # 空气耦合压电换能器电声效率（假设）
R["S9"] = dict(acoustic_W_per_element=W_el, acoustic_W_array=W_el*40,
               electrical_W_array_eta20=W_el*40/eta_ea,
               note="F/W 与小球尺寸无关，∝ p²/ρ_p；所需电功率 ∝ p² ∝ 加速度")
with open(os.path.join(HERE, "results.json"), "w") as fp:
    json.dump(R, fp, indent=1, ensure_ascii=False, default=float)
print(R["S9"])
