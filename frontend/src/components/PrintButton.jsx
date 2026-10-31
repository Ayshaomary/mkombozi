import { useEffect, useEffectEvent, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
import { formatDateTime } from '../lib/format'
import Letterhead from './Letterhead'
import { Button } from './ui'

// Don't hold up printing for a logo that is slow to arrive
const IMAGE_WAIT_MS = 3000

// Resolves once every picture in `element` has loaded (or failed), so it is on the paper
function imagesLoaded(element) {
  const pending = [...(element?.querySelectorAll('img') ?? [])].filter((img) => !img.complete)
  const loaded = Promise.all(
    pending.map(
      (img) =>
        new Promise((resolve) => {
          img.addEventListener('load', resolve, { once: true })
          img.addEventListener('error', resolve, { once: true })
        }),
    ),
  )
  return Promise.race([loaded, new Promise((resolve) => setTimeout(resolve, IMAGE_WAIT_MS))])
}

// Prints `children` on clean paper, then calls onDone. The app is hidden while printing,
// so the sheet starts at the top of the page whatever is open on the screen.
export function PrintSheet({ className = '', onDone, children }) {
  const sheetRef = useRef(null)
  const finished = useEffectEvent(() => onDone())

  // Once the sheet and the logo are on the page, open the browser's print window (also "Save as PDF")
  useEffect(() => {
    let cancelled = false
    const done = () => finished()
    document.body.classList.add('printing')
    window.addEventListener('afterprint', done, { once: true })
    imagesLoaded(sheetRef.current).then(() => {
      if (!cancelled) window.print()
    })
    return () => {
      cancelled = true
      window.removeEventListener('afterprint', done)
      document.body.classList.remove('printing')
    }
  }, [])

  return createPortal(
    <div ref={sheetRef} className={`print-sheet ${className}`}>
      {children}
    </div>,
    document.body,
  )
}

// Prints a list as a clean table: the shop's letterhead, the list's title, every row and the totals.
//   load():  a promise of { rows, total }, e.g. fetchAll('/sales/', params) from lib/useApi.js
//   columns: [{ label, value: (row) => text, align: 'right' }]
//   footer:  (rows, total) => [[label, value], ...]  (optional)
export default function PrintButton({ title, subtitle, load, columns, footer }) {
  const { t, lang } = useLanguage()
  const { user } = useAuth()
  const [sheet, setSheet] = useState(null)
  const [loading, setLoading] = useState(false)

  const print = async () => {
    setLoading(true)
    try {
      setSheet({ ...(await load()), printedAt: new Date() })
    } catch (err) {
      window.alert(err.status === 0 ? t('common.networkError') : err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <Button variant="secondary" icon="printer" loading={loading} onClick={print}>
        {t('print.button')}
      </Button>
      {sheet && (
        <PrintSheet onDone={() => setSheet(null)}>
          <header>
            <div className="mb-2 border-b border-black pb-2">
              <Letterhead business={user.business} />
            </div>
            <h2>{title}</h2>
            {subtitle && <p>{subtitle}</p>}
            <p>
              {t('print.printedOn', { date: formatDateTime(sheet.printedAt, lang) })} ·{' '}
              {t('print.rows', { count: sheet.rows.length })}
            </p>
          </header>
          <table>
            <thead>
              <tr>
                <th>#</th>
                {columns.map((column) => (
                  <th key={column.label} className={column.align === 'right' ? 'num' : ''}>
                    {column.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sheet.rows.map((row, index) => (
                <tr key={row.id ?? index}>
                  <td>{index + 1}</td>
                  {columns.map((column) => (
                    <td key={column.label} className={column.align === 'right' ? 'num' : ''}>
                      {column.value(row)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          {footer && (
            <footer>
              {footer(sheet.rows, sheet.total).map(([label, value]) => (
                <p key={label}>
                  <span>{label}</span>
                  <strong>{value}</strong>
                </p>
              ))}
            </footer>
          )}
        </PrintSheet>
      )}
    </>
  )
}
