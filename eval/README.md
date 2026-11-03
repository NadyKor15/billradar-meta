# How we measure BillRadar

We ask one thing: given a mixed pile of hospital bills and insurance statements, does BillRadar find more of what a family is owed than the same model does when it is simply asked?

Every path sees the same sheets and uses the same model, Muse Spark 1.3 on the Standard tier. Only what surrounds the model changes.

| Path | Given to the model |
|---|---|
| Simple prompt | Just the sheets and the question "Here are my hospital bills and insurance letters. Is anything wrong? Can I pay less?" |
| Strong prompt | Everything a prompt can carry and no code: the sheets, the full hospital policy, the federal rule on the application period, the household's numbers, the list of checks we run and our output schema. |
| BillRadar | The whole product: sheets cut by SAM 3.1 and read by Spark, checks in code against quoted policy rules, then a separate checker that works everything out again. |

A judge model matches the simple path's free-text answer to the key. That raw answer is stored beside its score.

## The packs

Packs live in `eval/packs/work/` and `eval/packs/holdout/`. A pack holds photos of fictional sheets on a table, each marked SAMPLE, any digital files, a `profile.json` with `"fictional": true`, and a `key.json`. The key lists what the pack really contains for each class (E1, E2, E3, E4, B1, P1, F1, F2, F3), with the sheets, amounts and dates.

- **Work packs** are used while building and tuning.
- **Holdout packs.** The final table counts only three packs, n1 to n3. A separate agent wrote them on Nov 2, 2026 from the sample generator. It did not open the pipeline code or the prompts, though it had the project notes in its context, and nobody looked at the answer keys before the run. Their key hashes went into `eval/SEALED.txt` before the run (commit 8973adc in our private working repository, Nov 3, 2026, 15:42 UTC), and scoring refuses a key that does not match. Five family roles the app does not offer (father, daughter, child) were set to "other" before the run; the keys were not touched. The six earlier holdout packs, h1 to h6, were run once on Nov 2. Two of them, h2 and h4, were then used to check how sheets are covered, so they no longer count as held out.

## What counts

For each class we count what was found (k of n), false findings, amounts off by more than $1, findings with no amount, and wrong deadlines. For the simple path we also count money claims the judge could not match to the key.

If the strong prompt catches up with BillRadar, that result gets published too.

## Where results go

Each run writes to `eval/results/<UTC time>/`. A run with no live model calls carries the label "REPLAYED (not a measurement)".
