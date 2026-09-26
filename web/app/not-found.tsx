import Link from "next/link";

export default function NotFound() {
  return (
    <section className="py-24 text-center">
      <p className="text-[11px] font-mono uppercase tracking-[0.18em] text-accent-2">404</p>
      <h1 className="mt-3 text-3xl font-semibold tracking-tight text-heading">Page not found</h1>
      <p className="mt-3 text-sm text-muted">This page does not exist.</p>
      <Link href="/" className="mt-6 inline-block text-sm text-accent hover:underline">
        Back to Overview &#8594;
      </Link>
    </section>
  );
}
