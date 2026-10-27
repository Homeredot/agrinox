"use client";

import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  CalendarDays,
  Cloud,
  CloudLightning,
  CloudRain,
  CloudSun,
  Droplets,
  Gauge,
  History,
  LoaderCircle,
  MapPin,
  Navigation,
  RefreshCw,
  Sprout,
  Sun,
  Wind,
} from "lucide-react";

import { api, type Farm } from "@/lib/api";
import type { Language } from "@/lib/i18n";
import LocationPicker, { type LocationSelection } from "./LocationPicker";
import type { MapFocus } from "./MapPicker";

type WeatherData = {
  location: {
    label: string;
    source: string;
    latitude: number;
    longitude: number;
    timezone: string;
  };
  current: Record<string, number | string>;
  hourly: Record<string, (number | string)[]>;
  daily: Record<string, (number | string)[]>;
  historical_months: {
    month: string;
    rainfall_mm: number;
    mean_high_c: number | null;
    mean_low_c: number | null;
    days: number;
  }[];
  historical_note: string;
  recommendations: {
    title: string;
    guidance: string;
    evidence: string;
    uncertainty: string;
    severity: string;
  }[];
  warnings: string[];
  warnings_supported: boolean;
  warnings_note: string;
  provider: string;
  generated_at: string;
  cache: { hit: boolean; stored_at?: string; ttl_minutes?: number };
};

function weatherLabel(code: number) {
  if (code === 0) return "Clear sky";
  if (code <= 3) return "Partly cloudy";
  if ([45, 48].includes(code)) return "Fog";
  if (code <= 57) return "Drizzle";
  if (code <= 67) return "Rain";
  if (code <= 77) return "Snow";
  if (code <= 82) return "Rain showers";
  if (code >= 95) return "Thunderstorm";
  return "Mixed weather";
}

function weatherTheme(code: number) {
  if (code === 0) return "sunny";
  if ([45, 48].includes(code)) return "foggy";
  if (code >= 95) return "stormy";
  if (code >= 51 && code <= 82) return "rainy";
  return "cloudy";
}

function WeatherIcon({ code, size = 24 }: { code: number; size?: number }) {
  if (code === 0) return <Sun size={size} />;
  if (code >= 95) return <CloudLightning size={size} />;
  if (code >= 51) return <CloudRain size={size} />;
  return <Cloud size={size} />;
}

function valueAt(
  values: Record<string, (number | string)[]>,
  key: string,
  index: number,
) {
  return values[key]?.[index] as number | string | undefined;
}

export default function WeatherDashboard({
  farms,
  token,
  language,
}: {
  farms: Farm[];
  token: string;
  language: Language;
}) {
  const [farmId, setFarmId] = useState<number | null>(farms[0]?.id ?? null);
  const [weather, setWeather] = useState<WeatherData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [location, setLocation] = useState<LocationSelection>({});
  const [latitude, setLatitude] = useState("");
  const [longitude, setLongitude] = useState("");

  async function loadWeather(path: string) {
    setLoading(true);
    setError("");
    try {
      setWeather(await api<WeatherData>(path, {}, token));
    } catch (requestError) {
      setWeather(null);
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Weather could not be loaded",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (farmId) void loadWeather(`/weather?farm_id=${farmId}`);
  }, [farmId]); // eslint-disable-line react-hooks/exhaustive-deps

  async function useCell(next: LocationSelection) {
    if (!next.cell) return;
    try {
      const focus = await api<MapFocus>(
        `/locations/cells/${next.cell.code}/map-focus`,
        {},
        token,
      );
      setLatitude(String(focus.latitude));
      setLongitude(String(focus.longitude));
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not locate this cell",
      );
    }
  }

  function loadCoordinates() {
    const lat = Number(latitude);
    const lon = Number(longitude);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
      setError("Enter valid latitude and longitude coordinates.");
      return;
    }
    const label = location.village
      ? `${location.village.name}, ${location.cell?.name}, ${location.district?.name}`
      : "Provided farm coordinates";
    void loadWeather(
      `/weather?latitude=${lat}&longitude=${lon}&label=${encodeURIComponent(label)}`,
    );
  }

  const nextHourIndex = useMemo(() => {
    if (!weather) return 0;
    const times = (weather.hourly.time ?? []) as string[];
    const currentTime = String(weather.current.time ?? "");
    const found = times.findIndex((time) => time >= currentTime);
    return found < 0 ? 0 : found;
  }, [weather]);

  const hourlyIndexes = useMemo(() => {
    if (!weather) return [];
    const length = weather.hourly.time?.length ?? 0;
    return Array.from(
      { length: Math.min(12, Math.max(0, length - nextHourIndex)) },
      (_, i) => i + nextHourIndex,
    );
  }, [weather, nextHourIndex]);

  const maxHistoricalRain = Math.max(
    1,
    ...(weather?.historical_months.map((month) => month.rainfall_mm) ?? [1]),
  );
  const currentCode = Number(weather?.current.weather_code ?? 0);
  const currentTheme = weatherTheme(currentCode);

  return (
    <div
      className={`weather-atmosphere weather-theme-${currentTheme} relative isolate`}
    >
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold sm:text-4xl">
            Farm weather
          </h1>
          <p className="mobile-secondary mt-2 max-w-2xl text-[#aeb3af]">
            Forecasts, historical context and explainable agricultural guidance
            for the selected farm location.
          </p>
        </div>
        {weather && (
          <button
            onClick={() =>
              farmId
                ? void loadWeather(`/weather?farm_id=${farmId}`)
                : loadCoordinates()
            }
            disabled={loading}
            aria-label="Refresh weather"
            className="flex h-11 items-center gap-2 rounded-full border border-[#4b504c] px-3 font-semibold hover:bg-[#292c2a] disabled:opacity-50 sm:px-5"
          >
            <RefreshCw size={17} className={loading ? "animate-spin" : ""} />{" "}
            <span className="hidden sm:inline">Refresh</span>
          </button>
        )}
      </div>

      <section className="weather-glass mobile-compact-card mt-4 rounded-2xl p-5 sm:mt-7">
        {farms.length > 0 ? (
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="mobile-secondary">
              <p className="text-xs uppercase tracking-widest text-[#8f9691]">
                Weather location
              </p>
              <h2 className="mt-1 font-semibold">Use a registered farm</h2>
              <p className="mt-1 text-sm text-[#969b97]">
                The saved farm location is used automatically.
              </p>
            </div>
            <label className="w-full text-sm text-[#b8bdb9] sm:w-auto sm:min-w-64">
              Farm
              <select
                value={farmId ?? ""}
                onChange={(event) => setFarmId(Number(event.target.value))}
                className="mt-1 w-full rounded-lg border border-[#4a4e4a] bg-[#292c2a] px-3 py-2.5 text-white"
              >
                {farms.map((farm) => (
                  <option key={farm.id} value={farm.id}>
                    {farm.name} — {farm.cell}, {farm.district}
                  </option>
                ))}
              </select>
            </label>
          </div>
        ) : (
          <div>
            <div className="flex items-start gap-3">
              <Navigation className="mt-1 text-[#8294f2]" size={20} />
              <div>
                <h2 className="font-semibold">
                  Choose a verified Rwanda location
                </h2>
                <p className="mt-1 text-sm text-[#969b97]">
                  No farm is registered, so choose the hierarchy or provide farm
                  coordinates.
                </p>
              </div>
            </div>
            <div className="mt-5">
              <LocationPicker
                token={token}
                value={location}
                onChange={setLocation}
                onCellChange={useCell}
              />
            </div>
            <div className="mt-4 grid gap-3 sm:grid-cols-[1fr_1fr_auto]">
              <label className="text-sm">
                Latitude
                <input
                  value={latitude}
                  onChange={(event) => setLatitude(event.target.value)}
                  inputMode="decimal"
                  placeholder="e.g. -1.95"
                  className="mt-1 w-full rounded-lg border border-[#4a4e4a] bg-[#292c2a] p-3"
                />
              </label>
              <label className="text-sm">
                Longitude
                <input
                  value={longitude}
                  onChange={(event) => setLongitude(event.target.value)}
                  inputMode="decimal"
                  placeholder="e.g. 30.06"
                  className="mt-1 w-full rounded-lg border border-[#4a4e4a] bg-[#292c2a] p-3"
                />
              </label>
              <button
                onClick={loadCoordinates}
                disabled={loading}
                className="self-end rounded-lg bg-[#4c60c9] px-5 py-3 font-semibold disabled:opacity-50"
              >
                View weather
              </button>
            </div>
          </div>
        )}
      </section>

      {error && (
        <div
          role="alert"
          className="mt-5 rounded-xl border border-[#6e3333] bg-[#3b2020] p-4 text-[#ffb9b9]"
        >
          {error}
        </div>
      )}
      {loading && (
        <div className="weather-glass mt-8 grid min-h-64 place-items-center rounded-2xl">
          <div className="text-center text-[#aeb3af]">
            <LoaderCircle className="mx-auto mb-3 animate-spin text-[#8294f2]" />
            <p>Loading weather intelligence…</p>
          </div>
        </div>
      )}

      {weather && !loading && (
        <>
          <section
            className={`weather-hero weather-hero-${currentTheme} relative mt-6 overflow-hidden rounded-[28px] p-5 sm:p-8`}
          >
            <div aria-hidden="true" className="weather-sun" />
            <div
              aria-hidden="true"
              className="weather-cloud weather-cloud-one"
            />
            <div
              aria-hidden="true"
              className="weather-cloud weather-cloud-two"
            />
            <div aria-hidden="true" className="weather-rain-lines" />
            <div aria-hidden="true" className="weather-lightning-flash" />
            <div aria-hidden="true" className="weather-haze" />
            <div className="flex flex-wrap items-start justify-between gap-6">
              <div>
                <div className="flex items-center gap-2 text-sm text-[#c0cae8]">
                  <MapPin size={16} />
                  {weather.location.label}
                </div>
                <div className="mt-5 flex items-center gap-5">
                  <span
                    className={`weather-current-icon weather-current-icon-${currentTheme}`}
                  >
                    <WeatherIcon code={currentCode} size={58} />
                  </span>
                  <div>
                    <strong className="text-5xl sm:text-6xl">
                      {Math.round(Number(weather.current.temperature_2m))}°
                    </strong>
                    <p className="mt-1 text-[#d0d7ea]">
                      {weatherLabel(currentCode)}
                    </p>
                  </div>
                </div>
              </div>
              <div className="text-right text-xs text-[#aeb8d2]">
                <p>{weather.location.source}</p>
                <p className="mt-1">Open-Meteo · Africa/Kigali</p>
                <p className="mt-1">
                  {weather.cache.hit ? "Cached response" : "Fresh response"}
                </p>
              </div>
            </div>
            <div className="mt-7 grid grid-cols-2 gap-3 lg:grid-cols-4">
              {[
                {
                  label: "Humidity",
                  value: `${weather.current.relative_humidity_2m}%`,
                  icon: Droplets,
                },
                {
                  label: "Rainfall now",
                  value: `${weather.current.precipitation ?? 0} mm`,
                  icon: CloudRain,
                },
                {
                  label: "Rain probability",
                  value: `${valueAt(weather.hourly, "precipitation_probability", nextHourIndex) ?? 0}%`,
                  icon: Gauge,
                },
                {
                  label: "Wind speed",
                  value: `${weather.current.wind_speed_10m} km/h`,
                  icon: Wind,
                },
              ].map((metric) => (
                <article
                  key={metric.label}
                  className="weather-metric rounded-2xl p-4"
                >
                  <metric.icon size={18} className="text-[#9badf5]" />
                  <p className="mt-3 text-xs text-[#aeb8d2]">{metric.label}</p>
                  <strong className="mt-1 block text-xl">{metric.value}</strong>
                </article>
              ))}
            </div>
          </section>

          <section className="mt-6 grid gap-5 xl:grid-cols-[1.25fr_.75fr]">
            <div className="weather-glass rounded-2xl p-5">
              <div className="flex items-center gap-3">
                <Sprout className="text-[#78c87e]" />
                <div>
                  <h2 className="text-xl font-semibold">
                    Agricultural guidance
                  </h2>
                  <p className="text-sm text-[#969b97]">
                    Evidence and uncertainty are shown for every recommendation.
                  </p>
                </div>
              </div>
              <div className="mt-4 space-y-3">
                {weather.recommendations.map((item) => (
                  <article
                    key={item.title}
                    className="rounded-xl border border-[#456052] bg-gradient-to-br from-[#29352f] to-[#252b28] p-4"
                  >
                    <h3 className="font-semibold">{item.title}</h3>
                    <p className="mt-2 text-sm text-[#d7dbd8]">
                      {item.guidance}
                    </p>
                    <p className="mt-3 text-xs text-[#8fc897]">
                      <strong>Evidence:</strong> {item.evidence}
                    </p>
                    <p className="mt-2 text-xs text-[#a2a7a3]">
                      <strong>Uncertainty:</strong> {item.uncertainty}
                    </p>
                  </article>
                ))}
              </div>
            </div>
            <div className="weather-warning-card rounded-2xl p-5">
              <div className="flex items-center gap-3">
                <AlertTriangle className="text-[#e2b560]" />
                <h2 className="text-lg font-semibold">Weather warnings</h2>
              </div>
              <p className="mt-4 text-sm text-[#d5cfbf]">
                {weather.warnings.length
                  ? weather.warnings.join(" · ")
                  : "No official warnings are available from this provider."}
              </p>
              <p className="mt-3 text-xs leading-relaxed text-[#a9a18d]">
                {weather.warnings_note}
              </p>
            </div>
          </section>

          <section className="mt-7">
            <div className="flex items-end justify-between">
              <div>
                <h2 className="text-xl font-semibold">Hourly weather</h2>
                <p className="mt-1 text-sm text-[#969b97]">Next 12 hours</p>
              </div>
            </div>
            <div className="weather-scroll mt-3 flex snap-x snap-mandatory gap-3 overflow-x-auto pb-3">
              {hourlyIndexes.map((index) => {
                const code = Number(
                  valueAt(weather.hourly, "weather_code", index) ?? 0,
                );
                const time = String(
                  valueAt(weather.hourly, "time", index) ?? "",
                );
                return (
                  <article
                    key={time}
                    className="weather-hour-card w-[7.5rem] shrink-0 snap-start rounded-2xl p-3 text-center sm:w-32 sm:p-4"
                  >
                    <p className="whitespace-nowrap text-xs text-[#9ca19d]">
                      {new Date(time).toLocaleTimeString(
                        language === "rw" ? "rw-RW" : "en-RW",
                        { hour: "2-digit", minute: "2-digit" },
                      )}
                    </p>
                    <span className="mx-auto mt-3 block w-fit text-[#8fa2ef]">
                      <WeatherIcon code={code} />
                    </span>
                    <strong className="mt-2 block whitespace-nowrap text-xl">
                      {Math.round(
                        Number(
                          valueAt(weather.hourly, "temperature_2m", index),
                        ),
                      )}
                      °
                    </strong>
                    <p className="mt-2 whitespace-nowrap text-xs text-[#7fc18a]">
                      {valueAt(
                        weather.hourly,
                        "precipitation_probability",
                        index,
                      ) ?? 0}
                      % rain
                    </p>
                    <div className="mt-3 h-1 overflow-hidden rounded-full bg-white/10">
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-[#6f86f2] to-[#63c5dc]"
                        style={{
                          width: `${valueAt(weather.hourly, "precipitation_probability", index) ?? 0}%`,
                        }}
                      />
                    </div>
                  </article>
                );
              })}
            </div>
          </section>

          <section className="mt-7">
            <div className="flex items-center gap-3">
              <CalendarDays className="text-[#8294f2]" />
              <div>
                <h2 className="text-xl font-semibold">Daily forecast</h2>
                <p className="text-sm text-[#969b97]">
                  A closer view of the next three days
                </p>
              </div>
            </div>
            <div className="mt-3 grid gap-3 md:grid-cols-3">
              {[0, 1, 2].map((index) => {
                const code = Number(
                  valueAt(weather.daily, "weather_code", index) ?? 0,
                );
                return (
                  <article
                    key={String(valueAt(weather.daily, "time", index))}
                    className="weather-day-card rounded-2xl p-5"
                  >
                    <div className="flex items-start justify-between">
                      <div>
                        <p className="text-sm text-[#aeb3af]">
                          {new Date(
                            `${valueAt(weather.daily, "time", index)}T12:00`,
                          ).toLocaleDateString("en-RW", { weekday: "long" })}
                        </p>
                        <h3 className="mt-1 font-semibold">
                          {weatherLabel(code)}
                        </h3>
                      </div>
                      <span className="text-[#e2b560]">
                        <WeatherIcon code={code} size={30} />
                      </span>
                    </div>
                    <div className="mt-5 flex items-end justify-between">
                      <span>
                        <strong className="text-2xl">
                          {valueAt(weather.daily, "temperature_2m_max", index)}°
                        </strong>
                        <small className="ml-2 text-[#8f9490]">
                          {valueAt(weather.daily, "temperature_2m_min", index)}°
                          low
                        </small>
                      </span>
                      <span className="text-sm text-[#84c78c]">
                        {valueAt(
                          weather.daily,
                          "precipitation_probability_max",
                          index,
                        )}
                        %
                      </span>
                    </div>
                  </article>
                );
              })}
            </div>
          </section>

          <section className="weather-glass mt-7 overflow-hidden rounded-2xl">
            <div className="border-b border-[#3b3e3b] p-5">
              <h2 className="text-xl font-semibold">Seven-day forecast</h2>
              <p className="mt-1 text-sm text-[#969b97]">
                Model outlook—not a guarantee of exact farm conditions.
              </p>
            </div>
            <div className="divide-y divide-[#353835]">
              {((weather.daily.time ?? []) as string[])
                .slice(0, 7)
                .map((day, index) => {
                  const code = Number(
                    valueAt(weather.daily, "weather_code", index) ?? 0,
                  );
                  return (
                    <article
                      key={day}
                      className="grid grid-cols-[1fr_auto] items-center gap-4 px-5 py-4 sm:grid-cols-[1.2fr_1fr_1fr_1fr]"
                    >
                      <div>
                        <strong>
                          {new Date(`${day}T12:00`).toLocaleDateString(
                            "en-RW",
                            {
                              weekday: "short",
                              month: "short",
                              day: "numeric",
                            },
                          )}
                        </strong>
                        <p className="mt-1 flex items-center gap-2 text-xs text-[#969b97]">
                          <WeatherIcon code={code} size={15} />
                          {weatherLabel(code)}
                        </p>
                      </div>
                      <div>
                        <span className="sm:hidden text-xs text-[#8f9490]">
                          Temperature{" "}
                        </span>
                        {valueAt(weather.daily, "temperature_2m_min", index)}° /{" "}
                        <strong>
                          {valueAt(weather.daily, "temperature_2m_max", index)}°
                        </strong>
                      </div>
                      <div className="text-sm text-[#82c68b]">
                        <CloudRain size={15} className="mr-1 inline" />
                        {valueAt(
                          weather.daily,
                          "precipitation_probability_max",
                          index,
                        )}
                        % · {valueAt(weather.daily, "precipitation_sum", index)}{" "}
                        mm
                      </div>
                      <div className="hidden text-sm text-[#aeb3af] sm:block">
                        <Wind size={15} className="mr-1 inline" />
                        {valueAt(
                          weather.daily,
                          "wind_speed_10m_max",
                          index,
                        )}{" "}
                        km/h
                      </div>
                    </article>
                  );
                })}
            </div>
          </section>

          <section className="weather-glass mt-7 rounded-2xl p-5">
            <div className="flex items-start gap-3">
              <History className="mt-1 text-[#b78bd1]" />
              <div>
                <h2 className="text-xl font-semibold">
                  Monthly historical summary
                </h2>
                <p className="mt-1 text-sm text-[#969b97]">
                  Past reanalysis estimates—not a long-range forecast.
                </p>
              </div>
            </div>
            <div className="mt-6 grid grid-cols-6 gap-2 sm:grid-cols-12">
              {weather.historical_months.map((month) => (
                <div key={month.month} className="text-center">
                  <div className="flex h-36 items-end justify-center rounded-lg bg-[#292c2a] p-1">
                    <div
                      className="w-full rounded-md bg-gradient-to-t from-[#4356c9] to-[#74a5e8]"
                      style={{
                        height: `${Math.max(5, (month.rainfall_mm / maxHistoricalRain) * 100)}%`,
                      }}
                      title={`${month.rainfall_mm} mm`}
                    />
                  </div>
                  <p className="mt-2 text-[10px] text-[#9ca19d]">
                    {new Date(`${month.month}-01T12:00`).toLocaleDateString(
                      "en-RW",
                      { month: "short" },
                    )}
                  </p>
                  <strong className="text-[10px]">
                    {month.rainfall_mm} mm
                  </strong>
                </div>
              ))}
            </div>
            <p className="mt-5 text-xs leading-relaxed text-[#858b86]">
              {weather.historical_note}
            </p>
          </section>
        </>
      )}
    </div>
  );
}
