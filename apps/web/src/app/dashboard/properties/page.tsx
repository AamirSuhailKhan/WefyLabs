'use client';

import React, { useState, useEffect } from 'react';
import { PropertyValuationCard } from '@/components/properties/PropertyValuationCard';
import { Building2, Search, Filter, Plus, Home, MapPin, Eye, Tag, Sparkles, Trash2, X, Check, RefreshCw } from 'lucide-react';
import DashboardNav from '@/components/shared/DashboardNav';
import { formatCurrencyINR } from '@/lib/utils';
import { api } from '@/lib/api-client';

export default function PropertiesPage() {
  const [selectedType, setSelectedType] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [properties, setProperties] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [formData, setFormData] = useState({
    title: '',
    property_type: 'apartment',
    property_category: 'residential',
    transaction_category: 'resale',
    status: 'available',
    price: 12000000,
    built_up_area_sqft: 1400,
    bedrooms: 2,
    bathrooms: 2,
    locality: 'Indiranagar',
    city: 'Bengaluru',
    project_name: '',
    description: '',
    amenities: 'Gym, Swimming Pool, 24/7 Security'
  });

  const fetchProperties = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.properties.list({
        property_type: selectedType !== 'all' ? selectedType : undefined,
        search: searchQuery ? searchQuery : undefined
      });
      setProperties(data.items || data.data || data || []);
    } catch (err: any) {
      setError(err?.message || 'Failed to load properties');
      setProperties([]);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchProperties();
  }, [selectedType, searchQuery]);

  const handleCreateProperty = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.title.trim()) {
      setFormError('Property title is required');
      return;
    }
    setIsSubmitting(true);
    setFormError(null);
    try {
      const amenitiesList = formData.amenities
        ? formData.amenities.split(',').map(s => s.trim()).filter(Boolean)
        : [];

      await api.properties.create({
        title: formData.title.trim(),
        property_type: formData.property_type,
        property_category: formData.property_category,
        transaction_category: formData.transaction_category,
        status: formData.status,
        price: Number(formData.price),
        currency_code: 'INR',
        built_up_area_sqft: Number(formData.built_up_area_sqft),
        bedrooms: Number(formData.bedrooms),
        bathrooms: Number(formData.bathrooms),
        locality: formData.locality.trim(),
        city: formData.city.trim(),
        project_name: formData.project_name.trim() || undefined,
        description: formData.description.trim() || undefined,
        amenities: amenitiesList
      });

      setIsModalOpen(false);
      setFormData({
        title: '',
        property_type: 'apartment',
        property_category: 'residential',
        transaction_category: 'resale',
        status: 'available',
        price: 12000000,
        built_up_area_sqft: 1400,
        bedrooms: 2,
        bathrooms: 2,
        locality: 'Indiranagar',
        city: 'Bengaluru',
        project_name: '',
        description: '',
        amenities: 'Gym, Swimming Pool, 24/7 Security'
      });
      fetchProperties();
    } catch (err: any) {
      setFormError(err?.message || 'Failed to create property listing');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteProperty = async (id: string, title: string) => {
    if (!confirm(`Are you sure you want to delete property "${title}"?`)) return;
    try {
      await api.properties.delete(id);
      setProperties(prev => prev.filter(p => p.id !== id));
    } catch (err: any) {
      alert(err?.message || 'Failed to delete property');
    }
  };

  return (
    <div className="min-h-screen bg-[#F0EDE8]">
      <DashboardNav />

      <div className="pt-16 max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#D4D0C8] pb-6">
          <div>
            <h1
              className="text-[26px] sm:text-[28px] font-bold text-[#1A1A1A] tracking-tight leading-tight"
              style={{ fontFamily: 'JetBrains Mono, monospace' }}
            >
              PROPERTY INVENTORY &amp; AVM
            </h1>
            <p className="text-[13px] text-[#6B6B6B] mt-0.5" style={{ fontFamily: 'Inter, sans-serif' }}>
              Manage active listings, track floor plans, locality benchmarks &amp; instant AI market valuations.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={fetchProperties}
              disabled={isLoading}
              title="Refresh properties"
              className="p-2.5 bg-[#FAF7F2] border border-[#D4D0C8] hover:bg-[#F0EDE8] text-[#4A4A4A] rounded-lg transition-all"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin text-[#0D9488]' : ''}`} />
            </button>
            <button
              onClick={() => setIsModalOpen(true)}
              className="flex items-center gap-1.5 px-4 py-2.5 bg-[#E8F5A8] hover:bg-[#D4E894] text-[#1A1A1A] rounded-lg text-[11px] font-bold transition-all shadow-xs"
            >
              <Plus className="w-4 h-4" />
              <span>+ Add New Property</span>
            </button>
          </div>
        </div>

        {/* Filter & Search Toolbar */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-[#FAF7F2] border border-[#D4D0C8] p-3 rounded-2xl shadow-xs">
          <div className="relative w-full sm:w-80">
            <Search className="w-4 h-4 text-gray-400 absolute left-3 top-2.5" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by title, project, or locality..."
              className="w-full pl-9 pr-3 py-2 bg-white border border-[#D4D0C8] rounded-xl text-xs focus:outline-none focus:border-[#1A1A1A]"
              style={{ fontFamily: 'Inter, sans-serif' }}
            />
          </div>

          <div className="flex items-center gap-2 w-full sm:w-auto overflow-x-auto pb-1 sm:pb-0">
            {['all', 'apartment', 'villa', 'penthouse', 'commercial'].map((t) => (
              <button
                key={t}
                onClick={() => setSelectedType(t)}
                className={`px-3 py-1.5 text-xs font-mono font-bold rounded-lg uppercase transition-all shrink-0 ${
                  selectedType === t
                    ? 'bg-[#1A1A1A] text-white shadow-xs'
                    : 'bg-white text-gray-700 hover:bg-[#F0EDE8] border border-[#D4D0C8]'
                }`}
              >
                {t}
              </button>
            ))}
          </div>
        </div>

        {/* Property Cards Grid */}
        {isLoading ? (
          <div className="text-center py-20 text-sm text-[#6B6B6B]">Loading properties...</div>
        ) : error ? (
          <div className="text-center py-20 text-sm text-red-500">{error}</div>
        ) : properties.length === 0 ? (
          <div className="text-center py-20 bg-white border border-[#D4D0C8] rounded-2xl p-8">
            <Building2 className="w-12 h-12 text-[#9CA3AF] mx-auto mb-3" />
            <h3 className="text-sm font-bold text-[#1A1A1A] mb-1 font-mono">No properties found</h3>
            <p className="text-xs text-[#6B6B6B] max-w-sm mx-auto mb-4 font-sans">
              No active listings match your filters. Create your first property listing to track AVM valuations.
            </p>
            <button
              onClick={() => setIsModalOpen(true)}
              className="px-4 py-2 bg-[#E8F5A8] hover:bg-[#D4E894] text-[#1A1A1A] rounded-lg text-xs font-bold"
            >
              + Add Property
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {properties.map((prop) => (
              <div
                key={prop.id}
                className="bg-white border border-[#D4D0C8] rounded-2xl overflow-hidden shadow-xs hover:border-[#B0ACA4] transition-all flex flex-col justify-between"
              >
                <div>
                  {/* Top Bar / Badges */}
                  <div className="p-4 bg-[#FAF7F2] border-b border-[#F0EDE8] flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="bg-[#1A1A1A] text-white text-[10px] font-mono font-bold px-2 py-0.5 rounded-md uppercase">
                        {prop.property_type || 'apartment'}
                      </span>
                      <span className="bg-emerald-100 text-emerald-800 text-[10px] font-mono font-bold px-2 py-0.5 rounded-md uppercase">
                        {prop.status || 'available'}
                      </span>
                    </div>

                    <button
                      onClick={() => handleDeleteProperty(prop.id, prop.title)}
                      title="Delete Property"
                      className="p-1.5 text-gray-400 hover:text-red-600 rounded-md transition-colors"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>

                  {/* Content */}
                  <div className="p-5 space-y-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <h3 className="text-base font-bold text-[#1A1A1A] leading-tight font-sans">
                          {prop.title}
                        </h3>
                        <div className="flex items-center gap-1 text-xs text-gray-500 font-sans mt-1">
                          <MapPin className="w-3.5 h-3.5 text-gray-400 shrink-0" />
                          <span>
                            {prop.locality || 'Locality'}, {prop.city || 'Bengaluru'}{' '}
                            {prop.project_name ? `(${prop.project_name})` : ''}
                          </span>
                        </div>
                      </div>
                      <span className="text-lg font-extrabold font-mono text-[#0D9488] shrink-0">
                        {formatCurrencyINR(prop.price || 0)}
                      </span>
                    </div>

                    <div className="flex items-center gap-3 text-xs font-mono text-gray-600 pt-2 border-t border-[#F0EDE8]">
                      {prop.bedrooms && <span>{prop.bedrooms} BHK</span>}
                      <span>•</span>
                      {prop.bathrooms && <span>{prop.bathrooms} Baths</span>}
                      <span>•</span>
                      {prop.built_up_area_sqft && <span>{prop.built_up_area_sqft} sqft</span>}
                    </div>

                    {/* Amenities tags */}
                    {prop.amenities && prop.amenities.length > 0 && (
                      <div className="flex items-center gap-1.5 flex-wrap pt-1">
                        {prop.amenities.map((am: string, idx: number) => (
                          <span
                            key={idx}
                            className="text-[10px] bg-[#FAF7F2] border border-[#D4D0C8] px-2 py-0.5 rounded-md text-[#4A4A4A] font-semibold font-sans"
                          >
                            {am}
                          </span>
                        ))}
                      </div>
                    )}

                    {/* AI Valuation Card Widget */}
                    {prop.valuation && (
                      <div className="pt-2">
                        <PropertyValuationCard
                          price={prop.price}
                          areaSqft={prop.built_up_area_sqft}
                          valuation={prop.valuation}
                        />
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* New Property Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs">
          <div className="bg-white border border-[#D4D0C8] rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-[#F0EDE8] pb-3">
              <h2 className="text-base font-bold font-mono text-[#1A1A1A]">ADD NEW PROPERTY LISTING</h2>
              <button onClick={() => setIsModalOpen(false)} className="p-1 hover:bg-gray-100 rounded-md">
                <X className="w-4 h-4 text-gray-500" />
              </button>
            </div>

            {formError && (
              <div className="p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-lg font-sans">
                {formError}
              </div>
            )}

            <form onSubmit={handleCreateProperty} className="space-y-3.5 font-sans">
              <div>
                <label className="block text-[11px] font-bold text-[#4A4A4A] uppercase mb-1">
                  Property Title *
                </label>
                <input
                  type="text"
                  required
                  value={formData.title}
                  onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                  placeholder="e.g. Luxury 3BHK Penthouse in Marina Gate"
                  className="w-full px-3 py-2 text-xs border border-[#D4D0C8] rounded-lg focus:outline-none focus:border-[#1A1A1A]"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-bold text-[#4A4A4A] uppercase mb-1">
                    Property Type
                  </label>
                  <select
                    value={formData.property_type}
                    onChange={(e) => setFormData({ ...formData, property_type: e.target.value })}
                    className="w-full px-3 py-2 text-xs border border-[#D4D0C8] rounded-lg focus:outline-none"
                  >
                    <option value="apartment">Apartment</option>
                    <option value="villa">Villa</option>
                    <option value="penthouse">Penthouse</option>
                    <option value="commercial">Commercial</option>
                  </select>
                </div>

                <div>
                  <label className="block text-[11px] font-bold text-[#4A4A4A] uppercase mb-1">
                    Status
                  </label>
                  <select
                    value={formData.status}
                    onChange={(e) => setFormData({ ...formData, status: e.target.value })}
                    className="w-full px-3 py-2 text-xs border border-[#D4D0C8] rounded-lg focus:outline-none"
                  >
                    <option value="available">Available</option>
                    <option value="under_offer">Under Offer</option>
                    <option value="sold">Sold</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-bold text-[#4A4A4A] uppercase mb-1">
                    Asking Price (INR ₹) *
                  </label>
                  <input
                    type="number"
                    required
                    min={100000}
                    value={formData.price}
                    onChange={(e) => setFormData({ ...formData, price: Number(e.target.value) })}
                    className="w-full px-3 py-2 text-xs border border-[#D4D0C8] rounded-lg focus:outline-none font-mono"
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-bold text-[#4A4A4A] uppercase mb-1">
                    Built-up Area (sqft) *
                  </label>
                  <input
                    type="number"
                    required
                    min={100}
                    value={formData.built_up_area_sqft}
                    onChange={(e) => setFormData({ ...formData, built_up_area_sqft: Number(e.target.value) })}
                    className="w-full px-3 py-2 text-xs border border-[#D4D0C8] rounded-lg focus:outline-none font-mono"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-bold text-[#4A4A4A] uppercase mb-1">
                    Bedrooms
                  </label>
                  <input
                    type="number"
                    min={1}
                    max={10}
                    value={formData.bedrooms}
                    onChange={(e) => setFormData({ ...formData, bedrooms: Number(e.target.value) })}
                    className="w-full px-3 py-2 text-xs border border-[#D4D0C8] rounded-lg focus:outline-none font-mono"
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-bold text-[#4A4A4A] uppercase mb-1">
                    Bathrooms
                  </label>
                  <input
                    type="number"
                    min={1}
                    max={10}
                    value={formData.bathrooms}
                    onChange={(e) => setFormData({ ...formData, bathrooms: Number(e.target.value) })}
                    className="w-full px-3 py-2 text-xs border border-[#D4D0C8] rounded-lg focus:outline-none font-mono"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-bold text-[#4A4A4A] uppercase mb-1">
                    Locality
                  </label>
                  <input
                    type="text"
                    value={formData.locality}
                    onChange={(e) => setFormData({ ...formData, locality: e.target.value })}
                    placeholder="e.g. Indiranagar"
                    className="w-full px-3 py-2 text-xs border border-[#D4D0C8] rounded-lg focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-bold text-[#4A4A4A] uppercase mb-1">
                    City
                  </label>
                  <input
                    type="text"
                    value={formData.city}
                    onChange={(e) => setFormData({ ...formData, city: e.target.value })}
                    placeholder="e.g. Bengaluru"
                    className="w-full px-3 py-2 text-xs border border-[#D4D0C8] rounded-lg focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-bold text-[#4A4A4A] uppercase mb-1">
                  Project / Building Name
                </label>
                <input
                  type="text"
                  value={formData.project_name}
                  onChange={(e) => setFormData({ ...formData, project_name: e.target.value })}
                  placeholder="e.g. Marina Gate"
                  className="w-full px-3 py-2 text-xs border border-[#D4D0C8] rounded-lg focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-[11px] font-bold text-[#4A4A4A] uppercase mb-1">
                  Amenities (comma-separated)
                </label>
                <input
                  type="text"
                  value={formData.amenities}
                  onChange={(e) => setFormData({ ...formData, amenities: e.target.value })}
                  placeholder="Gym, Swimming Pool, Clubhouse, 24/7 Power Backup"
                  className="w-full px-3 py-2 text-xs border border-[#D4D0C8] rounded-lg focus:outline-none"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-4 border-t border-[#F0EDE8]">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 text-xs font-bold text-gray-600 hover:bg-gray-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-5 py-2 text-xs font-bold bg-[#1A1A1A] text-white rounded-lg hover:bg-black disabled:opacity-50"
                >
                  {isSubmitting ? 'Creating...' : 'Create Property'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

