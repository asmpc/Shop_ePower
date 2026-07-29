# Chapter 05 --- Problems Encountered & Solutions

------------------------------------------------------------------------

# Introduction

Every engineering phase introduces new challenges. PHASE 19 was no
exception.

Although the business logic of Shop_ePower remained stable throughout
this phase, integrating modern engineering infrastructure required
solving a number of practical problems related to Continuous
Integration, containerization and automation.

Each problem provided valuable experience and helped improve both the
project and the development workflow.

------------------------------------------------------------------------

# Challenge 1 --- Building a Reliable CI Pipeline

## Problem

The project had no automated verification process. Every validation step
was performed manually before pushing changes.

## Solution

A GitHub Actions workflow was introduced to execute project validation
automatically on every relevant repository update.

------------------------------------------------------------------------

# Challenge 2 --- Infrastructure Validation

## Problem

Application code could pass tests while Docker configuration contained
errors.

## Solution

Docker image building and Docker Compose validation became mandatory
stages of the CI pipeline, ensuring that infrastructure changes are
verified together with application code.

------------------------------------------------------------------------

# Challenge 3 --- Consistent Development Environment

## Problem

Differences between local development and CI environments can lead to
unexpected failures.

## Solution

Dedicated PostgreSQL and Redis service containers were introduced into
the CI workflow, allowing automated tests to execute in an environment
closely matching local development.

------------------------------------------------------------------------

# Challenge 4 --- Code Quality Control

## Problem

Regression tests verify behaviour but cannot detect every style or
quality issue.

## Solution

Ruff was integrated into the pipeline to provide fast automated static
analysis before changes reach the main branch.

------------------------------------------------------------------------

# Challenge 5 --- Documentation Synchronization

## Problem

Infrastructure evolved faster than project documentation.

## Solution

Documentation updates became a mandatory part of infrastructure work,
ensuring that project guides accurately reflect the implemented
architecture.

------------------------------------------------------------------------

# Lessons from the Phase

The most important lesson learned during PHASE 19 was that engineering
automation should evolve gradually.

Instead of introducing every possible tool at once, the infrastructure
was improved through a sequence of small, well-tested iterations.

This approach reduced implementation risk, simplified troubleshooting
and made every completed sprint independently verifiable.

------------------------------------------------------------------------

# Summary

By resolving these challenges, Shop_ePower gained a stable engineering
foundation for future development.

The project now benefits from automated verification, improved
infrastructure consistency, better code quality control and
documentation that evolves together with the implementation.
