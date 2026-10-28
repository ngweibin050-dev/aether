"""v13b: plain 1D desk at 0.7 m viewing, image from 10 cm behind to 15 cm in front of the panel."""
import numpy as np, json
from _v9core import psf, mtf, WL
G=WL['G']; d=0.7; hp=250e-6/d; R={}
for h in (-0.10,-0.05,0.05,0.075,0.10,0.15):
    D=d-h; Fs=1/np.linspace(1/D-0.8,1/D+0.8,49)
    m=[sum(mtf(psf(d,D,F,G,hp),15))/2 for F in Fs]; i=int(np.argmax(m))
    R[h]=dict(astig_D=abs(1/D-1/d),mtf=float(m[i]),rel_2D=float(m[i]/0.8553),err_D=float(1/Fs[i]-1/D)); print(h,R[h],flush=True)
json.dump(R,open('results_v13_desk_d07.json','w'),indent=1)
