/**
 * Admin Kitchen Owners Page
 */

import { useState, useEffect } from 'react';
import { adminApi } from '../../services/adminApi';
import { DataTable, Badge, Pagination, SearchInput, PageHeader, Card, LoadingState, ErrorState } from '../../components/admin/AdminComponents';

export default function AdminKitchenOwners() {
  const [owners, setOwners] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [skip, setSkip] = useState(0);
  const [limit] = useState(50);
  const [search, setSearch] = useState('');

  const fetchOwners = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await adminApi.getKitchenOwners({ skip, limit, search: search || undefined });
      setOwners(data.kitchens);
      setTotal(data.total);
    } catch (err: any) {
      setError(err.detail || 'Failed to load kitchen owners');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOwners();
  }, [skip, search]);

  const columns = [
    {
      key: 'name',
      header: 'Owner',
      render: (owner: any) => (
        <div>
          <div className="font-medium">{owner.first_name} {owner.last_name}</div>
          <div className="text-xs text-gray-500">{owner.email}</div>
        </div>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (owner: any) => (
        <Badge variant={owner.status === 'ACTIVE' ? 'success' : 'warning'}>
          {owner.status}
        </Badge>
      ),
    },
    {
      key: 'verified',
      header: 'Email Verified',
      render: (owner: any) => (
        <Badge variant={owner.is_email_verified ? 'success' : 'warning'}>
          {owner.is_email_verified ? 'Yes' : 'No'}
        </Badge>
      ),
    },
    {
      key: 'created_at',
      header: 'Joined',
      render: (owner: any) => new Date(owner.created_at).toLocaleDateString(),
    },
  ];

  if (loading && owners.length === 0) {
    return <LoadingState />;
  }

  if (error) {
    return <ErrorState message={error} onRetry={fetchOwners} />;
  }

  return (
    <div>
      <PageHeader title="Kitchen Owners" description="Manage kitchen owner accounts" />

      <Card>
        <div className="p-6 border-b border-gray-200">
          <SearchInput value={search} onChange={setSearch} placeholder="Search owners..." />
        </div>

        <DataTable columns={columns} data={owners} keyExtractor={(o) => o.id} emptyMessage="No kitchen owners found" />

        <Pagination total={total} skip={skip} limit={limit} onPageChange={setSkip} />
      </Card>
    </div>
  );
}
