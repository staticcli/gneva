import { Link, useLocation } from 'react-router-dom'
import { Home, Brain, MessageCircle, LogOut } from 'lucide-react'

interface Props {
  user: { name: string; org_name: string };
  onLogout: () => void;
  children: React.ReactNode;
}

const NAV = [
  { path: '/', label: 'Meetings', icon: Home },
  { path: '/memory', label: 'Memory', icon: Brain },
  { path: '/ask', label: 'Ask Gneva', icon: MessageCircle },
];

export default function Layout({ user, onLogout, children }: Props) {
  const location = useLocation();

  return (
    <div className="min-h-screen flex">
      {/* Sidebar */}
      <aside className="w-64 bg-gneva-800 text-white flex flex-col">
        <div className="p-6">
          <h1 className="text-2xl font-bold tracking-tight">Gneva</h1>
          <p className="text-gneva-300 text-sm mt-1">{user.org_name}</p>
        </div>

        <nav className="flex-1 px-4">
          {NAV.map(({ path, label, icon: Icon }) => (
            <Link
              key={path}
              to={path}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg mb-1 transition-colors ${
                location.pathname === path
                  ? 'bg-gneva-600 text-white'
                  : 'text-gneva-200 hover:bg-gneva-700'
              }`}
            >
              <Icon size={18} />
              {label}
            </Link>
          ))}
        </nav>

        <div className="p-4 border-t border-gneva-700">
          <div className="flex items-center justify-between">
            <span className="text-sm text-gneva-300">{user.name}</span>
            <button onClick={onLogout} className="text-gneva-400 hover:text-white">
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 p-8 overflow-auto">
        {children}
      </main>
    </div>
  );
}
