"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";
import { Activity, AlertTriangle, CalendarDays, Cloud, Layers3, LoaderCircle, MapPin, Orbit, Search, ShieldCheck, Sparkles } from "lucide-react";
import type { GeoJsonObject } from "geojson";

import { API_URL, api, type Farm } from "@/lib/api";

const SatelliteMap = dynamic(() => import("./SatelliteMap"), { ssr: false, loading: () => <div className="h-[430px] animate-pulse rounded-2xl bg-[#202522]" /> });

type LocationResult = { display_name: string; latitude: number; longitude: number };
type TrendPoint = { date: string; ndvi: number; ndvi_min: number; ndvi_max: number; valid_area_percent: number | null };
type DashboardData = {
  integration: { configured: boolean; status: string; message: string; provider: string; collection: string; simulated: boolean };
  area: { label: string; source_mode: string; geometry: GeoJsonObject; bbox: [number, number, number, number] };
  spatial_resolution_m: number;
  latest: null | { acquisition_date: string; cloud_coverage_percent: number | null; cloud_coverage_scope: string; ndvi: number; valid_area_percent: number | null };
  trend: TrendPoint[];
  comparison: null | { previous_date: string; previous_ndvi: number; change: number };
  unusual_changes: { date: string; change: number; severity: string; message: string }[];
  imagery_available: boolean;
  limitations: string[];
  simulated: boolean;
};

function isoDate(date: Date) { return date.toISOString().slice(0, 10); }
function ndviLabel(value: number) {
  if (value < 0) return "Water / non-vegetation";
  if (value < 0.2) return "Very low vegetation";
  if (value < 0.4) return "Sparse or stressed cover";
  if (value < 0.6) return "Moderate vegetation";
  return "Dense green vegetation";
}

function TrendChart({ points }: { points: TrendPoint[] }) {
  if (points.length < 2) return <div className="h-44 grid place-items-center text-sm text-[#98a19a]">Two or more clear observations are needed for a trend.</div>;
  const width = 720, height = 190, pad = 25;
  const values = points.map((p) => p.ndvi);
  const min = Math.min(-0.1, ...values), max = Math.max(0.8, ...values);
  const coords = points.map((p, index) => ({ x: pad + index * (width - pad * 2) / (points.length - 1), y: height - pad - (p.ndvi - min) / (max - min) * (height - pad * 2), ...p }));
  return <div className="overflow-x-auto"><svg viewBox={`0 0 ${width} ${height}`} className="min-w-[580px] w-full h-48" role="img" aria-label="NDVI vegetation trend">
    {[0.2, 0.4, 0.6].map(v => { const y = height - pad - (v - min) / (max - min) * (height - pad * 2); return <g key={v}><line x1={pad} x2={width-pad} y1={y} y2={y} stroke="#465148" strokeDasharray="4 5"/><text x={1} y={y+4} fill="#8e9990" fontSize="10">{v}</text></g>; })}
    <polyline fill="none" stroke="#a8d36f" strokeWidth="3" points={coords.map(p => `${p.x},${p.y}`).join(" ")} />
    {coords.map((p, i) => <g key={p.date}><circle cx={p.x} cy={p.y} r="5" fill="#d8ef8b"><title>{p.date}: NDVI {p.ndvi}</title></circle>{(i===0||i===coords.length-1)&&<text x={p.x} y={height-5} textAnchor={i===0?"start":"end"} fill="#9da69f" fontSize="10">{p.date.slice(5)}</text>}</g>)}
  </svg></div>;
}

export default function SatelliteMonitoring({ farms, token }: { farms: Farm[]; token: string }) {
  const mappedFields = useMemo(() => farms.flatMap(farm => farm.fields.filter(field => field.boundary_geojson).map(field => ({ ...field, farmName: farm.name }))), [farms]);
  const [mode, setMode] = useState<"field" | "location">(mappedFields.length ? "field" : "location");
  const [fieldId, setFieldId] = useState<number | null>(mappedFields[0]?.id ?? null);
  const [query, setQuery] = useState(""); const [results, setResults] = useState<LocationResult[]>([]);
  const [location, setLocation] = useState<LocationResult | null>(null); const [radius, setRadius] = useState(250);
  const [from, setFrom] = useState(isoDate(new Date(Date.now() - 180 * 86400000))); const [to, setTo] = useState(isoDate(new Date()));
  const [data, setData] = useState<DashboardData | null>(null); const [loading, setLoading] = useState(false); const [searching, setSearching] = useState(false);
  const [error, setError] = useState(""); const [imageUrl, setImageUrl] = useState<string | null>(null); const [saving, setSaving] = useState(false);

  useEffect(() => () => { if (imageUrl) URL.revokeObjectURL(imageUrl); }, [imageUrl]);
  const request = mode === "field" ? { field_id: fieldId, date_from: from, date_to: to } : { latitude: location?.latitude, longitude: location?.longitude, radius_m: radius, label: location?.display_name, date_from: from, date_to: to };

  async function searchLocation() {
    if (query.trim().length < 2) return; setSearching(true); setError("");
    try { setResults(await api<LocationResult[]>(`/locations/search?q=${encodeURIComponent(query.trim())}`, {}, token)); }
    catch (e) { setError(e instanceof Error ? e.message : "Location search failed"); } finally { setSearching(false); }
  }

  async function load() {
    if ((mode === "field" && !fieldId) || (mode === "location" && !location)) { setError("Choose a mapped field or a searched Rwanda location first."); return; }
    setLoading(true); setError(""); setData(null); if (imageUrl) { URL.revokeObjectURL(imageUrl); setImageUrl(null); }
    try {
      const next = await api<DashboardData>("/satellite/dashboard", { method: "POST", body: JSON.stringify(request) }, token); setData(next);
      if (next.imagery_available) {
        const response = await fetch(`${API_URL}/satellite/imagery`, { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` }, body: JSON.stringify(request) });
        if (response.ok) setImageUrl(URL.createObjectURL(await response.blob()));
      }
    } catch (e) { setError(e instanceof Error ? e.message : "Satellite monitoring is unavailable"); } finally { setLoading(false); }
  }

  async function saveArea() {
    if (!location) return; setSaving(true);
    try { await api("/satellite/areas", { method: "POST", body: JSON.stringify({ name: location.display_name.slice(0, 160), latitude: location.latitude, longitude: location.longitude, radius_m: radius }) }, token); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not save this area"); } finally { setSaving(false); }
  }

  return <section className="space-y-6 satellite-atmosphere">
    <div className="theme-on-dark relative overflow-hidden rounded-3xl border border-[#536b45] bg-gradient-to-br from-[#243824] via-[#263b31] to-[#1d3140] p-4 sm:p-8">
      <div className="absolute -right-10 -top-14 h-52 w-52 rounded-full border border-[#badb7140] shadow-[0_0_80px_#a7ce5d22]" />
      <div className="relative flex flex-wrap items-end justify-between gap-5">
        <div><h1 className="text-2xl font-semibold sm:text-4xl">Satellite farm monitoring</h1><p className="mobile-secondary mt-3 max-w-2xl text-sm text-[#c0ccc2]">Review vegetation change from available cloud-filtered observations. Select a mapped field or search for a location in Rwanda.</p></div>
        <span className={`rounded-full border px-4 py-2 text-xs font-bold ${data?.integration.configured ? "border-[#7fc36d] bg-[#254c2e] text-[#b8e99f]" : "border-[#a77e45] bg-[#473720] text-[#f0c57f]"}`}><span className="mr-2">●</span>{data ? data.integration.status.replaceAll("_", " ") : "Waiting for selection"}</span>
      </div>
    </div>

    <div className="grid lg:grid-cols-[340px_1fr] gap-5">
      <aside className="rounded-2xl border border-[#3f4941] bg-[#222724] p-5 h-fit">
        <h2 className="font-semibold">1. Choose monitoring area</h2>
        <div className="mt-4 grid grid-cols-2 rounded-xl bg-[#191d1a] p-1"><button onClick={()=>{setMode("field");setData(null)}} className={`rounded-lg py-2.5 text-sm ${mode==="field"?"bg-[#39543a] text-white":"text-[#8f9991]"}`}>My field</button><button onClick={()=>{setMode("location");setData(null)}} className={`rounded-lg py-2.5 text-sm ${mode==="location"?"bg-[#39543a] text-white":"text-[#8f9991]"}`}>Search location</button></div>
        {mode === "field" ? <div className="mt-4"><label className="text-xs uppercase tracking-wider text-[#a2aaa4]">Farm · mapped field</label><select value={fieldId??""} onChange={e=>setFieldId(Number(e.target.value))} className="mt-2 w-full rounded-xl border border-[#4b574d] bg-[#1b201c] p-3"><option value="">Select field</option>{mappedFields.map(f=><option key={f.id} value={f.id}>{f.farmName} · {f.name}</option>)}</select>{mappedFields.length===0&&<p className="mt-3 text-xs text-[#e1b46e]">No field has a drawn boundary yet. Use Search location, or draw the boundary in My Farm.</p>}</div> : <div className="relative mt-4"><label className="text-xs uppercase tracking-wider text-[#a2aaa4]">Rwanda place</label><div className="mt-2 flex gap-2"><input value={query} onChange={e=>setQuery(e.target.value)} onKeyDown={e=>{if(e.key==="Enter")void searchLocation()}} placeholder="Search cell, village or place" className="min-w-0 flex-1 rounded-xl border border-[#4b574d] bg-[#1b201c] px-3"/><button onClick={()=>void searchLocation()} className="rounded-xl bg-[#3d6844] p-3" aria-label="Search">{searching?<LoaderCircle className="animate-spin" size={18}/>:<Search size={18}/>}</button></div>{results.length>0&&<div className="absolute z-[1200] mt-2 max-h-56 w-full overflow-auto rounded-xl border border-[#4b574d] bg-[#1d221e] shadow-2xl">{results.map((r,i)=><button key={i} onClick={()=>{setLocation(r);setQuery(r.display_name);setResults([]);setData(null)}} className="flex w-full gap-2 border-b border-[#343c36] p-3 text-left text-sm hover:bg-[#2d382f]"><MapPin size={16} className="mt-0.5 shrink-0 text-[#a7d268]"/><span>{r.display_name}</span></button>)}</div>}<label className="mt-4 block text-xs uppercase tracking-wider text-[#a2aaa4]">Observation radius · {radius} m</label><input type="range" min="50" max="1000" step="50" value={radius} onChange={e=>setRadius(Number(e.target.value))} className="mt-2 w-full accent-[#9dc862]"/>{location&&<button onClick={()=>void saveArea()} disabled={saving} className="mt-2 text-xs text-[#b9d88b] hover:underline">{saving?"Saving…":"Save these coordinates in SQLite"}</button>}</div>}
        <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2"><label className="text-xs text-[#a2aaa4]">From<input type="date" value={from} onChange={e=>setFrom(e.target.value)} className="mt-1.5 w-full min-w-0 rounded-lg border border-[#4b574d] bg-[#1b201c] p-2.5 text-white"/></label><label className="text-xs text-[#a2aaa4]">To<input type="date" value={to} onChange={e=>setTo(e.target.value)} className="mt-1.5 w-full min-w-0 rounded-lg border border-[#4b574d] bg-[#1b201c] p-2.5 text-white"/></label></div>
        <button onClick={()=>void load()} disabled={loading} className="mt-5 flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-[#557f3b] to-[#33715a] py-3 font-bold disabled:opacity-50">{loading?<LoaderCircle className="animate-spin" size={19}/>:<Sparkles size={19}/>} View real observations</button>
        {error&&<p role="alert" className="mt-3 text-sm text-[#ff9f9f]">{error}</p>}
      </aside>

      <div className="space-y-4">
        <SatelliteMap geometry={data?.area.geometry} bbox={data?.area.bbox} imageUrl={imageUrl}/>
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2 rounded-xl border border-[#3d493f] bg-[#202522] px-4 py-3 text-xs"><strong className="text-[#dfe9df]">NDVI legend</strong>{[["#526fb8","< 0 Water"],["#ba8545","0–0.2 Very low"],["#d6c24f","0.2–0.4 Sparse"],["#7daf40","0.4–0.6 Moderate"],["#19732e","> 0.6 Dense"]].map(([c,l])=><span key={l} className="flex items-center gap-2 text-[#aeb7b0]"><i className="h-3 w-3 rounded-sm" style={{background:c}}/>{l}</span>)}</div>
      </div>
    </div>

    {data && <>
      {!data.integration.configured && <div className="flex gap-3 rounded-2xl border border-[#896c3d] bg-[#362d20] p-5"><AlertTriangle className="shrink-0 text-[#e4b865]"/><div><h3 className="font-semibold">Planet satellite integration needs credentials</h3><p className="mt-1 text-sm text-[#c8b999]">{data.integration.message} No NDVI, cloud coverage, or imagery has been generated.</p><code className="mt-3 block text-xs text-[#e6cc95]">PLANET_CLIENT_ID + PLANET_CLIENT_SECRET</code></div></div>}
      {data.latest && <div className="grid sm:grid-cols-2 xl:grid-cols-4 gap-4">{[
        [<Activity key="a"/>,"Latest NDVI",data.latest.ndvi.toFixed(3),ndviLabel(data.latest.ndvi)],
        [<CalendarDays key="d"/>,"Acquired",data.latest.acquisition_date,"Sentinel-2 L2A"],
        [<Cloud key="c"/>,"Cloud cover",data.latest.cloud_coverage_percent==null?"—":`${Number(data.latest.cloud_coverage_percent).toFixed(1)}%`,"Entire source scene"],
        [<ShieldCheck key="s"/>,"Valid area",data.latest.valid_area_percent==null?"—":`${data.latest.valid_area_percent}%`,`${data.spatial_resolution_m} m pixels`],
      ].map(([icon,label,value,note],i)=><article key={i} className="rounded-2xl border border-[#3e4940] bg-[#222724] p-5"><div className="flex items-center gap-2 text-[#9fc970]">{icon}<span className="text-xs uppercase tracking-wider text-[#a5ada7]">{label}</span></div><strong className="mt-3 block text-2xl">{value}</strong><small className="text-[#89938b]">{note}</small></article>)}</div>}
      <div className="grid lg:grid-cols-[1fr_360px] gap-5"><article className="rounded-2xl border border-[#3e4940] bg-[#222724] p-5"><div className="flex items-center justify-between"><div><h2 className="font-semibold">Vegetation health trend</h2><p className="mt-1 text-xs text-[#929c94]">Cloud-filtered 10-day NDVI observations</p></div><Layers3 className="text-[#9fc970]"/></div><TrendChart points={data.trend}/></article><article className="rounded-2xl border border-[#3e4940] bg-[#222724] p-5"><h2 className="font-semibold">Change check</h2>{data.comparison?<div className="mt-4"><strong className={`text-3xl ${data.comparison.change<0?"text-[#efad79]":"text-[#9fd27c]"}`}>{data.comparison.change>0?"+":""}{data.comparison.change.toFixed(3)}</strong><p className="mt-1 text-sm text-[#a6afa8]">since {data.comparison.previous_date}</p></div>:<p className="mt-4 text-sm text-[#939c95]">No historical comparison yet.</p>}<div className="mt-5 border-t border-[#3b443d] pt-4"><p className="text-xs uppercase tracking-wider text-[#a2aaa4]">Unusual decreases</p>{data.unusual_changes.length?data.unusual_changes.map((c,i)=><p key={i} className="mt-3 rounded-lg bg-[#3b2d23] p-3 text-sm text-[#efc19d]">{c.date}: {c.message}</p>):<p className="mt-2 text-sm text-[#9eaaa1]">No drop ≥ 0.15 found among valid observations.</p>}</div></article></div>
      <article className="rounded-2xl border border-[#3e4940] bg-[#202522] p-5"><h2 className="font-semibold">Data limits</h2><div className="mt-3 grid md:grid-cols-2 gap-2">{data.limitations.map((item,i)=><p key={i} className="flex gap-2 text-sm text-[#a8b1aa]"><span className="text-[#d1d978]">—</span>{item}</p>)}</div><p className="mt-4 text-xs text-[#748078]">Source: Sentinel-2 Level-2A through Planet Insights Platform · No simulated satellite readings · Scene cloud cover is not the same as cloud over the selected field.</p></article>
    </>}
  </section>;
}
