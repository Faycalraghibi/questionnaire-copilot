# Evaluation Report

- Date: 2026-11-20
- Provider / Model: `openai` / `auto/fast`
- Thresholds (calibrated on A): `MIN_EVIDENCE=0.541`, `REUSE_THRESHOLD=0.92`

## Questionnaire A (calibration set, 60 questions)

| Metric | Value | Target |
| --- | --- | --- |
| Answer correctness | 84.6% | 90%+ |
| Citation correctness | 92.3% | 90%+ |
| Stale-version citations | 0 | 0 |
| Needs-input recall | 100.0% | 100% |
| Needs-input precision | 88.9% | 85%+ |
| Edit rate | 21.2% | report |
| Cost / Time | $0.0000 / 92.3s | report |

## Questionnaire B (held-out, 40 questions)

| Metric | Value | Target |
| --- | --- | --- |
| Answer correctness | 80.0% | 90%+ |
| Citation correctness | 100.0% | 90%+ |
| Stale-version citations | 0 | 0 |
| Needs-input recall | 100.0% | 100% |
| Needs-input precision | 100.0% | 85%+ |
| Reuse rate | 62.5% | report |
| Cost / Time | $0.0000 / 16.1s | report |

## Staleness Check (data-retention v4)

- Expected stale library entries: 4
- Flagged stale library entries: 4
- Staleness detection: 100.0% (target 100%)

## Failures

| Questionnaire | QID | Expected | Got | Reason |
| --- | --- | --- | --- | --- |
| acme_vendor_security_2026 | A-005 | yes (['hire', 'every year | annual']) | drafted: Employees and contractors complete security awareness training upon hire and annually thereafter. | short_answer='text' != 'yes' |
| acme_vendor_security_2026 | A-006 | yes (['24 hours']) | drafted: Access is revoked within 24 hours of an employee's departure. | short_answer='text' != 'yes' |
| acme_vendor_security_2026 | A-020 | yes (['twice']) | drafted: Disaster recovery is tested twice a year. | short_answer='text' != 'yes' |
| acme_vendor_security_2026 | A-025 | yes (['every year | annual']) | drafted: Critical vendors are assessed every year. | short_answer='text' != 'yes' |
| acme_vendor_security_2026 | A-026 | yes (['multi-factor']) | needs_input: None | status=needs_input; no citations |
| acme_vendor_security_2026 | A-035 | yes (['February 2026']) | drafted: An independent penetration test is performed annually by an external firm, with the most recent test occurring in February 2026. | short_answer='text' != 'yes' |
| acme_vendor_security_2026 | A-039 | yes (['hire']) | drafted: yes | extra citation outside truth: [('hr-security', 1, 'End of employment')] |
| acme_vendor_security_2026 | A-041 | yes (['NDA']) | drafted: yes | missing key phrase: NDA |
| acme_vendor_security_2026 | A-053 | yes (['AES-256']) | drafted: yes | extra citation outside truth: [('business-continuity', 1, 'Hosting')] |
| acme_vendor_security_2026 | A-055 | yes (['once a year | annual']) | drafted: All security policies are reviewed at least once a year. | short_answer='all security policies are reviewed at least once a year.' != 'yes' |
| acme_vendor_security_2026 | A-059 | yes (['24/7']) | drafted: yes | extra citation outside truth: [('incident-response', 1, 'On-call'), ('logging-monitoring', 1, 'Alerting')] |
| globex_supplier_review | B-005 | yes (['4 hours']) | drafted: Production admin access is granted just in time for up to four hours with approval from a second platform team engineer. | short_answer='production admin access is granted just in time for up to four hours with approval from a second platform team engineer.' != 'yes' |
| globex_supplier_review | B-006 | yes (['12 months']) | drafted: Encryption keys are rotated every 12 months. | short_answer='encryption keys are rotated every 12 months.' != 'yes' |
| globex_supplier_review | B-010 | yes (['tabletop']) | drafted: The incident response plan is tested annually using a tabletop exercise. | short_answer='the incident response plan is tested annually using a tabletop exercise.' != 'yes' |
| globex_supplier_review | B-018 | yes (['1 year | one year | 12 months']) | drafted: Security logs are retained for a period of 1 year. | short_answer='security logs are retained for a period of 1 year.' != 'yes' |
| globex_supplier_review | B-024 | yes (['eu-central-1 | Frankfurt']) | drafted: Encrypted backups are stored in AWS eu-central-1 (Frankfurt) in a separate account with restricted access. | short_answer='encrypted backups are stored in aws eu-central-1 (frankfurt) in a separate account with restricted access.' != 'yes' |
| globex_supplier_review | B-026 | yes (['EU']) | drafted: no | short_answer='no' != 'yes' |
| globex_supplier_review | B-027 | yes (['30 days']) | drafted: Customer data is deleted within 30 days after the end of the contract. | short_answer='customer data is deleted within 30 days after the end of the contract.' != 'yes' |
