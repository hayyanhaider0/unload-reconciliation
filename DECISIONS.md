# Decisions

## Tools

- Decided to use Python since it would allow me to easily normalize timestamps and weights.
- Used PostgreSQL to store the reconciled records and SQL to generate the report.
- Used Docker so the database could be set up without installing PostgreSQL manually.
- Decided to use a CLI instead of a frontend because I wanted to focus on the reconciliation logic.

## Reconciliation

- `trashed_at` only exists in the cloud data, so I will assume records can only be trashed on the cloud. There is a single source of truth for deletions, so there is no need to reconcile them.
- I tried to check online for error margins in Elmer's machines, but couldn't find anything. Other companies have a ±0.25%–1% margin, but I did not want to assume something sensitive like this. Weights should not be different after unit conversion anyway, so I decided to flag records with different weights unless the cloud had been updated later. I used a small rounding tolerance because of floating-point comparison issues.
- Controller-only records could be records that never made it to the cloud for whatever reason. Cloud-only records could have been manually created, or their controller counterpart could have been lost or never exported. I decided to flag both for manual review instead of assuming they are correct.
- I initially output my reconciled objects into a JSON file and sent the data into ChatGPT. It found two records that appeared identical but had different IDs. Same truck, field, crop, weight, and adjusted time. I initially flagged them as duplicates, but later realized that different controllers could have different clock settings. Without a controller ID, I cannot reliably determine whether these are duplicates, so I removed the check.
- All 4 unresolved weight mismatches differ by 470 kg. This could be a potential system issue, but I will flag them for manual review.
- After reconciliation, I check accepted unloads against truck capacity.
- Field ID `1682084f-1849-48df-bb8b-ebf1b3d4eced` doesn't exist in `fields.json` but is referenced by two unloads. I flag these records and preserve the original field ID.
- Removed the output JSON file and replaced it with direct imports into PostgreSQL running in Docker.
- Wrote an importer with the help of ChatGPT.
- Wrote 3 tests:
  - Check that every unique ID from both sources exists exactly once in the reconciled records.
  - Check that a newer cloud update overrides the controller weight.
  - Check that a newer controller update with a weight mismatch gets flagged.

## AI Bloopers

- Turned off GitHub Copilot after setting up the in-memory database because it kept suggesting the wrong things.
- ChatGPT asked me to normalize weights for the cloud instead of the controller because it thought the controller already had normalized weights. It doesn't. Cloud has `weight_kg`, while the controller has a weight and a separate unit.
- ChatGPT wanted me to check `field_id`, `truck_id`, and crop for differences. I checked the JSON files, and none of the matched records had those fields mismatched, so I decided not to check them. Though, I think for a better system, those checks might be necessary.
- ChatGPT suggested using a common clock offset to detect duplicate records with different IDs. I later realized this doesn't make sense if multiple controllers are used by different people who set their clocks differently. I removed the duplicate detection.

## Future Features That I Would Add

- Check unload weights against field area and expected crop yields.
- Check for unknown trucks.
- Allow multiple reasons for reconciliation decisions. Right now, a record can have a reason and a previous reason, but this doesn't cover every possible issue.
- Validate field, truck, and crop differences in matched records.
- Add controller IDs so I can properly identify which records came from which controller.
- Add a way to manually review and resolve flagged records.

## Review

- Test 1 failed because a later controller edit wasn't being used as a source of truth. Originally, I had this implemented, but removed it because I assumed that since the controller clock could potentially be incorrect, there was no way to tell whether the data is correct or not without manual review. I'm guessing the assumption here is that all unloads are coming from the same controller or that every controller has the same clock offset for some reason. There is evidence of this because all unloads on the controller are offset by -3600 compared to the cloud.
- I printed out the 2 records mentioned in the email and found out that they are certainly duplicates. In my previous iteration, I had a `find_duplicate()` function that was then removed because of the ambiguous clock offset. I assumed that if this data was coming from two different controllers, the same clock offset would only be a coincidence. 
- I replaced the `find_duplicate()` function. This is dataset specific, since this dataset has clock offsets of -3600 across the board.