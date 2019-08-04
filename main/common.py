import boto3

"""
Get telegram bot token from SSM
"""
def get_telegram_bot_token():
    ssm_client = boto3.client('ssm')
    response = ssm_client.get_parameter(
        Name='MessageAutoClearTelegramBotToken'
    )

    if 'Parameter' not in response:
        return None

    if 'Value' not in response['Parameter']:
        return None

    return response['Parameter']['Value']
