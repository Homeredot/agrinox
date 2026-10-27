"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  Activity,
  ArrowLeft,
  Cable,
  CheckCircle2,
  CircleGauge,
  Cpu,
  DatabaseZap,
  Download,
  Eye,
  LoaderCircle,
  Pencil,
  PlugZap,
  Radio,
  RefreshCw,
  ScanLine,
  Trash2,
  Unlink,
  Unplug,
  Wifi,
  X,
} from "lucide-react";

import { api, type Farm } from "@/lib/api";

type DiscoveredSensor = {
  key: string;
  name: string;
  type: string;
  unit?: string | null;
  pin?: string | null;
};
type Port = {
  port: string;
  description?: string;
  vid?: string;
  pid?: string;
  likely_esp32: boolean;
  identified: boolean;
  device?: {
    device_uid: string;
    board?: string;
    firmware?: string;
    sensors?: DiscoveredSensor[];
  } | null;
  error?: string | null;
  error_code?: "port_unavailable" | "port_busy" | "no_response" | "incompatible" | "probe_failed" | null;
  action?: string | null;
};
type Sensor = DiscoveredSensor & {
  id: number;
  latest_value?: number | null;
  last_read_at?: string | null;
};
type Device = {
  id: number;
  field_id: number | null;
  field_name: string | null;
  farm_id: number | null;
  farm_name: string | null;
  name: string;
  device_uid: string;
  board: string;
  port: string;
  baud_rate: number;
  firmware_version?: string | null;
  status: string;
  is_online: boolean;
  last_seen_seconds_ago?: number | null;
  offline_after_seconds?: number;
  last_seen_at?: string | null;
  created_at?: string;
  sensors: Sensor[];
};
type FieldChoice = { id: number; name: string; farmName: string };
type FirmwareInstallResponse = { device: Device; message: string; field_assignment_required: boolean };

function lastSeenLabel(device: Device) {
  if (device.last_seen_seconds_ago == null) return "Never connected";
  if (device.last_seen_seconds_ago < 60) return "Seen just now";
  if (device.last_seen_seconds_ago < 3600) return `Seen ${Math.floor(device.last_seen_seconds_ago / 60)} min ago`;
  if (device.last_seen_seconds_ago < 86400) return `Seen ${Math.floor(device.last_seen_seconds_ago / 3600)} hr ago`;
  return `Seen ${Math.floor(device.last_seen_seconds_ago / 86400)} days ago`;
}

function DeviceDetail({
  device,
  reading,
  onBack,
  onRead,
}: {
  device: Device;
  reading: boolean;
  onBack: () => void;
  onRead: () => void;
}) {
  return (
    <div>
      <button
        onClick={onBack}
        className="flex items-center gap-2 text-sm font-semibold text-[#aeb3af] hover:text-white"
      >
        <ArrowLeft size={18} /> Back to all devices
      </button>
      <div className="mt-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="inline-flex items-center gap-2 rounded-full border border-[#3e7258] bg-[#21382b] px-3 py-1.5 text-xs font-bold uppercase tracking-[.2em] text-[#8dd49b]">
            <Cpu size={15} /> Device details
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <h1 className="text-3xl font-semibold sm:text-4xl">
              {device.name}
            </h1>
            <span
              className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold ${device.is_online ? "bg-[#274b34] text-[#90d09a]" : "bg-[#482d2d] text-[#ee9b9b]"}`}
            >
              <span className={`h-2 w-2 rounded-full ${device.is_online ? "bg-[#70d182] shadow-[0_0_8px_#70d182]" : "bg-[#dc7777]"}`} />
              {device.is_online ? "Online" : "Offline"}
            </span>
          </div>
          <p className="mt-2 text-[#aeb3af]">
            Live sensor values and technical information for this device.
          </p>
        </div>
        <button
          onClick={onRead}
          disabled={reading}
          className="flex h-11 items-center gap-2 rounded-full bg-[#2f8059] px-5 font-semibold hover:bg-[#399466] disabled:opacity-50"
        >
          {reading ? (
            <LoaderCircle className="animate-spin" size={18} />
          ) : (
            <RefreshCw size={18} />
          )}
          {reading ? "Reading…" : "Read sensors now"}
        </button>
      </div>

      {!device.is_online && (
        <div className="mt-5 rounded-2xl border border-[#6d4a3d] bg-[#392922] p-4 text-sm text-[#e3b59d]">
          <p className="font-semibold">This device is not contacting Agrinox.</p>
          <p className="mt-1 leading-6 text-[#c6a99a]">Wi-Fi can be connected while the Agrinox server is still unreachable. Check that this computer and the device use the same network, then scan the USB port and choose <strong>Update firmware</strong> to install automatic heartbeat support.</p>
        </div>
      )}

      <section className="mt-7 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {[
          ["Device type", "Field monitoring device"],
          ["USB port", device.port],
          ["Firmware", device.firmware_version || "Not reported"],
          ["Assignment", device.field_name || "Unassigned"],
          ["Connection", device.is_online ? "Online" : "Offline"],
        ].map(([label, value]) => (
          <article
            key={label}
            className="rounded-xl border border-[#3b3e3b] bg-[#232523] p-5"
          >
            <p className="text-xs uppercase tracking-wider text-[#929793]">
              {label}
            </p>
            <strong className="mt-3 block truncate text-lg">{value}</strong>
          </article>
        ))}
      </section>

      <section className="mt-7 rounded-2xl border border-[#3b3e3b] bg-[#232523] p-5">
        <div className="flex items-center gap-3">
          <Activity className="text-[#7fa0ff]" />
          <div>
            <h2 className="text-xl font-semibold">Sensor data</h2>
            <p className="text-sm text-[#969b97]">
              Values reported directly by this device—not estimated values.
            </p>
          </div>
        </div>
        {device.sensors.length === 0 ? (
          <div className="py-16 text-center text-[#8f9490]">
            <CircleGauge className="mx-auto mb-3" size={36} />
            <p>This device reported no sensors.</p>
          </div>
        ) : (
          <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {device.sensors.map((sensor) => (
              <article
                key={sensor.id}
                className="rounded-xl border border-[#414541] bg-gradient-to-br from-[#2c3530] to-[#272b29] p-4"
              >
                <div className="flex items-center justify-between">
                  <Activity size={18} className="text-[#7fa0ff]" />
                  {sensor.last_read_at && (
                    <CheckCircle2 size={15} className="text-[#6fc17a]" />
                  )}
                </div>
                <p className="mt-4 text-sm text-[#aeb3af]">{sensor.name}</p>
                <p className="mt-1">
                  <strong className="text-3xl">
                    {sensor.latest_value ?? "—"}
                  </strong>{" "}
                  <span className="text-sm text-[#9da29e]">
                    {sensor.unit || ""}
                  </span>
                </p>
                <div className="mt-4 flex justify-between text-[11px] text-[#777d78]">
                  <span>{sensor.type}</span>
                  <span>{sensor.pin || "pin not reported"}</span>
                </div>
                <p className="mt-2 text-[11px] text-[#777d78]">
                  {sensor.last_read_at
                    ? `Read ${new Date(sensor.last_read_at).toLocaleString()}`
                    : "No reading received yet"}
                </p>
              </article>
            ))}
          </div>
        )}
      </section>

      <section className="mt-5 rounded-2xl border border-[#3b3e3b] bg-[#232523] p-5">
        <h2 className="text-xl font-semibold">Device information</h2>
        <dl className="mt-4 grid gap-4 text-sm sm:grid-cols-2 xl:grid-cols-3">
          {[
            ["Device UID", device.device_uid],
            ["Baud rate", device.baud_rate.toLocaleString()],
            ["Farm", device.farm_name || "Not assigned"],
            ["Field", device.field_name || "Not assigned"],
            [
              "Last connected",
              device.last_seen_at
                ? `${lastSeenLabel(device)} · ${new Date(device.last_seen_at).toLocaleString()}`
                : "Never connected",
            ],
            ["Registered sensors", String(device.sensors.length)],
          ].map(([label, value]) => (
            <div key={label} className="rounded-xl bg-[#292c2a] p-4">
              <dt className="text-[#858b86]">{label}</dt>
              <dd className="mt-1 break-all font-semibold text-[#e3e7e4]">
                {value}
              </dd>
            </div>
          ))}
        </dl>
      </section>
    </div>
  );
}

export default function DeviceManagement({
  farms,
  token,
}: {
  farms: Farm[];
  token: string;
}) {
  const [devices, setDevices] = useState<Device[]>([]);
  const [ports, setPorts] = useState<Port[]>([]);
  const [detailId, setDetailId] = useState<number | null>(null);
  const [registering, setRegistering] = useState<Port | null>(null);
  const [installingPort, setInstallingPort] = useState<Port | null>(null);
  const [editing, setEditing] = useState<Device | null>(null);
  const [scanning, setScanning] = useState(false);
  const [reading, setReading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const fields = useMemo<FieldChoice[]>(
    () =>
      farms.flatMap((farm) =>
        farm.fields.map((field) => ({
          id: field.id,
          name: field.name,
          farmName: farm.name,
        })),
      ),
    [farms],
  );
  const detail = devices.find((device) => device.id === detailId) ?? null;
  const sensorCount = devices.reduce(
    (sum, device) => sum + device.sensors.length,
    0,
  );
  const assignedCount = devices.filter(
    (device) => device.field_id !== null,
  ).length;
  const onlineCount = devices.filter((device) => device.is_online).length;
  const offlineCount = devices.length - onlineCount;

  async function loadDevices() {
    try {
      setDevices(await api<Device[]>("/devices", {}, token));
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not load devices",
      );
    }
  }

  useEffect(() => {
    void loadDevices();
    const timer = window.setInterval(() => void loadDevices(), 30_000);
    return () => window.clearInterval(timer);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function scan() {
    setScanning(true);
    setError("");
    try {
      setPorts(await api<Port[]>("/devices/scan?probe=true", {}, token));
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "USB scan failed",
      );
    } finally {
      setScanning(false);
    }
  }

  async function register(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!registering?.device) return;
    setBusy(true);
    setError("");
    const form = Object.fromEntries(new FormData(event.currentTarget));
    try {
      const assigned = await api<Device>(
        "/devices",
        {
          method: "POST",
          body: JSON.stringify({
            field_id: Number(form.field_id),
            name: form.name,
            device_uid: registering.device.device_uid,
            port: registering.port,
            board: registering.device.board || "Field device",
            firmware_version: registering.device.firmware || null,
            baud_rate: 115200,
            sensors: registering.device.sensors || [],
          }),
        },
        token,
      );
      setRegistering(null);
      setNotice(`${assigned.name} is assigned to ${assigned.field_name}.`);
      await loadDevices();
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Registration failed",
      );
    } finally {
      setBusy(false);
    }
  }

  async function installFirmware(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!installingPort) return;
    setBusy(true);
    setError("");
    setNotice("");
    const form = Object.fromEntries(new FormData(event.currentTarget));
    try {
      const result = await api<FirmwareInstallResponse>(
        "/devices/firmware/install",
        {
          method: "POST",
          body: JSON.stringify({
            port: installingPort.port,
            wifi_ssid: form.wifi_ssid,
            wifi_password: form.wifi_password,
          }),
        },
        token,
      );
      setInstallingPort(null);
      setPorts([]);
      setNotice(`${result.device.name} is ready. Assign it to a field when you are ready.`);
      await loadDevices();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Firmware installation failed");
    } finally {
      setBusy(false);
    }
  }

  async function saveEdit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editing) return;
    setBusy(true);
    const form = Object.fromEntries(new FormData(event.currentTarget));
    try {
      await api<Device>(
        `/devices/${editing.id}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            name: form.name,
            field_id: form.field_id ? Number(form.field_id) : null,
          }),
        },
        token,
      );
      setEditing(null);
      await loadDevices();
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not update device",
      );
    } finally {
      setBusy(false);
    }
  }

  async function unassign(device: Device) {
    if (
      !device.field_id ||
      !confirm(`Unassign ${device.name} from ${device.field_name}?`)
    )
      return;
    try {
      await api(
        `/devices/${device.id}`,
        { method: "PATCH", body: JSON.stringify({ field_id: null }) },
        token,
      );
      await loadDevices();
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not unassign device",
      );
    }
  }

  async function removeDevice(device: Device) {
    if (
      !confirm(`Delete ${device.name} and all of its stored sensor readings?`)
    )
      return;
    try {
      await api(`/devices/${device.id}`, { method: "DELETE" }, token);
      if (detailId === device.id) setDetailId(null);
      await loadDevices();
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not delete device",
      );
    }
  }

  async function readNow() {
    if (!detail) return;
    setReading(true);
    setError("");
    try {
      const updated = await api<Device>(
        `/devices/${detail.id}/read`,
        { method: "POST" },
        token,
      );
      setDevices((current) =>
        current.map((item) => (item.id === updated.id ? updated : item)),
      );
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Sensor read failed",
      );
      await loadDevices();
    } finally {
      setReading(false);
    }
  }

  if (detail)
    return (
      <DeviceDetail
        device={detail}
        reading={reading}
        onBack={() => setDetailId(null)}
        onRead={() => void readNow()}
      />
    );

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold sm:text-4xl">
            Device overview
          </h1>
          <p className="mobile-secondary mt-2 max-w-2xl text-[#aeb3af]">
            Register devices, manage field assignments and open a device only
            when you need its sensor data.
          </p>
        </div>
        <button
          onClick={() => void scan()}
          disabled={scanning}
          className="flex h-11 items-center gap-2 rounded-full bg-[#2f8059] px-5 font-semibold hover:bg-[#399466] disabled:opacity-50"
        >
          {scanning ? (
            <LoaderCircle className="animate-spin" size={18} />
          ) : (
            <ScanLine size={18} />
          )}
          <span className="sm:hidden">{scanning ? "Scanning…" : "Register"}</span><span className="hidden sm:inline">{scanning ? "Scanning USB…" : "Register a device"}</span>
        </button>
      </div>

      {error && (
        <div
          role="alert"
          className="mt-5 flex items-start justify-between rounded-xl border border-[#6e3333] bg-[#3b2020] p-4 text-[#ffb9b9]"
        >
          {error}
          <button onClick={() => setError("")}>
            <X size={18} />
          </button>
        </div>
      )}
      {notice && <div role="status" className="mt-5 flex items-start justify-between rounded-xl border border-[#3f6b4b] bg-[#203628] p-4 text-[#b8e1bf]"><span>{notice}</span><button onClick={() => setNotice("")} aria-label="Dismiss message"><X size={18} /></button></div>}

      <section className="mt-7 grid grid-cols-1 gap-3 min-[390px]:grid-cols-2 xl:grid-cols-4">
        {[
          {
            label: "Registered",
            value: devices.length,
            icon: Cpu,
            color: "text-[#78c87e]",
          },
          {
            label: "Assigned to fields",
            value: assignedCount,
            icon: DatabaseZap,
            color: "text-[#bb8bd1]",
          },
          {
            label: "Online",
            value: onlineCount,
            icon: Radio,
            color: "text-[#7fa0ff]",
            note: `${offlineCount} offline`,
          },
          {
            label: "Sensors",
            value: sensorCount,
            icon: Activity,
            color: "text-[#e2b560]",
          },
        ].map((stat) => (
          <article
            key={stat.label}
            className="rounded-xl border border-[#3b3e3b] bg-[#232523] p-5"
          >
            <div className="flex items-center justify-between">
              <p className="text-xs uppercase tracking-wider text-[#929793]">
                {stat.label}
              </p>
              <stat.icon size={19} className={stat.color} />
            </div>
            <strong className="mt-3 block text-3xl">{stat.value}</strong>
            {"note" in stat && <p className="mt-1 text-xs text-[#8f958f]">{stat.note}</p>}
          </article>
        ))}
      </section>

      {ports.length > 0 && (
        <section className="mt-7 rounded-2xl border border-[#3b3e3b] bg-[#232523] p-5">
          <div className="flex items-center gap-3">
            <Cable className="text-[#7fa0ff]" />
            <div>
              <h2 className="text-xl font-semibold">Register from USB</h2>
              <p className="text-sm text-[#969b97]">
                Only compatible devices detected by Agrinox can be registered.
              </p>
            </div>
          </div>
          <div className="mt-4 grid gap-3 lg:grid-cols-2">
            {ports.map((port) => (
              <article
                key={port.port}
                className="rounded-xl border border-[#414541] bg-[#292c2a] p-4"
              >
                <div className="flex items-start gap-3">
                  <span
                    className={`grid h-10 w-10 place-items-center rounded-lg ${port.identified ? "bg-[#2f7654]" : "bg-[#373b38] text-[#a4aaa5]"}`}
                  >
                    {port.identified ? (
                      <PlugZap size={20} />
                    ) : (
                      <Unplug size={20} />
                    )}
                  </span>
                  <div className="min-w-0 flex-1">
                    <strong>{port.port}</strong>
                    <p className="mt-1 truncate text-sm text-[#9da29e]">
                      {port.description || "Serial device"}
                    </p>
                    <p className="mt-2 text-xs text-[#777d78]">
                      VID:PID {port.vid || "—"}:{port.pid || "—"}
                    </p>
                  </div>
                </div>
                {port.identified && port.device ? (
                  <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-[#3f433f] pt-3">
                    <span className="text-sm text-[#aeb3af]">
                      {port.device.sensors?.length ?? 0} sensors detected
                    </span>
                    <div className="flex flex-wrap gap-2">
                      {devices.some((item) => item.device_uid === port.device?.device_uid) && (
                        <button onClick={() => setInstallingPort(port)} className="inline-flex items-center gap-1.5 rounded-full border border-[#52705b] px-3.5 py-2 text-sm font-semibold text-[#a9d7b2]">
                          <Download size={14} /> Update firmware
                        </button>
                      )}
                      <button
                        onClick={() => setRegistering(port)}
                        disabled={fields.length === 0}
                        className="rounded-full bg-[#4356c9] px-4 py-2 text-sm font-semibold disabled:opacity-40"
                      >
                        {devices.some((item) => item.device_uid === port.device?.device_uid) ? "Assign to field" : "Register"}
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="mt-3 rounded-lg bg-[#342f25] p-3 text-xs text-[#c4af82]">
                    <p className="font-semibold">{port.error || "No compatible device responded on this port."}</p>
                    {port.action && <p className="mt-1.5 leading-5 text-[#aa9c7c]">{port.action}</p>}
                    {port.likely_esp32 && <div className="mt-3 flex flex-wrap gap-2"><button type="button" onClick={() => setInstallingPort(port)} className="inline-flex items-center gap-1.5 rounded-full bg-[#3f8056] px-3 py-1.5 font-semibold text-white"><Download size={13} />Install firmware</button><button type="button" onClick={() => void scan()} disabled={scanning} className="inline-flex items-center gap-1.5 rounded-full border border-[#6d624a] px-3 py-1.5 font-semibold text-[#dbc38e] disabled:opacity-50"><RefreshCw size={13} className={scanning ? "animate-spin" : ""} />Scan again</button></div>}
                  </div>
                )}
              </article>
            ))}
          </div>
        </section>
      )}

      <section className="mt-7">
        <div className="mb-3">
          <h2 className="text-xl font-semibold">All registered devices</h2>
          <p className="mt-1 text-sm text-[#969b97]">
            Assign, unassign, edit or delete devices here. Sensor readings open
            on a separate page.
          </p>
        </div>
        <div className="overflow-hidden rounded-2xl border border-[#3b3e3b] bg-[#232523]">
          {devices.length === 0 ? (
            <div className="py-16 text-center text-[#8f9490]">
              <Cpu className="mx-auto mb-3" size={36} />
              <p>No devices registered.</p>
              <button
                onClick={() => void scan()}
                className="mt-4 rounded-full border border-[#4a594f] px-4 py-2 text-sm font-semibold text-[#b9d7c2]"
              >
                Scan USB ports
              </button>
            </div>
          ) : (
            <div className="divide-y divide-[#393d39]">
              {devices.map((device) => (
                <article
                  key={device.id}
                  className="grid gap-4 p-5 lg:grid-cols-[1.2fr_.9fr_.55fr_auto] lg:items-center"
                >
                  <div className="flex min-w-0 items-center gap-3">
                    <span
                      className={`h-2.5 w-2.5 shrink-0 rounded-full ${device.is_online ? "bg-[#67c477] shadow-[0_0_10px_#67c477]" : "bg-[#d06b6b]"}`}
                    />
                    <div className="min-w-0">
                      <strong className="block truncate">{device.name}</strong>
                      <p className="truncate text-sm text-[#8f958f]">
                        Field monitoring device · {device.port} · {device.sensors.length}{" "}
                        sensors
                      </p>
                    </div>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-wider text-[#777d78]">
                      Field assignment
                    </p>
                    <p
                      className={`mt-1 text-sm font-semibold ${device.field_id ? "text-[#d9ddda]" : "text-[#d1a965]"}`}
                    >
                      {device.field_name
                        ? `${device.farm_name} — ${device.field_name}`
                        : "Unassigned"}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-wider text-[#777d78]">
                      Status
                    </p>
                    <p className={`mt-1 inline-flex items-center gap-1.5 text-sm font-semibold ${device.is_online ? "text-[#82cc8d]" : "text-[#e38a8a]"}`}>
                      {device.is_online ? <Wifi size={14} /> : <Unplug size={14} />}
                      {device.is_online ? "Online" : "Offline"}
                    </p>
                    <p className="mt-1 text-xs text-[#858b86]">{lastSeenLabel(device)}</p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2 lg:justify-end">
                    <button
                      onClick={() => setDetailId(device.id)}
                      className="flex items-center gap-1.5 rounded-full bg-[#2f8059] px-3.5 py-2 text-sm font-semibold hover:bg-[#399466]"
                    >
                      <Eye size={15} /> View sensors
                    </button>
                    <button
                      onClick={() => setEditing(device)}
                      aria-label={`Edit ${device.name}`}
                      className="grid h-9 w-9 place-items-center rounded-lg border border-[#464b47] text-[#bfc4c0] hover:bg-[#303330]"
                    >
                      <Pencil size={16} />
                    </button>
                    <button
                      onClick={() => void unassign(device)}
                      disabled={!device.field_id}
                      aria-label={`Unassign ${device.name}`}
                      className="grid h-9 w-9 place-items-center rounded-lg border border-[#514b3f] text-[#d1a965] hover:bg-[#393228] disabled:cursor-not-allowed disabled:opacity-30"
                    >
                      <Unlink size={16} />
                    </button>
                    <button
                      onClick={() => void removeDevice(device)}
                      aria-label={`Delete ${device.name}`}
                      className="grid h-9 w-9 place-items-center rounded-lg text-[#d97979] hover:bg-[#482828]"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </article>
              ))}
            </div>
          )}
        </div>
      </section>

      {installingPort && <FirmwareInstallModal port={installingPort} busy={busy} onClose={() => setInstallingPort(null)} onSubmit={installFirmware} />}
      {registering?.device && (
        <DeviceFormModal
          title={devices.some((item) => item.device_uid === registering.device?.device_uid) ? "Assign device to field" : "Register device"}
          description={`${registering.port} · ${registering.device.sensors?.length ?? 0} sensors detected${devices.some((item) => item.device_uid === registering.device?.device_uid) ? " · already registered" : ""}`}
          defaultName={`NPK Monitor ${registering.device.device_uid.replace(/[^a-z0-9]/gi, "").slice(-6).toUpperCase() || "ESP32"}`}
          defaultField=""
          fields={fields}
          busy={busy}
          submitLabel={devices.some((item) => item.device_uid === registering.device?.device_uid) ? "Assign to field" : "Register device"}
          requireField
          allowRename={false}
          onClose={() => setRegistering(null)}
          onSubmit={register}
        />
      )}
      {editing && (
        <DeviceFormModal
          title="Edit device"
          description="Rename the device or change its field assignment."
          defaultName={editing.name}
          defaultField={editing.field_id ? String(editing.field_id) : ""}
          fields={fields}
          busy={busy}
          submitLabel="Save changes"
          onClose={() => setEditing(null)}
          onSubmit={saveEdit}
        />
      )}
    </div>
  );
}

function FirmwareInstallModal({
  port,
  busy,
  onClose,
  onSubmit,
}: {
  port: Port;
  busy: boolean;
  onClose: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return <div className="fixed inset-0 z-[1300] grid place-items-end overflow-y-auto bg-black/80 p-0 backdrop-blur-sm sm:place-items-center sm:p-4"><form onSubmit={onSubmit} className="w-full max-w-lg rounded-t-3xl border border-[#454b46] bg-[#202521] p-5 shadow-2xl sm:rounded-3xl sm:p-7"><div className="flex items-start justify-between gap-4"><div className="flex gap-3"><span className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-[#315f42] text-[#b8e6bf]"><Download size={22} /></span><div><p className="text-xs font-bold uppercase tracking-[.16em] text-[#83c18c]">ESP32 setup · {port.port}</p><h2 className="mt-1 text-2xl font-semibold">Install Agrinox firmware</h2><p className="mt-1 text-sm leading-5 text-[#a7afa8]">The device name, identity and security key are created automatically.</p></div></div><button type="button" onClick={onClose} disabled={busy} className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-[#303631] disabled:opacity-40" aria-label="Close firmware setup"><X size={18} /></button></div><div className="mt-6 rounded-2xl border border-[#3f5043] bg-[#27312a] p-4"><div className="flex items-center gap-2 text-sm font-semibold"><Wifi size={17} className="text-[#8bcb93]" />Connect the device to Wi-Fi</div><p className="mt-1 text-xs leading-5 text-[#929b93]">Enter the same Wi-Fi network used by this Agrinox computer. The password is sent directly to the ESP32 and is not returned by the API.</p><label className="mt-4 block text-sm font-semibold">Wi-Fi name<input name="wifi_ssid" required maxLength={32} autoComplete="off" className="mt-2 w-full rounded-xl border border-[#4a534b] bg-[#1e231f] p-3.5" placeholder="Example: Home WiFi" /></label><label className="mt-4 block text-sm font-semibold">Wi-Fi password<input name="wifi_password" type="password" required minLength={8} maxLength={63} autoComplete="new-password" className="mt-2 w-full rounded-xl border border-[#4a534b] bg-[#1e231f] p-3.5" placeholder="At least 8 characters" /></label></div>{busy && <div role="status" className="mt-4 rounded-xl border border-[#5f573a] bg-[#342f22] p-4 text-sm text-[#dccb95]"><p className="flex items-center gap-2 font-semibold"><LoaderCircle size={17} className="animate-spin" />Installing and verifying firmware…</p><p className="mt-1 text-xs leading-5 text-[#b6aa84]">Keep the USB cable connected. The ESP32 may restart several times.</p></div>}<div className="mt-6 flex justify-end gap-3"><button type="button" onClick={onClose} disabled={busy} className="h-11 rounded-xl border border-[#4c554d] px-4 font-semibold disabled:opacity-40">Cancel</button><button disabled={busy} className="flex h-11 items-center gap-2 rounded-xl bg-[#78b763] px-5 font-bold text-[#142013] disabled:opacity-50">{busy ? <LoaderCircle size={17} className="animate-spin" /> : <Download size={17} />}{busy ? "Installing…" : "Install firmware"}</button></div></form></div>;
}

function DeviceFormModal({
  title,
  description,
  defaultName,
  defaultField,
  fields,
  busy,
  submitLabel,
  requireField = false,
  allowRename = true,
  onClose,
  onSubmit,
}: {
  title: string;
  description: string;
  defaultName: string;
  defaultField: string;
  fields: FieldChoice[];
  busy: boolean;
  submitLabel: string;
  requireField?: boolean;
  allowRename?: boolean;
  onClose: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return (
    <div className="fixed inset-0 z-[1200] grid place-items-end overflow-y-auto bg-black/75 p-0 backdrop-blur-sm sm:place-items-center sm:p-4">
      <form
        onSubmit={onSubmit}
        className="max-h-[calc(100dvh-0.5rem)] w-full max-w-lg overflow-y-auto rounded-t-3xl border border-[#444844] bg-[#202220] p-5 shadow-2xl sm:my-auto sm:max-h-none sm:rounded-2xl sm:p-6"
      >
        <div className="flex items-start justify-between">
          <div>
            <p className="text-xs uppercase tracking-widest text-[#78c87e]">
              Device Management
            </p>
            <h2 className="mt-1 text-2xl font-semibold">{title}</h2>
            <p className="mt-1 text-sm text-[#969b97]">{description}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="grid h-9 w-9 place-items-center rounded-full bg-[#303330]"
          >
            <X size={18} />
          </button>
        </div>
        {allowRename ? <label className="mt-5 block font-semibold">
          Device name
          <input
            name="name"
            required
            minLength={2}
            defaultValue={defaultName}
            className="mt-2 w-full rounded-lg border border-[#494d4a] bg-[#262927] p-3.5"
          />
        </label> : <><input type="hidden" name="name" value={defaultName} /><div className="mt-5 rounded-xl border border-[#405044] bg-[#27312a] p-4"><p className="text-xs uppercase tracking-wider text-[#87a58e]">Automatic device name</p><strong className="mt-1 block">{defaultName}</strong><p className="mt-1 text-xs text-[#98a099]">Agrinox creates the name from the ESP32 identity.</p></div></>}
        <label className="mt-4 block font-semibold">
          Field assignment
          <select
            name="field_id"
            required={requireField}
            defaultValue={defaultField}
            className="mt-2 w-full rounded-lg border border-[#494d4a] bg-[#262927] p-3.5"
          >
            <option value="" disabled={requireField}>
              {requireField ? "Select a field" : "Unassigned"}
            </option>
            {fields.map((field) => (
              <option key={field.id} value={field.id}>
                {field.farmName} — {field.name}
              </option>
            ))}
          </select>
        </label>
        <p className="mt-3 text-xs text-[#969b97]">
          A device can be assigned only to a field. It is never assigned
          directly to a farm.
        </p>
        <button
          disabled={busy || (requireField && fields.length === 0)}
          className="mt-6 rounded-full bg-[#2f8059] px-6 py-3 font-bold disabled:opacity-50"
        >
          {busy ? "Saving…" : submitLabel}
        </button>
      </form>
    </div>
  );
}
