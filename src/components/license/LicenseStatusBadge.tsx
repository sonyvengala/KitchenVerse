import React from 'react';
import {
  ShieldAlert,
  ShieldCheck,
  Clock,
  AlertTriangle,
  XCircle,
  FileText,
  AlertCircle
} from 'lucide-react';
import { LicenseStatus } from '../../types';

interface LicenseStatusBadgeProps {
  status?: LicenseStatus | string;
  isDuplicateFlagged?: boolean;
  className?: string;
}

export const LicenseStatusBadge: React.FC<LicenseStatusBadgeProps> = ({
  status,
  isDuplicateFlagged = false,
  className = '',
}) => {
  const normStatus = (status || 'PENDING_REVIEW').toUpperCase();

  const getBadgeConfig = () => {
    switch (normStatus) {
      case 'VERIFIED':
        return {
          bg: 'bg-emerald-50 text-emerald-800 border-emerald-200',
          icon: ShieldCheck,
          label: 'FSSAI Verified',
        };
      case 'CORRECTION_REQUIRED':
        return {
          bg: 'bg-amber-50 text-amber-800 border-amber-200',
          icon: AlertTriangle,
          label: 'Correction Required',
        };
      case 'REJECTED':
        return {
          bg: 'bg-rose-50 text-rose-800 border-rose-200',
          icon: XCircle,
          label: 'License Rejected',
        };
      case 'EXPIRED':
        return {
          bg: 'bg-orange-50 text-orange-800 border-orange-200',
          icon: AlertCircle,
          label: 'License Expired',
        };
      case 'PENDING_REVIEW':
      default:
        return {
          bg: 'bg-blue-50 text-blue-800 border-blue-200',
          icon: Clock,
          label: 'Pending FSSAI Review',
        };
    }
  };

  const config = getBadgeConfig();
  const Icon = config.icon;

  return (
    <div className={`inline-flex items-center gap-1.5 ${className}`}>
      <span
        className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold border ${config.bg}`}
      >
        <Icon className="w-3.5 h-3.5 mr-1 shrink-0" />
        {config.label}
      </span>
      {isDuplicateFlagged && (
        <span
          title="Duplicate License Number Detected - Admin Flagged"
          className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-bold bg-purple-100 text-purple-800 border border-purple-200"
        >
          <ShieldAlert className="w-3 h-3 mr-1" />
          Duplicate Flag
        </span>
      )}
    </div>
  );
};
