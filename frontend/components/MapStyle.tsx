"use client";

import { useEffect, useState } from "react";
import { Map, Satellite } from "lucide-react";
import { TileLayer } from "react-leaflet";

export type MapStyle = "land" | "satellite";

const STORAGE_KEY = "agrinox_map_style";
const CHANGE_EVENT = "agrinox-map-style";

export function useMapStyle() {
  const [style, setStyleState] = useState<MapStyle>("land");

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "land" || stored === "satellite") setStyleState(stored);
    const update = (event: Event) => {
      const next = (event as CustomEvent<MapStyle>).detail;
      if (next === "land" || next === "satellite") setStyleState(next);
    };
    window.addEventListener(CHANGE_EVENT, update);
    return () => window.removeEventListener(CHANGE_EVENT, update);
  }, []);

  function setStyle(next: MapStyle) {
    setStyleState(next);
    localStorage.setItem(STORAGE_KEY, next);
    window.dispatchEvent(new CustomEvent<MapStyle>(CHANGE_EVENT, { detail: next }));
  }

  return { style, setStyle };
}

export function MapBaseLayer({ style }: { style: MapStyle }) {
  if (style === "satellite") {
    return (
      <TileLayer
        key="satellite"
        attribution='Tiles &copy; Esri &mdash; Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community'
        url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
        maxZoom={19}
      />
    );
  }
  return (
    <TileLayer
      key="land"
      attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>'
      url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
      maxZoom={19}
    />
  );
}

export function MapStyleToggle({ style, onChange }: { style: MapStyle; onChange: (style: MapStyle) => void }) {
  return (
    <div className="absolute right-3 top-3 z-[1000] flex rounded-xl border border-white/20 bg-[#171b18e8] p-1 shadow-xl backdrop-blur" aria-label="Map appearance">
      <button
        type="button"
        aria-pressed={style === "land"}
        title="Land map with roads and place names"
        onClick={() => onChange("land")}
        className={`flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-semibold ${style === "land" ? "bg-[#41634a] text-white" : "text-[#b7c0b9] hover:bg-white/10"}`}
      >
        <Map size={15} /> Land map
      </button>
      <button
        type="button"
        aria-pressed={style === "satellite"}
        title="Satellite and aerial imagery"
        onClick={() => onChange("satellite")}
        className={`flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-semibold ${style === "satellite" ? "bg-[#41634a] text-white" : "text-[#b7c0b9] hover:bg-white/10"}`}
      >
        <Satellite size={15} /> Satellite
      </button>
    </div>
  );
}
