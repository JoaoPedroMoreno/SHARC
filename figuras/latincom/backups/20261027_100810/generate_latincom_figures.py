"""LATINCOM schematic figures using the existing Encom presentation assets.

All positions are illustrative; no geographic coordinates or measured results
are encoded. The existing satellite PNG is embedded in SVG/PDF exports.
"""
from pathlib import Path
import shutil
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Circle
import numpy as np
import latincom_visual_style as s
import generate_fs_mitigation_methodology as methodology

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'figuras/latincom'

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
    centers=[]
    for row in range(3):
        for col in range(6):
            x=5.95+col*.76+(row%2)*.38
            y=1.40+row*.63
            affected=mode=='pbo' and col==0
            vertices=s.hexagon(x,y,.42)
            ax.add_patch(Polygon(vertices,fc=s.original.ORANGE_PALE if affected else s.original.BLUE_SELECTED,
                                 ec=s.ORANGE if affected else s.BLUE,lw=1.2,zorder=6))
            centers.append((x,y,affected))
    target=s.receiver(ax,4.25,1.48,.105)
    specs=[(6.4,4.95,2.05,7),(9.4,5.40,2.1,16),(8.4,4.4,1.65,3)] if multiple else [(7.7,5.15,2.7,7)]
    for x,y,width,index in specs:
        source=s.satellite(ax,x,y,width)
        for i in [index,index-1]:
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
    region(ax,'pbo',True)
    label(ax,.65,6.22,'DC-MSS / FS coexistence',25,'#387391')
    return fig

def context():
    fig,ax=canvas()
    region(ax,'none',True)
    label(ax,.65,6.22,'Cross-border aggregate interference',25,'#387391')
    label(ax,1.45,4.5,'Several downlinks\nOne victim receiver',17)
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

def save(fig,name):
    for ext in ['png','pdf','svg']:
        fig.savefig(OUT/f'{name}.{ext}',dpi=600,transparent=ext=='png',facecolor='none' if ext=='png' else 'white')
    fig.savefig(OUT/f'{name}_preview.png',dpi=140,facecolor='white')
    plt.close(fig)

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    plt.rcParams.update({'font.family':'DejaVu Sans','pdf.fonttype':42,'svg.fonttype':'none'})
    for name,build in [('latincom_cover',cover),('latincom_page_2',context),('latincom_page_3',methods)]:
        save(build(),name)
        print(name,flush=True)
    methodology.main()
    for ext in ['png','pdf','svg']:
        shutil.copy2(ROOT/f'figuras/dc_mss_fs_mitigation_methodology.{ext}',OUT/f'latincom_sharc_monte_carlo.{ext}')

if __name__=='__main__':
    main()
