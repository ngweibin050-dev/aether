"""AETHER v12 (2026-10-28): card with horizontally incoherent views.
Vertical: 1D hologram (coherent, 4 mm pupil height). Horizontal: columns mutually incoherent
(line source filling the 2 mm view; adjacent columns at pitch lam/theta_e have |mu| = sinc(1) = 0).
Two time-sequential 2 mm views; k vertical sparse groups. Same eye model as v11 (1' pooling)."""
import numpy as np, json, os, importlib.util
spec=importlib.util.spec_from_file_location('s',os.path.join(os.path.dirname(os.path.abspath(__file__)),'aether_v11_speckle_core.py'))
s=importlib.util.module_from_spec(spec); spec.loader.exec_module(s)
N,dth,AM,lam,rng=s.N,s.dth,s.AM,s.lam,s.rng
cx=1/(2*2e-3/lam*AM)*2          # column pitch lam/theta_e (= 2 x Nyquist cell of a 2 mm aperture), arcmin
cy=1/(2*4e-3/lam*AM)
cols=np.arange(-N/2*dth,N/2*dth,cx)
def col(xc,k,oy):
    u=np.zeros((N,N),complex); ix=int(round(xc/dth+N/2))%N
    for yy in np.arange(-N/2*dth,N/2*dth,k*cy)+oy*cy:
        u[int(round(yy/dth+N/2))%N,ix]=np.exp(2j*np.pi*rng.random())
    return u
R={'column_pitch_arcmin':cx}
for dz in (0,0.5):
    P=s.pupil(4e-3,'rect',dz=dz,ex=2e-3)
    for k in (1,2,3):
        I=np.zeros((N,N))
        for view in range(2):
            for xc in cols:
                if abs(xc)>26: continue
                for oy in range(k): I+=s.img(col(xc,k,oy),P)
        R[f'card_incoh_2views_k{k}_dz{dz}']=s.contrast(s.pool(I))
# horizontal sharpness at 15 cpd for incoherent views (focus stuck at panel) vs ideal 4 mm pupil
d=0.40
def mtf_h(e,dD,f=15):
    b=e*dD/AM/60                 # blur width, degrees
    geo=np.sinc(b*f)
    fc=e/lam*np.pi/180           # incoherent 1D cutoff, cycles/degree
    dif=max(0,1-f/fc)
    return geo*dif
ideal=1-15/(4e-3/lam*np.pi/180)
for name,z in (('face_7cm_behind',0.07),('face_mid_plane_at_card_+-2.5cm',0.025),('+-5cm',0.05)):
    dD=1/d-1/(d+z)
    R[f'h_sharpness_rel_ideal_{name}']={f'{n}views_e{4/n:.2f}mm':mtf_h(4e-3/n,dD)/ideal for n in (2,3,4)}
# crosstalk into the neighbouring view: column aperture a, far field sinc^2, source fills view (uniform)
u=np.linspace(-6,6,24001); du=u[1]-u[0]
for a_over in (1.0,1.5,2.0):                      # aperture in units of lam/theta_e
    far=np.sinc(a_over*u)**2                       # u = angle / theta_e
    src=(abs(u)<=0.5).astype(float)
    tot=np.convolve(far,src,'same')*du
    own=tot[abs(u)<=0.5].sum(); nb=tot[(u>0.5)&(u<=1.5)].sum()
    R[f'crosstalk_aperture_{a_over}x']={'to_neighbour_view':nb/own,'horizontal_resolution_arcmin':a_over*lam/2e-3*d/d/AM}
# frame budget with RGB colour-stripe columns (no field-sequential colour)
for k in (2,3):
    R[f'subframes_per_s_k{k}']={'1/60s':k*2*60,'1/30s':k*2*30,'with_field_sequential_colour_1/60s':k*2*3*60}
json.dump(R,open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'results_v12_card_incoherent.json'),'w'),indent=1)
print(json.dumps(R,indent=1))
