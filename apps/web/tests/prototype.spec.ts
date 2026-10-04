import { test, expect } from '@playwright/test';

const password = 'Research browser test password 2026!';
test('user registration, real prediction, history, persistence, guards and logout', async ({ page, context }) => {
  const email = `browser-${Date.now()}@example.com`;
  await page.goto('/register');
  await page.getByLabel('Full name').fill('Research Browser');
  await page.getByLabel('Email address').fill(email);
  await page.getByLabel('Password', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Create account' }).click();
  await expect(page.getByText('Registration processed.')).toBeVisible();
  await page.getByRole('link', { name: 'Continue to sign in' }).click();
  await page.getByLabel('Email address').fill(email);
  await page.getByLabel('Password', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page).toHaveURL(/dashboard/);
  await expect(page.getByRole('heading', { name: 'No applications yet' })).toBeVisible();
  await page.goto('/applications/new');
  await page.getByLabel('Age (years)', { exact: true }).fill('35');
  await page.getByLabel('Employment type').selectOption('WORKING');
  await page.getByLabel('Years in current employment').fill('8');
  await page.getByLabel('Annual income').fill('180000');
  await page.getByLabel('Education', { exact: true }).selectOption('HIGHER');
  await page.getByLabel('Household members').fill('3');
  await page.getByLabel('Dependent children').fill('1');
  await page.getByLabel('Occupation').selectOption('CORE_STAFF');
  await page.getByLabel('Housing').selectOption('OWN_OR_APARTMENT');
  await page.getByLabel('Requested amount').fill('450000');
  await page.getByLabel('Term (months)').fill('36');
  await page.getByRole('checkbox').check();
  await page.getByRole('button', { name: 'Get my assessment' }).click();
  await expect(page).toHaveURL(/applications\/.+\/result/);
  await expect(page.getByText('Risk Probability')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Recommended Loan Range' })).toBeVisible();
  await page.screenshot({ path: 'test-results/phase2-result.png', fullPage: true });
  await context.clearCookies({ name: 'creditiq_access' });
  await page.reload(); // Exercises refresh through the Next proxy with HttpOnly refresh cookie.
  await expect(page.getByText('Risk Probability')).toBeVisible();
  await page.getByRole('link', { name: 'Application details', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Submitted information' })).toBeVisible();
  await expect(page.getByText('Assessment completed', { exact: true })).toBeVisible();
  await page.goto('/applications');
  await expect(page.locator('tbody tr')).toHaveCount(1);
  await expect(page.getByRole('columnheader', {name:'Financial Health Score'})).toBeVisible();
  await page.screenshot({ path:'test-results/phase2-history.png', fullPage:true });
  await page.goto('/dashboard');
  await expect(page.getByRole('heading', {name:'Risk Distribution'})).toBeVisible();
  await expect(page.getByRole('heading', {name:'Financial Summary'})).toBeVisible();
  await page.screenshot({ path:'test-results/phase2-dashboard.png', fullPage:true });
  await page.setViewportSize({width:390,height:844});
  await expect(page.getByRole('heading', {name:'Financial Summary'})).toBeVisible();
  await page.screenshot({ path:'test-results/phase2-mobile-dashboard.png', fullPage:true });
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.goto('/financial-analysis');
  await expect(page.getByRole('heading',{name:'Installment Intelligence'})).toBeVisible();
  await page.setViewportSize({width:1280,height:720});
  await page.goto('/profile');
  await expect(page.getByText(email, { exact: true })).toBeVisible();
  await page.goto('/admin');
  await expect(page).toHaveURL(/dashboard/);
  await page.getByRole('button', { name: 'Sign out' }).click();
  await expect(page).toHaveURL(/login/);
  await page.goto('/applications');
  await expect(page).toHaveURL(/login/);
});

test('administrator can view users, applications and statistics', async ({ page, request }) => {
  const mutate = async (path: string, data: unknown, extra: Record<string,string> = {}) => {
    const csrf = await request.get('/api/v1/auth/csrf');
    return request.post('/api/v1'+path, { data, headers: { Origin: process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:3000', 'X-CSRF-Token': (await csrf.json()).csrf_token, ...extra } });
  };
  const email = `admin-fixture-${Date.now()}@example.com`;
  expect((await mutate('/auth/register', {email, password, full_name:'Admin View Fixture'})).status()).toBe(202);
  expect((await mutate('/auth/login', {email,password})).status()).toBe(200);
  expect((await mutate('/applications', {age_years:35,employment_type:'WORKING',years_employed:8,annual_income:'180000',requested_amount:'450000',term_months:36,education_level:'HIGHER',household_size:3,dependent_children:1,research_acknowledged:true}, {'Idempotency-Key':crypto.randomUUID()})).status()).toBe(201);
  await page.goto('/admin/login');
  await page.getByLabel('Email address').fill('browser-admin@example.com');
  await page.getByLabel('Password', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page).toHaveURL(/\/admin$/);
  await expect(page.getByText('Total predictions', { exact: true })).toBeVisible();
  await page.goto('/admin/users');
  await expect(page.locator('tbody tr')).not.toHaveCount(0);
  await page.locator('tbody a').first().click();
  await expect(page.getByRole('heading', { name: 'Profile' })).toBeVisible();
  await page.goto('/admin/applications');
  await page.locator('tbody a').first().click();
  await expect(page.getByText('Risk Probability')).toBeVisible();
  await expect(page.getByRole('button', { name: /approve|reject|override/i })).toHaveCount(0);
  await page.goto('/admin/statistics');
  await expect(page.getByRole('heading', { name: 'Workspace statistics' })).toBeVisible();
});

test('mobile registration fits viewport and validates required fields', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/register');
  await page.getByRole('button', { name: 'Create account' }).click();
  await expect(page).toHaveURL(/register/);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: 'test-results/mobile-register.png', fullPage: true });
});





