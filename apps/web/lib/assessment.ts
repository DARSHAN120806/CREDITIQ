import type { Application } from './applications';
import { affordabilityScore, financialInsights, riskLevel, RiskLevel } from './finance';

/** Read-only display overlay; never replace saved predictions or policy decisions. */
export function applicationAssessment(application: Application) {
  const insight = financialInsights(Number(application.input?.annual_income), Number(application.requested_amount),
    application.quote?.term_months ?? 0, application.quote ? Number(application.quote.monthly_payment) : undefined);
  const modelLevel = application.result ? riskLevel(application.result.probability) : null;
  const levels: RiskLevel[] = ['Low', 'Moderate', 'High'];
  const overridden = !!(insight && modelLevel && levels.indexOf(insight.assessment) > levels.indexOf(modelLevel));
  const finalLevel = insight && modelLevel ? (overridden ? insight.assessment : modelLevel) : null;
  return { insight, modelLevel, finalLevel, overridden, score: insight ? affordabilityScore(insight.ratio) : null };
}

export function qualityFlagMessage(flag: string, application: Application): string {
  const [kind, field] = flag.split(':');
  const label = (field || 'input').replaceAll('_', ' ');
  const title = label.charAt(0).toUpperCase() + label.slice(1);
  const value = application.input?.[field];
  const readable = value == null ? 'Not reported' : String(value).toLowerCase().replaceAll('_', ' ');
  const display = readable.charAt(0).toUpperCase() + readable.slice(1);
  if (kind === 'unsupported_category') return `${title} '${display}' was not seen in the model's training data.`;
  if (kind === 'outside_development_range') return `${title} is outside the range observed in the model's training data.`;
  if (kind === 'unseen_missing_tenure') return "Years employed was not reported; missing tenure was not seen in the model's training data.";
  return `The model reported a data-quality limitation: ${flag.replaceAll('_', ' ')}.`;
}
