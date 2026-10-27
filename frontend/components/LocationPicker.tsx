"use client";

import { useEffect, useMemo, useState } from "react";
import { Check, ChevronDown, MapPinned, Search } from "lucide-react";

import { api } from "@/lib/api";

type Option = { code: number | string; name: string };

export type LocationSelection = {
  province?: Option;
  district?: Option;
  sector?: Option;
  cell?: Option;
  village?: Option;
};

function SearchSelect({
  label,
  options,
  value,
  disabled,
  loading,
  onChange,
}: {
  label: string;
  options: Option[];
  value?: Option;
  disabled?: boolean;
  loading?: boolean;
  onChange: (option: Option) => void;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const filtered = useMemo(() => {
    const term = query.trim().toLocaleLowerCase();
    return term
      ? options.filter((option) =>
          option.name.toLocaleLowerCase().includes(term),
        )
      : options;
  }, [options, query]);

  return (
    <div className="relative">
      <label className="text-xs uppercase tracking-[.14em] font-semibold text-[#9fa49f]">
        {label}
      </label>
      <button
        type="button"
        disabled={disabled || loading}
        onClick={() => setOpen(!open)}
        className="mt-1.5 w-full min-h-12 px-3.5 rounded-lg border border-[#494d4a] bg-[#262927] text-left flex items-center justify-between gap-3 disabled:opacity-45 focus:outline-none focus:ring-2 focus:ring-[#62a86b]"
      >
        <span className={value ? "text-white" : "text-[#858a86]"}>
          {loading
            ? "Loading…"
            : (value?.name ?? `Select ${label.toLocaleLowerCase()}`)}
        </span>
        <ChevronDown size={17} className="shrink-0 text-[#8f948f]" />
      </button>
      {open && !disabled && (
        <div className="absolute z-[1200] left-0 right-0 top-[74px] rounded-xl border border-[#4b4f4b] bg-[#242725] shadow-2xl overflow-hidden">
          <div className="p-2 border-b border-[#3e423e] relative">
            <Search
              size={16}
              className="absolute left-5 top-1/2 -translate-y-1/2 text-[#8e938f]"
            />
            <input
              autoFocus
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={`Search ${label.toLocaleLowerCase()}…`}
              className="w-full h-10 pl-10 pr-3 rounded-lg bg-[#191b1a] border border-[#414541] text-sm focus:outline-none focus:ring-1 focus:ring-[#62a86b]"
            />
          </div>
          <div className="max-h-56 overflow-y-auto p-1">
            {filtered.map((option) => (
              <button
                type="button"
                key={String(option.code)}
                onClick={() => {
                  onChange(option);
                  setOpen(false);
                  setQuery("");
                }}
                className="w-full px-3 py-2.5 rounded-lg text-left flex items-center justify-between hover:bg-[#303431]"
              >
                <span>{option.name}</span>
                {String(value?.code) === String(option.code) && (
                  <Check size={16} className="text-[#78c87e]" />
                )}
              </button>
            ))}
            {filtered.length === 0 && (
              <p className="p-4 text-sm text-[#919692] text-center">
                No matching location
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function LocationPicker({
  token,
  value,
  onChange,
  onCellChange,
}: {
  token: string;
  value: LocationSelection;
  onChange: (value: LocationSelection) => void;
  onCellChange?: (value: LocationSelection) => void;
}) {
  const [provinces, setProvinces] = useState<Option[]>([]);
  const [districts, setDistricts] = useState<Option[]>([]);
  const [sectors, setSectors] = useState<Option[]>([]);
  const [cells, setCells] = useState<Option[]>([]);
  const [villages, setVillages] = useState<Option[]>([]);
  const [loading, setLoading] = useState("");
  const [error, setError] = useState("");

  async function fetchOptions(
    path: string,
    level: string,
    setter: (options: Option[]) => void,
  ) {
    setLoading(level);
    setError("");
    try {
      setter(await api<Option[]>(path, {}, token));
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Locations unavailable",
      );
    } finally {
      setLoading("");
    }
  }

  useEffect(() => {
    void fetchOptions("/locations/provinces", "province", setProvinces);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  function chooseProvince(province: Option) {
    onChange({ province });
    setDistricts([]);
    setSectors([]);
    setCells([]);
    setVillages([]);
    void fetchOptions(
      `/locations/districts?province_code=${province.code}`,
      "district",
      setDistricts,
    );
  }
  function chooseDistrict(district: Option) {
    onChange({ province: value.province, district });
    setSectors([]);
    setCells([]);
    setVillages([]);
    void fetchOptions(
      `/locations/sectors?district_code=${district.code}`,
      "sector",
      setSectors,
    );
  }
  function chooseSector(sector: Option) {
    onChange({ province: value.province, district: value.district, sector });
    setCells([]);
    setVillages([]);
    void fetchOptions(
      `/locations/cells?sector_code=${encodeURIComponent(String(sector.code))}`,
      "cell",
      setCells,
    );
  }
  function chooseCell(cell: Option) {
    const next = {
      province: value.province,
      district: value.district,
      sector: value.sector,
      cell,
    };
    onChange(next);
    onCellChange?.(next);
    setVillages([]);
    void fetchOptions(
      `/locations/villages?cell_code=${cell.code}`,
      "village",
      setVillages,
    );
  }

  return (
    <div className="rounded-xl border border-[#414541] bg-[#242725] p-4">
      <div className="flex gap-3 items-start mb-4">
        <span className="w-9 h-9 shrink-0 rounded-lg grid place-items-center bg-[#2a4532] text-[#78c87e]">
          <MapPinned size={19} />
        </span>
        <div>
          <h4 className="font-semibold">Rwanda administrative location</h4>
          <p className="text-xs text-[#929793] mt-1">
            Choose each level from the imported administrative hierarchy. Typing
            is used only to search valid options.
          </p>
        </div>
      </div>
      <div className="grid sm:grid-cols-2 gap-3">
        <SearchSelect
          label="Province"
          options={provinces}
          value={value.province}
          loading={loading === "province"}
          onChange={chooseProvince}
        />
        <SearchSelect
          label="District"
          options={districts}
          value={value.district}
          disabled={!value.province}
          loading={loading === "district"}
          onChange={chooseDistrict}
        />
        <SearchSelect
          label="Sector"
          options={sectors}
          value={value.sector}
          disabled={!value.district}
          loading={loading === "sector"}
          onChange={chooseSector}
        />
        <SearchSelect
          label="Cell"
          options={cells}
          value={value.cell}
          disabled={!value.sector}
          loading={loading === "cell"}
          onChange={chooseCell}
        />
        <div className="sm:col-span-2">
          <SearchSelect
            label="Village"
            options={villages}
            value={value.village}
            disabled={!value.cell}
            loading={loading === "village"}
            onChange={(village) => onChange({ ...value, village })}
          />
        </div>
      </div>
      {error && (
        <p role="alert" className="mt-3 text-sm text-[#ff9f9f]">
          {error}
        </p>
      )}
    </div>
  );
}
