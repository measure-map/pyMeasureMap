# Layered comparison on real chorales

These tests check `pymeasuremap.compare.compare_layered()` (and `unfold()`, `compare_pairs()`) on measure maps
of real scores. They complement `tests/test_compare_layered.py`, which uses small synthetic measure maps.

The examples come from the alignment of the 389 Choralgesänge (Breitkopf, typeset by Gertim Alberda) with the
three Riemenschneider datasets in [aligned_bach_chorales](https://github.com/measure-map/aligned_bach_chorales)
(notebook `code/05_align_389_chorale_settings.py`). In that notebook, the 389 are always the `preferred` side and a
Riemenschneider dataset is the `other` side. The tests do the same.

Five settings from the 389 are enough to produce every verdict that real pairs can have (`same_count` needs measure
maps without any field in common and is tested in `tests/test_compare_layered.py`) and the alignment operations
match, split, join, insert, change_length and change_time_signature.

## Fixtures

`fixtures/` contains unmodified copies of the measure maps from aligned_bach_chorales (only a final newline was
added):

| fixture         | source in aligned_bach_chorales                                     |
|-----------------|----------------------------------------------------------------------|
| `B006`, `B015`, `B072`, `B205`, `B329` | `data/389_chorale_settings/measuremaps/B###.mm.json` (converted from the ms3 measures tables of the 389, tag v2.4) |
| `krn_R087`, `krn_R179`, `krn_R253`, `krn_R327`, `krn_R359` | `data/craigsapp_krn/measuremaps/chor###.mm.json` |
| `cap_R087`, `cap_R359` | `data/DCMLab_cap/measuremaps/086 Du, o schönes Weltgebäude.mm.json`, `…/358 Allein zu dir, Herr Jesu Christ.mm.json` |
| `xml_R087`      | `data/MarkGotham_xml/measuremaps/087.mm.json`                         |

`R###` is the Riemenschneider number. The `(B###, R###)` pairs come from `concordance_389.csv`, and all of them are
confirmed by matching metadata and pitch-class vectors.

### Fixtures at a glance

Every measure is shown by its `count`. The actual length is given in parentheses when it is not 4 quarters, and
repeat signs are shown as `|:` and `:|`. The last column gives the first and last measure `number`.

| fixture    | measures | time sig. | measures (count, actual length, repeats)                                                    | numbers |
|------------|---------:|-----------|---------------------------------------------------------------------------------------------|---------|
| `B006`     | 19 | 4/4 | 1(1q) 2 3 4 5 6 7 8 9 10 11(3q) 12(1q) 13 14 15 16 17 18 19(3q) | 0…17 |
| `krn_R253` | 18 | 4/4 | 1(1q) 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18(3q) | 1…18 |
| `B015`     | 22 | 4/4 | 1(1q) 2 3 4 5 6 7 8(3q):\| 9(1q) 10 11 12 13(2q) 14 15 16 17 18 19 20 21 22(3q) | 0…20 |
| `cap_R359` | 22 | 4/4 | 1(1q) 2 3 4 5 6 7 8(3q):\| 9(1q) 10 11 12 13(2q) 14 15 16 17 18 19 20 21 22(3q) | 1…22 |
| `krn_R359` | 21 | 4/4 | 1(1q) 2 3 4 5 6 7 8(3q):\| 9(1q) 10 11 12 13 14 15 16 17 18 19 20 21 | 1…21 |
| `B072`     | 13 | 4/4 | 1 2 3 4 5 6:\| \|:7 8 9:\| 10 11 12 13 | 1…13 |
| `cap_R087` | 13 | 4/4 | 1 2 3 4 5 6:\| \|:7 8 9:\| 10 11 12 13 | 1…13 |
| `xml_R087` | 13 | 4/4 | 1(5q) 2 3 4(5q) 5 6:\| \|:7 8 9:\| 10 11 12 13 | 1…13 |
| `krn_R087` | 16 | 4/4 | 1 2 3 4 5 6:\| 7 8 9 10 11 12 13 14 15 16 | 1…16 |
| `B205`     | 24 | 4/4 | 1(1q) 2 3 4 5 6 7 8 9(3q):\| 10(1q) 11 12 13 14(3q) \|:15(1q) 16 17 18 19(3q):\| 20(1q) 21 22 23 24(3q) | 0…20 |
| `krn_R327` | 22 | 4/4 | 1(1q) 2 3 4 5 6 7 8 9(3q):\| 10(1q) 11 12(3q):\| 13(1q) 14 15 16 17(3q):\| 18(1q) 19 20 21 22(3q) | 1…22 |
| `B329`     | 36 | 2/2 | 1 2 … 16:\| 17 18 … 36 | 1…36 |
| `krn_R179` | 18 | 4/4 | 1 2 3 4 5 6 7 8(3q):\| 9(1q) 10 11 12 13 14 15 16 17 18 | 1…18 |

Two conventions explain most of the differences:

* **Numbering.** The 389 follow ms3's `mn`: an anacrusis gets number 0, and the two parts of a measure that is split
  by a repeat sign share one number (e.g. B015 counts 8 and 9 are both measure 7). `krn` and `cap` number every
  measure object consecutively from 1.
* **Repeats.** The `next` fields encode the play-through. Where a `:|` has no matching `|:`, the repeat goes back to
  the previous `:|` or to the beginning.

## Expected verdicts (`expected_verdicts.tsv`)

The table lists one pair for each verdict, with a short reason in the column `case`. Only the alignable verdict has
two pairs, one for a split and one for a join. `test_verdict` checks each row, `test_every_verdict_is_covered`
makes sure that the table contains every value of `pymeasuremap.compare.VERDICTS` except `same_count`, and
`test_compare_pairs_reproduces_the_table` runs all rows through `compare_pairs()`. That last test checks the
summary table and that it writes reports for every non-identical pair, and only for those.

## What the tests check, and how

### 2. Unfolding (`unfold()`)

The expected play-throughs can be read off the overview above:

* `B072`: `|: 1–6 :| |: 7–9 :| 10–13` → 1–6, 1–6, 7–9, 7–9, 10–13 (22 measures).
* `krn_R087`: `|: 1–6 :| 7–16` → 1–6, 1–16 (22 measures). krn writes the second repeat out as counts 10–12.
* `B205`: `1–9 :| 10–14 |: 15–19 :| 20–24` → 1–9, 1–19, 15–24 (38 measures). This checks that the split measures at
  the repeat signs (9+10, 14+15, 19+20) don't confuse the unfolding.

All fixtures specify `next`, so the tests above follow it. `test_unfold_from_repeat_signs_agrees_with_next` removes
`next` from every fixture and requires the same play-through, which then has to be inferred from the repeat signs
alone. `next` is the stated truth here, and the fixtures include a `:|` without a matching `|:` (B015, B205) and
measures split at repeat signs (B205).

### 3. Layers in detail

| test | pair | what it makes sure | why the expected values are right |
|------|------|--------------------|-----------------------------------|
| `test_identical_B072_cap` | B072 / cap_R087 | Identical maps pass layers 1 and 2. Layers 3 and 4 are skipped. A field that is undefined on both sides (`volta`) is listed as `undefined` and doesn't count as a difference. | The two fixture files are byte-identical. Both come from MuseScore files converted with ms3 in the same way. |
| `test_number_offsets_B015_cap` | B015 / cap_R359 | When only the numbering differs, the verdict is `same_measures` and the offset is reported as segments, here `+1 in 1–8, +2 in 9–22`. No single `number_offset` is reported, because the offset isn't constant, and `name` isn't reported because the names only mirror the numbers. | The anacrusis gives +1 from the start. The split measure 7 (counts 8/9) adds another +1 from count 9 onwards. |
| `test_length_differences_B072_xml` | B072 / xml_R087 | Length differences are reported per measure. qstamp differences that follow from earlier length differences are filtered out (`qstamp_explained_by_lengths`), and the alignment names the two `change_length`s. | xml_R087 encodes measures 1 and 4 with 5 quarters, so every qstamp from count 2 onwards is shifted by 1q, and from count 5 by 2q. |
| `test_written_out_repeat_B072_krn` | B072 / krn_R087 | Different measure counts (13 vs 16) that are the same once unfolded (22 each) give the verdict `same_when_unfolded`. The message says which side writes out the repeat, and no alignment is attempted. | See the unfolding tests above. |
| `test_split_B006_krn` | B006 / krn_R253 | A measure that the 389 split into two counts that add up to one measure of the other side is a single `split`, not an insert plus a length change. Neither side has repeats, so the unfolding layer is skipped. | Count 11 (3q) + count 12 (1q) in B006 corresponds to krn count 11 (4q), and the total duration is 68q on both sides. |
| `test_join_across_repeats_B205_krn` | B205 / krn_R327 | When the repeat structures differ, the unfolded sequences are aligned, and a `join` can bridge a repeat sign. | krn repeats 10–12 and 13–17, while B205 writes the first of these repeats out (10–14, 16q = 2 × (1+4+3)q) and repeats 15–19. Unfolded, krn has the 3q end of the repeated section (count 12) followed by the 1q pickup (count 10) where B205 has the full 4q count 12. |
| `test_different_B015_krn` | B015 / krn_R359 | A real difference in content gives `different`, with an `insert` for the missing measure and a `change_length` for the last measure. | krn_R359 has no counterpart of B015's 2q measure (count 13), and its final measure has 4q instead of 3q. cap_R359, on the other hand, is `same_measures` with B015, so this difference belongs to the krn encoding. |
| `test_compressed_map_is_identical_B015` | B015 / B015 compressed | A compressed map is decompressed before it is compared, so it is `identical` to the map it was made from, with all 22 measures and every field but `volta` compared. | Compression only omits entries that can be restored from their predecessor, so both describe the same 22 measures. B015 has an anacrusis, a split measure and a repeat, so several entries have to be kept and several can be omitted. |

### 4. Time signatures and the measure table

* `test_time_signature_mismatch_is_not_a_length_change_B329_krn`: B329 notates *Wachet auf* in 2/2 with twice as
  many measures as krn_R179 (4/4), and with doubled note values (144q against 68q). Where a measure of one is
  paired with a measure of the other, both have 4q, so the difference has to be reported as
  `change_time_signature` (16 times) and never as `change_length`. That the two encode the same music at
  different note values is not recognized: the verdict stays `different`.
* `test_measure_table_follows_the_play_throughs_B072_krn`: for `same_when_unfolded` there is no alignment, and
  pairing the measures by position would drop the 3 measures that krn writes out. The table therefore follows the
  two play-throughs (22 rows, see the unfolding tests above): krn counts 10–12 have to appear next to the second
  pass of B072 counts 7–9, and no row may differ in length or time signature.

## Running

```bash
pytest tests/compare_layered_chorales
```

The tests need only the fixtures in this folder, not a clone of aligned_bach_chorales.
