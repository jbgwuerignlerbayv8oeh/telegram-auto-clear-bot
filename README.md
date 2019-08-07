# telegram-auto-clear-bot

Telegram bot for auto remove messages



## Setup process

1. Install AWS CLI and SAM CLI
   
   See: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-install.html
   
   You can skip **Step 5: Install Docker**

1. Create Telegram bot
   
   See: https://core.telegram.org/bots#botfather

1. Store your Telegram bot token into AWS SSM
   
   See: https://docs.aws.amazon.com/systems-manager/latest/userguide/param-create-console.html
   
   Set the parameter as:
   
      - Name: `MessageAutoClearTelegramBotToken`
      - Type: `String`
      - Value: `{your_bot_token}`

1. Deploy app to AWS
   
   See: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-getting-started-hello-world.html
   
   ```
   # You can skip it if your have done in Step 1, Create a bucket to store packaged code
   aws s3 mb s3://{BUCKET_NAME}
   
   # Build the source code
   sam build
   
   # Package the app
   sam package --output-template packaged.yaml --s3-bucket {BUCKET_NAME}
   
   # Deploy to AWS using CloudFormation
   sam deploy --template-file packaged.yaml --stack-name {STACK_NAME} --capabilities CAPABILITY_IAM
   ```

1. Set bot webhook
   1. Get the API endpoint from CloudFormation panel
   
      Go into your named stack in CloudFormation, i.e. {STACK_NAMAE}. Look for `MainApi` in Output tab. You will see the API endpoint e.g. `https://xxxxxxxxx.execute-api.us-east-1.amazonaws.com/Prod/`

   1. Set the webhook using Telegram Bot Api `setWebhook`
      
      Set the webhook appended by your bot token i.e.: `https://xxxxxxxxx.execute-api.us-east-1.amazonaws.com/Prod/{token}`


## Configuration

##### `template.yaml`
   
   1. Scheduler Interval
      
      This will affect how frequently the bot check whether it's time to clear message
      e.g. if set to `rate(10 minutes)` and the next clear time is 00:02 a.m. the bot will actually clear message at 00:10 a.m.
      ```yaml
      ...
      Resources:
		...
        SchedulerFunction:
          Type: AWS::Serverless::Function
          Properties:
            ...
            Events:
              Scheduler:
                Type: Schedule
                Properties:
                  Schedule: rate(10 minutes)  # Change the interval here e.g. rate(10 minutes) , rate(2 hours), etc.
       ```
       
   1. Worker function timeout and allowed memory
      
      Since the worker function will open threads to clear messages one by one, it's important to allocate enough memory to them, and allow more time for them to do its job
      ```yaml
      ...
      Resources:
        ...
        WorkerFunction:
          Type: AWS::Serverless::Function
          Properties:
            ...
            Timeout: 600  # Change allowed runtime here, unit is second e.g. 600 seconds
            MemorySize: 3008  # Change allowed memory here, unit is MB, 3008 MB is maximum
            Policies:
              ...
      ```
        
##### `main/clear_message_worker.py`
   1. Message clear threading
      By default, the bot will clear 100 messages in a batch at the same time, and wait for 10 seconds before clearing next batch. You can change the batch size, and the wait time between batches
      ```python
      def lambda_handler(event, context):
        # ...
        splited_list = [message_id_list[x : x + 100] for x in range(0, len(message_id_list), 100)]  # Change the number 100 to any integer as batch size
    
        for current_message_id_list in splited_list:
            # ...
            time.sleep(10)  # Change the wait time between batches here, unit is second, e.g. 10 seconds
    
      # ...
      ```
