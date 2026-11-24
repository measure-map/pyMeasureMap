# Tests of the layered comparison (`tests/test_compare_layered.py`)

These tests check `pymeasuremap.compare` (`unfold()`, `align_measure_sequences()`, `compare_layered()`,
`compare_pairs()`, `ComparisonReport`) and the measure lengths in `pymeasuremap.base` they rely on, using small
synthetic measure maps. Tests on measure maps of real scores are in `tests/compare_layered_chorales/` and have their
own README.

This document states, for each group of tests, which input proves the behaviour and why the expected value is the
right one. The expected values follow from the definitions of the MeasureMap fields and from how the music would be
played or counted. Where a result is a convention of the implementation and not a musical necessity, this is said
explicitly.

Notation: measures are written by their `count`. `|:` and `:|` are `start_repeat` and `end_repeat`, `[1.` and `[2.`
are `volta` 1 and 2, and a length such as `3q` is an `actual_length` of three quarter notes. Unless stated otherwise,
the helper `make_mm(lengths)` builds a map in 4/4 with counts and numbers 1, 2, 3, … and qstamps accumulated from the
lengths.

## 1. Length of a measure

`actual_length` is the duration of a measure in quarter notes. When a map does not state it, the measure is assumed to
be complete, so its length is the `nominal_length`; when that is not stated either, the nominal length is the one the
time signature implies (numerator / denominator × 4 quarters). A measure that states none of the three has no known
length, and neither has one whose time signature is not a fraction.

| test | input | expected | why |
|------|-------|----------|-----|
| `test_length_from_nominal_length_only` | `Measure(count=1, nominal_length=3.0)` | `get_actual_length()` and `get_nominal_length()` are both `3.0` | Nothing says the measure is incomplete, so it lasts as long as its nominal length. |
| `test_length_from_time_signature_only` | `Measure(count=1, time_signature="3/4")` | both `3.0` | Three quarter notes. |
| `test_length_stated_wins` | `Measure(count=1, time_signature="4/4", nominal_length=4.0, actual_length=1.0)` | `get_actual_length()` is `1.0`, `get_nominal_length()` is `4.0` | An anacrusis: the stated actual length is the only information about its real duration. |
| `test_length_unknown_without_length_fields` | `Measure(count=1)` | both raise `ValueError` | There is nothing to derive a length from. |
| `test_length_unknown_for_time_signature_that_is_no_fraction` | `Measure(count=1, time_signature="C")` and `"4/0"` | both raise `ValueError` whose message contains the value (`'C'`, `'4/0'`) | "C" (common time) and a zero denominator do not denote a fraction. The caller must be able to tell an unknown length (`ValueError`) from a programming error, so no other exception type may escape. |
| `test_compare_uses_nominal_length_as_length` | a map with counts 1, 2 and `nominal_length` 3, 3 against a map with counts 1, 2 and `actual_length` 3, 3 | verdict `identical`; the compared fields are exactly `["actual_length"]`; `nominal_length` is among the undefined fields; both durations are 6 | Both maps describe two measures of three quarters. The lengths are therefore comparable and equal. The raw field `nominal_length` exists on one side only and cannot be compared. Before lengths were derived from `nominal_length`, the first map counted as having no lengths and the verdict was `same_count`. |

## 2. Unfolding

`unfold()` returns the counts in the order in which the measures are played.

### From repeat signs and endings

| test | input | expected | why |
|------|-------|----------|-----|
| `test_unfold_infers_repeats` | `\|: 1 2 :\| 3 4` | 1 2 1 2 3 4 | A repeated section is played twice. |
| `test_unfold_infers_voltas` | `\|: 1 [1. 2 :\| [2. 3 \| 4` | 1 2 1 3 4 | The first ending is played in the first pass only, the second in the second. |
| `test_unfold_second_ending_of_two_measures` | `\|: 1 [1. 2 3 :\| [2. 4 5 \| 6` | 1 2 3 1 4 5 6 | Every measure of an ending belongs to its pass, not only the first one. |
| `test_unfold_three_endings` | `\|: 1 [1. 2 :\| [2. 3 :\| [3. 4 \| 5` | 1 2 1 3 1 4 5 | Three endings mean three passes. |
| `test_unfold_two_repeated_sections_with_endings` | `\|: 1 [1. 2 :\| [2. 3 \|: 4 [1. 5 :\| [2. 6 \| 7` | 1 2 1 3 4 5 4 6 7 | The pass counter starts anew for the second section. |
| `test_unfold_end_repeat_without_start_repeat` | `1 2 :\| 3 4 :\|` | 1 2 1 2 3 4 3 4 | By convention, a `:\|` without a `\|:` goes back to the previous `:\|` or to the beginning. |
| `test_unfold_adjacent_repeated_sections` | `\|: 1 2 :\|\|: 3 4 :\| 5` | 1 2 1 2 3 4 3 4 5 | The `\|:` right after a `:\|` opens a new section; the second `:\|` must go back to it, not to the beginning. |
| `test_unfold_endings_without_end_repeat_warn` | `1 [1. 2 [2. 3 \| 4` without any repeat sign | 1 2 4 and a warning | Without a `:\|` nothing sends the player back, so the second ending is never reached. This is most likely an encoding error, hence the warning. |
| `test_unfold_nested_repeats_are_not_supported` | `\|: 1 \|: 2 :\| 3 :\|` | 1 2 2 3 3 | **Not the musical reading.** A musician would play 1 2 2 3 1 2 2 3. The inference keeps track of one repeated section at a time: the inner `\|:` replaces the outer one as the place to go back to, so measure 2 is repeated, and the final `:\|` then finds no open section and goes back to the measure after the previous `:\|`, which is measure 3 itself. The test pins this result so that a change does not go unnoticed; nested repeats have to be encoded with `next`. |

### From `next`

| test | input | expected | why |
|------|-------|----------|-----|
| `test_unfold_with_next_and_voltas` | `next` of the four measures: `[2, 3]`, `[1]`, `[4]`, `[-1]` | 1 2 1 3 4 | The k-th visit of a measure continues with the k-th element of its `next`: measure 1 goes to 2 first and to 3 the second time. |
| `test_unfold_next_with_ids_unknown_targets_and_loops` | (1) IDs a, b, c with `next` `["b"]`, `["a", "c"]`, `[]`; (2) a `next` pointing to count 99; (3) two measures pointing to each other | (1) 1 2 1 2 3; (2) 1 2 and a warning; (3) 1 2 ten times and a warning | (1) `next` may refer to IDs, and an empty list on the last measure ends the piece. (2) A target that does not exist cannot be played, so the play-through ends there. (3) Such a piece never ends; the result is cut off after ten times the number of measures (the default `max_factor`). |
| `test_unfold_next_on_some_measures_ignores_repeat_signs` | `\|: 1`, `2 :\|`, `3` with `next: [-1]` | 1 2 3 and a warning that says which signs are ignored | As soon as one measure has `next`, the map is taken to encode its play-through with `next`, and measures without it simply continue with the following count. The repeat signs on measures 1 and 2 are therefore not played, although a reader of the map would expect 1 2 1 2 3. The result is a rule of the implementation; the warning is what makes it visible. |
| `test_unfold_next_on_every_measure_does_not_warn` | the map of `test_unfold_with_next_and_voltas` plus repeat signs | 1 2 1 3 4, no warning | Every measure states its successors, so no sign is left uninterpreted. |
| `test_unfold_next_without_other_signs_does_not_warn` | three measures, the last with `next: [-1]`, no repeat signs or voltas | 1 2 3, no warning | Nothing is ignored. |

## 3. Layers and verdicts

| test | input | expected | why |
|------|-------|----------|-----|
| `test_identical` | twice `[1q, 4q, 3q]` | `identical`, unfolding skipped | Same maps; without repeats there is nothing to unfold. |
| `test_same_measures_with_number_offset` | `[1q, 4q, 3q]` numbered 0–2 against 1–3 | `same_measures`, `number_offset` 1, only `number` differs | An anacrusis numbered 0 against consecutive numbering from 1: the measures are the same, the numbering is not. |
| `test_qstamp_differences_explained_by_lengths_are_not_reported` | `[4, 4, 4]` against `[4, 3, 4]` | `same_count_different_measures`; only `actual_length` differs; the qstamp of measure 3 is listed as explained | Measure 3 starts at 8 against 7 only because measure 2 is one quarter shorter. Reporting the qstamp as well would count one difference twice. |
| `test_same_when_unfolded` | `\|: 1 2 :\| 3 4` against six measures | `same_when_unfolded`, no alignment | 2 × 2 + 2 = 6 measures of 4q on both sides once the repeat is written out. |
| `test_alignable_by_split` | `[1q, 3q, 4q]` against `[4q, 4q]` | `alignable`: split, match | 1q + 3q make up the first 4q measure. |
| `test_different` | `[4, 4, 2, 4]` against `[4, 4, 4]` | `different`, one insert | The 2q measure has no counterpart and the totals differ (14q, 12q). |
| `test_same_count_when_no_field_is_defined_on_both_sides` | a full map against counts only | `same_count` | Nothing but the number of measures could be compared, and the verdict must not claim more. |
| `test_summary_lists_what_was_compared` | a full map against a map with numbers only | `identical`, with `number` as the only compared field and the nine others listed as undefined | The verdict has to say what it rests on. |
| `test_unfolded_without_lengths_says_what_it_rests_on` | `\|: 1 2 :\| 3 4` against six bare counts | `same_when_unfolded` with the caveat in the message | Only the numbers of measures agree (6 = 6). |
| `test_lengths_on_one_side_only` | lengths against no lengths, with 4 and with 3 measures | `identical`; with 3 measures `different` with one insert and no change of length | A measure without a length is not different from one with a length; a missing measure is still missing. |
| `test_count_mismatch_without_lengths` | numbers 1–5 against 1–4, no lengths | insert of preferred 5; the report files are written | See section 4, placement by numbers. |
| `test_fields_argument` | `[4, 4]` against `[4, 2]` with `fields=["number"]`; an unknown field name | `same_count_different_measures`; `ValueError` | Lengths and time signatures decide the verdict whatever fields are requested. |
| `test_no_unfolding_without_repeats` | `[4, 4]` against `[2, 2, 4]` | unfolding skipped, alignment of the folded sequences, `alignable` | Neither side has repeats; 2q + 2q = 4q is a join. |
| `test_change_of_time_signature_is_not_a_change_of_length` | 4/4 against 2/2, all measures 4q | two `change_time_signature`, no `change_length` | Both measures last four quarters; what differs is the metre. |
| `test_alignment_with_joins_and_splits_only_is_preferred` | `1q \|: 2q :\| 3q` against `3q 2q 1q` | `alignable` on the folded sequences: split (1+2 → 1), join (3 ← 2+3) | Folded, 1 + 2 = 3 and 3 = 2 + 1. Unfolded, the preferred side has 8q against 6q, which cannot be aligned without a change. `alignable` is defined as "joins and splits suffice", so the folded alignment counts. |

### The summary and the text of a report

`summary()` is asserted as a whole dictionary for one report of each of three verdicts, and `to_text()` as a whole
text for one report. The keys are those documented in `ComparisonReport.summary()`; the values follow from the
inputs:

* `test_summary_of_identical_maps`: twice `[1q, 4q, 3q]`. 3 measures and 8q on both sides. `make_mm` defines
  `qstamp`, `number`, `time_signature` and `actual_length`, which are the compared fields (in the order of
  `LAYERED_FIELDS`); the other six fields are undefined on both sides. Nothing differs, there is no constant number
  offset to report, nothing was unfolded (no repeats) and no alignment was computed, so those keys are `None`.
* `test_summary_of_same_measures`: the same lengths, numbered 0–2 against 1–3. As before, except that `number`
  differs, by +1 in all three measures (counts 1–3).
* `test_summary_of_alignable_maps`: `[1q, 3q, 4q]` against `[4q, 4q]`. 3 against 2 measures, 8q each. The numbers
  of measures differ, so no field was compared measure by measure (three empty strings). The alignment consists of
  one split and one match, so `n_split` is 1 and the five other operation counts are 0, not `None`.
* `test_text_of_a_different_report`: `[4, 4, 2, 4]` (14q) against `[4, 4, 4]` (12q), named `a` and `b`. The first
  line names both sides and the verdict in capitals. Then one line per layer follows, with its status: the count
  layer differs (4 against 3 measures), the field and unfolding layers are skipped (unequal counts, no repeats) and
  have no message, the alignment needs one insert. The only step that is not a match is listed: preferred 3 (2q) has
  no counterpart.

## 4. Alignment (`align_measure_sequences()`)

The alignment turns the other sequence into the preferred one at the lowest cost. With the default costs, a match is
free, a join or split costs 0.5, and an insert, a delete or a change costs 1 each.

| test | input (count, length) | expected | why |
|------|-----------------------|----------|-----|
| `test_align_measure_sequences_join` | preferred `4q`; other `1q, 3q` | one join of other 1+2 | 1 + 3 = 4. A join (0.5) is cheaper than a change plus a delete (2). |
| `test_align_measure_sequences_delete` | preferred `4q, 3q`; other `4q, 2q, 3q` | match, delete of other 2, match | The 2q measure is surplus; deleting it (1) is cheaper than anything that pairs it. |
| `test_split_at_the_end_of_a_sequence` | preferred `4q, 3q, 1q`; other `4q, 4q` | match, split of other 2 into preferred 2+3 | 3 + 1 = 4. A split takes two preferred measures at once and must also work when they are the last two. |
| `test_change_is_kept_when_insert_and_delete_cost_the_same` | preferred `4q`; other `3q`; `change_cost=2.0` (with `gap_cost=1.0`) | one `change_length`; with the default `change_cost=1.0` likewise | With these parameters, changing the measure (2) costs exactly as much as deleting the other measure and inserting the preferred one (1 + 1). Both describe the data equally well. The function then reports the single change, because the pairing of two measures is considered before gaps and a later alternative replaces an earlier one only when it is strictly better. One step for one measure is also the simpler description. With the default costs the question does not arise: a change (1) is cheaper than insert plus delete (2). |

### Where a surplus measure is placed

When several alignments cost the same, the lengths do not say which measure is the surplus one: in a run of measures
of equal length, removing any one of them gives the same result. The measure numbers then decide. Two numberings of
the same music either agree (`other.number == preferred.number`) or differ by a constant offset, typically because
one side numbers an anacrusis 0 and the other 1. The function therefore counts the paired measures whose numbers
disagree *relative to an assumed offset* and tries up to three offsets, in this order: 0, the offset between the
first measures of the two sequences, and the offset between their last measures. It keeps the alignment with the
lowest (cost, number of disagreeing pairs); if two offsets are equally good, the earlier one wins. Equal numbers are
the strongest evidence and are therefore tried first.

| test | input | expected | why |
|------|-------|----------|-----|
| `test_missing_measure_is_located_by_number` | five 4q measures numbered 1–5 against four numbered 1, 2, 4, 5 | insert of preferred 3 | Number 3 is the one without counterpart. With offset 0 this alignment has no disagreeing pair; every other placement has at least one. |
| `test_count_mismatch_without_lengths` | numbers 1–5 against 1–4, no lengths | insert of preferred 5 | Number 5 has no counterpart. |
| `test_align_measure_sequences_prefers_equal_numbers` | numbers 10, 11, 12 against 11, 12, no lengths | insert of preferred 1 (number 10) | Pairing 11 with 11 and 12 with 12 leaves no disagreement at offset 0, which is tried first. Reading the other side as "the first two measures, renumbered by +1" is equally consistent but assumes more. |
| `test_surplus_measure_is_located_by_number_after_an_anacrusis` | preferred `1q, 4q, 4q, 4q, 4q, 3q` numbered 0–5; other `1q, 4q, 4q, 4q, 3q` numbered 0, 1, 2, 3, 5 | match ×4, insert of preferred 5 (number 4), match of preferred 6 with other 5 | The other side lacks number 4 and kept its numbering. The lengths allow any of the four 4q measures (counts 2–5) to be the surplus one; only for count 5 do all paired numbers agree. |
| `test_surplus_measure_is_located_when_numbers_are_offset_throughout` | the same preferred; other numbered 1, 2, 3, 4, 6 | the same alignment | The other side numbers from 1, i.e. every number is one higher, and its numbers jump from 4 to 6: it lacks its number 5, which is preferred number 4, count 5. At offset 0 the best placement is preferred count 2 with two disagreeing pairs (0 with 1, and 5 with 6); at offset +1, found from the first measures, placing the insert at count 5 leaves none. Comparing the numbers for equality only would put the insert at count 2, the wrong place. |
| `test_position_among_equal_measures_is_arbitrary_when_other_is_renumbered` | five 4q measures numbered 1–5; four 4q measures numbered 1–4 | match ×4, insert of preferred 5 | **Arbitrary.** The other side was renumbered consecutively after losing a measure, so neither lengths nor numbers say which one it lost: every placement is consistent with some reading of the numbers (offset 0 up to the gap and −1 after it). The rule yields the placement with no disagreement at offset 0, which is the last measure. The test pins the result of the rule; it does not claim that the last measure is the missing one. |

Items may be passed as `(count, length, time_signature)` or `(count, length, time_signature, number)` tuples; both
forms occur in the tests above.

### Describing a step

`AlignmentStep.describe()` is the line a reader sees in the report, so a join or split has to show that the lengths
add up. `test_describe_join_and_split` asserts the whole texts:

* a split of other count 11 (4q) into preferred counts 11 (3q) and 12 (1q): `other 11 (4q) would need to be split to correspond to preferred 11+12 (3q+1q)`;
* a join of other counts 12 (3q) and 10 (1q) into preferred count 12 (4q), as it occurs between unfolded sequences
  where counts do not ascend: `other 12+10 (3q+1q) would need to be joined to correspond to preferred 12 (4q)`;
* a step that was built without lengths names the counts only:
  `other 1+2 would need to be joined to correspond to preferred 1`;
* a join computed by `align_measure_sequences()` for preferred `4q` against other `1q, 3q` carries its lengths:
  `other 1+2 (1q+3q) would need to be joined to correspond to preferred 1 (4q)`.

## 5. The measure table

| test | input | expected | why |
|------|-------|----------|-----|
| `test_measure_table_for_equal_counts` | `[1q, 4q, 3q]` numbered 0–2 against 1–3 | three `match` rows paired by position, each with `number` as the differing field; the first four columns are `operation`, `differing`, `preferred_count`, `other_count` | Equal numbers of measures without an alignment are paired by position. |
| `test_measure_table_follows_the_play_throughs` | `\|: 1 2 :\| 3 4` against six measures | preferred counts 1 2 1 2 3 4 next to other counts 1–6 | Pairing by position would drop two measures of the written-out side, so the rows follow the play-throughs. |
| `test_measure_table_joins_values_of_split_measures` | `[1q, 3q, 4q]` against `[4q, 4q]` | the first row shows `1.0+3.0` against `4.0` | A split occupies one row; the values of its two measures are joined by `+`. |

## 6. Batches (`compare_pairs()`)

| test | input | expected | why |
|------|-------|----------|-----|
| `test_compare_pairs_writes_outputs` | a `same_when_unfolded` pair and an identical pair | the summary lists both verdicts; a report is written for the first pair only | Identical pairs need no report. |
| `test_compare_pairs_keeps_equally_named_files_apart` | folders A and B, each with `preferred.mm.json` and `other.mm.json` | names `A/preferred.mm.json`, …; four report files with the folder in their names, plus the summary | Without the folder, the rows could not be told apart and the second report would overwrite the first. |
| `test_compare_pairs_numbers_colliding_report_files` | two pairs with the same names | `x_vs_y` and `x_vs_y_2` | No report may be overwritten. |
| `test_compare_pairs_names_and_errors` | one name pair for two pairs; a missing file | `ValueError`; verdict `error` and `None` in place of the report, the other pair unaffected | One unreadable file must not abort a batch. |
| `test_compare_pairs_continues_when_a_report_cannot_be_written` | two non-identical pairs named x/y and p/q; `x_vs_y.tsv` exists as a directory in the output directory | both verdicts are in the returned summary; the first row's `output_error` is the representation of the error the operating system raises when that path is opened for writing, the second row's is empty; `p_vs_q.tsv`, `p_vs_q.txt` and `comparison_summary.tsv` are written, and the summary file has the same `output_error` column; `x_vs_y.txt` is not written | A directory cannot be opened as a file, so writing the first table fails. The failure belongs to that pair alone: its row says why, and the remaining files are still written. The text file of the failed pair is written after the table, so it is not reached. The expected error text is taken from the operating system in the test itself, because it differs between platforms. |
