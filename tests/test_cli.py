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


def test_compare_cmd_with_pairs_file(tmp_path):
    from pymeasuremap.base import MeasureMap

    for name, lengths in (("a.mm.json", [4.0, 4.0]), ("b.mm.json", [1.0, 3.0, 4.0])):
        MeasureMap.from_array(
            count=range(1, len(lengths) + 1), actual_length=lengths
        ).to_json_file(tmp_path / name)
    (tmp_path / "pairs.tsv").write_text("preferred\tother\na.mm.json\tb.mm.json\n")
    out = tmp_path / "out"
    out.mkdir()
    args = cli.get_arg_parser().parse_args(
        [
            "compare",
            "-d",
            str(tmp_path),
            "--pairs",
            str(tmp_path / "pairs.tsv"),
            "-o",
            str(out),
        ]
    )
    args.func(args)
    assert (out / "comparison_summary.tsv").read_text().count("alignable") == 1


def write_pair_of_measure_maps(directory):
    from pymeasuremap.base import MeasureMap

    for name, lengths in (("a.mm.json", [4.0, 4.0]), ("b.mm.json", [1.0, 3.0, 4.0])):
        MeasureMap.from_array(
            count=range(1, len(lengths) + 1), actual_length=lengths
        ).to_json_file(directory / name)


@pytest.mark.parametrize(
    "content",
    [
        "a.mm.json\tb.mm.json\n",
        "preferred\tother\na.mm.json\tb.mm.json\n",
        "a.mm.json,b.mm.json\n",
        "preferred,other\r\na.mm.json,b.mm.json\r\n",
        '"a.mm.json","b.mm.json"\n',
        "﻿a.mm.json,b.mm.json\n",
        "a.mm.json,b.mm.json,a comment\n\n",
    ],
    ids=[
        "tsv",
        "tsv_header",
        "csv",
        "csv_header_crlf",
        "quoted",
        "bom",
        "third_column",
    ],
)
def test_read_pairs_file(tmp_path, content):
    write_pair_of_measure_maps(tmp_path)
    pairs_file = tmp_path / "pairs.txt"
    pairs_file.write_text(content, encoding="utf-8")
    assert cli.read_pairs_file(pairs_file, tmp_path) == [
        (tmp_path / "a.mm.json", tmp_path / "b.mm.json")
    ]


def test_read_pairs_file_with_comma_in_path_and_without_json_extension(tmp_path):
    folder = tmp_path / "dir, with comma"
    folder.mkdir()
    (folder / "a.mm").write_text("[]")
    pairs_file = tmp_path / "pairs.csv"
    pairs_file.write_text('"dir, with comma/a.mm",b.mm\n', encoding="utf-8")
    assert cli.read_pairs_file(pairs_file, tmp_path) == [
        (folder / "a.mm", tmp_path / "b.mm")
    ]


def test_read_pairs_file_without_pairs(tmp_path):
    pairs_file = tmp_path / "pairs.tsv"
    pairs_file.write_text("preferred\tother\n", encoding="utf-8")
    with pytest.raises(ValueError, match="does not contain any pair"):
        cli.read_pairs_file(pairs_file, tmp_path)


def test_compare_cmd_with_other(tmp_path, capsys):
    write_pair_of_measure_maps(tmp_path)
    parser = cli.get_arg_parser()
    args = parser.parse_args(
        ["compare", "-d", str(tmp_path), "-f", "a.mm.json", "--other", "b.mm.json"]
    )
    args.files = cli.resolve_files_argument(args.files, args.dir)
    args.func(args)
    assert (
        "a.mm.json (preferred) vs. b.mm.json (other): ALIGNABLE"
        in capsys.readouterr().out
    )


@pytest.mark.parametrize(
    "arguments, message",
    [
        (["--other", "b.mm.json"], "Pass the preferred MeasureMap"),
        (
            [
                "-f",
                "a.mm.json",
                "a.mm.json",
                "a.mm.json",
                "--other",
                "b.mm.json",
                "b.mm.json",
            ],
            "either one or as many",
        ),
        (["--pairs", "pairs.tsv", "-f", "a.mm.json"], "either --pairs or -f"),
    ],
)
def test_compare_cmd_argument_errors(tmp_path, arguments, message):
    write_pair_of_measure_maps(tmp_path)
    args = cli.get_arg_parser().parse_args(["compare", "-d", str(tmp_path), *arguments])
    with pytest.raises(SystemExit, match=message):
        args.func(args)
