import type { CompatStatus } from '@/lib/queries/compat';

const META: Record<
  CompatStatus,
  { pip: string; label: string; color: string }
> = {
  fits: { pip: 'pip', label: 'Fits', color: 'text-good' },
  fits_with_caveat: { pip: 'pip pip-amber', label: 'Caveat', color: 'text-signal' },
  unknown: { pip: 'pip pip-dim', label: 'Unknown', color: 'text-fg-muted' },
  incompatible: { pip: 'pip pip-red', label: 'No fit', color: 'text-danger' },
};

export function CompatBadge({
  status,
  caveat,
}: {
  status: CompatStatus;
  caveat?: string | null;
}) {
  const meta = META[status];
  return (
    <span
      className={`inline-flex items-center gap-2 text-[10px] tracking-[0.12em] uppercase font-[family-name:var(--font-mono)] ${meta.color}`}
      title={caveat ?? undefined}
    >
      <span className={meta.pip} />
      {meta.label}
    </span>
  );
}
