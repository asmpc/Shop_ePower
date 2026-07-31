# Chapter 04 --- Engineering Decisions

------------------------------------------------------------------------

# Introduction

Every infrastructure project is shaped by a series of engineering
decisions. PHASE 19 was no exception. The objective was not to adopt
every available tool, but to choose technologies that matched the
current size and future direction of Shop_ePower.

The following decisions became the foundation of the completed CI
pipeline.

------------------------------------------------------------------------

# Single Docker Image

A single application image was selected for all project services.

## Decision

-   One Docker image
-   Multiple service roles (web, celery, beat)

## Rationale

Using one image guarantees that every service executes exactly the same
version of the application while reducing maintenance complexity.

------------------------------------------------------------------------

# Docker Buildx

## Decision

Docker Buildx was adopted instead of the classic build command.

## Rationale

Buildx provides a modern build engine, improved caching and prepares the
project for future multi-platform image builds.

------------------------------------------------------------------------

# GitHub Container Registry

## Decision

Container images are published to GitHub Container Registry after
successful CI.

## Rationale

Keeping images close to the source repository simplifies version
management and provides a natural foundation for future deployment
automation.

------------------------------------------------------------------------

# Ruff as the First Quality Gate

## Decision

Ruff was selected as the project's initial static analysis tool.

## Rationale

Ruff offers excellent performance, simple configuration and broad
compatibility with modern Python development practices. It introduces
automated quality checks without significantly increasing CI execution
time.

------------------------------------------------------------------------

# Service Containers in CI

## Decision

CI uses PostgreSQL and Redis service containers.

## Rationale

Testing against real infrastructure provides greater confidence than
relying on mocked services and more closely reflects the local
development environment.

------------------------------------------------------------------------

# Documentation as Definition of Done

## Decision

Infrastructure changes are considered complete only after the
corresponding documentation has been updated.

## Rationale

Keeping documentation synchronized with implementation reduces
onboarding time, improves maintainability and preserves engineering
knowledge.

------------------------------------------------------------------------

# Summary

The engineering decisions made during PHASE 19 favored simplicity,
maintainability and reproducibility over unnecessary complexity.

Rather than optimizing for hypothetical future requirements, the project
gained a practical infrastructure that solves today's needs while
remaining flexible enough to support future phases such as Poetry
migration, deployment automation and production hosting.
