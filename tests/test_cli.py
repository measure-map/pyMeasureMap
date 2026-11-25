"""Tests of the command-line interface. The reasoning behind the tests of 'MM compare' is laid out in
README_cli_compare.md."""

import argparse
import csv
import errno
import logging
import os
import sys

import pytest

from pymeasuremap import cli
from pymeasuremap.base import MeasureMap

MEASURE_LENGTHS = {
    "a.mm.json": [4.0, 4.0],
    "b.mm.json": [1.0, 3.0, 4.0],
    "c.mm.json": [4.0, 4.0],
}
"""a and c are identical; b splits the first measure of a, so that a and b are alignable."""


def write_measure_map(filepath, lengths):
    MeasureMap.from_array(
        count=range(1, len(lengths) + 1), actual_length=lengths
    ).to_json_file(filepath)


def write_measure_maps(directory):
    for name, lengths in MEASURE_LENGTHS.items():
        write_measure_map(directory / name, lengths)


class FakeStdin:
    def __init__(self, is_terminal):
        self.is_terminal = is_terminal

    def isatty(self):
        return self.is_terminal


def refuse_to_answer(prompt):
    raise AssertionError(f"The user was asked: {prompt}")


def run_mm(monkeypatch, *arguments):
    """Runs the MM command with the given arguments the way the installed script does."""
    monkeypatch.setattr(sys, "argv", ["MM", *(str(arg) for arg in arguments)])
    cli.run()


def unindented_lines(text):
    """The lines printed by the command itself and the first line of each report."""
    return [line for line in text.splitlines() if not line.startswith(" ")]


def read_summary(directory):
    with open(
        directory / "comparison_summary.tsv", "r", encoding="utf-8", newline=""
    ) as f:
        return list(csv.DictReader(f, delimiter="\t"))


# region choice of the mode


def test_compare_cmd_without_files_runs_corpus(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "run_corpus", calls.append)
    run_mm(monkeypatch, "compare", "-d", tmp_path)
    assert calls == [tmp_path]


def test_compare_cmd_with_files(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "one_comparison", lambda *paths: calls.append(paths))
    run_mm(monkeypatch, "compare", "-d", tmp_path, "-f", "preferred_measure_map.json")
    assert calls == [
        (tmp_path / "preferred_measure_map.json", tmp_path / "other_measure_map.json")
    ]


# endregion choice of the mode
# region layered comparison with --other


def test_compare_cmd_with_other(tmp_path, monkeypatch, capsys):
    write_measure_maps(tmp_path)
    run_mm(
        monkeypatch,
        *("compare", "-d", tmp_path, "-f", "a.mm.json", "--other", "b.mm.json"),
    )
    assert unindented_lines(capsys.readouterr().out) == [
        "Comparing MeasureMaps...",
        "a.mm.json (preferred) vs. b.mm.json (other): ALIGNABLE",
    ]


def test_compare_cmd_with_one_other_for_several_files(tmp_path, monkeypatch, capsys):
    write_measure_maps(tmp_path)
    run_mm(
        monkeypatch,
        *("compare", "-d", tmp_path, "-f", "a.mm.json", "c.mm.json"),
        *("--other", "b.mm.json"),
    )
    assert unindented_lines(capsys.readouterr().out) == [
        "Comparing MeasureMaps...",
        "a.mm.json (preferred) vs. b.mm.json (other): ALIGNABLE",
        "c.mm.json (preferred) vs. b.mm.json (other): ALIGNABLE",
    ]


def test_compare_cmd_with_as_many_others_as_files(tmp_path, monkeypatch, capsys):
    write_measure_maps(tmp_path)
    run_mm(
        monkeypatch,
        *("compare", "-d", tmp_path, "-f", "a.mm.json", "b.mm.json"),
        *("--other", "c.mm.json", "a.mm.json"),
    )
    assert unindented_lines(capsys.readouterr().out) == [
        "Comparing MeasureMaps...",
        "a.mm.json (preferred) vs. c.mm.json (other): IDENTICAL",
        "b.mm.json (preferred) vs. a.mm.json (other): ALIGNABLE",
    ]


# endregion layered comparison with --other
# region layered comparison with --pairs


def test_compare_cmd_with_pairs_file_writes_reports(tmp_path, monkeypatch, capsys):
    """The output folder does not exist and standard input is not a terminal: the run must not wait for an answer."""
    write_measure_maps(tmp_path)
    pairs_file = tmp_path / "pairs.tsv"
    pairs_file.write_text(
        "preferred\tother\na.mm.json\tc.mm.json\na.mm.json\tb.mm.json\n",
        encoding="utf-8",
    )
    out = tmp_path / "out"
    monkeypatch.setattr(sys, "stdin", FakeStdin(is_terminal=False))
    monkeypatch.setattr("builtins.input", refuse_to_answer)
    run_mm(monkeypatch, "compare", "-d", tmp_path, "--pairs", pairs_file, "-o", out)
    first_line = "a.mm.json (preferred) vs. b.mm.json (other): ALIGNABLE"
    assert unindented_lines(capsys.readouterr().out) == [
        "Comparing MeasureMaps...",
        "a.mm.json (preferred) vs. c.mm.json (other): IDENTICAL",
        first_line,
        f"Wrote the summary of 2 comparison(s) to {out / 'comparison_summary.tsv'}",
    ]
    assert sorted(path.name for path in out.iterdir()) == [
        "a_vs_b.tsv",
        "a_vs_b.txt",
        "comparison_summary.tsv",
    ]
    assert (out / "a_vs_b.txt").read_text(encoding="utf-8").splitlines()[
        0
    ] == first_line
    assert [row["verdict"] for row in read_summary(out)] == ["identical", "alignable"]


def test_compare_cmd_with_pairs_file_naming_a_missing_file(
    tmp_path, monkeypatch, capsys
):
    write_measure_maps(tmp_path)
    pairs_file = tmp_path / "pairs.tsv"
    pairs_file.write_text(
        "a.mm.json\tb.mm.json\na.mm.json\tmissing.mm.json\n", encoding="utf-8"
    )
    out = tmp_path / "out"
    out.mkdir()
    run_mm(monkeypatch, "compare", "-d", tmp_path, "--pairs", pairs_file, "-o", out)
    summary = read_summary(out)
    assert [(row["preferred"], row["other"], row["verdict"]) for row in summary] == [
        ("a.mm.json", "b.mm.json", "alignable"),
        ("a.mm.json", "missing.mm.json", "error"),
    ]
    message = (
        "FileNotFoundError: [Errno 2] No such file or directory: "
        f"{str(tmp_path / 'missing.mm.json')!r}"
    )
    assert summary[1]["message"] == message
    assert unindented_lines(capsys.readouterr().out) == [
        "Comparing MeasureMaps...",
        "a.mm.json (preferred) vs. b.mm.json (other): ALIGNABLE",
        f"a.mm.json vs. missing.mm.json: ERROR {message}",
        f"Wrote the summary of 2 comparison(s) to {out / 'comparison_summary.tsv'}",
    ]
    assert sorted(path.name for path in out.iterdir()) == [
        "a_vs_b.tsv",
        "a_vs_b.txt",
        "comparison_summary.tsv",
    ]


def test_compare_cmd_resolves_pairs_against_dir(tmp_path, monkeypatch, capsys):
    maps = tmp_path / "maps"
    elsewhere = tmp_path / "elsewhere"
    maps.mkdir()
    elsewhere.mkdir()
    write_measure_maps(maps)
    for name in ("a.mm.json", "b.mm.json"):  # decoys that would be identical
        write_measure_map(elsewhere / name, MEASURE_LENGTHS["a.mm.json"])
    pairs_file = elsewhere / "pairs.tsv"
    pairs_file.write_text("a.mm.json\tb.mm.json\n", encoding="utf-8")
    run_mm(monkeypatch, "compare", "-d", maps, "--pairs", pairs_file)
    assert unindented_lines(capsys.readouterr().out) == [
        "Comparing MeasureMaps...",
        "a.mm.json (preferred) vs. b.mm.json (other): ALIGNABLE",
    ]


# endregion layered comparison with --pairs
# region reading the pairs file


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
    write_measure_maps(tmp_path)
    pairs_file = tmp_path / "pairs.txt"
    pairs_file.write_bytes(content.encode("utf-8"))
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
    with pytest.raises(ValueError) as exc_info:
        cli.read_pairs_file(pairs_file, tmp_path)
    assert str(exc_info.value) == (
        f"{pairs_file} does not contain any pair of MeasureMap paths. Expected two columns separated by tabs "
        f"or commas."
    )


# endregion reading the pairs file
# region errors


@pytest.mark.parametrize(
    "arguments, message",
    [
        (
            ["--other", "b.mm.json"],
            "Pass the preferred MeasureMap(s) via -f when using --other.",
        ),
        (
            ["-f", "a.mm.json", "a.mm.json", "a.mm.json"]
            + ["--other", "b.mm.json", "b.mm.json"],
            "Pass either one or as many --other files as -f files.",
        ),
        (
            ["--pairs", "missing_pairs.tsv", "-f", "a.mm.json"],
            "Pass either --pairs or -f together with --other.",
        ),
        (
            ["--pairs", "missing_pairs.tsv", "--other", "b.mm.json"],
            "Pass either --pairs or -f together with --other.",
        ),
    ],
    ids=[
        "other_without_files",
        "two_others_for_three_files",
        "pairs_with_files",
        "pairs_with_other",
    ],
)
def test_compare_cmd_argument_errors(tmp_path, monkeypatch, capsys, arguments, message):
    write_measure_maps(tmp_path)
    with pytest.raises(SystemExit) as exc_info:
        run_mm(monkeypatch, "compare", "-d", tmp_path, *arguments)
    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == "Comparing MeasureMaps...\n"
    assert captured.err.startswith("usage: MM compare [-h] ")
    assert captured.err.splitlines()[-1] == f"MM compare: error: {message}"


def test_compare_cmd_with_pairs_file_without_pairs(tmp_path, monkeypatch, capsys):
    pairs_file = tmp_path / "pairs.tsv"
    pairs_file.write_text("preferred\tother\n", encoding="utf-8")
    with pytest.raises(SystemExit) as exc_info:
        run_mm(monkeypatch, "compare", "-d", tmp_path, "--pairs", pairs_file)
    assert exc_info.value.code == (
        f"MM compare: error: {pairs_file} does not contain any pair of MeasureMap paths. Expected two columns "
        f"separated by tabs or commas."
    )
    assert capsys.readouterr().out == "Comparing MeasureMaps...\n"


def test_compare_cmd_with_missing_pairs_file(tmp_path, monkeypatch, capsys):
    pairs_file = tmp_path / "missing.tsv"
    with pytest.raises(SystemExit) as exc_info:
        run_mm(monkeypatch, "compare", "-d", tmp_path, "--pairs", pairs_file)
    assert exc_info.value.code == (
        f"MM compare: error: {pairs_file}: {os.strerror(errno.ENOENT)}"
    )
    assert capsys.readouterr().out == "Comparing MeasureMaps...\n"


def test_compare_cmd_with_folder_as_pairs_file(tmp_path, monkeypatch, capsys):
    with pytest.raises(SystemExit) as exc_info:
        run_mm(monkeypatch, "compare", "-d", tmp_path, "--pairs", tmp_path)
    assert exc_info.value.code == (
        f"MM compare: error: {tmp_path}: {os.strerror(errno.EISDIR)}"
    )
    assert capsys.readouterr().out == "Comparing MeasureMaps...\n"


# endregion errors
# region folders


def test_check_dir_with_missing_directory(tmp_path):
    with pytest.raises(argparse.ArgumentTypeError) as exc_info:
        cli.check_dir(tmp_path / "missing")
    assert (
        str(exc_info.value)
        == f"{tmp_path / 'missing'} needs to be an existing directory"
    )


def test_check_and_create_without_terminal(tmp_path, monkeypatch, caplog):
    missing = tmp_path / "missing" / "nested"
    monkeypatch.setattr(sys, "stdin", FakeStdin(is_terminal=False))
    monkeypatch.setattr("builtins.input", refuse_to_answer)
    with caplog.at_level(logging.INFO, logger="pymeasuremap.cli"):
        assert cli.check_and_create(str(missing)) == missing
    assert missing.is_dir()
    assert [(record.levelname, record.getMessage()) for record in caplog.records] == [
        ("INFO", f"Created the output directory {missing}")
    ]


def test_check_and_create_on_terminal_answering_yes(tmp_path, monkeypatch):
    missing = tmp_path / "missing"
    prompts = []
    monkeypatch.setattr(sys, "stdin", FakeStdin(is_terminal=True))
    monkeypatch.setattr("builtins.input", lambda prompt: prompts.append(prompt) or "y")
    assert cli.check_and_create(str(missing)) == missing
    assert missing.is_dir()
    assert prompts == [f"{missing} does not exist. Create? (y|n)"]


def test_check_and_create_on_terminal_answering_no(tmp_path, monkeypatch):
    missing = tmp_path / "missing"
    prompts = []
    monkeypatch.setattr(sys, "stdin", FakeStdin(is_terminal=True))
    monkeypatch.setattr("builtins.input", lambda prompt: prompts.append(prompt) or "n")
    with pytest.raises(argparse.ArgumentTypeError) as exc_info:
        cli.check_and_create(str(missing))
    assert str(exc_info.value) == f"{missing} needs to be an existing directory."
    assert not missing.exists()
    assert prompts == [f"{missing} does not exist. Create? (y|n)"]


@pytest.mark.parametrize("is_terminal", [True, False])
def test_check_and_create_with_existing_directory(tmp_path, monkeypatch, is_terminal):
    monkeypatch.setattr(sys, "stdin", FakeStdin(is_terminal=is_terminal))
    monkeypatch.setattr("builtins.input", refuse_to_answer)
    assert cli.check_and_create(str(tmp_path)) == tmp_path


def test_check_and_create_without_standard_input(tmp_path, monkeypatch, caplog):
    missing = tmp_path / "missing" / "nested"
    monkeypatch.setattr(sys, "stdin", None)
    monkeypatch.setattr("builtins.input", refuse_to_answer)
    with caplog.at_level(logging.INFO, logger="pymeasuremap.cli"):
        assert cli.check_and_create(str(missing)) == missing
    assert missing.is_dir()
    assert [(record.levelname, record.getMessage()) for record in caplog.records] == [
        ("INFO", f"Created the output directory {missing}")
    ]


def test_output_folder_that_is_a_file(tmp_path, monkeypatch, capsys):
    a_file = tmp_path / "a_file"
    a_file.write_text("content", encoding="utf-8")
    monkeypatch.setattr(sys, "stdin", FakeStdin(is_terminal=False))
    monkeypatch.setattr("builtins.input", refuse_to_answer)
    with pytest.raises(SystemExit) as exc_info:
        run_mm(monkeypatch, "compare", "-d", tmp_path, "--pairs", "p.tsv", "-o", a_file)
    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("usage: MM compare [-h] ")
    assert captured.err.splitlines()[-1] == (
        f"MM compare: error: argument -o/--out: {a_file} is a file, not a directory."
    )
    assert a_file.read_text(encoding="utf-8") == "content"


def test_output_folder_under_a_file(tmp_path, monkeypatch, capsys):
    a_file = tmp_path / "a_file"
    a_file.write_text("content", encoding="utf-8")
    out = a_file / "sub"
    with pytest.raises(OSError) as error:
        out.mkdir(parents=True)
    monkeypatch.setattr(sys, "stdin", FakeStdin(is_terminal=False))
    monkeypatch.setattr("builtins.input", refuse_to_answer)
    with pytest.raises(SystemExit) as exc_info:
        run_mm(monkeypatch, "compare", "-d", tmp_path, "--pairs", "p.tsv", "-o", out)
    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("usage: MM compare [-h] ")
    assert captured.err.splitlines()[-1] == (
        f"MM compare: error: argument -o/--out: {out} cannot be created: {error.value.strerror}"
    )
    assert a_file.read_text(encoding="utf-8") == "content"


# endregion folders
