# One BigQuery dataset per data layer (architecture.md §2). A dataset is a
# container for tables and views, roughly a schema in a database; the GA4
# sample is read in place from the public project and is not copied (D2).
#
# Location US: a query can only join tables in the same location, and the GA4
# sample is in US (D7).
#
# `delete_contents_on_destroy = true`: tearing down dev is one step (US-6),
# even with tables inside. Nothing here is precious: GA4 is read in place, the
# cost generator is seeded and dbt rebuilds every model.
locals {
  datasets = {
    raw          = "Data exactly as the sources deliver it, never edited. Holds ad_spend, written by the cost generator."
    staging      = "dbt staging views: one cleaned model per source table, no business logic."
    intermediate = "dbt intermediate models: reusable joins and aggregations, e.g. one row per session."
    marts        = "dbt marts: day x channel tables, the only layer the API reads (D8)."
  }
}

resource "google_bigquery_dataset" "layer" {
  for_each = local.datasets

  dataset_id                 = each.key
  description                = each.value
  location                   = var.bq_location
  delete_contents_on_destroy = true

  depends_on = [google_project_service.this]
}
