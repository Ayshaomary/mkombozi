import { useState } from 'react'
import { avatarUrl } from '../lib/photo'

// The top of a printed list or receipt: the owner's photo, the business name, what it does and how to reach it
export default function Letterhead({ business, centered = false }) {
  const [brokenKey, setBrokenKey] = useState(null)
  if (!business) return null
  const key = business.owner_avatar_key
  const place = [business.address, business.location].filter(Boolean).join(', ')
  const contact = [business.phone, business.email].filter(Boolean).join(' · ')
  return (
    <div className={`flex items-center gap-3 ${centered ? 'flex-col text-center' : ''}`}>
      {key && key !== brokenKey && (
        <img
          src={avatarUrl(key)}
          alt=""
          className="h-16 w-16 shrink-0 rounded-full object-cover"
          onError={() => setBrokenKey(key)}
        />
      )}
      <div className="min-w-0">
        <h1 className="text-base font-bold text-ink">{business.name}</h1>
        {business.description && <p className="text-ink-2">{business.description}</p>}
        {place && <p className="text-muted">{place}</p>}
        {contact && <p className="text-muted">{contact}</p>}
      </div>
    </div>
  )
}
