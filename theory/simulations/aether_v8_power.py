"""AETHER v8 (2026-10-27): card power budget and battery life. Inputs marked FROM MEMORY / ASSUMED."""
import math, json
R={}
# 1. light needed into each eye (Theorem D), card at 0.4 m
A_card=0.0856*0.054; d=0.4; Om=A_card/d**2; A_pup=math.pi*(2e-3)**2
for L in (200,1000):                      # cd/m2 indoor / outdoor
    lm=L*A_pup*Om; R[f'eye_W_at_{L}nit']=lm/300   # white RGB ~300 lm/W optical (ASSUMED)
# window fills the SLM diffraction cone by design (p = lambda d / w) -> no steering loss
eta_opt=0.10                               # SLM refl x diffraction x waveguide (ASSUMED)
P_opt_src=2*R['eye_W_at_1000nit']/eta_opt
R['source_optical_W_outdoor']=P_opt_src
# coherence a sub-hologram needs (card: s=2 mm, z=0.1 m)
s=2e-3; z=0.1; lam=530e-9
dL=(s/2)**2/(2*z); R['path_diff_um']=dL*1e6; R['max_linewidth_nm']=lam**2/dL*1e9
R['max_source_angle_mrad']=lam/s*1e3; R['uLED_size_um_for_f40mm']=lam/s*40e-3*1e6
# laser threshold floor: 3 diodes x ~30 mA x ~2.5-5 V, colour duty 1/3 (FROM MEMORY)
R['edge_laser_floor_W']=[3*0.03*2.5/3,3*0.06*5/3]
# 2. panel drive (1D card): pixel + data-line charging
eps0=8.854e-12; er=10; dLC=0.8e-6
for name,Ncol,Nline,f,pw,ph in (('1D',3000,856,180,18e-6,100e-6),('2D',4756,3000,360,18e-6,18e-6)):
    Cpix=eps0*er*pw*ph/dLC*2           # x2 storage cap
    for V in (3,5):
        Ppix=Ncol*Nline*Cpix*V**2*f*0.5
        Pline=Ncol*20e-12*V**2*(Nline*f)*0.5   # 20 pF per data line (ASSUMED)
        R[f'panel_{name}_{V}V_W']=Ppix+Pline
# 3. hologram compute (eye-limited scene points)
Npts=(math.degrees(0.0856/d)*60)*(math.degrees(0.054/d)*60)   # 1 arcmin
sub=int(s/18e-6)
R['scene_points']=Npts; R['subholo_px_1D']=sub
mac1=Npts*sub*180; mac2=Npts*sub**2*360
R['MAC_per_s_1D']=mac1; R['MAC_per_s_2D']=mac2
for name,m in (('1D',mac1),('2D',mac2)):
    fl=m*8
    R[f'compute_{name}_W_mobileGPU_100GFLOPperW']=fl/100e9
    R[f'compute_{name}_W_ASIC_1pJperMAC']=m*4e-12   # complex MAC ~4 real ops at ~1 pJ (ASSUMED)
# 4. LC heating to 45 C on a card (convection+radiation ~16 W/m2K, both faces)
R['heat_card_45C_W']=2*A_card*16*20
# 5. thermal ceiling for a card at 10 K skin rise
R['thermal_cap_W_dT10']=2*A_card*16*10
# 6. battery = (card thickness - 2 mm stack) x 46 cm2 x 0.8 fill x 400-600 Wh/L (ASSUMED stack)
bat={t:[(t-2)*0.1*46*0.8/1000*e for e in (400,600)] for t in (3,4,5)}
R['battery_Wh_by_card_mm']=bat
# 7. budgets (W): viewing = light, panel, compute, tracking, system; call adds radio, 3D decode, audio
view=[0.005+0.05+0.05+0.02+0.08, 0.06+0.15+0.5+0.15+0.15]   # light, panel, compute, tracking, system
call=[view[0]+0.4, view[1]+0.8]                               # + radio, 3D decode, audio
R['view_W']=view; R['call_W_v2']=call
R['view_hours']={t:[b[0]/view[1],b[1]/view[0]] for t,b in bat.items()}
R['call_hours']={t:[b[0]/call[1],b[1]/call[0]] for t,b in bat.items()}
R['day_1hcall_3hview_Wh']=[call[0]+3*view[0]+0.3, call[1]+3*view[1]+0.3]
import os
json.dump(R,open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'results_v8.json'),'w'),indent=1)
print(json.dumps(R,indent=1))
