import { RegionConfig } from './regions';

export function formatCurrency(
  amount: number,
  region: RegionConfig,
  options?: { compact?: boolean }
): string {
  const { currency, currencySymbol, locale } = region;

  if (options?.compact && amount >= 100000) {
    if (region.code === 'IN') {
      return `${currencySymbol}${(amount / 100000).toFixed(1)}L`;
    }
    return `${currencySymbol}${(amount / 1000).toFixed(0)}K`;
  }

  try {
    return new Intl.NumberFormat(locale, {
      style: 'currency',
      currency,
      maximumFractionDigits: 0
    }).format(amount);
  } catch {
    return `${currencySymbol}${amount.toLocaleString(locale)}`;
  }
}
