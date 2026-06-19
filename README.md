# Azure Orphaned Resource & Cost Governance cleaner

[![Build Status](https://github.com/arcstar7/AzureResourceCleaner/actions/workflows/deploy.yml/badge.svg)](https://github.com/arcstar7/AzureResourceCleaner/actions)
[![Python Version](https://img.shields.io/badge/python-3.10-blue.svg)](https://www.python.org/downloads/release/python-3100/)
[![Azure Functions](https://img.shields.io/badge/Azure%20Functions-Serverless-blueviolet)](https://azure.microsoft.com/en-us/services/functions/)

An automated, serverless orchestration engine designed to enforce cloud governance, identify cost leakage, and route compliance alerts to Microsoft Teams. 

By leveraging the **Azure Resource Graph (ARG) API** instead of standard iterative API calls, this solution queries massive enterprise cloud environments in milliseconds. It operates on a **Zero-Trust security model**, utilizing System-Assigned Managed Identities to ensure no credentials or secrets are stored in the codebase.

---

## 🏗️ Architecture & Business Value

### The Problem
In sprawling cloud environments, orphaned resources (like unattached managed disks or unassociated public IPs) and untagged infrastructure result in significant "zombie spend" and broken chargeback models.

### The Solution
This orchestrator runs on a scheduled Azure Function (Timer Trigger) to automatically:
1. Query the Azure Resource Graph across all accessible subscriptions.
2. Identify orphaned disks, floating IPs, and infrastructure missing critical governance tags (e.g., `CostCenter`, `Environment`).
3. Aggregate the findings and push an actionable summary card to a Microsoft Teams channel via Webhook.

---

## 📂 Repository Structure

This repository is structured for enterprise CI/CD and clear separation of concerns.

```text
AzureResourceCleaner/
│
├── .github/                        
│   └── workflows/
│       └── deploy.yml              # GitHub Actions CI/CD deployment pipeline
│
├── infrastructure/                 
│   └── deploy.bicep                # IaC: Azure Bicep template for serverless infrastructure
│
├── src/                            
│   ├── requirements.txt            # Python dependencies
│   ├── host.json                   # Azure Functions global configuration
│   └── TimerTriggerCleaner/        
│       ├── __init__.py             # Core Python orchestration logic
│       └── function.json           # Cron schedule trigger definition
│
├── tests/                          
│   └── test_cleaner.py             # Pytest unit tests for query validation and API mocking
│
└── README.md                       # Project documentation
```

## 🚀 Deployment Guide
This solution is designed to be deployed entirely via code. Manual infrastructure creation in the Azure Portal is not required.

### 1. Provision Infrastructure (IaC)
Use the provided Bicep template to deploy the Storage Account, Consumption Plan, and Function App with a Managed Identity.

```bash
cd infrastructure
az deployment group create \
  --resource-group rg-governance-prod \
  --template-file deploy.bicep
```

### 2. Configure Access Management (RBAC)
The Bicep deployment outputs the principalId of the Function App's Managed Identity. You must grant this identity the Reader role at the Management Group or Subscription level so it can query the Azure Resource Graph.

```bash
az role assignment create \
  --assignee <OUTPUT_PRINCIPAL_ID> \
  --role "Reader" \
  --scope /subscriptions/<YOUR_SUBSCRIPTION_ID>
```

### 3. Continuous Integration & Deployment (CI/CD)
The .github/workflows/deploy.yml pipeline automatically deploys the Python code to the Function App whenever changes are pushed to the main branch.

To enable this:

Download the publishing profile of your new Function App.

In your GitHub repository, go to Settings > Secrets and variables > Actions.

Create a new secret named AZURE_CREDENTIALS and paste the publishing profile contents.

Set the TEAMS_WEBHOOK_URL as an App Setting in the Azure Portal so the script can route alerts.

## 🛠️ Customization & Extensibility
Adding Custom Governance Rules
To add rules tailored to specific organizational policies, simply append new KQL (Kusto Query Language) strings to the governance_queries dictionary inside src/TimerTriggerCleaner/__init__.py.

```python
# Example: Identify unused App Service Plans
"Empty_App_Service_Plans": """
    Resources
    | where type =~ 'microsoft.web/serverfarms'
    | where properties.numberOfSites == 0
    | project id, name, resourceGroup, sku=sku.name
"""
```

## Running Local Unit Tests
Automated tests are located in the /tests directory to validate query integrity and mock API responses. To run them locally:
```bash
pip install -r src/requirements.txt
pip install pytest
pytest tests/
```