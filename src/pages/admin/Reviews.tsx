/**
 * Admin Reviews Page
 * View customer reviews across all kitchens with ratings, orders, dishes, and comments.
 */

import { useState, useEffect } from 'react';
import { adminApi, Review, Kitchen } from '../../services/adminApi';
import {
  DataTable,
  Badge,
  Pagination,
  PageHeader,
  Card,
  LoadingState,
  ErrorState,
} from '../../components/admin/AdminComponents';

export default function AdminReviews() {
  const [reviews, setReviews] = useState<Review[]>([]);
  const [total, setTotal] = useState(0);
  const [kitchens, setKitchens] = useState<Kitchen[]>([]);
  const [selectedKitchenId, setSelectedKitchenId] = useState<string>('');
  const [minRating, setMinRating] = useState<number | undefined>(undefined);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [skip, setSkip] = useState(0);
  const [limit] = useState(50);

  // Load kitchens for filtering
  useEffect(() => {
    adminApi.getKitchens()
      .then((res) => setKitchens(res.kitchens || []))
      .catch((err) => console.error('Failed to load kitchens for reviews filter:', err));
  }, []);

  const fetchReviews = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await adminApi.getReviews({
        skip,
        limit,
        kitchen_id: selectedKitchenId || undefined,
        min_rating: minRating,
      });
      setReviews(data.reviews || []);
      setTotal(data.total || 0);
    } catch (err: any) {
      setError(err?.detail || err?.message || 'Failed to load reviews');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReviews();
  }, [skip, selectedKitchenId, minRating]);

  const columns = [
    {
      key: 'customer',
      header: 'Customer',
      render: (r: Review) => {
        const name = r.user
          ? `${r.user.first_name} ${r.user.last_name}`.trim()
          : (r.customer?.name || 'Anonymous');
        return (
          <div>
            <div className="font-semibold text-gray-900">{name}</div>
            {r.user?.email && (
              <div className="text-[11px] text-gray-400">{r.user.email}</div>
            )}
          </div>
        );
      },
    },
    {
      key: 'kitchen',
      header: 'Kitchen',
      render: (r: Review) => (
        <span className="font-medium text-gray-800">
          {r.kitchen?.kitchen_name || r.kitchen?.name || 'N/A'}
        </span>
      ),
    },
    {
      key: 'order',
      header: 'Order Ref',
      render: (r: Review) => {
        const ordRef = r.order?.order_number || r.order_number;
        return ordRef ? (
          <span className="font-mono text-xs text-gray-600 bg-gray-50 px-2 py-0.5 rounded border border-gray-200">
            {ordRef}
          </span>
        ) : (
          <span className="text-gray-400 text-xs">—</span>
        );
      },
    },
    {
      key: 'menu_item',
      header: 'Dish / Item',
      render: (r: Review) => {
        const dish = r.menu_item?.name || r.menu_item_name;
        return dish ? (
          <span className="font-medium text-gray-900">{dish}</span>
        ) : (
          <span className="text-xs text-gray-400 italic">Order Review</span>
        );
      },
    },
    {
      key: 'rating',
      header: 'Rating',
      render: (r: Review) => {
        const stars = Math.max(1, Math.min(5, r.rating || 0));
        return (
          <div className="flex items-center space-x-1.5">
            <span className="font-bold text-gray-900 text-sm">{r.rating}</span>
            <span className="text-amber-400 text-xs">{'⭐'.repeat(stars)}</span>
          </div>
        );
      },
    },
    {
      key: 'comment',
      header: 'Review Comment',
      render: (r: Review) => (
        <div className="max-w-xs text-gray-700 text-xs" title={r.comment || ''}>
          {r.comment || <span className="text-gray-400 italic">No comment provided</span>}
        </div>
      ),
    },
    {
      key: 'is_visible',
      header: 'Visible',
      render: (r: Review) => (
        <Badge variant={r.is_visible ? 'success' : 'default'}>
          {r.is_visible ? 'Visible' : 'Hidden'}
        </Badge>
      ),
    },
    {
      key: 'created_at',
      header: 'Date',
      render: (r: Review) => (
        <span className="text-xs text-gray-500 whitespace-nowrap">
          {r.created_at ? new Date(r.created_at).toLocaleDateString() : 'N/A'}
        </span>
      ),
    },
  ];

  if (loading && reviews.length === 0) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={fetchReviews} />;

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <PageHeader title="Customer Reviews" description="Monitor customer feedback and ratings across all KitchenVerse kitchens" />

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center space-x-2">
            <label htmlFor="kitchen-filter" className="text-xs font-semibold text-gray-600">
              Kitchen:
            </label>
            <select
              id="kitchen-filter"
              value={selectedKitchenId}
              onChange={(e) => {
                setSelectedKitchenId(e.target.value);
                setSkip(0);
              }}
              className="px-3 py-2 bg-white border border-gray-300 rounded-lg text-xs font-medium focus:ring-orange-500 focus:border-orange-500"
            >
              <option value="">All Kitchens</option>
              {kitchens.map((k) => (
                <option key={k.id} value={k.id}>
                  {k.kitchen_name}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center space-x-2">
            <label htmlFor="rating-filter" className="text-xs font-semibold text-gray-600">
              Rating:
            </label>
            <select
              id="rating-filter"
              value={minRating === undefined ? '' : minRating.toString()}
              onChange={(e) => {
                const val = e.target.value;
                setMinRating(val === '' ? undefined : Number(val));
                setSkip(0);
              }}
              className="px-3 py-2 bg-white border border-gray-300 rounded-lg text-xs font-medium focus:ring-orange-500 focus:border-orange-500"
            >
              <option value="">All Ratings</option>
              <option value="5">5 Stars only</option>
              <option value="4">4+ Stars</option>
              <option value="3">3+ Stars</option>
              <option value="2">2+ Stars</option>
              <option value="1">1+ Stars</option>
            </select>
          </div>
        </div>
      </div>

      <Card>
        <DataTable
          columns={columns}
          data={reviews}
          keyExtractor={(r) => r.id}
          emptyMessage="No reviews yet"
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
