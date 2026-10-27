"use client";

import { ChangeEvent, FormEvent, useEffect, useRef, useState } from "react";
import { AlertTriangle, Camera, CheckCircle2, ChevronRight, ExternalLink, Eye, FileImage, History, Leaf, LoaderCircle, RefreshCw, ScanSearch, ShieldCheck, Sparkles, Upload, X } from "lucide-react";
import { API_URL, api } from "@/lib/api";

type Prediction = { case_id: number; analysis_status: "completed" | "uncertain" | "unsupported_image" | "invalid_image" | "model_unavailable" | "analysis_failed"; possible_condition?: string; classification?: string; confidence?: number; model_top_class?: string; leading_candidate?: string; leading_candidate_score?: number; candidate_is_confirmed?: boolean; alternatives: { label: string; confidence: number }[]; visible_symptoms: string[]; recommended_inspection_steps: string[]; expert_confirmation_required: boolean; model_version?: string; model_message?: string; uncertainty_reason?: string; evidence_level?: string; field_validation?: string; disclaimer: string; sources: { title: string; url: string }[] };
type PlantCase = { id: number; crop_id: string; crop_name: string; original_filename: string; prediction: Prediction; model_version?: string; confidence?: number; review_status: string; created_at: string; image_url: string };
type ModelStatus = { available: boolean; framework: string; model_version?: string; limitation: string; supported_crops: { id: string; name: string; model_supported: boolean }[]; models?: { crop_id: string; crop_name: string; available: boolean; model_version?: string; validation?: { accuracy?: number; images?: number; design?: string } }[]; source: { title: string; url: string } };
type PlantAdvice = { status: "ready" | "limited"; text: string; sources: { article_title: string; source_url: string }[]; model: string; response_mode: string; language: string; generated_at: string; safety_notice: string };
type CropId = "irish-potato" | "tomato";
const CROPS: { id: CropId; name: string; note: string }[] = [
  { id: "irish-potato", name: "Irish potato", note: "Early blight · Late blight · Healthy" },
  { id: "tomato", name: "Tomato", note: "Conservative screening · no guessing" },
];

export default function PlantLens({ token }: { token: string }) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState("");
  const [result, setResult] = useState<PlantCase | null>(null);
  const [cases, setCases] = useState<PlantCase[]>([]);
  const [model, setModel] = useState<ModelStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [cropId, setCropId] = useState<CropId>("irish-potato");
  const [advice, setAdvice] = useState<PlantAdvice | null>(null);
  const [adviceBusy, setAdviceBusy] = useState(false);
  const [adviceError, setAdviceError] = useState("");
  const [cameraOpen, setCameraOpen] = useState(false);
  const [cameraError, setCameraError] = useState("");
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const nativeCameraRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    Promise.all([api<ModelStatus>("/plant-lens/model-status", {}, token), api<PlantCase[]>("/plant-lens/cases", {}, token)])
      .then(([status, history]) => { setModel(status); setCases(history); })
      .catch((requestError) => setError(requestError instanceof Error ? requestError.message : "Could not load Plant Lens"));
  }, [token]);
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);
  useEffect(() => {
    if (cameraOpen && videoRef.current && streamRef.current) {
      videoRef.current.srcObject = streamRef.current;
      void videoRef.current.play().catch(() => setCameraError("The camera preview could not start. Try the phone camera instead."));
    }
  }, [cameraOpen]);
  useEffect(() => () => { streamRef.current?.getTracks().forEach((track) => track.stop()); }, []);

  function selectImage(next: File | null) {
    setError(""); setResult(null); setAdvice(null); setAdviceError("");
    if (preview) URL.revokeObjectURL(preview);
    if (next && next.size > 10 * 1024 * 1024) { setFile(null); setPreview(""); setError("Choose an image smaller than 10 MB"); return; }
    setFile(next); setPreview(next ? URL.createObjectURL(next) : "");
  }

  function chooseImage(event: ChangeEvent<HTMLInputElement>) {
    const next = event.target.files?.[0] || null;
    selectImage(next);
    event.target.value = "";
  }

  function closeCamera() {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    setCameraOpen(false);
  }

  async function openCamera() {
    setCameraError("");
    if (!navigator.mediaDevices?.getUserMedia) {
      nativeCameraRef.current?.click();
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: "environment" } }, audio: false });
      streamRef.current = stream;
      setCameraOpen(true);
    } catch {
      nativeCameraRef.current?.click();
    }
  }

  function capturePhoto() {
    const video = videoRef.current;
    if (!video?.videoWidth || !video.videoHeight) {
      setCameraError("The camera is still starting. Wait a moment and try again.");
      return;
    }
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d")?.drawImage(video, 0, 0, canvas.width, canvas.height);
    canvas.toBlob((blob) => {
      if (!blob) { setCameraError("The photograph could not be captured. Please try again."); return; }
      selectImage(new File([blob], `plant-photo-${Date.now()}.jpg`, { type: "image/jpeg" }));
      closeCamera();
    }, "image/jpeg", 0.92);
  }

  async function loadAdvice(plantCase: PlantCase) {
    setAdviceBusy(true); setAdviceError("");
    try {
      const nextAdvice = await api<PlantAdvice>(`/plant-lens/cases/${plantCase.id}/advice`, { method: "POST" }, token);
      setAdvice(nextAdvice);
    } catch (requestError) {
      setAdviceError(requestError instanceof Error ? requestError.message : "Could not load Gemini advice");
    } finally { setAdviceBusy(false); }
  }

  async function analyze(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) { setError("Take or choose a plant photograph first"); return; }
    setBusy(true); setError("");
    const form = new FormData(); form.append("crop_id", cropId); form.append("image", file);
    try {
      const response = await fetch(`${API_URL}/plant-lens/analyze`, { method: "POST", headers: { Authorization: `Bearer ${token}` }, body: form });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : "Image analysis failed");
      setResult(body); setAdvice(null); setAdviceError(""); setCases(await api<PlantCase[]>("/plant-lens/cases", {}, token));
      if (body.prediction?.analysis_status === "completed" && !["healthy", "unsupported"].includes(body.prediction.classification || "")) void loadAdvice(body);
      requestAnimationFrame(() => document.getElementById("plant-lens-result")?.scrollIntoView({ behavior: "smooth", block: "start" }));
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : "Image analysis failed"); }
    finally { setBusy(false); }
  }

  const prediction = result?.prediction;
  const cropName = CROPS.find((crop) => crop.id === cropId)?.name || "Crop";
  const selectedModelAvailable = model?.supported_crops.find((crop) => crop.id === cropId)?.model_supported ?? false;
  const selectedModel = model?.models?.find((item) => item.crop_id === cropId);
  const modelFailed = prediction?.analysis_status === "model_unavailable" || prediction?.analysis_status === "analysis_failed";
  const acceptedResult = prediction?.analysis_status === "completed";
  return <div>
    <div className="flex flex-wrap items-end justify-between gap-4"><div><h1 className="text-2xl font-semibold sm:text-4xl">Check a crop leaf</h1><p className="mobile-secondary mt-2 max-w-2xl text-[#adb5ad]">Choose the crop and take one clear photo. The result is a visual screening, not a confirmed diagnosis.</p></div><div className={`rounded-full border px-3 py-1.5 text-[11px] font-semibold sm:px-4 sm:py-2 sm:text-xs ${selectedModelAvailable ? "border-[#47734a] bg-[#263c29] text-[#9fd19c]" : "border-[#725d36] bg-[#382f20] text-[#ddbd78]"}`}>{selectedModelAvailable ? <><span>{cropName} ready</span><span className="mobile-secondary">{selectedModel?.validation?.accuracy ? ` · ${(selectedModel.validation.accuracy * 100).toFixed(1)}% held-out validation` : ""}</span></> : `${cropName} setup required`}</div></div>
    {error && <div role="alert" className="mt-5 rounded-xl border border-[#713d38] bg-[#402522] p-4 text-[#ffc0b5]">{error}</div>}

    <form onSubmit={analyze} className="mt-7 grid gap-5 lg:grid-cols-[1fr_.9fr]">
      <section className="overflow-hidden rounded-3xl border border-[#414741] bg-[#242825]">
        <div className="relative grid min-h-[300px] place-items-center bg-[#1d211e] sm:min-h-[390px]">
          {preview ? <img src={preview} alt="Selected plant leaf" className="h-full max-h-[520px] w-full object-contain" /> : <div className="px-6 text-center"><span className="mx-auto grid h-20 w-20 place-items-center rounded-3xl bg-[#2c392d] text-[#8ac47b]"><Camera size={36} /></span><h2 className="mt-5 text-xl font-semibold">Photograph one affected leaf</h2><p className="mx-auto mt-2 max-w-sm text-sm leading-6 text-[#919a91]">Use natural light, keep the leaf sharp, and include the full leaf. Avoid fingers covering symptoms.</p></div>}
          {preview && <span className="absolute bottom-4 left-4 rounded-full bg-black/65 px-3 py-1.5 text-xs backdrop-blur">{file?.name}</span>}
        </div>
        <div className="grid grid-cols-2 gap-3 border-t border-[#414741] p-4">
          <button type="button" onClick={() => void openCamera()} className="flex h-12 items-center justify-center gap-2 rounded-xl bg-[#347c52] font-semibold hover:bg-[#3e9160]"><Camera size={18} />Take photo</button>
          <input ref={nativeCameraRef} type="file" accept="image/jpeg,image/png,image/webp" capture="environment" onChange={chooseImage} className="sr-only" />
          <label className="flex h-12 cursor-pointer items-center justify-center gap-2 rounded-xl border border-[#525a53] font-semibold hover:bg-[#2d332e]"><Upload size={18} />Choose photo<input type="file" accept="image/jpeg,image/png,image/webp" onChange={chooseImage} className="sr-only" /></label>
        </div>
      </section>

      <section className="rounded-3xl border border-[#414741] bg-[#242825] p-5 sm:p-6"><div className="flex items-center gap-3"><span className="grid h-11 w-11 place-items-center rounded-xl bg-[#30422c] text-[#98cf82]"><Leaf size={22} /></span><div><p className="text-xs uppercase tracking-wider text-[#858f86]">Choose crop</p><h2 className="font-semibold">{cropName}</h2></div></div>
        <div className="mt-5 grid grid-cols-2 gap-3">{CROPS.map((crop) => <button type="button" key={crop.id} onClick={() => { setCropId(crop.id); setResult(null); setAdvice(null); setAdviceError(""); setError(""); }} className={`rounded-xl border p-3 text-left transition ${cropId === crop.id ? "border-[#6aa45b] bg-[#30472e]" : "border-[#4b524c] bg-[#292e2a] hover:bg-[#303631]"}`}><strong className="block text-sm">{crop.name}</strong><span className="mt-1 block text-[11px] leading-4 text-[#9aa39a]">{crop.note}</span></button>)}</div>
        <div className="mt-6 space-y-3">{[`Show one full ${cropName} leaf`, "Use bright natural light", "Keep people and other crops out of view", cropId === "tomato" ? "An uncertain result is safer than a wrong answer" : "Do not spray based only on this result"].map((tip, index) => <div key={tip} className="flex items-center gap-3 rounded-xl bg-[#2b302c] px-4 py-3 text-sm text-[#c3cac2]"><span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-[#3b5036] text-xs text-[#a9d994]">{index + 1}</span>{tip}</div>)}</div>
        {!selectedModelAvailable && <div className="mt-5 rounded-xl border border-[#6b5734] bg-[#352e22] p-4 text-sm leading-6 text-[#d3bd8a]"><AlertTriangle className="mr-2 inline" size={17} />Your photograph will be stored for review, but no condition or confidence will be invented until the trained FastAI model is installed.</div>}
        <button disabled={!file || busy} className="mt-6 flex h-13 w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-[#65994d] to-[#28704f] font-semibold hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40">{busy ? <LoaderCircle className="animate-spin" size={19} /> : <ScanSearch size={19} />}{busy ? "Checking photograph…" : `Analyze ${cropName.toLowerCase()} photo`}</button>
        <p className="mt-3 text-center text-xs text-[#7f887f]">JPEG, PNG or WebP · maximum 10 MB</p>
      </section>
    </form>

    {cameraOpen && <div className="fixed inset-0 z-[1600] flex items-center justify-center bg-black/85 p-3 backdrop-blur-sm" role="dialog" aria-modal="true" aria-label="Take a plant photograph"><div className="w-full max-w-2xl overflow-hidden rounded-3xl border border-white/15 bg-[#171b18] shadow-2xl"><div className="flex items-center justify-between border-b border-white/10 px-4 py-3 sm:px-5"><div><h2 className="font-semibold">Take a plant photo</h2><p className="text-xs text-[#aab2aa]">Place one leaf inside the frame and keep the camera steady.</p></div><button type="button" onClick={closeCamera} className="grid h-10 w-10 place-items-center rounded-full bg-white/10" aria-label="Close camera"><X size={20} /></button></div><div className="relative bg-black"><video ref={videoRef} autoPlay playsInline muted className="max-h-[70vh] min-h-[320px] w-full object-contain" />{cameraError && <div role="alert" className="absolute inset-x-3 bottom-3 rounded-xl bg-[#492923]/95 p-3 text-sm text-[#ffd0c6]">{cameraError}</div>}</div><div className="flex items-center justify-center gap-3 p-4"><button type="button" onClick={closeCamera} className="h-12 rounded-xl border border-[#596159] px-5 font-semibold">Cancel</button><button type="button" onClick={capturePhoto} className="flex h-12 items-center gap-2 rounded-xl bg-[#69a754] px-6 font-bold text-[#10200f]"><Camera size={19} />Capture photo</button></div></div></div>}

    {prediction && <section id="plant-lens-result" className="scroll-mt-24 mt-7">
      {acceptedResult ? <div className="rounded-3xl border border-[#485748] bg-gradient-to-br from-[#2d3b2c] to-[#222824] p-6 sm:p-8"><div className="flex flex-wrap items-start justify-between gap-5"><div><p className="text-xs font-bold uppercase tracking-[.18em] text-[#9fd17e]">Strong visual screening match</p><h2 className="mt-2 text-2xl font-semibold sm:text-3xl">{prediction.possible_condition}</h2><p className="mt-2 max-w-2xl text-sm text-[#aeb9ac]">{prediction.disclaimer}</p></div><div className="rounded-2xl border border-white/10 bg-black/10 px-5 py-4 text-center"><span className="block text-3xl font-semibold">{Math.round((prediction.confidence || 0) * 100)}%</span><span className="text-xs text-[#9da89a]">visual match score · not accuracy</span></div></div></div> : <div className="rounded-3xl border border-[#725d36] bg-[#382f20] p-6"><div className="flex gap-3"><AlertTriangle className="shrink-0 text-[#e0b766]" /><div><p className="text-xs font-bold uppercase tracking-[.18em] text-[#dfbc72]">{modelFailed ? "Analysis unavailable" : "No condition reported"}</p><h2 className="mt-2 text-xl font-semibold">{modelFailed ? "The AI model could not run" : prediction.possible_condition}</h2><p className="mt-2 text-sm leading-6 text-[#cdbb94]">{prediction.disclaimer}</p>{prediction.uncertainty_reason && <p className="mt-2 text-xs text-[#ad9c7a]">{prediction.uncertainty_reason}</p>}</div></div></div>}
      {acceptedResult && prediction.classification === "tomato leaf spot pattern" && prediction.leading_candidate && <div className="mt-5 rounded-2xl border border-[#5d744c] bg-[#293528] p-5"><p className="text-xs font-bold uppercase tracking-[.16em] text-[#99ca7d]">Most likely within this group</p><div className="mt-2 flex flex-wrap items-end justify-between gap-3"><h3 className="text-xl font-semibold capitalize">{prediction.leading_candidate}</h3><strong className="text-2xl">{Math.round((prediction.leading_candidate_score || 0) * 100)}%</strong></div><p className="mt-2 text-sm leading-6 text-[#afb9ab]">This is the leading model candidate, not a confirmed diagnosis. Compare the alternatives below and obtain expert confirmation before treatment.</p></div>}
      {result?.crop_id === "tomato" && <div className="mt-5 rounded-2xl border border-[#6d5b36] bg-[#342f22] p-4 text-sm leading-6 text-[#d7c691]"><ShieldCheck className="mr-2 inline" size={18} /><strong>Honesty check:</strong> this model was tested on held-out disease_dataset images, not yet on an independent Rwanda field-photo set. It may miss or confuse real field symptoms, so it will now refuse borderline results.</div>}
      {(adviceBusy || advice || adviceError) && <section className="mt-5 overflow-hidden rounded-2xl border border-[#49644c] bg-[#252e27]"><div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#3e5040] bg-[#2b392d] px-5 py-4"><div className="flex items-center gap-3"><span className="grid h-9 w-9 place-items-center rounded-xl bg-[#425f3e] text-[#b8e69d]"><Sparkles size={18} /></span><div><h3 className="font-semibold">Gemini: what to do next</h3><p className="text-xs text-[#94a594]">Evidence-aware farmer guidance</p></div></div>{advice?.status === "ready" && <span className="rounded-full bg-[#38543a] px-3 py-1 text-xs text-[#b4dda9]">Grounded sources</span>}{advice?.status === "limited" && <span className="rounded-full bg-[#5d4a2d] px-3 py-1 text-xs text-[#e1c58b]">Non-chemical fallback</span>}</div><div className="p-5">{adviceBusy && <div className="flex items-center gap-3 text-sm text-[#b8c4b7]"><LoaderCircle className="animate-spin" size={18} />Checking authoritative guidance…</div>}{adviceError && !adviceBusy && <div><p className="text-sm text-[#e5b5a8]">{adviceError}</p>{result && <button type="button" onClick={() => loadAdvice(result)} className="mt-3 flex items-center gap-2 rounded-lg border border-[#665448] px-3 py-2 text-sm hover:bg-[#342e29]"><RefreshCw size={15} />Try advice again</button>}</div>}{advice && !adviceBusy && <><div className="whitespace-pre-line text-sm leading-7 text-[#d3dbd1]">{advice.text}</div><div className="mt-5 rounded-xl border border-[#705b38] bg-[#352f23] p-4 text-xs leading-5 text-[#dbc999]"><AlertTriangle className="mr-2 inline" size={15} />{advice.safety_notice}</div>{advice.sources.length > 0 && <div className="mt-5"><p className="text-xs font-bold uppercase tracking-wider text-[#8fa38e]">Supporting sources</p><div className="mt-2 space-y-2">{advice.sources.map((source) => <a key={source.source_url} href={source.source_url} target="_blank" rel="noreferrer" className="flex items-start gap-2 text-xs leading-5 text-[#9ed08d] hover:underline"><ExternalLink size={13} className="mt-1 shrink-0" />{source.article_title}</a>)}</div></div>}<p className="mt-4 text-[11px] text-[#7f8e7e]">Generated by {advice.model} · {new Date(advice.generated_at).toLocaleString()}</p></>}</div></section>}
      <div className="mt-5 grid gap-5 lg:grid-cols-2"><InfoPanel icon={Eye} title="Visible symptoms to compare" items={prediction.visible_symptoms.length ? prediction.visible_symptoms : ["No AI symptom description is available until the trained model runs."]} /><InfoPanel icon={CheckCircle2} title="What to inspect next" items={prediction.recommended_inspection_steps} /></div>
      {prediction.alternatives.length > 0 && prediction.analysis_status !== "unsupported_image" && <section className="mt-5 rounded-2xl border border-[#414741] bg-[#242825] p-5"><h3 className="font-semibold">Other possible classes</h3><div className="mt-3 space-y-2">{prediction.alternatives.map((item) => <div key={item.label} className="flex items-center justify-between rounded-xl bg-[#2b302c] px-4 py-3 text-sm"><span className="capitalize">{item.label}</span><strong>{Math.round(item.confidence * 100)}%</strong></div>)}</div></section>}
      {(acceptedResult || prediction.expert_confirmation_required) && <div className={`mt-5 rounded-2xl border p-5 ${prediction.expert_confirmation_required ? "border-[#75563c] bg-[#382c23]" : "border-[#456848] bg-[#263829]"}`}><div className="flex items-start gap-3">{prediction.expert_confirmation_required ? <AlertTriangle className="shrink-0 text-[#e3ae69]" /> : <ShieldCheck className="shrink-0 text-[#83c486]" />}<div><h3 className="font-semibold">{prediction.expert_confirmation_required ? "Expert confirmation is needed" : "Continue field monitoring"}</h3><p className="mt-1 text-sm leading-6 text-[#b7bdb5]">Never select a pesticide or disease treatment from the image result alone. Confirm symptoms across the field and consult a qualified local agronomist or plant-health officer.</p></div></div></div>}
      <details className="mt-4 rounded-xl border border-[#414741] bg-[#242825] px-4 py-3 text-sm"><summary className="cursor-pointer font-medium">Model and supporting sources</summary><p className="mt-3 text-xs text-[#929b92]">Model: {prediction.model_version || "Not available"}</p>{prediction.sources.map((source) => <a key={source.url} href={source.url} target="_blank" rel="noreferrer" className="mt-2 block text-xs text-[#9bcb80] hover:underline">{source.title}</a>)}</details>
    </section>}

    <section className="mt-8 rounded-2xl border border-[#414741] bg-[#242825] p-5"><div className="flex items-center gap-2"><History size={18} className="text-[#8fc77d]" /><h2 className="font-semibold">Previous checks</h2></div><div className="mt-4 space-y-2">{cases.length ? cases.slice(0, 8).map((item) => <div key={item.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-[#2b302c] px-4 py-3"><div className="flex items-center gap-3"><FileImage size={18} className="text-[#94a494]" /><div><strong className="text-sm">{item.prediction?.possible_condition || "Awaiting model analysis"}</strong><p className="mt-1 text-xs text-[#8e978e]">{item.crop_name} · {new Date(item.created_at).toLocaleString()} · {item.original_filename}</p></div></div><span className="flex items-center gap-1 text-xs capitalize text-[#a8b0a7]">{item.review_status.replaceAll("_", " ")}<ChevronRight size={14} /></span></div>) : <p className="text-sm text-[#8d958d]">Your submitted plant photographs will appear here.</p>}</div></section>
  </div>;
}

function InfoPanel({ icon: Icon, title, items }: { icon: typeof Eye; title: string; items: string[] }) { return <section className="rounded-2xl border border-[#414741] bg-[#242825] p-5"><div className="flex items-center gap-2"><Icon size={18} className="text-[#9acb7e]" /><h3 className="font-semibold">{title}</h3></div><ul className="mt-4 space-y-3 text-sm leading-6 text-[#b5bdb4]">{items.map((item) => <li key={item} className="flex gap-3"><span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-[#7cab63]" />{item}</li>)}</ul></section>; }
