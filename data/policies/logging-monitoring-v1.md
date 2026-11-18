---
policy_id: logging-monitoring
title: Logging and Monitoring Policy
version: 1
effective_date: 2025-05-15
---

# Logging and Monitoring Policy

This policy describes how Northbeam Cloud records security-relevant events and watches its systems
for signs of misuse or failure. It applies to the production environment, the identity provider and
the tools that engineers use to manage them.

## Scope

The policy covers authentication events, administrative actions, changes to infrastructure, access to
customer data by staff, and alerts from security tools. Application logs must not contain passwords,
keys or customer content.

## Logging

Logs are centralized and alerts are monitored 24/7. Every production system sends its logs to the
central logging platform, where they are protected against modification and can only be read by the
security and platform teams. Retention of logs follows the Data Retention Policy.

## Alerting

Detection rules cover failed and unusual logins, changes to privileged roles, disabled security
controls and unexpected data exports. Each rule has an owner and a documented response. Alerts are
routed to the person on call through the paging tool. The person on call acknowledges each alert,
records what was found and closes it or escalates it to an incident.

## Review

The security team reviews detection rules every six months and after every significant incident, and
removes rules that only produce noise.

## Time synchronisation

All systems synchronise their clocks with a trusted time source so that events from different systems
can be correlated during an investigation.
