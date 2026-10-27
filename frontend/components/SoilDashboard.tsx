"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  Beaker,
  CheckCircle2,
  ChevronRight,
  CloudRain,
  FlaskConical,
  Gauge,
  Leaf,
  LoaderCircle,
  Plus,
  RefreshCw,
  ShieldAlert,
  Sprout,
  Thermometer,
  Waves,
  X,
} from "lucide-react";

import { api, type Farm } from "@/lib/api";

type Point = {
  id: string;
  value: number;
  unit: string;
  source: "device" | "manual" | "laboratory";
  calibration_status: string;
  reliability: string;
  status: string;
  timestamp: string;
  note?: string | null;
  age_hours: number;
  freshness: "current" | "stale";
  unit_compatible: boolean;
  quality_status: "verified" | "reliable" | "needs_review" | "stale" | "unusable";
};
type Measurement = {
  type: string;
  label: string;
  latest: Point | null;
  trend: Point[];
  trend_summary?: {
    direction: "rising" | "falling" | "steady";
    change: number;
    unit: string;
    from_timestamp: string;
    to_timestamp: string;
  } | null;
};
type Advisory = {
  priority: string;
  title: string;
  message: string;
  evidence: string;
  uncertainty: string;
  action: string;
};
type SoilData = {
  field: { id: number; name: string; farm_name: string };
  context: { crop_type?: string | null; growth_stage?: string | null };
  measurements: Measurement[];
  summary: {
    available: number;
    missing: number;
    reliable: number;
    current: number;
    needs_review: number;
    device_count: number;
  };
  data_quality: {
    score: number;
    status: "high" | "medium" | "low";
    checks: { status: "good" | "warning"; label: string }[];
  };
  weather: {
    available: boolean;
    usable_for_advice?: boolean;
    rain_next_24h_mm?: number;
    rain_probability?: number;
    age_hours?: number;
    note: string;
  };
  advisories: Advisory[];
  safety_note: string;
};

const TYPES = [
  { key: "nitrogen", short: "N", name: "Nitrogen", unit: "mg/kg", icon: Leaf },
  {
    key: "phosphorus",
    short: "P",
    name: "Phosphorus",
    unit: "mg/kg",
    icon: Sprout,
  },
  {
    key: "potassium",
    short: "K",
    name: "Potassium",
    unit: "mg/kg",
    icon: Activity,
  },
  {
    key: "moisture",
    short: "%",
    name: "Soil moisture",
    unit: "%",
    icon: Waves,
  },
  {
    key: "temperature",
    short: "°C",
    name: "Soil temperature",
    unit: "°C",
    icon: Thermometer,
  },
  { key: "ph", short: "pH", name: "Soil pH", unit: "pH", icon: FlaskConical },
] as const;

function formatAge(hours: number) {
  if (hours < 1) return "Less than 1 hour old";
  if (hours < 48) return `${Math.round(hours)} hours old`;
  return `${Math.round(hours / 24)} days old`;
}

function TrendChart({ measurement }: { measurement: Measurement }) {
  const points = measurement.trend;
  if (points.length < 2) {
    return (
      <div className="grid h-52 place-items-center rounded-xl border border-dashed border-[#465047] text-center text-sm text-[#858c86]">
        <div>
          <Activity className="mx-auto mb-2" />
          <p>Add at least two readings to show a trend.</p>
        </div>
      </div>
    );
  }
  const values = points.map((point) => point.value);
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  const span = maximum - minimum || 1;
  const coordinates = points
    .map((point, index) => {
      const x = 8 + (index / (points.length - 1)) * 84;
      const y = 82 - ((point.value - minimum) / span) * 64;
      return `${x},${y}`;
    })
    .join(" ");
  return (
    <div className="rounded-xl border border-[#3d493f] bg-[#202722] p-4">
      <div className="flex items-center justify-between text-xs text-[#929993]">
        <span>{minimum.toLocaleString()}</span>
        <span>{points.length} readings</span>
        <span>{maximum.toLocaleString()}</span>
      </div>
      <svg
        viewBox="0 0 100 100"
        className="mt-2 h-40 w-full"
        role="img"
        aria-label={`${measurement.label} trend`}
      >
        <defs>
          <linearGradient id="soilTrend" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#70cb7d" stopOpacity=".35" />
            <stop offset="1" stopColor="#70cb7d" stopOpacity="0" />
          </linearGradient>
        </defs>
        <line
          x1="8"
          y1="82"
          x2="92"
          y2="82"
          stroke="#465047"
          strokeWidth=".7"
        />
        <polyline
          points={`8,82 ${coordinates} 92,82`}
          fill="url(#soilTrend)"
          stroke="none"
        />
        <polyline
          points={coordinates}
          fill="none"
          stroke="#76cf82"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        {points.map((point, index) => {
          const [x, y] = coordinates.split(" ")[index].split(",");
          return (
            <circle
              key={point.id}
              cx={x}
              cy={y}
              r="2.4"
              fill="#d6f3da"
              stroke="#438e53"
            />
          );
        })}
      </svg>
      <div className="flex justify-between text-[11px] text-[#7f8680]">
        <span>{new Date(points[0].timestamp).toLocaleDateString()}</span>
        <span>{new Date(points.at(-1)!.timestamp).toLocaleDateString()}</span>
      </div>
    </div>
  );
}

function PriorityAdvice({ advisories }: { advisories: Advisory[] }) {
  return (
    <section className="theme-on-dark mt-7 rounded-2xl border border-[#6c5732] bg-gradient-to-br from-[#352d1f] to-[#292820] p-5 sm:p-6">
      <div className="flex items-start gap-3">
        <span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-[#8b5e23] text-[#fff1cf]">
          <ShieldAlert size={24} />
        </span>
        <div>
          <p className="text-xs font-bold uppercase tracking-[.18em] text-[#e1bd70]">
            Priority advice
          </p>
          <h2 className="mt-1 text-2xl font-semibold">
            Advice from your readings
          </h2>
        </div>
      </div>
      <div className="mt-5 space-y-2">
        {advisories.map((advice, index) => (
          <article
            key={`${advice.title}-${index}`}
            className="rounded-xl border border-[#625238] bg-[#27251f]/80 p-4"
          >
            <div className="flex items-start gap-3">
              <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-[#8b5e23] text-sm font-bold text-white">
                {index + 1}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h3 className="font-semibold text-[#f0dfbb]">
                    {advice.title}
                  </h3>
                  <span
                    className={`rounded-full px-2.5 py-1 text-[10px] font-bold uppercase ${advice.priority === "high" ? "bg-[#663d2d] text-[#ffc5aa]" : "bg-[#33472f] text-[#a9d5a5]"}`}
                  >
                    {advice.priority}
                  </span>
                </div>
                <p className="mt-2 text-sm text-[#ded9ce]">{advice.message}</p>
                <p className="mt-2 flex items-center gap-2 font-semibold text-[#d2df91]">
                  <ChevronRight size={16} /> {advice.action}
                </p>
                <details className="mt-2 text-xs text-[#aaa79f]">
                  <summary className="cursor-pointer font-semibold text-[#c9b98f] hover:text-[#e1d3ad]">
                    Why this advice
                  </summary>
                  <div className="mt-2 grid gap-2 border-l border-[#625238] pl-3 sm:grid-cols-2">
                    <p>
                      <strong className="text-[#d7bd83]">Reading:</strong>{" "}
                      {advice.evidence}
                    </p>
                    <p>
                      <strong className="text-[#d7bd83]">Caution:</strong>{" "}
                      {advice.uncertainty}
                    </p>
                  </div>
                </details>
              </div>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

export default function SoilDashboard({
  farms,
  token,
}: {
  farms: Farm[];
  token: string;
}) {
  const fields = useMemo(
    () =>
      farms.flatMap((farm) =>
        farm.fields.map((field) => ({ ...field, farmName: farm.name })),
      ),
    [farms],
  );
  const [fieldId, setFieldId] = useState<number | null>(fields[0]?.id ?? null);
  const [data, setData] = useState<SoilData | null>(null);
  const [selectedType, setSelectedType] = useState("moisture");
  const [entryOpen, setEntryOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function load(nextFieldId = fieldId) {
    if (!nextFieldId) {
      setData(null);
      return;
    }
    setLoading(true);
    setError("");
    try {
      setData(await api<SoilData>(`/soil/fields/${nextFieldId}`, {}, token));
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not load soil data",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load(fieldId);
  }, [fieldId]); // eslint-disable-line react-hooks/exhaustive-deps

  async function saveContext(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!fieldId) return;
    const form = Object.fromEntries(new FormData(event.currentTarget));
    setSaving(true);
    try {
      await api(
        `/soil/fields/${fieldId}/context`,
        {
          method: "PUT",
          body: JSON.stringify({
            crop_type: form.crop_type || null,
            growth_stage: form.growth_stage || null,
          }),
        },
        token,
      );
      await load();
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not save crop profile",
      );
    } finally {
      setSaving(false);
    }
  }

  async function saveReadings(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!fieldId) return;
    const form = new FormData(event.currentTarget);
    const source = String(form.get("source"));
    const measurements = TYPES.flatMap((item) => {
      const raw = String(form.get(item.key) || "").trim();
      if (!raw) return [];
      return [
        {
          measurement_type: item.key,
          value: Number(raw),
          unit: String(form.get(`${item.key}_unit`) || item.unit),
          calibration_status:
            source === "laboratory"
              ? "not_applicable"
              : String(form.get("calibration_status")),
          reliability:
            source === "laboratory"
              ? "reliable"
              : String(form.get("reliability")),
        },
      ];
    });
    if (!measurements.length) {
      setError("Enter at least one soil measurement.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await api(
        `/soil/fields/${fieldId}/readings`,
        {
          method: "POST",
          body: JSON.stringify({
            source,
            measured_at: form.get("measured_at")
              ? new Date(String(form.get("measured_at"))).toISOString()
              : null,
            note: form.get("note") || null,
            measurements,
          }),
        },
        token,
      );
      setEntryOpen(false);
      await load();
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not save readings",
      );
    } finally {
      setSaving(false);
    }
  }

  const selectedMeasurement =
    data?.measurements.find((item) => item.type === selectedType) ??
    data?.measurements[0];

  if (!fields.length)
    return (
      <div className="grid min-h-[65vh] place-items-center text-center">
        <div>
          <Sprout className="mx-auto text-[#75c77e]" size={44} />
          <h1 className="mt-4 text-3xl font-semibold">Create a field first</h1>
          <p className="mt-2 max-w-md text-[#9ea49f]">
            Soil readings and advice belong to a field. Open My Farm and add a
            field before using Soil Quality.
          </p>
        </div>
      </div>
    );

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold sm:text-4xl">
            Soil health and advice
          </h1>
          <p className="mobile-secondary mt-2 max-w-2xl text-[#aeb3af]">
            Check the soil. See the next action.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => void load()}
            className="grid h-11 w-11 place-items-center rounded-full border border-[#4b504c] hover:bg-[#292c2a]"
            aria-label="Refresh soil dashboard"
          >
            <RefreshCw size={18} className={loading ? "animate-spin" : ""} />
          </button>
          <button
            onClick={() => setEntryOpen(true)}
            className="flex h-11 items-center gap-2 rounded-full bg-[#647c31] px-5 font-semibold hover:bg-[#748f39]"
          >
            <Plus size={18} /><span className="sm:hidden">Add</span><span className="hidden sm:inline">Add measurements</span>
          </button>
        </div>
      </div>

      {error && (
        <div
          role="alert"
          className="mt-5 flex items-start justify-between rounded-xl border border-[#6e3333] bg-[#3b2020] p-4 text-[#ffb9b9]"
        >
          {error}
          <button onClick={() => setError("")}>
            <X size={18} />
          </button>
        </div>
      )}

      <section className="theme-surface-panel mt-7 grid gap-4 rounded-2xl border border-[#3c4437] bg-gradient-to-r from-[#252b21] to-[#202522] p-5 lg:grid-cols-[1fr_1.35fr]">
        <label className="text-sm font-semibold">
          Field to monitor
          <select
            value={fieldId ?? ""}
            onChange={(event) => setFieldId(Number(event.target.value))}
            className="mt-2 w-full rounded-xl border border-[#4a5145] bg-[#222622] p-3.5"
          >
            {fields.map((field) => (
              <option key={field.id} value={field.id}>
                {field.farmName} — {field.name}
              </option>
            ))}
          </select>
        </label>
        <form
          key={`${fieldId}-${data?.context.crop_type}-${data?.context.growth_stage}`}
          onSubmit={saveContext}
          className="grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end"
        >
          <label className="text-sm font-semibold">
            Crop
            <input
              name="crop_type"
              list="soil-crop-options"
              defaultValue={data?.context.crop_type || ""}
              placeholder="Search or enter crop"
              className="mt-2 w-full rounded-xl border border-[#4a5145] bg-[#222622] p-3.5"
            />
            <datalist id="soil-crop-options">
              <option value="Rice" />
              <option value="Irish potatoes" />
              <option value="Maize" />
              <option value="Beans" />
              <option value="Cassava" />
              <option value="Wheat" />
              <option value="Vegetables" />
            </datalist>
          </label>
          <label className="text-sm font-semibold">
            Growth stage
            <select
              name="growth_stage"
              defaultValue={data?.context.growth_stage || ""}
              className="mt-2 w-full rounded-xl border border-[#4a5145] bg-[#222622] p-3.5"
            >
              <option value="">Select stage</option>
              <option>Land preparation</option>
              <option>Germination</option>
              <option>Seedling</option>
              <option>Vegetative</option>
              <option>Flowering</option>
              <option>Fruiting / grain filling</option>
              <option>Maturity</option>
            </select>
          </label>
          <button
            disabled={saving}
            className="h-12 rounded-xl border border-[#667254] px-4 font-semibold hover:bg-[#31382b] disabled:opacity-50"
          >
            Save profile
          </button>
        </form>
      </section>

      {loading && !data ? (
        <div className="grid h-80 place-items-center">
          <LoaderCircle className="animate-spin text-[#9bbd58]" size={38} />
        </div>
      ) : (
        data && (
          <>
            <section className="mt-6 grid grid-cols-1 gap-3 min-[390px]:grid-cols-2 xl:grid-cols-4">
              {[
                {
                  label: "Available",
                  value: data.summary.available,
                  icon: CheckCircle2,
                  color: "text-[#7ed083]",
                },
                {
                  label: "Reliable",
                  value: data.summary.reliable,
                  icon: Gauge,
                  color: "text-[#87a8ff]",
                },
                {
                  label: "Current",
                  value: data.summary.current,
                  icon: Activity,
                  color: "text-[#7ed083]",
                },
                {
                  label: "Review",
                  value: data.summary.needs_review,
                  icon: AlertTriangle,
                  color: "text-[#e1b761]",
                },
              ].map((stat) => (
                <article
                  key={stat.label}
                  className="rounded-xl border border-[#3b3e3b] bg-[#232523] p-4"
                >
                  <div className="flex items-center justify-between">
                    <p className="text-xs uppercase tracking-wider text-[#929793]">
                      {stat.label}
                    </p>
                    <stat.icon size={19} className={stat.color} />
                  </div>
                  <strong className="mt-3 block text-3xl">{stat.value}</strong>
                </article>
              ))}
            </section>

            <section className="mt-7">
              <div className="flex flex-wrap items-end justify-between gap-3">
                <div>
                  <h2 className="text-xl font-semibold">Soil readings</h2>
                </div>
                {data.weather.usable_for_advice ? (
                  <p className="flex items-center gap-2 rounded-full bg-[#26343a] px-3 py-2 text-xs text-[#a7cedb]" title={data.weather.note}>
                    <CloudRain size={15} /> Next 24h:{" "}
                    {data.weather.rain_next_24h_mm} mm ·{" "}
                    {data.weather.rain_probability}% chance
                  </p>
                ) : (
                  <p className="flex items-center gap-2 text-xs text-[#c5a568]" title={data.weather.note}>
                    <AlertTriangle size={14} /> Weather needs refresh
                  </p>
                )}
              </div>
              <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {data.measurements.map((measurement) => {
                  const config = TYPES.find(
                    (item) => item.key === measurement.type,
                  )!;
                  const Icon = config.icon;
                  const latest = measurement.latest;
                  return (
                    <button
                      key={measurement.type}
                      onClick={() => setSelectedType(measurement.type)}
                      className={`rounded-xl border p-4 text-left transition ${selectedType === measurement.type ? "border-[#71854a] bg-[#2b3226]" : "border-[#3e423e] bg-[#232523] hover:border-[#535a53]"}`}
                    >
                      <div className="flex items-start justify-between">
                        <span className="grid h-10 w-10 place-items-center rounded-xl bg-[#303b2e] text-[#9bc56d]">
                          <Icon size={20} />
                        </span>
                        <span
                          className={`rounded-full px-2 py-1 text-[10px] font-bold uppercase ${latest ? (latest.quality_status === "verified" || latest.quality_status === "reliable" ? "bg-[#294832] text-[#8bd398]" : "bg-[#4a4029] text-[#dfc37c]") : "bg-[#3d3d3d] text-[#999]"}`}
                        >
                          {latest
                            ? latest.quality_status.replace("_", " ")
                            : "missing"}
                        </span>
                      </div>
                      <p className="mt-3 text-sm text-[#afb4b0]">
                        {measurement.label}
                      </p>
                      <p className="mt-1">
                        <strong className="text-3xl">
                          {latest?.value ?? "—"}
                        </strong>{" "}
                        <span className="text-sm text-[#969b97]">
                          {latest?.unit || config.unit}
                        </span>
                      </p>
                      <div className="mt-3 border-t border-[#3b403b] pt-3 text-xs text-[#858b86]">
                        {latest ? (
                          <div className="space-y-2">
                            <div className="flex flex-wrap gap-1.5">
                              <span className="rounded-full bg-[#303630] px-2 py-1">
                                {latest.source}
                              </span>
                              <span className="rounded-full bg-[#303630] px-2 py-1">
                                {latest.status}
                              </span>
                              <span className="rounded-full bg-[#303630] px-2 py-1">
                                {latest.calibration_status.replace("_", " ")}
                              </span>
                            </div>
                            <p>{new Date(latest.timestamp).toLocaleString()}</p>
                            <p>{formatAge(latest.age_hours)}</p>
                          </div>
                        ) : (
                          <p className="font-semibold text-[#c4ad72]">
                            Add reading
                          </p>
                        )}
                      </div>
                    </button>
                  );
                })}
              </div>
            </section>

            {selectedMeasurement && (
              <section className="mt-7 grid gap-5 lg:grid-cols-[1.4fr_.6fr]">
                <div>
                  <h2 className="text-xl font-semibold">
                    {selectedMeasurement.label} trend
                  </h2>
                  <p className="mb-3 mt-1 text-sm text-[#969b97]">
                    {selectedMeasurement.trend_summary
                      ? `${selectedMeasurement.trend_summary.direction} · ${selectedMeasurement.trend_summary.change > 0 ? "+" : ""}${selectedMeasurement.trend_summary.change} ${selectedMeasurement.trend_summary.unit} since the previous reading`
                      : "Add comparable readings with the same unit to calculate change"}
                  </p>
                  <TrendChart measurement={selectedMeasurement} />
                </div>
                <aside className="rounded-2xl border border-[#405348] bg-[#222c27] p-5">
                  <div className="flex items-center justify-between">
                    <Gauge className="text-[#8fca9c]" />
                    <strong className="text-3xl text-[#d9f0de]">{data.data_quality.score}%</strong>
                  </div>
                  <h3 className="mt-3 font-semibold text-[#d9eadc]">
                    Decision readiness · {data.data_quality.status}
                  </h3>
                  <ul className="mt-3 space-y-3 text-sm text-[#afbeb3]">
                    {data.data_quality.checks.map((check) => (
                      <li key={check.label} className="flex gap-2">
                        {check.status === "good" ? (
                          <CheckCircle2 size={16} className="mt-0.5 shrink-0 text-[#79c58a]" />
                        ) : (
                          <AlertTriangle size={16} className="mt-0.5 shrink-0 text-[#d4aa5f]" />
                        )}
                        {check.label}
                      </li>
                    ))}
                  </ul>
                </aside>
              </section>
            )}

            <PriorityAdvice advisories={data.advisories} />

            <div className="mt-7 flex items-center gap-3 rounded-xl border border-[#455044] bg-[#242a25] p-4 text-sm text-[#aeb6af]">
              <ShieldAlert size={19} className="shrink-0 text-[#d0ae63]" />
              <strong className="text-[#cbd8cc]">
                Confirm major soil decisions with a laboratory or agronomist.
              </strong>
            </div>
          </>
        )
      )}

      {entryOpen && (
        <div className="fixed inset-0 z-[1200] flex items-end overflow-y-auto bg-black/75 p-0 backdrop-blur-sm sm:block sm:p-4">
          <form
            onSubmit={saveReadings}
            className="mx-auto max-h-[calc(100dvh-0.5rem)] w-full max-w-3xl overflow-y-auto rounded-t-3xl border border-[#444844] bg-[#202220] p-5 shadow-2xl sm:my-6 sm:max-h-none sm:rounded-2xl sm:p-6"
          >
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs font-bold uppercase tracking-widest text-[#b8cf65]">
                  Soil measurement
                </p>
                <h2 className="mt-1 text-2xl font-semibold">
                  Add field or laboratory results
                </h2>
                <p className="mt-1 text-sm text-[#969b97]">
                  Enter only what was measured.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setEntryOpen(false)}
                className="grid h-9 w-9 place-items-center rounded-full bg-[#303330]"
              >
                <X size={18} />
              </button>
            </div>
            <div className="mt-5 grid gap-4 sm:grid-cols-2">
              <label className="font-semibold">
                Source
                <select
                  name="source"
                  defaultValue="manual"
                  className="mt-2 w-full rounded-lg border border-[#494d4a] bg-[#262927] p-3.5"
                >
                  <option value="manual">Manual / field measurement</option>
                  <option value="laboratory">Laboratory result</option>
                </select>
              </label>
              <label className="font-semibold">
                Reading time
                <input
                  name="measured_at"
                  type="datetime-local"
                  className="mt-2 w-full rounded-lg border border-[#494d4a] bg-[#262927] p-3.5"
                />
              </label>
            </div>
            <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {TYPES.map((item) => (
                <div
                  key={item.key}
                  className="rounded-xl border border-[#414541] bg-[#292c2a] p-4"
                >
                  <label className="text-sm font-semibold">
                    {item.name}
                    <div className="mt-2 flex">
                      <input
                        name={item.key}
                        type="number"
                        step="any"
                        min={
                          item.key === "ph" || item.key === "moisture"
                            ? 0
                            : undefined
                        }
                        max={
                          item.key === "ph"
                            ? 14
                            : item.key === "moisture"
                              ? 100
                              : undefined
                        }
                        placeholder="Not measured"
                        className="min-w-0 flex-1 rounded-l-lg border border-[#4b504c] bg-[#222522] p-3"
                      />
                      <input
                        name={`${item.key}_unit`}
                        defaultValue={item.unit}
                        aria-label={`${item.name} unit`}
                        className="w-20 rounded-r-lg border border-l-0 border-[#4b504c] bg-[#303430] p-3 text-center text-xs"
                      />
                    </div>
                  </label>
                </div>
              ))}
            </div>
            <div className="mt-5 grid gap-4 sm:grid-cols-2">
              <label className="font-semibold">
                Calibration status
                <select
                  name="calibration_status"
                  defaultValue="unknown"
                  className="mt-2 w-full rounded-lg border border-[#494d4a] bg-[#262927] p-3.5"
                >
                  <option value="calibrated">Calibrated</option>
                  <option value="uncalibrated">Not calibrated</option>
                  <option value="unknown">I do not know</option>
                </select>
              </label>
              <label className="font-semibold">
                Reading quality
                <select
                  name="reliability"
                  defaultValue="needs_review"
                  className="mt-2 w-full rounded-lg border border-[#494d4a] bg-[#262927] p-3.5"
                >
                  <option value="reliable">Reliable</option>
                  <option value="needs_review">Needs review</option>
                  <option value="unreliable">Unreliable</option>
                </select>
              </label>
            </div>
            <label className="mt-4 block font-semibold">
              Notes
              <textarea
                name="note"
                rows={2}
                placeholder="Sampling location, laboratory name, unusual field condition…"
                className="mt-2 w-full rounded-lg border border-[#494d4a] bg-[#262927] p-3.5"
              />
            </label>
            <button
              disabled={saving}
              className="mt-6 flex items-center gap-2 rounded-full bg-[#647c31] px-6 py-3 font-bold disabled:opacity-50"
            >
              {saving ? (
                <LoaderCircle className="animate-spin" size={18} />
              ) : (
                <Beaker size={18} />
              )}
              {saving ? "Saving…" : "Save measurements"}
            </button>
          </form>
        </div>
      )}
    </div>
  );
}
