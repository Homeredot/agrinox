"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, CloudRain, Droplets, Gauge, History, LoaderCircle, LockKeyhole, Power, Radio, Settings2, ShieldAlert, Thermometer, Waves } from "lucide-react";
import { api, Farm } from "@/lib/api";

type Reading = { key: string; name: string; value: number; unit?: string; recorded_at: string; simulated: boolean; device_name: string } | null;
type Config = { mode: "manual" | "advisory" | "automatic"; safety_validated: boolean; remote_control_enabled: boolean; emergency_stop: boolean; max_pump_runtime_seconds: number; cooldown_minutes: number; min_tank_percent: number; max_reading_age_minutes: number; moisture_trigger_percent?: number };
type Command = { id: number; command: string; status: string; duration_seconds?: number; simulated: boolean; issued_at: string; execution_message?: string };
type IrrigationStatus = { decision: "recommended" | "not_needed" | "postpone" | "blocked" | "uncertain"; title: string; reasons: string[]; field: { id: number; name: string; farm_name: string; crop?: string; growth_stage?: string }; measurements: { soil_moisture: Reading; tank_level: Reading; temperature: Reading; recent_rainfall: Reading; flow_rate: Reading }; weather?: { rain_next_24h_mm: number; rain_probability_max: number; temperature_c?: number; provider: string }; weather_error?: string; threshold: { soil_moisture_percent: number; source: string }; config: Config; commands: Command[]; generated_at: string; uncertainty: string };
type Device = { id: number; field_id?: number; name: string; device_uid: string; device_credentials_configured: boolean; remote_control_enabled: boolean; sensors: { key: string; type: string }[] };

const decisionStyle = {
  recommended: { color: "#8bd46f", bg: "from-[#31552f] to-[#223a2b]", icon: Droplets, label: "Watering recommended" },
  not_needed: { color: "#82c6dd", bg: "from-[#294b56] to-[#23383c]", icon: CheckCircle2, label: "No watering needed" },
  postpone: { color: "#79bde4", bg: "from-[#29455b] to-[#232f3b]", icon: CloudRain, label: "Wait for rain" },
  blocked: { color: "#ef9a78", bg: "from-[#58332c] to-[#372724]", icon: ShieldAlert, label: "Pump blocked" },
  uncertain: { color: "#e2c16e", bg: "from-[#55472b] to-[#373125]", icon: AlertTriangle, label: "Check measurements" },
};
const fieldControl = "h-11 rounded-xl border border-[#454b46] bg-[#242825] px-3 text-white outline-none focus:border-[#72a75e]";

export default function IrrigationDashboard({ farms, token }: { farms: Farm[]; token: string }) {
  const fields = useMemo(() => farms.flatMap((farm) => farm.fields.map((field) => ({ farm, field }))), [farms]);
  const [fieldId, setFieldId] = useState<number | null>(fields[0]?.field.id ?? null);
  const [status, setStatus] = useState<IrrigationStatus | null>(null);
  const [devices, setDevices] = useState<Device[]>([]);
  const [config, setConfig] = useState<Config | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [deviceKey, setDeviceKey] = useState<{ uid: string; key: string } | null>(null);
  const [runtimeSeconds, setRuntimeSeconds] = useState(120);

  async function load(id = fieldId) {
    if (!id) return;
    setBusy(true); setError("");
    try {
      const [nextStatus, nextDevices] = await Promise.all([api<IrrigationStatus>(`/irrigation/status?field_id=${id}`, {}, token), api<Device[]>("/iot/devices", {}, token)]);
      setStatus(nextStatus); setConfig(nextStatus.config); setDevices(nextDevices.filter((item) => item.field_id === id));
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : "Could not load irrigation status"); }
    finally { setBusy(false); }
  }
  useEffect(() => { void load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function send(command: "start" | "stop" | "emergency_stop") {
    if (!fieldId) return;
    if (command === "emergency_stop" && !confirm("Emergency stop will block all pump starts until you reset it. Continue?")) return;
    if (command === "start" && status?.decision !== "recommended" && !confirm(`The current advice is “${status?.title}”. Start the pump manually anyway? This override will be recorded.`)) return;
    setBusy(true); setError("");
    try {
      await api("/irrigation/commands", { method: "POST", body: JSON.stringify({ field_id: fieldId, command, duration_seconds: command === "start" ? Math.min(runtimeSeconds, config?.max_pump_runtime_seconds || runtimeSeconds) : null, simulated: false }) }, token);
      await load(fieldId);
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : "Command was not accepted"); setBusy(false); }
  }

  async function saveConfig() {
    if (!fieldId || !config) return;
    setBusy(true); setError("");
    try {
      await api(`/irrigation/config?field_id=${fieldId}`, { method: "PUT", body: JSON.stringify(config) }, token);
      await load(fieldId);
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : "Could not save safety settings"); setBusy(false); }
  }

  async function enableDevice(device: Device) {
    try { await api(`/iot/devices/${device.id}/remote-control?enabled=true`, { method: "PATCH" }, token); await load(fieldId); }
    catch (requestError) { setError(requestError instanceof Error ? requestError.message : "Could not enable device control"); }
  }

  async function provision(device: Device) {
    try { const result = await api<{ device_uid: string; device_key: string }>(`/iot/devices/${device.id}/credentials`, { method: "POST" }, token); setDeviceKey({ uid: result.device_uid, key: result.device_key }); await load(fieldId); }
    catch (requestError) { setError(requestError instanceof Error ? requestError.message : "Could not create device key"); }
  }

  const style = decisionStyle[status?.decision || "uncertain"];
  const DecisionIcon = style.icon;
  const canStart = Boolean(status && config && (status.decision === "recommended" || (config.mode !== "automatic" && !["blocked", "uncertain"].includes(status.decision))));
  return <div>
    <div className="flex flex-wrap items-end justify-between gap-4"><div><h1 className="text-2xl font-semibold sm:text-4xl">Should I irrigate now?</h1><p className="mobile-secondary mt-2 max-w-2xl text-[#aeb6af]">See a clear decision based on field sensors, the water source, and the weather forecast.</p></div>{fields.length > 0 && <select className={`${fieldControl} w-full sm:w-auto sm:min-w-64`} value={fieldId ?? ""} onChange={(event) => { const id = Number(event.target.value); setFieldId(id); void load(id); }}>{fields.map(({ farm, field }) => <option key={field.id} value={field.id}>{farm.name} · {field.name}</option>)}</select>}</div>
    {error && <div role="alert" className="mt-5 rounded-xl border border-[#743d38] bg-[#402522] p-4 text-[#ffc0b5]">{error}</div>}
    {!fields.length ? <div className="mt-8 rounded-2xl border border-[#665834] bg-[#342f22] p-6">Add a farm field before configuring irrigation.</div> : busy && !status ? <div className="mt-10 flex items-center gap-3 text-[#aeb6af]"><LoaderCircle className="animate-spin" />Checking field data…</div> : status && <>
      <section className="theme-on-dark relative isolate mt-7 overflow-hidden rounded-3xl border border-white/15 bg-[#26372a] p-6 shadow-2xl shadow-black/20 sm:p-8">
        <div aria-hidden="true" className="absolute inset-0 -z-30 bg-cover bg-[center_46%]" style={{ backgroundImage: "url('/irrigation-status-hero.jpg')" }}/>
        <div aria-hidden="true" className={`absolute inset-0 -z-20 bg-gradient-to-br ${style.bg} opacity-80`}/>
        <div aria-hidden="true" className="absolute inset-0 -z-10 bg-[linear-gradient(90deg,rgba(16,24,18,.78)_0%,rgba(18,29,20,.55)_58%,rgba(14,24,17,.38)_100%)]"/>
        <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between"><div className="flex items-start gap-4"><span className="grid h-14 w-14 shrink-0 place-items-center rounded-2xl border border-white/10 bg-black/30 shadow-lg backdrop-blur-sm" style={{ color: style.color }}><DecisionIcon size={29} /></span><div><p className="text-xs font-bold uppercase tracking-[.18em] drop-shadow" style={{ color: style.color }}>{style.label}</p><h2 className="mt-2 text-2xl font-semibold drop-shadow-md sm:text-3xl">{status.title}</h2><p className="mt-2 text-sm text-white/75 drop-shadow">{status.field.crop || "Crop not recorded"}{status.field.growth_stage ? ` · ${status.field.growth_stage}` : " · Growth stage not recorded"}</p></div></div><button onClick={() => void load()} disabled={busy} className="h-11 rounded-full border border-white/25 bg-black/25 px-5 text-sm font-semibold shadow-lg backdrop-blur-sm hover:bg-black/40 disabled:opacity-50">{busy ? "Refreshing…" : "Refresh readings"}</button></div>
        <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-5"><SensorCard icon={Droplets} label="Soil moisture" reading={status.measurements.soil_moisture} /><SensorCard icon={Gauge} label="Tank level" reading={status.measurements.tank_level} /><SensorCard icon={Thermometer} label="Temperature" reading={status.measurements.temperature} fallback={status.weather?.temperature_c} fallbackUnit="°C forecast" /><SensorCard icon={CloudRain} label="Rain next 24h" reading={null} fallback={status.weather?.rain_next_24h_mm} fallbackUnit="mm forecast" /><SensorCard icon={Waves} label="Water flow" reading={status.measurements.flow_rate} /></div>
      </section>

      <div className="mt-5 grid gap-5 xl:grid-cols-[1.15fr_.85fr]">
        <section className="rounded-2xl border border-[#414741] bg-[#242825] p-5"><h3 className="font-semibold">Why?</h3><div className="mt-4 space-y-2">{status.reasons.map((reason) => <div key={reason} className="flex gap-3 rounded-xl bg-[#2b302c] p-3.5 text-sm leading-6 text-[#c2c9c1]"><span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: style.color }} />{reason}</div>)}</div><p className="mt-4 text-xs leading-5 text-[#8f988e]">{status.uncertainty}</p></section>
        <section className="rounded-2xl border border-[#414741] bg-[#242825] p-5"><div className="flex items-center justify-between"><div><h3 className="font-semibold">Pump control</h3><p className="mt-1 text-xs text-[#929a92]">Mode: <span className="capitalize text-[#d8ded6]">{status.config.mode}</span></p></div><Power className={status.config.emergency_stop ? "text-[#e67966]" : "text-[#79bd83]"} /></div><label className="mt-4 block text-xs text-[#aab2aa]">Run time (seconds)<input type="number" min={10} max={config?.max_pump_runtime_seconds || 7200} value={runtimeSeconds} onChange={(event) => setRuntimeSeconds(Math.max(10, Number(event.target.value) || 10))} className="mt-1.5 w-full rounded-xl border border-[#4b514c] bg-[#222624] p-3 text-white" /></label><div className="mt-3 grid grid-cols-2 gap-2"><button onClick={() => void send("start")} disabled={busy || !canStart} className="h-12 rounded-xl bg-[#398c5e] font-semibold disabled:cursor-not-allowed disabled:opacity-35">Start for {Math.min(runtimeSeconds, config?.max_pump_runtime_seconds || runtimeSeconds)}s</button><button onClick={() => void send("stop")} disabled={busy} className="h-12 rounded-xl border border-[#59615a] font-semibold hover:bg-[#303631]">Stop pump</button></div><button onClick={() => void send("emergency_stop")} disabled={busy} className="mt-3 h-11 w-full rounded-xl bg-[#71362f] font-semibold text-[#ffd0c7] hover:bg-[#834138]"><ShieldAlert className="mr-2 inline" size={17} />Emergency stop</button>{!canStart && <p className="mt-3 text-xs text-[#c5a76e]">Pump start is blocked until required readings and safety checks are valid.</p>}{canStart && status.decision !== "recommended" && <p className="mt-3 text-xs text-[#c5a76e]">Manual override is available, but you must confirm it before the command is recorded.</p>}</section>
      </div>

      <details className="mt-5 rounded-2xl border border-[#414741] bg-[#242825] p-5"><summary className="cursor-pointer list-none font-semibold"><Settings2 className="mr-2 inline text-[#9fc77c]" size={18} />Safety settings and device setup</summary>{config && <div className="mt-5 grid gap-5 lg:grid-cols-2"><div><p className="text-sm font-semibold">Irrigation mode</p><div className="mt-3 grid grid-cols-3 gap-2">{(["manual", "advisory", "automatic"] as const).map((mode) => <button key={mode} type="button" onClick={() => setConfig({ ...config, mode })} className={`rounded-xl border px-3 py-3 text-sm capitalize ${config.mode === mode ? "border-[#77a95e] bg-[#35482e]" : "border-[#454b46]"}`}>{mode}</button>)}</div><label className="mt-4 flex items-center gap-3 rounded-xl bg-[#2b302c] p-3 text-sm"><input type="checkbox" checked={config.remote_control_enabled} onChange={(event) => setConfig({ ...config, remote_control_enabled: event.target.checked })} />Allow remote commands for this field</label><label className="mt-2 flex items-center gap-3 rounded-xl bg-[#2b302c] p-3 text-sm"><input type="checkbox" checked={config.safety_validated} onChange={(event) => setConfig({ ...config, safety_validated: event.target.checked })} />Hardware and pump safety have been checked</label><label className="mt-2 flex items-center gap-3 rounded-xl bg-[#2b302c] p-3 text-sm"><input type="checkbox" checked={!config.emergency_stop} onChange={(event) => setConfig({ ...config, emergency_stop: !event.target.checked })} />Emergency stop reset</label><div className="mt-4 grid grid-cols-2 gap-3"><NumberSetting label="Max runtime (sec)" value={config.max_pump_runtime_seconds} onChange={(value) => setConfig({ ...config, max_pump_runtime_seconds: value })} /><NumberSetting label="Cooldown (min)" value={config.cooldown_minutes} onChange={(value) => setConfig({ ...config, cooldown_minutes: value })} /><NumberSetting label="Minimum tank %" value={config.min_tank_percent} onChange={(value) => setConfig({ ...config, min_tank_percent: value })} /><NumberSetting label="Max reading age (min)" value={config.max_reading_age_minutes} onChange={(value) => setConfig({ ...config, max_reading_age_minutes: value })} /></div><button onClick={() => void saveConfig()} disabled={busy || (config.mode === "automatic" && !config.safety_validated)} className="mt-4 rounded-xl bg-[#587e45] px-5 py-3 font-semibold disabled:opacity-40">Save safety settings</button></div>
        <div><p className="text-sm font-semibold">Field devices</p><div className="mt-3 space-y-3">{devices.length ? devices.map((device) => <div key={device.id} className="rounded-xl border border-[#454b46] bg-[#2b302c] p-4"><div className="flex items-start justify-between gap-3"><div><strong>{device.name}</strong><p className="mt-1 text-xs text-[#939b93]">{device.sensors.length} sensors · {device.remote_control_enabled ? "remote control enabled" : "remote control disabled"}</p></div><Radio size={17} className={device.remote_control_enabled ? "text-[#7dca85]" : "text-[#8b928c]"} /></div><div className="mt-3 flex flex-wrap gap-2">{!device.device_credentials_configured && <button onClick={() => void provision(device)} className="rounded-lg border border-[#59615a] px-3 py-2 text-xs"><LockKeyhole className="mr-1.5 inline" size={14} />Create device key</button>}{!device.remote_control_enabled && <button onClick={() => void enableDevice(device)} className="rounded-lg border border-[#59615a] px-3 py-2 text-xs">Enable device control</button>}</div></div>) : <p className="rounded-xl bg-[#2b302c] p-4 text-sm text-[#aab2aa]">No device is assigned to this field. Register one in Device Management.</p>}</div>{deviceKey && <div className="mt-4 rounded-xl border border-[#7d6337] bg-[#3b3222] p-4"><p className="text-xs font-bold uppercase tracking-wider text-[#e4be70]">Shown once — copy to ESP32</p><p className="mt-2 break-all text-xs">Device ID: {deviceKey.uid}</p><p className="mt-1 break-all text-xs">Device key: {deviceKey.key}</p></div>}</div>
      </div>}</details>

      <section className="mt-5 rounded-2xl border border-[#414741] bg-[#242825] p-5"><div className="flex items-center gap-2"><History size={18} className="text-[#9fc77c]" /><h3 className="font-semibold">Command history</h3></div><div className="mt-4 space-y-2">{status.commands.length ? status.commands.map((command) => <div key={command.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-[#2b302c] px-4 py-3 text-sm"><span className="capitalize"><strong>{command.command.replace("_", " ")}</strong>{command.simulated && <span className="ml-2 rounded bg-[#725b2e] px-2 py-0.5 text-[10px] font-bold">SIMULATED</span>}</span><span className="text-xs text-[#969e96]">{command.status} · {new Date(command.issued_at).toLocaleString()}</span></div>) : <p className="text-sm text-[#8f978f]">No pump commands have been issued.</p>}</div></section>
    </>}
  </div>;
}

function SensorCard({ icon: Icon, label, reading, fallback, fallbackUnit }: { icon: typeof Droplets; label: string; reading: Reading; fallback?: number; fallbackUnit?: string }) { const value = reading?.value ?? fallback; return <div className="rounded-2xl border border-white/15 bg-black/35 p-4 shadow-lg backdrop-blur-md"><div className="flex items-center gap-2 text-xs text-white/70"><Icon size={15} />{label}</div><div className="mt-3 text-2xl font-semibold drop-shadow">{value == null ? "—" : Number(value).toFixed(1)} <span className="text-xs font-normal text-white/65">{reading?.unit || fallbackUnit}</span></div><p className="mt-1 text-[10px] uppercase tracking-wider text-white/55">{reading?.simulated ? "SIMULATED" : reading ? `From ${reading.device_name}` : fallback != null ? "Weather model" : "Missing"}</p></div>; }
function NumberSetting({ label, value, onChange }: { label: string; value: number; onChange: (value: number) => void }) { return <label className="text-xs text-[#aab2aa]">{label}<input type="number" value={value} onChange={(event) => onChange(Number(event.target.value))} className="mt-1.5 w-full rounded-lg border border-[#4b514c] bg-[#222624] p-2.5 text-white" /></label>; }
