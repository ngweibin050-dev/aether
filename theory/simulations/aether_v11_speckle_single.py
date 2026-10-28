"""AETHER v11 speckle part 3: one sparse group only (no time multiplexing), and the cost of each
method in subframes. Pupil 4 mm (TV, eye fully coherent) and 2 mm x 4 mm sub-aperture (card view)."""
import numpy as np, json, os, importlib.util
spec=importlib.util.spec_from_file_location('s',os.path.join(os.path.dirname(os.path.abspath(__file__)),'aether_v11_speckle_core.py'))
s=importlib.util.module_from_spec(spec); spec.loader.exec_module(s)
N,dth,AM,lam,rng=s.N,s.dth,s.AM,s.lam,s.rng
def lat(k,cx,cy,ox=0,oy=0):
    u=np.zeros((N,N),complex)
    for yy in np.arange(-N/2*dth,N/2*dth,k*cy)+oy*cy:
        iy=int(round(yy/dth+N/2))%N
        for xx in np.arange(-N/2*dth,N/2*dth,k*cx)+ox*cx:
            u[iy,int(round(xx/dth+N/2))%N]=np.exp(2j*np.pi*rng.random())
    return u
R={}
for name,P,ex,ey in (('TV_4mm',s.pupil(4e-3),4e-3,4e-3),('card_view_2x4mm',s.pupil(4e-3,'rect',ex=2e-3),2e-3,4e-3)):
    cx=1/(2*ex/lam*AM); cy=1/(2*ey/lam*AM)       # Nyquist spacing per axis, arcmin
    r={'nyquist_cell_arcmin':[cx,cy]}
    for k in (2,3):
        for dz in (0,0.5):
            Pz=s.pupil(4e-3,dz=dz) if name=='TV_4mm' else s.pupil(4e-3,'rect',dz=dz,ex=2e-3)
            r[f'one_group_k{k}_dz{dz}']=float(np.mean([s.contrast(s.pool(s.img(lat(k,cx,cy),Pz))) for _ in range(3)]))
        r[f'lattice_pitch_k{k}_arcmin']=[k*cx,k*cy]; r[f'lattice_cpd_k{k}']=[60/(k*cx),60/(k*cy)]
    R[name]=r
json.dump(R,open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'results_v11_speckle_single.json'),'w'),indent=1)
print(json.dumps(R,indent=1))
