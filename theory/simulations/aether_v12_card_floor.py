"""AETHER v12 part 2: speckle floor of the horizontally incoherent card vs vertical group count k,
and vs number of in-pupil views (2 or 3)."""
import numpy as np, json, os, importlib.util
spec=importlib.util.spec_from_file_location('s',os.path.join(os.path.dirname(os.path.abspath(__file__)),'aether_v11_speckle_core.py'))
s=importlib.util.module_from_spec(spec); spec.loader.exec_module(s)
N,dth,AM,lam,rng=s.N,s.dth,s.AM,s.lam,s.rng
cy=1/(2*4e-3/lam*AM)
def run(k,nv,dz):
    e=4e-3/nv; cx=lam/e/AM
    P=s.pupil(4e-3,'rect',dz=dz,ex=e)
    I=np.zeros((N,N))
    for v in range(nv):
        for xc in np.arange(-26,26,cx):
            ix=int(round(xc/dth+N/2))%N
            for oy in range(k):
                u=np.zeros((N,N),complex)
                for yy in np.arange(-N/2*dth,N/2*dth,k*cy)+oy*cy:
                    u[int(round(yy/dth+N/2))%N,ix]=np.exp(2j*np.pi*rng.random())
                I+=s.img(u,P)
    return s.contrast(s.pool(I))
R={}
for nv in (2,3):
    for k in (3,4,6):
        R[f'views{nv}_k{k}']={'in_focus':run(k,nv,0),'defocus_0.5D':run(k,nv,0.5)}
json.dump(R,open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'results_v12_card_floor.json'),'w'),indent=1)
print(json.dumps(R,indent=1))
