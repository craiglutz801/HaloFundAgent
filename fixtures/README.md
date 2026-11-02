# Fixture companies

These six companies are fictional. `services/api/src/halo/services/seed.py` loads them into a database whose name contains `fixture`. The seed is idempotent. `make reset-fixtures` truncates that database and loads it again. The command refuses a database whose name omits `fixture`, contains `live`, or holds an organization with mode `live`.

| Company | Stage | What the fixture shows |
|---|---|---|
| Northline | discovered | Scout shortlist. Growth evidence is null. |
| Sideline | first_look | A sourced company waiting on a diligence open. |
| Atlas | diligence | Workbook sheet `Cohort Retention` cells `D14:D20` (dollar GRR 84.1%) and a board-deck page 14 capture that says 92% with no definition. Two open blocking concerns. Xavier leaves EX and BX unscored. Mutombo's independent pass is not sealed. |
| Vela | ic_review | Frozen packet with a sealed Mutombo dissent. No IC decision yet. Illustrative gross MOIC is labeled as not a forecast. |
| Rally | owned | Closed initial investment. Follow-on packet is frozen and waiting. Stockton records 18 tagged meetings as observed. Sloan records an 8 minute cycle against a 12 minute baseline. Capacity is 200 hours, estimated. Incremental revenue and cash savings are gaps. |
| Court | owned | The current quarterly report is missing. Health is unknown. One overdue notification goes to each of Sam Okonkwo and Jordan Hale. |

No fixture document is a real customer's file. The local object directory is `var/object-store` and is not committed.
