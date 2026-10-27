import { translateText, type Language } from "@/lib/i18n";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "/api/backend";

export type Field = { id: number; farm_id: number; name: string; crop_note?: string | null; side_a_m?: number | null; side_b_m?: number | null; side_c_m?: number | null; side_d_m?: number | null; area_m2: number; area_source: "map" | "manual_estimate"; boundary_geojson?: string | null };
export type Farm = { id: number; name: string; province: string; district: string; sector: string; cell: string; village: string; province_code?: number | null; district_code?: number | null; sector_code?: string | null; cell_code?: number | null; village_code?: number | null; latitude?: number | null; longitude?: number | null; fields: Field[] };
export type CurrentUser = {
  id: number;
  email: string;
  full_name: string;
  preferred_language: Language;
  phone?: string | null;
  location?: string | null;
  bio?: string | null;
  avatar_kind: "vector" | "photo";
  avatar_key: "farmer" | "sprout" | "leaf" | "wheat" | "mountain" | "sun";
  avatar_color: "forest" | "moss" | "earth" | "sunrise" | "sky" | "plum";
  has_profile_photo: boolean;
  created_at: string;
};

export async function api<T>(path: string, options: RequestInit = {}, token?: string): Promise<T> {
  const language: Language = typeof window !== "undefined" && localStorage.getItem("agrinox_language") === "rw" ? "rw" : "en";
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, { ...options, headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options.headers } });
  } catch {
    throw new Error(translateText("Cannot reach the Agrinox server. Refresh the page and try again.", language));
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(translateText(typeof body.detail === "string" ? body.detail : "Request failed", language));
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}

async function responseError(response: Response, language: Language): Promise<never> {
  const body = await response.json().catch(() => ({}));
  throw new Error(translateText(typeof body.detail === "string" ? body.detail : "Request failed", language));
}

export async function apiForm<T>(path: string, form: FormData, token: string): Promise<T> {
  const language: Language = typeof window !== "undefined" && localStorage.getItem("agrinox_language") === "rw" ? "rw" : "en";
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, { method: "POST", body: form, headers: { Authorization: `Bearer ${token}` } });
  } catch {
    throw new Error(translateText("Cannot reach the Agrinox server. Refresh the page and try again.", language));
  }
  if (!response.ok) return responseError(response, language);
  return response.json();
}

export async function apiBlob(path: string, token: string): Promise<Blob> {
  const language: Language = typeof window !== "undefined" && localStorage.getItem("agrinox_language") === "rw" ? "rw" : "en";
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, { headers: { Authorization: `Bearer ${token}` } });
  } catch {
    throw new Error(translateText("Cannot reach the Agrinox server. Refresh the page and try again.", language));
  }
  if (!response.ok) return responseError(response, language);
  return response.blob();
}

