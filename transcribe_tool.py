#!/usr/bin/python3
import argparse
import datetime
import os
import time

from boto3 import Session
from botocore.exceptions import ClientError


class AWSSessionManager:
    def __init__(self, aws_arn_role: str, session_name: str):
        self.aws_arn_role = aws_arn_role
        self.region_name = "ca-central-1"

        # Get the aws_access_key_id & aws_secret_access_key
        # from your ~ ./aws/credentials
        session = Session(profile_name="transcribe")

        # Request an AWS Security Token Service to grant temporary access
        sts_connection = session.client(
            "sts", region_name=self.region_name, verify=False
        )
        assume_role_object = sts_connection.assume_role(
            RoleArn=self.aws_arn_role,
            RoleSessionName=session_name,
            DurationSeconds=3600,
        )

        # Save temporary credentials
        self.credentials = assume_role_object["Credentials"]

    def __call__(self):
        """
        Use the provided AWS keys and ARN Role to generate a Session
        :return: Return an AWS session
        """
        access_key = self.credentials["AccessKeyId"]
        secret_key = self.credentials["SecretAccessKey"]
        security_token = self.credentials["SessionToken"]

        boto3_session = Session(
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            aws_session_token=security_token,
        )
        return boto3_session


class TranscribeTool:
    def __init__(self, env, file_type):
        self.purpose = f"{env.lower()}-test"
        self.file_format = file_type
        self.s3_bucket = "test-transcripts-calls"
        self.region_name = "ca-central-1"
        self.language_mapping = {"E": "en-US", "F": "fr-CA"}

        # Get the AWS Transcribe client
        aws_session_manager = AWSSessionManager(
            aws_arn_role="arn:aws:iam::761944119947:role/"
            "claims_transcribe_data_access_role_dev",
            session_name="transcribe_session",
        )

        boto3_session = aws_session_manager()
        self.transcribe_client = boto3_session.client(
            service_name="transcribe", region_name=self.region_name
        )

        # Get the AWS S3 Client
        aws_session_manager = AWSSessionManager(
            aws_arn_role="arn:aws:iam::761944119947:role/"
            "claims-audioexport-role-non-production",
            session_name="s3_session",
        )

        boto3_s3_session = aws_session_manager()
        self.s3_client = boto3_s3_session.client(
            service_name="s3", region_name=self.region_name
        )

    def _generate_job_name(self, audio_file: str):
        """
        Generate a unique job name for an audio file
        :param audio_file: Source filename
        :return: A unique filename
        """
        call = audio_file.split(".")[0]
        return f"{self.purpose}-{call}"

    def _start_transcription_job(
        self, audio_file_key: str, env: str, audio_language: str
    ):
        """
        Start a Transcribed job in AWS
        :param audio_file_key:
        The S3 key where the audio file should be located
        :param audio_language:
        Transcription audio language (by default is English)
        :return:
        The S3 key for the transcription JSON file that was generated
        """
        audio_file = os.path.basename(audio_file_key)
        job_name = self._generate_job_name(audio_file)
        job_uri = f"s3://{self.s3_bucket}/{audio_file_key}"

        if env:
            output_json_key = f"Output/{env}/{job_name}.json"
        else:
            output_json_key = f"Output/{job_name}.json"

        if not self._s3_object_exist(output_json_key):
            # Call AWS Transcribe with the provided configuration
            self.transcribe_client.start_transcription_job(
                TranscriptionJobName=job_name,
                MediaFormat=self.file_format,
                Media={"MediaFileUri": job_uri},
                LanguageCode=self.language_mapping[audio_language],
                OutputBucketName=self.s3_bucket,
                OutputKey=output_json_key,
                Settings={
                    "ChannelIdentification": False,
                    "ShowSpeakerLabels": True,
                    "MaxSpeakerLabels": 3,
                    "ShowAlternatives": True,
                    "MaxAlternatives": 2,
                },
            )
        else:
            print_message(f"{output_json_key} key is already transcribed")

    def _s3_object_exist(self, key: str):
        """
        Validate if an S3 object exists
        :param key: The S3 key of an object
        :return: True if the key was found and False otherwise
        """
        try:
            self.s3_client.head_object(Bucket=self.s3_bucket, Key=key)
            return True
        except self.s3_client.exceptions.NoSuchKey:
            return False
        except ClientError as e:
            status_code = e.response["ResponseMetadata"]["HTTPStatusCode"]
            if status_code == 404:
                return False
            raise e

    def _move_s3_object(self, s3_audio_key: str, destination_prefix="", env=""):
        """
        Move an audio S3 object from Input to destination folder
        :param s3_audio_key: The S3 key of the wav object
        """
        audio_key = os.path.basename(s3_audio_key)
        audio_input_key = f"Input/{env}/{audio_key}"
        destination_prefix = f"{destination_prefix}/{env}"

        if self._s3_object_exist(key=audio_input_key):
            copy_source = {"Bucket": self.s3_bucket, "Key": audio_input_key}
            self.s3_client.copy(
                copy_source, self.s3_bucket, f"{destination_prefix}/{audio_key}"
            )
            self.s3_client.delete_object(Bucket=self.s3_bucket, Key=audio_input_key)
            print_message(
                f"Moved s3 object `{audio_key}` " f"to the {destination_prefix} folder"
            )
            return f"{destination_prefix}/{audio_key}"
        else:
            print_message(
                f"{audio_key} can not be moved to {destination_prefix}. It doesn't exist."
            )
        return s3_audio_key

    def _get_s3_bucket_object_keys(
        self,
        prefix: str,
        extension: str,
        source: str,
        max_items: int = 500,
        print_list: bool = False,
    ):
        """
        Get a list of S3 object keys from the Bucket
        :param prefix: S3 folder name
        :param extension: File extension
        :param max_items: Maximum number of objects to return
        :param print_list: Boolean to enable the print of S3 object found
        :return: A list of S3 keys for the specified S3 folder and extension
        """
        s3_bucket_objects = list()

        s3_result = self.s3_client.list_objects_v2(
            Bucket=self.s3_bucket, Prefix=prefix, MaxKeys=max_items
        )

        if "Contents" in s3_result:
            if print_list:
                print_message(f"Listing a MAX of {max_items} files from {source}")
            index = 1
            for s3_object in s3_result["Contents"]:
                key = s3_object["Key"]
                if key.endswith(extension):
                    if print_list:
                        print_message(f"File #{index} found in S3 bucket: `{key}`")
                    s3_bucket_objects.append(key)
                    index += 1

        return s3_bucket_objects

    def start_process(
        self,
        env="",
        language="E",
        input_file="",
        max_calls=500,
    ):
        """
        Start the Transcribe process:
            1. Fetch audio files from Input folder
            2. Start Transcribe job
            3. Download transcription JSON file
        :param max_calls:
        Maximum number of calls that the program transcribes
        :param input_file:
        Input folder is where the program gets the calls
        Output folder and Input folder names are the same
        :param language:
        In which language the transcription will be
        :param env:
        The directory location where to save the downloaded transcriptions
        """

        input_prefix = "Input" if input_file == "" else f"Input/{input_file}"

        audio_file_keys = self._get_s3_bucket_object_keys(
            prefix=input_prefix,
            extension=f".{self.file_format}",
            source="S3 bucket",
            max_items=max_calls,
            print_list=True,
        )
        counter = 0
        for audio_file_key in audio_file_keys:

            processing_audio_file_key = self._move_s3_object(
                audio_file_key, destination_prefix="Processing", env=env
            )
            print_message(f"START Job: {processing_audio_file_key}")
            self._start_transcription_job(
                processing_audio_file_key, env=env, audio_language=language
            )
            counter = counter + 1

            if counter % 100 == 0:
                time.sleep(30)


def print_message(message: str):
    print(f"{datetime.datetime.now()} - {message}")


# Create the parser
argument_parser = argparse.ArgumentParser(description="Transcribe Tool")

# Add the arguments
argument_parser.add_argument(
    "command",
    metavar=" command",
    type=str,
    choices=["TRANSCRIBE"],
    help="Type of operation to execute: ['TRANSCRIBE']",
)

argument_parser.add_argument(
    "-o",
    metavar="output_dir",
    dest="output_dir",
    type=str,
    action="store",
    help="The directory where to save transcriptions",
)

argument_parser.add_argument(
    "-i",
    metavar="input_path",
    dest="input_path",
    action="store",
    help="Path to an audio file for UPLOAD command",
)

argument_parser.add_argument(
    "-l",
    metavar="language",
    dest="language",
    type=str,
    action="store",
    help="To which language is the transcript being translated to",
)

argument_parser.add_argument(
    "-c",
    metavar="amount",
    dest="amount",
    type=int,
    action="store",
    help="The amount of calls to be transcribed",
)

argument_parser.add_argument(
    "-t",
    metavar="type",
    dest="type",
    type=str,
    action="store",
    help="The file type of calls to be transcribed",
)


args = argument_parser.parse_args()

print_message("START Process")
command = args.command
print_message(f"Command: `{command}`")

# Start Transcribe Job
if command == "TRANSCRIBE":
    if not args.output_dir:
        argument_parser.error("TRANSCRIBE command requires `output_dir`")

    if not args.language:
        argument_parser.error("TRANSCRIBE command requires `language`")

    if not args.amount:
        argument_parser.error("TRANSCRIBE command requires `amount`")

    if args.amount > 500:
        argument_parser.error("Please enter an `amount` less than 500")

    if not args.type:
        argument_parser.error("TRANSCRIBE command requires `type`")

    transcribe_tool = TranscribeTool(args.output_dir, args.type)
    transcribe_tool.start_process(
        env=args.output_dir,
        language=args.language,
        input_file=args.output_dir,
        max_calls=args.amount,
    )

print_message("END Process")
