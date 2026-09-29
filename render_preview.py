"""Render a reproducible results overview, not a Streamlit screenshot.
Run: python -m docs.render_preview
"""
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from src.optimizer import solve_baseline, solve_risk_aware
from src.evaluation import scenario_evaluation, summary_metrics
ROOT=Path(__file__).resolve().parents[1]
s=pd.read_csv(ROOT/'data/suppliers.csv'); c=pd.read_csv(ROOT/'data/scenarios.csv',keep_default_na=False)
b,_,_=solve_baseline(s,1740); r,_,_=solve_risk_aware(s,c,1740)
metrics=[]; evaluations=[]
for a in [b,r]:
 e=scenario_evaluation(a,s,c,1740); evaluations.append(e);metrics.append(summary_metrics(a,s,e,1740))
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False})
fig=plt.figure(figsize=(14,8),facecolor='#f3f6fa'); gs=fig.add_gridspec(2,2,height_ratios=[1,3],hspace=.55,wspace=.25)
fig.suptitle('SupplyShield  /  Procurement decision lab',x=.07,ha='left',fontsize=23,fontweight='bold',color='#12253d')
fig.text(.07,.905,'DEFAULT SCENARIO · 1,740 units · 25% disruption probability · 100 MU shortage penalty',fontsize=10,color='#52667c')
ax=fig.add_subplot(gs[0,:]);ax.axis('off')
for x,label,key,fmt in [(0,'Expected total cost','expected_total_cost',',.0f'),(.27,'Expected shortage','expected_shortage',',.1f'),(.54,'Expected fill rate','fill_rate','.1%'),(.81,'Concentration HHI','hhi','.3f')]:
 ax.text(x,.85,label,fontsize=11,color='#52667c');ax.text(x,.38,format(metrics[1][key],fmt),fontsize=25,fontweight='bold',color='#087f8c');ax.text(x,.02,'Baseline '+format(metrics[0][key],fmt),fontsize=10)
ax=fig.add_subplot(gs[1,0]); pd.DataFrame({'Baseline':b,'Risk-aware':r}).plot.bar(ax=ax,color=['#9baac0','#087f8c'],rot=0); ax.set_title('Order allocation',loc='left',fontweight='bold');ax.set_ylabel('Units');ax.legend(frameon=False)
ax=fig.add_subplot(gs[1,1]); pd.DataFrame({'Baseline':evaluations[0].shortage.values[1:],'Risk-aware':evaluations[1].shortage.values[1:]},index=['S1 fails','S2 fails','S3 fails','S4 fails','S5 fails']).plot.bar(ax=ax,color=['#9baac0','#087f8c'],rot=0);ax.set_title('Shortage by disruption scenario',loc='left',fontweight='bold');ax.set_ylabel('Missing units');ax.legend(frameon=False)
fig.text(.07,.035,'Illustrative benchmark adaptation · Assumed risks · Static results preview; not a live app screenshot',fontsize=10,color='#52667c')
fig.subplots_adjust(top=.84,bottom=.14,left=.07,right=.97)
fig.savefig(ROOT/'docs/dashboard.png',dpi=150);print(metrics)
