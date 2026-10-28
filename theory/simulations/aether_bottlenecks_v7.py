"""AETHER v7 (2026-10-27): the three Route A bottlenecks (fast phase LC, cost, large size).
Every printed value follows from the formulas in AETHER_Physics_v7_Bottlenecks.md; inputs marked ASSUMED."""
import math, json
R={}
lam={'R':635e-9,'G':532e-9,'B':450e-9}
# ---------- 1. fast phase LC ----------
# full 2*pi at red: transmissive d = lam/dn, reflective (double pass) d = lam/(2 dn)
# free relaxation time tau = gamma1 d^2 / (K11 pi^2)   (ESTABLISHED, Jakeman-Raynes)
gamma1=0.10   # Pa s, typical display nematic   ASSUMED (from memory)
K11=12e-12    # N                               ASSUMED (from memory)
def tau(d,g=gamma1,K=K11): return g*d*d/(K*math.pi**2)
cases={}
for name,dn,refl,g in [('transmissive dn0.20',0.20,False,0.10),
                       ('transmissive dn0.40',0.40,False,0.10),
                       ('reflective dn0.20',0.20,True,0.10),
                       ('reflective dn0.40',0.40,True,0.10),
                       ('reflective dn0.40 low-visc',0.40,True,0.05)]:
    d=lam['R']/dn/(2 if refl else 1)
    t=tau(d,g)
    cases[name]={'d_um':d*1e6,'tau_ms':t*1e3,'max_subframe_Hz':1/(2.2*t)}  # ~2.2 tau = 90% settle
R['lc_cases']=cases
# sub-frame budget: 360 Hz -> 2.78 ms = row scan + LC settle + laser flash
R['subframe_ms']={f'{f}Hz':1e3/f for f in (120,360,720,1440)}
# ---------- 2. reduce the rate you need ----------
# time-sequential colour: 2 eyes x 3 colours x 60 Hz; spatial colour: 2 x 60
R['rate_per_viewer_Hz']={'time_colour':2*3*60,'spatial_colour':2*60}
# ---------- 3. pixel count vs window size w (card, d=0.4 m, blue) ----------
W,H=85.6e-3,54e-3
def pix(Wd,Hd,d,w,lm=lam['B']):
    p=lm*d/w; return p,(Wd/p)*(Hd/p)
R['card_w_tradeoff']={f'w{w*1e3:.0f}mm':{'pitch_um':pix(W,H,0.4,w)[0]*1e6,'pixels':pix(W,H,0.4,w)[1]} for w in (0.010,0.007,0.005)}
# horizontal-parallax-only (1D) encoding: fine pitch horizontally, display-like vertically
p_h=lam['B']*0.4/0.010; p_v=100e-6   # ASSUMED vertical pitch
R['card_hpo_pixels']=(W/p_h)*(H/p_v)
# ---------- 4. row addressing time ----------
sizes={'card':(W,H,0.4),'desk':(0.60,0.34,0.7),'tv':(1.05,0.60,2.0)}
for k,(Wd,Hd,d) in sizes.items():
    p=lam['B']*d/0.010; rows=Hd/p; cols=Wd/p
    for f in (360,720):
        for seg in (1,2,4):
            R.setdefault('row_time_us',{})[f'{k}_{f}Hz_{seg}seg']=1e6*seg/(f*rows)/2  # half the sub-frame for scanning
    R.setdefault('panel',{})[k]={'pitch_um':p*1e6,'rows':rows,'cols':cols,'pixels':rows*cols,'ppi':25.4e-3/p}
# ---------- 4b. 1D (vertical-parallax-only) encoding, SeeReal-style ----------
# fine holographic pitch vertically; horizontally a coarse lenticular "sweet spot" per eye,
# so both eyes are served at once (rate 3 colours x 60 Hz time-sequential) and the panel is
# scanned along the coarse direction. Coarse pitch ASSUMED: card 100 um, desk 150 um, tv 250 um.
coarse={'card':100e-6,'desk':150e-6,'tv':250e-6}
for k,(Wd,Hd,d) in sizes.items():
    pf=lam['B']*d/0.010; lines=Wd/coarse[k]; px=lines*(Hd/pf)
    f=180
    R.setdefault('vpo',{})[k]={'fine_pitch_um':pf*1e6,'coarse_pitch_um':coarse[k]*1e6,'scan_lines':lines,
        'pixels':px,'rate_Hz':f,'line_time_us_rolling_1seg':1e6/(f*lines),'line_time_us_rolling_2seg':2e6/(f*lines)}
# full-2D rolling scan (scan uses the whole sub-frame, laser band follows) for comparison
for k,(Wd,Hd,d) in sizes.items():
    p=lam['B']*d/0.010; rows=Hd/p
    R.setdefault('full2d_rolling_line_time_us_360Hz',{})[k]={s:1e6*s/(360*rows) for s in (1,2,4)}
# ---------- 5. gap uniformity for large panels ----------
# phase error = 2 pi dn dd / lam (x2 if reflective); allow lam/10 wavefront error -> 0.2 pi
for dn in (0.2,0.4):
    dd=0.1*lam['B']/dn   # transmissive, worst colour blue
    R.setdefault('gap_tolerance_um',{})[f'dn{dn}']=dd*1e6
# ---------- 6. cost per area (ASSUMED panel costs, not quotes) ----------
# ASSUMED cost per m^2 of finished LTPS/oxide TFT-LCD glass: phone-class ~ US$2000-4000/m2, TV-class ~ US$150-400/m2
R['area_m2']={k:v[0]*v[1] for k,v in sizes.items()}
print(json.dumps(R,indent=1))
json.dump(R,open(__file__.replace('aether_bottlenecks_v7.py','results_v7.json'),'w'),indent=1)
