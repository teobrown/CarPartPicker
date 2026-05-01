'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';

type Step = 'make' | 'model' | 'year' | 'trim';

export function VehiclePicker() {
  const router = useRouter();
  const [make, setMake] = useState<string | null>(null);
  const [modelName, setModelName] = useState<string | null>(null);
  const [year, setYear] = useState<number | null>(null);
  const [vehicleId, setVehicleId] = useState<number | null>(null);

  const [makes, setMakes] = useState<string[]>([]);
  const [models, setModels] = useState<string[]>([]);
  const [years, setYears] = useState<number[]>([]);
  const [trims, setTrims] = useState<{ id: number; trim: string | null; subModel: string | null; generation: string }[]>([]);

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // load makes on mount
  useEffect(() => {
    void fetchOptions('make').then((d) => setMakes(d.options as string[]));
  }, []);
  useEffect(() => {
    if (!make) { setModels([]); setModelName(null); return; }
    void fetchOptions('model', { make }).then((d) => setModels(d.options as string[]));
  }, [make]);
  useEffect(() => {
    if (!make || !modelName) { setYears([]); setYear(null); return; }
    void fetchOptions('year', { make, model: modelName }).then((d) => setYears(d.options as number[]));
  }, [make, modelName]);
  useEffect(() => {
    if (!make || !modelName || !year) { setTrims([]); setVehicleId(null); return; }
    void fetchOptions('trim', { make, model: modelName, year: String(year) }).then((d) => setTrims(d.options as typeof trims));
  }, [make, modelName, year]);

  async function startBuild() {
    if (!vehicleId) return;
    setSubmitting(true);
    setError(null);
    try {
      const r = await fetch('/api/builds', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ vehicleId }),
      });
      if (!r.ok) {
        setError('Could not start build. Try again.');
        return;
      }
      const { slug } = await r.json();
      router.push(`/build/${slug}`);
    } catch {
      setError('Network error.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="hairline bg-surface p-5">
      <p className="eyebrow-signal text-[10px] mb-4">[VEH] · Pick your platform</p>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Select label="Make"   value={make ?? ''}      options={makes.map((m) => ({ label: m, value: m }))}                                              onChange={(v) => { setMake(v || null); setModelName(null); setYear(null); setVehicleId(null); }} />
        <Select label="Model"  value={modelName ?? ''} options={models.map((m) => ({ label: m, value: m }))}                                             onChange={(v) => { setModelName(v || null); setYear(null); setVehicleId(null); }} disabled={!make} />
        <Select label="Year"   value={year ? String(year) : ''} options={years.map((y) => ({ label: String(y), value: String(y) }))}                  onChange={(v) => { setYear(v ? Number(v) : null); setVehicleId(null); }} disabled={!modelName} />
        <Select label="Trim"   value={vehicleId ? String(vehicleId) : ''}
                options={trims.map((t) => ({ label: trimLabel(t), value: String(t.id) }))}
                onChange={(v) => setVehicleId(v ? Number(v) : null)}
                disabled={!year} />
      </div>
      {error && <p className="text-danger eyebrow text-[10px] mt-3">{error}</p>}
      <div className="flex items-center gap-3 mt-5">
        <button
          onClick={startBuild}
          disabled={!vehicleId || submitting}
          className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {submitting ? 'STARTING…' : 'START BUILD →'}
        </button>
        <a href="/parts" className="arrow-link">Or browse the catalog</a>
      </div>
    </div>
  );
}

function trimLabel(t: { trim: string | null; subModel: string | null; generation: string }) {
  return [t.subModel, t.trim, `(${t.generation})`].filter(Boolean).join(' · ');
}

async function fetchOptions(level: Step, params: Record<string, string> = {}) {
  const u = new URL('/api/vehicles', window.location.origin);
  for (const [k, v] of Object.entries(params)) u.searchParams.set(k, v);
  const r = await fetch(u.toString());
  if (!r.ok) throw new Error(`fetch failed: ${r.status}`);
  return (await r.json()) as { level: Step; options: unknown[] };
}

function Select({
  label,
  value,
  options,
  onChange,
  disabled,
}: {
  label: string;
  value: string;
  options: { label: string; value: string }[];
  onChange: (v: string) => void;
  disabled?: boolean;
}) {
  return (
    <label className="block">
      <span className="eyebrow text-[10px]">{label}</span>
      <select
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        className="mt-2 w-full bg-bg-deep hairline px-3 py-2 text-sm font-[family-name:var(--font-mono)] text-fg disabled:text-fg-dim disabled:cursor-not-allowed appearance-none"
      >
        <option value="">{disabled ? '—' : `Select ${label.toLowerCase()}`}</option>
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </label>
  );
}
