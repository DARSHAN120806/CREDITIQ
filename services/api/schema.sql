BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 20261003_0001

CREATE TABLE model_versions (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    release_name TEXT NOT NULL, 
    variant TEXT NOT NULL, 
    feature_schema_version TEXT NOT NULL, 
    target_definition_version TEXT NOT NULL, 
    training_manifest_key TEXT NOT NULL, 
    artifact_key TEXT NOT NULL, 
    sha256 VARCHAR(64) NOT NULL, 
    calibration_version TEXT NOT NULL, 
    runtime_lock_hash VARCHAR(64) NOT NULL, 
    metrics_json JSONB DEFAULT '{}'::jsonb NOT NULL, 
    lifecycle_status TEXT DEFAULT 'REGISTERED' NOT NULL, 
    mode TEXT DEFAULT 'RESEARCH_ONLY' NOT NULL, 
    release_ready BOOLEAN DEFAULT false NOT NULL, 
    CONSTRAINT pk_model_versions PRIMARY KEY (id), 
    CONSTRAINT ck_model_versions_metrics_json_shape CHECK (jsonb_typeof(metrics_json) = 'object'), 
    CONSTRAINT ck_model_versions_lifecycle_status_values CHECK (lifecycle_status IN ('REGISTERED', 'VALIDATED', 'RETIRED')), 
    CONSTRAINT ck_model_versions_mode_values CHECK (mode IN ('RESEARCH_ONLY')), 
    CONSTRAINT ck_model_versions_runtime_lock_hash_sha256 CHECK (runtime_lock_hash ~ '^[0-9a-f]{64}$'), 
    CONSTRAINT ck_model_versions_sha256_sha256 CHECK (sha256 ~ '^[0-9a-f]{64}$'), 
    CONSTRAINT ck_model_versions_variant_values CHECK (variant IN ('LITE', 'FULL')), 
    CONSTRAINT ck_model_versions_research_release CHECK (release_ready = false), 
    CONSTRAINT uq_model_versions_id_variant UNIQUE (id, variant), 
    CONSTRAINT uq_model_versions_release_name UNIQUE (release_name)
);

CREATE TABLE outbox_events (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    aggregate_id UUID NOT NULL, 
    event_type TEXT NOT NULL, 
    payload_reference TEXT NOT NULL, 
    dispatched_at TIMESTAMP WITH TIME ZONE, 
    attempt_count INTEGER DEFAULT '0' NOT NULL, 
    CONSTRAINT pk_outbox_events PRIMARY KEY (id), 
    CONSTRAINT ck_outbox_events_attempt_nonnegative CHECK (attempt_count >= 0)
);

CREATE INDEX ix_outbox_pending_created ON outbox_events (created_at) WHERE dispatched_at IS NULL;

CREATE TABLE users (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    normalized_email TEXT NOT NULL, 
    password_hash TEXT NOT NULL, 
    role TEXT DEFAULT 'USER' NOT NULL, 
    account_status TEXT DEFAULT 'ACTIVE' NOT NULL, 
    permissions JSONB DEFAULT '[]'::jsonb NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_users PRIMARY KEY (id), 
    CONSTRAINT ck_users_account_status_values CHECK (account_status IN ('ACTIVE', 'DISABLED', 'CLOSED')), 
    CONSTRAINT ck_users_permissions_shape CHECK (jsonb_typeof(permissions) = 'array'), 
    CONSTRAINT ck_users_normalized_email_format CHECK (normalized_email = lower(btrim(normalized_email)) AND position('@' in normalized_email) > 1), 
    CONSTRAINT ck_users_role_values CHECK (role IN ('USER', 'ADMIN')), 
    CONSTRAINT ck_users_password_hash_nonempty CHECK (length(password_hash) > 0), 
    CONSTRAINT uq_users_normalized_email UNIQUE (normalized_email)
);

CREATE TABLE audit_events (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    actor_id UUID, 
    action TEXT NOT NULL, 
    entity_type TEXT NOT NULL, 
    entity_id UUID NOT NULL, 
    request_id TEXT NOT NULL, 
    redacted_metadata_json JSONB DEFAULT '{}'::jsonb NOT NULL, 
    CONSTRAINT pk_audit_events PRIMARY KEY (id), 
    CONSTRAINT ck_audit_events_redacted_metadata_json_shape CHECK (jsonb_typeof(redacted_metadata_json) = 'object'), 
    CONSTRAINT fk_audit_events_actor_id_users FOREIGN KEY(actor_id) REFERENCES users (id)
);

CREATE TABLE auth_sessions (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    user_id UUID NOT NULL, 
    hashed_refresh_token TEXT NOT NULL, 
    token_family_id UUID NOT NULL, 
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    revoked_at TIMESTAMP WITH TIME ZONE, 
    CONSTRAINT pk_auth_sessions PRIMARY KEY (id), 
    CONSTRAINT ck_auth_sessions_expires_after_creation CHECK (expires_at > created_at), 
    CONSTRAINT ck_auth_sessions_revocation_time CHECK (revoked_at IS NULL OR revoked_at >= created_at), 
    CONSTRAINT fk_auth_sessions_user_id_users FOREIGN KEY(user_id) REFERENCES users (id), 
    CONSTRAINT uq_auth_sessions_hashed_refresh_token UNIQUE (hashed_refresh_token)
);

CREATE INDEX ix_auth_sessions_user_id ON auth_sessions (user_id);

CREATE TABLE loan_applications (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    user_id UUID NOT NULL, 
    current_version INTEGER DEFAULT '1' NOT NULL, 
    product_code TEXT DEFAULT 'CASH_INSTALLMENT_V1' NOT NULL, 
    currency VARCHAR(3) NOT NULL, 
    requested_amount NUMERIC(20, 2) NOT NULL, 
    workflow_status TEXT DEFAULT 'DRAFT' NOT NULL, 
    current_decision_id UUID, 
    submitted_at TIMESTAMP WITH TIME ZONE, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_loan_applications PRIMARY KEY (id), 
    CONSTRAINT ck_loan_applications_currency_format CHECK (currency ~ '^[A-Z]{3}$'), 
    CONSTRAINT ck_loan_applications_product_code_values CHECK (product_code IN ('CASH_INSTALLMENT_V1')), 
    CONSTRAINT ck_loan_applications_requested_amount_finite CHECK (requested_amount > 0 AND requested_amount < 'Infinity'), 
    CONSTRAINT ck_loan_applications_workflow_status_values CHECK (workflow_status IN ('DRAFT', 'SUBMITTED', 'PROCESSING', 'PENDING_DATA', 'MANUAL_REVIEW', 'DECIDED', 'WITHDRAWN')), 
    CONSTRAINT ck_loan_applications_current_version_positive CHECK (current_version > 0), 
    CONSTRAINT fk_loan_applications_user_id_users FOREIGN KEY(user_id) REFERENCES users (id), 
    CONSTRAINT uq_loan_applications_id_user_id UNIQUE (id, user_id)
);

CREATE INDEX ix_applications_status_submitted ON loan_applications (workflow_status, submitted_at);

CREATE INDEX ix_applications_user_created ON loan_applications (user_id, created_at);

CREATE TABLE model_deployments (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    product_code TEXT NOT NULL, 
    variant TEXT NOT NULL, 
    model_version_id UUID NOT NULL, 
    activated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    retired_at TIMESTAMP WITH TIME ZONE, 
    CONSTRAINT pk_model_deployments PRIMARY KEY (id), 
    CONSTRAINT ck_model_deployments_variant_values CHECK (variant IN ('LITE', 'FULL')), 
    CONSTRAINT ck_model_deployments_retirement_order CHECK (retired_at IS NULL OR retired_at >= activated_at), 
    CONSTRAINT fk_model_deployments_model_version_id_model_versions FOREIGN KEY(model_version_id, variant) REFERENCES model_versions (id, variant)
);

CREATE UNIQUE INDEX uq_model_deployment_active ON model_deployments (product_code, variant) WHERE retired_at IS NULL;

CREATE TABLE policy_versions (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    version TEXT NOT NULL, 
    product_code TEXT NOT NULL, 
    variant TEXT NOT NULL, 
    mode TEXT DEFAULT 'SANDBOX' NOT NULL, 
    approve_below DOUBLE PRECISION, 
    reject_at DOUBLE PRECISION, 
    band_thresholds_json JSONB DEFAULT '{}'::jsonb NOT NULL, 
    affordability_rules_json JSONB DEFAULT '{}'::jsonb NOT NULL, 
    validation_report_key TEXT, 
    approved_by UUID, 
    effective_from TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_policy_versions PRIMARY KEY (id), 
    CONSTRAINT ck_policy_versions_affordability_rules_json_shape CHECK (jsonb_typeof(affordability_rules_json) = 'object'), 
    CONSTRAINT ck_policy_versions_band_thresholds_json_shape CHECK (jsonb_typeof(band_thresholds_json) = 'object'), 
    CONSTRAINT ck_policy_versions_mode_values CHECK (mode IN ('SANDBOX', 'SHADOW')), 
    CONSTRAINT ck_policy_versions_variant_values CHECK (variant IN ('LITE', 'FULL')), 
    CONSTRAINT ck_policy_versions_threshold_order CHECK ((approve_below IS NULL AND reject_at IS NULL) OR (approve_below IS NOT NULL AND reject_at IS NOT NULL AND 0 < approve_below AND approve_below < reject_at AND reject_at < 1)), 
    CONSTRAINT fk_policy_versions_approved_by_users FOREIGN KEY(approved_by) REFERENCES users (id), 
    CONSTRAINT uq_policy_versions_version UNIQUE (version)
);

CREATE TABLE user_profiles (
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    user_id UUID NOT NULL, 
    full_name TEXT NOT NULL, 
    birth_date DATE, 
    contact_json JSONB DEFAULT '{}'::jsonb NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_user_profiles PRIMARY KEY (user_id), 
    CONSTRAINT ck_user_profiles_contact_json_shape CHECK (jsonb_typeof(contact_json) = 'object'), 
    CONSTRAINT fk_user_profiles_user_id_users FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE TABLE application_versions (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    application_id UUID NOT NULL, 
    version INTEGER NOT NULL, 
    input_schema_version TEXT NOT NULL, 
    immutable_input_json JSONB DEFAULT '{}'::jsonb NOT NULL, 
    input_hash VARCHAR(64) NOT NULL, 
    as_of TIMESTAMP WITH TIME ZONE NOT NULL, 
    created_by UUID NOT NULL, 
    CONSTRAINT pk_application_versions PRIMARY KEY (id), 
    CONSTRAINT ck_application_versions_input_hash_sha256 CHECK (input_hash ~ '^[0-9a-f]{64}$'), 
    CONSTRAINT ck_application_versions_immutable_input_json_shape CHECK (jsonb_typeof(immutable_input_json) = 'object'), 
    CONSTRAINT ck_application_versions_version_positive CHECK (version > 0), 
    CONSTRAINT fk_application_versions_application_id_loan_applications FOREIGN KEY(application_id) REFERENCES loan_applications (id), 
    CONSTRAINT fk_application_versions_created_by_users FOREIGN KEY(created_by) REFERENCES users (id), 
    CONSTRAINT uq_application_versions_application_id_version UNIQUE (application_id, version), 
    CONSTRAINT uq_application_versions_id_application_id_version UNIQUE (id, application_id, version), 
    CONSTRAINT uq_application_versions_id_application_id UNIQUE (id, application_id)
);

CREATE TABLE data_consents (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    application_id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    purpose TEXT NOT NULL, 
    source_scope TEXT NOT NULL, 
    consent_version TEXT NOT NULL, 
    granted_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    revoked_at TIMESTAMP WITH TIME ZONE, 
    CONSTRAINT pk_data_consents PRIMARY KEY (id), 
    CONSTRAINT ck_data_consents_revocation_order CHECK (revoked_at IS NULL OR revoked_at >= granted_at), 
    CONSTRAINT fk_data_consents_application_id_loan_applications FOREIGN KEY(application_id, user_id) REFERENCES loan_applications (id, user_id), 
    CONSTRAINT uq_data_consents_id_application_id UNIQUE (id, application_id)
);

CREATE TABLE reports (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    requested_by UUID NOT NULL, 
    application_id UUID, 
    report_type TEXT NOT NULL, 
    format TEXT NOT NULL, 
    filter_snapshot_json JSONB DEFAULT '{}'::jsonb NOT NULL, 
    status TEXT DEFAULT 'QUEUED' NOT NULL, 
    object_key TEXT, 
    content_hash VARCHAR(64), 
    expires_at TIMESTAMP WITH TIME ZONE, 
    completed_at TIMESTAMP WITH TIME ZONE, 
    CONSTRAINT pk_reports PRIMARY KEY (id), 
    CONSTRAINT ck_reports_content_hash_sha256 CHECK (content_hash ~ '^[0-9a-f]{64}$'), 
    CONSTRAINT ck_reports_format_values CHECK (format IN ('PDF', 'XLSX')), 
    CONSTRAINT ck_reports_filter_snapshot_json_shape CHECK (jsonb_typeof(filter_snapshot_json) = 'object'), 
    CONSTRAINT ck_reports_completed_report_object CHECK (status <> 'SUCCEEDED' OR (object_key IS NOT NULL AND content_hash IS NOT NULL AND completed_at IS NOT NULL)), 
    CONSTRAINT ck_reports_status_values CHECK (status IN ('QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'EXPIRED')), 
    CONSTRAINT fk_reports_application_id_loan_applications FOREIGN KEY(application_id) REFERENCES loan_applications (id), 
    CONSTRAINT fk_reports_requested_by_users FOREIGN KEY(requested_by) REFERENCES users (id)
);

CREATE INDEX ix_reports_requester_created ON reports (requested_by, created_at);

CREATE TABLE feature_snapshots (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    application_version_id UUID NOT NULL, 
    variant TEXT NOT NULL, 
    feature_schema_version TEXT NOT NULL, 
    feature_values_json JSONB DEFAULT '{}'::jsonb NOT NULL, 
    ordered_feature_hash VARCHAR(64) NOT NULL, 
    quality_flags_json JSONB DEFAULT '[]'::jsonb NOT NULL, 
    as_of TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_feature_snapshots PRIMARY KEY (id), 
    CONSTRAINT ck_feature_snapshots_feature_values_json_shape CHECK (jsonb_typeof(feature_values_json) = 'object'), 
    CONSTRAINT ck_feature_snapshots_quality_flags_json_shape CHECK (jsonb_typeof(quality_flags_json) = 'array'), 
    CONSTRAINT ck_feature_snapshots_ordered_feature_hash_sha256 CHECK (ordered_feature_hash ~ '^[0-9a-f]{64}$'), 
    CONSTRAINT ck_feature_snapshots_variant_values CHECK (variant IN ('LITE', 'FULL')), 
    CONSTRAINT fk_feature_snapshots_application_version_id_application_8217 FOREIGN KEY(application_version_id) REFERENCES application_versions (id), 
    CONSTRAINT uq_feature_snapshots_id_application_version_id_variant UNIQUE (id, application_version_id, variant), 
    CONSTRAINT uq_feature_snapshots_id_application_version_id UNIQUE (id, application_version_id)
);

CREATE TABLE loan_quotes (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    application_version_id UUID NOT NULL, 
    product_version TEXT NOT NULL, 
    principal NUMERIC(20, 2) NOT NULL, 
    term_months INTEGER NOT NULL, 
    annual_rate NUMERIC(12, 8) NOT NULL, 
    monthly_payment NUMERIC(20, 2) NOT NULL, 
    fees_json JSONB DEFAULT '{}'::jsonb NOT NULL, 
    currency VARCHAR(3) NOT NULL, 
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_loan_quotes PRIMARY KEY (id), 
    CONSTRAINT ck_loan_quotes_annual_rate_finite CHECK (annual_rate >= 0 AND annual_rate < 'Infinity'), 
    CONSTRAINT ck_loan_quotes_currency_format CHECK (currency ~ '^[A-Z]{3}$'), 
    CONSTRAINT ck_loan_quotes_fees_json_shape CHECK (jsonb_typeof(fees_json) = 'object'), 
    CONSTRAINT ck_loan_quotes_monthly_payment_finite CHECK (monthly_payment > 0 AND monthly_payment < 'Infinity'), 
    CONSTRAINT ck_loan_quotes_principal_finite CHECK (principal > 0 AND principal < 'Infinity'), 
    CONSTRAINT ck_loan_quotes_expiry CHECK (expires_at > created_at), 
    CONSTRAINT ck_loan_quotes_term_positive CHECK (term_months > 0), 
    CONSTRAINT fk_loan_quotes_application_version_id_application_versions FOREIGN KEY(application_version_id) REFERENCES application_versions (id)
);

CREATE INDEX ix_loan_quotes_application_version ON loan_quotes (application_version_id);

CREATE TABLE scoring_jobs (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    application_version_id UUID NOT NULL, 
    variant_requested TEXT DEFAULT 'AUTO' NOT NULL, 
    status TEXT DEFAULT 'QUEUED' NOT NULL, 
    model_version_id UUID, 
    idempotency_key TEXT NOT NULL, 
    request_body_hash VARCHAR(64) NOT NULL, 
    error_code TEXT, 
    attempts INTEGER DEFAULT '0' NOT NULL, 
    completed_at TIMESTAMP WITH TIME ZONE, 
    CONSTRAINT pk_scoring_jobs PRIMARY KEY (id), 
    CONSTRAINT ck_scoring_jobs_request_body_hash_sha256 CHECK (request_body_hash ~ '^[0-9a-f]{64}$'), 
    CONSTRAINT ck_scoring_jobs_status_values CHECK (status IN ('QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'PENDING_DATA')), 
    CONSTRAINT ck_scoring_jobs_variant_requested_values CHECK (variant_requested IN ('AUTO', 'LITE', 'FULL')), 
    CONSTRAINT ck_scoring_jobs_attempts_nonnegative CHECK (attempts >= 0), 
    CONSTRAINT fk_scoring_jobs_application_version_id_application_versions FOREIGN KEY(application_version_id) REFERENCES application_versions (id), 
    CONSTRAINT fk_scoring_jobs_model_version_id_model_versions FOREIGN KEY(model_version_id) REFERENCES model_versions (id), 
    CONSTRAINT uq_scoring_jobs_application_version_id_idempotency_key UNIQUE (application_version_id, idempotency_key), 
    CONSTRAINT uq_scoring_jobs_id_application_version_id_model_version_id UNIQUE (id, application_version_id, model_version_id)
);

CREATE INDEX ix_jobs_status_created ON scoring_jobs (status, created_at);

CREATE TABLE source_snapshots (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    application_version_id UUID NOT NULL, 
    application_id UUID NOT NULL, 
    source_type TEXT NOT NULL, 
    state TEXT NOT NULL, 
    source_as_of TIMESTAMP WITH TIME ZONE NOT NULL, 
    fetched_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    schema_version TEXT NOT NULL, 
    coverage_json JSONB DEFAULT '{}'::jsonb NOT NULL, 
    object_key TEXT, 
    content_hash VARCHAR(64), 
    consent_id UUID, 
    CONSTRAINT pk_source_snapshots PRIMARY KEY (id), 
    CONSTRAINT ck_source_snapshots_content_hash_sha256 CHECK (content_hash ~ '^[0-9a-f]{64}$'), 
    CONSTRAINT ck_source_snapshots_coverage_json_shape CHECK (jsonb_typeof(coverage_json) = 'object'), 
    CONSTRAINT ck_source_snapshots_state_values CHECK (state IN ('COMPLETE', 'CONFIRMED_EMPTY', 'UNAVAILABLE', 'INVALID')), 
    CONSTRAINT ck_source_snapshots_coverage_time CHECK (source_as_of <= fetched_at), 
    CONSTRAINT fk_source_snapshots_application_version_id_application_versions FOREIGN KEY(application_version_id, application_id) REFERENCES application_versions (id, application_id), 
    CONSTRAINT fk_source_snapshots_consent_id_data_consents FOREIGN KEY(consent_id, application_id) REFERENCES data_consents (id, application_id), 
    CONSTRAINT uq_source_snapshots_id_application_id UNIQUE (id, application_id), 
    CONSTRAINT uq_source_snapshots_id_application_version_id UNIQUE (id, application_version_id)
);

CREATE TABLE feature_snapshot_sources (
    feature_snapshot_id UUID NOT NULL, 
    source_snapshot_id UUID NOT NULL, 
    application_version_id UUID NOT NULL, 
    CONSTRAINT pk_feature_snapshot_sources PRIMARY KEY (feature_snapshot_id, source_snapshot_id), 
    CONSTRAINT fk_feature_snapshot_sources_feature_snapshot_id_feature_30fa FOREIGN KEY(feature_snapshot_id, application_version_id) REFERENCES feature_snapshots (id, application_version_id), 
    CONSTRAINT fk_feature_snapshot_sources_source_snapshot_id_source_snapshots FOREIGN KEY(source_snapshot_id, application_version_id) REFERENCES source_snapshots (id, application_version_id)
);

CREATE TABLE loan_outcomes (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    application_id UUID NOT NULL, 
    outcome_definition_version TEXT NOT NULL, 
    observation_end TIMESTAMP WITH TIME ZONE NOT NULL, 
    outcome_matured BOOLEAN DEFAULT false NOT NULL, 
    default_observed BOOLEAN, 
    exposure NUMERIC(20, 2), 
    loss_amount NUMERIC(20, 2), 
    source_snapshot_id UUID, 
    CONSTRAINT pk_loan_outcomes PRIMARY KEY (id), 
    CONSTRAINT ck_loan_outcomes_exposure_finite CHECK (exposure >= 0 AND exposure < 'Infinity'), 
    CONSTRAINT ck_loan_outcomes_loss_amount_finite CHECK (loss_amount >= 0 AND loss_amount < 'Infinity'), 
    CONSTRAINT ck_loan_outcomes_matured_outcome CHECK ((outcome_matured AND default_observed IS NOT NULL) OR (NOT outcome_matured AND default_observed IS NULL)), 
    CONSTRAINT fk_loan_outcomes_application_id_loan_applications FOREIGN KEY(application_id) REFERENCES loan_applications (id), 
    CONSTRAINT fk_loan_outcomes_source_snapshot_id_source_snapshots FOREIGN KEY(source_snapshot_id, application_id) REFERENCES source_snapshots (id, application_id)
);

CREATE TABLE predictions (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    scoring_job_id UUID NOT NULL, 
    application_version_id UUID NOT NULL, 
    feature_snapshot_id UUID NOT NULL, 
    model_version_id UUID NOT NULL, 
    variant TEXT NOT NULL, 
    raw_positive_output DOUBLE PRECISION NOT NULL, 
    calibrated_pd DOUBLE PRECISION NOT NULL, 
    quality_flags_json JSONB DEFAULT '[]'::jsonb NOT NULL, 
    verification_status TEXT NOT NULL, 
    scored_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_predictions PRIMARY KEY (id), 
    CONSTRAINT ck_predictions_quality_flags_json_shape CHECK (jsonb_typeof(quality_flags_json) = 'array'), 
    CONSTRAINT ck_predictions_raw_output_finite CHECK (raw_positive_output > '-Infinity'::float8 AND raw_positive_output < 'Infinity'::float8), 
    CONSTRAINT ck_predictions_variant_values CHECK (variant IN ('LITE', 'FULL')), 
    CONSTRAINT ck_predictions_verification_status_values CHECK (verification_status IN ('UNVERIFIED', 'PARTIAL', 'VERIFIED')), 
    CONSTRAINT ck_predictions_calibrated_pd_bounds CHECK (calibrated_pd >= 0 AND calibrated_pd <= 1), 
    CONSTRAINT fk_predictions_feature_snapshot_id_feature_snapshots FOREIGN KEY(feature_snapshot_id, application_version_id, variant) REFERENCES feature_snapshots (id, application_version_id, variant), 
    CONSTRAINT fk_predictions_model_version_id_model_versions FOREIGN KEY(model_version_id, variant) REFERENCES model_versions (id, variant), 
    CONSTRAINT fk_predictions_scoring_job_id_scoring_jobs FOREIGN KEY(scoring_job_id, application_version_id, model_version_id) REFERENCES scoring_jobs (id, application_version_id, model_version_id), 
    CONSTRAINT uq_predictions_id_application_version_id UNIQUE (id, application_version_id), 
    CONSTRAINT uq_predictions_scoring_job_id UNIQUE (scoring_job_id)
);

CREATE INDEX ix_predictions_version_scored ON predictions (application_version_id, scored_at);

CREATE TABLE decisions (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    application_version_id UUID NOT NULL, 
    application_id UUID NOT NULL, 
    application_version_number INTEGER NOT NULL, 
    prediction_id UUID, 
    policy_version_id UUID NOT NULL, 
    kind TEXT NOT NULL, 
    status TEXT NOT NULL, 
    reason_codes_json JSONB DEFAULT '[]'::jsonb NOT NULL, 
    affordability_snapshot_json JSONB DEFAULT '{}'::jsonb NOT NULL, 
    actor_id UUID, 
    supersedes_id UUID, 
    CONSTRAINT pk_decisions PRIMARY KEY (id), 
    CONSTRAINT ck_decisions_kind_status CHECK ((kind = 'RECOMMENDATION' AND status IN ('APPROVAL_CANDIDATE','REJECTION_CANDIDATE','MANUAL_REVIEW','PENDING_DATA')) OR (kind = 'FINAL' AND status IN ('MANUAL_REVIEW','PENDING_DATA','APPROVED','REJECTED'))), 
    CONSTRAINT ck_decisions_affordability_snapshot_json_shape CHECK (jsonb_typeof(affordability_snapshot_json) = 'object'), 
    CONSTRAINT ck_decisions_reason_codes_json_shape CHECK (jsonb_typeof(reason_codes_json) = 'array'), 
    CONSTRAINT ck_decisions_kind_values CHECK (kind IN ('RECOMMENDATION', 'FINAL')), 
    CONSTRAINT ck_decisions_human_final_credit_decision CHECK (status NOT IN ('APPROVED','REJECTED') OR actor_id IS NOT NULL), 
    CONSTRAINT ck_decisions_no_self_supersede CHECK (supersedes_id IS NULL OR supersedes_id <> id), 
    CONSTRAINT fk_decisions_actor_id_users FOREIGN KEY(actor_id) REFERENCES users (id), 
    CONSTRAINT fk_decisions_application_version_id_application_versions FOREIGN KEY(application_version_id, application_id, application_version_number) REFERENCES application_versions (id, application_id, version), 
    CONSTRAINT fk_decisions_policy_version_id_policy_versions FOREIGN KEY(policy_version_id) REFERENCES policy_versions (id), 
    CONSTRAINT fk_decisions_prediction_id_predictions FOREIGN KEY(prediction_id, application_version_id) REFERENCES predictions (id, application_version_id), 
    CONSTRAINT fk_decisions_supersedes_id_decisions FOREIGN KEY(supersedes_id, application_version_id) REFERENCES decisions (id, application_version_id), 
    CONSTRAINT uq_decisions_id_application_id_application_version_number UNIQUE (id, application_id, application_version_number), 
    CONSTRAINT uq_decisions_id_application_id UNIQUE (id, application_id), 
    CONSTRAINT uq_decisions_id_application_version_id UNIQUE (id, application_version_id)
);

CREATE TABLE explanations (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    prediction_id UUID NOT NULL, 
    explainer_version TEXT NOT NULL, 
    explained_output TEXT, 
    reference_version TEXT, 
    base_value DOUBLE PRECISION, 
    contributions_json JSONB DEFAULT '{}'::jsonb NOT NULL, 
    remainder_value DOUBLE PRECISION, 
    additivity_error DOUBLE PRECISION, 
    status TEXT NOT NULL, 
    CONSTRAINT pk_explanations PRIMARY KEY (id), 
    CONSTRAINT ck_explanations_additivity_error_finite CHECK (additivity_error > '-Infinity'::float8 AND additivity_error < 'Infinity'::float8), 
    CONSTRAINT ck_explanations_base_value_finite CHECK (base_value > '-Infinity'::float8 AND base_value < 'Infinity'::float8), 
    CONSTRAINT ck_explanations_explained_output_values CHECK (explained_output IN ('raw_margin', 'uncalibrated_probability')), 
    CONSTRAINT ck_explanations_contributions_json_shape CHECK (jsonb_typeof(contributions_json) = 'object'), 
    CONSTRAINT ck_explanations_remainder_value_finite CHECK (remainder_value > '-Infinity'::float8 AND remainder_value < 'Infinity'::float8), 
    CONSTRAINT ck_explanations_success_requires_values CHECK (status <> 'SUCCEEDED' OR (explained_output IS NOT NULL AND reference_version IS NOT NULL AND base_value IS NOT NULL AND remainder_value IS NOT NULL AND additivity_error IS NOT NULL)), 
    CONSTRAINT ck_explanations_status_values CHECK (status IN ('PENDING', 'SUCCEEDED', 'FAILED')), 
    CONSTRAINT fk_explanations_prediction_id_predictions FOREIGN KEY(prediction_id) REFERENCES predictions (id), 
    CONSTRAINT uq_explanations_prediction_id_explainer_version UNIQUE (prediction_id, explainer_version)
);

CREATE TABLE risk_scores (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    prediction_id UUID NOT NULL, 
    score_policy_version TEXT NOT NULL, 
    risk_score DOUBLE PRECISION NOT NULL, 
    risk_band TEXT NOT NULL, 
    reference_percentile DOUBLE PRECISION, 
    reference_cohort_version TEXT, 
    credit_health_index DOUBLE PRECISION NOT NULL, 
    CONSTRAINT pk_risk_scores PRIMARY KEY (id), 
    CONSTRAINT ck_risk_scores_risk_band_values CHECK (risk_band IN ('Low', 'Medium', 'High')), 
    CONSTRAINT ck_risk_scores_reference_pair CHECK ((reference_percentile IS NULL) = (reference_cohort_version IS NULL)), 
    CONSTRAINT ck_risk_scores_credit_health_index_bounds CHECK (credit_health_index >= 0 AND credit_health_index <= 100), 
    CONSTRAINT ck_risk_scores_reference_percentile_bounds CHECK (reference_percentile >= 0 AND reference_percentile <= 100), 
    CONSTRAINT ck_risk_scores_risk_score_bounds CHECK (risk_score >= 0 AND risk_score <= 100), 
    CONSTRAINT fk_risk_scores_prediction_id_predictions FOREIGN KEY(prediction_id) REFERENCES predictions (id), 
    CONSTRAINT uq_risk_scores_prediction_id_score_policy_version UNIQUE (prediction_id, score_policy_version)
);

CREATE TABLE segment_assignments (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    prediction_id UUID NOT NULL, 
    segmenter_version TEXT NOT NULL, 
    segment_id INTEGER, 
    label TEXT, 
    distance DOUBLE PRECISION, 
    status TEXT NOT NULL, 
    CONSTRAINT pk_segment_assignments PRIMARY KEY (id), 
    CONSTRAINT ck_segment_assignments_distance_finite CHECK (distance >= 0 AND distance < 'Infinity'), 
    CONSTRAINT ck_segment_assignments_assignment_requires_values CHECK (status <> 'ASSIGNED' OR (segment_id IS NOT NULL AND label IS NOT NULL AND distance IS NOT NULL)), 
    CONSTRAINT ck_segment_assignments_status_values CHECK (status IN ('ASSIGNED', 'UNSUPPORTED')), 
    CONSTRAINT ck_segment_assignments_segment_id_nonnegative CHECK (segment_id >= 0), 
    CONSTRAINT fk_segment_assignments_prediction_id_predictions FOREIGN KEY(prediction_id) REFERENCES predictions (id), 
    CONSTRAINT uq_segment_assignments_prediction_id_segmenter_version UNIQUE (prediction_id, segmenter_version)
);

CREATE TABLE application_history (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    application_id UUID NOT NULL, 
    application_version_id UUID, 
    actor_id UUID, 
    event_type TEXT NOT NULL, 
    old_status TEXT, 
    new_status TEXT, 
    decision_id UUID, 
    request_id TEXT NOT NULL, 
    redacted_event_json JSONB DEFAULT '{}'::jsonb NOT NULL, 
    CONSTRAINT pk_application_history PRIMARY KEY (id), 
    CONSTRAINT ck_application_history_redacted_event_json_shape CHECK (jsonb_typeof(redacted_event_json) = 'object'), 
    CONSTRAINT ck_application_history_decision_requires_version CHECK (decision_id IS NULL OR application_version_id IS NOT NULL), 
    CONSTRAINT fk_application_history_actor_id_users FOREIGN KEY(actor_id) REFERENCES users (id), 
    CONSTRAINT fk_application_history_application_id_loan_applications FOREIGN KEY(application_id) REFERENCES loan_applications (id), 
    CONSTRAINT fk_application_history_application_version_id_applicati_3d4d FOREIGN KEY(application_version_id, application_id) REFERENCES application_versions (id, application_id), 
    CONSTRAINT fk_application_history_decision_id_decisions FOREIGN KEY(decision_id, application_version_id) REFERENCES decisions (id, application_version_id)
);

CREATE INDEX ix_history_application_created ON application_history (application_id, created_at);

ALTER TABLE loan_applications ADD CONSTRAINT fk_application_current_version FOREIGN KEY(id, current_version) REFERENCES application_versions (application_id, version) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE loan_applications ADD CONSTRAINT fk_application_current_decision FOREIGN KEY(current_decision_id, id, current_version) REFERENCES decisions (id, application_id, application_version_number) DEFERRABLE INITIALLY DEFERRED;

CREATE FUNCTION creditiq_reject_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN RAISE EXCEPTION 'immutable record in %', TG_TABLE_NAME USING ERRCODE = '23514'; END; $$;

CREATE TRIGGER immutable_record BEFORE UPDATE OR DELETE ON application_versions FOR EACH ROW EXECUTE FUNCTION creditiq_reject_mutation();

CREATE TRIGGER immutable_record BEFORE UPDATE OR DELETE ON loan_quotes FOR EACH ROW EXECUTE FUNCTION creditiq_reject_mutation();

CREATE TRIGGER immutable_record BEFORE UPDATE OR DELETE ON source_snapshots FOR EACH ROW EXECUTE FUNCTION creditiq_reject_mutation();

CREATE TRIGGER immutable_record BEFORE UPDATE OR DELETE ON feature_snapshots FOR EACH ROW EXECUTE FUNCTION creditiq_reject_mutation();

CREATE TRIGGER immutable_record BEFORE UPDATE OR DELETE ON feature_snapshot_sources FOR EACH ROW EXECUTE FUNCTION creditiq_reject_mutation();

CREATE TRIGGER immutable_record BEFORE UPDATE OR DELETE ON model_versions FOR EACH ROW EXECUTE FUNCTION creditiq_reject_mutation();

CREATE TRIGGER immutable_record BEFORE UPDATE OR DELETE ON predictions FOR EACH ROW EXECUTE FUNCTION creditiq_reject_mutation();

CREATE TRIGGER immutable_record BEFORE UPDATE OR DELETE ON risk_scores FOR EACH ROW EXECUTE FUNCTION creditiq_reject_mutation();

CREATE TRIGGER immutable_record BEFORE UPDATE OR DELETE ON policy_versions FOR EACH ROW EXECUTE FUNCTION creditiq_reject_mutation();

CREATE TRIGGER immutable_record BEFORE UPDATE OR DELETE ON decisions FOR EACH ROW EXECUTE FUNCTION creditiq_reject_mutation();

CREATE TRIGGER immutable_record BEFORE UPDATE OR DELETE ON segment_assignments FOR EACH ROW EXECUTE FUNCTION creditiq_reject_mutation();

CREATE TRIGGER immutable_record BEFORE UPDATE OR DELETE ON application_history FOR EACH ROW EXECUTE FUNCTION creditiq_reject_mutation();

CREATE TRIGGER immutable_record BEFORE UPDATE OR DELETE ON loan_outcomes FOR EACH ROW EXECUTE FUNCTION creditiq_reject_mutation();

CREATE TRIGGER immutable_record BEFORE UPDATE OR DELETE ON audit_events FOR EACH ROW EXECUTE FUNCTION creditiq_reject_mutation();

CREATE FUNCTION creditiq_protect_explanation() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF OLD.status = 'SUCCEEDED' THEN
        RAISE EXCEPTION 'completed explanation is immutable' USING ERRCODE = '23514';
      END IF;
      IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
      RETURN NEW;
    END; $$;

CREATE TRIGGER completed_explanation BEFORE UPDATE OR DELETE ON explanations FOR EACH ROW EXECUTE FUNCTION creditiq_protect_explanation();

CREATE FUNCTION creditiq_touch_updated_at() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN NEW.updated_at = now(); RETURN NEW; END; $$;

CREATE TRIGGER touch_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION creditiq_touch_updated_at();

CREATE TRIGGER touch_updated_at BEFORE UPDATE ON user_profiles FOR EACH ROW EXECUTE FUNCTION creditiq_touch_updated_at();

CREATE TRIGGER touch_updated_at BEFORE UPDATE ON loan_applications FOR EACH ROW EXECUTE FUNCTION creditiq_touch_updated_at();

INSERT INTO alembic_version (version_num) VALUES ('20261003_0001') RETURNING alembic_version.version_num;

-- Running upgrade 20261003_0001 -> 20261003_0002

CREATE INDEX ix_auth_sessions_user_family ON auth_sessions (user_id, token_family_id);

CREATE INDEX ix_auth_sessions_active_expiry ON auth_sessions (user_id, expires_at) WHERE revoked_at IS NULL;

CREATE INDEX ix_audit_auth_rate ON audit_events (action, entity_id, created_at);

UPDATE alembic_version SET version_num='20261003_0002' WHERE alembic_version.version_num = '20261003_0001';

COMMIT;

