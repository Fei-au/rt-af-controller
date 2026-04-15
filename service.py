

import os
import gql
from gql.transport.requests import RequestsHTTPTransport
from gql import Client, gql
from pathlib import Path
import pandas as pd


LOG_BACK = os.getenv("LOG_BACK", "http://127.0.0.1:8008")
print(f"Using LOG_BACK: {LOG_BACK}")
if not LOG_BACK:
    raise RuntimeError("Missing required env var LOG_BACK. Set it in .env before running the app.")
GRAPHQL_URL = LOG_BACK + "/graphql"


def read_records_from_csv(csv_file_path):
    """
    Read store-credit records from a CSV file and convert fields to expected types.

    Required headers:
    - refund_id
    - target_auction_id
    - bidcard_num
    - lot
    - payment_type
    - amount
    - invoice_number
    """
    required_fields = [
        "refund_id",
        "target_auction_id",
        "bidcard_num",
        "lot",
        "payment_type",
        "amount",
        "invoice_number",
    ]

    file_path = Path(csv_file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"CSV file not found: {file_path}")

    df = pd.read_csv(
        file_path,
        encoding="utf-8-sig",
        dtype=str,
        keep_default_na=False,
    )

    missing_fields = [field for field in required_fields if field not in df.columns]
    if missing_fields:
        raise ValueError(f"Missing required CSV headers: {', '.join(missing_fields)}")

    if 'status' not in df.columns:
        df['status'] = pd.NA
        df.to_csv(csv_file_path, index=False)
    if 'details' not in df.columns:
        df['details'] = pd.NA
        df.to_csv(csv_file_path, index=False)
        
    records = []
    for row_offset, row in df.iterrows():
        row_index = row_offset + 2
        
        if not row["bidcard_num"] or row["bidcard_num"].strip() == "":
            df.at[row_offset, 'status'] = '-1'
            df.at[row_offset, 'details'] = 'Missing bidcard' + df.at[row_offset, 'details']
            df.to_csv(csv_file_path, index=False)
            continue

        try:
            record = {
                "row_offset": row_offset,
                "status": str(row["status"]).strip(),
                "refund_id": str(row["refund_id"]).strip(),
                "target_auction_id": int(row["target_auction_id"]),
                "bidcard_num": int(row["bidcard_num"]),
                "lot": int(row["lot"]),
                "payment_type": str(row["payment_type"]).strip(),
                "amount": float(row["amount"]),
                "invoice_number": int(row["invoice_number"]),
            }
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid data at CSV row {row_index}: {row.to_dict()}") from exc

        records.append(record)

    if not records:
        raise ValueError("CSV file has no valid data rows")

    return records


def read_deduct_records_from_csv(csv_file_path) -> tuple[int, dict[int, list[dict]]]:
    """
    Read store-credit records from a CSV file and convert fields to expected types.

    Required headers:
    - auction_id
    - bidcard_num
    - invoice_number
    - sc_id
    - sc_invoice_number
    """
    required_fields = [
        "auction_id",
        "bidcard_num",
        "invoice_number",
        "sc_id",
        "sc_invoice_number",
    ]

    file_path = Path(csv_file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"CSV file not found: {file_path}")

    df = pd.read_csv(
        file_path,
        encoding="utf-8-sig",
        dtype=str,
        keep_default_na=False,
    )

    missing_fields = [field for field in required_fields if field not in df.columns]
    if missing_fields:
        raise ValueError(f"Missing required CSV headers: {', '.join(missing_fields)}")

    if 'status' not in df.columns:
        df['status'] = pd.NA
        df.to_csv(csv_file_path, index=False)
    if 'details' not in df.columns:
        df['details'] = pd.NA
        df.to_csv(csv_file_path, index=False)
    if 'errors' not in df.columns:
        df['errors'] = pd.NA
        df.to_csv(csv_file_path, index=False)
        
    records = {}
    for row_offset, row in df.iterrows():
        row_index = row_offset + 2
        
        if not row["bidcard_num"] or row["bidcard_num"].strip() == "":
            df.at[row_offset, 'status'] = '-1'
            df.at[row_offset, 'details'] = 'Missing bidcard' + df.at[row_offset, 'details']
            df.to_csv(csv_file_path, index=False)
            continue
        auction_id = int(row["auction_id"])
        try:
            if int(row["bidcard_num"]) not in records:
                records[int(row["bidcard_num"])] = [{
                    "row_offset": row_offset,
                    "status": str(row["status"]).strip(),
                    "invoice_number": int(row["invoice_number"]),
                    "sc_id": str(row["sc_id"]).strip(),
                    "sc_invoice_number": str(row["sc_invoice_number"]).strip(),
                }]
            else:
                records[int(row["bidcard_num"])].append({
                    "row_offset": row_offset,
                    "status": str(row["status"]).strip(),
                    "invoice_number": int(row["invoice_number"]),
                    "sc_id": str(row["sc_id"]).strip(),
                    "sc_invoice_number": str(row["sc_invoice_number"]).strip(),
                })
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid data at CSV row {row_index}: {row.to_dict()}") from exc

    if not records:
        raise ValueError("CSV file has no valid data rows")

    return auction_id,records


def query_refund_invoice_enhanced(
    refund_id,
    *,
    timeout=15,
    headers=None,
):
    """
    Query refund invoice records from a GraphQL endpoint.

    Query by refund_id and return only fields needed for skip logic.
    """
    graphql_url = GRAPHQL_URL

    graphql_query = gql(
        """
        query QueryRefundInvoiceById($input: RefundInvoiceByIdInput!) {
            refundInvoice(input: $input) {
                invoiceNumber
                hasCompleted
                hasVoided
                isStoreCredit
                store_credit_added: storeCreditAdded
                store_credit_added_time: storeCreditAddedTime
            }
        }
        """
    )

    transport_headers = {"Accept": "application/json"}
    if headers:
        transport_headers.update(headers)

    transport = RequestsHTTPTransport(
        url=graphql_url,
        headers=transport_headers,
        timeout=timeout,
        verify=True,
    )

    variables = {
        "input": {
            "refundId": str(refund_id),
        }
    }

    try:
        with Client(transport=transport, fetch_schema_from_transport=False) as session:
            result = session.execute(graphql_query, variable_values=variables)
    except Exception as exc:
        raise RuntimeError(f"GraphQL request failed: {exc}") from exc

    if "refundInvoice" not in result:
        raise RuntimeError("GraphQL response missing 'refundInvoice' field")

    return result["refundInvoice"]


def add_store_credit_refund_invoice(refund_id, *, timeout=15, headers=None):
    """
    Mark a refund invoice as store-credit-added via GraphQL mutation.
    """
    graphql_mutation = gql(
        """
        mutation AddStoreCreditRefundInvoice($input: MarkAsStoreCreditRefundInvoiceInput!) {
            addStoreCreditRefundInvoice(input: $input) {
                modified_count: modifiedCount
            }
        }
        """
    )

    transport_headers = {"Accept": "application/json"}
    if headers:
        transport_headers.update(headers)

    transport = RequestsHTTPTransport(
        url=GRAPHQL_URL,
        headers=transport_headers,
        timeout=timeout,
        verify=True,
    )

    variables = {
        "input": {
            "refundId": str(refund_id),
        }
    }

    try:
        with Client(transport=transport, fetch_schema_from_transport=False) as session:
            result = session.execute(graphql_mutation, variable_values=variables)
    except Exception as exc:
        raise RuntimeError(f"GraphQL mutation failed: {exc}") from exc

    if "addStoreCreditRefundInvoice" not in result:
        raise RuntimeError("GraphQL response missing 'addStoreCreditRefundInvoice' field")

    return result["addStoreCreditRefundInvoice"]


def complete_refund_invoice(refund_id, *, timeout=15, headers=None):
    """
    Mark a refund invoice as completed via GraphQL mutation.
    """
    graphql_mutation = gql(
        """
        mutation CompleteRefundInvoice($input: CompleteRefundInvoiceInput!) {
            completeRefundInvoice(input: $input) {
                modified_count: modifiedCount
            }
        }
        """
    )

    transport_headers = {"Accept": "application/json"}
    if headers:
        transport_headers.update(headers)

    transport = RequestsHTTPTransport(
        url=GRAPHQL_URL,
        headers=transport_headers,
        timeout=timeout,
        verify=True,
    )

    variables = {
        "input": {
            "refundId": str(refund_id),
        }
    }

    try:
        with Client(transport=transport, fetch_schema_from_transport=False) as session:
            result = session.execute(graphql_mutation, variable_values=variables)
    except Exception as exc:
        raise RuntimeError(f"GraphQL mutation failed: {exc}") from exc

    if "completeRefundInvoice" not in result:
        raise RuntimeError("GraphQL response missing 'completeRefundInvoice' field")

    return result["completeRefundInvoice"]
