import {test,expect,Page} from '@playwright/test';
const password='Installment browser password 2026!';
async function signup(page:Page){
 const email=`installments-${Date.now()}@example.com`;
 await page.goto('/register');await page.getByLabel('Full name').fill('Repayment Explorer');
 await page.getByLabel('Email address').fill(email);await page.getByLabel('Password',{exact:true}).fill(password);
 await page.getByRole('button',{name:'Create account'}).click();await expect(page.getByText('Registration processed.')).toBeVisible();
 await page.goto('/login');await page.getByLabel('Email address').fill(email);await page.getByLabel('Password',{exact:true}).fill(password);
 await page.getByRole('button',{name:'Sign in',exact:true}).click();await expect(page).toHaveURL(/dashboard/);
}

test('personal split-payment entry, saved results and dashboard integration',async({page})=>{
 await signup(page);await page.getByRole('link',{name:'Repayment Intelligence',exact:true}).click();
 await page.getByLabel('History name').fill('My repayment record');await page.getByLabel('Analysis as of').fill('2026-10-01');
 await page.getByLabel('Observation starts').fill('2026-01-01');await page.getByRole('button',{name:'Add installment',exact:true}).click();
 await page.getByLabel('Due date 1',{exact:true}).fill('2026-08-01');await page.getByLabel('Scheduled amount 1').fill('100');
 await page.getByRole('button',{name:'Add payment',exact:true}).click();await page.getByLabel('Payment date 1').fill('2026-07-30');await page.getByLabel('Payment amount 1').fill('40');
 await page.getByRole('button',{name:'Add payment',exact:true}).click();await page.getByLabel('Payment date 2').fill('2026-08-05');await page.getByLabel('Payment amount 2').fill('60');
 await page.getByLabel('I supplied all scheduled installments').check();await page.getByLabel('I supplied all payments').check();await page.getByLabel('I confirm this is the effective').check();
 await page.getByRole('button',{name:'Analyze repayment history',exact:true}).click();
 const result=page.getByRole('region',{name:'Repayment analysis result'});
 await expect(result.getByRole('heading',{name:'My repayment record'})).toBeVisible();
 await expect(result.getByText('4 days',{exact:true}).first()).toBeVisible();await expect(result.getByText('40%',{exact:true})).toBeVisible();
 await page.reload();await page.getByRole('button',{name:'View analysis',exact:true}).click();
 await expect(result.getByRole('heading',{name:'Installment timeline'})).toBeVisible();
 await page.goto('/dashboard');await expect(page.getByText('My repayment record · as of 2026-10-01')).toBeVisible();
});

test('labeled demonstration charts, JSON import and responsive layout',async({page})=>{
 await signup(page);await page.goto('/financial-analysis');
 await page.getByRole('button',{name:'Explore example history'}).click();
 const result=page.getByRole('region',{name:'Repayment analysis result'});
 await expect(result.getByRole('heading',{name:'Example repayment history'})).toBeVisible();
 await expect(result.getByText('Example history · not your financial records')).toBeVisible();
 await expect(result.getByRole('heading',{name:'Coverage & confidence'})).toBeVisible();
 await page.locator('.history-entry').first().evaluate(e=>e.removeAttribute('open'));
 await page.screenshot({path:'test-results/installment-desktop.png',fullPage:true});
 await page.setViewportSize({width:390,height:844});
 await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:'test-results/installment-mobile.png',fullPage:true});
 await page.getByText('Import a history JSON file',{exact:true}).click();
 await page.getByLabel('History JSON file').setInputFiles('public/installment-history-example.json');
 await expect(result.getByRole('heading',{name:'Example import: split payment'})).toBeVisible();
 await expect(page.getByRole('button',{name:'View analysis',exact:true})).toHaveCount(2);
});

test('admin repayment views contain no mutation controls',async({page})=>{
 await page.goto('/admin/login');await page.getByLabel('Email address').fill('browser-admin@example.com');
 await page.getByLabel('Password',{exact:true}).fill('Research browser test password 2026!');
 await page.getByRole('button',{name:'Sign in',exact:true}).click();await expect(page).toHaveURL(/admin/);
 await page.getByRole('link',{name:'Repayment insights'}).click();
 await expect(page.getByRole('heading',{name:'Installment Intelligence'})).toBeVisible();
 await expect(page.getByText('Personal analyses',{exact:true})).toBeVisible();
 await expect(page.getByRole('button',{name:'Analyze repayment history'})).toHaveCount(0);
 await expect(page.getByRole('button',{name:'Explore example history'})).toHaveCount(0);
});
