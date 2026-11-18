---
policy_id: encryption-standard
title: Encryption Standard
version: 2
effective_date: 2025-10-01
---

# Encryption Standard

This standard describes how Northbeam Cloud uses encryption to protect customer and company data. It
supports the Information Security Policy and applies to every system in the production environment
and to every service that handles customer data.

## Scope

The standard covers data stored by the platform, data exchanged with customers and partners, and the
cryptographic keys that protect both. Engineering teams must follow it when they design a new
service or change an existing one.

## Data at rest

Northbeam Cloud uses AES-256 encryption at rest for databases, backups and object storage.
Encryption is enabled by default on every new storage resource through infrastructure templates, and
a daily configuration check reports any resource where it is missing. Laptops issued to employees
use full-disk encryption.

## Data in transit

The platform requires TLS 1.2 or higher for all external traffic, and TLS 1.3 is preferred wherever
the client supports it. Older protocol versions and weak cipher suites are disabled at the load
balancer. Connections between internal services also use encrypted channels.

## Key management

Keys are managed in AWS KMS and rotated every 12 months. Access to key administration is limited to
the platform team and every use of a key is logged. Keys are never stored in source code or in
configuration files.

## Review

The security team reviews this standard when cryptographic guidance changes and at least as often as
the Information Security Policy requires.
