const healthConfig = {
  excellent: { label: 'Exzellent', class: 'bg-green-100 text-green-800' },
  good: { label: 'Gut', class: 'bg-emerald-100 text-emerald-800' },
  warning: { label: 'Achtung', class: 'bg-yellow-100 text-yellow-800' },
  poor: { label: 'Schlecht', class: 'bg-orange-100 text-orange-800' },
  critical: { label: 'Kritisch', class: 'bg-red-100 text-red-800' },
}

export default function HealthBadge({ score }) {
  const config = healthConfig[score] || healthConfig.warning
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${config.class}`}>
      {config.label}
    </span>
  )
}
