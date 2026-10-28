"""AETHER v9 (2026-10-27): does 1D (single-parallax) holography give natural focus?
Wave-optics eye model: field in the 4 mm pupil -> eye lens focused at distance F -> retinal PSF (FFT).
2D hologram : a scene point at distance D sends a spherical wave, curvature 1/D in x and y.
1D hologram : vertical (y) curvature 1/D (true hologram); horizontal (x) light comes from the panel
              plane through a lenticular, curvature 1/d, plus the coarse horizontal pixel width.
Assumptions: diffraction-limited eye (no own aberrations), diffuse scene (layers add in intensity),
paraxial optics, pupil fully filled by the 10 mm viewing window. Speckle not modelled."""
import numpy as np, json, os
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif']=['WenQuanYi Zen Hei','Microsoft YaHei','SimHei','DejaVu Sans']; plt.rcParams['font.family']='sans-serif'; plt.rcParams['axes.unicode_minus']=False
OUT='.'
AM=np.pi/180/60                      # 1 arcmin in rad
PUP=4e-3                             # pupil diameter
dth=0.125*AM                         # PSF sampling (rad)
N=1024
WL={'R':635e-9,'G':530e-9,'B':460e-9}

def psf(Dx,Dy,F,lam,hpix_ang=0.0):
    """retinal PSF (normalised) for wave curvatures 1/Dx, 1/Dy and eye focus 1/F; angular grid dth."""
    dx=lam/(N*dth)                    # pupil-plane sample so the FFT lands on dth
    x=(np.arange(N)-N/2)*dx; X,Y=np.meshgrid(x,x)
    P=(X**2+Y**2<=(PUP/2)**2).astype(float)
    k=2*np.pi/lam
    W=0.5*k*(X**2*(1/Dx-1/F)+Y**2*(1/Dy-1/F))   # sign convention: diverging wave minus lens power
    E=np.fft.fftshift(np.fft.fft2(np.fft.ifftshift(P*np.exp(-1j*W))))
    I=np.abs(E)**2
    if hpix_ang>0:                    # horizontal box blur of the coarse 1D-mode pixel
        n=max(1,int(round(hpix_ang/dth)))
        I=np.apply_along_axis(lambda r: np.convolve(r,np.ones(n)/n,'same'),1,I)
    return I/I.sum()

def psf_smv(D,d,F,lam,nv,hpix_ang=0.0):
    """1D hologram vertically (curvature 1/D) + nv horizontal views inside the pupil (super multi-view).
    Each view strip: horizontal curvature 1/d (panel), tilted as a ray from depth D through the strip centre."""
    dx=lam/(N*dth); x=(np.arange(N)-N/2)*dx; X,Y=np.meshgrid(x,x)
    P=(X**2+Y**2<=(PUP/2)**2).astype(float); k=2*np.pi/lam; I=np.zeros((N,N))
    w=PUP/nv
    for i in range(nv):
        xc=-PUP/2+w*(i+0.5); S=P*(np.abs(X-xc)<=w/2)
        W=0.5*k*Y**2*(1/D-1/F)+k*(xc*(1/D-1/F)*(X-xc)+0.5*(X-xc)**2*(1/d-1/F))
        E=np.fft.fftshift(np.fft.fft2(np.fft.ifftshift(S*np.exp(-1j*W)))); I+=np.abs(E)**2
    if hpix_ang>0:
        n=max(1,int(round(hpix_ang/dth)))
        I=np.apply_along_axis(lambda r: np.convolve(r,np.ones(n)/n,'same'),1,I)
    return I/I.sum()

def mtf(I,cpd):
    """MTF at cpd (cycles/degree) along x (horizontal detail = vertical lines) and y."""
    O=np.abs(np.fft.fftshift(np.fft.fft2(np.fft.ifftshift(I))))
    f=np.fft.fftshift(np.fft.fftfreq(N,d=dth/(np.pi/180)))   # cycles/degree
    j=np.argmin(abs(f-cpd)); c=N//2
    return float(O[c,j]), float(O[j,c])        # (x-direction, y-direction)

