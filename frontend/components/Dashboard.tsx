"use client";

import dynamic from "next/dynamic";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowLeft,
  CalendarDays,
  Check,
  ChevronDown,
  CircleUserRound,
  ChartNoAxesCombined,
  CloudSun,
  Cpu,
  Droplets,
  FlaskConical,
  Gauge,
  LandPlot,
  LayoutDashboard,
  LibraryBig,
  LogOut,
  Languages,
  MapPinned,
  MapPin,
  Menu,
  Pencil,
  Plus,
  Ruler,
  Search,
  ScanSearch,
  Satellite,
  Settings2,
  Sprout,
  Sun,
  Moon,
  Palette,
  Contrast,
  Waves,
  WalletCards,
  Trash2,
  Undo2,
  X,
} from "lucide-react";

import { api, CurrentUser, Farm, Field } from "@/lib/api";
import { copy, Language, message } from "@/lib/i18n";
import LocationPicker, { type LocationSelection } from "./LocationPicker";
import type { MapFocus, SearchResult } from "./MapPicker";
import WeatherDashboard from "./WeatherDashboard";
import DeviceManagement from "./DeviceManagement";
import SoilDashboard from "./SoilDashboard";
import KnowledgeBase from "./KnowledgeBase";
import CropPlanning from "./CropPlanning";
import IrrigationDashboard from "./IrrigationDashboard";
import PlantLens from "./PlantLens";
import SatelliteMonitoring from "./SatelliteMonitoring";
import FarmingCalendar from "./FarmingCalendar";
import FarmFinance from "./FarmFinance";
import SystemDashboard from "./SystemDashboard";
import NotificationCenter from "./NotificationCenter";
import NotificationsPage from "./NotificationsPage";
import ProfilePage from "./ProfilePage";
import SettingsPage from "./SettingsPage";
import FieldWaterSources from "./FieldWaterSources";
import SidebarLiveStatus from "./SidebarLiveStatus";
import UserAvatar from "./UserAvatar";
import BrandLogo from "./BrandLogo";
import { type AppTheme, useTheme } from "./ThemeProvider";

const MapPicker = dynamic(() => import("./MapPicker"), {
  ssr: false,
  loading: () => (
    <div className="h-[360px] rounded-xl bg-[#282b29] animate-pulse" />
  ),
});
const FarmOverviewMap = dynamic(() => import("./FarmOverviewMap"), {
  ssr: false,
  loading: () => (
    <div className="h-[390px] rounded-2xl bg-[#282b29] animate-pulse" />
  ),
});

const input =
  "w-full p-3.5 rounded-lg border border-[#494d4a] bg-[#262927] text-white placeholder:text-[#868b87] focus:outline-none focus:ring-2 focus:ring-[#62a86b]";

type DashboardView =
  | "home" | "portfolio" | "farm" | "weather" | "devices" | "soil"
  | "knowledge" | "planning" | "calendar" | "finance" | "irrigation"
  | "plant-lens" | "satellite" | "profile" | "settings" | "notifications";

const DASHBOARD_VIEWS = new Set<DashboardView>([
  "home", "portfolio", "farm", "weather", "devices", "soil", "knowledge",
  "planning", "calendar", "finance", "irrigation", "plant-lens", "satellite",
  "profile", "settings", "notifications",
]);

function readDashboardRoute(): { view: DashboardView; farmId: number | null } {
  if (typeof window === "undefined") return { view: "home", farmId: null };
  const params = new URLSearchParams(window.location.search);
  const requestedView = params.get("view") as DashboardView | null;
  const farmValue = Number(params.get("farm"));
  return {
    view: requestedView && DASHBOARD_VIEWS.has(requestedView) ? requestedView : "home",
    farmId: Number.isInteger(farmValue) && farmValue > 0 ? farmValue : null,
  };
}

export default function Dashboard({
  token,
  language,
  setLanguage,
  onLogout,
}: {
  token: string;
  language: Language;
  setLanguage: (language: Language) => void;
  onLogout: () => void;
}) {
  const t = copy[language];
  const { theme, setTheme } = useTheme();
  const [initialRoute] = useState(readDashboardRoute);
  const [farms, setFarms] = useState<Farm[]>([]);
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [selected, setSelected] = useState<number | null>(initialRoute.farmId);
  const [modal, setModal] = useState<"farm" | "field" | null>(null);
  const [editingFarm, setEditingFarm] = useState<Farm | null>(null);
  const [editingField, setEditingField] = useState<Field | null>(null);
  const [waterField, setWaterField] = useState<Field | null>(null);
  const [points, setPoints] = useState<[number, number][]>([]);
  const [geo, setGeo] = useState<Record<string, string | number | undefined>>(
    {},
  );
  const [location, setLocation] = useState<LocationSelection>({});
  const [cellFocus, setCellFocus] = useState<MapFocus | null>(null);
  const [cellFocusLoading, setCellFocusLoading] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [query, setQuery] = useState("");
  const [mobileNav, setMobileNav] = useState(false);
  const [accountMenu, setAccountMenu] = useState(false);
  const accountMenuRef = useRef<HTMLDivElement>(null);
  const [view, setView] = useState<DashboardView>(initialRoute.view);
  const farm = farms.find((item) => item.id === selected) ?? farms[0];

  async function load() {
    try {
      const data = await api<Farm[]>("/farms", {}, token);
      setFarms(data);
      setSelected((current) =>
        current && data.some((item) => item.id === current)
          ? current
          : data[0]?.id ?? null,
      );
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : "Failed to load",
      );
    }
  }

  useEffect(() => {
    void load();
    api<CurrentUser>("/auth/me", {}, token).then(setCurrentUser).catch(() => undefined);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    setCurrentUser((user) => user ? { ...user, preferred_language: language } : user);
  }, [language]);

  useEffect(() => {
    const url = new URL(window.location.href);
    if (view === "home") url.searchParams.delete("view");
    else url.searchParams.set("view", view);
    if (selected) url.searchParams.set("farm", String(selected));
    else url.searchParams.delete("farm");
    window.history.replaceState(window.history.state, "", `${url.pathname}${url.search}${url.hash}`);
  }, [selected, view]);

  useEffect(() => {
    if (!accountMenu) return;
    const closeOutside = (event: MouseEvent) => {
      if (!accountMenuRef.current?.contains(event.target as Node)) setAccountMenu(false);
    };
    const closeOnEscape = (event: KeyboardEvent) => { if (event.key === "Escape") setAccountMenu(false); };
    document.addEventListener("mousedown", closeOutside);
    document.addEventListener("keydown", closeOnEscape);
    return () => { document.removeEventListener("mousedown", closeOutside); document.removeEventListener("keydown", closeOnEscape); };
  }, [accountMenu]);

  async function pick(latitude: number, longitude: number) {
    setGeo((current) => ({ ...current, latitude, longitude }));
    try {
      setGeo(
        await api<Record<string, string | number | undefined>>(
          `/locations/reverse?latitude=${latitude}&longitude=${longitude}`,
          {},
          token,
        ),
      );
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Location lookup failed",
      );
    }
  }

  function applySearchResult(result: SearchResult) {
    setGeo({ ...result });
  }
  function changeLocation(next: LocationSelection) {
    if (String(next.cell?.code ?? "") !== String(location.cell?.code ?? ""))
      setCellFocus(null);
    setLocation(next);
  }
  async function focusSelectedCell(next: LocationSelection) {
    if (!next.cell) return;
    setCellFocusLoading(true);
    try {
      setCellFocus(
        await api<MapFocus>(
          `/locations/cells/${next.cell.code}/map-focus`,
          {},
          token,
        ),
      );
    } catch (requestError) {
      setCellFocus(null);
      setError(
        requestError instanceof Error
          ? `${requestError.message}. You can still search or click the map manually.`
          : "Cell map view unavailable",
      );
    } finally {
      setCellFocusLoading(false);
    }
  }

  const polygon = useMemo(
    () =>
      points.length >= 3
        ? {
            type: "Polygon",
            coordinates: [
              [
                ...points.map(([latitude, longitude]) => [longitude, latitude]),
                [points[0][1], points[0][0]],
              ],
            ],
          }
        : null,
    [points],
  );

  const visibleFields = useMemo(() => {
    if (!farm) return [];
    const term = query.trim().toLocaleLowerCase();
    if (!term) return farm.fields;
    return farm.fields.filter((field) =>
      `${field.name} ${field.crop_note ?? ""} ${field.area_source}`
        .toLocaleLowerCase()
        .includes(term),
    );
  }, [farm, query]);

  const visibleFarms = useMemo(() => {
    const term = query.trim().toLocaleLowerCase();
    if (!term) return farms;
    return farms.filter((item) =>
      `${item.name} ${item.province} ${item.district} ${item.sector} ${item.cell} ${item.village} ${item.fields.map((field) => `${field.name} ${field.crop_note ?? ""}`).join(" ")}`
        .toLocaleLowerCase()
        .includes(term),
    );
  }, [farms, query]);

  const totalArea =
    farm?.fields.reduce((sum, field) => sum + field.area_m2, 0) ?? 0;
  const portfolioFields = farms.flatMap((item) => item.fields);
  const portfolioArea = portfolioFields.reduce(
    (sum, field) => sum + field.area_m2,
    0,
  );
  const mappedFarms = farms.filter(
    (item) => item.latitude != null && item.longitude != null,
  ).length;
  const districts = new Set(farms.map((item) => item.district)).size;
  const provinces = new Set(farms.map((item) => item.province)).size;

  function enterFarm(farmId: number) {
    setSelected(farmId);
    setView("farm");
    setQuery("");
    setMobileNav(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function showPortfolio() {
    setView("portfolio");
    setQuery("");
    setMobileNav(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function showHome() {
    setView("home");
    setQuery("");
    setMobileNav(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function openDashboardTarget(target: "farms" | "weather" | "devices" | "soil" | "planning" | "calendar" | "finance" | "irrigation" | "plant-lens" | "satellite") {
    ({ farms: showPortfolio, weather: showWeather, devices: showDevices, soil: showSoil, planning: showCropPlanning, calendar: showCalendar, finance: showFinance, irrigation: showIrrigation, "plant-lens": showPlantLens, satellite: showSatellite })[target]();
  }

  function showWeather() {
    setView("weather");
    setQuery("");
    setMobileNav(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function showDevices() {
    setView("devices");
    setQuery("");
    setMobileNav(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function showSoil() {
    setView("soil");
    setQuery("");
    setMobileNav(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function showKnowledge() {
    setView("knowledge");
    setQuery("");
    setMobileNav(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function showCropPlanning() {
    setView("planning");
    setQuery("");
    setMobileNav(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function showCalendar() {
    setView("calendar");
    setQuery("");
    setMobileNav(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function showFinance() {
    setView("finance");
    setQuery("");
    setMobileNav(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function showIrrigation() {
    setView("irrigation");
    setQuery("");
    setMobileNav(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function showPlantLens() {
    setView("plant-lens");
    setQuery("");
    setMobileNav(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function showSatellite() {
    setView("satellite");
    setQuery("");
    setMobileNav(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function showProfile() {
    setAccountMenu(false);
    setView("profile");
    setQuery("");
    setMobileNav(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function showSettings() {
    setView("settings");
    setQuery("");
    setMobileNav(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function showNotifications() {
    setView("notifications");
    setQuery("");
    setMobileNav(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function saveFarm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!location.village) {
      setError(
        "Select the complete Province, District, Sector, Cell and Village hierarchy.",
      );
      return;
    }
    setBusy(true);
    setError("");
    const data = Object.fromEntries(new FormData(event.currentTarget));
    try {
      await api(
        editingFarm ? `/farms/${editingFarm.id}` : "/farms",
        {
          method: editingFarm ? "PUT" : "POST",
          body: JSON.stringify({
            ...data,
            latitude: geo.latitude || null,
            longitude: geo.longitude || null,
          }),
        },
        token,
      );
      setModal(null);
      setEditingFarm(null);
      setPoints([]);
      setGeo({});
      await load();
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : "Could not save",
      );
    } finally {
      setBusy(false);
    }
  }

  async function saveField(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!farm) return;
    setBusy(true);
    setError("");
    const raw = Object.fromEntries(new FormData(event.currentTarget));
    const data: Record<string, string | number> = {};
    for (const [key, value] of Object.entries(raw)) data[key] = String(value);
    for (const key of ["side_a", "side_b", "side_c", "side_d"])
      if (data[key]) data[key] = Number(data[key]);
    try {
      await api(
        editingField
          ? `/farms/${farm.id}/fields/${editingField.id}`
          : `/farms/${farm.id}/fields`,
        {
          method: editingField ? "PUT" : "POST",
          body: JSON.stringify({ ...data, boundary_geojson: polygon }),
        },
        token,
      );
      setModal(null);
      setEditingField(null);
      setPoints([]);
      await load();
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : "Could not save",
      );
    } finally {
      setBusy(false);
    }
  }

  async function remove(path: string) {
    if (!confirm("Delete this record?")) return;
    await api(path, { method: "DELETE" }, token);
    await load();
  }

  const openFarmModal = () => {
    setEditingFarm(null);
    setEditingField(null);
    setModal("farm");
    setPoints([]);
    setGeo({});
    setLocation({});
    setCellFocus(null);
  };
  const openFarmEditModal = (item: Farm) => {
    setEditingFarm(item);
    setEditingField(null);
    setModal("farm");
    setPoints(
      item.latitude != null && item.longitude != null
        ? [[item.latitude, item.longitude]]
        : [],
    );
    setGeo({ latitude: item.latitude ?? undefined, longitude: item.longitude ?? undefined });
    setLocation({
      province: item.province_code != null ? { code: item.province_code, name: item.province } : undefined,
      district: item.district_code != null ? { code: item.district_code, name: item.district } : undefined,
      sector: item.sector_code != null ? { code: item.sector_code, name: item.sector } : undefined,
      cell: item.cell_code != null ? { code: item.cell_code, name: item.cell } : undefined,
      village: item.village_code != null ? { code: item.village_code, name: item.village } : undefined,
    });
    setCellFocus(null);
  };
  const openFieldModal = () => {
    if (farm) {
      setEditingField(null);
      setEditingFarm(null);
      setModal("field");
      setPoints([]);
    }
  };
  const openFieldEditModal = (field: Field) => {
    setEditingField(field);
    setEditingFarm(null);
    setModal("field");
    try {
      const boundary = field.boundary_geojson ? JSON.parse(field.boundary_geojson) : null;
      const coordinates = boundary?.type === "Polygon" ? boundary.coordinates?.[0] : null;
      setPoints(
        Array.isArray(coordinates)
          ? coordinates.slice(0, -1).map(([longitude, latitude]: [number, number]) => [latitude, longitude] as [number, number])
          : [],
      );
    } catch {
      setPoints([]);
    }
  };

  return (
    <div className="dark-shell min-h-screen bg-[#191b1a] text-[#f5f7f5]">
      <header className="fixed top-0 left-0 right-0 z-[1050] h-16 bg-[#1d1f1e] border-b border-[#303330] flex items-center">
        <div className="flex w-full min-w-0 items-center gap-2 px-3 sm:gap-4 sm:px-4">
          <button
            onClick={() => setMobileNav(!mobileNav)}
            className="hidden shrink-0 rounded-lg p-2 hover:bg-[#2b2e2c] sm:block lg:hidden"
            aria-label="Open navigation"
          >
            <Menu size={21} />
          </button>
          <div className="flex min-w-0 shrink-0 sm:w-[180px] lg:w-[245px]">
            <BrandLogo className="[&>span:last-child]:hidden min-[390px]:[&>span:last-child]:inline" markClassName="h-9 w-9"/>
          </div>
          <div className="relative mx-auto hidden max-w-xl flex-1 md:block">
            <Search
              size={18}
              className="absolute left-4 top-1/2 -translate-y-1/2 text-[#8d918e]"
            />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              disabled={
                view === "home" || view === "weather" || view === "devices" || view === "soil" || view === "knowledge" || view === "planning" || view === "calendar" || view === "finance" || view === "irrigation" || view === "plant-lens" || view === "satellite" || view === "profile" || view === "settings" || view === "notifications"
              }
              placeholder={
                view === "home"
                  ? "Your farm dashboard shows what needs attention"
                  : view === "portfolio"
                  ? "Search farms or locations"
                  : view === "farm"
                    ? "Search fields in this farm"
                    : view === "weather"
                      ? "Weather uses the selected farm location"
                      : view === "devices"
                        ? "Device sensors are searched inside Device Management"
                      : view === "satellite"
                        ? "Satellite monitoring uses a mapped field or Rwanda location search"
                      : view === "profile"
                        ? t.profileSearch
                      : view === "settings"
                        ? t.settingsSearch
                      : view === "notifications"
                        ? "Review recent farm alerts and activity"
                      : view === "soil"
                        ? "Soil measurements are filtered by field"
                        : view === "knowledge"
                          ? "Search inside the agricultural knowledge library"
                          : view === "planning" ? "Crop planning reuses your saved farm and field data" : view === "calendar" ? "Plan and track field work inside the Smart Farming Calendar" : view === "finance" ? "Calculate farm profit and record actual RWF transactions" : view === "irrigation" ? "Irrigation safety and sensor decisions" : "Plant photo screening is available inside Plant Lens"
              }
              className="w-full h-10 rounded-full bg-[#292c2a] border border-transparent pl-11 pr-4 text-sm text-white placeholder:text-[#9b9f9c] focus:outline-none focus:border-[#5b8f62] disabled:opacity-60"
            />
          </div>
          <div className="ml-auto flex shrink-0 items-center gap-1.5 sm:gap-2">
            <NotificationCenter token={token} onViewAll={showNotifications} />
            <div ref={accountMenuRef} className="relative">
              <button onClick={() => setAccountMenu((open) => !open)} aria-expanded={accountMenu} aria-haspopup="menu" aria-label={message(language, "account.menu")} className={`flex h-11 items-center gap-2 rounded-2xl border px-1.5 pr-2 transition ${accountMenu || view === "profile" ? "border-[#79b97b] bg-[#304333]" : "border-[#454945] hover:bg-[#292c2a]"}`}>
                {currentUser ? <UserAvatar user={currentUser} token={token}/> : <span className="grid h-9 w-9 place-items-center"><CircleUserRound size={20}/></span>}
                <span className="hidden max-w-28 truncate text-left text-sm font-semibold xl:block">{currentUser?.full_name || t.profile}</span>
                <ChevronDown size={15} className={`text-[#a7afa9] transition ${accountMenu ? "rotate-180" : ""}`}/>
              </button>

              {accountMenu && <div role="menu" className="account-menu absolute right-0 top-[calc(100%+10px)] z-[1100] max-h-[calc(100dvh-5rem)] w-[min(22rem,calc(100vw-1.5rem))] overflow-y-auto rounded-3xl border border-[#454d47] bg-[#202421] p-2 shadow-2xl shadow-black/40">
                <div className="flex items-center gap-3 rounded-2xl bg-[#292e2a] p-3">
                  {currentUser ? <UserAvatar user={currentUser} token={token} size="medium"/> : <CircleUserRound size={28}/>}<div className="min-w-0"><strong className="block truncate text-sm">{currentUser?.full_name || t.profile}</strong><span className="block truncate text-xs text-[#929c94]">{currentUser?.email}</span></div>
                </div>
                <button role="menuitem" onClick={showProfile} className="mt-2 flex min-h-11 w-full items-center gap-3 rounded-xl px-3 text-left text-sm font-semibold hover:bg-[#2d332f]"><CircleUserRound size={18} className="text-[#8fd28b]"/>{t.profile}</button>

                <div className="my-2 border-t border-[#373d39]"/>
                <div className="px-3 py-1 text-[11px] font-bold uppercase tracking-[.14em] text-[#7f8981]"><Languages className="mr-2 inline" size={14}/>{message(language, "settings.language")}</div>
                <div className="mt-1 grid grid-cols-2 gap-1 p-1">{(["en", "rw"] as Language[]).map((item) => <button role="menuitemradio" aria-checked={language === item} key={item} onClick={() => { setLanguage(item); setAccountMenu(false); }} className={`flex min-h-10 items-center justify-between rounded-xl px-3 text-sm ${language === item ? "bg-[#304333] text-[#aee1a6]" : "hover:bg-[#2d332f]"}`}><span>{item === "en" ? message(language, "language.english") : message(language, "language.kinyarwanda")}</span>{language === item && <Check size={16}/>}</button>)}</div>

                <div className="my-2 border-t border-[#373d39]"/>
                <div className="px-3 py-1 text-[11px] font-bold uppercase tracking-[.14em] text-[#7f8981]"><Palette className="mr-2 inline" size={14}/>{message(language, "settings.appearance")}</div>
                <div className="mt-1 grid grid-cols-4 gap-1 p-1">{([
                  ["grey", Palette, "settings.themeGrey"], ["dark", Moon, "settings.themeDark"], ["light", Sun, "settings.themeLight"], ["contrast", Contrast, "settings.themeContrast"],
                ] as const).map(([value, Icon, label]) => <button role="menuitemradio" aria-checked={theme === value} key={value} title={message(language, label)} onClick={() => setTheme(value as AppTheme)} className={`relative flex min-h-14 flex-col items-center justify-center gap-1 rounded-xl text-[10px] ${theme === value ? "bg-[#304333] text-[#aee1a6]" : "hover:bg-[#2d332f]"}`}><Icon size={17}/><span>{message(language, label)}</span>{theme === value && <span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-[#8fd28b]"/>}</button>)}</div>

                <div className="my-2 border-t border-[#373d39]"/>
                <button role="menuitem" onClick={() => { setAccountMenu(false); onLogout(); }} className="flex min-h-11 w-full items-center gap-3 rounded-xl px-3 text-left text-sm font-semibold text-[#efaa9d] hover:bg-[#3b2826]"><LogOut size={18}/>{t.logout}</button>
              </div>}
            </div>
          </div>
        </div>
      </header>

      <aside
        className={`${mobileNav ? "translate-x-0" : "-translate-x-full"} fixed bottom-0 left-0 top-16 z-[1040] flex w-[min(88vw,320px)] flex-col border-r border-[#303330] bg-[#1d1f1e] px-3 py-5 transition-transform lg:w-[260px] lg:translate-x-0`}
      >
        <nav className="min-h-0 flex-1 space-y-1 overflow-y-auto pr-1 text-sm">
          <div className="pb-2 px-3 text-xs uppercase tracking-[.16em] font-bold text-[#8b908c]">
            {t.tools}
          </div>
          <button
            onClick={showHome}
            className={`w-full h-10 px-3 flex items-center gap-3 rounded-lg ${view === "home" ? "bg-[#2a382d] text-white" : "text-[#d4d8d5] hover:bg-[#282b29]"}`}
          >
            <Gauge size={18} className={view === "home" ? "text-[#8fd28b]" : ""} />
            Dashboard
          </button>
          <button
            onClick={showPortfolio}
            className={`w-full h-10 px-3 flex items-center gap-3 rounded-lg ${view === "portfolio" || view === "farm" ? "bg-[#2a302c] text-white" : "text-[#d4d8d5] hover:bg-[#282b29]"}`}
          >
            <LayoutDashboard size={18} className="text-[#7acb78]" />
            My Farm
          </button>
          <button
            onClick={showWeather}
            className={`w-full h-10 px-3 flex items-center gap-3 rounded-lg ${view === "weather" ? "bg-[#2a3042] text-white" : "text-[#d4d8d5] hover:bg-[#282b29]"}`}
          >
            <CloudSun
              size={18}
              className={view === "weather" ? "text-[#91a4ff]" : ""}
            />
            Weather Intelligence
          </button>
          <button
            onClick={showDevices}
            className={`w-full h-10 px-3 flex items-center gap-3 rounded-lg ${view === "devices" ? "bg-[#27362d] text-white" : "text-[#d4d8d5] hover:bg-[#282b29]"}`}
          >
            <Cpu
              size={18}
              className={view === "devices" ? "text-[#78c87e]" : ""}
            />
            Device Management
          </button>
          <button
            onClick={showSoil}
            className={`w-full h-10 px-3 flex items-center gap-3 rounded-lg ${view === "soil" ? "bg-[#343a25] text-white" : "text-[#d4d8d5] hover:bg-[#282b29]"}`}
          >
            <FlaskConical
              size={18}
              className={view === "soil" ? "text-[#c1da6f]" : ""}
            />
            Soil Quality &amp; Advisory
          </button>
          <button
            onClick={showKnowledge}
            className={`w-full h-10 px-3 flex items-center gap-3 rounded-lg ${view === "knowledge" ? "bg-[#3a3325] text-white" : "text-[#d4d8d5] hover:bg-[#282b29]"}`}
          >
            <LibraryBig
              size={18}
              className={view === "knowledge" ? "text-[#e1bd68]" : ""}
            />
            Agricultural Knowledge
          </button>
          <button
            onClick={showCropPlanning}
            className={`w-full h-10 px-3 flex items-center gap-3 rounded-lg ${view === "planning" ? "bg-[#303824] text-white" : "text-[#d4d8d5] hover:bg-[#282b29]"}`}
          >
            <ChartNoAxesCombined
              size={18}
              className={view === "planning" ? "text-[#acd675]" : ""}
            />
            Crop Planning &amp; Yield
          </button>
          <button
            onClick={showCalendar}
            className={`w-full h-10 px-3 flex items-center gap-3 rounded-lg ${view === "calendar" ? "bg-[#2e3b29] text-white" : "text-[#d4d8d5] hover:bg-[#282b29]"}`}
          >
            <CalendarDays size={18} className={view === "calendar" ? "text-[#b6d975]" : ""} />
            Smart Farming Calendar
          </button>
          <button
            onClick={showFinance}
            className={`w-full h-10 px-3 flex items-center gap-3 rounded-lg ${view === "finance" ? "bg-[#3b3525] text-white" : "text-[#d4d8d5] hover:bg-[#282b29]"}`}
          >
            <WalletCards size={18} className={view === "finance" ? "text-[#dfbd68]" : ""} />
            Farm Profit &amp; Expenses
          </button>
          <button
            onClick={showIrrigation}
            className={`w-full h-10 px-3 flex items-center gap-3 rounded-lg ${view === "irrigation" ? "bg-[#243a36] text-white" : "text-[#d4d8d5] hover:bg-[#282b29]"}`}
          >
            <Waves size={18} className={view === "irrigation" ? "text-[#74c6b0]" : ""} />
            Smart Irrigation
          </button>
          <button
            onClick={showPlantLens}
            className={`w-full h-10 px-3 flex items-center gap-3 rounded-lg ${view === "plant-lens" ? "bg-[#343927] text-white" : "text-[#d4d8d5] hover:bg-[#282b29]"}`}
          >
            <ScanSearch size={18} className={view === "plant-lens" ? "text-[#a6d276]" : ""} />
            Plant Lens
          </button>
          <button
            onClick={showSatellite}
            className={`w-full h-10 px-3 flex items-center gap-3 rounded-lg ${view === "satellite" ? "bg-[#2e3c29] text-white" : "text-[#d4d8d5] hover:bg-[#282b29]"}`}
          >
            <Satellite size={18} className={view === "satellite" ? "text-[#b6d96f]" : ""} />
            Satellite Monitoring
          </button>
        </nav>
        <button onClick={showSettings} className={`mb-3 mt-3 h-10 w-full rounded-lg px-3 flex items-center gap-3 text-sm ${view === "settings" ? "bg-[#303632] text-white" : "text-[#d4d8d5] hover:bg-[#282b29]"}`}>
          <Settings2 size={18} className={view === "settings" ? "text-[#8fd28b]" : ""}/>
          {t.settings}
        </button>
        <SidebarLiveStatus token={token}/>
      </aside>

      {mobileNav && (
        <button
          aria-label="Close navigation"
          onClick={() => setMobileNav(false)}
          className="fixed inset-0 z-[1030] bg-black/60 lg:hidden"
        />
      )}

      <nav className="mobile-app-nav fixed inset-x-2 bottom-2 z-[1020] grid grid-cols-5 rounded-[1.35rem] border border-[#414842] bg-[#1d1f1e]/95 px-1.5 pt-1.5 shadow-2xl shadow-black/40 backdrop-blur-xl sm:hidden" aria-label={language === "rw" ? "Kugendagenda muri porogaramu" : "Mobile app navigation"}>
        <button type="button" data-compact-control="true" onClick={showHome} aria-current={view === "home" ? "page" : undefined} className={`mobile-app-tab ${view === "home" ? "mobile-app-tab-active" : ""}`}><Gauge size={20}/><span>{language === "rw" ? "Ahabanza" : "Home"}</span></button>
        <button type="button" data-compact-control="true" onClick={showPortfolio} aria-current={view === "portfolio" || view === "farm" ? "page" : undefined} className={`mobile-app-tab ${view === "portfolio" || view === "farm" ? "mobile-app-tab-active" : ""}`}><LayoutDashboard size={20}/><span>{language === "rw" ? "Imirima" : "My Farm"}</span></button>
        <button type="button" data-compact-control="true" onClick={showWeather} aria-current={view === "weather" ? "page" : undefined} className={`mobile-app-tab ${view === "weather" ? "mobile-app-tab-active" : ""}`}><CloudSun size={20}/><span>{language === "rw" ? "Ikirere" : "Weather"}</span></button>
        <button type="button" data-compact-control="true" onClick={showCalendar} aria-current={view === "calendar" ? "page" : undefined} className={`mobile-app-tab ${view === "calendar" ? "mobile-app-tab-active" : ""}`}><CalendarDays size={20}/><span>{language === "rw" ? "Kalendari" : "Calendar"}</span></button>
        <button type="button" data-compact-control="true" onClick={() => setMobileNav(true)} aria-expanded={mobileNav} className={`mobile-app-tab ${!["home", "portfolio", "farm", "weather", "calendar"].includes(view) ? "mobile-app-tab-active" : ""}`}><Menu size={20}/><span>{language === "rw" ? "Ibindi" : "More"}</span></button>
      </nav>

      <main className="min-h-screen min-w-0 pb-24 pt-16 sm:pb-0 lg:ml-[260px]">
        <div className="mx-auto w-full max-w-[1180px] min-w-0 px-3 py-4 sm:px-6 sm:py-7 lg:px-8 lg:py-9">
          {view === "home" ? (
            <SystemDashboard farms={farms} token={token} onOpen={openDashboardTarget} />
          ) : view === "weather" ? (
            <WeatherDashboard farms={farms} token={token} language={language} />
          ) : view === "devices" ? (
            <DeviceManagement farms={farms} token={token} />
          ) : view === "soil" ? (
            <SoilDashboard farms={farms} token={token} />
          ) : view === "knowledge" ? (
            <KnowledgeBase token={token} language={language} />
          ) : view === "planning" ? (
            <CropPlanning farms={farms} token={token} onOpenCalendar={showCalendar} />
          ) : view === "calendar" ? (
            <FarmingCalendar farms={farms} token={token} />
          ) : view === "finance" ? (
            <FarmFinance farms={farms} token={token} />
          ) : view === "irrigation" ? (
            <IrrigationDashboard farms={farms} token={token} />
          ) : view === "plant-lens" ? (
            <PlantLens token={token} />
          ) : view === "satellite" ? (
            <SatelliteMonitoring farms={farms} token={token} />
          ) : view === "profile" ? (
            <ProfilePage token={token} user={currentUser} farms={farms} onUpdated={setCurrentUser} />
          ) : view === "settings" ? (
            <SettingsPage token={token} language={language} setLanguage={setLanguage} />
          ) : view === "notifications" ? (
            <NotificationsPage token={token} />
          ) : (
            <>
              <div className="flex flex-wrap items-end justify-between gap-4">
                <div>
                  <h1 className="text-2xl font-semibold sm:text-4xl">
                    {view === "portfolio" ? "My farms" : farm?.name}
                  </h1>
                  <p className="mobile-secondary mt-2 max-w-2xl text-[#aeb3af]">
                    {view === "portfolio"
                      ? "Choose a farm to view its fields and records."
                      : farm
                        ? `${farm.village} · ${farm.cell} · ${farm.sector} · ${farm.district}`
                        : t.noFarms}
                  </p>
                </div>
                {view === "portfolio" ? (
                  <button
                    onClick={openFarmModal}
                    className="h-11 px-5 rounded-full bg-[#2f8059] hover:bg-[#399466] font-semibold flex items-center gap-2"
                  >
                    <Plus size={18} />
                    {t.addFarm}
                  </button>
                ) : (
                  <button
                    onClick={showPortfolio}
                    className="h-11 px-5 rounded-full border border-[#4b504c] hover:bg-[#292c2a] font-semibold flex items-center gap-2"
                  >
                    <ArrowLeft size={18} />
                    All farms
                  </button>
                )}
              </div>

              {error && (
                <div
                  role="alert"
                  className="mt-5 rounded-lg bg-[#3b2020] border border-[#6e3333] p-4 text-[#ffb9b9] flex justify-between"
                >
                  {error}
                  <button onClick={() => setError("")}>
                    <X size={18} />
                  </button>
                </div>
              )}

              {view === "portfolio" ? (
                <>
                  <section className="mt-8 grid grid-cols-1 gap-3 min-[390px]:grid-cols-2 xl:grid-cols-4">
                    {[
                      {
                        label: "Total farms",
                        value: farms.length,
                        note: "Registered portfolio",
                        icon: Sprout,
                        color: "#78c87e",
                      },
                      {
                        label: "Districts",
                        value: districts,
                        note: "Farm locations",
                        icon: MapPin,
                        color: "#8294f2",
                      },
                      {
                        label: "Recorded land",
                        value: `${(portfolioArea / 10000).toFixed(2)} ha`,
                        note: "Portfolio total",
                        icon: LandPlot,
                        color: "#e2b560",
                      },
                      {
                        label: "Mapped farms",
                        value: `${mappedFarms}/${farms.length}`,
                        note: `${provinces} provinces`,
                        icon: MapPinned,
                        color: "#b78bd1",
                      },
                    ].map((stat) => (
                      <article
                        key={stat.label}
                        className="rounded-xl border border-[#3b3e3b] bg-[#232523] p-4 sm:p-5"
                      >
                        <div className="flex items-center justify-between gap-3">
                          <p className="text-xs uppercase tracking-wider text-[#969b97]">
                            {stat.label}
                          </p>
                          <stat.icon size={19} style={{ color: stat.color }} />
                        </div>
                        <strong className="mt-3 block text-2xl sm:text-3xl">
                          {stat.value}
                        </strong>
                        <p className="mt-1 text-xs text-[#858b86]">
                          {stat.note}
                        </p>
                      </article>
                    ))}
                  </section>

                  <section className="mt-8 grid xl:grid-cols-[1.45fr_.9fr] gap-5">
                    <div>
                      <div className="mb-3 flex items-end justify-between gap-4">
                        <div>
                          <h2 className="text-xl font-semibold">Farm map</h2>
                          <p className="mt-1 text-sm text-[#969b97]">
                            Select a marker to enter that farm.
                          </p>
                        </div>
                        <span className="text-xs text-[#969b97]">
                          {mappedFarms} mapped
                        </span>
                      </div>
                      <FarmOverviewMap
                        farms={visibleFarms}
                        selectedId={null}
                        onSelect={enterFarm}
                      />
                    </div>
                    <div>
                      <div className="mb-3">
                        <h2 className="text-xl font-semibold">Farms</h2>
                        <p className="mt-1 text-sm text-[#969b97]">
                          Choose a farm to view its workspace
                        </p>
                      </div>
                      <div className="h-[390px] overflow-y-auto rounded-2xl border border-[#3b3e3b] bg-[#232523] p-2">
                        {visibleFarms.length === 0 ? (
                          <div className="grid h-full place-items-center p-8 text-center text-[#8f9490]">
                            <div>
                              <LandPlot className="mx-auto mb-3" size={30} />
                              <p>
                                {query
                                  ? "No farms match your search."
                                  : t.noFarms}
                              </p>
                            </div>
                          </div>
                        ) : (
                          visibleFarms.map((item) => (
                            <article
                              key={item.id}
                              className="mb-2 flex w-full items-center gap-2 rounded-xl border border-transparent bg-[#292c2a] p-2 transition last:mb-0 hover:border-[#54725b] hover:bg-[#29352d]"
                            >
                              <button onClick={() => enterFarm(item.id)} className="flex min-w-0 flex-1 items-center gap-3 p-2 text-left">
                                <span className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-[#343936] text-[#86c88c]">
                                  <LandPlot size={19} />
                                </span>
                                <span className="min-w-0 flex-1">
                                  <strong className="block truncate">
                                    {item.name}
                                  </strong>
                                  <small className="mt-1 block truncate text-[#9ea39f]">
                                    {item.cell}, {item.district}
                                  </small>
                                </span>
                                <span className="rounded-full border border-[#4b504c] px-3 py-1.5 text-xs text-[#cbd0cc]">
                                  Open
                                </span>
                              </button>
                              <button onClick={() => openFarmEditModal(item)} aria-label={`${t.edit} ${item.name}`} title={t.edit} className="grid h-9 w-9 shrink-0 place-items-center rounded-lg text-[#d7bd75] hover:bg-[#473d24]"><Pencil size={16}/></button>
                            </article>
                          ))
                        )}
                      </div>
                    </div>
                  </section>
                </>
              ) : farm ? (
                <>
                  <section
                    id="farm-workspace"
                    className="mt-8"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-4">
                      <div>
                        <p className="text-xs uppercase tracking-widest text-[#78c87e]">
                          {farm.name}
                        </p>
                        <h2 className="mt-1 text-xl font-semibold">
                          Fields
                        </h2>
                        <p className="text-sm text-[#969b97] mt-1">
                          Manage field measurements and irrigation water sources.
                        </p>
                      </div>
                      <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto">
                        <span className="min-h-11 flex-1 rounded-full border border-[#454945] px-3 py-2 text-center text-sm text-[#b9beba] sm:flex-none">
                          {farm.fields.length} fields ·{" "}
                          {(totalArea / 10000).toFixed(3)} ha
                        </span>
                        <button
                          onClick={openFieldModal}
                          className="flex min-h-11 flex-1 items-center justify-center gap-2 rounded-full bg-[#2f8059] px-4 py-2 text-sm font-semibold hover:bg-[#379265] sm:flex-none"
                        >
                          <Plus size={17} />
                          {t.addField}
                        </button>
                      </div>
                    </div>
                    <div className="mt-4 rounded-xl border border-[#3b3e3b] bg-[#232523] overflow-hidden">
                      <div className="grid grid-cols-[minmax(180px,1.8fr)_minmax(100px,.8fr)_minmax(120px,1fr)_minmax(120px,1.2fr)_132px] gap-4 px-5 py-3 border-b border-[#3b3e3b] text-xs font-semibold text-[#a8ada9] max-md:hidden">
                        <span>Name</span>
                        <span>Area</span>
                        <span>Measurement</span>
                        <span>Location</span>
                        <span />
                      </div>
                      {visibleFields.length === 0 && (
                        <div className="p-12 text-center text-[#8f9490]">
                          <Ruler className="mx-auto mb-3" size={28} />
                          {query
                            ? "No fields match your search."
                            : "No fields added yet."}
                        </div>
                      )}
                      {visibleFields.map((field) => (
                        <article
                          key={field.id}
                          className="grid md:grid-cols-[minmax(180px,1.8fr)_minmax(100px,.8fr)_minmax(120px,1fr)_minmax(120px,1.2fr)_132px] gap-3 md:gap-4 items-center px-5 py-4 border-b border-[#353835] last:border-b-0 hover:bg-[#282b29]"
                        >
                          <div className="flex items-center gap-3">
                            <span className="w-9 h-9 shrink-0 grid place-items-center rounded-lg bg-[#2b4432] text-[#78c87e]">
                              <LandPlot size={18} />
                            </span>
                            <span>
                              <strong className="block">{field.name}</strong>
                              <small className="text-[#8f9490]">
                                {field.crop_note || "Crop not recorded"}
                              </small>
                            </span>
                          </div>
                          <div>
                            <span className="md:hidden text-xs text-[#8f9490] mr-2">
                              Area
                            </span>
                            <strong>
                              {(field.area_m2 / 10000).toFixed(3)}
                            </strong>{" "}
                            <span className="text-xs text-[#a7aca8]">ha</span>
                          </div>
                          <div>
                            <span className="md:hidden text-xs text-[#8f9490] mr-2">
                              Method
                            </span>
                            <span className="inline-flex rounded-full border border-[#4a4e4a] px-2.5 py-1 text-xs">
                              {field.area_source === "map"
                                ? t.mapped
                                : t.estimated}
                            </span>
                          </div>
                          <div className="text-sm text-[#b3b8b4] truncate">
                            <MapPin size={14} className="inline mr-1" />
                            {farm.sector}, {farm.district}
                          </div>
                          <div className="flex items-center gap-1">
                            <button onClick={() => setWaterField(field)} aria-label={t.waterSources} title={t.waterSources} className="w-9 h-9 grid place-items-center rounded-lg text-[#77bcd7] hover:bg-[#263c45]"><Droplets size={18}/></button>
                            <button onClick={() => openFieldEditModal(field)} aria-label={`${t.edit} ${field.name}`} title={t.edit} className="w-9 h-9 grid place-items-center rounded-lg text-[#d7bd75] hover:bg-[#473d24]"><Pencil size={17}/></button>
                            <button onClick={() => remove(`/farms/${farm.id}/fields/${field.id}`)} aria-label={t.delete} className="w-9 h-9 grid place-items-center rounded-lg text-[#d97979] hover:bg-[#482828]"><Trash2 size={17}/></button>
                          </div>
                        </article>
                      ))}
                      <div className="px-5 py-3 text-xs text-[#777c78]">
                        Area values come only from saved map geometry or
                        user-entered measurements.
                      </div>
                    </div>
                  </section>
                  <section className="mt-8 rounded-xl border border-[#3b3e3b] bg-[#232523] p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <div>
                      <p className="text-xs uppercase tracking-widest text-[#78c87e]">
                        Selected farm
                      </p>
                      <h3 className="text-xl font-semibold mt-1">
                        {farm.name}
                      </h3>
                      <p className="text-sm text-[#9ea39f] mt-1">
                        {[
                          farm.village,
                          farm.cell,
                          farm.sector,
                          farm.district,
                          farm.province,
                        ].join(" · ")}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2 self-start sm:self-auto">
                    <button
                      onClick={() => openFarmEditModal(farm)}
                      className="px-4 py-2 rounded-full border border-[#665a38] text-[#dfc57d] hover:bg-[#473d24] flex gap-2 items-center"
                    >
                      <Pencil size={16} />
                      {t.editFarm}
                    </button>
                    <button
                      onClick={async () => {
                        if (!confirm("Delete this record?")) return;
                        await api(
                          `/farms/${farm.id}`,
                          { method: "DELETE" },
                          token,
                        );
                        showPortfolio();
                        await load();
                      }}
                      className="px-4 py-2 rounded-full border border-[#704040] text-[#e18d8d] hover:bg-[#482828] flex gap-2 items-center"
                    >
                      <Trash2 size={16} />
                      Delete farm
                    </button>
                    </div>
                  </section>
                </>
              ) : (
                <div className="mt-8 rounded-xl border border-dashed border-[#4a4e4a] py-16 text-center">
                  <LandPlot className="mx-auto text-[#6fba76]" size={42} />
                  <h3 className="text-xl font-semibold mt-4">{t.noFarms}</h3>
                  <button
                    onClick={showPortfolio}
                    className="mt-5 px-5 py-2.5 rounded-full bg-[#2f8059]"
                  >
                    All farms
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </main>

      {waterField && <FieldWaterSources field={waterField} token={token} onClose={() => setWaterField(null)}/>}

      {modal && (
        <div className="fixed inset-0 z-[1100] flex items-end overflow-y-auto bg-black/75 p-0 backdrop-blur-sm sm:block sm:p-6">
          <div className="mx-auto max-h-[calc(100dvh-0.5rem)] w-full max-w-4xl overflow-y-auto rounded-t-3xl border border-[#444844] bg-[#202220] p-5 shadow-2xl sm:my-4 sm:max-h-none sm:rounded-2xl sm:p-8">
            <div className="flex justify-between items-start">
              <div>
                <h2 className="text-3xl font-semibold mt-1">
                  {modal === "farm"
                    ? editingFarm ? t.editFarm : t.addFarm
                    : editingField ? t.editField : t.addField}
                </h2>
              </div>
              <button
                onClick={() => {
                  setModal(null);
                  setEditingFarm(null);
                  setEditingField(null);
                  setPoints([]);
                }}
                className="w-10 h-10 grid place-items-center bg-[#2d302e] rounded-full hover:bg-[#383c39]"
              >
                <X />
              </button>
            </div>
            {modal === "farm" ? (
              <form onSubmit={saveFarm} className="mt-7">
                <label className="font-semibold">
                  Farm name
                  <input
                    name="name"
                    required
                    minLength={2}
                    defaultValue={editingFarm?.name ?? ""}
                    className={`${input} mt-2`}
                    placeholder="e.g. Hillside farm"
                  />
                </label>
                <div className="mt-7">
                  <h3 className="font-semibold">{t.location}</h3>
                  <p className="text-sm text-[#9da29e] mt-1">
                    Select the official administrative hierarchy, then
                    optionally place the exact farm point on the map.
                  </p>
                  <div className="mt-4">
                    <LocationPicker
                      token={token}
                      value={location}
                      onChange={changeLocation}
                      onCellChange={focusSelectedCell}
                    />
                  </div>
                  <input
                    type="hidden"
                    name="province"
                    value={location.province?.name ?? ""}
                  />
                  <input
                    type="hidden"
                    name="province_code"
                    value={location.province?.code ?? ""}
                  />
                  <input
                    type="hidden"
                    name="district"
                    value={location.district?.name ?? ""}
                  />
                  <input
                    type="hidden"
                    name="district_code"
                    value={location.district?.code ?? ""}
                  />
                  <input
                    type="hidden"
                    name="sector"
                    value={location.sector?.name ?? ""}
                  />
                  <input
                    type="hidden"
                    name="sector_code"
                    value={location.sector?.code ?? ""}
                  />
                  <input
                    type="hidden"
                    name="cell"
                    value={location.cell?.name ?? ""}
                  />
                  <input
                    type="hidden"
                    name="cell_code"
                    value={location.cell?.code ?? ""}
                  />
                  <input
                    type="hidden"
                    name="village"
                    value={location.village?.name ?? ""}
                  />
                  <input
                    type="hidden"
                    name="village_code"
                    value={location.village?.code ?? ""}
                  />
                  <h3 className="font-semibold mt-7">
                    Precise map point{" "}
                    <span className="text-[#8e938f] font-normal">
                      (optional)
                    </span>
                  </h3>
                  <p className="text-sm text-[#9da29e] mt-1">
                    Search a landmark or click the map. This records coordinates
                    without replacing the official hierarchy.
                  </p>
                  {cellFocusLoading && (
                    <p className="mt-3 text-sm text-[#aeb8d8]">
                      Locating the selected cell on the map…
                    </p>
                  )}
                  <div className="mt-4">
                    <MapPicker
                      points={points.slice(-1)}
                      setPoints={(next) => setPoints(next.slice(-1))}
                      onPick={pick}
                      token={token}
                      language={language}
                      addSearchPoint
                      onSearchResult={applySearchResult}
                      focusArea={cellFocus}
                    />
                  </div>
                </div>
                <p className="mt-3 text-xs text-[#e9c57a] bg-[#382f1e] border border-[#5c4b27] p-3 rounded-lg">
                  The administrative selection is validated against the local
                  Rwanda dataset. OpenStreetMap is used only for optional
                  coordinates and boundary drawing.
                </p>
                <button
                  disabled={busy}
                  className="mt-7 px-6 py-3 rounded-full bg-[#2f8059] hover:bg-[#399466] font-bold disabled:opacity-50"
                >
                  {busy ? "…" : t.save}
                </button>
              </form>
            ) : (
              <form onSubmit={saveField} className="mt-7">
                <div className="grid sm:grid-cols-2 gap-4">
                  <label className="font-semibold">
                    Field name
                    <input
                      name="name"
                      required
                      minLength={2}
                      defaultValue={editingField?.name ?? ""}
                      className={`${input} mt-2`}
                      placeholder="e.g. North plot"
                    />
                  </label>
                  <label className="font-semibold">
                    Crop note (optional)
                    <input
                      name="crop_note"
                      defaultValue={editingField?.crop_note ?? ""}
                      className={`${input} mt-2`}
                      placeholder="No prediction is made"
                    />
                  </label>
                </div>
                <div className="mt-7">
                  <h3 className="font-semibold">{t.map}</h3>
                  <p className="text-sm text-[#9da29e] mt-1">{t.mapHelp}</p>
                  <div className="mt-4">
                    <MapPicker
                      points={points}
                      setPoints={setPoints}
                      onPick={() => {}}
                      token={token}
                      language={language}
                    />
                  </div>
                  <div className="flex gap-2 mt-3">
                    <button
                      type="button"
                      onClick={() => setPoints(points.slice(0, -1))}
                      className="px-3 py-2 bg-[#303330] rounded-lg flex gap-2"
                    >
                      <Undo2 size={17} />
                      {t.undo}
                    </button>
                    <button
                      type="button"
                      onClick={() => setPoints([])}
                      className="px-3 py-2 bg-[#303330] rounded-lg"
                    >
                      {t.clear}
                    </button>
                  </div>
                </div>
                <div className="mt-7 p-5 rounded-xl bg-[#272a28] border border-[#414541]">
                  <h3 className="font-semibold">{t.manual}</h3>
                  <p className="text-sm text-[#9da29e] mt-1">{t.manualHelp}</p>
                  <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mt-4">
                    {(["a", "b", "c", "d"] as const).map((side) => (
                      <label key={side} className="text-sm">
                        Side {side.toUpperCase()}
                        <input
                          name={`side_${side}`}
                          type="number"
                          step="any"
                          min="0.001"
                          defaultValue={editingField?.[`side_${side}_m`] ?? undefined}
                          className={`${input} mt-1`}
                        />
                      </label>
                    ))}
                    <label className="text-sm">
                      Unit
                      <select name="side_unit" className={`${input} mt-1`}>
                        <option value="m">m</option>
                        <option value="cm">cm</option>
                        <option value="km">km</option>
                      </select>
                    </label>
                  </div>
                </div>
                <button
                  disabled={busy || (!polygon && points.length > 0)}
                  className="mt-7 px-6 py-3 rounded-full bg-[#2f8059] hover:bg-[#399466] font-bold disabled:opacity-50"
                >
                  {busy ? "…" : t.save}
                </button>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
