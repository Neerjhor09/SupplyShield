# Methodology and provenance

## Data
The supplied CSVs contain five suppliers and six scenarios, preserving the user's
working prototype rather than reducing it to the earlier four-supplier sketch.
Procurement inputs are attributed to Hamdan and Cheaitou (2017), *Datasets for
supplier selection and order allocation with green criteria, all-unit quantity
discounts and varying number of suppliers*, Data in Brief 13, 444–452.
https://doi.org/10.1016/j.dib.2017.06.018 (open-access CC BY 4.0 article).
These are generated research benchmark inputs, not observed supplier transactions.
The supplied notebook identifies Input.xlsx period 1 and QDiscount.xlsx as sources.
CSV values are preserved as supplied; this release does not claim to reproduce the
original multi-period, quantity-discount optimization study.

| Field | Interpretation |
|---|---|
| unit_cost | First price tier applied to all quantities: explicit fixed-price approximation |
| capacity | Maximum quantity-band endpoint used as an ordering cap, not verified physical capacity |
| planning_demand | 1,740 units from supplied period-1 extraction |
| green/traditional weights and composite_score | Descriptive only, unused by optimizer |
| risk_share | Assumed conditional disruption share, not an empirical failure probability |
| probability in scenarios.csv | Reference snapshot at q=0.25; recomputed at runtime |

## Decisions and constraints
Continuous ordered quantities x_i satisfy sum(x_i)=D and
0 <= x_i <= min(K_i, alpha*D). Capacity and share constraints can make an instance
infeasible. In that case no allocation is returned. Each ordered unit is paid for,
including disrupted units; there are no refunds, emergency orders or inventory.
Currency is unspecified; the dashboard uses illustrative monetary units (MU).

Baseline minimizes sum(c_i*x_i). Risk-aware minimizes
sum(c_i*x_i) + penalty * sum(p_s*u_s), with
u_s >= D - sum(a_si*x_i) and u_s >= 0.
Both solutions are evaluated with shortages recomputed from actual allocations.
This matters at zero penalty, when solver shortage variables are not unique.

## Scenario probabilities
Normal has probability 1-q. Each disruption scenario has probability q*risk_share.
Conditional shares sum to one. Exactly one supplier loses 80% of deliveries in
each supplied disruption scenario; simultaneous failures are excluded. The model
can accept other delivery-fraction matrices, but the scenario set is an assumption.
The shortage penalty of 100 MU/unit is also a scenario assumption.

## Interpretation and limitations
Expected cost is purchase cost plus expected shortage penalty. Expected fill rate
is 1 - expected shortage/D. HHI is the sum of squared order shares. Diversification
is not guaranteed to rise: the objective rewards expected cost, not diversity itself.
Because total orders equal demand and delivery fractions are bounded by one,
shortage equals sum((1-a_si)*x_i). Thus this model is equivalent to allocating by
risk-adjusted unit costs. Under this linear expectation objective, correlation
alone does not change the result if marginal expected delivery fractions stay
fixed. Tail-risk or service-level constraints would be needed to study that effect.

Baseline ties can produce different risk exposure for equal purchase cost;
reported comparisons refer to the particular optimal baseline returned by CBC.
Results are illustrative decision experiments, not calibrated supplier forecasts.

## Version 2: Tail-protected strategy
Let L_s = penalty * shortage_s. CVaR at confidence beta is
min_eta eta + sum(p_s * max(L_s-eta,0))/(1-beta). The third LP minimizes
purchase + (1-w)*E[L] + w*CVaR_beta(L), with w between zero and one.
Linear excess variables implement the positive-part expression. The evaluator
independently computes discrete CVaR, including partial probability atoms.
The third strategy may sacrifice expected performance for lower tail exposure.
Unlike the expectation-only model, this objective responds to joint loss patterns;
however the supplied scenarios still exclude simultaneous disruptions.
The severity control changes the disrupted supplier's delivered fraction to
1-severity. Scenario probabilities continue to be q times conditional shares.
