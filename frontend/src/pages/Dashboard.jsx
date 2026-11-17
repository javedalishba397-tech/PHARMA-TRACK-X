import { useEffect, useState } from 'react';
import { stockApi } from '../api/client';
import { PageLoader } from '../components/Spinner';
import { AlertTriangle, TrendingDown, Package, ClipboardList, DollarSign, Receipt } from 'lucide-react';

function MetricCard({ label, value, sub, icon: Icon, color }) {
  const colors = {
    blue:   'bg-blue-50 text-blue-700 border-blue-200',
    yellow: 'bg-yellow-50 text-yellow-700 border-yellow-200',
    orange: 'bg-orange-50 text-orange-700 border-orange-200',
    red:    'bg-red-50 text-red-700 border-red-200',
    green:  'bg-green-50 text-green-700 border-green-200',
    indigo: 'bg-indigo-50 text-indigo-700 border-indigo-200',
  };
  return (
    <div className={`rounded-xl border p-5 ${colors[color]}`}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium opacity-80">{label}</p>
          <p className="text-3xl font-bold mt-1">{value ?? '—'}</p>
          {sub && <p className="text-xs opacity-70 mt-1">{sub}</p>}
        </div>
        <div className="p-2 bg-white/60 rounded-lg">
          <Icon size={22} />
        </div>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    stockApi.dashboard()
      .then((r) => setData(r.data))
      .catch(() => setError('Failed to load dashboard metrics.'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <PageLoader />;

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-sm text-gray-500 mt-1">Pharmacy inventory overview</p>
      </div>

      {error && <div className="mb-4 p-3 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg">{error}</div>}

      {data && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          <MetricCard label="Low Stock Items"       value={data.low_stock_count}         icon={TrendingDown}  color="yellow" sub="Below reorder level" />
          <MetricCard label="Near Expiry Batches"   value={data.near_expiry_count}        icon={AlertTriangle} color="orange" sub="Expiring within threshold" />
          <MetricCard label="Expired Batches"       value={data.expired_count}            icon={Package}       color="red"    sub="Must not be sold" />
          <MetricCard label="Pending Recommendations" value={data.pending_recommendations_count ?? data.pending_recommendations} icon={ClipboardList} color="blue"   sub="Awaiting pharmacist review" />
          <MetricCard label="Today's Sales (PKR)"   value={data.today_sales_total != null ? `₨ ${Number(data.today_sales_total).toLocaleString()}` : '₨ 0'} icon={DollarSign} color="green" />
          <MetricCard label="Today's Bills"         value={data.today_bills_count}        icon={Receipt}       color="indigo" sub="Transactions processed" />
        </div>
      )}

      {/* Alerts summary */}
      {data && (data.expired_count > 0 || data.low_stock_count > 0) && (
        <div className="mt-6 p-4 bg-amber-50 border border-amber-200 rounded-xl">
          <h2 className="text-sm font-semibold text-amber-800 flex items-center gap-2">
            <AlertTriangle size={16} /> Action Required
          </h2>
          <ul className="mt-2 text-sm text-amber-700 list-disc list-inside space-y-1">
            {data.expired_count > 0 && <li>{data.expired_count} expired batch(es) need to be written off</li>}
            {data.low_stock_count > 0 && <li>{data.low_stock_count} item(s) are below reorder level</li>}
            {(data.pending_recommendations_count ?? data.pending_recommendations) > 0 && <li>{data.pending_recommendations_count ?? data.pending_recommendations} recommendation(s) pending your decision</li>}
          </ul>
        </div>
      )}
    </div>
  );
}
