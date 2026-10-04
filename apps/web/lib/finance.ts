/** Presentation calculations only: never change the model, stored values or decisions. */
export const currency = "INR";
export function formatCurrency(value: number | string | null | undefined): string {
  if (value === null || value === undefined || value === "" || !Number.isFinite(Number(value))) return "—";
  return new Intl.NumberFormat("en-IN", { style: "currency", currency, maximumFractionDigits: 0 }).format(Number(value));
}
export function riskLevel(probability: number): "Low" | "Moderate" | "High" {
  if (!Number.isFinite(probability) || probability < 0 || probability > 1) throw new Error("Invalid probability");
  return probability < 0.05 ? "Low" : probability < 0.15 ? "Moderate" : "High";
}
export function financialHealth(probability: number): number {
  riskLevel(probability);
  return Math.round((1 - probability) * 10000) / 100;
}
export function estimateEmi(principal: number, months: number, annualRate = 0.12): number {
  if (!Number.isFinite(principal) || principal <= 0 || !Number.isInteger(months) || months < 1 || !Number.isFinite(annualRate) || annualRate < 0) throw new Error("Invalid loan inputs");
  const rate = annualRate / 12;
  return rate === 0 ? principal / months : principal * rate / (1 - Math.pow(1 + rate, -months));
}
export function affordabilityLevel(ratio: number): "Comfortable" | "Manageable" | "Aggressive" {
  if (!Number.isFinite(ratio) || ratio < 0) throw new Error("Invalid EMI ratio");
  return ratio < 0.2 ? "Comfortable" : ratio <= 0.4 ? "Manageable" : "Aggressive";
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
