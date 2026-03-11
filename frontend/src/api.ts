const API_URL = import.meta.env.VITE_API_URL || '';

let token: string | null = localStorage.getItem('gneva_token');

export function setToken(t: string | null) {
  token = t;
  if (t) localStorage.setItem('gneva_token', t);
  else localStorage.removeItem('gneva_token');
}

export function getToken() {
  return token;
}

async function request(path: string, options: RequestInit = {}) {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (res.status === 401) {
    setToken(null);
    window.location.href = '/login';
    throw new Error('Unauthorized');
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Request failed');
  }
  return res.json();
}

export const api = {
  // Auth
  login: (email: string, password: string) =>
    request('/api/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
  register: (email: string, password: string, name: string, org_name: string) =>
    request('/api/auth/register', { method: 'POST', body: JSON.stringify({ email, password, name, org_name }) }),
  me: () => request('/api/auth/me'),

  // Meetings
  meetings: (offset = 0, limit = 20) => request(`/api/meetings?offset=${offset}&limit=${limit}`),
  meeting: (id: string) => request(`/api/meetings/${id}`),
  transcript: (id: string) => request(`/api/meetings/${id}/transcript`),
  summary: (id: string) => request(`/api/meetings/${id}/summary`),
  meetingActions: (id: string) => request(`/api/meetings/${id}/action-items`),
  meetingDecisions: (id: string) => request(`/api/meetings/${id}/decisions`),

  // Bot
  joinMeeting: (meeting_url: string, _platform: string, title?: string, bot_name?: string) =>
    request('/api/bot/join', { method: 'POST', body: JSON.stringify({ meeting_url, platform: 'auto', meeting_title: title, bot_name }) }),
  leaveMeeting: (bot_id: string) =>
    request('/api/bot/leave', { method: 'POST', body: JSON.stringify({ bot_id }) }),
  botStatus: (bot_id: string) => request(`/api/bot/status/${bot_id}`),
  activeBots: () => request('/api/bot/active'),

  // Memory
  search: (q: string, type?: string) => request(`/api/memory/search?q=${encodeURIComponent(q)}${type ? `&type=${type}` : ''}`),
  entities: (type?: string) => request(`/api/memory/entities${type ? `?type=${type}` : ''}`),
  entity: (id: string) => request(`/api/memory/entities/${id}`),
  decisions: () => request('/api/memory/decisions'),
  contradictions: () => request('/api/memory/contradictions'),

  // Ask
  ask: (question: string) => request('/api/ask', { method: 'POST', body: JSON.stringify({ question }) }),

  // Demo
  createDemoMeeting: (title?: string) =>
    request('/api/demo/meeting', { method: 'POST', body: JSON.stringify({ title: title || 'Q2 Planning Session', run_ai: true }) }),

  // Actions
  actionItems: (status?: string) => request(`/api/actions${status ? `?status=${status}` : ''}`),
  updateAction: (id: string, update: { status?: string; priority?: string }) =>
    request(`/api/actions/${id}`, { method: 'PATCH', body: JSON.stringify(update) }),

  // Upload
  uploadAudio: async (file: File, title?: string, platform?: string) => {
    const form = new FormData();
    form.append('file', file);
    if (title) form.append('title', title);
    if (platform) form.append('platform', platform);

    const headers: Record<string, string> = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const res = await fetch(`${API_URL}/api/upload/audio`, {
      method: 'POST',
      headers,
      body: form,
    });
    if (res.status === 401) {
      setToken(null);
      window.location.href = '/login';
      throw new Error('Unauthorized');
    }
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || 'Upload failed');
    }
    return res.json();
  },

  // Calendar
  calendarEvents: () => request('/api/calendar/events'),
  calendarSync: () => request('/api/calendar/sync', { method: 'POST' }),
  calendarToggleAutoJoin: (id: string, auto_join: boolean) =>
    request(`/api/calendar/events/${id}`, { method: 'PATCH', body: JSON.stringify({ auto_join }) }),

  // Notifications
  notifications: () => request('/api/notifications'),
  unreadCount: () => request('/api/notifications/unread-count'),
  markRead: (id: string) => request(`/api/notifications/${id}/read`, { method: 'POST' }),
  markAllRead: () => request('/api/notifications/read-all', { method: 'POST' }),

  // Analytics
  analyticsOverview: () => request('/api/analytics/overview'),
  speakerAnalytics: (meetingId: string) => request(`/api/analytics/meetings/${meetingId}/speakers`),
  patterns: () => request('/api/analytics/patterns'),
  dismissPattern: (id: string) => request(`/api/analytics/patterns/${id}/dismiss`, { method: 'POST' }),
  trends: () => request('/api/analytics/trends'),

  // PM / Follow-ups
  followUps: () => request('/api/pm/follow-ups'),
  updateFollowUp: (id: string, update: any) => request(`/api/pm/follow-ups/${id}`, { method: 'PATCH', body: JSON.stringify(update) }),
  statusReport: () => request('/api/pm/status-report'),
  suggestMeetings: () => request('/api/pm/suggest-meetings', { method: 'POST' }),
  pmDashboard: () => request('/api/pm/dashboard'),
};
