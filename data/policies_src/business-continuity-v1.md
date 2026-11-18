---
policy_id: business-continuity
title: Business Continuity and Disaster Recovery Policy
version: 1
effective_date: 2025-04-01
---

# Business Continuity and Disaster Recovery Policy

This policy describes how Northbeam Cloud keeps its platform available and recovers it after a
serious outage. It applies to the production environment and to the teams that operate it.

## Scope

The policy covers the customer-facing platform, its databases and the internal tools needed to run
it. Office systems are covered by a separate checklist owned by the IT team.

## Hosting

Production runs in AWS eu-west-1 (Ireland) across multiple availability zones, so the loss of a single
zone does not stop the service. Encrypted backups are stored in eu-central-1 (Frankfurt), in a
separate account with restricted access.

## Objectives

The recovery objectives for the production platform are RPO 4 hours, RTO 8 hours. These objectives
are used to size backup frequency, replication and the recovery runbooks.

## Recovery procedures

Recovery runbooks describe how to restore each component, who is allowed to start a recovery and how
customers are kept informed. Runbooks are stored outside the production environment so that they
remain available during an outage.

## Testing

Disaster recovery is tested twice a year by restoring production data into an isolated environment
and measuring the time needed against the recovery objectives. Results and follow-up actions are
recorded by the platform team.

## Responsibilities

The platform team owns this policy and the runbooks. The Head of Security reviews test results and
reports them to the leadership team.
