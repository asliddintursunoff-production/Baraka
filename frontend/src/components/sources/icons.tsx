/** Line icons copied from design/pages/Connect.html and Sources.html (decorative: always aria-hidden). */

export function SheetIcon({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" className="shrink-0">
      <rect x="4" y="2" width="16" height="20" rx="2" fill="#067647" />
      <path d="M8 9h8M8 13h8M8 17h8M12 9v8" stroke="#FFFFFF" strokeWidth="1.6" />
    </svg>
  );
}

export function CheckIcon({
  size = 14,
  strokeWidth = 3,
  color = "currentColor",
}: {
  size?: number;
  strokeWidth?: number;
  color?: string;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke={color}
      strokeWidth={strokeWidth}
      aria-hidden="true"
      className="shrink-0"
    >
      <path d="M5 12l5 5 9-10" />
    </svg>
  );
}

export function LockIcon() {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="#475467"
      strokeWidth="2"
      aria-hidden="true"
      className="shrink-0"
    >
      <rect x="5" y="11" width="14" height="10" rx="2" />
      <path d="M8 11V7a4 4 0 0 1 8 0v4" />
    </svg>
  );
}

export function ArrowRightIcon() {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="#FFFFFF"
      strokeWidth="2.2"
      aria-hidden="true"
      className="shrink-0"
    >
      <path d="M5 12h14M13 6l6 6-6 6" />
    </svg>
  );
}

export function AlertIcon({ size = 22 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="#FFFFFF"
      strokeWidth="2.6"
      strokeLinecap="round"
      aria-hidden="true"
      className="shrink-0"
    >
      <path d="M12 7v6M12 17h0" />
    </svg>
  );
}
