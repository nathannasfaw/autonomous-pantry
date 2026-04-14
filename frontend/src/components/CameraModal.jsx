import { useState, useRef, useEffect, useCallback } from 'react'

const API_BASE = 'http://localhost:8000'
const SCAN_INTERVAL_MS = 900
const MAX_SCAN_WIDTH = 640

const BOX_COLOR_PROVISIONAL = '#00D4FF'
const BOX_COLOR_STICKY = '#34D399'
const BOX_BG_PROVISIONAL = 'rgba(0,212,255,0.08)'

const createScanSessionId = () => {
  if (globalThis.crypto?.randomUUID) {
    return globalThis.crypto.randomUUID()
  }
  return `scan-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
}

const CameraIcon = ({ size = 16 }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" />
    <circle cx="12" cy="13" r="4" />
  </svg>
)

const XIcon = () => (
  <svg
    width="18"
    height="18"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
  >
    <line x1="18" y1="6" x2="6" y2="18" />
    <line x1="6" y1="6" x2="18" y2="18" />
  </svg>
)

const CheckIcon = ({ size = 13 }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2.5"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <polyline points="20 6 9 17 4 12" />
  </svg>
)

const StopIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
    <rect x="3" y="3" width="18" height="18" rx="2" />
  </svg>
)

function drawBoxes(canvas, boxes) {
  const ctx = canvas.getContext('2d')
  const width = canvas.width
  const height = canvas.height
  ctx.clearRect(0, 0, width, height)

  if (boxes.length === 0) return

  console.debug('[Scanner] drawBoxes: canvas=%dx%d boxes=%d', width, height, boxes.length,
    boxes.map(b => `${b.item}(${b.x1.toFixed(2)},${b.y1.toFixed(2)},${b.x2.toFixed(2)},${b.y2.toFixed(2)})`))

  boxes.forEach(box => {
    const stale = (box.stale_frames ?? 0) > 0
    const color = stale ? BOX_COLOR_STICKY : BOX_COLOR_PROVISIONAL
    const x1 = box.x1 * width
    const y1 = box.y1 * height
    const x2 = box.x2 * width
    const y2 = box.y2 * height
    const boxWidth = x2 - x1
    const boxHeight = y2 - y1

    ctx.fillStyle = BOX_BG_PROVISIONAL
    ctx.fillRect(x1, y1, boxWidth, boxHeight)

    ctx.strokeStyle = color
    ctx.lineWidth = stale ? 1.5 : 2.0
    ctx.setLineDash(stale ? [6, 4] : [])
    ctx.strokeRect(x1, y1, boxWidth, boxHeight)
    ctx.setLineDash([])

    const confidence = Math.round((box.confidence ?? 0) * 100)
    // Show the Claude-verified item name once inline verification completes.
    // Until then show "scanning…" so nothing misleading appears.
    const label = box.live_verified
      ? `${box.item} ${confidence}%`
      : box.provisional
        ? `scanning… ${confidence}%`
        : `${box.item} ${confidence}%`
    ctx.font = '11px Inter, system-ui, sans-serif'
    const textWidth = ctx.measureText(label).width
    const paddingX = 6
    const paddingY = 3
    const labelHeight = 14
    const labelX = x1
    const labelY = y1 - labelHeight - paddingY * 2 < 0 ? y1 : y1 - labelHeight - paddingY * 2

    ctx.fillStyle = color
    ctx.fillRect(labelX, labelY, textWidth + paddingX * 2, labelHeight + paddingY * 2)
    ctx.fillStyle = '#fff'
    ctx.fillText(label, labelX + paddingX, labelY + paddingY + labelHeight - 1)
  })
}

export default function CameraModal({ conversationId, onClose, onItemsAdded }) {
  const videoRef = useRef(null)
  const overlayRef = useRef(null)
  const frameRef = useRef(null)
  const streamRef = useRef(null)
  const scanningRef = useRef(false)
  const timeoutRef = useRef(null)
  const sendFrameRef = useRef(null)
  const scanSessionIdRef = useRef(createScanSessionId())
  const latestBoxesRef = useRef([])

  const [devices, setDevices] = useState([])
  const [selectedDevice, setSelectedDevice] = useState('')
  const [ready, setReady] = useState(false)
  const [isScanning, setIsScanning] = useState(false)
  const [phase, setPhase] = useState('live')
  const [errorMsg, setErrorMsg] = useState('')
  const [provisionalItems, setProvisionalItems] = useState([])
  const [reviewItems, setReviewItems] = useState([])
  const [selectedKeys, setSelectedKeys] = useState(new Set())
  const [isFinalizing, setIsFinalizing] = useState(false)

  const resetRemoteScan = useCallback(() => {
    fetch(`${API_BASE}/pantry/reset-scan`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        conversation_id: conversationId,
        scan_session_id: scanSessionIdRef.current,
      }),
    }).catch(() => {})
  }, [conversationId])

  useEffect(() => {
    navigator.mediaDevices.enumerateDevices().then(devs => {
      const cameras = devs.filter(device => device.kind === 'videoinput')
      setDevices(cameras)
      const external = cameras.find(device => !/built-in|facetime|integrated/i.test(device.label))
      setSelectedDevice(external ? external.deviceId : (cameras[0]?.deviceId ?? ''))
    }).catch(() => {})
  }, [])

  const stopStream = useCallback(() => {
    streamRef.current?.getTracks().forEach(track => track.stop())
    streamRef.current = null
  }, [])

  const stopScanLoop = useCallback(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
      timeoutRef.current = null
    }
    scanningRef.current = false
    setIsScanning(false)
  }, [])

  useEffect(() => {
    if (!selectedDevice) return undefined

    const startStream = async () => {
      stopScanLoop()
      stopStream()
      setReady(false)
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: {
            deviceId: { exact: selectedDevice },
            width: { ideal: 1280 },
            height: { ideal: 720 },
          },
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

    startStream()
    return () => {
      stopScanLoop()
      stopStream()
    }
  }, [selectedDevice, stopScanLoop, stopStream])

  useEffect(() => {
    const overlay = overlayRef.current
    if (!overlay || !latestBoxesRef.current.length || phase !== 'live') return
    drawBoxes(overlay, latestBoxesRef.current)
  }, [provisionalItems, phase])

  const scheduleNextScan = useCallback(() => {
    if (phase !== 'live' || !ready) return
    timeoutRef.current = setTimeout(() => {
      timeoutRef.current = null
      sendFrameRef.current?.()
    }, SCAN_INTERVAL_MS)
  }, [phase, ready])

  const sendFrame = useCallback(async () => {
    if (scanningRef.current || phase !== 'live') return

    const video = videoRef.current
    const overlay = overlayRef.current
    const frame = frameRef.current
    if (!video || !overlay || !frame || !streamRef.current) return

    const displayWidth = video.clientWidth
    const displayHeight = video.clientHeight
    if (!displayWidth || !displayHeight) {
      scheduleNextScan()
      return
    }

    // Only resize the canvas when dimensions actually change.
    // Setting canvas.width/height clears the buffer as a side effect, so doing
    // it unconditionally wipes the previous boxes for the entire duration of the
    // backend inference (up to several seconds with heavier models).
    if (overlay.width !== displayWidth || overlay.height !== displayHeight) {
      overlay.width = displayWidth
      overlay.height = displayHeight
    }

    const scale = Math.min(1, MAX_SCAN_WIDTH / displayWidth)
    const scanWidth = Math.max(1, Math.round(displayWidth * scale))
    const scanHeight = Math.max(1, Math.round(displayHeight * scale))
    frame.width = scanWidth
    frame.height = scanHeight
    frame.getContext('2d').drawImage(video, 0, 0, scanWidth, scanHeight)

    const base64 = frame.toDataURL('image/jpeg', 0.72).split(',')[1]

    scanningRef.current = true
    try {
      const res = await fetch(`${API_BASE}/pantry/scan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          image: base64,
          media_type: 'image/jpeg',
          conversation_id: conversationId,
          scan_session_id: scanSessionIdRef.current,
        }),
      })
      if (!res.ok) return
      const data = await res.json()
      const boxes = data.boxes ?? []
      const items = data.items ?? []
      console.debug(
        '[Scanner] /scan → items=%d boxes=%d detector=%s fallback=%s',
        items.length,
        boxes.length,
        data.debug?.detector ?? '?',
        data.debug?.fallback ?? false,
        boxes.length > 0 ? boxes.map(b => `${b.item}@(${b.x1.toFixed(2)},${b.y1.toFixed(2)})`) : '(none)',
      )
      if (data.debug?.discarded?.length > 0) {
        console.debug('[Scanner] discarded candidates:', data.debug.discarded)
      }
      latestBoxesRef.current = boxes
      setProvisionalItems(items)
      drawBoxes(overlay, latestBoxesRef.current)
    } catch (_) {
      // Live scan failures should not break the camera session.
    } finally {
      scanningRef.current = false
      scheduleNextScan()
    }
  }, [conversationId, phase, scheduleNextScan])

  sendFrameRef.current = sendFrame

  const startScanLoop = useCallback(() => {
    if (timeoutRef.current || scanningRef.current) return
    setIsScanning(true)
    sendFrame()
  }, [sendFrame])

  useEffect(() => {
    if (ready && phase === 'live') {
      startScanLoop()
    }
    return () => stopScanLoop()
  }, [ready, phase, startScanLoop, stopScanLoop])

  useEffect(() => () => {
    stopScanLoop()
    stopStream()
    resetRemoteScan()
  }, [resetRemoteScan, stopScanLoop, stopStream])

  const goToReview = useCallback(async () => {
    stopScanLoop()
    const overlay = overlayRef.current
    if (overlay) {
      overlay.getContext('2d').clearRect(0, 0, overlay.width, overlay.height)
    }

    setIsFinalizing(true)
    setPhase('finalizing')
    try {
      const res = await fetch(`${API_BASE}/pantry/finalize-scan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          conversation_id: conversationId,
          scan_session_id: scanSessionIdRef.current,
        }),
      })
      if (!res.ok) {
        throw new Error('Final verification failed')
      }
      const data = await res.json()
      const items = data.items ?? []
      setReviewItems(items)
      setSelectedKeys(new Set(items.map(item => item.track_id)))
      setPhase('review')
    } catch (err) {
      setErrorMsg(err.message || 'Final verification failed')
      setPhase('error')
    } finally {
      setIsFinalizing(false)
    }
  }, [conversationId, stopScanLoop])

  const confirmItems = useCallback(async () => {
    const items = reviewItems
      .filter(item => selectedKeys.has(item.track_id))
      .map(item => ({
        item: item.item,
        quantity: item.quantity,
        unit: item.unit,
        confidence: item.confidence,
      }))

    if (!items.length) {
      resetRemoteScan()
      onClose()
      return
    }

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
    resetRemoteScan()
    onClose()
  }, [conversationId, onClose, onItemsAdded, resetRemoteScan, reviewItems, selectedKeys])

  const closeModal = useCallback(() => {
    stopScanLoop()
    stopStream()
    resetRemoteScan()
    onClose()
  }, [onClose, resetRemoteScan, stopScanLoop, stopStream])

  const toggleKey = useCallback(key => {
    setSelectedKeys(prev => {
      const next = new Set(prev)
      if (next.has(key)) {
        next.delete(key)
      } else {
        next.add(key)
      }
      return next
    })
  }, [])

  const resumeScanning = useCallback(() => {
    setPhase('live')
    setReviewItems([])
  }, [])

  const liveItems = provisionalItems.map((item, index) => ({
    key: item.track_id,
    item: item.live_verified ? item.item : `item ${index + 1}`,
    quantity: item.quantity,
    unit: item.unit,
    confidence: item.confidence,
    provisional: !item.live_verified,
    liveVerified: item.live_verified,
    verificationOnly: item.verification_only,
    seenCount: item.seen_count,
  }))

  const reviewedItems = reviewItems.map(item => ({
    key: item.track_id,
    item: item.item,
    quantity: item.quantity,
    unit: item.unit,
    confidence: item.confidence,
    verified: item.verified,
    provisionalItem: item.provisional_item,
  }))

  const panelItems = phase === 'review' ? reviewedItems : liveItems

  return (
    <div
      className="fixed inset-0 flex items-center justify-center z-50"
      style={{ background: 'rgba(0,0,0,0.82)', backdropFilter: 'blur(6px)' }}
      onClick={event => event.target === event.currentTarget && closeModal()}
    >
      <div
        className="flex rounded-2xl overflow-hidden"
        style={{
          background: '#2B2D31',
          border: '1px solid #4F5159',
          width: '92vw',
          maxWidth: 860,
          maxHeight: '90vh',
          boxShadow: '0 32px 80px rgba(0,0,0,0.7)',
        }}
      >
        <div className="flex flex-col flex-shrink-0" style={{ width: 520, background: '#111' }}>
          <div className="flex items-center justify-between px-4 py-3" style={{ borderBottom: '1px solid #1E1F22' }}>
            <div className="flex items-center gap-2.5">
              <CameraIcon />
              <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                Scan Pantry
              </span>
              {isScanning && phase === 'live' && (
                <span className="flex items-center gap-1.5 text-xs font-medium" style={{ color: '#34D399' }}>
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse inline-block" />
                  LIVE
                </span>
              )}
            </div>

            <div className="flex items-center gap-2">
              {devices.length > 1 && (
                <select
                  value={selectedDevice}
                  onChange={event => setSelectedDevice(event.target.value)}
                  className="text-xs rounded-lg px-2 py-1 outline-none"
                  style={{ background: '#3F4147', color: 'var(--text-secondary)', border: '1px solid #4F5159' }}
                >
                  {devices.map((device, index) => (
                    <option key={device.deviceId} value={device.deviceId}>
                      {device.label || `Camera ${index + 1}`}
                    </option>
                  ))}
                </select>
              )}
              <button
                onClick={closeModal}
                className="p-1 rounded-lg hover:bg-[#3F4147] transition-colors"
                style={{ color: 'var(--text-secondary)' }}
              >
                <XIcon />
              </button>
            </div>
          </div>

          <div className="flex-1 relative" style={{ minHeight: 320 }}>
            {phase !== 'error' ? (
              <>
                <video
                  ref={videoRef}
                  autoPlay
                  playsInline
                  muted
                  className="w-full h-full"
                  style={{ display: 'block', objectFit: 'fill' }}
                />
                <canvas
                  ref={overlayRef}
                  className="absolute inset-0 pointer-events-none"
                  style={{ width: '100%', height: '100%' }}
                />
                {!ready && (
                  <div className="absolute inset-0 flex items-center justify-center" style={{ background: '#111' }}>
                    <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Starting camera...</p>
                  </div>
                )}
                {phase === 'finalizing' && (
                  <div className="absolute inset-0 flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.55)' }}>
                    <div className="text-center space-y-2">
                      <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                        Reviewing best crops
                      </p>
                      <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                        Final verification only runs once per tracked item.
                      </p>
                    </div>
                  </div>
                )}
                {phase === 'review' && (
                  <div className="absolute inset-0 flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.55)' }}>
                    <button
                      onClick={resumeScanning}
                      className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold"
                      style={{ background: '#3F4147', color: 'var(--text-primary)' }}
                    >
                      <CameraIcon /> Resume scanning
                    </button>
                  </div>
                )}
              </>
            ) : (
              <div className="flex flex-col items-center justify-center h-full gap-3 p-6 text-center">
                <p className="text-sm" style={{ color: '#F87171' }}>{errorMsg}</p>
              </div>
            )}
          </div>

          <div className="px-4 py-3 flex items-center justify-between gap-3" style={{ borderTop: '1px solid #1E1F22' }}>
            <div className="flex items-center gap-3 text-xs" style={{ color: 'var(--text-muted)' }}>
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-0.5 inline-block" style={{ background: BOX_COLOR_PROVISIONAL, opacity: 0.8 }} />
                Live detection (scanning…)
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-0.5 inline-block" style={{ background: BOX_COLOR_STICKY }} />
                Sticky carry-over
              </span>
            </div>

            {phase === 'live' && isScanning && (
              <button
                onClick={goToReview}
                className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold flex-shrink-0"
                style={{ background: '#3F4147', color: 'var(--text-primary)' }}
              >
                <StopIcon /> Done scanning
              </button>
            )}
            {phase === 'review' && (
              <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                Review the final items on the right, then add them to your pantry.
              </p>
            )}
          </div>
        </div>

        <div className="flex flex-col flex-1 min-w-0">
          <div className="px-5 py-3 flex items-center gap-2.5" style={{ borderBottom: '1px solid #3F4147' }}>
            <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              {phase === 'review' ? 'Reviewed items' : 'Tracked items'}
            </span>
            {panelItems.length > 0 && (
              <span
                className="text-xs px-2 py-0.5 rounded-full font-medium"
                style={{ background: 'rgba(0,212,255,0.15)', color: '#00D4FF' }}
              >
                {panelItems.length}
              </span>
            )}
          </div>

          <div className="flex-1 overflow-y-auto px-4 py-3 space-y-1.5">
            {phase === 'finalizing' ? (
              <div className="flex flex-col items-center justify-center h-full gap-3 text-center py-10">
                <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
                  Finalizing your scan with one verification pass per tracked item...
                </p>
              </div>
            ) : panelItems.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full gap-3 text-center py-10">
                <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
                  {phase === 'review'
                    ? 'No final pantry items were confirmed from this scan.'
                    : 'Point the camera at your items. Boxes appear as objects are detected — item names are identified by Claude after you click Done scanning.'}
                </p>
              </div>
            ) : (
              panelItems.map(item => (
                <button
                  key={item.key}
                  onClick={() => phase === 'review' && toggleKey(item.key)}
                  className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-left transition-all"
                  style={{
                    background: selectedKeys.has(item.key) ? 'rgba(0,212,255,0.08)' : '#3F4147',
                    border: `1px solid ${selectedKeys.has(item.key) ? 'rgba(0,212,255,0.35)' : 'transparent'}`,
                    cursor: phase === 'review' ? 'pointer' : 'default',
                  }}
                >
                  {phase === 'review' ? (
                    <div
                      className="w-5 h-5 rounded-md flex items-center justify-center flex-shrink-0"
                      style={{
                        background: selectedKeys.has(item.key) ? '#00D4FF' : '#2B2D31',
                        border: `1.5px solid ${selectedKeys.has(item.key) ? '#00D4FF' : '#4F5159'}`,
                      }}
                    >
                      {selectedKeys.has(item.key) && <span style={{ color: '#000' }}><CheckIcon /></span>}
                    </div>
                  ) : (
                    <span
                      className="w-2 h-2 rounded-full flex-shrink-0"
                      style={{ background: BOX_COLOR_PROVISIONAL }}
                    />
                  )}

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5">
                      <span className="text-sm font-medium capitalize truncate" style={{ color: 'var(--text-primary)' }}>
                        {item.item}
                      </span>
                      {phase === 'review' && item.verified && (
                        <span className="text-xs flex-shrink-0" style={{ color: '#00D4FF' }}>Verified</span>
                      )}
                      {phase === 'review' && !item.verified && (
                        <span className="text-xs flex-shrink-0" style={{ color: 'var(--text-muted)' }}>Detector fallback</span>
                      )}
                      {phase !== 'review' && item.liveVerified && (
                        <span className="text-xs flex-shrink-0" style={{ color: '#34D399' }}>Live ID</span>
                      )}
                      {phase !== 'review' && !item.liveVerified && (
                        <span className="text-xs flex-shrink-0" style={{ color: 'var(--text-muted)' }}>Detecting…</span>
                      )}
                    </div>

                    <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                      {item.quantity} {item.unit}
                      {phase === 'review' && item.provisionalItem && item.provisionalItem !== item.item
                        ? `  |  detector saw ${item.provisionalItem}`
                        : ''}
                    </span>
                  </div>

                  <span
                    className="text-xs px-1.5 py-0.5 rounded-full flex-shrink-0"
                    style={{
                      background: item.confidence >= 0.75 ? 'rgba(52,211,153,0.15)' : 'rgba(251,191,36,0.15)',
                      color: item.confidence >= 0.75 ? '#34D399' : '#FBBF24',
                    }}
                  >
                    {Math.round(item.confidence * 100)}%
                  </span>
                </button>
              ))
            )}
          </div>

          {phase === 'review' && (
            <div className="px-4 py-3" style={{ borderTop: '1px solid #3F4147' }}>
              <button
                onClick={confirmItems}
                disabled={selectedKeys.size === 0 || isFinalizing}
                className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl text-sm font-semibold text-white transition-all hover:brightness-110 disabled:opacity-40 disabled:cursor-not-allowed"
                style={{ background: 'linear-gradient(135deg,#0061A0,#0D5E9D)' }}
              >
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
