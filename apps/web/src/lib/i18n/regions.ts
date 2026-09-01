export type RegionCode = 'IN' | 'AE' | 'SG' | 'GB' | 'US' | 'AU' | 'CA';

export interface RegionConfig {
  code: RegionCode;
  name: string;
  currency: string;
  currencySymbol: string;
  locale: string;
  timezone: string;
  whatsappProvider: string;
  paymentProvider: string;
  defaultAdSpend: number;
  defaultCommission: number;
  defaultLeadsPerMonth: number;
  defaultTimePerLead: number;
  defaultConversionRate: number;
  defaultColdLeadPercent: number;
  starterPrice: number;
  proPrice: number;
  currencyDisplay: 'symbol' | 'code';
  flag: string;
}

export const REGIONS: Record<RegionCode, RegionConfig> = {
  US: {
    code: 'US',
    name: 'United States',
    currency: 'USD',
    currencySymbol: '$',
    locale: 'en-US',
    timezone: 'America/New_York',
    whatsappProvider: 'twilio',
    paymentProvider: 'stripe',
    defaultAdSpend: 2000,
    defaultCommission: 10000,
    defaultLeadsPerMonth: 150,
    defaultTimePerLead: 8,
    defaultConversionRate: 4,
    defaultColdLeadPercent: 65,
    starterPrice: 29,
    proPrice: 79,
    currencyDisplay: 'symbol',
    flag: '🇺🇸'
  },
  AE: {
    code: 'AE',
    name: 'UAE',
    currency: 'AED',
    currencySymbol: 'AED ',
    locale: 'en-AE',
    timezone: 'Asia/Dubai',
    whatsappProvider: '360dialog',
    paymentProvider: 'stripe',
    defaultAdSpend: 3000,
    defaultCommission: 50000,
    defaultLeadsPerMonth: 150,
    defaultTimePerLead: 10,
    defaultConversionRate: 6,
    defaultColdLeadPercent: 65,
    starterPrice: 109,
    proPrice: 289,
    currencyDisplay: 'symbol',
    flag: '🇦🇪'
  },
  IN: {
    code: 'IN',
    name: 'India',
    currency: 'INR',
    currencySymbol: '₹',
    locale: 'en-IN',
    timezone: 'Asia/Kolkata',
    whatsappProvider: '360dialog',
    paymentProvider: 'razorpay',
    defaultAdSpend: 25000,
    defaultCommission: 150000,
    defaultLeadsPerMonth: 150,
    defaultTimePerLead: 8,
    defaultConversionRate: 8,
    defaultColdLeadPercent: 70,
    starterPrice: 2499,
    proPrice: 6499,
    currencyDisplay: 'symbol',
    flag: '🇮🇳'
  },
  GB: {
    code: 'GB',
    name: 'United Kingdom',
    currency: 'GBP',
    currencySymbol: '£',
    locale: 'en-GB',
    timezone: 'Europe/London',
    whatsappProvider: 'twilio',
    paymentProvider: 'stripe',
    defaultAdSpend: 1500,
    defaultCommission: 8000,
    defaultLeadsPerMonth: 150,
    defaultTimePerLead: 10,
    defaultConversionRate: 5,
    defaultColdLeadPercent: 60,
    starterPrice: 24,
    proPrice: 64,
    currencyDisplay: 'symbol',
    flag: '🇬🇧'
  },
  SG: {
    code: 'SG',
    name: 'Singapore',
    currency: 'SGD',
    currencySymbol: 'S$',
    locale: 'en-SG',
    timezone: 'Asia/Singapore',
    whatsappProvider: '360dialog',
    paymentProvider: 'stripe',
    defaultAdSpend: 2000,
    defaultCommission: 40000,
    defaultLeadsPerMonth: 150,
    defaultTimePerLead: 8,
    defaultConversionRate: 7,
    defaultColdLeadPercent: 60,
    starterPrice: 39,
    proPrice: 109,
    currencyDisplay: 'symbol',
    flag: '🇸🇬'
  },
  AU: {
    code: 'AU',
    name: 'Australia',
    currency: 'AUD',
    currencySymbol: 'A$',
    locale: 'en-AU',
    timezone: 'Australia/Sydney',
    whatsappProvider: 'twilio',
    paymentProvider: 'stripe',
    defaultAdSpend: 2500,
    defaultCommission: 15000,
    defaultLeadsPerMonth: 150,
    defaultTimePerLead: 8,
    defaultConversionRate: 5,
    defaultColdLeadPercent: 60,
    starterPrice: 45,
    proPrice: 119,
    currencyDisplay: 'symbol',
    flag: '🇦🇺'
  },
  CA: {
    code: 'CA',
    name: 'Canada',
    currency: 'CAD',
    currencySymbol: 'C$',
    locale: 'en-CA',
    timezone: 'America/Toronto',
    whatsappProvider: 'twilio',
    paymentProvider: 'stripe',
    defaultAdSpend: 2000,
    defaultCommission: 12000,
    defaultLeadsPerMonth: 150,
    defaultTimePerLead: 8,
    defaultConversionRate: 5,
    defaultColdLeadPercent: 60,
    starterPrice: 39,
    proPrice: 109,
    currencyDisplay: 'symbol',
    flag: '🇨🇦'
  }
};
