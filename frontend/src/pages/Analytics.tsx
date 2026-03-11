import { useState, useEffect } from 'react'
import { BarChart3, Clock, CheckSquare, Lightbulb, X, TrendingUp, Users, MessageSquare } from 'lucide-react'
import { api } from '../api'

interface OverviewStats {
  total_meetings: number;
  total_hours: number;
  total_action_items: number;
  total_decisions: number;
  top_speakers: Speaker[];
  top_topics: Topic[];
}

interface MeetingTrend {
  week: string;
  meeting_count: number;
}

interface Speaker {
  speaker: string;
  total_talk_time_sec: number;
  meetings_attended: number;
}

interface Topic {
  topic: string;
  mention_count: number;
}

interface Pattern {
  id: string;
  type: string;
  title: string;
  description: string;
  severity: string;
}

interface SentimentPoint {
  week: string;
  avg_sentiment: number;
}

interface TrendsData {
  meeting_trends: MeetingTrend[];
  sentiment_trends: SentimentPoint[];
}

export default function Analytics() {
  const [overview, setOverview] = useState<OverviewStats | null>(null);
  const [trends, setTrends] = useState<TrendsData | null>(null);
  const [patterns, setPatterns] = useState<Pattern[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.analyticsOverview().catch(() => null),
      api.trends().catch(() => null),
      api.patterns().catch(() => []),
    ]).then(([overviewData, trendsData, patternsData]) => {
      setOverview(overviewData);
      setTrends(trendsData);
      const items = Array.isArray(patternsData) ? patternsData : patternsData?.patterns || [];
      setPatterns(items);
    }).finally(() => setLoading(false));
  }, []);

  const handleDismissPattern = async (id: string) => {
    try {
      await api.dismissPattern(id);
      setPatterns(prev => prev.filter(p => p.id !== id));
    } catch (err) {
      console.error(err);
    }
  };

  const formatHours = (hours: number) => {
    if (hours < 1) return `${Math.round(hours * 60)}m`;
    return `${hours.toFixed(1)}h`;
  };

  const formatTalkTime = (sec: number) => {
    const min = Math.floor(sec / 60);
    if (min < 60) return `${min}m`;
    const hours = Math.floor(min / 60);
    const rem = min % 60;
    return `${hours}h ${rem}m`;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-gray-400">
        Loading analytics...
      </div>
    );
  }

  const meetingTrends = trends?.meeting_trends || [];
  const maxFreq = Math.max(...meetingTrends.map(d => d.meeting_count), 1);
  const speakers = overview?.top_speakers || [];
  const maxTalkTime = Math.max(...speakers.map(s => s.total_talk_time_sec), 1);
  const topics = overview?.top_topics || [];
  const maxTopicCount = Math.max(...topics.map(t => t.mention_count), 1);
  const sentiment = trends?.sentiment_trends || [];

  const sentimentColor = (score: number) => {
    if (score >= 0.6) return 'bg-green-500';
    if (score >= 0.3) return 'bg-yellow-500';
    if (score >= 0) return 'bg-orange-500';
    return 'bg-red-500';
  };

  const patternTypeColors: Record<string, string> = {
    recurring_topic: 'border-l-blue-500',
    sentiment_trend: 'border-l-amber-500',
    action_overdue: 'border-l-red-500',
    engagement_drop: 'border-l-purple-500',
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <h2 className="text-2xl font-bold">Analytics</h2>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-gneva-100 rounded-lg">
              <BarChart3 size={20} className="text-gneva-600" />
            </div>
            <span className="text-sm text-gray-500">Total Meetings</span>
          </div>
          <p className="text-3xl font-bold">{overview?.total_meetings ?? 0}</p>
        </div>
        <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-blue-100 rounded-lg">
              <Clock size={20} className="text-blue-600" />
            </div>
            <span className="text-sm text-gray-500">Total Hours</span>
          </div>
          <p className="text-3xl font-bold">{formatHours(overview?.total_hours ?? 0)}</p>
        </div>
        <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-green-100 rounded-lg">
              <CheckSquare size={20} className="text-green-600" />
            </div>
            <span className="text-sm text-gray-500">Action Items Created</span>
          </div>
          <p className="text-3xl font-bold">{overview?.total_action_items ?? 0}</p>
        </div>
        <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-purple-100 rounded-lg">
              <Lightbulb size={20} className="text-purple-600" />
            </div>
            <span className="text-sm text-gray-500">Decisions Made</span>
          </div>
          <p className="text-3xl font-bold">{overview?.total_decisions ?? 0}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        {/* Meeting Frequency Chart */}
        <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-100">
          <h3 className="font-semibold text-lg mb-4 flex items-center gap-2">
            <TrendingUp size={18} className="text-gneva-600" />
            Meeting Frequency
          </h3>
          {meetingTrends.length === 0 ? (
            <p className="text-gray-400 text-sm py-8 text-center">No data yet</p>
          ) : (
            <div className="flex items-end gap-2 h-40">
              {meetingTrends.map((d, i) => (
                <div key={i} className="flex-1 flex flex-col items-center gap-1">
                  <span className="text-xs text-gray-500 font-medium">{d.meeting_count}</span>
                  <div
                    className="w-full bg-gneva-500 rounded-t-md transition-all hover:bg-gneva-600"
                    style={{ height: `${Math.max((d.meeting_count / maxFreq) * 100, 4)}%` }}
                  />
                  <span className="text-xs text-gray-400 mt-1 truncate w-full text-center">{d.week}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Speaker Analytics */}
        <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-100">
          <h3 className="font-semibold text-lg mb-4 flex items-center gap-2">
            <Users size={18} className="text-gneva-600" />
            Top Speakers by Talk Time
          </h3>
          {speakers.length === 0 ? (
            <p className="text-gray-400 text-sm py-8 text-center">No speaker data yet</p>
          ) : (
            <div className="space-y-3">
              {speakers.slice(0, 8).map((s, i) => (
                <div key={i}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-medium text-gray-700 truncate">{s.speaker}</span>
                    <span className="text-xs text-gray-500 flex-shrink-0 ml-2">
                      {formatTalkTime(s.total_talk_time_sec)} across {s.meetings_attended} meeting{s.meetings_attended !== 1 ? 's' : ''}
                    </span>
                  </div>
                  <div className="w-full bg-gray-100 rounded-full h-2">
                    <div
                      className="bg-gneva-500 h-2 rounded-full transition-all"
                      style={{ width: `${(s.total_talk_time_sec / maxTalkTime) * 100}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        {/* Topic Cloud */}
        <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-100">
          <h3 className="font-semibold text-lg mb-4 flex items-center gap-2">
            <MessageSquare size={18} className="text-gneva-600" />
            Most Discussed Topics
          </h3>
          {topics.length === 0 ? (
            <p className="text-gray-400 text-sm py-8 text-center">No topic data yet</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {topics.map((t, i) => {
                const ratio = t.mention_count / maxTopicCount;
                const sizeClass = ratio > 0.75 ? 'text-lg font-bold' :
                                  ratio > 0.5 ? 'text-base font-semibold' :
                                  ratio > 0.25 ? 'text-sm font-medium' : 'text-xs';
                const opacity = Math.max(0.4, ratio);
                return (
                  <span
                    key={i}
                    className={`inline-block px-3 py-1.5 bg-gneva-100 text-gneva-800 rounded-full ${sizeClass}`}
                    style={{ opacity }}
                    title={`${t.mention_count} mentions`}
                  >
                    {t.topic}
                  </span>
                );
              })}
            </div>
          )}
        </div>

        {/* Sentiment Trend */}
        <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-100">
          <h3 className="font-semibold text-lg mb-4">Sentiment Trend</h3>
          {sentiment.length === 0 ? (
            <p className="text-gray-400 text-sm py-8 text-center">No sentiment data yet</p>
          ) : (
            <div>
              <div className="flex items-end gap-1 h-32 mb-2">
                {sentiment.map((s, i) => (
                  <div key={i} className="flex-1 flex flex-col items-center justify-end h-full">
                    <div
                      className={`w-3 h-3 rounded-full ${sentimentColor(s.avg_sentiment)} transition-all`}
                      style={{ marginBottom: `${Math.max(0, (s.avg_sentiment + 1) / 2 * 100)}%` }}
                      title={`${s.week}: ${s.avg_sentiment.toFixed(2)}`}
                    />
                  </div>
                ))}
              </div>
              <div className="flex justify-between text-xs text-gray-400">
                {sentiment.length > 0 && <span>{sentiment[0].week}</span>}
                {sentiment.length > 1 && <span>{sentiment[sentiment.length - 1].week}</span>}
              </div>
              <div className="flex items-center gap-4 mt-3 text-xs text-gray-500">
                <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-green-500" /> Positive</span>
                <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-yellow-500" /> Neutral</span>
                <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-500" /> Negative</span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Pattern Alerts */}
      {patterns.length > 0 && (
        <div>
          <h3 className="font-semibold text-lg mb-4">Pattern Alerts</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {patterns.map(p => (
              <div
                key={p.id}
                className={`bg-white rounded-xl p-5 shadow-sm border border-gray-100 border-l-4 ${patternTypeColors[p.type] || 'border-l-gray-400'}`}
              >
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">
                        {p.type.replace(/_/g, ' ')}
                      </span>
                      {p.severity === 'high' && (
                        <span className="px-1.5 py-0.5 bg-red-100 text-red-700 text-xs rounded font-medium">High</span>
                      )}
                    </div>
                    <h4 className="font-semibold text-gray-900">{p.title}</h4>
                    <p className="text-sm text-gray-500 mt-1">{p.description}</p>
                  </div>
                  <button
                    onClick={() => handleDismissPattern(p.id)}
                    className="text-gray-300 hover:text-gray-500 flex-shrink-0 ml-3"
                    title="Dismiss"
                  >
                    <X size={18} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
