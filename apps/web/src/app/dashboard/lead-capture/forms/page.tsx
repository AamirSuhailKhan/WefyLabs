'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { 
  FormInput, 
  Copy, 
  Check, 
  Smartphone, 
  Monitor, 
  Sparkles, 
  RefreshCw, 
  Eye, 
  Code2, 
  Settings2,
  CheckCircle2
} from 'lucide-react';
import DashboardNav from '@/components/shared/DashboardNav';
import LeadCaptureNav from '@/components/lead-capture/LeadCaptureNav';
import { api } from '@/lib/api-client';

interface FormFieldConfig {
  id: string;
  label: string;
  enabled: boolean;
  required: boolean;
  placeholder?: string;
}

export default function FormBuilderPage() {
  const [sources, setSources] = useState<any[]>([]);
  const [selectedSourceId, setSelectedSourceId] = useState<string>('');
  const [copiedSnippet, setCopiedSnippet] = useState<string | null>(null);
  const [previewDevice, setPreviewDevice] = useState<'desktop' | 'mobile'>('desktop');

  // Form customizer state
  const [formTitle, setFormTitle] = useState('Schedule a Viewing');
  const [formSubtitle, setFormSubtitle] = useState('Leave your details and a dedicated property advisor will contact you.');
  const [buttonText, setButtonText] = useState('Submit Inquiry');
  const [buttonColor, setButtonColor] = useState('#111827');

  const [fields, setFields] = useState<FormFieldConfig[]>([
    { id: 'name', label: 'Full Name', enabled: true, required: true, placeholder: 'e.g. Rahul Sharma' },
    { id: 'phone', label: 'Phone Number', enabled: true, required: true, placeholder: '+91 98765 43210' },
    { id: 'email', label: 'Email Address', enabled: true, required: false, placeholder: 'you@example.com' },
    { id: 'budget', label: 'Target Budget', enabled: true, required: false, placeholder: 'e.g. ₹75L or 1.5 Cr' },
    { id: 'city', label: 'Preferred Location', enabled: true, required: false, placeholder: 'e.g. Whitefield, Indiranagar' },
    { id: 'property_type', label: 'Property Type', enabled: true, required: false, placeholder: 'Select Property Type' },
    { id: 'message', label: 'Requirements / Notes', enabled: true, required: false, placeholder: 'Specific bedrooms, amenities, or move-in timeframe...' },
  ]);

  useEffect(() => {
    async function loadSources() {
      try {
        const data = await api.leadCapture.listSources();
        if (data && data.length > 0) {
          setSources(data);
          setSelectedSourceId(data[0].id);
        }
      } catch (err) {
        console.error('Failed to load sources for form builder', err);
      }
    }
    loadSources();
  }, []);

  const selectedSource = sources.find((s) => s.id === selectedSourceId);
  const token = selectedSource?.webhook_url_token || 'bl_src_demo_token';
  const apiOrigin = typeof window !== 'undefined' ? window.location.origin : 'http://localhost:3000';
  const embedScriptUrl = `${apiOrigin}/api/v1/public/lead-capture/forms/${token}/embed.js`;

  const scriptSnippet = `<!-- WefyLabs Lead Capture Embed -->\n<div id="wefylabs-lead-form-${token}"></div>\n<script src="${embedScriptUrl}" async></script>`;
  const iframeSnippet = `<!-- WefyLabs Responsive iFrame Embed -->\n<iframe\n  src="${apiOrigin}/api/v1/public/lead-capture/forms/${token}/frame"\n  width="100%"\n  height="540"\n  frameborder="0"\n  style="border-radius: 12px; border: 1px solid #E5E7EB; max-width: 480px;"\n></iframe>`;

  const handleToggleField = (id: string) => {
    if (id === 'name' || id === 'phone') return; // Core contact fields cannot be disabled
    setFields((prev) =>
      prev.map((f) => (f.id === id ? { ...f, enabled: !f.enabled } : f))
    );
  };

  const handleToggleRequired = (id: string) => {
    if (id === 'name' || id === 'phone') return; // Core contact fields are strictly required
    setFields((prev) =>
      prev.map((f) => (f.id === id ? { ...f, required: !f.required } : f))
    );
  };

  const copySnippet = (text: string, type: string) => {
    navigator.clipboard.writeText(text);
    setCopiedSnippet(type);
    setTimeout(() => setCopiedSnippet(null), 2500);
  };

  return (
    <div className="min-h-screen bg-[#F8F9FA] text-gray-900 pb-16">
      <DashboardNav />

      <main className="max-w-[1400px] mx-auto pt-20 px-4 sm:px-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 py-6 border-b border-gray-200">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="px-2 py-0.5 rounded text-[10px] font-extrabold uppercase tracking-widest bg-gray-900 text-white">
                Part 26
              </span>
              <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-gray-900">
                Embeddable Form Builder
              </h1>
            </div>
            <p className="text-xs sm:text-sm text-gray-500">
              Customize fields, preview in real time, and generate drop-in embed code for client websites.
            </p>
          </div>

          {sources.length > 0 && (
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-gray-500">Source:</span>
              <select
                value={selectedSourceId}
                onChange={(e) => setSelectedSourceId(e.target.value)}
                className="px-3 py-1.5 border border-gray-300 rounded-lg text-xs font-semibold bg-white focus:outline-none focus:ring-2 focus:ring-gray-900"
              >
                {sources.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} ({s.channel})
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>

        {/* Lead Capture Sub Navigation */}
        <div className="my-4 rounded-xl overflow-hidden border border-gray-200 shadow-sm">
          <LeadCaptureNav />
        </div>

        {/* Builder Grid: Controls (Left) & Live Preview (Right) */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 mb-10">
          {/* Controls Panel */}
          <div className="lg:col-span-5 space-y-5">
            {/* Appearance Settings */}
            <div className="p-5 bg-white rounded-2xl border border-gray-200/80 shadow-sm">
              <div className="flex items-center gap-2 mb-4">
                <Settings2 className="w-4 h-4 text-gray-700" />
                <h3 className="text-sm font-bold text-gray-900">Appearance & Copy</h3>
              </div>

              <div className="space-y-3">
                <div>
                  <label className="block text-[11px] font-semibold text-gray-600 mb-1">Form Heading</label>
                  <input
                    type="text"
                    value={formTitle}
                    onChange={(e) => setFormTitle(e.target.value)}
                    className="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-xs focus:ring-2 focus:ring-gray-900 focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-semibold text-gray-600 mb-1">Subtitle / Notice</label>
                  <input
                    type="text"
                    value={formSubtitle}
                    onChange={(e) => setFormSubtitle(e.target.value)}
                    className="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-xs focus:ring-2 focus:ring-gray-900 focus:outline-none"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-[11px] font-semibold text-gray-600 mb-1">Button Text</label>
                    <input
                      type="text"
                      value={buttonText}
                      onChange={(e) => setButtonText(e.target.value)}
                      className="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-xs focus:ring-2 focus:ring-gray-900 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-semibold text-gray-600 mb-1">Button Color</label>
                    <div className="flex items-center gap-2">
                      <input
                        type="color"
                        value={buttonColor}
                        onChange={(e) => setButtonColor(e.target.value)}
                        className="w-8 h-8 rounded border border-gray-300 cursor-pointer p-0"
                      />
                      <span className="text-[11px] font-mono text-gray-600 font-semibold uppercase">{buttonColor}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Field Toggles */}
            <div className="p-5 bg-white rounded-2xl border border-gray-200/80 shadow-sm">
              <div className="flex items-center gap-2 mb-4">
                <FormInput className="w-4 h-4 text-gray-700" />
                <h3 className="text-sm font-bold text-gray-900">Field Configuration</h3>
              </div>

              <div className="divide-y divide-gray-100">
                {fields.map((field) => (
                  <div key={field.id} className="py-2.5 flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2.5">
                      <input
                        type="checkbox"
                        checked={field.enabled}
                        disabled={field.id === 'name' || field.id === 'phone'}
                        onChange={() => handleToggleField(field.id)}
                        className="rounded border-gray-300 text-gray-900 focus:ring-gray-900 cursor-pointer"
                      />
                      <span className={`font-semibold ${field.enabled ? 'text-gray-900' : 'text-gray-400'}`}>
                        {field.label}
                      </span>
                    </div>

                    <div className="flex items-center gap-3">
                      <label className="flex items-center gap-1 text-[11px] text-gray-500 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={field.required}
                          disabled={!field.enabled || field.id === 'name' || field.id === 'phone'}
                          onChange={() => handleToggleRequired(field.id)}
                          className="rounded border-gray-300 text-gray-900 focus:ring-gray-900"
                        />
                        Required
                      </label>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Embed Code Snippets Card */}
            <div className="p-5 bg-white rounded-2xl border border-gray-200/80 shadow-sm">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <Code2 className="w-4 h-4 text-gray-700" />
                  <h3 className="text-sm font-bold text-gray-900">Generated Embed Code</h3>
                </div>
                <button
                  onClick={() => copySnippet(scriptSnippet, 'script')}
                  className="text-xs font-bold text-gray-900 hover:underline inline-flex items-center gap-1"
                >
                  {copiedSnippet === 'script' ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3" />}
                  {copiedSnippet === 'script' ? 'Copied' : 'Copy Script Tag'}
                </button>
              </div>

              <pre className="p-3 bg-gray-950 text-emerald-400 font-mono text-[11px] rounded-lg overflow-x-auto whitespace-pre-wrap mb-4">
                {scriptSnippet}
              </pre>

              <div className="flex items-center justify-between mb-2">
                <span className="text-[11px] font-semibold text-gray-600">Alternative: iFrame Tag</span>
                <button
                  onClick={() => copySnippet(iframeSnippet, 'iframe')}
                  className="text-[11px] font-bold text-gray-700 hover:underline inline-flex items-center gap-1"
                >
                  {copiedSnippet === 'iframe' ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3" />}
                  {copiedSnippet === 'iframe' ? 'Copied' : 'Copy iFrame'}
                </button>
              </div>
              <pre className="p-2.5 bg-gray-100 text-gray-700 font-mono text-[10px] rounded-lg overflow-x-auto whitespace-pre-wrap">
                {iframeSnippet}
              </pre>
            </div>
          </div>

          {/* Live Preview Panel */}
          <div className="lg:col-span-7">
            <div className="bg-white rounded-2xl border border-gray-200/80 shadow-sm p-6 flex flex-col items-center">
              {/* Preview Toolbar */}
              <div className="w-full flex items-center justify-between mb-6 pb-3 border-b border-gray-100">
                <div className="flex items-center gap-2">
                  <Eye className="w-4 h-4 text-emerald-600" />
                  <span className="text-xs font-bold text-gray-900 uppercase tracking-wider">Live Form Preview</span>
                </div>

                <div className="flex items-center bg-gray-100 p-0.5 rounded-lg">
                  <button
                    onClick={() => setPreviewDevice('desktop')}
                    className={`p-1.5 rounded-md text-xs font-semibold flex items-center gap-1.5 transition ${
                      previewDevice === 'desktop' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-900'
                    }`}
                  >
                    <Monitor className="w-3.5 h-3.5" /> Desktop
                  </button>
                  <button
                    onClick={() => setPreviewDevice('mobile')}
                    className={`p-1.5 rounded-md text-xs font-semibold flex items-center gap-1.5 transition ${
                      previewDevice === 'mobile' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-900'
                    }`}
                  >
                    <Smartphone className="w-3.5 h-3.5" /> Mobile
                  </button>
                </div>
              </div>

              {/* Form Frame */}
              <div
                className={`transition-all duration-300 w-full p-6 bg-white border border-gray-200 rounded-2xl shadow-sm ${
                  previewDevice === 'mobile' ? 'max-w-[360px]' : 'max-w-[460px]'
                }`}
              >
                <div className="mb-5">
                  <h3 className="text-lg font-bold text-gray-900 leading-tight mb-1">{formTitle}</h3>
                  <p className="text-xs text-gray-500">{formSubtitle}</p>
                </div>

                <form onSubmit={(e) => e.preventDefault()} className="space-y-3">
                  {fields
                    .filter((f) => f.enabled)
                    .map((field) => (
                      <div key={field.id}>
                        <label className="block text-[11px] font-semibold text-gray-700 mb-1">
                          {field.label} {field.required && <span className="text-rose-500">*</span>}
                        </label>
                        {field.id === 'property_type' ? (
                          <select className="w-full px-3 py-2 border border-gray-300 rounded-lg text-xs bg-white focus:outline-none focus:ring-2 focus:ring-gray-900">
                            <option>Apartment / Flat</option>
                            <option>Villa / Row House</option>
                            <option>Penthouse</option>
                            <option>Plot / Land</option>
                            <option>Commercial Office</option>
                          </select>
                        ) : field.id === 'message' ? (
                          <textarea
                            rows={2}
                            placeholder={field.placeholder}
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-gray-900"
                          />
                        ) : (
                          <input
                            type={field.id === 'email' ? 'email' : field.id === 'phone' ? 'tel' : 'text'}
                            placeholder={field.placeholder}
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-gray-900"
                          />
                        )}
                      </div>
                    ))}

                  <div className="pt-2">
                    <button
                      type="button"
                      style={{ backgroundColor: buttonColor }}
                      className="w-full py-2.5 px-4 text-white text-xs font-bold rounded-lg shadow-sm hover:opacity-95 transition"
                    >
                      {buttonText}
                    </button>
                  </div>

                  <p className="text-[10px] text-gray-400 text-center mt-3">
                    Protected by Honeypot anti-spam & rate limiting. Powered by WefyLabs.
                  </p>
                </form>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
