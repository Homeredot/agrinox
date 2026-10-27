"use client";

import { useEffect, useMemo } from "react";
import type { Feature, FeatureCollection, GeoJsonProperties, Geometry } from "geojson";
import { GeoJSON, MapContainer, useMap } from "react-leaflet";
import type { Layer } from "leaflet";

import { MapBaseLayer, MapStyleToggle, useMapStyle } from "./MapStyle";

function FitRwanda() {
  const map = useMap();
  useEffect(() => { map.fitBounds([[-2.85, 28.85], [-1.04, 30.91]], { padding: [18, 18] }); }, [map]);
  return null;
}

const COLORS = ["#27342b", "#d7e58a", "#a8cf69", "#6eaa54", "#367844", "#155330"];

export default function DistrictIntelligenceMap({
  boundaries,
  values,
  selectedDistrict,
  unit,
  onDistrict,
}: {
  boundaries: FeatureCollection;
  values: { district: string; value: number }[];
  selectedDistrict?: string | null;
  unit: string;
  onDistrict: (district: string, province?: string) => void;
}) {
  const { style: mapStyle, setStyle } = useMapStyle();
  const lookup = useMemo(() => new Map(values.map(item => [item.district, item.value])), [values]);
  const numeric = values.map(item => item.value).filter(Number.isFinite);
  const min = numeric.length ? Math.min(...numeric) : 0;
  const max = numeric.length ? Math.max(...numeric) : 0;

  function color(value?: number) {
    if (value == null || !Number.isFinite(value)) return COLORS[0];
    if (max === min) return COLORS[4];
    const index = Math.min(4, Math.floor((value - min) / (max - min) * 5));
    return COLORS[index + 1];
  }

  function districtName(feature?: Feature<Geometry, GeoJsonProperties>) {
    return String(feature?.properties?.district ?? "");
  }

  function attach(feature: Feature<Geometry, GeoJsonProperties>, layer: Layer) {
    const district = districtName(feature);
    const value = lookup.get(district);
    layer.bindTooltip(`<strong>${district}</strong><br>${value == null ? "No published data" : `${value.toLocaleString(undefined, { maximumFractionDigits: 2 })} ${unit}`}`, { sticky: true });
    layer.on("click", () => onDistrict(district, String(feature.properties?.province ?? "")));
  }

  return (
    <div className="relative h-[440px] overflow-hidden rounded-2xl border border-[#405043] bg-[#202522]">
      <MapStyleToggle style={mapStyle} onChange={setStyle} />
      <MapContainer center={[-1.94, 29.87]} zoom={8} scrollWheelZoom>
        <MapBaseLayer style={mapStyle} />
        <FitRwanda />
        <GeoJSON
          key={`${selectedDistrict}-${values.map(v => `${v.district}:${v.value}`).join("|")}`}
          data={boundaries}
          onEachFeature={attach}
          style={(feature) => {
            const district = districtName(feature as Feature<Geometry, GeoJsonProperties>);
            return {
              color: district === selectedDistrict ? "#ffffff" : "#d8e0d5",
              weight: district === selectedDistrict ? 3 : 1,
              fillColor: color(lookup.get(district)),
              fillOpacity: lookup.has(district) ? 0.76 : 0.28,
            };
          }}
        />
      </MapContainer>
      <div className="pointer-events-none absolute bottom-7 left-3 z-[1000] rounded-xl border border-white/15 bg-[#171b18e8] p-3 text-[10px] text-[#d9e0da] shadow-xl backdrop-blur">
        <strong className="block text-xs">District value</strong>
        <div className="mt-2 flex items-center gap-1">{COLORS.slice(1).map((value, index) => <i key={value} className="h-3 w-7" style={{ background: value }} title={`Class ${index + 1}`} />)}</div>
        <div className="mt-1 flex justify-between"><span>{min.toLocaleString(undefined, { maximumFractionDigits: 1 })}</span><span>{max.toLocaleString(undefined, { maximumFractionDigits: 1 })}</span></div>
      </div>
    </div>
  );
}
