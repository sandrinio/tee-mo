import { createFileRoute } from '@tanstack/react-router';

/**
 * Index route — landing page at `/`.
 *
 * Renders a typography + brand-token demo per STORY-001-03 acceptance criteria:
 *   - "Tee-Mo" heading: Display style from Design Guide §3.2
 *   - Brand swatch: bg-brand-500 box proves coral token is resolved
 *   - Subtitle: slate-500 secondary text
 *   - Monospace code sample: JetBrains Mono, slate-100 bg
 *
 * No API calls. No components beyond HTML. Story 001-04 adds Card/Badge/fetch.
 */
export const Route = createFileRoute('/')({
  component: Landing,
});

/**
 * Landing page component — typography + design-system token demo.
 * Scoped to Sprint 1 scaffold verification; real content arrives in Sprint 2.
 */
function Landing() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-16">
      <div className="flex items-center gap-4">
        {/* Brand swatch — verifies bg-brand-500 resolves to #F43F5E */}
        <div className="h-10 w-10 rounded-md bg-brand-500" aria-hidden="true" />
        <h1 className="text-4xl font-semibold tracking-tight text-slate-900">
          Tee-Mo
        </h1>
      </div>
      <p className="mt-3 text-base text-slate-500">Your BYOK Slack assistant.</p>
      <pre className="mt-8 rounded-md bg-slate-100 px-4 py-3 font-mono text-sm text-slate-700">
        {`GET /api/health → {"status":"ok"}`}
      </pre>
    </main>
  );
}
