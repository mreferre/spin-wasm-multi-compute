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

import aws_cdk.aws_ec2 as ec2
import aws_cdk.aws_ecs as ecs
import aws_cdk.aws_elasticloadbalancingv2 as elasticloadbalancingv2
import aws_cdk.aws_elasticloadbalancingv2_targets as elasticloadbalancingv2_targets
import aws_cdk.aws_lambda as lambda_
from constructs import Construct

import constants


class LoadBalancer(Construct):
    def __init__(
        self,
        scope: Construct,
        id_: str,
        *,
        ec2_instance: ec2.Instance,
        ecs_fargate_service: ecs.FargateService,
        lambda_function: lambda_.IFunction,
        vpc: ec2.IVpc,
    ):
        super().__init__(scope, id_)

        self._elb_alb = elasticloadbalancingv2.ApplicationLoadBalancer(
            self,
            "ELBALB",
            internet_facing=True,
            vpc=vpc,
        )

        ec2_target_group = self._create_ec2_target_group(ec2_instance, vpc, weight=1)
        ecs_target_group = self._create_ecs_target_group(
            ecs_fargate_service, vpc, weight=1
        )
        lambda_target_group = self._create_lambda_target_group(
            lambda_function, weight=1
        )

        listener = self._elb_alb.add_listener("Listener", port=80)
        listener.add_action(
            "Action",
            action=elasticloadbalancingv2.ListenerAction.weighted_forward(
                target_groups=[ec2_target_group, ecs_target_group, lambda_target_group]
            ),
        )

        self.endpoint = self._elb_alb.load_balancer_dns_name

    def _create_ec2_target_group(
        self, ec2_instance: ec2.Instance, vpc: ec2.IVpc, *, weight: int
    ) -> elasticloadbalancingv2.WeightedTargetGroup:
        self._elb_alb.connections.allow_to(
            ec2_instance,
            port_range=ec2.Port(
                protocol=ec2.Protocol.TCP,
                string_representation=str(constants.SPIN_PORT),
                from_port=constants.SPIN_PORT,
                to_port=constants.SPIN_PORT,
            ),
        )
        target_group = elasticloadbalancingv2.ApplicationTargetGroup(
            self,
            "ELBApplicationTargetGroupEC2Instance",
            port=constants.SPIN_PORT,
            protocol=elasticloadbalancingv2.ApplicationProtocol.HTTP,
            targets=[elasticloadbalancingv2_targets.InstanceTarget(ec2_instance)],
            vpc=vpc,
        )
        weighted_target_group = elasticloadbalancingv2.WeightedTargetGroup(
            target_group=target_group,
            weight=weight,
        )
        return weighted_target_group

    def _create_ecs_target_group(
        self, ecs_fargate_service: ecs.FargateService, vpc: ec2.IVpc, *, weight: int
    ) -> elasticloadbalancingv2.WeightedTargetGroup:
        target_group = elasticloadbalancingv2.ApplicationTargetGroup(
            self,
            "ELBApplicationTargetGroupECSFargateService",
            port=constants.SPIN_PORT,
            protocol=elasticloadbalancingv2.ApplicationProtocol.HTTP,
            targets=[ecs_fargate_service],
            vpc=vpc,
        )
        weighted_target_group = elasticloadbalancingv2.WeightedTargetGroup(
            target_group=target_group,
            weight=weight,
        )
        return weighted_target_group

    def _create_lambda_target_group(
        self, lambda_function: lambda_.IFunction, *, weight: int
    ) -> elasticloadbalancingv2.WeightedTargetGroup:
        target_group = elasticloadbalancingv2.ApplicationTargetGroup(
            self,
            "ELBApplicationTargetGroupLambdaFunction",
            targets=[elasticloadbalancingv2_targets.LambdaTarget(lambda_function)],
        )
        weighted_target_group = elasticloadbalancingv2.WeightedTargetGroup(
            target_group=target_group,
            weight=weight,
        )
        return weighted_target_group
