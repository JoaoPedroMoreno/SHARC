"""LATINCOM schematic figures using the existing Encom presentation assets.

All positions are illustrative; no geographic coordinates or measured results
are encoded. The existing satellite PNG is embedded in SVG/PDF exports.
"""
from pathlib import Path
import shutil
import argparse
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Circle, FancyBboxPatch, Arc, Ellipse
from matplotlib.transforms import Affine2D
import numpy as np
import latincom_visual_style as s
import generate_fs_mitigation_methodology as methodology
from latincom_encom_cover import cover as regional_cover
from latincom_perspective import context as perspective_context

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'figuras/latincom/encom_style_20261027'

def label(ax,x,y,value,size=18,color=s.INK,ha='left'):
    ax.text(x,y,value,fontsize=size,color=color,va='center',ha=ha,zorder=30)

def line(ax,source,target,color=s.RED):
    ax.annotate('',xy=target,xytext=source,zorder=22,
                arrowprops=dict(arrowstyle='-|>',lw=1.7,color=color,linestyle=(0,(5,3))))

def canvas():
    fig=plt.figure(figsize=(12,6.75))
    ax=fig.add_axes([0,0,1,1],xlim=(0,12),ylim=(0,6.75))
    ax.set_aspect('equal'); ax.axis('off')
    return fig,ax

def region(ax, mode='none', multiple=True, labels=True):
    # Shared idealized terrain; the border is not an actual geographic trace.
    ax.add_patch(Polygon([(1,.95),(5.1,.95),(5.6,3.25),(1.5,3.25)],
                         fc='#F1F7F3',ec='#AEC1B8',lw=1.2,zorder=1))
    ax.add_patch(Polygon([(5.1,.95),(10.5,.95),(11,3.25),(5.6,3.25)],
                         fc=s.original.BLUE_PALE,ec=s.BLUE,lw=1.2,zorder=1))
    ax.plot([5.1,5.6],[.95,3.25],color=s.original.BORDER,lw=1.7,zorder=8)
    if labels:
        label(ax,2.8,.56,'Paraguay',19,ha='center')
        label(ax,8,.56,'Brazil',19,ha='center')
    # Intentional, disjoint service targets at several depths and lateral positions.
    specs=[(6.10,4.92,2.05,(0,7)),(9.65,5.35,2.1,(10,17)),
           (8.35,3.65,1.65,(2,9))] if multiple else [(7.7,5.15,2.7,(7,10))]
    served={i for _,_,_,indices in specs for i in indices}
    centers=[]
    for row in range(3):
        for col in range(6):
            x=5.95+col*.76+(row%2)*.38
            y=1.40+row*.63
            affected=mode=='pbo' and col==0
            vertices=s.hexagon(x,y,.42)
            fill=s.original.ORANGE_PALE if affected else s.original.BLUE_SELECTED if row*6+col in served else s.original.BLUE_PALE
            ax.add_patch(Polygon(vertices,fc=fill,
                                 ec=s.ORANGE if affected else s.BLUE,lw=1.2,zorder=6))
            centers.append((x,y,affected))
    target=s.receiver(ax,4.25,1.48,.105)
    for x,y,width,indices in specs:
        source=s.satellite(ax,x,y,width)
        for i in indices:
            cx,cy,affected=centers[i]
            vertices=s.hexagon(cx,cy,.42)
            s.original.beam(ax,source,vertices,pbo=affected,broad=True)
        line(ax,source,target)
    if mode=='pbo':
        label(ax,1.65,3.75,'Victim FS',18,s.GREEN)
        label(ax,7.7,3.63,'Selective power back-off',17,s.ORANGE)
    elif labels:
        label(ax,2.55,2.85,'Victim FS',18,s.GREEN)
    return target

def cover():
    fig,ax=canvas()
    label(ax,.55,6.25,'DC-MSS / FS: two mitigation strategies',25,'#387391')
    for side,kind in enumerate(['ez','pbo']):
        dx=side*5.9
        label(ax,dx+.55,5.56,'Exclusion zone' if kind=='ez' else 'Conditional power back-off',18,
              '#387391' if kind=='ez' else s.ORANGE)
        border=dx+2.65
        ax.add_patch(Polygon([(dx+.4,1.05),(border,1.05),(border+.3,3.25),(dx+.7,3.25)],
                             fc='#F1F7F3',ec='#AEC1B8',lw=1,zorder=1))
        ax.add_patch(Polygon([(border,1.05),(dx+5.5,1.05),(dx+5.8,3.25),(border+.3,3.25)],
                             fc=s.original.BLUE_PALE,ec=s.BLUE,lw=1,zorder=1))
        ax.plot([border,border+.3],[1.05,3.25],c=s.original.BORDER,lw=1.4,zorder=9)
        victim=np.array([dx+2.1,2.05])
        points=[]
        for row in range(5):
            for col in range(10):
                x=dx+.82+col*.44+(row%2)*.22
                y=1.32+row*.38
                if kind=='pbo' and x<border+.34:
                    continue
                excluded=kind=='ez' and np.linalg.norm(np.array([x,y])-victim)<.77
                pbo=kind=='pbo' and x<border+.88
                color='#AAB8C0' if excluded else s.ORANGE if pbo else s.BLUE
                fill='#E9ECEE' if excluded else s.original.ORANGE_PALE if pbo else s.original.BLUE_SELECTED
                vertices=s.hexagon(x,y,.25)
                ax.add_patch(Polygon(vertices,fc=fill,ec=color,lw=.7,zorder=6))
                if not excluded:
                    points.append((x,y,pbo))
        if kind=='ez':
            ax.add_patch(Circle(victim,.77,fill=False,ec=s.RED,lw=1.5,zorder=20))
            label(ax,dx+.65,3.6,r'$R_{ez}$',15,s.RED)
        else:
            ax.annotate('',xy=(border+.88,3.47),xytext=(border+.3,3.47),
                        arrowprops=dict(arrowstyle='<->',color=s.ORANGE,lw=1.2))
            label(ax,border+.57,3.72,r'$D_{border}$',14,s.ORANGE,ha='center')
        target=s.receiver(ax,victim[0],victim[1]-.15,.065)
        for j,(x,y) in enumerate([(dx+1.5,4.55),(dx+4.45,4.76)]):
            source=s.satellite(ax,x,y,1.55)
            candidates=sorted(points,key=lambda p:abs(p[0]-x))
            for cx,cy,pbo in candidates[j:j+2]:
                s.original.beam(ax,source,s.hexagon(cx,cy,.25),pbo=pbo,broad=True)
            line(ax,source,target)
        label(ax,dx+1.38,.72,'Paraguay',14,ha='center')
        label(ax,dx+4.25,.72,'Brazil',14,ha='center')
        label(ax,dx+2.08,1.0,'FS',12,s.GREEN,ha='center')
    label(ax,6,.24,'Regional coverage / excluded cells                 Brazil-Argentina coverage / border-cell back-off',12,ha='center')
    return fig

def context():
    fig,ax=canvas()
    region(ax,'none',True)
    label(ax,.65,6.22,'Cross-border aggregate interference',25,'#387391')
    label(ax,1.45,4.5,'Several downlinks\nOne victim receiver',17)
    tx=s.receiver(ax,1.75,1.45,.105)
    rx=np.array([4.25,1.48+8.8*.105])
    ax.annotate('',xy=rx,xytext=tx,zorder=24,
                arrowprops=dict(arrowstyle='-|>',lw=2.1,color=s.GREEN))
    label(ax,1.70,1.18,'FS transmitter',13,s.GREEN,ha='center')
    label(ax,4.15,1.18,'FS receiver',13,s.GREEN,ha='center')
    label(ax,2.9,2.55,'Wanted link',13,s.GREEN,ha='center')
    label(ax,1.3,3.7,r'$I_{agg}=\sum_i I_i$',22,s.RED)
    return fig

def terminal(ax,x,y,conventional=False):
    ax.add_patch(FancyBboxPatch((x-.19,y-.3),.38,.62,
                 boxstyle='round,pad=0.01,rounding_size=0.04',fc='#DDE6EB',ec=s.INK,lw=1.3,zorder=16))
    screen_bottom=y+.04 if conventional else y-.16
    ax.add_patch(Polygon([(x-.13,screen_bottom),(x+.13,screen_bottom),(x+.13,y+.22),(x-.13,y+.22)],
                         fc='white',ec=s.BLUE,lw=.7,zorder=17))
    ax.add_patch(Circle((x,y-.23),.025,fc=s.INK,zorder=18))
    if conventional:
        ax.plot([x+.13,x+.13],[y+.32,y+.72],c=s.INK,lw=3,zorder=18)
        for row in range(3):
            for col in range(3):
                ax.add_patch(Circle((x+(col-1)*.08,y-.02-row*.065),.019,fc=s.INK,zorder=19))
    return np.array([x+.13 if conventional else x,y+.72 if conventional else y+.32])

def gateway(ax,x,y):
    center=np.array([x,y+.58])
    normal=np.array([.55,.835]); tangent=np.array([-.835,.55])
    t=np.linspace(-.56,.56,80)
    curve=center+t[:,None]*tangent+(t*t/.95)[:,None]*normal
    ax.plot([x,x],[y,center[1]],c=s.INK,lw=3,zorder=16)
    ax.plot([x-.36,x+.36],[y,y],c=s.INK,lw=3,zorder=16)
    ax.add_patch(Polygon(curve,fc='#DDE6EB',ec=s.INK,lw=1.5,zorder=17))
    feed=center+.27*normal
    for rim in [curve[0],curve[-1]]:
        ax.plot([rim[0],feed[0]],[rim[1],feed[1]],c=s.INK,lw=1,zorder=18)
    ax.add_patch(Circle(feed,.045,fc=s.BLUE,ec=s.INK,lw=.7,zorder=19))
    return feed

def architecture_panel(ax,offset,conventional):
    title='Conventional MSS' if conventional else 'DC-MSS-IMT'
    label(ax,offset+3,5.85,title,24,'#387391',ha='center')
    source=s.satellite(ax,offset+3,4.65,2.3)
    if conventional:
        feed=gateway(ax,offset+1.18,1.46)
        ax.annotate('',xy=source,xytext=feed,zorder=14,
                    arrowprops=dict(arrowstyle='<->',color=s.GREEN,lw=1.8))
        label(ax,offset+.52,3.55,'Feeder link',14,s.GREEN)
        footprint=Affine2D().scale(1,.45).skew_deg(8,0).translate(offset+4.35,1.73).transform(
            s.original.hex_vertices((0,0),1.0))
        ax.add_patch(Polygon(footprint,fc=s.original.BLUE_PALE,ec=s.BLUE,lw=1.2,zorder=3))
        s.original.beam(ax,source,footprint,broad=True)
        # The service-link arrow replaces the beam's separate centerline.
        ax.lines[-1].remove()
        target=terminal(ax,offset+4.35,1.98,True)
        service_link=ax.annotate('',xy=target,xytext=source,zorder=14,
                                arrowprops=dict(arrowstyle='<->',color=s.BLUE,lw=1.8))
        service_link.set_gid('mss-service-link-bidirectional')
        label(ax,offset+4.21,3.48,'Service link',14,'#387391')
        label(ax,offset+3,5.23,'Transparent / bent-pipe payload',12,ha='center')
        label(ax,offset+1.25,.96,'Ground gateway',15,ha='center')
        label(ax,offset+4.35,.96,'Dedicated MSS terminal',14,ha='center')
        label(ax,offset+3,.47,r'Gateway $\rightarrow$ satellite $\rightarrow$ MSS handset',13,ha='center')
        return
    ground=Affine2D().scale(1,.5).skew_deg(8,0).translate(offset+2.15,1.7)
    centers=[(0,0),(0,.9526),(.825,.4763),(.825,1.4289),(1.65,0),(1.65,.9526)]
    for i,center in enumerate(centers):
        footprint=ground.transform(s.original.hex_vertices(center,.55))
        ax.add_patch(Polygon(footprint,fc=s.original.BLUE_PALE,ec=s.BLUE,lw=1.2,zorder=3))
        if i in (0,3,4):
            s.original.beam(ax,source,footprint,broad=True)
            x,y=ground.transform(center)
            terminal(ax,x,y+.29)
    label(ax,offset+3,.95,'Dedicated MSS terminal' if conventional else 'IMT user equipment',18,ha='center')
    label(ax,offset+3,.47,'Satellite-terminal link' if conventional else 'Direct satellite-to-device link',14,ha='center')

def architecture(which=None):
    if which is None:
        fig,ax=canvas()
        architecture_panel(ax,0,True)
        architecture_panel(ax,6,False)
        ax.plot([6,6],[.7,6.1],c='#D9E4EA',lw=1)
    else:
        fig=plt.figure(figsize=(6,6.75))
        ax=fig.add_axes([0,0,1,1],xlim=(0,6),ylim=(0,6.75))
        ax.axis('off'); ax.set_aspect('equal')
        architecture_panel(ax,0,which=='mss')
    return fig

def methods():
    fig,ax=canvas()
    label(ax,.65,6.25,'Two spatial mitigation strategies',25,'#387391')
    for side,kind in [(0,'ez'),(1,'pbo')]:
        offset=side*5.8
        label(ax,offset+.65,5.55,'Exclusion zone' if kind=='ez' else 'Power back-off',21,
              '#387391' if kind=='ez' else s.ORANGE)
        source=s.satellite(ax,offset+3.5,4.6,1.75)
        victim=(offset+2,2.35) if kind=='ez' else (offset+1.1,2.15)
        for row in range(3):
            for col in range(5):
                x=offset+1.15+col*.73+(row%2)*.365
                y=1.55+row*.63
                if kind=='pbo' and col==0:
                    continue
                excluded=kind=='ez' and np.hypot(x-victim[0],y-victim[1])<1.02
                pbo=kind=='pbo' and col==1
                color='#ADB8BF' if excluded else s.ORANGE if pbo else s.BLUE
                fill='#E9ECEE' if excluded else s.original.ORANGE_PALE if pbo else s.original.BLUE_SELECTED
                ax.add_patch(Polygon(s.hexagon(x,y,.42),fc=fill,ec=color,lw=.8 if excluded else 1.3,zorder=6))
        if kind=='ez':
            ax.add_patch(Circle(victim,1.02,fill=False,ec=s.RED,lw=1.6,zorder=20))
            label(ax,offset+.65,3.6,r'$R_{ez}$',17,s.RED)
            label(ax,offset+.65,.77,'Exclude cells around the FS',16)
        else:
            ax.plot([offset+1.5]*2,[1.05,3.18],color=s.original.BORDER,lw=1.5)
            ax.annotate('',xy=(offset+2.4,3.33),xytext=(offset+1.5,3.33),
                        arrowprops=dict(arrowstyle='<->',lw=1.2,color=s.ORANGE))
            label(ax,offset+1.95,3.65,r'$D_{border}$',16,s.ORANGE,ha='center')
            label(ax,offset+.65,.77,'Reduce border-cell power by 10 dB',16)
        target=s.receiver(ax,victim[0],victim[1]-.22,.065)
        line(ax,source,target)
        s.original.beam(ax,source,s.hexagon(offset+4.07,2.18,.42),broad=True)
    label(ax,6,.22,'Schematic geometry; no geographic scale',10,'#8B9BA4',ha='center')
    return fig

def save(fig,name,preview=False):
    if not preview:
        for ext in ['png','pdf','svg']:
            fig.savefig(OUT/f'{name}.{ext}',dpi=600,transparent=ext=='png',facecolor='none' if ext=='png' else 'white')
    fig.savefig(OUT/f'{name}_preview.png',dpi=140,facecolor='white')
    if hasattr(fig,'_latincom_validation'):
        (OUT/f'{name}_validation.json').write_text(json.dumps(fig._latincom_validation,indent=2),encoding='utf-8')
    plt.close(fig)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preview',action='store_true')
    parser.add_argument('--figures',nargs='+',choices=['cover','architecture','context','methodology'],
                        default=['cover','architecture','context','methodology'])
    args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    plt.rcParams.update({'font.family':'DejaVu Sans','pdf.fonttype':42,'svg.fonttype':'none'})
    jobs=[]
    if 'cover' in args.figures:
        jobs.append(('latincom_cover',regional_cover))
    if 'architecture' in args.figures:
        jobs.extend([('latincom_page_2',architecture),('latincom_page_2A_conventional_mss',lambda:architecture('mss')),
                     ('latincom_page_2B_dc_mss_imt',lambda:architecture('dc'))])
    if 'context' in args.figures:
        jobs.append(('latincom_page_3',perspective_context))
    for name,build in jobs:
        save(build(),name,args.preview)
        print(name,flush=True)
    if 'methodology' in args.figures:
        methodology.main(output_dir=OUT,preview=args.preview)
        if not args.preview:
            for ext in ['png','pdf','svg']:
                shutil.copy2(OUT/f'dc_mss_fs_mitigation_methodology.{ext}',OUT/f'latincom_sharc_monte_carlo.{ext}')

if __name__=='__main__':
    main()
