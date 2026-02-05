# Singularity

This repository contains tools, scripts, and guides for [Singularity](https://github.com/data-preservation-programs/singularity), a data preparation and Filecoin onboarding application.

## Goal & Purpose

The purpose of this repository is to provide resources to help users deploy Singularity and manage data onboarding workflows. These utilities are intended to assist with preparing data for Filecoin storage.

## Contents

### Guides
- **[Preserving Open Science Data with Singularity and Docker](./Guides/Preserving%20Open%20Science%20Data%20with%20Singularity%20and.md)**: A guide covering Singularity deployment using Docker and Docker Compose.

### Utilities & Tools
- **[CID Comparison Tool](./Utilities/cid-comparison)**: A containerized environment for comparing CID generation between IPFS (Kubo) and Singularity.
- **[Retrieval Review](./Utilities/retrieval-review)**: A Python toolkit for checking the retrieval status of unsealed content from storage providers.
- **[Docker Deployment](./Utilities/docker)**: The `Dockerfile` and `docker-compose` files referenced in the guides.

### Scripts
A suite of scripts for specific use cases:
- **[Piece Download Automation](./Utilities/scripts/car-retrieval)**: Automates the download of pieces from a Singularity preparation.
- **[Metadata Export](./Utilities/scripts/extract-piece-cids)**: Exports metadata on the deal status of piece CIDs for preparations.
- **[Deal Size Summarizer](./Utilities/scripts/summarize-deal-size)**: Summarizes the total size of Filecoin deals.

## Getting Started

The [Step-by-Step Guide](./Guides/Preserving%20Open%20Science%20Data%20with%20Singularity%20and.md) provides instructions for deploying using the provided Docker utilities.

---
