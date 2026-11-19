import { useState, useCallback, useEffect } from 'react';
import { recommendationsApi } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { PageLoader } from '../components/Spinner';
import Modal from '../components/Modal';
import Badge from '../components/Badge';
import { FormField, Select, Btn, ErrorAlert, Textarea, Input } from '../components/FormComponents';
import { ClipboardList, ChevronDown, ChevronRight, RefreshCw, CheckCircle, XCircle, Edit } from 'lucide-react';
import { safeFormatDate } from '../utils/date';

// ── Decision Modal ────────────────────────────────────────────────────────────
function DecisionModal({ rec, onClose, onSaved }) {
  const [decision, setDecision] = useState('Approved');
  const [comment, setComment] = useState('');
  const [modAction, setModAction] = useState(rec.action ?? 'Reorder');
  const [modQty, setModQty] = useState(rec.suggested_qty ?? '');
  const [error, setError] = useState(''); const [loading, setLoading] = useState(false);

  const save = async () => {
    setError(''); setLoading(true);
    try {
      const payload = {
        decision,
        comment: comment || null,
        final_action: decision === 'Modified' ? modAction : (decision === 'Approved' ? rec.action : null),
        final_qty: decision === 'Modified' ? (modQty ? +modQty : null) : (decision === 'Approved' ? rec.suggested_qty : null),
      };
      await recommendationsApi.decide(rec.recommendation_id, payload);
      onSaved();
    } catch (err) { setError(err.response?.data?.detail ?? 'Failed'); } finally { setLoading(false); }
  };

  const actions = ['Reorder', 'Hold', 'Prioritize FEFO', 'Review'];

  return (
    <Modal title="Record Decision" onClose={onClose} size="sm"
      footer={<><Btn variant="secondary" onClick={onClose}>Cancel</Btn><Btn onClick={save} disabled={loading}>{loading ? 'Saving…' : 'Submit'}</Btn></>}>
      <div className="space-y-4"><ErrorAlert message={error} />
        <div className="p-3 bg-gray-50 rounded-lg text-sm">
          <p className="font-medium text-gray-800">{rec.medicine_name}</p>
          <p className="text-gray-500 text-xs mt-1">Recommended: <Badge label={rec.action} /></p>
        </div>
        <FormField label="Decision">
          <Select value={decision} onChange={e => setDecision(e.target.value)}>
            <option value="Approved">Approve</option>
            <option value="Rejected">Reject</option>
            <option value="Modified">Modify</option>
          </Select>
        </FormField>
        {decision === 'Modified' && (
          <>
            <FormField label="Modified Action"><Select value={modAction} onChange={e => setModAction(e.target.value)}>{actions.map(a => <option key={a}>{a}</option>)}</Select></FormField>
            <FormField label="Modified Qty (if Reorder)"><Input type="number" min={0} value={modQty} onChange={e => setModQty(e.target.value)} /></FormField>
          </>
        )}
        <FormField label="Comment"><Textarea value={comment} onChange={e => setComment(e.target.value)} placeholder="Optional pharmacist note…" /></FormField>
      </div>
    </Modal>
  );
}

// ── Recommendation Row ────────────────────────────────────────────────────────
function RecRow({ rec, onDecide }) {
  const [expanded, setExpanded] = useState(false);
  const { isRole } = useAuth();

  const riskColor = { Low: 'text-green-700', Medium: 'text-amber-700', High: 'text-red-700' };
  const confBar = (c) => {
    const pct = Math.round((c ?? 0) * 100);
    const color = pct >= 70 ? 'bg-green-500' : pct >= 40 ? 'bg-amber-500' : 'bg-red-500';
    return <div className="flex items-center gap-2"><div className="flex-1 h-1.5 bg-gray-200 rounded-full"><div className={`h-1.5 rounded-full ${color}`} style={{ width: `${pct}%` }} /></div><span className="text-xs text-gray-500">{pct}%</span></div>;
  };

  return (
    <>
      <tr className="border-b border-gray-100 hover:bg-gray-50 cursor-pointer" onClick={() => setExpanded(!expanded)}>
        <td className="px-4 py-3 text-gray-400">{expanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}</td>
        <td className="px-4 py-3">
          <p className="font-medium text-gray-900 text-sm">{rec.medicine_name}</p>
          {rec.batch_number && <p className="text-xs text-gray-400 font-mono">Batch: {rec.batch_number}</p>}
        </td>
        <td className="px-4 py-3 text-sm">{rec.current_stock ?? rec.stock ?? '—'}</td>
        <td className="px-4 py-3 text-sm">{rec.days_to_expiry != null ? `${rec.days_to_expiry}d` : '—'}</td>
        <td className="px-4 py-3 text-xs text-gray-500">{rec.demand_lower != null ? `${rec.demand_lower}–${rec.demand_upper}` : rec.lower_bound != null ? `${rec.lower_bound}–${rec.upper_bound}` : '—'}</td>
        <td className="px-4 py-3">{confBar(rec.confidence_score ?? (rec.confidence_level === 'High' ? 0.9 : rec.confidence_level === 'Medium' ? 0.6 : 0.3))}</td>
        <td className={`px-4 py-3 font-semibold text-sm ${riskColor[rec.risk_band] ?? ''}`}>{rec.risk_band ?? '—'}</td>
        <td className="px-4 py-3"><Badge label={rec.recommended_action ?? rec.action} /></td>
        <td className="px-4 py-3"><Badge label={rec.status} /></td>
        {isRole('pharmacist') && (
          <td className="px-4 py-3">
            {rec.status === 'Pending' && (
              <button onClick={(e) => { e.stopPropagation(); onDecide(rec); }}
                className="p-1.5 text-blue-600 hover:bg-blue-50 rounded-lg"><Edit size={15} /></button>
            )}
          </td>
        )}
      </tr>
      {expanded && (
        <tr className="border-b border-gray-100">
          <td colSpan={10} className="px-6 py-4 bg-blue-50/40">
            <div className="text-sm space-y-2">
              <p className="font-semibold text-gray-700">Decision Explanation</p>
              <p className="text-gray-600 leading-relaxed">{rec.explanation}</p>
              {rec.suggested_order_qty && <p className="text-blue-700">Suggested Order Qty: <strong>{rec.suggested_order_qty}</strong></p>}
              {rec.pharmacist_comment && <p className="text-gray-500 italic">Pharmacist comment: {rec.pharmacist_comment}</p>}
              {rec.decided_at && <p className="text-xs text-gray-400">Decided: {safeFormatDate(rec.decided_at, 'dd MMM yyyy HH:mm')}</p>}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export default function Recommendations() {
  const { isRole } = useAuth();
  const [tab, setTab] = useState('pending');
  const [recs, setRecs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [runLoading, setRunLoading] = useState(false);
  const [decideModal, setDecideModal] = useState(null);
  const [filterAction, setFilterAction] = useState('');
  const [history, setHistory] = useState([]);
  const [histLoading, setHistLoading] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    const params = { status: tab === 'pending' ? 'Pending' : undefined, action: filterAction || undefined };
    recommendationsApi.list(params).then(r => setRecs(r.data)).finally(() => setLoading(false));
  }, [tab, filterAction]);

  useEffect(() => { load(); }, [load]);

  const loadHistory = useCallback(() => {
    setHistLoading(true);
    recommendationsApi.history().then(r => setHistory(r.data)).finally(() => setHistLoading(false));
  }, []);

  const runAll = async () => {
    setRunLoading(true);
    try { await recommendationsApi.runAll(); load(); }
    catch (err) { alert(err.response?.data?.detail ?? 'Failed'); }
    finally { setRunLoading(false); }
  };

  const tabs = [
    { id: 'pending', label: 'Pending' },
    { id: 'all', label: 'All Recommendations' },
    { id: 'history', label: 'Decision History' },
  ];

  const actions = ['Reorder', 'Hold', 'Prioritize FEFO', 'Review'];

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <ClipboardList size={22} className="text-blue-600" />
          <h1 className="text-2xl font-bold text-gray-900">Recommendations</h1>
        </div>
        {isRole('pharmacist') && (
          <Btn onClick={runAll} disabled={runLoading} variant="secondary">
            <RefreshCw size={16} className={runLoading ? 'animate-spin' : ''} />
            {runLoading ? 'Running…' : 'Run All Analysis'}
          </Btn>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-4 border-b border-gray-200">
        {tabs.map(t => (
          <button key={t.id} onClick={() => { setTab(t.id); if (t.id === 'history') loadHistory(); }}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-fast ${tab === t.id ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'history' ? (
        histLoading ? <PageLoader /> : (
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>{['Medicine','Batch #','Decision','Final Action','Qty','Pharmacist','Comment','Decided At'].map(h => <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500">{h}</th>)}</tr>
              </thead>
              <tbody>
                {history.map((h, i) => (
                  <tr key={i} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium">{h.medicine_name ?? '—'}</td>
                    <td className="px-4 py-3 font-mono text-xs">{h.batch_number ?? '—'}</td>
                    <td className="px-4 py-3"><Badge label={h.decision} /></td>
                    <td className="px-4 py-3">{h.final_action ? <Badge label={h.final_action} /> : '—'}</td>
                    <td className="px-4 py-3">{h.final_qty ?? '—'}</td>
                    <td className="px-4 py-3 text-xs">{h.user_name ?? '—'}</td>
                    <td className="px-4 py-3 text-xs text-gray-500">{h.comment ?? '—'}</td>
                    <td className="px-4 py-3 text-xs text-gray-400">{safeFormatDate(h.decided_at, 'dd MMM yy HH:mm')}</td>
                  </tr>
                ))}
                {history.length === 0 && <tr><td colSpan={8} className="py-8 text-center text-gray-400">No decisions yet</td></tr>}
              </tbody>
            </table>
          </div>
        )
      ) : (
        <>
          {/* Filter */}
          <div className="flex gap-3 mb-4">
            <Select value={filterAction} onChange={e => setFilterAction(e.target.value)} className="w-48">
              <option value="">All Actions</option>
              {actions.map(a => <option key={a}>{a}</option>)}
            </Select>
          </div>

          {loading ? <PageLoader /> : (
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="px-4 py-3"></th>
                    {['Medicine/Batch','Stock','Days','Demand Range','Confidence','Risk','Action','Status'].map(h => (
                      <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500">{h}</th>
                    ))}
                    {isRole('pharmacist') && <th className="px-4 py-3"></th>}
                  </tr>
                </thead>
                <tbody>
                  {recs.map(rec => (
                    <RecRow key={rec.recommendation_id} rec={rec} onDecide={setDecideModal} />
                  ))}
                  {recs.length === 0 && <tr><td colSpan={10} className="py-12 text-center text-gray-400">No recommendations</td></tr>}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {decideModal && (
        <DecisionModal rec={decideModal} onClose={() => setDecideModal(null)} onSaved={() => { setDecideModal(null); load(); }} />
      )}
    </div>
  );
}
