import boto3
import base64

acm_client = boto3.client('acm')

def lambda_handler(event, context):
    cert_arn = event['CertificateArn']
    passphrase = event['Passphrase']
    cert_name = event['CertName']
    tag_key = event['TargetTagKey']
    tag_value = event['TargetTagValue']

    # Export Certificate
    response = acm_client.export_certificate(
        CertificateArn=cert_arn,
        Passphrase=passphrase.encode('utf-8')
    )

    # Return everything needed for next step
    return {
        'CertificateArn': cert_arn,
        'CertificateBase64': base64.b64encode(response['Certificate'].encode('utf-8')).decode('utf-8'),
        'PrivateKeyBase64': base64.b64encode(response['PrivateKey'].encode('utf-8')).decode('utf-8'),
        'CertificateChainBase64': base64.b64encode(response['CertificateChain'].encode('utf-8')).decode('utf-8'),
        'CertName': cert_name,
        'TargetTagKey': tag_key,
        'TargetTagValue': tag_value,
        'Passphrase': passphrase
    }
