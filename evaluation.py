from .validation import scenario_probability
import numpy as np
import pandas as pd



def purchase_cost(allocation, suppliers):
    costs = suppliers.set_index("supplier")["unit_cost"].to_dict()
    return float(sum(float(costs[s]) * float(allocation[s]) for s in allocation))


def hhi(allocation):
    total = float(sum(allocation.values()))
    if total <= 0:
        return 0.0
    shares = np.array([float(v) / total for v in allocation.values()])
    return float(np.square(shares).sum())


def scenario_evaluation(
    allocation,
    suppliers,
    scenarios,
    demand,
    shortage_penalty=100.0,
    total_disruption_prob=0.25,
):
    buy_cost = purchase_cost(allocation, suppliers)
    rows = []
    for _, row in scenarios.iterrows():
        probability = scenario_probability(row, total_disruption_prob)
        delivered = sum(float(row[s]) * float(allocation[s]) for s in allocation)
        shortage = max(float(demand) - delivered, 0.0)
        rows.append({
            "scenario": row["scenario"],
            "probability": probability,
            "delivered": delivered,
            "shortage": shortage,
            "fill_rate": max(0.0, min(delivered / float(demand), 1.0)),
            "purchase_cost": buy_cost,
            "shortage_cost": float(shortage_penalty) * shortage,
            "total_cost": buy_cost + float(shortage_penalty) * shortage,
        })
    return pd.DataFrame(rows)


def summary_metrics(allocation, suppliers, evaluation_df, demand):
    buy_cost = purchase_cost(allocation, suppliers)
    expected_shortage = float(
        (evaluation_df["probability"] * evaluation_df["shortage"]).sum()
    )
    expected_shortage_cost = float(
        (evaluation_df["probability"] * evaluation_df["shortage_cost"]).sum()
    )
    return {
        "purchase_cost": buy_cost,
        "expected_shortage": expected_shortage,
        "expected_shortage_cost": expected_shortage_cost,
        "expected_total_cost": buy_cost + expected_shortage_cost,
        "fill_rate": 1.0 - expected_shortage / float(demand),
        "hhi": hhi(allocation),
    }


def cvar(losses, probabilities, confidence=.9):
    """Exact weighted upper-tail mean, including partial probability atoms."""
    losses=np.asarray(losses,dtype=float); p=np.asarray(probabilities,dtype=float)
    if losses.shape!=p.shape or losses.size==0 or not np.isfinite(losses).all() or not np.isfinite(p).all() or (p<0).any() or not np.isclose(p.sum(),1):
        raise ValueError('Finite losses and normalized nonnegative probabilities required')
    if not 0 <= confidence < 1: raise ValueError('Confidence must be in [0,1)')
    return float(min(t + np.dot(p,np.maximum(losses-t,0))/(1-confidence) for t in losses))
