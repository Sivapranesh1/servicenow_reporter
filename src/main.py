"""Entry point: run end-to-end pipeline once."""
from __future__ import annotations

import sys
import traceback
from datetime import datetime

from src.config_loader import load_config
from src.email_sender import send_email, send_failure_notification, EmailError
from src.excel_processor import (
    ExcelProcessingError, find_latest_excel,
    normalize_dataframe, read_incident_file,
)
from src.incident_analyzer import analyze
from src.logger_setup import setup_logger
from src.report_generator import build_html_report, write_excel, write_html


def run_pipeline(config_path: str | None = None) -> int:
    cfg = load_config(config_path)
    logger = setup_logger(
        log_dir=cfg["paths"]["log_folder"],
        file_name=cfg["logging"]["file_name"],
        level=cfg["logging"]["level"],
        when=cfg["logging"]["rotate_when"],
        backup_count=cfg["logging"]["backup_count"],
    )
    logger.info("=" * 70)
    logger.info("Starting ServiceNow Reporter run")
    try:
        # 1. Locate + read Excel
        latest = find_latest_excel(cfg["paths"]["excel_input_folder"])
        raw_df, col_map = read_incident_file(latest, cfg["excel"]["required_columns"])
        df = normalize_dataframe(raw_df, col_map)

        # 2. Analyze
        result = analyze(df, cfg["thresholds"])

        # 3. Build reports
        subject = f"{cfg['email']['subject_prefix']} - {datetime.now():%Y-%m-%d}"
        html = build_html_report(result, cfg["thresholds"]["stale_hours"], subject)
        html_path = write_html(html, cfg["paths"]["report_output_folder"])
        xlsx_path = write_excel(result, cfg["paths"]["report_output_folder"])

        # 4. Email
        if cfg["email"].get("enabled", True):
            attachments = []
            if cfg["email"].get("attach_html"):
                attachments.append(html_path)
            if cfg["email"].get("attach_excel"):
                attachments.append(xlsx_path)
            send_email(
                smtp_host=cfg["email"]["smtp_host"],
                smtp_port=cfg["email"]["smtp_port"],
                smtp_user=cfg["email"]["smtp_user"],
                smtp_password=cfg["email"]["smtp_password"],
                use_tls=cfg["email"]["smtp_use_tls"],
                from_address=cfg["email"]["from_address"],
                from_name=cfg["email"]["from_name"],
                to_addrs=cfg["email"].get("recipients_to", []),
                cc_addrs=cfg["email"].get("recipients_cc", []),
                subject=subject,
                html_body=html,
                attachments=attachments,
            )
        else:
            logger.info("Email delivery disabled in config.")

        logger.info("Run completed successfully.")
        return 0

    except (ExcelProcessingError, EmailError) as exc:
        logger.exception("Recoverable failure: %s", exc)
        send_failure_notification(cfg, str(exc))
        return 2
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unhandled error: %s", exc)
        send_failure_notification(cfg, traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(run_pipeline())
