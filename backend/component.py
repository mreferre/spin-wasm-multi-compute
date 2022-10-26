# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

from typing import Any

import aws_cdk as cdk
import aws_cdk.aws_ec2 as ec2
from constructs import Construct

from backend.compute.infrastructure import Compute
from backend.datastore.infrastructure import Datastore
from backend.load_balancer.infrastructure import LoadBalancer


class Backend(cdk.Stack):
    def __init__(
        self,
        scope: Construct,
        id_: str,
        **kwargs: Any,
    ):
        super().__init__(scope, id_, **kwargs)

        vpc = ec2.Vpc.from_lookup(scope=self, id="VPC", is_default=True)
        datastore = Datastore(
            self,
            "Datastore",
            vpc=vpc,
        )
        compute = Compute(
            self,
            "Compute",
            efs_access_point=datastore.efs_access_point,
            efs_file_system_id=datastore.efs_file_system.file_system_id,
            vpc=vpc,
        )
        datastore.allow_connections_from(
            compute.ec2_instance, compute.ecs_fargate_service, compute.lambda_function
        )
        load_balancer = LoadBalancer(
            self,
            "LoadBalancer",
            ec2_instance=compute.ec2_instance,
            ecs_fargate_service=compute.ecs_fargate_service,
            lambda_function=compute.lambda_function,
            vpc=vpc,
        )
        self.load_balancer_endpoint = cdk.CfnOutput(
            self,
            "LoadBalancerEndpoint",
            value=load_balancer.endpoint,
        )
