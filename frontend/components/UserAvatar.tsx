"use client";

import { useEffect, useState } from "react";

import { apiBlob, type CurrentUser } from "@/lib/api";

export type AvatarKey = CurrentUser["avatar_key"];
export type AvatarColor = CurrentUser["avatar_color"];

export const avatarOptions: { key: AvatarKey; label: string }[] = [
  { key: "farmer", label: "Farmer with cap" },
  { key: "sprout", label: "Farmer with green headwrap" },
  { key: "leaf", label: "Farmer with short hair" },
  { key: "wheat", label: "Farmer with braids" },
  { key: "mountain", label: "Farmer with field hat" },
  { key: "sun", label: "Farmer with natural curls" },
];

export const avatarColors: Record<AvatarColor, string> = {
  forest: "from-[#2f7b4d] to-[#1c4b32]", moss: "from-[#7fa652] to-[#4e702f]",
  earth: "from-[#9a6546] to-[#633e2b]", sunrise: "from-[#d98c3f] to-[#a94d35]",
  sky: "from-[#4f91ad] to-[#315b87]", plum: "from-[#8a6091] to-[#593b69]",
};

export function AvatarPortrait({ variant, className = "" }: { variant: AvatarKey; className?: string }) {
  const common = "h-full w-full";
  if (variant === "sprout") return <svg viewBox="0 0 128 128" aria-hidden="true" className={`${common} ${className}`}><path fill="#183927" d="M11 128c2-27 22-43 53-43s51 16 53 43z"/><path fill="#2d6b43" d="m35 128 6-32 23-11 24 11 6 32z"/><path fill="#603b2b" d="M52 76h24v21H52z"/><ellipse cx="64" cy="55" rx="28" ry="34" fill="#704735"/><path fill="#3a201b" d="M39 44c2-24 47-29 52 2-8-10-20-16-34-14-8 1-13 5-18 12z"/><path fill="#a5cd65" d="M31 36c7-23 26-30 45-23 16 6 22 20 20 34-12-11-23-15-35-15-11 0-21 3-30 4z"/><path fill="#79a94a" d="M38 20c15 3 35 13 49 26l9 1c1-13-5-27-20-34-15-7-29-3-38 7z"/><path fill="#38211d" d="M51 55c3-3 7-3 10 0-4 2-7 2-10 0m16 0c3-3 7-3 10 0-4 2-7 2-10 0"/><path fill="none" stroke="#3d211d" strokeLinecap="round" strokeWidth="2.5" d="M56 70c5 4 11 4 16 0"/><circle cx="48" cy="57" r="2" fill="#d99f6c"/><circle cx="80" cy="57" r="2" fill="#d99f6c"/></svg>;
  if (variant === "leaf") return <svg viewBox="0 0 128 128" aria-hidden="true" className={`${common} ${className}`}><path fill="#173d42" d="M9 128c4-28 23-43 55-43s51 15 55 43z"/><path fill="#2b6f72" d="m30 128 11-32 23-11 23 11 11 32z"/><path fill="#87553c" d="M52 77h24v20H52z"/><ellipse cx="64" cy="54" rx="28" ry="35" fill="#9c6648"/><path fill="#201b19" d="M36 47c0-23 12-35 29-35 21 0 30 15 28 37-5-11-12-16-20-18-13-4-25 1-37 16z"/><path fill="#201b19" d="M37 41c-4-9-1-18 5-23 4 2 6 5 6 9 2-10 8-16 15-19 4 4 5 9 3 14 5-8 12-11 19-10 2 7 0 13-4 18z"/><path fill="#31231f" d="M49 55c4-3 8-3 11 0-4 2-7 2-11 0m18 0c4-3 8-3 11 0-4 2-7 2-11 0"/><path fill="none" stroke="#4b2c24" strokeLinecap="round" strokeWidth="2.5" d="M55 70c6 5 12 5 18 0"/><path fill="#f0c989" d="m42 95 22 17 22-17 8 33H34z" opacity=".35"/></svg>;
  if (variant === "wheat") return <svg viewBox="0 0 128 128" aria-hidden="true" className={`${common} ${className}`}><path fill="#3f2849" d="M8 128c4-27 24-43 56-43s52 16 56 43z"/><path fill="#765080" d="m31 128 9-31 24-12 24 12 9 31z"/><path fill="#744631" d="M52 77h24v21H52z"/><ellipse cx="64" cy="53" rx="27" ry="34" fill="#89563d"/><path fill="#251c1c" d="M37 49c-2-24 9-39 27-39 21 0 31 16 28 40-8-13-17-19-29-19-11 0-19 6-26 18z"/><path fill="none" stroke="#251c1c" strokeLinecap="round" strokeWidth="5" d="M39 37c-9 14-8 32-2 49m10-58c-7 18-5 37 1 56m41-47c8 15 7 34 1 49M81 28c7 18 5 37-1 56"/><circle cx="38" cy="83" r="4" fill="#dcb85f"/><circle cx="90" cy="83" r="4" fill="#dcb85f"/><path fill="#33211d" d="M50 54c4-3 8-3 11 0-4 2-7 2-11 0m17 0c4-3 8-3 11 0-4 2-7 2-11 0"/><path fill="none" stroke="#472820" strokeLinecap="round" strokeWidth="2.5" d="M55 69c6 5 12 5 18 0"/></svg>;
  if (variant === "mountain") return <svg viewBox="0 0 128 128" aria-hidden="true" className={`${common} ${className}`}><path fill="#453328" d="M7 128c3-27 24-42 57-42s54 15 57 42z"/><path fill="#76583c" d="m31 128 9-31 24-11 24 11 9 31z"/><path fill="#563524" d="M52 75h24v22H52z"/><ellipse cx="64" cy="53" rx="28" ry="34" fill="#6b422d"/><path fill="#d3a64e" d="M22 35c12-8 24-12 42-12s31 4 43 12c-12 7-28 9-43 9s-30-2-42-9z"/><path fill="#b98938" d="M42 25C45 8 82 8 87 26c-14 6-31 6-45-1z"/><path fill="#27201d" d="M49 54c4-3 8-3 11 0-4 2-7 2-11 0m18 0c4-3 8-3 11 0-4 2-7 2-11 0"/><path fill="#ece2d2" d="M45 65c4 23 34 27 39 0-5 3-9 4-13 3-5-2-9-2-14 0-4 1-8 0-12-3z"/><path fill="#4c3024" d="M53 68c7 3 15 3 22 0-2 8-7 12-11 12s-9-4-11-12z"/><path fill="none" stroke="#b48e51" strokeWidth="2" d="M42 54h17m10 0h17m-27 0h10"/><rect x="41" y="49" width="19" height="12" rx="5" fill="none" stroke="#b48e51" strokeWidth="2"/><rect x="68" y="49" width="19" height="12" rx="5" fill="none" stroke="#b48e51" strokeWidth="2"/></svg>;
  if (variant === "sun") return <svg viewBox="0 0 128 128" aria-hidden="true" className={`${common} ${className}`}><path fill="#6b3926" d="M7 128c4-28 24-43 57-43s53 15 57 43z"/><path fill="#d0783c" d="m30 128 10-32 24-11 24 11 10 32z"/><path fill="#6b3f2d" d="M52 76h24v21H52z"/><ellipse cx="64" cy="55" rx="28" ry="34" fill="#7e4d37"/><g fill="#241c1b"><circle cx="39" cy="32" r="10"/><circle cx="48" cy="21" r="11"/><circle cx="62" cy="17" r="12"/><circle cx="77" cy="20" r="11"/><circle cx="88" cy="30" r="11"/><circle cx="94" cy="43" r="9"/><circle cx="34" cy="45" r="9"/></g><path fill="#30201c" d="M49 56c4-3 8-3 11 0-4 2-7 2-11 0m18 0c4-3 8-3 11 0-4 2-7 2-11 0"/><path fill="#f1d2b0" d="M55 69c6 5 12 5 18 0-2 8-16 9-18 0"/><circle cx="39" cy="61" r="3" fill="#d08c66"/><circle cx="89" cy="61" r="3" fill="#d08c66"/></svg>;
  return <svg viewBox="0 0 128 128" aria-hidden="true" className={`${common} ${className}`}><path fill="#1f3b2b" d="M7 128c4-28 24-43 57-43s53 15 57 43z"/><path fill="#356846" d="m31 128 9-32 24-11 24 11 9 32z"/><path fill="#5d3928" d="M52 77h24v21H52z"/><ellipse cx="64" cy="54" rx="28" ry="35" fill="#724632"/><path fill="#241c1a" d="M36 47c-1-24 10-37 29-37 20 0 30 15 28 39-8-12-18-18-30-18-11 0-20 6-27 16z"/><path fill="#547946" d="M28 31c11-12 24-18 39-18 14 0 27 5 37 16l-7 11c-20-8-41-8-63 0z"/><path fill="#3d5e34" d="M28 31c22 1 46 3 69 9l7-11c-26-5-52-4-76 2z"/><path fill="#30201c" d="M49 55c4-3 8-3 11 0-4 2-7 2-11 0m18 0c4-3 8-3 11 0-4 2-7 2-11 0"/><path fill="none" stroke="#42261f" strokeLinecap="round" strokeWidth="2.5" d="M55 70c6 5 12 5 18 0"/><path fill="#d9b15a" d="M38 101h52l5 27H33z" opacity=".18"/></svg>;
}

export default function UserAvatar({ user, token, size = "small", className = "" }: { user: CurrentUser; token: string; size?: "small" | "medium" | "large"; className?: string }) {
  const [photoUrl, setPhotoUrl] = useState<string | null>(null);
  const sizing = size === "large" ? "h-28 w-28 rounded-[1.8rem] sm:h-32 sm:w-32" : size === "medium" ? "h-12 w-12 rounded-2xl" : "h-9 w-9 rounded-xl";

  useEffect(() => {
    let active = true;
    let url: string | null = null;
    if (user.has_profile_photo) {
      apiBlob("/auth/me/avatar", token).then((blob) => {
        if (!active) return;
        url = URL.createObjectURL(blob);
        setPhotoUrl(url);
      }).catch(() => { if (active) setPhotoUrl(null); });
    } else setPhotoUrl(null);
    return () => { active = false; if (url) URL.revokeObjectURL(url); };
  }, [token, user]);

  return <span className={`grid shrink-0 place-items-center overflow-hidden border border-white/20 bg-gradient-to-br ${avatarColors[user.avatar_color] || avatarColors.forest} ${sizing} text-white shadow-sm ${className}`}>
    {photoUrl ? (
      <img src={photoUrl} alt={user.full_name} className="h-full w-full object-cover"/>
    ) : (
      <AvatarPortrait variant={user.avatar_key}/>
    )}
  </span>;
}
