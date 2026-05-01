import type { BuildDetail } from '@/lib/queries/builds';
import { formatPrice } from '@/lib/format';

export function BuildSummary({ build }: { build: BuildDetail }) {
  const total = build.items.reduce<number>(
    (acc, it) => acc + (it.part.cheapestPriceCents ?? 0),
    0,
  );

  return (
    <div className="hairline bg-bg-deep">
      <div className="px-5 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="pip pip-amber" />
          <span className="eyebrow-signal text-[11px]">PHASE 1 PREVIEW · COMPAT ENGINE LIVE</span>
        </div>
        <span className="font-[family-name:var(--font-mono)] text-[12px] text-fg-muted">
          {build.items.length} parts · last updated{' '}
          {new Date(build.createdAt).toISOString().slice(0, 16).replace('T', ' ')}
        </span>
      </div>
      <div className="hairline-t px-5 py-4 flex items-baseline justify-between">
        <span className="eyebrow">Total</span>
        <span className="figure text-3xl text-signal">{formatPrice(total)}</span>
      </div>
      <div className="hairline-t px-5 py-3">
        <p className="eyebrow text-fg-dim text-[10px]">
          warnings live in v2 of the editor
        </p>
      </div>
    </div>
  );
}
