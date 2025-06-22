import boto3
import base64
import secrets
import json

acm_client = boto3.client('acm')
secrets_client = boto3.client('secretsmanager')

def generate_passphrase(length=32):
    return secrets.token_urlsafe(length)

def lambda_handler(event, context):
    cert_arn = event['CertificateArn']
    cert_name = event['CertName']
    tag_key = event['TargetTagKey']
    tag_value = event['TargetTagValue']
    
    passphrase = generate_passphrase()
    secret_name = f"acm-passphrase/{cert_name}"

    # Create or update secret and its value
    try:
        secrets_client.create_secret(
            Name=secret_name,
            SecretString=json.dumps({'passphrase': passphrase}),
            Tags=[{'Key': tag_key, 'Value': tag_value}]
        )
    except secrets_client.exceptions.ResourceExistsException:
        secrets_client.put_secret_value(
            SecretId=secret_name,
            SecretString=json.dumps({'passphrase': passphrase})
        )
        # Ensure secret has the correct up-to-date tag
        secrets_client.tag_resource(
            SecretId=secret_name,
            Tags=[{'Key': tag_key, 'Value': tag_value}]
        )

    # Export the certificate
    response = acm_client.export_certificate(
        CertificateArn=cert_arn,
        Passphrase=passphrase.encode('utf-8')
    )

    encode = lambda data: base64.b64encode(data.encode('utf-8')).decode('utf-8')

    return {
        'CertificateArn': cert_arn,
        'CertificateBase64': encode(response['Certificate']),
        'PrivateKeyBase64': encode(response['PrivateKey']),
        'CertificateChainBase64': encode(response['CertificateChain']),
        'CertName': cert_name,
        'TargetTagKey': tag_key,
        'TargetTagValue': tag_value,
        'PassphraseSecretName': secret_name
    }
