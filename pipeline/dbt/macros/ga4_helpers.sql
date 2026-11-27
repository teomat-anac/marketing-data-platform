{#-
  The `_TABLE_SUFFIX` (YYYYMMDD) of the day `days` after `iso_date`. `iso_date` may be a
  string or a date: YAML reads an unquoted 2020-12-01 as a date, so it's turned into text.
-#}
{% macro ga4_table_suffix(iso_date, days=0) -%}
    {%- set day = modules.datetime.date.fromisoformat(iso_date | string) -%}
    {{- (day + modules.datetime.timedelta(days=days)).strftime('%Y%m%d') -}}
{%- endmacro %}

{#-
  The `attribution_lookback_days` variable, checked: a whole number of days, 0 or more
  (0 means a Direct visit never inherits a channel). Anything else stops the build. Jinja's
  `int` filter alone would turn a typo such as "9O" into 0 and quietly shift credit to Direct.
-#}
{% macro attribution_lookback_days() -%}
    {%- set value = var('attribution_lookback_days') -%}
    {%- set text = value | string | trim -%}
    {%- if value is boolean or not modules.re.fullmatch('[0-9]+', text) -%}
        {{ exceptions.raise_compiler_error(
            "var attribution_lookback_days must be a whole number of days, 0 or more, not: " ~ value
        ) }}
    {%- endif -%}
    {{- text | int -}}
{%- endmacro %}

{#-
  True when `column` (a traffic source) contains one of the shop's own domains (D16),
  ignoring case. `self_referral_domains` must be a list of domains; an empty list means no
  self-referrals. A plain string is refused: Jinja would loop over its letters, and almost
  every source would count as a self-referral without any test noticing.
-#}
{% macro is_self_referral(column) -%}
    {%- set domains = var('self_referral_domains') -%}
    {%- if domains is none -%}
        {%- set domains = [] -%}
    {%- endif -%}
    {%- if domains is string or domains is mapping or domains is not iterable -%}
        {{ exceptions.raise_compiler_error(
            "var self_referral_domains must be a list, e.g. ['myshop.com'], not: " ~ domains
        ) }}
    {%- endif -%}
    {%- for domain in domains -%}
        {%- if domain is not string or domain | trim == '' or "'" in domain -%}
            {{ exceptions.raise_compiler_error(
                "var self_referral_domains: each entry must be a domain name, not: " ~ domain
            ) }}
        {%- endif -%}
    {%- endfor -%}
    {%- if domains | length == 0 -%}
        false
    {%- else -%}
        (
        {%- for domain in domains %}
            strpos(lower(ifnull({{ column }}, '')), '{{ domain | trim | lower }}') > 0{% if not loop.last %} or{% endif %}
        {%- endfor %}
        )
    {%- endif -%}
{%- endmacro %}
