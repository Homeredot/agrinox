"use client";

import { useCallback, useEffect, useState } from "react";
import { Cloud, CloudRain, LocateFixed, MapPin, RefreshCw, Sun } from "lucide-react";

import { api } from "@/lib/api";
import { useI18n } from "./I18nProvider";

type ReverseLocation = { display_name?: string; district?: string; sector?: string; cell?: string; village?: string };
type Weather = { current: { temperature_2m?: number; relative_humidity_2m?: number; weather_code?: number }; current_units?: { temperature_2m?: string } };

export default function SidebarLiveStatus({ token }: { token: string }) {
  const { t } = useI18n();
  const [location, setLocation] = useState("");
  const [weather, setWeather] = useState<Weather | null>(null);
  const [loading, setLoading] = useState(false);
  const [locationError, setLocationError] = useState(false);

  const findLocation = useCallback(() => {
    if (!navigator.geolocation) { setLocationError(true); return; }
    setLoading(true); setLocationError(false);
    navigator.geolocation.getCurrentPosition(async ({ coords }) => {
      const query = `latitude=${coords.latitude}&longitude=${coords.longitude}`;
      try {
        const [place, conditions] = await Promise.all([
          api<ReverseLocation>(`/locations/reverse?${query}`, {}, token),
          api<Weather>(`/weather?${query}&label=Current location`, {}, token),
        ]);
        setLocation(place.village || place.cell || place.sector || place.district || place.display_name?.split(",")[0] || t("sidebar.currentLocation"));
        setWeather(conditions);
      } catch { setLocationError(true); }
      finally { setLoading(false); }
    }, () => { setLocationError(true); setLoading(false); }, { enableHighAccuracy: false, timeout: 12000, maximumAge: 30 * 60 * 1000 });
  }, [t, token]);

  useEffect(() => { findLocation(); }, [findLocation]);

  const code = Number(weather?.current.weather_code ?? 0);
  const temperature = Number(weather?.current.temperature_2m);
  const temperatureLabel = Number.isFinite(temperature) ? `${Math.round(temperature)}°` : "—";
  const WeatherIcon = code >= 51 ? CloudRain : code >= 1 ? Cloud : Sun;
  const condition = code >= 61 ? t("sidebar.rain") : code >= 51 ? t("sidebar.drizzle") : code >= 1 ? t("sidebar.cloudy") : t("sidebar.clear");

  return <section className="mt-auto rounded-2xl border border-[#39433b] bg-[#242925] p-3 shadow-inner shadow-black/10">
    {weather ? <div className="flex min-h-11 items-center gap-3"><span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-[#304333] text-[#8fd18a]"><WeatherIcon size={18}/></span><div className="min-w-0 flex-1"><span className="flex items-center gap-1.5 truncate text-xs font-medium text-[#d5ddd7]"><MapPin size={12} className="shrink-0"/>{location}</span><span className="mt-0.5 block text-[11px] text-[#7f8981]">{condition}</span></div><strong className="shrink-0 text-lg text-white">{temperatureLabel}</strong></div> : <button onClick={findLocation} disabled={loading} className="flex min-h-11 w-full items-center justify-center gap-2 rounded-xl px-2 text-xs text-[#adb6af] hover:bg-[#303631] disabled:opacity-50">{loading ? <RefreshCw className="animate-spin" size={15}/> : locationError ? <LocateFixed size={15}/> : <MapPin size={15}/>} {loading ? t("sidebar.locating") : locationError ? t("sidebar.allowLocation") : t("sidebar.currentLocation")}</button>}
  </section>;
}
