"""AETHER v11 speckle part 2: does each speckle-reduction method keep a correct focus cue?
Object: band-limited random texture at the eye's focus distance. Metric: retinal contrast of the
8-16 cpd band vs eye defocus, compared with an ideal incoherent object (natural viewing)."""
import numpy as np, json, os, importlib.util
spec=importlib.util.spec_from_file_location('s',os.path.join(os.path.dirname(os.path.abspath(__file__)),'aether_v11_speckle_core.py'))
s=importlib.util.module_from_spec(spec); spec.loader.exec_module(s)
np_=np; N,X,Y,x,dth,pupil,img,pool,lattice,rng=s.N,s.X,s.Y,s.x,s.dth,s.pupil,s.img,s.pool,s.lattice,s.rng
fr=np.fft.fftfreq(N,d=dth)*60                  # cycles/degree
FR=np.hypot(*np.meshgrid(fr,fr))
band=(FR>8)&(FR<16)
tex=np.real(np.fft.ifft2(np.fft.fft2(rng.standard_normal((N,N)))*((FR>4)&(FR<20))))
obj=1+0.5*tex/tex.std(); obj=np.clip(obj,0.05,None)      # intensity texture
def bandc(I): F=np.fft.fft2(I-I.mean()); return float(np.sqrt((abs(F[band])**2).sum())/I.mean())
ref0=None; out={}
dzs=[0,0.15,0.3,0.5,0.75,1.0]
for dz in dzs:
    P=pupil(4e-3,dz=dz)
    psf=abs(np.fft.ifft2(P))**2; psf/=psf.sum()
    Iinc=np.real(np.fft.ifft2(np.fft.fft2(obj)*np.fft.fft2(psf)))
    row={'incoherent':bandc(Iinc)}
    a=np.sqrt(obj)
    row['smooth_phase']=bandc(img(a.astype(complex),P))
    row['random_64frames']=bandc(sum(img(a*np.exp(2j*np.pi*rng.random((N,N))),P) for _ in range(64)))
    for k in (3,4):
        I=np.zeros((N,N))
        for ox in range(k):
            for oy in range(k): I+=img(lattice(k,ox,oy)*a,P)
        row[f'sparse_k{k}']=bandc(I)
    # sparse k3 with the random phases redrawn for 2 cycles (60 Hz reload in 33 ms)
    I=np.zeros((N,N))
    for c in range(2):
        for ox in range(3):
            for oy in range(3): I+=img(lattice(3,ox,oy)*a,P)
    row['sparse_k3_x2cycles']=bandc(I)
    out[str(dz)]=row
# normalise each method by its own in-focus value -> focus curve; compare to incoherent
curves={m:[out[str(dz)][m]/out['0'][m] for dz in dzs] for m in out['0']}
# speckle contrast of a uniform patch in focus and at 0.5 D for the combined method
P0=pupil(4e-3); P5=pupil(4e-3,dz=0.5)
def sp(P,k,cyc):
    I=np.zeros((N,N))
    for c in range(cyc):
        for ox in range(k):
            for oy in range(k): I+=img(lattice(k,ox,oy),P)
    return s.contrast(pool(I))
spk={f'k{k}_cycles{c}':{'in_focus':sp(P0,k,c),'defocus_0.5D':sp(P5,k,c)} for k,c in ((3,1),(3,2),(4,1),(3,4))}
R={'defocus_D':dzs,'band_contrast':out,'focus_curve_relative':curves,'speckle_uniform':spk}
json.dump(R,open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'results_v11_speckle_focus.json'),'w'),indent=1)
print(json.dumps({'focus_curve_relative':curves,'speckle_uniform':spk,'in_focus_band':out['0']},indent=1))
