import boto3

ssm_client = boto3.client('ssm')

def lambda_handler(event, context):
    command_id = event['CommandId']

    # Get invocation statuses for this command
    response = ssm_client.list_command_invocations(
        CommandId=command_id,
        Details=False  # We only need Status field
    )

    invocations = response.get('CommandInvocations', [])

    if not invocations:
        return {'Status': 'Pending'}

    # Aggregate statuses
    statuses = [inv['Status'] for inv in invocations]

    if all(s in ['Success'] for s in statuses):
        return {'Status': 'Success'}

    if any(s in ['Failed', 'Cancelled', 'TimedOut'] for s in statuses):
        return {'Status': 'Failed'}

    return {'Status': 'InProgress'}
