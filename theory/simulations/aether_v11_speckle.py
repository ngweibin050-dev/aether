"""AETHER v11 speckle (2026-10-28). Wave-optics eye model of speckle in a thin-SLM holographic window.
Retinal amplitude = IFFT[ pupil(f) * FFT[object field] ], intensity pooled by a 1-arcmin Gaussian
(approximate foveal neural resolution, unverified) and contrast C = std/mean on a uniform patch."""
import numpy as np, json, os
rng=np.random.default_rng(1)
N=512; dth=0.125                       # retinal sampling, arcmin
AM=np.pi/180/60                        # rad per arcmin
lam=530e-9
f=np.fft.fftfreq(N,d=dth*AM)           # cycles/rad
FX,FY=np.meshgrid(f,f)
x=(np.arange(N)-N/2)*dth; X,Y=np.meshgrid(x,x)
def pupil(D,shape='circ',dz=0.0,ex=None):
    rx=FX*lam; ry=FY*lam               # pupil coords, m
    if shape=='circ': P=(rx**2+ry**2<=(D/2)**2).astype(complex)
    else: P=((abs(rx)<=ex/2)&(abs(ry)<=D/2)).astype(complex)   # rectangle ex wide (horizontal) x D tall
    return P*np.exp(1j*np.pi*lam*dz*(FX**2+FY**2))              # defocus dz in dioptres
def pool(I,fwhm=1.0):
    s=fwhm/2.355; G=np.exp(-((X)**2+(Y)**2)/(2*(s)**2)); G/=G.sum()
    return np.real(np.fft.ifft2(np.fft.fft2(I)*np.fft.fft2(np.fft.ifftshift(G))))
def img(u,P): return abs(np.fft.ifft2(np.fft.fft2(u)*P))**2
core=(abs(X)<16)&(abs(Y)<16)
def contrast(I): v=I[core]; return float(v.std()/v.mean())
def rand_obj(): return np.exp(2j*np.pi*rng.random((N,N)))
R={}
# 1) single frame, fully random phase: C vs pupil and pooling width -> bound C ~ lam/(D theta)
R['single_frame']={}
for D in (3e-3,4e-3,6e-3):
    P=pupil(D)
    for w in (1.0,2.0,3.0):
        c=np.mean([contrast(pool(img(rand_obj(),P),w)) for _ in range(4)])
        R['single_frame'][f'D{D*1e3:.0f}mm_pool{w:.0f}arcmin']={'C':c,'theory_lam_over_Dtheta':lam/(D*w*AM)}
# card view: 2 mm x 4 mm sub-aperture, two views sequential (independent holograms)
Pa=pupil(4e-3,'rect',ex=2e-3)
c1=np.mean([contrast(pool(img(rand_obj(),Pa))) for _ in range(4)])
c2=np.mean([contrast(pool(img(rand_obj(),Pa)+img(rand_obj(),Pa))) for _ in range(4)])
R['card_subaperture']={'one_view':c1,'two_views':c2}
# 2) temporal averaging of independent random-phase frames (4 mm, 1')
P=pupil(4e-3)
R['frames']={}
for n in (1,4,16,64):
    I=sum(img(rand_obj(),P) for _ in range(n)); R['frames'][n]=contrast(pool(I))
# 3) spectral diversity in a THIN phase SLM: same phase pattern, phase scales as lam0/lam, plus
#    image magnification lam/lam0 (approximated by the phase term only, worst-case favourable)
phi=2*np.pi*rng.random((N,N))
for dl in (0.0,0.02,0.06):
    I=sum(img(np.exp(1j*phi*(1/(1+e))),P) for e in np.linspace(-dl/2,dl/2,9))
    R.setdefault('spectral_thin_slm',{})[f'dlam_over_lam_{dl}']=contrast(pool(I))
# 4) sparse point groups (points on a lattice of spacing k Nyquist cells; G=k^2 groups shown sequentially)
fc=4e-3/lam*AM                        # coherent cutoff, cycles/arcmin
cell=1/(2*fc)                         # Nyquist spacing, arcmin
def lattice(k,ox,oy,phase=True):
    u=np.zeros((N,N),complex); st=k*cell
    xs=np.arange(-N/2*dth,N/2*dth,st)+ox*cell
    ys=np.arange(-N/2*dth,N/2*dth,st)+oy*cell
    for yy in ys:
        iy=int(round(yy/dth+N/2))%N
        for xx in xs:
            ix=int(round(xx/dth+N/2))%N
            u[iy,ix]=np.exp(2j*np.pi*rng.random()) if phase else 1
    return u
R['sparse_groups']={}
for k in (1,2,3,4):
    I=np.zeros((N,N))
    for ox in range(k):
        for oy in range(k): I+=img(lattice(k,ox,oy),P)
    R['sparse_groups'][f'k{k}_G{k*k}']=contrast(pool(I))
# 5) focus cue test: bright/dark edge, eye defocused 0.5 D. Compare averaged image to incoherent blur.
edge=(X<0).astype(float)
Pd=pupil(4e-3,dz=0.5)

# incoherent reference: |PSF|^2 convolved with intensity edge
psf=abs(np.fft.ifft2(Pd))**2; psf/=psf.sum()
Iinc=np.real(np.fft.ifft2(np.fft.fft2(edge)*np.fft.fft2(psf)))
def width(I):  # 10-90 % edge width, arcmin, along centre rows
    p=I[N//2-8:N//2+8].mean(0); p=(p-p[N//2+60])/(p[N//2-60]-p[N//2+60])
    xs=x[N//2-60:N//2+60]; q=p[N//2-60:N//2+60]
    return float(xs[np.argmin(abs(q-0.1))]-xs[np.argmin(abs(q-0.9))])
R['focus_edge_0.5D']={'incoherent_reference':width(Iinc)}
I=sum(img(np.sqrt(edge)*rand_obj(),Pd) for _ in range(32)); R['focus_edge_0.5D']['random_phase_32frames']=width(I)
I=img(np.sqrt(edge).astype(complex),Pd); R['focus_edge_0.5D']['smooth_phase']=width(I)
for k in (2,3):
    I=np.zeros((N,N))
    for ox in range(k):
        for oy in range(k): I+=img(lattice(k,ox,oy)*np.sqrt(edge),Pd)
    R['focus_edge_0.5D'][f'sparse_k{k}']=width(I)
    R.setdefault('sparse_defocus_speckle_0.5D',{})[f'k{k}']=None
# speckle in a defocused uniform region with sparse groups
for k in (1,2,3):
    I=np.zeros((N,N))
    for ox in range(k):
        for oy in range(k): I+=img(lattice(k,ox,oy),Pd)
    R['sparse_defocus_speckle_0.5D'][f'k{k}']=contrast(pool(I))
json.dump(R,open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'results_v11_speckle.json'),'w'),indent=1)
print(json.dumps(R,indent=1))
