# Berkshire EDA: computed findings

- Both continuation sheets are included without losing their first data row. Primary results retain flagged repeated rows; none of the original Excel files is written to.

- The study contains 69,176 filed charge rows, 65,492 disposed charge rows, and 22,380 bail events. Dates outside 1900–2026 are flagged, never repaired by guessing a century.

- Case volume changed -13.1% from 2017 to 2024. The class chart describes charges, not the share of defendants convicted or incarcerated.

- There are 1,120 literal descriptions and 914 charge codes in the filing window. The top 12 codes account for 36.6% of charge rows. Text variation and placeholder codes should not be interpreted as new criminal conduct.

- October has the most pooled charge rows. Compare the daily-adjusted panel before attributing this pattern to seasonality.

- Mean offense-to-initiation delay is 148.4 days; median 19; 90th percentile 97. 343 rows lack a usable offense date and 0 have negative intervals. Long valid intervals remain in the primary mean; the 10-year sensitivity is explicitly secondary.

- The highest-charge defendant ID has 82 recorded charge rows across 14 cases. The top 1% of defendant IDs account for 9.4% of filed charge rows.

- Both count and percentage charts are needed: a large count is not necessarily a high within-group share. No causal claim or population-adjusted racial/gender ranking is made.

- The most frequent raw label is Plea, covering 53.2% of disposed charge rows. Original type/description combinations remain available for client review rather than being overwritten.

- Among 34,870 Plea charge rows, 12,226 carry a CWOF sentence translation. Of those, 3,167 also have a positive actual-jail field and are quarantined as conflicts; 9,059 retain an unconflicted CWOF marker. 6,770 have an explicit custodial sentence translation; 7,882 meet the broader custody-marker rule. Neither rule proves physical time served. Case-level markers can overlap across different charges.

- A code with more dismissals may have different evidence, screening, or case mix. No underlying facts, prior-record measure, or original referral charge are available to explain the differences.

- Race is blank on 1.6% of the disposed criminal-charge population. Unknown/raw unverified codes remain explicit; complete-case-only comparisons are not substituted.

- Sex is blank on 0.2% of the disposed criminal-charge population. Unknown/raw unverified codes remain explicit; complete-case-only comparisons are not substituted.

- 4,340 criminal charge rows have a missing or explicitly nonjudge name (such as Clerk--No Judge) and are excluded from judge comparisons, with an audit table retained. The restricted comparison holds court and charge code (90/23/D) constant. Differences remain descriptive; the charts do not identify a judge effect. Source-name variants are not merged without verification.

- 5,005 of 65,492 disposed rows (7.6%) have disposition before initiation. The valid nonnegative charge-weighted median is 131 days. The chronology issue prevents treating the unfiltered mean as reliable.

- 22,380 bail events represent 17,576 case IDs. 42 cases have multiple events on their earliest observed date, so first-event ordering is uncertain for those cases. No actual payment or custody-duration conclusion is made.

- The largest first-event cash-related caseload is Assault & Battery. The median-amount chart applies the team coverage threshold within cash-related statuses, rather than across all recognizance/held events.

- Both amounts are recorded on 2,407 events (10.8% of all bail events). Set amounts are lower on 39.6% of those paired events. This is a selected-subset description; it is insufficient evidence for an all-hearings rate when coverage is poor.

- For 2,949 cases with a selected positive cash-related set amount, the median is $500. The largest 10% of selected amounts account for 84.6% of their sum. The selected-condition sum is $17,723,218; **actual money paid or received is not measurable from these data**.

- These charts describe recorded case experiences. They cannot distinguish differences in case severity, pretrial history, finances, or systemic decision-making. A detention disparity cannot be calculated from cash-bail status alone.

- 3,126 case IDs have bail/status records on different dates in the window. Endpoint changes describe the available records, not the duration or cause of detention. Cash-only and cash/surety counts are available separately for every recorded crime type.

- 54,553 of 68,769 unambiguous filed charge keys have a same-code, chronologically valid disposition recorded by the 2024 cutoff. 382 filed rows were quarantined for ambiguous keys. Matching does not justify dropping unmatched cases from all population-level conclusions.

- The linked view avoids multiplying bail events by charges and keeps coverage visible. Custody and CWOF case markers can coexist; they are not mutually exclusive final case judgments. The comparison cannot establish whether bail causes later outcomes.