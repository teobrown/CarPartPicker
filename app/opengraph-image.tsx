import { ImageResponse } from 'next/og';

// 1200x630 OpenGraph card — what shows up when someone pastes a
// carbuildr.com link into iMessage / Slack / Discord / Twitter.
// Brutalist editorial layout: logomark + wordmark on the left, tagline
// and stat row on the right, hairline grid background. No external
// fonts — uses system sans so the edge runtime doesn't have to fetch.

export const alt = 'Carbuildr — Compatibility-checked tuner part builds';
export const size = { width: 1200, height: 630 };
export const contentType = 'image/png';

const BG = '#1F1C19';
const BG_DEEP = '#161310';
const FG = '#ECE7DF';
const FG_DIM = '#6E665B';
const SIGNAL = '#F5C535';
const LINE = '#3A352E';

export default async function OpengraphImage() {
  // Logomark: 3x3 grid, top-left signal cell. Larger version of the
  // header logomark — same design language so the OG card ties to the
  // site instantly.
  const cell = 56;
  const stroke = 3;
  const gridSize = cell * 3;

  return new ImageResponse(
    (
      <div
        style={{
          width: 1200,
          height: 630,
          background: BG,
          display: 'flex',
          flexDirection: 'column',
          position: 'relative',
        }}
      >
        {/* hairline crosshatch — 4 vertical column rules to suggest the */}
        {/* page grid that runs throughout the site                       */}
        {[0.25, 0.5, 0.75].map((p) => (
          <div
            key={p}
            style={{
              position: 'absolute',
              top: 0,
              bottom: 0,
              left: `${p * 100}%`,
              width: 1,
              background: LINE,
            }}
          />
        ))}

        {/* top telemetry strip — mirrors the site header */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            background: BG_DEEP,
            borderBottom: `1px solid ${LINE}`,
            padding: '14px 60px',
            fontSize: 18,
            letterSpacing: '0.18em',
            textTransform: 'uppercase',
            color: FG_DIM,
            fontFamily: 'monospace',
            gap: 16,
          }}
        >
          <div
            style={{
              width: 10,
              height: 10,
              borderRadius: 9999,
              background: SIGNAL,
            }}
          />
          <span style={{ color: FG }}>PIT WALL</span>
          <span>·</span>
          <span>SESSION 001</span>
          <span style={{ marginLeft: 'auto' }}>carbuildr.com</span>
        </div>

        {/* main content row */}
        <div
          style={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            padding: '0 60px',
            gap: 60,
          }}
        >
          {/* logomark */}
          <div
            style={{
              width: gridSize + 24,
              height: gridSize + 24,
              padding: 12,
              border: `1px solid ${LINE}`,
              display: 'flex',
              position: 'relative',
              flexShrink: 0,
            }}
          >
            <div
              style={{
                position: 'relative',
                width: gridSize,
                height: gridSize,
                border: `${stroke}px solid ${FG_DIM}`,
                display: 'flex',
              }}
            >
              {/* signal cell top-left */}
              <div
                style={{
                  position: 'absolute',
                  left: 0,
                  top: 0,
                  width: cell,
                  height: cell,
                  background: SIGNAL,
                }}
              />
              {/* horizontal grid lines */}
              {[1, 2].map((i) => (
                <div
                  key={`h${i}`}
                  style={{
                    position: 'absolute',
                    left: 0,
                    top: cell * i - stroke / 2,
                    width: gridSize,
                    height: stroke,
                    background: FG_DIM,
                  }}
                />
              ))}
              {/* vertical grid lines */}
              {[1, 2].map((i) => (
                <div
                  key={`v${i}`}
                  style={{
                    position: 'absolute',
                    left: cell * i - stroke / 2,
                    top: 0,
                    width: stroke,
                    height: gridSize,
                    background: FG_DIM,
                  }}
                />
              ))}
            </div>
          </div>

          {/* headline cluster */}
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              flex: 1,
              minWidth: 0,
            }}
          >
            <div
              style={{
                fontSize: 18,
                letterSpacing: '0.2em',
                textTransform: 'uppercase',
                color: SIGNAL,
                fontFamily: 'monospace',
                marginBottom: 18,
              }}
            >
              [001] · The PCPartPicker for tuner cars
            </div>
            <div
              style={{
                display: 'flex',
                alignItems: 'baseline',
                fontSize: 132,
                fontWeight: 600,
                color: FG,
                lineHeight: 1,
                letterSpacing: '-0.03em',
              }}
            >
              <span>Carbuildr</span>
              <span style={{ color: SIGNAL }}>.</span>
            </div>
            <div
              style={{
                fontSize: 28,
                color: FG_DIM,
                marginTop: 28,
                lineHeight: 1.3,
                maxWidth: 640,
              }}
            >
              Pick your car. Get a compatibility-checked catalog of bolt-ons,
              suspension, wheels, and body mods. Build it. Buy it.
            </div>
          </div>
        </div>

        {/* bottom strip */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            background: BG_DEEP,
            borderTop: `1px solid ${LINE}`,
            padding: '18px 60px',
            fontSize: 16,
            letterSpacing: '0.18em',
            textTransform: 'uppercase',
            color: FG_DIM,
            fontFamily: 'monospace',
          }}
        >
          <span>Compatibility · checked</span>
          <span>Affiliate · supported</span>
          <span>Free for users</span>
        </div>
      </div>
    ),
    { ...size },
  );
}
