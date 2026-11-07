/**
 * Automated Verification Script for Frontend Role-Based Routing & Utilities.
 * Tests role normalization, canonical dashboards, route guards, and login redirects.
 */
import {
  normalizeRole,
  getRoleDashboardPath,
  isPathAllowedForRole,
  getValidDestinationForRole,
} from '../src/utils/roleUtils';

function assert(condition, message) {
  if (!condition) {
    console.error(`❌ FAILED: ${message}`);
    process.exit(1);
  }
  console.log(`✅ PASSED: ${message}`);
}

console.log('=== 1. ROLE NORMALIZATION TESTS ===');
assert(normalizeRole('ADMIN') === 'ADMIN', 'Normalizes ADMIN');
assert(normalizeRole('admin') === 'ADMIN', 'Normalizes admin (lowercase)');
assert(normalizeRole('KITCHEN_OWNER') === 'KITCHEN_OWNER', 'Normalizes KITCHEN_OWNER');
assert(normalizeRole('kitchen_owner') === 'KITCHEN_OWNER', 'Normalizes kitchen_owner (lowercase)');
assert(normalizeRole('kitchen') === 'KITCHEN_OWNER', 'Normalizes kitchen');
assert(normalizeRole('CUSTOMER') === 'CUSTOMER', 'Normalizes CUSTOMER');
assert(normalizeRole('customer') === 'CUSTOMER', 'Normalizes customer (lowercase)');
assert(normalizeRole(null) === null, 'Handles null role');
assert(normalizeRole(undefined) === null, 'Handles undefined role');

console.log('\n=== 2. CANONICAL DASHBOARD DESTINATIONS ===');
assert(getRoleDashboardPath('ADMIN') === '/admin/dashboard', 'Admin lands on /admin/dashboard');
assert(getRoleDashboardPath('KITCHEN_OWNER') === '/kitchen/dashboard', 'Kitchen Owner lands on /kitchen/dashboard');
assert(getRoleDashboardPath('CUSTOMER') === '/', 'Customer lands on / (canonical)');
assert(getRoleDashboardPath(null) === '/', 'Unauthenticated fallback is /');

console.log('\n=== 3. ROUTE ACCESS BY ROLE ===');
// Admin tests
assert(isPathAllowedForRole('/admin/dashboard', 'ADMIN'), 'Admin allowed on /admin/dashboard');
assert(isPathAllowedForRole('/admin/users', 'ADMIN'), 'Admin allowed on /admin/users');
assert(isPathAllowedForRole('/profile', 'ADMIN'), 'Admin allowed on /profile');
assert(!isPathAllowedForRole('/kitchen/dashboard', 'ADMIN'), 'Admin rejected from /kitchen/dashboard');
assert(!isPathAllowedForRole('/orders', 'ADMIN'), 'Admin rejected from /orders');
assert(!isPathAllowedForRole('/checkout', 'ADMIN'), 'Admin rejected from /checkout');
assert(!isPathAllowedForRole('/cart', 'ADMIN'), 'Admin rejected from /cart');
assert(!isPathAllowedForRole('/', 'ADMIN'), 'Admin rejected from /');

// Kitchen Owner tests
assert(isPathAllowedForRole('/kitchen/dashboard', 'KITCHEN_OWNER'), 'Kitchen Owner allowed on /kitchen/dashboard');
assert(isPathAllowedForRole('/kitchen/menu', 'KITCHEN_OWNER'), 'Kitchen Owner allowed on /kitchen/menu');
assert(isPathAllowedForRole('/profile', 'KITCHEN_OWNER'), 'Kitchen Owner allowed on /profile');
assert(!isPathAllowedForRole('/admin/dashboard', 'KITCHEN_OWNER'), 'Kitchen Owner rejected from /admin/dashboard');
assert(!isPathAllowedForRole('/orders', 'KITCHEN_OWNER'), 'Kitchen Owner rejected from /orders');
assert(!isPathAllowedForRole('/checkout', 'KITCHEN_OWNER'), 'Kitchen Owner rejected from /checkout');
assert(!isPathAllowedForRole('/cart', 'KITCHEN_OWNER'), 'Kitchen Owner rejected from /cart');
assert(!isPathAllowedForRole('/', 'KITCHEN_OWNER'), 'Kitchen Owner rejected from /');

// Customer tests
assert(isPathAllowedForRole('/', 'CUSTOMER'), 'Customer allowed on /');
assert(isPathAllowedForRole('/kitchens', 'CUSTOMER'), 'Customer allowed on /kitchens');
assert(isPathAllowedForRole('/menu', 'CUSTOMER'), 'Customer allowed on /menu');
assert(isPathAllowedForRole('/cart', 'CUSTOMER'), 'Customer allowed on /cart');
assert(isPathAllowedForRole('/orders', 'CUSTOMER'), 'Customer allowed on /orders');
assert(isPathAllowedForRole('/checkout', 'CUSTOMER'), 'Customer allowed on /checkout');
assert(isPathAllowedForRole('/profile', 'CUSTOMER'), 'Customer allowed on /profile');
assert(!isPathAllowedForRole('/admin/dashboard', 'CUSTOMER'), 'Customer rejected from /admin/dashboard');
assert(!isPathAllowedForRole('/kitchen/dashboard', 'CUSTOMER'), 'Customer rejected from /kitchen/dashboard');

console.log('\n=== 4. POST-LOGIN REDIRECT RESOLUTION ===');
// Admin logins
assert(getValidDestinationForRole('/admin/orders', 'ADMIN') === '/admin/orders', 'Admin redirect preserved for admin route');
assert(getValidDestinationForRole('/orders', 'ADMIN') === '/admin/dashboard', 'Admin redirecting from customer route sanitized to admin dashboard');
assert(getValidDestinationForRole('/', 'ADMIN') === '/admin/dashboard', 'Admin redirecting from root sanitized to admin dashboard');
assert(getValidDestinationForRole(undefined, 'ADMIN') === '/admin/dashboard', 'Admin default redirect is admin dashboard');

// Kitchen Owner logins
assert(getValidDestinationForRole('/kitchen/orders', 'KITCHEN_OWNER') === '/kitchen/orders', 'Kitchen Owner redirect preserved for kitchen route');
assert(getValidDestinationForRole('/admin/dashboard', 'KITCHEN_OWNER') === '/kitchen/dashboard', 'Kitchen Owner redirecting from admin route sanitized to kitchen dashboard');
assert(getValidDestinationForRole('/', 'KITCHEN_OWNER') === '/kitchen/dashboard', 'Kitchen Owner redirecting from root sanitized to kitchen dashboard');
assert(getValidDestinationForRole(undefined, 'KITCHEN_OWNER') === '/kitchen/dashboard', 'Kitchen Owner default redirect is kitchen dashboard');

// Customer logins
assert(getValidDestinationForRole('/orders', 'CUSTOMER') === '/orders', 'Customer redirect preserved for customer route');
assert(getValidDestinationForRole('/admin/users', 'CUSTOMER') === '/', 'Customer redirecting from admin route sanitized to root');
assert(getValidDestinationForRole('/kitchen/dashboard', 'CUSTOMER') === '/', 'Customer redirecting from kitchen route sanitized to root');
assert(getValidDestinationForRole(undefined, 'CUSTOMER') === '/', 'Customer default redirect is root');

console.log('\n✨ ALL FRONTEND ROUTING AND ROLE LOGIC TESTS PASSED SUCCESSFULLY!');
