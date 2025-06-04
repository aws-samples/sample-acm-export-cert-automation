# ACM Certificate Export and Renewal Automation

This project automates the process of exporting Amazon Certificate Manager (ACM) certificates and installing them on EC2 instances and on-premises servers. It also automates the certificate renewal process, creating a seamless, event-driven workflow that requires minimal manual intervention.

## 📋 Table of Contents

- [Solution Overview](#️-solution-overview)
- [Architecture Components](#-architecture-components)
- [Part 1: Export and Install](#-part-1-export-and-install)
- [Part 2: Certificate Renewal](#-part-2-certificate-renewal)
- [Step Function Details](#-step-function-details)
- [Setup Instructions](#️-setup-instructions)
- [Testing the Solution](#-testing-the-solution)
- [Quickstart with CloudFormation](#-quickstart-with-cloudformation)
- [Monitoring and Notifications](#-monitoring-and-notifications)

## 🏗️ Solution Overview

The solution consists of two main parts:

1. **Export and Install**: Triggered via API Gateway to export certificates from ACM and install them on EC2 or on-premises servers
2. **Certificate Renewal**: Automatically handles certificate renewals via EventBridge events

### Certificate Export and Installation Flow
![Certificate Export and Installation Flow](diagram/EC2Automation-ACM%20certificate%20export%20cert.drawio.png)

### Certificate Renewal Flow
![Certificate Renewal Flow](diagram/EC2Automation-Certificate%20renewal.drawio.png)

## 🧩 Architecture Components

* **API Gateway** - Accepts requests to export and install certificates
* **ACM (Amazon Certificate Manager)** - Source of certificates and renewal events
* **Amazon EventBridge** - Listens for certificate renewal events
* **Lambda Functions**:
  * `renewACMCert` - Handles renewal events and starts the Step Function
  * `acm-Export` - Exports certificates from ACM
  * `checkAndUpdateMappingAndSendSSM` - Updates DynamoDB and triggers SSM automation
  * `checkCommandStatus` - Monitors SSM command execution
* **Step Function** - Orchestrates the export and installation process
* **DynamoDB (CertTagMapping)** - Stores certificate metadata and target information
* **SSM** - Runs the `Install-ACMCertificate` document to install certificates on targets

## 🔄 Part 1: Export and Install

This workflow is initiated through an API Gateway call with the following input:

```json
{
  "CertificateArn": "arn:aws:acm:us-east-1:1234567890123:certificate/8106d6b2-f204-4354-8893-d49e311b3900",
  "CertName": "academe",
  "Passphrase": "1234",
  "TargetTagKey": "env",
  "TargetTagValue": "dev"
}
```

The API Gateway triggers a Step Function with the following steps:

1. **acm-Export**:
   * Exports the certificate from ACM using the provided ARN and passphrase
   * Converts the certificate, private key, and chain to Base64 format
   * Passes the encoded data to the next step

2. **checkAndUpdateMappingAndSendSSM**:
   * Updates or creates an entry in the DynamoDB table with:
     ```
     'CertificateArn': cert_arn,
     'Passphrase': passphrase,
     'CertName': cert_name,
     'TargetTagKey': tag_key,
     'TargetTagValue': tag_value,
     'CertExpiryDate': cert_not_after,
     'LastExportedDate': datetime.utcnow().isoformat() + 'Z'
     ```
   * Runs the SSM automation document `Install-ACMCertificate` targeting EC2 or on-premises servers using the specified tags

3. **checkCommandStatus**:
   * Monitors the SSM command execution
   * Reports success or failure of the installation

## 🔄 Part 2: Certificate Renewal

This workflow is triggered automatically when ACM renews a certificate:

1. **EventBridge Rule** matches the following event pattern:
   ```json
   {
     "source": ["aws.acm"],
     "detail-type": ["ACM Certificate Available"],
     "detail": {
       "Action": ["RENEWAL"],
       "CertificateType": ["AMAZON_ISSUED"],
       "Exported": [true]
     }
   }
   ```

2. **renewACMCert Lambda** is triggered:
   * Extracts the certificate ARN from the event
   * Queries the DynamoDB table to retrieve the associated metadata:
     ```
     "CertificateArn": cert_arn,
     "CertName": item.get("CertName"),
     "Passphrase": item.get("Passphrase"),
     "TargetTagKey": item.get("TargetTagKey"),
     "TargetTagValue": item.get("TargetTagValue")
     ```
   * Starts the same Step Function used in Part 1 with this data

3. The **Step Function** then follows the same process as in Part 1 to export and install the renewed certificate.

## 🧠 Step Function Details

The Step Function (`acmExportMachine.json`) orchestrates the certificate export and installation process. Here's the actual Step Function definition:

```json
{
  "StartAt": "ExportCertOnly",
  "States": {
    "ExportCertOnly": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:us-east-1:1234567890123:function:acm-Export",
      "Next": "CheckAndUpdateMappingAndSendSSM"
    },
    "CheckAndUpdateMappingAndSendSSM": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:us-east-1:1234567890123:function:checkAndUpdateMappingAndSendSSM",
      "Next": "WaitForStatus"
    },
    "WaitForStatus": {
      "Type": "Wait",
      "Seconds": 15,
      "Next": "CheckCommandStatus"
    },
    "CheckCommandStatus": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:us-east-1:1234567890123:function:checkCommandStatus",
      "Next": "IsCommandComplete"
    },
    "IsCommandComplete": {
      "Type": "Choice",
      "Choices": [
        {
          "Variable": "$.Status",
          "StringEquals": "Success",
          "Next": "SuccessState"
        },
        {
          "Variable": "$.Status",
          "StringEquals": "Failed",
          "Next": "FailureState"
        }
      ],
      "Default": "WaitForStatus"
    },
    "SuccessState": {
      "Type": "Succeed"
    },
    "FailureState": {
      "Type": "Fail",
      "Error": "SSMCommandFailed",
      "Cause": "The SSM command execution failed"
    }
  }
}
```

### Step Function Flow

```
Start
 └──► ExportCertOnly (acm-Export Lambda)
       ↓
    CheckAndUpdateMappingAndSendSSM (Lambda)
       ↓
       WaitForStatus (Wait 15s)
       ↓
    CheckCommandStatus (Lambda)
       ↓
 ┌─────► IsCommandComplete? (Choice)
 │            ├──► SuccessState (Succeed)
 │            └──► FailureState (Fail)
 └─────────────► WaitForStatus (loop back if still InProgress)
```

### Benefits

| Feature                         | Benefit                                          |
| ------------------------------- | ------------------------------------------------ |
| Tag-based targeting             | Works with both EC2 and on-premises servers      |
| Central certificate management  | All certificate metadata stored in DynamoDB      |
| Fully automated renewals        | No manual intervention needed for renewals       |
| SSM automation                  | Consistent installation across environments      |
| Step Function orchestration     | Reliable execution with visibility and logging   |


## 🛠️ Setup Instructions

1. **DynamoDB Setup**:
   - Create a `CertTagMapping` table with `CertificateArn` as the primary key
   - Additional fields: `CertName`, `Passphrase`, `TargetTagKey`, `TargetTagValue`, `CertExpiryDate`, `LastExportedDate`

2. **Lambda Functions**:
   - Deploy the following Lambda functions:
     - `renewACMCert` - Set environment variables `CERT_TAG_TABLE` and `STATE_MACHINE_ARN`
     - `acm-Export`
     - `checkAndUpdateMappingAndSendSSM`
     - `checkCommandStatus`

3. **Step Function**:
   - Deploy the Step Function using the state machine definition in `step_func/acmExportMachine.json`
   - Use the exact ARNs as shown in the JSON definition or update them to match your deployed functions:
     ```
     arn:aws:lambda:us-east-1:1234567890123:function:acm-Export
     arn:aws:lambda:us-east-1:1234567890123:function:checkAndUpdateMappingAndSendSSM
     arn:aws:lambda:us-east-1:1234567890123:function:checkCommandStatus
     ```

4. **API Gateway**:
   - Create an API Gateway endpoint that triggers the Step Function for manual certificate export and installation

5. **EventBridge Rule**:
   - Create a rule named `ACM_PubCert_Renewed` to match ACM certificate renewal events
   - Set the target to the `renewACMCert` Lambda

6. **SSM Document**:
   - Create an SSM document named `Install-ACMCertificate` that handles certificate installation on target servers

7. **IAM Permissions**:
   - Ensure Lambda functions have appropriate permissions:
     - ACM: `ExportCertificate`, `DescribeCertificate`
     - DynamoDB: Read/Write to `CertTagMapping`
     - SSM: `SendCommand`, `ListCommandInvocations`
     - Step Functions: `StartExecution`

## 🧪 Testing the Solution

### Testing Part 1: Export and Install

Make an API call to your API Gateway endpoint with the following payload:

```json
{
  "CertificateArn": "arn:aws:acm:us-east-1:1234567890123:certificate/8106d6b2-f204-4354-8893-d49e311b3900",
  "CertName": "academe",
  "Passphrase": "1234",
  "TargetTagKey": "env",
  "TargetTagValue": "dev"
}
```

### Testing Part 2: Certificate Renewal

You can test the renewal process by manually triggering an EventBridge event using the AWS CLI:

```bash
aws events put-events --entries '[
  {
    "Source": "custom.aws.acm",
    "DetailType": "ACM Certificate Available",
    "Detail": "{\"Action\": \"RENEWAL\", \"CertificateType\": \"AMAZON_ISSUED\", \"CommonName\": \"example.cipherclouds.com\", \"DomainValidationMethod\": \"DNS\", \"CertificateCreatedDate\": \"2025-05-18T02:22:05Z\", \"CertificateExpirationDate\": \"2026-06-16T23:59:59Z\", \"DaysToExpiry\": 395, \"InUse\": false, \"Exported\": true}",
    "Resources": [
      "arn:aws:acm:us-east-1:1234567890123:certificate/0762eb4c-f9a8-4cf2-bfd6-7715ff743942"
    ],
    "EventBusName": "default"
  }
]' --region us-east-1
```

Make sure the certificate ARN exists in your DynamoDB table before testing.


## 🚀 Quickstart with CloudFormation

Deploy the solution quickly using the provided CloudFormation template:

### Deployment Steps

1. **Deploy the CloudFormation stack**:
   ```bash
   aws cloudformation deploy \
     --stack-name acm-cert-export \
     --template-file acm-cert-export-part1.yaml \
     --capabilities CAPABILITY_IAM
2. **Tag your target EC2 instances where certificates should be installed**:
   ```bash
    aws ec2 create-tags \
    --resources i-1234567890abcdef0 \
    --tags Key=env,Value=dev
3. **Get the API Gateway endpoint URL from CloudFormation outputs**
4. **Create a payload file (payload.json) with your certificate details:**
    ```json
      {
        "CertificateArn": "arn:aws:acm:us-east-1:123456789012:certificate/your-cert-id",
        "CertName": "my-cert",
        "Passphrase": "your-secure-passphrase",
        "TargetTagKey": "env",
        "TargetTagValue": "dev"
      }
5. **Invoke the API to export and install the certificate:**
  ```bash
      awscurl -X POST https://your-api-id.execute-api.us-east-1.amazonaws.com/prod/export-cert \
      -H "Content-Type: application/json" \
      -d @payload.json
  ```

6. **Monitor the execution in the Step Functions console to see the certificate export and installation progress.**

## Important Notes  

  * Target EC2 instances must be running Linux and have SSM Agent installed

  * Certificates are installed in /etc/ssl/certs/ and /etc/ssl/private/ folders
  
  * The API Gateway is secured with IAM authentication
  
  * Each certificate requires a one-to-one mapping with EC2 instance tags
  
  * You can customize the installation paths by modifying the SSM document


## Successful Execution Flow
![Sucessful step fuction execution flow](diagram/sample-step-fuction-excution.png)

## 🔔 Monitoring and Notifications

* Monitor Step Function executions through CloudWatch Logs and the AWS Step Functions console
* Set up CloudWatch Alarms for failed Step Function executions
* Consider adding SNS notifications for failed certificate installations or renewals

---riggering an EventBridge event using the AWS CLI:

```bash
aws events put-events --entries '[
  {
    "Source": "custom.aws.acm",
    "DetailType": "ACM Certificate Available",
    "Detail": "{\"Action\": \"RENEWAL\", \"CertificateType\": \"AMAZON_ISSUED\", \"CommonName\": \"example.cipherclouds.com\", \"DomainValidationMethod\": \"DNS\", \"CertificateCreatedDate\": \"2025-05-18T02:22:05Z\", \"CertificateExpirationDate\": \"2026-06-16T23:59:59Z\", \"DaysToExpiry\": 395, \"InUse\": false, \"Exported\": true}",
    "Resources": [
      "arn:aws:acm:us-east-1:1234567890123:certificate/0762eb4c-f9a8-4cf2-bfd6-7715ff743942"
    ],
    "EventBusName": "default"
  }
]' --region us-east-1
```

Make sure the certificate ARN exists in your DynamoDB table before testing.

## 🔔 Monitoring and Notifications

* Monitor Step Function executions through CloudWatch Logs and the AWS Step Functions console
* Set up CloudWatch Alarms for failed Step Function executions
* Consider adding SNS notifications for failed certificate installations or renewals

---