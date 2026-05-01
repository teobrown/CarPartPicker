import { NextRequest } from 'next/server';
import { cookies } from 'next/headers';
import { createBuild } from '@/lib/queries/builds';
import { db } from '@/lib/db/client';
import { vehicles } from '@/lib/db/schema';
import { eq } from 'drizzle-orm';

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));
  const vehicleId = Number(body?.vehicleId);
  if (!vehicleId || Number.isNaN(vehicleId)) {
    return Response.json({ error: 'vehicleId required' }, { status: 400 });
  }
  const [v] = await db.select().from(vehicles).where(eq(vehicles.id, vehicleId)).limit(1);
  if (!v) return Response.json({ error: 'vehicle not found' }, { status: 404 });
  const b = await createBuild({ vehicleId });
  // remember the vehicle for future page loads
  const c = await cookies();
  c.set('cpp_vehicle_id', String(vehicleId), { path: '/', maxAge: 60 * 60 * 24 * 90 });
  return Response.json({ slug: b.slug });
}
