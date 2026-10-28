import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
import { formatDateTime } from '../lib/format'
import { Button } from './ui'

// Prints a list as a clean table: the shop's name, the list's title, every row and the totals.
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

  // Once the table is on the page, open the browser's print window (also "Save as PDF")
  useEffect(() => {
    if (!sheet) return
    const done = () => setSheet(null)
    document.body.classList.add('printing-list')
    window.addEventListener('afterprint', done, { once: true })
    window.print()
    return () => {
      window.removeEventListener('afterprint', done)
      document.body.classList.remove('printing-list')
    }
  }, [sheet])

  return (
    <>
      <Button variant="secondary" icon="printer" loading={loading} onClick={print}>
        {t('print.button')}
      </Button>
      {sheet &&
        createPortal(
          <div className="print-area print-sheet">
            <header>
              <h1>{user.business?.name}</h1>
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
          </div>,
          document.body,
        )}
    </>
  )
}
