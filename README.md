# telegram-auto-clear-bot

Telegram bot for auto remove messages

## Setup process

1. Install AWS CLI and SAM CLI, see: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-install.html

1. Create Telegram bot, see: https://core.telegram.org/bots#botfather

1. Store your Telegram bot token into AWS SSM, see: https://docs.aws.amazon.com/systems-manager/latest/userguide/param-create-console.html. Set the parameter name as `MessageAutoClearTelegramBotToken`

1. Deploy app to AWS
     See: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-getting-started-hello-world.html
  ```
aws s3 mb s3://{BUCKET_NAME}    # Create a bucket to store packaged code
sam build    # Build the source code
sam package --output-template packaged.yaml --s3-bucket {BUCKET_NAME}    # Package the app
sam deploy --template-file packaged.yaml --stack-name {STACK_NAME} --capabilities CAPABILITY_IAM    # Deploy to AWS using CloudFormation
```


5. Set bot webhook
    1. Get the API endpoint from CloudFormation panel
        Go into your named stack in CloudFormation, i.e. {STACK_NAMAE}. Look for `MainApi` in Output tab. You will see the API endpoint e.g. `https://xxxxxxxxx.execute-api.us-east-1.amazonaws.com/Prod/`

    1. Set the webhook using Telegram Bot Api `setWebhook`
        Set the webhook appended by your bot token i.e.: `https://xxxxxxxxx.execute-api.us-east-1.amazonaws.com/Prod/{token}`
