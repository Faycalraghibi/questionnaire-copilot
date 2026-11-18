---
policy_id: secure-sdlc
title: Secure Development Policy
version: 1
effective_date: 2025-08-01
---

# Secure Development Policy

This policy describes how Northbeam Cloud builds security into the way its software is designed,
written, tested and released. It applies to every engineer and to every repository that contributes
to the production platform.

## Design

New features that touch authentication, customer data or external integrations include a short
threat review in their design document. The security team is consulted when the review identifies a
significant risk.

## Code review

Every change requires review by a second engineer before it is merged. Reviewers check for
correctness and for common security issues such as missing authorization checks and unsafe input
handling. The main branch is protected so that this rule cannot be bypassed.

## Testing

Static analysis runs on every pull request, and findings above a defined severity block the merge.
Third-party dependencies are scanned daily against public vulnerability databases, and the owning
team is alerted when a fix is available. Automated tests must pass before a release.

## Penetration testing

An independent penetration test is performed every year by an external firm; the last one was in
February 2026. Findings are tracked to resolution and retested by the firm.

## Releases

Releases go through an automated pipeline. Only the pipeline can deploy to production, and every
deployment is recorded with the change it contains.
