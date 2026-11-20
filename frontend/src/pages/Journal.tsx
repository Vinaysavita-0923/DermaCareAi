import { useEffect, useState, type FormEvent } from 'react'
import {
  ALLOWED_FEELING_TAGS,
  createJournalEntry,
  deleteJournalEntry,
  listJournalEntries,
  updateJournalEntry,
  type JournalEntry,
} from '../services/journal'
import { extractErrorMessage } from '../services/auth'
import PageHeader from '../components/PageHeader'
import PhotoCapture from '../components/PhotoCapture'
import { getJournalPhoto, removeJournalPhoto, setJournalPhoto } from '../services/journalPhotos'

function todayIso(): string {
  return new Date().toISOString().slice(0, 10)
}

export default function Journal() {
  const [entries, setEntries] = useState<JournalEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // New-entry form state
  const [entryDate, setEntryDate] = useState(todayIso())
  const [notes, setNotes] = useState('')
  const [tags, setTags] = useState<string[]>([])
  const [photo, setPhoto] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  // Inline edit state
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editNotes, setEditNotes] = useState('')
  const [editTags, setEditTags] = useState<string[]>([])

  function reload() {
    setLoading(true)
    listJournalEntries()
      .then(setEntries)
      .catch((err) => setError(extractErrorMessage(err)))
      .finally(() => setLoading(false))
  }

  useEffect(reload, [])

  function toggleTag(tag: string, list: string[], setList: (t: string[]) => void) {
    setList(list.includes(tag) ? list.filter((t) => t !== tag) : [...list, tag])
  }

  async function handleCreate(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      const created = await createJournalEntry({
        entry_date: entryDate,
        notes: notes || undefined,
        skin_feeling_tags: tags,
      })
      if (photo && created?.id) {
        const saved = setJournalPhoto(created.id, photo)
        if (!saved) setError('Entry saved, but the photo was too large to store in this browser.')
      }
      setNotes('')
      setTags([])
      setPhoto(null)
      setEntryDate(todayIso())
      reload()
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  function startEdit(entry: JournalEntry) {
    setEditingId(entry.id)
    setEditNotes(entry.notes ?? '')
    setEditTags(entry.skin_feeling_tags ?? [])
  }

  async function saveEdit(id: number) {
    setError(null)
    try {
      await updateJournalEntry(id, { notes: editNotes || undefined, skin_feeling_tags: editTags })
      setEditingId(null)
      reload()
    } catch (err) {
      setError(extractErrorMessage(err))
    }
  }

  async function handleDelete(id: number) {
    setError(null)
    try {
      await deleteJournalEntry(id)
      removeJournalPhoto(id)
      reload()
    } catch (err) {
      setError(extractErrorMessage(err))
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <PageHeader
        title="Photos and notes, dated"
        intro="One entry per day. Your own observations — not a clinical record."
      />

      <form onSubmit={handleCreate} className="space-y-4 rounded-xl border border-slate-200 bg-white p-5">
        <div className="flex items-end gap-3">
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">Date</label>
            <input
              type="date"
              value={entryDate}
              max={todayIso()}
              onChange={(e) => setEntryDate(e.target.value)}
              className="rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-emerald-500 focus:outline-none"
            />
          </div>
        </div>
        <div>
          <label className="mb-2 block text-sm font-medium text-slate-700">How did your skin feel?</label>
          <div className="flex flex-wrap gap-2">
            {ALLOWED_FEELING_TAGS.map((tag) => (
              <button
                key={tag}
                type="button"
                onClick={() => toggleTag(tag, tags, setTags)}
                className={`rounded-full border px-3 py-1.5 text-sm capitalize ${
                  tags.includes(tag)
                    ? 'border-emerald-600 bg-emerald-50 text-emerald-700'
                    : 'border-slate-300 text-slate-600 hover:bg-slate-50'
                }`}
              >
                {tag}
              </button>
            ))}
          </div>
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">Notes (optional)</label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={2}
            maxLength={2000}
            className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-emerald-500 focus:outline-none"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">Photo (optional)</label>
          <PhotoCapture value={photo} onChange={setPhoto} />
          <p className="mt-1.5 text-xs text-slate-400">
            Saved on this device only — never uploaded. Location and camera metadata are removed.
          </p>
        </div>
        {error && (
          <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700" role="alert">
            {error}
          </p>
        )}
        <button
          type="submit"
          disabled={submitting}
          className="rounded-md bg-emerald-600 px-5 py-2.5 font-medium text-white hover:bg-emerald-700 disabled:opacity-60"
        >
          {submitting ? 'Saving…' : 'Add entry'}
        </button>
      </form>

      <div className="space-y-3">
        {loading ? (
          <p className="py-6 text-center text-slate-400">Loading entries…</p>
        ) : entries.length === 0 ? (
          <p className="py-6 text-center text-slate-400">No journal entries yet.</p>
        ) : (
          entries.map((entry) => (
            <div key={entry.id} className="rounded-xl border border-slate-200 bg-white p-4">
              <div className="flex items-start justify-between">
                <span className="font-medium text-slate-900">{entry.entry_date}</span>
                {editingId !== entry.id && (
                  <div className="flex gap-2 text-sm">
                    <button onClick={() => startEdit(entry)} className="text-emerald-600 hover:underline">
                      Edit
                    </button>
                    <button onClick={() => handleDelete(entry.id)} className="text-rose-600 hover:underline">
                      Delete
                    </button>
                  </div>
                )}
              </div>

              {editingId === entry.id ? (
                <div className="mt-2 space-y-3">
                  <div className="flex flex-wrap gap-2">
                    {ALLOWED_FEELING_TAGS.map((tag) => (
                      <button
                        key={tag}
                        type="button"
                        onClick={() => toggleTag(tag, editTags, setEditTags)}
                        className={`rounded-full border px-3 py-1 text-xs capitalize ${
                          editTags.includes(tag)
                            ? 'border-emerald-600 bg-emerald-50 text-emerald-700'
                            : 'border-slate-300 text-slate-600'
                        }`}
                      >
                        {tag}
                      </button>
                    ))}
                  </div>
                  <textarea
                    value={editNotes}
                    onChange={(e) => setEditNotes(e.target.value)}
                    rows={2}
                    className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                  />
                  <div className="flex gap-2">
                    <button
                      onClick={() => saveEdit(entry.id)}
                      className="rounded-md bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white"
                    >
                      Save
                    </button>
                    <button
                      onClick={() => setEditingId(null)}
                      className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-600"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <>
                  {entry.skin_feeling_tags && entry.skin_feeling_tags.length > 0 && (
                    <p className="mt-1 text-sm capitalize text-slate-500">
                      {entry.skin_feeling_tags.join(', ')}
                    </p>
                  )}
                  {entry.notes && <p className="mt-1 text-sm text-slate-700">{entry.notes}</p>}
                  {getJournalPhoto(entry.id) && (
                    <img
                      src={getJournalPhoto(entry.id) as string}
                      alt={`Journal photo from ${entry.entry_date}`}
                      className="mt-3 max-h-64 w-full rounded-lg object-contain"
                    />
                  )}
                </>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  )
}
