import { Loader2 } from 'lucide-react';

export default function Spinner({ className = '' }) {
  return <Loader2 className={`animate-spin text-blue-600 ${className}`} />;
}

export function PageLoader() {
  return (
    <div className="flex items-center justify-center h-64">
      <Loader2 className="animate-spin text-blue-500" size={36} />
    </div>
  );
}
