"""Domain-specific ORM model modules. Import order matters for SQLAlchemy mapper registration."""
from app.models._db.base import Base
from app.models._db.user import UserModel
from app.models._db.legal_base import LegalBaseModel
from app.models._db.playbook import PlaybookModel, PlaybookRevisionModel, PromptTemplateModel
from app.models._db.case import CaseModel, ActivityLogModel
from app.models._db.document import DocumentModel, DocumentCommentModel
from app.models._db.finding import FindingModel, FindingCommentModel, FindingChatMessageModel
from app.models._db.job import (
    RunChecksJobModel,
    DSBReportModel,
    DSBReportJobModel,
    DSFAAssessmentModel,
    DSFAJobModel,
)
from app.models._db.compliance import (
    DSRRequestModel,
    DSRActivityLogModel,
    DataBreachModel,
    DataBreachActivityLogModel,
    AVVContractModel,
    TOMModel,
    TOMAttachmentModel,
    PrivacyPolicyModel,
    CaseTemplateModel,
)
from app.models._db.webhook import WebhookConfigModel, WebhookDeliveryLogModel
from app.models._db.analytics import ComplianceMaturitySnapshotModel

__all__ = [
    "Base",
    "ActivityLogModel",
    "AVVContractModel",
    "ComplianceMaturitySnapshotModel",
    "CaseModel",
    "CaseTemplateModel",
    "DataBreachActivityLogModel",
    "DataBreachModel",
    "DocumentCommentModel",
    "DocumentModel",
    "DSBReportJobModel",
    "DSBReportModel",
    "DSFAAssessmentModel",
    "DSFAJobModel",
    "DSRActivityLogModel",
    "DSRRequestModel",
    "FindingChatMessageModel",
    "FindingCommentModel",
    "FindingModel",
    "LegalBaseModel",
    "PlaybookModel",
    "PlaybookRevisionModel",
    "PrivacyPolicyModel",
    "PromptTemplateModel",
    "RunChecksJobModel",
    "TOMAttachmentModel",
    "TOMModel",
    "UserModel",
    "WebhookConfigModel",
    "WebhookDeliveryLogModel",
]
