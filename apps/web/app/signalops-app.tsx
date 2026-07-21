"use client";

import { useEffect, useMemo, useState } from "react";

type View = "overview" | "incidents" | "scenarios" | "evaluations" | "about";
type Evidence = { id: string; kind: string; service: string; title: string; summary: string; source: string; detail: string };

const evidence: Evidence[] = [
  { id: "ev_metric_1", kind: "metric", service: "orders-api", title: "Orders p95 increased", summary: "1,246 ms over 60 seconds · baseline 151 ms", source: "Prometheus · qry_72f", detail: "84 requests sampled. The high-latency rule persisted for three consecutive evaluations." },
  { id: "ev_trace_1", kind: "trace", service: "orders-api", title: "Payment client span was slow", summary: "Orders → Payments · 1,137 ms", source: "Jaeger · trace 9f81…441d", detail: "The client span accounts for 91% of end-to-end order latency." },
  { id: "ev_trace_2", kind: "trace", service: "payments-api", title: "Payments processing remained normal", summary: "Payments server span · 42 ms", source: "Jaeger · trace 9f81…441d", detail: "The paired server span is within the healthy 38–55 ms range, contradicting an internal Payments slowdown." },
  { id: "ev_log_1", kind: "log", service: "orders-api", title: "Dependency threshold exceeded", summary: "18 representative warnings · one message pattern", source: "Loki · qry_b19", detail: "Payment dependency duration exceeded 750 ms. Identifiers are retained only in the linked trace." },
  { id: "ev_runbook_1", kind: "runbook", service: "orders-api", title: "Dependency-path latency", summary: "Runbook F-04 · version 1.0", source: "Repository · reviewed", detail: "Compare Orders client spans with Payments server spans before attributing the failure to Payments." },
];

const services = [
  { name: "Orders", code: "orders-api", state: "degraded", rate: "42.8/s", p95: "1,246 ms", error: "3.2%", delta: "+725%" },
  { name: "Payments", code: "payments-api", state: "healthy", rate: "39.4/s", p95: "42 ms", error: "0.8%", delta: "normal" },
  { name: "Inventory", code: "inventory-api", state: "healthy", rate: "43.1/s", p95: "67 ms", error: "0.3%", delta: "normal" },
];

const scenarios = [
  { id: "F-01", name: "Slow Orders database", signal: "Database span latency", target: "orders-api" },
  { id: "F-02", name: "Payment error surge", signal: "Seeded 60% HTTP 503", target: "payments-api" },
  { id: "F-03", name: "Inventory unavailable", signal: "Readiness + reservations", target: "inventory-api" },
  { id: "F-04", name: "Orders → Payments latency", signal: "Dependency-path delay", target: "orders-api" },
];

const nav: { id: View; label: string; glyph: string }[] = [
  { id: "overview", label: "Overview", glyph: "⌁" }, { id: "incidents", label: "Incidents", glyph: "!" },
  { id: "scenarios", label: "Scenarios", glyph: "◇" }, { id: "evaluations", label: "Evaluations", glyph: "✓" },
  { id: "about", label: "System notes", glyph: "i" },
];

const configuredApi = process.env.NEXT_PUBLIC_SIGNALOPS_API_URL;
const api = configuredApi ?? (
  typeof window !== "undefined" && ["localhost", "127.0.0.1"].includes(window.location.hostname)
    ? "http://localhost:8000/api/v1"
    : "/api/v1"
);

export function SignalOpsApp() {
  const [view, setView] = useState<View>("incidents");
  const [drawer, setDrawer] = useState<Evidence | null>(null);
  const [diagnosed, setDiagnosed] = useState(true);
  const [remaining, setRemaining] = useState(161);
  const [activeScenario, setActiveScenario] = useState("F-04");
  const [toast, setToast] = useState("");
  const [fresh, setFresh] = useState("8 sec ago");

  useEffect(() => {
    const timer = window.setInterval(() => setRemaining(value => Math.max(0, value - 1)), 1000);
    const freshness = window.setInterval(() => setFresh("just now"), 10000);
    return () => { window.clearInterval(timer); window.clearInterval(freshness); };
  }, []);

  useEffect(() => {
    const source = new EventSource(`${api}/events`);
    source.addEventListener("heartbeat", () => setFresh("just now"));
    source.onerror = () => source.close();
    return () => source.close();
  }, []);

  const clock = useMemo(() => `${String(Math.floor(remaining / 60)).padStart(2, "0")}:${String(remaining % 60).padStart(2, "0")}`, [remaining]);

  function notify(message: string) {
    setToast(message); window.setTimeout(() => setToast(""), 2600);
  }

  async function runScenario(id: string) {
    setActiveScenario(id); setRemaining(180); setView("incidents"); setDiagnosed(false);
    notify(`${id} started · automatic clear in 3 minutes`);
    try { await fetch(`${api}/scenarios/runs`, { method: "POST", headers: { "Content-Type": "application/json", "X-Fault-Control-Token": "signalops-local-demo" }, body: JSON.stringify({ scenarioId: id, ttlSeconds: 180 }) }); } catch { /* local replay remains available */ }
  }

  function clearScenario() {
    setActiveScenario(""); setRemaining(0); notify("Scenario cleared · watching recovery window");
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <button className="brand" onClick={() => setView("overview")} aria-label="SignalOps overview">
          <span className="brand-mark"><i /><i /><i /></span><span>Signal<span>Ops</span></span>
        </button>
        <nav aria-label="Main navigation">
          {nav.map(item => <button key={item.id} className={view === item.id ? "nav-item active" : "nav-item"} onClick={() => setView(item.id)}><span className="nav-glyph">{item.glyph}</span>{item.label}{item.id === "incidents" && <b>1</b>}</button>)}
        </nav>
        <div className="sidebar-bottom">
          <div className="demo-flag"><span className="pulse-dot" /> Demo mode</div>
          <p>Fault controls enabled<br />Read-only diagnosis</p>
          <button className="operator"><span>SV</span><span>Sambhav<br /><small>Local operator</small></span><b>···</b></button>
        </div>
      </aside>

      <main>
        <header className="topbar">
          <div><span className="crumb">LOCAL /</span> <b>{view === "incidents" ? "INC-2407-04" : view.toUpperCase()}</b></div>
          <div className="top-actions"><span className="fresh"><i /> Telemetry {fresh}</span><button aria-label="Search">⌕ <kbd>⌘K</kbd></button><button aria-label="Notifications">◌<i className="notice" /></button></div>
        </header>
        {view === "incidents" && <IncidentView drawer={drawer} setDrawer={setDrawer} diagnosed={diagnosed} setDiagnosed={setDiagnosed} active={Boolean(activeScenario)} clock={clock} clearScenario={clearScenario} notify={notify} />}
        {view === "overview" && <Overview setView={setView} />}
        {view === "scenarios" && <Scenarios active={activeScenario} clock={clock} run={runScenario} clear={clearScenario} />}
        {view === "evaluations" && <Evaluations notify={notify} />}
        {view === "about" && <About />}
      </main>
      {drawer && <EvidenceDrawer item={drawer} close={() => setDrawer(null)} />}
      {toast && <div className="toast" role="status"><span>✓</span>{toast}</div>}
    </div>
  );
}

function IncidentView({ setDrawer, diagnosed, setDiagnosed, active, clock, clearScenario, notify }: { drawer: Evidence | null; setDrawer: (item: Evidence | null) => void; diagnosed: boolean; setDiagnosed: (v: boolean) => void; active: boolean; clock: string; clearScenario: () => void; notify: (m: string) => void }) {
  const [evidenceTab, setEvidenceTab] = useState<"analysis" | "evidence">("analysis");
  function diagnoseNow() { setDiagnosed(false); window.setTimeout(() => { setDiagnosed(true); notify("Diagnosis complete · 4 claims validated"); }, 900); }
  return <div className="page incident-page">
    <section className="incident-head">
      <div className="eyebrow-row"><span className="severity high">High</span><span className={active ? "status open" : "status resolved"}><i />{active ? "Investigating" : "Resolved"}</span><span>Started 14:31:08 · 18m 42s</span></div>
      <div className="incident-title-row"><div><h1>Orders latency on payment dependency</h1><p>p95 crossed 750 ms for 3 evaluation windows · <code>orders-api → payments-api</code></p></div><div className="incident-actions"><button className="quiet" onClick={() => notify("Incident acknowledged")}>Acknowledge</button><button className="primary" onClick={diagnoseNow}>{diagnosed ? "Run diagnosis again" : <><span className="spinner" /> Analysing evidence</>}</button><button className="square" aria-label="More incident actions">···</button></div></div>
    </section>

    {active && <section className="scenario-ribbon"><div><span className="scenario-icon">◇</span><div><b>Controlled scenario active</b><span>F-04 · 1,100 ms Orders-to-Payments dependency delay</span></div></div><div><span>Auto-clear in</span><strong>{clock}</strong><button onClick={clearScenario}>Clear now</button></div></section>}

    <section className="signal-strip" aria-label="Incident signal summary">
      <div><span>Affected path</span><strong>Orders <i>→</i> Payments</strong><small>Inventory healthy</small></div>
      <div><span>Orders p95</span><strong className="bad">1,246 <small>ms</small></strong><small>Baseline 151 ms · <b>+725%</b></small></div>
      <div><span>Payment server p95</span><strong>42 <small>ms</small></strong><small>Within normal range</small></div>
      <div><span>Evidence window</span><strong>18:42</strong><small>14:26:08 → now</small></div>
      <SignalMini />
    </section>

    <div className="investigation-grid">
      <section className="timeline-panel panel">
        <div className="panel-title"><div><span className="section-kicker">EVENT STREAM</span><h2>Incident timeline</h2></div><button>All signals⌄</button></div>
        <div className="timeline">
          <Timeline at="14:31:08" type="scenario" title="Scenario F-04 started" text="Dependency-path latency armed with a three-minute TTL." />
          <Timeline at="14:32:00" type="metric" title="Orders p95 crossed 750 ms" text="First qualifying window · 31 requests sampled." evidenceItem={evidence[0]} open={setDrawer} />
          <Timeline at="14:32:40" type="detection" title="Incident opened" text="High dependency latency persisted for three evaluations." />
          <Timeline at="14:32:43" type="trace" title="Discriminating trace retained" text="Client 1,137 ms · paired server 42 ms." evidenceItem={evidence[1]} open={setDrawer} />
          {diagnosed && <Timeline at="14:33:02" type="diagnosis" title="Diagnosis validated" text="4 claims · 100% valid citations · mock/deterministic-v1." />}
        </div>
      </section>

      <section className="analysis-panel panel">
        <div className="analysis-tabs"><button className={evidenceTab === "analysis" ? "active" : ""} onClick={() => setEvidenceTab("analysis")}>Analysis</button><button className={evidenceTab === "evidence" ? "active" : ""} onClick={() => setEvidenceTab("evidence")}>Evidence <b>{evidence.length}</b></button><span>mock · deterministic-v1</span></div>
        {evidenceTab === "analysis" ? <DiagnosisContent setDrawer={setDrawer} diagnosed={diagnosed} /> : <EvidenceList open={setDrawer} />}
      </section>
    </div>
  </div>;
}

function DiagnosisContent({ setDrawer, diagnosed }: { setDrawer: (item: Evidence) => void; diagnosed: boolean }) {
  if (!diagnosed) return <div className="diagnosis-loading"><span className="scan-line" /><div className="diagnosis-symbol">⌁</div><h3>Correlating five evidence items</h3><p>Checking citations, topology, and recommendation safety…</p></div>;
  return <div className="diagnosis-content">
    <div className="finding-label"><span>AI INFERENCE</span><span className="confidence"><i /> High confidence · 94%</span></div>
    <h2>Latency is on the dependency path,<br />not inside Payments.</h2>
    <p className="lead">The Orders client span is <b>27× slower</b> than the paired Payments server span. Payments processes the request normally; delay is introduced before it reaches the service.</p>
    <div className="cause-path"><div><span>orders-api</span><strong>1,137 ms</strong></div><div className="path-line"><i /><b>+1,095 ms</b><i /></div><div><span>payments-api</span><strong>42 ms</strong></div></div>
    <div className="claims"><div className="subhead"><span>OBSERVED FACTS</span><span>Every claim cites retained evidence</span></div>
      <Claim number="01" text="Orders p95 increased to 1,246 ms from a 151 ms baseline." refs={[evidence[0]]} open={setDrawer} />
      <Claim number="02" text="The Orders → Payments client span took 1,137 ms." refs={[evidence[1]]} open={setDrawer} />
      <Claim number="03" text="The paired Payments server span completed in 42 ms." refs={[evidence[2]]} open={setDrawer} />
    </div>
    <div className="recommendation"><div><span className="rec-icon">→</span><div><span>RECOMMENDED NEXT STEP · READ ONLY</span><p>Inspect the dependency path, proxy, and network between Orders and Payments. Compare client/server span boundaries before reviewing the Payments deployment.</p></div></div><button onClick={() => setDrawer(evidence[4])}>Open runbook ↗</button></div>
    <details><summary>Limitations and confidence rationale</summary><p>This deterministic diagnosis recognises the controlled failure mode. Confirm live network and deployment context before acting. Confidence is descriptive, not statistically calibrated.</p></details>
  </div>;
}

function Timeline({ at, type, title, text, evidenceItem, open }: { at: string; type: string; title: string; text: string; evidenceItem?: Evidence; open?: (item: Evidence) => void }) {
  return <div className={`timeline-event ${type}`}><time>{at}</time><span className="rail-dot" /><div><span className="event-type">{type}</span><h3>{title}</h3><p>{text}</p>{evidenceItem && <button onClick={() => open?.(evidenceItem)}>Inspect evidence ↗</button>}</div></div>;
}

function Claim({ number, text, refs, open }: { number: string; text: string; refs: Evidence[]; open: (item: Evidence) => void }) {
  return <div className="claim"><span>{number}</span><p>{text}</p><div>{refs.map(ref => <button key={ref.id} onClick={() => open(ref)}>{ref.kind === "metric" ? "⌁" : "↗"} {ref.id}</button>)}</div></div>;
}

function SignalMini() { return <div className="signal-mini" aria-label="Latency trend: stable then elevated"><i style={{height:"13%"}}/><i style={{height:"18%"}}/><i style={{height:"16%"}}/><i style={{height:"21%"}}/><i className="hot" style={{height:"78%"}}/><i className="hot" style={{height:"65%"}}/><i className="hot" style={{height:"92%"}}/><i className="hot" style={{height:"71%"}}/><i className="hot" style={{height:"84%"}}/></div>; }

function EvidenceList({ open }: { open: (item: Evidence) => void }) { return <div className="evidence-list"><div className="subhead"><span>RETAINED BUNDLE</span><span>5 items · 4.2 KB · bounded</span></div>{evidence.map((item, index) => <button className="evidence-row" key={item.id} onClick={() => open(item)}><span className={`kind ${item.kind}`}>{item.kind.slice(0,1).toUpperCase()}</span><span><b>{item.title}</b><small>{item.service} · {item.summary}</small></span><code>{String(index + 1).padStart(2,"0")}</code></button>)}</div>; }

function Overview({ setView }: { setView: (v: View) => void }) { return <div className="page overview-page"><section className="overview-hero"><div><span className="section-kicker">SYSTEM OVERVIEW · LIVE</span><h1>One weak signal.<br /><em>Three healthy services.</em></h1><p>SignalOps is correlating the latency change across the complete order path.</p><button className="primary" onClick={() => setView("incidents")}>Open active investigation →</button></div><div className="topology" aria-label="Service dependency map"><div className="service-node degraded"><span>Orders</span><b>1,246 ms</b><i>degraded</i></div><span className="connector alert">→</span><div className="service-node"><span>Payments</span><b>42 ms</b><i>healthy</i></div><span className="branch">↘</span><div className="service-node inventory"><span>Inventory</span><b>67 ms</b><i>healthy</i></div></div></section><section className="service-section panel"><div className="panel-title"><div><span className="section-kicker">SERVICE HEALTH</span><h2>Commerce path</h2></div><span className="fresh"><i /> Updated just now</span></div><div className="service-table"><div className="table-head"><span>Service</span><span>State</span><span>Request rate</span><span>p95 latency</span><span>Error rate</span><span>Change</span></div>{services.map(service => <div className="service-row" key={service.code}><span><b>{service.name}</b><small>{service.code}</small></span><span className={`state ${service.state}`}><i />{service.state}</span><span>{service.rate}</span><span>{service.p95}</span><span>{service.error}</span><span className={service.delta.startsWith("+") ? "bad" : "muted"}>{service.delta}</span></div>)}</div></section></div>; }

function Scenarios({ active, clock, run, clear }: { active: string; clock: string; run: (id: string) => void; clear: () => void }) { return <div className="page standard-page"><div className="page-heading"><div><span className="section-kicker">CONTROLLED FAILURE LAB</span><h1>Fault scenarios</h1><p>Allow-listed, deterministic, and self-clearing. Scenario events are excluded from blind diagnosis evidence.</p></div><div className="safety-note"><b>Safety boundary</b><span>One active fault · 10 minute maximum · demo credential required</span></div></div><div className="scenario-grid">{scenarios.map(item => <article className={active === item.id ? "scenario-card active" : "scenario-card"} key={item.id}><div><span className="scenario-number">{item.id}</span>{active === item.id && <span className="active-label"><i />Active · {clock}</span>}</div><h2>{item.name}</h2><p>{item.signal}</p><dl><div><dt>Target</dt><dd>{item.target}</dd></div><div><dt>TTL</dt><dd>03:00</dd></div></dl>{active === item.id ? <button className="danger" onClick={clear}>Clear scenario</button> : <button onClick={() => run(item.id)} disabled={Boolean(active)}>Start scenario →</button>}</article>)}</div></div>; }

function Evaluations({ notify }: { notify: (m: string) => void }) { return <div className="page standard-page"><div className="page-heading"><div><span className="section-kicker">DETERMINISTIC QUALITY GATE</span><h1>Evaluation report</h1><p>Dataset scenarios-v1 · 12 positive and 4 negative cases · prompt diagnosis-v1</p></div><button className="primary" onClick={() => notify("Evaluation complete · all deterministic gates passed")}>Run evaluation</button></div><div className="score-hero"><div><span>Overall result</span><strong>PASS</strong><small>16 / 16 cases</small></div><div className="score-grid"><Score value="100%" label="Detection recall" gate="Gate ≥ 90%" /><Score value="0%" label="False positives" gate="Gate ≤ 5%" /><Score value="100%" label="Root-cause accuracy" gate="Gate ≥ 80%" /><Score value="100%" label="Evidence validity" gate="Required" /></div></div><section className="panel eval-table"><div className="panel-title"><div><span className="section-kicker">LATEST RUN</span><h2>Per-scenario results</h2></div><code>eval_01J…72A</code></div>{scenarios.map(item => <div className="eval-row" key={item.id}><span>{item.id}</span><b>{item.name}</b><span>3 variations</span><span className="pass">✓ correct root cause</span><span>100% valid citations</span></div>)}<div className="eval-row"><span>NEG</span><b>Healthy and transient noise</b><span>4 variations</span><span className="pass">✓ correctly silent</span><span>0 incidents</span></div></section></div>; }
function Score({ value, label, gate }: { value: string; label: string; gate: string }) { return <div><strong>{value}</strong><span>{label}</span><small>{gate}</small></div>; }

function About() { return <div className="page standard-page"><div className="page-heading"><div><span className="section-kicker">SYSTEM NOTES</span><h1>Trust is an architecture.</h1><p>SignalOps separates observed telemetry, inferred conclusions, and recommended action at every boundary.</p></div></div><div className="principles"><article><span>01 · OBSERVE</span><h2>Evidence before diagnosis</h2><p>Prometheus, Loki, and Jaeger results are normalised into a bounded bundle with stable identifiers.</p></article><article><span>02 · INFER</span><h2>Every claim is cited</h2><p>Provider output is schema-validated. A nonexistent evidence reference fails the complete diagnosis.</p></article><article><span>03 · ADVISE</span><h2>No production write tools</h2><p>Recommendations are read-only. SignalOps never restarts, deploys, mutates data, or clears a real incident.</p></article></div><div className="architecture panel"><div className="arch-node">Commerce services<small>Orders · Payments · Inventory</small></div><b>→</b><div className="arch-node">Telemetry boundary<small>OpenTelemetry collector</small></div><b>→</b><div className="arch-node">Evidence stores<small>Prometheus · Loki · Jaeger</small></div><b>→</b><div className="arch-node accent">SignalOps<small>Detect · correlate · diagnose</small></div></div></div>; }

function EvidenceDrawer({ item, close }: { item: Evidence; close: () => void }) { return <div className="drawer-scrim" role="presentation" onMouseDown={close}><aside className="drawer" role="dialog" aria-modal="true" aria-label={`Evidence: ${item.title}`} onMouseDown={e => e.stopPropagation()}><div className="drawer-head"><span className={`kind ${item.kind}`}>{item.kind.slice(0,1).toUpperCase()}</span><button onClick={close} aria-label="Close evidence">×</button></div><span className="section-kicker">{item.kind.toUpperCase()} EVIDENCE</span><h2>{item.title}</h2><p className="drawer-summary">{item.summary}</p><dl><div><dt>Evidence ID</dt><dd><code>{item.id}</code></dd></div><div><dt>Service</dt><dd>{item.service}</dd></div><div><dt>Source</dt><dd>{item.source}</dd></div><div><dt>Observed</dt><dd>21 Jul 2026 · 14:32:43 UTC</dd></div></dl><section><span className="section-kicker">INTERPRETATION</span><p>{item.detail}</p></section><div className="raw-block"><span>normalised attributes</span><code>{`{\n  "windowSeconds": 60,\n  "sampleCount": 84,\n  "redacted": true\n}`}</code></div><button className="drawer-link">Open in {item.kind === "metric" ? "Prometheus" : item.kind === "log" ? "Loki" : item.kind === "runbook" ? "repository" : "Jaeger"} ↗</button></aside></div>; }
