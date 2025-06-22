import boto3
from datetime import datetime

dynamodb = boto3.resource('dynamodb')
acm_client = boto3.client('acm')
ssm_client = boto3.client('ssm')

def lambda_handler(event, context):
    cert_arn = event['CertificateArn']
    cert_name = event.get('CertName', 'default-cert')
    tag_key = event.get('TargetTagKey', 'Environment')
    tag_value = event.get('TargetTagValue', 'Dev')
    secret_name = event['PassphraseSecretName']  # The name of the secret in Secrets Manager

    now = datetime.utcnow().isoformat() + 'Z'
    
    table = dynamodb.Table('CertTagMapping')

    # Get certificate expiration date
    cert_description = acm_client.describe_certificate(CertificateArn=cert_arn)
    cert_not_after = cert_description['Certificate']['NotAfter'].isoformat() + 'Z'

    key = {
        'TagKeyValue': f"{tag_key}#{tag_value}",
        'CertificateArn#CertName': f"{cert_arn}#{cert_name}"
    }

    # Check if a record already exists
    response = table.get_item(Key=key)
    item = response.get('Item')

    if item:
        # Update existing record
        table.update_item(
            Key=key,
            UpdateExpression="SET LastExportedDate = :led, CertExpiryDate = :ced, Passphrase = :ps",
            ExpressionAttributeValues={
                ':led': now,
                ':ced': cert_not_after,
                ':ps': secret_name
            }
        )
    else:
        # Create a new record
        table.put_item(Item={
            'TagKeyValue': f"{tag_key}#{tag_value}",
            'CertificateArn#CertName': f"{cert_arn}#{cert_name}",
            'CertificateArn': cert_arn,
            'CertName': cert_name,
            'TargetTagKey': tag_key,
            'TargetTagValue': tag_value,
            'Passphrase': secret_name,
            'CertExpiryDate': cert_not_after,
            'LastExportedDate': now
        })

    # Send certificate to EC2 via SSM
    ssm_response = ssm_client.send_command(
        DocumentName='Install-ACMCertificate',
        Targets=[
            {
                'Key': f'tag:{tag_key}',
                'Values': [tag_value]
            }
        ],
        Parameters={
            'CertName': [cert_name],
            'CertBase64': [event['CertificateBase64']],
            'KeyBase64': [event['PrivateKeyBase64']],
            'ChainBase64': [event['CertificateChainBase64']],
            'PassphraseSecretName': [secret_name]
        },
        Comment=f"Installing cert {cert_name} to EC2s tagged {tag_key}={tag_value}"
    )

    return {
        'CommandId': ssm_response['Command']['CommandId'],
        'CertificateArn': cert_arn
    }
