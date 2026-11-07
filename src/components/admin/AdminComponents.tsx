/**
 * Reusable Admin Components
 */

import { ReactNode } from 'react';

// =============================================
// STAT CARD
// =============================================

interface StatCardProps {
  title: string;
  value: string | number;
  icon?: string;
  color?: string;
  subtitle?: string;
}

export function StatCard({ title, value, icon, color = 'bg-blue-500', subtitle }: StatCardProps) {
  return (
    <div className="bg-white rounded-lg shadow-sm p-6">
      <div className="flex items-center justify-between">
        <div className="flex-1">
          <p className="text-sm font-medium text-gray-500 mb-1">{title}</p>
          <p className="text-2xl font-bold text-gray-900">{value}</p>
          {subtitle && <p className="text-xs text-gray-400 mt-1">{subtitle}</p>}
        </div>
        {icon && (
          <div className={`${color} w-12 h-12 rounded-lg flex items-center justify-center text-2xl`}>
            {icon}
          </div>
        )}
      </div>
    </div>
  );
}

// =============================================
// EMPTY STATE
// =============================================

interface EmptyStateProps {
  icon?: string;
  title: string;
  description?: string;
}

export function EmptyState({ icon = '📭', title, description }: EmptyStateProps) {
  return (
    <div className="text-center py-12">
      <div className="text-6xl mb-4">{icon}</div>
      <h3 className="text-lg font-medium text-gray-900 mb-2">{title}</h3>
      {description && <p className="text-sm text-gray-500">{description}</p>}
    </div>
  );
}

// =============================================
// LOADING STATE
// =============================================

export function LoadingState() {
  return (
    <div className="flex items-center justify-center py-12">
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-orange-600"></div>
    </div>
  );
}

// =============================================
// ERROR STATE
// =============================================

interface ErrorStateProps {
  message?: string;
  onRetry?: () => void;
}

export function ErrorState({ message = 'Failed to load data', onRetry }: ErrorStateProps) {
  return (
    <div className="text-center py-12">
      <div className="text-6xl mb-4">⚠️</div>
      <h3 className="text-lg font-medium text-gray-900 mb-2">Error</h3>
      <p className="text-sm text-gray-500 mb-4">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700 transition-colors"
        >
          Retry
        </button>
      )}
    </div>
  );
}

// =============================================
// DATA TABLE
// =============================================

interface Column<T> {
  key: string;
  header: ReactNode;
  render?: (item: T) => ReactNode;
  className?: string;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  keyExtractor: (item: T) => string;
  emptyMessage?: string;
}

export function DataTable<T>({ columns, data, keyExtractor, emptyMessage = 'No data available' }: DataTableProps<T>) {
  if (data.length === 0) {
    return <EmptyState title={emptyMessage} />;
  }

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            {columns.map((col) => (
              <th
                key={col.key}
                className={`px-4 sm:px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider ${col.className || ''}`}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {data.map((item) => (
            <tr key={keyExtractor(item)} className="hover:bg-gray-50/80 transition-colors">
              {columns.map((col) => (
                <td key={col.key} className={`px-4 sm:px-6 py-3 text-sm text-gray-900 ${col.className || ''}`}>
                  {col.render ? col.render(item) : (item as any)[col.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// =============================================
// BADGE
// =============================================

interface BadgeProps {
  children: ReactNode;
  variant?: 'success' | 'warning' | 'danger' | 'info' | 'default';
}

export function Badge({ children, variant = 'default' }: BadgeProps) {
  const variants = {
    success: 'bg-green-100 text-green-800',
    warning: 'bg-yellow-100 text-yellow-800',
    danger: 'bg-red-100 text-red-800',
    info: 'bg-blue-100 text-blue-800',
    default: 'bg-gray-100 text-gray-800',
  };

  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${variants[variant]}`}>
      {children}
    </span>
  );
}

// =============================================
// PAGINATION
// =============================================

interface PaginationProps {
  total: number;
  skip: number;
  limit: number;
  onPageChange: (skip: number) => void;
}

export function Pagination({ total, skip, limit, onPageChange }: PaginationProps) {
  const currentPage = Math.floor(skip / limit) + 1;
  const totalPages = Math.ceil(total / limit);

  if (totalPages <= 1) return null;

  return (
    <div className="flex items-center justify-between px-6 py-3 bg-white border-t border-gray-200">
      <div className="text-sm text-gray-500">
        Showing {skip + 1} to {Math.min(skip + limit, total)} of {total} results
      </div>
      <div className="flex space-x-2">
        <button
          onClick={() => onPageChange(Math.max(0, skip - limit))}
          disabled={skip === 0}
          className="px-3 py-1 text-sm border border-gray-300 rounded-md disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
        >
          Previous
        </button>
        <span className="px-3 py-1 text-sm text-gray-700">
          Page {currentPage} of {totalPages}
        </span>
        <button
          onClick={() => onPageChange(skip + limit)}
          disabled={skip + limit >= total}
          className="px-3 py-1 text-sm border border-gray-300 rounded-md disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
        >
          Next
        </button>
      </div>
    </div>
  );
}

// =============================================
// SEARCH INPUT
// =============================================

interface SearchInputProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}

export function SearchInput({ value, onChange, placeholder = 'Search...' }: SearchInputProps) {
  return (
    <div className="relative">
      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
        <svg className="h-5 w-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
      </div>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="block w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md leading-5 bg-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-orange-500 sm:text-sm"
      />
    </div>
  );
}

// =============================================
// FILTER SELECT
// =============================================

interface FilterSelectProps {
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
  placeholder?: string;
}

export function FilterSelect({ value, onChange, options, placeholder = 'Filter...' }: FilterSelectProps) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="block w-full pl-3 pr-10 py-2 text-base border border-gray-300 focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-orange-500 sm:text-sm rounded-md"
    >
      <option value="">{placeholder}</option>
      {options.map((opt) => (
        <option key={opt.value} value={opt.value}>
          {opt.label}
        </option>
      ))}
    </select>
  );
}

// =============================================
// PAGE HEADER
// =============================================

interface PageHeaderProps {
  title: string;
  description?: string;
  actions?: ReactNode;
}

export function PageHeader({ title, description, actions }: PageHeaderProps) {
  return (
    <div className="mb-6 flex items-center justify-between">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">{title}</h1>
        {description && <p className="mt-1 text-sm text-gray-500">{description}</p>}
      </div>
      {actions && <div className="flex space-x-3">{actions}</div>}
    </div>
  );
}

// =============================================
// CARD
// =============================================

interface CardProps {
  children: ReactNode;
  className?: string;
}

export function Card({ children, className = '' }: CardProps) {
  return (
    <div className={`bg-white rounded-lg shadow-sm ${className}`}>
      {children}
    </div>
  );
}
