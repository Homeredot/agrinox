"use client";

import { useEffect } from "react";
import L from "leaflet";
import {
  MapContainer,
  Marker,
  Tooltip,
  useMap,
} from "react-leaflet";

import type { Farm } from "@/lib/api";
import { MapBaseLayer, MapStyleToggle, useMapStyle } from "./MapStyle";

const farmIcon = L.divIcon({
  className: "",
  html: '<div style="width:18px;height:18px;border:3px solid white;background:#45a66e;border-radius:50%;box-shadow:0 3px 12px #000a"></div>',
  iconSize: [18, 18],
  iconAnchor: [9, 9],
});

const selectedIcon = L.divIcon({
  className: "",
  html: '<div style="width:24px;height:24px;border:4px solid white;background:#6578e8;border-radius:50%;box-shadow:0 3px 14px #000b"></div>',
  iconSize: [24, 24],
  iconAnchor: [12, 12],
});

function FitFarms({ farms }: { farms: Farm[] }) {
  const map = useMap();

  useEffect(() => {
    const points = farms
      .filter((farm) => farm.latitude != null && farm.longitude != null)
      .map((farm) => [farm.latitude!, farm.longitude!] as [number, number]);
    if (points.length === 1) map.setView(points[0], 13);
    else if (points.length > 1)
      map.fitBounds(points, { padding: [42, 42], maxZoom: 13 });
    else map.setView([-1.94, 29.87], 8);
  }, [farms, map]);

  return null;
}

export default function FarmOverviewMap({
  farms,
  selectedId,
  onSelect,
}: {
  farms: Farm[];
  selectedId: number | null;
  onSelect: (farmId: number) => void;
}) {
  const { style, setStyle } = useMapStyle();
  const mappedFarms = farms.filter(
    (farm) => farm.latitude != null && farm.longitude != null,
  );

  return (
    <div className="relative h-[390px] overflow-hidden rounded-2xl border border-[#3b3e3b] bg-[#232523]">
      <MapStyleToggle style={style} onChange={setStyle} />
      <MapContainer center={[-1.94, 29.87]} zoom={8} scrollWheelZoom>
        <MapBaseLayer style={style} />
        <FitFarms farms={farms} />
        {mappedFarms.map((farm) => (
          <Marker
            key={farm.id}
            position={[farm.latitude!, farm.longitude!]}
            icon={farm.id === selectedId ? selectedIcon : farmIcon}
            eventHandlers={{ click: () => onSelect(farm.id) }}
          >
            <Tooltip direction="top" offset={[0, -10]}>
              <strong>{farm.name}</strong>
              <br />
              {farm.cell}, {farm.district}
            </Tooltip>
          </Marker>
        ))}
      </MapContainer>
      {mappedFarms.length === 0 && (
        <div className="pointer-events-none absolute inset-0 z-[500] grid place-items-center bg-[#1c211ed9] p-8 text-center">
          <div>
            <p className="font-semibold text-white">
              No farm points mapped yet
            </p>
            <p className="mt-1 max-w-xs text-sm text-[#aeb3af]">
              Add an exact map point when registering a farm to see it here.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
