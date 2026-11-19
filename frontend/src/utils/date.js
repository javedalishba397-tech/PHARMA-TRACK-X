import { format, parseISO } from 'date-fns';

export function safeFormatDate(dateVal, pattern = 'dd MMM yy') {
  if (!dateVal) return '—';
  try {
    if (typeof dateVal === 'string') {
      // If it's pure date string like YYYY-MM-DD
      const parsed = parseISO(dateVal);
      if (isNaN(parsed.getTime())) {
        const d = new Date(dateVal);
        return isNaN(d.getTime()) ? String(dateVal) : format(d, pattern);
      }
      return format(parsed, pattern);
    } else if (dateVal instanceof Date) {
      return isNaN(dateVal.getTime()) ? '—' : format(dateVal, pattern);
    }
    return String(dateVal);
  } catch {
    return String(dateVal);
  }
}
