deploy:
	sam build
	sam package --profile $(PROFILE_NAME) --output-template packaged.yaml --s3-bucket $(BUCKET_NAME)
	sam deploy --profile $(PROFILE_NAME) --template-file packaged.yaml --stack-name $(STACK_NAME) --capabilities CAPABILITY_IAM
