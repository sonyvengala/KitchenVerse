/**
 * Admin Users Page
 */

import { useState, useEffect } from 'react';
import { adminApi, User } from '../../services/adminApi';
import { DataTable, Badge, Pagination, SearchInput, FilterSelect, PageHeader, Card, LoadingState, ErrorState } from '../../components/admin/AdminComponents';

export default function AdminUsers() {
  const [users, setUsers] = useState<User[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [skip, setSkip] = useState(0);
  const [limit] = useState(50);
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  const fetchUsers = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await adminApi.getUsers({
        skip,
        limit,
        search: search || undefined,
        role: roleFilter || undefined,
        status: statusFilter || undefined,
      });
      setUsers(data.users);
      setTotal(data.total);
    } catch (err: any) {
      setError(err.detail || 'Failed to load users');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, [skip, search, roleFilter, statusFilter]);

  const handleStatusUpdate = async (userId: string, newStatus: string) => {
    try {
      await adminApi.updateUserStatus(userId, newStatus);
      fetchUsers();
    } catch (err: any) {
      alert(err.detail || 'Failed to update user status');
    }
  };

  const columns = [
    {
      key: 'name',
      header: 'Name',
      render: (user: User) => (
        <div>
          <div className="font-medium">{user.first_name} {user.last_name}</div>
          <div className="text-xs text-gray-500">{user.email}</div>
        </div>
      ),
    },
    {
      key: 'role',
      header: 'Role',
      render: (user: User) => (
        <Badge variant={user.role === 'ADMIN' ? 'danger' : user.role === 'KITCHEN_OWNER' ? 'info' : 'default'}>
          {user.role.replace('_', ' ')}
        </Badge>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (user: User) => (
        <Badge variant={user.status === 'ACTIVE' ? 'success' : user.status === 'SUSPENDED' ? 'danger' : 'warning'}>
          {user.status}
        </Badge>
      ),
    },
    {
      key: 'verified',
      header: 'Verified',
      render: (user: User) => (
        <Badge variant={user.is_email_verified ? 'success' : 'warning'}>
          {user.is_email_verified ? 'Yes' : 'No'}
        </Badge>
      ),
    },
    {
      key: 'created_at',
      header: 'Joined',
      render: (user: User) => new Date(user.created_at).toLocaleDateString(),
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (user: User) => (
        <div className="flex space-x-2">
          {user.status === 'ACTIVE' ? (
            <button
              onClick={() => handleStatusUpdate(user.id, 'SUSPENDED')}
              className="text-xs text-red-600 hover:text-red-800"
            >
              Suspend
            </button>
          ) : (
            <button
              onClick={() => handleStatusUpdate(user.id, 'ACTIVE')}
              className="text-xs text-green-600 hover:text-green-800"
            >
              Activate
            </button>
          )}
        </div>
      ),
    },
  ];

  if (loading && users.length === 0) {
    return <LoadingState />;
  }

  if (error) {
    return <ErrorState message={error} onRetry={fetchUsers} />;
  }

  return (
    <div>
      <PageHeader
        title="Users"
        description="Manage platform users"
      />

      <Card>
        <div className="p-6 border-b border-gray-200">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <SearchInput
              value={search}
              onChange={setSearch}
              placeholder="Search users..."
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

        <DataTable
          columns={columns}
          data={users}
          keyExtractor={(user) => user.id}
          emptyMessage="No users found"
        />

        <Pagination
          total={total}
          skip={skip}
          limit={limit}
          onPageChange={setSkip}
        />
      </Card>
    </div>
  );
}
