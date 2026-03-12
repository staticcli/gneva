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
  joinMeeting: (meeting_url: string, _platform: string, title?: string, bot_name?: string, voice_id?: string, greeting_mode?: string, meeting_info?: string) =>
    request('/api/bot/join', { method: 'POST', body: JSON.stringify({ meeting_url, platform: 'auto', meeting_title: title, bot_name, voice_id, greeting_mode, meeting_info }) }),
  greetingModes: () => request('/api/bot/greeting-modes'),
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

  // Voices
  voices: () => request('/api/settings/voices'),
  addVoice: (voice_id: string, name: string, provider = 'elevenlabs') =>
    request('/api/settings/voices', { method: 'POST', body: JSON.stringify({ voice_id, name, provider }) }),
  updateVoice: (voice_id: string, update: { is_default?: boolean; name?: string }) =>
    request(`/api/settings/voices/${voice_id}`, { method: 'PATCH', body: JSON.stringify(update) }),
  deleteVoice: (voice_id: string) =>
    request(`/api/settings/voices/${voice_id}`, { method: 'DELETE' }),
  previewVoice: (voice_id: string) =>
    request(`/api/settings/voices/${voice_id}/preview`, { method: 'POST' }),
  settings: () => request('/api/settings/'),

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

  // Agents
  agents: (category?: string) => request(`/api/agents${category ? `?category=${category}` : ''}`),
  agent: (name: string) => request(`/api/agents/${name}`),
  createAgent: (data: any) => request('/api/agents', { method: 'POST', body: JSON.stringify(data) }),
  updateAgent: (name: string, data: any) => request(`/api/agents/${name}`, { method: 'PATCH', body: JSON.stringify(data) }),
  deleteAgent: (name: string) => request(`/api/agents/${name}`, { method: 'DELETE' }),
  meetingAgents: (meetingId: string) => request(`/api/agents/meetings/${meetingId}/agents`),
  assignAgent: (meetingId: string, data: { agent_name?: string; agent_id?: string; mode?: string }) =>
    request(`/api/agents/meetings/${meetingId}/assign`, { method: 'POST', body: JSON.stringify(data) }),
  removeAgentFromMeeting: (meetingId: string, agentName: string) =>
    request(`/api/agents/meetings/${meetingId}/agents/${agentName}`, { method: 'DELETE' }),
  agentPerformance: (name: string, days?: number) =>
    request(`/api/agents/${name}/performance${days ? `?days=${days}` : ''}`),
  agentMessages: (meetingId: string, agentName?: string) =>
    request(`/api/agents/meetings/${meetingId}/messages${agentName ? `?agent_name=${agentName}` : ''}`),

  // PM / Follow-ups
  followUps: () => request('/api/pm/follow-ups'),
  updateFollowUp: (id: string, update: any) => request(`/api/pm/follow-ups/${id}`, { method: 'PATCH', body: JSON.stringify(update) }),
  statusReport: () => request('/api/pm/status-report'),
  suggestMeetings: () => request('/api/pm/suggest-meetings', { method: 'POST' }),
  pmDashboard: () => request('/api/pm/dashboard'),

  // ROI
  meetingRoi: (id: string) => request(`/api/roi/meetings/${id}`),
  roiOverview: () => request('/api/roi/overview'),

  // Follow-ups (enforcement)
  overdueFollowups: () => request('/api/followups/overdue'),
  upcomingFollowups: () => request('/api/followups/upcoming'),
  nudgeAction: (id: string) => request(`/api/followups/${id}/nudge`, { method: 'POST' }),

  // Team Dynamics
  speakerDynamics: () => request('/api/dynamics/speakers'),
  meetingBalance: (id: string) => request(`/api/dynamics/meeting/${id}/balance`),

  // Contradictions
  activeContradictions: () => request('/api/contradictions/active'),
  resolveContradiction: (id: string, resolution_note: string) =>
    request(`/api/contradictions/${id}/resolve`, { method: 'POST', body: JSON.stringify({ resolution_note }) }),
};
