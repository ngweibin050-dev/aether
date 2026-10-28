"""AETHER v5 (2026-10-27): n-photon generalisation of Theorem G, channel screening,
and the coherent four-wave-mixing loophole. Inputs marked ASSUMED / FROM MEMORY."""
import math, json
c=2.998e8; h=6.626e-34; e=1.602e-19; n_air=2.5e25
S_req=4.63e17          # visible photons/s for 113 lm (from v4)
R={}
def c_n(n):            # integral of (1+x^2)^-(n-1) dx  (x = z/zR)
    return math.sqrt(math.pi)*math.gamma(n-1.5)/math.gamma(n-1)
# Theorem G_n:  S = eta n sigma_n I^(n-1) dz c_n P_avg / (2 n (h nu)^n)   [SI: I W/m2, sigma_n m^2n s^(n-1)]
s1,tau=1e-21,1e-16
def sigma_req(n,lam,I_Wcm2,dz,P,eta=1.0):
    hv=h*c/lam; I=I_Wcm2*1e4
    return 2*n*S_req*hv**n/(eta*n_air*I**(n-1)*dz*c_n(n)*P)
def I_req(n,lam,dz,P,eta):   # uses generic sigma_n in log space (avoids underflow)
    hv=h*c/lam
    lg=(math.log(2*n*S_req)+n*math.log(hv)-math.log(eta*n_air*dz*c_n(n)*P)
        -(n*math.log(s1)+(n-1)*math.log(tau)))
    return math.exp(lg/(n-1))/1e4  # W/cm2
# generic non-resonant scaling (ASSUMED): sigma_n ~ s^n tau^(n-1), s=1e-21 m^2 (1e-17 cm^2), tau=1e-16 s
s1,tau=1e-21,1e-16
def sigma_generic(n): return s1**n*tau**(n-1)
# sanity check against known air ionisation: O2 IP 12.07 eV at 800 nm -> n=8, 100 fs
F=1e14*1e4/(h*c/800e-9)       # photons m^-2 s^-1 at 1e14 W/cm2
R['check_O2_ionisation_prob_100fs_at_1e14']=sigma_generic(8)*F**8*100e-15
# gate check: n=2 reproduces Theorem G
R['check_n2_GM']=sigma_req(2,1550e-9,1e11,1e-3,10)*1e58
# required intensity per channel (P=10 W, dz=1 mm)
ch=[ # name, threshold eV, visible-photon yield eta (FROM MEMORY / ESTIMATE), note
 ('N2 B3Pg -> first positive red (via triplet, spin-forbidden)',7.35,1e-3*1e-5,'eta ~ quench(1e-3) x spin factor(1e-5)'),
 ('N2+ B -> 391/428 nm (needs ionisation)',18.7,1e-2,'reached only through ionisation'),
 ('O(1S) 557.7 nm from O2 dissociation',9.3,1e-6,'1S quenched in air'),
 ('O2 b 762 nm, two-photon, spin-forbidden',1.63,1e-5*6e-5/1.0,'spin x luminous penalty'),
 ('H2O -> OH(A) 309 nm (UV, not visible)',9.1,0.0,'UV'),
]
out=[]
for name,E,eta,note in ch:
    for lam in (1550e-9,1064e-9,800e-9):
        hv=h*c/lam/e; n=math.ceil(E/hv)
        if n<2 or eta==0: continue
        I=I_req(n,lam,1e-3,10,eta)
        out.append(dict(channel=name,pump_nm=round(lam*1e9),n=n,I_req_Wcm2=I,note=note))
R['channels']=out
# coherent loophole: degenerate four-wave mixing (phase conjugation) in air, visible pumps
n2=3e-23; lam=532e-9
for I in (1e11,1e12,1e13):
    kap=4*math.pi/lam*n2*I*1e4; R[f'DFWM_R_L1mm_I{I:.0e}']=(kap*1e-3)**2
# momentum cone: single card, P at distance hP, aperture half-width a -> beta
for hP in (0.3,1.0):
    beta=math.degrees(math.atan(0.0428/hP)); R[f'cone_beta_deg_h{hP}']=beta; R[f'DFWM_max_output_deg_h{hP}']=2*beta
# eye check: visible pump average needed and Rayleigh streak vs signal
R_dfwm=(4*math.pi/lam*n2*1e16*1e-3)**2
P_sig_eye=1.15e-7; R['probe_avg_W']=P_sig_eye/R_dfwm
beta_R=1.3e-5   # 1/m Rayleigh extinction at 532 nm (FROM MEMORY, sea level)
P_pump=0.3; Ap=math.pi*(2e-3)**2
R['rayleigh_into_pupil_W_per_m_at_1m']=P_pump*beta_R*Ap/(4*math.pi*1.0**2)
R['signal_per_voxel_W_M1e5']=P_sig_eye/1e5
json.dump(R,open('/mnt/project-files/aether/v4/results_v5.json','w'),indent=1,default=float)
print(json.dumps(R,indent=1,default=float))
