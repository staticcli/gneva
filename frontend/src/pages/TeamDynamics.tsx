import { useState, useEffect } from 'react'
import { api } from '../api'

interface Speaker {
  speaker: string;
  total_segments: number;
  total_words: number;
  meetings_participated: number;
  avg_words_per_segment: number;
}

export default function TeamDynamics() {
  const [speakers, setSpeakers] = useState<Speaker[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    api.speakerDynamics()
      .then(r => setSpeakers(r.speakers || []))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const maxWords = speakers.length > 0 ? Math.max(...speakers.map(s => s.total_words)) : 1;

  if (loading) return <div className="flex items-center justify-center h-64 text-gray-400">Loading...</div>;
  if (error) return <div className="text-red-500 p-4">Error: {error}</div>;

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Team Dynamics</h2>

      {speakers.length === 0 ? (
        <div className="text-center py-20 text-gray-400">
          <p className="text-lg">No speaker data yet</p>
          <p className="text-sm mt-1">Speaker stats will appear after meetings are processed</p>
        </div>
      ) : (
        <>
          {/* Bar chart */}
          <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-100 mb-8">
            <h3 className="text-lg font-semibold mb-4">Total Words by Speaker</h3>
            <div className="space-y-3">
              {speakers.map(s => (
                <div key={s.speaker} className="flex items-center gap-3">
                  <span className="w-32 text-sm font-medium text-gray-700 truncate">{s.speaker}</span>
                  <div className="flex-1 bg-gray-100 rounded-full h-6 overflow-hidden">
                    <div
                      className="bg-gneva-600 h-full rounded-full transition-all"
                      style={{ width: `${(s.total_words / maxWords) * 100}%` }}
                    />
                  </div>
                  <span className="text-sm text-gray-500 w-20 text-right">{s.total_words.toLocaleString()}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Stats table */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Speaker</th>
                  <th className="text-right px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Segments</th>
                  <th className="text-right px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Words</th>
                  <th className="text-right px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Meetings</th>
                  <th className="text-right px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Avg Words/Seg</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {speakers.map(s => (
                  <tr key={s.speaker} className="hover:bg-gray-50">
                    <td className="px-6 py-4 text-sm font-medium text-gray-900">{s.speaker}</td>
                    <td className="px-6 py-4 text-sm text-gray-600 text-right">{s.total_segments}</td>
                    <td className="px-6 py-4 text-sm text-gray-600 text-right">{s.total_words.toLocaleString()}</td>
                    <td className="px-6 py-4 text-sm text-gray-600 text-right">{s.meetings_participated}</td>
                    <td className="px-6 py-4 text-sm text-gray-600 text-right">{s.avg_words_per_segment}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
