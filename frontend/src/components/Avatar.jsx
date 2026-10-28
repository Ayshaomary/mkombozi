import { useState } from 'react'
import { avatarUrl } from '../lib/photo'

// A round profile photo, or the person's initials when they have none
export default function Avatar({ user, size = 40, className = '' }) {
  const [brokenKey, setBrokenKey] = useState(null)
  const initials =
    [user.first_name, user.last_name]
      .filter(Boolean)
      .map((name) => name[0])
      .join('')
      .slice(0, 2)
      .toUpperCase() || '?'
  const style = { width: size, height: size }

  if (user.avatar_key && user.avatar_key !== brokenKey) {
    return (
      <img
        src={avatarUrl(user.avatar_key)}
        alt=""
        style={style}
        className={`shrink-0 rounded-full bg-soft object-cover ${className}`}
        onError={() => setBrokenKey(user.avatar_key)}
      />
    )
  }
  return (
    <span
      style={{ ...style, fontSize: size * 0.38 }}
      className={`inline-flex shrink-0 items-center justify-center rounded-full bg-brand-soft font-semibold text-brand-ink ${className}`}
      aria-hidden="true"
    >
      {initials}
    </span>
  )
}
