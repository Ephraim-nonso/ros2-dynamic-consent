"""Terminal consent interface.

Only an explicit allow or refuse selection publishes a decision. Invalid
input, EOF, or closing this process leaves the request pending and therefore
denied.
"""

from __future__ import annotations

import sys

import rclpy
from rclpy.node import Node

from dynamic_consent_interfaces.msg import ConsentDecision, ConsentPrompt

from .ui_logic import (PromptView, UiChoice, format_more_information,
                       format_prompt, parse_choice)


def _to_view(msg: ConsentPrompt) -> PromptView:
    return PromptView(
        request_id=msg.request_id,
        session_id=msg.session_id,
        capability_id=msg.capability_id,
        sensor=msg.sensor,
        purpose=msg.purpose,
        prompt_text=msg.prompt_text,
        retention=msg.retention,
        expiry_seconds=msg.expiry_seconds,
    )


class ConsentUiNode(Node):

    def __init__(self) -> None:
        super().__init__('consent_ui')
        self._decision_pub = self.create_publisher(
            ConsentDecision, '/consent/decision', 10)
        self.create_subscription(
            ConsentPrompt, '/consent/prompt', self._on_prompt, 10)
        self._answered_requests: set[str] = set()
        self._input_stream = self._open_terminal_input()
        self.get_logger().info('terminal consent UI ready')

    @staticmethod
    def _open_terminal_input():
        try:
            return open('/dev/tty', 'r', encoding='utf-8')
        except OSError:
            return sys.stdin

    def _on_prompt(self, msg: ConsentPrompt) -> None:
        if msg.request_id in self._answered_requests:
            return

        prompt = _to_view(msg)
        print(format_prompt(prompt), flush=True)
        while rclpy.ok():
            print('Selection: ', end='', flush=True)
            value = self._input_stream.readline()
            if value == '':
                self.get_logger().warning(
                    'terminal input closed; request remains pending')
                return

            choice = parse_choice(value)
            if choice is UiChoice.MORE_INFORMATION:
                print(format_more_information(prompt), flush=True)
                continue
            if choice is None:
                print('Please enter 1, 2, or 3.', flush=True)
                continue

            decision = ConsentDecision()
            decision.request_id = msg.request_id
            decision.session_id = msg.session_id
            decision.capability_id = msg.capability_id
            decision.decision = (
                ConsentDecision.GRANTED
                if choice is UiChoice.ALLOW
                else ConsentDecision.REFUSED
            )
            decision.decided_at = self.get_clock().now().to_msg()
            self._decision_pub.publish(decision)
            self._answered_requests.add(msg.request_id)
            label = 'allowed' if choice is UiChoice.ALLOW else 'refused'
            self.get_logger().info(
                f'{msg.capability_id} explicitly {label}')
            return

    def destroy_node(self):
        if self._input_stream is not sys.stdin:
            self._input_stream.close()
        return super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = ConsentUiNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
