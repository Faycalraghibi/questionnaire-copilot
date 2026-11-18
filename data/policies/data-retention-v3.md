---
policy_id: data-retention
title: Data Retention Policy
version: 3
effective_date: 2026-03-01
---

# Data Retention Policy

This policy defines how long Northbeam Cloud keeps customer data, backups and logs, and how that data
is deleted at the end of its retention period. It applies to every system that stores customer or
company information.

## Principles

Data is kept only as long as it is needed to provide the service, to meet a legal obligation or to
investigate a security event. Deletion is automated wherever possible so that it does not depend on
a person remembering to do it.

## Customer data

Customer data is deleted within 30 days after contract end. During that period the customer can ask
for an export of its data. After deletion, the data cannot be recovered from the production systems.
Customers can also ask for deletion of specific records during the contract through their account
manager.

## Backups

Backups are kept for 35 days. Older backups are removed automatically by the backup lifecycle rules,
so data deleted from production disappears from backups once the retention period has passed.
Backups are not used for any purpose other than restoring the service.

## Logs

Security logs are kept for 1 year to support investigations and audits. Application debug logs are
kept for a shorter period set by the platform team and do not contain customer content.

## Legal holds

If a legal hold applies, the Head of Security can suspend deletion for the data concerned. Every hold
is recorded with its reason and is lifted as soon as it is no longer needed.
