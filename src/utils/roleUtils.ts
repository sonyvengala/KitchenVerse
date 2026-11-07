/**
 * Role-Based Access Control and Route Utilities.
 * Provides role normalization, canonical destination mapping, and route access validation.
 */
import { UserRole } from '../types';

/**
 * Normalizes an arbitrary role string to a canonical UserRole enum value.
 */
export function normalizeRole(role?: string | null): UserRole | null {
  if (!role) return null;
  const upper = role.toUpperCase().trim();
  if (upper === 'ADMIN') return 'ADMIN';
  if (upper === 'KITCHEN_OWNER' || upper === 'KITCHEN') return 'KITCHEN_OWNER';
  if (upper === 'CUSTOMER') return 'CUSTOMER';
  return null;
}

/**
 * Returns the canonical portal path for a given role.
 */
export function getRoleDashboardPath(role?: UserRole | string | null): string {
  const norm = normalizeRole(role);
  if (norm === 'ADMIN') return '/admin/dashboard';
  if (norm === 'KITCHEN_OWNER') return '/kitchen/dashboard';
  return '/';
}

/**
 * Helper to identify Kitchen Owner portal paths (excluding customer /kitchens).
 */
export function isKitchenPortalPath(path: string): boolean {
  return (
    path === '/kitchen' ||
    path.startsWith('/kitchen/') ||
    path === '/kitchen-owner' ||
    path.startsWith('/kitchen-owner/')
  );
}

/**
 * Helper to identify Admin portal paths.
 */
export function isAdminPortalPath(path: string): boolean {
  return path === '/admin' || path.startsWith('/admin/');
}

/**
 * Checks whether a given path is valid for a given role.
 */
export function isPathAllowedForRole(path: string, role?: UserRole | string | null): boolean {
  if (!path) return false;
  const norm = normalizeRole(role);
  if (!norm) return false;

  // Profile is shared by all authenticated roles
  if (path === '/profile' || path.startsWith('/profile/')) {
    return true;
  }

  if (norm === 'ADMIN') {
    return isAdminPortalPath(path);
  }

  if (norm === 'KITCHEN_OWNER') {
    return isKitchenPortalPath(path);
  }

  if (norm === 'CUSTOMER') {
    // Customers can access public and customer features, but NOT admin or kitchen owner portals
    if (isAdminPortalPath(path) || isKitchenPortalPath(path)) {
      return false;
    }
    return true;
  }

  return false;
}

/**
 * Resolves the destination after login, ensuring users never enter a forbidden portal.
 */
export function getValidDestinationForRole(targetPath: string | undefined | null, role?: UserRole | string | null): string {
  const norm = normalizeRole(role);
  if (targetPath && isPathAllowedForRole(targetPath, norm)) {
    return targetPath;
  }
  return getRoleDashboardPath(norm);
}
