# A-Lin Institutional Valuation Framework
Author: Senior Analyst Framework
Purpose: Structured Three-Axis Valuation Model

------------------------------------------------------------
SECTION 1 — DISCOUNTED CASH FLOW (DCF)
------------------------------------------------------------

## Step 1: Free Cash Flow to Firm (FCFF)

FCFF = EBIT × (1 - Tax Rate)
       + Depreciation & Amortization
       - Maintenance CapEx
       - Change in Net Working Capital

------------------------------------------------------------

## Step 2: Weighted Average Cost of Capital (WACC)

WACC = (E / (D + E)) × Re
     + (D / (D + E)) × Rd × (1 - Tax Rate)

Where:
Re = Risk-Free Rate + Beta × Equity Risk Premium
Rd = Cost of Debt

------------------------------------------------------------

## Step 3: Stage 1 Projection (Years 1–N)

FCFF_t = FCFF_0 × (1 + g_t)^t

Present Value (Stage 1) =
Σ [ FCFF_t / (1 + WACC)^t ]

------------------------------------------------------------

## Step 4: Terminal Value (Gordon Growth Model)

Terminal Value (TV) =
FCFF_(N+1) / (WACC - g_terminal)

Where:
g_terminal ≤ Long-Term GDP Growth

------------------------------------------------------------

## Step 5: Enterprise Value

EV = Present Value (Stage 1)
   + TV / (1 + WACC)^N

------------------------------------------------------------

## Step 6: Equity Value

Equity Value = EV
             - Net Debt
             + Non-operating Assets

Per Share Value =
Equity Value / Diluted Shares Outstanding

------------------------------------------------------------
SECTION 2 — RELATIVE VALUATION (EV/EBITDA)
------------------------------------------------------------

## Enterprise Value

EV = Market Cap
   + Total Debt
   + Minority Interest
   - Cash & Equivalents

------------------------------------------------------------

## EV/EBITDA Multiple

EV/EBITDA = Enterprise Value / EBITDA

------------------------------------------------------------

## Implied Equity Value from Target Multiple

Implied EV =
Target Multiple × EBITDA

Implied Equity Value =
Implied EV - Net Debt

Implied Share Price =
Implied Equity Value / Shares Outstanding

------------------------------------------------------------
SECTION 3 — EARNINGS POWER VALUE (EPV)
------------------------------------------------------------

## Step 1: Normalized EBIT

Normalized EBIT =
Mid-cycle Revenue × Normalized Margin

------------------------------------------------------------

## Step 2: Adjusted Earnings (Zero Growth Assumption)

EPV Earnings =
Normalized EBIT × (1 - Tax Rate)

------------------------------------------------------------

## Step 3: EPV Enterprise Value

EPV_EV =
EPV Earnings / WACC

------------------------------------------------------------

## Step 4: EPV Equity Value

EPV Equity =
EPV_EV
- Net Debt
+ Excess Cash

EPV Per Share =
EPV Equity / Shares Outstanding

------------------------------------------------------------
SECTION 4 — MARGIN OF SAFETY
------------------------------------------------------------

Entry Price =
Intrinsic Value × (1 - Safety Discount)

Typical Safety Discount:
20% – 40%

------------------------------------------------------------
SECTION 5 — TRIANGULATION DECISION MODEL
------------------------------------------------------------

Case A:
DCF ≈ EPV ≈ Relative
→ Fairly Valued

Case B:
DCF >> EPV & Relative Low
→ Deep Value

Case C:
DCF << Market Price
→ Bubble Risk

Case D:
EPV > Market Price
→ Downside Protected