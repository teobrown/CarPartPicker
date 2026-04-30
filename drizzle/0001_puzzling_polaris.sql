DROP INDEX "build_items_pk";--> statement-breakpoint
ALTER TABLE "parts" ALTER COLUMN "msrp_cents" SET DATA TYPE bigint;--> statement-breakpoint
ALTER TABLE "vendor_listings" ALTER COLUMN "price_cents" SET DATA TYPE bigint;--> statement-breakpoint
ALTER TABLE "build_items" ADD CONSTRAINT "build_items_build_id_part_id_position_pk" PRIMARY KEY("build_id","part_id","position");--> statement-breakpoint
ALTER TABLE "affiliate_clicks" ADD CONSTRAINT "affiliate_clicks_build_id_builds_id_fk" FOREIGN KEY ("build_id") REFERENCES "public"."builds"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "categories" ADD CONSTRAINT "categories_parent_id_categories_id_fk" FOREIGN KEY ("parent_id") REFERENCES "public"."categories"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
CREATE INDEX "vendor_listings_part_idx" ON "vendor_listings" USING btree ("part_id");