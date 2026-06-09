/**
 * Lightweight inline SVG illustrations for empty states (~140px).
 * Uses currentColor + token vars so they adapt to light/dark automatically.
 */

export function EmptyWalletIllustration({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 160 120"
      className={className}
      width="140"
      height="105"
      role="img"
      aria-hidden
      fill="none"
    >
      <ellipse cx="80" cy="104" rx="56" ry="8" fill="var(--muted)" />
      <rect
        x="34" y="20" width="78" height="58" rx="8"
        fill="var(--card)" stroke="var(--border)" strokeWidth="2"
        transform="rotate(-6 73 49)"
      />
      <rect
        x="48" y="30" width="82" height="60" rx="8"
        fill="var(--card)" stroke="var(--border)" strokeWidth="2"
      />
      <rect x="58" y="42" width="34" height="5" rx="2.5" fill="var(--muted-foreground)" opacity="0.5" />
      <rect x="58" y="54" width="62" height="4" rx="2" fill="var(--muted)" />
      <rect x="58" y="63" width="50" height="4" rx="2" fill="var(--muted)" />
      <rect x="58" y="72" width="40" height="4" rx="2" fill="var(--muted)" />
      <circle cx="118" cy="34" r="15" fill="var(--primary)" />
      <path
        d="M114 28h6.2a3.6 3.6 0 0 1 .8 7.1 3.8 3.8 0 0 1-.7 4.9H114V28Zm2.6 2.3v2.5h3.1a1.25 1.25 0 0 0 0-2.5h-3.1Zm0 4.6v2.6h3.3a1.3 1.3 0 0 0 0-2.6h-3.3Z"
        fill="var(--primary-foreground)"
      />
    </svg>
  );
}

export function NoResultsIllustration({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 160 120"
      className={className}
      width="132"
      height="99"
      role="img"
      aria-hidden
      fill="none"
    >
      <ellipse cx="80" cy="104" rx="50" ry="7" fill="var(--muted)" />
      <rect
        x="44" y="26" width="72" height="58" rx="8"
        fill="var(--card)" stroke="var(--border)" strokeWidth="2"
      />
      <rect x="56" y="40" width="36" height="4" rx="2" fill="var(--muted)" />
      <rect x="56" y="50" width="48" height="4" rx="2" fill="var(--muted)" />
      <rect x="56" y="60" width="28" height="4" rx="2" fill="var(--muted)" />
      <circle cx="104" cy="78" r="18" fill="var(--background)" stroke="var(--primary)" strokeWidth="3" />
      <line x1="117" y1="91" x2="128" y2="102" stroke="var(--primary)" strokeWidth="4" strokeLinecap="round" />
    </svg>
  );
}
