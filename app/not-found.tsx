import Link from "next/link";
import { SiteHeader } from "@/app/components/site-header";
import { SiteFooter } from "@/app/components/site-footer";

export default function NotFound() {
  return (
    <>
      <SiteHeader />
      <main className="flex-1 mx-auto max-w-[1400px] px-6 py-32 text-center">
        <p className="eyebrow-signal mb-4">[404] · LOST IN THE PIT</p>
        <h1 className="display-xl">
          Wrong way<span className="text-signal">.</span>
        </h1>
        <p className="body mt-6 max-w-md mx-auto">
          The route doesn&apos;t exist or the part isn&apos;t indexed yet.
        </p>
        <div className="mt-10 flex items-center gap-4 justify-center">
          <Link href="/" className="btn-primary">
            RETURN TO PIT
          </Link>
          <Link href="/parts" className="arrow-link">
            Browse catalog
          </Link>
        </div>
      </main>
      <SiteFooter />
    </>
  );
}
