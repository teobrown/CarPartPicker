'use client';

import { useState, useTransition } from 'react';
import Link from 'next/link';
import { PartPickerModal } from './part-picker-modal';
import { CompatBadge } from './compat-badge';
import { removeItemAction } from '@/app/build/[slug]/edit-actions';
import type { BuildItemRow } from '@/lib/queries/builds';
import type { CompatStatus } from '@/lib/queries/compat';
import { partSlug, formatPrice } from '@/lib/format';

type Props = {
  buildSlug: string;
  vehicleId: number;
  categorySlug: string;
  categoryLabel: string;
  item:
    | (BuildItemRow & {
        compatStatus?: CompatStatus;
        compatCaveat?: string | null;
      })
    | null;
};

export function BuildRow({
  buildSlug,
  vehicleId,
  categorySlug,
  categoryLabel,
  item,
}: Props) {
  const [open, setOpen] = useState(false);
  const [pending, startTransition] = useTransition();

  return (
    <>
      <li className="hairline-soft-b py-4 px-5 grid grid-cols-12 gap-3 items-center row-hover">
        <span className="col-span-2 eyebrow text-fg-dim">{categoryLabel}</span>
        {item ? (
          <>
            <Link
              href={`/part/${partSlug(item.part.brand)}/${partSlug(item.part.model)}`}
              className="col-span-5 min-w-0 block"
            >
              <span className="block text-[10px] tracking-[0.14em] uppercase font-[family-name:var(--font-mono)] text-fg-dim">
                {item.part.brand}
              </span>
              <span className="display-md text-base text-fg leading-tight truncate block">
                {item.part.model}
              </span>
            </Link>
            <span className="col-span-2">
              {item.compatStatus && (
                <CompatBadge status={item.compatStatus} caveat={item.compatCaveat} />
              )}
            </span>
            <span className="col-span-2 figure text-right text-fg">
              {formatPrice(item.part.cheapestPriceCents)}
            </span>
            <span className="col-span-1 text-right">
              <button
                onClick={() =>
                  startTransition(() =>
                    removeItemAction({ slug: buildSlug, partId: item.part.id }),
                  )
                }
                disabled={pending}
                className="text-fg-dim hover:text-danger text-[11px] tracking-[0.1em] uppercase font-[family-name:var(--font-mono)]"
                title="Remove from build"
              >
                ×
              </button>
            </span>
          </>
        ) : (
          <>
            <span className="col-span-7 italic text-fg-dim text-sm">— empty</span>
            <span className="col-span-2 text-right">
              <button onClick={() => setOpen(true)} className="btn-ghost py-1.5">
                + ADD
              </button>
            </span>
            <span className="col-span-1" />
          </>
        )}
      </li>
      <PartPickerModal
        open={open}
        onClose={() => setOpen(false)}
        buildSlug={buildSlug}
        vehicleId={vehicleId}
        categorySlug={categorySlug}
        categoryLabel={categoryLabel}
      />
    </>
  );
}
