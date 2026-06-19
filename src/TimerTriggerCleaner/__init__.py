"""
S&T Systems Group - Cloud Infrastructure Governance
Azure Orphaned Resource & Cost Cleaner

This orchestration script queries the Azure Resource Graph to identify cost leakage,
orphaned infrastructure, and compliance violations across all accessible subscriptions.
It is designed to run via Azure Functions or Azure Automation using a System-Assigned Managed Identity.
"""

import os
import json
import logging
from datetime import datetime
import requests

# Azure SDKs
from azure.identity import DefaultAzureCredential
from azure.mgmt.resourcegraph import ResourceGraphClient
from azure.mgmt.resourcegraph.models import QueryRequest, QueryRequestOptions

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class AzureCostCleaner:
    def __init__(self):
        """
        Initializes the Azure Resource Graph client using DefaultAzureCredential.
        In Azure, this automatically uses the Managed Identity. Locally, it uses the Azure CLI login.
        """
        logging.info("Authenticating with Azure...")
        self.credential = DefaultAzureCredential()
        self.rg_client = ResourceGraphClient(credential=self.credential)
        
        # MODIFICATION POINT: Add or modify KQL queries here for different business needs.
        # These queries execute globally across all subscriptions the Managed Identity can read.
        self.governance_queries = {
            "Orphaned_Managed_Disks": """
                Resources
                | where type =~ 'microsoft.compute/disks'
                | where properties.diskState == 'Unattached'
                | project id, name, resourceGroup, subscriptionId, sku=sku.name, sizeGB=properties.diskSizeGB
            """,
            "Unassociated_Public_IPs": """
                Resources
                | where type =~ 'microsoft.network/publicipaddresses'
                | where isnull(properties.ipConfiguration)
                | project id, name, resourceGroup, subscriptionId, ipAddress=properties.ipAddress
            """,
            "Untagged_Resources": """
                Resources
                | where tags !contains "CostCenter" or tags !contains "Environment"
                | where type !match 'microsoft.alertsmanagement' // Exclude resource types that don't support tags
                | project id, name, type, resourceGroup, subscriptionId, tags
            """
        }

    def run_query(self, query_name: str, query_text: str):
        """Executes a KQL query against the Azure Resource Graph."""
        logging.info(f"Executing Governance Rule: {query_name}")
        
        # Query options: limit to 1000 results per rule. 
        # For massive environments, implement pagination using the $skip token.
        options = QueryRequestOptions(result_format="objectArray", top=1000)
        request = QueryRequest(query=query_text, options=options)
        
        try:
            response = self.rg_client.resources(request)
            return response.data
        except Exception as e:
            logging.error(f"Failed to execute query {query_name}: {e}")
            return []

    def audit_environment(self):
        """Runs all configured governance rules and aggregates the findings."""
        audit_results = {}
        total_violations = 0

        for rule_name, kql_query in self.governance_queries.items():
            results = self.run_query(rule_name, kql_query)
            audit_results[rule_name] = results
            total_violations += len(results)
            logging.info(f"Found {len(results)} resources violating '{rule_name}'.")

        return audit_results, total_violations

    def send_teams_alert(self, webhook_url: str, total_violations: int, results: dict):
        """
        Routes a summary alert to a Microsoft Teams channel via Webhook.
        
        MODIFICATION POINT: To integrate this with an ITSM tool (like ServiceNow or Jira), 
        replace this payload with the respective REST API schema to auto-generate tickets.
        """
        if total_violations == 0:
            logging.info("No violations found. Skipping Teams notification.")
            return

        # Build a markdown summary of the findings
        summary_details = "\n".join([f"- **{rule}**: {len(items)} resources flagged." for rule, items in results.items()])
        
        payload = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": "FF0000",
            "summary": "Azure Governance Audit Alert",
            "sections": [{
                "activityTitle": f"⚠️ Azure Governance Audit: {total_violations} Violations Detected",
                "activitySubtitle": f"Scan completed at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
                "text": f"The automated Azure Cleaner identified resources requiring remediation:\n\n{summary_details}",
                "facts": [
                    {"name": "Action Required", "value": "Review unattached disks and untagged infrastructure."}
                ]
            }]
        }

        try:
            response = requests.post(webhook_url, json=payload)
            response.raise_for_status()
            logging.info("Alert successfully routed to Microsoft Teams.")
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to send Teams alert: {e}")

if __name__ == "__main__":
    # 1. Initialize the Cleaner
    cleaner = AzureCostCleaner()
    
    # 2. Run the Audit
    findings, total_flags = cleaner.audit_environment()
    
    # 3. Optional: Save to local JSON for review or storage in an Azure Blob
    with open("azure_governance_report.json", "w") as f:
        json.dump(findings, f, indent=4)
    logging.info("Detailed report saved to azure_governance_report.json")
    
    # 4. Alerting
    # MODIFICATION POINT: Set this environment variable in your Azure Function configuration
    teams_webhook = os.environ.get("TEAMS_WEBHOOK_URL")
    if teams_webhook:
        cleaner.send_teams_alert(teams_webhook, total_flags, findings)
    else:
        logging.warning("TEAMS_WEBHOOK_URL environment variable not set. Skipping alert.")
        
    # MODIFICATION POINT: Remediation Logic (Future Iteration)
    # If the business signs off on automated deletion, you would import `ComputeManagementClient`
    # and iterate through `findings["Orphaned_Managed_Disks"]` calling `client.disks.begin_delete(rg, name)`.
    # It is highly recommended to keep this as an "Audit-Only" script until tagging practices are mature.