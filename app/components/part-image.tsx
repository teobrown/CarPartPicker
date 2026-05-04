'use client';

/**
 * PartImage — specimen-plate part thumbnail.
 *
 * Vendor product photos almost always sit on white. We lean into that with
 * a brutalist "specimen plate" treatment: white background, sharp hairline
 * frame, generous padding, object-contain so the part shape (asymmetric
 * wheels, exhausts, etc.) shows whole. Falls back to a precise mono-typed
 * placeholder when imageUrl is missing OR fails to load (dead CDN URL,
 * mixed-content http on https page, etc.) — same hairline frame so the
 * row geometry stays even.
 *
 * Native <img> rather than next/image: Carbuildr ingests vendor CDN URLs
 * across ~15 hosts (Shopify, BigCommerce, Magento media, etc.), and
 * whitelisting every host in next.config remotePatterns is more cost
 * than benefit for thumbnail-grade images. We add `loading="lazy"`
 * + `decoding="async"` for behavior-equivalent perf.
 */

import { useState } from 'react';

type Size = 'sm' | 'md' | 'lg' | 'hero';

type Props = {
  src: string | null;
  alt: string;
  size?: Size;
  /** Optional mono-typed index that overlays the bottom-right corner. */
  index?: string;
  /** Extra classes on the outer frame (e.g. `shrink-0`). */
  className?: string;
};

const SIZE_CLASS: Record<Size, string> = {
  sm: 'w-12 h-12 p-1',           // 48px — build editor row
  md: 'w-16 h-16 p-1.5',         // 64px — catalog list row
  lg: 'w-24 h-24 p-2',           // 96px — picker modal card / wide list
  hero: 'w-full aspect-square p-6', // hero — part detail page
};

export function PartImage({ src, alt, size = 'md', index, className = '' }: Props) {
  const [failed, setFailed] = useState(false);
  const frameClasses =
    `relative inline-block bg-white text-black hairline overflow-hidden shrink-0 ${SIZE_CLASS[size]} ${className}`.trim();
  const showImg = src && !failed;
  return (
    <div className={frameClasses}>
      {showImg ? (
        <img
          src={src}
          alt={alt}
          loading="lazy"
          decoding="async"
          onError={() => setFailed(true)}
          className="w-full h-full object-contain mix-blend-multiply"
        />
      ) : (
        <span className="absolute inset-0 flex items-center justify-center select-none">
          <span
            className={
              'tracking-[0.2em] font-[family-name:var(--font-mono)] text-neutral-400 ' +
              (size === 'hero'
                ? 'text-[14px]'
                : size === 'lg'
                  ? 'text-[10px]'
                  : 'text-[9px]')
            }
          >
            {size === 'sm' ? '·' : 'NO IMG'}
          </span>
        </span>
      )}
      {index && (
        <span
          className={
            'absolute right-0 bottom-0 px-1.5 py-0.5 text-[9px] tracking-[0.14em] ' +
            'font-[family-name:var(--font-mono)] tabular bg-bg text-fg ' +
            'border-t border-l border-line'
          }
        >
          {index}
        </span>
      )}
    </div>
  );
}
