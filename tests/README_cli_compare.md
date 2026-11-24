# How `MM compare` is tested

This file states, for each behaviour of the `compare` command and of the helpers it relies on, which input proves
the behaviour and why the expected outcome is the right one. The tests live in `test_cli.py` and follow this
reasoning; a test that does not is wrong, even if it passes.

## Principles

* **Through the front door.** Wherever the behaviour involves the command line (argument parsing, resolution of
  paths against `-d`, exit status, what is printed), the test sets `sys.argv` to `MM compare ...` and calls
  `cli.run()`. This is what the installed `MM` script does, so the test also covers what happens between parsing
  and the command function. Only the pure helpers (`read_pairs_file`, `check_dir`, `check_and_create`) are called
  directly.
* **Small maps with a known relation.** The measure maps are built in the test from lists of measure lengths, so
  that the correct verdict can be derived by hand:
  * `a` = two measures of 4 quarters,
  * `b` = three measures of 1, 3 and 4 quarters: the same 8 quarters, but the first measure of `a` is split in
    two. `a` against `b` is therefore `alignable` (one join), and so is `b` against `a` (one split);
  * `c` = a second file with the content of `a`. `a` against `c` is `identical`.
* **Whole values.** The command line decides which maps are paired, in which order, where the output goes and what
  is said about failures. The tests therefore assert whole values: the complete list of unindented lines printed
  (the first line of each report and the lines the command adds itself), the complete set of files in the output
  folder, the complete list of verdicts in the summary. The indented lines of a report describe the layers of the
  comparison; they belong to the comparison itself and are tested with it, not here.

## Choice of the mode

* **No `--other`, no `--pairs`, no `-f`**: the diagnosis must be run on the folder given via `-d`. The function
  doing that is replaced by a recorder; it must have been called exactly once, with that folder.
* **`-f` only**: each file is diagnosed against `other_measure_map.json` in its own folder. With the diagnosing
  function replaced by a recorder, the recorded pair must be (`-d`/file, `-d`/`other_measure_map.json`), which
  also shows that a relative `-f` is resolved against `-d`.

## Layered comparison with `--other`

* **One `-f`, one `--other`**: `-f a --other b`, both relative to `-d`. Exactly one report must be printed and its
  first line must name `a` as preferred, `b` as other, and the verdict `ALIGNABLE`. Swapped roles or unresolved
  paths would give another first line or an error line.
* **Several `-f`, one `--other`**: `-f a c --other b`. Every preferred map must be compared with the same other
  one, in the order given: two reports, `a` vs. `b` and `c` vs. `b`, both `ALIGNABLE`. A command that used the
  other file only once would print one report; one that paired the wrong way round would name `b` as preferred.
* **As many `--other` as `-f`**: `-f a b --other c a`. The files must be paired by position: `a` vs. `c` is
  `IDENTICAL` and `b` vs. `a` is `ALIGNABLE`. The two pairs have different verdicts on purpose: pairing every
  `-f` with the first `--other`, or crossing the lists, yields other first lines.

## Layered comparison with `--pairs`

* **Output files**: a pairs file with a header row and the rows `a, c` (identical) and `a, b` (not identical),
  with `-o`. The output folder must contain exactly `comparison_summary.tsv`, `a_vs_b.tsv` and `a_vs_b.txt`: a
  summary is always written, reports only for pairs that are not identical, so any file for `a` vs. `c` is an
  error and so is a missing one for `a` vs. `b`. The first line of `a_vs_b.txt` must be the first line of the
  printed report, the verdicts in the summary must be `identical`, `alignable` in the order of the rows (which
  also proves that the header row was not taken for a pair), and the last printed line must name the summary
  file and the number of comparisons, 2.
* **A missing measure map**: the rows `a, b` and `a, missing`. One unreadable file must not abort a run over many
  pairs. The run must complete without an exception; the summary must have the verdicts `alignable`, `error`; no
  report file may be written for the failed pair; and the command must print one line
  `a.mm.json vs. missing.mm.json: ERROR <message>`, where `<message>` is what the summary holds in the column
  `message` for that row. The test reads it from the summary and requires it to be non-empty: the wording of the
  failure belongs to the comparison, what the command owes is that it prints exactly that and for exactly that
  pair.
* **Relative paths resolve against `-d`**: the pairs file lies in another folder than the one given via `-d`, and
  its only row is `a, b`. Under `-d`, `a` and `b` are the maps described above (`alignable`). The folder of the
  pairs file contains decoys of the same names with equal content, which would be `identical`. The printed first
  line must say `ALIGNABLE`: `IDENTICAL` would mean the paths were resolved against the folder of the pairs file,
  an error line that they were resolved against neither.

## Reading the pairs file

`read_pairs_file` is given a folder containing `a` and `b` and must return exactly the one pair (`a`, `b`) as
absolute paths for each of these spellings of the same content: tab-separated, tab-separated with a header,
comma-separated, comma-separated with a header and Windows line endings, quoted cells, a leading byte order mark,
and a third column plus an empty line. Each of them is a way such a file leaves a spreadsheet program or an
editor, and none of them changes what the file says.

* **Comma within a path, no `.json` extension**: a quoted first cell containing a comma must stay one path, and
  an existing file without `.json` in the first row must not be taken for a header. The expected result is the
  one pair with the path containing the comma.
* **No pair**: a file with a header row only must raise a `ValueError` saying that the file does not contain any
  pair. An empty list would let the command write an empty summary and report success.

## Errors

There are two kinds, and they leave the program differently.

* **Wrong combination of arguments**: `--other` without `-f`; a number of `--other` files that is neither one nor
  the number of `-f` files (three against two); `--pairs` together with `-f`; `--pairs` together with `--other`.
  These are mistakes in the call, and must be reported the way the argument parser reports its own: exit status
  2, and on the error stream the usage line of `MM compare` followed by a last line `MM compare: error: <reason>`
  with the exact reason. For the two `--pairs` cases the pairs file does not exist: the combination must be
  rejected before anything is read. Nothing but the line announcing the command may be printed on the output
  stream.
* **Unusable content of the pairs file**: a pairs file without any pair is not a mistake in the call. The
  command must end with exit status 1 and the message `MM compare: error: <reason given by read_pairs_file>`,
  without a traceback, i.e. as a `SystemExit` carrying exactly that message.

## Folders

* **`-d` must exist**: `check_dir` on a missing folder raises `argparse.ArgumentTypeError` (which the parser
  turns into a usage error) with the message `<folder> needs to be an existing directory`.
* **`-o` may be created** (`check_and_create`). Whether the user can be asked depends on whether standard input
  is a terminal, so the test replaces standard input by an object that claims to be one or not:
  * *not a terminal*: nobody can answer a question, and waiting for an answer would block a script or a
    scheduled job for ever. The missing folder must exist afterwards, the function must return its path, the
    question must not have been asked (asking raises in the test), and one message at info level must say that
    the folder was created.
  * *terminal, answer `y`*: the question `<folder> does not exist. Create? (y|n)` must have been asked exactly
    once with exactly this text, the folder must exist afterwards, and its path is returned.
  * *terminal, answer `n`*: the same question, then `argparse.ArgumentTypeError` with the message
    `<folder> needs to be an existing directory.`, and the folder must still not exist.
  * *existing folder*: returned as it is, without a question, whatever standard input is.
  * *end to end*: the `--pairs` run described under "Output files" is given an output folder that does not exist
    while standard input is not a terminal; that it finds its three files there proves that the command as a
    whole runs unattended.
