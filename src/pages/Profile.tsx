/**
 * User profile page (protected).
 */
import { useState, FormEvent } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import authService from '../services/authService';
import SavedAddressesManager from '../components/customer/SavedAddressesManager';

export default function Profile() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [showChangePassword, setShowChangePassword] = useState(false);
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmNewPassword, setConfirmNewPassword] = useState('');
  const [passwordMessage, setPasswordMessage] = useState('');
  const [passwordError, setPasswordError] = useState('');
  const [isChangingPassword, setIsChangingPassword] = useState(false);

  const handleChangePassword = async (e: FormEvent) => {
    e.preventDefault();
    setPasswordError('');
    setPasswordMessage('');

    if (newPassword !== confirmNewPassword) {
      setPasswordError('Passwords do not match');
      return;
    }

    if (newPassword.length < 8) {
      setPasswordError('Password must be at least 8 characters');
      return;
    }

    setIsChangingPassword(true);

    try {
      const response = await authService.changePassword(currentPassword, newPassword);
      setPasswordMessage(response.message);
      setCurrentPassword('');
      setNewPassword('');
      setConfirmNewPassword('');
    } catch (err: any) {
      setPasswordError(err.detail || 'Failed to change password');
    } finally {
      setIsChangingPassword(false);
    }
  };

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-gray-500">Loading profile...</p>
      </div>
    );
  }

  const roleColors: Record<string, string> = {
    CUSTOMER: 'bg-blue-100 text-blue-800',
    KITCHEN_OWNER: 'bg-green-100 text-green-800',
    ADMIN: 'bg-purple-100 text-purple-800',
  };

  const statusColors: Record<string, string> = {
    ACTIVE: 'bg-green-100 text-green-800',
    INACTIVE: 'bg-gray-100 text-gray-800',
    SUSPENDED: 'bg-red-100 text-red-800',
    PENDING_VERIFICATION: 'bg-yellow-100 text-yellow-800',
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-5xl mx-auto px-4 py-4 flex items-center justify-between">
          <h1 className="text-xl font-bold text-gray-800">KitchenVerse Platform</h1>
          <button
            onClick={handleLogout}
            className="text-sm text-gray-600 hover:text-red-600 font-medium transition"
          >
            Logout
          </button>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-5xl mx-auto px-4 py-8">
        {/* Email verification warning */}
        {user && !user.is_email_verified && (
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-6">
            <div className="flex items-start gap-3">
              <svg className="w-5 h-5 text-yellow-600 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <div>
                <h3 className="text-sm font-medium text-yellow-800">Email not verified</h3>
                <p className="text-sm text-yellow-700 mt-1">
                  Please check your email for a verification link. Some features may be limited until your email is verified.
                </p>
              </div>
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Profile Card */}
          <div className="lg:col-span-2">
            <div className="bg-white rounded-xl shadow-sm p-6">
              <h2 className="text-lg font-semibold text-gray-800 mb-4">Profile Information</h2>
              
              <div className="space-y-4">
                <div className="flex items-center gap-4">
                  <div className="w-16 h-16 bg-orange-100 rounded-full flex items-center justify-center">
                    <span className="text-2xl font-bold text-orange-600">
                      {user.first_name[0]}{user.last_name[0]}
                    </span>
                  </div>
                  <div>
                    <h3 className="text-lg font-medium text-gray-800">
                      {user.first_name} {user.last_name}
                    </h3>
                    <p className="text-gray-500">{user.email}</p>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4 pt-4 border-t">
                  <div>
                    <p className="text-sm text-gray-500">Role</p>
                    <span className={`inline-block mt-1 px-3 py-1 rounded-full text-xs font-medium ${roleColors[user.role] || 'bg-gray-100'}`}>
                      {user.role.replace('_', ' ')}
                    </span>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500">Status</p>
                    <span className={`inline-block mt-1 px-3 py-1 rounded-full text-xs font-medium ${statusColors[user.status] || 'bg-gray-100'}`}>
                      {user.status.replace('_', ' ')}
                    </span>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500">Email Verified</p>
                    <p className="mt-1 text-sm font-medium">
                      {user.is_email_verified ? (
                        <span className="text-green-600">✓ Verified</span>
                      ) : (
                        <span className="text-yellow-600">⚠ Not verified</span>
                      )}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500">Member Since</p>
                    <p className="mt-1 text-sm font-medium text-gray-800">
                      {new Date(user.created_at).toLocaleDateString()}
                    </p>
                  </div>
                  {user.last_login_at && (
                    <div>
                      <p className="text-sm text-gray-500">Last Login</p>
                      <p className="mt-1 text-sm font-medium text-gray-800">
                        {new Date(user.last_login_at).toLocaleString()}
                      </p>
                    </div>
                  )}
                  {user.phone && (
                    <div>
                      <p className="text-sm text-gray-500">Phone</p>
                      <p className="mt-1 text-sm font-medium text-gray-800">{user.phone}</p>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {user.role === 'CUSTOMER' && (
              <div className="bg-white rounded-xl shadow-sm p-6 mt-6">
                <SavedAddressesManager />
              </div>
            )}
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* Change Password */}
            <div className="bg-white rounded-xl shadow-sm p-6">
              <button
                onClick={() => setShowChangePassword(!showChangePassword)}
                className="w-full text-left"
              >
                <h3 className="text-lg font-semibold text-gray-800">
                  {showChangePassword ? 'Change Password' : 'Security'}
                </h3>
              </button>

              {showChangePassword && (
                <form onSubmit={handleChangePassword} className="mt-4 space-y-3">
                  {passwordError && (
                    <div className="bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded-lg text-sm">
                      {passwordError}
                    </div>
                  )}
                  {passwordMessage && (
                    <div className="bg-green-50 border border-green-200 text-green-700 px-3 py-2 rounded-lg text-sm">
                      {passwordMessage}
                    </div>
                  )}

                  <input
                    type="password"
                    required
                    value={currentPassword}
                    onChange={(e) => setCurrentPassword(e.target.value)}
                    placeholder="Current password"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-orange-500 focus:border-orange-500"
                  />
                  <input
                    type="password"
                    required
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    placeholder="New password"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-orange-500 focus:border-orange-500"
                  />
                  <input
                    type="password"
                    required
                    value={confirmNewPassword}
                    onChange={(e) => setConfirmNewPassword(e.target.value)}
                    placeholder="Confirm new password"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-orange-500 focus:border-orange-500"
                  />
                  <button
                    type="submit"
                    disabled={isChangingPassword}
                    className="w-full bg-orange-600 text-white py-2 px-4 rounded-lg text-sm font-medium hover:bg-orange-700 transition disabled:opacity-50"
                  >
                    {isChangingPassword ? 'Changing...' : 'Change Password'}
                  </button>
                </form>
              )}
            </div>

            {/* Quick Actions */}
            <div className="bg-white rounded-xl shadow-sm p-6">
              <h3 className="text-lg font-semibold text-gray-800 mb-3">
                {user.role === 'KITCHEN_OWNER' ? 'Kitchen Owner Actions' : user.role === 'ADMIN' ? 'Admin Actions' : 'Quick Actions'}
              </h3>
              
              {user.role === 'KITCHEN_OWNER' && (
                <div className="space-y-3">
                  <Link
                    to="/kitchen/dashboard"
                    className="block w-full text-center bg-emerald-600 hover:bg-emerald-700 text-white font-medium py-2.5 px-4 rounded-lg shadow-sm transition"
                  >
                    Open Kitchen Owner Portal →
                  </Link>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <Link
                      to="/kitchen/orders"
                      className="p-2.5 bg-gray-50 hover:bg-emerald-50 rounded-lg text-gray-700 font-medium text-center border border-gray-100 transition"
                    >
                      📦 Live Orders
                    </Link>
                    <Link
                      to="/kitchen/menu"
                      className="p-2.5 bg-gray-50 hover:bg-emerald-50 rounded-lg text-gray-700 font-medium text-center border border-gray-100 transition"
                    >
                      🍲 Menu Items
                    </Link>
                    <Link
                      to="/kitchen/inventory"
                      className="p-2.5 bg-gray-50 hover:bg-emerald-50 rounded-lg text-gray-700 font-medium text-center border border-gray-100 transition"
                    >
                      📊 Inventory Ledger
                    </Link>
                    <Link
                      to="/kitchen/forecast"
                      className="p-2.5 bg-gray-50 hover:bg-emerald-50 rounded-lg text-gray-700 font-medium text-center border border-gray-100 transition"
                    >
                      📈 Demand Forecast
                    </Link>
                  </div>
                </div>
              )}

              {user.role === 'ADMIN' && (
                <div className="space-y-3">
                  <Link
                    to="/admin/dashboard"
                    className="block w-full text-center bg-purple-600 hover:bg-purple-700 text-white font-medium py-2.5 px-4 rounded-lg shadow-sm transition"
                  >
                    Open Admin Portal →
                  </Link>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <Link
                      to="/admin/kitchens"
                      className="p-2.5 bg-gray-50 hover:bg-purple-50 rounded-lg text-gray-700 font-medium text-center border border-gray-100 transition"
                    >
                      🏪 Manage Kitchens
                    </Link>
                    <Link
                      to="/admin/users"
                      className="p-2.5 bg-gray-50 hover:bg-purple-50 rounded-lg text-gray-700 font-medium text-center border border-gray-100 transition"
                    >
                      👥 Manage Users
                    </Link>
                  </div>
                </div>
              )}

              {user.role === 'CUSTOMER' && (
                <div className="space-y-2">
                  <p className="text-sm text-gray-600">
                    Welcome to your Customer Account! You can browse kitchens, place orders, and manage dining preferences.
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
