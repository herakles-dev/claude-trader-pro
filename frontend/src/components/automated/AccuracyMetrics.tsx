import React from 'react';
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { TrendingUp, TrendingDown, Download } from '@mui/icons-material';

interface AccuracyMetricsProps {
  metrics: {
    last24h: { accuracy: number; total: number; correct: number; incorrect: number };
    last7d: { accuracy: number; total: number; correct: number; incorrect: number };
    last30d: { accuracy: number; total: number; correct: number; incorrect: number };
    trend: Array<{ date: string; accuracy: number }>;
    dailyPredictions: Array<{ date: string; count: number }>;
    performance: {
      avgLatency: number;
      avgCost: number;
      totalCost: number;
      avgConfidence: number;
    };
  };
  loading?: boolean;
}

const COLORS = {
  correct: '#10b981',
  incorrect: '#ef4444',
  primary: '#3b82f6',
};

const AccuracyMetrics: React.FC<AccuracyMetricsProps> = ({ metrics, loading = false }) => {
  // Calculate trend comparisons
  const calculate24hTrend = () => {
    const current = metrics.last24h.accuracy;
    const previous = metrics.last7d.accuracy - metrics.last24h.accuracy;
    return current - previous;
  };

  const calculate7dTrend = () => {
    const current = metrics.last7d.accuracy;
    const previous = metrics.last30d.accuracy - metrics.last7d.accuracy;
    return current - previous;
  };

  const calculate30dTrend = () => {
    if (metrics.trend.length < 2) return 0;
    const recentAvg = metrics.trend.slice(-7).reduce((sum, item) => sum + item.accuracy, 0) / 7;
    const previousAvg = metrics.trend.slice(-14, -7).reduce((sum, item) => sum + item.accuracy, 0) / 7;
    return recentAvg - previousAvg;
  };

  // Export CSV functionality
  const exportToCSV = () => {
    const csvData = [
      ['Metric', 'Value'],
      ['24h Accuracy', `${metrics.last24h.accuracy.toFixed(2)}%`],
      ['24h Total Predictions', metrics.last24h.total],
      ['24h Correct', metrics.last24h.correct],
      ['24h Incorrect', metrics.last24h.incorrect],
      ['7d Accuracy', `${metrics.last7d.accuracy.toFixed(2)}%`],
      ['7d Total Predictions', metrics.last7d.total],
      ['7d Correct', metrics.last7d.correct],
      ['7d Incorrect', metrics.last7d.incorrect],
      ['30d Accuracy', `${metrics.last30d.accuracy.toFixed(2)}%`],
      ['30d Total Predictions', metrics.last30d.total],
      ['30d Correct', metrics.last30d.correct],
      ['30d Incorrect', metrics.last30d.incorrect],
      ['Avg Latency (ms)', metrics.performance.avgLatency],
      ['Avg Cost per Prediction', `$${metrics.performance.avgCost.toFixed(4)}`],
      ['Total Cost This Month', `$${metrics.performance.totalCost.toFixed(2)}`],
      ['Avg Confidence', `${metrics.performance.avgConfidence.toFixed(2)}%`],
    ];

    const csvContent = csvData.map(row => row.join(',')).join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `accuracy-metrics-${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
  };

  // Prepare pie chart data
  const pieData = [
    { name: 'Correct', value: metrics.last30d.correct },
    { name: 'Incorrect', value: metrics.last30d.incorrect },
  ];

  // Trend indicator component
  const TrendIndicator: React.FC<{ value: number }> = ({ value }) => {
    const isPositive = value >= 0;
    return (
      <span className={`flex items-center text-sm ml-2 ${isPositive ? 'text-green-400' : 'text-red-400'}`}>
        {isPositive ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
        <span className="ml-1">{Math.abs(value).toFixed(2)}%</span>
      </span>
    );
  };

  // Accuracy card component
  const AccuracyCard: React.FC<{
    title: string;
    data: { accuracy: number; total: number; correct: number; incorrect: number };
    trend: number;
  }> = ({ title, data, trend }) => (
    <div className="bg-gray-800 border border-gray-700 rounded-lg p-6 hover:border-blue-500 transition-colors">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-gray-300 font-semibold">{title}</h3>
        <TrendIndicator value={trend} />
      </div>
      <div className="text-4xl font-bold text-white mb-4">{data.accuracy.toFixed(1)}%</div>
      <div className="grid grid-cols-3 gap-2 text-sm">
        <div className="text-center">
          <div className="text-gray-400">Total</div>
          <div className="text-white font-semibold">{data.total}</div>
        </div>
        <div className="text-center">
          <div className="text-gray-400">Correct</div>
          <div className="text-green-400 font-semibold">{data.correct}</div>
        </div>
        <div className="text-center">
          <div className="text-gray-400">Incorrect</div>
          <div className="text-red-400 font-semibold">{data.incorrect}</div>
        </div>
      </div>
    </div>
  );

  // Performance metric card
  const PerformanceCard: React.FC<{ title: string; value: string; unit: string }> = ({ title, value, unit }) => (
    <div className="bg-gray-800 border border-gray-700 rounded-lg p-4">
      <div className="text-gray-400 text-sm mb-2">{title}</div>
      <div className="text-2xl font-bold text-white">
        {value}
        <span className="text-sm text-gray-400 ml-1">{unit}</span>
      </div>
    </div>
  );

  if (loading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="bg-gray-800 rounded-lg h-48" />
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-gray-800 rounded-lg h-80" />
          <div className="bg-gray-800 rounded-lg h-80" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header with Export Button */}
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-white">Accuracy Metrics Dashboard</h2>
        <button
          onClick={exportToCSV}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
        >
          <Download className="w-4 h-4" />
          Export CSV
        </button>
      </div>

      {/* Accuracy Cards - 3 Time Periods */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <AccuracyCard title="Last 24 Hours" data={metrics.last24h} trend={calculate24hTrend()} />
        <AccuracyCard title="Last 7 Days" data={metrics.last7d} trend={calculate7dTrend()} />
        <AccuracyCard title="Last 30 Days" data={metrics.last30d} trend={calculate30dTrend()} />
      </div>

      {/* Charts Row 1: Accuracy Trend & Daily Predictions */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Accuracy Trend Line Chart */}
        <div className="bg-gray-800 border border-gray-700 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-white mb-4">Accuracy Trend (30 Days)</h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={metrics.trend}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis
                dataKey="date"
                stroke="#9ca3af"
                tick={{ fill: '#9ca3af' }}
                tickFormatter={(value) => new Date(value).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
              />
              <YAxis stroke="#9ca3af" tick={{ fill: '#9ca3af' }} domain={[0, 100]} />
              <Tooltip
                contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151', borderRadius: '8px' }}
                labelStyle={{ color: '#f3f4f6' }}
                formatter={(value: number) => [`${value.toFixed(1)}%`, 'Accuracy']}
              />
              <Legend wrapperStyle={{ color: '#9ca3af' }} />
              <Line
                type="monotone"
                dataKey="accuracy"
                stroke={COLORS.primary}
                strokeWidth={2}
                dot={{ fill: COLORS.primary, r: 4 }}
                activeDot={{ r: 6 }}
                name="Accuracy %"
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Daily Predictions Bar Chart */}
        <div className="bg-gray-800 border border-gray-700 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-white mb-4">Predictions Per Day (7 Days)</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={metrics.dailyPredictions}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis
                dataKey="date"
                stroke="#9ca3af"
                tick={{ fill: '#9ca3af' }}
                tickFormatter={(value) => new Date(value).toLocaleDateString('en-US', { weekday: 'short' })}
              />
              <YAxis stroke="#9ca3af" tick={{ fill: '#9ca3af' }} />
              <Tooltip
                contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151', borderRadius: '8px' }}
                labelStyle={{ color: '#f3f4f6' }}
                formatter={(value: number) => [value, 'Predictions']}
              />
              <Legend wrapperStyle={{ color: '#9ca3af' }} />
              <Bar dataKey="count" fill={COLORS.primary} radius={[8, 8, 0, 0]} name="Predictions" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Charts Row 2: Pie Chart & Performance Metrics */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Correct vs Incorrect Pie Chart */}
        <div className="bg-gray-800 border border-gray-700 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-white mb-4">Correct vs Incorrect Distribution (30 Days)</h3>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={pieData}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(1)}%`}
                outerRadius={100}
                fill="#8884d8"
                dataKey="value"
              >
                {pieData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={index === 0 ? COLORS.correct : COLORS.incorrect} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151', borderRadius: '8px' }}
                formatter={(value: number) => [value, 'Count']}
              />
              <Legend wrapperStyle={{ color: '#9ca3af' }} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Performance Metrics Grid */}
        <div className="bg-gray-800 border border-gray-700 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-white mb-4">Performance Metrics</h3>
          <div className="grid grid-cols-2 gap-4">
            <PerformanceCard
              title="Avg API Latency"
              value={metrics.performance.avgLatency.toFixed(0)}
              unit="ms"
            />
            <PerformanceCard
              title="Avg Cost per Prediction"
              value={`$${metrics.performance.avgCost.toFixed(4)}`}
              unit=""
            />
            <PerformanceCard
              title="Total Cost This Month"
              value={`$${metrics.performance.totalCost.toFixed(2)}`}
              unit=""
            />
            <PerformanceCard
              title="Avg Confidence"
              value={metrics.performance.avgConfidence.toFixed(1)}
              unit="%"
            />
          </div>
        </div>
      </div>
    </div>
  );
};

export default AccuracyMetrics;
