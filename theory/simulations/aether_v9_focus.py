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
OUT=os.path.dirname(os.path.abspath(__file__))
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

CASES={'card':dict(d=0.40,depths={'鼻尖':0.45,'脸':0.47,'耳和头发':0.53,'背景':0.75},hpix=100e-6),
       'tv':  dict(d=2.0, depths={'鼻尖':2.9,'脸':3.0,'耳和头发':3.12,'背景':5.0},hpix=250e-6)}

def curves(case):
    d=case['d']; D=case['depths']['脸']; hp=case['hpix']/d
    Fs=1/np.linspace(1/D-0.9,1/D+0.9,73)     # accommodation sweep, diopters around the face
    out={}
    for mode in ('2D','1D','stereo'):
        Dx=D if mode=='2D' else d
        Dy=d if mode=='stereo' else D
        hx=0 if mode=='2D' else hp
        mx=[];my=[]
        for F in Fs:
            I=psf(Dx,Dy,F,WL['G'],hx); a,b=mtf(I,15); mx.append(a); my.append(b)
        out[mode]=dict(diopter=list(1/Fs),mtf_h=mx,mtf_v=my)
    for nv in (3,4):
        mx=[];my=[]
        for F in Fs:
            I=psf_smv(D,d,F,WL['G'],nv,hp); a,b=mtf(I,15); mx.append(a); my.append(b)
        out[f'1D+{nv}views']=dict(diopter=list(1/Fs),mtf_h=mx,mtf_v=my)
    return out

R={}; C={}
for name,case in CASES.items():
    c=curves(case); C[name]=c
    D=case['depths']['脸']; d=case['d']
    r={'astigmatism_D':abs(1/d-1/D)}
    for mode in ('2D','1D','stereo','1D+3views','1D+4views'):
        dio=np.array(c[mode]['diopter']); mean=(np.array(c[mode]['mtf_h'])+np.array(c[mode]['mtf_v']))/2
        r[f'{mode}_best_focus_D']=float(dio[np.argmax(mean)])
        r[f'{mode}_best_mean_mtf15']=float(mean.max())
        r[f'{mode}_focus_error_D']=float(dio[np.argmax(mean)]-1/D)
    r['face_D']=1/D; r['panel_D']=1/d
    R[name]=r

# ---------- figure 1: sharpness vs where the eye focuses ----------
fig,axs=plt.subplots(1,2,figsize=(12,4.4))
for ax,(name,title) in zip(axs,(('card','卡片：眼睛 40 cm，人脸在卡片后 7 cm'),('tv','电视：眼睛 2 m，人在屏幕后 1 m'))):
    c=C[name]; r=R[name]
    for mode,col,lab in (('2D','#1f6feb','二维全息'),('1D','#d1495b','一维全息'),('stereo','#888888','普通裸眼 3D')):
        dio=c[mode]['diopter']; mean=(np.array(c[mode]['mtf_h'])+np.array(c[mode]['mtf_v']))/2
        ax.plot(dio,mean,color=col,lw=2.2,label=f'{lab}（上下左右平均）')
        if mode=='1D':
            ax.plot(dio,c[mode]['mtf_v'],color=col,lw=1,ls=':',label='一维：上下方向细节')
            ax.plot(dio,c[mode]['mtf_h'],color=col,lw=1,ls='--',label='一维：左右方向细节')
    dio=c['1D+3views']['diopter']; mean=(np.array(c['1D+3views']['mtf_h'])+np.array(c['1D+3views']['mtf_v']))/2
    ax.plot(dio,mean,color='#2a9d8f',lw=2.2,label='一维 + 瞳孔内 3 个视点（平均）')
    ax.axvline(r['face_D'],color='k',lw=1); ax.text(r['face_D'],1.02,'人脸深度',ha='center',fontsize=9)
    ax.axvline(r['panel_D'],color='gray',lw=1,ls=':'); ax.text(r['panel_D'],1.02,'面板',ha='center',fontsize=9,color='gray')
    ax.set_xlabel('眼睛对焦距离（屈光度 D，越大越近）'); ax.set_ylabel('清晰度（15 周/度的对比度）')
    ax.set_ylim(0,1.08); ax.set_title(title,fontsize=11,pad=14); ax.invert_xaxis()
axs[1].legend(fontsize=8,loc='upper right')
fig.tight_layout(); fig.savefig(f'{OUT}/v9_fig1_focus_curves.png',dpi=130); plt.close(fig)

# ---------- procedural test face with depth layers ----------
def face_layers(size=560):
    """RGB texture + per-layer masks. Fine features in all orientations: lashes, hair, brows, text."""
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.patches import Ellipse, Circle
    def draw(fn):
        f=Figure(figsize=(size/100,size/100),dpi=100); FigureCanvasAgg(f); ax=f.add_axes([0,0,1,1])
        ax.set_xlim(0,1); ax.set_ylim(0,1); ax.axis('off'); fn(ax); f.canvas.draw()
        return np.asarray(f.canvas.buffer_rgba())[...,:3].astype(float)/255
    rng=np.random.default_rng(1)
    def bg(ax):
        ax.add_patch(plt.Rectangle((0,0),1,1,color='#e8e4da',zorder=0))
        for i in range(14): ax.plot([i/14,i/14],[0,1],color='#9a8f7a',lw=1,zorder=0.5)
        for i in range(14): ax.plot([0,1],[i/14,i/14],color='#9a8f7a',lw=1,zorder=0.5)
        ax.text(0.03,0.03,'AETHER 背景',fontsize=11,color='#333',zorder=0.5)
    def hair(ax):
        ax.add_patch(Ellipse((0.5,0.6),0.62,0.74,color='#3b2a1e',zorder=2))
        for _ in range(160):
            a=rng.uniform(0,np.pi); r0=rng.uniform(0.25,0.36)
            x0,y0=0.5+r0*np.cos(a)*0.9,0.62+r0*np.sin(a)
            ax.plot([x0,x0+rng.normal(0,0.03)],[y0,y0-rng.uniform(0.05,0.15)],color='#c9a27a',lw=0.6,zorder=2.5)
        for s in (-1,1): ax.add_patch(Ellipse((0.5+s*0.255,0.5),0.07,0.13,color='#d9a98a',zorder=2.6))
    def face(ax):
        ax.add_patch(Ellipse((0.5,0.5),0.46,0.6,color='#f0c4a4',zorder=4))
        for s in (-1,1):
            cx=0.5+s*0.1
            ax.add_patch(Ellipse((cx,0.55),0.09,0.045,color='white',zorder=4.1))
            ax.add_patch(Circle((cx,0.55),0.018,color='#4a6a8a',zorder=4.2)); ax.add_patch(Circle((cx,0.55),0.008,color='k',zorder=4.3))
            for t in np.linspace(-0.04,0.04,11):
                ax.plot([cx+t,cx+t*1.2],[0.572,0.59],color='k',lw=0.6,zorder=4.4)      # lashes (near-vertical lines)
            ax.plot([cx-0.05,cx+0.05],[0.615,0.62],color='#3b2a1e',lw=3,zorder=4.4)    # brow (horizontal)
        ax.plot([0.43,0.57],[0.37,0.37],color='#a0473f',lw=2.5,zorder=4.4)              # mouth (horizontal)
        ax.text(0.5,0.25,'妈妈 MOM',fontsize=9,ha='center',color='#5a2e2e',zorder=4.4)  # fine text
    def nose(ax):
        ax.add_patch(Ellipse((0.5,0.46),0.06,0.09,color='#e8b494',zorder=6))
        ax.plot([0.5,0.5],[0.5,0.43],color='#b07a5a',lw=0.8,zorder=6.1)                 # ridge (vertical line)
        for s in (-1,1): ax.add_patch(Circle((0.5+s*0.015,0.43),0.006,color='#7a4a3a',zorder=6.2))
    imgs={'背景':draw(bg),'耳和头发':draw(lambda a:(bg(a),hair(a))),
          '脸':draw(lambda a:(bg(a),hair(a),face(a))),'鼻尖':draw(lambda a:(bg(a),hair(a),face(a),nose(a)))}
    full=imgs['鼻尖']
    m={}; prev=None; masks={}
    order=['背景','耳和头发','脸','鼻尖']
    for i,k in enumerate(order):
        if i==0: masks[k]=np.ones(full.shape[:2])
        else: masks[k]=(np.abs(imgs[k]-imgs[order[i-1]]).sum(-1)>0.02).astype(float)
    # exclusive ownership: the nearest layer owns the pixel
    own={}; taken=np.zeros(full.shape[:2])
    for k in reversed(order):
        own[k]=masks[k]*(1-taken); taken=np.clip(taken+own[k],0,1)
    return full,own

def bin4(I):
    n=I.shape[0]//4*4; I=I[:n,:n]; return I.reshape(n//4,4,n//4,4).sum((1,3))

def render(case,mode,F,full,own,px_arcmin=0.5):
    d=case['d']; out=np.zeros_like(full); hp=case['hpix']/d
    for ci,(cname,lam) in enumerate(WL.items()):
        for layer,D in case['depths'].items():
            Dx=D if mode=='2D' else d
            Dy=d if mode=='stereo' else D
            I=bin4(psf(Dx,Dy,F,lam,0 if mode=='2D' else hp))   # 0.5 arcmin per sample
            c=I.shape[0]//2; h=40; K=I[c-h:c+h,c-h:c+h]; K/=K.sum()
            src=full[...,ci]*own[layer]
            S=np.fft.rfft2(src,s=(src.shape[0]+2*h,src.shape[1]+2*h))
            Kf=np.fft.rfft2(K,s=(src.shape[0]+2*h,src.shape[1]+2*h))
            conv=np.fft.irfft2(S*Kf,s=(src.shape[0]+2*h,src.shape[1]+2*h))[h:h+src.shape[0],h:h+src.shape[1]]
            out[...,ci]+=conv
    return np.clip(out,0,1)

full,own=face_layers()
for name,case in CASES.items():
    D=case['depths']; d=case['d']
    foci=[('眼睛对焦在人脸',D['脸']),('眼睛对焦在背景',D['背景'])]
    fig,axs=plt.subplots(3,2,figsize=(8.6,13.4))
    names={'2D':'二维全息','1D':'一维全息','stereo':'普通裸眼 3D（对照）'}
    for i,mode in enumerate(('2D','1D','stereo')):
        for j,(lab,F) in enumerate(foci):
            img=render(case,mode,F,full,own)
            ax=axs[i,j]; ax.imshow(img[110:450,110:450]); ax.set_xticks([]); ax.set_yticks([])
            ax.set_title(f'{names[mode]}，{lab}',fontsize=11)
    ttl='卡片（眼睛 40 cm，人脸在卡片后约 7 cm）' if name=='card' else '电视（眼睛 2 m，人在屏幕后约 1 m）'
    fig.suptitle(f'{ttl}：眼睛看到的画面（每像素 0.5 角分，放大显示）',fontsize=12)
    fig.tight_layout(); fig.savefig(f'{OUT}/v9_fig2_face_{name}.png',dpi=110); plt.close(fig)

tol=[]
for delta in np.arange(0,0.81,0.05):
    d=0.4; D=1/(1/d-delta) if delta>0 else d
    Fs=1/np.linspace(1/D-0.6,1/D+0.6+delta,61)
    best=max(sum(mtf(psf(d,D,F,WL['G'],100e-6/d),15))/2 for F in Fs)
    tol.append([round(float(delta),2),float(best)])
R['tolerance_1D_best_mtf15_vs_delta']=tol
R['mtf15_2D_reference']=R['card']['2D_best_mean_mtf15']
json.dump(R,open(f'{OUT}/results_v9.json','w'),indent=1,ensure_ascii=False)
print(json.dumps(R,indent=1,ensure_ascii=False))
