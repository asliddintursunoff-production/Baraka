import { Component, type ErrorInfo, type ReactNode } from "react";

/** One broken card never takes the page down: it renders a short note instead. */
export class BlockBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("block render failed", error, info.componentStack);
  }

  render() {
    if (this.state.failed) {
      return (
        <div className="rounded-inner border border-border bg-bg p-3 text-13 text-text-3">
          Bu kartani ko&apos;rsatib bo&apos;lmadi.
        </div>
      );
    }
    return this.props.children;
  }
}

/** Route-level fallback instead of React Router's developer error page. */
export function RouteError() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-bg p-6">
      <div className="flex max-w-[420px] flex-col items-center gap-3 rounded-card border border-border bg-surface p-8 text-center">
        <h1 className="m-0 font-display text-20 font-bold">Nimadir xato ketdi</h1>
        <p className="m-0 text-15 text-text-3">Sahifani qayta yuklang. Muammo takrorlansa, birozdan keyin urinib ko&apos;ring.</p>
        <button
          type="button"
          onClick={() => window.location.reload()}
          className="inline-flex min-h-tap items-center rounded-btn border-0 bg-primary px-[18px] text-15 font-semibold text-white hover:bg-primary-hover"
        >
          Qayta yuklash
        </button>
      </div>
    </div>
  );
}
