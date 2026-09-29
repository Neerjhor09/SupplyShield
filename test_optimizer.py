import pandas as pd

from src.optimizer import solve_baseline, solve_risk_aware
from src.validation import validate_inputs


def demo_data():
    suppliers = pd.DataFrame({
        "supplier": ["A", "B", "C"],
        "unit_cost": [10.0, 11.0, 12.0],
        "capacity": [80.0, 80.0, 80.0],
        "risk_share": [0.60, 0.25, 0.15],
    })
    scenarios = pd.DataFrame([
        {"scenario": "Normal", "disrupted_supplier": "None", "risk_share": 0.0, "A": 1.0, "B": 1.0, "C": 1.0},
        {"scenario": "A Disruption", "disrupted_supplier": "A", "risk_share": 0.60, "A": 0.2, "B": 1.0, "C": 1.0},
        {"scenario": "B Disruption", "disrupted_supplier": "B", "risk_share": 0.25, "A": 1.0, "B": 0.2, "C": 1.0},
        {"scenario": "C Disruption", "disrupted_supplier": "C", "risk_share": 0.15, "A": 1.0, "B": 1.0, "C": 0.2},
    ])
    return suppliers, scenarios


def test_validation():
    suppliers, scenarios = demo_data()
    assert validate_inputs(suppliers, scenarios) is True


def test_baseline_is_feasible():
    suppliers, _ = demo_data()
    allocation, status, _ = solve_baseline(suppliers, demand=100.0, max_share=0.60)
    assert status == "Optimal"
    assert abs(sum(allocation.values()) - 100.0) < 1e-6
    assert max(allocation.values()) <= 60.0 + 1e-6


def test_risk_aware_is_feasible():
    suppliers, scenarios = demo_data()
    allocation, status, objective = solve_risk_aware(
        suppliers,
        scenarios,
        demand=100.0,
        shortage_penalty=100.0,
        total_disruption_prob=0.30,
        max_share=0.60,
    )
    assert status == "Optimal"
    assert abs(sum(allocation.values()) - 100.0) < 1e-6
    assert objective is not None and objective > 0

import pytest
from src.evaluation import scenario_evaluation, summary_metrics

@pytest.mark.parametrize('q,penalty', [(0,100),(.3,0),(.3,100),(1,100)])
def test_common_evaluation_and_limits(q, penalty):
    s, scenarios = demo_data()
    base, _, base_cost = solve_baseline(s,100,.6)
    risk, status, objective = solve_risk_aware(s,scenarios,100,penalty,q,.6)
    assert status == 'Optimal'
    def metrics(a):
        e = scenario_evaluation(a,s,scenarios,100,penalty,q)
        assert e.probability.sum() == pytest.approx(1)
        return summary_metrics(a,s,e,100)
    b,r = metrics(base),metrics(risk)
    assert r['expected_total_cost'] <= b['expected_total_cost'] + 1e-6
    assert objective == pytest.approx(r['expected_total_cost'])
    if q == 0 or penalty == 0:
        assert r['purchase_cost'] == pytest.approx(base_cost)


def test_infeasible_never_returns_allocation():
    s, scenarios = demo_data()
    a, status, objective = solve_baseline(s,100,.2)
    assert status == 'Infeasible' and a == {} and objective is None

@pytest.mark.parametrize('problem', ['missing','duplicate','nan','negative_share','bad_sum','normal'])
def test_rejects_invalid_inputs(problem):
    s,c = demo_data()
    if problem == 'missing': s=s.drop(columns='supplier')
    if problem == 'duplicate': s.loc[1,'supplier']='A'
    if problem == 'nan': c.loc[1,'A']=float('nan')
    if problem == 'negative_share': c.loc[1,'risk_share']=-.6
    if problem == 'bad_sum': c.loc[1,'risk_share']=.1
    if problem == 'normal': c.loc[0,'A']=.5
    with pytest.raises(ValueError): validate_inputs(s,c)


def test_packaged_data():
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    s=pd.read_csv(root/'data/suppliers.csv')
    c=pd.read_csv(root/'data/scenarios.csv',keep_default_na=False)
    validate_inputs(s,c)
    a,status,_=solve_risk_aware(s,c,1740)
    assert status=='Optimal'
    assert sum(a.values())==pytest.approx(1740)


def test_dashboard_smoke():
    from pathlib import Path
    from streamlit.testing.v1 import AppTest
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py')).run(timeout=30)
    assert not app.exception
    assert len(app.metric)==4
    app.number_input[0].set_value(10000.0).run()
    assert not app.exception
    assert len(app.error)==1


from src.optimizer import solve_tail_aware
from src.evaluation import cvar

def test_cvar_partial_atom():
    assert cvar([0,100],[.95,.05],.9)==pytest.approx(50)

def test_tail_objective_matches_evaluation():
    s,c=demo_data()
    a,status,obj=solve_tail_aware(s,c,100,100,.3,.6,.9,.5)
    e=scenario_evaluation(a,s,c,100,100,.3)
    expected=(e.probability*e.shortage_cost).sum()
    purchase=e.purchase_cost.iloc[0]
    assert status=='Optimal'
    assert obj==pytest.approx(purchase+.5*expected+.5*cvar(e.shortage_cost,e.probability,.9))

def test_zero_tail_weight_matches_expected():
    s,c=demo_data()
    _,_,expected=solve_risk_aware(s,c,100,100,.3,.6)
    _,_,tail=solve_tail_aware(s,c,100,100,.3,.6,.9,0)
    assert tail==pytest.approx(expected)

def test_tail_rejects_invalid_confidence():
    s,c=demo_data()
    with pytest.raises(ValueError): solve_tail_aware(s,c,100,confidence=1)

def test_sensitivity_workflow():
    from pathlib import Path
    from streamlit.testing.v1 import AppTest
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py')).run(timeout=30)
    app.button[0].click().run(timeout=30)
    assert not app.exception
    app.radio[0].set_value('Tail-protected').run()
    assert not app.exception
