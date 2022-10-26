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

import aws_cdk as cdk
import aws_cdk.aws_ec2 as ec2
import aws_cdk.aws_efs as efs
from constructs import Construct


class Datastore(Construct):
    def __init__(self, scope: Construct, id_: str, *, vpc: ec2.IVpc):
        super().__init__(scope, id_)

        self.efs_file_system = efs.FileSystem(
            self,
            "EFSFileSystem",
            removal_policy=cdk.RemovalPolicy.DESTROY,
            vpc=vpc,
        )
        self.efs_access_point = self.efs_file_system.add_access_point("AccessPoint")

    def allow_connections_from(self, *others: ec2.IConnectable) -> None:
        for other in others:
            self.efs_file_system.connections.allow_default_port_from(other)
