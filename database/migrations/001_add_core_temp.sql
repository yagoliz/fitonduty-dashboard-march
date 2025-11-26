-- Migration: Add core body temperature support
-- Date: 2025-11-26
-- Description: Add core_temp to timeseries data and avg_core_temp to health metrics

BEGIN;

-- Add core_temp column to march_timeseries_data
ALTER TABLE march_timeseries_data
ADD COLUMN IF NOT EXISTS core_temp NUMERIC(4,2);

-- Add avg_core_temp column to march_health_metrics
ALTER TABLE march_health_metrics
ADD COLUMN IF NOT EXISTS avg_core_temp NUMERIC(4,2);

-- Add documentation comments
COMMENT ON COLUMN march_timeseries_data.core_temp
IS 'Core body temperature in Celsius from Empatica E4 sensor (30-45°C range)';

COMMENT ON COLUMN march_health_metrics.avg_core_temp
IS 'Average core body temperature during march in Celsius';

COMMIT;