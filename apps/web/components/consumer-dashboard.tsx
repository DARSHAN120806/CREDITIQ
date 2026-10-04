"use client";
import { RepaymentPreview } from './installment-workspace';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { User } from '../lib/api';
import { Application, dashboardAnalytics, loadAllApplications } from '../lib/applications';
import ApplicationTable from './application-table';
import DashboardCharts from './dashboard-charts';
import { FinancialSummary, EstimateNote } from './financial-insights';
export default function ConsumerDashboard({user}:{user:User}) {
  const [items,setItems]=useState<Application[]|null>(null);
  const [error,setError]=useState('');
  useEffect(()=>{let active=true;loadAllApplications().then(rows=>{if(active)setItems(rows);}).catch(e=>{if(active)setError(e.message);});return()=>{active=false;};},[]);
  const data=items?dashboardAnalytics(items):null;
  const cards=[['Total Applications',data?.total,'Your complete application history'],['Average Financial Health Score',data?.average===null?'—':data?.average.toFixed(1),'Across assessed applications'],['Low Risk Applications',data?.distribution[0].value,'Risk probability below 5%'],['High Risk Applications',data?.distribution[2].value,'Risk probability of 15% or more']];
  return <><div className="page-heading"><div><div className="eyebrow">Your financial overview</div><h1>Hello, {user.full_name.split(' ')[0]}.</h1><p>A clearer picture of your borrowing journey.</p></div><Link className="btn" href="/applications/new">＋ New application</Link></div><div className="welcome-banner"><div><span className="eyebrow">Clarity for your next step</span><h2>Understand your numbers.<br/>Plan with confidence.</h2><p>Explore risk, track progress and find a repayment plan that fits.</p></div><div className="banner-symbol" aria-hidden="true">↗</div></div>{error&&<div className="error" role="alert">{error} Analytics could not be completed. Refresh to try again.</div>}<div className="cards dashboard-cards">{cards.map(([label,value,description],i)=><div className="card" key={label}><div className={`metric-icon icon-${i}`} aria-hidden="true">{['▤','↗','✓','!'][i]}</div><span className="muted">{label}</span><strong className="metric">{value??'—'}</strong><p className="muted">{description}</p></div>)}</div>{items?<><DashboardCharts items={items}/>{items.length>0&&<FinancialSummary application={items[0]}/>}<section className="panel"><div className="section-heading"><h2>Recent applications</h2><Link className="text-link" href="/applications">View all →</Link></div><ApplicationTable items={items.slice(0,5)}/></section></>:!error&&<p role="status">Loading your financial overview…</p>}<RepaymentPreview/><EstimateNote/></>;
}

