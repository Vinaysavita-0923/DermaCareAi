import { useEffect, useState } from 'react'

const SEEN_KEY = 'dermacare_splash_seen'
const SHOW_MS = 2900 // matches the CSS timeline in index.css (2.3s hold + 0.6s fade)

function shouldShow(): boolean {
  try {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return false
    return sessionStorage.getItem(SEEN_KEY) !== '1'
  } catch {
    return true
  }
}

/** Welcome animation shown once per browser session when the site opens.
 * Click or press a key to skip. Skipped entirely when the user prefers
 * reduced motion. */
export default function Splash() {
  const [visible, setVisible] = useState(shouldShow)

  useEffect(() => {
    if (!visible) return
    try {
      sessionStorage.setItem(SEEN_KEY, '1')
    } catch {
      /* private mode: the splash just shows again next time */
    }
    const done = () => setVisible(false)
    const timer = window.setTimeout(done, SHOW_MS)
    window.addEventListener('keydown', done)
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden' // no page scrollbar behind the welcome screen
    return () => {
      window.clearTimeout(timer)
      window.removeEventListener('keydown', done)
      document.body.style.overflow = previousOverflow
    }
  }, [visible])

  if (!visible) return null

  return (
    <div className="splash" role="presentation" onClick={() => setVisible(false)}>
      <div className="splash-logo-wrap">
        <span className="splash-ring" />
        <span className="splash-ring r2" />
        <span className="splash-ring r3" />
        <img src="/logo.png" alt="" className="splash-logo" />
      </div>
      <p className="splash-title">
        DermaCare <span>AI</span>
      </p>
      <p className="splash-tag">Your smart skincare assistant</p>
      <div className="splash-bar">
        <i />
      </div>
    </div>
  )
}
