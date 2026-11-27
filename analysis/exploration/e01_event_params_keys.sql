-- E1: which keys does event_params contain, how often, and with which value type?
-- Answers: Q2 (does each visit carry its own source/medium/campaign?).
-- Scope: one week (1-7 Dec 2020) is enough to see the structure.
-- Cost: ~155 MB (dry run). Run with "Maximum bytes billed" = 2 GB.

SELECT
  ep.key,
  COUNT(*)                                     AS events,
  COUNT(DISTINCT event_name)                   AS on_event_names,
  COUNTIF(ep.value.string_value IS NOT NULL)   AS string_values,
  COUNTIF(ep.value.int_value IS NOT NULL)      AS int_values,
  COUNTIF(ep.value.double_value IS NOT NULL
       OR ep.value.float_value IS NOT NULL)    AS decimal_values
FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`,
  UNNEST(event_params) AS ep
WHERE _TABLE_SUFFIX BETWEEN '20201201' AND '20201207'
GROUP BY ep.key
ORDER BY events DESC;
