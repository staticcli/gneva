import { Routes, Route, Navigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import { api, getToken, setToken } from './api'
import Layout from './components/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import MeetingDetail from './pages/MeetingDetail'
import Memory from './pages/Memory'
import Ask from './pages/Ask'
import Calendar from './pages/Calendar'
import ActionCenter from './pages/ActionCenter'
import Analytics from './pages/Analytics'
import Settings from './pages/Settings'
import TeamDynamics from './pages/TeamDynamics'
import MeetingROI from './pages/MeetingROI'
import FollowUps from './pages/FollowUps'
import Agents from './pages/Agents'

interface User {
  id: string;
  email: string;
  name: string;
  role: string;
  org_id: string;
  org_name: string;
}

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (getToken()) {
      api.me().then(setUser).catch(() => setToken(null)).finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  if (loading) return <div className="flex items-center justify-center h-screen">Loading...</div>;

  if (!user) {
    return (
      <Routes>
        <Route path="/login" element={<Login onLogin={setUser} />} />
        <Route path="*" element={<Navigate to="/login" />} />
      </Routes>
    );
  }

  return (
    <Layout user={user} onLogout={() => { setToken(null); setUser(null); }}>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/meetings/:id" element={<MeetingDetail />} />
        <Route path="/memory" element={<Memory />} />
        <Route path="/ask" element={<Ask />} />
        <Route path="/calendar" element={<Calendar />} />
        <Route path="/actions" element={<ActionCenter />} />
        <Route path="/analytics" element={<Analytics />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/dynamics" element={<TeamDynamics />} />
        <Route path="/roi" element={<MeetingROI />} />
        <Route path="/followups" element={<FollowUps />} />
        <Route path="/agents" element={<Agents />} />
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </Layout>
  );
}
