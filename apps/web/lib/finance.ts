/** Presentation calculations only: never change the model, stored values or decisions. */
export const currency = "INR";
export function formatCurrency(value: number | string | null | undefined): string {
  if (value === null || value === undefined || value === "" || !Number.isFinite(Number(value))) return "—";
  return new Intl.NumberFormat("en-IN", { style: "currency", currency, maximumFractionDigits: 0 }).format(Number(value));
}
// Presentation bands: NumPy linear 33rd/66th percentiles of calibrated Lite probabilities
// on 27,822 reserved policy-validation applicants in splits.json (not the final test set).
// Run 20261002T140817Z-045430a7; features_lite_37489e0c27416f0e.parquet.
// Relative historical bands, not lending thresholds; no stored policy/model values change.
export const MODEL_BAND_CUTOFFS = { lowBelow: 0.050386401618192744, highAt: 0.08841984944398855 } as const;
export type RiskLevel = "Low" | "Moderate" | "High";
export function riskLevel(probability: number): "Low" | "Moderate" | "High" {
  if (!Number.isFinite(probability) || probability < 0 || probability > 1) throw new Error("Invalid probability");
  return probability < MODEL_BAND_CUTOFFS.lowBelow ? "Low" : probability < MODEL_BAND_CUTOFFS.highAt ? "Moderate" : "High";
}
export function affordabilityScore(ratio: number): number {
  if (!Number.isFinite(ratio) || ratio < 0) throw new Error("Invalid EMI ratio");
  if (ratio <= 0.2) return 100;
  if (ratio <= 0.4) return 100 - (ratio - 0.2) * 250;
  return Math.max(0, 50 - (ratio - 0.4) * (50 / 0.6));
}
export function estimateEmi(principal: number, months: number, annualRate = 0.12): number {
  if (!Number.isFinite(principal) || principal <= 0 || !Number.isInteger(months) || months < 1 || !Number.isFinite(annualRate) || annualRate < 0) throw new Error("Invalid loan inputs");
  const rate = annualRate / 12;
  return rate === 0 ? principal / months : principal * rate / (1 - Math.pow(1 + rate, -months));
}
export function affordabilityLevel(ratio: number): RiskLevel {
  if (!Number.isFinite(ratio) || ratio < 0) throw new Error("Invalid EMI ratio");
  return ratio <= 0.2 ? "Low" : ratio <= 0.4 ? "Moderate" : "High";
}
export function financialInsights(annualIncome: number, principal: number, months: number, quotedEmi?: number) {
  if (!Number.isFinite(annualIncome) || annualIncome <= 0) return null;
  if (!Number.isFinite(principal) || principal <= 0 || !Number.isInteger(months) || months < 1) return null;
  const monthlyIncome = annualIncome / 12;
  const emi = quotedEmi ?? estimateEmi(principal, months);
  if (!Number.isFinite(emi) || emi <= 0) return null;
  const ratio = emi / monthlyIncome;
  const principalPerEmi = (1 - Math.pow(1.01, -months)) / 0.01;
  const ranges = [
    { label: "Conservative Loan Range", lower: 0.1, upper: 0.2 },
    { label: "Moderate Loan Range", lower: 0.2, upper: 0.25 },
    { label: "Maximum Suggested Loan Range", lower: 0.25, upper: 0.3 },
  ].map(range => ({ ...range, min: monthlyIncome * range.lower * principalPerEmi, max: monthlyIncome * range.upper * principalPerEmi }));
  return { annualIncome, monthlyIncome, principal, months, emi, ratio, assessment: affordabilityLevel(ratio), recommendedMaxEmi: monthlyIncome * 0.3, ranges };
}
