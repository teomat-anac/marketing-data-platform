"""Command-line entry points.

- `mdp-generate`: the cost generator alone (reads int_ga4__sessions, replaces raw.ad_spend).
- `mdp-pipeline`: one full run in the order the data needs (architecture.md §3):
  dbt for the GA4 side, then the generator, then dbt for costs and marts, with every test.
"""

import argparse
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from mdp_pipeline import bigquery_io
from mdp_pipeline.generator import generate
from mdp_pipeline.settings import CAMPAIGNS, DEFAULT_SEED, PROJECT_ENV, project

# Where the dbt project is: MDP_DBT_DIR (e.g. in a container image), else pipeline/dbt in
# this checkout, found from this file (uv installs the project in editable mode).
DBT_DIR_ENV = "MDP_DBT_DIR"
SOURCE_DBT_DIR = Path(__file__).resolve().parents[2] / "dbt"

# Step 1 builds what the generator reads: the seeds, GA4 staging and the sessions.
# Step 3 builds the rest. `buildable` runs a test only when every model it reads is built in
# the same step or before it, so no step tests a model the other step hasn't built yet.
DBT_STEP_GA4 = ["--select", "resource_type:seed", "+int_ga4__sessions"]
DBT_STEP_MARTS = ["--select", "source:ads+", "path:models/marts"]
# A full parse on every build (a few seconds): a saved parse can miss a changed seed file.
DBT_OPTIONS = ["--indirect-selection", "buildable", "--no-partial-parse"]


def default_dbt_dir() -> Path:
    return Path(os.environ.get(DBT_DIR_ENV) or SOURCE_DBT_DIR)


def run_generator(project_id: str, seed: int, dry_run: bool = False) -> None:
    from google.cloud import bigquery

    client = bigquery.Client(project=project_id)
    channels = [c.channel for c in CAMPAIGNS]
    paid_sessions = bigquery_io.read_paid_sessions(client, project_id, channels)
    rows = generate(paid_sessions, CAMPAIGNS, seed)
    clicks = sum(r.clicks for r in rows)
    spend = sum(r.spend for r in rows)
    print(
        f"Generated {len(rows)} rows for {', '.join(channels)}: "
        f"{rows[0].date} to {rows[-1].date}, {clicks:,} clicks, ${spend:,.2f} spend (seed {seed})."
    )
    if dry_run:
        print("Dry run: raw.ad_spend not written.")
        return
    written = bigquery_io.replace_ad_spend(client, project_id, rows, datetime.now(UTC))
    print(f"Replaced {project_id}.raw.ad_spend: {written} rows.")


def run_dbt(args: list[str], dbt_dir: Path) -> None:
    from dbt.cli.main import dbtRunner

    print(f"\n$ dbt {' '.join(args)}", flush=True)
    result = dbtRunner().invoke(
        [*args, "--project-dir", str(dbt_dir), "--profiles-dir", str(dbt_dir)]
    )
    if not result.success:
        raise SystemExit(f"dbt {args[0]} failed: stopping the pipeline.")


def generate_main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="mdp-generate",
        description="Generate synthetic ad costs from paid sessions and replace raw.ad_spend.",
    )
    _add_common_args(parser)
    parser.add_argument(
        "--dry-run", action="store_true", help="read and generate, but don't write the table"
    )
    args = _parse(parser, argv)
    run_generator(args.project, args.seed, args.dry_run)


def pipeline_main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="mdp-pipeline",
        description="Run dbt (GA4 side), the cost generator, then dbt (costs and marts).",
    )
    _add_common_args(parser)
    parser.add_argument(
        "--dbt-dir",
        type=Path,
        default=None,
        help=f"the dbt project folder (default: ${DBT_DIR_ENV}, else pipeline/dbt)",
    )
    args = _parse(parser, argv)
    dbt_dir = args.dbt_dir or default_dbt_dir()
    if not (dbt_dir / "dbt_project.yml").is_file():
        raise SystemExit(
            f"No dbt project in {dbt_dir}: pass --dbt-dir or set {DBT_DIR_ENV} "
            "to the folder that holds dbt_project.yml."
        )
    # dbt's profile reads the project from the environment; keep both on the same project.
    os.environ[PROJECT_ENV] = args.project

    run_dbt(["deps"], dbt_dir)
    run_dbt(["build", *DBT_STEP_GA4, *DBT_OPTIONS], dbt_dir)
    print("\n$ mdp-generate", flush=True)
    run_generator(args.project, args.seed)
    run_dbt(["build", *DBT_STEP_MARTS, *DBT_OPTIONS], dbt_dir)
    print("\nPipeline finished: marts rebuilt and every test passed.")


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--project",
        default=project(),
        help=f"GCP project (default: ${PROJECT_ENV}; one of the two is required)",
    )
    parser.add_argument(
        "--seed", type=int, default=DEFAULT_SEED, help="random seed (default: %(default)s)"
    )


def _parse(parser: argparse.ArgumentParser, argv: list[str] | None) -> argparse.Namespace:
    args = parser.parse_args(argv)
    if not args.project:
        parser.error(f"no GCP project: pass --project or set ${PROJECT_ENV}")
    return args


if __name__ == "__main__":
    sys.exit(pipeline_main())
