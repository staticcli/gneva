import { useState, useEffect } from 'react'
import { api } from '../api'

interface MeetingScore {
  meeting_id: string;
  title: string | null;
  decisions_made: number;
  actions_assigned: number;
  key_topics: number;
  duration_min: number;
  participant_count: number;
  score: number;
  grade: string;
  created_at: string;
}

interface Overview {
  average_score: number;
  average_grade: string;
  meeting_count: number;
  meetings: MeetingScore[];
}

const gradeColors: Record<string, string> = {
  A: 'bg-green-100 text-green-700',
  B: 'bg-blue-100 text-blue-700',
  C: 'bg-yellow-100 text-yellow-700',
  D: 'bg-orange-100 text-orange-700',
  F: 'bg-red-100 text-red-700',
};

export default function MeetingROI() {
  const [data, setData] = useState<Overview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    api.roiOverview()
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="flex items-center justify-center h-64 text-gray-400">Loading...</div>;
  if (error) return <div className="text-red-500 p-4">Error: {error}</div>;
  if (!data) return null;

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Meeting ROI</h2>

      {/* Overview cards */}
      <div className="grid grid-cols-3 gap-4 mb-8">
        <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-100 text-center">
          <p className="text-sm text-gray-500 mb-1">Average Score</p>
          <p className="text-3xl font-bold text-gneva-700">{data.average_score}</p>
        </div>
        <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-100 text-center">
          <p className="text-sm text-gray-500 mb-1">Average Grade</p>
          <span className={`inline-block text-3xl font-bold px-4 py-1 rounded-lg ${gradeColors[data.average_grade] || 'bg-gray-100'}`}>
            {data.average_grade}
          </span>
        </div>
        <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-100 text-center">
          <p className="text-sm text-gray-500 mb-1">Meetings Analyzed</p>
          <p className="text-3xl font-bold text-gray-700">{data.meeting_count}</p>
        </div>
      </div>

      {/* Meeting list */}
      {data.meetings.length === 0 ? (
        <div className="text-center py-20 text-gray-400">
          <p className="text-lg">No meetings to score</p>
        </div>
      ) : (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Meeting</th>
                <th className="text-right px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Decisions</th>
                <th className="text-right px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                <th className="text-right px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Topics</th>
                <th className="text-right px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Duration</th>
                <th className="text-right px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Score</th>
                <th className="text-center px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Grade</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {data.meetings.map(m => (
                <tr key={m.meeting_id} className="hover:bg-gray-50">
                  <td className="px-6 py-4">
                    <p className="text-sm font-medium text-gray-900">{m.title || 'Untitled'}</p>
                    <p className="text-xs text-gray-400">
                      {new Date(m.created_at).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}
                    </p>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-600 text-right">{m.decisions_made}</td>
                  <td className="px-6 py-4 text-sm text-gray-600 text-right">{m.actions_assigned}</td>
                  <td className="px-6 py-4 text-sm text-gray-600 text-right">{m.key_topics}</td>
                  <td className="px-6 py-4 text-sm text-gray-600 text-right">{m.duration_min}m</td>
                  <td className="px-6 py-4 text-sm font-semibold text-gray-900 text-right">{m.score}</td>
                  <td className="px-6 py-4 text-center">
                    <span className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-bold ${gradeColors[m.grade] || 'bg-gray-100'}`}>
                      {m.grade}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
