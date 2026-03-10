import { useState, useEffect } from 'react'
import { Search, Users, FolderKanban, GitBranch, CheckSquare, Tag } from 'lucide-react'
import { api } from '../api'

const ENTITY_TYPES = [
  { key: '', label: 'All', icon: Tag },
  { key: 'person', label: 'People', icon: Users },
  { key: 'project', label: 'Projects', icon: FolderKanban },
  { key: 'decision', label: 'Decisions', icon: GitBranch },
  { key: 'action_item', label: 'Actions', icon: CheckSquare },
  { key: 'topic', label: 'Topics', icon: Tag },
];

export default function Memory() {
  const [query, setQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [entities, setEntities] = useState<any[]>([]);
  const [selected, setSelected] = useState<any>(null);

  useEffect(() => {
    if (query.length >= 2) {
      api.search(query, typeFilter || undefined).then(r => setEntities(r.results));
    } else {
      api.entities(typeFilter || undefined).then(r => setEntities(r.entities));
    }
  }, [query, typeFilter]);

  const loadEntity = async (id: string) => {
    const e = await api.entity(id);
    setSelected(e);
  };

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Organizational Memory</h2>

      {/* Search */}
      <div className="relative mb-4">
        <Search size={18} className="absolute left-3 top-3 text-gray-400" />
        <input
          type="text"
          placeholder="Search people, projects, decisions..."
          value={query}
          onChange={e => setQuery(e.target.value)}
          className="w-full pl-10 pr-4 py-2.5 border rounded-lg focus:ring-2 focus:ring-gneva-500 outline-none"
        />
      </div>

      {/* Type filters */}
      <div className="flex gap-2 mb-6 flex-wrap">
        {ENTITY_TYPES.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setTypeFilter(key)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm transition-colors ${
              typeFilter === key
                ? 'bg-gneva-600 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            <Icon size={14} />
            {label}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Entity list */}
        <div className="lg:col-span-2 space-y-2">
          {entities.length === 0 ? (
            <p className="text-gray-400 text-center py-12">No entities found</p>
          ) : (
            entities.map((e: any) => (
              <button
                key={e.id}
                onClick={() => loadEntity(e.id)}
                className={`w-full text-left p-4 rounded-lg border transition-colors ${
                  selected?.id === e.id
                    ? 'border-gneva-500 bg-gneva-50'
                    : 'border-gray-100 bg-white hover:border-gneva-200'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div>
                    <span className="text-xs uppercase tracking-wide text-gray-400">{e.type}</span>
                    <h4 className="font-medium">{e.name}</h4>
                    {e.description && <p className="text-sm text-gray-500 mt-0.5 line-clamp-1">{e.description}</p>}
                  </div>
                  <span className="text-xs text-gray-400">{e.mention_count}x</span>
                </div>
              </button>
            ))
          )}
        </div>

        {/* Entity detail */}
        <div>
          {selected ? (
            <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100 sticky top-8">
              <span className="text-xs uppercase tracking-wide text-gneva-600">{selected.type}</span>
              <h3 className="text-xl font-bold mt-1">{selected.name}</h3>
              {selected.description && <p className="text-gray-600 mt-2">{selected.description}</p>}

              <div className="mt-4 text-sm text-gray-500">
                <p>Mentions: {selected.mention_count}</p>
                <p>First seen: {new Date(selected.first_seen).toLocaleDateString()}</p>
                <p>Last seen: {new Date(selected.last_seen).toLocaleDateString()}</p>
              </div>

              {(selected.relationships_out?.length > 0 || selected.relationships_in?.length > 0) && (
                <div className="mt-4">
                  <h4 className="font-semibold text-sm mb-2">Relationships</h4>
                  <div className="space-y-1">
                    {selected.relationships_out?.map((r: any, i: number) => (
                      <p key={i} className="text-sm text-gray-600">
                        &rarr; {r.relationship} <span className="text-gray-400">({(r.confidence * 100).toFixed(0)}%)</span>
                      </p>
                    ))}
                    {selected.relationships_in?.map((r: any, i: number) => (
                      <p key={i} className="text-sm text-gray-600">
                        &larr; {r.relationship} <span className="text-gray-400">({(r.confidence * 100).toFixed(0)}%)</span>
                      </p>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center text-gray-400 py-12">
              Select an entity to view details
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
