import { useEffect, useMemo, useState } from "react";
import { Activity, AlertTriangle, Brain, Database, Gauge, LineChart, Radar, Shield, WalletCards, Zap } from "lucide-react";
import {
  acknowledgeExecution,
  BackendEvent,
  DashboardPayload,
  ExecutionStatusPayload,
  MarketsPayload,
  RiskStatusPayload,
  SourceHealth,
  StrategyScoresPayload,
  connectEventStream,
  getDashboard,
  getEvents,
  getExecutionStatus,
  getMarkets,
  getRiskStatus,
  getSources,
  getStrategyScores,
  runScan,
  transitionStrategyModel,
  verifyEndpoints,
} from "./api";

type LogItem = { time: string; message: string };
type TransitionState = "candidate" | "shadow" | "approved" | "retired";

const nav = [
  ["Command", Activity],
  ["Research", Brain],
  ["Markets", LineChart],
  ["Wallet", WalletCards],
  ["Strategy", Radar],
  ["Risk", Shield],
  ["Execution", Zap],
  ["Health", Gauge],
  ["Audit", Database],
] as const;

function fmt(value: unknown, digits = 2) {
  if (value === null || value === undefined) return "-";
  if (typeof value === "number") return Number.isFinite(value) ? value.toFixed(digits) : "-";
  return String(value);
}

function statusClass(status: string) {
  if (status === "live" || status === "clear" || status === "approved") return "good";
  if (status === "stale" || status === "loading" || status === "monitor" || status === "tight" || status === "shadow") return "warn";
  if (status === "offline" || status === "error" || status === "degraded" || status === "blocked") return "bad";
  return "muted-pill";
}

function decisionClass(decision: unknown) {
  const value = String(decision || "watch");
  if (value === "approve") return "good";
  if (value === "reject") return "bad";
  return "warn";
}

function freshnessClass(value: unknown) {
  const text = String(value || "unknown");
  if (text === "fresh") return "good";
  if (text === "warming") return "warn";
  if (text === "stale") return "bad";
  return "muted-pill";
}

function eventToLog(event: BackendEvent) {
  return `${event.type} ${JSON.stringify(event.payload)}`;
}

function compactTime(value: unknown) {
  if (!value || typeof value !== "string") return "No timestamp";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
}

function nextStrategyAction(status: string, liveEligibleCount: number) {
  if (liveEligibleCount > 0) return "Manual approval and execution secrets are the next gate.";
  if (status === "shadow") return "Collect more shadow outcomes before requesting approval.";
  if (status === "candidate") return "Promote the strongest candidate into shadow validation.";
  if (status === "retired") return "Register a replacement candidate before the next scan cycle.";
  return "Register the first model version to start the promotion ladder.";
}

export default function App() {
  const [dashboard, setDashboard] = useState<DashboardPayload | null>(null);
  const [markets, setMarkets] = useState<MarketsPayload | null>(null);
  const [risk, setRisk] = useState<RiskStatusPayload | null>(null);
  const [execution, setExecution] = useState<ExecutionStatusPayload | null>(null);
  const [strategy, setStrategy] = useState<StrategyScoresPayload | null>(null);
  const [sources, setSources] = useState<SourceHealth[]>([]);
  const [limit, setLimit] = useState(25);
  const [busy, setBusy] = useState(false);
  const [strategyBusy, setStrategyBusy] = useState(false);
  const [eventState, setEventState] = useState("connecting");
  const [logs, setLogs] = useState<LogItem[]>([{ time: new Date().toLocaleTimeString(), message: "Desktop Command Center ready" }]);
  const [operatorNote, setOperatorNote] = useState("");
  const [executionNote, setExecutionNote] = useState("");

  const addLog = (message: string) => setLogs((items) => [{ time: new Date().toLocaleTimeString(), message }, ...items].slice(0, 120));

  async function refresh() {
    try {
      const [dash, marketsPayload, riskPayload, executionPayload, strategyPayload, sourcePayload, events] = await Promise.all([
        getDashboard(),
        getMarkets(),
        getRiskStatus(),
        getExecutionStatus(),
        getStrategyScores(),
        getSources(),
        getEvents(20),
      ]);
      setDashboard(dash);
      setMarkets(marketsPayload);
      setRisk(riskPayload);
      setExecution(executionPayload);
      setStrategy(strategyPayload);
      setSources(sourcePayload.sources);
      if (events.events.length > 0) {
        setLogs((items) => [
          ...events.events.slice(-8).reverse().map((event) => ({ time: new Date(event.created_at).toLocaleTimeString(), message: eventToLog(event) })),
          ...items,
        ].slice(0, 120));
      }
    } catch (error) {
      addLog(`Backend unavailable: ${error instanceof Error ? error.message : String(error)}`);
    }
  }

  async function startScan() {
    setBusy(true);
    addLog(`Scan started limit=${limit}`);
    try {
      const result = await runScan(limit);
      addLog(`Scan completed ${JSON.stringify(result)}`);
      await refresh();
    } catch (error) {
      addLog(`Scan failed: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setBusy(false);
    }
  }

  async function checkEndpoints() {
    setBusy(true);
    addLog("Endpoint verification started");
    try {
      const result = await verifyEndpoints();
      addLog(`Endpoint verification ${JSON.stringify(result)}`);
      await refresh();
    } catch (error) {
      addLog(`Endpoint verification failed: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setBusy(false);
    }
  }

  async function applyStrategyTransition(status: TransitionState) {
    setStrategyBusy(true);
    const model = strategy?.models?.[0];
    const note = operatorNote.trim();

    addLog(`Operator transition requested ${status}${model?.version ? ` for ${String(model.version)}` : ""}`);

    try {
      const result = await transitionStrategyModel({
        status,
        notes: note || undefined,
        model_name: model?.name,
        model_version: model?.version,
      });
      addLog(`Operator transition completed ${JSON.stringify(result)}`);
      setOperatorNote("");
      await refresh();
    } catch (error) {
      addLog(`Operator transition failed: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setStrategyBusy(false);
    }
  }

  async function acknowledgeExecutionReadiness() {
    addLog("Operator execution acknowledgement requested");
    setStrategyBusy(true);
    try {
      const result = await acknowledgeExecution({
        acknowledged: true,
        note: executionNote.trim() || undefined,
        acknowledged_by: "desktop_operator",
      });
      addLog(`Execution acknowledgement saved ${JSON.stringify(result)}`);
      setExecutionNote("");
      await refresh();
    } catch (error) {
      addLog(`Execution acknowledgement failed: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setStrategyBusy(false);
    }
  }

  useEffect(() => {
    let active = true;
    let socket: { close: () => void } | null = null;

    void refresh();
    void connectEventStream(
      (event) => {
        if (!active) return;
        setEventState("live");
        addLog(eventToLog(event));
      },
      (message) => {
        if (!active) return;
        setEventState("offline");
        addLog(message);
      },
    ).then((resolvedSocket) => {
      if (!active) {
        resolvedSocket.close();
        return;
      }
      socket = resolvedSocket;
    });

    const id = window.setInterval(refresh, 15000);
    return () => {
      active = false;
      socket?.close();
      window.clearInterval(id);
    };
  }, []);

  const aggregate = dashboard?.aggregate || {};
  const shadow = dashboard?.shadow || {};
  const topMarkets = markets?.top_markets || [];
  const marketSummary = markets?.market_summary || {};
  const referenceSources = markets?.reference_sources || [];
  const latestScan = markets?.latest_scan || null;
  const riskSignals = risk?.risk_signals || {};
  const sourceHealthGate = risk?.source_health_gate || {};
  const strategyModels = strategy?.models || [];
  const strategyScores = strategy?.scores || [];
  const liveEligibleModels = strategy?.live_eligible_models || [];
  const readinessChecklist = execution?.micro_live_readiness?.items || [];
  const readinessBlockedItems = execution?.micro_live_readiness?.blocked_items || [];
  const operatorAck = execution?.micro_live_readiness?.operator_ack || null;
  const onlineSources = useMemo(() => sources.filter((source) => source.status === "live").length, [sources]);
  const strategyStatusCounts = useMemo(() => {
    return strategyModels.reduce<Record<string, number>>((acc, row) => {
      const key = String(row.status || "unknown");
      acc[key] = (acc[key] || 0) + 1;
      return acc;
    }, {});
  }, [strategyModels]);
  const latestModel = strategyModels[0] || null;
  const latestStrategyScore = strategyScores[0] || null;
  const canTransitionModel = Boolean(latestModel);
  const readinessTone = liveEligibleModels.length > 0 ? "good" : latestModel && latestModel.status === "shadow" ? "warn" : "muted-pill";
  const readinessLabel = liveEligibleModels.length > 0 ? "promotion ready" : latestModel ? String(latestModel.status || "watching") : "awaiting model";
  const readinessCopy = nextStrategyAction(String(latestModel?.status || ""), liveEligibleModels.length);

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">SA</div>
          <div>
            <div className="brand-title">SuperAjan12</div>
            <div className="brand-subtitle">Desktop Command Center</div>
          </div>
        </div>
        <nav>
          {nav.map(([label, Icon], index) => (
            <button key={label} className={index === 0 ? "nav-item active" : "nav-item"}>
              <Icon size={17} />
              <span>{label}</span>
            </button>
          ))}
        </nav>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <h1>Autonomous Research + Paper/Shadow Operations</h1>
            <p>Gercek kaynak bagliysa canli veri; kaynak yoksa acikca not configured/offline. Canli emir kapali.</p>
          </div>
          <div className="top-actions">
            <span className="pill warn">Live Orders Disabled</span>
            <span className="pill good">Mode {dashboard?.mode || "paper"}</span>
            <span className="pill muted-pill">Sources {onlineSources}/{sources.length || 9}</span>
            <span className={`pill ${eventState === "live" ? "good" : eventState === "connecting" ? "warn" : "bad"}`}>Events {eventState}</span>
          </div>
        </header>

        <section className="kpi-grid">
          <Kpi title="Scan Count" value={fmt(aggregate.scan_count, 0)} tone="blue" />
          <Kpi title="Approved" value={fmt(aggregate.approved_count, 0)} tone="green" />
          <Kpi title="Risk Blocks" value={fmt(aggregate.rejected_count, 0)} tone="red" />
          <Kpi title="Paper Positions" value={fmt(aggregate.paper_position_count, 0)} tone="yellow" />
          <Kpi title="Shadow PnL" value={fmt(shadow.total_unrealized_pnl_usdc, 2)} tone="green" />
          <Kpi title="Win Rate" value={shadow.win_rate === null || shadow.win_rate === undefined ? "-" : `${(Number(shadow.win_rate) * 100).toFixed(1)}%`} tone="blue" />
        </section>

        <section className="control-card">
          <div>
            <h2>Operations Control</h2>
            <p>Scan, endpoint check ve source health desktop sidecar backend uzerinden calisir.</p>
          </div>
          <div className="controls">
            <label>Limit</label>
            <input value={limit} onChange={(event) => setLimit(Number(event.target.value || 25))} />
            <button disabled={busy} onClick={startScan}>Scan Baslat</button>
            <button disabled={busy} className="secondary" onClick={checkEndpoints}>Endpoint Kontrol</button>
            <button disabled={busy} className="secondary" onClick={refresh}>Yenile</button>
          </div>
        </section>

        <section className="content-grid risk-grid">
          <div className="panel large">
            <div className="panel-head">
              <div>
                <h2>Market Intelligence</h2>
                <p className="section-copy">En son taramadan gelen piyasa kalitesi, derinlik ve referans durumu tek yerde.</p>
              </div>
              <div className="top-actions">
                <span className="pill muted-pill">{markets?.source_health_mode || "static"} source mode</span>
                <span className={`pill ${freshnessClass(latestScan?.freshness)}`}>Scan {String(latestScan?.freshness || "unknown")}</span>
              </div>
            </div>

            <div className="summary-strip">
              <SummaryCard title="Visible" value={fmt(marketSummary.visible_market_count, 0)} sub="ranked rows" />
              <SummaryCard title="Avg Edge" value={fmt(marketSummary.avg_edge, 4)} sub="model minus implied" />
              <SummaryCard title="Avg Spread" value={fmt(marketSummary.avg_spread_bps, 1)} sub="bps" />
              <SummaryCard title="Liquidity" value={fmt(marketSummary.total_liquidity_usdc, 0)} sub="visible USDC" />
              <SummaryCard title="Depth" value={`${fmt(marketSummary.total_bid_depth_usdc, 0)} / ${fmt(marketSummary.total_ask_depth_usdc, 0)}`} sub="bid / ask" />
              <SummaryCard title="Latest Scan" value={latestScan?.age_seconds === null || latestScan?.age_seconds === undefined ? "-" : `${fmt(latestScan.age_seconds, 0)}s`} sub={String(latestScan?.freshness || "unknown")} />
            </div>

            <table className="market-table">
              <thead>
                <tr>
                  <th>Decision</th>
                  <th>Score</th>
                  <th>Edge</th>
                  <th>Liquidity</th>
                  <th>Depth</th>
                  <th>Resolution</th>
                  <th>Reference</th>
                  <th>Question</th>
                </tr>
              </thead>
              <tbody>
                {topMarkets.length === 0 ? <tr><td colSpan={8} className="empty">No market data yet. Run a scan.</td></tr> : topMarkets.map((market, index) => (
                  <tr key={`${market.market_id}-${index}`}>
                    <td><span className={`pill ${decisionClass(market.decision)}`}>{fmt(market.decision, 0)}</span></td>
                    <td>
                      {fmt(market.score, 1)}
                      <small>{fmt(market.spread_bps, 1)} bps</small>
                    </td>
                    <td>
                      {fmt(market.edge, 4)}
                      <small>model {fmt(market.model_probability, 3)} / implied {fmt(market.implied_probability, 3)}</small>
                    </td>
                    <td>
                      {fmt(market.liquidity_usdc, 0)}
                      <small>vol {fmt(market.volume_usdc, 0)}</small>
                    </td>
                    <td>
                      {fmt(market.bid_depth_usdc, 0)} / {fmt(market.ask_depth_usdc, 0)}
                      <small>{fmt(market.orderbook_source, 0)}</small>
                    </td>
                    <td>
                      {fmt(market.resolution_confidence, 2)}
                      <small>liq {fmt(market.liquidity_confidence, 2)}</small>
                    </td>
                    <td>
                      {fmt(market.reference_confidence, 2)}
                      <small>risk {fmt(market.suggested_paper_risk_usdc, 1)} usdc</small>
                    </td>
                    <td>{fmt(market.question, 0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="panel">
            <div className="panel-head"><h2>Risk Center</h2><Shield size={18} /></div>
            <div className="summary-strip summary-strip-two">
              <SummaryCard title="Open Risk" value={fmt(risk?.capital?.current_open_risk_usdc, 1)} sub="current exposure" />
              <SummaryCard title="Risk Cap" value={fmt(risk?.capital?.max_allowed_risk_usdc, 1)} sub="remaining room" />
            </div>
            <div className="source-list source-stack compact-gap">
              {Object.entries(riskSignals).map(([name, signal]) => (
                <div className="source-row" key={name}>
                  <div className="source-body">
                    <strong>{name.replace(/_/g, " ")}</strong>
                    <div className="source-sub">{Array.isArray(signal.reasons) ? signal.reasons.join(" | ") : fmt(signal.reasons, 0)}</div>
                  </div>
                  <div className="source-meta vertical-meta">
                    <span className={`pill ${statusClass(String(signal.status || "unknown"))}`}>{fmt(signal.status, 0)}</span>
                    <span className="source-latency">confidence {fmt(signal.confidence, 2)}</span>
                    {signal.value !== null && signal.value !== undefined ? <span className="source-latency">value {fmt(signal.value, 2)}</span> : null}
                  </div>
                </div>
              ))}
              <div className="source-row">
                <div className="source-body">
                  <strong>source health gate</strong>
                  <div className="source-sub">degraded {fmt(sourceHealthGate.degraded_source_count, 0)} | breakers {fmt(sourceHealthGate.open_circuit_breakers, 0)}</div>
                </div>
                <div className="source-meta vertical-meta">
                  <span className={`pill ${Boolean(sourceHealthGate.allowed) ? "good" : "bad"}`}>{Boolean(sourceHealthGate.allowed) ? "clear" : "blocked"}</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="content-grid bottom">
          <div className="panel">
            <div className="panel-head"><h2>Reference Venues</h2><AlertTriangle size={18} /></div>
            <div className="source-list source-stack">
              {referenceSources.map((source) => (
                <div className="source-row" key={String(source.name)}>
                  <div className="source-body">
                    <strong>{fmt(source.label, 0)}</strong>
                    <div className="source-sub">{fmt(source.detail, 0)}</div>
                    {source.error ? <div className="source-error">{fmt(source.error, 0)}</div> : null}
                  </div>
                  <div className="source-meta">
                    {source.latency_ms !== null && source.latency_ms !== undefined ? <span className="source-latency">{fmt(source.latency_ms, 0)} ms</span> : null}
                    <span className={`pill ${statusClass(String(source.status || "missing"))}`}>{fmt(source.status, 0)}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
          <div className="panel">
            <div className="panel-head"><h2>Research Center</h2><span className="pill muted-pill">no fake data</span></div>
            <div className="empty-box">Research sources are shown as not configured until real providers are connected. No demo headlines are displayed.</div>
          </div>
          <div className="panel">
            <div className="panel-head"><h2>Wallet Intelligence</h2><span className="pill muted-pill">provider gated</span></div>
            <div className="empty-box">Dune / Nansen / Glassnode adapters require real API access. Wallet feed remains empty until configured.</div>
          </div>
          <div className="panel">
            <div className="panel-head"><h2>Execution Readiness</h2><span className={`pill ${execution?.micro_live_readiness?.ready ? "good" : "warn"}`}>{execution?.micro_live_readiness?.ready ? "ready" : "gated"}</span></div>
            <div className="summary-strip summary-strip-two">
              <SummaryCard title="Checklist" value={`${fmt(execution?.micro_live_readiness?.passed_count, 0)}/${fmt(execution?.micro_live_readiness?.total_count, 0)}`} sub="passed items" />
              <SummaryCard title="Approval" value={operatorAck?.acknowledged ? "acked" : "pending"} sub={operatorAck?.acknowledged_by ? String(operatorAck.acknowledged_by) : "operator gate"} />
            </div>
            <div className="source-list compact-gap">
              {readinessChecklist.length === 0 ? <div className="empty-box">No readiness items recorded yet.</div> : readinessChecklist.slice(0, 6).map((item, index) => (
                <div className="source-row" key={`${String(item.item_key || "item")}-${index}`}>
                  <div className="source-body">
                    <strong>{fmt(item.label, 0)}</strong>
                    <div className="source-sub">{fmt(item.detail, 0)}</div>
                  </div>
                  <div className="source-meta vertical-meta">
                    <span className={`pill ${item.passed ? "good" : "warn"}`}>{item.passed ? "passed" : "blocked"}</span>
                    <span className="source-latency">{fmt(item.updated_by, 0)}</span>
                  </div>
                </div>
              ))}
            </div>
            <div className="execution-ack-card">
              <div className="mini-section-title">Operator acknowledgement</div>
              <p className="operator-copy">{operatorAck?.note ? String(operatorAck.note) : readinessBlockedItems.length > 0 ? `Blocked: ${readinessBlockedItems.map((item) => String(item.item_key || "item")).join(", ")}` : "Save an operator acknowledgement when the checklist and manual review are complete."}</p>
              <div className="operator-note-wrap">
                <textarea
                  value={executionNote}
                  onChange={(event) => setExecutionNote(event.target.value)}
                  placeholder="Operator note, incident ref, or approval context"
                />
              </div>
              <div className="execution-ack-actions">
                <button disabled={strategyBusy} onClick={acknowledgeExecutionReadiness}>Acknowledgement Kaydet</button>
              </div>
            </div>
          </div>
          <div className="panel strategy-panel">
            <div className="panel-head">
              <h2>Strategy Console</h2>
              <div className="top-actions">
                <span className={`pill ${readinessTone}`}>{readinessLabel}</span>
                <Radar size={18} />
              </div>
            </div>
            <div className="strategy-banner">
              <div>
                <strong>{liveEligibleModels.length > 0 ? "Model promotion path is open" : "Promotion path is still gated"}</strong>
                <p>{readinessCopy}</p>
              </div>
              <div className="strategy-stats">
                <div>
                  <span>Live eligible</span>
                  <strong>{fmt(liveEligibleModels.length, 0)}</strong>
                </div>
                <div>
                  <span>Latest score</span>
                  <strong>{latestStrategyScore ? fmt(latestStrategyScore.score, 2) : "-"}</strong>
                </div>
              </div>
            </div>
            <div className="operator-card">
              <div className="operator-head">
                <div>
                  <div className="mini-section-title">Operator controls</div>
                  <p className="operator-copy">Readiness backend tarafinda uretilir; operator burada son gecisi ve gerekceyi kaydeder.</p>
                </div>
                <span className={`pill ${statusClass(String(latestModel?.status || "unknown"))}`}>{fmt(latestModel?.status, 0)}</span>
              </div>
              <div className="operator-grid">
                <div className="operator-actions">
                  <button disabled={strategyBusy || !canTransitionModel} className="secondary" onClick={() => applyStrategyTransition("candidate")}>Adaya Al</button>
                  <button disabled={strategyBusy || !canTransitionModel} className="secondary" onClick={() => applyStrategyTransition("shadow")}>Shadowa Gec</button>
                  <button disabled={strategyBusy || !canTransitionModel} onClick={() => applyStrategyTransition("approved")}>Approve Et</button>
                  <button disabled={strategyBusy || !canTransitionModel} className="danger" onClick={() => applyStrategyTransition("retired")}>Retire Et</button>
                </div>
                <div className="operator-note-wrap">
                  <textarea
                    value={operatorNote}
                    onChange={(event) => setOperatorNote(event.target.value)}
                    placeholder="Transition note, experiment ID, or approval context"
                  />
                  <div className="strategy-footnote">
                    <strong>Current ladder</strong>
                    <p>{strategyStatusCounts.candidate || 0} candidate, {strategyStatusCounts.shadow || 0} shadow, {strategyStatusCounts.approved || 0} approved, {strategyStatusCounts.retired || 0} retired.</p>
                    <p>Last transition: {strategy?.last_transition ? `${fmt(strategy.last_transition.from_status, 0)} -> ${fmt(strategy.last_transition.to_status, 0)} at ${compactTime(strategy.last_transition.changed_at)}` : "none recorded yet"}.</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div className="panel large">
            <div className="panel-head"><h2>Audit / Agent Activity</h2><span className="pill good">live event stream</span></div>
            <div className="log-feed">
              {logs.map((log, index) => <div key={`${log.time}-${index}`}><b>{log.time}</b> {log.message}</div>)}
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}

function Kpi({ title, value, tone }: { title: string; value: string; tone: string }) {
  return <div className={`kpi ${tone}`}><span>{title}</span><strong>{value}</strong></div>;
}

function SummaryCard({ title, value, sub }: { title: string; value: string; sub: string }) {
  return <div className="summary-card"><span>{title}</span><strong>{value}</strong><small>{sub}</small></div>;
}
