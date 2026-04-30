import { db } from '@/lib/db/client';
import { vehicles } from '@/lib/db/schema';

type V = typeof vehicles.$inferInsert;

function years(start: number, end: number): number[] {
  return Array.from({ length: end - start + 1 }, (_, i) => start + i);
}
function trims<T extends string>(t: T[]): T[] {
  return t;
}

const data: V[] = [
  // Subaru WRX (VA: 2015-2021), Premium / Limited / Base
  ...years(2015, 2021).flatMap((year) =>
    trims(['Base', 'Premium', 'Limited']).map<V>((trim) => ({
      make: 'Subaru',
      model: 'WRX',
      year,
      trim,
      generation: 'VA',
      bodyStyle: 'sedan',
      boltPattern: '5x114.3',
      centerBoreMm: 56.1,
      stockWheelWidthIn: 8,
      stockWheelOffsetMm: 55,
      stockTireSize: '235/45R17',
      maxNoRubWidthIn: 9,
    }))
  ),
  // Subaru WRX (VB: 2022-2024)
  ...years(2022, 2024).flatMap((year) =>
    trims(['Base', 'Premium', 'Limited', 'GT']).map<V>((trim) => ({
      make: 'Subaru',
      model: 'WRX',
      year,
      trim,
      generation: 'VB',
      bodyStyle: 'sedan',
      boltPattern: '5x114.3',
      centerBoreMm: 56.1,
      stockWheelWidthIn: 8,
      stockWheelOffsetMm: 55,
      stockTireSize: '245/40R18',
      maxNoRubWidthIn: 9,
    }))
  ),
  // Subaru STI (VA: 2015-2021)
  ...years(2015, 2021).flatMap((year) =>
    trims(['Base', 'Limited']).map<V>((trim) => ({
      make: 'Subaru',
      model: 'WRX STI',
      year,
      trim,
      generation: 'VA',
      bodyStyle: 'sedan',
      boltPattern: '5x114.3',
      centerBoreMm: 56.1,
      stockWheelWidthIn: 9,
      stockWheelOffsetMm: 53,
      stockTireSize: '245/40R18',
      maxNoRubWidthIn: 10,
    }))
  ),
  // Toyota GR Corolla (2023-2024)
  ...years(2023, 2024).flatMap((year) =>
    trims(['Core', 'Circuit', 'Premium']).map<V>((trim) => ({
      make: 'Toyota',
      model: 'GR Corolla',
      year,
      trim,
      generation: 'GR',
      bodyStyle: 'hatch',
      boltPattern: '5x114.3',
      centerBoreMm: 60.1,
      stockWheelWidthIn: 8,
      stockWheelOffsetMm: 45,
      stockTireSize: '235/40R18',
      maxNoRubWidthIn: 9.5,
    }))
  ),
  // Toyota GR86 (2022-2024)
  ...years(2022, 2024).flatMap((year) =>
    trims(['Base', 'Premium']).map<V>((trim) => ({
      make: 'Toyota',
      model: 'GR86',
      year,
      trim,
      generation: 'ZN8',
      bodyStyle: 'coupe',
      boltPattern: '5x100',
      centerBoreMm: 56.1,
      stockWheelWidthIn: 7.5,
      stockWheelOffsetMm: 48,
      stockTireSize: '215/40R18',
      maxNoRubWidthIn: 9,
    }))
  ),
  // Subaru BRZ (2022-2024)
  ...years(2022, 2024).flatMap((year) =>
    trims(['Premium', 'Limited']).map<V>((trim) => ({
      make: 'Subaru',
      model: 'BRZ',
      year,
      trim,
      generation: 'ZD8',
      bodyStyle: 'coupe',
      boltPattern: '5x100',
      centerBoreMm: 56.1,
      stockWheelWidthIn: 7.5,
      stockWheelOffsetMm: 48,
      stockTireSize: '215/40R18',
      maxNoRubWidthIn: 9,
    }))
  ),
  // Honda Civic Si (FE: 2022-2024)
  ...years(2022, 2024).flatMap((year) =>
    trims(['Base']).map<V>((trim) => ({
      make: 'Honda',
      model: 'Civic Si',
      year,
      trim,
      generation: 'FE',
      bodyStyle: 'sedan',
      boltPattern: '5x114.3',
      centerBoreMm: 64.1,
      stockWheelWidthIn: 8,
      stockWheelOffsetMm: 50,
      stockTireSize: '235/40R18',
      maxNoRubWidthIn: 9,
    }))
  ),
  // Honda Civic Type R (FK8: 2017-2021)
  ...years(2017, 2021).flatMap((year) =>
    trims(['Base', 'Touring']).map<V>((trim) => ({
      make: 'Honda',
      model: 'Civic Type R',
      year,
      trim,
      generation: 'FK8',
      bodyStyle: 'hatch',
      boltPattern: '5x120',
      centerBoreMm: 64.1,
      stockWheelWidthIn: 8.5,
      stockWheelOffsetMm: 60,
      stockTireSize: '245/30R20',
      maxNoRubWidthIn: 10,
    }))
  ),
  // Honda Civic Type R (FL5: 2023-2024)
  ...years(2023, 2024).flatMap((year) =>
    trims(['Base']).map<V>((trim) => ({
      make: 'Honda',
      model: 'Civic Type R',
      year,
      trim,
      generation: 'FL5',
      bodyStyle: 'hatch',
      boltPattern: '5x120',
      centerBoreMm: 64.1,
      stockWheelWidthIn: 9.5,
      stockWheelOffsetMm: 60,
      stockTireSize: '265/30R19',
      maxNoRubWidthIn: 10.5,
    }))
  ),
  // Ford Mustang GT (S550: 2015-2023)
  ...years(2015, 2023).flatMap((year) =>
    trims(['Base', 'Premium']).map<V>((trim) => ({
      make: 'Ford',
      model: 'Mustang',
      year,
      trim,
      subModel: 'GT',
      generation: 'S550',
      bodyStyle: 'coupe',
      boltPattern: '5x114.3',
      centerBoreMm: 70.5,
      stockWheelWidthIn: 9,
      stockWheelOffsetMm: 38,
      stockTireSize: '255/40R19',
      maxNoRubWidthIn: 10,
    }))
  ),
  // Ford Mustang Ecoboost (S550)
  ...years(2015, 2023).flatMap((year) =>
    trims(['Base', 'Premium', 'High Performance']).map<V>((trim) => ({
      make: 'Ford',
      model: 'Mustang',
      year,
      trim,
      subModel: 'Ecoboost',
      generation: 'S550',
      bodyStyle: 'coupe',
      boltPattern: '5x114.3',
      centerBoreMm: 70.5,
      stockWheelWidthIn: 8,
      stockWheelOffsetMm: 38,
      stockTireSize: '235/55R17',
      maxNoRubWidthIn: 10,
    }))
  ),
  // Mazda MX-5 Miata (ND: 2016-2024)
  ...years(2016, 2024).flatMap((year) =>
    trims(['Sport', 'Club', 'Grand Touring']).map<V>((trim) => ({
      make: 'Mazda',
      model: 'MX-5 Miata',
      year,
      trim,
      generation: 'ND',
      bodyStyle: 'roadster',
      boltPattern: '4x100',
      centerBoreMm: 54.1,
      stockWheelWidthIn: 7,
      stockWheelOffsetMm: 45,
      stockTireSize: '205/45R17',
      maxNoRubWidthIn: 8,
    }))
  ),
  // VW Golf R (Mk7: 2015-2019)
  ...years(2015, 2019).flatMap((year) =>
    trims(['Base', 'DCC']).map<V>((trim) => ({
      make: 'Volkswagen',
      model: 'Golf R',
      year,
      trim,
      generation: 'Mk7',
      bodyStyle: 'hatch',
      boltPattern: '5x112',
      centerBoreMm: 57.1,
      stockWheelWidthIn: 7.5,
      stockWheelOffsetMm: 51,
      stockTireSize: '235/35R19',
      maxNoRubWidthIn: 9,
    }))
  ),
  // VW Golf R (Mk8: 2022-2024)
  ...years(2022, 2024).flatMap((year) =>
    trims(['Base']).map<V>((trim) => ({
      make: 'Volkswagen',
      model: 'Golf R',
      year,
      trim,
      generation: 'Mk8',
      bodyStyle: 'hatch',
      boltPattern: '5x112',
      centerBoreMm: 57.1,
      stockWheelWidthIn: 8,
      stockWheelOffsetMm: 50,
      stockTireSize: '235/35R19',
      maxNoRubWidthIn: 9.5,
    }))
  ),
  // VW GTI (Mk7: 2015-2021)
  ...years(2015, 2021).flatMap((year) =>
    trims(['S', 'SE', 'Autobahn']).map<V>((trim) => ({
      make: 'Volkswagen',
      model: 'GTI',
      year,
      trim,
      generation: 'Mk7',
      bodyStyle: 'hatch',
      boltPattern: '5x112',
      centerBoreMm: 57.1,
      stockWheelWidthIn: 7.5,
      stockWheelOffsetMm: 51,
      stockTireSize: '225/40R18',
      maxNoRubWidthIn: 9,
    }))
  ),
  // VW GTI (Mk8: 2022-2024)
  ...years(2022, 2024).flatMap((year) =>
    trims(['S', 'SE', 'Autobahn']).map<V>((trim) => ({
      make: 'Volkswagen',
      model: 'GTI',
      year,
      trim,
      generation: 'Mk8',
      bodyStyle: 'hatch',
      boltPattern: '5x112',
      centerBoreMm: 57.1,
      stockWheelWidthIn: 7.5,
      stockWheelOffsetMm: 50,
      stockTireSize: '225/40R18',
      maxNoRubWidthIn: 9,
    }))
  ),
];

export async function runVehicleSeed() {
  await db.insert(vehicles).values(data).onConflictDoNothing();
  return data.length;
}
