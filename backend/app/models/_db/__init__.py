"""Domain-specific ORM model modules. Import order matters for SQLAlchemy mapper registration."""

from app.models._db.analytics import ComplianceMaturitySnapshotModel
from app.models._db.base import Base
from app.models._db.case import ActivityLogModel, CaseModel
from app.models._db.compliance import (
    AVVContractModel,
    AvvMitigationLinkModel,
    CaseMitigationLinkModel,
    CaseTemplateModel,
    DataBreachActivityLogModel,
    DataBreachModel,
    DSRActivityLogModel,
    DSRRequestModel,
    PrivacyPolicyModel,
    TOMAttachmentModel,
    TOMModel,
)
from app.models._db.document import DocumentCommentModel, DocumentModel
from app.models._db.finding import (
    FindingChatMessageModel,
    FindingCommentModel,
    FindingModel,
)
from app.models._db.job import (
    DSBReportJobModel,
    DSBReportModel,
    DSFAAssessmentModel,
    DSFAJobModel,
    RunChecksJobModel,
)
from app.models._db.legal_base import LegalBaseModel
from app.models._db.playbook import (
    PlaybookModel,
    PlaybookRevisionModel,
    PromptTemplateModel,
)
from app.models._db.user import UserModel
from app.models._db.webhook import WebhookConfigModel, WebhookDeliveryLogModel

__all__ = [
    "Base",
    "ActivityLogModel",
    "AVVContractModel",
    "AvvMitigationLinkModel",
    "CaseMitigationLinkModel",
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
