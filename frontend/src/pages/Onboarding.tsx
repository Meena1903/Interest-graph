import React, { useEffect, useState } from 'react';
import { Interest, User } from '../types';
import { apiClient } from '../api/client';
import { InterestSelector } from '../components/InterestSelector';
import { UserPlus, Sparkles, AlertCircle } from 'lucide-react';

interface OnboardingProps {
  onSuccess: (newUser: User) => void;
}

export const Onboarding: React.FC<OnboardingProps> = ({ onSuccess }) => {
  const [username, setUsername] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [email, setEmail] = useState('');
  const [bio, setBio] = useState('');
  const [city, setCity] = useState('San Francisco');
  const [userType, setUserType] = useState('community');
  const [selectedInterests, setSelectedInterests] = useState<number[]>([]);
  const [availableInterests, setAvailableInterests] = useState<Interest[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  useEffect(() => {
    const fetchInterests = async () => {
      try {
        // Query some post to get interests list, or let's create a temporary user 1 call
        // For POC, we fetch from backend list of interests.
        // We fetch users profile which returns label map or we fetch default list.
        const res = await apiClient.getUserProfile(1);
        if (res && res.interest_vector_labels) {
          // Re-map to list of Interest objects
          const list = res.interest_vector_labels.map((name, i) => ({
            id: i + 1,
            name,
            domain_id: 1,
            description: `Interests related to ${name}`
          }));
          setAvailableInterests(list);
        }
      } catch (err) {
        console.error("Fetch onboarding interests error:", err);
      }
    };
    fetchInterests();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username || !displayName || !email) return;

    setSubmitting(true);
    setErrorMessage('');
    
    // SF Coordinates fallback
    const lat = city === 'Oakland' ? 37.8044 : city === 'San Jose' ? 37.3382 : 37.7749;
    const lon = city === 'Oakland' ? -122.2712 : city === 'San Jose' ? -121.8863 : -122.4194;

    try {
      const createdUser = await apiClient.createUser({
        username,
        display_name: displayName,
        email,
        bio: bio || undefined,
        location_city: city,
        location_lat: lat,
        location_lon: lon,
        user_type: userType,
        interest_ids: selectedInterests
      });
      onSuccess(createdUser);
    } catch (err: any) {
      console.error(err);
      setErrorMessage(err.message || 'Username or email already exists.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto bg-slate-900 border border-slate-800 rounded-xl p-8 shadow-2xl space-y-6">
      <div className="text-center space-y-2">
        <h2 className="text-xl font-bold text-slate-100 flex items-center justify-center gap-2">
          <Sparkles className="h-5 w-5 text-emerald-400 animate-bounce" />
          Create New Persona Node
        </h2>
        <p className="text-xs text-slate-400">
          Create a user profile to seed initial interests. The ranking engine will compute vectors dynamically.
        </p>
      </div>

      {errorMessage && (
        <div className="bg-red-500/10 border border-red-500/20 text-red-400 p-3 rounded-lg text-xs flex items-center gap-2">
          <AlertCircle className="h-4 w-4 flex-shrink-0" />
          {errorMessage}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-300">Username</label>
            <input
              type="text"
              placeholder="e.g. john_doe"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full bg-slate-950 border border-slate-850 rounded-lg py-2 px-3 text-xs focus:outline-none focus:ring-1 focus:ring-emerald-500 text-slate-200"
              required
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-300">Display Name</label>
            <input
              type="text"
              placeholder="e.g. John Doe"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              className="w-full bg-slate-950 border border-slate-850 rounded-lg py-2 px-3 text-xs focus:outline-none focus:ring-1 focus:ring-emerald-500 text-slate-200"
              required
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-300">Email Address</label>
            <input
              type="email"
              placeholder="e.g. john@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full bg-slate-950 border border-slate-850 rounded-lg py-2 px-3 text-xs focus:outline-none focus:ring-1 focus:ring-emerald-500 text-slate-200"
              required
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-300">City Proximity</label>
            <select
              value={city}
              onChange={(e) => setCity(e.target.value)}
              className="w-full bg-slate-950 border border-slate-850 rounded-lg py-2 px-3 text-xs focus:outline-none focus:ring-1 focus:ring-emerald-500 text-slate-200"
            >
              <option value="San Francisco">San Francisco</option>
              <option value="Oakland">Oakland</option>
              <option value="San Jose">San Jose</option>
            </select>
          </div>
          <div className="space-y-1.5 md:col-span-2">
            <label className="text-xs font-semibold text-slate-300">User Account Type</label>
            <div className="grid grid-cols-3 gap-2">
              {['community', 'creator', 'verified'].map((type) => (
                <button
                  key={type}
                  type="button"
                  onClick={() => setUserType(type)}
                  className={`py-1.5 rounded-lg border text-xs font-semibold capitalize transition-all ${
                    userType === type
                      ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                      : 'bg-slate-950 text-slate-400 border-slate-850 hover:bg-slate-900'
                  }`}
                >
                  {type}
                </button>
              ))}
            </div>
          </div>
          <div className="space-y-1.5 md:col-span-2">
            <label className="text-xs font-semibold text-slate-300">Bio</label>
            <textarea
              placeholder="Tell us about yourself..."
              rows={2}
              value={bio}
              onChange={(e) => setBio(e.target.value)}
              className="w-full bg-slate-950 border border-slate-850 rounded-lg py-2 px-3 text-xs focus:outline-none focus:ring-1 focus:ring-emerald-500 text-slate-200"
            />
          </div>
        </div>

        {/* Interests Selector */}
        <div className="space-y-2 border-t border-slate-850 pt-4">
          <label className="text-xs font-bold text-slate-300 uppercase tracking-wider block mb-2">
            Select Your Interests (Onboarding Seeds)
          </label>
          <InterestSelector
            availableInterests={availableInterests}
            selectedIds={selectedInterests}
            onChange={setSelectedInterests}
          />
        </div>

        {/* Submit */}
        <button
          type="submit"
          disabled={submitting}
          className="w-full py-2.5 bg-emerald-500 hover:bg-emerald-600 text-slate-950 rounded-lg font-bold text-sm flex items-center justify-center gap-2 transition-all shadow-lg shadow-emerald-950/20"
        >
          <UserPlus className="h-4 w-4" />
          {submitting ? 'Creating Profile...' : 'Complete Registration'}
        </button>
      </form>
    </div>
  );
};
