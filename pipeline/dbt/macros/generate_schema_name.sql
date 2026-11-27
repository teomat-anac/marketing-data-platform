{#
  Write each model to the dataset its folder names (dbt_project.yml `+schema`), exactly.
  dbt's default would prefix it with the target dataset (e.g. `staging_marts`), but the
  datasets are created by Terraform with plain names: raw, staging, intermediate, marts.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
