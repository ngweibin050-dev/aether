"""AETHER theoretical dossier v4 (2026-10-27): reproducible numbers.
Every printed value is derived from the formulas in the dossier; inputs marked ASSUMED."""
import math, json
c=2.998e8; h=6.626e-34; n_air=2.5e25  # m^-3 (sea level, 20 C)
lam=532e-9                              # display wavelength
R={}
# 1. smartphone OLED as a diffractive element
p_phone=55e-6
R['phone_max_diffraction_deg']=math.degrees(math.asin(lam/(2*p_phone)))
# 2. untracked full-parallax hologram on a card, +/-30 deg
W,H=85.6e-3,54e-3
p30=lam/(2*math.sin(math.radians(30)))
R['p_for_30deg_um']=p30*1e6
R['card_pixels_untracked']=(W/p30)*(H/p30)
# 3. eye-tracked window: p = lam d / w
for d,w in [(0.4,0.010),(0.5,0.010)]:
    p=lam*d/w; R[f'tracked_pitch_um_d{d}_w{w*1e3:.0f}mm']=p*1e6
    R[f'tracked_pixels_d{d}_w{w*1e3:.0f}mm']=(W/p)*(H/p)
# 4. Miller degrees of freedom card -> pupil and card -> 10 mm window
A=W*H
for d in (0.4,0.5):
    R[f'miller_N_pupil4mm_d{d}']=A*math.pi*(2e-3)**2/(lam*d)**2
    R[f'miller_N_window10mm_d{d}']=A*(10e-3)**2/(lam*d)**2
# 5. aperture-cone half angle for a point h in front of the card (short side)
R['cone_half_angle_deg']={f'{hh*1e3:.0f}mm':math.degrees(math.atan((H/2)/hh)) for hh in (0.01,0.05,0.2)}
# 6. power: broadcast human-size image vs tracked pupils
L=30; S=0.6; R['broadcast_lm']=2*math.pi*L*S; R['broadcast_W_555']=R['broadcast_lm']/683
L2=100; Om=(0.1*0.1)/0.4**2; Ap=math.pi*(2e-3)**2
R['tracked_lm_per_eye']=L2*Ap*Om; R['tracked_W_per_eye_555']=R['tracked_lm_per_eye']/683
# 7. two-photon air emission bound
#   integral of I^2 over all space for a focused Gaussian = P^2 * pi / lam_p  (focus independent)
S_req=R['broadcast_W_555']/(h*c/555e-9)       # photons/s
R['photons_per_s_needed']=S_req
def bound(lam_p,P_avg,I_max_Wcm2,w0):
    hv=h*c/lam_p
    Cp=n_air*math.pi/(lam_p*hv**2)            # per unit sigma2 [m^4 s]
    P_pk=I_max_Wcm2*1e4*math.pi*w0**2/2
    sig=S_req/(Cp*P_pk*P_avg)                 # m^4 s
    return sig*1e8*1e50, P_pk, P_avg/P_pk     # GM, W, duty
for lam_p in (1064e-9,1550e-9):
    for P_avg,I in [(10,1e11),(100,1e11),(10,1e12)]:
        g,ppk,D=bound(lam_p,P_avg,I,27e-6)
        R[f'sigma2eta_GM_lam{lam_p*1e9:.0f}_P{P_avg}W_I{I:.0e}']=dict(GM=g,P_peak_W=ppk,duty=D)
# 8. Lorentzian tail of 2-photon emission: fraction within +/- a zR
R['frac_within_1zR']=2/math.pi*math.atan(1); R['frac_within_10zR']=2/math.pi*math.atan(10)
# 9. focus geometry for a human-size image at 1.5 m from a card-width aperture
NA=(W/2)/1.5; w0=1064e-9/(math.pi*NA); R['w0_um_1p5m']=w0*1e6; R['zR_mm_1p5m']=math.pi*w0**2/1064e-9*1e3
print(json.dumps(R,indent=1,default=float))
json.dump(R,open('/mnt/project-files/aether/v4/results_v4.json','w'),indent=1,default=float)

# 10. Theorem G in voxel form: w0^2 = lam_p*dz/(2 pi)  ->  P_pk = I_max*lam_p*dz/4
#     S = eta*n*sigma2*pi*I_max*dz*P_avg/(4 (h nu)^2)
G={}
for lam_p in (1064e-9,1550e-9):
    hv=h*c/lam_p
    for P_avg in (2,10,100):
        for I in (1e11,1e12):
            for dz in (1e-3,3e-3):
                sig=4*S_req*hv**2/(math.pi*n_air*I*1e4*dz*P_avg)
                G[f'{lam_p*1e9:.0f}nm_P{P_avg}W_I{I:.0e}_dz{dz*1e3:.0f}mm']=dict(
                    GM=sig*1e58, w0_um=math.sqrt(lam_p*dz/(2*math.pi))*1e6,
                    P_peak_kW=I*1e4*lam_p*dz/4/1e3, duty=P_avg/(I*1e4*lam_p*dz/4))
R['theoremG']=G
# luminous penalty for O2 b-state 762 nm emission (CIE V(760)=6e-5, from memory)
R['O2b_762nm_W_for_113lm']=113/(683*6e-5)
json.dump(R,open('/mnt/project-files/aether/v4/results_v4.json','w'),indent=1,default=float)
for k,v in G.items(): print(k, {a:round(b,4) if b<10 else round(b) for a,b in v.items()})
print('O2b W',R['O2b_762nm_W_for_113lm'])
