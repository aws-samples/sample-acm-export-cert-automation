import boto3
import json

ssm_client = boto3.client('ssm')

def lambda_handler(event, context):
    command_id = event['CommandId']

    # Get invocation statuses for this command
    response = ssm_client.list_command_invocations(
        CommandId=command_id,
        Details=False  # We only need Status field
    )
    command = ssm_client.list_commands(CommandId=command_id)
    if command['Commands']:
        status = command['Commands'][0]['Status']
        return {'Status': status}

    if all(s in ['Success'] for s in status):
        return {'Status': 'Success'}

    if any(s in ['Failed', 'Cancelled', 'TimedOut'] for s in status):
        return {'Status': 'Failed'}

    return {'Status': 'InProgress'}
