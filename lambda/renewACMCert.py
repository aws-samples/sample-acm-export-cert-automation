import boto3
import os
import json

dynamodb = boto3.resource('dynamodb')
stepfunctions = boto3.client('stepfunctions')

CERT_TAG_TABLE = os.environ['CERT_TAG_TABLE']
STATE_MACHINE_ARN = os.environ['STATE_MACHINE_ARN']

def lambda_handler(event, context):
    cert_arn = event['resources'][0]  # From ACM Certificate Available event

    # Query DynamoDB by CertificateArn
    table = dynamodb.Table(CERT_TAG_TABLE)
    response = table.get_item(Key={'CertificateArn': cert_arn})

    if 'Item' not in response:
        raise Exception(f"CertificateArn {cert_arn} not found in DynamoDB")

    item = response['Item']

    # Build input payload for existing Step Function
    step_input = {
        "CertificateArn": cert_arn,
        "CertName": item.get("CertName"),
        "Passphrase": item.get("Passphrase"),
        "TargetTagKey": item.get("TargetTagKey"),
        "TargetTagValue": item.get("TargetTagValue")
    }

    # Start the Step Function execution
    stepfunctions.start_execution(
        stateMachineArn=STATE_MACHINE_ARN,
        input=json.dumps(step_input)
    )

    return {
        "status": "Triggered Step Function",
        "input": step_input
    }
