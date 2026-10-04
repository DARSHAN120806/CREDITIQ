export type Schedule = {account_ref:string; installment_ref:string; schedule_version:string; due_date:string; amount:string};
export type Payment = {event_ref:string; account_ref:string; installment_ref:string; paid_date:string; amount:string};
export type HistoryInput = {label:string; source_kind:'USER_DECLARED'|'DEMO'; currency:'INR'|'XXX'; as_of:string; window_start:string; schedule_complete:boolean; payments_complete:boolean; effective_schedule_confirmed:true; schedules:Schedule[]; payments:Payment[]};
export type Timeline = {month:string;due_count:number;on_time:number;late:number;missed:number;partial:number;unknown:number;on_time_percent:number|null;recovery_30d_percent:number|null;recovery_eligible_count:number|null};
export type Analysis = {id:string;import_id:string;created_at:string;calculation_version:string;label:string;source_kind:string;currency:string;as_of:string;window_start:string;metrics:Record<string,number|string|null>;coverage:{status:string;basis:string;score_available:boolean;observed_installments:number;accounts:number;window_days:number;excluded_schedules:number;excluded_future_payments:number;interpretation:string};timeline:Timeline[];installments:{account_ref:string;installment_ref:string;due_date:string;scheduled_amount:string;paid_amount:string;status:string;delay_days:number|null;overdue_days:number|null}[]};
export type AnalysisPage = {items:Analysis[];total:number;limit:number;offset:number};
export const today = () => new Date().toISOString().slice(0,10);
export function demoHistory():HistoryInput {
  const end=today(); const cutoff=new Date(`${end}T00:00:00Z`);
  const day=(ago:number)=>new Date(cutoff.getTime()-ago*86400000).toISOString().slice(0,10);
  const schedules:Schedule[]=[],payments:Payment[]=[];
  for(let i=0;i<12;i++){
    const ago=350-i*30; const ref=`emi-${i+1}`;
    schedules.push({account_ref:'demo-loan',installment_ref:ref,schedule_version:'1',due_date:day(ago),amount:'5000.00'});
    if(i===10)continue;
    if(i===11){payments.push({event_ref:`payment-${i}`,account_ref:'demo-loan',installment_ref:ref,paid_date:day(ago-2),amount:'2500.00'});continue;}
    const delay=i<4?8:0;
    payments.push({event_ref:`payment-${i}-a`,account_ref:'demo-loan',installment_ref:ref,paid_date:day(ago+2),amount:'2000.00'});
    payments.push({event_ref:`payment-${i}-b`,account_ref:'demo-loan',installment_ref:ref,paid_date:day(ago-delay),amount:'3000.00'});
  }
  return {label:'Example repayment history',source_kind:'DEMO',currency:'XXX',as_of:end,window_start:day(365),schedule_complete:true,payments_complete:true,effective_schedule_confirmed:true,schedules,payments};
}
