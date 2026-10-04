"""Register all approved database models for Alembic discovery."""
from .schema import (
    User, UserProfile, AuthSession, LoanApplication, ApplicationVersion, LoanQuote,
    DataConsent, SourceSnapshot, FeatureSnapshot, FeatureSnapshotSource,
    ModelVersion, ModelDeployment, ScoringJob, Prediction, RiskScore, PolicyVersion,
    Decision, Explanation, SegmentAssignment, Report, ApplicationHistory, LoanOutcome,
    AuditEvent, OutboxEvent,
)

from .installment_analysis import InstallmentImport, InstallmentSchedule, InstallmentPayment, InstallmentAnalysis
