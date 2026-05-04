import { cookies } from 'next/headers';
import { db } from '@/lib/db/client';
import { vehicles } from '@/lib/db/schema';
import { eq } from 'drizzle-orm';

export type SelectedVehicle = {
  id: number;
  make: string;
  model: string;
  year: number;
  trim: string | null;
  subModel: string | null;
  generation: string;
};

/** Server helper: returns the currently-selected vehicle from cookie, if any. */
export async function getSelectedVehicle(): Promise<SelectedVehicle | null> {
  const c = await cookies();
  const id = Number(c.get('cpp_vehicle_id')?.value);
  if (!id || Number.isNaN(id)) return null;
  const [v] = await db.select().from(vehicles).where(eq(vehicles.id, id)).limit(1);
  if (!v) return null;
  return {
    id: v.id,
    make: v.make,
    model: v.model,
    year: v.year,
    trim: v.trim,
    subModel: v.subModel,
    generation: v.generation,
  };
}

export function vehicleLabel(v: SelectedVehicle): string {
  return `${v.year} ${v.make} ${v.model}${v.subModel ? ' ' + v.subModel : ''}${v.trim ? ' · ' + v.trim : ''}`;
}
