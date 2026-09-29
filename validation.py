"""Validation for benchmark-derived procurement and assumed disruption scenarios."""
import numpy as np


def validate_suppliers(suppliers):
    required = {'supplier', 'unit_cost', 'capacity'}
    missing = required - set(suppliers.columns)
    if missing:
        raise ValueError(f'Missing supplier columns: {sorted(missing)}')
    if suppliers.empty or suppliers['supplier'].isna().any() or not suppliers['supplier'].is_unique:
        raise ValueError('Supplier names must be present and unique')
    if not suppliers['supplier'].map(lambda x: isinstance(x, str) and bool(x.strip())).all():
        raise ValueError('Supplier names must be nonempty strings')
    try:
        values = suppliers[['unit_cost', 'capacity']].to_numpy(dtype=float)
    except (ValueError, TypeError) as exc:
        raise ValueError('Supplier costs and capacities must be numeric') from exc
    if not np.isfinite(values).all() or (values[:, 0] <= 0).any() or (values[:, 1] < 0).any():
        raise ValueError('Costs must be positive, capacities nonnegative, and all values finite')


def validate_parameters(demand, max_share=1.0, shortage_penalty=0.0, total_disruption_prob=0.0):
    values = np.asarray([demand, max_share, shortage_penalty, total_disruption_prob], dtype=float)
    if not np.isfinite(values).all():
        raise ValueError('Parameters must be finite')
    if demand <= 0 or not 0 < max_share <= 1 or shortage_penalty < 0 or not 0 <= total_disruption_prob <= 1:
        raise ValueError('Demand > 0, share in (0,1], penalty >= 0 and probability in [0,1] required')


def validate_inputs(suppliers, scenarios):
    validate_suppliers(suppliers)
    names = suppliers['supplier'].tolist()
    missing = {'scenario', 'risk_share', *names} - set(scenarios.columns)
    if missing:
        raise ValueError(f'Missing scenario columns: {sorted(missing)}')
    if scenarios.empty or scenarios['scenario'].isna().any() or not scenarios['scenario'].is_unique:
        raise ValueError('Scenario names must be present and unique')
    normal = scenarios['scenario'].eq('Normal')
    if normal.sum() != 1:
        raise ValueError('Exactly one Normal scenario required')
    try:
        values = scenarios[names + ['risk_share']].to_numpy(dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError('Scenario fractions and shares must be numeric') from exc
    if not np.isfinite(values).all() or (values < 0).any() or (values > 1).any():
        raise ValueError('Scenario fractions and shares must be finite and in [0,1]')
    shares = scenarios['risk_share'].astype(float)
    if not np.isclose(shares[~normal].sum(), 1.0) or not np.isclose(shares[normal].iloc[0], 0):
        raise ValueError('Disruption risk shares must sum to one; Normal risk share must be zero')
    if not np.allclose(scenarios.loc[normal, names].to_numpy(dtype=float), 1):
        raise ValueError('Normal scenario must deliver all ordered units')
    return True


def scenario_probability(row, total_disruption_prob):
    """Stored probability is a reference snapshot; controls recompute it."""
    return 1.0 - total_disruption_prob if row['scenario'] == 'Normal' else total_disruption_prob * float(row['risk_share'])
