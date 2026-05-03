-- Pre-cleanup: re-seeds inserted duplicate vehicle rows because Postgres'
-- default UNIQUE semantics treat NULL sub_model as distinct from another
-- NULL sub_model. Up to 6x dupes per (make, model, year, trim) for rows
-- where sub_model is null (e.g. Civic Si, Type R, Golf R, MX-5, BRZ, GR86).
-- Steps:
--   1. Re-point any builds.vehicle_id that lands on a non-canonical (non-min)
--      duplicate to the lowest id for the same (make, model, year, trim,
--      sub_model). With FK validation, the non-canonical id can then be
--      safely deleted.
--   2. Delete every duplicate row except the lowest id per group.
--   3. Drop the old unique index.
--   4. Recreate it as a constraint with NULLS NOT DISTINCT, so re-seeds will
--      conflict on the existing row instead of inserting new copies.

WITH canonical AS (
  SELECT
    MIN(id) AS canonical_id,
    make, model, year, trim, sub_model
  FROM vehicles
  GROUP BY make, model, year, trim, sub_model
)
UPDATE builds b
SET vehicle_id = c.canonical_id
FROM vehicles v, canonical c
WHERE b.vehicle_id = v.id
  AND v.make = c.make
  AND v.model = c.model
  AND v.year = c.year
  AND v.trim IS NOT DISTINCT FROM c.trim
  AND v.sub_model IS NOT DISTINCT FROM c.sub_model
  AND b.vehicle_id <> c.canonical_id;
--> statement-breakpoint

DELETE FROM vehicles v
USING (
  SELECT MIN(id) AS keep_id, make, model, year, trim, sub_model
  FROM vehicles
  GROUP BY make, model, year, trim, sub_model
) k
WHERE v.make = k.make
  AND v.model = k.model
  AND v.year = k.year
  AND v.trim IS NOT DISTINCT FROM k.trim
  AND v.sub_model IS NOT DISTINCT FROM k.sub_model
  AND v.id <> k.keep_id;
--> statement-breakpoint

DROP INDEX "vehicles_make_model_year_trim_sub_model_uq";--> statement-breakpoint
ALTER TABLE "vehicles" ADD CONSTRAINT "vehicles_make_model_year_trim_sub_model_uq" UNIQUE NULLS NOT DISTINCT("make","model","year","trim","sub_model");
