import { ReactNode } from "react";

const palette = ["#b8ff5a", "#ffad2f", "#f5f7f4", "#73d8ff"];

export function ChartCard({ title, eyebrow, children, className = "" }: { title: string; eyebrow?: string; children: ReactNode; className?: string }) {
  return <section className={`chart-card ${className}`}>
    <div className="chart-card-heading"><div><p className="chart-eyebrow">{eyebrow || "Live overview"}</p><h3>{title}</h3></div><span className="chart-menu">•••</span></div>
    {children}
  </section>;
}

export function TrendChart({ values, color = palette[0] }: { values: number[]; color?: string }) {
  const max = Math.max(...values, 1);
  const points = values.map((value, index) => `${(index / (values.length - 1)) * 100},${38 - (value / max) * 30}`).join(" ");
  return <div className="trend-chart"><svg viewBox="0 0 100 42" preserveAspectRatio="none" aria-label="Trend chart" role="img">
    <defs><linearGradient id="trend-fill" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor={color} stopOpacity=".28"/><stop offset="1" stopColor={color} stopOpacity="0"/></linearGradient></defs>
    <polygon points={`0,42 ${points} 100,42`} fill="url(#trend-fill)" />
    <polyline points={points} fill="none" stroke={color} strokeWidth="1.8" vectorEffect="non-scaling-stroke" />
  </svg><div className="chart-axis"><span>Mon</span><span>Wed</span><span>Fri</span><span>Today</span></div></div>;
}

export function BarChart({ values, labels = ["Files", "Rules", "Passed", "Review"] }: { values: number[]; labels?: string[] }) {
  const max = Math.max(...values, 1);
  return <div className="bar-chart" role="img" aria-label="Bar chart">{values.map((value, index) => <div className="bar-column" key={`${labels[index]}-${index}`}><span className="bar-value">{value}</span><div className="bar-track"><i style={{ height: `${Math.max(10, value / max * 100)}%`, background: palette[index % palette.length] }} /></div><span className="bar-label">{labels[index]}</span></div>)}</div>;
}

export function DonutChart({ value, label }: { value: number; label: string }) {
  const radius = 42;
  const circumference = 2 * Math.PI * radius;
  return <div className="donut-chart"><svg viewBox="0 0 100 100" aria-label={`${value}% ${label}`} role="img"><circle cx="50" cy="50" r={radius} className="donut-track"/><circle cx="50" cy="50" r={radius} className="donut-value" strokeDasharray={`${circumference} ${circumference}`} strokeDashoffset={circumference - value / 100 * circumference}/></svg><div><strong>{value}%</strong><span>{label}</span></div></div>;
}

