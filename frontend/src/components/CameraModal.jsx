import { useState, useRef, useEffect, useCallback } from 'react'

const API_BASE = 'http://localhost:8000'
const SCAN_INTERVAL_MS = 800

/* ── icons ─────────────────────────────────────────────────────────────────── */
const CameraIcon = ({ size = 16 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>
    <circle cx="12" cy="13" r="4"/>
  </svg>
)
const XIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth="2" strokeLinecap="round">
    <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
  </svg>
)
const CheckIcon = ({ size = 13 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="20 6 9 17 4 12"/>
  </svg>
)
const StopIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
    <rect x="3" y="3" width="18" height="18" rx="2"/>
  </svg>
)

const BOX_COLOR_YOLO   = '#4F5159'   // grey while waiting for Claude
const BOX_COLOR_CLAUDE = '#00D4FF'   // cyan once Claude confirms
const BOX_BG_YOLO      = 'rgba(79,81,89,0.15)'
const BOX_BG_CLAUDE    = 'rgba(0,212,255,0.10)'

/* ── draw bounding boxes ─────────────────────────────────────────────────────── */
function drawBoxes(canvas, boxes, claudeMap) {
  const ctx = canvas.getContext('2d')
  const cw  = canvas.width
  const ch  = canvas.height
  ctx.clearRect(0, 0, cw, ch)

  boxes.forEach(b => {
    const claudeResult = claudeMap[b.label]
    const identified   = claudeResult && !claudeResult.loading
    const color  = identified ? BOX_COLOR_CLAUDE : BOX_COLOR_YOLO
    const bgFill = identified ? BOX_BG_CLAUDE    : BOX_BG_YOLO

    const x1 = b.x1 * cw, y1 = b.y1 * ch
    const x2 = b.x2 * cw, y2 = b.y2 * ch
    const w = x2 - x1, h = y2 - y1

    ctx.fillStyle = bgFill
    ctx.fillRect(x1, y1, w, h)

    ctx.strokeStyle = color
    ctx.lineWidth = identified ? 2 : 1.5
    if (!identified) {
      ctx.setLineDash([4, 3])   // dashed while YOLO-only
    } else {
      ctx.setLineDash([])
    }
    ctx.strokeRect(x1, y1, w, h)
    ctx.setLineDash([])

    // label
    const displayItem = identified
      ? claudeResult.item
      : (claudeResult?.loading ? `${b.item} …` : b.item)
    const conf  = Math.round(b.confidence * 100)
    const label = `${displayItem}  ${conf}%`

    ctx.font = `${identified ? 'bold' : 'normal'} 11px Inter, system-ui, sans-serif`
    const tw = ctx.measureText(label).width
    const px = 6, py = 3, lh = 14
    const bx = x1
    const by = y1 - lh - py * 2 < 0 ? y1 : y1 - lh - py * 2

    ctx.fillStyle = color
    ctx.fillRect(bx, by, tw + px * 2, lh + py * 2)
    ctx.fillStyle = identified ? '#000' : '#fff'
    ctx.fillText(label, bx + px, by + py + lh - 1)
  })
}

/* ── crop a bounding box from a canvas ──────────────────────────────────────── */
function cropBox(sourceCanvas, box) {
  const cw = sourceCanvas.width
  const ch = sourceCanvas.height
  const pad = 24

  const sx = Math.max(0, Math.floor(box.x1 * cw) - pad)
  const sy = Math.max(0, Math.floor(box.y1 * ch) - pad)
  const sw = Math.min(cw - sx, Math.ceil((box.x2 - box.x1) * cw) + pad * 2)
  const sh = Math.min(ch - sy, Math.ceil((box.y2 - box.y1) * ch) + pad * 2)

  const crop = document.createElement('canvas')
  crop.width  = sw
  crop.height = sh
  crop.getContext('2d').drawImage(sourceCanvas, sx, sy, sw, sh, 0, 0, sw, sh)
  return crop.toDataURL('image/jpeg', 0.88).split(',')[1]
}

/* ── component ───────────────────────────────────────────────────────────────── */
export default function CameraModal({ conversationId, onClose, onItemsAdded }) {
  const videoRef   = useRef(null)
  const overlayRef = useRef(null)
  const frameRef   = useRef(null)   // hidden canvas for frame capture
  const streamRef  = useRef(null)
  const scanningRef = useRef(false) // true while a YOLO fetch is in-flight
  const intervalRef = useRef(null)

  // Set of YOLO class labels already queued/identified by Claude (persists across frames)
  const identifiedRef = useRef(new Set())

  // Latest YOLO boxes — needed to re-draw overlay when claudeMap updates
  const latestBoxesRef = useRef([])

  const [devices, setDevices]               = useState([])
  const [selectedDevice, setSelectedDevice] = useState('')
  const [ready, setReady]                   = useState(false)
  const [isScanning, setIsScanning]         = useState(false)
  const [phase, setPhase]                   = useState('live') // live | review | error
  const [errorMsg, setErrorMsg]             = useState('')

  // claudeMap: { [yolo_label]: { item, quantity, unit, loading } }
  const [claudeMap, setClaudeMap] = useState({})

  // detectedMap: { [yolo_label]: { item, quantity, unit, confidence } } (YOLO-level data)
  const [detectedMap, setDetectedMap] = useState({})

  // Selected keys for confirm step (yolo labels)
  const [selectedKeys, setSelectedKeys] = useState(new Set())

  /* enumerate cameras ──────────────────────────────────────────────────────── */
  useEffect(() => {
    navigator.mediaDevices.enumerateDevices().then(devs => {
      const cams = devs.filter(d => d.kind === 'videoinput')
      setDevices(cams)
      const ext = cams.find(d => !/built-in|facetime|integrated/i.test(d.label))
      setSelectedDevice(ext ? ext.deviceId : (cams[0]?.deviceId ?? ''))
    }).catch(() => {})
  }, [])

  /* start / switch stream ─────────────────────────────────────────────────── */
  useEffect(() => {
    if (!selectedDevice) return
    startStream(selectedDevice)
    return () => { stopScanLoop(); stopStream() }
  }, [selectedDevice])

  const startStream = async (deviceId) => {
    stopScanLoop()
    stopStream()
    setReady(false)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { deviceId: { exact: deviceId }, width: { ideal: 1280 }, height: { ideal: 720 } },
      })
      streamRef.current = stream
      if (videoRef.current) {
        videoRef.current.srcObject = stream
        videoRef.current.onloadedmetadata = () => {
          videoRef.current.play()
          setReady(true)
        }
      }
    } catch (err) {
      setErrorMsg(`Camera error: ${err.message}`)
      setPhase('error')
    }
  }

  const stopStream = () => {
    streamRef.current?.getTracks().forEach(t => t.stop())
    streamRef.current = null
  }

  /* re-draw overlay whenever claudeMap changes ─────────────────────────────── */
  useEffect(() => {
    const overlay = overlayRef.current
    if (!overlay || !latestBoxesRef.current.length) return
    drawBoxes(overlay, latestBoxesRef.current, claudeMap)
  }, [claudeMap])

  /* ── Claude crop identification ──────────────────────────────────────────── */
  const identifyWithClaude = useCallback(async (yoloLabel, box) => {
    const frame = frameRef.current
    if (!frame) return

    // Mark as loading immediately
    setClaudeMap(prev => ({ ...prev, [yoloLabel]: { ...prev[yoloLabel], loading: true } }))

    const cropB64 = cropBox(frame, box)

    try {
      const res = await fetch(`${API_BASE}/pantry/identify-crop`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image: cropB64, yolo_class: yoloLabel }),
      })
      if (!res.ok) throw new Error(res.statusText)
      const data = await res.json()

      if (data.item) {
        setClaudeMap(prev => ({
          ...prev,
          [yoloLabel]: { item: data.item, quantity: data.quantity, unit: data.unit, loading: false },
        }))
        // Auto-select claude-confirmed items
        setSelectedKeys(prev => new Set([...prev, yoloLabel]))
      } else {
        // Claude says not a food item — remove from map
        setClaudeMap(prev => { const n = { ...prev }; delete n[yoloLabel]; return n })
        setDetectedMap(prev => { const n = { ...prev }; delete n[yoloLabel]; return n })
        setSelectedKeys(prev => { const n = new Set(prev); n.delete(yoloLabel); return n })
      }
    } catch (_) {
      // On failure keep the YOLO-level detection
      setClaudeMap(prev => { const n = { ...prev }; delete n[yoloLabel]; return n })
    }
  }, [])

  /* ── single frame scan ───────────────────────────────────────────────────── */
  const sendFrame = useCallback(async () => {
    if (scanningRef.current) return
    const video   = videoRef.current
    const frame   = frameRef.current
    const overlay = overlayRef.current
    if (!video || !frame || !overlay || !streamRef.current) return

    const dw = video.clientWidth
    const dh = video.clientHeight
    if (!dw || !dh) return

    // Sync overlay + frame to video display size
    overlay.width  = dw
    overlay.height = dh
    frame.width    = dw
    frame.height   = dh
    frame.getContext('2d').drawImage(video, 0, 0, dw, dh)

    const base64 = frame.toDataURL('image/jpeg', 0.75).split(',')[1]

    scanningRef.current = true
    try {
      const res = await fetch(`${API_BASE}/pantry/scan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image: base64, media_type: 'image/jpeg' }),
      })
      if (!res.ok) return
      const data = await res.json()

      // Store latest boxes for overlay re-draw on claudeMap updates
      latestBoxesRef.current = data.boxes

      // Draw immediately with YOLO labels (fast feedback)
      drawBoxes(overlay, data.boxes, claudeMap)

      // Update detectedMap with YOLO-level data
      if (data.items.length > 0) {
        setDetectedMap(prev => {
          const next = { ...prev }
          data.items.forEach(item => {
            // Key by YOLO label so we can cross-reference with claudeMap
            const yoloLabel = data.boxes.find(b => b.item === item.item)?.label ?? item.item
            if (!next[yoloLabel] || item.confidence > (next[yoloLabel]?.confidence ?? 0)) {
              next[yoloLabel] = { ...item, yoloLabel }
            }
          })
          return next
        })
        setSelectedKeys(prev => {
          const next = new Set(prev)
          data.items.forEach(item => {
            const yoloLabel = data.boxes.find(b => b.item === item.item)?.label ?? item.item
            next.add(yoloLabel)
          })
          return next
        })
      }

      // Dispatch Claude identification for any new unique YOLO classes
      data.boxes.forEach(box => {
        if (!identifiedRef.current.has(box.label)) {
          identifiedRef.current.add(box.label)
          identifyWithClaude(box.label, box)
        }
      })
    } catch (_) {
      // network errors during live scan are non-fatal
    } finally {
      scanningRef.current = false
    }
  }, [claudeMap, identifyWithClaude])

  /* ── scan loop ───────────────────────────────────────────────────────────── */
  const startScanLoop = useCallback(() => {
    if (intervalRef.current) return
    setIsScanning(true)
    sendFrame()
    intervalRef.current = setInterval(sendFrame, SCAN_INTERVAL_MS)
  }, [sendFrame])

  const stopScanLoop = () => {
    clearInterval(intervalRef.current)
    intervalRef.current = null
    scanningRef.current = false
    setIsScanning(false)
  }

  useEffect(() => {
    if (ready && phase === 'live') startScanLoop()
    return () => stopScanLoop()
  }, [ready, phase])

  /* ── review / confirm ────────────────────────────────────────────────────── */
  const goToReview = () => {
    stopScanLoop()
    const overlay = overlayRef.current
    if (overlay) overlay.getContext('2d').clearRect(0, 0, overlay.width, overlay.height)
    setPhase('review')
  }

  const confirmItems = useCallback(async () => {
    // Prefer Claude-identified data; fall back to YOLO data
    const items = [...selectedKeys].map(label => {
      const claude = claudeMap[label]
      const yolo   = detectedMap[label]
      if (claude && !claude.loading) {
        return { item: claude.item, quantity: claude.quantity, unit: claude.unit, confidence: yolo?.confidence ?? 0.8 }
      }
      return yolo ? { item: yolo.item, quantity: yolo.quantity, unit: yolo.unit, confidence: yolo.confidence } : null
    }).filter(Boolean)

    if (!items.length) { onClose(); return }

    if (conversationId) {
      try {
        await fetch(`${API_BASE}/pantry/update`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ conversation_id: conversationId, items, replace: false }),
        })
      } catch (_) {}
    }

    onItemsAdded?.(items)
    onClose()
  }, [selectedKeys, claudeMap, detectedMap, conversationId, onClose, onItemsAdded])

  const toggleKey = (key) => {
    setSelectedKeys(prev => {
      const next = new Set(prev)
      next.has(key) ? next.delete(key) : next.add(key)
      return next
    })
  }

  const resumeScanning = () => { setPhase('live'); startScanLoop() }

  /* ── merged item list for display ────────────────────────────────────────── */
  const displayItems = Object.keys(detectedMap).map(label => {
    const claude = claudeMap[label]
    const yolo   = detectedMap[label]
    return {
      key:      label,
      item:     (claude && !claude.loading) ? claude.item : yolo.item,
      quantity: (claude && !claude.loading) ? claude.quantity : yolo.quantity,
      unit:     (claude && !claude.loading) ? claude.unit : yolo.unit,
      confidence: yolo.confidence,
      loading:  claude?.loading ?? false,
      verified: claude && !claude.loading,
    }
  })

  /* ── render ──────────────────────────────────────────────────────────────── */
  return (
    <div
      className="fixed inset-0 flex items-center justify-center z-50"
      style={{ background: 'rgba(0,0,0,0.82)', backdropFilter: 'blur(6px)' }}
      onClick={e => e.target === e.currentTarget && onClose()}
    >
      <div
        className="flex rounded-2xl overflow-hidden"
        style={{
          background: '#2B2D31',
          border: '1px solid #4F5159',
          width: '92vw', maxWidth: 860,
          maxHeight: '90vh',
          boxShadow: '0 32px 80px rgba(0,0,0,0.7)',
        }}
      >

        {/* ── LEFT: live video ─────────────────────────────────────────────── */}
        <div className="flex flex-col flex-shrink-0" style={{ width: 520, background: '#111' }}>

          {/* header */}
          <div className="flex items-center justify-between px-4 py-3"
            style={{ borderBottom: '1px solid #1E1F22' }}>
            <div className="flex items-center gap-2.5">
              <CameraIcon />
              <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                Scan Pantry
              </span>
              {isScanning && (
                <span className="flex items-center gap-1.5 text-xs font-medium"
                  style={{ color: '#34D399' }}>
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse inline-block" />
                  LIVE
                </span>
              )}
            </div>

            <div className="flex items-center gap-2">
              {devices.length > 1 && (
                <select
                  value={selectedDevice}
                  onChange={e => setSelectedDevice(e.target.value)}
                  className="text-xs rounded-lg px-2 py-1 outline-none"
                  style={{ background: '#3F4147', color: 'var(--text-secondary)', border: '1px solid #4F5159' }}
                >
                  {devices.map((d, i) => (
                    <option key={d.deviceId} value={d.deviceId}>
                      {d.label || `Camera ${i + 1}`}
                    </option>
                  ))}
                </select>
              )}
              <button onClick={onClose}
                className="p-1 rounded-lg hover:bg-[#3F4147] transition-colors"
                style={{ color: 'var(--text-secondary)' }}>
                <XIcon />
              </button>
            </div>
          </div>

          {/* video + overlay */}
          <div className="flex-1 relative" style={{ minHeight: 320 }}>
            {phase !== 'error' ? (
              <>
                <video ref={videoRef} autoPlay playsInline muted
                  className="w-full h-full"
                  style={{ display: 'block', objectFit: 'fill' }} />
                <canvas ref={overlayRef}
                  className="absolute inset-0 pointer-events-none"
                  style={{ width: '100%', height: '100%' }} />
                {!ready && (
                  <div className="absolute inset-0 flex items-center justify-center"
                    style={{ background: '#111' }}>
                    <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Starting camera…</p>
                  </div>
                )}
                {phase === 'review' && (
                  <div className="absolute inset-0 flex items-center justify-center"
                    style={{ background: 'rgba(0,0,0,0.55)' }}>
                    <button onClick={resumeScanning}
                      className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold"
                      style={{ background: '#3F4147', color: 'var(--text-primary)' }}>
                      <CameraIcon /> Resume scanning
                    </button>
                  </div>
                )}
              </>
            ) : (
              <div className="flex flex-col items-center justify-center h-full gap-3 p-6 text-center">
                <span className="text-4xl">⚠️</span>
                <p className="text-sm" style={{ color: '#F87171' }}>{errorMsg}</p>
              </div>
            )}
          </div>

          {/* legend + action bar */}
          <div className="px-4 py-3 flex items-center justify-between gap-3"
            style={{ borderTop: '1px solid #1E1F22' }}>
            <div className="flex items-center gap-3 text-xs" style={{ color: 'var(--text-muted)' }}>
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-0.5 inline-block" style={{ background: BOX_COLOR_YOLO, opacity: 0.7 }} />
                YOLO detected
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-0.5 inline-block" style={{ background: BOX_COLOR_CLAUDE }} />
                Claude verified
              </span>
            </div>
            {phase === 'live' && isScanning && (
              <button onClick={goToReview}
                className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold flex-shrink-0"
                style={{ background: '#3F4147', color: 'var(--text-primary)' }}>
                <StopIcon /> Done scanning
              </button>
            )}
            {phase === 'review' && (
              <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                Review items on the right, then add to pantry.
              </p>
            )}
          </div>
        </div>

        {/* ── RIGHT: detected items ─────────────────────────────────────────── */}
        <div className="flex flex-col flex-1 min-w-0">
          <div className="px-5 py-3 flex items-center gap-2.5"
            style={{ borderBottom: '1px solid #3F4147' }}>
            <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              Detected items
            </span>
            {displayItems.length > 0 && (
              <span className="text-xs px-2 py-0.5 rounded-full font-medium"
                style={{ background: 'rgba(0,212,255,0.15)', color: '#00D4FF' }}>
                {displayItems.length}
              </span>
            )}
          </div>

          <div className="flex-1 overflow-y-auto px-4 py-3 space-y-1.5">
            {displayItems.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full gap-3 text-center py-10">
                <span className="text-3xl">🔍</span>
                <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
                  Point the camera at your pantry.<br />
                  YOLO finds items instantly, Claude verifies them.
                </p>
              </div>
            ) : (
              displayItems.map(it => (
                <button
                  key={it.key}
                  onClick={() => phase === 'review' && toggleKey(it.key)}
                  className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-left transition-all"
                  style={{
                    background: selectedKeys.has(it.key) ? 'rgba(0,212,255,0.08)' : '#3F4147',
                    border: `1px solid ${selectedKeys.has(it.key) ? 'rgba(0,212,255,0.35)' : 'transparent'}`,
                    cursor: phase === 'review' ? 'pointer' : 'default',
                  }}
                >
                  {/* checkbox (review) or status dot (live) */}
                  {phase === 'review' ? (
                    <div className="w-5 h-5 rounded-md flex items-center justify-center flex-shrink-0"
                      style={{
                        background: selectedKeys.has(it.key) ? '#00D4FF' : '#2B2D31',
                        border: `1.5px solid ${selectedKeys.has(it.key) ? '#00D4FF' : '#4F5159'}`,
                      }}>
                      {selectedKeys.has(it.key) && <span style={{ color: '#000' }}><CheckIcon /></span>}
                    </div>
                  ) : (
                    <span className="w-2 h-2 rounded-full flex-shrink-0"
                      style={{ background: it.verified ? BOX_COLOR_CLAUDE : BOX_COLOR_YOLO }} />
                  )}

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5">
                      <span className="text-sm font-medium capitalize truncate"
                        style={{ color: 'var(--text-primary)' }}>{it.item}</span>
                      {it.loading && (
                        <span className="text-xs animate-pulse flex-shrink-0"
                          style={{ color: '#00D4FF' }}>Claude…</span>
                      )}
                      {it.verified && (
                        <span className="text-xs flex-shrink-0" style={{ color: '#00D4FF' }}>✓</span>
                      )}
                    </div>
                    <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                      {it.quantity} {it.unit}
                    </span>
                  </div>

                  <span className="text-xs px-1.5 py-0.5 rounded-full flex-shrink-0"
                    style={{
                      background: it.confidence >= 0.75 ? 'rgba(52,211,153,0.15)' : 'rgba(251,191,36,0.15)',
                      color: it.confidence >= 0.75 ? '#34D399' : '#FBBF24',
                    }}>
                    {Math.round(it.confidence * 100)}%
                  </span>
                </button>
              ))
            )}
          </div>

          {phase === 'review' && (
            <div className="px-4 py-3" style={{ borderTop: '1px solid #3F4147' }}>
              <button
                onClick={confirmItems}
                disabled={selectedKeys.size === 0}
                className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl text-sm font-semibold text-white transition-all hover:brightness-110 disabled:opacity-40 disabled:cursor-not-allowed"
                style={{ background: 'linear-gradient(135deg,#0061A0,#0D5E9D)' }}>
                <CheckIcon size={14} />
                Add {selectedKeys.size} item{selectedKeys.size !== 1 ? 's' : ''} to pantry
              </button>
            </div>
          )}
        </div>
      </div>

      <canvas ref={frameRef} className="hidden" />
    </div>
  )
}
