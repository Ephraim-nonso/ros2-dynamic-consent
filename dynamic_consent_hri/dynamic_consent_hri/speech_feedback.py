"""Display and optionally speak locally produced transcripts."""

from __future__ import annotations

import shutil
import subprocess
import threading

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class SpeechFeedbackNode(Node):

    def __init__(self) -> None:
        super().__init__('speech_feedback')
        self.declare_parameter('enable_tts', True)
        self.declare_parameter('tts_executable', 'espeak-ng')
        self._display_pub = self.create_publisher(
            String, '/assistant/transcript', 10)
        self._status_pub = self.create_publisher(
            String, '/assistant/speech_feedback/status', 10)
        self.create_subscription(
            String, '/perception/speech/transcript', self._on_transcript, 10)

    def _on_transcript(self, msg: String) -> None:
        text = msg.data.strip()
        if not text:
            return
        self._display_pub.publish(msg)
        if not bool(self.get_parameter('enable_tts').value):
            self._publish_status('displayed_without_tts')
            return
        executable = shutil.which(
            str(self.get_parameter('tts_executable').value))
        if executable is None:
            self.get_logger().warning(
                'espeak-ng unavailable; transcript was displayed only')
            self._publish_status('displayed:tts_unavailable')
            return
        # Keep participant speech out of the process command line.
        threading.Thread(
            target=self._speak,
            args=(executable, text),
            name='local-speech-feedback',
            daemon=True,
        ).start()
        self._publish_status('displayed_and_spoken')

    def _speak(self, executable: str, text: str) -> None:
        try:
            process = subprocess.Popen(
                [executable, '--stdin'],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
            )
            process.communicate(text)
        except OSError:
            self.get_logger().error('local speech output failed')

    def _publish_status(self, value: str) -> None:
        msg = String()
        msg.data = value
        self._status_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = SpeechFeedbackNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
