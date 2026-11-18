---
policy_id: encryption-standard
title: Encryption Standard
version: 1
effective_date: 2023-09-01
---

# Encryption Standard

This standard describes how Northbeam Cloud uses encryption to protect customer and company data. It
supports the Information Security Policy and applies to every system in the production environment.

## Scope

The standard covers data stored by the platform, data exchanged with customers, and the cryptographic
keys that protect both. Engineering teams must follow it when they design a new service.

## Data at rest

Production databases, backups and object storage are encrypted at rest with AES-256. Encryption is
enabled when a storage resource is created, and engineers confirm it during the change review for
any new database or bucket. Laptops issued to employees use full-disk encryption, which the IT team
checks when the laptop is first set up.

## Data in transit

External traffic to the platform uses TLS 1.2 or higher. Older protocol versions are disabled at the
load balancer. Certificates are issued by a public certificate authority and renewed automatically
before they expire.

## Key management

Encryption keys are managed in AWS KMS and rotated every 24 months. Access to key administration is
limited to the platform team. Keys are never stored in source code or in configuration files.

## Review

The security team reviews this standard when cryptographic guidance changes. The next planned review
will consider a shorter rotation period for encryption keys.
