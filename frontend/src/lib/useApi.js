import { useCallback, useEffect, useState } from 'react'
import { api } from './api'

/**
 * Load data from the API when a component appears, and again when `params` change.
 *   const { data, loading, error, reload } = useApi('/products/', { search })
 * Pass `null` as the path to skip loading.
 */
export function useApi(path, params) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(Boolean(path))
  const [error, setError] = useState(null)
  const paramsKey = JSON.stringify(params ?? {})

  const load = useCallback(async () => {
    if (!path) return
    setLoading(true)
    setError(null)
    try {
      setData(await api.get(path, JSON.parse(paramsKey)))
    } catch (err) {
      setError(err)
    } finally {
      setLoading(false)
    }
  }, [path, paramsKey])

  useEffect(() => {
    load()
  }, [load])

  return { data, setData, loading, error, reload: load }
}

/**
 * Like useApi, for paginated lists: keeps the loaded pages and adds a loadMore() function.
 *   const { items, count, hasMore, loadMore } = usePaginated('/sales/', { period })
 */
export function usePaginated(path, params) {
  const [items, setItems] = useState([])
  const [count, setCount] = useState(0)
  // Some lists (sales, expenses) also send the total amount of all matching records
  const [total, setTotal] = useState(null)
  const [page, setPage] = useState(1)
  const [hasMore, setHasMore] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const paramsKey = JSON.stringify(params ?? {})

  const fetchPage = useCallback(
    async (pageNumber) => {
      setLoading(true)
      setError(null)
      try {
        const data = await api.get(path, { ...JSON.parse(paramsKey), page: pageNumber })
        setItems((previous) => (pageNumber === 1 ? data.results : [...previous, ...data.results]))
        setCount(data.count)
        setTotal(data.total ?? null)
        setHasMore(Boolean(data.next))
        setPage(pageNumber)
      } catch (err) {
        setError(err)
      } finally {
        setLoading(false)
      }
    },
    [path, paramsKey],
  )

  useEffect(() => {
    fetchPage(1)
  }, [fetchPage])

  return {
    items,
    setItems,
    count,
    total,
    hasMore,
    loading,
    error,
    loadMore: () => fetchPage(page + 1),
    reload: () => fetchPage(1),
  }
}
