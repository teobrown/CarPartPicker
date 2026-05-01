import { NextRequest } from 'next/server';
import { listCategoryPartsRankedForVehicle } from '@/lib/queries/compat';

export async function GET(req: NextRequest) {
  const sp = req.nextUrl.searchParams;
  const category = sp.get('category');
  if (!category) return Response.json({ error: 'category required' }, { status: 400 });
  const vehicleIdRaw = sp.get('vehicleId');
  const vehicleId = vehicleIdRaw ? Number(vehicleIdRaw) : null;
  if (vehicleId !== null && Number.isNaN(vehicleId)) {
    return Response.json({ error: 'vehicleId must be numeric' }, { status: 400 });
  }
  const search = sp.get('q') ?? undefined;
  const parts = await listCategoryPartsRankedForVehicle({
    categorySlug: category,
    vehicleId,
    search,
  });
  return Response.json({ parts });
}
