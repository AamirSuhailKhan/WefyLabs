'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { api, getToken } from '@/lib/api-client';

export default function OnboardingPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  // Form State
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [whatsappNumber, setWhatsappNumber] = useState('');
  const [sameAsPhone, setSameAsPhone] = useState(true);
  const [agencyName, setAgencyName] = useState('');
  const [city, setCity] = useState('Bengaluru');
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    async function loadUser() {
      const token = getToken();
      if (!token) {
        router.push('/login');
        return;
      }

      try {
        const broker = await api.auth.me();
        if (broker.onboarding_status === 'ONBOARDED') {
          router.push('/dashboard');
          return;
        }
        if (broker.onboarding_status === 'SUSPENDED') {
          router.push('/login');
          return;
        }

        setName(broker.name || '');
        setLoading(false);
      } catch (err) {
        console.error('Failed to retrieve user profile', err);
        router.push('/login');
      }
    }
    loadUser();
  }, [router]);

  // Sync whatsapp number with phone if checkbox is ticked
  useEffect(() => {
    if (sameAsPhone) {
      setWhatsappNumber(phone);
      setFieldErrors((prev) => {
        const next = { ...prev };
        delete next.whatsappNumber;
        return next;
      });
    }
  }, [phone, sameAsPhone]);

  const isValidIndianPhone = (p: string): boolean => {
    const cleaned = p.replace(/[\s\-().]/g, '');
    if (/^0[6-9]\d{9}$/.test(cleaned)) return true;
    return /^(\+91)?[6-9]\d{9}$/.test(cleaned);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    const newFieldErrors: Record<string, string> = {};

    // Comprehensive client-side validations
    if (!name.trim()) {
      newFieldErrors.name = 'Please enter your full name.';
    }

    if (!phone.trim()) {
      newFieldErrors.phone = 'Please enter your phone number.';
    } else if (!isValidIndianPhone(phone)) {
      newFieldErrors.phone = 'Please enter a valid 10-digit Indian phone number (e.g. +91 98765 43210 or 9876543210).';
    }

    const effectiveWhatsapp = sameAsPhone ? phone : whatsappNumber;
    if (!sameAsPhone) {
      if (!whatsappNumber.trim()) {
        newFieldErrors.whatsappNumber = 'Please enter your WhatsApp number.';
      } else if (!isValidIndianPhone(whatsappNumber)) {
        newFieldErrors.whatsappNumber = 'Please enter a valid 10-digit Indian WhatsApp number.';
      }
    }

    if (!agencyName.trim()) {
      newFieldErrors.agencyName = 'Please enter your agency or company name.';
    }

    if (!city.trim()) {
      newFieldErrors.city = 'Please enter your operating city.';
    }

    if (Object.keys(newFieldErrors).length > 0) {
      setFieldErrors(newFieldErrors);
      setError('Please correct the highlighted fields before proceeding.');
      return;
    }

    setFieldErrors({});
    setSubmitting(true);
    try {
      await api.auth.onboard({
        name: name.trim(),
        phone: phone.trim(),
        whatsapp_number: effectiveWhatsapp.trim(),
        agency_name: agencyName.trim(),
        city: city.trim()
      });
      // Redirect to dashboard on success
      router.push('/dashboard');
    } catch (err: any) {
      // Extract structured backend validation details if present
      const backendDetails = err?.data?.details;
      if (Array.isArray(backendDetails) && backendDetails.length > 0) {
        const mappedErrors: Record<string, string> = {};
        for (const item of backendDetails) {
          const field = item.field?.toLowerCase() || '';
          const msg = (item.message || '').replace(/^Value error,\s*/i, '');
          if (field.includes('phone')) mappedErrors.phone = msg;
          else if (field.includes('whatsapp')) mappedErrors.whatsappNumber = msg;
          else if (field.includes('name')) mappedErrors.name = msg;
          else if (field.includes('agency')) mappedErrors.agencyName = msg;
          else if (field.includes('city')) mappedErrors.city = msg;
        }
        if (Object.keys(mappedErrors).length > 0) {
          setFieldErrors(mappedErrors);
        }
      }
      setError(err.message || 'Onboarding failed. Please check your details and try again.');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#F0EDE8]">
        <div className="flex flex-col items-center space-y-4">
          <div className="h-10 w-10 animate-spin rounded-full border-4 border-gray-900 border-t-transparent"></div>
          <p className="text-sm font-medium text-gray-600">Loading onboarding portal...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-[#F0EDE8] py-12 px-4 sm:px-6 lg:px-8">
      <div className="w-full max-w-xl bg-white rounded-3xl p-8 sm:p-12 shadow-2xl border border-stone-200">
        
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-stone-100 text-stone-700 mb-4">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="h-6 w-6">
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM4.501 20.118a7.5 7.5 0 0 1 14.998 0A17.933 17.933 0 0 1 12 21.75c-2.676 0-5.216-.584-7.499-1.632Z" />
            </svg>
          </div>
          <h2 className="text-3xl font-bold tracking-tight text-gray-950 font-serif">Create Your Broker Profile</h2>
          <p className="mt-2 text-stone-500 text-sm">
            Complete your profile details to access the BeetleLabs dashboard.
          </p>
        </div>

        {error && (
          <div className="mb-6 rounded-xl bg-red-50 border border-red-100 p-4 text-sm text-red-600 flex items-start gap-3">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="h-5 w-5 shrink-0 mt-0.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 3.75h.008v.008H12v-.008Z" />
            </svg>
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Name Field */}
          <div>
            <label htmlFor="name" className="block text-sm font-semibold text-gray-700 mb-2">
              Full Name
            </label>
            <input
              id="name"
              type="text"
              required
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                if (fieldErrors.name) setFieldErrors((prev) => ({ ...prev, name: '' }));
              }}
              className={`block w-full rounded-xl border py-3 px-4 text-gray-950 placeholder-stone-400 focus:outline-none focus:ring-1 transition-colors ${
                fieldErrors.name
                  ? 'border-red-500 focus:border-red-500 focus:ring-red-500 bg-red-50/20'
                  : 'border-stone-300 focus:border-stone-500 focus:ring-stone-500'
              }`}
              placeholder="e.g. Aamir Suhail"
            />
            {fieldErrors.name && (
              <p className="mt-1.5 text-xs text-red-600 font-medium">{fieldErrors.name}</p>
            )}
          </div>

          {/* Phone Field */}
          <div>
            <label htmlFor="phone" className="block text-sm font-semibold text-gray-700 mb-2">
              Phone Number
            </label>
            <input
              id="phone"
              type="tel"
              required
              value={phone}
              onChange={(e) => {
                setPhone(e.target.value);
                if (fieldErrors.phone) setFieldErrors((prev) => ({ ...prev, phone: '' }));
              }}
              className={`block w-full rounded-xl border py-3 px-4 text-gray-950 placeholder-stone-400 focus:outline-none focus:ring-1 transition-colors ${
                fieldErrors.phone
                  ? 'border-red-500 focus:border-red-500 focus:ring-red-500 bg-red-50/20'
                  : 'border-stone-300 focus:border-stone-500 focus:ring-stone-500'
              }`}
              placeholder="e.g. +91 98765 43210"
            />
            {fieldErrors.phone && (
              <p className="mt-1.5 text-xs text-red-600 font-medium">{fieldErrors.phone}</p>
            )}
          </div>

          {/* Same as phone switch */}
          <div className="flex items-center gap-3">
            <input
              id="sameAsPhone"
              type="checkbox"
              checked={sameAsPhone}
              onChange={(e) => setSameAsPhone(e.target.checked)}
              className="h-5 w-5 rounded border-stone-300 text-stone-900 focus:ring-stone-500 cursor-pointer"
            />
            <label htmlFor="sameAsPhone" className="text-sm font-medium text-gray-600 cursor-pointer select-none">
              WhatsApp number is the same as Phone number
            </label>
          </div>

          {/* WhatsApp Field (only visible if sameAsPhone is false) */}
          {!sameAsPhone && (
            <div className="transition-all duration-300">
              <label htmlFor="whatsapp" className="block text-sm font-semibold text-gray-700 mb-2">
                WhatsApp Number
              </label>
              <input
                id="whatsapp"
                type="tel"
                required={!sameAsPhone}
                value={whatsappNumber}
                onChange={(e) => {
                  setWhatsappNumber(e.target.value);
                  if (fieldErrors.whatsappNumber) setFieldErrors((prev) => ({ ...prev, whatsappNumber: '' }));
                }}
                className={`block w-full rounded-xl border py-3 px-4 text-gray-950 placeholder-stone-400 focus:outline-none focus:ring-1 transition-colors ${
                  fieldErrors.whatsappNumber
                    ? 'border-red-500 focus:border-red-500 focus:ring-red-500 bg-red-50/20'
                    : 'border-stone-300 focus:border-stone-500 focus:ring-stone-500'
                }`}
                placeholder="e.g. +91 98765 43210"
              />
              {fieldErrors.whatsappNumber && (
                <p className="mt-1.5 text-xs text-red-600 font-medium">{fieldErrors.whatsappNumber}</p>
              )}
            </div>
          )}

          {/* Agency Name Field */}
          <div>
            <label htmlFor="agency" className="block text-sm font-semibold text-gray-700 mb-2">
              Agency / Company Name
            </label>
            <input
              id="agency"
              type="text"
              required
              value={agencyName}
              onChange={(e) => {
                setAgencyName(e.target.value);
                if (fieldErrors.agencyName) setFieldErrors((prev) => ({ ...prev, agencyName: '' }));
              }}
              className={`block w-full rounded-xl border py-3 px-4 text-gray-950 placeholder-stone-400 focus:outline-none focus:ring-1 transition-colors ${
                fieldErrors.agencyName
                  ? 'border-red-500 focus:border-red-500 focus:ring-red-500 bg-red-50/20'
                  : 'border-stone-300 focus:border-stone-500 focus:ring-stone-500'
              }`}
              placeholder="e.g. Beetle Realty Group"
            />
            {fieldErrors.agencyName && (
              <p className="mt-1.5 text-xs text-red-600 font-medium">{fieldErrors.agencyName}</p>
            )}
          </div>

          {/* City Field */}
          <div>
            <label htmlFor="city" className="block text-sm font-semibold text-gray-700 mb-2">
              City
            </label>
            <input
              id="city"
              type="text"
              required
              value={city}
              onChange={(e) => {
                setCity(e.target.value);
                if (fieldErrors.city) setFieldErrors((prev) => ({ ...prev, city: '' }));
              }}
              className={`block w-full rounded-xl border py-3 px-4 text-gray-950 placeholder-stone-400 focus:outline-none focus:ring-1 transition-colors ${
                fieldErrors.city
                  ? 'border-red-500 focus:border-red-500 focus:ring-red-500 bg-red-50/20'
                  : 'border-stone-300 focus:border-stone-500 focus:ring-stone-500'
              }`}
              placeholder="e.g. Bengaluru"
            />
            {fieldErrors.city && (
              <p className="mt-1.5 text-xs text-red-600 font-medium">{fieldErrors.city}</p>
            )}
          </div>

          {/* Submit Button */}
          <button
            type="submit"
            disabled={submitting}
            className="w-full flex justify-center py-3 px-4 border border-transparent rounded-xl shadow-sm text-sm font-medium text-white bg-gray-950 hover:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-950 transition-colors disabled:bg-gray-400 disabled:cursor-not-allowed mt-4"
          >
            {submitting ? (
              <span className="flex items-center gap-2">
                <svg className="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Saving profile...
              </span>
            ) : (
              'Complete Onboarding'
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
