import {
  pgTable,
  serial,
  text,
  integer,
  varchar,
  boolean,
  timestamp,
  uniqueIndex,
  index,
  bigserial,
} from 'drizzle-orm/pg-core';

export const vehicles = pgTable(
  'vehicles',
  {
    id: serial('id').primaryKey(),
    make: varchar('make', { length: 64 }).notNull(),
    model: varchar('model', { length: 64 }).notNull(),
    year: integer('year').notNull(),
    trim: varchar('trim', { length: 64 }),
    subModel: varchar('sub_model', { length: 64 }),
    generation: varchar('generation', { length: 16 }).notNull(),
    bodyStyle: varchar('body_style', { length: 32 }),
    boltPattern: varchar('bolt_pattern', { length: 16 }),
    centerBoreMm: integer('center_bore_mm'),
    stockWheelWidthIn: integer('stock_wheel_width_in'),
    stockWheelOffsetMm: integer('stock_wheel_offset_mm'),
    stockTireSize: varchar('stock_tire_size', { length: 32 }),
    maxNoRubWidthIn: integer('max_no_rub_width_in'),
  },
  (t) => ({
    uq: uniqueIndex('vehicles_make_model_year_trim_uq').on(t.make, t.model, t.year, t.trim),
    genIdx: index('vehicles_generation_idx').on(t.generation),
  })
);

export const categories = pgTable('categories', {
  id: serial('id').primaryKey(),
  name: varchar('name', { length: 64 }).notNull(),
  slug: varchar('slug', { length: 64 }).notNull().unique(),
  parentId: integer('parent_id'),
  description: text('description'),
});

export const vendors = pgTable('vendors', {
  id: serial('id').primaryKey(),
  name: varchar('name', { length: 64 }).notNull(),
  slug: varchar('slug', { length: 64 }).notNull().unique(),
  affiliateProgram: varchar('affiliate_program', { length: 64 }),
  affiliateParam: varchar('affiliate_param', { length: 32 }),
  affiliateValue: varchar('affiliate_value', { length: 64 }),
  baseUrl: varchar('base_url', { length: 256 }).notNull(),
});

export const parts = pgTable(
  'parts',
  {
    id: serial('id').primaryKey(),
    categoryId: integer('category_id')
      .notNull()
      .references(() => categories.id),
    brand: varchar('brand', { length: 64 }).notNull(),
    model: varchar('model', { length: 128 }).notNull(),
    sku: varchar('sku', { length: 64 }),
    name: varchar('name', { length: 256 }).notNull(),
    description: text('description'),
    imageUrl: varchar('image_url', { length: 512 }),
    // wheel-only
    wheelDiameterIn: integer('wheel_diameter_in'),
    wheelWidthIn: integer('wheel_width_in'),
    wheelOffsetMm: integer('wheel_offset_mm'),
    wheelBoltPattern: varchar('wheel_bolt_pattern', { length: 16 }),
    wheelCenterBoreMm: integer('wheel_center_bore_mm'),
    // tire-only
    tireSectionWidth: integer('tire_section_width'),
    tireAspect: integer('tire_aspect'),
    tireDiameter: integer('tire_diameter'),
    // shared
    weightLbs: integer('weight_lbs'),
    msrpCents: integer('msrp_cents'),
  },
  (t) => ({
    brandModelIdx: index('parts_brand_model_idx').on(t.brand, t.model),
    categoryIdx: index('parts_category_idx').on(t.categoryId),
  })
);

export const vendorListings = pgTable(
  'vendor_listings',
  {
    id: serial('id').primaryKey(),
    partId: integer('part_id')
      .notNull()
      .references(() => parts.id),
    vendorId: integer('vendor_id')
      .notNull()
      .references(() => vendors.id),
    vendorSku: varchar('vendor_sku', { length: 64 }),
    vendorUrl: varchar('vendor_url', { length: 1024 }).notNull(),
    priceCents: integer('price_cents'),
    inStock: boolean('in_stock').default(true).notNull(),
    lastScrapedAt: timestamp('last_scraped_at', { withTimezone: true }).defaultNow().notNull(),
    missedRuns: integer('missed_runs').default(0).notNull(),
  },
  (t) => ({
    uq: uniqueIndex('vendor_listings_vendor_part_uq').on(t.vendorId, t.partId),
  })
);

export const fitmentRules = pgTable(
  'fitment_rules',
  {
    id: serial('id').primaryKey(),
    partId: integer('part_id')
      .notNull()
      .references(() => parts.id),
    make: varchar('make', { length: 64 }),
    model: varchar('model', { length: 64 }),
    generation: varchar('generation', { length: 16 }),
    yearStart: integer('year_start'),
    yearEnd: integer('year_end'),
    trimsIncluded: text('trims_included').array(),
    trimsExcluded: text('trims_excluded').array(),
    bodyStyle: varchar('body_style', { length: 32 }),
    status: varchar('status', { length: 32 }).notNull(),
    caveat: text('caveat'),
    requiresPartCategories: text('requires_part_categories').array(),
    conflictsWithPartIds: integer('conflicts_with_part_ids').array(),
    source: varchar('source', { length: 64 }).notNull(),
  },
  (t) => ({
    partIdx: index('fitment_rules_part_idx').on(t.partId),
    matchIdx: index('fitment_rules_match_idx').on(t.make, t.model, t.generation),
  })
);

export const builds = pgTable('builds', {
  id: serial('id').primaryKey(),
  slug: varchar('slug', { length: 16 }).notNull().unique(),
  vehicleId: integer('vehicle_id')
    .notNull()
    .references(() => vehicles.id),
  ownerUserId: integer('owner_user_id'),
  createdAt: timestamp('created_at', { withTimezone: true }).defaultNow().notNull(),
  updatedAt: timestamp('updated_at', { withTimezone: true }).defaultNow().notNull(),
});

export const buildItems = pgTable(
  'build_items',
  {
    buildId: integer('build_id')
      .notNull()
      .references(() => builds.id, { onDelete: 'cascade' }),
    partId: integer('part_id')
      .notNull()
      .references(() => parts.id),
    position: integer('position').notNull(),
    userNote: text('user_note'),
  },
  (t) => ({
    pk: uniqueIndex('build_items_pk').on(t.buildId, t.partId, t.position),
  })
);

export const affiliateClicks = pgTable(
  'affiliate_clicks',
  {
    id: bigserial('id', { mode: 'number' }).primaryKey(),
    buildId: integer('build_id'),
    listingId: integer('listing_id')
      .notNull()
      .references(() => vendorListings.id),
    partId: integer('part_id')
      .notNull()
      .references(() => parts.id),
    vendorId: integer('vendor_id')
      .notNull()
      .references(() => vendors.id),
    clickedAt: timestamp('clicked_at', { withTimezone: true }).defaultNow().notNull(),
    ipHash: varchar('ip_hash', { length: 64 }),
    userAgent: varchar('user_agent', { length: 512 }),
  },
  (t) => ({
    vendorIdx: index('affiliate_clicks_vendor_idx').on(t.vendorId, t.clickedAt),
  })
);
