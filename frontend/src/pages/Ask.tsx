import { useState } from 'react'
import { Send } from 'lucide-react'
import { api } from '../api'

interface Message {
  role: 'user' | 'gneva';
  content: string;
  sources?: any[];
}

export default function Ask() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const question = input.trim();
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: question }]);
    setLoading(true);

    try {
      const res = await api.ask(question);
      setMessages(prev => [...prev, {
        role: 'gneva',
        content: res.answer,
        sources: res.sources,
      }]);
    } catch (err: any) {
      setMessages(prev => [...prev, {
        role: 'gneva',
        content: `Sorry, I couldn't process that: ${err.message}`,
      }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)]">
      <h2 className="text-2xl font-bold mb-4">Ask Gneva</h2>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-4 mb-4">
        {messages.length === 0 && (
          <div className="text-center text-gray-400 py-20">
            <p className="text-lg mb-2">Ask me anything about your organization</p>
            <div className="flex flex-wrap justify-center gap-2 mt-4">
              {[
                'What did we decide about the roadmap?',
                'Who owns the authentication project?',
                'What action items are overdue?',
                'Summarize last week\'s standup',
              ].map((q, i) => (
                <button
                  key={i}
                  onClick={() => setInput(q)}
                  className="px-4 py-2 bg-white border rounded-lg text-sm text-gray-600 hover:border-gneva-400 transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div className={`max-w-[80%] rounded-2xl px-5 py-3 ${
              msg.role === 'user'
                ? 'bg-gneva-600 text-white'
                : 'bg-white border border-gray-200'
            }`}>
              <p className="whitespace-pre-wrap">{msg.content}</p>
              {msg.sources && msg.sources.length > 0 && (
                <div className="mt-3 pt-2 border-t border-gray-100">
                  <p className="text-xs text-gray-400 mb-1">Sources:</p>
                  {msg.sources.map((s: any, j: number) => (
                    <span key={j} className="text-xs bg-gneva-50 text-gneva-600 px-2 py-0.5 rounded mr-1">
                      {s.name}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-white border border-gray-200 rounded-2xl px-5 py-3 text-gray-400">
              Thinking...
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <form onSubmit={handleSend} className="flex gap-3">
        <input
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder="Ask Gneva a question..."
          className="flex-1 px-4 py-3 border rounded-xl focus:ring-2 focus:ring-gneva-500 outline-none"
          disabled={loading}
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="bg-gneva-600 text-white px-5 py-3 rounded-xl hover:bg-gneva-700 transition-colors disabled:opacity-50"
        >
          <Send size={18} />
        </button>
      </form>
    </div>
  );
}
