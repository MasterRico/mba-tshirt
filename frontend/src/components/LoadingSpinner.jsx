export default function LoadingSpinner({ text = 'Laden...' }) {
  return (
    <div className="flex items-center justify-center py-12">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-kdp-600 mr-3"></div>
      <span className="text-gray-500">{text}</span>
    </div>
  )
}
