import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const root=resolve(process.cwd(),'../..');
const artifactRoot=resolve(root,'ml/research_output/customer_segmentation');
const runId=(JSON.parse(readFileSync(resolve(artifactRoot,'latest.json'),'utf8')) as {run_id:string}).run_id;
const run=resolve(artifactRoot,runId);
const metrics=JSON.parse(readFileSync(resolve(run,'cluster_metrics.json'),'utf8'));
const pca=readFileSync(resolve(run,'pca_visualization_data.csv'),'utf8').trim().split(/\r?\n/).slice(1).map(line=>{
 const [pca_1,pca_2,cluster_id]=line.split(',').map(Number);return {pca_1,pca_2,cluster_id};
});
const dashboard={mode:'RESEARCH_ONLY',release_ready:false,run_id:runId,
 source:{contract:metrics.source_contract,run_id:metrics.source_run_id,rows:metrics.source_rows,feature_count:metrics.feature_count},
 selected_k:metrics.selected_k,methodology:metrics.selection_criteria,selection_metrics:metrics.selection,
 final_model:metrics.final_model,profiles:metrics.profiles,
 pca:{explained_variance_ratio:metrics.pca.explained_variance_ratio,points:pca},
 limitations:['Exploratory groups only: cluster IDs are arbitrary and are not risk, quality, eligibility, or lending labels.','The source is a historical Home Credit cohort and may not represent CreditIQ users.','The source contract has no credit utilization feature; requested principal is only a current-loan amount proxy, not total debt.','Bureau inquiry history availability for real applicants remains unresolved.','K-Means uses Euclidean distance and is sensitive to outliers, scaling, encoding, and the requested cluster count.','PCA is a lossy two-dimensional view; visual separation does not validate cluster quality.','TARGET was excluded from clustering, selection, profiling, and descriptions.']};

test('admin customer segmentation renders saved profiles and PCA and captures responsive screenshots',async({page})=>{
 await page.route('**/api/v1/**',async route=>{
  const path=new URL(route.request().url()).pathname;
  if(path==='/api/v1/me')return route.fulfill({json:{id:'admin-1',email:'admin@example.test',full_name:'Research Admin',role:'ADMIN',permissions:[]}});
  if(path==='/api/v1/admin/customer-segmentation')return route.fulfill({json:dashboard});
  return route.fulfill({status:404,json:{detail:'not mocked'}});
 });
 await page.setViewportSize({width:1280,height:900});
 await page.goto('/admin/customer-segmentation');
 await expect(page.getByRole('heading',{name:'Customer Segmentation'})).toBeVisible();
 await expect(page.getByText('4 neutral segments')).toBeVisible();
 await expect(page.getByText('TARGET was excluded from clustering, selection, profiling, and descriptions.')).toBeVisible();
 await expect(page.getByText('Unavailable',{exact:true}).first()).toBeVisible();
 await page.screenshot({path:'test-results/customer-segmentation-desktop.png',fullPage:true});
 await page.setViewportSize({width:390,height:844});
 await page.screenshot({path:'test-results/customer-segmentation-mobile.png',fullPage:true});
});
