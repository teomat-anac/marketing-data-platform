"""Where mdp-pipeline finds the dbt project and the GCP project; nothing here reaches dbt
or BigQuery."""

from collections.abc import Callable
from pathlib import Path

import pytest

from mdp_pipeline import cli
from mdp_pipeline.settings import PROJECT_ENV


def must_not_run(*args: object) -> None:
    raise AssertionError("no step must run")


def test_the_source_checkout_holds_the_dbt_project(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(cli.DBT_DIR_ENV, raising=False)
    assert (cli.default_dbt_dir() / "dbt_project.yml").is_file()


def test_the_environment_variable_wins(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(cli.DBT_DIR_ENV, str(tmp_path))
    assert cli.default_dbt_dir() == tmp_path


def test_a_folder_without_a_dbt_project_stops_before_any_step(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(cli, "run_dbt", must_not_run)
    with pytest.raises(SystemExit, match="No dbt project in"):
        cli.pipeline_main(["--project", "test-project", "--dbt-dir", str(tmp_path)])


@pytest.mark.parametrize("main", [cli.pipeline_main, cli.generate_main])
def test_no_gcp_project_stops_before_any_step(
    main: Callable[[list[str]], None],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv(PROJECT_ENV, raising=False)
    monkeypatch.setattr(cli, "run_dbt", must_not_run)
    monkeypatch.setattr(cli, "run_generator", must_not_run)
    with pytest.raises(SystemExit):
        main([])
    assert f"no GCP project: pass --project or set ${PROJECT_ENV}" in capsys.readouterr().err


def test_the_project_comes_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[object, ...]] = []
    monkeypatch.setenv(PROJECT_ENV, "env-project")
    monkeypatch.setattr(cli, "run_generator", lambda *args: calls.append(args))
    cli.generate_main([])
    assert calls == [("env-project", cli.DEFAULT_SEED, False)]
