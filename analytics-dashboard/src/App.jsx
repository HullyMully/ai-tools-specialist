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
  const [error, setError] = useState('')

  useEffect(() => {
    async function loadOrders() {
      if (!supabase) {
        setError(
          'Не заданы SUPABASE URL/KEY. Добавьте VITE_SUPABASE_URL и VITE_SUPABASE_KEY в .env.',
        )
        setLoading(false)
        return
      }

      const { data, error: fetchError } = await supabase
        .from('orders')
        .select('*')

      if (fetchError) {
        setError(fetchError.message)
        setLoading(false)
        return
      }

      setOrders(data ?? [])
      setLoading(false)
    }

    loadOrders()
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

  const formatMoney = (amount) =>
    new Intl.NumberFormat('ru-RU', {
      style: 'currency',
      currency: 'KZT',
      maximumFractionDigits: 0,
    }).format(amount)

  return (
    <main className="dashboard">
      <h1>Дашборд заказов</h1>

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
        </>
      )}
    </main>
  )
}

export default App
