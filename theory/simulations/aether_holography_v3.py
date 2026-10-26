"""
Project AETHER — stage 7 (true holography) numbers, reproduced from closed-form physics.
Covers: H1 window law, pixel steering, space-bandwidth product, superoscillation cost,
H3 scattering-focus law, light budget, air-emission screening, N2(A) quenching.
Run: python3 aether_holography_v3.py  -> results_v3.json, figs/v3_*.png
Values marked ASSUMED or FROM_MEMORY are not measured and must be checked before citing.
"""
import json, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(HERE, "figs"); os.makedirs(FIG, exist_ok=True)
plt.rcParams.update({"figure.dpi": 130, "axes.grid": True, "grid.alpha": .25, "font.size": 10})
R = {}

h_pl, c0 = 6.626e-34, 2.998e8
CARD = (85.6e-3, 54.0e-3)                 # m
A_CARD = CARD[0] * CARD[1]

# ---------------------------------------------------------------------------
# H1 window law: angular size of the card "window" and the distance a 1.7 m figure needs
# ---------------------------------------------------------------------------
d = 0.40
th_x = 2 * np.degrees(np.arctan(CARD[0] / 2 / d))
th_y = 2 * np.degrees(np.arctan(CARD[1] / 2 / d))
R["H1"] = {"window_deg_at_40cm": [round(th_x, 1), round(th_y, 1)],
           "figure_1p7m_behind_card_m": round(1.7 / (CARD[1] / d), 1)}

# grating equation sin(theta_max) = lambda / (2 p)
lam_g = 532e-9
R["steering_deg"] = {f"{p*1e6:g}um": round(np.degrees(np.arcsin(lam_g / (2 * p))), 1)
                     for p in (3.7e-6, 2e-6, 1e-6, 0.5e-6)}

# space-bandwidth product of the card
N_max = A_CARD / (lam_g / 2) ** 2
R["card_SBP_pixels"] = float(f"{N_max:.3g}")

# ---------------------------------------------------------------------------
# Attack 1: superoscillation. Extra cycles across the pupil to fake a 0.3 rad tilt.
# Energy fraction in the superoscillating region ~ exp(-N_extra) (order of magnitude).
# ---------------------------------------------------------------------------
D_pupil, dtheta, lam = 4e-3, 0.3, 0.53e-6
N_extra = D_pupil * dtheta / lam
R["superoscillation"] = {"extra_cycles": round(N_extra), "log10_energy_fraction": round(-N_extra / np.log(10))}

# ---------------------------------------------------------------------------
# H3: walls as a random unitary scatterer. eta = (pi/4) N / N_tot ; contrast C = (pi/4) N / M
# ---------------------------------------------------------------------------
A_wall = 60.0
N_tot = A_wall / (lam_g / 2) ** 2
N_4k = 3840 * 2160 * 1.06            # ~8.8e6 controllable modes (4K phase SLM)
eta_4k = N_4k / N_tot
eta_card = N_max / N_tot
L_img, S_img = 30.0, 0.6              # cd/m^2, m^2 (dimmed room, human silhouette)
Phi_img = 2 * np.pi * L_img * S_img   # lm, emitting to both sides
R["H3"] = {"N_tot_wall_modes": float(f"{N_tot:.3g}"),
           "eta_4k_SLM": float(f"{eta_4k:.2g}"),
           "eta_card_limit": float(f"{eta_card:.2g}"),
           "image_lm": round(Phi_img),
           "card_must_emit_lm": float(f"{Phi_img/eta_card:.2g}"),
           "contrast_4k_M1e5": round(np.pi / 4 * N_4k / 1e5),
           "laser_linewidth_max_MHz": round(c0 / 10.0 / 1e6)}

# ---------------------------------------------------------------------------
# Air-emission screening: photons needed vs molecules available
# ---------------------------------------------------------------------------
P_vis = Phi_img / 683.0                        # W at 555 nm
E_ph = h_pl * c0 / 555e-9
Ndot = P_vis / E_ph
n_air = 2.5e25                                 # m^-3
V_skin = 2 * S_img * 1e-3                      # 1 mm emitting skin on both faces
N_mol = n_air * V_skin
rate = Ndot / N_mol
R["screening"] = {"photons_per_s": float(f"{Ndot:.2g}"), "molecules": float(f"{N_mol:.2g}"),
                  "photons_per_molecule_per_s": float(f"{rate:.2g}"),
                  "hours_between_emissions": round(1 / rate / 3600, 1)}

# Two-photon estimate. sigma2 is ASSUMED (order-of-magnitude placeholder, not a real line).
sigma2 = 1e-53 * 1e-8                          # cm^4 s -> m^4 s
hv = h_pl * c0 / 1064e-9                       # pump photon
# rate per molecule = sigma2 * F^2, F = I / hv  ->  I = hv * sqrt(rate / sigma2)
I_cw = hv * np.sqrt(rate / sigma2)             # W/m^2
duty = 1e-5                                    # scanning 1e5 points
I_peak = hv * np.sqrt(rate / duty / sigma2)
R["two_photon_ASSUMED_sigma2"] = {"I_cw_W_cm2": float(f"{I_cw/1e4:.2g}"),
                                  "I_peak_scan1e5_W_cm2": float(f"{I_peak/1e4:.2g}"),
                                  "below_plasma_1e13_factor": float(f"{1e13/(I_peak/1e4):.2g}")}

# N2(A) quenching by O2. k is FROM_MEMORY and must be verified.
k_q = 2.5e-12                                  # cm^3/s
n_O2 = 0.21 * n_air * 1e-6 * 0.99              # cm^-3
R["N2A_quench_FROM_MEMORY"] = {"n_O2_cm3": float(f"{n_O2:.2g}"),
                               "lifetime_ns": round(1 / (k_q * n_O2) * 1e9)}

# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------
fig, ax = plt.subplots(1, 2, figsize=(10, 3.8))
Ns = np.logspace(6, 11, 100)
ax[0].loglog(Ns, Ns / N_tot, color="#1f5f8b")
ax[0].axvline(N_4k, ls="--", color="#7a7a7a"); ax[0].text(N_4k * 1.2, 1e-9, "4K SLM", fontsize=8)
ax[0].axvline(N_max, ls="--", color="#c0582b"); ax[0].text(N_max / 30, 1e-9, "card limit", fontsize=8)
ax[0].set_xlabel("controllable modes N"); ax[0].set_ylabel("focusing efficiency  N/N_tot")
ax[0].set_title("H3: room walls as the hologram (60 m²)")
P_need = Phi_img / (Ns / N_tot) / 683 / 0.2     # electrical W at ~20 % laser wall-plug (ASSUMED)
ax[1].loglog(Ns, P_need, color="#c0582b")
ax[1].axhline(100, ls="--", color="#3d8b5a"); ax[1].text(2e6, 130, "100 W target", fontsize=8)
ax[1].set_xlabel("controllable modes N"); ax[1].set_ylabel("laser electrical power for 113 lm (W)")
ax[1].set_title("Laser power for a human-size image (20 % wall-plug, assumed)")
fig.tight_layout(); fig.savefig(os.path.join(FIG, "v3_h3_efficiency.png")); plt.close(fig)

fig, ax = plt.subplots(figsize=(6.5, 3.6))
labels = ["plasma today", "screening\n(2-photon, scan)", "discovery\ntarget"]
vals = [1e13, I_peak / 1e4, 1e9]
ax.bar(labels, vals, color=["#7a7a7a", "#1f5f8b", "#3d8b5a"]); ax.set_yscale("log")
ax.set_ylabel("peak intensity (W/cm²)"); ax.set_title("Where the air-emission bottleneck is")
fig.tight_layout(); fig.savefig(os.path.join(FIG, "v3_screening.png")); plt.close(fig)

with open(os.path.join(HERE, "results_v3.json"), "w") as f:
    json.dump(R, f, indent=1)
print(json.dumps(R, indent=1))
