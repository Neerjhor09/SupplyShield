"""SupplyShield decision workspace. Run with streamlit run app.py."""
from pathlib import Path
import io
import json
import zipfile
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from src.optimizer import solve_baseline, solve_risk_aware, solve_tail_aware
from src.evaluation import scenario_evaluation, summary_metrics, cvar
from src.validation import validate_inputs

ROOT=Path(__file__).parent
st.set_page_config(page_title='SupplyShield | Sourcing intelligence',page_icon='◈',layout='wide')
st.markdown('''<style>
.block-container{max-width:1450px;padding-top:2rem}h1{letter-spacing:-1.8px!important;font-size:3rem!important}
[data-testid="stMetric"]{background:white;border:1px solid #E1E8EF;border-radius:14px;padding:18px}
[data-testid="stSidebar"]{border-right:1px solid #E1E8EF}.eyebrow{color:#0D9488;font-size:12px;letter-spacing:3px;font-weight:700}
.hero{padding:26px 30px;border-radius:20px;background:#132C43;color:white;margin-bottom:22px}.hero h1{color:white}.hero p{color:#B9CEDD}
</style>''',unsafe_allow_html=True)
st.markdown('<div class="hero"><div class="eyebrow">SUPPLYSHIELD / DECISION INTELLIGENCE</div><h1>Source with confidence.</h1><p>Understand the price of reliability. Build a sourcing plan for the risks you choose to model.</p></div>',unsafe_allow_html=True)
suppliers=pd.read_csv(ROOT/'data/suppliers.csv')
scenarios=pd.read_csv(ROOT/'data/scenarios.csv',keep_default_na=False)
with st.sidebar:
    st.markdown('### Planning controls')
    demand=st.number_input('Order requirement',min_value=1.,value=float(suppliers.planning_demand.iloc[0]),step=50.)
    q=st.slider('Disruption probability',0.,1.,.25,.01)
    penalty=st.number_input('Shortage penalty · MU/unit',min_value=0.,value=100.,step=10.)
    share=st.slider('Maximum supplier share',.1,1.,.4,.05)
    st.divider()
    st.markdown('### Tail-risk protection')
    confidence=st.select_slider('CVaR confidence',options=[.8,.9,.95,.99],value=.9)
    weight=st.slider('Tail-risk weight',0.,1.,.5,.05)
    st.caption('CVaR measures average shortage cost in the worst probability tail. Higher weight prioritizes protection against severe outcomes.')
    severity=st.slider('Delivery loss during disruption',0.,1.,.8,.05)
    st.caption('MU = illustrative monetary units. Risks and loss severity are assumptions.')
with st.expander('Supplier workbench · edit prices and ordering caps'):
    edited=st.data_editor(suppliers[['supplier','unit_cost','capacity']],disabled=['supplier'],hide_index=True,use_container_width=True)
    suppliers=suppliers.drop(columns=['unit_cost','capacity']).merge(edited,on='supplier',how='left')
    st.caption('Ordering caps are benchmark quantity-band proxies, not measured physical capacities. Changes apply to this session.')
for _,row in scenarios.iterrows():
    if row.scenario!='Normal': scenarios.loc[scenarios.scenario.eq(row.scenario),row.disrupted_supplier]=1-severity
try:
    validate_inputs(suppliers,scenarios)
except ValueError as exc:
    st.error(str(exc));st.stop()
effective=float(np.minimum(suppliers.capacity.astype(float),share*demand).sum())
if effective+1e-7<demand:
    st.error(f'Plan infeasible: effective ordering capacity is {effective:,.0f} units against demand of {demand:,.0f}. Increase the supplier share limit or ordering caps, or reduce demand.');st.stop()
params=dict(shortage_penalty=penalty,total_disruption_prob=q,max_share=share)
solutions={
 'Cost-first':solve_baseline(suppliers,demand,share),
 'Expected-cost':solve_risk_aware(suppliers,scenarios,demand,**params),
 'Tail-protected':solve_tail_aware(suppliers,scenarios,demand,**params,confidence=confidence,tail_weight=weight)}
if any(v[1]!='Optimal' for v in solutions.values()):
    st.error('A solver did not return an optimal plan. Review inputs.');st.stop()
evals={}; records=[]
for label,(a,_,objective) in solutions.items():
    e=scenario_evaluation(a,suppliers,scenarios,demand,penalty,q);evals[label]=e
    m=summary_metrics(a,suppliers,e,demand)
    m.update(strategy=label,tail_shortage_cost=cvar(e.shortage_cost,e.probability,confidence),objective=objective)
    records.append(m)
metrics=pd.DataFrame(records).set_index('strategy')
selected=st.radio('Decision lens',list(solutions),index=1,horizontal=True)
m=metrics.loc[selected]; b=metrics.loc['Cost-first']; cols=st.columns(4)
cols[0].metric('Expected total cost · MU',f'{m.expected_total_cost:,.0f}',f'{m.expected_total_cost-b.expected_total_cost:+,.0f} vs cost-first',delta_color='inverse')
cols[1].metric('Expected fill rate',f'{m.fill_rate:.1%}',f'{100*(m.fill_rate-b.fill_rate):+.1f} pp')
cols[2].metric(f'Tail shortage cost · CVaR {confidence:.0%}',f'{m.tail_shortage_cost:,.0f}',f'{m.tail_shortage_cost-b.tail_shortage_cost:+,.0f}',delta_color='inverse')
cols[3].metric('Supplier concentration · HHI',f'{m.hhi:.3f}',delta_color='off')
allocation=pd.DataFrame({k:v[0] for k,v in solutions.items()}).rename_axis('supplier').reset_index()
colors=['#94A3B8','#0D9488','#6D5CE8']
def chart(fig):
    fig.update_layout(template='plotly_white',paper_bgcolor='rgba(0,0,0,0)',margin=dict(l=10,r=10,t=35,b=15),font=dict(color='#152C43'),legend_title_text='')
    st.plotly_chart(fig,use_container_width=True)
overview,stress,sensitivity,audit=st.tabs(['Allocation studio','Scenario stress test','Sensitivity lab','Method & export'])
with overview:
    left,right=st.columns([2,1])
    with left:
        st.subheader('Where the order goes')
        chart(px.bar(allocation.melt(id_vars='supplier',var_name='Strategy',value_name='Units'),x='supplier',y='Units',color='Strategy',barmode='group',color_discrete_sequence=colors))
    with right:
        st.subheader('Decision brief')
        premium=m.purchase_cost-b.purchase_cost
        savings=b.expected_total_cost-m.expected_total_cost
        st.markdown(f'**{selected}** spends **{premium:,.0f} MU more** upfront than cost-first and changes expected total cost by **{-savings:+,.0f} MU**.')
        st.markdown(f'Expected missing units: **{m.expected_shortage:,.1f}**. Tail shortage cost: **{m.tail_shortage_cost:,.0f} MU**.')
        st.caption('Tail protection can increase expected cost. Compare objectives separately; all strategies use the same scenarios.')
    st.dataframe(allocation,hide_index=True,use_container_width=True)
    limits=suppliers[['supplier','capacity']].copy();limits['effective_cap']=np.minimum(limits.capacity,share*demand);limits['ordered']=limits.supplier.map(solutions[selected][0]);limits['headroom']=limits.effective_cap-limits.ordered
    with st.expander('Binding constraints and remaining headroom'):st.dataframe(limits,hide_index=True)
with stress:
    st.subheader('What happens when supply falls short?')
    long=pd.concat([e.assign(Strategy=k) for k,e in evals.items()],ignore_index=True)
    chart(px.bar(long,x='scenario',y='shortage',color='Strategy',barmode='group',color_discrete_sequence=colors))
    st.dataframe(evals[selected][['scenario','probability','delivered','shortage','total_cost']],hide_index=True,use_container_width=True)
    st.caption('One supplier is disrupted per scenario. The Normal scenario delivers the whole order. The worst scenario is not necessarily the most probable.')
with sensitivity:
    st.subheader('At what risk level does your allocation change?')
    st.caption('Reoptimizes both risk-aware strategies at each probability; prices, caps, severity and other controls stay fixed.')
    if st.button('Run probability sweep',type='primary'):
        rows=[]
        for prob in np.linspace(0,1,11):
            for label in solutions:
                if label=='Cost-first': a=solutions[label][0]
                elif label=='Expected-cost': a=solve_risk_aware(suppliers,scenarios,demand,penalty,prob,share)[0]
                else:a=solve_tail_aware(suppliers,scenarios,demand,penalty,prob,share,confidence,weight)[0]
                e=scenario_evaluation(a,suppliers,scenarios,demand,penalty,prob)
                rows.append(dict(probability=prob,strategy=label,expected_cost=float((e.probability*e.total_cost).sum()),tail_cost=cvar(e.shortage_cost,e.probability,confidence)))
        sweep=pd.DataFrame(rows)
        chart(px.line(sweep,x='probability',y='expected_cost',color='strategy',markers=True,color_discrete_sequence=colors))
        chart(px.line(sweep,x='probability',y='tail_cost',color='strategy',markers=True,color_discrete_sequence=colors))
        st.download_button('Download sensitivity CSV',sweep.to_csv(index=False),'sensitivity.csv')
with audit:
    st.markdown('### Transparent by design')
    st.markdown('Benchmark-derived fixed prices and ordering caps. Assumed disruption shares and severity. Continuous quantities; exact total ordering; no refunds or emergency replenishment. CVaR applies to shortage penalties, not purchase costs.')
    st.dataframe(metrics,use_container_width=True)
    config=dict(demand=demand,disruption_probability=q,penalty=penalty,max_share=share,confidence=confidence,tail_weight=weight,severity=severity)
    mem=io.BytesIO()
    with zipfile.ZipFile(mem,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('allocation.csv',allocation.to_csv(index=False));z.writestr('metrics.csv',metrics.to_csv())
        z.writestr('suppliers.csv',suppliers.to_csv(index=False));z.writestr('scenarios.csv',scenarios.assign(probability=evals[selected].probability.to_numpy()).to_csv(index=False))
        z.writestr('parameters.json',json.dumps(config,indent=2))
        z.writestr('decision_brief.md',f'# SupplyShield decision brief\n\nSelected: {selected}\n\nExpected cost: {m.expected_total_cost:.2f} MU\nExpected fill rate: {m.fill_rate:.2%}\nCVaR shortage cost: {m.tail_shortage_cost:.2f} MU\n\nIllustrative scenarios, not calibrated forecasts.\n')
    st.download_button('Download decision pack',mem.getvalue(),'supplyshield_decision.zip','application/zip',type='primary')
    st.caption('Includes inputs, parameters, allocations, metrics and a decision brief for reproducibility.')
st.caption('SUPPLYSHIELD · Benchmark adaptation / Scenario assumptions / Reproducible optimization')
