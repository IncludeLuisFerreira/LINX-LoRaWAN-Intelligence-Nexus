import type { ReactNode, SVGProps } from 'react';

type IconProps = SVGProps<SVGSVGElement>;

function Base({ children, ...props }: IconProps & { children: ReactNode }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={props.className ?? 'h-5 w-5'}
      {...props}
    >
      {children}
    </svg>
  );
}

export const Plus = (p: IconProps) => (
  <Base {...p}>
    <path d="M12 5v14M5 12h14" />
  </Base>
);

export const Trash = (p: IconProps) => (
  <Base {...p}>
    <path d="M3 6h18M8 6V4h8v2m-9 0 1 14h8l1-14" />
  </Base>
);

export const Edit = (p: IconProps) => (
  <Base {...p}>
    <path d="M12 20h9" />
    <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z" />
  </Base>
);

export const ChevronRight = (p: IconProps) => (
  <Base {...p}>
    <path d="m9 6 6 6-6 6" />
  </Base>
);

export const Menu = (p: IconProps) => (
  <Base {...p}>
    <path d="M4 6h16M4 12h16M4 18h16" />
  </Base>
);

export const Building = (p: IconProps) => (
  <Base {...p}>
    <path d="M3 21h18M6 21V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v17M16 21v-9h3a1 1 0 0 1 1 1v8M9 7h1M9 11h1M9 15h1" />
  </Base>
);

export const Layers = (p: IconProps) => (
  <Base {...p}>
    <path d="m12 2 9 5-9 5-9-5 9-5ZM3 12l9 5 9-5M3 17l9 5 9-5" />
  </Base>
);

export const Cpu = (p: IconProps) => (
  <Base {...p}>
    <rect x="4" y="4" width="16" height="16" rx="2" />
    <rect x="9" y="9" width="6" height="6" />
    <path d="M9 1v3M15 1v3M9 20v3M15 20v3M1 9h3M1 15h3M20 9h3M20 15h3" />
  </Base>
);

export const Search = (p: IconProps) => (
  <Base {...p}>
    <circle cx="11" cy="11" r="7" />
    <path d="m21 21-4.3-4.3" />
  </Base>
);

export const Refresh = (p: IconProps) => (
  <Base {...p}>
    <path d="M3 12a9 9 0 0 1 15-6.7L21 8M21 3v5h-5M21 12a9 9 0 0 1-15 6.7L3 16M3 21v-5h5" />
  </Base>
);

export const Close = (p: IconProps) => (
  <Base {...p}>
    <path d="M18 6 6 18M6 6l12 12" />
  </Base>
);

export const Device = (p: IconProps) => (
  <Base {...p}>
    <rect x="5" y="5" width="14" height="14" rx="2" />
    <path d="M12 9v6M9 12h6" />
  </Base>
);
