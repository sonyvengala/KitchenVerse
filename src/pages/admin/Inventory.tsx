/**
 * Admin Inventory Page
 */

import { useState, useEffect } from 'react';
import { adminApi, InventoryItem } from '../../services/adminApi';
import { DataTable, Badge, Pagination, FilterSelect, PageHeader, Card, LoadingState, ErrorState } from '../../components/admin/AdminComponents';

export default function AdminInventory() {
  const [inventory, setInventory] = useState<InventoryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [skip, setSkip] = useState(0);
  const [limit] = useState(50);
  const [stockFilter, setStockFilter] = useState('');

  const fetchInventory = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await adminApi.getInventory({
        skip,
        limit,
        low_stock: stockFilter === 'low' ? true : stockFilter === 'normal' ? false : undefined,
      });
      setInventory(data.inventory);
      setTotal(data.total);
    } catch (err: any) {
      setError(err.detail || 'Failed to load inventory');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchInventory();
  }, [skip, stockFilter]);

  const columns = [
    {
      key: 'ingredient',
      header: 'Ingredient',
      render: (item: InventoryItem) => item.ingredient ? (
        <div>
          <div className="font-medium">{item.ingredient.name}</div>
          <div className="text-xs text-gray-500">{item.ingredient.unit}</div>
        </div>
      ) : 'N/A',
    },
    {
      key: 'kitchen',
      header: 'Kitchen',
      render: (item: InventoryItem) => item.kitchen?.kitchen_name || 'N/A',
    },
    {
      key: 'quantity_on_hand',
      header: 'Quantity',
      render: (item: InventoryItem) => item.quantity_on_hand.toFixed(2),
    },
    {
      key: 'min_quantity',
      header: 'Min Stock',
      render: (item: InventoryItem) => item.min_quantity.toFixed(2),
    },
    {
      key: 'status',
      header: 'Status',
      render: (item: InventoryItem) => {
        const isLow = item.quantity_on_hand <= item.min_quantity;
        return (
          <Badge variant={isLow ? 'danger' : 'success'}>
            {isLow ? 'Low Stock' : 'Normal'}
          </Badge>
        );
      },
    },
    {
      key: 'unit_cost',
      header: 'Unit Cost',
      render: (item: InventoryItem) => `$${item.unit_cost.toFixed(2)}`,
    },
  ];

  if (loading && inventory.length === 0) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={fetchInventory} />;

  return (
    <div>
      <PageHeader title="Inventory" description="Monitor stock levels across kitchens" />
      <Card>
        <div className="p-6 border-b border-gray-200">
          <FilterSelect
            value={stockFilter}
            onChange={setStockFilter}
            options={[
              { value: 'low', label: 'Low Stock' },
              { value: 'normal', label: 'Normal Stock' },
            ]}
            placeholder="All Stock Levels"
          />
        </div>
        <DataTable columns={columns} data={inventory} keyExtractor={(i) => i.id} emptyMessage="No inventory items found" />
        <Pagination total={total} skip={skip} limit={limit} onPageChange={setSkip} />
      </Card>
    </div>
  );
}
