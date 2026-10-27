# CIP final canary authorization — closed

Date: 2026-10-27  
State: **APPROVED, EXECUTED, PASSED**

The owner approved the final controlled read-only survey-238 canary. It ran in
an isolated process with one worker and one TLS staging connection. It did not
run the publisher CLI, ETL, cache warming, backups, notifications or any live
publication/service operation.

Base-HEAD and patched payloads were generated from the same staging state and
matched exactly for all available question cuts, respondent bitsets, book rows,
bases, unweighted values, canonical hashes and publisher-contract bytes. Survey
238 contains no non-unit weighted output and no populated demographic bitsets;
those paths remain covered by the full regression suite rather than claimed as
canary measurements.

Evidence:
[FINAL_SURVEY_238_CANARY_RESULTS.json](cip_staging_verification/evidence/FINAL_SURVEY_238_CANARY_RESULTS.json)  
SHA-256: `5ae5a6836c84f60593245ec9cc1c9f2f5156a00e6f5d1611f1466e051cf2defe`

No further routine SQL approval is requested. Deployment remains a separate
release-owner action; exact commands and rollback are in
[CIP_FINAL_CONSOLIDATED_RESULT.md](CIP_FINAL_CONSOLIDATED_RESULT.md).
