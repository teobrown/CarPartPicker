CREATE TABLE "affiliate_clicks" (
	"id" bigserial PRIMARY KEY NOT NULL,
	"build_id" integer,
	"listing_id" integer NOT NULL,
	"part_id" integer NOT NULL,
	"vendor_id" integer NOT NULL,
	"clicked_at" timestamp with time zone DEFAULT now() NOT NULL,
	"ip_hash" varchar(64),
	"user_agent" varchar(512)
);
--> statement-breakpoint
CREATE TABLE "build_items" (
	"build_id" integer NOT NULL,
	"part_id" integer NOT NULL,
	"position" integer NOT NULL,
	"user_note" text
);
--> statement-breakpoint
CREATE TABLE "builds" (
	"id" serial PRIMARY KEY NOT NULL,
	"slug" varchar(16) NOT NULL,
	"vehicle_id" integer NOT NULL,
	"owner_user_id" integer,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "builds_slug_unique" UNIQUE("slug")
);
--> statement-breakpoint
CREATE TABLE "categories" (
	"id" serial PRIMARY KEY NOT NULL,
	"name" varchar(64) NOT NULL,
	"slug" varchar(64) NOT NULL,
	"parent_id" integer,
	"description" text,
	CONSTRAINT "categories_slug_unique" UNIQUE("slug")
);
--> statement-breakpoint
CREATE TABLE "fitment_rules" (
	"id" serial PRIMARY KEY NOT NULL,
	"part_id" integer NOT NULL,
	"make" varchar(64),
	"model" varchar(64),
	"generation" varchar(16),
	"year_start" integer,
	"year_end" integer,
	"trims_included" text[],
	"trims_excluded" text[],
	"body_style" varchar(32),
	"status" varchar(32) NOT NULL,
	"caveat" text,
	"requires_part_categories" text[],
	"conflicts_with_part_ids" integer[],
	"source" varchar(64) NOT NULL
);
--> statement-breakpoint
CREATE TABLE "parts" (
	"id" serial PRIMARY KEY NOT NULL,
	"category_id" integer NOT NULL,
	"brand" varchar(64) NOT NULL,
	"model" varchar(128) NOT NULL,
	"sku" varchar(64),
	"name" varchar(256) NOT NULL,
	"description" text,
	"image_url" varchar(512),
	"wheel_diameter_in" integer,
	"wheel_width_in" integer,
	"wheel_offset_mm" integer,
	"wheel_bolt_pattern" varchar(16),
	"wheel_center_bore_mm" integer,
	"tire_section_width" integer,
	"tire_aspect" integer,
	"tire_diameter" integer,
	"weight_lbs" integer,
	"msrp_cents" integer
);
--> statement-breakpoint
CREATE TABLE "vehicles" (
	"id" serial PRIMARY KEY NOT NULL,
	"make" varchar(64) NOT NULL,
	"model" varchar(64) NOT NULL,
	"year" integer NOT NULL,
	"trim" varchar(64),
	"sub_model" varchar(64),
	"generation" varchar(16) NOT NULL,
	"body_style" varchar(32),
	"bolt_pattern" varchar(16),
	"center_bore_mm" integer,
	"stock_wheel_width_in" integer,
	"stock_wheel_offset_mm" integer,
	"stock_tire_size" varchar(32),
	"max_no_rub_width_in" integer
);
--> statement-breakpoint
CREATE TABLE "vendor_listings" (
	"id" serial PRIMARY KEY NOT NULL,
	"part_id" integer NOT NULL,
	"vendor_id" integer NOT NULL,
	"vendor_sku" varchar(64),
	"vendor_url" varchar(1024) NOT NULL,
	"price_cents" integer,
	"in_stock" boolean DEFAULT true NOT NULL,
	"last_scraped_at" timestamp with time zone DEFAULT now() NOT NULL,
	"missed_runs" integer DEFAULT 0 NOT NULL
);
--> statement-breakpoint
CREATE TABLE "vendors" (
	"id" serial PRIMARY KEY NOT NULL,
	"name" varchar(64) NOT NULL,
	"slug" varchar(64) NOT NULL,
	"affiliate_program" varchar(64),
	"affiliate_param" varchar(32),
	"affiliate_value" varchar(64),
	"base_url" varchar(256) NOT NULL,
	CONSTRAINT "vendors_slug_unique" UNIQUE("slug")
);
--> statement-breakpoint
ALTER TABLE "affiliate_clicks" ADD CONSTRAINT "affiliate_clicks_listing_id_vendor_listings_id_fk" FOREIGN KEY ("listing_id") REFERENCES "public"."vendor_listings"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "affiliate_clicks" ADD CONSTRAINT "affiliate_clicks_part_id_parts_id_fk" FOREIGN KEY ("part_id") REFERENCES "public"."parts"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "affiliate_clicks" ADD CONSTRAINT "affiliate_clicks_vendor_id_vendors_id_fk" FOREIGN KEY ("vendor_id") REFERENCES "public"."vendors"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "build_items" ADD CONSTRAINT "build_items_build_id_builds_id_fk" FOREIGN KEY ("build_id") REFERENCES "public"."builds"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "build_items" ADD CONSTRAINT "build_items_part_id_parts_id_fk" FOREIGN KEY ("part_id") REFERENCES "public"."parts"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "builds" ADD CONSTRAINT "builds_vehicle_id_vehicles_id_fk" FOREIGN KEY ("vehicle_id") REFERENCES "public"."vehicles"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "fitment_rules" ADD CONSTRAINT "fitment_rules_part_id_parts_id_fk" FOREIGN KEY ("part_id") REFERENCES "public"."parts"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "parts" ADD CONSTRAINT "parts_category_id_categories_id_fk" FOREIGN KEY ("category_id") REFERENCES "public"."categories"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vendor_listings" ADD CONSTRAINT "vendor_listings_part_id_parts_id_fk" FOREIGN KEY ("part_id") REFERENCES "public"."parts"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "vendor_listings" ADD CONSTRAINT "vendor_listings_vendor_id_vendors_id_fk" FOREIGN KEY ("vendor_id") REFERENCES "public"."vendors"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
CREATE INDEX "affiliate_clicks_vendor_idx" ON "affiliate_clicks" USING btree ("vendor_id","clicked_at");--> statement-breakpoint
CREATE UNIQUE INDEX "build_items_pk" ON "build_items" USING btree ("build_id","part_id","position");--> statement-breakpoint
CREATE INDEX "fitment_rules_part_idx" ON "fitment_rules" USING btree ("part_id");--> statement-breakpoint
CREATE INDEX "fitment_rules_match_idx" ON "fitment_rules" USING btree ("make","model","generation");--> statement-breakpoint
CREATE INDEX "parts_brand_model_idx" ON "parts" USING btree ("brand","model");--> statement-breakpoint
CREATE INDEX "parts_category_idx" ON "parts" USING btree ("category_id");--> statement-breakpoint
CREATE UNIQUE INDEX "vehicles_make_model_year_trim_uq" ON "vehicles" USING btree ("make","model","year","trim");--> statement-breakpoint
CREATE INDEX "vehicles_generation_idx" ON "vehicles" USING btree ("generation");--> statement-breakpoint
CREATE UNIQUE INDEX "vendor_listings_vendor_part_uq" ON "vendor_listings" USING btree ("vendor_id","part_id");