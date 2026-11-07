/**
 * Root Route component for the "/" path.
 * Dispatches visitors based on authoritative authentication and role state:
 * - Loading: Branded loading state (no customer features rendered).
 * - Unauthenticated: Public customer landing page.
 * - CUSTOMER: Customer home.
 * - KITCHEN_OWNER: Kitchen Owner dashboard (/kitchen/dashboard).
 * - ADMIN: Admin dashboard (/admin/dashboard).
 */
import { Navigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import CustomerHome from '../../pages/customer/Home';
import { normalizeRole } from '../../utils/roleUtils';

export default function RootRoute() {
  const { isAuthenticated, isLoading, user } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#FFFDF8]">
        <div className="flex flex-col items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#166534] to-[#15803d] flex items-center justify-center text-white shadow-xs animate-pulse">
            <span className="text-lg font-black text-amber-300">CK</span>
          </div>
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-orange-600 mt-2"></div>
          <span className="text-sm font-semibold text-gray-600">Restoring session...</span>
        </div>
      </div>
    );
  }

  if (isAuthenticated && user) {
    const role = normalizeRole(user.role);
    if (role === 'KITCHEN_OWNER') {
      return <Navigate to="/kitchen/dashboard" replace />;
    }
    if (role === 'ADMIN') {
      return <Navigate to="/admin/dashboard" replace />;
    }
    // CUSTOMER role
    return <CustomerHome />;
  }

  // Unauthenticated visitor -> public customer landing experience
  return <CustomerHome />;
}
