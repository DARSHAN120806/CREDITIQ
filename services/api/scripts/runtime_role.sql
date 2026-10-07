-- Apply as the operator, inside one transaction, to revision 20261003_0003.
-- No credential literals: the provisioning tool sets a generated password separately.
-- Intentionally fails if the role already exists; review rather than reset it.
CREATE ROLE creditiq_runtime NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
    NOINHERIT NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 20;
ALTER ROLE creditiq_runtime SET search_path = pg_catalog, public;
ALTER ROLE creditiq_runtime SET statement_timeout = '15s';
ALTER ROLE creditiq_runtime SET lock_timeout = '5s';
ALTER ROLE creditiq_runtime SET idle_in_transaction_session_timeout = '60s';
DO $$ BEGIN
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO creditiq_runtime', current_database());
END $$;
GRANT USAGE ON SCHEMA public TO creditiq_runtime;
-- No membership in authenticator, anon, authenticated, service_role or owner roles.
-- Backend is the tenant authorization boundary; these policies are backend-only.
GRANT SELECT, INSERT ON public.users TO creditiq_runtime;
CREATE POLICY creditiq_runtime_select ON public.users FOR SELECT TO creditiq_runtime USING (true);
CREATE POLICY creditiq_runtime_insert ON public.users FOR INSERT TO creditiq_runtime WITH CHECK (true);
GRANT SELECT, INSERT ON public.user_profiles TO creditiq_runtime;
CREATE POLICY creditiq_runtime_select ON public.user_profiles FOR SELECT TO creditiq_runtime USING (true);
CREATE POLICY creditiq_runtime_insert ON public.user_profiles FOR INSERT TO creditiq_runtime WITH CHECK (true);
GRANT SELECT, INSERT ON public.auth_sessions TO creditiq_runtime;
CREATE POLICY creditiq_runtime_select ON public.auth_sessions FOR SELECT TO creditiq_runtime USING (true);
CREATE POLICY creditiq_runtime_insert ON public.auth_sessions FOR INSERT TO creditiq_runtime WITH CHECK (true);
GRANT SELECT, INSERT ON public.audit_events TO creditiq_runtime;
CREATE POLICY creditiq_runtime_select ON public.audit_events FOR SELECT TO creditiq_runtime USING (true);
CREATE POLICY creditiq_runtime_insert ON public.audit_events FOR INSERT TO creditiq_runtime WITH CHECK (true);
GRANT SELECT, INSERT ON public.loan_applications TO creditiq_runtime;
CREATE POLICY creditiq_runtime_select ON public.loan_applications FOR SELECT TO creditiq_runtime USING (true);
CREATE POLICY creditiq_runtime_insert ON public.loan_applications FOR INSERT TO creditiq_runtime WITH CHECK (true);
GRANT SELECT, INSERT ON public.application_versions TO creditiq_runtime;
CREATE POLICY creditiq_runtime_select ON public.application_versions FOR SELECT TO creditiq_runtime USING (true);
CREATE POLICY creditiq_runtime_insert ON public.application_versions FOR INSERT TO creditiq_runtime WITH CHECK (true);
GRANT SELECT, INSERT ON public.loan_quotes TO creditiq_runtime;
CREATE POLICY creditiq_runtime_select ON public.loan_quotes FOR SELECT TO creditiq_runtime USING (true);
CREATE POLICY creditiq_runtime_insert ON public.loan_quotes FOR INSERT TO creditiq_runtime WITH CHECK (true);
GRANT SELECT, INSERT ON public.model_versions TO creditiq_runtime;
CREATE POLICY creditiq_runtime_select ON public.model_versions FOR SELECT TO creditiq_runtime USING (true);
CREATE POLICY creditiq_runtime_insert ON public.model_versions FOR INSERT TO creditiq_runtime WITH CHECK (true);
GRANT SELECT, INSERT ON public.policy_versions TO creditiq_runtime;
CREATE POLICY creditiq_runtime_select ON public.policy_versions FOR SELECT TO creditiq_runtime USING (true);
CREATE POLICY creditiq_runtime_insert ON public.policy_versions FOR INSERT TO creditiq_runtime WITH CHECK (true);
GRANT SELECT, INSERT ON public.feature_snapshots TO creditiq_runtime;
CREATE POLICY creditiq_runtime_select ON public.feature_snapshots FOR SELECT TO creditiq_runtime USING (true);
CREATE POLICY creditiq_runtime_insert ON public.feature_snapshots FOR INSERT TO creditiq_runtime WITH CHECK (true);
GRANT SELECT, INSERT ON public.scoring_jobs TO creditiq_runtime;
CREATE POLICY creditiq_runtime_select ON public.scoring_jobs FOR SELECT TO creditiq_runtime USING (true);
CREATE POLICY creditiq_runtime_insert ON public.scoring_jobs FOR INSERT TO creditiq_runtime WITH CHECK (true);
GRANT SELECT, INSERT ON public.predictions TO creditiq_runtime;
CREATE POLICY creditiq_runtime_select ON public.predictions FOR SELECT TO creditiq_runtime USING (true);
CREATE POLICY creditiq_runtime_insert ON public.predictions FOR INSERT TO creditiq_runtime WITH CHECK (true);
GRANT SELECT, INSERT ON public.risk_scores TO creditiq_runtime;
CREATE POLICY creditiq_runtime_select ON public.risk_scores FOR SELECT TO creditiq_runtime USING (true);
CREATE POLICY creditiq_runtime_insert ON public.risk_scores FOR INSERT TO creditiq_runtime WITH CHECK (true);
GRANT SELECT, INSERT ON public.decisions TO creditiq_runtime;
CREATE POLICY creditiq_runtime_select ON public.decisions FOR SELECT TO creditiq_runtime USING (true);
CREATE POLICY creditiq_runtime_insert ON public.decisions FOR INSERT TO creditiq_runtime WITH CHECK (true);
GRANT SELECT, INSERT ON public.application_history TO creditiq_runtime;
CREATE POLICY creditiq_runtime_select ON public.application_history FOR SELECT TO creditiq_runtime USING (true);
CREATE POLICY creditiq_runtime_insert ON public.application_history FOR INSERT TO creditiq_runtime WITH CHECK (true);
GRANT SELECT, INSERT ON public.installment_imports TO creditiq_runtime;
CREATE POLICY creditiq_runtime_select ON public.installment_imports FOR SELECT TO creditiq_runtime USING (true);
CREATE POLICY creditiq_runtime_insert ON public.installment_imports FOR INSERT TO creditiq_runtime WITH CHECK (true);
GRANT SELECT, INSERT ON public.installment_schedules TO creditiq_runtime;
CREATE POLICY creditiq_runtime_select ON public.installment_schedules FOR SELECT TO creditiq_runtime USING (true);
CREATE POLICY creditiq_runtime_insert ON public.installment_schedules FOR INSERT TO creditiq_runtime WITH CHECK (true);
GRANT SELECT, INSERT ON public.installment_payments TO creditiq_runtime;
CREATE POLICY creditiq_runtime_select ON public.installment_payments FOR SELECT TO creditiq_runtime USING (true);
CREATE POLICY creditiq_runtime_insert ON public.installment_payments FOR INSERT TO creditiq_runtime WITH CHECK (true);
GRANT SELECT, INSERT ON public.installment_analyses TO creditiq_runtime;
CREATE POLICY creditiq_runtime_select ON public.installment_analyses FOR SELECT TO creditiq_runtime USING (true);
CREATE POLICY creditiq_runtime_insert ON public.installment_analyses FOR INSERT TO creditiq_runtime WITH CHECK (true);
GRANT UPDATE (password_hash) ON public.users TO creditiq_runtime;
CREATE POLICY creditiq_runtime_update ON public.users FOR UPDATE TO creditiq_runtime USING (true) WITH CHECK (true);
GRANT UPDATE (revoked_at) ON public.auth_sessions TO creditiq_runtime;
CREATE POLICY creditiq_runtime_update ON public.auth_sessions FOR UPDATE TO creditiq_runtime USING (true) WITH CHECK (true);
GRANT UPDATE (workflow_status, current_decision_id) ON public.loan_applications TO creditiq_runtime;
CREATE POLICY creditiq_runtime_update ON public.loan_applications FOR UPDATE TO creditiq_runtime USING (true) WITH CHECK (true);
-- Enable LOGIN only after grants/policies and a strong password are installed.
-- Password provisioning (psql equivalent, prompt securely before use):
-- ALTER ROLE creditiq_runtime LOGIN PASSWORD :'runtime_password';
-- No future-table grants: each new workflow must explicitly justify its permissions.
