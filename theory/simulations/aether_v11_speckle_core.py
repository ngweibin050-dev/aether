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

fc=4e-3/lam*AM; cell=1/(2*fc)
def lattice(k,ox,oy):
    u=np.zeros((N,N),complex); st=k*cell
    for yy in np.arange(-N/2*dth,N/2*dth,st)+oy*cell:
        iy=int(round(yy/dth+N/2))%N
        for xx in np.arange(-N/2*dth,N/2*dth,st)+ox*cell:
            u[iy,int(round(xx/dth+N/2))%N]=np.exp(2j*np.pi*rng.random())
    return u
