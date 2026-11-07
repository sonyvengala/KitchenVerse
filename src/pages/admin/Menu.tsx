/**
 * Admin Menu Items Page
 */

import { useState, useEffect } from 'react';
import { adminApi, MenuItem } from '../../services/adminApi';
import { DataTable, Badge, Pagination, SearchInput, PageHeader, Card, LoadingState, ErrorState } from '../../components/admin/AdminComponents';
import { formatINR } from '../../utils/currency';

export default function AdminMenu() {
  const [items, setItems] = useState<MenuItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [skip, setSkip] = useState(0);
  const [limit] = useState(50);
  const [search, setSearch] = useState('');

  const fetchItems = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await adminApi.getMenuItems({ skip, limit, search: search || undefined });
      setItems(data.items);
      setTotal(data.total);
    } catch (err: any) {
      setError(err.detail || 'Failed to load menu items');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchItems();
  }, [skip, search]);

  const columns = [
    {
      key: 'name',
      header: 'Item',
      render: (item: MenuItem) => (
        <div>
          <div className="font-medium">{item.name}</div>
          {item.description && (
            <div className="text-xs text-gray-500 truncate max-w-xs">{item.description}</div>
          )}
        </div>
      ),
    },
    {
      key: 'kitchen',
      header: 'Kitchen',
      render: (item: MenuItem) => item.kitchen?.kitchen_name || 'N/A',
    },
    {
      key: 'price',
      header: 'Price',
      render: (item: MenuItem) => <span className="font-semibold text-gray-900">{formatINR(item.price)}</span>,
    },
    {
      key: 'is_available',
      header: 'Status',
      render: (item: MenuItem) => (
        <Badge variant={item.is_available ? 'success' : 'default'}>
          {item.is_available ? 'Available' : 'Unavailable'}
        </Badge>
      ),
    },
    {
      key: 'created_at',
      header: 'Created',
      render: (item: MenuItem) => new Date(item.created_at).toLocaleDateString(),
    },
  ];

  if (loading && items.length === 0) {
    return <LoadingState />;
  }

  if (error) {
    return <ErrorState message={error} onRetry={fetchItems} />;
  }

  return (
    <div>
      <PageHeader title="Menu Items" description="View all menu items across kitchens" />

      <Card>
        <div className="p-6 border-b border-gray-200">
          <SearchInput value={search} onChange={setSearch} placeholder="Search menu items..." />
        </div>

        <DataTable columns={columns} data={items} keyExtractor={(i) => i.id} emptyMessage="No menu items found" />

        <Pagination total={total} skip={skip} limit={limit} onPageChange={setSkip} />
      </Card>
    </div>
  );
}
