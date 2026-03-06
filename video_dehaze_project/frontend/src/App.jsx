import { useEffect, useMemo, useRef, useState, useCallback } from "react";
import {
  Camera,
  Sparkles,
  ShieldCheck,
  CloudSun,
  LogOut,
  Upload,
  Image as ImageIcon,
  Film,
  Loader2,
} from "lucide-react";
import clsx from "clsx";

const API_URL = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";

const mediaTabs = [
  { id: "image", label: "Image boost", caption: "Crystal stills", icon: ImageIcon },
  { id: "video", label: "Video revive", caption: "60s cinematic cap", icon: Film },
];

const modelPresets = {
  image: [
    { id: "auto", label: "Auto", caption: "Use backend default" },
    { id: "ffa_net", label: "FFA-Net", caption: "Neural enhancement" },
    { id: "clahe", label: "CLAHE", caption: "Classic contrast" },
  ],
  video: [
    { id: "auto", label: "Auto", caption: "Use backend default" },
    { id: "ffa_net", label: "FFA-Net", caption: "Neural enhancement" },
    { id: "clahe", label: "CLAHE", caption: "Fast contrast" },
  ],
};

const perks = [
  { icon: Sparkles, text: "Live preview with neon theme" },
  { icon: ShieldCheck, text: "JWT-secured uploads" },
  { icon: CloudSun, text: "FFmpeg-ready outputs" },
];

const initialResult = { kind: null, src: null, originalSrc: null, mime: null, downloadLabel: null, resolution: null, improvement: null };

function App() {
  const [token, setToken] = useState(() => localStorage.getItem("token"));
  const [currentUser, setCurrentUser] = useState(() => localStorage.getItem("username") || "");
  const [view, setView] = useState(() => (localStorage.getItem("token") ? "dashboard" : "auth"));
  const [authVariant, setAuthVariant] = useState("login");
  const [authForm, setAuthForm] = useState({ username: "", password: "" });
  const [authMessage, setAuthMessage] = useState("");
  const [authLoading, setAuthLoading] = useState(false);

  const [mode, setMode] = useState("image");
  const [file, setFile] = useState(null);
  const [result, setResult] = useState(initialResult);
  const [runMessage, setRunMessage] = useState("Drop your next hazy shot to get started.");
  const [runLoading, setRunLoading] = useState(false);
  const [modelChoice, setModelChoice] = useState({ image: "auto", video: "auto" });

  const fileInputRef = useRef(null);

  useEffect(() => {
    if (token) {
      localStorage.setItem("token", token);
    } else {
      localStorage.removeItem("token");
    }
  }, [token]);

  const handleAuthSubmit = async (event) => {
    event.preventDefault();
    if (!authForm.username || !authForm.password) {
      setAuthMessage("Please fill out both fields.");
      return;
    }
    setAuthLoading(true);
    setAuthMessage("");
    try {
      const endpoint = authVariant === "login" ? "login" : "register";
      const payload = new FormData();
      payload.append("username", authForm.username.trim());
      payload.append("password", authForm.password);

      const response = await fetch(`${API_URL}/${endpoint}`, { method: "POST", body: payload });
      const data = await response.json();

      if (data.status !== "success") {
        throw new Error(data.message ?? "Unexpected response");
      }

      if (authVariant === "login") {
        setToken(data.token);
        setCurrentUser(authForm.username.trim());
        localStorage.setItem("username", authForm.username.trim());
        setView("dashboard");
        setRunMessage("Welcome back! Upload a file to breathe clarity into it.");
      } else {
        setAuthVariant("login");
        setAuthMessage("Registration complete. You can log in now ✨");
      }
    } catch (error) {
      setAuthMessage(error.message);
    } finally {
      setAuthLoading(false);
    }
  };

  const handleLogout = () => {
    setToken(null);
    setCurrentUser("");
    setView("auth");
    setResult(initialResult);
    localStorage.removeItem("token");
    localStorage.removeItem("username");
  };

  const handleFileChange = (event) => {
    const selected = event.target.files?.[0];
    setFile(selected || null);
    setRunMessage(selected ? `Ready to enhance: ${selected.name}` : "Drop your next hazy shot.");
  };

  const handleRun = async () => {
    if (!token) {
      setRunMessage("Please log in before processing files.");
      setView("auth");
      return;
    }
    if (!file) {
      setRunMessage("Choose an image or video first.");
      return;
    }
    setRunLoading(true);
    setRunMessage("Brewing clarity...");
    setResult(initialResult);
    try {
      const formData = new FormData();
      formData.append("dehaze_type", mode);
      formData.append("file", file);
      formData.append("model_choice", modelChoice[mode]);

      const response = await fetch(`${API_URL}/dehaze`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });

      if (response.status === 401) {
        handleLogout();
        setRunMessage("Session expired. Please log in again.");
        return;
      }

      const data = await response.json();
      if (data.status !== "success") {
        throw new Error(data.message ?? "Processing failed");
      }

      if (data.image) {
        setResult({
          kind: "image",
          src: `data:image/jpeg;base64,${data.image}`,
          originalSrc: data.original_image ? `data:image/jpeg;base64,${data.original_image}` : null,
          downloadLabel: "Download enhanced JPG",
          resolution: data.resolution,
          improvement: data.improvement,
        });
        setRunMessage("Image restored. Enjoy the crispness!");
      } else if (data.url) {
        const absolute = data.url.startsWith("http") ? data.url : `${API_URL}${data.url}`;
        setResult({
          kind: "video",
          src: absolute,
          mime: data.mime ?? "video/mp4",
          downloadLabel: "Download processed clip",
        });
        setRunMessage("Video rendered. Ready to preview below.");
      } else {
        setRunMessage("Processing finished, but no payload returned.");
      }
    } catch (error) {
      setRunMessage(error.message);
    } finally {
      setRunLoading(false);
    }
  };

  const uploadLabel = useMemo(() => {
    const suffix = mode === "image" ? "PNG / JPG" : "MP4 / AVI";
    return `Attach ${suffix}`;
  }, [mode]);

  return (
    <div className="relative min-h-screen overflow-hidden bg-slate-950 text-white">
      <GradientBackground />
      <div className="relative z-10 flex min-h-screen flex-col px-6 py-10 lg:flex-row lg:items-center lg:justify-center lg:px-12 lg:py-16">
        <div className="w-full max-w-6xl space-y-10 lg:space-y-0 lg:gap-10 lg:flex">
          <HeroPanel />
          <div className="w-full lg:max-w-xl">
            {view === "auth" ? (
              <AuthPanel
                variant={authVariant}
                setVariant={setAuthVariant}
                form={authForm}
                setForm={setAuthForm}
                loading={authLoading}
                message={authMessage}
                onSubmit={handleAuthSubmit}
              />
            ) : (
              <DashboardPanel
                currentUser={currentUser}
                mode={mode}
                setMode={setMode}
                modelChoice={modelChoice}
                setModelChoice={setModelChoice}
                file={file}
                fileInputRef={fileInputRef}
                uploadLabel={uploadLabel}
                handleFileChange={handleFileChange}
                handleRun={handleRun}
                runLoading={runLoading}
                runMessage={runMessage}
                result={result}
                onLogout={handleLogout}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function HeroPanel() {
  return (
    <div className="glass-panel relative mb-8 flex-1 overflow-hidden p-8 lg:mb-0">
      <div className="absolute inset-0 -z-10 opacity-60">
        <div className="absolute left-0 top-1/3 h-64 w-64 rounded-full bg-neon-pink blur-[160px]" />
        <div className="absolute right-4 top-10 h-64 w-64 rounded-full bg-neon-cyan blur-[160px]" />
      </div>
      <div className="flex items-center gap-3 text-sm uppercase tracking-[0.3em] text-slate-300">
        <Sparkles className="h-4 w-4 text-neon-cyan" />
        Neptune Deck
      </div>
      <h1 className="mt-6 text-4xl font-semibold leading-tight text-white md:text-5xl">
        Elevate hazy frames into <span className="text-neon-blue">cinematic clarity</span>.
      </h1>
      <p className="mt-4 text-base text-slate-300 md:text-lg">
        Upload raw underwater or foggy footage, let our ML-powered filters work, and preview vibrant
        results instantly inside the dashboard.
      </p>
      <div className="mt-10 grid gap-4 sm:grid-cols-2">
        {perks.map((perk) => (
          <div
            key={perk.text}
            className="flex items-center gap-3 rounded-2xl border border-white/10 bg-white/5 p-4"
          >
            <perk.icon className="h-6 w-6 text-neon-cyan" />
            <span className="text-sm text-white/90">{perk.text}</span>
          </div>
        ))}
      </div>
      <div className="mt-12 flex flex-wrap items-center gap-6 rounded-2xl border border-white/10 bg-white/5 p-4">
        <Camera className="h-12 w-12 text-neon-blue" />
        <div>
          <p className="text-sm uppercase tracking-[0.2em] text-white/60">Featured workflow</p>
          <p className="text-xl font-semibold text-white">Neptune Dehaze Pipeline</p>
        </div>
      </div>
    </div>
  );
}

function AuthPanel({ variant, setVariant, form, setForm, loading, message, onSubmit }) {
  return (
    <div className="glass-panel p-8 text-white">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.4em] text-white/40">Access</p>
          <h2 className="mt-2 text-3xl font-semibold">
            {variant === "login" ? "Welcome back" : "Create account"}
          </h2>
        </div>
        <ShieldCheck className="h-10 w-10 text-neon-cyan" />
      </div>
      <div className="mt-6 flex gap-3 rounded-2xl bg-white/5 p-1">
        {["login", "register"].map((item) => (
          <button
            key={item}
            type="button"
            onClick={() => {
              setVariant(item);
              setForm({ username: "", password: "" });
            }}
            className={clsx(
              "flex-1 rounded-xl px-4 py-2 text-sm font-semibold transition",
              variant === item ? "bg-white/90 text-slate-900" : "text-white/60",
            )}
          >
            {item === "login" ? "Sign in" : "Sign up"}
          </button>
        ))}
      </div>
      <form className="mt-8 space-y-5" onSubmit={onSubmit}>
        <LabeledInput
          label="Username"
          placeholder="neptune-user"
          value={form.username}
          onChange={(e) => setForm((prev) => ({ ...prev, username: e.target.value }))}
        />
        <LabeledInput
          label="Password"
          type="password"
          placeholder="••••••••"
          value={form.password}
          onChange={(e) => setForm((prev) => ({ ...prev, password: e.target.value }))}
        />
        <button
          type="submit"
          className="mt-4 flex w-full items-center justify-center rounded-2xl bg-gradient-to-r from-neon-pink via-neon-cyan to-neon-blue py-3 text-lg font-semibold text-slate-900 transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
          disabled={loading}
        >
          {loading ? (
            <>
              <Loader2 className="mr-2 h-5 w-5 animate-spin" />
              Processing...
            </>
          ) : variant === "login" ? (
            "Enter deck"
          ) : (
            "Create account"
          )}
        </button>
      </form>
      {message && <p className="mt-4 text-sm text-neon-cyan">{message}</p>}
      <p className="mt-6 text-xs text-white/50">
        By continuing you accept our zero-watermark policy and consent to temp storage while your
        files are enhanced.
      </p>
    </div>
  );
}

function DashboardPanel({
  currentUser,
  mode,
  setMode,
  modelChoice,
  setModelChoice,
  file,
  fileInputRef,
  uploadLabel,
  handleFileChange,
  handleRun,
  runLoading,
  runMessage,
  result,
  onLogout,
}) {
  const activeModel = modelChoice[mode];

  return (
    <div className="glass-panel p-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.3em] text-white/40">Control room</p>
          <h2 className="mt-1 text-3xl font-semibold text-white">Hi {currentUser || "creator"} 👋</h2>
        </div>
        <button
          onClick={onLogout}
          className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/5 px-4 py-2 text-sm text-white transition hover:border-red-400 hover:text-red-200"
        >
          <LogOut className="h-4 w-4" /> Logout
        </button>
      </div>

      <div className="mt-8 grid gap-6">
        <div className="rounded-3xl border border-white/10 bg-white/5 p-4">
          <p className="text-xs uppercase tracking-[0.3em] text-white/40">Mode</p>
          <div className="mt-3 flex gap-3">
            {mediaTabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setMode(tab.id)}
                className={clsx(
                  "flex-1 rounded-2xl border px-4 py-3 text-left transition",
                  mode === tab.id
                    ? "border-neon-cyan bg-neon-cyan/20 text-white"
                    : "border-white/10 text-white/70 hover:border-white/30",
                )}
              >
                <div className="flex items-center gap-3">
                  <tab.icon className="h-5 w-5 text-neon-cyan" />
                  <div>
                    <p className="text-sm font-semibold">{tab.label}</p>
                    <p className="text-xs text-white/60">{tab.caption}</p>
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>

        <div className="rounded-3xl border border-white/10 bg-white/5 p-4">
          <p className="text-xs uppercase tracking-[0.3em] text-white/40">Model</p>
          <div className="mt-3 grid gap-3 sm:grid-cols-3">
            {modelPresets[mode].map((preset) => (
              <button
                key={`${mode}-${preset.id}`}
                onClick={() =>
                  setModelChoice((prev) => ({
                    ...prev,
                    [mode]: preset.id,
                  }))
                }
                className={clsx(
                  "rounded-2xl border px-4 py-3 text-left transition",
                  activeModel === preset.id
                    ? "border-neon-pink bg-neon-pink/20 text-white"
                    : "border-white/10 text-white/70 hover:border-white/30",
                )}
              >
                <p className="text-sm font-semibold">{preset.label}</p>
                <p className="text-xs text-white/60">{preset.caption}</p>
              </button>
            ))}
          </div>
        </div>

        <div className="rounded-3xl border border-dashed border-white/20 bg-slate-900/40 p-5 text-center">
          <input
            ref={fileInputRef}
            type="file"
            accept={mode === "image" ? "image/*" : "video/*"}
            className="hidden"
            onChange={handleFileChange}
          />
          <div className="flex flex-col items-center justify-center gap-4 py-6">
            <div className="rounded-full bg-white/5 p-4">
              <Upload className="h-6 w-6 text-neon-cyan" />
            </div>
            <p className="text-lg font-semibold text-white">Drag & drop your {mode}</p>
            <p className="text-sm text-white/60">
              {file ? file.name : "Up to 50 MB • auto-optimized output"}
            </p>
            <button
              onClick={() => fileInputRef.current?.click()}
              className="rounded-full border border-white/20 px-6 py-2 text-sm font-semibold text-white transition hover:border-neon-cyan hover:text-neon-cyan"
            >
              {uploadLabel}
            </button>
          </div>
        </div>

        <button
          onClick={handleRun}
          disabled={runLoading}
          className="flex w-full items-center justify-center rounded-3xl bg-gradient-to-r from-neon-blue via-neon-cyan to-neon-pink py-4 text-lg font-semibold text-slate-900 transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {runLoading ? (
            <>
              <Loader2 className="mr-2 h-5 w-5 animate-spin" />
              Dehazing...
            </>
          ) : (
            "Launch dehaze"
          )}
        </button>

        <div className="rounded-3xl border border-white/10 bg-white/5 p-5">
          <p className="text-xs uppercase tracking-[0.3em] text-white/50">Status</p>
          <p className="mt-2 text-base text-white/90">{runMessage}</p>
          <ResultPreview result={result} />
        </div>
      </div>
    </div>
  );
}

function BeforeAfterComparison({ beforeSrc, afterSrc }) {
  const [sliderPosition, setSliderPosition] = useState(50);
  const [isDragging, setIsDragging] = useState(false);
  const containerRef = useRef(null);

  const handleMouseMove = useCallback((e) => {
    if (!isDragging || !containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const percentage = Math.max(0, Math.min(100, (x / rect.width) * 100));
    setSliderPosition(percentage);
  }, [isDragging]);

  const handleMouseDown = useCallback(() => {
    setIsDragging(true);
  }, []);

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  const handleTouchMove = useCallback((e) => {
    if (!isDragging || !containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const x = e.touches[0].clientX - rect.left;
    const percentage = Math.max(0, Math.min(100, (x / rect.width) * 100));
    setSliderPosition(percentage);
  }, [isDragging]);

  useEffect(() => {
    if (isDragging) {
      window.addEventListener("mousemove", handleMouseMove);
      window.addEventListener("mouseup", handleMouseUp);
      window.addEventListener("touchmove", handleTouchMove);
      window.addEventListener("touchend", handleMouseUp);
      return () => {
        window.removeEventListener("mousemove", handleMouseMove);
        window.removeEventListener("mouseup", handleMouseUp);
        window.removeEventListener("touchmove", handleTouchMove);
        window.removeEventListener("touchend", handleMouseUp);
      };
    }
  }, [isDragging, handleMouseMove, handleMouseUp, handleTouchMove]);

  return (
    <div className="relative w-full overflow-hidden rounded-2xl border border-white/10">
      <div
        ref={containerRef}
        className="relative aspect-auto w-full cursor-col-resize"
        onMouseDown={handleMouseDown}
        onTouchStart={handleMouseDown}
      >
        {/* Before Image (Full) */}
        <img
          src={beforeSrc}
          alt="Before dehazing"
          className="block w-full object-cover"
        />
        
        {/* After Image (Clipped) */}
        <div
          className="absolute inset-0 overflow-hidden"
          style={{ clipPath: `inset(0 ${100 - sliderPosition}% 0 0)` }}
        >
          <img
            src={afterSrc}
            alt="After dehazing"
            className="block w-full object-cover"
          />
        </div>
        
        {/* Slider Line */}
        <div
          className="absolute top-0 bottom-0 w-1 bg-white shadow-lg transition-all"
          style={{ left: `${sliderPosition}%`, transform: "translateX(-50%)" }}
        >
          <div className="absolute left-1/2 top-1/2 h-12 w-12 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white bg-white/90 shadow-lg backdrop-blur-sm">
            <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
              <div className="h-0.5 w-1 bg-slate-900"></div>
              <div className="mt-1 flex gap-0.5">
                <div className="h-0.5 w-0.5 bg-slate-900"></div>
                <div className="h-0.5 w-0.5 bg-slate-900"></div>
              </div>
              <div className="h-0.5 w-1 bg-slate-900"></div>
            </div>
          </div>
        </div>
        
        {/* Labels */}
        <div className="absolute left-4 top-4 rounded-lg bg-black/60 px-3 py-1.5 text-sm font-semibold text-white backdrop-blur-sm">
          Before
        </div>
        <div className="absolute right-4 top-4 rounded-lg bg-black/60 px-3 py-1.5 text-sm font-semibold text-white backdrop-blur-sm">
          After
        </div>
      </div>
    </div>
  );
}

function ResultPreview({ result }) {
  if (!result?.kind) {
    return (
      <div className="mt-6 flex flex-col items-center justify-center rounded-2xl border border-white/10 bg-slate-900/40 py-10 text-white/50">
        <p>No render yet. Upload a file to preview the glow-up.</p>
      </div>
    );
  }

  if (result.kind === "image") {
    const improvement = result.improvement?.percentage || 0;
    const resolution = result.resolution || {};
    const hasOriginal = !!result.originalSrc;
    
    return (
      <div className="mt-6 space-y-4">
        {/* Before/After Comparison */}
        {hasOriginal ? (
          <BeforeAfterComparison
            beforeSrc={result.originalSrc}
            afterSrc={result.src}
          />
        ) : (
          <img
            src={result.src}
            alt="Enhanced visual"
            className="w-full rounded-2xl border border-white/10 object-cover"
          />
        )}
        
        {/* Resolution and Improvement Info */}
        <div className="space-y-3 rounded-2xl border border-white/10 bg-slate-900/40 p-4">
          {/* Resolution Info */}
          <div className="flex items-center justify-between text-sm">
            <span className="text-white/60">Resolution:</span>
            <div className="flex items-center gap-2">
              <span className="text-white/80">{resolution.before || "N/A"}</span>
              <span className="text-white/40">→</span>
              <span className="font-semibold text-neon-cyan">{resolution.after || "N/A"}</span>
              {resolution.changed && (
                <span className="ml-2 rounded-full bg-yellow-500/20 px-2 py-0.5 text-xs text-yellow-400">
                  Changed
                </span>
              )}
            </div>
          </div>
          
          {/* Improvement Percentage Bar */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-white/60">Haze Removal Improvement:</span>
              <span className="font-semibold text-neon-pink">{improvement.toFixed(1)}%</span>
            </div>
            <div className="h-3 w-full overflow-hidden rounded-full bg-white/10">
              <div
                className="h-full rounded-full bg-gradient-to-r from-neon-pink via-neon-cyan to-neon-blue transition-all duration-500"
                style={{ width: `${Math.min(100, Math.max(0, improvement))}%` }}
              />
            </div>
            <div className="flex items-center justify-between text-xs text-white/50">
              <span>Before</span>
              <span>After</span>
            </div>
          </div>
        </div>
        
        <a
          href={result.src}
          download="enhanced.jpg"
          className="inline-flex items-center justify-center rounded-full border border-white/20 px-5 py-2 text-sm font-semibold text-white transition hover:border-neon-cyan"
        >
          {result.downloadLabel}
        </a>
      </div>
    );
  }

  if (result.kind === "video") {
    return (
      <div className="mt-6 space-y-4">
        <video controls src={result.src} className="w-full rounded-2xl border border-white/10" />
        <a
          href={result.src}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center justify-center rounded-full border border-white/20 px-5 py-2 text-sm font-semibold text-white transition hover:border-neon-cyan"
        >
          {result.downloadLabel}
        </a>
      </div>
    );
  }

  return null;
}

function LabeledInput({ label, ...props }) {
  return (
    <label className="block text-sm font-semibold text-white/80">
      {label}
      <input
        {...props}
        className="mt-2 w-full rounded-2xl border border-white/10 bg-slate-900/40 px-4 py-3 text-white placeholder:text-white/30 focus:border-neon-cyan focus:outline-none"
      />
    </label>
  );
}

function GradientBackground() {
  return (
    <>
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top,_#0f172a,_transparent_55%)]" />
      <div className="pointer-events-none absolute -left-10 top-10 h-72 w-72 rounded-full bg-neon-pink blur-[160px]" />
      <div className="pointer-events-none absolute right-0 top-1/3 h-80 w-80 rounded-full bg-neon-blue blur-[200px]" />
      <div className="pointer-events-none absolute inset-0 opacity-30 mix-blend-screen">
        <div className="h-full w-full bg-[radial-gradient(circle,_rgba(96,165,250,0.35),_transparent_50%)]" />
      </div>
    </>
  );
}

export default App;

