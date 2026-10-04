import { api } from "./api";
import { financialHealth, riskLevel } from "./finance";
export type Result = { probability:number; risk_score:number; risk_band:string; credit_health_index:number; recommendation:string; model_version:string; scored_at:string; quality_flags:string[] };
export type Application = { id:string; user_id:string; requested_amount:string; status:string; created_at:string; version:number; input?:Record<string,unknown>; quote?:{ monthly_payment:string; annual_rate:string; term_months:number }; result?:Result };
export type Page<T> = { items:T[]; total:number; limit:number; offset:number };

export async function hydrateApplications(items: Application[], admin = false) {
  const hydrated: Application[] = [];
  // Bound fan-out; errors remain visible rather than showing incomplete averages as complete.
  for (let i = 0; i < items.length; i += 4) {
    hydrated.push(...await Promise.all(items.slice(i, i + 4).map(item => item.input && item.quote && item.result
      ? Promise.resolve(item) : api<Application>(`${admin ? "/admin" : ""}/applications/${item.id}`))));
  }
  return hydrated;
}
export async function loadApplicationPage(url: string, admin = false) {
  const page = await api<Page<Application>>(url);
  return { ...page, items: await hydrateApplications(page.items, admin) };
}
export async function loadAllApplications() {
  const items: Application[] = [];
  let offset = 0;
  while (true) {
    const page = await api<Page<Application>>(`/applications?limit=100&offset=${offset}`);
    items.push(...page.items);
    offset += page.items.length;
    if (offset >= page.total) break;
    if (!page.items.length) throw new Error("Applications changed while loading. Please refresh.");
  }
  const unique = [...new Map(items.map(item => [item.id, item])).values()];
  return hydrateApplications(unique);
}
export function dashboardAnalytics(items: Application[]) {
  const scored = items.filter(item => item.result);
  const distribution = ["Low", "Moderate", "High"].map(name => ({name, value: scored.filter(item => riskLevel(item.result!.probability) === name).length}));
  const days = new Map<string, {date:string; applications:number; sum:number; count:number}>();
  for (const item of items) {
    const key = new Date(item.created_at).toISOString().slice(0,10);
    const day = days.get(key) ?? {date:key, applications:0, sum:0, count:0};
    day.applications++;
    if (item.result) {day.sum += financialHealth(item.result.probability);day.count++;}
    days.set(key,day);
  }
  return {total:items.length, average:scored.length ? scored.reduce((sum,item)=>sum+financialHealth(item.result!.probability),0)/scored.length : null,
    scored:scored.length, distribution, trend:[...days.values()].sort((a,b)=>a.date.localeCompare(b.date)).map(day=>({...day, health:day.count?day.sum/day.count:null}))};
}
