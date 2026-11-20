import { useEffect, useRef, useState } from 'react'
import { encodePhoto } from '../services/journalPhotos'

/**
 * Capture a photo from the device camera, or pick an image file. The
 * result is handed back as a small JPEG data URL (metadata stripped).
 * The camera stream is always stopped on capture, cancel, or unmount.
 */
export default function PhotoCapture({
  value,
  onChange,
}: {
  value: string | null
  onChange: (dataUrl: string | null) => void
}) {
  const [cameraOn, setCameraOn] = useState(false)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const videoRef = useRef<HTMLVideoElement>(null)
  const streamRef = useRef<MediaStream | null>(null)

  function stopCamera() {
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
    setCameraOn(false)
  }

  // Always release the camera when this component goes away.
  useEffect(() => () => stopCamera(), [])

  // Attach the stream once the <video> is in the DOM.
  useEffect(() => {
    if (cameraOn && videoRef.current && streamRef.current) {
      videoRef.current.srcObject = streamRef.current
      videoRef.current.play().catch(() => {})
    }
  }, [cameraOn])

  async function startCamera() {
    setErr(null)
    if (!navigator.mediaDevices?.getUserMedia) {
      setErr('This browser has no camera access — choose a file instead.')
      return
    }
    try {
      streamRef.current = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment' },
        audio: false,
      })
      setCameraOn(true)
    } catch {
      setErr('Could not open the camera. Check permissions, or choose a file instead.')
    }
  }

  function capture() {
    const v = videoRef.current
    if (!v || !v.videoWidth) return
    const maxDim = 1000
    const scale = Math.min(1, maxDim / Math.max(v.videoWidth, v.videoHeight))
    const canvas = document.createElement('canvas')
    canvas.width = Math.round(v.videoWidth * scale)
    canvas.height = Math.round(v.videoHeight * scale)
    const ctx = canvas.getContext('2d')
    if (ctx) {
      ctx.drawImage(v, 0, 0, canvas.width, canvas.height)
      onChange(canvas.toDataURL('image/jpeg', 0.75))
    }
    stopCamera()
  }

  async function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    e.target.value = '' // allow picking the same file again later
    if (!file) return
    setBusy(true)
    setErr(null)
    try {
      onChange(await encodePhoto(file))
    } catch {
      setErr('Could not read that image. Try a JPEG or PNG.')
    } finally {
      setBusy(false)
    }
  }

  if (cameraOn) {
    return (
      <div className="space-y-2">
        <video ref={videoRef} playsInline muted className="w-full rounded-xl bg-black" />
        <div className="flex gap-2">
          <button
            type="button"
            onClick={capture}
            className="rounded-full bg-emerald-700 px-5 py-2 text-sm font-medium text-white hover:bg-emerald-800"
          >
            Capture
          </button>
          <button
            type="button"
            onClick={stopCamera}
            className="rounded-full px-4 py-2 text-sm font-medium text-slate-500 hover:bg-slate-100"
          >
            Cancel
          </button>
        </div>
      </div>
    )
  }

  if (value) {
    return (
      <div className="space-y-2">
        <img src={value} alt="Journal photo preview" className="max-h-56 w-full rounded-xl object-contain" />
        <button
          type="button"
          onClick={() => onChange(null)}
          className="rounded-full border border-slate-300 px-4 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-50"
        >
          Remove photo
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={startCamera}
          className="inline-flex items-center gap-2 rounded-full border border-emerald-600 px-4 py-2 text-sm font-medium text-emerald-700 hover:bg-emerald-50"
        >
          <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M3 9a2 2 0 0 1 2-2h1.5l1-1.5h5l1 1.5H20a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V9Z" strokeLinejoin="round" />
            <circle cx="12" cy="13" r="3.5" />
          </svg>
          Take photo
        </button>
        <label className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-slate-300 px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50">
          {busy ? 'Reading…' : 'Choose file'}
          <input type="file" accept="image/*" capture="environment" onChange={onFile} className="hidden" />
        </label>
      </div>
      {err && <p className="text-sm text-rose-600">{err}</p>}
    </div>
  )
}
