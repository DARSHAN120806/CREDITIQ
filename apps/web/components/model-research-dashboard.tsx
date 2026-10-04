"use client";

import { useEffect, useState } from 'react';
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { api } from '../lib/api';

type MetricValues = { roc_auc:number; average_precision:number; brier_score:number };
type Model = { name:string; model:string; status:string; run_id:string; feature_count:number; values:MetricValues };
type Bin = { model:string; bin:number; mean_predicted_probability:number; observed_default_rate:number };
type Feature = { feature:string; mean_abs_shap_raw_margin:number };
type Dashboard = {
 mode:string; release_ready:boolean; metrics:Model[]; metric_deltas:MetricValues;
 calibration:{method:string;cohort:string;test_rows:number;bins:Bin[];summary:string};
 shap:{interpretation:string;top_features:Feature[];importance:Feature[]};
 contracts:Record<string,{feature_count:number;groups:{name:string;features:string[]}[]}>;
 ablation:{variant:string;feature_count:number;roc_auc:number;average_precision:number;brier_score:number;evaluation_cohort:string}[];
 registry:{name:string;version:string;feature_count:number;training_date:string;calibration_method:string;dataset_size:number;status:string}[];
 limitations:string[]; ablation_note:string; shap_note:string;
};

const metricLabels:{key:keyof MetricValues;label:string;better:'higher'|'lower'}[]=[
 {key:'roc_auc',label:'ROC-AUC',better:'higher'},
 {key:'average_precision',label:'Average Precision',better:'higher'},
 {key:'brier_score',label:'Brier Score',better:'lower'},
];
const percent=(value:number)=>`${(value*100).toFixed(2)}%`;
const score=(value:number)=>value.toFixed(4);

function ReliabilityChart({model,bins}:{model:string;bins:Bin[]}) {
 const data=bins.filter(row=>row.model===model);
 return <section className="panel research-chart-panel"><h3>{model==='Lite'?'Lite':'FULL_RESEARCH_V1_NO_EXT'}</h3><div className="chart" role="img" aria-label={`${model} reliability curve, predicted probability versus observed event rate`}>
  <ResponsiveContainer width="100%" height="100%"><LineChart data={data} margin={{top:12,right:16,bottom:16,left:0}}>
   <CartesianGrid strokeDasharray="3 3"/><XAxis type="number" dataKey="mean_predicted_probability" domain={[0,'dataMax']} tickFormatter={percent} name="Mean predicted probability"/><YAxis type="number" domain={[0,'dataMax']} tickFormatter={percent} name="Observed outcome rate"/><Tooltip formatter={(value)=>percent(Number(value))}/>
   <Line dataKey="mean_predicted_probability" name="Perfect calibration" stroke="#94a3b8" strokeDasharray="5 5" dot={false} isAnimationActive={false}/>
   <Line dataKey="observed_default_rate" name="Observed rate" stroke={model==='Lite'?'#0f766e':'#6366f1'} strokeWidth={3} dot={{r:3}} isAnimationActive={false}/>
  </LineChart></ResponsiveContainer>
 </div><p className="muted">Ten saved test-set bins · x: predicted probability · y: observed rate.</p></section>;
}

export default function ModelResearchDashboard(){
 const [data,setData]=useState<Dashboard|null>(null);const [error,setError]=useState('');
 useEffect(()=>{let active=true;api<Dashboard>('/admin/model-research').then(value=>{if(active)setData(value);}).catch(reason=>{if(active)setError((reason as Error).message);});return()=>{active=false;};},[]);
 if(error)return <><div className="eyebrow">Research evaluation</div><h1>Model Research Dashboard</h1><div className="error" role="alert">{error}</div></>;
 if(!data)return <main><p role="status">Loading saved model research artifacts…</p></main>;
 const [lite,research]=data.metrics;
 return <main className="model-research">
  <div className="page-heading"><div><div className="eyebrow">Admin · Model evaluation</div><h1>Model Research Dashboard</h1><p>Side-by-side diagnostics from saved model runs. This page does not score applications.</p></div><span className="badge research-only">RESEARCH_ONLY · release_ready=false</span></div>
  <div className="notice research-notice">FULL_RESEARCH_V1_NO_EXT remains RESEARCH_ONLY. Neither model comparison nor research metrics are production approval evidence.</div>

  <section className="panel"><div className="section-heading"><div><h2>Model overview</h2><p className="muted">Paired evaluation on the same untouched final-test cohort · {data.calibration.test_rows.toLocaleString()} applicants</p></div></div>
   <div className="tablewrap"><table className="research-table"><thead><tr><th>Metric</th><th>Lite · 17 features</th><th>Research · 22 features</th><th>Delta · research − Lite</th><th>Direction</th></tr></thead><tbody>{metricLabels.map(({key,label,better})=>{const delta=data.metric_deltas[key];return <tr key={key}><th scope="row">{label}</th><td>{score(lite.values[key])}</td><td>{score(research.values[key])}</td><td className={delta===0?'':(delta>0)===(better==='higher')?'delta-good':'delta-neutral'}>{delta>0?'+':''}{score(delta)}</td><td>{better==='higher'?'Higher is better':'Lower is better'}</td></tr>;})}<tr><th scope="row">Feature count</th><td>{lite.feature_count}</td><td>{research.feature_count}</td><td>+{research.feature_count-lite.feature_count}</td><td>Research contract size</td></tr></tbody></table></div>
   <div className="research-model-status"><div><strong>Lite</strong><span>{lite.status}</span><code>{lite.run_id}</code></div><div><strong>FULL_RESEARCH_V1_NO_EXT</strong><span>{research.status}</span><code>{research.run_id}</code></div></div>
  </section>

  <section className="panel"><div className="section-heading"><div><h2>Calibration analysis</h2><p className="muted">Saved reliability bins from the paired, untouched final-test cohort. Calibration: {data.calibration.method}.</p></div></div><p>{data.calibration.summary}</p>
   <div className="research-chart-grid"><ReliabilityChart model="Lite" bins={data.calibration.bins}/><ReliabilityChart model="FULL_RESEARCH_V1_NO_EXT" bins={data.calibration.bins}/></div>
   <details className="research-details"><summary>Reliability bin values</summary><div className="tablewrap"><table><thead><tr><th>Model</th><th>Bin</th><th>Mean predicted probability</th><th>Observed rate</th></tr></thead><tbody>{data.calibration.bins.map(row=><tr key={`${row.model}-${row.bin}`}><td>{row.model}</td><td>{row.bin}</td><td>{percent(row.mean_predicted_probability)}</td><td>{percent(row.observed_default_rate)}</td></tr>)}</tbody></table></div></details>
  </section>

  <section className="panel"><div className="section-heading"><div><h2>Research feature contributions</h2><p className="muted">Existing Tree SHAP rankings for FULL_RESEARCH_V1_NO_EXT. No new SHAP values are generated here.</p></div></div>
   <p>{data.shap.interpretation}</p><div className="research-shap-grid"><section className="panel research-chart-panel"><h3>Top 20 mean absolute SHAP values</h3><div className="research-shap-chart" role="img" aria-label="Bar chart of the top 20 research model features by mean absolute SHAP raw-margin contribution"><ResponsiveContainer width="100%" height="100%"><BarChart data={data.shap.top_features} layout="vertical" margin={{top:8,right:22,bottom:8,left:22}}><CartesianGrid horizontal={false} strokeDasharray="3 3"/><XAxis type="number"/><YAxis type="category" dataKey="feature" width={205} tick={{fontSize:11}}/><Tooltip formatter={(value)=>Number(value).toFixed(4)}/><Bar dataKey="mean_abs_shap_raw_margin" name="Mean |SHAP|" fill="#0f766e" radius={[0,4,4,0]}/></BarChart></ResponsiveContainer></div></section>
    <section className="panel research-chart-panel"><h3>Feature contribution ranking</h3><div className="tablewrap research-feature-table"><table><thead><tr><th>Rank</th><th>Feature</th><th>Mean |SHAP|</th></tr></thead><tbody>{data.shap.top_features.map((row,index)=><tr key={row.feature}><td>{index+1}</td><td>{row.feature}</td><td>{row.mean_abs_shap_raw_margin.toFixed(4)}</td></tr>)}</tbody></table></div></section>
   </div><p className="muted">{data.shap_note} Absolute SHAP values rank contribution magnitude and do not show direction or causation.</p>
  </section>

  <section className="panel"><div className="section-heading"><div><h2>Feature contracts</h2><p className="muted">Lite: 17 features · FULL_RESEARCH_V1_NO_EXT: 22 features</p></div></div><div className="research-contract-grid">{Object.entries(data.contracts).map(([name,contract])=><article className="panel" key={name}><h3>{name} <span className="badge">{contract.feature_count} features</span></h3>{contract.groups.map(group=><div className="research-feature-group" key={group.name}><strong>{group.name}</strong><p>{group.features.join(' · ')}</p></div>)}</article>)}</div></section>

  <section className="panel"><div className="section-heading"><div><h2>Feature ablation</h2><p className="muted">Existing saved diagnostics; separate from the final-test model comparison.</p></div></div><div className="notice">{data.ablation_note}</div><div className="research-ablation-grid">{(['roc_auc','average_precision','brier_score'] as const).map((metric,index)=><section className="panel research-chart-panel" key={metric}><h3>{metric==='roc_auc'?'ROC-AUC':metric==='average_precision'?'Average Precision':'Brier Score'}</h3><div className="chart" role="img" aria-label={`Feature ablation comparison for ${metric}`}><ResponsiveContainer width="100%" height="100%"><BarChart data={data.ablation} margin={{top:12,right:8,bottom:50,left:0}}><CartesianGrid vertical={false} strokeDasharray="3 3"/><XAxis dataKey="variant" interval={0} tickFormatter={value=>({'FULL_RESEARCH_V1_NO_EXT':'Full research','Lite feature subset (17)':'Lite subset','Without inquiry features':'No inquiries','Without loan-to-goods ratio':'No loan-to-goods'} as Record<string,string>)[value]??value} angle={-25} textAnchor="end" height={70} tick={{fontSize:9}}/><YAxis domain={['dataMin', 'dataMax']} tick={{fontSize:10}}/><Tooltip formatter={(value)=>Number(value).toFixed(4)}/><Bar dataKey={metric} name={metric==='brier_score'?'Brier Score':metric==='roc_auc'?'ROC-AUC':'Average Precision'} fill={index===2?'#6366f1':'#0f766e'}/></BarChart></ResponsiveContainer></div></section>)}</div>
   <details className="research-details"><summary>Ablation values and evaluation cohort</summary><div className="tablewrap"><table><thead><tr><th>Variant</th><th>Features</th><th>ROC-AUC</th><th>Average Precision</th><th>Brier</th><th>Cohort</th></tr></thead><tbody>{data.ablation.map(row=><tr key={row.variant}><td>{row.variant}</td><td>{row.feature_count}</td><td>{score(row.roc_auc)}</td><td>{score(row.average_precision)}</td><td>{score(row.brier_score)}</td><td>{row.evaluation_cohort}</td></tr>)}</tbody></table></div></details>
  </section>

  <section className="panel"><div className="section-heading"><div><h2>Artifact registry</h2><p className="muted">Metadata and run pointers read from existing artifacts.</p></div></div><div className="tablewrap"><table className="research-table"><thead><tr><th>Model</th><th>Version</th><th>Features</th><th>Training date</th><th>Calibration</th><th>Dataset size</th><th>Status</th></tr></thead><tbody>{data.registry.map(row=><tr key={row.name}><th scope="row">{row.name}</th><td><code>{row.version}</code></td><td>{row.feature_count}</td><td>{row.training_date.slice(0,10)}</td><td>{row.calibration_method}</td><td>{row.dataset_size.toLocaleString()}</td><td>{row.status}</td></tr>)}</tbody></table></div></section>

  <section className="panel research-limitations"><div className="section-heading"><div><h2>Model limitations</h2><p className="muted">Research diagnostics only</p></div></div><ul>{data.limitations.map(item=><li key={item}>{item}</li>)}</ul></section>
 </main>;
}
