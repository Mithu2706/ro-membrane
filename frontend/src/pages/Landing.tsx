import { ArrowRight, BookOpenCheck, FileText, FlaskConical, Gauge, Layers, ShieldCheck, Waves } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";

interface Summary {
  membranes: number;
  verified_datasheets: number;
  sources: number;
  manufacturers: string[];
}

function SpiralMark() {
  // Stylised cross-section of a spiral-wound element
  const turns = 7;
  const pts: string[] = [];
  for (let i = 0; i <= turns * 120; i++) {
    const t = (i / 120) * Math.PI * 2;
    const r = 14 + t * 6.2;
    pts.push(`${200 + r * Math.cos(t)},${200 + r * Math.sin(t)}`);
  }
  return (
    <svg viewBox="0 0 400 400" className="h-full w-full" aria-hidden>
      <defs>
        <radialGradient id="g" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#2D7771" stopOpacity="0.35" />
          <stop offset="100%" stopColor="#102A2A" stopOpacity="0" />
        </radialGradient>
      </defs>
      <circle cx="200" cy="200" r="190" fill="url(#g)" />
      <circle cx="200" cy="200" r="186" fill="none" stroke="#F5F2EA" strokeOpacity="0.18" />
      <circle cx="200" cy="200" r="196" fill="none" stroke="#C29B58" strokeOpacity="0.35" strokeDasharray="2 6" />
      <polyline points={pts.join(" ")} fill="none" stroke="#C29B58" strokeWidth="1.4" strokeOpacity="0.85" />
      <polyline
        points={pts.map((p) => p.split(",").map((v, k) => (k === 0 ? Number(v) + 3 : Number(v) + 2)).join(",")).join(" ")}
        fill="none"
        stroke="#2D7771"
        strokeWidth="1"
        strokeOpacity="0.9"
      />
      <circle cx="200" cy="200" r="11" fill="#102A2A" stroke="#F5F2EA" strokeOpacity="0.6" />
      <g fontFamily="IBM Plex Mono, monospace" fontSize="9" fill="#F5F2EA" fillOpacity="0.55">
        <text x="300" y="70">FEED</text>
        <line x1="296" y1="73" x2="262" y2="104" stroke="#F5F2EA" strokeOpacity="0.3" />
        <text x="40" y="340">CONCENTRATE</text>
        <line x1="110" y1="330" x2="140" y2="300" stroke="#F5F2EA" strokeOpacity="0.3" />
        <text x="214" y="196">PERMEATE</text>
      </g>
    </svg>
  );
}

const STEPS = [
  { icon: Waves, title: "Specify your water", text: "Application, feed salinity, temperature, available pressure, production target and as much of the water analysis as you have." },
  { icon: Layers, title: "Screen the evidence", text: "Every catalogued element is checked against its documented operating limits, your chemistry and the conditions under which it was tested." },
  { icon: FileText, title: "Receive a defensible shortlist", text: "A recommended candidate — or a clear statement that none is supported — with alternatives, warnings and a downloadable technical report." },
];

const LAYERS = [
  { tag: "Manufacturer rating", tone: "text-teal-400", text: "Datasheet values at standard test conditions. Used for operating limits and normalised performance." },
  { tag: "Laboratory test", tone: "text-brass-400", text: "Cross-flow or element tests reported in research. Shown as context, never treated as a rating." },
  { tag: "Pilot & plant data", tone: "text-brass-400", text: "Observed performance in real installations, stored with its original feed and operating conditions." },
  { tag: "Estimate", tone: "text-ivory/70", text: "Values this platform calculates — always labelled, always with their assumptions stated." },
];

export default function Landing() {
  const [summary, setSummary] = useState<Summary | null>(null);
  useEffect(() => {
    api<Summary>("/api/catalog/summary").then(setSummary).catch(() => setSummary(null));
  }, []);

  return (
    <div>
      {/* Hero */}
      <section className="relative overflow-hidden bg-midnight text-ivory">
        <div className="grid-lines absolute inset-0" />
        <div className="relative mx-auto grid max-w-7xl items-center gap-12 px-5 pb-20 pt-16 lg:grid-cols-[1.15fr_1fr] lg:px-8 lg:pb-28 lg:pt-24">
          <div className="animate-rise">
            <div className="eyebrow !text-brass">Reverse osmosis · Membrane selection</div>
            <h1 className="mt-5 font-display text-[44px] leading-[1.04] text-ivory sm:text-[58px] lg:text-[66px]">
              Membrane selection grounded in evidence,
              <span className="italic text-brass"> not guesswork.</span>
            </h1>
            <p className="mt-6 max-w-xl text-[16.5px] leading-relaxed text-ivory/70">
              Osmora screens commercial RO elements against your feed water, operating limits and published performance data —
              and tells you plainly when the evidence is not strong enough to recommend one.
            </p>
            <div className="mt-9 flex flex-wrap items-center gap-3">
              <Link
                to="/assess"
                className="inline-flex h-12 items-center gap-2 rounded-[3px] bg-brass px-6 text-[15px] font-medium text-midnight transition-colors hover:bg-brass-400"
              >
                Start an assessment <ArrowRight className="h-4 w-4" />
              </Link>
              <a href="#method" className="inline-flex h-12 items-center px-4 text-[14px] text-ivory/70 hover:text-ivory">
                How the screening works
              </a>
            </div>
            <dl className="mt-14 grid max-w-lg grid-cols-3 gap-6 border-t border-ivory/10 pt-6">
              <div>
                <dt className="text-[11px] uppercase tracking-wider text-ivory/45">Elements catalogued</dt>
                <dd className="num mt-1 text-[28px] text-ivory">{summary?.membranes ?? "—"}</dd>
              </div>
              <div>
                <dt className="text-[11px] uppercase tracking-wider text-ivory/45">Verified datasheets</dt>
                <dd className="num mt-1 text-[28px] text-ivory">{summary?.verified_datasheets ?? "—"}</dd>
              </div>
              <div>
                <dt className="text-[11px] uppercase tracking-wider text-ivory/45">Research sources</dt>
                <dd className="num mt-1 text-[28px] text-ivory">{summary?.sources ?? "—"}</dd>
              </div>
            </dl>
          </div>
          <div className="relative mx-auto aspect-square w-full max-w-[460px] animate-rise [animation-delay:120ms]">
            <SpiralMark />
          </div>
        </div>
        {summary && summary.manufacturers.length > 0 && (
          <div className="relative border-t border-ivory/10">
            <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-10 gap-y-2 px-5 py-5 text-[12px] uppercase tracking-eyebrow text-ivory/40 lg:px-8">
              <span className="text-ivory/60">Elements from</span>
              {summary.manufacturers.map((m) => (
                <span key={m}>{m}</span>
              ))}
            </div>
          </div>
        )}
      </section>

      {/* Steps */}
      <section id="method" className="mx-auto max-w-7xl scroll-mt-20 px-5 py-20 lg:px-8">
        <div className="grid gap-12 lg:grid-cols-[1fr_2fr]">
          <div>
            <div className="eyebrow">The workflow</div>
            <h2 className="mt-3 text-[36px] leading-tight">From water analysis to a shortlist you can defend.</h2>
          </div>
          <ol className="grid gap-px overflow-hidden border border-line bg-line sm:grid-cols-3">
            {STEPS.map((s, i) => (
              <li key={s.title} className="bg-ivory-50 p-6">
                <div className="flex items-center justify-between">
                  <s.icon className="h-5 w-5 text-teal" strokeWidth={1.6} />
                  <span className="num text-[12px] text-graphite-300">0{i + 1}</span>
                </div>
                <h3 className="mt-8 text-[20px]">{s.title}</h3>
                <p className="mt-2 text-[13.5px] leading-relaxed text-graphite-500">{s.text}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* Evidence layers */}
      <section className="bg-graphite text-ivory">
        <div className="mx-auto grid max-w-7xl gap-12 px-5 py-20 lg:grid-cols-2 lg:px-8">
          <div>
            <div className="eyebrow !text-brass">Provenance first</div>
            <h2 className="mt-3 text-[36px] leading-tight text-ivory">Four kinds of evidence. Never mixed.</h2>
            <p className="mt-4 max-w-md text-[15px] leading-relaxed text-ivory/65">
              A seawater datasheet rating, a wastewater lab trial and a model estimate are not interchangeable. Each value in
              Osmora carries its source, test conditions and verification status — and missing values stay missing.
            </p>
            <div className="mt-8 flex flex-wrap gap-6 text-[13px] text-ivory/70">
              <span className="inline-flex items-center gap-2"><ShieldCheck className="h-4 w-4 text-teal-400" /> Documented limits screened first</span>
              <span className="inline-flex items-center gap-2"><BookOpenCheck className="h-4 w-4 text-brass" /> Sources cited in every report</span>
            </div>
          </div>
          <div className="divide-y divide-ivory/10 border-y border-ivory/10">
            {LAYERS.map((l) => (
              <div key={l.tag} className="grid grid-cols-[160px_1fr] gap-6 py-5">
                <div className={`text-[12px] font-semibold uppercase tracking-wider ${l.tone}`}>{l.tag}</div>
                <p className="text-[14px] leading-relaxed text-ivory/70">{l.text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Deliverables */}
      <section className="mx-auto max-w-7xl px-5 py-20 lg:px-8">
        <div className="grid gap-10 lg:grid-cols-3">
          {[
            { icon: Gauge, t: "Pressure feasibility", d: "Indicative feed-pressure range against your pump and each element's documented rating." },
            { icon: FlaskConical, t: "Chemistry screening", d: "Carbonate scaling, silica, particulate fouling, oxidants and boron — explained in plain language." },
            { icon: FileText, t: "Technical report", d: "A PDF with requirements, ranked candidates, specifications with provenance, assumptions and sources." },
          ].map((x) => (
            <div key={x.t} className="border-t-2 border-midnight pt-5">
              <x.icon className="h-5 w-5 text-brass-600" strokeWidth={1.6} />
              <h3 className="mt-4 text-[22px]">{x.t}</h3>
              <p className="mt-2 text-[14px] leading-relaxed text-graphite-500">{x.d}</p>
            </div>
          ))}
        </div>
        <div className="mt-16 grid items-center gap-8 border border-line bg-ivory-50 p-8 lg:grid-cols-[1.4fr_1fr] lg:p-10">
          <div>
            <div className="eyebrow">Honest by design</div>
            <h3 className="mt-2 text-[28px] leading-tight">When the evidence is thin, you will hear it first.</h3>
            <p className="mt-3 max-w-xl text-[14.5px] leading-relaxed text-graphite-500">
              If no element passes your hard constraints, or the documented specifications and water analysis are insufficient,
              Osmora returns <span className="font-medium text-midnight">“No supported recommendation”</span> with the reasons —
              rather than forcing a winner.
            </p>
          </div>
          <div className="flex lg:justify-end">
            <Link
              to="/assess"
              className="inline-flex h-12 items-center gap-2 rounded-[3px] bg-midnight px-6 text-[15px] font-medium text-ivory hover:bg-midnight-700"
            >
              Begin with your water <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
