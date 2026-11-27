-- E7: what is inside purchase revenue? Tax, shipping, refunds.
-- Answers: Q3 (revenue definition).
-- Compares purchase_revenue_in_usd with the item totals, with and without tax and shipping.
WITH p AS (
  SELECT
    ecommerce.purchase_revenue_in_usd AS revenue,
    ecommerce.tax_value_in_usd        AS tax,
    ecommerce.shipping_value_in_usd   AS shipping,
    ecommerce.refund_value_in_usd     AS refund,
    (SELECT SUM(item_revenue_in_usd) FROM UNNEST(items))  AS items_revenue,
    (SELECT SUM(price_in_usd * quantity) FROM UNNEST(items)) AS items_price_x_qty,
    ARRAY_LENGTH(items)               AS item_rows
  FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
  WHERE event_name = 'purchase'
)
SELECT
  COUNT(*)                                        AS purchase_events,
  COUNTIF(revenue IS NULL)                        AS revenue_null,
  COUNTIF(revenue = 0)                            AS revenue_zero,
  ROUND(SUM(revenue))                             AS revenue,
  COUNTIF(tax > 0)                                AS with_tax,
  ROUND(SUM(tax))                                 AS tax,
  COUNTIF(shipping > 0)                           AS with_shipping,
  ROUND(SUM(shipping))                            AS shipping,
  COUNTIF(refund IS NOT NULL)                     AS with_refund_field,
  ROUND(SUM(items_revenue))                       AS items_revenue,
  ROUND(SUM(items_price_x_qty))                   AS items_price_x_qty,
  COUNTIF(item_rows = 0)                          AS without_items,
  COUNTIF(ABS(revenue - items_revenue) < 0.01)    AS revenue_eq_items,
  COUNTIF(ABS(revenue - (items_revenue + IFNULL(tax, 0) + IFNULL(shipping, 0))) < 0.01)
                                                  AS revenue_eq_items_tax_shipping,
  COUNTIF(ABS(revenue - (items_revenue + IFNULL(tax, 0))) < 0.01 AND tax > 0)
                                                  AS revenue_eq_items_tax
FROM p;
