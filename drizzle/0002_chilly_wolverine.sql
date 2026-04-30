ALTER TABLE "parts" ALTER COLUMN "wheel_width_in" SET DATA TYPE real;--> statement-breakpoint
ALTER TABLE "parts" ALTER COLUMN "wheel_center_bore_mm" SET DATA TYPE real;--> statement-breakpoint
ALTER TABLE "vehicles" ALTER COLUMN "center_bore_mm" SET DATA TYPE real;--> statement-breakpoint
ALTER TABLE "vehicles" ALTER COLUMN "stock_wheel_width_in" SET DATA TYPE real;--> statement-breakpoint
ALTER TABLE "vehicles" ALTER COLUMN "max_no_rub_width_in" SET DATA TYPE real;