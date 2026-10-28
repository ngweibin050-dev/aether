"""AETHER v11 speckle part 5: card, two time-sequential 2 mm x 4 mm views per pupil (each view coherent),
k x k sparse groups per view."""
import numpy as np, json, os, importlib.util
spec=importlib.util.spec_from_file_location('s',os.path.join(os.path.dirname(os.path.abspath(__file__)),'aether_v11_speckle_core.py'))
s=importlib.util.module_from_spec(spec); spec.loader.exec_module(s)
N,dth,AM,lam,rng=s.N,s.dth,s.AM,s.lam,s.rng
cx=1/(2*2e-3/lam*AM); cy=1/(2*4e-3/lam*AM)
def lat(k,ox,oy):
    u=np.zeros((N,N),complex)
    for yy in np.arange(-N/2*dth,N/2*dth,k*cy)+oy*cy:
        iy=int(round(yy/dth+N/2))%N
        for xx in np.arange(-N/2*dth,N/2*dth,k*cx)+ox*cx:
            u[iy,int(round(xx/dth+N/2))%N]=np.exp(2j*np.pi*rng.random())
    return u
R={}
for dz in (0,0.5):
    P=s.pupil(4e-3,'rect',dz=dz,ex=2e-3)
    for k in (1,2,3):
        I=np.zeros((N,N))
        for view in range(2):
            for ox in range(k):
                for oy in range(k): I+=s.img(lat(k,ox,oy),P)
        R[f'card_2views_k{k}_G{k*k}_dz{dz}']=s.contrast(s.pool(I))
json.dump(R,open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'results_v11_speckle_card.json'),'w'),indent=1)
print(json.dumps(R,indent=1))
