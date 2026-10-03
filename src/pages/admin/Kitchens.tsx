/**
 * Admin Kitchens Page
 */

import { useState, useEffect } from 'react';
import { adminApi, Kitchen } from '../../services/adminApi';
import { DataTable, Badge, Pagination, SearchInput, PageHeader, Card, LoadingState, ErrorState } from '../../components/admin/AdminComponents';

export default function AdminKitchens() {
  const [kitchens, setKitchens] = useState<Kitchen[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [skip, setSkip] = useState(0);
  const [limit] = useState(50);
  const [search, setSearch] = useState('');

  const fetchKitchens = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await adminApi.getKitchens({ skip, limit, search: search || undefined });
      setKitchens(data.kitchens);
      setTotal(data.total);
    } catch (err: any) {
      setError(err.detail || 'Failed to load kitchens');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchKitchens();
  }, [skip, search]);

  const columns = [
    {
      key: 'kitchen_name',
      header: 'Kitchen Name',
      render: (kitchen: Kitchen) => (
        <div>
          <div className="font-medium">{kitchen.kitchen_name}</div>
          {kitchen.description && (
            <div className="text-xs text-gray-500 truncate max-w-xs">{kitchen.description}</div>
          )}
        </div>
      ),
    },
    {
      key: 'owner',
      header: 'Owner',
      render: (kitchen: Kitchen) => kitchen.owner ? (
        <div>
          <div>{kitchen.owner.first_name} {kitchen.owner.last_name}</div>
          <div className="text-xs text-gray-500">{kitchen.owner.email}</div>
        </div>
      ) : 'N/A',
    },
    {
      key: 'is_verified',
      header: 'Verified',
      render: (kitchen: Kitchen) => (
        <Badge variant={kitchen.is_verified ? 'success' : 'warning'}>
          {kitchen.is_verified ? 'Yes' : 'No'}
        </Badge>
      ),
    },
    {
      key: 'rating',
      header: 'Rating',
      render: (kitchen: Kitchen) => kitchen.rating ? `${kitchen.rating.toFixed(1)} ⭐` : 'N/A',
    },
    {
      key: 'total_reviews',
      header: 'Reviews',
      render: (kitchen: Kitchen) => kitchen.total_reviews,
    },
    {
      key: 'created_at',
      header: 'Created',
      render: (kitchen: Kitchen) => new Date(kitchen.created_at).toLocaleDateString(),
    },
  ];

  if (loading && kitchens.length === 0) {
    return <LoadingState />;
  }

  if (error) {
    return <ErrorState message={error} onRetry={fetchKitchens} />;
  }

  return (
    <div>
      <PageHeader title="Kitchens" description="Manage registered kitchens" />

      <Card>
        <div className="p-6 border-b border-gray-200">
          <SearchInput value={search} onChange={setSearch} placeholder="Search kitchens..." />
        </div>

        <DataTable columns={columns} data={kitchens} keyExtractor={(k) => k.id} emptyMessage="No kitchens found" />

        <Pagination total={total} skip={skip} limit={limit} onPageChange={setSkip} />
      </Card>
    </div>
  );
}
