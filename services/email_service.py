"""
Email service for sending formal emails via SMTP with STARTTLS.
"""

import asyncio
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class EmailResult:
    """Result of an email send operation."""

    success: bool
    message: str
    recipients_sent: List[str]


class EmailService:
    """Service for sending emails via SMTP."""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        username: str,
        password: str,
        from_address: str,
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_address = from_address

    def send_email(
        self,
        recipients: List[str],
        subject: str,
        body: str,
        html_body: Optional[str] = None,
    ) -> EmailResult:
        """
        Send an email to the specified recipients.

        Args:
            recipients: List of email addresses to send to
            subject: Email subject line
            body: Plain text email body
            html_body: Optional HTML version of the email body

        Returns:
            EmailResult with success status and details
        """
        try:
            # Create message
            if html_body:
                msg = MIMEMultipart("alternative")
                msg.attach(MIMEText(body, "plain"))
                msg.attach(MIMEText(html_body, "html"))
            else:
                msg = MIMEText(body, "plain")

            msg["Subject"] = subject
            msg["From"] = self.from_address
            msg["To"] = ", ".join(recipients)

            # Send via SMTP with STARTTLS
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30) as server:
                server.ehlo()  # Identify ourselves to the server
                # Upgrade connection to TLS using STARTTLS
                context = ssl.create_default_context()
                server.starttls(context=context)
                server.ehlo()  # Re-identify after STARTTLS
                server.login(self.username, self.password)
                server.sendmail(self.from_address, recipients, msg.as_string())

            return EmailResult(
                success=True,
                message=f"Email sent successfully to {len(recipients)} recipient(s)",
                recipients_sent=recipients,
            )

        except smtplib.SMTPAuthenticationError as e:
            return EmailResult(
                success=False,
                message=f"SMTP authentication failed: {str(e)}",
                recipients_sent=[],
            )
        except smtplib.SMTPException as e:
            return EmailResult(
                success=False, message=f"SMTP error: {str(e)}", recipients_sent=[]
            )
        except Exception as e:
            return EmailResult(
                success=False,
                message=f"Failed to send email: {str(e)}",
                recipients_sent=[],
            )

    async def send_email_async(
        self,
        recipients: List[str],
        subject: str,
        body: str,
        html_body: Optional[str] = None,
    ) -> EmailResult:
        """Async wrapper for send_email."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, lambda: self.send_email(recipients, subject, body, html_body)
        )

