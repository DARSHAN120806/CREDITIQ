import { test, expect, Page } from '@playwright/test';
import { estimateEmi, financialInsights, formatCurrency, riskLevel } from '../lib/finance';

async function mockApplication(page: Page, income: number, amount: number, months: number, probability = .03) {
  await page.route('**/api/v1/**', route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith('/me')) return route.fulfill({json: {id:'owner', role:'USER', full_name:'Test User', permissions:[]}});
    if (path.endsWith('/history')) return route.fulfill({json: []});
    if (path.endsWith('/applications/sample')) return route.fulfill({json: {
      id:'sample', user_id:'owner', requested_amount:String(amount), status:'DECIDED', version:1,
      created_at:'2026-10-06T10:00:00Z', input:{annual_income:String(income), years_employed:null, occupation:null},
      quote:{monthly_payment:String(estimateEmi(amount,months)), annual_rate:'.12', term_months:months},
      result:{probability, risk_score:probability*100, risk_band:'unchanged', credit_health_index:100*(1-probability), recommendation:'MANUAL_REVIEW', model_version:'unchanged', scored_at:'2026-10-06T10:00:00Z', quality_flags:[]},
    }});
    return route.fulfill({status:404, json:{detail:'Not mocked'}});
  });
}

for (const [income, amount, months, probability] of [[1800000,300000,36,.03],[600000,800000,48,.1],[120000,1500000,60,.2]]) {
  test(`range context for income ${income} and request ${amount}`, async ({page}) => {
    await mockApplication(page,income,amount,months,probability);
    await page.goto('/applications/sample/result');
    const insight = financialInsights(income,amount,months)!;
    for (const range of insight.ranges) await expect(page.getByText(`${formatCurrency(range.min)} – ${formatCurrency(range.max)}`,{exact:true})).toBeVisible();
    if (amount < insight.ranges[0].min) await expect(page.getByText(`Your requested amount of ${formatCurrency(amount)} is below the suggested range. You can proceed with your requested amount.`)).toBeVisible();
    if (amount > insight.ranges[2].max) await expect(page.getByText('Your requested amount is above the suggested maximum for your income.')).toBeVisible();
    await expect(page.getByText('Ranges are based on income only and do not reflect your risk level.')).toHaveCount((riskLevel(probability)==='High' || insight.ratio>.4)?1:0);
    await expect(page.locator('.loan-ranges')).not.toContainText('₹0');
  });
}

test('matching range has one badge, including a shared boundary; nullable fields render', async ({page}) => {
  const amount = financialInsights(600000,300000,36)!.ranges[0].max;
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await mockApplication(page,600000,amount,36);
  await page.goto('/applications/sample');
  await expect(page.locator('.range-card-selected')).toHaveCount(1);
  await expect(page.locator('.range-card').first()).toContainText('Your request');
  await expect(page.getByText('Not reported',{exact:true})).toHaveCount(2);
  expect(errors).toEqual([]);
});

for (const income of [0, -100, .001]) {
  test(`invalid or zero-displaying ranges are hidden: ${income}`, async ({page}) => {
    await mockApplication(page,income,300000,36);
    await page.goto('/applications/sample/result');
    await expect(page.getByText('Not enough information to suggest a range.')).toBeVisible();
    await expect(page.locator('.loan-ranges')).toHaveCount(0);
  });
}

for (const width of [1280,390]) {
  for (const path of ['/applications/sample/result','/applications/new']) {
test(`disclaimer is readable at ${width}px on ${path}`, async ({page}) => {
  await mockApplication(page,1800000,300000,36);
    await page.setViewportSize({width,height:900});
      await page.goto(path);
      const note = page.locator('.estimate-note');
      await expect(note).toBeVisible();
      const style = await note.evaluate(el => ({size:parseFloat(getComputedStyle(el).fontSize),color:getComputedStyle(el).color}));
      expect(style.size).toBeGreaterThanOrEqual(12);
      expect(style.color).toBe('rgb(181, 195, 214)'); // Current dark-theme disclaimer color (#b5c3d6).
      await page.screenshot({path:`test-results/results-${width}-${path.endsWith('new')?'form':'assessment'}.png`,fullPage:true});
});
  }
}
