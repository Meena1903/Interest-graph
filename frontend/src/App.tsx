import React, { useEffect, useState } from 'react';
import { User } from './types';
import { apiClient } from './api/client';
import { Layout } from './components/Layout';
import { Dashboard } from './pages/Dashboard';
import { Discovery } from './pages/Discovery';
import { GraphExplorer } from './pages/GraphExplorer';
import { Analytics } from './pages/Analytics';
import { Onboarding } from './pages/Onboarding';
import { UserPlus } from 'lucide-react';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<string>('dashboard');
  const [users, setUsers] = useState<User[]>([]);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [loadingUsers, setLoadingUsers] = useState(false);

  const fetchUsers = async (defaultSelectId?: number) => {
    setLoadingUsers(true);
    try {
      const res = await apiClient.getUsers();
      setUsers(res);
      if (res.length > 0) {
        // Select default or pre-selected user
        const toSelect = defaultSelectId 
          ? res.find((u) => u.id === defaultSelectId) || res[0]
          : res[0];
        setSelectedUser(toSelect);
      }
    } catch (err) {
      console.error("Fetch personas list error:", err);
    } finally {
      setLoadingUsers(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  const handleInteract = async (entityType: string, entityId: number, interactionType: string) => {
    if (!selectedUser) return;
    try {
      await apiClient.recordInteraction({
        user_id: selectedUser.id,
        entity_type: entityType,
        entity_id: entityId,
        interaction_type: interactionType
      });
      console.log(`Interaction recorded: ${interactionType} on ${entityType}#${entityId}`);
    } catch (err) {
      console.error("Record interaction error:", err);
    }
  };

  const handleOnboardingSuccess = (newUser: User) => {
    fetchUsers(newUser.id);
    setActiveTab('dashboard');
  };

  return (
    <Layout
      activeTab={activeTab}
      setActiveTab={setActiveTab}
      users={users}
      selectedUser={selectedUser}
      setSelectedUser={setSelectedUser}
      loadingUsers={loadingUsers}
    >
      {activeTab === 'dashboard' && (
        <Dashboard selectedUser={selectedUser} onInteract={handleInteract} />
      )}
      {activeTab === 'discovery' && (
        <Discovery selectedUser={selectedUser} onInteract={handleInteract} />
      )}
      {activeTab === 'graph' && (
        <GraphExplorer selectedUser={selectedUser} />
      )}
      {activeTab === 'analytics' && (
        <Analytics />
      )}
      {activeTab === 'onboarding' && (
        <Onboarding onSuccess={handleOnboardingSuccess} />
      )}
      
      {/* Absolute Add User Button floating on workspace */}
      {activeTab !== 'onboarding' && (
        <button
          onClick={() => setActiveTab('onboarding')}
          className="fixed bottom-6 right-6 p-3 bg-emerald-500 hover:bg-emerald-600 text-slate-950 rounded-full font-bold shadow-xl transition-all flex items-center gap-1.5 z-20 text-xs border border-emerald-400"
          title="Create New Persona Node"
        >
          <UserPlus className="h-4.5 w-4.5" />
          <span>New Node</span>
        </button>
      )}
    </Layout>
  );
};

export default App;
