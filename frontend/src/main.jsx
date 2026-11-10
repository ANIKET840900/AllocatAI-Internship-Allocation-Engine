import { useCallback, useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import axios from 'axios';
import {
  Activity, AlertTriangle, BarChart3, BriefcaseBusiness, Check, Moon,
  ChevronRight, CircleHelp, Database, Download, FileText, Gauge, Menu, Play,
  RefreshCw, Search, Settings2, ShieldCheck, SlidersHorizontal, Sparkles,
  Sun, Users, X, Zap
} from 'lucide-react';
import './styles.css';

const api = axios.create({ baseURL: 'http://localhost:8000/api', timeout: 12000 });
api.interceptors.request.use((config) => {
  const token = window.localStorage.getItem('allocateai-api-token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});
const navItems = [
  ['overview', 'Overview', Gauge], ['candidates', 'Candidates', Users],
  ['internships', 'Internships', BriefcaseBusiness], ['dataset', 'Dataset', Database],
  ['allocation', 'Allocation', Zap], ['fairness', 'Fairness', ShieldCheck],
  ['agents', 'Agents / RAG', Sparkles], ['reports', 'Reports', FileText]
];
const toArray = (value) => Array.isArray(value) ? value : value?.results || value?.data || value?.items || [];
const num = (value, fallback = 0) => Number.isFinite(Number(value)) ? Number(value) : fallback;
const hasObjectData = (value) => value && typeof value === 'object' && Object.keys(value).length > 0;
const errorText = (error) => error?.response?.data?.detail || error?.response?.data?.message || error?.message || 'The service did not return a usable response.';
const EMPTY_OBJECT = Object.freeze({});
const EMPTY_ARRAY = Object.freeze([]);

function useApi(path, fallback = null) {
  const [state, setState] = useState({ data: fallback, loading: true, error: '' });
  const reload = useCallback(async () => {
    setState((s) => ({ ...s, loading: true, error: '' }));
    try { const response = await api.get(path); setState({ data: response.data, loading: false, error: '' }); }
    catch (error) { setState({ data: fallback, loading: false, error: errorText(error) }); }
  }, [fallback, path]);
  useEffect(() => { reload(); }, [reload]);
  return { ...state, reload };
}

function Button({ children, variant = 'secondary', loading, type = 'button', ...props }) {
  return <button type={type} className={`button ${variant}`} disabled={loading || props.disabled} {...props}>{loading ? <RefreshCw className="spin" size={15} /> : null}{children}</button>;
}
function State({ loading, error, empty = 'No records available yet.', onRetry }) {
  if (loading) return <div className="state"><RefreshCw className="spin" size={18} /><span>Loading operational data…</span></div>;
  if (error) return <div className="state state-error"><AlertTriangle size={18} /><span>{error}</span>{onRetry && <button type="button" className="text-button" onClick={onRetry}>Retry</button>}</div>;
  return <div className="state"><Database size={18} /><span>{empty}</span></div>;
}
function Metric({ label, value, note, icon: Icon, tone = '' }) {
  return <article className={`metric ${tone}`}><div className="metric-icon"><Icon size={17} /></div><div><span>{label}</span><strong>{value}</strong><small>{note}</small></div></article>;
}
function Header({ title, kicker, description, actions }) {
  return <header className="page-header"><div><p className="eyebrow">{kicker}</p><h1>{title}</h1><p className="subtitle">{description}</p></div><div className="header-actions">{actions}</div></header>;
}
function Panel({ title, eyebrow, children, className = '', action }) {
  return <section className={`panel ${className}`}><div className="panel-head"><div><p className="eyebrow">{eyebrow}</p><h2>{title}</h2></div>{action}</div>{children}</section>;
}
function Table({ columns, rows, empty, loading, error, retry, renderRow }) {
  if (loading || error || !rows?.length) return <State loading={loading} error={error} empty={empty} onRetry={retry} />;
  return <div className="table-wrap"><table><thead><tr>{columns.map((col) => <th key={col}>{col}</th>)}</tr></thead><tbody>{rows.map(renderRow)}</tbody></table></div>;
}
function Overview({ go }) {
  const dashboard = useApi('/dashboard', EMPTY_OBJECT);
  const results = useApi('/allocation/results', EMPTY_ARRAY);
  const fairness = useApi('/fairness/report', null);
  const d = dashboard.data || {};
  const runRows = toArray(results.data);
  const rates = fairness.data?.selection_rates || {};
  return <><Header kicker="01 / COMMAND CENTER" title="Decision workspace" description="Monitor supply, run transparent matching, and keep every placement auditable." actions={<><Button onClick={() => go('dataset')}><Database size={15} /> Generate data</Button><Button variant="primary" onClick={() => go('allocation')}><Play size={15} /> Run allocation</Button></>} />
    <div className="signal-strip"><span className="signal-marker" /><strong>{dashboard.error ? 'Service connection required' : 'Allocation control is ready'}</strong><span>{dashboard.error ? 'Start the FastAPI service to populate live metrics.' : 'Live operational data is synced from the allocation engine.'}</span><button type="button" onClick={dashboard.reload}><RefreshCw size={14} /></button></div>
    <div className="metrics"><Metric label="Candidates" value={num(d.candidates).toLocaleString()} note="active dataset" icon={Users} /><Metric label="Internships" value={num(d.internships).toLocaleString()} note={`${num(d.seats).toLocaleString()} total seats`} icon={BriefcaseBusiness} /><Metric label="Allocation rate" value={`${num(d.allocation_rate)}%`} note={`${num(d.allocated)} selected`} icon={Gauge} tone="lime" /><Metric label="Average score" value={num(d.average_score).toFixed(1)} note="out of 100" icon={BarChart3} /></div>
    <div className="content-grid overview-grid"><Panel className="wide" eyebrow="LATEST RUN" title="Allocation results" action={<span className="count-label">{runRows.length} assignments</span>}><Table columns={['Candidate', 'Internship', 'Score', 'Decision basis']} rows={runRows.slice(0, 10)} loading={results.loading} error={results.error} retry={results.reload} empty="Run the optimizer to see verified assignments." renderRow={(row, i) => <tr key={`${row.candidate_id}-${row.internship_id}-${i}`}><td><strong className="mono">{row.candidate_id || '—'}</strong></td><td>{row.internship_id || '—'}</td><td><span className="score">{num(row.score).toFixed(1)}</span></td><td>{row.explanation?.eligibility?.eligible === false ? 'Review required' : 'Eligible and selected'}</td></tr>} /></Panel>
      <Panel eyebrow="AUDIT SIGNAL" title="Fairness pulse" action={<ShieldCheck size={18} className="lime-icon" />}>{fairness.loading || fairness.error ? <State loading={fairness.loading} error={fairness.error} empty="No audit report yet." onRetry={fairness.reload} /> : <><div className="fairness-number">{(num(fairness.data?.demographic_parity_difference) * 100).toFixed(1)}<small>pp</small></div><p className="muted">Demographic parity gap across audit groups.</p><div className="bars">{Object.entries(rates).slice(0, 5).map(([group, rate]) => <div className="bar-row" key={group}><span>{group}</span><div><i style={{ width: `${Math.min(num(rate) * 100, 100)}%` }} /></div><b>{(num(rate) * 100).toFixed(1)}%</b></div>)}</div></>}</Panel>
    </div><div className="quick-row"><button type="button" onClick={() => go('candidates')}><Users size={17} /><span><b>Review candidates</b><small>Check eligibility and profile coverage</small></span><ChevronRight size={16} /></button><button type="button" onClick={() => go('fairness')}><ShieldCheck size={17} /><span><b>Inspect fairness</b><small>Compare selection rates by group</small></span><ChevronRight size={16} /></button><button type="button" onClick={() => go('reports')}><Download size={17} /><span><b>Export reports</b><small>Download an audit-ready snapshot</small></span><ChevronRight size={16} /></button></div></>;
}
function RecordsView({ type }) {
  const isCandidate = type === 'candidates';
  const resource = isCandidate ? '/candidates' : '/internships';
  const query = useApi(resource, EMPTY_ARRAY);
  const [formOpen, setFormOpen] = useState(false);
  const [form, setForm] = useState({});
  const [editId, setEditId] = useState('');
  const [formState, setFormState] = useState({ busy: false, error: '', message: '' });
  const [search, setSearch] = useState('');
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [location, setLocation] = useState('');
  const [minimum, setMinimum] = useState('');
  const allRows = toArray(query.data);
  const rows = allRows.filter((row) => {
    const haystack = JSON.stringify(row).toLowerCase();
    const locationMatch = !location || haystack.includes(location.toLowerCase());
    const numericValue = isCandidate ? num(row.experience_months, 0) : num(row.available_seats, 0);
    const minimumMatch = !minimum || numericValue >= num(minimum);
    return haystack.includes(search.toLowerCase()) && locationMatch && minimumMatch;
  });
  const activeFilters = Number(Boolean(location)) + Number(Boolean(minimum));
  const columns = isCandidate ? ['Candidate ID', 'Name', 'Skills', 'Experience', 'Location'] : ['Internship ID', 'Role', 'Organization', 'Location', 'Seats'];
  const submit = async (event) => {
    event.preventDefault();
    setFormState({ busy: true, error: '', message: '' });
    const parts = (value) => value.split(',').map((part) => part.trim()).filter(Boolean);
    const payload = isCandidate ? {
      candidate_id: form.id, name: form.name, education: form.education || 'B.Tech', specialization: form.specialization || 'General',
      cgpa: num(form.cgpa, 7), technical_skills: parts(form.skills || ''), soft_skills: [], experience_months: num(form.experience_months),
      preferred_domains: parts(form.domains || ''), preferred_locations: parts(form.locations || ''), preferred_stipend: num(form.stipend), preferred_duration: num(form.duration, 3), preference_rank: []
    } : {
      internship_id: form.id, company_name: form.company, role: form.role, domain: form.domain || 'General',
      required_skills: parts(form.skills || ''), preferred_skills: [], minimum_cgpa: num(form.cgpa), required_education: form.education || 'Any',
      minimum_experience: num(form.experience_months), location: form.location || 'Remote', stipend: num(form.stipend), duration: num(form.duration, 3),
      available_seats: num(form.seats, 1), mandatory_requirements: []
    };
    try {
      if (editId) await api.put(`${resource}/${encodeURIComponent(editId)}`, payload);
      else await api.post(resource, payload);
      setFormState({ busy: false, error: '', message: editId ? 'Record updated.' : 'Record created.' });
      setForm({});
      setEditId('');
      query.reload();
    } catch (error) {
      setFormState({ busy: false, error: errorText(error), message: '' });
    }
  };
  const remove = async (id) => {
    if (!window.confirm(`Delete ${id}?`)) return;
    try { await api.delete(`${resource}/${encodeURIComponent(id)}`); query.reload(); }
    catch (error) { setFormState({ busy: false, error: errorText(error), message: '' }); }
  };
  const edit = (row) => {
    setEditId(isCandidate ? row.candidate_id : row.internship_id);
    setForm(isCandidate ? {
      id: row.candidate_id, name: row.name, education: row.education, specialization: row.specialization, cgpa: row.cgpa,
      experience_months: row.experience_months, skills: (row.technical_skills || []).join(', '), domains: (row.preferred_domains || []).join(', '),
      locations: (row.preferred_locations || []).join(', '), stipend: row.preferred_stipend, duration: row.preferred_duration
    } : {
      id: row.internship_id, role: row.role, company: row.company_name, domain: row.domain, location: row.location,
      cgpa: row.minimum_cgpa, experience_months: row.minimum_experience, skills: (row.required_skills || []).join(', '),
      seats: row.available_seats, stipend: row.stipend, duration: row.duration, education: row.required_education
    });
    setFormOpen(true);
    setFormState({ busy: false, error: '', message: '' });
  };
  return <><Header kicker={isCandidate ? '02 / TALENT POOL' : '03 / SUPPLY MAP'} title={isCandidate ? 'Candidates' : 'Internships'} description={isCandidate ? 'Search and maintain candidate records.' : 'Manage internship requirements and seat capacity.'} actions={<><Button onClick={query.reload}><RefreshCw size={15} /> Refresh</Button><Button variant="primary" onClick={() => { setEditId(''); setForm({}); setFormOpen(!formOpen); }}>Add record</Button></>} />
    {formOpen && <Panel eyebrow={editId ? 'EDIT RECORD' : 'NEW RECORD'} title={isCandidate ? 'Candidate profile' : 'Internship opportunity'}><form className="form-grid" onSubmit={submit}>
      {[['id', isCandidate ? 'Candidate ID' : 'Internship ID'], [isCandidate ? 'name' : 'role', isCandidate ? 'Name' : 'Role'], ...(isCandidate ? [['education', 'Education'], ['specialization', 'Specialization'], ['cgpa', 'CGPA'], ['experience_months', 'Experience (months)'], ['skills', 'Technical skills (comma separated)'], ['domains', 'Preferred domains'], ['locations', 'Preferred locations']] : [['company', 'Company'], ['domain', 'Domain'], ['location', 'Location'], ['cgpa', 'Minimum CGPA'], ['experience_months', 'Minimum experience (months)'], ['skills', 'Required skills'], ['seats', 'Available seats']]), ['stipend', 'Stipend'], ['duration', 'Duration (months)']].map(([key, label]) => <label key={key}>{label}<input required={['id', 'name', 'role', 'company'].includes(key)} type={['cgpa', 'experience_months', 'seats', 'stipend', 'duration'].includes(key) ? 'number' : 'text'} min={['experience_months', 'seats', 'stipend'].includes(key) ? 0 : undefined} step={key === 'cgpa' ? '0.1' : undefined} value={form[key] || ''} onChange={(event) => setForm({ ...form, [key]: event.target.value })} /></label>)}
      <div className="form-actions"><Button type="submit" variant="primary" loading={formState.busy}>Save record</Button><Button type="button" onClick={() => { setFormOpen(false); setEditId(''); }}>Cancel</Button></div>
    </form>{formState.message && <div className="feedback success">{formState.message}</div>}{formState.error && <div className="feedback danger">{formState.error}</div>}</Panel>}
    <div className="toolbar"><div className="searchbox"><Search size={16} /><input aria-label={`Search ${isCandidate ? 'candidates' : 'internships'}`} value={search} onChange={(e) => setSearch(e.target.value)} placeholder={`Search ${isCandidate ? 'candidate ID, name, or skill' : 'role, company, or location'}…`} /></div><button type="button" className="filter-button" aria-expanded={filtersOpen} onClick={() => setFiltersOpen(!filtersOpen)}><SlidersHorizontal size={15} /> Filters <span>{activeFilters}</span></button></div>
    {filtersOpen && <div className="filter-panel"><label>Location or keyword<input value={location} onChange={(e) => setLocation(e.target.value)} placeholder="e.g. Pune, remote" /></label><label>{isCandidate ? 'Minimum experience (months)' : 'Minimum available seats'}<input type="number" min="0" value={minimum} onChange={(e) => setMinimum(e.target.value)} placeholder="Any" /></label><button type="button" className="text-button" onClick={() => { setLocation(''); setMinimum(''); }}>Clear filters</button></div>}
    {formState.error && !formOpen && <div className="feedback danger">{formState.error}</div>}
    <Panel eyebrow="LIVE DATASET" title={`${rows.length} ${isCandidate ? 'candidates' : 'internships'} visible`}><Table columns={[...columns, 'Actions']} rows={rows} loading={query.loading} error={query.error} retry={query.reload} empty={`No ${isCandidate ? 'candidates' : 'internships'} found. Generate a dataset to begin.`} renderRow={(row, i) => <tr key={row.candidate_id || row.internship_id || i}><td><strong className="mono">{row.candidate_id || row.internship_id || '—'}</strong></td><td>{row.name || row.role || 'Unspecified'}</td><td>{isCandidate ? (row.technical_skills || []).join(', ') || '—' : row.company_name || '—'}</td><td>{isCandidate ? `${num(row.experience_months)} mo` : row.location || '—'}</td><td>{isCandidate ? (row.preferred_locations || []).join(', ') || '—' : num(row.available_seats)}</td><td><button type="button" className="text-button" onClick={() => edit(row)}>Edit</button> <button type="button" className="text-button" onClick={() => remove(row.candidate_id || row.internship_id)}>Delete</button></td></tr>} /></Panel></>;
}
function Dataset() {
  const summary = useApi('/dataset/summary', EMPTY_OBJECT);
  const [form, setForm] = useState({ candidates: 1000, internships: 100, seed: 42 });
  const [csvFile, setCsvFile] = useState(null);
  const [state, setState] = useState({ busy: false, message: '', error: '' });
  const submit = async (e) => { e.preventDefault(); setState({ busy: true, message: '', error: '' }); try { const payload = Object.fromEntries(Object.entries(form).map(([k, v]) => [k, num(v)])); if (payload.candidates < 1 || payload.internships < 1) throw new Error('Candidate and internship counts must be at least 1.'); const response = await api.post('/dataset/generate', payload); setState({ busy: false, message: `Generated ${num(response.data?.candidates).toLocaleString()} candidates and ${num(response.data?.internships).toLocaleString()} internships.`, error: '' }); summary.reload(); } catch (error) { setState({ busy: false, message: '', error: errorText(error) }); } };
  const uploadCsv = async () => {
    if (!csvFile) return;
    setState({ busy: true, message: '', error: '' });
    const body = new FormData(); body.append('file', csvFile);
    try { const response = await api.post('/dataset/upload-csv', body); setState({ busy: false, message: `Imported ${num(response.data?.candidates)} candidates.`, error: '' }); setCsvFile(null); summary.reload(); }
    catch (error) { setState({ busy: false, message: '', error: errorText(error) }); }
  };
  return <><Header kicker="04 / DATA OPERATIONS" title="Dataset studio" description="Generate reproducible synthetic records or validate and import a candidate CSV." /><div className="two-col"><Panel eyebrow="GENERATOR" title="Create a dataset"><form className="form-grid" onSubmit={submit}>{[['candidates','Candidates'],['internships','Internships'],['seed','Random seed']].map(([key, label]) => <label key={key}>{label}<input type="number" min="1" value={form[key]} onChange={(e) => setForm({ ...form, [key]: e.target.value })} /></label>)}<div className="form-actions"><Button type="submit" variant="primary" loading={state.busy}><Database size={15} /> Generate dataset</Button></div><label>Candidate CSV<input type="file" accept=".csv,text/csv" onChange={(e) => setCsvFile(e.target.files?.[0] || null)} /></label><Button type="button" disabled={!csvFile || state.busy} loading={state.busy} onClick={uploadCsv}><Download size={15} /> Import candidate CSV</Button></form>{state.message && <div className="feedback success"><Check size={15} />{state.message}</div>}{state.error && <div className="feedback danger"><AlertTriangle size={15} />{state.error}</div>}</Panel><Panel eyebrow="DATASET HEALTH" title="Current inventory"><div className="health-stack">{[['Candidates', summary.data?.candidates, Users], ['Internships', summary.data?.internships, BriefcaseBusiness], ['Available seats', summary.data?.seats, Gauge]].map(([label, value, Icon]) => <div className="health-row" key={label}><Icon size={17} /><span>{label}</span><strong>{summary.loading ? '…' : num(value).toLocaleString()}</strong></div>)}</div><div className="note-box"><CircleHelp size={15} /><span>Generated synthetic records are explicitly sandbox data. Imported candidates are added without replacing the existing dataset.</span></div></Panel></div></>;
}
function Allocation() {
  const results = useApi('/allocation/results', EMPTY_ARRAY);
  const [weights, setWeights] = useState({ skill_weight: 0.35, education_weight: 0.2, preference_weight: 0.15, location_weight: 0.15, experience_weight: 0.1, other_weight: 0.05 });
  const [state, setState] = useState({ busy: false, message: '', error: '' });
  const total = Object.values(weights).reduce((a, b) => a + num(b), 0);
  const run = async (e) => { e.preventDefault(); if (Math.abs(total - 1) > 0.001) { setState({ busy: false, message: '', error: `Weights must sum to 1.00 (currently ${total.toFixed(2)}).` }); return; } setState({ busy: true, message: '', error: '' }); try { const payload = Object.fromEntries(Object.entries(weights).map(([k, v]) => [k, num(v)])); const response = await api.post('/allocation/run', payload); setState({ busy: false, message: `${num(response.data?.allocations?.length || response.data?.allocated_count)} assignments created.`, error: '' }); results.reload(); } catch (error) { setState({ busy: false, message: '', error: errorText(error) }); } };
  const rows = toArray(results.data);
  return <><Header kicker="05 / OPTIMIZER" title="Allocation run" description="Tune the scoring mix, validate the total, and launch a traceable allocation job." /><div className="two-col allocation-layout"><Panel eyebrow="SCORING MODEL" title="Allocation weights"><form className="weights-form" onSubmit={run}>{Object.entries(weights).map(([key, value]) => <label key={key}><span>{key.replace('_', ' ')} <b>{num(value).toFixed(2)}</b></span><input type="range" min="0" max="1" step="0.05" value={value} onChange={(e) => setWeights({ ...weights, [key]: Number(e.target.value) })} /></label>)}<div className={`weight-total ${Math.abs(total - 1) < 0.001 ? 'valid' : 'invalid'}`}><span>Total weight</span><strong>{total.toFixed(2)}</strong></div><Button type="submit" variant="primary" loading={state.busy}><Play size={15} /> Launch allocation</Button></form>{state.message && <div className="feedback success"><Check size={15} />{state.message}</div>}{state.error && <div className="feedback danger">{state.error}</div>}</Panel><Panel eyebrow="RESULTS" title="Latest assignments" action={<span className="count-label">{rows.length} rows</span>}><Table columns={['Candidate', 'Internship', 'Score']} rows={rows.slice(0, 8)} loading={results.loading} error={results.error} retry={results.reload} empty="No allocation results yet." renderRow={(row, i) => <tr key={i}><td className="mono">{row.candidate_id || '—'}</td><td>{row.internship_id || '—'}</td><td><span className="score">{num(row.score).toFixed(1)}</span></td></tr>} /></Panel></div></>;
}
function Fairness() { const report = useApi('/fairness/report', null); const rates = report.data?.selection_rates || {}; return <><Header kicker="06 / RESPONSIBLE AI" title="Fairness review" description="Review group-level selection outcomes before sharing an allocation decision." actions={<Button onClick={report.reload}><RefreshCw size={15} /> Refresh report</Button>} /><Panel eyebrow="AUDIT REPORT" title="Selection rate by group"><State loading={report.loading} error={report.error} empty="No fairness report available. Generate data and run allocation first." onRetry={report.reload} />{!report.loading && !report.error && report.data && <div className="fairness-layout"><div><div className="big-stat">{(num(report.data.demographic_parity_difference) * 100).toFixed(1)}<small>pp gap</small></div><p className="muted">Demographic parity difference</p></div><div className="bars large-bars">{Object.entries(rates).map(([group, rate]) => <div className="bar-row" key={group}><span>{group}</span><div><i style={{ width: `${Math.min(num(rate) * 100, 100)}%` }} /></div><b>{(num(rate) * 100).toFixed(1)}%</b></div>)}</div></div>}</Panel></>; }
function Agents() {
  const status = useApi('/agents/status', null);
  const auth = useApi('/auth/status', null);
  const logs = useApi('/agents/logs', EMPTY_ARRAY);
  const [token, setToken] = useState(window.localStorage.getItem('allocateai-api-token') || '');
  const [task, setTask] = useState('');
  const [agent, setAgent] = useState('orchestrator');
  const [question, setQuestion] = useState('');
  const [file, setFile] = useState(null);
  const [resumeFile, setResumeFile] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const execute = async (event) => {
    event.preventDefault(); setBusy(true); setError(''); setResult(null);
    try { const response = await api.post('/agents/execute', { task, agent }); setResult(response.data); setTask(''); logs.reload(); }
    catch (err) { setError(errorText(err)); } finally { setBusy(false); }
  };
  const ask = async (event) => {
    event.preventDefault(); setBusy(true); setError(''); setResult(null);
    try { const response = await api.post('/rag/query', { question }); setResult(response.data); }
    catch (err) { setError(errorText(err)); } finally { setBusy(false); }
  };
  const upload = async () => {
    if (!file) return;
    setBusy(true); setError(''); setResult(null);
    const body = new FormData(); body.append('file', file);
    try { const response = await api.post('/rag/documents/upload', body); await api.post('/rag/index'); setResult(response.data); setFile(null); }
    catch (err) { setError(errorText(err)); } finally { setBusy(false); }
  };
  const uploadResume = async () => {
    if (!resumeFile) return;
    setBusy(true); setError(''); setResult(null);
    const body = new FormData(); body.append('file', resumeFile);
    try { const response = await api.post('/resumes/upload', body); setResult(response.data); setResumeFile(null); }
    catch (err) { setError(errorText(err)); } finally { setBusy(false); }
  };
  return <><Header kicker="07 / OPERATIONS" title="Agents / RAG" description="Run controlled advisory tools and answer policy questions from indexed sources." />
    <div className="agent-grid">
      <Panel eyebrow="SYSTEM STATUS" title="Agent layer">{status.error ? <State error={status.error} empty="Agent status is unavailable." onRetry={status.reload} /> : <><div className={`agent-status ${status.data?.enabled ? 'online' : ''}`}><span className="status-dot" /><strong>{status.loading ? 'Checking provider…' : status.data?.enabled ? 'Provider configured' : 'Deterministic advisory mode'}</strong></div><p className="muted">Provider: {status.data?.provider || 'unknown'}. Allocation remains deterministic.</p><div className="agent-list">{(status.data?.agents || []).map((name) => <div key={name}><Sparkles size={14} />{name}<span>controlled</span></div>)}</div></>}</Panel>
      <Panel eyebrow="SECURITY" title="API access">{auth.data?.enabled ? <><p className="muted">Authentication is enabled. Enter a role token supplied by the administrator.</p><label>Bearer token<input type="password" autoComplete="off" value={token} onChange={(event) => setToken(event.target.value)} /></label><Button onClick={() => { window.localStorage.setItem('allocateai-api-token', token); setError('Token saved for this browser.'); }}>Save token</Button></> : <p className="muted">Role-token authentication is disabled for local development.</p>}</Panel>
    </div>
    <div className="agent-grid">
      <Panel eyebrow="TOOL EXECUTION" title="Run an agent task"><form className="form-grid" onSubmit={execute}><label>Agent<select value={agent} onChange={(event) => setAgent(event.target.value)}>{(status.data?.agents || ['orchestrator']).map((name) => <option key={name}>{name}</option>)}</select></label><label>Task<input required value={task} onChange={(event) => setTask(event.target.value)} placeholder="Summarize the latest allocation" /></label><Button type="submit" variant="primary" loading={busy}>Execute</Button></form><div className="agent-list">{toArray(logs.data).slice(0, 5).map((entry) => <div key={entry.id}><Activity size={14} />{entry.agent}: {entry.task}<span>{entry.status}</span></div>)}</div></Panel>
      <Panel eyebrow="RESUME INTAKE" title="Analyze a candidate resume"><label>Resume file<input type="file" accept=".pdf,.docx,.txt" onChange={(event) => setResumeFile(event.target.files?.[0] || null)} /></label><Button disabled={!resumeFile || busy} loading={busy} onClick={uploadResume}>Extract fields for review</Button><p className="muted">Extracted details are unverified and require human review before entering candidate records.</p></Panel>
      <Panel eyebrow="KNOWLEDGE BASE" title="Upload policy document"><label>Policy or FAQ file<input type="file" accept=".txt,.pdf,.docx" onChange={(event) => setFile(event.target.files?.[0] || null)} /></label><Button disabled={!file || busy} loading={busy} onClick={upload}>Upload and index</Button><form className="form-grid" onSubmit={ask}><label>Ask a policy question<textarea required value={question} onChange={(event) => setQuestion(event.target.value)} rows="3" /></label><Button type="submit" variant="primary" loading={busy}>Search grounded sources</Button></form></Panel>
    </div>
    {error && <div className="feedback danger">{error}</div>}
    {result && <Panel eyebrow="TOOL RESPONSE" title="Evidence"><pre className="json-preview">{JSON.stringify(result, null, 2)}</pre></Panel>}
  </>;
}
function Reports() {
  const report = useApi('/reports/allocation', EMPTY_OBJECT);
  const performance = useApi('/reports/performance', EMPTY_OBJECT);
  const performanceAvailable = hasObjectData(performance.data);
  const download = async (path, filename) => {
    try { const response = await api.get(path, { responseType: 'blob' }); const url = URL.createObjectURL(response.data); const a = document.createElement('a'); a.href = url; a.download = filename; a.click(); URL.revokeObjectURL(url); }
    catch (error) { window.alert(errorText(error)); }
  };
  return <><Header kicker="08 / EVIDENCE" title="Reports" description="Download allocation and fairness exports based on persisted service data." actions={<><Button onClick={() => window.print()}><FileText size={15} /> Print page</Button><Button onClick={() => download('/reports/allocation.csv', 'allocateai-allocation.csv')}><Download size={15} /> Allocation CSV</Button><Button onClick={() => download('/reports/allocation.pdf', 'allocateai-allocation.pdf')}><Download size={15} /> Allocation PDF</Button></>} />
    <div className="metrics report-metrics"><Metric label="Allocation runs" value={performance.loading || !performanceAvailable ? '—' : num(performance.data?.allocation_runs).toLocaleString()} note="recorded by service" icon={Activity} /><Metric label="Agent executions" value={performance.loading || !performanceAvailable ? '—' : num(performance.data?.agent_executions).toLocaleString()} note="advisory calls" icon={Sparkles} /><Metric label="Provider" value={performance.loading || !performanceAvailable ? '—' : performance.data?.llm_provider || '—'} note="runtime configuration" icon={Settings2} /></div>
    <div className="quick-row"><Button onClick={() => download('/reports/fairness.csv', 'allocateai-fairness.csv')}><Download size={15} /> Fairness CSV</Button><Button onClick={() => download('/reports/fairness.pdf', 'allocateai-fairness.pdf')}><Download size={15} /> Fairness PDF</Button></div>
    <Panel eyebrow="ALLOCATION EVIDENCE" title="Allocation run history"><Table columns={['Run', 'Status', 'Assignments', 'Objective', 'Runtime', 'Created']} rows={toArray(report.data?.history)} loading={report.loading} error={report.error} retry={report.reload} empty="No allocation runs have been recorded." renderRow={(row) => <tr key={row.run_id}><td className="mono">#{row.run_id}</td><td>{row.status || '—'}</td><td>{num(row.allocated_count).toLocaleString()}</td><td>{num(row.objective_value).toFixed(2)}</td><td>{num(row.runtime_ms).toFixed(2)} ms</td><td>{row.created_at ? new Date(row.created_at).toLocaleString() : '—'}</td></tr>} /></Panel>
    <Panel eyebrow="LATEST RUN" title="Assignment details"><Table columns={['Candidate', 'Internship', 'Score', 'Decision basis']} rows={toArray(report.data?.results)} loading={report.loading} error={report.error} retry={report.reload} empty="No assignment details are available for the latest run." renderRow={(row, i) => <tr key={`${row.candidate_id}-${row.internship_id}-${i}`}><td><strong className="mono">{row.candidate_id || '—'}</strong></td><td>{row.internship_id || '—'}</td><td><span className="score">{num(row.score).toFixed(1)}</span></td><td>{row.explanation?.eligibility?.eligible === false ? 'Review required' : 'Eligible and selected'}</td></tr>} /></Panel>
  </>;
}
function App() {
  const [view, setView] = useState('overview');
  const [mobileOpen, setMobileOpen] = useState(false);
  const [theme, setTheme] = useState(() => {
    try { return window.localStorage.getItem('allocateai-theme') === 'dark' ? 'dark' : 'light'; }
    catch { return 'light'; }
  });
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try { window.localStorage.setItem('allocateai-theme', theme); } catch { /* Storage may be disabled by browser policy. */ }
  }, [theme]);
  const Current = view === 'overview' ? Overview : view === 'candidates' || view === 'internships' ? () => <RecordsView type={view} /> : view === 'dataset' ? Dataset : view === 'allocation' ? Allocation : view === 'fairness' ? Fairness : view === 'agents' ? Agents : Reports;
  const navigate = (next) => { setView(next); setMobileOpen(false); window.scrollTo({ top: 0, behavior: 'smooth' }); };
  return <div className="app-shell">
    <fieldset className="theme-switch">
      <legend>Color theme</legend>
      <button type="button" className={theme === 'light' ? 'selected' : ''} aria-pressed={theme === 'light'} onClick={() => setTheme('light')}><Sun size={15} /> Light</button>
      <button type="button" className={theme === 'dark' ? 'selected' : ''} aria-pressed={theme === 'dark'} onClick={() => setTheme('dark')}><Moon size={15} /> Dark</button>
    </fieldset>
    <aside className={mobileOpen ? 'open' : ''}><div className="brand"><div className="brand-mark">A</div><div><b>AllocatAI</b><span>Fair placement lab</span></div><button type="button" className="close-nav" aria-label="Close navigation" onClick={() => setMobileOpen(false)}><X size={18} /></button></div><nav aria-label="Primary navigation">{navItems.map(([id, label, Icon]) => <button type="button" key={id} className={view === id ? 'active' : ''} aria-current={view === id ? 'page' : undefined} onClick={() => navigate(id)}><Icon size={17} /><span>{label}</span>{view === id && <i />}</button>)}</nav><div className="side-foot"><span className="status-dot" /> Local simulation<br /><small>Protected audit data stays separate</small></div></aside>
    {mobileOpen && <button type="button" className="nav-scrim" aria-label="Close navigation overlay" onClick={() => setMobileOpen(false)} />}
    <main><div className="mobile-top"><button type="button" aria-label="Open navigation" onClick={() => setMobileOpen(true)}><Menu size={20} /></button><span>ALLOCAT<span>AI</span> / CONTROL</span><span className="mobile-signal" /></div><Current go={navigate} /></main>
  </div>;
}
const rootElement = document.getElementById('root');
const root = import.meta.hot?.data.root || createRoot(rootElement);
if (import.meta.hot) import.meta.hot.data.root = root;
root.render(<App />);
