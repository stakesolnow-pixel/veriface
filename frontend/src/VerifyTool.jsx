import { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import { toast, Toaster } from "sonner";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  CloudUpload,
  Glasses,
  Image as ImageIcon,
  Play,
  ShieldCheck,
  Sparkles,
  Sun,
  User,
  Download,
  RotateCcw,
  X,
} from "lucide-react";

const API = import.meta.env.VITE_API_URL || "/api";
const POLL_MS = 2500;

const STATE = {
  IDLE: "idle",
  READY: "ready",
  PROCESSING: "processing",
  COMPLETED: "completed",
  FAILED: "failed",
};

function fmtTime(seconds) {
  const s = Math.max(0, Math.floor(seconds || 0));
  const mm = String(Math.floor(s / 60)).padStart(2, "0");
  const ss = String(s % 60).padStart(2, "0");
  return `${mm}:${ss}`;
}

export default function VerifyTool() {
  const [state, setState] = useState(STATE.IDLE);
  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const [jobId, setJobId] = useState(null);
  const [elapsed, setElapsed] = useState(0);
  const [statusMsg, setStatusMsg] = useState("");
  const [videoBlobUrl, setVideoBlobUrl] = useState(null);
  const [model, setModel] = useState("sora-2");
  const [backendLive, setBackendLive] = useState(false);
  const inputRef = useRef(null);
  const tickerRef = useRef(null);
  const pollerRef = useRef(null);

  const cleanup = useCallback(() => {
    if (tickerRef.current) clearInterval(tickerRef.current);
    if (pollerRef.current) clearTimeout(pollerRef.current);
    tickerRef.current = null;
    pollerRef.current = null;
  }, []);

  useEffect(() => () => cleanup(), [cleanup]);

  useEffect(() => {
    let cancelled = false;
    const ping = async () => {
      try {
        await axios.get(`${API}/`);
        if (!cancelled) setBackendLive(true);
      } catch {
        if (!cancelled) setBackendLive(false);
      }
    };
    ping();
    const id = setInterval(ping, 15000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  const handleFiles = (files) => {
    const f = files?.[0];
    if (!f) return;
    if (!/^image\/(jpe?g|png|webp)$/i.test(f.type)) {
      toast.error("Unsupported file. Please upload a JPEG, PNG, or WEBP image.");
      return;
    }
    if (f.size > 12 * 1024 * 1024) {
      toast.error("Image too large. Max 12MB.");
      return;
    }
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setFile(f);
    setPreviewUrl(URL.createObjectURL(f));
    setState(STATE.READY);
  };

  const reset = () => {
    cleanup();
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    if (videoBlobUrl) URL.revokeObjectURL(videoBlobUrl);
    setFile(null);
    setPreviewUrl(null);
    setJobId(null);
    setElapsed(0);
    setStatusMsg("");
    setVideoBlobUrl(null);
    setState(STATE.IDLE);
    if (inputRef.current) inputRef.current.value = "";
  };

  const startGeneration = async () => {
    if (!file) return;
    setState(STATE.PROCESSING);
    setElapsed(0);
    setStatusMsg("Uploading photo…");
    try {
      const formData = new FormData();
      formData.append("image", file);
      formData.append("model", model);
      const res = await axios.post(`${API}/verify/start`, formData);
      const id = res.data.job_id;
      setJobId(id);
      setStatusMsg("Job queued · waiting for video provider…");
      const startedAt = Date.now();
      tickerRef.current = setInterval(() => {
        setElapsed((Date.now() - startedAt) / 1000);
      }, 250);

      const poll = async () => {
        try {
          const s = await axios.get(`${API}/verify/status/${id}`);
          const data = s.data;
          if (data.message) setStatusMsg(data.message);
          if (data.status === "completed") {
            cleanup();
            const dl = await axios.get(`${API}/verify/download/${id}`, {
              responseType: "blob",
            });
            const url = URL.createObjectURL(
              new Blob([dl.data], { type: "video/mp4" }),
            );
            setVideoBlobUrl(url);
            setState(STATE.COMPLETED);
            toast.success("Verification video ready");
            return;
          }
          if (data.status === "failed") {
            cleanup();
            setStatusMsg(data.error || data.message || "Generation failed");
            setState(STATE.FAILED);
            toast.error(data.error || "Generation failed");
            return;
          }
          pollerRef.current = setTimeout(poll, POLL_MS);
        } catch (e) {
          console.error(e);
          pollerRef.current = setTimeout(poll, POLL_MS);
        }
      };
      pollerRef.current = setTimeout(poll, 1200);
    } catch (e) {
      console.error(e);
      cleanup();
      setState(STATE.FAILED);
      toast.error(e.response?.data?.detail || "Failed to start generation");
    }
  };

  const downloadVideo = () => {
    if (!videoBlobUrl) return;
    const a = document.createElement("a");
    a.href = videoBlobUrl;
    a.download = `verification_${jobId || "clip"}.mp4`;
    document.body.appendChild(a);
    a.click();
    a.remove();
  };

  return (
    <main
      data-testid="verify-tool-page"
      className="relative min-h-screen overflow-hidden bg-[#F7F5F2] text-[#1C1917]"
    >
      <Toaster position="top-center" richColors />
      <div className="vf-grain absolute inset-0" aria-hidden="true" />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-40 -right-40 h-[420px] w-[420px] rounded-full bg-[#FED7AA] opacity-40 blur-3xl"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -bottom-32 -left-32 h-[360px] w-[360px] rounded-full bg-[#E7E5E4] opacity-60 blur-3xl"
      />

      <div className="relative mx-auto max-w-7xl px-5 py-8 md:px-10 md:py-14">
        <header className="vf-stagger flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#1C1917] text-white">
              <ShieldCheck className="h-5 w-5" strokeWidth={1.7} />
            </div>
            <div className="flex items-baseline gap-2">
              <span className="font-display text-xl tracking-tight">Veriface</span>
              <span className="font-mono-vf text-[11px] uppercase tracking-[0.18em] text-[#78716C]">
                / sora 2 liveness
              </span>
            </div>
          </div>
          <div className="hidden items-center gap-2 rounded-full border border-[#E7E5E4] bg-white px-4 py-2 text-xs text-[#78716C] md:flex">
            <span className="vf-dot" /> {backendLive ? "Backend live" : "Backend offline"}
          </div>
        </header>

        <section className="mt-12 grid grid-cols-1 gap-10 md:mt-20 md:grid-cols-12 md:gap-12">
          <div className="vf-stagger delay-1 md:col-span-9">
            <div className="font-mono-vf mb-5 inline-flex items-center gap-2 rounded-full border border-[#E7E5E4] bg-white px-3 py-1 text-[11px] uppercase tracking-[0.22em] text-[#78716C]">
              <Sparkles className="h-3 w-3" strokeWidth={2} /> identity verification clip
            </div>
            <h1 className="font-display text-4xl leading-[0.95] sm:text-5xl lg:text-7xl">
              Turn one photo
              <br />
              <span className="text-[#C2410C]">into a head-turn</span>
              <br />
              proof of life.
            </h1>
            <p className="mt-7 max-w-2xl text-base leading-relaxed text-[#44403C] md:text-lg">
              Upload a portrait. Our pipeline animates the same person looking
              <span className="mx-1 font-semibold">left</span>
              then
              <span className="mx-1 font-semibold">right</span>
              — a 12-second 720p clip you can hand to any KYC reviewer.
            </p>
          </div>

          <div className="vf-stagger delay-2 hidden md:col-span-3 md:flex md:flex-col md:items-end md:justify-end">
            <div className="space-y-2 text-right">
              <div className="font-mono-vf text-[11px] uppercase tracking-[0.22em] text-[#78716C]">
                pipeline
              </div>
              <div className="flex items-center gap-2 text-sm text-[#44403C]">
                <span className="inline-flex items-center gap-1 rounded-lg border border-[#E7E5E4] bg-white px-2 py-1">
                  <ImageIcon className="h-3.5 w-3.5" /> photo
                </span>
                <ArrowLeft className="h-3.5 w-3.5 rotate-180 text-[#A8A29E]" />
                <span className="inline-flex items-center gap-1 rounded-lg border border-[#E7E5E4] bg-white px-2 py-1">
                  <ArrowLeft className="h-3.5 w-3.5" /> left
                </span>
                <ArrowLeft className="h-3.5 w-3.5 rotate-180 text-[#A8A29E]" />
                <span className="inline-flex items-center gap-1 rounded-lg border border-[#E7E5E4] bg-white px-2 py-1">
                  right <ArrowRight className="h-3.5 w-3.5" />
                </span>
                <ArrowLeft className="h-3.5 w-3.5 rotate-180 text-[#A8A29E]" />
                <span className="inline-flex items-center gap-1 rounded-lg border border-[#E7E5E4] bg-white px-2 py-1">
                  <Play className="h-3.5 w-3.5" /> mp4
                </span>
              </div>
            </div>
          </div>
        </section>

        <section className="vf-stagger delay-3 mt-12 grid grid-cols-1 gap-6 md:mt-16 md:grid-cols-12">
          <div className="md:col-span-8">
            {state === STATE.IDLE && (
              <UploadZone
                dragOver={dragOver}
                setDragOver={setDragOver}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragOver(false);
                  handleFiles(e.dataTransfer.files);
                }}
                inputRef={inputRef}
                handleFiles={handleFiles}
              />
            )}
            {state === STATE.READY && (
              <ReadyPanel
                previewUrl={previewUrl}
                model={model}
                onModelChange={setModel}
                onGenerate={startGeneration}
                onReset={reset}
              />
            )}
            {state === STATE.PROCESSING && (
              <ProcessingPanel
                previewUrl={previewUrl}
                elapsed={elapsed}
                statusMsg={statusMsg}
                onCancel={reset}
              />
            )}
            {state === STATE.COMPLETED && (
              <ResultPanel
                videoBlobUrl={videoBlobUrl}
                onDownload={downloadVideo}
                onReset={reset}
              />
            )}
            {state === STATE.FAILED && (
              <FailedPanel message={statusMsg} onReset={reset} />
            )}
          </div>

          <aside className="md:col-span-4">
            <GuidelinesCard />
          </aside>
        </section>

        <footer className="vf-stagger delay-4 mt-16 flex flex-col gap-4 border-t border-[#E7E5E4] pt-8 text-xs text-[#78716C] md:flex-row md:items-center md:justify-between">
          <div className="font-mono-vf uppercase tracking-[0.18em]">
            Veriface · powered by Sora 2 · no images stored
          </div>
          <div className="flex flex-wrap gap-4 font-mono-vf uppercase tracking-[0.14em]">
            <span>1280 × 720</span>
            <span>12s mp4</span>
            <span>~2–6 min generation</span>
          </div>
        </footer>
      </div>
    </main>
  );
}

function UploadZone({ dragOver, setDragOver, onDrop, inputRef, handleFiles }) {
  return (
    <div
      data-testid="upload-dropzone"
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={onDrop}
      onClick={() => inputRef.current?.click()}
      className={`flex min-h-[420px] cursor-pointer flex-col items-center justify-center rounded-[28px] border border-dashed bg-white px-8 py-16 text-center shadow-[0_8px_40px_rgba(28,25,23,0.04)] transition-colors ${
        dragOver
          ? "border-[#C2410C] bg-[#FFF7ED]"
          : "border-[#E7E5E4] hover:border-[#D6D3D1]"
      }`}
    >
      <div className="mb-6 flex h-14 w-14 items-center justify-center rounded-2xl bg-[#1C1917] text-white">
        <CloudUpload className="h-6 w-6" strokeWidth={1.7} />
      </div>
      <h2 className="text-xl font-semibold tracking-tight">Drop a photo, or click to browse</h2>
      <p className="mt-3 max-w-sm text-sm leading-relaxed text-[#78716C]">
        JPEG, PNG, or WEBP up to 12MB. Front-facing portrait works best.
      </p>
      <div className="mt-8 flex gap-3 font-mono-vf text-[11px] uppercase tracking-[0.18em] text-[#A8A29E]">
        <span>jpg</span>
        <span>png</span>
        <span>webp</span>
      </div>
      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        className="sr-only"
        data-testid="file-input"
        onChange={(e) => handleFiles(e.target.files)}
      />
    </div>
  );
}

function ModelToggle({ model, onModelChange }) {
  const opts = [
    { id: "sora-2", label: "Sora 2", hint: "fast" },
    { id: "sora-2-pro", label: "Sora 2 Pro", hint: "higher quality" },
  ];
  return (
    <div
      data-testid="model-toggle"
      className="mt-6 inline-flex items-center gap-1 rounded-full border border-[#E7E5E4] bg-[#FAFAF9] p-1"
    >
      {opts.map((o) => {
        const active = model === o.id;
        return (
          <button
            key={o.id}
            type="button"
            onClick={() => onModelChange(o.id)}
            className={`rounded-full px-4 py-2 text-sm transition-colors ${
              active
                ? "bg-[#1C1917] text-white"
                : "text-[#78716C] hover:text-[#1C1917]"
            }`}
          >
            {o.label}
            <span className={`ml-2 text-[11px] ${active ? "text-white/60" : "text-[#A8A29E]"}`}>
              {o.hint}
            </span>
          </button>
        );
      })}
    </div>
  );
}

function ReadyPanel({ previewUrl, model, onModelChange, onGenerate, onReset }) {
  return (
    <div className="rounded-[28px] border border-[#E7E5E4] bg-white p-6 shadow-[0_8px_40px_rgba(28,25,23,0.04)] md:p-8">
      <div className="grid gap-6 md:grid-cols-[180px_1fr] md:items-center">
        <img
          src={previewUrl}
          alt="Upload preview"
          className="aspect-[3/4] w-full rounded-2xl object-cover"
        />
        <div>
          <h2 className="text-xl font-semibold tracking-tight">Portrait ready</h2>
          <p className="mt-2 text-sm text-[#78716C]">
            Choose a model, then generate a 12-second left → right verification clip.
          </p>
          <ModelToggle model={model} onModelChange={onModelChange} />
          <div className="mt-8 flex flex-wrap gap-3">
            <button
              data-testid="generate-video-button"
              type="button"
              onClick={onGenerate}
              className="inline-flex items-center gap-2 rounded-full bg-[#1C1917] px-6 py-3 text-sm font-medium text-white transition-colors hover:bg-[#292524]"
            >
              <Sparkles className="h-4 w-4" /> Generate verification video
            </button>
            <button
              type="button"
              onClick={onReset}
              className="rounded-full border border-[#E7E5E4] bg-white px-6 py-3 text-sm text-[#1C1917] transition-colors hover:bg-stone-100"
            >
              Change photo
            </button>
          </div>
          <p className="mt-3 text-xs text-[#78716C]">
            ~{model === "sora-2-pro" ? "4–6" : "2–4"} min on {model === "sora-2-pro" ? "Sora 2 Pro" : "Sora 2"}
            {" · "}local mock renders in seconds
          </p>
        </div>
      </div>
    </div>
  );
}

function ProcessingPanel({ previewUrl, elapsed, statusMsg, onCancel }) {
  return (
    <div className="rounded-[28px] border border-[#E7E5E4] bg-white p-6 shadow-[0_8px_40px_rgba(28,25,23,0.04)] md:p-8">
      <div className="grid gap-6 md:grid-cols-[160px_1fr] md:items-center">
        <div className="relative overflow-hidden rounded-2xl">
          <img src={previewUrl} alt="" className="aspect-[3/4] w-full object-cover opacity-80" />
          <div className="absolute inset-0 bg-gradient-to-t from-black/40 to-transparent" />
        </div>
        <div>
          <div className="font-mono-vf text-[11px] uppercase tracking-[0.2em] text-[#C2410C]">
            {fmtTime(elapsed)}
          </div>
          <h2 className="mt-2 text-xl font-semibold tracking-tight">Generating on Sora 2</h2>
          <p className="mt-2 text-sm text-[#78716C]">
            look left · hold · look right · render
          </p>
          <p className="mt-4 text-sm text-[#44403C]">{statusMsg}</p>
          <div className="vf-progress mt-6" />
          <button
            data-testid="cancel-job-button"
            type="button"
            onClick={onCancel}
            className="mt-8 rounded-full border border-[#E7E5E4] bg-white px-6 py-3 text-sm text-[#1C1917] transition-colors hover:bg-stone-100"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

function ResultPanel({ videoBlobUrl, onDownload, onReset }) {
  return (
    <div className="rounded-[28px] border border-[#E7E5E4] bg-white p-6 shadow-[0_8px_40px_rgba(28,25,23,0.04)] md:p-8">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold tracking-tight">Verification video ready</h2>
          <p className="mt-1 text-sm text-[#78716C]">
            Subject turns left, then right. Use this clip as the verification artefact.
          </p>
        </div>
        <span className="font-mono-vf shrink-0 rounded-full border border-[#E7E5E4] px-3 py-1 text-[11px] uppercase tracking-[0.14em] text-[#78716C]">
          mp4 · 720p · 12s
        </span>
      </div>
      <video
        data-testid="verification-video-player"
        src={videoBlobUrl}
        controls
        autoPlay
        loop
        playsInline
        className="aspect-video w-full rounded-2xl border border-[#E7E5E4] bg-black object-cover shadow-[0_8px_32px_rgba(0,0,0,0.08)]"
      />
      <div className="mt-6 flex flex-wrap gap-3">
        <button
          type="button"
          onClick={onDownload}
          className="inline-flex items-center gap-2 rounded-full bg-[#1C1917] px-6 py-3 text-sm font-medium text-white transition-colors hover:bg-[#292524]"
        >
          <Download className="h-4 w-4" /> Download mp4
        </button>
        <button
          type="button"
          onClick={onReset}
          className="inline-flex items-center gap-2 rounded-full border border-[#E7E5E4] bg-white px-6 py-3 text-sm text-[#1C1917] transition-colors hover:bg-stone-100"
        >
          <RotateCcw className="h-4 w-4" /> New photo
        </button>
      </div>
    </div>
  );
}

function FailedPanel({ message, onReset }) {
  return (
    <div className="rounded-[28px] border border-[#FECACA] bg-white p-8 shadow-[0_8px_40px_rgba(28,25,23,0.04)]">
      <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-full bg-[#FEE2E2] text-[#B91C1C]">
        <X className="h-5 w-5" />
      </div>
      <h2 className="text-xl font-semibold tracking-tight">Generation failed</h2>
      <p className="mt-2 text-sm text-[#78716C]">
        {message || "Sora 2 couldn't produce the verification clip. Try a clearer front-facing photo."}
      </p>
      <button
        type="button"
        onClick={onReset}
        className="mt-8 rounded-full bg-[#1C1917] px-6 py-3 text-sm font-medium text-white"
      >
        Try another photo
      </button>
    </div>
  );
}

function GuidelinesCard() {
  const tips = [
    { icon: User, text: "One person, centered, head & shoulders." },
    { icon: Sun, text: "Even lighting, no harsh shadows." },
    { icon: Glasses, text: "Remove sunglasses, hats and face coverings." },
    { icon: ImageIcon, text: "Sharp focus, plain background ideal." },
  ];
  return (
    <div className="space-y-4">
      <div className="rounded-[28px] border border-[#E7E5E4] bg-white p-5 shadow-[0_8px_40px_rgba(28,25,23,0.04)]">
        <div className="font-mono-vf text-[11px] uppercase tracking-[0.22em] text-[#78716C]">
          photo guidelines
        </div>
        <h3 className="mt-2 text-lg font-semibold tracking-tight">Get the best result</h3>
        <div className="relative mt-4 overflow-hidden rounded-2xl">
          <img
            src="https://images.unsplash.com/photo-1666577624653-b6f0043fed0e?w=800&q=80"
            alt="Perfect example portrait"
            className="aspect-[4/5] w-full object-cover"
          />
          <div className="absolute bottom-3 left-3 inline-flex items-center gap-1.5 rounded-full bg-white/95 px-3 py-1 text-xs font-medium text-[#15803D]">
            <Check className="h-3.5 w-3.5" strokeWidth={2.5} /> Perfect example
          </div>
          <div className="absolute top-3 right-3 rounded-full bg-black/50 px-2.5 py-1 font-mono-vf text-[10px] uppercase tracking-[0.16em] text-white">
            do
          </div>
        </div>
        <ul className="mt-5 space-y-3">
          {tips.map(({ icon: Icon, text }) => (
            <li key={text} className="flex gap-3 text-sm leading-snug text-[#44403C]">
              <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-[#F5F5F4] text-[#1C1917]">
                <Icon className="h-3.5 w-3.5" strokeWidth={1.8} />
              </span>
              {text}
            </li>
          ))}
        </ul>
      </div>

      <div className="rounded-[28px] bg-[#1C1917] p-5 text-[#E7E5E4]">
        <div className="font-mono-vf text-[11px] uppercase tracking-[0.22em] text-[#A8A29E]">
          how it works
        </div>
        <p className="mt-3 text-sm leading-relaxed">
          Your photo is sent to Sora 2 with a strict liveness prompt. The model synthesises a
          12-second clip of the same person looking left, then right.
        </p>
        <p className="mt-4 text-xs leading-relaxed text-[#A8A29E]">
          Subject to Sora 2&apos;s content policy. Some photos of public figures or third parties
          may be blocked by upstream moderation — best results are with your own portrait or
          clearly generated / stylised faces.
        </p>
      </div>
    </div>
  );
}
