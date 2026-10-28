import { useLanguage } from '../i18n/LanguageContext'
import { PERMISSION_PRESETS, PERMISSIONS } from '../lib/constants'
import { presetOf } from '../lib/permissions'

// The owner chooses what a staff member may do: a quick choice, or box by box
export default function PermissionPicker({ value, onChange }) {
  const { t } = useLanguage()
  const preset = presetOf(value)
  const toggle = (permission) =>
    onChange(
      value.includes(permission)
        ? value.filter((p) => p !== permission)
        : PERMISSIONS.filter((p) => p === permission || value.includes(p)),
    )

  return (
    <div className="space-y-3">
      <div>
        <p className="mb-1 text-sm font-medium text-ink-2">{t('access.presets')}</p>
        <div className="flex flex-wrap gap-2">
          {Object.keys(PERMISSION_PRESETS).map((key) => (
            <button
              key={key}
              type="button"
              aria-pressed={preset === key}
              onClick={() => onChange(PERMISSION_PRESETS[key])}
              className={`rounded-full border px-3 py-1.5 text-sm font-medium ${
                preset === key ? 'border-brand bg-brand-soft text-brand-ink' : 'border-line-strong text-ink-2 hover:bg-soft'
              }`}
            >
              {t(`access.preset.${key}`)}
            </button>
          ))}
        </div>
      </div>
      <div className="space-y-2">
        {PERMISSIONS.map((permission) => (
          <label key={permission} className="flex cursor-pointer items-start gap-3 rounded-lg border border-line p-2.5">
            <input
              type="checkbox"
              className="mt-0.5 size-4 accent-brand"
              checked={value.includes(permission)}
              onChange={() => toggle(permission)}
            />
            <span>
              <span className="block text-sm font-medium text-ink">{t(`access.perm.${permission}`)}</span>
              <span className="block text-xs text-muted">{t(`access.hint.${permission}`)}</span>
            </span>
          </label>
        ))}
      </div>
      <p className="text-xs text-muted">{t('access.ownerOnlyNote')}</p>
    </div>
  )
}
