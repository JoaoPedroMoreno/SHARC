"""Deterministic presentation diagram; geometry is schematic, not simulation data."""
from pathlib import Path
import math
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle, RegularPolygon, Polygon, Arc
import latincom_visual_style as style

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

def main(output_dir=None):
    output_dir=Path(output_dir) if output_dir is not None else OUT
    plt.rcParams.update({'font.family':'DejaVu Sans','pdf.fonttype':42,'svg.fonttype':'none'})
    fig,ax=plt.subplots(figsize=(16,9))
    fig.subplots_adjust(0,0,1,1)
    ax.set(xlim=(0,16),ylim=(0,9)); ax.axis('off')
    text(ax,.55,8.45,'SHARC + Monte Carlo',30,BLUE,weight='bold')
    text(ax,.55,7.94,'DC-MSS downlink interference mitigation at a victim FS receiver',17)
    for x,n,title in [(.55,'1','Scenario setup'),(4.1,'2','Two mitigation methods'),(11.65,'3','FS protection assessment')]:
        text(ax,x,7.22,n,19,BLUE,weight='bold')
        text(ax,x+.35,7.22,title,18,weight='bold')
    ax.plot([.55,15.45],[7.58,7.58],color='#DCE4E8',lw=1)
    text(ax,.55,6.47,'System 3 constellation',16,BLUE,weight='bold')
    text(ax,.55,5.99,'Altitude: 340 / 525 km\nLoad factor: 20 / 50%',14,linespacing=1.7)
    text(ax,.55,5.12,'Victim: terrestrial FS',16,RED,weight='bold')
    text(ax,.55,4.64,'Tower height: 20 / 40 m\nCo-channel downlink',14,linespacing=1.7)
    text(ax,.55,3.68,'Mitigation sweep',16,BLUE,weight='bold')
    text(ax,.55,3.12,'Radius / border-strip width\n0 to 100 km, in 10 km steps',13,linespacing=1.7)
    text(ax,.55,1.91,'Repeat for every\nscenario configuration',14,weight='bold',linespacing=1.5)
    arrow(ax,(3.42,4.55),(3.94,4.55))
    text(ax,4.1,6.65,'A  Exclusion zone',17,BLUE,weight='bold')
    text(ax,4.1,6.23,'Regional coverage: exclude cells around the FS.',12)
    snapshot(ax,5.55,4.78,'ez',0)
    snapshot(ax,9.02,4.78,'ez',1)
    arrow(ax,(7.07,4.68),(7.47,4.68))
    ax.plot([4.1,11.05],[3.64,3.64],color='#DCE4E8',lw=1)
    text(ax,4.1,3.35,'B  Conditional power back-off',17,ORANGE,weight='bold')
    text(ax,4.1,2.97,'Brazil / Argentina: 10 dB reduction in the border strip.',12)
    snapshot(ax,5.55,1.56,'pbo',0)
    snapshot(ax,9.02,1.56,'pbo',1)
    arrow(ax,(7.07,1.46),(7.47,1.46))
    arrow(ax,(11.05,4.55),(11.55,4.55))
    text(ax,11.65,6.51,'For each snapshot',16,BLUE,weight='bold')
    text(ax,11.65,5.94,'New satellite positions and\ncell activity; apply mitigation.',13,linespacing=1.6)
    text(ax,11.65,5.08,'Sum interference at the FS\nin linear power units:',13,linespacing=1.6)
    text(ax,11.65,4.46,r'$I_{agg}=\sum_i I_i\quad\mathrm{INR}=10\log_{10}(I_{agg}/N_{FS})$',14)
    text(ax,11.65,3.64,'Across N snapshots',16,BLUE,weight='bold')
    text(ax,11.65,3.04,'CCDF: P(INR > x)\nINR at 20% exceedance',14,linespacing=1.7)
    text(ax,11.65,2.20,r'$M_{20}=-6\ \mathrm{dB}-\mathrm{INR}_{20\%}$',17,BLUE)
    text(ax,11.65,1.60,'Positive margin: criterion met\nNegative margin: criterion exceeded',12,linespacing=1.6)
    ax.plot([.55,15.45],[.74,.74],color='#DCE4E8',lw=1)
    for x,c,label,ls in [( .65,BLUE,'Active','-'),(2.45,GRAY,'Inactive','--'),(4.6,ORANGE,'10 dB back-off','-'),(7.9,GRAY,'Excluded','-')]:
        ax.add_patch(RegularPolygon((x,.39),6,radius=.12,orientation=math.pi/6,fc='#E9ECEE' if c==GRAY and ls=='-' else 'white',ec=c,lw=1.6,ls=ls))
        text(ax,x+.23,.39,label,12)
    ax.plot([10.65,11.16],[.39,.39],color=RED,lw=1.7,ls=(0,(4,3)))
    text(ax,11.3,.39,'Interference to FS',12)
    text(ax,15.45,.39,'Schematic',10,GRAY,ha='right')
    output_dir.mkdir(parents=True,exist_ok=True)
    for ext in ['png','pdf','svg']:
        path=output_dir/f'dc_mss_fs_mitigation_methodology.{ext}'
        fig.savefig(path,dpi=600,facecolor='white')
        print(path)
    fig.savefig(output_dir/'latincom_sharc_monte_carlo_preview.png',dpi=140,facecolor='white')
    plt.close(fig)

if __name__=='__main__':
    main()
