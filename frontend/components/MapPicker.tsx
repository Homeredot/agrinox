"use client";

import { useEffect, useState } from "react";
import { LoaderCircle, MapPin, Search } from "lucide-react";
import {
  GeoJSON,
  MapContainer,
  Marker,
  Polygon,
  useMap,
  useMapEvents,
} from "react-leaflet";
import L from "leaflet";
import type { GeoJsonObject } from "geojson";

import { api } from "@/lib/api";
import { copy, Language } from "@/lib/i18n";
import { MapBaseLayer, MapStyleToggle, useMapStyle } from "./MapStyle";

const icon = L.divIcon({
  className: "",
  html: '<div style="width:18px;height:18px;border:3px solid white;background:#d7a53f;border-radius:50%;box-shadow:0 2px 8px #0008"></div>',
  iconSize: [18, 18],
  iconAnchor: [9, 9],
});
const focusIcon = L.divIcon({
  className: "",
  html: '<div style="width:22px;height:22px;border:4px solid white;background:#4356c9;border-radius:50%;box-shadow:0 2px 10px #0009"></div>',
  iconSize: [22, 22],
  iconAnchor: [11, 11],
});

export type SearchResult = {
  display_name: string;
  latitude: number;
  longitude: number;
  province?: string;
  district?: string;
  sector?: string;
  cell?: string;
  village?: string;
};

export type MapFocus = {
  cell_code: number;
  label: string;
  latitude: number;
  longitude: number;
  bounds?: [number, number, number, number] | null;
  geometry?: GeoJsonObject | null;
  focus_level: "cell" | "sector" | "district";
  exact_cell_match: boolean;
  navigation_only: boolean;
};

function Clicker({
  points,
  setPoints,
  onPick,
}: {
  points: [number, number][];
  setPoints: (p: [number, number][]) => void;
  onPick: (lat: number, lng: number) => void;
}) {
  useMapEvents({
    click(e) {
      setPoints([...points, [e.latlng.lat, e.latlng.lng]]);
      onPick(e.latlng.lat, e.latlng.lng);
    },
  });
  return null;
}

function Recenter({
  target,
  focusArea,
}: {
  target: [number, number] | null;
  focusArea?: MapFocus | null;
}) {
  const map = useMap();
  useEffect(() => {
    if (target) map.setView(target, 15);
    else if (focusArea?.bounds) {
      const [south, north, west, east] = focusArea.bounds;
      map.fitBounds(
        [
          [south, west],
          [north, east],
        ],
        { padding: [28, 28], maxZoom: 16 },
      );
    } else if (focusArea)
      map.setView([focusArea.latitude, focusArea.longitude], 15);
  }, [map, target, focusArea]);
  return null;
}

export default function MapPicker({
  points,
  setPoints,
  onPick,
  token,
  language,
  addSearchPoint = false,
  onSearchResult,
  focusArea,
}: {
  points: [number, number][];
  setPoints: (p: [number, number][]) => void;
  onPick: (lat: number, lng: number) => void;
  token: string;
  language: Language;
  addSearchPoint?: boolean;
  onSearchResult?: (result: SearchResult) => void;
  focusArea?: MapFocus | null;
}) {
  const { style, setStyle } = useMapStyle();
  const t = copy[language];
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [searched, setSearched] = useState(false);
  const [target, setTarget] = useState<[number, number] | null>(null);
  const [searchError, setSearchError] = useState("");

  useEffect(() => {
    setTimeout(() => window.dispatchEvent(new Event("resize")), 50);
  }, []);

  async function search() {
    if (query.trim().length < 2) return;
    setSearching(true);
    setSearched(false);
    setSearchError("");
    try {
      setResults(
        await api<SearchResult[]>(
          `/locations/search?q=${encodeURIComponent(query.trim())}`,
          {},
          token,
        ),
      );
      setSearched(true);
    } catch (error) {
      setResults([]);
      setSearchError(error instanceof Error ? error.message : "Search failed");
    } finally {
      setSearching(false);
    }
  }

  function select(result: SearchResult) {
    const location: [number, number] = [result.latitude, result.longitude];
    setTarget(location);
    setResults([]);
    setSearched(false);
    setQuery(result.display_name);
    onSearchResult?.(result);
    if (addSearchPoint) {
      setPoints([location]);
      onPick(result.latitude, result.longitude);
    }
  }

  return (
    <div className="relative">
      <div className="flex gap-2 mb-3" role="search">
        <label className="sr-only" htmlFor="map-search">
          {t.searchMap}
        </label>
        <div className="relative flex-1">
          <Search
            className="absolute left-4 top-1/2 -translate-y-1/2 text-[#66766d]"
            size={19}
          />
          <input
            id="map-search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                void search();
              }
            }}
            placeholder={t.searchPlaceholder}
            className="w-full pl-11 pr-4 py-3.5 rounded-lg border border-[#494d4a] bg-[#262927] text-white placeholder:text-[#868b87] focus:outline-none focus:ring-2 focus:ring-[#62a86b]"
          />
        </div>
        <button
          type="button"
          onClick={() => void search()}
          disabled={searching || query.trim().length < 2}
          className="px-4 sm:px-5 rounded-lg bg-[#2f8059] text-white font-bold disabled:opacity-50"
          aria-label={t.searchMap}
        >
          {searching ? (
            <LoaderCircle className="animate-spin" size={20} />
          ) : (
            <>
              <span className="hidden sm:inline">{t.searchMap}</span>
              <Search className="sm:hidden" size={20} />
            </>
          )}
        </button>
      </div>
      {(results.length > 0 ||
        (searched && results.length === 0) ||
        searchError) && (
        <div className="absolute z-[1000] top-[62px] left-0 right-0 bg-[#262927] text-white rounded-xl border border-[#494d4a] shadow-xl overflow-hidden">
          {results.map((result, index) => (
            <button
              type="button"
              key={`${result.latitude}-${result.longitude}-${index}`}
              onClick={() => select(result)}
              className="w-full text-left p-4 flex gap-3 hover:bg-[#303431] border-b border-[#424642] last:border-b-0"
            >
              <MapPin className="shrink-0 text-[#78c87e]" size={20} />
              <span>
                <strong className="block text-sm">
                  {result.display_name.split(",")[0]}
                </strong>
                <small className="text-[#aeb3af] line-clamp-2">
                  {result.display_name}
                </small>
              </span>
            </button>
          ))}
          {searched && results.length === 0 && !searchError && (
            <p className="p-4 text-sm text-[#aeb3af]">{t.noResults}</p>
          )}
          {searchError && (
            <p className="p-4 text-sm text-red-700">{searchError}</p>
          )}
        </div>
      )}
      {focusArea && (
        <div className="mb-3 flex items-start gap-3 rounded-lg border border-[#3f4f73] bg-[#222a3d] px-3 py-2.5 text-sm">
          <MapPin size={17} className="mt-0.5 shrink-0 text-[#8fa5ff]" />
          <span>
            <strong className="block">Showing {focusArea.label}</strong>
            <small className="text-[#aeb8d8]">
              {focusArea.exact_cell_match
                ? "Cell boundary from OpenStreetMap. "
                : `OpenStreetMap does not publish this cell boundary, so the map is focused using its ${focusArea.focus_level}. `}
              Click the map to set the farm&apos;s exact point.
            </small>
          </span>
        </div>
      )}
      <div className="relative h-[300px] overflow-hidden rounded-2xl border border-[#cad7c7] sm:h-[360px] sm:rounded-3xl">
        <MapStyleToggle style={style} onChange={setStyle} />
        <MapContainer center={[-1.94, 29.87]} zoom={8} scrollWheelZoom>
          <MapBaseLayer style={style} />
          <Recenter target={target} focusArea={focusArea} />
          <Clicker points={points} setPoints={setPoints} onPick={onPick} />
          {points.map((point, i) => (
            <Marker key={i} position={point} icon={icon} />
          ))}
          {focusArea && (
            <Marker
              position={[focusArea.latitude, focusArea.longitude]}
              icon={focusIcon}
            />
          )}
          {focusArea?.geometry && (
            <GeoJSON
              key={focusArea.cell_code}
              data={focusArea.geometry}
              style={{
                color: "#4356c9",
                weight: 3,
                fillColor: "#6477dc",
                fillOpacity: 0.18,
              }}
            />
          )}
          {points.length >= 3 && (
            <Polygon
              positions={points}
              pathOptions={{
                color: "#2f7d4a",
                fillColor: "#b8d96b",
                fillOpacity: 0.35,
              }}
            />
          )}
        </MapContainer>
      </div>
    </div>
  );
}
