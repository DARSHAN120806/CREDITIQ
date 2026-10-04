import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const bins=(model:string,offset:number)=>Array.from({length:10},(_,i)=>({model,bin:i+1,mean_predicted_probability:.02+i*.02+offset,observed_default_rate:.025+i*.02}));
const features=[
 {feature:'payment_principal_ratio',mean_abs_shap_raw_margin:.28035800397947724},
 {feature:'loan_to_goods_price_ratio',mean_abs_shap_raw_margin:.13963989189763257},
 {feature:'years_employed',mean_abs_shap_raw_margin:.12925875156246755},
 {feature:'age_years',mean_abs_shap_raw_margin:.1278030912860531},
 {feature:'education_level_HIGHER',mean_abs_shap_raw_margin:.0839352568913065},
 {feature:'requested_amount',mean_abs_shap_raw_margin:.0664544855072811},
 {feature:'quoted_monthly_payment',mean_abs_shap_raw_margin:.06128685919975224},
 {feature:'education_level_SECONDARY',mean_abs_shap_raw_margin:.06073997946199785},
 {feature:'employment_type_WORKING',mean_abs_shap_raw_margin:.042657893354804764},
 {feature:'employed_age_ratio',mean_abs_shap_raw_margin:.042511223578540605},
 {feature:'proposed_payment_income_ratio',mean_abs_shap_raw_margin:.03985360271804553},
 {feature:'credit_bureau_inquiry_history_missing',mean_abs_shap_raw_margin:.0374137489695473},
 {feature:'credit_bureau_inquiries_12m',mean_abs_shap_raw_margin:.03333037472130437},
 {feature:'income_per_household_member',mean_abs_shap_raw_margin:.033067921489561454},
 {feature:'credit_bureau_inquiries_3m',mean_abs_shap_raw_margin:.03189914848592675},
 {feature:'principal_income_ratio',mean_abs_shap_raw_margin:.022830631929674015},
 {feature:'occupation_ACCOUNTANT',mean_abs_shap_raw_margin:.02256060881267273},
 {feature:'employment_type_COMMERCIAL_ASSOCIATE',mean_abs_shap_raw_margin:.022152660748546632},
 {feature:'employment_type_PENSIONER',mean_abs_shap_raw_margin:.02119275905726795},
 {feature:'occupation_LABORER',mean_abs_shap_raw_margin:.020029200806057378},
];
const researchData={
 mode:'RESEARCH_ONLY',release_ready:false,
 metrics:[
  {name:'Lite',model:'LightGBM',status:'Current application baseline · research mode',run_id:'20261002T140817Z-045430a7',feature_count:17,values:{roc_auc:.7007798513,average_precision:.1757755084,brier_score:.0731289769}},
  {name:'FULL_RESEARCH_V1_NO_EXT',model:'LightGBM',status:'Research candidate · RESEARCH_ONLY',run_id:'20261004T075100Z',feature_count:22,values:{roc_auc:.7047402078,average_precision:.1764089249,brier_score:.0730485831}},
 ],
 metric_deltas:{roc_auc:.0039603565,average_precision:.0006334165,brier_score:-.0000803939},
 calibration:{method:'sigmoid',cohort:'untouched final test',test_rows:41733,bins:[...bins('Lite',0),...bins('FULL_RESEARCH_V1_NO_EXT',.001)],summary:'Both models use sigmoid calibration. Saved reliability bins from the shared final-test cohort.'},
 shap:{interpretation:'Tree SHAP explains the LightGBM raw margin before probability calibration; it is not causal.',top_features:features,importance:features},
 contracts:{Lite:{feature_count:17,groups:[{name:'Application',features:['age_years','household_size','dependent_children','education_level','housing_status']},{name:'Employment',features:['years_employed','employment_type','occupation','employment_tenure_missing','employed_age_ratio']},{name:'Affordability',features:['annual_income','requested_amount','quoted_monthly_payment','proposed_payment_income_ratio','principal_income_ratio','income_per_household_member','payment_principal_ratio']}]},FULL_RESEARCH_V1_NO_EXT:{feature_count:22,groups:[{name:'Application',features:['age_years','household_size','dependent_children','education_level','housing_status']},{name:'Employment',features:['years_employed','employment_type','occupation','employment_tenure_missing','employed_age_ratio']},{name:'Affordability',features:['annual_income','requested_amount','quoted_monthly_payment','proposed_payment_income_ratio','principal_income_ratio','income_per_household_member','payment_principal_ratio']},{name:'Borrowing History',features:['credit_bureau_inquiries_1m','credit_bureau_inquiries_3m','credit_bureau_inquiries_12m','credit_bureau_inquiry_history_missing']},{name:'Debt Exposure',features:['loan_to_goods_price_ratio']}]}},
 ablation:[
  {variant:'FULL_RESEARCH_V1_NO_EXT',feature_count:22,roc_auc:.6909992485,average_precision:.1736824378,brier_score:.0733459764,evaluation_cohort:'reserved policy partition; diagnostic only'},
  {variant:'Lite feature subset (17)',feature_count:17,roc_auc:.6879948743,average_precision:.1742898751,brier_score:.0733852676,evaluation_cohort:'reserved policy partition; diagnostic only'},
  {variant:'Without inquiry features',feature_count:18,roc_auc:.6882049872,average_precision:.1732592609,brier_score:.0734003204,evaluation_cohort:'reserved policy partition; diagnostic only'},
  {variant:'Without loan-to-goods ratio',feature_count:21,roc_auc:.6887109152,average_precision:.1746347978,brier_score:.0733453876,evaluation_cohort:'reserved policy partition; diagnostic only'},
 ],
 registry:[
  {name:'Lite',version:'20261002T140817Z-045430a7',feature_count:17,training_date:'2026-10-02',calibration_method:'sigmoid',dataset_size:278220,status:'Current application baseline · research mode'},
  {name:'FULL_RESEARCH_V1_NO_EXT',version:'20261004T075100Z',feature_count:22,training_date:'2026-10-04',calibration_method:'sigmoid',dataset_size:278220,status:'Research candidate · RESEARCH_ONLY'},
 ],
 limitations:['RESEARCH_ONLY; not production approved and not for lending decisions.','External validation has not been completed; evaluation uses one shared held-out Home Credit cohort.','Bureau inquiry availability for real applicants remains unresolved.','Target population and outcome horizon are not independently established.','SHAP values describe model associations on the raw margin; they are not causal explanations.'],
 ablation_note:'Research diagnostics only. Ablations use the reserved policy partition and are not final-test comparisons.',shap_note:'Existing Tree SHAP outputs only; no SHAP values are computed by this dashboard.',
};

test('admin model research dashboard renders saved comparisons and captures responsive screenshots',async({page})=>{
 await page.route('**/api/v1/**',async route=>{
  const path=new URL(route.request().url()).pathname;
  if(path==='/api/v1/me')return route.fulfill({json:{id:'admin-1',email:'admin@example.test',full_name:'Research Admin',role:'ADMIN',permissions:[]}});
  if(path==='/api/v1/admin/model-research')return route.fulfill({json:researchData});
  return route.fulfill({status:404,json:{detail:'not mocked'}});
 });
 await page.setViewportSize({width:1280,height:900});
 await page.goto('/admin/model-research');
 await expect(page.getByRole('heading',{name:'Model Research Dashboard'})).toBeVisible();
 await expect(page.getByText('0.7047',{exact:true})).toBeVisible();
 await expect(page.getByText('+0.0040',{exact:true})).toBeVisible();
 await expect(page.getByText('payment_principal_ratio',{exact:true}).first()).toBeVisible();
 await expect(page.getByText('Bureau inquiry availability for real applicants remains unresolved.')).toBeVisible();
 await page.screenshot({path:'test-results/model-research-desktop.png',fullPage:true});
 await page.setViewportSize({width:390,height:844});
 await page.screenshot({path:'test-results/model-research-mobile.png',fullPage:true});
});

test('admin model research dashboard shows the saved XGBoost benchmark and descriptive ranking',async({page})=>{
 const root=resolve(process.cwd(),'../../ml/research_output/xgboost_full_research_v1_no_ext');
 const runId=JSON.parse(readFileSync(resolve(root,'latest.json'),'utf8')).run_id;
 const run=resolve(root,runId);
 const meta=JSON.parse(readFileSync(resolve(run,'metadata.json'),'utf8'));
 const calibration=JSON.parse(readFileSync(resolve(run,'calibration_results.json'),'utf8'));
 const importance=readFileSync(resolve(run,'shap_feature_importance.csv'),'utf8').trim().split(/\r?\n/).slice(1).map(line=>{
  const [feature,value]=line.split(',');return {feature,mean_abs_shap_raw_margin:Number(value)};
 });
 const comparison=['LightGBM','XGBoost'].map(model=>({model,...meta.test_metrics[model]}));
 const benchmark={run_id:runId,baseline_run_id:meta.baseline_run_id,feature_count:22,test_rows:meta.split_sizes.test,
  calibration_method:meta.calibration_method,metrics:comparison,metric_deltas:meta.metric_deltas,
  ranking:meta.research_ranking.map((model:string,index:number)=>({rank:index+1,model,...meta.test_metrics[model]})),
  ranking_basis:meta.ranking_basis,evaluation_note:meta.test_evaluation_note,
  calibration:{selection_basis:calibration.selection_basis,development_selection:calibration.development_selection,
   bins:['LightGBM','XGBoost'].flatMap(model=>calibration[model].map((row:object,index:number)=>({model,bin:index+1,...row})))},
  shap:{interpretation:meta.shap_interpretation,importance,top_features:importance.slice(0,20)}};
 await page.route('**/api/v1/**',async route=>{
  const path=new URL(route.request().url()).pathname;
  if(path==='/api/v1/me')return route.fulfill({json:{id:'admin-1',email:'admin@example.test',full_name:'Research Admin',role:'ADMIN',permissions:[]}});
  if(path==='/api/v1/admin/model-research')return route.fulfill({json:{...researchData,xgboost_benchmark:benchmark}});
  return route.fulfill({status:404,json:{detail:'not mocked'}});
 });
 await page.setViewportSize({width:1440,height:1000});
 await page.goto('/admin/model-research');
 const section=page.getByRole('region',{name:'XGBoost research benchmark'});
 await expect(section.getByRole('heading',{name:'LightGBM vs XGBoost'})).toBeVisible();
 await expect(section.getByRole('heading',{name:'Research model ranking'})).toBeVisible();
 await expect(section.getByText(meta.test_evaluation_note)).toBeVisible();
 await expect(section.getByText(meta.test_metrics.XGBoost.roc_auc.toFixed(6),{exact:true}).first()).toBeVisible();
 await expect(section.getByRole('img',{name:'XGBoost top 20 native Tree SHAP feature importance'})).toBeVisible();
 await section.screenshot({path:'test-results/xgboost-research-desktop.png'});
 await page.setViewportSize({width:390,height:844});
 await section.screenshot({path:'test-results/xgboost-research-mobile.png'});
});
