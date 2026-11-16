"""HO candidate angles and, optionally, exact link geometry before/after decisions.

Streams compressed files; never expands raw archives or reads user archives.
Candidate plots describe the selected satellite, not the original satellite.
--with-links adds original and updated geometry using the lossless SHARC decoder.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT))
from sharc.support.tcc2_detailed_records import read_detailed_rows
from interference_postprocessing import (CAMPAIGN, HO, default_roots, inventory,
    read_gzip_csv, save_csv, save_figure, style)

ANGLE_FIELDS = ['service_elevation_deg','tx_offaxis_deg','rx_offaxis_deg',
                'tx_gain_dbi','rx_gain_dbi','path_loss_db','i_link_mw']
LINK_FIELDS = ANGLE_FIELDS + ['slant_range_m','distance_paraguay_border_km',
    'satellite_x_m','satellite_y_m','satellite_z_m','cell_lat','cell_lon','tx_power_dbm']


def accepted_events(folder, limit):
    events={}
    for row in read_gzip_csv(folder/'tcc2_events.csv.gz'):
        sid=int(row['snapshot_id'])
        if limit and sid>limit: break
        key=(sid,int(row['beam_row_idx']))
        if key in events: raise ValueError(f'Cell examined more than once: {folder}, {key}')
        events[key]=dict(row)
    return events


def attach_candidates(folder, events, limit):
    reasons=Counter(); evaluated=Counter(); selected=set()
    for row in read_gzip_csv(folder/'tcc2_candidates.csv.gz'):
        sid=int(row['snapshot_id'])
        if limit and sid>limit: break
        reasons[row['reason']]+=1
        key=(sid,int(row['beam_id']))
        event=events.get(key)
        # Angles are finite only for physically evaluated candidates.
        angle=float(row['rx_offaxis_deg'])
        if np.isfinite(angle): evaluated[int(min(angle,179.999)//5)*5]+=1
        if event and event['accepted']=='True' and int(row['candidate_satellite'])==int(event['selected_satellite_idx']):
            if key in selected: raise ValueError(f'Duplicate selected candidate {key}')
            selected.add(key)
            for field in ANGLE_FIELDS: event['candidate_'+field]=float(row[field])
    expected={key for key,event in events.items() if event['accepted']=='True'}
    if selected != expected: raise ValueError(f'Missing selected candidates: {len(expected-selected)}')
    return reasons,evaluated


def attach_links(folder, events, limit):
    targets={}
    for (sid,beam),event in events.items():
        accepted=event['accepted']=='True'
        step=int(event['accepted_count'])
        targets[(sid,step-1 if accepted else step,beam)]=(event,'before')
        if accepted: targets[(sid,step,beam)]=(event,'after')
    seen=set()
    for row in read_detailed_rows(folder,'links'):
        sid=int(row['snapshot_id'])
        if limit and sid>limit: break
        key=(sid,int(row['step']),int(row['beam_id']))
        match=targets.get(key)
        if match is None: continue
        if key in seen: raise ValueError(f'Duplicate geometry row {key}')
        seen.add(key)
        event,stage=match
        expected_sat=int(event['current_satellite_idx' if stage=='before' else 'selected_satellite_idx'])
        if int(row['satellite_id'])!=expected_sat or int(row['cell_id'])!=int(event['cell_id']):
            raise ValueError(f'Event/link association mismatch: {key}')
        for field in LINK_FIELDS: event[stage+'_'+field]=float(row[field])
    if seen!=set(targets): raise ValueError(f'Missing link states: {len(set(targets)-seen)}')


def figures(events, stem, formats, with_links):
    accepted=[e for e in events.values() if e['accepted']=='True']
    if not accepted: return
    fig,axes=plt.subplots(1,3,figsize=(12,3.8))
    for ax,field,label in zip(axes,ANGLE_FIELDS[:3],
        ['Eleva\u00e7\u00e3o na c\u00e9lula (graus)','Fora do eixo TX (graus)','Fora do eixo do FS (graus)']):
        groups=[('candidate_','Sat\u00e9lite selecionado','#0072B2')]
        if with_links: groups=[('before_','Antes da troca','#555555'),('after_','Depois da troca','#0072B2')]
        for prefix,text,color in groups:
            x=np.sort([e[prefix+field] for e in accepted])
            if not np.isfinite(x).all(): raise ValueError('Missing/nonfinite accepted geometry')
            ax.step(x,np.arange(1,len(x)+1)/len(x),where='post',color=color,label=text,lw=1.5)
        ax.set(xlabel=label,ylabel='Probabilidade acumulada',ylim=(0,1)); ax.grid(alpha=.2)
    axes[0].legend(frameon=False,fontsize=9)
    fig.tight_layout(); save_figure(fig,stem.with_name(stem.name+'_angulos'),formats)
    if with_links:
        fig,axes=plt.subplots(1,2,figsize=(9.5,4))
        gain=[float(e['inr_before_db'])-float(e['inr_after_db']) for e in accepted]
        for ax,field,label in zip(axes,['rx_offaxis_deg','service_elevation_deg'],
                                 ['Fora do eixo do FS antes (graus)','Eleva\u00e7\u00e3o na c\u00e9lula antes (graus)']):
            h=ax.hexbin([e['before_'+field] for e in accepted],gain,gridsize=35,mincnt=1,cmap='Blues',bins='log')
            fig.colorbar(h,ax=ax,label='Trocas aceitas')
            ax.set(xlabel=label,ylabel='Redu\u00e7\u00e3o do INR agregado na troca (dB)')
        fig.tight_layout(); save_figure(fig,stem.with_name(stem.name+'_ganho_posicao'),formats)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-root',type=Path,action='append')
    p.add_argument('--plots-dir',type=Path,default=CAMPAIGN/'plots/handover_geometria')
    p.add_argument('--ho',type=int,nargs='+',choices=HO,default=HO)
    p.add_argument('--altitude',type=int,choices=[340,525])
    p.add_argument('--fs-height',type=int,choices=[20,40])
    p.add_argument('--lf',type=int,choices=[20,50])
    p.add_argument('--with-links',action='store_true',help='Read large link archives for exact pre/post geometry')
    p.add_argument('--max-snapshots',type=int,help='Explicit preview only; outputs are labelled with the cap')
    p.add_argument('--formats',nargs='+',choices=['png','pdf'],default=['png'])
    args=p.parse_args(argv)
    if args.max_snapshots is not None and args.max_snapshots<1: p.error('--max-snapshots must be positive')
    style(); summaries=[]
    for key,folder in inventory(args.output_root or default_roots()).items():
        a,h,lf,mode=key
        if mode not in [f'HO{x}' for x in args.ho]: continue
        if any(w is not None and key[i]!=w for i,w in enumerate([args.altitude,args.fs_height,args.lf])): continue
        print('Geometry:',folder.name,flush=True)
        events=accepted_events(folder,args.max_snapshots)
        reasons,evaluated=attach_candidates(folder,events,args.max_snapshots)
        if args.with_links:
            print('Reading compressed links; no user archive is needed.',flush=True)
            attach_links(folder,events,args.max_snapshots)
        suffix=f'_preview_N{args.max_snapshots}' if args.max_snapshots else ''
        suffix+='_pre_pos' if args.with_links else '_selecionado'
        stem=args.plots_dir/f'{a}km_FS{h}m_LF{lf}_{mode}{suffix}'
        figures(events,stem,args.formats,args.with_links)
        fields=sorted({field for e in events.values() for field in e})
        save_csv(stem.with_suffix('.csv'),[{field:e.get(field,'') for field in fields} for e in events.values()])
        save_csv(stem.with_name(stem.name+'_candidate_reasons.csv'),[dict(reason=k,count=v) for k,v in sorted(reasons.items())])
        bins=[]
        if args.with_links:
            for low in range(0,180,5):
                bucket=[e for e in events.values() if low<=e['before_rx_offaxis_deg']<low+5 or
                        (low==175 and e['before_rx_offaxis_deg']==180)]
                if bucket:
                    n=sum(e['accepted']=='True' for e in bucket)
                    bins.append(dict(rx_offaxis_lower_deg=low,rx_offaxis_upper_deg=low+5,
                                     examined_cells=len(bucket),accepted=n,accepted_fraction=n/len(bucket)))
            save_csv(stem.with_name(stem.name+'_acceptance_by_angle.csv'),bins)
            if bins:
                fig,axes=plt.subplots(2,1,figsize=(7.2,5.2),sharex=True)
                centers=[b['rx_offaxis_lower_deg']+2.5 for b in bins]
                axes[0].plot(centers,[100*b['accepted_fraction'] for b in bins],'o-',color='#0072B2',ms=4)
                axes[0].set(ylabel='Decis\u00f5es aceitas (%)',ylim=(0,100))
                axes[1].bar(centers,[b['examined_cells'] for b in bins],width=4.5,color='#666666')
                axes[1].set(xlabel='\u00c2ngulo fora do eixo do FS antes da decis\u00e3o (graus)',
                            ylabel='C\u00e9lulas examinadas')
                for ax in axes: ax.grid(axis='y',alpha=.2)
                fig.tight_layout()
                save_figure(fig,stem.with_name(stem.name+'_aceitacao_angular'),args.formats)
        summary=dict(source=str(folder),events=len(events),accepted=sum(e['accepted']=='True' for e in events.values()),
                     with_links=args.with_links,snapshot_cap=args.max_snapshots,
                     candidate_reasons=dict(reasons),evaluated_candidate_angle_bins=dict(evaluated),
                     caution='Exploratory, decision-weighted geometry; not a validated positional threshold. '
                             'No cross-configuration pooling. Rejected ineligible candidates lack RF angles.')
        stem.with_suffix('.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
        summaries.append(summary)
    if not summaries: raise ValueError('No selected handover scenarios')
    return summaries


if __name__=='__main__': main()
