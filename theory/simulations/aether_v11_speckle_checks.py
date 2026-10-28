"""AETHER v11 speckle part 4: (a) G mutually incoherent emitters showing ONE sparse hologram shifted by
one Nyquist cell each (no extra frames) vs G independent groups; (b) TV 1D holography: vertical coherent,
horizontal incoherent (columns do not interfere), with k vertical sparse groups."""
import numpy as np, json, os, importlib.util
spec=importlib.util.spec_from_file_location('s',os.path.join(os.path.dirname(os.path.abspath(__file__)),'aether_v11_speckle_core.py'))
s=importlib.util.module_from_spec(spec); spec.loader.exec_module(s)
N,dth,rng,cell=s.N,s.dth,s.rng,s.cell
R={}
P0=s.pupil(4e-3); P5=s.pupil(4e-3,dz=0.5)
for k in (3,):
    base=s.lattice(k,0,0)
    for nm,P in (('in_focus',P0),('defocus_0.5D',P5)):
        I=np.zeros((N,N))
        for ox in range(k):
            for oy in range(k):
                sh=(int(round(oy*cell/dth)),int(round(ox*cell/dth)))
                I+=s.img(np.roll(base,sh,(0,1)),P)
        R[f'shifted_copies_one_hologram_k{k}_{nm}']=s.contrast(s.pool(I))
# (b) columns mutually incoherent; vertical sparse groups (time-multiplexed)
cols=np.arange(-N/2*dth,N/2*dth,cell)
def col_field(xc,k,oy):
    u=np.zeros((N,N),complex); ix=int(round(xc/dth+N/2))%N
    for yy in np.arange(-N/2*dth,N/2*dth,k*cell)+oy*cell:
        u[int(round(yy/dth+N/2))%N,ix]=np.exp(2j*np.pi*rng.random())
    return u
for k in (1,2,3):
    for nm,P in (('in_focus',P0),('defocus_0.5D',P5)):
        I=np.zeros((N,N))
        for xc in cols[::1]:
            if abs(xc)>26: continue
            for oy in range(k): I+=s.img(col_field(xc,k,oy),P)
        R[f'TV_1D_vertical_k{k}_{nm}']=s.contrast(s.pool(I))
json.dump(R,open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'results_v11_speckle_checks.json'),'w'),indent=1)
print(json.dumps(R,indent=1))
