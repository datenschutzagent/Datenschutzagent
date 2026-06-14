"""Domain-specific ORM model modules. Import order matters for SQLAlchemy mapper registration."""

from app.models._db.analytics import ComplianceMaturitySnapshotModel
from app.models._db.avv import AVVContractModel, AvvMitigationLinkModel
from app.models._db.base import Base
from app.models._db.breach import DataBreachActivityLogModel, DataBreachModel
from app.models._db.case import ActivityLogModel, CaseModel
from app.models._db.case_template import CaseTemplateModel
from app.models._db.document import DocumentCommentModel, DocumentModel
from app.models._db.dsr import DSRActivityLogModel, DSRRequestModel
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
from app.models._db.privacy_policy import PrivacyPolicyModel
from app.models._db.tom import CaseMitigationLinkModel, TOMAttachmentModel, TOMModel
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
