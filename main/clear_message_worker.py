# -*- coding: utf-8

import datetime
import threading
import time
import boto3

from telegram import Bot
from telegram.utils.request import Request

from telegram.error import ChatMigrated

from common import get_telegram_bot_token

# Customized class for getting result from thread
class ReturnResultThread(threading.Thread):
	target = None
	args = None
	kwargs = None

	def __init__(self, group=None, target=None, name=None, args=(), kwargs={}, *, daemon=None):
		super().__init__(group = group, target = target, name = name, args = args, kwargs = kwargs, daemon = daemon)
		self._return = None
		self.target = target
		self.args = args
		self.kwargs = kwargs

	def run(self):
		if self.target is not None:
			try:
				self._return = self.target(*self.args, **self.kwargs)
			except Exception as e:
				return

	def join(self, timeout=None):
		super().join(timeout)
		return self._return

"""
Handle Chat ID change, move old record to record with new chat # IDEA:
"""
def change_chat_id(dynamodb_client, chat_id, new_chat_id):
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
def lambda_handler(event, context):
    # Get params from event
    chat_id = event['chat_id']
    last_deleted_message_id = event['last_deleted_message_id']
    clear_message_interval = event['clear_message_interval']

    token = get_telegram_bot_token()    # Get telegram bot token

    # Return if no token found
    if not token:
        return

    # Init Request instance
    request = Request(con_pool_size = 10000, connect_timeout = 2, read_timeout = 2)

    # Init Bot instance
    bot = Bot(token, request = request)

    # Get DynamoDB clients
    dynamodb_client = boto3.client('dynamodb')

    try:
        message = bot.send_message(chat_id = chat_id, text = "正在刪除訊息", timeout = 120)
    except ChatMigrated as e:   # Chat ID changed
        print("Chat ID: %s" % str(chat_id))
        print(e)

        new_chat_id = e.new_chat_id
        change_chat_id(dynamodb_client, chat_id, new_chat_id)
        chat_id = new_chat_id
        message = bot.send_message(chat_id = chat_id, text = "正在刪除訊息", timeout = 120)
    except Exception as e:
        print("Chat ID: %s" % str(chat_id))
        print(e)
        return


    if not message or not message.message_id:
        return

    message_id = message.message_id

    start_from = message_id - 5    # Retain latest messages

    # Saving latest deleted message ID
    latest_deleted_message_id = 1


    # Loop through message ID from last time deleted message ID to latest message ID
    message_id_list = list(range(last_deleted_message_id, start_from))

    # Split the list every 500 items
    splited_list = [message_id_list[x : x + 500] for x in range(0, len(message_id_list),500)]

    for current_message_id_list in splited_list:   # Run specific number of threads in a time
        thread_list = {}    # Reset thread list

        for i in current_message_id_list:
            thread = ReturnResultThread(target = bot.delete_message, args = (chat_id, i))
            thread.start()
            thread_list[i] = thread

        time.sleep(5)  # Wait for 5 seconds

        for i, thread in thread_list.items():
            if not thread.is_alive():	# Thread finished
                result = thread.join()
                if i > latest_deleted_message_id:
                    latest_deleted_message_id = i

        # Save latest deleted message into `Chat` table
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
                }
            },
            UpdateExpression = 'SET last_deleted_message_id = :latest_deleted_message_id'
        )


    # Get next clear time
    now = datetime.datetime.now()
    next_clear_time = now + datetime.timedelta(hours = clear_message_interval)  # certain hours later
    next_clear_time_timestamp = int(next_clear_time.timestamp())

    # Save next clear time into `Chat` table
    response = dynamodb_client.update_item(
        TableName = 'telegram-auto-clear-bot-chats',
        Key = {
            'chat_id' : {
                'S' : str(chat_id)
            }
        },
        ExpressionAttributeValues = {
            ":next_clear_time_timestamp": {
                "N": str(next_clear_time_timestamp)
            }
        },
        UpdateExpression = 'SET next_clear_time = :next_clear_time_timestamp'
    )

    return
