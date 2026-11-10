"""Deterministic presentation diagram; geometry is schematic, not simulation data."""
from pathlib import Path
import math
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle, RegularPolygon, Polygon, Arc
import latincom_visual_style as style
from latincom_perspective import snapshot as perspective_snapshot

OUT = Path(__file__).resolve().parents[1] / 'figuras'
BLUE, ORANGE, RED = style.BLUE, style.ORANGE, style.RED
INK, GRAY = style.INK, '#AAB8C0'

def text(ax, x, y, s, size=14, color=INK, **kw):
    return ax.text(x, y, s, fontsize=size, color=color, va='center', **kw)

def arrow(ax, a, b, color=BLUE, **kw):
    ax.annotate('', xy=b, xytext=a, arrowprops=dict(arrowstyle='-|>', color=color, lw=1.8, **kw))

def sat(ax, x, y):
    return style.satellite(ax,x,y,1.2)

def fs(ax,x,y):
    style.receiver(ax,x,y-.28,.055)
    text(ax,x+.20,y-.08,'FS',11,RED,weight='bold')

def cells(ax, cx, cy, method):
    victim=(cx+.72,cy-.10)
    for row in range(3):
        for col in range(4):
            x=cx-1.12+col*.52+(row%2)*.26
            y=cy+(row-1)*.45
            if method=='ez':
                affected=math.hypot(x-victim[0],y-victim[1])<.85
            else:
                affected=col==3
            fc='#E9ECEE' if affected and method=='ez' else style.original.ORANGE_PALE if affected else style.original.BLUE_SELECTED
            ec=GRAY if affected and method=='ez' else ORANGE if affected else BLUE
            ax.add_patch(RegularPolygon((x,y),6,radius=.29,orientation=0,
                fc=fc,ec=ec,lw=.8 if affected and method=='ez' else 1.2,ls='-'))
    if method=='ez':
        ax.add_patch(Circle(victim,.85,fill=False,ec=RED,lw=1.5,ls='-',zorder=20))
        fs(ax,*victim)
        text(ax,cx+1.12,cy+.65,'$R_{ez}$',13,RED)
    else:
        ax.plot([cx+1.02]*2,[cy-.75,cy+.75],color=GRAY,lw=1.5)
        fs(ax,cx+1.18,cy-.10)
        text(ax,cx+1.15,cy+.84,'Paraguay',10,ha='center')
        text(ax,cx-.40,cy-.90,'Brazil / Argentina',11,ha='center')
        text(ax,cx+.47,cy+.74,'$D_{border}$',12,ORANGE)
    sx,sy=cx-.45,cy+1.45
    source=sat(ax,sx,sy)
    ax.add_patch(Polygon([source,(cx-1.25,cy+.05),(cx-.20,cy+.05)],fc=BLUE,alpha=.18,ec=None))
    arrow(ax,source,(cx-.67,cy+.12),BLUE)
    end=victim if method=='ez' else (cx+1.18,cy-.10)
    arrow(ax,source,(end[0],end[1]+.15),RED,linestyle=(0,(4,3)))

def snapshot(ax,cx,cy,method,phase):
    """Illustrative realizations; geometric rules stay fixed across snapshots."""
    text(ax,cx,cy+1.18,f'Snapshot {phase+1}',12,INK,ha='center')
    victim=(cx+.74,cy-.22)
    available=[]
    for row in range(3):
        for col in range(4):
            x=cx-.94+col*.43+(row%2)*.215+phase*.045
            y=cy-.13+(row-1)*.375
            excluded=method=='ez' and math.hypot(x-victim[0],y-victim[1])<.64
            active=(row*4+col+phase*3)%5 not in (1,4)
            pbo=method=='pbo' and col==3
            fill='#E9ECEE' if excluded else 'white' if not active else style.original.ORANGE_PALE if pbo else style.original.BLUE_SELECTED
            color=GRAY if excluded or not active else ORANGE if pbo else BLUE
            ax.add_patch(Polygon(style.hexagon(x,y,.247),fc=fill,ec=color,lw=.8 if excluded else 1,
                                 ls='--' if not active and not excluded else '-',zorder=6))
            if active and not excluded:
                available.append((x,y,pbo))
    if method=='ez':
        ax.add_patch(Circle(victim,.64,fill=False,ec=RED,lw=1.2,zorder=20))
        text(ax,cx+1.08,cy+.39,r'$R_{ez}$',10,RED)
    else:
        ax.plot([cx+.83]*2,[cy-.70,cy+.45],c=GRAY,lw=1.1)
        text(ax,cx+1.04,cy+.49,r'$D_{border}$',10,ORANGE,ha='center')
        victim=(cx+1.02,cy-.30)
    target=style.receiver(ax,victim[0],victim[1]-.17,.045)
    used=set()
    for j,(dx,dy) in enumerate([(-.67+phase*.20,.74),(.62-phase*.12,.93)]):
        source=style.satellite(ax,cx+dx,cy+dy,.87)
        aim=(cx+dx+(.19 if j==0 else -.16),cy-.30+(.20 if j==1 else -.15))
        index=min((i for i in range(len(available)) if i not in used),
                  key=lambda i:(available[i][0]-aim[0])**2+(available[i][1]-aim[1])**2)
        used.add(index)
        x,y,pbo=available[index]
        style.original.beam(ax,source,style.hexagon(x,y,.247),pbo=pbo,broad=True)
        arrow(ax,source,target,RED,linestyle=(0,(4,3)))
    text(ax,victim[0]+.16,victim[1]-.12,'FS',9,RED)

def figure():
    """Encom-style visual workflow; the small CCDF is illustrative only."""
    import numpy as np

    fig,ax=plt.subplots(figsize=(16,9))
    fig.subplots_adjust(0,0,1,1)
    ax.set(xlim=(0,16),ylim=(0,9)); ax.axis('off')
    text(ax,.55,8.46,'SHARC + Monte Carlo',30,BLUE,weight='bold')
    for x,n,title in [(.55,'1','Scenario'),(3.35,'2','Snapshots and mitigation'),
                      (12.0,'3','FS assessment')]:
        text(ax,x,7.62,n,19,BLUE,weight='bold')
        text(ax,x+.32,7.62,title,18,weight='bold')

    text(ax,.55,6.98,'System 3',16,BLUE,weight='bold')
    style.satellite(ax,1.25,6.43,1.45)
    text(ax,.55,5.89,'340 / 525 km',16)
    text(ax,.55,5.48,'LF 20 / 50%',16)
    text(ax,.55,4.80,'Victim FS',16,RED,weight='bold')
    style.receiver(ax,.95,3.50,.09)
    text(ax,.55,3.17,'20 / 40 m',16)
    text(ax,.55,2.50,'Mitigation sweep',15,BLUE,weight='bold')
    text(ax,.55,2.08,'0 to 100 km',16)
    arrow(ax,(2.65,4.55),(3.16,4.55))

    text(ax,3.35,6.95,'Exclusion zone',19,BLUE,weight='bold')
    text(ax,10.95,6.95,'Regional coverage',12,ha='right')
    perspective_snapshot(ax,4.85,4.93,'ez',0)
    perspective_snapshot(ax,8.95,4.93,'ez',1,snapshot_number=10_000)
    text(ax,6.92,5.10,r'$\cdots$',30,BLUE,ha='center')
    ax.plot([3.35,11.15],[3.98,3.98],color='#DCE4E8',lw=1)
    text(ax,3.35,3.60,'Conditional power back-off',19,ORANGE,weight='bold')
    text(ax,10.95,3.60,'Brazil / Argentina',12,ha='right')
    perspective_snapshot(ax,4.85,1.90,'pbo',0)
    perspective_snapshot(ax,8.95,1.90,'pbo',1,snapshot_number=10_000)
    text(ax,6.92,2.07,r'$\cdots$',30,BLUE,ha='center')
    arrow(ax,(11.10,4.55),(11.77,4.55))

    text(ax,13.75,5.98,'CCDF of INR',17,BLUE,ha='center')
    left,right,bottom,top=12.30,15.35,3.72,5.57
    ax.plot([left,left,right],[top,bottom,bottom],color=GRAY,lw=1.25)
    # A decreasing schematic distribution, never a sampled campaign result.
    t=np.linspace(0,1,24)
    ccdf=np.clip(1-t**.75,0,1)
    ax.step(left+.06+t*(right-left-.12),bottom+.06+ccdf*(top-bottom-.12),
            where='post',color=BLUE,lw=2.25)
    text(ax,(left+right)/2,bottom-.25,'INR (dB)',12,ha='center')
    text(ax,left-.24,(bottom+top)/2,'CCDF',11,ha='center',rotation=90)
    text(ax,right,top-.07,'Illustrative',9,GRAY,ha='right')
    text(ax,13.78,2.72,'Compare\nconfigurations',17,ha='center',linespacing=1.5)

    ax.plot([.55,15.45],[1.05,1.05],color='#DCE4E8',lw=1)
    for x,c,label,ls in [(.68,BLUE,'Active','-'),(2.40,GRAY,'Inactive','--'),
                         (4.35,ORANGE,'10 dB back-off','-'),(7.55,GRAY,'Excluded','-')]:
        ax.add_patch(RegularPolygon((x,.78),6,radius=.115,orientation=math.pi/6,
                     fc='#E9ECEE' if c==GRAY and ls=='-' else
                     style.original.ORANGE_PALE if c==ORANGE else
                     style.original.BLUE_SELECTED if c==BLUE else 'white',
                     ec=c,lw=1.6,ls=ls))
        text(ax,x+.22,.78,label,12)
    ax.plot([10.24,10.75],[.78,.78],color=RED,lw=1.7,ls=(0,(4,3)))
    text(ax,10.89,.78,'Interference to FS',12)
    text(ax,15.45,.78,'Schematic',10,GRAY,ha='right')
    text(ax,8,.26,r'1 configuration  $\rightarrow$  10 000 snapshots  $\rightarrow$  FS statistics',
         17,BLUE,ha='center')
    fig._latincom_validation={
        'schematic_not_simulation_data':True,
        'methods':['exclusion zone','conditional power back-off'],
        'snapshots_per_method':2,'satellites_per_snapshot':2,
        'displayed_snapshot_numbers':[1,10_000],
        'ccdf_is_illustrative':True,
        'presentation_style':'Encom visual workflow',
    }
    return fig


def main(output_dir=None,preview=False):
    output_dir=Path(output_dir) if output_dir is not None else OUT
    plt.rcParams.update({'font.family':'DejaVu Sans','pdf.fonttype':42,'svg.fonttype':'none'})
    fig=figure()
    output_dir.mkdir(parents=True,exist_ok=True)
    if not preview:
        for ext in ['png','pdf','svg']:
            path=output_dir/f'dc_mss_fs_mitigation_methodology.{ext}'
            fig.savefig(path,dpi=600,transparent=True,facecolor='none')
            print(path)
    fig.savefig(output_dir/'latincom_sharc_monte_carlo_preview.png',dpi=140,
                transparent=True,facecolor='none')
    plt.close(fig)

if __name__=='__main__':
    main()
