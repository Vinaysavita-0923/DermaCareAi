import { useCallback, useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import {
  confirmAgentAction,
  deleteChatSession,
  getChatSession,
  listChatSessions,
  sendChatMessage,
  type ChatMessage,
  type ChatSession,
  type ProposedAction,
  type ToolTrace,
} from '../services/chat'
import { extractErrorMessage } from '../services/auth'
import { useAuth } from '../hooks/useAuth'

interface Extras {
  trace: ToolTrace[]
  actions: { action: ProposedAction; state: 'pending' | 'done' | 'cancelled'; result?: string }[]
}

const MENU: { title: string; questions: string[]; featured?: boolean }[] = [
  { title: 'Continue your skincare journey', questions: ['Check my latest skin assessment'], featured: true },
  {
    title: 'Explore skincare options',
    questions: [
      'What is my skin type?',
      'How to reduce acne?',
      'Suggest a skincare routine',
      'Why is my skin getting dry?',
    ],
  },
  {
    title: 'Your skin, your questions',
    questions: ['Dark spots & pigmentation', 'Acne & pimples', 'Oily vs dry skin', 'Sunscreen recommendations'],
  },
  {
    title: 'Try something new',
    questions: ['Build my morning routine', 'Understand my skin report', 'Ingredients to avoid'],
  },
]

// Related questions offered after a reply, picked by the topic of the exchange.
const RELATED: { match: RegExp; questions: string[] }[] = [
  {
    match: /acne|pimple|breakout|comedon|blackhead|whitehead/i,
    questions: ['Which ingredients help with acne?', 'Show acne-friendly cleansers', 'Can I use niacinamide with salicylic acid?'],
  },
  {
    match: /dry|dehydrat|flak|tight/i,
    questions: ['Suggest a moisturizer for dry skin', 'Is hyaluronic acid good for me?', 'Why does my skin feel tight after washing?'],
  },
  {
    match: /oily|sebum|shine|pore/i,
    questions: ['Best cleanser for oily skin', 'How do I minimise pores?', 'Do oily skin types need moisturizer?'],
  },
  {
    match: /dark spot|pigment|melasma|uneven|tan/i,
    questions: ['Is vitamin C good for dark spots?', 'How long do dark spots take to fade?', 'Show serums for pigmentation'],
  },
  {
    match: /sunscreen|spf|sun|uv/i,
    questions: ['Mineral vs chemical sunscreen?', 'How much sunscreen should I apply?', 'Show sunscreens for my skin type'],
  },
  {
    match: /routine|morning|night|evening|step/i,
    questions: ['Build my night routine', 'In what order should I apply products?', 'Save this as my morning routine'],
  },
  {
    match: /ingredient|avoid|fragrance|retinol|acid/i,
    questions: ['Which ingredients should not be mixed?', 'Is retinol safe for sensitive skin?', 'Explain niacinamide'],
  },
  {
    match: /assessment|profile|report|skin type/i,
    questions: ['Recommend products for my profile', 'What should I focus on first?', 'Understand my skin report'],
  },
]
const DEFAULT_RELATED = ['Suggest a skincare routine', 'Ingredients to avoid', 'Sunscreen recommendations']

function relatedFor(text: string): string[] {
  const picked: string[] = []
  for (const { match, questions } of RELATED) {
    if (match.test(text)) picked.push(...questions)
    if (picked.length >= 3) break
  }
  return (picked.length ? picked : DEFAULT_RELATED).slice(0, 3)
}

// --- Voice input (browser Web Speech API; Chrome/Edge) ---
interface SpeechResultEvent {
  resultIndex: number
  results: ArrayLike<{ isFinal: boolean; 0: { transcript: string } }>
}
interface SpeechRecognizer {
  lang: string
  interimResults: boolean
  continuous: boolean
  onresult: ((e: SpeechResultEvent) => void) | null
  onerror: ((e: { error: string }) => void) | null
  onend: (() => void) | null
  start: () => void
  stop: () => void
}
type SpeechCtor = new () => SpeechRecognizer

function speechCtor(): SpeechCtor | null {
  const w = window as unknown as { SpeechRecognition?: SpeechCtor; webkitSpeechRecognition?: SpeechCtor }
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null
}

const VOICE_ROUTES: { match: RegExp; to: string; label: string }[] = [
  { match: /dashboard|home/, to: '/dashboard', label: 'Dashboard' },
  { match: /product|ingredient/, to: '/products', label: 'Products & Ingredients' },
  { match: /routine/, to: '/routines', label: 'Skincare Routine' },
  { match: /journal|diary/, to: '/journal', label: 'Skin Journal' },
  { match: /report|progress/, to: '/reports', label: 'Reports' },
  { match: /assessment/, to: '/skin-assessment', label: 'Skin Assessment' },
  { match: /profile/, to: '/profile', label: 'My Profile' },
  { match: /analysis|scan|camera|photo/, to: '/acne-analysis', label: 'Skin Analysis' },
]

// "open products", "go to my routine", "show reports" -> a page, not a question.
function voiceRoute(text: string) {
  const m = text.toLowerCase().match(/^(?:please\s+)?(?:open|go to|show(?: me)?|take me to|navigate to)\s+(?:the\s+|my\s+)?(.+)$/)
  if (!m) return null
  return VOICE_ROUTES.find((r) => r.match.test(m[1])) ?? null
}

const VOICE_ERRORS: Record<string, string> = {
  'not-allowed': 'Microphone access was blocked. Allow it in your browser’s site settings to use voice.',
  'service-not-allowed': 'Microphone access was blocked. Allow it in your browser’s site settings to use voice.',
  network: 'This browser can’t reach its speech service (Brave blocks it). Try Chrome or Edge for voice.',
  'no-speech': 'I didn’t catch that — tap the mic and try again.',
  'audio-capture': 'No microphone was found.',
}

// The backend appends this to every answer (app/services/safety_service.py
// MEDICAL_DISCLAIMER). Shown once under the input instead of in each bubble.
const MEDICAL_DISCLAIMER =
  'This is general educational information about skin care, not medical advice, diagnosis, or treatment. ' +
  'For a persistent, worsening, painful, or concerning skin problem, please see a qualified doctor or dermatologist.'

function stripDisclaimer(text: string): string {
  const i = text.lastIndexOf('This is general educational information about skin care')
  return i > 0 ? text.slice(0, i).trimEnd() : text
}

const CONSENT_KEY = 'kashvi.useProfile'

function readConsent(): boolean {
  try {
    return localStorage.getItem(CONSENT_KEY) !== 'false'
  } catch {
    return true
  }
}

// Invisible marker TypedReply appends to the partial text; renderInline
// turns it into the blinking cursor so it sits at the end of the last line.
const CURSOR_MARK = '⁣'

// Minimal formatting for model replies: **bold** and "-"/"*" bullet lines.
function renderInline(text: string): ReactNode[] {
  return text.split(/<br\s*\/?>/i).flatMap((segment, s) => [
    ...(s > 0 ? [<br key={`br-${s}`} />] : []),
    ...segment.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
      part.startsWith('**') && part.endsWith('**') ? (
        <strong key={`${s}-${i}`}>{part.slice(2, -2)}</strong>
      ) : (
        <span key={`${s}-${i}`}>{renderItalic(part)}</span>
      ),
    ),
  ])
}

// Single-asterisk *emphasis*, plus the typing cursor marker.
function renderItalic(text: string): ReactNode[] {
  return text.split(/(\*[^*\s][^*]*\*)/g).map((part, i) => {
    const italic = part.length > 2 && part.startsWith('*') && part.endsWith('*')
    const body = italic ? part.slice(1, -1) : part
    const content = body.includes(CURSOR_MARK) ? (
      <>
        {body.replace(CURSOR_MARK, '')}
        <span className="type-cursor" aria-hidden="true" />
      </>
    ) : (
      body
    )
    return italic ? <em key={i}>{content}</em> : <span key={i}>{content}</span>
  })
}

function cells(line: string): string[] {
  return line.replace(/^\|/, '').replace(/\|$/, '').split('|').map((c) => c.trim())
}

function FormattedText({ text }: { text: string }) {
  const blocks: ReactNode[] = []
  let bullets: { mark: string; text: string; sub: boolean }[] = []
  let table: string[][] = []
  const flushTable = () => {
    if (table.length) {
      const [head, ...body] = table
      blocks.push(
        <div key={`t-${blocks.length}`} className="my-1 overflow-x-auto rounded-xl border border-emerald-100">
          <table className="w-full text-left text-[15px]">
            <thead className="bg-emerald-50 text-emerald-900">
              <tr>
                {head.map((h, i) => (
                  <th key={i} className="px-2.5 py-2 font-semibold">
                    {renderInline(h)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {body.map((row, r) => (
                <tr key={r} className="border-t border-emerald-50 align-top">
                  {row.map((c, i) => (
                    <td key={i} className="px-2.5 py-2">
                      {renderInline(c)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>,
      )
      table = []
    }
  }
  const flush = () => {
    flushTable()
    if (bullets.length) {
      blocks.push(
        <ul key={`ul-${blocks.length}`} className="my-1 space-y-1">
          {bullets.map((b, i) => (
            <li key={i} className={`flex gap-2 ${b.sub ? 'pl-7' : ''}`}>
              <span className="shrink-0 font-semibold text-emerald-600">{b.mark}</span>
              <span>{renderInline(b.text)}</span>
            </li>
          ))}
        </ul>,
      )
      bullets = []
    }
  }
  for (const raw of text.split('\n')) {
    const line = raw.trim().replace(/^>\s*/, '')
    if (line.startsWith('|')) {
      if (!/^\|[\s:|-]+\|?$/.test(line)) table.push(cells(line))
      continue
    }
    flushTable()
    if (/^[-*_]{3,}$/.test(line)) continue
    const bullet = line.match(/^([-*•]|\d+\.)\s+(.*)$/)
    if (bullet) {
      bullets.push({ mark: /\d/.test(bullet[1]) ? bullet[1] : '•', text: bullet[2], sub: /^\s{2,}/.test(raw) })
      continue
    }
    flush()
    if (/^#+\s/.test(line)) {
      blocks.push(
        <p key={`h-${blocks.length}`} className="pt-1 font-semibold text-emerald-900">
          {renderInline(line.replace(/^#+\s*/, ''))}
        </p>,
      )
    } else if (line) blocks.push(<p key={`p-${blocks.length}`}>{renderInline(line)}</p>)
  }
  flush()
  return <div className="space-y-2 leading-relaxed">{blocks}</div>
}

// Reveals a finished reply word by word, ChatGPT-style, at a steady reading
// pace (~16 words/s). Very long answers speed up so none takes over ~15s;
// click to show it all at once.
const WORD_MS = 60
const MAX_TYPING_MS = 15000

function TypedReply({ text, onDone, onProgress }: { text: string; onDone: () => void; onProgress: () => void }) {
  // Alternating word / whitespace tokens: revealing 2 tokens = 1 word.
  const tokens = text.split(/(\s+)/)
  const [shown, setShown] = useState(0)

  useEffect(() => {
    const words = Math.ceil(tokens.length / 2)
    const delay = Math.max(15, Math.min(WORD_MS, MAX_TYPING_MS / Math.max(words, 1)))
    const id = window.setInterval(() => {
      setShown((n) => {
        const next = Math.min(tokens.length, n + 2)
        if (next >= tokens.length) window.clearInterval(id)
        return next
      })
    }, delay)
    return () => window.clearInterval(id)
  }, [tokens.length])

  useEffect(() => {
    if (shown >= tokens.length) onDone()
    else onProgress()
  }, [shown, tokens.length, onDone, onProgress])

  return (
    <div onClick={() => setShown(tokens.length)} title="Click to show the full answer" className="cursor-text">
      <FormattedText text={tokens.slice(0, shown).join('').trimEnd() + (shown < tokens.length ? CURSOR_MARK : '')} />
    </div>
  )
}

const prefersReducedMotion = () =>
  typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

export default function Chatbot() {
  const { user } = useAuth()
  const location = useLocation()
  // Extras (what Kashvi looked up, actions to confirm) belong to a reply in
  // this browser session; they are not stored on the server.
  const [extras, setExtras] = useState<Record<number, Extras>>({})
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [activeId, setActiveId] = useState<number | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showHistory, setShowHistory] = useState(false)
  const [useProfile, setUseProfile] = useState(readConsent)
  const listRef = useRef<HTMLDivElement>(null)
  const [typingId, setTypingId] = useState<number | null>(null)
  const typingIdRef = useRef<number | null>(null)
  typingIdRef.current = typingId
  // While a reply types out, keep the newest line in view - unless the user
  // scrolls up to read, in which case stop following until they return.
  const followRef = useRef(true)
  const followTyping = useCallback(() => {
    const list = listRef.current
    if (list && followRef.current) list.scrollTop = list.scrollHeight
  }, [])
  const typingDone = useCallback(() => {
    setTypingId(null)
    // let the "You might also ask" chips render, then bring them into view
    window.setTimeout(() => {
      const list = listRef.current
      if (list && followRef.current) list.scrollTo({ top: list.scrollHeight, behavior: 'smooth' })
    }, 50)
  }, [])

  function onListScroll() {
    const list = listRef.current
    if (!list) return
    followRef.current = list.scrollHeight - list.scrollTop - list.clientHeight < 60
  }
  const inputRef = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()
  const recognizerRef = useRef<SpeechRecognizer | null>(null)
  const [listening, setListening] = useState(false)
  const [voiceNote, setVoiceNote] = useState<string | null>(null)
  const voiceSupported = speechCtor() !== null

  useEffect(() => () => recognizerRef.current?.stop(), [])

  function toggleVoice() {
    if (listening) {
      recognizerRef.current?.stop()
      return
    }
    const Ctor = speechCtor()
    if (!Ctor) return
    const rec = new Ctor()
    rec.lang = 'en-IN'
    rec.interimResults = true
    rec.continuous = false
    let finalText = ''
    rec.onresult = (e) => {
      let interim = ''
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const r = e.results[i]
        if (r.isFinal) finalText += r[0].transcript
        else interim += r[0].transcript
      }
      setInput((finalText + interim).trim())
    }
    rec.onerror = (e) => setVoiceNote(VOICE_ERRORS[e.error] ?? 'Voice input stopped unexpectedly. Please try again.')
    rec.onend = () => {
      setListening(false)
      recognizerRef.current = null
      const text = finalText.trim()
      if (!text) return
      const route = voiceRoute(text)
      if (route) {
        setInput('')
        navigate(route.to)
      } else {
        ask(text)
      }
    }
    setVoiceNote(null)
    recognizerRef.current = rec
    setListening(true)
    rec.start()
  }

  const firstName = user?.full_name?.trim().split(/\s+/)[0] || 'there'
  const inChat = messages.length > 0 || sending

  function reloadSessions() {
    listChatSessions()
      .then(setSessions)
      .catch((err) => setError(extractErrorMessage(err)))
  }

  useEffect(reloadSessions, [])

  // Other pages (e.g. Acne Analysis) can hand over a draft question.
  // It is only placed in the box - the user still presses Send.
  // The top-bar search asks Kashvi directly (autoSend); other pages only
  // prefill. The ref stops a double send when the effect re-runs.
  const handledState = useRef<unknown>(null)
  useEffect(() => {
    const state = location.state as { prefill?: string; autoSend?: boolean } | null
    if (!state?.prefill || handledState.current === state) return
    handledState.current = state
    if (state.autoSend) {
      setMessages([])
      setActiveId(null)
      ask(state.prefill, null)
    } else {
      setInput(state.prefill)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.state])

  // Scroll only the message list. scrollIntoView() would also scroll the
  // overflow-hidden chat card, pushing the header and messages out of view.
  // When a reply lands, keep the user's question at the top so the start of
  // the answer is readable; otherwise (sending/typing) stick to the bottom.
  useEffect(() => {
    const list = listRef.current
    if (!list) return
    const last = messages[messages.length - 1]
    // A reply that is about to type out is followed by followTyping() instead.
    if (!sending && last?.role === 'assistant' && last.id !== typingIdRef.current) {
      const question = [...messages].reverse().find((m) => m.role === 'user')
      const el = question && list.querySelector<HTMLElement>(`[data-msg-id="${question.id}"]`)
      if (el) {
        list.scrollTo({ top: el.offsetTop - 12, behavior: 'smooth' })
        return
      }
    }
    list.scrollTo({ top: list.scrollHeight, behavior: 'smooth' })
  }, [messages, sending])

  function toggleConsent() {
    const next = !useProfile
    setUseProfile(next)
    try {
      localStorage.setItem(CONSENT_KEY, String(next))
    } catch {
      /* storage unavailable - the toggle still works for this visit */
    }
  }

  async function openSession(id: number) {
    setError(null)
    setShowHistory(false)
    try {
      const detail = await getChatSession(id)
      setActiveId(id)
      setMessages(detail.messages)
    } catch (err) {
      setError(extractErrorMessage(err))
    }
  }

  function backToMenu() {
    setTypingId(null)
    setActiveId(null)
    setMessages([])
    setError(null)
    setShowHistory(false)
  }

  async function handleDelete(id: number) {
    try {
      await deleteChatSession(id)
      if (activeId === id) backToMenu()
      reloadSessions()
    } catch (err) {
      setError(extractErrorMessage(err))
    }
  }

  async function ask(raw: string, sessionId: number | null = activeId) {
    const text = raw.trim()
    if (!text || sending) return
    setError(null)
    setSending(true)

    const optimisticUser: ChatMessage = {
      id: -Date.now(),
      role: 'user',
      content: text,
      is_mock_response: false,
      created_at: new Date().toISOString(),
    }
    setMessages((prev) => [...prev, optimisticUser])
    setInput('')

    try {
      const result = await sendChatMessage(text, sessionId ?? undefined, useProfile)
      if (!prefersReducedMotion()) {
        followRef.current = true
        setTypingId(result.reply.id)
      }
      setMessages((prev) => [...prev, result.reply])
      if (result.tool_trace.length || result.proposed_actions.length) {
        setExtras((prev) => ({
          ...prev,
          [result.reply.id]: {
            trace: result.tool_trace,
            actions: result.proposed_actions.map((action) => ({ action, state: 'pending' as const })),
          },
        }))
      }
      if (sessionId === null) {
        setActiveId(result.session_id)
        reloadSessions()
      }
    } catch (err) {
      // The backend saves nothing on a failed turn, so drop the optimistic message too.
      setMessages((prev) => prev.filter((m) => m.id !== optimisticUser.id))
      setInput(text)
      setError(extractErrorMessage(err))
    } finally {
      setSending(false)
      inputRef.current?.focus()
    }
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    ask(input)
  }

  function setActionState(messageId: number, index: number, patch: Partial<Extras['actions'][number]>) {
    setExtras((prev) => {
      const cur = prev[messageId]
      if (!cur) return prev
      const actions = cur.actions.map((a, i) => (i === index ? { ...a, ...patch } : a))
      return { ...prev, [messageId]: { ...cur, actions } }
    })
  }

  async function handleConfirm(messageId: number, index: number, token: string) {
    setError(null)
    try {
      const result = await confirmAgentAction(token)
      setActionState(messageId, index, { state: 'done', result })
    } catch (err) {
      setError(extractErrorMessage(err))
    }
  }

  const last = messages[messages.length - 1]
  const lastUser = [...messages].reverse().find((m) => m.role === 'user')
  const related =
    !sending && typingId === null && last?.role === 'assistant' ? relatedFor(`${lastUser?.content ?? ''} ${last.content}`) : []

  return (
    <div className="mx-auto flex h-[calc(100vh-7.5rem)] min-h-[36rem] max-w-5xl flex-col overflow-hidden rounded-3xl border border-emerald-100 bg-white shadow-sm">
      {/* Header */}
      <header className="relative shrink-0 border-b border-emerald-100 bg-gradient-to-b from-emerald-50 to-white px-4 pb-3 pt-4 text-center">
        {inChat && (
          <button
            type="button"
            onClick={backToMenu}
            aria-label="Back to main menu"
            title="Back to main menu"
            className="absolute left-4 top-4 rounded-full p-2 text-slate-500 hover:bg-emerald-100 hover:text-emerald-800"
          >
            <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 6 6 18M6 6l12 12" strokeLinecap="round" />
            </svg>
          </button>
        )}
        <button
          type="button"
          onClick={() => setShowHistory((v) => !v)}
          aria-label="Chat history"
          title="Chat history"
          className={`absolute right-4 top-4 rounded-full p-2 hover:bg-emerald-100 hover:text-emerald-800 ${
            showHistory ? 'bg-emerald-100 text-emerald-800' : 'text-slate-500'
          }`}
        >
          <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M3 12a9 9 0 1 0 3-6.7L3 8" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M3 3v5h5M12 7v5l3 2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
        <h1 className="text-2xl font-semibold text-emerald-900">
          Kashvi <span className="text-emerald-500">✦</span>
        </h1>
        <p className="text-sm text-slate-500">Your AI Skincare Companion</p>
        <label className="mt-2 inline-flex cursor-pointer items-center gap-2 text-xs text-slate-500">
          <span
            role="switch"
            aria-checked={useProfile}
            tabIndex={0}
            onClick={toggleConsent}
            onKeyDown={(e) => (e.key === ' ' || e.key === 'Enter') && (e.preventDefault(), toggleConsent())}
            className={`relative inline-block h-4 w-7 rounded-full transition-colors ${
              useProfile ? 'bg-emerald-600' : 'bg-slate-300'
            }`}
          >
            <span
              className={`absolute top-0.5 h-3 w-3 rounded-full bg-white transition-all ${
                useProfile ? 'left-3.5' : 'left-0.5'
              }`}
            />
          </span>
          <span onClick={toggleConsent}>
            {useProfile ? 'Personalising with my skin assessment' : 'Not using my skin assessment'}
          </span>
        </label>
      </header>

      <div className="relative flex min-h-0 flex-1 flex-col">
        {/* History drawer */}
        {showHistory && (
          <div className="anim-fade-in absolute inset-0 z-10 overflow-y-auto bg-white p-4">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-slate-800">Previous chats</h2>
              <button
                type="button"
                onClick={backToMenu}
                className="rounded-full bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-700"
              >
                + New chat
              </button>
            </div>
            {sessions.length === 0 ? (
              <p className="py-6 text-center text-sm text-slate-400">No conversations yet.</p>
            ) : (
              <ul className="space-y-1.5">
                {sessions.map((s) => (
                  <li
                    key={s.id}
                    className={`flex items-center justify-between rounded-xl border px-3 py-2 text-sm ${
                      activeId === s.id ? 'border-emerald-300 bg-emerald-50' : 'border-slate-100 hover:bg-slate-50'
                    }`}
                  >
                    <button onClick={() => openSession(s.id)} className="flex-1 truncate text-left text-slate-700">
                      {s.title || 'Untitled chat'}
                      <span className="ml-2 text-xs text-slate-400">
                        {new Date(s.created_at).toLocaleDateString()}
                      </span>
                    </button>
                    <button
                      onClick={() => handleDelete(s.id)}
                      className="ml-2 text-xs text-slate-300 hover:text-rose-600"
                      aria-label="Delete conversation"
                    >
                      ✕
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        <div ref={listRef} onScroll={onListScroll} className="relative flex-1 overflow-y-auto px-4 py-5 sm:px-6">
          {!inChat ? (
            <div className="space-y-6">
              <div className="anim-fade-up">
                <h2 className="text-2xl font-semibold text-slate-900">Hi, {firstName}! 👋</h2>
                <p className="mt-1 text-lg text-slate-600">I'm Kashvi! What do you need help with today?</p>
              </div>

              {MENU.map((section, si) => (
                <section key={section.title} className="anim-fade-up" style={{ ['--d' as string]: `${0.08 * (si + 1)}s` }}>
                  <h3 className="mb-2.5 text-sm font-semibold text-slate-800">{section.title}</h3>
                  <div className="flex flex-wrap gap-2">
                    {section.questions.map((q) =>
                      section.featured ? (
                        <button
                          key={q}
                          type="button"
                          onClick={() => ask(q)}
                          className="flex w-full items-center gap-3 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3.5 text-left font-medium text-emerald-800 transition hover:-translate-y-0.5 hover:bg-emerald-100 hover:shadow-sm"
                        >
                          <span className="flex h-8 w-8 items-center justify-center rounded-full bg-emerald-600 text-white">
                            <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
                              <path d="M4 8V5a1 1 0 0 1 1-1h3M16 4h3a1 1 0 0 1 1 1v3M20 16v3a1 1 0 0 1-1 1h-3M8 20H5a1 1 0 0 1-1-1v-3M9 10h.01M15 10h.01M9.5 15a3.5 3.5 0 0 0 5 0" strokeLinecap="round" />
                            </svg>
                          </span>
                          {q}
                          <span className="ml-auto text-emerald-500">→</span>
                        </button>
                      ) : (
                        <QuestionChip key={q} text={q} onClick={() => ask(q)} />
                      ),
                    )}
                  </div>
                </section>
              ))}

              <section className="anim-fade-up" style={{ ['--d' as string]: '0.4s' }}>
                <h3 className="mb-1 text-sm font-semibold text-slate-800">Ask Kashvi</h3>
                <p className="text-sm text-slate-500">
                  Type anything below — products, ingredients, routines or your skin concerns.
                </p>
              </section>
            </div>
          ) : (
            <div className="space-y-4">
              {messages.map((m) => (
                <div
                  key={m.id}
                  data-msg-id={m.id}
                  className={`anim-fade-up flex items-end gap-2 ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  {m.role === 'assistant' && <KashviAvatar />}
                  <div
                    className={`max-w-[85%] rounded-2xl px-5 py-3.5 text-[1.075rem] leading-relaxed ${
                      m.role === 'user'
                        ? 'rounded-br-md bg-emerald-600 text-white'
                        : 'rounded-bl-md border border-emerald-100 bg-slate-50 text-slate-800'
                    }`}
                  >
                    {extras[m.id]?.trace.length ? (
                      <div className="mb-2 flex flex-wrap gap-1">
                        {extras[m.id].trace.map((t, i) => (
                          <span key={i} className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs text-emerald-800">
                            ✓ {t.label}
                          </span>
                        ))}
                      </div>
                    ) : null}
                    {m.role === 'user' ? (
                      <p className="whitespace-pre-wrap">{m.content}</p>
                    ) : (
                      m.id === typingId ? (
                        <TypedReply text={stripDisclaimer(m.content)} onDone={typingDone} onProgress={followTyping} />
                      ) : (
                        <FormattedText text={stripDisclaimer(m.content)} />
                      )
                    )}
                    {extras[m.id]?.actions.map((a, i) => (
                      <div key={i} className="mt-2 rounded-xl border border-emerald-200 bg-white p-2.5">
                        <p className="text-xs font-medium text-slate-700">Proposed: {a.action.summary}</p>
                        {a.state === 'pending' && (
                          <div className="mt-1.5 flex gap-2">
                            <button
                              onClick={() => handleConfirm(m.id, i, a.action.token)}
                              className="rounded-full bg-emerald-600 px-3 py-1 text-xs font-medium text-white hover:bg-emerald-700"
                            >
                              Confirm
                            </button>
                            <button
                              onClick={() => setActionState(m.id, i, { state: 'cancelled' })}
                              className="rounded-full border border-slate-300 px-3 py-1 text-xs text-slate-600 hover:bg-slate-100"
                            >
                              Cancel
                            </button>
                          </div>
                        )}
                        {a.state === 'done' && <p className="mt-1 text-xs text-emerald-700">{a.result}</p>}
                        {a.state === 'cancelled' && (
                          <p className="mt-1 text-xs text-slate-400">Cancelled - nothing was saved.</p>
                        )}
                      </div>
                    ))}
                    {m.role === 'assistant' && m.is_mock_response && (
                      <p className="mt-1 text-xs italic text-slate-400">
                        Rule-based response — no AI model answered this one.
                      </p>
                    )}
                  </div>
                </div>
              ))}

              {sending && (
                <div className="anim-fade-in flex items-end gap-2">
                  <KashviAvatar />
                  <div className="flex items-center gap-1 rounded-2xl rounded-bl-md border border-emerald-100 bg-slate-50 px-4 py-3">
                    <span className="typing-dot h-2 w-2 rounded-full bg-emerald-500" />
                    <span className="typing-dot h-2 w-2 rounded-full bg-emerald-500" />
                    <span className="typing-dot h-2 w-2 rounded-full bg-emerald-500" />
                    <span className="sr-only">Kashvi is typing</span>
                  </div>
                </div>
              )}

              {related.length > 0 && (
                <div className="anim-fade-up pl-10" style={{ ['--d' as string]: '0.15s' }}>
                  <p className="mb-1.5 text-sm font-medium text-slate-400">You might also ask</p>
                  <div className="flex flex-wrap gap-2">
                    {related.map((q) => (
                      <QuestionChip key={q} text={q} onClick={() => ask(q)} small />
                    ))}
                    <button
                      type="button"
                      onClick={backToMenu}
                      className="rounded-full border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-500 hover:bg-slate-50"
                    >
                      ← Main menu
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {error && (
          <p className="mx-4 mb-2 rounded-xl bg-rose-50 px-3 py-2 text-sm text-rose-700" role="alert">
            {error}
          </p>
        )}

        {voiceNote && (
          <p className="mx-4 mb-2 rounded-xl bg-amber-50 px-3 py-2 text-sm text-amber-800" role="status">
            {voiceNote}
          </p>
        )}

        <form onSubmit={handleSubmit} className="shrink-0 border-t border-emerald-100 p-3 sm:p-4">
          <div
            className={`flex items-center gap-2 rounded-full border bg-white py-1.5 pl-5 pr-1.5 focus-within:border-emerald-500 focus-within:ring-2 focus-within:ring-emerald-100 ${
              listening ? 'border-rose-300 ring-2 ring-rose-100' : 'border-slate-300'
            }`}
          >
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={listening ? 'Listening… say a question, or "open products"' : 'Ask Kashvi anything...'}
              aria-label="Ask Kashvi anything"
              className="min-w-0 flex-1 bg-transparent py-1.5 text-base focus:outline-none"
            />
            <button
              type="button"
              onClick={toggleVoice}
              disabled={!voiceSupported || sending}
              aria-pressed={listening}
              aria-label={listening ? 'Stop listening' : 'Speak to Kashvi'}
              title={
                voiceSupported
                  ? listening
                    ? 'Stop listening'
                    : 'Speak a question, or a command like “open products”'
                  : 'Voice input isn’t supported in this browser — try Chrome or Edge'
              }
              className={`relative flex h-9 w-9 shrink-0 items-center justify-center rounded-full transition disabled:opacity-40 ${
                listening ? 'bg-rose-500 text-white' : 'text-slate-500 hover:bg-emerald-50 hover:text-emerald-700'
              }`}
            >
              {listening && <span className="absolute inset-0 animate-ping rounded-full bg-rose-400 opacity-40" />}
              <svg viewBox="0 0 24 24" className="relative h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="9" y="3" width="6" height="11" rx="3" />
                <path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
              </svg>
            </button>
            <button
              type="submit"
              disabled={sending || !input.trim()}
              aria-label="Send"
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-emerald-600 text-white transition hover:bg-emerald-700 disabled:opacity-40"
            >
              <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="m22 2-7 20-4-9-9-4 20-7ZM22 2 11 13" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          </div>
          <p className="mt-2 text-center text-[11px] text-slate-400">{MEDICAL_DISCLAIMER}</p>
        </form>
      </div>
    </div>
  )
}

function QuestionChip({ text, onClick, small }: { text: string; onClick: () => void; small?: boolean }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full border border-emerald-100 bg-emerald-50 font-medium text-emerald-800 transition hover:-translate-y-0.5 hover:border-emerald-300 hover:bg-emerald-100 ${
        small ? 'px-3.5 py-1.5 text-sm' : 'px-4 py-2 text-sm'
      }`}
    >
      {text}
    </button>
  )
}

function KashviAvatar() {
  return (
    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-emerald-600 text-sm font-semibold text-white">
      K
    </span>
  )
}
