import { useState } from 'react'
import { api, setToken } from '../api'

interface Props {
  onLogin: (user: any) => void;
}

export default function Login({ onLogin }: Props) {
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [orgName, setOrgName] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      let res;
      if (isRegister) {
        res = await api.register(email, password, name, orgName);
      } else {
        res = await api.login(email, password);
      }
      setToken(res.access_token);
      const user = await api.me();
      onLogin(user);
    } catch (err: any) {
      setError(err.message || 'Something went wrong');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gneva-50">
      <div className="bg-white rounded-2xl shadow-xl p-8 w-full max-w-md">
        <h1 className="text-3xl font-bold text-gneva-800 mb-2 text-center">Gneva</h1>
        <p className="text-gray-500 mb-8 text-center">Your AI team member</p>

        <form onSubmit={handleSubmit} className="space-y-4">
          {isRegister && (
            <>
              <input
                type="text"
                placeholder="Your name"
                value={name}
                onChange={e => setName(e.target.value)}
                className="w-full px-4 py-2.5 border rounded-lg focus:ring-2 focus:ring-gneva-500 outline-none"
                required
              />
              <input
                type="text"
                placeholder="Organization name"
                value={orgName}
                onChange={e => setOrgName(e.target.value)}
                className="w-full px-4 py-2.5 border rounded-lg focus:ring-2 focus:ring-gneva-500 outline-none"
                required
              />
            </>
          )}
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            className="w-full px-4 py-2.5 border rounded-lg focus:ring-2 focus:ring-gneva-500 outline-none"
            required
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            className="w-full px-4 py-2.5 border rounded-lg focus:ring-2 focus:ring-gneva-500 outline-none"
            required
          />

          {error && <p className="text-red-500 text-sm">{error}</p>}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-gneva-600 text-white py-2.5 rounded-lg font-medium hover:bg-gneva-700 transition-colors disabled:opacity-50"
          >
            {loading ? 'Loading...' : isRegister ? 'Create Account' : 'Sign In'}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-gray-500">
          {isRegister ? 'Already have an account?' : "Don't have an account?"}{' '}
          <button
            onClick={() => setIsRegister(!isRegister)}
            className="text-gneva-600 font-medium hover:underline"
          >
            {isRegister ? 'Sign in' : 'Register'}
          </button>
        </p>
      </div>
    </div>
  );
}
