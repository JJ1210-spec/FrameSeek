import { statusDisplay } from '../../lib/stages';

export default function StatusBadge({ status, resultStatus }) {
  const { label, tone } = statusDisplay(status, resultStatus);
  return <span className={`chip chip--${tone}`}>{label}</span>;
}
