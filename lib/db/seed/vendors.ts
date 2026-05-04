import { db } from '@/lib/db/client';
import { vendors } from '@/lib/db/schema';

type V = typeof vendors.$inferInsert;

// affiliateValue is intentionally null until each program is approved and a
// real publisher code lands. The /go/[listingId] redirector gates on
// `affiliateParam && affiliateValue`, so a null value cleanly skips the
// param append — no fake "carbuildr" token gets shipped to vendors who
// haven't onboarded us. To enable a vendor: set affiliateValue to the
// real code from their dashboard and re-seed (or UPDATE in place).
const data: V[] = [
  {
    name: 'Summit Racing', slug: 'summit-racing',
    affiliateProgram: 'Impact Radius', affiliateParam: 'utm_source',
    affiliateValue: null, baseUrl: 'https://www.summitracing.com',
  },
  {
    name: 'FCP Euro', slug: 'fcp-euro',
    affiliateProgram: 'AvantLink', affiliateParam: 'avad',
    affiliateValue: null, baseUrl: 'https://www.fcpeuro.com',
  },
  {
    name: 'ECS Tuning', slug: 'ecs-tuning',
    affiliateProgram: 'AvantLink', affiliateParam: 'avad',
    affiliateValue: null, baseUrl: 'https://www.ecstuning.com',
  },
  {
    name: 'AmericanMuscle', slug: 'americanmuscle',
    affiliateProgram: 'AmericanMuscle Affiliate', affiliateParam: 'aff',
    affiliateValue: null, baseUrl: 'https://www.americanmuscle.com',
  },
  {
    name: 'RallySport Direct', slug: 'rallysport-direct',
    affiliateProgram: 'ShareASale', affiliateParam: 'sscid',
    affiliateValue: null, baseUrl: 'https://www.rallysportdirect.com',
  },
  {
    name: 'PRL Motorsports', slug: 'prl-motorsports',
    affiliateProgram: 'AvantLink', affiliateParam: 'avad',
    affiliateValue: null, baseUrl: 'https://www.prlmotorsports.com',
  },
  {
    name: '27WON Performance', slug: '27won',
    affiliateProgram: 'AvantLink', affiliateParam: 'avad',
    affiliateValue: null, baseUrl: 'https://store.27won.com',
  },
  {
    name: 'Flyin Miata', slug: 'flyin-miata',
    affiliateProgram: 'AvantLink', affiliateParam: 'avad',
    affiliateValue: null, baseUrl: 'https://flyinmiata.com',
  },
  {
    name: 'MAPerformance', slug: 'maperformance',
    affiliateProgram: 'AvantLink', affiliateParam: 'avad',
    affiliateValue: null, baseUrl: 'https://www.maperformance.com',
  },
  {
    name: 'IAG Performance', slug: 'iag-performance',
    affiliateProgram: 'AvantLink', affiliateParam: 'avad',
    affiliateValue: null, baseUrl: 'https://www.iagperformance.com',
  },
  {
    name: 'Steeda Autosports', slug: 'steeda',
    affiliateProgram: 'AvantLink', affiliateParam: 'avad',
    affiliateValue: null, baseUrl: 'https://www.steeda.com',
  },
  {
    name: '034Motorsport', slug: '034motorsport',
    affiliateProgram: 'AvantLink', affiliateParam: 'avad',
    affiliateValue: null, baseUrl: 'https://www.034motorsport.com',
  },
  {
    name: 'K-Tuned', slug: 'k-tuned',
    affiliateProgram: 'AvantLink', affiliateParam: 'avad',
    affiliateValue: null, baseUrl: 'https://www.k-tuned.com',
  },
  {
    name: 'Skunk2 Racing', slug: 'skunk2',
    affiliateProgram: 'Direct', affiliateParam: 'aff',
    affiliateValue: null, baseUrl: 'https://www.skunk2.com',
  },
  {
    name: 'eBay Motors', slug: 'ebay-motors',
    affiliateProgram: 'eBay Partner Network', affiliateParam: 'campid',
    affiliateValue: null, baseUrl: 'https://www.ebay.com',
  },
];

export async function runVendorSeed() {
  await db.insert(vendors).values(data).onConflictDoNothing();
  return data.length;
}
