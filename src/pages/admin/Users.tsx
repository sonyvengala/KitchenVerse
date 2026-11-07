/**
 * Admin Users Page
 * Manage platform users with safe deletion, activation/deactivation, and admin account protections.
 */

import { useState, useEffect } from 'react';
import { adminApi, User } from '../../services/adminApi';
import { useAuth } from '../../hooks/useAuth';
import {
  DataTable,
  Badge,
  Pagination,
  SearchInput,
  FilterSelect,
  PageHeader,
  Card,
  LoadingState,
  ErrorState,
} from '../../components/admin/AdminComponents';
import { Trash2, ShieldAlert, CheckCircle2, AlertCircle, Shield, Archive, Info } from 'lucide-react';
import { useDebounce } from '../../hooks/useDebounce';

export const PROTECTED_REAL_EMAILS = new Set<string>();

export interface UserProtectionInfo {
  isProtected: boolean;
  type: 'self' | 'last_admin' | 'root_admin' | 'system' | null;
  badgeLabel: string | null;
  reason: string | null;
  variant: 'default' | 'warning' | 'success';
}

export const getUserProtection = (
  user: User | null,
  currentUser: any,
  allUsers: User[] = []
): UserProtectionInfo => {
  if (!user) {
    return { isProtected: false, type: null, badgeLabel: null, reason: null, variant: 'default' };
  }

  const cleanEmail = (user.email || '').trim().toLowerCase();

  // 1. Current Authenticated Administrator (Self-protection)
  const isSelf = Boolean(
    user.is_self ||
    (currentUser && (
      user.id === currentUser.id ||
      cleanEmail === (currentUser.email || '').trim().toLowerCase()
    ))
  );
  if (isSelf) {
    return {
      isProtected: true,
      type: 'self',
      badgeLabel: 'Current Admin',
      reason: user.protection_reason || 'Current Administrator (Self-protection: You cannot suspend or delete your currently authenticated account)',
      variant: 'default',
    };
  }

  // 2. Last Active Administrator
  if (user.is_last_admin) {
    return {
      isProtected: true,
      type: 'last_admin',
      badgeLabel: 'Last Active Admin',
      reason: user.protection_reason || 'Last Active Administrator (Platform security policy requires at least one active administrator)',
      variant: 'warning',
    };
  }
  if (user.role === 'ADMIN' && (user.status === 'ACTIVE' || (user as any).is_active)) {
    const activeAdmins = allUsers.filter(
      (u) => u.role === 'ADMIN' && (u.status === 'ACTIVE' || (u as any).is_active)
    );
    if (activeAdmins.length <= 1) {
      return {
        isProtected: true,
        type: 'last_admin',
        badgeLabel: 'Last Active Admin',
        reason: 'Last Active Administrator (Platform security policy requires at least one active administrator)',
        variant: 'warning',
      };
    }
  }

  // 3. Root System Administrator
  if (cleanEmail === 'admin@cloudkitchen.com') {
    return {
      isProtected: true,
      type: 'root_admin',
      badgeLabel: 'Root Admin',
      reason: user.protection_reason || 'Root System Administrator (Primary bootstrap administrator cannot be deleted or suspended)',
      variant: 'success',
    };
  }

  // 4. Genuine Protected System Administrator Accounts (never ordinary customers or kitchen owners)
  if (
    user.role === 'ADMIN' &&
    (user.is_system_account || user.is_protected) &&
    user.protection_reason
  ) {
    return {
      isProtected: true,
      type: 'system',
      badgeLabel: 'Protected System Account',
      reason: user.protection_reason,
      variant: 'success',
    };
  }

  return {
    isProtected: false,
    type: null,
    badgeLabel: null,
    reason: null,
    variant: 'default',
  };
};

export const isUserProtected = (user: User | null): boolean => {
  return getUserProtection(user, null, []).isProtected;
};

export default function AdminUsers() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [skip, setSkip] = useState(0);
  const [limit, setLimit] = useState(50);
  const [search, setSearch] = useState('');
  const debouncedSearch = useDebounce(search, 300);
  const [roleFilter, setRoleFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  // Notifications / feedback
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  // Delete modal state
  const [deleteTarget, setDeleteTarget] = useState<User | null>(null);
  const [deleting, setDeleting] = useState(false);

  const fetchUsers = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await adminApi.getUsers({
        skip,
        limit,
        search: debouncedSearch || undefined,
        role: roleFilter || undefined,
        status: statusFilter || undefined,
      });
      setUsers(data.users);
      setTotal(data.total);
    } catch (err: any) {
      setError(err.detail || err.message || 'Failed to load users');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, [skip, debouncedSearch, roleFilter, statusFilter]);

  const handleStatusUpdate = async (userId: string, newStatus: string) => {
    const targetUser = users.find((u) => u.id === userId);
    if (!targetUser) return;

    const protection = getUserProtection(targetUser, currentUser, users);
    if (protection.isProtected && newStatus !== 'ACTIVE') {
      setActionError(protection.reason || 'Protected accounts cannot be deactivated.');
      setTimeout(() => setActionError(null), 6000);
      return;
    }

    try {
      setActionError(null);
      await adminApi.updateUserStatus(userId, newStatus);
      setActionSuccess(`User '${targetUser.first_name || targetUser.email}' status successfully changed to ${newStatus}.`);
      setTimeout(() => setActionSuccess(null), 4000);
      fetchUsers();
    } catch (err: any) {
      setActionError(err.detail || err.message || 'Failed to update user status');
      setTimeout(() => setActionError(null), 6000);
    }
  };

  const handleConfirmDelete = async () => {
    if (!deleteTarget) return;

    const protection = getUserProtection(deleteTarget, currentUser, users);
    if (protection.isProtected) {
      setActionError(protection.reason || 'Protected accounts cannot be deleted.');
      setDeleteTarget(null);
      setTimeout(() => setActionError(null), 6000);
      return;
    }

    try {
      setDeleting(true);
      setActionError(null);
      const res = await adminApi.deleteUser(deleteTarget.id);
      setActionSuccess(res.message || `User '${deleteTarget.first_name} ${deleteTarget.last_name}' processed successfully.`);
      setTimeout(() => setActionSuccess(null), 5000);
      setDeleteTarget(null);
      fetchUsers();
    } catch (err: any) {
      setActionError(err.detail || err.message || 'Failed to process user account');
      setTimeout(() => setActionError(null), 6000);
      setDeleteTarget(null);
    } finally {
      setDeleting(false);
    }
  };

  const columns = [
    {
      key: 'name',
      header: 'User',
      className: 'min-w-[180px]',
      render: (user: User) => (
        <div className="flex flex-col">
          <div className="font-semibold text-gray-900 leading-tight">
            {user.first_name} {user.last_name}
          </div>
          <div className="text-xs text-gray-500 font-mono truncate max-w-[200px]" title={user.email}>
            {user.email}
          </div>
        </div>
      ),
    },
    {
      key: 'role',
      header: 'Role',
      className: 'w-[120px]',
      render: (user: User) => (
        <Badge variant={user.role === 'ADMIN' ? 'danger' : user.role === 'KITCHEN_OWNER' ? 'info' : 'default'}>
          {user.role.replace('_', ' ')}
        </Badge>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      className: 'w-[100px]',
      render: (user: User) => (
        <Badge variant={user.status === 'ACTIVE' ? 'success' : user.status === 'SUSPENDED' ? 'danger' : 'warning'}>
          {user.status}
        </Badge>
      ),
    },
    {
      key: 'verified',
      header: 'Verified',
      className: 'w-[90px]',
      render: (user: User) => (
        <Badge variant={user.is_email_verified ? 'success' : 'warning'}>
          {user.is_email_verified ? 'Yes' : 'No'}
        </Badge>
      ),
    },
    {
      key: 'created_at',
      header: 'Joined',
      className: 'w-[110px] hidden sm:table-cell',
      render: (user: User) => (
        <span className="text-xs text-gray-600">
          {new Date(user.created_at).toLocaleDateString()}
        </span>
      ),
    },
    {
      key: 'actions',
      header: 'Actions',
      className: 'min-w-[200px] text-right',
      render: (user: User) => {
        const protection = getUserProtection(user, currentUser, users);

        if (protection.isProtected) {
          const badgeStyles =
            protection.variant === 'warning'
              ? 'bg-amber-50 text-amber-800 border-amber-200'
              : protection.variant === 'success'
              ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
              : 'bg-gray-100 text-gray-700 border-gray-200';

          const iconStyles =
            protection.variant === 'warning'
              ? 'text-amber-600'
              : protection.variant === 'success'
              ? 'text-emerald-600'
              : 'text-gray-500';

          return (
            <div className="relative group inline-flex items-center justify-end">
              <span
                className={`inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-md text-xs font-semibold border select-none cursor-help transition-all ${badgeStyles}`}
                title={protection.reason || 'Protected account'}
              >
                <Shield className={`w-3.5 h-3.5 ${iconStyles}`} />
                <span>{protection.badgeLabel}</span>
              </span>

              {/* Exact reason tooltip */}
              <div className="absolute right-0 bottom-full mb-2 hidden group-hover:flex flex-col z-30 w-72 p-2.5 bg-gray-900 text-white text-[11px] rounded-xl shadow-xl border border-gray-700 pointer-events-none text-left">
                <div className="font-bold text-gray-100 flex items-center space-x-1.5 border-b border-gray-700 pb-1 mb-1">
                  <Shield className="w-3.5 h-3.5 text-emerald-400" />
                  <span>{protection.badgeLabel}</span>
                </div>
                <div className="text-gray-300 leading-snug">
                  {protection.reason}
                </div>
              </div>
            </div>
          );
        }

        const isArchive = Boolean(user.has_business_records || user.delete_action_type === 'archive');

        return (
          <div className="flex items-center justify-end space-x-2">
            {user.status === 'ACTIVE' ? (
              <button
                onClick={() => handleStatusUpdate(user.id, 'SUSPENDED')}
                className="px-2.5 py-1 text-xs font-semibold text-amber-700 bg-amber-50 hover:bg-amber-100 border border-amber-200 rounded-lg transition"
                title="Suspend User: Revoke active sessions and deactivate platform access"
              >
                Suspend
              </button>
            ) : (
              <button
                onClick={() => handleStatusUpdate(user.id, 'ACTIVE')}
                className="px-2.5 py-1 text-xs font-semibold text-emerald-700 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 rounded-lg transition"
                title="Activate User: Restore active platform access"
              >
                Activate
              </button>
            )}

            {isArchive ? (
              <button
                onClick={() => setDeleteTarget(user)}
                className="inline-flex items-center space-x-1 px-2.5 py-1 text-xs font-semibold text-purple-700 bg-purple-50 hover:bg-purple-100 border border-purple-200 rounded-lg transition"
                title="Archive User: Safely deactivate and preserve historical orders, payments, and business records"
              >
                <Archive className="w-3.5 h-3.5 text-purple-600" />
                <span>Archive</span>
              </button>
            ) : (
              <button
                onClick={() => setDeleteTarget(user)}
                className="inline-flex items-center space-x-1 px-2.5 py-1 text-xs font-semibold text-red-600 bg-red-50 hover:bg-red-100 border border-red-200 rounded-lg transition"
                title="Delete User: Permanently removes account (no dependent business records)"
              >
                <Trash2 className="w-3.5 h-3.5 text-red-600" />
                <span>Delete</span>
              </button>
            )}
          </div>
        );
      },
    },
  ];

  if (loading && users.length === 0) {
    return <LoadingState />;
  }

  if (error) {
    return <ErrorState message={error} onRetry={fetchUsers} />;
  }

  const isTargetArchival = Boolean(
    deleteTarget && (deleteTarget.has_business_records || deleteTarget.delete_action_type === 'archive')
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title="Users"
        description="Manage customer, kitchen owner, and administrator platform accounts"
      />

      {actionSuccess && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 text-[#166534] rounded-xl text-sm font-semibold flex items-center space-x-2 animate-fade-in">
          <CheckCircle2 className="w-5 h-5 flex-shrink-0" />
          <span>{actionSuccess}</span>
        </div>
      )}

      {actionError && (
        <div className="p-4 bg-red-50 border border-red-200 text-red-700 rounded-xl text-sm font-semibold flex items-center space-x-2 animate-fade-in">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          <span>{actionError}</span>
        </div>
      )}

      <Card>
        <div className="p-6 border-b border-gray-200">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <SearchInput
              value={search}
              onChange={setSearch}
              placeholder="Search by name or email..."
            />
            <FilterSelect
              value={roleFilter}
              onChange={setRoleFilter}
              options={[
                { value: 'CUSTOMER', label: 'Customer' },
                { value: 'KITCHEN_OWNER', label: 'Kitchen Owner' },
                { value: 'ADMIN', label: 'Admin' },
              ]}
              placeholder="All Roles"
            />
            <FilterSelect
              value={statusFilter}
              onChange={setStatusFilter}
              options={[
                { value: 'ACTIVE', label: 'Active' },
                { value: 'SUSPENDED', label: 'Suspended' },
                { value: 'PENDING_VERIFICATION', label: 'Pending' },
              ]}
              placeholder="All Statuses"
            />
          </div>
        </div>

        <div className="overflow-x-auto">
          <DataTable
            columns={columns}
            data={users}
            keyExtractor={(user) => user.id}
            emptyMessage="No users found"
          />
        </div>

        <Pagination
          total={total}
          skip={skip}
          limit={limit}
          onPageChange={setSkip}
        />
      </Card>

      {/* Delete / Archive User Confirmation Modal */}
      {deleteTarget && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-xs flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-gray-100">
            <div className="flex items-start space-x-3 mb-4">
              <div
                className={`p-2.5 rounded-xl ${
                  isTargetArchival ? 'bg-purple-100 text-purple-600' : 'bg-red-100 text-red-600'
                }`}
              >
                {isTargetArchival ? <Archive className="w-6 h-6" /> : <ShieldAlert className="w-6 h-6" />}
              </div>
              <div className="flex-1">
                <h3 className="text-base font-bold text-gray-900">
                  {isTargetArchival ? 'Archive User Account' : 'Delete User Account'}
                </h3>
                <div className="mt-1 p-2.5 bg-gray-50 rounded-xl border border-gray-100 text-xs space-y-0.5">
                  <div className="font-semibold text-gray-900">
                    {deleteTarget.first_name} {deleteTarget.last_name}
                  </div>
                  <div className="text-gray-600 font-mono">{deleteTarget.email}</div>
                  <div className="text-gray-500">
                    Role: <span className="font-medium text-gray-700">{deleteTarget.role}</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="space-y-3 mb-6 text-xs text-gray-600 leading-relaxed">
              {isTargetArchival ? (
                <div className="p-3 bg-purple-50 border border-purple-200 rounded-xl space-y-1.5 text-purple-900">
                  <div className="font-bold flex items-center space-x-1.5 text-purple-800">
                    <Info className="w-4 h-4 text-purple-600 flex-shrink-0" />
                    <span>Historical Business Records Linked</span>
                  </div>
                  <p className="text-purple-700">
                    This account has associated business activity (
                    {deleteTarget.orders_count ? `${deleteTarget.orders_count} customer orders` : ''}
                    {deleteTarget.orders_count && deleteTarget.kitchen_orders ? ', ' : ''}
                    {deleteTarget.kitchen_orders ? `${deleteTarget.kitchen_orders} kitchen orders` : ''}
                    {deleteTarget.reviews_count ? `, ${deleteTarget.reviews_count} reviews` : ''}
                    ).
                  </p>
                  <p className="text-purple-800 font-medium">
                    To preserve financial, tax, and order history, this account will be <strong>safely archived and deactivated</strong>. No historical orders, payments, reviews, or audit logs will be deleted.
                  </p>
                </div>
              ) : (
                <div className="p-3 bg-gray-50 border border-gray-200 rounded-xl space-y-1 text-gray-700">
                  <div className="font-bold text-gray-900">Permanent Deletion Notice:</div>
                  <p>
                    This user account has no associated orders, payments, reviews, or kitchen history. It will be <strong>permanently removed</strong> from the platform.
                  </p>
                </div>
              )}

              <p className="font-semibold text-gray-800">Security & Integrity Protections:</p>
              <ul className="list-disc pl-4 space-y-1 text-gray-600">
                <li>Active administrator self-deletion and last-active-admin deletion are strictly prohibited.</li>
                <li>All sessions for this user will be immediately revoked.</li>
                <li>Action will be recorded in the administrative audit logs.</li>
              </ul>
            </div>

            <div className="flex items-center justify-end space-x-3">
              <button
                type="button"
                onClick={() => setDeleteTarget(null)}
                disabled={deleting}
                className="px-4 py-2 border border-gray-200 text-gray-700 rounded-xl text-xs font-semibold hover:bg-gray-50 transition cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmDelete}
                disabled={deleting}
                className={`px-4 py-2 rounded-xl text-xs font-bold transition flex items-center space-x-1.5 shadow-sm text-white cursor-pointer ${
                  isTargetArchival
                    ? 'bg-purple-600 hover:bg-purple-700'
                    : 'bg-red-600 hover:bg-red-700'
                }`}
              >
                {deleting && <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />}
                <span>{deleting ? 'Processing...' : isTargetArchival ? 'Confirm Archive' : 'Confirm Delete'}</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
