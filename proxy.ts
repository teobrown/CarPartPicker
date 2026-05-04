import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";

// Routes that REQUIRE auth. Everything else is public — the catalog,
// part detail, vehicle picker, and (importantly) the build editor are
// all anonymous-friendly. The auth gate only fires when a user clicks
// Save Build / Share Build (those actions hit /api/builds/claim and
// /dashboard, which must reject unauthenticated requests).
const isProtectedRoute = createRouteMatcher([
  "/dashboard(.*)",
  "/api/builds/claim",
]);

export default clerkMiddleware(async (auth, req) => {
  if (isProtectedRoute(req)) {
    await auth.protect();
  }
});

export const config = {
  matcher: [
    // Skip Next.js internals and all static files unless found in search params
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    // Always run for API routes
    "/(api|trpc)(.*)",
  ],
};
