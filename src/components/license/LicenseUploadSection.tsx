import React, { useState } from 'react';
import {
  FileCheck,
  UploadCloud,
  Loader2,
  AlertCircle,
  CheckCircle2,
  FileText,
  Calendar,
  Building,
  Hash
} from 'lucide-react';
import kitchenApi from '../../services/kitchenApi';

export interface LicenseScanResult {
  license_number: string;
  business_name?: string;
  expiry_date?: string;
  confidence?: number;
  document_base64: string;
  filename: string;
  is_test_identifier?: boolean;
}

interface LicenseUploadSectionProps {
  initialLicenseNumber?: string;
  initialBusinessName?: string;
  initialExpiryDate?: string;
  onChange: (data: {
    license_number: string;
    business_name: string;
    expiry_date: string;
    document_base64: string;
    filename: string;
  }) => void;
  required?: boolean;
}

export const LicenseUploadSection: React.FC<LicenseUploadSectionProps> = ({
  initialLicenseNumber = '',
  initialBusinessName = '',
  initialExpiryDate = '',
  onChange,
  required = true,
}) => {
  const [file, setFile] = useState<File | null>(null);
  const [scanning, setScanning] = useState(false);
  const [ocrSuccess, setOcrSuccess] = useState(false);
  const [scanMessage, setScanMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [licenseNumber, setLicenseNumber] = useState(initialLicenseNumber);
  const [businessName, setBusinessName] = useState(initialBusinessName);
  const [expiryDate, setExpiryDate] = useState(initialExpiryDate);
  const [documentBase64, setDocumentBase64] = useState<string>('');
  const [filename, setFilename] = useState<string>('');

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (!selectedFile) return;

    // Validate size (max 5MB)
    if (selectedFile.size > 5 * 1024 * 1024) {
      setError('File size exceeds 5MB limit.');
      return;
    }

    const ext = selectedFile.name.toLowerCase();
    if (!ext.endsWith('.pdf') && !ext.endsWith('.jpg') && !ext.endsWith('.jpeg') && !ext.endsWith('.png')) {
      setError('Invalid format. Only PDF, JPG, and PNG are supported.');
      return;
    }

    setError(null);
    setFile(selectedFile);
    setFilename(selectedFile.name);

    // Read base64
    const reader = new FileReader();
    reader.onload = async () => {
      const base64Str = reader.result as string;
      setDocumentBase64(base64Str);

      // Trigger automatic OCR scan
      try {
        setScanning(true);
        setScanMessage('Scanning document with OCR to extract license details...');
        const formData = new FormData();
        formData.append('file', selectedFile);
        formData.append('document', selectedFile);

        const res = await kitchenApi.ocrScanLicense(formData);
        if (res) {
          const extractedNum = res.extracted_license_number || '';
          const extractedName = res.extracted_business_name || '';
          const extractedExp = res.extracted_expiry_date || '';

          if (extractedNum) setLicenseNumber(extractedNum);
          if (extractedName) setBusinessName(extractedName);
          if (extractedExp) setExpiryDate(extractedExp);

          setOcrSuccess(true);
          setScanMessage(
            res.notes ||
              'OCR extraction complete. Please review and verify the extracted details below before submitting.'
          );

          onChange({
            license_number: extractedNum || licenseNumber,
            business_name: extractedName || businessName,
            expiry_date: extractedExp || expiryDate,
            document_base64: base64Str,
            filename: selectedFile.name,
          });
        }
      } catch (ocrErr: any) {
        console.warn('OCR extraction warning:', ocrErr);
        setScanMessage(
          'Document uploaded. Automated OCR could not extract all fields automatically; please enter your 14-digit FSSAI number and details manually below.'
        );
        onChange({
          license_number: licenseNumber,
          business_name: businessName,
          expiry_date: expiryDate,
          document_base64: base64Str,
          filename: selectedFile.name,
        });
      } finally {
        setScanning(false);
      }
    };
    reader.readAsDataURL(selectedFile);
  };

  const handleFieldChange = (field: 'number' | 'name' | 'expiry', value: string) => {
    let nextNum = licenseNumber;
    let nextName = businessName;
    let nextExp = expiryDate;

    if (field === 'number') {
      nextNum = value;
      setLicenseNumber(value);
    } else if (field === 'name') {
      nextName = value;
      setBusinessName(value);
    } else if (field === 'expiry') {
      nextExp = value;
      setExpiryDate(value);
    }

    onChange({
      license_number: nextNum,
      business_name: nextName,
      expiry_date: nextExp,
      document_base64: documentBase64,
      filename: filename,
    });
  };

  return (
    <div className="space-y-4 p-4 bg-emerald-50/50 border border-emerald-200/80 rounded-xl">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2">
          <FileCheck className="w-5 h-5 text-emerald-700 shrink-0" />
          <div>
            <h4 className="text-sm font-bold text-emerald-950">
              FSSAI Food License Verification {required && <span className="text-rose-500">*</span>}
            </h4>
            <p className="text-xs text-emerald-800/80">
              Mandatory government food safety license (14 digits) required for all KitchenVerse kitchens.
            </p>
          </div>
        </div>
      </div>

      {/* File Upload Box */}
      <div>
        <label className="block text-xs font-semibold text-gray-700 mb-1">
          Upload License Document (PDF, JPG, PNG - Max 5MB)
        </label>
        <div className="relative border-2 border-dashed border-emerald-300 rounded-xl p-4 text-center hover:bg-emerald-50/80 transition bg-white">
          <input
            type="file"
            accept=".pdf,.jpg,.jpeg,.png"
            onChange={handleFileChange}
            className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
            required={required && !documentBase64}
          />
          <div className="flex flex-col items-center justify-center gap-1.5 pointer-events-none">
            {scanning ? (
              <>
                <Loader2 className="w-6 h-6 text-emerald-600 animate-spin" />
                <span className="text-xs font-semibold text-emerald-900">
                  Scanning document & extracting details...
                </span>
              </>
            ) : file ? (
              <>
                <FileText className="w-6 h-6 text-emerald-700" />
                <span className="text-xs font-semibold text-gray-900">{file.name}</span>
                <span className="text-[11px] text-gray-500">
                  {(file.size / 1024).toFixed(1)} KB — Click or drag to replace
                </span>
              </>
            ) : (
              <>
                <UploadCloud className="w-6 h-6 text-emerald-600" />
                <span className="text-xs font-semibold text-gray-800">
                  Click or drag your FSSAI certificate here
                </span>
                <span className="text-[11px] text-gray-500">
                  System verifies file signature & scans 14-digit registration number
                </span>
              </>
            )}
          </div>
        </div>

        {error && (
          <div className="flex items-center gap-1.5 mt-2 text-xs text-rose-600">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {scanMessage && !error && (
          <div className="flex items-start gap-1.5 mt-2 text-xs text-emerald-800 bg-emerald-100/60 p-2.5 rounded-lg border border-emerald-200">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
            <span>{scanMessage}</span>
          </div>
        )}
      </div>

      {/* Review & Edit Extracted Fields */}
      <div className="pt-2 border-t border-emerald-200/60">
        <div className="mb-2">
          <span className="text-[11px] font-bold uppercase tracking-wider text-emerald-900">
            Review Extracted Details (Editable)
          </span>
          <p className="text-[11px] text-gray-600">
            OCR suggestions are advisory. Always verify that details match your certificate.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1 flex items-center gap-1">
              <Hash className="w-3.5 h-3.5 text-gray-500" />
              14-Digit FSSAI License Number {required && <span className="text-rose-500">*</span>}
            </label>
            <input
              type="text"
              required={required}
              maxLength={18}
              value={licenseNumber}
              onChange={(e) => handleFieldChange('number', e.target.value)}
              placeholder="e.g. 10019043002844"
              className="w-full px-3 py-2 text-sm bg-white border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 font-mono tracking-wider"
            />
            <span className="text-[10px] text-gray-500">Must be exactly 14 numeric digits</span>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1 flex items-center gap-1">
              <Building className="w-3.5 h-3.5 text-gray-500" />
              Business Name on License
            </label>
            <input
              type="text"
              value={businessName}
              onChange={(e) => handleFieldChange('name', e.target.value)}
              placeholder="e.g. Royal Curry Foods Pvt Ltd"
              className="w-full px-3 py-2 text-sm bg-white border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1 flex items-center gap-1">
              <Calendar className="w-3.5 h-3.5 text-gray-500" />
              License Expiry Date
            </label>
            <input
              type="date"
              value={expiryDate}
              onChange={(e) => handleFieldChange('expiry', e.target.value)}
              className="w-full px-3 py-2 text-sm bg-white border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
            />
          </div>
        </div>
      </div>
    </div>
  );
};
