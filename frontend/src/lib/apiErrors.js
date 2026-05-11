/**
 * Turn FastAPI / fetch error bodies into short, user-facing messages.
 */
export function friendlyErrorMessage(raw) {
  if (raw == null) return 'Something went wrong. Please try again.'
  const text = typeof raw === 'string' ? raw.trim() : String(raw)

  let detail = text
  try {
    const j = JSON.parse(text)
    if (typeof j?.detail === 'string') {
      detail = j.detail
    } else if (Array.isArray(j?.detail)) {
      detail = j.detail
        .map((item) => {
          if (item && typeof item === 'object' && item.msg) return String(item.msg)
          return typeof item === 'string' ? item : JSON.stringify(item)
        })
        .join(' ')
    }
  } catch {
    // use whole text as detail
  }

  const d = detail.trim()
  const lower = d.toLowerCase()

  if (lower.includes('openai_api_key') || lower.includes('openai api key')) {
    return '⚠️ OpenAI API key missing. Add OPENAI_API_KEY to your backend `.env` file and restart the server.'
  }
  if (lower.includes('api key') && (lower.includes('not set') || lower.includes('missing'))) {
    return '⚠️ A required API key is missing. Check your backend `.env` file.'
  }
  if (lower.includes('failed to fetch') || lower.includes('networkerror')) {
    return 'Could not reach the API. Is the backend running on port 8000?'
  }

  if (d.length > 280) return `${d.slice(0, 277)}…`
  return d || 'Request failed.'
}
