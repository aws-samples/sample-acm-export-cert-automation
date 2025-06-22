import boto3
import os
import json
from boto3.dynamodb.conditions import Attr

dynamodb = boto3.resource('dynamodb')
stepfunctions = boto3.client('stepfunctions')

CERT_TAG_TABLE = os.environ['CERT_TAG_TABLE']
STATE_MACHINE_ARN = os.environ['STATE_MACHINE_ARN']

def lambda_handler(event, context):
    cert_arn = event['resources'][0]  # From ACM Certificate Available event

    table = dynamodb.Table(CERT_TAG_TABLE)

    # Scan for all rows with this cert ARN
    response = table.scan(
        FilterExpression=Attr('CertificateArn#CertName').begins_with(f"{cert_arn}#")
    )

    items = response.get('Items', [])

    if not items:
        raise Exception(f"CertificateArn {cert_arn} not found in CertTagMapping table")

    # Trigger Step Function for each cert-tag mapping
    for item in items:
        step_input = {
            "CertificateArn": cert_arn,
            "CertName": item.get("CertName"),
            "Passphrase": item.get("Passphrase"),
            "TargetTagKey": item.get("TargetTagKey"),
            "TargetTagValue": item.get("TargetTagValue")
        }

        stepfunctions.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            input=json.dumps(step_input)
        )

    return {
        "status": "Triggered Step Function for renewals",
        "certArn": cert_arn,
        "executionsStarted": len(items)
    }
