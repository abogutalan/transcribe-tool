# Transcribe Tool

The purpose of this Transcribe tool is to be able to perform AWS Transcribe on an audio file in S3 bucket.

## Getting Started

### AWS Setup

Setup the AWS CLI version 2 in order to store the `aws_access_key_id` and `aws_secret_access_key`.  This two keys will be sue by the application to authenticate an AWS session.

1. Install the AWS CLI v2
    ```
    $ curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
    unzip awscliv2.zip
    sudo ./aws/install
    ```
    Reference: https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2-linux.html#cliv2-linux-install

2. Create an aws folder in your home and empty credentials file
    ```
    $ cd ~
    $ mkdir .aws
    $ cd .aws/
    $ touch credentials
    ```
3. Setup the credentials file
- Create a profile `claimns` and add the secret keys
    ```
    [claims]
    aws_access_key_id=xxxxxxxxxxxxxxx
    aws_secret_access_key=xxxxxxxxxxxxxxx
    ```
  NOTE: Enter the provide secret keys in the config



### Python Setup

Open project using an IDE like PyCharm.  Create a virtual environment `venv` and run the requirements.txt.

This can be done directly from an IDE like Pycharm.  See: https://www.jetbrains.com/help/pycharm/creating-virtual-environment.html

Alternatively, the virtual environment can be created in command line as followed.

Create a python virtual environment with Python 3.8.x and activate it
```
$ virtualenv venv --python=3.8
$ . venv/bin/activate
```

Install Python dependencies in requirements.txt
```
python -m pip install -r requirements.txt
```

## Program Flow
![program_flow](https://github.com/abogutalan/transcribe-tool/blob/master/tanscribe_process.png)

## Usage

The following describes the functionality available in the Transcribe Tool. When running a Transcribe job, an available .wav audio file is taken from the `Input` S3 folder for processing.  Once completed, the .wav is moved to the `Done` folder and the resulting transcription is place in the `Output` S3 folder. 

### Prepare to run Python script

Activate the virtual environment from the `claims-infrastructure-as-code` and locate the script.
```
$ source venv/bin/activate

$ cd tools/transcribe_tool/ 
```

### Get script usage manual

Use the -h command of the script to get a usage manual
```
$ python3 transcribe_tool.py -h

usage: transcribe_tool.py [-h] [-o output_dir] [-i input_path] [-l language] [-c amount]  command

Transcribe Tool

positional arguments:
   command       Type of operation to execute: ['TRANSCRIBE']

optional arguments:
  -h, --help     show this help message and exit
  -o output_dir  The directory where to save transcriptions
  -i input_path  Path to an audio file for UPLOAD command
  -l language    To which language is the transcript being translated to
  -c amount      The amount of calls to be transcribed

```



### Running Transcribe Jobs

Start the Transcribe jobs by fetching at most 500 available audio files from the `Input` S3 bucket.
```
$ python3 transcribe_tool.py TRANSCRIBE -o IntactUnderwriters -l E -c 500 -t wav
```


## S3 Bucket Structure

The following is the S3 bucket file structure for this tool.

    .                           # Root S3 bucket `dev-audio-metadata-claims`
    ├── Input                   # Input folder contains all the .wav files that were uploaded
    ├── Output                  # Output folder contains the transcription jobs (.JSON)
    └── Processing              # Processing folder contains process wav files

### Useful commands

List Output folder
```
$ aws s3 ls s3://test-transcripts-calls/Output/
```

See how many calls are transcribed for IntactUnderwriters
```
$ aws s3 ls s3://test-transcripts-calls/Output/IntactUnderwriters/ | wc -l
```

If you ever get the error below, just try the same python execution command
```
botocore.exceptions.ClientError: An error occurred (AccessDenied) when calling the ListObjectsV2 operation: Access Denied
```
