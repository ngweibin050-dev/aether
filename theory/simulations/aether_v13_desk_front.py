"""AETHER v13 (2026-10-28): Jarvis-style desk. The image floats IN FRONT of the panel (real image),
so the eye is closer to the image than to the panel. Does 1D holography still focus correctly?
Reuses the v9 wave-optics eye (psf, psf_smv, mtf). Eye at d from panel; image at D from eye, D<d."""
import numpy as np, json
from _v9core import psf, psf_smv, mtf, WL
G=WL['G']
def best(fn,D):
    Fs=1/np.linspace(1/D-1.2,1/D+1.2,97); m=[sum(mtf(fn(F),15))/2 for F in Fs]
    i=int(np.argmax(m)); return float(m[i]), float(1/Fs[i]-1/D)
R={}
for d in (0.6,):
  for h in (0.05,0.10,0.15,0.20,0.25):          # image height in front of panel (towards eye)
    D=d-h; hp=250e-6/d
    r={'astig_D':1/D-1/d}
    r['2D']=best(lambda F:psf(D,D,F,G),D)
    r['1D']=best(lambda F:psf(d,D,F,G,hp),D)
    for nv in (3,4):
        r[f'1D+{nv}v']=best(lambda F:psf_smv(D,d,F,G,nv,hp),D)
    R[f'd{d}_h{h}']=r; print(d,h,{k:(v if isinstance(v,float) else (round(v[0],3),round(v[1],3))) for k,v in r.items()})
json.dump(R,open('results_v13_desk.json','w'),indent=1)
