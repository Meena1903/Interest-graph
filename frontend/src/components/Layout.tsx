import React from 'react';
import { User } from '../types';
import { Network, Home, Compass, BarChart2, Loader2 } from 'lucide-react';

interface LayoutProps {
  children: React.ReactNode;
  activeTab: string;
  setActiveTab: (tab: string) => void;
  users: User[];
  selectedUser: User | null;
  setSelectedUser: (user: User) => void;
  loadingUsers: boolean;
}

export const Layout: React.FC<LayoutProps> = ({
  children,
  activeTab,
  setActiveTab,
  users,
  selectedUser,
  setSelectedUser,
  loadingUsers
}) => {
  const tabs = [
    { id: 'dashboard', name: 'Dashboard', icon: Home },
    { id: 'discovery', name: 'Discovery', icon: Compass },
    { id: 'graph', name: 'Graph Explorer', icon: Network },
    { id: 'analytics', name: 'Analytics', icon: BarChart2 }
  ];

  return (
    <div className="flex min-h-screen bg-slate-950 text-slate-100">
      {/* Sidebar */}
      <aside className="w-64 border-r border-slate-800 bg-slate-900/50 backdrop-blur flex flex-col">
        {/* Brand */}
        <div className="p-6 border-b border-slate-800 flex items-center gap-2">
          <Network className="h-6 w-6 text-emerald-400 animate-pulse" />
          <span className="text-xl font-bold tracking-tight bg-gradient-to-r from-emerald-400 to-cyan-400 bg-clip-text text-transparent">
            Sodio Interest
          </span>
        </div>

        {/* User Switcher */}
        <div className="p-4 border-b border-slate-800">
          <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider block mb-2">
            Active Persona (User Node)
          </label>
          {loadingUsers ? (
            <div className="flex items-center gap-2 py-2 px-3 text-slate-500 text-sm">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading personas...
            </div>
          ) : (
            <select
              className="w-full bg-slate-800 border border-slate-700 text-slate-200 py-1.5 px-2.5 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
              value={selectedUser?.id || ''}
              onChange={(e) => {
                const u = users.find((x) => x.id === parseInt(e.target.value));
                if (u) setSelectedUser(u);
              }}
            >
              {users.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.display_name} ({u.user_type})
                </option>
              ))}
            </select>
          )}
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-4 space-y-1">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const active = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-medium transition-all ${
                  active
                    ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                    : 'text-slate-400 hover:bg-slate-800/60 hover:text-slate-200 border border-transparent'
                }`}
              >
                <Icon className="h-4 w-4" />
                {tab.name}
              </button>
            );
          })}
        </nav>

        {/* Info footer */}
        <div className="p-4 border-t border-slate-800 text-xs text-slate-500 flex flex-col gap-1">
          <div>POC v1.0.0 (FastAPI + React TS)</div>
          <div>Calculations: 100% Native Python</div>
          <div>NLP Extraction: NVIDIA NIM APIs</div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Topbar */}
        <header className="h-16 border-b border-slate-800 bg-slate-900/20 backdrop-blur flex items-center justify-between px-8">
          <div>
            <h1 className="text-lg font-semibold text-slate-200 capitalize">
              {activeTab} Workspace
            </h1>
          </div>
          {selectedUser && (
            <div className="flex items-center gap-4">
              <div className="text-right">
                <div className="text-sm font-semibold text-slate-200">{selectedUser.display_name}</div>
                <div className="text-xs text-slate-400">@{selectedUser.username}</div>
              </div>
              <div className="h-10 w-10 rounded-full bg-gradient-to-tr from-emerald-500 to-cyan-500 flex items-center justify-center font-bold text-slate-950 uppercase border-2 border-slate-800">
                {selectedUser.username.substring(0, 2)}
              </div>
            </div>
          )}
        </header>

        {/* Page content container */}
        <main className="flex-1 overflow-y-auto p-8 custom-scrollbar">
          <div className="max-w-7xl mx-auto space-y-6">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
};
