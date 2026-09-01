"""
Email service for CertVerify — sends transactional and notification emails via SMTP.
"""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


def _get_smtp_connection() -> smtplib.SMTP:
    """Create and return an authenticated SMTP connection."""
    server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)
    if settings.SMTP_USE_TLS:
        server.starttls()
    if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
        server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
    return server


def send_email(
    to_email: str,
    subject: str,
    html_body: str,
    plain_body: Optional[str] = None,
) -> bool:
    """
    Send a single email via SMTP.
    Returns True on success, False on failure.
    """
    if not settings.SMTP_USERNAME:
        logger.warning("SMTP not configured — skipping email send.")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM_ADDRESS}>"
        msg["To"] = to_email
        msg["Subject"] = subject

        if plain_body:
            msg.attach(MIMEText(plain_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        server = _get_smtp_connection()
        server.sendmail(settings.EMAIL_FROM_ADDRESS, to_email, msg.as_string())
        server.quit()

        logger.info(f"Email sent to {to_email}: {subject}")
        return True

    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False


def send_bulk_emails(
    recipient_emails: list[str],
    subject: str,
    html_body: str,
    plain_body: Optional[str] = None,
) -> dict:
    """
    Send the same email to multiple recipients.
    Returns a summary of successes and failures.
    """
    if not settings.SMTP_USERNAME:
        logger.warning("SMTP not configured — skipping bulk email send.")
        return {"sent": 0, "failed": len(recipient_emails), "errors": ["SMTP not configured"]}

    sent = 0
    failed = 0
    errors = []

    try:
        server = _get_smtp_connection()

        for email_addr in recipient_emails:
            try:
                msg = MIMEMultipart("alternative")
                msg["From"] = f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM_ADDRESS}>"
                msg["To"] = email_addr
                msg["Subject"] = subject

                if plain_body:
                    msg.attach(MIMEText(plain_body, "plain"))
                msg.attach(MIMEText(html_body, "html"))

                server.sendmail(settings.EMAIL_FROM_ADDRESS, email_addr, msg.as_string())
                sent += 1
            except Exception as e:
                failed += 1
                errors.append(f"{email_addr}: {str(e)}")
                logger.error(f"Failed to send email to {email_addr}: {e}")

        server.quit()
    except Exception as e:
        logger.error(f"SMTP connection error during bulk send: {e}")
        errors.append(f"SMTP connection error: {str(e)}")

    return {"sent": sent, "failed": failed, "errors": errors}


# ─── Email Templates ─────────────────────────────────────────

def send_payment_confirmation(email: str, transaction_ref: str, amount: float) -> bool:
    """Send payment confirmation email."""
    subject = "Payment Confirmed — CertVerify"
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: #1a73e8; color: white; padding: 20px; text-align: center;">
            <h1>Payment Confirmed ✅</h1>
        </div>
        <div style="padding: 20px;">
            <p>Your payment has been successfully processed.</p>
            <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Transaction Ref:</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;">{transaction_ref}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Amount:</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;">₦{amount:,.2f}</td>
                </tr>
            </table>
            <p>You can now upload your certificate for AI-powered forensic verification.</p>
            <a href="{settings.FRONTEND_URL}/verify" style="display: inline-block; background: #1a73e8; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; margin-top: 10px;">
                Start Verification →
            </a>
        </div>
        <div style="padding: 15px; background: #f5f5f5; text-align: center; font-size: 12px; color: #666;">
            CertVerify — AI-Powered Forensic Certificate Verification
        </div>
    </body>
    </html>
    """
    return send_email(email, subject, html_body)


def send_verification_report(
    email: str,
    transaction_ref: str,
    cert_type: str,
    final_verdict: str,
    final_trust_score: float,
    document_score: float,
) -> bool:
    """Send verification result summary email."""
    verdict_colors = {
        "AUTHENTIC": "#4CAF50",
        "SUSPICIOUS": "#FF9800",
        "HIGH_RISK": "#F44336",
    }
    verdict_color = verdict_colors.get(final_verdict, "#666")

    subject = f"Verification Complete — {final_verdict} | CertVerify"
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: #1a73e8; color: white; padding: 20px; text-align: center;">
            <h1>Verification Report 📋</h1>
        </div>
        <div style="padding: 20px;">
            <p>Your {cert_type} certificate verification is complete.</p>
            <div style="background: {verdict_color}; color: white; padding: 15px; border-radius: 8px; text-align: center; margin: 20px 0;">
                <h2 style="margin: 0;">{final_verdict}</h2>
                <p style="margin: 5px 0 0 0;">Trust Score: {final_trust_score:.1f}/100</p>
            </div>
            <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Transaction Ref:</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;">{transaction_ref}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Certificate Type:</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;">{cert_type}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Document Score:</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;">{document_score:.1f}/100</td>
                </tr>
            </table>
            <a href="{settings.FRONTEND_URL}/report/{transaction_ref}" style="display: inline-block; background: #1a73e8; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; margin-top: 10px;">
                View Full Report →
            </a>
        </div>
        <div style="padding: 15px; background: #f5f5f5; text-align: center; font-size: 12px; color: #666;">
            CertVerify — AI-Powered Forensic Certificate Verification
        </div>
    </body>
    </html>
    """
    return send_email(email, subject, html_body)


def send_b2b_credit_alert(
    email: str,
    api_key: str,
    credits_remaining: int,
) -> bool:
    """Send low-credit warning email to B2B API key owner."""
    masked_key = api_key[:8] + "..." + api_key[-4:]
    subject = "⚠️ Low Credit Alert — CertVerify B2B"
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: #FF9800; color: white; padding: 20px; text-align: center;">
            <h1>Low Credit Warning ⚠️</h1>
        </div>
        <div style="padding: 20px;">
            <p>Your B2B API key is running low on credits.</p>
            <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>API Key:</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;"><code>{masked_key}</code></td>
                </tr>
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Credits Remaining:</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #eee; color: #FF9800; font-weight: bold;">{credits_remaining}</td>
                </tr>
            </table>
            <p>Top up your credits to continue using the verification API without interruption.</p>
            <a href="{settings.FRONTEND_URL}/b2b/credits" style="display: inline-block; background: #1a73e8; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; margin-top: 10px;">
                Top Up Credits →
            </a>
        </div>
        <div style="padding: 15px; background: #f5f5f5; text-align: center; font-size: 12px; color: #666;">
            CertVerify — AI-Powered Forensic Certificate Verification
        </div>
    </body>
    </html>
    """
    return send_email(email, subject, html_body)


def send_api_key_generated(email: str, api_key: str, name: str) -> bool:
    """Send API key creation confirmation email."""
    subject = "Your API Key is Ready — CertVerify B2B"
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: #1a73e8; color: white; padding: 20px; text-align: center;">
            <h1>API Key Generated 🔑</h1>
        </div>
        <div style="padding: 20px;">
            <p>Your new B2B API key "<strong>{name}</strong>" has been created.</p>
            <div style="background: #f5f5f5; padding: 15px; border-radius: 4px; margin: 20px 0; font-family: monospace; word-break: break-all;">
                {api_key}
            </div>
            <p style="color: #F44336;"><strong>⚠️ Store this key securely. It will not be shown again in full.</strong></p>
            <p>Use this key in the <code>X-API-Key</code> header when making verification requests.</p>
        </div>
        <div style="padding: 15px; background: #f5f5f5; text-align: center; font-size: 12px; color: #666;">
            CertVerify — AI-Powered Forensic Certificate Verification
        </div>
    </body>
    </html>
    """
    return send_email(email, subject, html_body)
