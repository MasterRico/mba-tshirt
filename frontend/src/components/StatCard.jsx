import { isValidElement, createElement } from 'react'

export default function StatCard({ title, label, value, subtitle, icon, color = 'blue' }) {
  const heading = title ?? label
  const colorClasses = {
    blue: 'bg-blue-50 text-blue-600',
    green: 'bg-green-50 text-green-600',
    yellow: 'bg-yellow-50 text-yellow-600',
    red: 'bg-red-50 text-red-600',
    purple: 'bg-purple-50 text-purple-600',
  }

  // `icon` may be passed either as a component (e.g. icon={Target})
  // or as a rendered element (e.g. icon={<Target size={20} />}).
  let iconNode = null
  if (icon) {
    iconNode = isValidElement(icon) ? icon : createElement(icon, { size: 24 })
  }

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-500">{heading}</p>
          <p className="text-2xl font-bold mt-1">{value}</p>
          {subtitle && <p className="text-sm text-gray-400 mt-1">{subtitle}</p>}
        </div>
        {iconNode && (
          <div className={`p-3 rounded-lg ${colorClasses[color]}`}>
            {iconNode}
          </div>
        )}
      </div>
    </div>
  )
}
