/**
 * Admin Promotions Page
 */

import { useState, useEffect } from 'react';
import { adminApi, Promotion } from '../../services/adminApi';
import { DataTable, Badge, Pagination, FilterSelect, PageHeader, Card, LoadingState, ErrorState } from '../../components/admin/AdminComponents';

export default function AdminPromotions() {
  const [promotions, setPromotions] = useState<Promotion[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [skip, setSkip] = useState(0);
  const [limit] = useState(50);
  const [activeFilter, setActiveFilter] = useState('');

  const fetchPromotions = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await adminApi.getPromotions({
        skip,
        limit,
        active: activeFilter === 'active' ? true : activeFilter === 'inactive' ? false : undefined,
      });
      setPromotions(data.promotions);
      setTotal(data.total);
    } catch (err: any) {
      setError(err.detail || 'Failed to load promotions');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPromotions();
  }, [skip, activeFilter]);

  const columns = [
    {
      key: 'code',
      header: 'Code',
      render: (p: Promotion) => <span className="font-mono font-bold">{p.code}</span>,
    },
    {
      key: 'promotion_type',
      header: 'Type',
      render: (p: Promotion) => p.promotion_type.replace('_', ' '),
    },
    {
      key: 'discount_value',
      header: 'Discount',
      render: (p: Promotion) => p.promotion_type === 'PERCENTAGE' ? `${p.discount_value}%` : `$${p.discount_value.toFixed(2)}`,
    },
    {
      key: 'is_active',
      header: 'Status',
      render: (p: Promotion) => (
        <Badge variant={p.is_active ? 'success' : 'default'}>
          {p.is_active ? 'Active' : 'Inactive'}
        </Badge>
      ),
    },
    {
      key: 'usage',
      header: 'Usage',
      render: (p: Promotion) => `${p.usage_count}${p.usage_limit ? ` / ${p.usage_limit}` : ''}`,
    },
    {
      key: 'expires_at',
      header: 'Expires',
      render: (p: Promotion) => new Date(p.expires_at).toLocaleDateString(),
    },
  ];

  if (loading && promotions.length === 0) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={fetchPromotions} />;

  return (
    <div>
      <PageHeader title="Promotions" description="Manage promotional offers" />
      <Card>
        <div className="p-6 border-b border-gray-200">
          <FilterSelect
            value={activeFilter}
            onChange={setActiveFilter}
            options={[
              { value: 'active', label: 'Active' },
              { value: 'inactive', label: 'Inactive' },
            ]}
            placeholder="All Promotions"
          />
        </div>
        <DataTable columns={columns} data={promotions} keyExtractor={(p) => p.id} emptyMessage="No promotions found" />
        <Pagination total={total} skip={skip} limit={limit} onPageChange={setSkip} />
      </Card>
    </div>
  );
}
