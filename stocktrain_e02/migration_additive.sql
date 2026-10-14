-- Additive metadata only: DO NOT replace CoPhieu_KLCN.sql or alter E02 tables.
CREATE TABLE IF NOT EXISTS public.stocktrain_prediction_meta (
    ma_du_doan bigint PRIMARY KEY REFERENCES public.du_doan(ma_du_doan) ON DELETE CASCADE,
    source_sha256 char(64) NOT NULL,
    bundle_sha256 char(64) NOT NULL,
    experiment_id varchar(100) NOT NULL,
    model_name varchar(50) NOT NULL,
    trained_until date,
    warnings jsonb NOT NULL DEFAULT '[]'::jsonb,
    descriptive_risk jsonb NOT NULL DEFAULT '{}'::jsonb,
    target_date_estimated boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_stocktrain_meta_bundle ON public.stocktrain_prediction_meta(bundle_sha256);
