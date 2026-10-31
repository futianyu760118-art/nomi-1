import { BarChart, Bar, Cell, ResponsiveContainer, XAxis, YAxis, Tooltip } from 'recharts'
import type { Week } from '../types'

export function WeekChart({ weeks, current }: { weeks: Week[]; current: number }) {
  return <div className="week-chart" aria-label="各周完成度柱状图">
    <ResponsiveContainer width="100%" height="100%" minWidth={0}>
      <BarChart data={weeks} margin={{ left: -15, right: 12, top: 8, bottom: 0 }}>
        <XAxis dataKey="week" tickFormatter={value => `W${value}`} axisLine={false} tickLine={false} tick={{ fill: 'var(--muted)', fontSize: 10 }} />
        <YAxis domain={[0, 100]} ticks={[0, 50, 100]} axisLine={false} tickLine={false} tick={{ fill: 'var(--muted)', fontSize: 10 }} />
        <Tooltip labelFormatter={value => `Week ${value}`} formatter={value => [`${value}%`, '完成度']} contentStyle={{ background: 'var(--surface)', color: 'var(--text)', borderColor: 'var(--line)', borderRadius: 6, fontSize: 11 }} />
        <Bar dataKey="progress" maxBarSize={28} radius={[3, 3, 0, 0]} isAnimationActive={false}>
          {weeks.map(week => <Cell key={week.week} fill={week.week === current ? 'var(--green)' : '#92939b'} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  </div>
}
