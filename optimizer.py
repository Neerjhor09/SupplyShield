"""Continuous procurement allocation using PuLP and bundled CBC."""
from .validation import validate_suppliers, validate_inputs, validate_parameters, scenario_probability
from pulp import LpProblem, LpMinimize, LpVariable, LpStatus, PULP_CBC_CMD, lpSum, value


def _add_shared_constraints(model, x, suppliers, demand, max_share):
    model += lpSum(x[s] for s in suppliers["supplier"]) == demand
    for row in suppliers.itertuples(index=False):
        model += x[row.supplier] <= float(row.capacity)
        model += x[row.supplier] <= float(max_share) * float(demand)



def solve_baseline(suppliers, demand, max_share=0.40, solver_msg=False):
    validate_suppliers(suppliers)
    validate_parameters(demand, max_share)
    supplier_names = suppliers["supplier"].tolist()
    costs = suppliers.set_index("supplier")["unit_cost"].to_dict()

    model = LpProblem("SupplyShield_Baseline", LpMinimize)
    x = {s: LpVariable(f"x_{i}", lowBound=0) for i, s in enumerate(supplier_names)}
    _add_shared_constraints(model, x, suppliers, demand, max_share)
    model += lpSum(float(costs[s]) * x[s] for s in supplier_names)
    model.solve(PULP_CBC_CMD(msg=solver_msg))

    status = LpStatus[model.status]
    if status != "Optimal":
        return {}, status, None
    allocation = {s: float(x[s].value() or 0.0) for s in supplier_names}
    objective = float(value(model.objective)) if model.objective is not None else None
    return allocation, status, objective


def solve_risk_aware(
    suppliers,
    scenarios,
    demand,
    shortage_penalty=100.0,
    total_disruption_prob=0.25,
    max_share=0.40,
    solver_msg=False,
):
    validate_inputs(suppliers, scenarios)
    validate_parameters(demand, max_share, shortage_penalty, total_disruption_prob)
    supplier_names = suppliers["supplier"].tolist()
    costs = suppliers.set_index("supplier")["unit_cost"].to_dict()

    model = LpProblem("SupplyShield_RiskAware", LpMinimize)
    x = {s: LpVariable(f"x_{i}", lowBound=0) for i, s in enumerate(supplier_names)}
    shortage = {
        row["scenario"]: LpVariable(f"shortage_{i}", lowBound=0)
        for i, (_, row) in enumerate(scenarios.iterrows())
    }

    _add_shared_constraints(model, x, suppliers, demand, max_share)

    for _, row in scenarios.iterrows():
        delivered = lpSum(float(row[s]) * x[s] for s in supplier_names)
        model += shortage[row["scenario"]] >= float(demand) - delivered

    purchase = lpSum(float(costs[s]) * x[s] for s in supplier_names)
    expected_shortage = lpSum(
        scenario_probability(row, total_disruption_prob) * shortage[row["scenario"]]
        for _, row in scenarios.iterrows()
    )
    model += purchase + float(shortage_penalty) * expected_shortage
    model.solve(PULP_CBC_CMD(msg=solver_msg))

    status = LpStatus[model.status]
    if status != "Optimal":
        return {}, status, None
    allocation = {s: float(x[s].value() or 0.0) for s in supplier_names}
    objective = float(value(model.objective)) if model.objective is not None else None
    return allocation, status, objective


def solve_tail_aware(suppliers, scenarios, demand, shortage_penalty=100.0,
                     total_disruption_prob=.25, max_share=.4, confidence=.9,
                     tail_weight=.5):
    """Minimize purchase + blended expected and CVaR shortage costs."""
    import math
    validate_inputs(suppliers, scenarios)
    validate_parameters(demand, max_share, shortage_penalty, total_disruption_prob)
    if not math.isfinite(confidence) or not 0 <= confidence < 1:
        raise ValueError('Confidence must be in [0,1)')
    if not math.isfinite(tail_weight) or not 0 <= tail_weight <= 1:
        raise ValueError('Tail weight must be in [0,1]')
    names=suppliers.supplier.tolist()
    model=LpProblem('SupplyShield_TailRisk', LpMinimize)
    x={s:LpVariable(f'x_{i}',lowBound=0) for i,s in enumerate(names)}
    _add_shared_constraints(model,x,suppliers,demand,max_share)
    eta=LpVariable('tail_threshold',lowBound=0)
    losses=[]; excesses=[]; probs=[]
    for i,(_,row) in enumerate(scenarios.iterrows()):
        u=LpVariable(f'short_{i}',lowBound=0)
        z=LpVariable(f'excess_{i}',lowBound=0)
        model += u >= demand-lpSum(float(row[s])*x[s] for s in names)
        loss=shortage_penalty*u
        model += z >= loss-eta
        losses.append(loss);excesses.append(z);probs.append(scenario_probability(row,total_disruption_prob))
    purchase=lpSum(float(r.unit_cost)*x[r.supplier] for r in suppliers.itertuples())
    expected=lpSum(p*l for p,l in zip(probs,losses))
    tail=eta+lpSum(p*z for p,z in zip(probs,excesses))/(1-confidence)
    model += purchase+(1-tail_weight)*expected+tail_weight*tail
    model.solve(PULP_CBC_CMD(msg=False))
    status=LpStatus[model.status]
    if status!='Optimal': return {},status,None
    return {s:float(x[s].value() or 0) for s in names},status,float(value(model.objective))
