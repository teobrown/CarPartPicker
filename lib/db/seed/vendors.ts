import { db } from '@/lib/db/client';
import { vendors } from '@/lib/db/schema';

type V = typeof vendors.$inferInsert;

// affiliateValue is a placeholder; replace with the real ID once the program
// signup is approved (see spec §11 open question 2).
const data: V[] = [
  {
    name: 'Summit Racing', slug: 'summit-racing',
    affiliateProgram: 'Impact Radius', affiliateParam: 'utm_source',
    affiliateValue: 'carpartpicker', baseUrl: 'https://www.summitracing.com',
  },
  {
    name: 'FCP Euro', slug: 'fcp-euro',
    affiliateProgram: 'AvantLink', affiliateParam: 'avad',
    affiliateValue: 'carpartpicker', baseUrl: 'https://www.fcpeuro.com',
  },
  {
    name: 'ECS Tuning', slug: 'ecs-tuning',
    affiliateProgram: 'AvantLink', affiliateParam: 'avad',
    affiliateValue: 'carpartpicker', baseUrl: 'https://www.ecstuning.com',
  },
  {
    name: 'AmericanMuscle', slug: 'americanmuscle',
    affiliateProgram: 'AmericanMuscle Affiliate', affiliateParam: 'aff',
    affiliateValue: 'carpartpicker', baseUrl: 'https://www.americanmuscle.com',
  },
  {
    name: 'RallySport Direct', slug: 'rallysport-direct',
    affiliateProgram: 'ShareASale', affiliateParam: 'sscid',
    affiliateValue: 'carpartpicker', baseUrl: 'https://www.rallysportdirect.com',
  },
  {
    name: 'PRL Motorsports', slug: 'prl-motorsports',
    affiliateProgram: 'AvantLink', affiliateParam: 'avad',
    affiliateValue: 'carpartpicker', baseUrl: 'https://www.prlmotorsports.com',
  },
  {
    name: '27WON Performance', slug: '27won',
    affiliateProgram: 'AvantLink', affiliateParam: 'avad',
    affiliateValue: 'carpartpicker', baseUrl: 'https://store.27won.com',
  },
  {
    name: 'Flyin Miata', slug: 'flyin-miata',
    affiliateProgram: 'AvantLink', affiliateParam: 'avad',
    affiliateValue: 'carpartpicker', baseUrl: 'https://flyinmiata.com',
  },
  {
    name: 'MAPerformance', slug: 'maperformance',
    affiliateProgram: 'AvantLink', affiliateParam: 'avad',
    affiliateValue: 'carpartpicker', baseUrl: 'https://www.maperformance.com',
  },
  {
    name: 'IAG Performance', slug: 'iag-performance',
    affiliateProgram: 'AvantLink', affiliateParam: 'avad',
    affiliateValue: 'carpartpicker', baseUrl: 'https://www.iagperformance.com',
  },
  {
    name: 'Steeda Autosports', slug: 'steeda',
    affiliateProgram: 'AvantLink', affiliateParam: 'avad',
    affiliateValue: 'carpartpicker', baseUrl: 'https://www.steeda.com',
  },
  {
    name: 'eBay Motors', slug: 'ebay-motors',
    affiliateProgram: 'eBay Partner Network', affiliateParam: 'campid',
    affiliateValue: 'carpartpicker', baseUrl: 'https://www.ebay.com',
  },
];

export async function runVendorSeed() {
  await db.insert(vendors).values(data).onConflictDoNothing();
  return data.length;
}
