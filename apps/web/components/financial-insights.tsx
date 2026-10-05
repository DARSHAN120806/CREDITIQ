import { Application } from "../lib/applications";
import { financialInsights, formatCurrency, RiskLevel } from "../lib/finance";
import { applicationAssessment, qualityFlagMessage } from "../lib/assessment";

export function RiskBadge({level}:{level:RiskLevel|null}) {
  if (!level) return <span className="muted">Unavailable</span>;
  return <span className={`badge ${level}`}><span aria-hidden="true">●</span> {level} Risk</span>;
}
export function EstimateNote() {
  return <p className="estimate-note">Indicative estimates, not a loan offer. ₹ is a display label; amounts are not currency-converted.</p>;
}
export function Assessment({application}:{application:Application}) {
  const {insight,finalLevel,modelLevel,score,overridden}=applicationAssessment(application);
  const result=application.result;
  if (!result) return null;
  return <>
    <section className="panel assessment-panel">
      <div><div className="eyebrow">Affordability first</div>
        <h2>{insight ? `Your estimated EMI is ${(insight.ratio*100).toFixed(1)}% of your monthly income.` : 'Not enough information to assess affordability.'}</h2>
        {overridden && <p>This raises the overall rating above the model&apos;s estimate.</p>}
        <p>Risk Level combines the model band and your EMI burden, using whichever is higher. It is not a lending decision.</p>
      </div><RiskBadge level={finalLevel}/>
    </section>
    {result.quality_flags.length>0 && <section className="quality-warning" role="note" aria-label="Data quality limitations">
      <strong>Some information is outside the model&apos;s training experience.</strong>
      <ul>{result.quality_flags.map(flag=><li key={flag}>{qualityFlagMessage(flag,application)}</li>)}</ul>
    </section>}
    <div className="cards assessment-cards">
      <div className="card"><span className="muted">Risk Level</span><div className="metric"><RiskBadge level={finalLevel}/></div></div>
      <div className="card"><span className="muted">Affordability score</span><strong className="metric">{score===null?'—':score.toFixed(1)}<small> / 100</small></strong>
        {score!==null && <div className="score-track"><span style={{width:`${score}%`}}/></div>}
        <p className="muted">Based on this loan&apos;s EMI relative to income, excluding other commitments.</p>
      </div>
      <div className="card"><span className="muted">Indicative model estimate</span><strong className="metric">{(result.probability*100).toFixed(2)}%</strong>
        <p>Based on historical patterns in the training data. It does not measure whether this loan is affordable for you.</p>
        <p className="muted">Historical model band: {modelLevel}. Bands are relative to the held-out validation cohort.</p>
      </div>
    </div>
  </>;
}
export function FinancialSummary({application}:{application:Application}) {
  const {insight,finalLevel,score}=applicationAssessment(application);
  if(!insight)return <section className="panel"><h2>Financial Summary</h2><p>Income or repayment details are unavailable for this application.</p></section>;
  const fields=[['Annual Income',formatCurrency(insight.annualIncome)],['Monthly Income',formatCurrency(insight.monthlyIncome)],['Requested Loan',formatCurrency(insight.principal)],['Estimated EMI',`${formatCurrency(insight.emi)}/month`],['EMI Ratio',`${(insight.ratio*100).toFixed(1)}%`],['Risk Level',finalLevel?`${finalLevel} Risk`:'Unavailable'],['Affordability score',score===null?'Unavailable':`${score.toFixed(1)} / 100`]];
  return <section className="panel"><div className="section-heading"><h2>Financial Summary</h2><span className="muted">Application {application.id.slice(0,8).toUpperCase()}</span></div><dl className="financial-grid">{fields.map(([label,value])=><div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl></section>;
}
export function AffordabilityInsights({application}:{application:Application}) {
  const insight=financialInsights(Number(application.input?.annual_income),Number(application.requested_amount),application.quote?.term_months??0,application.quote?Number(application.quote.monthly_payment):undefined);
  const unavailable=<section className="panel"><p>Not enough information to suggest a range.</p></section>;
  if(!insight)return <><section className="panel"><h2>Affordability Assessment</h2><p>Add complete income and term details in a new application to see an estimate.</p></section>{unavailable}</>;
  // Hide invalid bounds, including positive amounts that would display as ₹0.
  const validRanges=insight.ranges.length===3 && insight.ranges.every(range=>
    Number.isFinite(range.min) && Number.isFinite(range.max) &&
    Math.round(range.min)>0 && Math.round(range.max)>0 && range.min<=range.max);
  // A shared boundary belongs to the first matching card, so the badge stays unique.
  const matchingRange=insight.ranges.findIndex(range=>insight.principal>=range.min && insight.principal<=range.max);
  const highRisk=applicationAssessment(application).finalLevel==="High";
  return <>
    <section className="panel"><div className="section-heading"><h2>Affordability Assessment</h2><span className={`badge ${insight.assessment}`}>{insight.assessment}</span></div><p>Your estimated EMI uses <strong>{(insight.ratio*100).toFixed(1)}%</strong> of your monthly income.</p><div className="affordability-track"><span style={{width:`${Math.min(insight.ratio*100,100)}%`,background:insight.ratio<=.2?'#22C55E':insight.ratio<=.4?'#F59E0B':'#EF4444'}}/></div><div className="scale-labels"><span>Up to 20% · Low</span><span>Over 20–40% · Moderate</span><span>Over 40% · High</span></div><p className="muted">Based on this loan only. Existing EMIs, living expenses and fees are not included.</p></section>
    {validRanges ? <section className="panel">
      <div className="section-heading">
        <div>
          <h2>Recommended Loan Range</h2>
          {insight.principal<insight.ranges[0].min && <p className="range-note">Your requested amount of {formatCurrency(insight.principal)} is below the suggested range. You can proceed with your requested amount.</p>}
          {insight.principal>insight.ranges[2].max && <p className="range-note range-warning">Your requested amount is above the suggested maximum for your income.</p>}
          {highRisk && <p className="range-note">Ranges are based on income only and do not reflect your risk level.</p>}
          <p className="muted">Planning estimates at 12% annual interest over {insight.months} months.</p>
        </div>
        <span className="badge">EMI budget up to {formatCurrency(insight.recommendedMaxEmi)}/month</span>
      </div>
      <div className="loan-ranges">{insight.ranges.map((range,index)=>
        <div className={`range-card${index===matchingRange ? " range-card-selected" : ""}`} key={range.label}>
          <span className="muted">{range.label}</span>
          {index===matchingRange && <span className="badge request-badge">Your request</span>}
          <strong>{formatCurrency(range.min)} – {formatCurrency(range.max)}</strong>
          <span>{range.lower*100}–{range.upper*100}% of monthly income</span>
        </div>
      )}</div>
      <p className="muted">These ranges are not an eligibility or affordability guarantee. Choose a lower amount if other commitments reduce your available income.</p>
    </section> : unavailable}
  </>;
}
