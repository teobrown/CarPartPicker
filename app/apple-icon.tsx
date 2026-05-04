import { ImageResponse } from 'next/og';

// 180x180 home-screen icon for iOS. Same logomark as /icon, scaled up
// with proportionally thicker grid lines so it reads well at iOS app-
// icon size. iOS adds its own rounded-corner mask, so we fill the
// canvas edge-to-edge with the brand bg.

export const size = { width: 180, height: 180 };
export const contentType = 'image/png';

const BG = '#1F1C19';
const SIGNAL = '#F5C535';
const LINE = '#7A746A';

export default function AppleIcon() {
  // 3x3 grid centered, generous padding. Each cell 40px, grid is 120px,
  // padding 30px each side. Stroke 4px reads well at iOS rendering size.
  const cell = 40;
  const stroke = 4;
  const pad = (180 - cell * 3) / 2;
  return new ImageResponse(
    (
      <div
        style={{
          width: 180,
          height: 180,
          background: BG,
          position: 'relative',
          display: 'flex',
        }}
      >
        <div
          style={{
            position: 'absolute',
            left: pad,
            top: pad,
            width: cell * 3,
            height: cell * 3,
            border: `${stroke}px solid ${LINE}`,
          }}
        />
        <div
          style={{
            position: 'absolute',
            left: pad,
            top: pad,
            width: cell,
            height: cell,
            background: SIGNAL,
          }}
        />
        {[1, 2].map((i) => (
          <div
            key={`h${i}`}
            style={{
              position: 'absolute',
              left: pad,
              top: pad + cell * i - stroke / 2,
              width: cell * 3,
              height: stroke,
              background: LINE,
            }}
          />
        ))}
        {[1, 2].map((i) => (
          <div
            key={`v${i}`}
            style={{
              position: 'absolute',
              left: pad + cell * i - stroke / 2,
              top: pad,
              width: stroke,
              height: cell * 3,
              background: LINE,
            }}
          />
        ))}
      </div>
    ),
    { ...size },
  );
}
