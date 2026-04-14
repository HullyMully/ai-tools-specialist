import { useEffect, useMemo, useState } from 'react'
import { createClient } from '@supabase/supabase-js'
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import './App.css'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || import.meta.env.SUPABASE_URL
const supabaseKey = import.meta.env.VITE_SUPABASE_KEY || import.meta.env.SUPABASE_KEY

const supabase =
  supabaseUrl && supabaseKey ? createClient(supabaseUrl, supabaseKey) : null

function App() {
  const [orders, setOrders] = useState([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')

  async function loadOrders(isRefresh = false) {
    if (!supabase) {
      setError(
        'Не заданы SUPABASE URL/KEY. Добавьте VITE_SUPABASE_URL и VITE_SUPABASE_KEY в .env.',
      )
      setLoading(false)
      setRefreshing(false)
      return
    }

    if (isRefresh) {
      setRefreshing(true)
    } else {
      setLoading(true)
    }
    setError('')

    const { data, error: fetchError } = await supabase.from('orders').select('*')

    if (fetchError) {
      setError(fetchError.message)
    } else {
      setOrders(data ?? [])
    }

    setLoading(false)
    if (isRefresh) {
      setRefreshing(false)
    }
  }

  useEffect(() => {
    loadOrders()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const totalRevenue = useMemo(
    () =>
      orders.reduce((sum, order) => {
        const value = Number(order.total_sum ?? order.total_summ ?? 0)
        return sum + (Number.isFinite(value) ? value : 0)
      }, 0),
    [orders],
  )

  const ordersCount = orders.length
  const averageCheck = ordersCount > 0 ? totalRevenue / ordersCount : 0

  const statusChartData = useMemo(() => {
    const grouped = orders.reduce((acc, order) => {
      const status = order.status || 'unknown'
      acc[status] = (acc[status] ?? 0) + 1
      return acc
    }, {})

    return Object.entries(grouped).map(([status, count]) => ({
      status,
      count,
    }))
  }, [orders])

  const tableRows = useMemo(
    () =>
      orders.map((order) => {
        const firstName = (order.first_name || order.firstName || '').trim()
        const lastName = (order.last_name || order.lastName || '').trim()
        const customerName =
          order.customer_name ||
          `${firstName} ${lastName}`.trim() ||
          'Неизвестный покупатель'
        return {
          id: order.id || order.external_id || '-',
          customerName,
          total: Number(order.total_sum ?? order.total_summ ?? 0),
        }
      }),
    [orders],
  )

  const formatMoney = (amount) =>
    new Intl.NumberFormat('ru-RU', {
      style: 'currency',
      currency: 'KZT',
      maximumFractionDigits: 0,
    }).format(amount)

  return (
    <main className="dashboard">
      <div className="dashboard-header">
        <h1>Дашборд заказов</h1>
        <button
          type="button"
          className="refresh-btn"
          onClick={() => loadOrders(true)}
          disabled={loading || refreshing}
        >
          {refreshing ? 'Обновление...' : 'Обновить'}
        </button>
      </div>

      {loading && <p className="state">Загрузка данных...</p>}
      {error && !loading && <p className="state error">{error}</p>}

      {!loading && !error && (
        <>
          <section className="kpi-grid">
            <article className="kpi-card">
              <h2>Всего выручки</h2>
              <p>{formatMoney(totalRevenue)}</p>
            </article>
            <article className="kpi-card">
              <h2>Количество заказов</h2>
              <p>{ordersCount}</p>
            </article>
            <article className="kpi-card">
              <h2>Средний чек</h2>
              <p>{formatMoney(averageCheck)}</p>
            </article>
          </section>

          <section className="chart-card">
            <h2>Распределение заказов по статусам</h2>
            <div className="chart-wrap">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={statusChartData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="status" />
                  <YAxis allowDecimals={false} />
                  <Tooltip />
                  <Bar dataKey="count" fill="#6c63ff" radius={[8, 8, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </section>

          <section className="table-card">
            <h2>Список заказов</h2>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Имя клиента</th>
                    <th>Сумма</th>
                  </tr>
                </thead>
                <tbody>
                  {tableRows.map((row) => (
                    <tr key={String(row.id)}>
                      <td>{row.id}</td>
                      <td>{row.customerName}</td>
                      <td>{formatMoney(row.total)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </main>
  )
}

export default App
