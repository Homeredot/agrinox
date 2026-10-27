"use client";

import dynamic from "next/dynamic";
import type { FeatureCollection } from "geojson";
import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, BarChart3, Database, Download, FileText, Filter, LandPlot, LoaderCircle, LockKeyhole, MapPinned, ShieldCheck, Sprout, TrendingDown, TrendingUp } from "lucide-react";

import { API_URL, api } from "@/lib/api";

const DistrictMap = dynamic(() => import("./DistrictIntelligenceMap"), { ssr: false, loading: () => <div className="h-[440px] animate-pulse rounded-2xl bg-[#202522]" /> });

type Indicator = { value: string; label: string; unit: string; category: "crop" | "land" | "irrigation" | "practice" };
type Options = { years: number[]; seasons: { value: string; label: string }[]; provinces: string[]; districts: { province: string; district: string }[]; crops: string[]; indicators: Indicator[]; dataset_version: string; coverage: { districts: number; years: number[]; seasons: string[] } };
type Filters = { year: number; season: string; province: string; district: string; crop: string; indicator: string };
type Dashboard = {
  selection: Filters; indicator: Indicator;
  summary: { value: number | null; unit: string; records: number; geography: string; change: null | { from_period: string; absolute: number; percent: number } };
  trend: { period: string; year: number; season: string; value: number; unit: string }[];
  crop_comparison: { crop: string; value: number; unit: string }[];
  seasonal_comparison: { season: string; value: number; unit: string }[];
  map: { values: { district: string; province: string; value: number; unit: string }[]; available: boolean; districts_with_data: number; districts_total: number };
  coverage: { dataset_version: string; observation_period: string; district_records: number; missing_districts: string[]; note: string };
  sources: { season: string; title: string; url: string; report_url: string; observation_period: string; sample_note: string; sha256: string }[];
  methodology: string; sampling_notes: string[]; boundary_source: { title: string; url: string; note: string };
  private_farm_aggregate: { included: boolean; status: string; message: string; disclosure_rule: string };
};

function format(value: number | null, unit: string) {
  if (value == null) return "No data";
  const digits = unit.includes("tonnes/ha") || unit.includes("%") ? 2 : 0;
  return `${value.toLocaleString(undefined, { maximumFractionDigits: digits })} ${unit}`;
}

function LineChart({ data, unit }: { data: Dashboard["trend"]; unit: string }) {
  if (data.length < 2) return <div className="grid h-48 place-items-center text-center text-sm text-[#8f9991]">Historical district series is not available for this filter.<br/>Try Rwanda-level crop indicators for 2024–2026 trends.</div>;
  const width = 720, height = 210, pad = 34;
  const min = Math.min(...data.map(d => d.value)); const max = Math.max(...data.map(d => d.value)); const range = max - min || 1;
  const points = data.map((d, index) => ({ ...d, x: pad + index * (width - pad * 2) / Math.max(1, data.length - 1), y: height - pad - (d.value - min) / range * (height - pad * 2) }));
  return <div className="overflow-x-auto"><svg viewBox={`0 0 ${width} ${height}`} className="h-52 min-w-[580px] w-full" role="img" aria-label={`Historical ${unit} trend`}>
    {[0, .5, 1].map(t => { const y=height-pad-t*(height-pad*2); const v=min+t*range; return <g key={t}><line x1={pad} x2={width-pad} y1={y} y2={y} stroke="#455047" strokeDasharray="4 5"/><text x={2} y={y+4} fill="#8d978f" fontSize="10">{v.toLocaleString(undefined,{maximumFractionDigits:1})}</text></g>; })}
    <polyline points={points.map(p=>`${p.x},${p.y}`).join(" ")} fill="none" stroke="#a9d36d" strokeWidth="3"/>
    {points.map(p=><g key={p.period}><circle cx={p.x} cy={p.y} r="5" fill="#e2f3a7"><title>{p.period}: {p.value} {unit}</title></circle><text x={p.x} y={height-8} textAnchor="middle" fill="#9aa49c" fontSize="10">{p.period}</text></g>)}
  </svg></div>;
}

function Bars({ data, unit }: { data: { crop: string; value: number }[]; unit: string }) {
  if (!data.length) return <div className="grid h-52 place-items-center text-sm text-[#8f9991]">Crop comparison applies to crop indicators.</div>;
  const max = Math.max(...data.map(d => d.value), 1);
  return <div className="mt-5 space-y-2.5">{data.slice(0,8).map(item=><div key={item.crop} className="grid grid-cols-[82px_minmax(70px,1fr)_70px] items-center gap-2 text-xs sm:grid-cols-[110px_1fr_86px] sm:gap-3"><span className="truncate text-[#cbd3cc]" title={item.crop}>{item.crop}</span><div className="h-2.5 overflow-hidden rounded-full bg-[#343c36]"><div className="h-full rounded-full bg-gradient-to-r from-[#5c944e] to-[#b0d76d]" style={{width:`${Math.max(2,item.value/max*100)}%`}}/></div><strong className="text-right text-[#e5ebe6]">{item.value.toLocaleString(undefined,{maximumFractionDigits:1})}</strong></div>)}<p className="pt-1 text-right text-[10px] text-[#748078]">{unit}</p></div>;
}

export default function DistrictIntelligence({ token }: { token: string }) {
  const [options, setOptions] = useState<Options | null>(null); const [boundaries, setBoundaries] = useState<FeatureCollection | null>(null);
  const [filters, setFilters] = useState<Filters>({ year: 2026, season: "A", province: "", district: "", crop: "Maize", indicator: "production" });
  const [data, setData] = useState<Dashboard | null>(null); const [loading, setLoading] = useState(true); const [error, setError] = useState(""); const [exporting, setExporting] = useState("");

  const selectedIndicator = options?.indicators.find(item=>item.value===filters.indicator);
  const filteredDistricts = useMemo(()=>options?.districts.filter(item=>!filters.province||item.province===filters.province)??[],[options,filters.province]);

  function query(value: Filters) {
    const params = new URLSearchParams({ year: String(value.year), season: value.season, indicator: value.indicator });
    if (value.province) params.set("province", value.province); if (value.district) params.set("district", value.district); if (value.crop) params.set("crop", value.crop);
    return params.toString();
  }

  async function load(next = filters) {
    setLoading(true); setError("");
    try { setData(await api<Dashboard>(`/district-intelligence/dashboard?${query(next)}`,{},token)); }
    catch(e){setError(e instanceof Error?e.message:"District intelligence is unavailable");} finally {setLoading(false);}
  }

  useEffect(()=>{(async()=>{try{const [o,b]=await Promise.all([api<Options>("/district-intelligence/options",{},token),api<FeatureCollection>("/district-intelligence/boundaries",{},token)]);setOptions(o);setBoundaries(b);await load();}catch(e){setError(e instanceof Error?e.message:"Could not load NISR district data");setLoading(false);}})();},[]); // eslint-disable-line react-hooks/exhaustive-deps

  async function download(kind:"csv"|"pdf") {
    setExporting(kind); setError("");
    try { const response=await fetch(`${API_URL}/district-intelligence/export.${kind}?${query(filters)}`,{headers:{Authorization:`Bearer ${token}`}}); if(!response.ok)throw new Error("Export failed"); const blob=await response.blob(); const url=URL.createObjectURL(blob); const anchor=document.createElement("a"); anchor.href=url; anchor.download=kind==="csv"?"nisr-district-aggregate.csv":"nisr-district-intelligence.pdf"; anchor.click(); URL.revokeObjectURL(url); }
    catch(e){setError(e instanceof Error?e.message:"Export failed");} finally{setExporting("");}
  }

  function selectDistrict(district:string,province?:string){const next={...filters,province:province||filters.province,district};setFilters(next);void load(next);}

  return <section className="space-y-6">
    <header className="theme-on-dark relative overflow-hidden rounded-3xl border border-[#4c6848] bg-gradient-to-br from-[#213728] via-[#26382d] to-[#1f3240] p-4 sm:p-8">
      <div className="absolute -right-12 -top-16 h-60 w-60 rounded-full border border-[#b8dc7133] shadow-[0_0_90px_#9bc75a20]"/><div className="relative flex flex-wrap items-end justify-between gap-5"><div><h1 className="text-2xl font-semibold sm:text-4xl">District agricultural data</h1><p className="mobile-secondary mt-3 max-w-2xl text-sm text-[#bdc9bf]">Explore published NISR indicators for crops, land, irrigation, and agricultural practices. Individual farmer records are never shown here.</p></div><div className="rounded-xl border border-[#75966555] bg-[#1d2a22aa] px-3 py-2 sm:px-4 sm:py-3"><span className="mobile-secondary text-xs text-[#91a094] sm:block">Dataset</span><strong className="text-xs text-[#dce8d7] sm:text-sm">{options?.dataset_version??"Loading…"}</strong></div></div>
    </header>

    <div className="rounded-2xl border border-[#404a42] bg-[#222724] p-5"><div className="mb-4 flex items-center justify-between"><h2 className="flex items-center gap-2 font-semibold"><Filter size={18} className="text-[#a6cf6c]"/> Analysis filters</h2><span className="text-xs text-[#7f8a82]">Validated published options only</span></div><div className="grid sm:grid-cols-2 xl:grid-cols-6 gap-3">
      <label className="text-xs text-[#9da69f]">Year<select value={filters.year} onChange={e=>setFilters({...filters,year:Number(e.target.value)})} className="mt-1.5 w-full rounded-lg border border-[#4a554c] bg-[#191e1a] p-3 text-white">{options?.years.map(v=><option key={v}>{v}</option>)}</select></label>
      <label className="text-xs text-[#9da69f]">Season<select value={filters.season} onChange={e=>setFilters({...filters,season:e.target.value})} className="mt-1.5 w-full rounded-lg border border-[#4a554c] bg-[#191e1a] p-3 text-white">{options?.seasons.map(v=><option key={v.value} value={v.value}>{v.label}</option>)}</select></label>
      <label className="text-xs text-[#9da69f]">Province<select value={filters.province} onChange={e=>setFilters({...filters,province:e.target.value,district:""})} className="mt-1.5 w-full rounded-lg border border-[#4a554c] bg-[#191e1a] p-3 text-white"><option value="">All Rwanda</option>{options?.provinces.map(v=><option key={v}>{v}</option>)}</select></label>
      <label className="text-xs text-[#9da69f]">District<select value={filters.district} onChange={e=>setFilters({...filters,district:e.target.value})} className="mt-1.5 w-full rounded-lg border border-[#4a554c] bg-[#191e1a] p-3 text-white"><option value="">All districts</option>{filteredDistricts.map(v=><option key={v.district}>{v.district}</option>)}</select></label>
      <label className="text-xs text-[#9da69f]">Crop<select disabled={selectedIndicator?.category!=="crop"} value={filters.crop} onChange={e=>setFilters({...filters,crop:e.target.value})} className="mt-1.5 w-full rounded-lg border border-[#4a554c] bg-[#191e1a] p-3 text-white disabled:opacity-40">{options?.crops.map(v=><option key={v}>{v}</option>)}</select></label>
      <label className="text-xs text-[#9da69f]">Indicator<select value={filters.indicator} onChange={e=>setFilters({...filters,indicator:e.target.value})} className="mt-1.5 w-full rounded-lg border border-[#4a554c] bg-[#191e1a] p-3 text-white">{["crop","land","irrigation","practice"].map(category=><optgroup key={category} label={category.toUpperCase()}>{options?.indicators.filter(v=>v.category===category).map(v=><option key={v.value} value={v.value}>{v.label}</option>)}</optgroup>)}</select></label>
    </div><div className="mt-4 flex flex-wrap gap-3"><button onClick={()=>void load()} disabled={loading} className="flex items-center gap-2 rounded-xl bg-[#4d7947] px-5 py-3 text-sm font-bold disabled:opacity-50">{loading?<LoaderCircle size={18} className="animate-spin"/>:<BarChart3 size={18}/>}Apply filters</button><button onClick={()=>void download("csv")} disabled={!!exporting} className="flex items-center gap-2 rounded-xl border border-[#4b594e] px-4 py-3 text-sm hover:bg-[#2b332d]"><Download size={17}/>{exporting==="csv"?"Preparing…":"Export CSV"}</button><button onClick={()=>void download("pdf")} disabled={!!exporting} className="flex items-center gap-2 rounded-xl border border-[#4b594e] px-4 py-3 text-sm hover:bg-[#2b332d]"><FileText size={17}/>{exporting==="pdf"?"Preparing…":"Export PDF"}</button></div>{error&&<p role="alert" className="mt-3 text-sm text-[#ff9f9f]">{error}</p>}</div>

    {data&&<>
      <div className="grid sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <article className="rounded-2xl border border-[#435044] bg-[#232925] p-5"><span className="flex items-center gap-2 text-xs uppercase tracking-wider text-[#9ca69e]"><Sprout size={17} className="text-[#a6ce6b]"/>Selected value</span><strong className="mt-3 block text-2xl">{format(data.summary.value,data.summary.unit)}</strong><small className="text-[#89938b]">{data.summary.geography} · {filters.year} {filters.season}</small></article>
        <article className="rounded-2xl border border-[#435044] bg-[#232925] p-5"><span className="flex items-center gap-2 text-xs uppercase tracking-wider text-[#9ca69e]"><LandPlot size={17} className="text-[#a6ce6b]"/>Map coverage</span><strong className="mt-3 block text-2xl">{data.map.districts_with_data}/{data.map.districts_total}</strong><small className="text-[#89938b]">districts with a published value</small></article>
        <article className="rounded-2xl border border-[#435044] bg-[#232925] p-5"><span className="flex items-center gap-2 text-xs uppercase tracking-wider text-[#9ca69e]">{(data.summary.change?.percent??0)>=0?<TrendingUp size={17} className="text-[#9ed27c]"/>:<TrendingDown size={17} className="text-[#e8a273]"/>}Historical change</span><strong className="mt-3 block text-2xl">{data.summary.change?`${data.summary.change.percent>0?"+":""}${data.summary.change.percent}%`:"Not available"}</strong><small className="text-[#89938b]">{data.summary.change?`since ${data.summary.change.from_period}`:"No comparable earlier period"}</small></article>
        <article className="rounded-2xl border border-[#435044] bg-[#232925] p-5"><span className="flex items-center gap-2 text-xs uppercase tracking-wider text-[#9ca69e]"><Database size={17} className="text-[#a6ce6b]"/>Observation</span><strong className="mt-3 block text-lg">{data.indicator.label}</strong><small className="text-[#89938b]">Unit: {data.indicator.unit}</small></article>
      </div>

      <div className="grid xl:grid-cols-[1.35fr_.65fr] gap-5"><article className="rounded-2xl border border-[#404a42] bg-[#222724] p-5"><div className="flex items-center justify-between"><div><h2 className="font-semibold">District map</h2><p className="mt-1 text-xs text-[#8d978f]">Click a district to filter the dashboard</p></div><MapPinned className="text-[#9fc96b]"/></div><div className="mt-4">{boundaries?<DistrictMap boundaries={boundaries} values={data.map.values} selectedDistrict={filters.district} unit={data.indicator.unit} onDistrict={selectDistrict}/>:<div className="h-[440px] animate-pulse rounded-2xl bg-[#1a1e1b]"/>}</div>{!data.map.available&&<p className="mt-3 flex gap-2 rounded-xl bg-[#372e21] p-3 text-sm text-[#e2bc7d]"><AlertTriangle size={18} className="shrink-0"/>No district boundary can be colored because this filter has no compatible district-level observation.</p>}</article>
      <article className="rounded-2xl border border-[#404a42] bg-[#222724] p-5"><h2 className="font-semibold">Crop comparison</h2><p className="mt-1 text-xs text-[#8d978f]">Top published values for the same period and geography</p><Bars data={data.crop_comparison} unit={data.indicator.unit}/><div className="mt-6 border-t border-[#3b443d] pt-4"><h3 className="text-sm font-semibold">Season comparison</h3><div className="mt-3 grid grid-cols-2 gap-3">{data.seasonal_comparison.map(item=><div key={item.season} className="rounded-xl bg-[#1b201c] p-3"><span className="text-xs text-[#8e9890]">Season {item.season}</span><strong className="mt-1 block">{format(item.value,item.unit)}</strong></div>)}{!data.seasonal_comparison.length&&<p className="col-span-2 text-sm text-[#88928a]">No comparable seasons.</p>}</div></div></article></div>

      <article className="rounded-2xl border border-[#404a42] bg-[#222724] p-5"><h2 className="font-semibold">Historical trend</h2><p className="mt-1 text-xs text-[#8d978f]">Published observations only; gaps are not interpolated</p><LineChart data={data.trend} unit={data.indicator.unit}/></article>

      <div className="grid lg:grid-cols-2 gap-5"><article className="rounded-2xl border border-[#404a42] bg-[#222724] p-5"><h2 className="flex items-center gap-2 font-semibold"><ShieldCheck size={19} className="text-[#a8d16d]"/>Evidence and coverage</h2><dl className="mt-4 grid grid-cols-1 gap-x-3 gap-y-2 text-sm sm:grid-cols-[130px_1fr] sm:gap-y-3"><dt className="text-[#8f9991]">Source period</dt><dd>{data.coverage.observation_period||"No matching observation"}</dd><dt className="text-[#8f9991]">Coverage</dt><dd>{data.coverage.note}</dd><dt className="text-[#8f9991]">Missing data</dt><dd>{data.coverage.missing_districts.length?`${data.coverage.missing_districts.length} districts: ${data.coverage.missing_districts.join(", ")}`:"No missing district values for this view."}</dd><dt className="text-[#8f9991]">Processing</dt><dd>{data.methodology}</dd></dl><div className="mt-5 space-y-3">{data.sources.map(source=><a key={source.season} href={source.report_url} target="_blank" rel="noreferrer" className="block rounded-xl border border-[#445047] bg-[#1b201c] p-3 hover:border-[#728466]"><strong className="text-sm">{source.title}</strong><span className="mt-1 block text-xs text-[#8e9990]">{source.observation_period} · Source table verified by SHA-256</span></a>)}</div></article>
      <article className="rounded-2xl border border-[#5b5135] bg-[#292820] p-5"><h2 className="flex items-center gap-2 font-semibold"><LockKeyhole size={19} className="text-[#dbc775]"/>Official and private data stay separate</h2><div className="mt-4 rounded-xl border border-[#4f5d4f] bg-[#1d251f] p-4"><span className="text-xs font-bold uppercase tracking-wider text-[#a8d16d]">Official view</span><p className="mt-2 text-sm text-[#bcc7be]">This dashboard and its exports contain published NISR aggregates only. They contain no farmer name, farm coordinate, device identifier or individual sensor reading.</p></div><div className="mt-3 rounded-xl border border-[#564d37] bg-[#27241c] p-4"><span className="text-xs font-bold uppercase tracking-wider text-[#dfc579]">Private observations suppressed</span><p className="mt-2 text-sm text-[#c8c0a7]">{data.private_farm_aggregate.message}</p><p className="mt-2 text-xs text-[#958d75]">{data.private_farm_aggregate.disclosure_rule}</p></div><div className="mt-5"><h3 className="text-sm font-semibold">Sampling notes</h3>{data.sampling_notes.map((note,index)=><p key={index} className="mt-2 flex gap-2 text-sm text-[#aeb8b0]"><span className="text-[#cbd878]">—</span>{note}</p>)}</div></article></div>
    </>}
  </section>;
}
