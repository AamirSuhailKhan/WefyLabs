'use client';

import React, { useState } from 'react';
import { PropertyValuationCard } from '@/components/properties/PropertyValuationCard';
import { Building2, Search, Filter, Plus, Home, MapPin, Eye, Tag, Sparkles } from 'lucide-react';
import { useRegion } from '@/lib/i18n/region-context';
import { formatCurrency } from '@/lib/i18n/currency';

export default function PropertiesPage() {
  const { region } = useRegion();
  const [selectedType, setSelectedType] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');

  const properties = [
    {
      id: '1',
      title: 'Luxury 3BHK Penthouse in Marina Gate',
      property_category: 'residential',
      property_type: 'penthouse',
      transaction_category: 'resale',
      status: 'available',
      price: 2850000,
      built_up_area_sqft: 1850,
      bedrooms: 3,
      bathrooms: 4,
      project_name: 'Marina Gate 1',
      city: 'Dubai',
      locality: 'Dubai Marina',
      image: 'https://images.unsplash.com/photo-1545324418-cc1a3fa10c00?w=600&auto=format&fit=crop&q=80',
      valuation: {
        estimated_market_value: 3237500,
        estimated_price_per_sqft: 1750,
        is_overpriced: false,
        overpriced_percentage: -11.9,
        estimated_annual_roi_yield_pct: 7.8,
        confidence_score: 0.94
      }
    },
    {
      id: '2',
      title: 'Modern 2BHK Apartment in Downtown Heights',
      property_category: 'residential',
      property_type: 'apartment',
      transaction_category: 'offplan_developer',
      status: 'available',
      price: 3100000,
      built_up_area_sqft: 1200,
      bedrooms: 2,
      bathrooms: 2,
      project_name: 'Downtown Heights',
      city: 'Dubai',
      locality: 'Downtown Dubai',
      image: 'https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?w=600&auto=format&fit=crop&q=80',
      valuation: {
        estimated_market_value: 2880000,
        estimated_price_per_sqft: 2400,
        is_overpriced: true,
        overpriced_percentage: 7.6,
        estimated_annual_roi_yield_pct: 6.8,
        confidence_score: 0.89
      }
    }
  ];

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold font-mono text-[#1A1A1A]">Property Inventory & AI AVM</h1>
          <p className="text-xs text-[#6B6B6B] font-sans">
            Manage listings, track price changes, floor plans, and AI market valuations.
          </p>
        </div>

        <button className="btn-lime px-4 py-2 text-xs flex items-center gap-1.5 self-start sm:self-auto">
          <Plus className="w-4 h-4" />
          <span>Add New Property</span>
        </button>
      </div>

      {/* Filter Toolbar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-[#FAF7F2] border border-[#D4D0C8] p-3 rounded-2xl shadow-xs">
        <div className="relative w-full sm:w-80">
          <Search className="w-4 h-4 text-gray-400 absolute left-3 top-2.5" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search by project, building, or locality..."
            className="w-full pl-9 pr-3 py-2 bg-white border border-[#D4D0C8] rounded-xl text-xs focus:outline-none"
          />
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto">
          {['all', 'apartment', 'villa', 'penthouse', 'commercial'].map((t) => (
            <button
              key={t}
              onClick={() => setSelectedType(t)}
              className={`px-3 py-1.5 text-xs font-mono font-bold rounded-lg uppercase transition-colors ${
                selectedType === t ? 'bg-[#1A1A1A] text-white' : 'bg-white text-gray-700 hover:bg-gray-200 border border-[#D4D0C8]'
              }`}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      {/* Property Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {properties.map((prop) => (
          <div key={prop.id} className="bg-white border border-[#D4D0C8] rounded-2xl overflow-hidden shadow-xs hover:border-gray-400 transition-all flex flex-col justify-between">
            <div>
              {/* Image & Badge */}
              <div className="relative h-48 w-full bg-gray-100 overflow-hidden">
                <img src={prop.image} alt={prop.title} className="w-full h-full object-cover" />
                <div className="absolute top-3 left-3 bg-[#1A1A1A] text-white text-[10px] font-mono font-bold px-2 py-1 rounded-md uppercase">
                  {prop.transaction_category}
                </div>
                <div className="absolute top-3 right-3 bg-emerald-500 text-white text-[10px] font-mono font-bold px-2 py-1 rounded-md uppercase">
                  {prop.status}
                </div>
              </div>

              {/* Content */}
              <div className="p-4 space-y-3">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <h3 className="text-sm font-bold font-mono text-[#1A1A1A]">{prop.title}</h3>
                    <div className="flex items-center gap-1 text-xs text-gray-500 font-sans mt-0.5">
                      <MapPin className="w-3.5 h-3.5 text-gray-400 shrink-0" />
                      <span>{prop.locality}, {prop.city} ({prop.project_name})</span>
                    </div>
                  </div>
                  <span className="text-base font-extrabold font-mono text-[#1A1A1A] shrink-0">
                    {formatCurrency(prop.price, region)}
                  </span>
                </div>

                <div className="flex items-center gap-4 text-xs font-mono text-gray-600 pt-1 border-t border-[#F0EDE8]">
                  <span>{prop.bedrooms} Beds</span>
                  <span>•</span>
                  <span>{prop.bathrooms} Baths</span>
                  <span>•</span>
                  <span>{prop.built_up_area_sqft} sqft</span>
                </div>

                {/* AI Valuation Card Widget */}
                <PropertyValuationCard price={prop.price} areaSqft={prop.built_up_area_sqft} valuation={prop.valuation} />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
