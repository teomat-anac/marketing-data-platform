"""The generator's BigQuery side: read paid sessions, replace `raw.ad_spend`.

Kept thin so that the rules (generator.py) are tested without BigQuery.
"""

from collections.abc import Sequence
from datetime import datetime

from google.cloud import bigquery

from mdp_pipeline.generator import AdSpendRow, PaidSessions
from mdp_pipeline.settings import AD_SPEND_TABLE, LOCATION, MAX_BYTES_BILLED, SESSIONS_TABLE

# Own-source sessions per day of the paid channels (D16): the visits ads actually brought.
_PAID_SESSIONS_SQL = """
select session_date as date, own_channel as channel, count(*) as sessions
from `{table}`
where own_channel in unnest(@channels)
group by session_date, own_channel
order by session_date, own_channel
"""

# Same columns as an ad-platform export (data-sources.md §3).
AD_SPEND_SCHEMA = [
    bigquery.SchemaField("date", "DATE", mode="REQUIRED", description="Day of the ad activity"),
    bigquery.SchemaField("channel", "STRING", mode="REQUIRED", description="Paid channel"),
    bigquery.SchemaField("campaign", "STRING", mode="REQUIRED", description="Campaign name"),
    bigquery.SchemaField(
        "impressions", "INT64", mode="REQUIRED", description="Times the ads were shown"
    ),
    bigquery.SchemaField("clicks", "INT64", mode="REQUIRED", description="Clicks on the ads"),
    bigquery.SchemaField("spend", "NUMERIC", mode="REQUIRED", description="Cost in USD"),
    bigquery.SchemaField(
        "loaded_at", "TIMESTAMP", mode="REQUIRED", description="When the row was written"
    ),
]


def read_paid_sessions(
    client: bigquery.Client, project: str, channels: Sequence[str]
) -> list[PaidSessions]:
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ArrayQueryParameter("channels", "STRING", list(channels))],
        maximum_bytes_billed=MAX_BYTES_BILLED,
    )
    sql = _PAID_SESSIONS_SQL.format(table=f"{project}.{SESSIONS_TABLE}")
    rows = client.query(sql, job_config=job_config, location=LOCATION).result()
    return [PaidSessions(r["date"], r["channel"], r["sessions"]) for r in rows]


def to_json_row(row: AdSpendRow, loaded_at: datetime) -> dict[str, str | int]:
    """One row in the shape a load job expects; NUMERIC goes as a string to stay exact."""
    return {
        "date": row.date.isoformat(),
        "channel": row.channel,
        "campaign": row.campaign,
        "impressions": row.impressions,
        "clicks": row.clicks,
        "spend": str(row.spend),
        "loaded_at": loaded_at.isoformat(),
    }


def replace_ad_spend(
    client: bigquery.Client, project: str, rows: Sequence[AdSpendRow], loaded_at: datetime
) -> int:
    """Replace the whole table with `rows`, in one load job; returns the rows written.

    A load job is free (streaming inserts are not), and WRITE_TRUNCATE swaps the table in
    one step: a re-run leaves no duplicates, and a failed run leaves the old table (FR-5).
    The job creates the table on the first run, partitioned by day like the marts.
    """
    job_config = bigquery.LoadJobConfig(
        schema=AD_SPEND_SCHEMA,
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        create_disposition=bigquery.CreateDisposition.CREATE_IF_NEEDED,
        time_partitioning=bigquery.TimePartitioning(
            type_=bigquery.TimePartitioningType.DAY, field="date"
        ),
    )
    job = client.load_table_from_json(
        [to_json_row(r, loaded_at) for r in rows],
        f"{project}.{AD_SPEND_TABLE}",
        job_config=job_config,
        location=LOCATION,
    )
    job.result()
    return job.output_rows or 0
