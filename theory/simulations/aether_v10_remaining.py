"""AETHER v10 (2026-10-27): the six open items. Reuses the v9 wave-optics eye model for item 1.
Labels in comments: DERIVED, ESTIMATE, ASSUMED (from memory, unverified)."""
import math, json, os
import numpy as np
R={}
lam=530e-9; AM=math.pi/180/60
# ---------------- 1. card in-pupil multi-view (SMV) ----------------
d=0.40; Dp=4e-3; w=10e-3
r1={}
for nv in (2,3):
    e=Dp/nv
    r1[f'{nv}views']=dict(strip_mm=e*1e3,
        horiz_res_limit_arcmin=lam/e/AM,              # DERIVED: uncertainty, any scheme
        min_incoherent_pixel_um=lam*d/e*1e6,          # aperture needed if views are incoherent sub-pixels
        frame_Hz_LR_simultaneous=nv*3*60,             # views x colours x 60 Hz, L/R spatially split
        frame_Hz_LR_time=2*nv*3*60)
# temporal crosstalk: LC relaxes exp(-t/tau); light on in last 40% of each subframe
def xtalk(f,tau): T=1/f; return math.exp(-0.6*T/tau)
r1['temporal_crosstalk']={f'{f}Hz_tau{tau*1e3:.2f}ms':xtalk(f,tau) for f in (360,540) for tau in (0.74e-3,0.37e-3)}
# horizontal samples for a coherent band-limited view: 12.2 deg / 1.37' x2 (Nyquist) x2 (double-phase amplitude encoding)
fov_h=math.degrees(0.0856/d)*60
r1['horiz_samples_3views']=fov_h/(lam/(Dp/3)/AM)*2*2
r1['card_px_3views_M']=r1['horiz_samples_3views']*3000/1e6
R['1_multiview']=r1
# wave-optics: SMV PSF with adjacent-view leakage c (light of view i entering strip i+-1 with view i's tilt)
N=1024; dth=0.125*AM
def psf_smv_x(D,dd,F,nv,c):
    dx=lam/(N*dth); x=(np.arange(N)-N/2)*dx; X,Y=np.meshgrid(x,x)
    P=(X**2+Y**2<=(Dp/2)**2).astype(float); k=2*np.pi/lam; I=np.zeros((N,N)); e=Dp/nv
    cen=[-Dp/2+e*(i+0.5) for i in range(nv)]
    for j in range(nv):                      # strip where light lands
        S=P*(np.abs(X-cen[j])<=e/2)
        for i in range(nv):                  # view whose content it carries
            wgt=(1-c) if i==j else (c/2 if abs(i-j)==1 else 0)
            if wgt==0: continue
            W=0.5*k*Y**2*(1/D-1/F)+k*(cen[i]*(1/D-1/F)*(X-cen[j])+0.5*(X-cen[j])**2*(1/dd-1/F))
            E=np.fft.fftshift(np.fft.fft2(np.fft.ifftshift(S*np.exp(-1j*W)))); I+=wgt*np.abs(E)**2
    return I/I.sum()
def mtf15(I):
    O=np.abs(np.fft.fftshift(np.fft.fft2(np.fft.ifftshift(I))))
    f=np.fft.fftshift(np.fft.fftfreq(N,d=dth/(np.pi/180))); j=np.argmin(abs(f-15)); cc=N//2
    return (O[cc,j]+O[j,cc])/2
D=0.47; sim={}
for nv in (2,3):
    for c in (0.0,0.05,0.10,0.20):
        Fs=1/np.linspace(1/D-0.4,1/D+0.6,41)
        m=[mtf15(psf_smv_x(D,d,F,nv,c)) for F in Fs]
        b=int(np.argmax(m)); sim[f'{nv}views_c{int(c*100)}']=dict(best_mtf15=float(m[b]),focus_error_D=float(1/Fs[b]-1/D))
R['1_multiview']['sim_card_face7cm']=sim
R['1_multiview']['ref_2D_mtf15']=0.855
# ---------------- 2. tracking latency and accuracy ----------------
margin=(w-Dp)/2
lat={}
for v in (0.1,0.3,0.5):                      # m/s head speed (ASSUMED typical..fast)
    lat[f'window_noPred_{v}mps_ms']=margin/v*1e3
for a in (2,5):                              # m/s^2 residual after constant-velocity prediction
    lat[f'window_pred_{a}mps2_ms']=math.sqrt(2*margin/a)*1e3
e3=Dp/3; m3=e3/2
for v in (0.1,0.3): lat[f'views_noPred_{v}mps_ms']=m3/v*1e3
for a in (2,5): lat[f'views_pred_{a}mps2_ms']=math.sqrt(2*m3/a)*1e3
# camera accuracy: 4K, 60 deg FOV, 0.1 px centroid
pix=math.radians(60)/3840
lat['lateral_sigma_mm_card']=0.4*pix*0.1*1e3; lat['lateral_sigma_mm_tv']=2.0*pix*0.1*1e3
lat['stereo_depth_sigma_mm_tv_b0.1']=2.0**2*pix*0.1/0.1*1e3
# window depth tolerance: beam from aperture W converging to eye; spread at dz must stay < margin
for nm,W,dd in (('card',0.0856,0.4),('tv',1.05,2.0)): lat[f'depth_tol_mm_{nm}']=margin*dd/W*1e3
lat['pipeline_ms']='camera 500 fps 2 ms + detect 2-4 ms + source switch <0.1 ms = 4-6 ms (ESTIMATE)'
R['2_tracking']=lat
# ---------------- 3. viewers on a TV ----------------
v3={}
f_view=180                                   # Hz per viewer (3 colours x 60, L/R simultaneous)
for rows in (1,2,4,6):                       # tile rows, each with its own drivers, both-side drive
    lines=4200/rows; t_line=1/(f_view*lines) # s per line for one viewer
    v3[f'tile_rows_{rows}_viewers_by_drive']=t_line*2/1.9e-6   # vs 8K-class 1.9 us line time, x2 dual-side
v3['viewers_by_LC_45C_overdrive']=1/(3*0.18e-3)/f_view
R['3_viewers']=v3
# ---------------- 4. speckle ----------------
s=2e-3; z=0.1; theta_c=lam/s                 # decorrelation angle of a sub-hologram (= coherence limit)
v4={}
for M_src in (1,4,9,16):
    theta_s=theta_c*math.sqrt(M_src)
    blur=theta_s*z/(d+z)/AM
    M=M_src*3*1.45                           # x3 views (mutually incoherent) x1.45 wavelength diversity (25 nm uLED)
    v4[f'Msrc{M_src}']=dict(source_angle_mrad=theta_s*1e3,blur_arcmin=blur,total_patterns=M,contrast=1/math.sqrt(M))
v4['M_lambda']=1+25e-9*((s/2)**2/(2*z))/lam**2
R['4_speckle']=v4
# ---------------- 6. capture on the far side ----------------
v6={}
stereo_acuity=30/3600*math.pi/180            # 30 arcsec, natural viewing (ASSUMED)
for nm,zv in (('tv_person_3m',3.0),('card_face_0.47m',0.47)):
    v6[f'depth_tol_mm_{nm}']=zv**2*stereo_acuity/0.064*1e3
for b in (0.3,0.6):                          # camera baseline at 1 m, 0.3 px matching on skin (ESTIMATE)
    v6[f'stereo_sigma_mm_b{b}']=1.0**2*pix*0.3/b*1e3
v6['angle_cover_deg_tv']=math.degrees(math.atan(0.5/2.0))
v6['rgbd_mbps']='~10-20 Mbit/s for 1080p RGB-D at 30 fps (ESTIMATE)'
R['6_capture']=v6
json.dump(R,open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'results_v10.json'),'w'),indent=1)
print(json.dumps(R,indent=1))
