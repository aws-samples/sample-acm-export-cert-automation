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
    passphrase = event.get('Passphrase', 'unknown')

    table = dynamodb.Table('CertTagMapping')

    # Check if record exists
    response = table.get_item(Key={'CertificateArn': cert_arn})
    item = response.get('Item')

    # Get expiry from ACM
    cert_description = acm_client.describe_certificate(CertificateArn=cert_arn)
    cert_not_after = cert_description['Certificate']['NotAfter'].isoformat() + 'Z'

    if item:
        # Update LastExportedDate and CertExpiryDate
        table.update_item(
            Key={'CertificateArn': cert_arn},
            UpdateExpression="SET LastExportedDate = :led, CertExpiryDate = :ced",
            ExpressionAttributeValues={
                ':led': datetime.utcnow().isoformat() + 'Z',
                ':ced': cert_not_after
            }
        )
    else:
        # Create new mapping entry
        table.put_item(Item={
            'CertificateArn': cert_arn,
            'Passphrase': passphrase,
            'CertName': cert_name,
            'TargetTagKey': tag_key,
            'TargetTagValue': tag_value,
            'CertExpiryDate': cert_not_after,
            'LastExportedDate': datetime.utcnow().isoformat() + 'Z'
        })

    # SendCommand using provided tag and certs
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
            'ChainBase64': [event['CertificateChainBase64']]
        },
        Comment=f"Installing cert {cert_name} to EC2 instances with tag {tag_key}={tag_value}"
    )

    return {
        'CommandId': ssm_response['Command']['CommandId'],
        'CertificateArn': cert_arn
    }
