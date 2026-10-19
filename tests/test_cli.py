import argparse

import pytest

from pymeasuremap import cli


def test_compare_cmd_without_files_runs_corpus(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "run_corpus", calls.append)
    args = cli.get_arg_parser().parse_args(["compare", "-d", str(tmp_path)])
    args.func(args)
    assert calls == [tmp_path]


def test_compare_cmd_with_files(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "one_comparison", lambda *paths: calls.append(paths))
    args = cli.get_arg_parser().parse_args(
        ["compare", "-d", str(tmp_path), "-f", "preferred_measure_map.json"]
    )
    args.files = cli.resolve_files_argument(args.files, args.dir)
    args.func(args)
    assert calls == [
        (tmp_path / "preferred_measure_map.json", tmp_path / "other_measure_map.json")
    ]


def test_check_dir_with_missing_directory(tmp_path):
    with pytest.raises(argparse.ArgumentTypeError, match="needs to be an existing"):
        cli.check_dir(tmp_path / "missing")
