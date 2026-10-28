import { useState } from 'react'

// A small form that saves itself and shows "Saved" afterwards.
// If saveFn returns an object, the form is reset to it (e.g. to clear password fields).
export function useSaveForm(initial, saveFn) {
  const [form, setForm] = useState(initial)
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  const field = (name) => ({
    value: form[name] ?? '',
    onChange: (e) => {
      setForm({ ...form, [name]: e.target.value })
      setSaved(false)
    },
    error: error?.fields?.[name],
  })

  const submit = async (event) => {
    event.preventDefault()
    setSaving(true)
    setError(null)
    try {
      const nextForm = await saveFn(form)
      if (nextForm) setForm(nextForm)
      setSaved(true)
    } catch (err) {
      setError(err)
    } finally {
      setSaving(false)
    }
  }

  return { field, submit, error, saving, saved }
}
