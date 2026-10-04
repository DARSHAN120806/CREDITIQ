import { test, expect } from '@playwright/test';

const stress=(drop:number,residual:string)=>({income_drop_percent:drop,stressed_take_home_income:String(120000*(1-drop/100)),debt_service_ratio:.29/(1-drop/100),stressed_residual:residual,goal_adjusted_residual:(Number(residual)-10000).toFixed(2)});
const scenarios=[
 {term_months:36,annual_rate_percent:'12',emi:'16607.15',total_repayment:'597857.40',total_interest:'97857.40',current_dti:.12,proposed_debt_to_income_ratio:.23,current_take_home_payment_ratio:.15,proposed_take_home_payment_ratio:.29,residual_monthly_income:'40392.85',goal_adjusted_residual:'30392.85',additional_emi_headroom:'47000.00',planning_fit_score:73,score_components:{payment_burden:33,residual_cash_flow:40},fits_stated_budget:true,savings_goal_fit:true,stress:[stress(0,'40392.85'),stress(10,'28392.85'),stress(20,'16392.85'),stress(30,'4392.85')],monthly_room_score:70,interest_saving_score:60,rank_score:65,rank:1,rank_explanation:'Ranks #1 for balanced using 50% monthly-room and 50% interest-saving weights. Monthly payment is ₹16607.15; estimated total interest is ₹97857.40.'},
 {term_months:60,annual_rate_percent:'12',emi:'11122.22',total_repayment:'667333.20',total_interest:'167333.20',current_dti:.12,proposed_debt_to_income_ratio:.19,current_take_home_payment_ratio:.15,proposed_take_home_payment_ratio:.24,residual_monthly_income:'45877.78',goal_adjusted_residual:'35877.78',additional_emi_headroom:'47000.00',planning_fit_score:78,score_components:{payment_burden:48,residual_cash_flow:40},fits_stated_budget:true,savings_goal_fit:true,stress:[stress(0,'45877.78'),stress(10,'33877.78'),stress(20,'21877.78'),stress(30,'9877.78')],monthly_room_score:100,interest_saving_score:0,rank_score:50,rank:2,rank_explanation:'Ranks #2 for balanced using 50% monthly-room and 50% interest-saving weights. Monthly payment is ₹11122.22; estimated total interest is ₹167333.20.'},
];

test('planner submits user cash-flow inputs, renders scenarios and captures responsive screenshots',async({page})=>{
 await page.route('**/api/v1/**',async route=>{
  const url=new URL(route.request().url());
  if(url.pathname==='/api/v1/me')return route.fulfill({json:{id:'user-1',email:'user@example.test',full_name:'Planner User',role:'USER',permissions:[]}});
  if(url.pathname==='/api/v1/applications')return route.fulfill({json:{items:[],total:0,limit:100,offset:0}});
  if(url.pathname==='/api/v1/auth/csrf')return route.fulfill({json:{csrf_token:'test-csrf'}});
  if(url.pathname==='/api/v1/planner/plan')return route.fulfill({json:{calculation_version:'borrowing-planner-v1',mode:'RESEARCH_ONLY',release_ready:false,currency:'INR',as_of:'2026-10-04',inputs_basis:'USER_DECLARED',current_debt_burden_monthly:'18000.00',current_dti:.12,current_take_home_payment_ratio:.15,total_outstanding_debt:'420000.00',liquid_savings:'300000.00',monthly_essential_expenses:'45000.00',monthly_savings_goal:'10000.00',additional_emi_headroom:'47000.00',additional_emi_headroom_before_savings_goal:'57000.00',savings_buffer_months:6.67,planning_priority:'BALANCED',ranking_weights:{monthly_room:.5,interest_saving:.5},scenarios,warnings:['Illustrative planning estimate, not a loan offer.']}});
  return route.fulfill({status:404,json:{detail:'not mocked'}});
 });
 await page.goto('/borrowing-planner');
 await expect(page.getByRole('heading',{name:'Borrowing Planner'})).toBeVisible();
 await page.getByLabel('Monthly take-home income').fill('120000');
 await page.getByLabel('Essential monthly expenses').fill('45000');
 await page.getByLabel('Existing monthly debt payments').fill('18000');
 await page.getByLabel('Monthly gross income').fill('150000');
 await page.getByLabel('Requested amount').fill('500000');
 await page.getByLabel('Monthly savings goal').fill('10000');
 await page.getByRole('button',{name:'Compare borrowing scenarios'}).click();
 await expect(page.getByRole('heading',{name:'Your monthly plan'})).toBeVisible();
 await expect(page.getByRole('heading',{name:'Planning Fit Score'})).toBeVisible();
 await expect(page.getByRole('table').first().getByText('36 months').first()).toBeVisible();
 await expect(page.getByText('Ranks #1 for balanced', {exact:false})).toBeVisible();
 await page.screenshot({path:'test-results/borrowing-planner-desktop.png',fullPage:true});
 await page.setViewportSize({width:390,height:844});
 await page.screenshot({path:'test-results/borrowing-planner-mobile.png',fullPage:true});
});
