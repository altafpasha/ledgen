from typing import Any, Dict, List, Optional
from app.core.config import settings
from app.core.exceptions import ProviderException
from app.core.logging import logger
from app.providers.base import SheetsProvider

COLUMNS = [
    "Business Name",
    "Owner Name",
    "Email",
    "Phone",
    "Location",
    "Website",
    "Category",
    "Lead Score",
    "Opportunity",
    "Lead Status",
    "Source",
    "Created At",
    "Google Maps / Source Link",
]


class GoogleSheetsProvider(SheetsProvider):
    """
    Google Sheets API Provider.
    Exports and synchronizes lead records with Google Sheets.
    Adheres strictly to the rule: Missing websites, emails, phones, or owner names
    must remain completely blank in the sheet cells (no N/A, None, or placeholders).
    """

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        refresh_token: Optional[str] = None,
        default_spreadsheet_id: Optional[str] = None,
        mock_mode: Optional[bool] = None,
    ):
        self.client_id = client_id or settings.google_client_id
        self.client_secret = client_secret or settings.google_client_secret
        self.refresh_token = refresh_token or settings.google_refresh_token
        self.spreadsheet_id = default_spreadsheet_id or settings.google_sheets_spreadsheet_id
        
        has_creds = bool(self.client_id and self.client_secret and self.refresh_token)
        if mock_mode is not None:
            self.mock_mode = mock_mode
        else:
            # If valid credentials are provided, use live mode unless explicitly mocked
            self.mock_mode = settings.mock_providers and not has_creds

    def _format_lead_row(self, lead: Dict[str, Any]) -> List[Any]:
        """
        Formats lead data to sheet row according to strict rules:
        Missing fields must be empty string "" (never "N/A" or "None").
        Maintains exact column alignment for Lead Score (Col H), Opportunity (Col I),
        and Lead Status (Col J) so custom Google Sheet dropdowns remain valid.
        """
        website_val = lead.get("website")
        if not website_val or str(website_val).strip().lower() in ("none", "n/a", "null"):
            website_val = ""

        email_val = lead.get("email")
        if not email_val or str(email_val).strip().lower() in ("none", "n/a", "null"):
            email_val = ""

        phone_val = lead.get("phone")
        if not phone_val or str(phone_val).strip().lower() in ("none", "n/a", "null"):
            phone_val = ""

        owner_val = lead.get("owner_name")
        if not owner_val or str(owner_val).strip().lower() in ("none", "n/a", "null"):
            owner_val = ""

        location_parts = [lead.get("city"), lead.get("district"), lead.get("state")]
        location_str = ", ".join([p for p in location_parts if p])

        # Clickable source verification link placed at the end
        source_link = lead.get("google_maps_url")
        # Check if missing or a mock dummy link (e.g. cid=1001, cid=1002) that doesn't resolve in Google Maps
        is_dummy = bool(source_link and any(d in source_link for d in ["cid=100", "cid=101", "cid=102", "cid=103", "example.com"]))
        if not source_link or is_dummy:
            biz_name = lead.get("business_name") or ""
            addr = lead.get("address") or location_str
            if biz_name:
                import urllib.parse
                query_parts = [biz_name]
                if addr:
                    query_parts.append(addr)
                query_str = " ".join(query_parts).strip()
                source_link = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(query_str)}"
            else:
                source_link = ""

        created_at_val = lead.get("created_at")
        if hasattr(created_at_val, "isoformat"):
            created_at_str = created_at_val.isoformat()
        else:
            created_at_str = str(created_at_val or "")

        return [
            lead.get("business_name") or "",
            owner_val,
            email_val,
            phone_val,
            location_str,
            website_val,
            lead.get("category") or "",
            lead.get("lead_score", 0),
            lead.get("opportunity") or "UNKNOWN",
            lead.get("status") or "NEW",
            lead.get("source") or "apify",
            created_at_str,
            source_link,
        ]

    async def export_leads(
        self,
        spreadsheet_id: Optional[str],
        sheet_name: str,
        leads_data: List[Dict[str, Any]],
        **kwargs
    ) -> Dict[str, Any]:
        target_sheet_id = spreadsheet_id or self.spreadsheet_id or "mock_spreadsheet_id_123"

        if self.mock_mode or not (self.client_id and self.client_secret and self.refresh_token):
            logger.info(
                f"Exporting {len(leads_data)} leads via Mock Google Sheets Provider",
                extra={"event": "google_sheets_mock_export", "spreadsheet_id": target_sheet_id}
            )
            return {
                "status": "completed",
                "spreadsheet_id": target_sheet_id,
                "sheet_name": sheet_name,
                "total_rows_exported": len(leads_data),
                "spreadsheet_url": f"https://docs.google.com/spreadsheets/d/{target_sheet_id}/edit",
                "mock": True,
            }

        return await self._live_export(target_sheet_id, sheet_name, leads_data)

    async def _live_export(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        leads_data: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build

            creds = Credentials(
                None,
                refresh_token=self.refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=self.client_id,
                client_secret=self.client_secret,
            )
            service = build("sheets", "v4", credentials=creds)

            # Query spreadsheet metadata to resolve or match sheet title
            meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
            existing_sheets = [s.get("properties", {}).get("title") for s in meta.get("sheets", [])]

            target_sheet = sheet_name
            if target_sheet not in existing_sheets:
                if "Leads" in existing_sheets:
                    target_sheet = "Leads"
                elif existing_sheets:
                    target_sheet = existing_sheets[0]
                else:
                    target_sheet = "Sheet1"

            # Check existing sheet content to support cumulative daily appending
            range_check = f"'{target_sheet}'!A:D"
            get_res = service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=range_check
            ).execute()
            existing_values = get_res.get("values", [])

            if not existing_values:
                # Sheet is empty: write header row first
                service.spreadsheets().values().update(
                    spreadsheetId=spreadsheet_id,
                    range=f"'{target_sheet}'!A1",
                    valueInputOption="RAW",
                    body={"values": [COLUMNS]},
                ).execute()
                existing_names = set()
            else:
                # Collect existing business names (case-insensitive) to prevent duplicating rows
                existing_names = {
                    (row[0] or "").strip().lower()
                    for row in existing_values
                    if row and len(row) > 0 and (row[0] or "").strip().lower() != "business name"
                }

            # Filter leads to only append new leads that are not already in the sheet
            new_rows = []
            for lead in leads_data:
                biz_name = (lead.get("business_name") or "").strip()
                if not biz_name:
                    continue
                if biz_name.lower() not in existing_names:
                    new_rows.append(self._format_lead_row(lead))
                    existing_names.add(biz_name.lower())

            if new_rows:
                append_range = f"'{target_sheet}'!A1"
                service.spreadsheets().values().append(
                    spreadsheetId=spreadsheet_id,
                    range=append_range,
                    valueInputOption="RAW",
                    insertDataOption="INSERT_ROWS",
                    body={"values": new_rows},
                ).execute()

            logger.info(
                f"Successfully synced {len(new_rows)} new leads to Google Sheets spreadsheet {spreadsheet_id} on tab '{target_sheet}' (total campaign batch: {len(leads_data)})",
                extra={"event": "google_sheets_live_export", "spreadsheet_id": spreadsheet_id, "new_rows": len(new_rows), "total_batch": len(leads_data)}
            )

            return {
                "status": "completed",
                "spreadsheet_id": spreadsheet_id,
                "sheet_name": target_sheet,
                "total_rows_exported": len(leads_data),
                "spreadsheet_url": f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit",
                "mock": False,
            }

        except Exception as e:
            logger.error(f"Google Sheets live export error: {str(e)}")
            raise ProviderException("google_sheets", f"Failed to export leads to Google Sheets: {str(e)}")
