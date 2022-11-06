FROM ubuntu:latest

RUN apt-get update && apt install curl jq -y && apt-get clean && apt-get autoclean && apt-get autoremove

SHELL ["/bin/bash", "-c"]

RUN curl -L -O https://github.com/fermyon/spin/releases/download/v0.6.0/spin-v0.6.0-linux-amd64.tar.gz \
    && tar -zxvf spin-v0.6.0-linux-amd64.tar.gz \
    && mv spin /usr/local/bin/spin

ENV PORT 3000

# Lambda function requires that the container listens on port 3000
EXPOSE ${PORT}

# Lambda function local runtime (to run the image locally)
RUN curl -L -o /usr/bin/lambda_rie https://github.com/aws/aws-lambda-runtime-interface-emulator/releases/download/v1.2/aws-lambda-rie-x86_64
RUN chmod +x /usr/bin/lambda_rie

# Lambda adapter
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.4.1 /lambda-adapter /opt/extensions/lambda-adapter

# The container need to be laucnhed with EFS_MOUNT_PATH variable set.
# EFS_MOUNT_PATH should be a path under /mnt. This is required for Lambda function.
# This assumes that files/artifacts are mounted on the folder specified in EFS_MOUNT_PATH.
# The --disable-cache and --log-dir flags are required because of the lambda restrictive environment (only /tmp is R/W)
CMD spin up --listen 0.0.0.0:${PORT} --disable-cache --log-dir /tmp --file ${EFS_MOUNT_PATH}/spin-hello-world/spin.toml
