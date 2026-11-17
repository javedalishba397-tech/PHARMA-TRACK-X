const variants = {
  // Status
  Pending:   'bg-yellow-100 text-yellow-800 border border-yellow-200',
  Approved:  'bg-green-100 text-green-800 border border-green-200',
  Rejected:  'bg-red-100 text-red-800 border border-red-200',
  Modified:  'bg-purple-100 text-purple-800 border border-purple-200',
  // Risk
  Low:       'bg-green-100 text-green-700 border border-green-200',
  Medium:    'bg-amber-100 text-amber-700 border border-amber-200',
  High:      'bg-red-100 text-red-700 border border-red-200',
  // Actions
  Reorder:         'bg-blue-100 text-blue-700 border border-blue-200',
  Hold:            'bg-gray-100 text-gray-700 border border-gray-200',
  'Prioritize FEFO': 'bg-orange-100 text-orange-700 border border-orange-200',
  Review:          'bg-pink-100 text-pink-700 border border-pink-200',
  // PO Status
  Draft:     'bg-gray-100 text-gray-600 border border-gray-200',
  Ordered:   'bg-blue-100 text-blue-700 border border-blue-200',
  Received:  'bg-green-100 text-green-700 border border-green-200',
  Cancelled: 'bg-red-100 text-red-700 border border-red-200',
  Overdue:   'bg-red-200 text-red-800 border border-red-300',
  // Batch status
  Active:        'bg-green-100 text-green-700 border border-green-200',
  Expired:       'bg-red-100 text-red-700 border border-red-200',
  'Near Expiry': 'bg-orange-100 text-orange-700 border border-orange-200',
  'Near-Expiry': 'bg-orange-100 text-orange-700 border border-orange-200',
  Depleted:      'bg-gray-200 text-gray-500 border border-gray-300',
  'Written Off': 'bg-gray-200 text-gray-600 border border-gray-300',
  Adequate:      'bg-green-100 text-green-700 border border-green-200',
  Voided:        'bg-red-100 text-red-700 border border-red-200',
  Rx:            'bg-purple-100 text-purple-700 border border-purple-200',
  // Role
  admin:         'bg-indigo-100 text-indigo-700',
  pharmacist:    'bg-teal-100 text-teal-700',
  clerk:         'bg-cyan-100 text-cyan-700',
  Administrator: 'bg-indigo-100 text-indigo-700',
  Pharmacist:    'bg-teal-100 text-teal-700',
  'Sales Clerk': 'bg-cyan-100 text-cyan-700',
  // Generic
  default:   'bg-gray-100 text-gray-600 border border-gray-200',
};

export default function Badge({ label, className = '' }) {
  const cls = variants[label] ?? variants.default;
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${cls} ${className}`}>
      {label}
    </span>
  );
}
