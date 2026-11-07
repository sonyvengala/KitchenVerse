/**
 * Protected route component.
 * Redirects to login if not authenticated.
 * Optionally checks for specific roles.
 */
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { UserRole } from '../types';
import { normalizeRole, getRoleDashboardPath } from '../utils/roleUtils';

interface ProtectedRouteProps {
  children: React.ReactNode;
  allowedRoles?: UserRole[];
}

export default function ProtectedRoute({ children, allowedRoles }: ProtectedRouteProps) {
  const { isAuthenticated, isLoading, user } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#FFFDF8]">
        <div className="flex flex-col items-center gap-3">
          <div className="w-12 h-12 bg-[#166534] rounded-2xl flex items-center justify-center shadow-md animate-pulse">
            <span className="text-amber-300 font-black text-xl">KV</span>
          </div>
          <div className="text-center">
            <p className="text-base font-black text-gray-900 leading-none">
              Kitchen<span className="text-[#F97316]">Verse</span>
            </p>
            <p className="text-[10px] text-gray-500 font-semibold tracking-tight mt-1">
              Multiple Kitchens. One Destination.
            </p>
          </div>
          <div className="animate-spin rounded-full h-5 w-5 border-2 border-[#166534] border-t-transparent mt-1"></div>
        </div>
      </div>
    );
  }

  if (!isAuthenticated || !user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  const userRole = normalizeRole(user.role);

  if (allowedRoles && allowedRoles.length > 0) {
    const isAllowed = userRole && allowedRoles.some((r) => normalizeRole(r) === userRole);
    if (!isAllowed) {
      // Redirect unauthorized users to their authoritative portal instead of an error wall
      const targetPath = getRoleDashboardPath(userRole);
      return <Navigate to={targetPath} replace />;
    }
  }

  return <>{children}</>;
}
