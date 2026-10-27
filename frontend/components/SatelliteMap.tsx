"use client";

import { useEffect } from "react";
import { GeoJSON, ImageOverlay, MapContainer, useMap } from "react-leaflet";
import type { GeoJsonObject } from "geojson";
import { MapBaseLayer, MapStyleToggle, useMapStyle } from "./MapStyle";

function FitArea({ bbox }: { bbox?: [number, number, number, number] }) {
  const map = useMap();
  useEffect(() => {
    if (bbox) map.fitBounds([[bbox[1], bbox[0]], [bbox[3], bbox[2]]], { padding: [28, 28], maxZoom: 17 });
  }, [bbox, map]);
  return null;
}

export default function SatelliteMap({
  geometry,
  bbox,
  imageUrl,
}: {
  geometry?: GeoJsonObject | null;
  bbox?: [number, number, number, number];
  imageUrl?: string | null;
}) {
  const { style, setStyle } = useMapStyle();
  return (
    <div className="relative h-[430px] overflow-hidden rounded-2xl border border-[#405043] bg-[#202522]">
      <MapStyleToggle style={style} onChange={setStyle} />
      <MapContainer center={[-1.94, 29.87]} zoom={8} scrollWheelZoom>
        <MapBaseLayer style={style} />
        <FitArea bbox={bbox} />
        {imageUrl && bbox && <ImageOverlay url={imageUrl} bounds={[[bbox[1], bbox[0]], [bbox[3], bbox[2]]]} opacity={0.9} />}
        {geometry && <GeoJSON key={JSON.stringify(geometry)} data={geometry} style={{ color: "#e8f59a", weight: 3, fillColor: "#83b735", fillOpacity: imageUrl ? 0.03 : 0.2 }} />}
      </MapContainer>
    </div>
  );
}
