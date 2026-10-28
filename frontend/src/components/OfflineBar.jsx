import { useState } from 'react'
import { useOffline } from '../context/OfflineContext'
import { useLanguage } from '../i18n/LanguageContext'
import { formatDateTime, formatMoney } from '../lib/format'
import Icon from './Icon'
import { Badge, Button, EmptyState, Modal } from './ui'

function OutboxModal({ onClose }) {
  const { t, lang } = useLanguage()
  const { items, online, syncing, sync, retry, discard } = useOffline()

  return (
    <Modal
      open
      onClose={onClose}
      title={t('offline.title')}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            {t('common.close')}
          </Button>
          <Button icon="repeat" loading={syncing} disabled={!online} onClick={sync}>
            {t('offline.sendNow')}
          </Button>
        </>
      }
    >
      <p className="mb-3 text-sm text-ink-2">{t('offline.explain')}</p>
      {items.length === 0 ? (
        <EmptyState icon="check" title={t('offline.empty')} />
      ) : (
        <ul className="divide-y divide-line">
          {items.map((item) => (
            <li key={item.id} className="py-3 text-sm">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="font-medium text-ink">
                    {t(`offline.${item.kind}`)} · {formatMoney(item.summary.amount)}
                  </p>
                  <p className="truncate text-xs text-muted">
                    {[item.summary.label, formatDateTime(item.created_at, lang)].filter(Boolean).join(' · ')}
                  </p>
                </div>
                <Badge tone={item.status === 'failed' ? 'bad' : 'warn'}>{t(item.status === 'failed' ? 'offline.failed' : 'offline.waitingStatus')}</Badge>
              </div>
              {item.status === 'failed' && (
                <div className="mt-2 rounded-lg bg-bad-soft p-2">
                  <p className="text-xs text-bad">{item.error}</p>
                  <div className="mt-2 flex gap-2">
                    <Button size="sm" variant="secondary" onClick={() => retry(item.id)}>
                      {t('common.tryAgain')}
                    </Button>
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => window.confirm(t('offline.confirmDiscard')) && discard(item.id)}
                    >
                      {t('common.delete')}
                    </Button>
                  </div>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </Modal>
  )
}

// Shows when the phone is offline, and how many sales and expenses are waiting to be sent
export default function OfflineBar() {
  const { t } = useLanguage()
  const { online, waitingCount, failedCount, syncing } = useOffline()
  const [open, setOpen] = useState(false)
  if (online && waitingCount === 0 && failedCount === 0) return null

  const failed = failedCount > 0
  const colors = failed ? 'bg-bad-soft text-bad' : online ? 'bg-warn-soft text-warn-ink' : 'bg-soft text-ink'
  const parts = []
  if (!online) parts.push(t('offline.offline'))
  if (waitingCount > 0) parts.push(syncing ? t('offline.sending') : t('offline.waiting', { count: waitingCount }))
  if (failed) parts.push(t('offline.failedCount', { count: failedCount }))

  return (
    <>
      <div className={`flex flex-wrap items-center justify-between gap-2 px-4 py-2.5 text-sm ${colors}`}>
        <span className="flex items-center gap-2">
          <Icon name={failed ? 'alert' : online ? 'repeat' : 'globe'} size={16} />
          {parts.join(' · ')}
        </span>
        {waitingCount + failedCount > 0 && (
          <button className="font-semibold underline" onClick={() => setOpen(true)}>
            {t('offline.view')}
          </button>
        )}
      </div>
      {open && <OutboxModal onClose={() => setOpen(false)} />}
    </>
  )
}
