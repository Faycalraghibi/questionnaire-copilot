# Evaluation Report

- Date: 2026-11-18
- Provider / Model: `stub` / `stub`
- Thresholds (calibrated on A): `MIN_EVIDENCE=0.541`, `REUSE_THRESHOLD=0.92`

## Questionnaire A (calibration set, 60 questions)

| Metric | Value | Target |
| --- | --- | --- |
| Answer correctness | 7.7% | 90%+ |
| Citation correctness | 11.5% | 90%+ |
| Stale-version citations | 0 | 0 |
| Needs-input recall | 100.0% | 100% |
| Needs-input precision | 17.4% | 85%+ |
| Edit rate | 92.3% | report |
| Cost / Time | $0.0000 / 26.7s | report |

## Questionnaire B (held-out, 40 questions)

| Metric | Value | Target |
| --- | --- | --- |
| Answer correctness | 51.4% | 90%+ |
| Citation correctness | 71.4% | 90%+ |
| Stale-version citations | 0 | 0 |
| Needs-input recall | 100.0% | 100% |
| Needs-input precision | 35.7% | 85%+ |
| Reuse rate | 62.5% | report |
| Cost / Time | $0.0000 / 3.4s | report |

## Staleness Check (data-retention v4)

- Expected stale library entries: 4
- Flagged stale library entries: 4
- Staleness detection: 100.0% (target 100%)

## Failures

| Questionnaire | QID | Expected | Got | Reason |
| --- | --- | --- | --- | --- |
| acme_vendor_security_2026 | A-001 | yes (['AES-256']) | needs_input: None | status=needs_input; no citations |
| acme_vendor_security_2026 | A-002 | yes (['Head of Security']) | drafted: yes | missing key phrase: Head of Security; no truth source cited (got [('access-control', 1, 'Authentication')]) |
| acme_vendor_security_2026 | A-003 | text (['once a year | annual']) | needs_input: None | status=needs_input; no citations |
| acme_vendor_security_2026 | A-004 | text (['quarter']) | needs_input: None | status=needs_input; no citations |
| acme_vendor_security_2026 | A-005 | yes (['hire', 'every year | annual']) | needs_input: None | status=needs_input; no citations |
| acme_vendor_security_2026 | A-006 | yes (['24 hours']) | needs_input: None | status=needs_input; no citations |
| acme_vendor_security_2026 | A-007 | text (['just in time', '4 hours']) | drafted: yes | missing key phrase: just in time; no truth source cited (got [('access-control', 1, 'Authentication')]) |
| acme_vendor_security_2026 | A-008 | yes (['least privilege']) | needs_input: None | status=needs_input; no citations |
| acme_vendor_security_2026 | A-009 | text (['30 days']) | needs_input: None | status=needs_input; no citations |
| acme_vendor_security_2026 | A-010 | text (['TLS 1.2']) | needs_input: None | status=needs_input; no citations |
| acme_vendor_security_2026 | A-011 | text (['KMS']) | drafted: yes | missing key phrase: KMS; no truth source cited (got [('access-control', 1, 'Authentication')]) |
| acme_vendor_security_2026 | A-012 | text (['12 months']) | needs_input: None | status=needs_input; no citations |
| acme_vendor_security_2026 | A-013 | text (['35 days']) | needs_input: None | status=needs_input; no citations |
| acme_vendor_security_2026 | A-014 | text (['1 year | one year | 12 months']) | needs_input: None | status=needs_input; no citations |
| acme_vendor_security_2026 | A-016 | yes (['tabletop']) | needs_input: None | status=needs_input; no citations |
| acme_vendor_security_2026 | A-017 | text (['72 hours']) | needs_input: None | status=needs_input; no citations |
| acme_vendor_security_2026 | A-018 | yes (['24/7']) | needs_input: None | status=needs_input; no citations |
| acme_vendor_security_2026 | A-020 | yes (['twice']) | needs_input: None | status=needs_input; no citations |
| acme_vendor_security_2026 | A-021 | text (['4 hours', '8 hours']) | needs_input: None | status=needs_input; no citations |
| acme_vendor_security_2026 | A-023 | text (['AWS', 'eu-west-1 | Ireland']) | drafted: yes | missing key phrase: AWS; no truth source cited (got [('access-control', 1, 'Authentication')]) |
| acme_vendor_security_2026 | A-024 | text (['eu-central-1 | Frankfurt']) | needs_input: None | status=needs_input; no citations |
| acme_vendor_security_2026 | A-025 | yes (['every year | annual']) | needs_input: None | status=needs_input; no citations |
| acme_vendor_security_2026 | A-026 | yes (['multi-factor']) | needs_input: None | status=needs_input; no citations |
| acme_vendor_security_2026 | A-027 | yes (['website']) | drafted: yes | missing key phrase: website; no truth source cited (got [('access-control', 1, 'Authentication')]) |
| acme_vendor_security_2026 | A-028 | yes (['30 days']) | needs_input: None | status=needs_input; no citations |
| acme_vendor_security_2026 | A-029 | yes (['data processing agreement']) | needs_input: None | status=needs_input; no citations |
| acme_vendor_security_2026 | A-031 | yes (['second engineer']) | needs_input: None | status=needs_input; no citations |
| acme_vendor_security_2026 | A-032 | yes (['pull request']) | drafted: yes | missing key phrase: pull request; no truth source cited (got [('access-control', 1, 'Authentication')]) |
| acme_vendor_security_2026 | A-033 | yes (['quarter']) | needs_input: None | status=needs_input; no citations |
| acme_vendor_security_2026 | A-034 | text (['daily']) | needs_input: None | status=needs_input; no citations |
| acme_vendor_security_2026 | A-035 | yes (['February 2026']) | needs_input: None | status=needs_input; no citations |
| acme_vendor_security_2026 | A-037 | yes (['24/7']) | needs_input: None | status=needs_input; no citations |
| acme_vendor_security_2026 | A-038 | yes (['background check']) | needs_input: None | status=needs_input; no citations |
| acme_vendor_security_2026 | A-039 | yes (['hire']) | needs_input: None | status=needs_input; no citations |
| acme_vendor_security_2026 | A-040 | no (['2027']) | drafted: yes | short_answer='yes' != 'no'; no truth source cited (got [('access-control', 1, 'Authentication')]) |
| acme_vendor_security_2026 | A-041 | yes (['NDA']) | needs_input: None | status=needs_input; no citations |
| acme_vendor_security_2026 | A-043 | no (['EU']) | needs_input: None | status=needs_input; no citations |
| acme_vendor_security_2026 | A-044 | text (['EU']) | needs_input: None | status=needs_input; no citations |
| acme_vendor_security_2026 | A-045 | text (['CEO']) | needs_input: None | status=needs_input; no citations |
| acme_vendor_security_2026 | A-047 | yes (['availability zones']) | needs_input: None | status=needs_input; no citations |
| acme_vendor_security_2026 | A-048 | yes (['multi-factor']) | drafted: yes | missing key phrase: multi-factor |
| acme_vendor_security_2026 | A-049 | yes (['role-based']) | drafted: yes | missing key phrase: role-based; no truth source cited (got [('access-control', 1, 'Authentication')]) |
| acme_vendor_security_2026 | A-052 | yes (['1.2']) | needs_input: None | status=needs_input; no citations |
| acme_vendor_security_2026 | A-053 | yes (['AES-256']) | needs_input: None | status=needs_input; no citations |
| acme_vendor_security_2026 | A-054 | text (['30 days']) | needs_input: None | status=needs_input; no citations |
| acme_vendor_security_2026 | A-055 | yes (['once a year | annual']) | drafted: text | short_answer='text' != 'yes' |
| acme_vendor_security_2026 | A-058 | text (['once a year | annual']) | needs_input: None | status=needs_input; no citations |
| acme_vendor_security_2026 | A-059 | yes (['24/7']) | needs_input: None | status=needs_input; no citations |
| globex_supplier_review | B-002 | yes (['quarter']) | needs_input: None | status=needs_input; no citations |
| globex_supplier_review | B-004 | yes (['24 hours']) | drafted: yes | missing key phrase: 24 hours; no truth source cited (got [('access-control', 1, 'Authentication')]) |
| globex_supplier_review | B-005 | yes (['4 hours']) | drafted: text | short_answer='text' != 'yes' |
| globex_supplier_review | B-006 | yes (['12 months']) | drafted: text | short_answer='text' != 'yes' |
| globex_supplier_review | B-007 | yes (['TLS 1.2']) | needs_input: None | status=needs_input; no citations |
| globex_supplier_review | B-010 | yes (['tabletop']) | drafted: text | short_answer='text' != 'yes' |
| globex_supplier_review | B-011 | yes (['72 hours']) | needs_input: None | status=needs_input; no citations |
| globex_supplier_review | B-012 | yes (['24/7']) | needs_input: None | status=needs_input; no citations |
| globex_supplier_review | B-014 | yes (['4 hours']) | needs_input: None | status=needs_input; no citations |
| globex_supplier_review | B-016 | yes (['static analysis']) | needs_input: None | status=needs_input; no citations |
| globex_supplier_review | B-018 | yes (['1 year | one year | 12 months']) | drafted: text | short_answer='text' != 'yes' |
| globex_supplier_review | B-024 | yes (['eu-central-1 | Frankfurt']) | drafted: text | short_answer='text' != 'yes' |
| globex_supplier_review | B-026 | yes (['EU']) | drafted: no | short_answer='no' != 'yes' |
| globex_supplier_review | B-027 | yes (['30 days']) | drafted: text | short_answer='text' != 'yes' |
| globex_supplier_review | B-028 | yes (['35 days']) | needs_input: None | status=needs_input; no citations |
| globex_supplier_review | B-032 | yes (['every year | annual']) | needs_input: None | status=needs_input; no citations |
| globex_supplier_review | B-037 | yes (['least privilege']) | needs_input: None | status=needs_input; no citations |
