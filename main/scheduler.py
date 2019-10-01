# -*- coding: utf-8

import boto3
import datetime
import threading
import time
import json

from telegram import Bot
from telegram.utils.request import Request

from common import get_telegram_bot_token
from telegram.error import ChatMigrated


"""
Main lambda handler, handle event from CloudWatch
"""
def lambda_handler(event, context):
    # Get AWS service clients
    dynamodb_client = boto3.client('dynamodb')
    lambda_client = boto3.client('lambda')

    # Get current timestamp
    now = datetime.datetime.now()
    current_timestamp = int(now.timestamp())

    # Get chat list to be cleared
    response = dynamodb_client.scan(
        TableName = 'telegram-auto-clear-bot-chats',
        Select = 'ALL_ATTRIBUTES',
        ExpressionAttributeValues = {
            ":enabled": {
                "BOOL": True
            },
            ":currentTimestamp": {
                "N": str(current_timestamp)
            }
        },
        FilterExpression = 'enabled = :enabled AND next_clear_time <= :currentTimestamp'
    )

    if not response:
        return

    if 'Items' not in response:
        return

    for item in response['Items']:
        if 'chat_id' not in item or 'S' not in item['chat_id']:
            continue

        # Get chat ID from record
        chat_id = int(item['chat_id']['S'])

        # Get last deleted message ID, set to 1 if no previous record
        if 'last_deleted_message_id' in item and 'N' in item['last_deleted_message_id']:
            last_deleted_message_id = int(item['last_deleted_message_id']['N'])
        else:
            last_deleted_message_id = 1

        # UPDATE: Try to get interval from 'clear_message_interval_in_minute' field first
        if 'clear_message_interval_in_minute' in item and 'N' in item['clear_message_interval_in_minute']:
            clear_message_interval = int(item['clear_message_interval_in_minute']['N'])
        else:
            # Get clear message interval, set to 720 minutes (12 hours) if no record
            if 'clear_message_interval' in item and 'N' in item['clear_message_interval']:
                clear_message_interval = int(item['clear_message_interval']['N']) * 60  # Convert hour to minute
            else:
                clear_message_interval = 720

        lambda_client.invoke(
            FunctionName="telegram-auto-clear-bot-clear-message-worker",
            InvocationType='Event',
            Payload = json.dumps({
                'chat_id': chat_id,
                'last_deleted_message_id': last_deleted_message_id,
                'clear_message_interval': clear_message_interval
            })
        )

    return
