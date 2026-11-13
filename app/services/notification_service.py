"""
SmartSpend AI — Notification Dispatcher Service
Sends budget alerts via:
  1. In-app notifications (DB)
  2. Email (Gmail SMTP)
  3. WhatsApp (Twilio)
"""
import smtplib
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from flask import current_app


# ─────────────────────────────────────────────────────────────
# EMAIL TEMPLATES
# ─────────────────────────────────────────────────────────────

def _build_email_html(user_name, alert_type, category, spent, limit, percentage):
    """Generate a beautiful HTML email for budget alerts."""
    if alert_type == "over budget":
        color = "#ef4444"
        emoji = "🚨"
        heading = "Budget Exceeded!"
        sub = f"You have gone over your {category} budget this month."
    elif alert_type == "near limit":
        color = "#f97316"
        emoji = "⚠️"
        heading = "Budget Warning — 80% Used"
        sub = f"You are close to your {category} spending limit."
    else:  # halfway
        color = "#3b82f6"
        emoji = "📊"
        heading = "Budget Halfway Point"
        sub = f"You have used half of your {category} budget."

    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#0d1117;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#0d1117;padding:30px 0;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0"
             style="background:#161b22;border-radius:12px;overflow:hidden;border:1px solid #30363d;">
        <!-- Header -->
        <tr>
          <td style="background:{color};padding:30px;text-align:center;">
            <div style="font-size:48px;">{emoji}</div>
            <h1 style="color:#fff;margin:10px 0 5px;font-size:24px;">{heading}</h1>
            <p style="color:rgba(255,255,255,0.85);margin:0;font-size:14px;">{sub}</p>
          </td>
        </tr>
        <!-- Body -->
        <tr>
          <td style="padding:30px;">
            <p style="color:#8b949e;font-size:16px;margin:0 0 20px;">
              Hi <strong style="color:#e6edf3;">{user_name}</strong>,
            </p>
            <!-- Stats Card -->
            <table width="100%" style="background:#0d1117;border-radius:8px;padding:20px;margin-bottom:24px;">
              <tr>
                <td style="text-align:center;padding:10px;">
                  <div style="color:#8b949e;font-size:12px;text-transform:uppercase;letter-spacing:1px;">Category</div>
                  <div style="color:#e6edf3;font-size:22px;font-weight:bold;margin-top:4px;">📂 {category}</div>
                </td>
              </tr>
              <tr>
                <td>
                  <table width="100%">
                    <tr>
                      <td style="text-align:center;padding:12px;background:#161b22;border-radius:6px;margin:4px;">
                        <div style="color:#8b949e;font-size:11px;">SPENT</div>
                        <div style="color:#ef4444;font-size:20px;font-weight:bold;">₹{spent:,.0f}</div>
                      </td>
                      <td width="10"></td>
                      <td style="text-align:center;padding:12px;background:#161b22;border-radius:6px;">
                        <div style="color:#8b949e;font-size:11px;">LIMIT</div>
                        <div style="color:#10b981;font-size:20px;font-weight:bold;">₹{limit:,.0f}</div>
                      </td>
                      <td width="10"></td>
                      <td style="text-align:center;padding:12px;background:#161b22;border-radius:6px;">
                        <div style="color:#8b949e;font-size:11px;">USED</div>
                        <div style="color:{color};font-size:20px;font-weight:bold;">{percentage:.0f}%</div>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>
            </table>
            <!-- Progress Bar -->
            <div style="background:#21262d;border-radius:4px;height:10px;overflow:hidden;margin-bottom:24px;">
              <div style="background:{color};width:{min(percentage, 100):.0f}%;height:100%;border-radius:4px;"></div>
            </div>
            <!-- CTA -->
            <div style="text-align:center;">
              <a href="http://localhost:5173/budgets"
                 style="background:#10b981;color:#fff;padding:12px 32px;border-radius:8px;
                        text-decoration:none;font-weight:bold;font-size:15px;display:inline-block;">
                View Budget Dashboard →
              </a>
            </div>
          </td>
        </tr>
        <!-- Footer -->
        <tr>
          <td style="padding:16px 30px;border-top:1px solid #21262d;text-align:center;">
            <p style="color:#484f58;font-size:12px;margin:0;">
              SmartSpend AI • Personal Finance Dashboard<br>
              To stop email alerts, update your <a href="http://localhost:5173/profile"
              style="color:#10b981;">notification settings</a>.
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>
"""


def _build_whatsapp_message(user_name, alert_type, category, spent, limit, percentage):
    """Build WhatsApp text message for budget alert."""
    if alert_type == "over budget":
        emoji = "🚨"
        status = "EXCEEDED"
    elif alert_type == "near limit":
        emoji = "⚠️"
        status = "WARNING (80%)"
    else:
        emoji = "📊"
        status = "HALFWAY (50%)"

    return (
        f"{emoji} *SmartSpend AI — Budget Alert*\n\n"
        f"Hi *{user_name}*!\n\n"
        f"*Category:* {category}\n"
        f"*Status:* {status}\n"
        f"*Spent:* ₹{spent:,.0f}\n"
        f"*Monthly Limit:* ₹{limit:,.0f}\n"
        f"*Used:* {percentage:.0f}%\n\n"
        f"{'🔴 You have exceeded your budget!' if alert_type == 'over budget' else '💡 Tip: Review your spending to stay on track.'}\n\n"
        f"_SmartSpend AI — http://localhost:5173/budgets_"
    )


# ─────────────────────────────────────────────────────────────
# EMAIL SENDER
# ─────────────────────────────────────────────────────────────

def send_email_alert(to_email, user_name, alert_type, category, spent, limit, percentage):
    """Send budget alert email via Gmail SMTP (runs in background thread)."""
    def _send():
        try:
            smtp_host = current_app.config.get("MAIL_SERVER", "smtp.gmail.com")
            smtp_port = int(current_app.config.get("MAIL_PORT", 587))
            username = current_app.config.get("MAIL_USERNAME", "")
            password = current_app.config.get("MAIL_PASSWORD", "")

            if not username or not password:
                current_app.logger.warning("Email not configured: MAIL_USERNAME/MAIL_PASSWORD missing")
                return

            subject_map = {
                "over budget": f"🚨 Budget Exceeded: {category}",
                "near limit":  f"⚠️ Budget Warning (80%): {category}",
                "halfway":     f"📊 Budget Halfway: {category}",
            }
            subject = subject_map.get(alert_type, f"SmartSpend Alert: {category}")

            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"]    = f"SmartSpend AI <{username}>"
            msg["To"]      = to_email

            html_body = _build_email_html(user_name, alert_type, category, spent, limit, percentage)
            msg.attach(MIMEText(html_body, "html"))

            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.ehlo()
                server.starttls()
                server.login(username, password)
                server.sendmail(username, to_email, msg.as_string())

            current_app.logger.info(f"Budget alert email sent to {to_email}")

        except Exception as e:
            current_app.logger.error(f"Email send failed: {e}")

    # Run in background so it doesn't block the API response
    app = current_app._get_current_object()
    t = threading.Thread(target=lambda: _send_with_ctx(app, _send))
    t.daemon = True
    t.start()


def _send_with_ctx(app, fn):
    with app.app_context():
        fn()


# ─────────────────────────────────────────────────────────────
# WHATSAPP SENDER (Twilio)
# ─────────────────────────────────────────────────────────────

def send_whatsapp_alert(to_number, user_name, alert_type, category, spent, limit, percentage):
    """Send budget alert via Twilio WhatsApp (runs in background thread)."""
    def _send():
        try:
            from twilio.rest import Client

            account_sid = current_app.config.get("TWILIO_ACCOUNT_SID", "")
            auth_token  = current_app.config.get("TWILIO_AUTH_TOKEN", "")
            from_number = current_app.config.get("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")  # Twilio sandbox

            if not account_sid or not auth_token:
                current_app.logger.warning("WhatsApp not configured: TWILIO credentials missing")
                return

            # Ensure E.164 + whatsapp: prefix
            if not to_number.startswith("+"):
                to_number = "+91" + to_number.lstrip("0")
            to_wa = f"whatsapp:{to_number}"

            message_body = _build_whatsapp_message(user_name, alert_type, category, spent, limit, percentage)

            client = Client(account_sid, auth_token)
            msg = client.messages.create(
                body=message_body,
                from_=from_number,
                to=to_wa,
            )
            current_app.logger.info(f"WhatsApp alert sent to {to_number}: {msg.sid}")

        except ImportError:
            current_app.logger.error("Twilio not installed. Run: pip install twilio")
        except Exception as e:
            current_app.logger.error(f"WhatsApp send failed: {e}")

    app = current_app._get_current_object()
    t = threading.Thread(target=lambda: _send_with_ctx(app, _send))
    t.daemon = True
    t.start()


# ─────────────────────────────────────────────────────────────
# UNIFIED DISPATCHER
# ─────────────────────────────────────────────────────────────

def dispatch_budget_alert(user, alert_type, category, spent, limit, percentage):
    """
    Dispatch budget alert through all configured channels.
    Called from budget_service.check_and_notify_budget()

    Args:
        user: User model instance
        alert_type: 'over budget' | 'near limit' | 'halfway'
        category: category name string
        spent: float — amount spent
        limit: float — monthly limit
        percentage: float — percentage used
    """
    if getattr(user, "notify_email", True):
        send_email_alert(
            to_email=user.email,
            user_name=user.full_name,
            alert_type=alert_type,
            category=category,
            spent=spent,
            limit=limit,
            percentage=percentage,
        )

    whatsapp_num = getattr(user, "whatsapp_number", None)
    if getattr(user, "notify_whatsapp", False) and whatsapp_num:
        send_whatsapp_alert(
            to_number=whatsapp_num,
            user_name=user.full_name,
            alert_type=alert_type,
            category=category,
            spent=spent,
            limit=limit,
            percentage=percentage,
        )
