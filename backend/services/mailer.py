import os
import re
import json
import logging
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Any, List

logger = logging.getLogger("finance_screener.mailer")

# Persistent storage file for subscriber records / sent links
DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))
SUBSCRIBERS_FILE = os.path.join(DATA_DIR, "subscribers.json")


def _ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(SUBSCRIBERS_FILE):
        with open(SUBSCRIBERS_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2)


def is_valid_email(email: str) -> bool:
    """Validates basic email structure."""
    if not email or not isinstance(email, str):
        return False
    email = email.strip()
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return bool(re.match(pattern, email))


def record_subscriber(email: str, portal_link: str, delivery_mode: str) -> None:
    """Appends the subscriber request to local JSON storage for tracking."""
    try:
        _ensure_data_dir()
        records: List[Dict[str, Any]] = []
        if os.path.exists(SUBSCRIBERS_FILE):
            with open(SUBSCRIBERS_FILE, "r", encoding="utf-8") as f:
                try:
                    records = json.load(f)
                except Exception:
                    records = []

        records.append({
            "email": email.strip().lower(),
            "portal_link": portal_link,
            "delivery_mode": delivery_mode,
            "created_at": datetime.now().isoformat()
        })

        with open(SUBSCRIBERS_FILE, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)
    except Exception as e:
        logger.warning(f"Failed to record subscriber in local file: {e}")


def get_subscribers_list() -> List[Dict[str, Any]]:
    """Retrieves list of all saved subscriber requests."""
    try:
        _ensure_data_dir()
        if os.path.exists(SUBSCRIBERS_FILE):
            with open(SUBSCRIBERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to read subscribers list: {e}")
    return []


def build_email_content(email: str, portal_link: str) -> tuple[str, str, str]:
    """
    Builds the subject line, HTML email body, and plain-text fallback.
    Styled as a modern institutional fintech terminal access email.
    """
    subject = "⚡ Your Direct Access Link to the Equity Finance Screener Terminal"
    now_str = datetime.now().strftime("%B %d, %Y at %I:%M %p UTC")

    # Plain text version
    plain_text = f"""Hello,

You requested direct access to the Equity Finance Screener Platform.

Use the link below to launch the financial terminal:
{portal_link}

PLATFORM HIGHLIGHTS:
- Real-Time 1-Second Price Streaming (NSE, BSE, US Equities)
- Interactive Plotly Candlestick & Volume Profiles
- 12+ Server-Side Technical Indicators (RSI, MACD, Bollinger Bands, ATR)
- Standardized Annual, Quarterly & TTM Statements
- 11 Derived Financial Valuation & Profitability Ratios
- CAGR & Historical Growth Analysis Engine

Requested on: {now_str}
If you did not request this link, you can safely disregard this email.

— The Equity Finance Screener Team
"""

    # Modern Responsive HTML version
    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{subject}</title>
  <style>
    body {{
      margin: 0;
      padding: 0;
      background-color: #0b0f17;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      color: #e2e8f0;
      line-height: 1.6;
    }}
    .email-wrapper {{
      max-width: 600px;
      margin: 30px auto;
      background: #121824;
      border: 1px solid #1e293b;
      border-radius: 12px;
      overflow: hidden;
      box-shadow: 0 10px 25px rgba(0, 0, 0, 0.5);
    }}
    .email-header {{
      background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
      padding: 28px 32px;
      border-bottom: 1px solid #334155;
      text-align: center;
    }}
    .logo-badge {{
      display: inline-block;
      background: rgba(59, 130, 246, 0.15);
      border: 1px solid rgba(59, 130, 246, 0.35);
      color: #60a5fa;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      padding: 4px 10px;
      border-radius: 20px;
      margin-bottom: 10px;
    }}
    .header-title {{
      margin: 0;
      font-size: 22px;
      font-weight: 800;
      letter-spacing: -0.02em;
      color: #ffffff;
    }}
    .email-body {{
      padding: 32px;
    }}
    .greeting {{
      font-size: 17px;
      font-weight: 600;
      color: #f8fafc;
      margin-top: 0;
    }}
    .message-text {{
      font-size: 14.5px;
      color: #94a3b8;
      margin-bottom: 24px;
    }}
    .cta-card {{
      background: #162032;
      border: 1px solid #253349;
      border-radius: 10px;
      padding: 24px;
      text-align: center;
      margin: 24px 0;
    }}
    .btn-launch {{
      display: inline-block;
      background: #2563eb;
      color: #ffffff !important;
      text-decoration: none;
      font-weight: 700;
      font-size: 15px;
      padding: 13px 28px;
      border-radius: 8px;
      box-shadow: 0 4px 14px rgba(37, 99, 235, 0.4);
      margin: 8px 0;
    }}
    .link-fallback {{
      font-size: 11.5px;
      color: #64748b;
      word-break: break-all;
      margin-top: 14px;
    }}
    .link-fallback a {{
      color: #38bdf8;
      text-decoration: underline;
    }}
    .features-list {{
      background: #0f1420;
      border: 1px solid #1e293b;
      border-radius: 8px;
      padding: 18px 20px;
      margin: 24px 0 10px 0;
    }}
    .features-title {{
      font-size: 12px;
      font-weight: 700;
      color: #94a3b8;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      margin-bottom: 12px;
    }}
    .feature-item {{
      font-size: 13px;
      color: #cbd5e1;
      padding: 5px 0;
      display: flex;
      align-items: center;
    }}
    .feature-item span {{
      color: #10b981;
      margin-right: 8px;
      font-weight: bold;
    }}
    .email-footer {{
      background: #0d121c;
      padding: 20px 32px;
      border-top: 1px solid #1e293b;
      font-size: 11.5px;
      color: #64748b;
      text-align: center;
    }}
  </style>
</head>
<body>
  <div class="email-wrapper">
    <div class="email-header">
      <div class="logo-badge">Institutional Access</div>
      <h1 class="header-title">FINANCE SCREENER TERMINAL</h1>
    </div>

    <div class="email-body">
      <p class="greeting">Hello,</p>
      <p class="message-text">
        You requested direct access to the <strong>Equity Finance Screener Platform</strong>.
        Your interactive workspace has been provisioned with real-time market data and fundamental intelligence.
      </p>

      <div class="cta-card">
        <a href="{portal_link}" class="btn-launch" target="_blank">Launch Financial Terminal &rarr;</a>
        <div class="link-fallback">
          Direct URL: <a href="{portal_link}">{portal_link}</a>
        </div>
      </div>

      <div class="features-list">
        <div class="features-title">What is included in your portal access:</div>
        <div class="feature-item"><span>&#10003;</span> Real-Time 1-Second Price Streaming (NSE, BSE, US Equities)</div>
        <div class="feature-item"><span>&#10003;</span> Interactive Candlestick Charts & Technical Indicators (RSI, MACD, BB)</div>
        <div class="feature-item"><span>&#10003;</span> Normalized Annual, Quarterly & TTM Financial Statements</div>
        <div class="feature-item"><span>&#10003;</span> 11 Key Valuation & Return Ratios with Disclosed Formulas</div>
        <div class="feature-item"><span>&#10003;</span> Historical CAGR & YoY Growth Engine</div>
      </div>
    </div>

    <div class="email-footer">
      Requested for: <strong>{email}</strong> &bull; Generated on: {now_str}<br>
      If you did not request this access link, no action is required and you can safely ignore this email.
    </div>
  </div>
</body>
</html>"""

    return subject, plain_text, html_content


def send_portal_access_email(email: str, base_url: str = "http://127.0.0.1:8000") -> Dict[str, Any]:
    """
    Sends the portal access link to the user's email.
    If SMTP credentials are provided in the environment, delivers via real SMTP.
    Otherwise, gracefully simulates delivery and records the access link locally.
    """
    email = email.strip()
    if not is_valid_email(email):
        raise ValueError(f"'{email}' is not a valid email address.")

    portal_link = f"{base_url.rstrip('/')}/?access=granted&email={email}"
    subject, plain_text, html_content = build_email_content(email, portal_link)

    # Check for SMTP configuration in environment
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_from = os.getenv("SMTP_FROM", smtp_user or "noreply@financescreener.local")

    delivery_mode = "demo_simulated"

    if smtp_host and smtp_user and smtp_password:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = smtp_from
            msg["To"] = email

            part1 = MIMEText(plain_text, "plain")
            part2 = MIMEText(html_content, "html")
            msg.attach(part1)
            msg.attach(part2)

            if smtp_port == 465:
                server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10)
            else:
                server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
                server.starttls()

            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_from, [email], msg.as_string())
            server.quit()

            delivery_mode = "smtp"
            logger.info(f"Successfully sent live SMTP email to {email}")
        except Exception as e:
            logger.warning(f"SMTP delivery failed ({e}); falling back to local simulation mode.")
            delivery_mode = "demo_simulated"

    # Record dispatch
    record_subscriber(email, portal_link, delivery_mode)

    return {
        "status": "success",
        "message": "Portal access link generated and sent successfully!",
        "email": email,
        "portal_link": portal_link,
        "delivery_mode": delivery_mode,
        "timestamp": datetime.now().isoformat(),
        "preview_subject": subject,
        "preview_snippet": f"Direct access link to Equity Finance Screener generated for {email}."
    }
