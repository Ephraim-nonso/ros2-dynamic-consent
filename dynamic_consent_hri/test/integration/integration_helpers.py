"""Small synchronous ROS probe used by Phase 8 launch-pytest suites."""

from __future__ import annotations

from collections import defaultdict
from contextlib import contextmanager
import time

import rclpy
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy


TRANSIENT_QOS = QoSProfile(
    depth=10,
    durability=DurabilityPolicy.TRANSIENT_LOCAL,
    reliability=ReliabilityPolicy.RELIABLE,
)


class RosProbe:
    """Collect selected topics and perform bounded publish/service actions."""

    def __init__(self, subscriptions):
        self.node = rclpy.create_node(
            f'phase8_probe_{time.monotonic_ns()}')
        self.messages = defaultdict(list)
        self._subscriptions = []
        self._publishers = {}
        for topic, message_type, qos in subscriptions:
            subscription = self.node.create_subscription(
                message_type,
                topic,
                lambda msg, name=topic: self.messages[name].append(msg),
                qos,
            )
            self._subscriptions.append(subscription)

    def wait_for_message(self, topic, predicate=lambda _msg: True,
                         timeout=10.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for index, message in enumerate(self.messages[topic]):
                if predicate(message):
                    return self.messages[topic].pop(index)
            rclpy.spin_once(self.node, timeout_sec=0.1)
        raise AssertionError(f'timed out waiting for {topic}')

    def assert_no_message(self, topic, predicate=lambda _msg: True,
                          duration=0.5):
        deadline = time.monotonic() + duration
        while time.monotonic() < deadline:
            rclpy.spin_once(self.node, timeout_sec=0.05)
            if any(predicate(message) for message in self.messages[topic]):
                raise AssertionError(f'unexpected message received on {topic}')

    def discard(self, topic):
        self.messages[topic].clear()

    def publish(self, topic, message, timeout=5.0):
        key = (topic, type(message))
        publisher = self._publishers.get(key)
        if publisher is None:
            publisher = self.node.create_publisher(type(message), topic, 10)
            self._publishers[key] = publisher

        deadline = time.monotonic() + timeout
        while (publisher.get_subscription_count() == 0
               and time.monotonic() < deadline):
            rclpy.spin_once(self.node, timeout_sec=0.05)
        if publisher.get_subscription_count() == 0:
            raise AssertionError(f'no subscriber discovered on {topic}')
        publisher.publish(message)

    def call(self, service_name, service_type, request, timeout=10.0):
        client = self.node.create_client(service_type, service_name)
        try:
            if not client.wait_for_service(timeout_sec=timeout):
                raise AssertionError(
                    f'service {service_name} was not discovered')
            future = client.call_async(request)
            rclpy.spin_until_future_complete(
                self.node, future, timeout_sec=timeout)
            if not future.done():
                raise AssertionError(
                    f'service {service_name} did not respond')
            if future.exception() is not None:
                raise AssertionError(
                    f'service {service_name} failed: {future.exception()}')
            return future.result()
        finally:
            self.node.destroy_client(client)

    def close(self):
        self.node.destroy_node()


@contextmanager
def running_probe(subscriptions):
    initialized_here = not rclpy.ok()
    if initialized_here:
        rclpy.init()
    probe = RosProbe(subscriptions)
    try:
        yield probe
    finally:
        probe.close()
        if initialized_here and rclpy.ok():
            rclpy.shutdown()
