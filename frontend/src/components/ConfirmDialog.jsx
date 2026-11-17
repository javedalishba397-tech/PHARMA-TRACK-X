import { AlertTriangle } from 'lucide-react';
import Modal from './Modal';

export default function ConfirmDialog({ title, message, confirmLabel = 'Confirm', danger = false, onConfirm, onClose, loading }) {
  return (
    <Modal title={title} onClose={onClose} size="sm"
      footer={
        <>
          <button onClick={onClose} disabled={loading}
            className="px-4 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 transition-fast">
            Cancel
          </button>
          <button onClick={onConfirm} disabled={loading}
            className={`px-4 py-2 text-sm text-white rounded-lg transition-fast ${danger ? 'bg-red-600 hover:bg-red-700' : 'bg-blue-600 hover:bg-blue-700'}`}>
            {loading ? 'Processing…' : confirmLabel}
          </button>
        </>
      }>
      <div className="flex items-start gap-4">
        <div className={`p-2 rounded-full ${danger ? 'bg-red-100' : 'bg-blue-100'}`}>
          <AlertTriangle size={20} className={danger ? 'text-red-600' : 'text-blue-600'} />
        </div>
        <p className="text-sm text-gray-700 mt-1">{message}</p>
      </div>
    </Modal>
  );
}
