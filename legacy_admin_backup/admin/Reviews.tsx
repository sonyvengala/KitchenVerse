/**
 * Admin Reviews Page
 */

import { useState, useEffect } from 'react';
import { adminApi, Review } from '../../services/adminApi';
import { DataTable, Badge, Pagination, PageHeader, Card, LoadingState, ErrorState } from '../../components/admin/AdminComponents';

export default function AdminReviews() {
  const [reviews, setReviews] = useState<Review[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [skip, setSkip] = useState(0);
  const [limit] = useState(50);

  const fetchReviews = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await adminApi.getReviews({ skip, limit });
      setReviews(data.reviews);
      setTotal(data.total);
    } catch (err: any) {
      setError(err.detail || 'Failed to load reviews');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReviews();
  }, [skip]);

  const columns = [
    {
      key: 'user',
      header: 'Customer',
      render: (r: Review) => r.user ? `${r.user.first_name} ${r.user.last_name}` : 'N/A',
    },
    {
      key: 'kitchen',
      header: 'Kitchen',
      render: (r: Review) => r.kitchen?.kitchen_name || 'N/A',
    },
    {
      key: 'rating',
      header: 'Rating',
      render: (r: Review) => (
        <div className="flex items-center">
          <span className="mr-1">{r.rating}</span>
          <span className="text-yellow-500">{'⭐'.repeat(r.rating)}</span>
        </div>
      ),
    },
    {
      key: 'comment',
      header: 'Comment',
      render: (r: Review) => (
        <div className="max-w-xs truncate">{r.comment || 'No comment'}</div>
      ),
    },
    {
      key: 'is_visible',
      header: 'Visible',
      render: (r: Review) => (
        <Badge variant={r.is_visible ? 'success' : 'default'}>
          {r.is_visible ? 'Yes' : 'No'}
        </Badge>
      ),
    },
    {
      key: 'created_at',
      header: 'Date',
      render: (r: Review) => new Date(r.created_at).toLocaleDateString(),
    },
  ];

  if (loading && reviews.length === 0) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={fetchReviews} />;

  return (
    <div>
      <PageHeader title="Reviews" description="View customer reviews" />
      <Card>
        <DataTable columns={columns} data={reviews} keyExtractor={(r) => r.id} emptyMessage="No reviews found" />
        <Pagination total={total} skip={skip} limit={limit} onPageChange={setSkip} />
      </Card>
    </div>
  );
}
