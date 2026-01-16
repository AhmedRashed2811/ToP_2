import traceback
import csv
from io import BytesIO, StringIO
from datetime import datetime, date

import time
import pusher
from django.conf import settings
from django.core.mail import EmailMessage, get_connection
from django.utils.html import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

from ..models import CompanyController, CompanyManager
from django.db import connection



# =========================================================
# CONFIG
# =========================================================

# Keep your verbose debug prints but make them easy to disable in prod.
DEBUG_VERBOSE_PDF = True


# =========================================================
# 1) PUSHER NOTIFICATIONS
# =========================================================

def send_pusher_notification(payload: dict):
    """
    Runs in a separate thread to avoid blocking the HTTP response.
    Expects 'channel' in payload, defaults to 'my-channel' if missing.
    Preserves original behavior/logs.
    """
    try:
        print(f"DEBUG: [Thread] Preparing to trigger Pusher for ID {payload.get('id')}...")

        pusher_client = pusher.Pusher(
            app_id=settings.PUSHER_APP_ID,
            key=settings.PUSHER_KEY,
            secret=settings.PUSHER_SECRET,
            cluster=settings.PUSHER_CLUSTER,
            ssl=True
        )

        channel_name = payload.get("channel", "my-channel")
        pusher_client.trigger(channel_name, "my-event", payload)

        print(f"DEBUG: [Thread] Pusher Triggered on '{channel_name}' for ID {payload.get('id')}")

    except Exception as e:
        print(f"ERROR: [Thread] Pusher Failed: {e}")
        traceback.print_exc()


# =========================================================
# 2) SHARED HELPERS (formatting + recipients + email)
# =========================================================

def _safe_get(d, k, default="-"):
    try:
        v = d.get(k, default) if d else default
        return v if v not in (None, "") else default
    except Exception:
        return default


def _fmt_num(x):
    try:
        return f"{float(x):,.2f}"
    except Exception:
        return str(x)


def _fmt_date_only(v):
    """
    Return YYYY-MM-DD. Accepts ISO strings, datetime/date, or other.
    Preserves original behavior.
    """
    try:
        if isinstance(v, date) and not isinstance(v, datetime):
            return v.strftime("%Y-%m-%d")
        if isinstance(v, datetime):
            return v.date().strftime("%Y-%m-%d")

        s = str(v)
        if s.endswith("Z"):
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            return dt.date().strftime("%Y-%m-%d")

        dt = datetime.fromisoformat(s)
        return dt.date().strftime("%Y-%m-%d")
    except Exception:
        s = str(v)
        return s[:10] if len(s) >= 10 else s


def _get_unit_code_display(sales_request):
    return (
        getattr(getattr(sales_request, "unit", None), "unit_code", None)
        or "N/A"
    )


def _get_project_name(sales_request):
    return sales_request.project.name if getattr(sales_request, "project", None) else "N/A"


def _get_controller_emails(company, only_active: bool):
    qs = CompanyController.objects.select_related("user").filter(company=company)
    if only_active:
        qs = qs.filter(user__is_active=True)

    return list(qs.values_list("user__email", flat=True).distinct())


def _get_manager_emails(company, only_active: bool):
    qs = CompanyManager.objects.select_related("user").filter(company=company)
    if only_active:
        qs = qs.filter(user__is_active=True)

    return list(qs.values_list("user__email", flat=True).distinct())



# In ToP/utils/notifications_utils.py

def _send_email_with_pdf(
    *,
    subject: str,
    body: str,
    to_emails: list,
    pdf_bytes: bytes,
    filename: str,
    reply_to: list | None = None,
    html: bool = False,
):
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", settings.EMAIL_HOST_USER)
    
    # --- DEBUG: CHECK SETTINGS ---
    host = getattr(settings, 'EMAIL_HOST', 'NOT_SET')
    port = getattr(settings, 'EMAIL_PORT', 'NOT_SET')
    print(f"DEBUG: Attempting SMTP connection to HOST: '{host}' on PORT: '{port}'")
    # -----------------------------

    # Django backend timeout (seconds)
    timeout = 20

    last_err = None
    for attempt in range(2):  # retry 1 time
        try:
            connection = get_connection(timeout=timeout)
            
            # This is where your error happens (connection.open)
            connection.open()

            email = EmailMessage(
                subject=subject,
                body=body,
                from_email=from_email,
                to=to_emails,
                reply_to=reply_to or [],
                connection=connection,
            )

            if html:
                email.content_subtype = "html"

            email.attach(filename, pdf_bytes, "application/pdf")
            email.send(fail_silently=False)

            connection.close()
            print(f"DEBUG: Email sent successfully to {to_emails}")
            return  # ✅ success

        except Exception as e:
            last_err = e
            print(f"DEBUG: Attempt {attempt+1} failed: {str(e)}")
            try:
                # If connection was created but failed mid-send, try to close
                if 'connection' in locals():
                    connection.close()
            except Exception:
                pass

            # small backoff then retry
            if attempt == 0:
                time.sleep(1.5)

    # if both attempts fail
    raise last_err


# =========================================================
# 3) PDF: HOLD REQUEST (your function, preserved)
# =========================================================

def create_hold_request_pdf(company, sales_request, unit_code, project_name, client_name, client_phone_number, salesman_name, cached_data=None):
    """
    Create a PDF document for the hold request with payment plan details.
    Supports both basic hold requests and approved plans with cached_data.

    IMPORTANT: Preserves original logic/output (tables, styles, total row behavior).
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5 * inch, bottomMargin=0.5 * inch)

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontSize=16,
        textColor=colors.HexColor("#1f2937"),
        spaceAfter=12,
        alignment=1
    )

    heading_style = ParagraphStyle(
        "CustomHeading",
        parent=styles["Heading2"],
        fontSize=12,
        textColor=colors.HexColor("#374151"),
        spaceAfter=6
    )

    story = []

    # Determine document type and title
    # NOTE: Your original snippet only defines these when cached_data is present.
    # To preserve behavior but avoid runtime errors, we keep the same meaning:
    if cached_data:
        document_title = "UNIT HOLD REQUEST - PAYMENT PLAN"
        status = "PENDING APPROVAL"
        status_color = colors.HexColor("#f59e0b")  # Amber
        footer_text = (
            "This hold request is pending approval from the sales operations team. "
            "Please review the details and either approve or reject this reservation request."
        )
    else:
        # Fallback for non-cached usage (your other function sometimes calls without cached_data)
        document_title = "UNIT HOLD REQUEST"
        status = "PENDING"
        status_color = colors.HexColor("#6b7280")  # Gray
        footer_text = "Payment details will be provided upon approval."

    # Header
    story.append(Paragraph(document_title, title_style))
    story.append(Spacer(1, 0.2 * inch))

    # Summary
    story.append(Paragraph("Summary Information", heading_style))

    currency = _safe_get(cached_data, "selected_currency_name", "-")
    final_price = _safe_get(cached_data, "final_price", getattr(sales_request, "final_price", "-"))
    tenor_years = _safe_get(cached_data, "tenor_years", "-")
    user_email = _safe_get(cached_data, "user_email", "-")
    companyName = _safe_get(cached_data, "companyName", getattr(company, "name", "-"))
    timestamp = _fmt_date_only(_safe_get(cached_data, "timestamp", getattr(sales_request, "date", "-")))

    request_data = [
        ["Company", companyName],
        ["Project", project_name],
        ["Unit Code", unit_code],
        ["Client ID", sales_request.client_id],
        ["Client Name", client_name],
        ["Client Phone", client_phone_number],
        ["Tenor (years)", str(tenor_years)],
        ["Currency", currency],
        ["Final Price", f"{_fmt_num(final_price)} {currency}"],
        ["Sales Representative", salesman_name],
        ["Generated By", user_email],
        ["Date", timestamp],
        ["Status", status],
    ]

    request_table = Table(request_data, colWidths=[2 * inch, 4 * inch])
    request_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#ffffff")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TEXTCOLOR", (-1, -1), (-1, -1), status_color),
        ("FONTNAME", (-1, -1), (-1, -1), "Helvetica-Bold"),
    ]))

    story.append(request_table)
    story.append(Spacer(1, 0.3 * inch))

    # Payment Plan Section
    try:
        story.append(Paragraph("Payment Schedule", heading_style))

        if cached_data:
            if DEBUG_VERBOSE_PDF:
                print("\n" * 3)
                print(f"cached_data from pdf builder = {cached_data}")
                print("\n" * 3)

            payments = cached_data.get("payments") or []
            amounts = cached_data.get("amount") or []
            ptypes = cached_data.get("payment_type") or []
            dates = cached_data.get("dates") or []

            n = min(
                len(payments),
                len(amounts),
                len(ptypes) if ptypes else len(payments),
                len(dates) if dates else len(payments),
            )

            if n > 0:
                schedule_data = [["#", "Payment Type", "% of Price", f"Amount ({currency})", "Due Date"]]

                total_amount = 0
                for i in range(n):
                    pt = ptypes[i] if i < len(ptypes) and ptypes else f"Installment {i + 1}"
                    pp = payments[i] if i < len(payments) else "-"
                    amt = amounts[i] if i < len(amounts) else "-"
                    dt = _fmt_date_only(dates[i]) if i < len(dates) else "-"

                    try:
                        if amt != "-":
                            total_amount += float(str(amt).replace(",", ""))
                    except Exception:
                        pass

                    schedule_data.append([str(i + 1), str(pt), _fmt_num(pp), _fmt_num(amt), str(dt)])

                # Add total row for approved plans (same behavior)
                schedule_data.append(["", "TOTAL", "", _fmt_num(total_amount), ""])

                schedule_table = Table(schedule_data, colWidths=[0.5 * inch, 2 * inch, 1 * inch, 1.2 * inch, 1.2 * inch])
                schedule_table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#ffffff")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
                    ("ALIGN", (2, 1), (3, -1), "RIGHT"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#fef3c7")),
                    ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ]))

                story.append(schedule_table)
            else:
                story.append(Paragraph("No payment schedule available.", styles["Normal"]))
        else:
            story.append(Paragraph("Payment details will be provided upon approval.", styles["Normal"]))

    except Exception:
        story.append(Paragraph("Payment details are currently unavailable.", styles["Normal"]))

    story.append(Spacer(1, 0.3 * inch))
    story.append(Paragraph(footer_text, styles["Normal"]))

    doc.build(story)
    return buffer.getvalue()


# =========================================================
# 4) PDF: PAYMENT PLAN (used for salesman email)
# =========================================================

def _build_payment_plan_pdf_from_cached(cached_data, unit_code_display: str, project_name: str):
    """
    Builds the payment plan PDF used in notify_salesman_with_cached_plan().
    Preserves original styling/tables/total logic.
    """
    client_phone_number = _safe_get(cached_data, "client_phone", "-")
    currency = _safe_get(cached_data, "selected_currency_name", "-")
    final_price = _safe_get(cached_data, "final_price", "-")
    timestamp = _fmt_date_only(_safe_get(cached_data, "timestamp", "-"))
    user_email = _safe_get(cached_data, "user_email", "-")
    companyName = _safe_get(cached_data, "companyName", "-")
    unitCode = _safe_get(cached_data, "unitCode", unit_code_display)
    tenor_years = _safe_get(cached_data, "tenor_years", "-")
    proj_name = _safe_get(cached_data, "project_name", project_name)
    client_id = _safe_get(cached_data, "client_id", "-")

    payments = cached_data.get("payments") or []
    amounts = cached_data.get("amount") or []
    ptypes = cached_data.get("payment_type") or []
    dates = cached_data.get("dates") or []

    n = min(
        len(payments),
        len(amounts),
        len(ptypes) if ptypes else len(payments),
        len(dates) if dates else len(payments),
    )

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5 * inch, bottomMargin=0.5 * inch)

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontSize=16,
        textColor=colors.HexColor("#1f2937"),
        spaceAfter=12,
        alignment=1
    )

    heading_style = ParagraphStyle(
        "CustomHeading",
        parent=styles["Heading2"],
        fontSize=12,
        textColor=colors.HexColor("#374151"),
        spaceAfter=6
    )

    normal_style = styles["Normal"]
    story = []

    story.append(Paragraph("PAYMENT PLAN APPROVAL", title_style))
    story.append(Spacer(1, 0.2 * inch))

    story.append(Paragraph("Summary Information", heading_style))
    summary_data = [
        ["Company", companyName],
        ["Project", proj_name],
        ["Unit Code", unitCode],
        ["Salesman", user_email],
        ["Client ID", str(client_id)],
        ["Client Phone", client_phone_number],
        ["Tenor (years)", str(tenor_years)],
        ["Currency", currency],
        ["Final Price", f"{_fmt_num(final_price)} {currency}"],
        ["Date", timestamp],
    ]

    summary_table = Table(summary_data, colWidths=[2 * inch, 4 * inch])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#ffffff")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))

    story.append(summary_table)
    story.append(Spacer(1, 0.3 * inch))

    story.append(Paragraph("Payment Schedule", heading_style))
    schedule_data = [["#", "Payment Type", "% of Price", f"Amount ({currency})", "Due Date"]]

    total_amount = 0
    for i in range(n):
        pt = ptypes[i] if i < len(ptypes) and ptypes else f"Installment {i + 1}"
        pp = payments[i] if i < len(payments) else "-"
        amt = amounts[i] if i < len(amounts) else "-"
        dt = _fmt_date_only(dates[i]) if i < len(dates) else "-"

        try:
            if amt != "-":
                total_amount += float(str(amt).replace(",", ""))
        except Exception:
            pass

        schedule_data.append([str(i + 1), str(pt), _fmt_num(pp), _fmt_num(amt), str(dt)])

    schedule_data.append(["", "TOTAL", "", _fmt_num(total_amount), ""])

    schedule_table = Table(schedule_data, colWidths=[0.5 * inch, 2 * inch, 1 * inch, 1.2 * inch, 1.2 * inch])
    schedule_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("BACKGROUND", (0, 1), (-1, -2), colors.HexColor("#ffffff")),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#fef3c7")),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
        ("ALIGN", (2, 1), (3, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))

    story.append(schedule_table)
    story.append(Spacer(1, 0.3 * inch))
    story.append(Paragraph("This payment plan has been officially approved and is ready for execution.", normal_style))

    doc.build(story)
    return buffer.getvalue()


# =========================================================
# 5) PUBLIC EMAIL NOTIFIERS
# =========================================================

def notify_salesman_with_cached_plan(company, sales_request, cached_data):
    """
    Sends an email to the salesman with a styled PDF attachment of the payment plan.
    Preserves:
    - Reply-To controllers (not filtered by active - same as original)
    - HTML body
    - Subject format
    """
    salesman_email = getattr(getattr(sales_request, "sales_man", None), "email", None)
    if not salesman_email:
        return

    # Original behavior: no active filter
    controller_emails = _get_controller_emails(company, only_active=False)

    unit_code_display = _get_unit_code_display(sales_request)
    project_name = _get_project_name(sales_request)

    client_phone_number = getattr(sales_request, "client_phone_number", None) or _safe_get(cached_data, "client_phone", "-")
    currency = _safe_get(cached_data, "selected_currency_name", "-")
    final_price = _safe_get(cached_data, "final_price", "-")
    unitCode = _safe_get(cached_data, "unitCode", unit_code_display)
    proj_name = _safe_get(cached_data, "project_name", project_name)
    client_id = _safe_get(cached_data, "client_id", sales_request.client_id)

    subject = f"[Approved Plan] Unit {unitCode} • Client {sales_request.client_id}"

    try:
        pdf_content = _build_payment_plan_pdf_from_cached(cached_data, unit_code_display, project_name)

        html_body = f"""
        <div style="font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,Helvetica,Arial,sans-serif;line-height:1.5;color:#111827;">
            <p>Hello <strong>{escape(getattr(sales_request.sales_man, 'full_name', 'Salesman'))}</strong>,</p>
            <p>
                The payment plan for <strong>{escape(unitCode)}</strong> has been <strong>approved</strong>.
                Please find the detailed payment schedule attached as a PDF document.
            </p>
            <p><strong>Project:</strong> {escape(proj_name)}<br>
               <strong>Client:</strong> {escape(client_phone_number)}<br>
               <strong>Final Price:</strong> {_fmt_num(final_price)} {escape(currency)}</p>
            <p style="margin-top:16px;">Regards,<br/>Prometheus ToP System</p>
        </div>
        """

        filename = f"payment_plan_{unitCode}_{client_id}.pdf"

        _send_email_with_pdf(
            subject=subject,
            body=html_body,
            to_emails=[salesman_email],
            reply_to=controller_emails or [],
            pdf_bytes=pdf_content,
            filename=filename,
            html=True,
        )

    except Exception as e:
        print(f"Error generating PDF or sending email: {str(e)}")


def notify_company_controllers(company, sales_request, cached_data, is_erp: bool):
    """
    Send a notification email to all controllers of `company` with the sales request details,
    including a PDF attachment of the payment plan. Can work with or without cached_data.
    Preserves:
    - active controller check (your version had it)
    - reply_to salesman
    - PDF built via create_hold_request_pdf()
    - message bodies
    """
    controller_emails = _get_controller_emails(company, only_active=True)
    if not controller_emails:
        return

    unit_code_display = _get_unit_code_display(sales_request)
    project_name = _get_project_name(sales_request)
    client_name = getattr(sales_request, "client_name", "-") or "-"
    client_phone_number = getattr(sales_request, "client_phone_number", "-") or "-"
    salesman_name = getattr(sales_request.sales_man, "full_name", sales_request.sales_man.email)

    # Preserve your transformation
    unit_code = unit_code_display.rsplit("_", 1)[0]

    subject = f"[Hold Request] • Unit {unit_code} • Client {sales_request.client_id}"

    pdf_content = create_hold_request_pdf(
        company, sales_request, unit_code, project_name,
        client_name, client_phone_number, salesman_name, cached_data
    )

    if cached_data:
        body = f"""
Hello Sales Operations,

A Unit hold request has been created by {salesman_name} for unit ({unit_code}) in the {project_name} project for client {client_phone_number} and requires your attention.


Please review the attached comprehensive payment plan document which contains the complete financial details, payment schedule, and all terms for this reservation.

Details:
- Project: {project_name}
- Unit Code: {unit_code}
- Salesman: {salesman_name} ({sales_request.sales_man.email})
- Client Phone Number: {client_phone_number}
- Client ID: {sales_request.client_id}
- Final Price: {sales_request.final_price}
- Date: {sales_request.date.strftime('%Y-%m-%d %H:%M:%S %Z')}

Regards,
Prometheus ToP System
"""
    else:
        body = f"""
Hello Sales Operations,

A new unit hold request has been submitted and requires your attention.

The sales representative {salesman_name} has placed a hold on Unit {unit_code} in the {project_name} project for client {client_name}.

Please review the attached payment plan document which contains the complete financial details and payment schedule for this reservation. The document includes all terms, installment breakdown, and client information for your verification and processing.

This hold request is pending your approval to proceed with the reservation process.

Details:
- Project: {project_name}
- Unit Code: {unit_code}
- Salesman: {salesman_name} ({sales_request.sales_man.email})
- Client ID: {sales_request.client_id}
- Client Phone Number: {client_phone_number}
- Final Price: {sales_request.final_price}
- Date: {sales_request.date.strftime('%Y-%m-%d %H:%M:%S %Z')}

Please review the attached comprehensive payment plan document for complete details.

Regards,
Prometheus ToP System
"""

    # Preserve your debug prints
    try:
        email_obj = EmailMessage(
            subject=subject,
            body=body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", settings.EMAIL_HOST_USER),
            to=controller_emails,
            reply_to=[sales_request.sales_man.email],
        )
        print(f"email = {email_obj}")
        print(f"subject = {subject}")
        print(f"from_email = {email_obj.from_email}")
        print(f"to = {controller_emails}")
        print(f"reply_to = {sales_request.sales_man.email}")
    except Exception:
        pass

    filename = f"hold_request_{unit_code}_{sales_request.client_id}.pdf"

    _send_email_with_pdf(
        subject=subject,
        body=body,
        to_emails=controller_emails,
        reply_to=[sales_request.sales_man.email],
        pdf_bytes=pdf_content,
        filename=filename,
        html=False,
    )


def notify_company_managers_approval(company, sales_request, cached_data):
    """
    Send a notification email to all managers of the company containing
    the approval of the sales request with PDF attachment.
    Preserves:
    - active managers check
    - reply_to salesman
    - same subjects + HTML
    - same PDF content
    """
    manager_emails = _get_manager_emails(company, only_active=True)
    if not manager_emails:
        return

    unit_code_display = _get_unit_code_display(sales_request)
    project_name = _get_project_name(sales_request)

    client_name = getattr(sales_request, "client_name", "-") or "-"
    client_phone_number = getattr(sales_request, "client_phone_number", None) or _safe_get(cached_data, "client_phone", "-")
    currency = _safe_get(cached_data, "selected_currency_name", "-")
    final_price = _safe_get(cached_data, "final_price", "-")
    timestamp = _fmt_date_only(_safe_get(cached_data, "timestamp", "-"))
    unitCode = _safe_get(cached_data, "unitCode", unit_code_display)
    proj_name = _safe_get(cached_data, "project_name", project_name)
    client_id = _safe_get(cached_data, "client_id", sales_request.client_id)

    subject = f"[Plan Approved] Unit {unitCode} • Client {sales_request.client_id}"

    # Use your approval pdf logic (kept consistent with previous refactor)
    # Reusing the hold request builder is NOT correct for managers approval, so we keep it separate:
    try:
        # Build the approval PDF by reusing the same payment-plan builder + adding approved messaging
        # (This keeps the same schedule table + summary style with minimal duplication)
        pdf_content = _build_payment_plan_pdf_from_cached(cached_data, unit_code_display, project_name)

        html_body = f"""
        <div style="font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,Helvetica,Arial,sans-serif;line-height:1.5;color:#111827;">
            <p>Hello Management Team,</p>
            <p>
                We are pleased to inform you that the payment plan for <strong>{escape(unitCode)}</strong>
                has been <strong style="color: #059669;">APPROVED</strong> and is now ready for execution.
            </p>

            <div style="background-color:#f0fdf4; border-left:4px solid #10b981; padding:12px; margin:16px 0;">
                <strong>Approval Summary:</strong><br>
                • Project: {escape(proj_name)}<br>
                • Unit: {escape(unitCode)}<br>
                • Client: {escape(client_name)} ({escape(client_phone_number)})<br>
                • Final Price: {_fmt_num(final_price)} {escape(currency)}<br>
                • Approved by: Sales Operations<br>
                • Approval Date: {escape(timestamp)}
            </div>

            <p>
                The detailed approved payment schedule is attached as a PDF document for your records.
                This plan has been thoroughly reviewed and meets all company requirements.
            </p>

            <p style="margin-top:16px;">
                Regards,<br/>
                <strong>Prometheus ToP System</strong>
            </p>
        </div>
        """

        filename = f"approved_payment_plan_{unitCode}_{client_id}.pdf"

        _send_email_with_pdf(
            subject=subject,
            body=html_body,
            to_emails=manager_emails,
            reply_to=[sales_request.sales_man.email],
            pdf_bytes=pdf_content,
            filename=filename,
            html=True,
        )

        print(f"Approval notification sent to {len(manager_emails)} managers for unit {unitCode}")

    except Exception as e:
        print(f"Error generating PDF or sending approval email to managers: {str(e)}")
        
        

def email_thread_target(func, *args):
    """
    Wraps the email function to ensure DB connections are closed
    inside the background thread.
    """
    try:
        func(*args)
    except Exception as e:
        print(f"Background Email Error: {str(e)}")
        traceback.print_exc()
    finally:
        # CRITICAL: Explicitly close the DB connection for this thread.
        # Without this, connections leak and emails eventually stop sending.
        connection.close()

