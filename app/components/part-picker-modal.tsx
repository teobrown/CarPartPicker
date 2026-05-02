'use client';

import { useEffect, useState, useTransition } from 'react';
import { addItemAction } from '@/app/build/[slug]/edit-actions';
import { CompatBadge } from './compat-badge';
import { formatPrice } from '@/lib/format';
import type { CompatStatus } from '@/lib/queries/compat';

export type PartPickerProps = {
  open: boolean;
  onClose: () => void;
  buildSlug: string;
  vehicleId: number;
  categorySlug: string;
  categoryLabel: string;
};

type Row = {
  id: number;
  brand: string;
  model: string;
  name: string;
  cheapestPriceCents: number | null;
  vendorCount: number;
  status: CompatStatus;
  caveat: string | null;
};

export function PartPickerModal(p: PartPickerProps) {
  const [rows, setRows] = useState<Row[]>([]);
  const [q, setQ] = useState('');
  const [isPending, startTransition] = useTransition();

  // Fetch ranked parts whenever the modal opens or the search/category/vehicle changes.
  // hideIncompatible=true: only parts that could plausibly fit this vehicle. Parts
  // demoted to "incompatible" by the make-name heuristic (or by an explicit fitment
  // rule) are filtered out server-side. Catalog browse pages don't pass this flag.
  useEffect(() => {
    if (!p.open) return;
    const u = new URL('/api/parts/search', window.location.origin);
    u.searchParams.set('category', p.categorySlug);
    u.searchParams.set('vehicleId', String(p.vehicleId));
    u.searchParams.set('hideIncompatible', 'true');
    if (q) u.searchParams.set('q', q);
    let cancelled = false;
    void fetch(u.toString())
      .then((r) => r.json())
      .then((d) => {
        if (!cancelled) setRows((d.parts as Row[]) ?? []);
      })
      .catch(() => {
        if (!cancelled) setRows([]);
      });
    return () => {
      cancelled = true;
    };
  }, [p.open, p.categorySlug, p.vehicleId, q]);

  // ESC closes the modal cleanly.
  useEffect(() => {
    if (!p.open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') p.onClose();
    }
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [p.open, p.onClose, p]);

  // Reset the search box every time we reopen the modal.
  useEffect(() => {
    if (!p.open) setQ('');
  }, [p.open]);

  if (!p.open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-end md:items-center justify-center"
      role="dialog"
      aria-modal="true"
    >
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={p.onClose} />
      <div className="relative w-full md:max-w-3xl max-h-[85vh] overflow-hidden bg-bg hairline flex flex-col">
        <div className="hairline-b px-5 py-4 flex items-center justify-between">
          <div>
            <p className="eyebrow-signal text-[10px]">[PICK PART]</p>
            <h3 className="display-md text-base mt-1">{p.categoryLabel}</h3>
          </div>
          <button onClick={p.onClose} className="btn-ghost">CLOSE</button>
        </div>
        <div className="hairline-b px-5 py-3">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search by brand or model…"
            autoFocus
            className="w-full bg-bg-deep hairline px-3 py-2 text-sm font-[family-name:var(--font-mono)] text-fg"
          />
        </div>
        <ul className="overflow-y-auto">
          {rows.map((r) => (
            <li key={r.id}>
              <button
                onClick={() =>
                  startTransition(async () => {
                    await addItemAction({ slug: p.buildSlug, partId: r.id });
                    p.onClose();
                  })
                }
                className="row-hover hairline-soft-b py-3 px-5 grid grid-cols-12 gap-3 items-baseline w-full text-left disabled:opacity-50"
                disabled={isPending}
              >
                <span className="col-span-1 index-marker tabular">
                  {String(r.id).padStart(3, '0')}
                </span>
                <span className="col-span-4 min-w-0">
                  <span className="block text-[10px] tracking-[0.14em] uppercase font-[family-name:var(--font-mono)] text-fg-dim">
                    {r.brand}
                  </span>
                  <span className="display-md text-base text-fg leading-tight truncate block">
                    {r.model}
                  </span>
                </span>
                <span className="col-span-3">
                  <CompatBadge status={r.status} caveat={r.caveat} />
                </span>
                <span className="col-span-2 figure text-fg text-right">
                  {formatPrice(r.cheapestPriceCents)}
                </span>
                <span className="col-span-2 text-right text-[11px] text-fg-muted">
                  ×{r.vendorCount}
                </span>
              </button>
            </li>
          ))}
          {rows.length === 0 && (
            <li className="px-5 py-12 text-center">
              <p className="eyebrow text-[10px] mb-3">[NO MATCHES]</p>
              <p className="display-md text-base mb-2">Nothing here fits your vehicle yet.</p>
              <p className="body-sm max-w-sm mx-auto">
                {q
                  ? "No parts match your search for this category and vehicle. Try a different search term, or browse the full catalog."
                  : "No parts in this category have been indexed for this vehicle yet. Catalog grows as we add more vendors — Phase 2 brings Honda, Toyota, and more."}
              </p>
            </li>
          )}
        </ul>
      </div>
    </div>
  );
}
