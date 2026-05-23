# Integris Clinical Platform

> **Status: Active Development — v0.8 (targeting v1.0 release Q3 2026)**

A proprietary, cloud-native SaaS platform for clinical data validation and regulatory compliance, built for Contract Research Organizations (CROs) and pharmaceutical sponsors operating under FDA and EMA standards.

Developed and maintained by **George Adrian Pircalaboiu**, Founder & CEO/CTO of **Integris Clinical Services LLC**, San Antonio, Texas.

---

## Overview

The Integris Clinical Platform automates the validation of clinical trial datasets against CDISC/SDTM compliance standards, detects data anomalies in real time, generates FDA-ready compliance reports with electronic signatures, and maintains a complete audit trail in accordance with FDA 21 CFR Part 11 requirements.

It addresses a documented gap in the US clinical research industry: the lack of affordable, modern, cloud-native validation tooling accessible to small and mid-size CROs that cannot afford enterprise platforms like Medidata or Veeva.

---

## Core Features

- **CDISC/SDTM Rule-Based Validation** — automated validation across all major SDTM domains (DM, VS, AE, CM, LB, EG, MH, SV) with systematic rule IDs and severity classification (Critical, High, Medium, Low)
- **Cross-Domain Validation** — detects inconsistencies spanning multiple clinical domains (e.g. adverse event dates preceding subject enrollment)
- **CDISC Dataset-JSON v1.1 Support** — native parsing and validation of the FDA's emerging exchange standard
- **Anomaly Detection** — Isolation Forest-based statistical outlier detection on SDTM numeric variables
- **Real-Time Compliance Dashboard** — live aggregated compliance status across all active studies powered by Elasticsearch
- **Automated PDF Compliance Reports** — structured, FDA-ready reports with electronic signature support
- **FDA 21 CFR Part 11 Audit Trail** — immutable, cryptographically hashed audit log of every action
- **Multi-Tenant Architecture** — complete data isolation per CRO client
- **Role-Based Access Control** — configurable user roles with multi-factor authentication

---

## Technology Stack

### Backend
- Python 3.10+ / FastAPI — async REST API
- PostgreSQL — multi-tenant relational database (GCP Cloud SQL)
- Elasticsearch — real-time findings aggregation and dashboard queries
- Redis + Celery — async validation job processing
- SQLAlchemy + Alembic — ORM and database migrations
- JWT RS256 + TOTP MFA — authentication and authorization

### Frontend
- TypeScript / Angular 21
- Angular Material — UI component library
- Responsive web application with real-time WebSocket updates

### Infrastructure
- Google Cloud Platform (GCP)
- Cloud Run — containerized auto-scaling deployment
- Cloud Storage — encrypted dataset storage
- Cloud KMS — encryption key management
- Secret Manager — credentials management
- Cloud Armor WAF — web application firewall
- Docker + Docker Compose — local development

---

## Architecture
┌─────────────────────────────────────────┐
│           Angular 21 SPA                │
│     (Web Dashboard + Mobile future)     │
└──────────────┬──────────────────────────┘
│ HTTPS / WebSocket
┌──────────────▼──────────────────────────┐
│         FastAPI Backend                 │
│    (REST API + Celery Workers)          │
└──────────────┬──────────────────────────┘
│
┌──────────────▼──────────────────────────┐
│         GCP Managed Services            │
│  Cloud SQL │ Elasticsearch │ Redis      │
│  Cloud Storage │ Cloud KMS              │
└─────────────────────────────────────────┘

---

## Regulatory Alignment

The Integris Clinical Platform directly addresses US federal priorities in clinical data modernization:

- **FDA Dataset-JSON v1.1** — native support for the FDA's emerging electronic study data submission standard (Federal Register, April 2025)
- **NIH Strategic Plan for Data Science 2025–2030** — supports Goal 2 (Enhance Human Derived Data for Research) and Objective 2-2 (Adopt Health IT Standards for Research)
- **CDC Public Health Data Strategy 2025–2026** — real-time, secure clinical data exchange aligned with CDC milestones
- **FDA 21 CFR Part 11** — electronic records and signatures compliance built into the core platform
- **21st Century Cures Act** — modern, interoperable digital health infrastructure

---

## Project Status

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 0 | ✅ Complete | Prototype stabilization — 62 tests passing |
| Phase 1 | ✅ Complete | FastAPI backend, auth, multi-tenancy, validation pipeline, 45 integration tests |
| Phase 2 | ✅ Complete | Angular 21 frontend — all 9 modules |
| Phase 3 | 🔄 In Progress | GCP deployment, Terraform, CI/CD, HIPAA controls |
| Phase 4 | ⏳ Planned | Dependency packaging, installation scripts |
| Phase 5 | ⏳ Planned | v1.0 release, full documentation |

---

## Local Development

### Prerequisites
- Docker Desktop
- Node.js 18+
- Python 3.10+

### Quick Start (Linux/macOS)
```bash
git clone https://github.com/Adrian0491/integris-clinical-platform.git
cd integris-clinical-platform
cp backend/.env.example backend/.env
make up
make migrate
make frontend
```

### Quick Start (Windows)
```powershell
git clone https://github.com/Adrian0491/integris-clinical-platform.git
cd integris-clinical-platform
copy backend\.env.example backend\.env
.\scripts\run.ps1 up
.\scripts\run.ps1 migrate
.\scripts\run.ps1 frontend
```

Navigate to `http://localhost:4200`

---

## About

**Integris Clinical Services LLC**
San Antonio, Texas, United States

Building modern clinical data infrastructure for the US clinical research industry.

---

*This repository contains proprietary software. All rights reserved.*
