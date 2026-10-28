"""AETHER v11 speckle part 6: subframe budget (how fast the modulator must switch) for the speckle levels
found in parts 1-5. Integration window for speckle averaging: 1/60 s (safe) or 1/30 s (unverified)."""
import json, os
mods={'nematic_room_0.96ms':347,'nematic_heated_0.6ms':555,'MEMS_PLM_now':1440,'MEMS_PLM_planned':10000,'binary_FLC_6.3kHz':6300}
cases={'TV_1D_k2 (C 0.06 focus / 0.07 at 0.5 D)':2*3,'TV_1D_k3 (C 0.027 / 0.05)':3*3,
       'card_k1 (C 0.24 / 0.26)':1*2*3,'card_k2 (C 0.073 / 0.12)':4*2*3,'card_k3 (C 0.056 / 0.079)':9*2*3}
R={}
for c,n in cases.items():
    for T in (60,30):
        need=n*T
        R[f'{c} @1/{T}s']={'subframes_per_s_per_viewer':need,'viewers_or_ratio':{m:round(f/need,2) for m,f in mods.items()}}
# card panel rows ~3000: line time needed
for f in (1440,1620,3240): R[f'card_line_time_us_at_{f}Hz']=1e6/(f*3000)
json.dump(R,open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'results_v11_speckle_budget.json'),'w'),indent=1)
print(json.dumps(R,indent=1))
