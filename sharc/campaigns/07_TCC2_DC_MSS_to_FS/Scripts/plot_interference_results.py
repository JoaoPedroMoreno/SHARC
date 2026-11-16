"""Generate all campaign-07 INR, mitigation sweep and HO-operation figures."""
import argparse
from collections import Counter
from datetime import datetime
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np

from interference_postprocessing import (BOOTSTRAPS, CAMPAIGN, HO, MODES, PBO, SEED,
    default_roots, inventory, load_case, metrics, save_csv, save_figure, style, sustained)


def mode_label(mode):
    if mode == 'BASELINE':
        return 'Sem mitiga\u00e7\u00e3o'
    return f'HO: limite {mode[2:]}' if mode.startswith('HO') else f'PBO: {mode[3:-2]} km'


def ccdfs(cases, output, formats):
    for group in sorted({key[:3] for key in cases}):
        for technique, modes in [('HO', ['BASELINE']+[f'HO{n}' for n in HO]),
                                 ('PBO', ['BASELINE']+[f'PBO{n}km' for n in PBO])]:
            fig, ax = plt.subplots(figsize=(8.8, 4.5))
            for i, mode in enumerate(modes):
                case = cases.get((*group, mode))
                if case is None:
                    continue
                x = np.sort(case.values['inr_after_db'])
                y = 1 - np.arange(1, len(x)+1)/len(x)
                good = y > 0
                color = '#222222' if i == 0 else plt.cm.viridis(.1+.8*(i-1)/max(1,len(modes)-2))
                label = mode_label(mode) + (f' (N={case.n}, parcial)' if case.partial else '')
                ax.step(x[good], y[good], where='post', color=color,
                        linestyle='--' if i == 0 else '-', lw=1.5, label=label)
            ax.plot([-6, -6], [.2, 1], 'k:', lw=1.3, label='Crit\u00e9rio: -6 dB / 20%')
            ax.axhline(.2, color='#777777', linestyle=':', lw=.8)
            ax.set(xlabel='INR (dB)', ylabel='Probabilidade de exced\u00eancia',
                   yscale='log', ylim=(1e-4, 1))
            ax.grid(True, which='both', alpha=.2)
            ax.legend(loc='center left', bbox_to_anchor=(1.01,.5), frameon=False,
                      title=f'{group[0]} km | FS {group[1]} m | LF {group[2]}%')
            fig.tight_layout()
            save_figure(fig, output / 'ccdf' / f'ccdf_{technique}_{group[0]}km_FS{group[1]}m_LF{group[2]}', formats)


def sweeps(rows, output, formats):
    indexed = {(r['altitude_km'], r['fs_height_m'], r['lf_pct'], r['mode']): r for r in rows}
    for altitude in sorted({r['altitude_km'] for r in rows}):
        for technique, settings in [('HO', HO), ('PBO', PBO)]:
            for field, ylabel, reference in [
                ('margin_db', 'Margem de prote\u00e7\u00e3o $M_{20}$ (dB)', 0),
                ('inr20_db', '$INR_{20}$ (dB)', -6),
                ('exceedance_pct', 'Snapshots com INR > -6 dB (%)', 20)]:
                fig, ax = plt.subplots(figsize=(7.2,4.4))
                for h in [20,40]:
                    for lf in [20,50]:
                        modes = ['BASELINE'] + ([f'HO{x}' for x in settings] if technique=='HO' else [f'PBO{x}km' for x in settings])
                        group = [(x,indexed[(altitude,h,lf,m)]) for x,m in zip([0]+settings,modes)
                                 if (altitude,h,lf,m) in indexed]
                        if not group:
                            continue
                        x = [a for a,_ in group]; y = [r[field] for _,r in group]
                        color = '#0072B2' if h==20 else '#C45C24'
                        ax.plot(x,y,color=color,linestyle='-' if lf==20 else '--',
                                marker='o' if lf==20 else 's',ms=4,label=f'FS={h} m, LF={lf}%')
                        if field != 'exceedance_pct' and group[0][1]['bootstrap_resamples']:
                            prefix = 'margin' if field=='margin_db' else 'inr'
                            lo=[r[f'{prefix}_ci_low_db'] for _,r in group]
                            hi=[r[f'{prefix}_ci_high_db'] for _,r in group]
                            ax.fill_between(x,lo,hi,color=color,alpha=.12)
                        partial = [(a,r[field]) for a,r in group if r['partial']]
                        if partial:
                            ax.scatter(*zip(*partial),marker='D',s=55,facecolors='white',edgecolors=color,zorder=5)
                ax.axhline(reference,color='black',linestyle=':',lw=1.2)
                ax.set(xlabel='Limite de reassocia\u00e7\u00f5es por snapshot' if technique=='HO'
                       else 'Dist\u00e2ncia de aplica\u00e7\u00e3o do PBO (km)', ylabel=ylabel)
                ax.set_xticks([0]+settings)
                ax.grid(alpha=.22)
                handles, labels = ax.get_legend_handles_labels()
                if any(r['partial'] and r['altitude_km']==altitude and r['mode'].startswith(technique) for r in rows):
                    handles.append(Line2D([],[],marker='D',color='none',markeredgecolor='#555555',markerfacecolor='white'))
                    labels.append('Execu\u00e7\u00e3o parcial')
                ax.legend(handles,labels,loc='best',frameon=False,ncol=2)
                fig.tight_layout()
                save_figure(fig,output/'varreduras'/f'{field}_{technique}_{altitude}km',formats)


def operation(cases, rows, output, formats):
    for group in sorted({key[:3] for key in cases}):
        selected = [cases[(*group,f'HO{n}')] for n in HO if (*group,f'HO{n}') in cases]
        if not selected:
            continue
        fig, axes = plt.subplots(1,2,figsize=(10,4))
        for i,case in enumerate(selected):
            color=plt.cm.viridis(.1+.8*i/max(1,len(selected)-1))
            changes=case.values['accepted_changes'].astype(int)
            count=np.bincount(changes,minlength=31)/case.n*100
            axes[0].plot(range(31),count,color=color,lw=1.3,label=mode_label(case.key[3]))
            x=np.sort(case.values['inr_before_db']-case.values['inr_after_db'])
            axes[1].step(x,np.arange(1,len(x)+1)/len(x),where='post',color=color,lw=1.3)
        axes[0].set(xlabel='Reassocia\u00e7\u00f5es aceitas no snapshot',ylabel='Snapshots (%)',xlim=(-.5,30.5))
        axes[1].set(xlabel='Redu\u00e7\u00e3o de INR no mesmo snapshot (dB)',ylabel='Probabilidade acumulada',ylim=(0,1))
        for ax in axes: ax.grid(alpha=.2)
        axes[0].legend(frameon=False,fontsize=8)
        fig.tight_layout()
        save_figure(fig,output/'handover'/f'trocas_ganho_{group[0]}km_FS{group[1]}m_LF{group[2]}',formats)
        reasons=sorted(set().union(*(c.stops for c in selected)))
        labels={'PROTECTION_REACHED':'Prote\u00e7\u00e3o atingida','MAX_HANDOVERS':'Limite de trocas',
                'SEARCH_EXHAUSTED':'Busca esgotada','DISABLED':'Desativado'}
        fig,ax=plt.subplots(figsize=(7.2,4))
        bottom=np.zeros(len(selected))
        for j,reason in enumerate(reasons):
            heights=np.array([100*c.stops[reason]/c.n for c in selected])
            ax.bar(range(len(selected)),heights,bottom=bottom,label=labels.get(reason,reason),
                   color=plt.cm.Set2(j/max(1,len(reasons)-1)))
            bottom+=heights
        ax.set_xticks(range(len(selected)),[c.key[3] for c in selected])
        ax.set(xlabel='Limite de handover configurado',ylabel='Snapshots (%)',ylim=(0,100))
        ax.legend(loc='upper center',bbox_to_anchor=(.5,1.2),ncol=2,frameon=False)
        fig.tight_layout()
        save_figure(fig,output/'handover'/f'paradas_{group[0]}km_FS{group[1]}m_LF{group[2]}',formats)
    stop_rows=[]
    for case in cases.values():
        if not case.key[3].startswith('HO'): continue
        for reason,count in case.stops.items():
            stop_rows.append(dict(altitude_km=case.key[0],fs_height_m=case.key[1],lf_pct=case.key[2],
                                  mode=case.key[3],reason=reason,snapshots=count,percent=100*count/case.n))
    save_csv(output/'tables/ho_stop_reasons.csv',stop_rows)
    for altitude in sorted({r['altitude_km'] for r in rows}):
        fig,axes=plt.subplots(1,2,figsize=(10,4))
        for h in [20,40]:
            for lf in [20,50]:
                group=sorted([r for r in rows if (r['altitude_km'],r['fs_height_m'],r['lf_pct'])==(altitude,h,lf)
                              and r['mode'].startswith('HO')],key=lambda r:int(r['mode'][2:]))
                if not group: continue
                color='#0072B2' if h==20 else '#C45C24'
                x=[int(r['mode'][2:]) for r in group]
                for ax,field in zip(axes,['mean_accepted_changes','mean_evaluated_candidates']):
                    ax.plot(x,[r[field] for r in group],color=color,ls='-' if lf==20 else '--',marker='o',ms=4,
                            label=f'FS={h} m, LF={lf}%')
        axes[0].set_ylabel('Trocas aceitas por snapshot (m\u00e9dia)')
        axes[1].set_ylabel('Candidatos avaliados por snapshot (m\u00e9dia)')
        for ax in axes:
            ax.set_xlabel('Limite de reassocia\u00e7\u00f5es'); ax.set_xticks(HO); ax.grid(alpha=.2)
        axes[0].legend(frameon=False,fontsize=9)
        fig.tight_layout()
        save_figure(fig,output/'handover'/f'esforco_busca_{altitude}km',formats)
        fig,ax=plt.subplots(figsize=(7.2,4.4))
        for h in [20,40]:
            for lf in [20,50]:
                group=sorted([r for r in rows if (r['altitude_km'],r['fs_height_m'],r['lf_pct'])==(altitude,h,lf)
                              and r['mode'].startswith('PBO')],key=lambda r:int(r['mode'][3:-2]))
                if group:
                    ax.plot([int(r['mode'][3:-2]) for r in group],[r['mean_active_pbo_beams'] for r in group],
                            color='#0072B2' if h==20 else '#C45C24',ls='-' if lf==20 else '--',marker='o',ms=4,
                            label=f'FS={h} m, LF={lf}%')
        ax.set(xlabel='Dist\u00e2ncia de aplica\u00e7\u00e3o do PBO (km)',
               ylabel='Feixes ativos com PBO por snapshot (m\u00e9dia)')
        ax.set_xticks(PBO);ax.grid(alpha=.2);ax.legend(frameon=False,ncol=2)
        fig.tight_layout()
        save_figure(fig,output/'varreduras'/f'feixes_com_PBO_{altitude}km',formats)


def thresholds(rows):
    result=[]
    indexed={(r['altitude_km'],r['fs_height_m'],r['lf_pct'],r['mode']):r for r in rows}
    for group in sorted({key[:3] for key in indexed}):
        for tech,settings in [('HO',HO),('PBO',PBO)]:
            modes=['BASELINE']+([f'HO{x}' for x in settings] if tech=='HO' else [f'PBO{x}km' for x in settings])
            available=[indexed.get((*group,m)) for m in modes]
            if not all(r is not None and r['bootstrap_resamples'] for r in available):
                status='incomplete_matrix_or_no_bootstrap'; first=None
            else:
                first=sustained([(x,r['margin_ci_low_db']) for x,r in zip([0]+settings,available)])
                status='supported_over_remaining_evaluated_settings' if first is not None else 'not_supported_within_evaluated_range'
            result.append(dict(altitude_km=group[0],fs_height_m=group[1],lf_pct=group[2],technique=tech,
                               first_supported_setting=first,unit='km' if tech=='PBO' else 'accepted_handover_limit',
                               status=status,includes_partial=any(r and r['partial'] for r in available)))
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root',type=Path,action='append')
    parser.add_argument('--plots-dir',type=Path,default=CAMPAIGN/'plots/interferencia_completa')
    parser.add_argument('--n-bootstrap',type=int,default=BOOTSTRAPS)
    parser.add_argument('--seed',type=int,default=SEED)
    parser.add_argument('--no-bootstrap',action='store_true',help='Point estimates only; no compliance classification')
    parser.add_argument('--altitude',type=int,choices=[340,525])
    parser.add_argument('--fs-height',type=int,choices=[20,40])
    parser.add_argument('--lf',type=int,choices=[20,50])
    parser.add_argument('--formats',nargs='+',choices=['png','pdf'],default=['png'])
    args=parser.parse_args(argv)
    found=inventory(args.output_root or default_roots())
    cases={}; rows=[]
    for key,folder in found.items():
        if any(wanted is not None and key[i]!=wanted for i,wanted in enumerate([args.altitude,args.fs_height,args.lf])): continue
        print('Reading',folder.name,flush=True)
        case=load_case(key,folder); cases[key]=case
        rows.append(metrics(case,args.plots_dir/'cache',0 if args.no_bootstrap else args.n_bootstrap,args.seed))
    if not cases: raise ValueError('No matching results')
    style()
    args.plots_dir.mkdir(parents=True,exist_ok=True)
    save_csv(args.plots_dir/'tables/inr_metrics.csv',rows)
    save_csv(args.plots_dir/'tables/supported_settings.csv',thresholds(rows))
    stop_counts=dict(Counter(r['classification'] for r in rows))
    report=dict(generated_at=datetime.now().astimezone().isoformat(),scenarios=len(rows),
                classifications=stop_counts,partial=[str(c.folder) for c in cases.values() if c.partial],
                quantile='order statistic ceil(0.8*N)-1; no interpolation',
                bootstrap='snapshot IID resampling with replacement, original sample size, percentile CI 2.5/97.5',
                bootstrap_resamples=0 if args.no_bootstrap else args.n_bootstrap,bootstrap_seed=args.seed,
                pairing='Across configurations: marginal distributions, no assumed pairing. HO before/after: same snapshot.',
                raw_data='tcc2_snapshots.csv.gz, full completed rows, including retained partial PBO',
                uncertainty='Pointwise confidence intervals, not simultaneous bands; zero means baseline in sweep plots.')
    (args.plots_dir/'analysis_manifest.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    ccdfs(cases,args.plots_dir,args.formats)
    sweeps(rows,args.plots_dir,args.formats)
    operation(cases,rows,args.plots_dir,args.formats)
    print(json.dumps(report,indent=2))
    return rows


if __name__=='__main__': main()
