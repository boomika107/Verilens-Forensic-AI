import { useEffect, useState } from "react";
import { Routes, Route, Navigate, Link, useNavigate, useParams, Outlet } from "react-router-dom";
import { PieChart, Pie, Cell, Tooltip } from "recharts";
import ReactFlow, { Background, Controls, Node, Edge } from "reactflow"; import "reactflow/dist/style.css";
import { Shield, LayoutDashboard, FolderOpen, LogOut, ScrollText } from "lucide-react";
import { api, errMsg, DISCLAIMER } from "./api";

const Err = ({ e }: { e: string }) => (e ? <div className="text-sm text-red-300 my-2">{e}</div> : null);
const Field = (p: any) => <input className="inp" {...p} />;

function Login() {
  const nav = useNavigate(); const [reg, setReg] = useState(false); const [f, setF] = useState({ username: "", email: "", password: "" }); const [e, setE] = useState("");
  const go = async () => { try { const r = await api.post(reg ? "/api/auth/register" : "/api/auth/login", f); localStorage.setItem("vl_token", r.data.token); nav("/"); } catch (x) { setE(errMsg(x)); } };
  return (<div className="min-h-screen grid place-items-center p-4"><div className="panel w-full max-w-sm space-y-3">
    <div className="flex items-center gap-2 text-cyan-300"><Shield /><div><div className="font-bold tracking-wide">VERILENS FORENSIC AI</div><div className="text-xs text-slate-400">Multimodal Forensic Evidence Intelligence Platform</div></div></div>
    <Field placeholder="Username" value={f.username} onChange={(x: any) => setF({ ...f, username: x.target.value })} />
    {reg && <Field placeholder="Email" value={f.email} onChange={(x: any) => setF({ ...f, email: x.target.value })} />}
    <Field type="password" placeholder="Password (min 8)" value={f.password} onChange={(x: any) => setF({ ...f, password: x.target.value })} />
    <Err e={e} /><button className="btn w-full" onClick={go}>{reg ? "Register" : "Log in"}</button>
    <button className="text-xs text-cyan-300" onClick={() => setReg(!reg)}>{reg ? "Have an account? Log in" : "Create account (first user becomes administrator)"}</button>
    <p className="text-[11px] text-slate-500">Analyze Evidence. Reveal Connections. Support Justice.</p></div></div>);
}

function Layout() {
  const nav = useNavigate(); const [u, setU] = useState<any>(null);
  useEffect(() => { api.get("/api/auth/me").then((r) => setU(r.data)).catch(() => nav("/login")); }, []);
  if (!u) return null;
  const L = ({ to, icon, children }: any) => <Link to={to} className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm hover:bg-cyan-400/10">{icon}{children}</Link>;
  return (<div className="flex min-h-screen"><aside className="w-56 shrink-0 border-r border-cyan-400/10 p-3 space-y-1">
    <div className="flex items-center gap-2 px-2 py-3 text-cyan-300 font-bold text-sm"><Shield size={18} />VERILENS</div>
    <L to="/" icon={<LayoutDashboard size={16} />}>Dashboard</L><L to="/cases" icon={<FolderOpen size={16} />}>Cases</L>
    {u.role !== "investigator" && <L to="/audit" icon={<ScrollText size={16} />}>Audit Logs</L>}
    <button className="flex items-center gap-2 px-3 py-2 text-sm text-slate-400" onClick={() => { localStorage.removeItem("vl_token"); nav("/login"); }}><LogOut size={16} />Log out</button>
    <div className="px-3 pt-4 text-xs text-slate-500">{u.username} · {u.role}</div></aside>
    <main className="flex-1 p-6 space-y-4 min-w-0"><Outlet /><p className="text-[11px] text-slate-500 pt-6">{DISCLAIMER}</p></main></div>);
}

function Dashboard() {
  const [d, setD] = useState<any>(null);
  useEffect(() => { api.get("/api/dashboard").then((r) => setD(r.data)); }, []);
  if (!d) return <div>Loading…</div>;
  const dist = Object.entries(d.status_distribution).map(([name, value]) => ({ name, value: value as number }));
  const stat = (l: string, v: number) => <div className="panel"><div className="text-2xl font-semibold text-cyan-300">{v}</div><div className="text-xs text-slate-400">{l}</div></div>;
  return (<><h1 className="text-xl font-semibold">Dashboard</h1>
    <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">{stat("Total cases", d.total_cases)}{stat("Active cases", d.active_cases)}{stat("Evidence files", d.evidence_files)}{stat("Completed analyses", d.completed_analyses)}{stat("Pending human reviews", d.pending_reviews)}</div>
    <div className="grid lg:grid-cols-3 gap-3">
      <div className="panel"><h3 className="text-sm mb-2">Case status</h3>{dist.length ? <PieChart width={220} height={180}><Pie data={dist} dataKey="value" nameKey="name" outerRadius={70} label>{dist.map((_, i) => <Cell key={i} fill={["#22d3ee", "#14b8a6", "#64748b"][i % 3]} />)}</Pie><Tooltip /></PieChart> : <p className="text-sm text-slate-400">No cases yet.</p>}</div>
      <div className="panel"><h3 className="text-sm mb-2">Recent processing jobs</h3>{d.recent_jobs.map((j: any) => <div key={j.id} className="text-xs py-1">{j.kind} · {j.status} · {j.message}</div>)}{!d.recent_jobs.length && <p className="text-sm text-slate-400">None.</p>}</div>
      <div className="panel"><h3 className="text-sm mb-2">Recent activity</h3>{d.recent_activity.map((a: any) => <div key={a.id} className="text-xs py-1">{a.action} · {a.detail.slice(0, 50)}</div>)}</div></div></>);
}

function Cases() {
  const [cs, setCs] = useState<any[]>([]); const [q, setQ] = useState(""); const [f, setF] = useState({ title: "", description: "", category: "general" }); const [e, setE] = useState("");
  const load = () => api.get("/api/cases", { params: { q } }).then((r) => setCs(r.data));
  useEffect(() => { load(); }, [q]);
  const create = async () => { try { await api.post("/api/cases", f); setF({ title: "", description: "", category: "general" }); setE(""); load(); } catch (x) { setE(errMsg(x)); } };
  const demo = async () => { try { await api.post("/api/demo/reset"); load(); } catch (x) { setE(errMsg(x)); } };
  return (<><h1 className="text-xl font-semibold">Cases</h1>
    <div className="panel grid md:grid-cols-4 gap-2"><Field placeholder="Case title" value={f.title} onChange={(x: any) => setF({ ...f, title: x.target.value })} /><Field placeholder="Description" value={f.description} onChange={(x: any) => setF({ ...f, description: x.target.value })} /><Field placeholder="Category" value={f.category} onChange={(x: any) => setF({ ...f, category: x.target.value })} />
      <div className="flex gap-2"><button className="btn" onClick={create}>Create case</button><button className="btn2" onClick={demo}>Load synthetic demo</button></div><Err e={e} /></div>
    <Field placeholder="Search cases…" value={q} onChange={(x: any) => setQ(x.target.value)} />
    <div className="space-y-2">{cs.map((c) => <Link key={c.id} to={`/cases/${c.case_id}`} className="panel block hover:border-cyan-400/40"><b>{c.case_id}</b> — {c.title} <span className="text-xs text-slate-400">[{c.status}]</span></Link>)}</div></>);
}

const TABS = ["Evidence", "Statements", "Timeline", "Findings", "Graph", "Assistant", "Reports"];
function CaseView() {
  const { cid } = useParams(); const [c, setC] = useState<any>(null); const [tab, setTab] = useState("Evidence");
  useEffect(() => { api.get(`/api/cases/${cid}`).then((r) => setC(r.data)); }, [cid]);
  if (!c) return <div>Loading…</div>;
  return (<><h1 className="text-xl font-semibold">{c.case_id} — {c.title}</h1>{c.synthetic && <div className="text-amber-300 text-sm">SYNTHETIC demonstration data — not real evidence.</div>}
    <div className="flex gap-1 flex-wrap">{TABS.map((t) => <button key={t} className={t === tab ? "btn" : "btn2"} onClick={() => setTab(t)}>{t}</button>)}</div>
    {tab === "Evidence" && <EvidenceTab cid={cid!} />}{tab === "Statements" && <StatementsTab cid={cid!} />}{tab === "Timeline" && <TimelineTab cid={cid!} />}
    {tab === "Findings" && <FindingsTab cid={cid!} />}{tab === "Graph" && <GraphTab cid={cid!} />}{tab === "Assistant" && <AssistantTab cid={cid!} />}{tab === "Reports" && <ReportsTab cid={cid!} />}</>);
}

function EvidenceTab({ cid }: { cid: string }) {
  const [ev, setEv] = useState<any[]>([]); const [e, setE] = useState(""); const [sd, setSd] = useState(""); const [st, setSt] = useState(""); const [sel, setSel] = useState<any>(null); const [busy, setBusy] = useState(0);
  const load = () => api.get(`/api/cases/${cid}/evidence`).then((r) => setEv(r.data)); useEffect(() => { load(); }, [cid]);
  const up = async (file: File) => { const fd = new FormData(); fd.append("file", file); if (sd) fd.append("start_date", sd); if (st) fd.append("start_time", st); try { await api.post(`/api/cases/${cid}/evidence`, fd); setE(""); load(); } catch (x) { setE(errMsg(x)); } };
  const run = async (id: number) => { setBusy(id); try { await api.post(`/api/evidence/${id}/analyze`); setE(""); } catch (x) { setE(errMsg(x)); } setBusy(0); load(); };
  const ver = async (id: number) => { const r = await api.post(`/api/evidence/${id}/verify`); alert(`${r.data.match ? "MATCH" : "MISMATCH"}\n${r.data.note}`); load(); };
  const show = async (id: number) => setSel((await api.get(`/api/evidence/${id}`)).data);
  return (<div className="space-y-3"><div className="panel space-y-2" onDragOver={(x) => x.preventDefault()} onDrop={(x) => { x.preventDefault(); const f = x.dataTransfer.files[0]; if (f) up(f); }}>
    <div className="text-sm">Drag & drop evidence here, or <input type="file" onChange={(x) => x.target.files?.[0] && up(x.target.files[0])} /></div>
    <div className="flex gap-2 text-xs items-center">Recording start (optional, for video/audio wall-clock times):<Field type="date" value={sd} onChange={(x: any) => setSd(x.target.value)} style={{ width: 150 }} /><Field type="time" step="1" value={st} onChange={(x: any) => setSt(x.target.value)} style={{ width: 130 }} /></div>
    <p className="text-[11px] text-slate-400">Without a start time, video/audio events are placed by offset only and stay off the dated timeline. A SHA-256 match shows the stored file is unchanged, not that it is authentic.</p><Err e={e} /></div>
    {ev.map((x) => <div key={x.id} className="panel text-sm space-y-1"><div><b>{x.original_name}</b> · {x.kind} · {(x.size / 1024).toFixed(1)} KB · <span className="text-cyan-300">{x.status}</span></div>
      <div className="font-mono text-[11px] text-slate-400 break-all">SHA-256 {x.sha256}</div>{x.error && <Err e={x.error} />}{x.last_integrity && <div className="text-xs">Integrity: {x.last_integrity}</div>}
      <div className="flex gap-2"><button className="btn" disabled={busy === x.id} onClick={() => run(x.id)}>{busy === x.id ? "Processing…" : "Analyze"}</button><button className="btn2" onClick={() => ver(x.id)}>Verify hash</button><button className="btn2" onClick={() => show(x.id)}>View extraction</button></div></div>)}
    {sel && <div className="panel text-xs max-h-96 overflow-auto"><b>Extraction for {sel.original_name}</b>{sel.analysis?.detector && <div>Detector: {sel.analysis.detector}</div>}{sel.analysis?.language && <div>Language: {sel.analysis.language} ({sel.analysis.model})</div>}
      {(sel.analysis?.pages || []).map((p: any, i: number) => <div key={i} className="py-1"><span className="text-cyan-300">[{p.ref}]</span> {p.text}</div>)}
      {(sel.analysis?.segments || []).map((p: any, i: number) => <div key={i} className="py-1"><span className="text-cyan-300">[{p.start.toFixed(1)}s]</span> {p.text}</div>)}
      {(sel.analysis?.observations || []).slice(0, 50).map((o: any, i: number) => <div key={i}>{o.timestamp} {o.label} (detector confidence {o.confidence.toFixed(2)})</div>)}
      {(sel.analysis?.warnings || []).map((w: string, i: number) => <div key={i} className="text-amber-300">{w}</div>)}</div>}</div>);
}

function StatementsTab({ cid }: { cid: string }) {
  const [t, setT] = useState(""); const [sp, setSp] = useState(""); const [d, setD] = useState<any>({ statements: [], claims: [] }); const [e, setE] = useState("");
  const load = () => api.get(`/api/cases/${cid}/statements`).then((r) => setD(r.data)); useEffect(() => { load(); }, [cid]);
  const add = async () => { try { await api.post(`/api/cases/${cid}/statements`, { text: t, speaker: sp || null }); setT(""); setE(""); load(); } catch (x) { setE(errMsg(x)); } };
  return (<div className="space-y-3"><div className="panel space-y-2"><Field placeholder="Speaker reference (e.g. Witness A)" value={sp} onChange={(x: any) => setSp(x.target.value)} />
    <textarea className="inp" rows={3} placeholder='e.g. "I was at home at 8:00 PM on 2024-03-05."' value={t} onChange={(x) => setT(x.target.value)} /><Err e={e} /><button className="btn" onClick={add}>Extract claims</button></div>
    {d.claims.map((c: any) => <div key={c.id} className="panel text-sm"><div>"{c.event_description}"</div><div className="text-xs text-slate-400">time {c.claimed_time || "—"} · date {c.claimed_date || "—"} · location {c.claimed_location || "—"} · people {c.people.join(", ") || "—"} · {c.source_reference}</div></div>)}</div>);
}

function TimelineTab({ cid }: { cid: string }) {
  const [t, setT] = useState<any>({ ordered: [], unplaced: [] }); const [src, setSrc] = useState(""); const [q, setQ] = useState(""); const [me, setMe] = useState<any>(null); const [f, setF] = useState({ description: "", date: "", time: "", location: "" });
  const load = () => api.get(`/api/cases/${cid}/timeline`, { params: { source: src, q } }).then((r) => setT(r.data)); useEffect(() => { load(); }, [cid, src, q]); useEffect(() => { api.get("/api/auth/me").then((r) => setMe(r.data)); }, []);
  const mark = async (id: number, s: string) => { await api.patch(`/api/events/${id}`, { description: "x", human_review_status: s }); load(); };
  const add = async () => { const b: any = { description: f.description }; if (f.date) b.date = f.date; if (f.time) b.time = f.time; if (f.location) b.location = f.location; await api.post(`/api/cases/${cid}/events`, b); setF({ description: "", date: "", time: "", location: "" }); load(); };
  const row = (e: any) => <div key={e.id} className="panel text-sm"><div><span className="text-cyan-300">{e.date || "date ?"} {e.time || "time ?"}</span> · {e.description}</div><div className="text-xs text-slate-400">{e.source_type} · {e.source_file || ""} {e.source_ref || ""} · {e.extraction_method} · review: {e.human_review_status}{e.location ? ` · at ${e.location}` : ""}</div>
    <button className="btn2 mt-1" onClick={() => mark(e.id, "reviewed")}>Mark reviewed</button></div>;
  return (<div className="space-y-3"><div className="flex gap-2"><select className="inp" style={{ width: 160 }} value={src} onChange={(x) => setSrc(x.target.value)}><option value="">All sources</option>{["cctv", "audio", "document", "statement", "manual"].map((s) => <option key={s}>{s}</option>)}</select><Field placeholder="Search events" value={q} onChange={(x: any) => setQ(x.target.value)} /></div>
    {me?.role !== "reviewer" && <div className="panel grid md:grid-cols-5 gap-2"><Field placeholder="Manual event" value={f.description} onChange={(x: any) => setF({ ...f, description: x.target.value })} /><Field type="date" value={f.date} onChange={(x: any) => setF({ ...f, date: x.target.value })} /><Field type="time" value={f.time} onChange={(x: any) => setF({ ...f, time: x.target.value })} /><Field placeholder="Location" value={f.location} onChange={(x: any) => setF({ ...f, location: x.target.value })} /><button className="btn" onClick={add}>Add event</button></div>}
    {t.ordered.map(row)}{!!t.unplaced.length && <><h3 className="text-sm text-amber-300">No usable timestamp — not placed on the timeline</h3>{t.unplaced.map(row)}</>}</div>);
}

function FindingsTab({ cid }: { cid: string }) {
  const [fs, setFs] = useState<any[]>([]); const [e, setE] = useState(""); const [me, setMe] = useState<any>(null);
  const load = () => api.get(`/api/cases/${cid}/findings`).then((r) => setFs(r.data)); useEffect(() => { load(); api.get("/api/auth/me").then((r) => setMe(r.data)); }, [cid]);
  const run = async () => { try { await api.post(`/api/cases/${cid}/compare`); setE(""); load(); } catch (x) { setE(errMsg(x)); } };
  const rev = async (id: number, s: string) => { try { await api.put(`/api/findings/${id}/review`, { review_status: s }); load(); } catch (x) { setE(errMsg(x)); } };
  const col: any = { "Potential inconsistency": "text-red-300", "Consistent with available evidence": "text-emerald-300" };
  return (<div className="space-y-3">{me?.role !== "reviewer" && <button className="btn" onClick={run}>Compare claims with evidence</button>}<Err e={e} />
    {fs.map((f) => <div key={f.id} className="panel text-sm space-y-1"><div className={`font-semibold ${col[f.label] || "text-amber-300"}`}>{f.label}</div><div>Claim: "{f.data.claim_text}" <span className="text-xs text-slate-400">({f.data.claim_source})</span></div>
      {f.data.evidence.map((x: any, i: number) => <div key={i} className="text-xs">Evidence: {x.description} — {x.source_file} @ {x.source_ref} ({x.time}, {x.location || "no location"})</div>)}
      <div className="text-xs">Reason: {f.data.reason}</div><div className="text-xs text-slate-400">Missing verification: {f.data.missing_verification}</div><div className="text-xs">Review: {f.review_status}</div>
      {me && me.role !== "investigator" && <div className="flex gap-2"><button className="btn2" onClick={() => rev(f.id, "approved")}>Approve</button><button className="btn2" onClick={() => rev(f.id, "rejected")}>Reject</button></div>}</div>)}
    {!fs.length && <p className="text-sm text-slate-400">No findings yet. No guilt, honesty or deception scores are produced.</p>}</div>);
}

function GraphTab({ cid }: { cid: string }) {
  const [g, setG] = useState<{ nodes: Node[]; edges: Edge[] }>({ nodes: [], edges: [] }); const [sel, setSel] = useState<any>(null);
  useEffect(() => { api.get(`/api/cases/${cid}/graph`).then((r) => { const cols: any = {}; setG({
    nodes: r.data.nodes.map((n: any) => { const k = n.type; cols[k] = (cols[k] ?? -1) + 1; const row = ["case", "video", "audio", "document", "image", "statement", "event", "location"].indexOf(k); return { id: n.id, data: { label: `${n.type}: ${n.label}`, ...n }, position: { x: cols[k] * 190, y: row * 110 }, style: { background: "#0f172a", color: "#e2e8f0", border: "1px solid #22d3ee55", fontSize: 11, width: 170 } }; }),
    edges: r.data.edges.map((e: any, i: number) => ({ id: `${i}`, source: e.source, target: e.target, label: `${e.label}${e.basis.startsWith("inferred") ? " (inferred)" : ""}`, style: { stroke: e.basis.startsWith("inferred") ? "#f59e0b" : "#22d3ee" }, labelStyle: { fontSize: 9, fill: "#cbd5e1" } })) }); }); }, [cid]);
  return (<div className="space-y-2"><div className="panel" style={{ height: 520 }}><ReactFlow nodes={g.nodes} edges={g.edges} onNodeClick={(_, n) => setSel(n.data)} fitView><Background /><Controls /></ReactFlow></div>
    <p className="text-xs text-slate-400">Cyan edges are recorded/extracted; amber edges are rule-inferred and unverified.</p>{sel && <div className="panel text-sm"><b>{sel.type}</b>: {sel.label}<div className="text-xs text-slate-400">{sel.detail}</div></div>}</div>);
}

function AssistantTab({ cid }: { cid: string }) {
  const [q, setQ] = useState(""); const [r, setR] = useState<any>(null); const [e, setE] = useState("");
  const ask = async () => { try { setR((await api.post(`/api/cases/${cid}/assistant`, { question: q })).data); setE(""); } catch (x) { setE(errMsg(x)); } };
  return (<div className="space-y-3"><div className="flex gap-2"><Field placeholder="Ask about this case's evidence…" value={q} onChange={(x: any) => setQ(x.target.value)} /><button className="btn" onClick={ask}>Ask</button></div><Err e={e} />
    {r && <div className="panel text-sm space-y-2"><div>{r.answer}</div>{r.note && <div className="text-amber-300 text-xs">{r.note}</div>}{r.citations.map((c: any, i: number) => <div key={i} className="text-xs border-l-2 border-cyan-400/40 pl-2"><b>{c.source_file}</b> [{c.ref}] (relevance {c.score}): {c.text}</div>)}</div>}</div>);
}

function ReportsTab({ cid }: { cid: string }) {
  const [rs, setRs] = useState<any[]>([]); const [e, setE] = useState("");
  const load = () => api.get(`/api/cases/${cid}/reports`).then((r) => setRs(r.data)); useEffect(() => { load(); }, [cid]);
  const gen = async () => { try { await api.post(`/api/cases/${cid}/reports`); load(); } catch (x) { setE(errMsg(x)); } };
  const open = async (id: number) => { const r = await api.get(`/api/reports/${id}/download`, { responseType: "blob" }); window.open(URL.createObjectURL(r.data)); };
  return (<div className="space-y-3"><button className="btn" onClick={gen}>Generate / regenerate PDF report</button><Err e={e} />{rs.map((r) => <div key={r.id} className="panel text-sm flex justify-between"><span>Report #{r.id} · {r.created_at}</span><button className="btn2" onClick={() => open(r.id)}>Preview / download</button></div>)}</div>);
}

function Audit() {
  const [a, setA] = useState<any[]>([]); useEffect(() => { api.get("/api/audit").then((r) => setA(r.data)); }, []);
  return (<><h1 className="text-xl font-semibold">Audit Logs</h1><div className="panel text-xs space-y-1">{a.map((x) => <div key={x.id}>{x.created_at} · {x.username || "-"} · {x.action} · {x.detail}</div>)}</div></>);
}

export default function App() {
  return (<Routes><Route path="/login" element={<Login />} /><Route element={<Layout />}><Route path="/" element={<Dashboard />} /><Route path="/cases" element={<Cases />} /><Route path="/cases/:cid" element={<CaseView />} /><Route path="/audit" element={<Audit />} /></Route><Route path="*" element={<Navigate to="/" />} /></Routes>);
}
