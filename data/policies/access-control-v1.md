---
policy_id: access-control
title: Access Control Policy
version: 1
effective_date: 2025-05-01
---

# Access Control Policy

This policy defines how Northbeam Cloud grants, reviews and removes access to its systems and to
customer data. It applies to every employee and contractor and to every system that stores or
processes company or customer information.

## Authentication

SSO with multi-factor authentication is required for all production and admin systems. Accounts are
personal and must not be shared. Service accounts used by automated jobs are owned by a named
engineer, use credentials stored in the company secrets manager, and cannot be used for interactive
login. Passwords for the identity provider follow the length and complexity rules published by the
security team.

## Authorization

Permissions are assigned through role-based access following least privilege. Each role is defined
by the system owner and grants only the permissions needed for the job. Requests for additional
access are made through the service desk and approved by the system owner and the employee's
manager.

## Access reviews

User access is reviewed every quarter. System owners confirm that each account still belongs to a
current employee or contractor and that its role is still appropriate. Access that is no longer
needed is removed, and the review result is recorded by the security team.

## Privileged access

Production admin access is granted just in time, for at most 4 hours, with approval from a second
engineer on the platform team. Every privileged session is logged. Standing administrator rights on
production systems are not permitted.

## Offboarding

Access is revoked within 24 hours of departure. The People team opens an offboarding ticket on or
before the last working day, and the IT team disables the identity provider account, which removes
access to every connected application. Company devices are returned and wiped.
