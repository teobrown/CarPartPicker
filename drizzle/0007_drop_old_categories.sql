-- Cleanup: every old category was renamed to slug-old by the
-- migrate-categories.ts script, parts were moved to new leaves by
-- the reclassify.py script. Now safe to drop.
--
-- Pre-condition: zero parts reference any '%-old' category. Enforced
-- by raising an error if that's not true.
DO $$
DECLARE
    n_stuck integer;
BEGIN
    SELECT COUNT(*) INTO n_stuck
    FROM parts p
    JOIN categories c ON c.id = p.category_id
    WHERE c.slug LIKE '%-old';
    IF n_stuck > 0 THEN
        RAISE EXCEPTION 'cannot drop old categories: % parts still reference them. Run scraper.reclassify first.', n_stuck;
    END IF;
END $$;
--> statement-breakpoint

DELETE FROM categories WHERE slug LIKE '%-old';
