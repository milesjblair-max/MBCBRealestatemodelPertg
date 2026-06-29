// Finance: turn a user's income and cash position into a budget band and a
// buy-timing posture. This is the "adaptable" part - the same market looks
// different to a cash-rich buyer with a 0% facility than to a renting first-home
// buyer with a small deposit, and the model should say so.
//
// Simplified but defensible serviceability. Macro constants are mid-2026; refresh
// when the RBA prints. Not financial advice.

import type { BuyerProfile, BudgetBand, BuyTiming } from "./types.js";

const CASH_RATE = 4.35; // RBA cash rate, mid-2026
const MORTGAGE_SPREAD = 2.0; // owner-occupier rate over cash
const APRA_BUFFER = 3.0; // serviceability assessment buffer
const DSR = 0.35; // share of gross income available for repayments
const TERM_MONTHS = 360;
const TX_COSTS = 0.055; // stamp duty + fees as a share of price
const MIN_DEPOSIT = 0.1; // 90% LVR prudent floor
const EQUITY_LVR = 0.8; // usable equity = 80% of value minus the mortgage
const DEFAULT_EQUITY_RATE = CASH_RATE + MORTGAGE_SPREAD; // equity release is a normal loan

/** Monthly interest-only carrying cost of borrowed money at a given rate. Zero
 *  at a zero rate (an interest-free facility you can simply hold), so it scales
 *  smoothly: this is what makes borrowed funds cost capacity and cash not. */
function carryingCost(amount: number, ratePct: number): number {
  return amount > 0 && ratePct > 0 ? (amount * (ratePct / 100)) / 12 : 0;
}

/** Max loan from income, assessed at the buffered rate over 30 years. */
export function borrowingCapacity(income: number, monthlyCommitments = 0): number {
  const grossMonthly = income / 12;
  const maxRepay = Math.max(0, grossMonthly * DSR - monthlyCommitments);
  const annual = (CASH_RATE + MORTGAGE_SPREAD + APRA_BUFFER) / 100;
  const r = annual / 12;
  const loan = r > 0 ? (maxRepay * (1 - (1 + r) ** -TERM_MONTHS)) / r : maxRepay * TERM_MONTHS;
  return Math.round(loan);
}

/** The price band the buyer can realistically shop in.
 *
 * Cash (deposit + buffer) and BORROWED funds (a credit facility, or equity
 * released from a property you already own) both help cover the price, but they
 * are not the same: borrowed funds carry a servicing cost that eats into how
 * much you can safely borrow for the new home. Treating released equity as if it
 * were cash (the old behaviour) overstates the safe budget for anyone whose
 * facility is not interest-free. Interest-free money still behaves like cash. */
export function budgetBand(p: BuyerProfile): BudgetBand {
  const f = p.finances ?? {};
  const cash = (f.deposit ?? 0) + (f.cash_buffer ?? 0);

  // Released equity: take it directly, or compute usable equity from the
  // property's value and outstanding mortgage at an 80% LVR.
  const usableEquity =
    f.equity_release ??
    (f.property_value != null
      ? Math.max(0, f.property_value * EQUITY_LVR - (f.property_mortgage ?? 0))
      : 0);
  const equityRate = f.equity_rate_pct ?? DEFAULT_EQUITY_RATE;

  const creditLine = f.credit_line ?? 0;
  const creditRate = f.credit_rate_pct ?? 0; // a stated facility; 0 if interest-free

  const borrowedFunds = creditLine + usableEquity;

  // Borrowed funds reduce serviceability by their carrying cost; cash does not.
  const servicing =
    carryingCost(creditLine, creditRate) + carryingCost(usableEquity, equityRate);
  const loan = borrowingCapacity(p.income ?? 0, (f.monthly_commitments ?? 0) + servicing);

  const ownFunds = cash + borrowedFunds; // money brought to cover price + costs
  // Bound 1: total funds (loan + own funds) must cover price + transaction costs.
  const byFunds = (loan + ownFunds) / (1 + TX_COSTS);
  // Bound 2: own funds must cover the minimum deposit + costs (LVR cap).
  const byDeposit = ownFunds / (MIN_DEPOSIT + TX_COSTS);

  const ceiling = Math.round(Math.min(byFunds, byDeposit));
  const floor = Math.round(ceiling * 0.72); // sensible bottom of the shopping band
  return {
    floor,
    ceiling,
    borrowingCapacity: loan,
    cash: Math.round(cash),
    borrowedFunds: Math.round(borrowedFunds),
    monthlyServicing: Math.round(servicing),
  };
}

/** How urgently this buyer should act, derived from their cash position. */
export function buyTiming(p: BuyerProfile, budget: BudgetBand): BuyTiming {
  const f = p.finances ?? {};
  const ownFunds = (f.deposit ?? 0) + (f.cash_buffer ?? 0);
  const rationale: string[] = [];
  let urgency = 50;

  if (f.currently_renting) {
    urgency += 20;
    rationale.push("Paying rent now, so waiting has a real holding cost.");
  } else {
    rationale.push("Low holding cost (not renting), so waiting is cheap.");
  }

  const fundsRatio = budget.ceiling > 0 ? ownFunds / budget.ceiling : 0;
  if (fundsRatio < 0.2) {
    urgency += 15;
    rationale.push("Deposit is thin relative to budget, so buy when serviceable rather than trying to time a dip.");
  } else if (fundsRatio > 0.4) {
    urgency -= 15;
    rationale.push("Strong cash position can weather a soft patch.");
  }

  if ((f.credit_line ?? 0) > 0 && (f.credit_rate_pct ?? 99) < 2) {
    urgency -= 20;
    rationale.push("A low/zero-interest facility makes holding cheap, so you can be patient and opportunistic.");
  }

  const horizon = p.horizon_years ?? 3;
  if (horizon < 2) {
    urgency += 10;
    rationale.push("Short horizon favours acting sooner.");
  } else if (horizon >= 4) {
    urgency -= 10;
    rationale.push("Long horizon leaves room to wait for the better entry.");
  }

  if ((p.age ?? 35) > 55) {
    urgency += 10;
    rationale.push("Shorter hold horizon at this life stage favours acting sooner.");
  } else if ((p.age ?? 35) < 30) {
    urgency -= 5;
  }

  urgency = Math.max(0, Math.min(100, urgency));
  const posture: BuyTiming["posture"] =
    urgency >= 65 ? "act-now" : urgency < 40 ? "patient-opportunistic" : "balanced";

  if (posture === "patient-opportunistic")
    rationale.push("Model view: a resources-led soft patch is likely around 2027; your position lets you wait for it.");
  else if (posture === "act-now")
    rationale.push("Model view: do not over-time the market; buy a good fit within budget when you find it.");

  return { posture, urgency, rationale };
}
