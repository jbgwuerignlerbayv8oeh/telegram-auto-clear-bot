# -*- coding: utf-8

import boto3
import datetime

from telegram import Bot

from common import get_telegram_bot_token
from telegram.error import ChatMigrated

"""
Handle Chat ID change, move old record to record with new chat # IDEA:
"""
def change_chat_id(chat_id, new_chat_id):
    # Get related chat
    response = dynamodb_client.scan(
        TableName = 'telegram-auto-clear-bot-chats',
        Select = 'ALL_ATTRIBUTES',
        ExpressionAttributeValues = {
            ":chat_id": {
                "S": str(chat_id)
            }
        },
        FilterExpression = 'chat_id = :chat_id'
    )

    if not response:
        return

    if 'Items' not in response or len(response['Items']) == 0 or not response['Items'][0]:
        return

    item = response['Items'][0]

    # Use new chat ID
    item['chat_id'] = {
        'S': str(new_chat_id)
    }

    # Create new item with new chat ID
    response = dynamodb_client.put_item(
        TableName = 'telegram-auto-clear-bot-chats',
        Item = item
    )

    # Remove old record
    response = dynamodb_client.delete_item(
        TableName = 'telegram-auto-clear-bot-chats',
        Key = {
            'chat_id': {
                'S': str(chat_id)
            }
        }
    )
    return

"""
Clear messages in specific chat
"""
def clear_messages(bot, dynamodb_client, chat_id, last_deleted_message_id, clear_message_interval):
    try:
        message = bot.send_message(chat_id = chat_id, text = "正在刪除訊息")
    except ChatMigrated as e:   # Chat ID changed
        new_chat_id = e.new_chat_id
        change_chat_id(dynamodb_client, chat_id, new_chat_id)
        chat_id = new_chat_id
        message = bot.send_message(chat_id = chat_id, text = "正在刪除訊息")
    except:
        return


    if not message or not message.message_id:
        return

    message_id = message.message_id

    start_from = message_id - 20    # Retain latest messages

    # Flag for getting latest deleted message ID
    has_deleted = False
    latest_deleted_message_id = 1

    # Loop through message ID from last time deleted message ID to latest message ID
    for i in reversed(range(last_deleted_message_id, start_from)):
        try:
            if bot.delete_message(chat_id, i, timeout = 0.00001) and not has_deleted:
                latest_deleted_message_id = i    # Mark the latest deleted message, will be saved to `Chat` table
                has_deleted = True
        except:
            pass

    # Get next clear time
    now = datetime.datetime.now()
    next_clear_time = now + datetime.timedelta(hours = clear_message_interval)  # certain hours later
    next_clear_time_timestamp = int(next_clear_time.timestamp())

    # Save latest deleted message and next clear time into `Chat` table
    response = dynamodb_client.update_item(
        TableName = 'telegram-auto-clear-bot-chats',
        Key = {
            'chat_id' : {
                'S' : str(chat_id)
            }
        },
        ExpressionAttributeValues = {
            ":latest_deleted_message_id": {
                "N": str(latest_deleted_message_id)
            },
            ":next_clear_time_timestamp": {
                "N": str(next_clear_time_timestamp)
            }
        },
        UpdateExpression = 'SET last_deleted_message_id = :latest_deleted_message_id, next_clear_time = :next_clear_time_timestamp'
    )


"""
Main lambda handler, handle event from CloudWatch
"""
def lambda_handler(event, context):
    token = get_telegram_bot_token()    # Get telegram bot token

    # Return if no token found
    if not token:
        return

    # Init Bot instance
    bot = Bot(token)

    # Get chat to be cleared
    dynamodb_client = boto3.client('dynamodb')


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

        # Get clear message interval, set to 12 hours if no record
        if 'clear_message_interval' in item and 'N' in item['clear_message_interval']:
            clear_message_interval = int(item['clear_message_interval']['N'])
        else:
            clear_message_interval = 12


        clear_messages(bot, dynamodb_client, chat_id, last_deleted_message_id, clear_message_interval)

    return
