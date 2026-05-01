import { NextRequest } from 'next/server';
import { db } from '@/lib/db/client';
import { vehicles } from '@/lib/db/schema';
import { sql, eq, and } from 'drizzle-orm';

// returns the next-level options for cascading make → model → year → trim
export async function GET(req: NextRequest) {
  const make = req.nextUrl.searchParams.get('make');
  const model = req.nextUrl.searchParams.get('model');
  const year = req.nextUrl.searchParams.get('year');

  if (!make) {
    const rows = await db.select({ make: vehicles.make }).from(vehicles).groupBy(vehicles.make).orderBy(vehicles.make);
    return Response.json({ level: 'make', options: rows.map((r) => r.make) });
  }
  if (!model) {
    const rows = await db
      .select({ model: vehicles.model })
      .from(vehicles)
      .where(eq(vehicles.make, make))
      .groupBy(vehicles.model)
      .orderBy(vehicles.model);
    return Response.json({ level: 'model', options: rows.map((r) => r.model) });
  }
  if (!year) {
    const rows = await db
      .select({ year: vehicles.year })
      .from(vehicles)
      .where(and(eq(vehicles.make, make), eq(vehicles.model, model)))
      .groupBy(vehicles.year)
      .orderBy(sql`${vehicles.year} DESC`);
    return Response.json({ level: 'year', options: rows.map((r) => r.year) });
  }
  // trim list (with vehicle ID for each)
  const rows = await db
    .select({
      id: vehicles.id,
      trim: vehicles.trim,
      subModel: vehicles.subModel,
      generation: vehicles.generation,
    })
    .from(vehicles)
    .where(and(eq(vehicles.make, make), eq(vehicles.model, model), eq(vehicles.year, Number(year))))
    .orderBy(vehicles.subModel, vehicles.trim);
  return Response.json({ level: 'trim', options: rows });
}
