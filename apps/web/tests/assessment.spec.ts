import { expect, test } from '@playwright/test';
import { applicationAssessment, qualityFlagMessage } from '../lib/assessment';
import { affordabilityLevel, affordabilityScore, estimateEmi } from '../lib/finance';
import type { Application } from '../lib/applications';

function saved(income:number, amount:number, months:number, probability:number): Application {
  return {id:'213cbf7e-0000-4000-8000-000000000000',user_id:'owner',created_at:'2026-10-01T00:00:00Z',version:1,status:'DECIDED',requested_amount:String(amount),
    input:{annual_income:String(income),age_years:21,years_employed:null,employment_type:'UNEMPLOYED',education_level:'LOWER_SECONDARY',household_size:6,dependent_children:4,occupation:null,housing_status:'OTHER'},
    quote:{monthly_payment:estimateEmi(amount,months).toFixed(2),term_months:months,annual_rate:'.12'},
    result:{probability,risk_score:5.17,risk_band:'Medium',credit_health_index:94.83,recommendation:'MANUAL_REVIEW',model_version:'20261002T140817Z-045430a7',scored_at:'2026-10-01T00:00:00Z',quality_flags:['unsupported_category:housing_status']}};
}

test('score follows every piecewise boundary and does not depend on probability',()=>{
  for(const [ratio,score] of [[0,100],[.2,100],[.3,75],[.4,50],[.7,25],[1,0],[3.336667,0]]) expect(affordabilityScore(ratio)).toBeCloseTo(score,10);
  expect(affordabilityLevel(.2)).toBe('Low');
  expect(affordabilityLevel(.200001)).toBe('Moderate');
  expect(affordabilityLevel(.4)).toBe('Moderate');
  expect(affordabilityLevel(.400001)).toBe('High');
  for (const ratio of [-1,NaN,Infinity]) expect(()=>affordabilityScore(ratio)).toThrow();
});

test('three acceptance cases and persisted model values remain unchanged',()=>{
  const cases=[saved(1800000,300000,36,.03),saved(600000,800000,48,.03),saved(120000,1500000,60,.05170021947098553)];
  const before=JSON.stringify(cases);
  const [a,b,c]=cases.map(applicationAssessment);
  expect(a.finalLevel).toBe('Low');expect(a.score).toBe(100);expect(a.overridden).toBe(false);
  expect(b.finalLevel).toBe('High');expect(b.score).toBeLessThanOrEqual(50);
  expect(c.finalLevel).toBe('High');expect(c.score).toBe(0);expect(c.modelLevel).toBe('Moderate');expect(c.overridden).toBe(true);
  expect(JSON.stringify(cases)).toBe(before);
  expect(applicationAssessment(saved(1800000,300000,36,.2)).finalLevel).toBe('High');
});

test('missing inputs stay unavailable and quality flags have individual explanations',()=>{
  const record=saved(120000,1500000,60,.0517);
  expect(qualityFlagMessage('unsupported_category:housing_status',record)).toBe("Housing status 'Other' was not seen in the model's training data.");
  expect(qualityFlagMessage('unsupported_category:occupation',record)).toContain('Not reported');
  expect(qualityFlagMessage('outside_development_range:annual_income',record)).toContain('Annual income is outside');
  expect(qualityFlagMessage('unseen_missing_tenure',record)).toContain('Years employed was not reported');
  expect(qualityFlagMessage('future_flag',record)).toContain('future flag');
  delete record.input;
  expect(applicationAssessment(record).score).toBeNull();
  expect(applicationAssessment(record).finalLevel).toBeNull();
});

test('old saved record renders overlay and amber warning without rescoring',async({page})=>{
  const record=saved(120000,1500000,60,.05170021947098553);
  const mutations:string[]=[];
  await page.route('**/api/v1/**',route=>{
    if(route.request().method()!=='GET') mutations.push(route.request().method());
    const path=new URL(route.request().url()).pathname;
    if(path.endsWith('/me'))return route.fulfill({json:{id:'owner',role:'USER',full_name:'Test User',permissions:[]}});
    if(path.endsWith('/history'))return route.fulfill({json:[]});
    if(path.endsWith(`/applications/${record.id}`))return route.fulfill({json:record});
    return route.fulfill({status:404,json:{detail:'Not mocked'}});
  });
  await page.goto(`/applications/${record.id}/result`);
  await expect(page.getByRole('heading',{name:'Your estimated EMI is 333.7% of your monthly income.'})).toBeVisible();
  await expect(page.getByText("This raises the overall rating above the model's estimate.")).toBeVisible();
  await expect(page.getByText('5.17%',{exact:true})).toBeVisible();
  await expect(page.locator('.assessment-cards .card').nth(0)).toContainText('High Risk');
  await expect(page.locator('.assessment-cards .card').nth(1)).toContainText('0.0');
  const banner=page.getByRole('note',{name:'Data quality limitations'});
  await expect(banner).toContainText("Housing status 'Other' was not seen in the model's training data.");
  await expect(banner).toHaveCSS('background-color','rgb(255, 251, 235)');
  expect(mutations).toEqual([]);
  await page.screenshot({path:'test-results/affordability-overlay-desktop.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:'test-results/affordability-overlay-mobile.png',fullPage:true});
});
