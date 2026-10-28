"""AETHER v11 (2026-10-28): recompute the conclusions that depend on constants checked online.
Each sourced value cites the page opened on 2026-10-28; see the v11 report for links."""
import math, json, os
R={}
# --- LC speed: tau = gamma1 d^2 /(K pi^2); reflective, d = lambda/(2 dn)
lam_r=635e-9; K=13e-12                      # K still unverified (typical 10-15 pN)
def tau(g,dn): d=lam_r/(2*dn); return g*d**2/(K*math.pi**2), d
cases={'v7 assumption (g1 0.15 Pa s for high-dn, dn 0.40)':(0.15,0.40),
       'sourced: E7-class g1 0.15 Pa s, dn 0.35 (UCF terphenyls)':(0.15*1.0,0.35),
       'sourced high-dn mixtures are more viscous (assume g1 0.22, dn 0.35)':(0.22,0.35)}
R['LC_room_temp']={k:dict(tau_ms=tau(*v)[0]*1e3,d_um=tau(*v)[1]*1e6,max_Hz_3tau=1/(3*tau(*v)[0])) for k,v in cases.items()}
# measured anchors (opened pages): Meadowlark UHSP 0.6 ms full wave at 532 nm with TEC 33-75 C;
# 4K2K phase LCoS (Yang et al. SID 2019) ~1-2 ms at 45 C
R['measured_anchor_ms']={'Meadowlark_UHSP_532nm_heated':0.6,'4K2K_phase_LCoS_45C':[1,2]}
for t in (0.6,1.0,1.5):
    R[f'frame_Hz_at_tau_{t}ms']=1/(3*t*1e-3)
# card needs 360 Hz (2 views) -> tau <= 0.93 ms ; TV needs 180 Hz per viewer
R['card_tau_needed_ms']=1e3/(3*360)
R['tv_viewers_LC_limited']={t:1/(3*t*1e-3)/180 for t in (0.6,1.0)}
# --- panel cost per m2 (TrendForce via TechNews, early Aug 2025)
def area(diag_in,ar=(16,9)):
    dm=diag_in*0.0254; k=dm/math.hypot(*ar); return ar[0]*k*ar[1]*k
R['usd_per_m2']={'TV_65in_173usd':173/area(65),'TV_55in_123usd':123/area(55),
                 'monitor_27in_63usd':63/area(27),'notebook_14in_26.9usd':26.9/area(14)}
R['tv_hologram_panel_usd']=[0.63*R['usd_per_m2']['monitor_27in_63usd'],0.63*R['usd_per_m2']['notebook_14in_26.9usd']]
# --- air phase-conjugate mirror with sourced electronic n2 = 8e-20 cm2/W (Zahedpour et al., 800 nm)
def Rpc(n2,I,L=0.1,lam=800e-7): return (4*math.pi*n2*I*L/lam)**2   # cm units, L=1 mm
for n2 in (3e-19,8e-20):
    R[f'R_air_n2_{n2:.0e}']={f'{I:.0e}':Rpc(n2,I) for I in (1e12,2.5e12,1e13)}
R['intensity_factor_for_same_R']=3e-19/8e-20
R['classI_pump_needed_Wcm2']=2.4e12*3e-19/8e-20
# --- speckle: sourced visibility limits 3.2-4.4 % still, 4.8-6.9 % moving (Verschaffelt et al. 2015)
for C in (0.05,0.035):
    R[f'patterns_needed_C{C}']=1/C**2
R['v10_contrast_2views']=[0.12*math.sqrt(1.5),0.16*math.sqrt(1.5)]
# --- stereoacuity sourced: geometric mean 58-73 arcsec (range 24-275), Alarcon Carrillo et al. 2020
for a in (30,60):
    s=a/3600*math.pi/180
    R[f'capture_tol_mm_stereo{a}']={'tv_3m':9*s/0.064*1e3,'card_0.47m':0.47**2*s/0.064*1e3}
json.dump(R,open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'results_v11.json'),'w'),indent=1)
print(json.dumps(R,indent=1))
