import { test, expect } from '@playwright/test';
import { affordabilityLevel, currency, estimateEmi, financialHealth, financialInsights, formatCurrency, riskLevel } from '../lib/finance';
import { dashboardAnalytics, loadAllApplications, Application } from '../lib/applications';

for(const [probability,level] of [[0,'Low'],[.04999999,'Low'],[.05,'Moderate'],[.14999999,'Moderate'],[.15,'High'],[1,'High']] as const) {
  test(`risk boundary ${probability} is ${level}`,()=>expect(riskLevel(probability)).toBe(level));
}
test('health score and invalid probability handling',()=>{
  expect(financialHealth(.125)).toBe(87.5);
  for(const value of [NaN,Infinity,-.1,1.01]) expect(()=>riskLevel(value)).toThrow();
});
test('currency is presentation only and invalid amounts are unavailable',()=>{
  expect(currency).toBe('INR');expect(formatCurrency(150000)).toBe('₹1,50,000');
  expect(formatCurrency('25000')).toBe('₹25,000');
  expect(formatCurrency(null)).toBe('—');expect(formatCurrency(NaN)).toBe('—');
});
test('affordability boundaries are inclusive at 20 and 40 percent',()=>{
  expect(affordabilityLevel(.19999)).toBe('Comfortable');
  expect(affordabilityLevel(.2)).toBe('Manageable');
  expect(affordabilityLevel(.4)).toBe('Manageable');
  expect(affordabilityLevel(.40001)).toBe('Aggressive');
});
test('EMI and inverse principal calculations agree at 12 percent',()=>{
  expect(estimateEmi(450000,36)).toBeCloseTo(14946.44,2);
  expect(estimateEmi(12000,12,0)).toBe(1000);
  const insight=financialInsights(600000,450000,36,14946.44)!;
  expect(insight.monthlyIncome).toBe(50000);
  expect(insight.ratio).toBeCloseTo(.2989288,7);
  expect(insight.assessment).toBe('Manageable');
  expect(insight.recommendedMaxEmi).toBe(15000);
  expect(estimateEmi(insight.ranges[2].max,36)).toBeCloseTo(15000,8);
  expect(insight.ranges[0].max).toBe(insight.ranges[1].min);
  expect(insight.ranges[1].max).toBe(insight.ranges[2].min);
});
test('missing financial inputs do not fabricate zero-income insights',()=>{
  expect(financialInsights(0,10000,12)).toBeNull();
  expect(financialInsights(NaN,10000,12)).toBeNull();
  expect(financialInsights(100000,10000,0)).toBeNull();
  expect(financialInsights(100000,10000,12,NaN)).toBeNull();
});
function app(id:string,p:number,date:string):Application {
  return {id,user_id:'owner',created_at:date,requested_amount:'10000',status:'DECIDED',version:1,
    input:{annual_income:'600000'},quote:{monthly_payment:'900',annual_rate:'.12',term_months:12},
    result:{probability:p,risk_score:p*100,risk_band:'unchanged',credit_health_index:100*(1-p),recommendation:'MANUAL_REVIEW',model_version:'unchanged',scored_at:date,quality_flags:[]}};
}
test('analytics groups dates chronologically and averages actual scores',()=>{
  const data=dashboardAnalytics([app('a',.2,'2026-10-02T01:00:00Z'),app('b',.01,'2026-10-01T01:00:00Z'),app('c',.1,'2026-10-01T02:00:00Z')]);
  expect(data.total).toBe(3);expect(data.average).toBeCloseTo((80+99+90)/3);
  expect(data.distribution.map(d=>d.value)).toEqual([1,1,1]);
  expect(data.trend.map(d=>[d.date,d.applications,d.health])).toEqual([['2026-10-01',2,94.5],['2026-10-02',1,80]]);
  expect(dashboardAnalytics([]).average).toBeNull();
});
test('dashboard loads beyond the first page without changing API records',async()=>{
  const original=globalThis.fetch;
  const records=Array.from({length:125},(_,i)=>app(String(i),i===124?.2:.01,'2026-10-01T01:00:00Z'));
  const offsets:number[]=[];
  globalThis.fetch=async(input)=>{
    const url=new URL(String(input),'http://test');const offset=Number(url.searchParams.get('offset'));offsets.push(offset);
    return new Response(JSON.stringify({items:records.slice(offset,offset+100),total:125,limit:100,offset}),{status:200});
  };
  try {const loaded=await loadAllApplications();expect(loaded).toHaveLength(125);expect(offsets).toEqual([0,100]);expect(dashboardAnalytics(loaded).distribution[2].value).toBe(1);expect(loaded[0].result?.recommendation).toBe('MANUAL_REVIEW');}
  finally {globalThis.fetch=original;}
});
