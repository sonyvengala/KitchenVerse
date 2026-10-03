/**
 * Admin Waste Management Page
 */

import { useState, useEffect } from 'react';
import { adminApi, WasteRecord } from '../../services/adminApi';
import { DataTable, Pagination, PageHeader, Card, LoadingState, ErrorState } from '../../components/admin/AdminComponents';

export default function AdminWaste() {
  const [wasteRecords, setWasteRecords] = useState<WasteRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [skip, setSkip] = useState(0);
  const [limit] = useState(50);

  const fetchWaste = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await adminApi.getWasteRecords({ skip, limit });
      setWasteRecords(data.waste_records);
      setTotal(data.total);
    } catch (err: any) {
      setError(err.detail || 'Failed to load waste records');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchWaste();
  }, [skip]);

  const columns = [
    {
      key: 'kitchen',
      header: 'Kitchen',
      render: (w: WasteRecord) => w.kitchen?.kitchen_name || 'N/A',
    },
    {
      key: 'ingredient',
      header: 'Ingredient',
      render: (w: WasteRecord) => w.ingredient ? (
        <div>
          <div className="font-medium">{w.ingredient.name}</div>
          <div className="text-xs text-gray-500">{w.ingredient.unit}</div>
        </div>
      ) : 'N/A',
    },
    {
      key: 'quantity',
      header: 'Quantity',
      render: (w: WasteRecord) => w.quantity.toFixed(2),
    },
    {
      key: 'reason',
      header: 'Reason',
      render: (w: WasteRecord) => w.reason || 'Not specified',
    },
    {
      key: 'cost',
      header: 'Cost',
      render: (w: WasteRecord) => `$${w.cost.toFixed(2)}`,
    },
    {
      key: 'recorded_at',
      header: 'Date',
      render: (w: WasteRecord) => new Date(w.recorded_at).toLocaleDateString(),
    },
  ];

  if (loading && wasteRecords.length === 0) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={fetchWaste} />;

  return (
    <div>
      <PageHeader title="Waste Management" description="Track and analyze kitchen waste" />
      <Card>
        <DataTable columns={columns} data={wasteRecords} keyExtractor={(w) => w.id} emptyMessage="No waste records found" />
        <Pagination total={total} skip={skip} limit={limit} onPageChange={setSkip} />
      </Card>
    </div>
  );
}
