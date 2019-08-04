# -*- coding: utf-8

import json
import boto3
import datetime
import re

from telegram import Update
from telegram.ext import Updater, CommandHandler

from common import get_telegram_bot_token


"""
Handle /start command, return help message
"""
def start_command_handler(bot, update):
    help_text = '''
使用方法:

/enable_auto_clear <hour> - 設定每<hour>小時自動清除訊息 (最多47小時)

/disable_auto_clear - 停用自動清除功能

/get_next_clear_time - 查看下次清除訊息時間
    '''

    bot.send_message(chat_id = update.message.chat_id, text = help_text)
    return

"""
Handle /enable_auto_clear command, set enabled = True into `Chat` tabl
"""
def enable_auto_clear_command_handler(bot, update):
    chat_id = update.message.chat.id
    if not chat_id:
        return

    dynamodb_client = boto3.client('dynamodb')

    # Get interval in hour from command
    clear_message_interval = 12   # default to 12 hours
    if update.message.text:
        command_text = update.message.text

        regex = r"^\/enable\_auto\_clear\s+(\d{1,2})$"
        matches = re.search(regex, command_text)
        if matches:
            clear_message_interval = int(matches.group(1))

            # At most 47 hours
            if clear_message_interval > 47:
                clear_message_interval = 47


    # Get next clear time
    now = datetime.datetime.now()
    next_clear_time = now + datetime.timedelta(hours = clear_message_interval)  # certain hours later
    next_clear_time_timestamp = int(next_clear_time.timestamp())

    # Check if there is existing clear time earlier than the current one
    response = dynamodb_client.scan(
        TableName = 'telegram-auto-clear-bot-chats',
        Select = 'ALL_ATTRIBUTES',
        ExpressionAttributeValues = {
            ":chat_id": {
                "S": str(chat_id)
            },
            ":next_clear_time_timestamp": {
                "N": str(next_clear_time_timestamp)
            }
        },
        FilterExpression = 'chat_id = :chat_id AND next_clear_time < :next_clear_time_timestamp'
    )

    print(response)

    # If earlier timestamp found, use that one as next clear time
    if response and 'Items' in response and len(response['Items']) and 'next_clear_time' in response['Items'][0] and 'N' in response['Items'][0]['next_clear_time']:
        next_clear_time_timestamp = int(response['Items'][0]['next_clear_time']['N'])

    # Save chat ID, clear message interval and next clear time into `Chat` table
    response = dynamodb_client.update_item(
        TableName = 'telegram-auto-clear-bot-chats',
        Key = {
            'chat_id' : {
                'S' : str(chat_id)
            }
        },
        ExpressionAttributeValues = {
            ":enabled": {
                "BOOL": True
            },
            ":next_clear_time_timestamp": {
                "N": str(next_clear_time_timestamp)
            },
            ':clear_message_interval': {
                "N": str(clear_message_interval)
            }
        },
        UpdateExpression = 'SET enabled = :enabled, next_clear_time = :next_clear_time_timestamp, clear_message_interval = :clear_message_interval'
    )

    bot.send_message(chat_id = update.message.chat_id, text = ("已啟動自動刪除，每%d小時自動清除訊息" % clear_message_interval))

"""
Handle /disable_auto_clear command, set enabled = False into `Chat` table
"""
def disable_auto_clear_command_handler(bot, update):
    chat_id = update.message.chat.id
    if not chat_id:
        return

    dynamodb_client = boto3.client('dynamodb')

    response = dynamodb_client.update_item(
        TableName = 'telegram-auto-clear-bot-chats',
        Key = {
            'chat_id' : {
                'S' : str(chat_id)
            }
        },
        ExpressionAttributeValues = {
            ":enabled": {
                "BOOL": False
            }
        },
        UpdateExpression = 'SET enabled = :enabled'
    )

    bot.send_message(chat_id = update.message.chat_id, text = "已停用自動刪除")


"""
Handle /get_next_clear_time command, display next clear time
"""
def get_next_clear_time_command_handler(bot, update):
    chat_id = update.message.chat.id
    if not chat_id:
        return

    dynamodb_client = boto3.client('dynamodb')

    # Get record for related chat
    response = dynamodb_client.scan(
        TableName = 'telegram-auto-clear-bot-chats',
        Select = 'ALL_ATTRIBUTES',
        ExpressionAttributeValues = {
            ":enabled": {
                "BOOL": True
            },
            ":chat_id": {
                "S": str(chat_id)
            }
        },
        FilterExpression = 'enabled = :enabled AND chat_id = :chat_id'
    )

    if not response:
        bot.send_message(chat_id = chat_id, text = "已停用自動刪除")
        return

    if 'Items' not in response or len(response['Items']) == 0 or not response['Items'][0]:
        bot.send_message(chat_id = chat_id, text = "已停用自動刪除")
        return

    item = response['Items'][0]
    if 'next_clear_time' not in item or 'N' not in item['next_clear_time']:
        bot.send_message(chat_id = chat_id, text = "已停用自動刪除")
        return

    next_clear_timestamp = int(item['next_clear_time']['N'])

    next_clear_time = datetime.datetime.fromtimestamp(next_clear_timestamp)
    next_clear_time = next_clear_time + datetime.timedelta(hours = 8)   # For UTC+8
    next_clear_time_string = next_clear_time.strftime("%Y-%m-%d %H:%M:%S")

    bot.send_message(chat_id = chat_id, text = "下次清除訊息時間: %s" % next_clear_time_string)
    return

"""
Main lambda handler, handle event from API Gateway
"""
def lambda_handler(event, context):
    token = get_telegram_bot_token()    # Get telegram bot token

    # Return error if no token found
    if not token:
        return {
            'statusCode': 400
        }

    # Make sure the request url is end with the token
    # For security reason, please read: https://core.telegram.org/bots/api#setwebhook
    path = event['pathParameters']['proxy']
    if path != token:
        return {
            'statusCode': 400
        }

    # Init Updater, Dispatcher and Bot instance
    updater = Updater(token = token)
    dispatcher = updater.dispatcher
    bot = updater.bot

    # Parse request body into Update instance
    body = event['body']
    update = Update.de_json(json.loads(body), bot)

    # Add command handlers
    dispatcher.add_handler(CommandHandler('start', start_command_handler))
    dispatcher.add_handler(CommandHandler('enable_auto_clear', enable_auto_clear_command_handler))
    dispatcher.add_handler(CommandHandler('disable_auto_clear', disable_auto_clear_command_handler))
    dispatcher.add_handler(CommandHandler('get_next_clear_time', get_next_clear_time_command_handler))

    # Start process update
    dispatcher.process_update(update)

    # Return 200 OK
    return {
        "statusCode": 200,
        "body": ""
    }
