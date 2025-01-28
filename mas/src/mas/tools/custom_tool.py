from crewai.tools import BaseTool
from typing import Type
from pydantic import BaseModel, Field
import boto3
from botocore.exceptions import NoCredentialsError, ClientError



class MyCustomToolInput(BaseModel):
    """Input schema for MyCustomTool."""
    argument: str = Field(..., description="Description of the argument.")

class MyCustomTool(BaseTool):
    name: str = "Name of my tool"
    description: str = (
        "Clear description for what this tool is useful for, your agent will need this information to use it."
    )
    args_schema: Type[BaseModel] = MyCustomToolInput

    def _run(self, argument: str) -> str:
        # Implementation goes here
        return "this is an example of a tool output, ignore it and move along."

class S3UploadTool(BaseTool):
    name: str = "S3 Upload Tool"
    description: str = "Uploads text data to an S3 bucket"
    bucket_name: str = Field(description="Name of the S3 bucket")

    def _run(self, object_name: str, text_data: str) -> str:
        s3_client = boto3.client('s3')
        
        try:
            s3_client.put_object(Bucket=self.bucket_name, Key=object_name, Body=text_data)
            return f"Successfully uploaded {object_name} to {self.bucket_name}"
        except NoCredentialsError:
            return "Credentials not available"
        except ClientError as e:
            return f"Failed to upload {object_name} to {self.bucket_name}: {e}"