// deploy.bicep
// Deploys the serverless infrastructure for the Azure Governance Janitor

param location string = resourceGroup().location
param appName string = 'fn-azure-janitor-${uniqueString(resourceGroup().id)}'

// 1. Storage Account (Required for Azure Functions)
resource storageAccount 'Microsoft.Storage/storageAccounts@2022-09-01' = {
  name: 'stjanitor${uniqueString(resourceGroup().id)}'
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
}

// 2. Serverless Consumption Plan
resource hostingPlan 'Microsoft.Web/serverfarms@2022-03-01' = {
  name: 'plan-${appName}'
  location: location
  sku: {
    name: 'Y1' // Dynamic consumption (pay-per-execution)
    tier: 'Dynamic'
  }
  properties: {
    reserved: true // Required for Linux/Python functions
  }
}

// 3. Python Function App with System-Assigned Managed Identity
resource functionApp 'Microsoft.Web/sites@2022-03-01' = {
  name: appName
  location: location
  kind: 'functionapp,linux'
  identity: {
    type: 'SystemAssigned' // This is what DefaultAzureCredential uses in the Python script
  }
  properties: {
    serverFarmId: hostingPlan.id
    siteConfig: {
      linuxFxVersion: 'python|3.10'
      appSettings: [
        {
          name: 'AzureWebJobsStorage'
          value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};EndpointSuffix=${environment().suffixes.storage};AccountKey=${storageAccount.listKeys().keys[0].value}'
        }
        {
          name: 'FUNCTIONS_EXTENSION_VERSION'
          value: '~4'
        }
        {
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: 'python'
        }
        // MODIFICATION POINT: User adds their webhook URL here via KeyVault or portal later
        {
          name: 'TEAMS_WEBHOOK_URL'
          value: '' 
        }
      ]
    }
  }
}

output functionAppName string = functionApp.name
output principalId string = functionApp.identity.principalId // Use this to assign 'Reader' rights at the Subscription level