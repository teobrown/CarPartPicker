import { ImageResponse } from 'next/og';

// 32x32 brand favicon — same 3x3 grid logomark used in the site header.
// Top-left cell filled signal amber, the remaining 8 cells are outlined
// hairlines on near-black warm bg. Pure shapes, no fonts — keeps file
// size tiny and scales crisply on retina tabs / pinned tabs.

export const size = { width: 32, height: 32 };
export const contentType = 'image/png';

const BG = '#1F1C19';
const SIGNAL = '#F5C535';
const LINE = '#5A554C';

export default function Icon() {
  // 3x3 grid lives inside a 24x24 viewBox at 4..28 of the 32x32 canvas.
  // Each cell is 8px wide. We render absolute-positioned divs since
  // ImageResponse doesn't support full SVG path/line rendering — it
  // composes flex/abs-positioned blocks the same way OG images do.
  const cell = 8;
  const x0 = 4;
  const y0 = 4;
  return new ImageResponse(
    (
      <div
        style={{
          width: 32,
          height: 32,
          background: BG,
          position: 'relative',
          display: 'flex',
        }}
      >
        {/* outer frame */}
        <div
          style={{
            position: 'absolute',
            left: x0,
            top: y0,
            width: cell * 3,
            height: cell * 3,
            border: `1px solid ${LINE}`,
          }}
        />
        {/* signal cell (top-left) */}
        <div
          style={{
            position: 'absolute',
            left: x0,
            top: y0,
            width: cell,
            height: cell,
            background: SIGNAL,
          }}
        />
        {/* horizontal grid lines */}
        <div
          style={{
            position: 'absolute',
            left: x0,
            top: y0 + cell,
            width: cell * 3,
            height: 1,
            background: LINE,
          }}
        />
        <div
          style={{
            position: 'absolute',
            left: x0,
            top: y0 + cell * 2,
            width: cell * 3,
            height: 1,
            background: LINE,
          }}
        />
        {/* vertical grid lines */}
        <div
          style={{
            position: 'absolute',
            left: x0 + cell,
            top: y0,
            width: 1,
            height: cell * 3,
            background: LINE,
          }}
        />
        <div
          style={{
            position: 'absolute',
            left: x0 + cell * 2,
            top: y0,
            width: 1,
            height: cell * 3,
            background: LINE,
          }}
        />
      </div>
    ),
    { ...size },
  );
}
