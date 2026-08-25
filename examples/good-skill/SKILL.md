---
name: good-skill
description: Use this skill when reviewing, checking, or auditing a payment or checkout integration (Stripe, PayPal, or similar) for correctness and security issues, such as amount handling, webhook verification, refund logic, and idempotency.
---

# Payment Review

This skill reviews payment integration code for common mistakes before it ships.

## When to use

Use this skill when a pull request touches payment processing, checkout flows,
webhook handlers, or billing logic.

## What to check

- Amounts are handled in the smallest currency unit (cents), never floats.
- Webhook signatures are verified before the payload is trusted.
- Payment operations are idempotent (a retried request can't double-charge).
- Card data never touches application logs.
- Refund and cancellation paths are covered by tests.

## Output

Summarize findings as a short list of concrete issues, each with the file and
line where it occurs, ordered by severity.
