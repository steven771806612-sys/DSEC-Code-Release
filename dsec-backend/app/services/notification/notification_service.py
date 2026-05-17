"""Email notification service."""
import asyncio
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional
from uuid import UUID

import aiosmtplib
from jinja2 import Environment, PackageLoader, select_autoescape

from app.core.config import settings

# Simple inline templates (avoids filesystem dependency)
EMAIL_TEMPLATES = {
    "CaseSubmitted": {
        "subject": "[DSEC] New Case Submitted for Review: {case_title}",
        "body": """
<h2>New Case Submitted</h2>
<p>A new case has been submitted and is ready for your review.</p>
<ul>
  <li><strong>Case Title:</strong> {case_title}</li>
  <li><strong>Submitted By:</strong> {actor_name}</li>
  <li><strong>Industry:</strong> {industry}</li>
</ul>
<p><a href="{portal_link}">View Case →</a></p>
""",
    },
    "AIReviewCompleted": {
        "subject": "[DSEC] AI Review Completed — Action Required: {case_title}",
        "body": """
<h2>AI Review Completed</h2>
<p>The AI has completed its review. Please review the findings.</p>
<ul>
  <li><strong>Case:</strong> {case_title}</li>
  <li><strong>AI Score:</strong> {ai_score}</li>
  <li><strong>Confidence:</strong> {confidence}</li>
</ul>
<p><a href="{portal_link}">Review Now →</a></p>
""",
    },
    "CaseApproved": {
        "subject": "[DSEC] Congratulations! Case Approved: {case_title}",
        "body": """
<h2>Case Approved</h2>
<p>Your case has been approved by DJI SE.</p>
<ul>
  <li><strong>Case:</strong> {case_title}</li>
  <li><strong>Final Score:</strong> {final_score}</li>
</ul>
<p><a href="{portal_link}">View Details →</a></p>
""",
    },
    "CaseRejected": {
        "subject": "[DSEC] Case Review Result: {case_title}",
        "body": """
<h2>Case Requires Revision</h2>
<p>Your case was not approved this time. Please review the feedback.</p>
<ul>
  <li><strong>Case:</strong> {case_title}</li>
  <li><strong>Feedback:</strong> {feedback}</li>
</ul>
<p><a href="{portal_link}">View Feedback →</a></p>
""",
    },
    "SLABreached": {
        "subject": "[DSEC] SLA Alert — Review Overdue: {case_title}",
        "body": """
<h2>SLA Breach Alert</h2>
<p>A review task has exceeded its SLA deadline.</p>
<ul>
  <li><strong>Case:</strong> {case_title}</li>
  <li><strong>Review Type:</strong> {review_type}</li>
  <li><strong>Due At:</strong> {due_at}</li>
</ul>
<p><a href="{portal_link}">Take Action →</a></p>
""",
    },
}


class NotificationService:
    async def send_email(
        self,
        to_email: str,
        event_type: str,
        context: dict,
    ) -> bool:
        """Send an HTML email for the given event type."""
        template = EMAIL_TEMPLATES.get(event_type)
        if not template:
            return False

        subject = template["subject"].format(**context)
        html_body = template["body"].format(**context)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_FROM
        msg["To"] = to_email
        msg.attach(MIMEText(html_body, "html"))

        try:
            await aiosmtplib.send(
                msg,
                hostname=settings.SMTP_HOST,
                port=settings.SMTP_PORT,
                username=settings.SMTP_USER or None,
                password=settings.SMTP_PASSWORD or None,
                use_tls=settings.SMTP_TLS,
            )
            return True
        except Exception as exc:
            # Log but don't crash the main flow
            import structlog
            log = structlog.get_logger()
            log.error("email_send_failed", event_type=event_type, error=str(exc))
            return False

    async def push_portal_notification(
        self,
        db,  # AsyncSession
        user_id: UUID,
        event_type: str,
        title: str,
        body: Optional[str] = None,
        case_id: Optional[UUID] = None,
    ) -> None:
        """Create an in-app portal notification."""
        from app.models.audit import PortalNotification
        notif = PortalNotification(
            user_id=user_id,
            event_type=event_type,
            title=title,
            body=body,
            case_id=case_id,
        )
        db.add(notif)
        # Caller is responsible for commit


# Singleton
notification_service = NotificationService()
