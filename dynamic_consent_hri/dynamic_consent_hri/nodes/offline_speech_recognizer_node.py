"""Offline PocketSphinx adapter for consent-authorized PCM audio."""

from __future__ import annotations

import rclpy
from rclpy.node import Node
from std_msgs.msg import String, UInt8MultiArray


class OfflineSpeechRecognizerNode(Node):
    """Transcribe authorized audio locally; never write audio to disk."""

    def __init__(self) -> None:
        super().__init__('offline_speech_recognizer')
        self._decoder = self._create_decoder()
        self._listening = False
        self._transcript_pub = self.create_publisher(
            String, '/perception/speech/transcript', 10)
        self._status_pub = self.create_publisher(
            String, '/perception/speech/status', 10)
        self._completion_pub = self.create_publisher(
            String, '/capability/execution_completed', 10)
        self.create_subscription(
            UInt8MultiArray,
            '/privacy/speech_input/audio',
            self._on_audio,
            10,
        )
        self.create_subscription(
            String, '/sensors/microphone/status', self._on_status, 10)
        self._publish_status(
            'ready' if self._decoder is not None
            else 'unavailable:pocketsphinx_not_installed')

    def _create_decoder(self):
        try:
            from pocketsphinx import Decoder
        except ImportError:
            self.get_logger().error(
                'PocketSphinx is unavailable; install python3-pocketsphinx '
                'and pocketsphinx-en-us. Audio remains protected.')
            return None
        try:
            return Decoder(Decoder.default_config())
        except Exception as exc:
            self.get_logger().error(
                f'PocketSphinx initialization failed: {exc}')
            return None

    def _on_status(self, msg: String) -> None:
        if self._decoder is None:
            if (msg.data == 'capture_started'
                    or msg.data.startswith('unavailable:')):
                self._publish_completion('failed')
            return
        if msg.data == 'capture_started':
            if self._listening:
                self._decoder.end_utt()
            self._decoder.start_utt()
            self._listening = True
            self._publish_status('transcribing')
            return
        if (self._listening
                and msg.data in {'capture_complete', 'capture_failed',
                                 'capture_stopped_by_consent',
                                 'capture_stopped_by_session_change',
                                 'shutdown'}):
            self._finish(msg.data == 'capture_complete')
        elif msg.data.startswith('unavailable:'):
            self._publish_completion('failed')

    def _on_audio(self, msg: UInt8MultiArray) -> None:
        if self._decoder is None or not self._listening:
            return
        self._decoder.process_raw(bytes(msg.data), False, False)

    def _finish(self, publish_result: bool) -> None:
        self._decoder.end_utt()
        self._listening = False
        hypothesis = self._decoder.hyp()
        transcript = hypothesis.hypstr.strip() if hypothesis else ''
        if publish_result and transcript:
            msg = String()
            msg.data = transcript
            self._transcript_pub.publish(msg)
            self._publish_status('transcript_published')
            self._publish_completion('success')
            self.get_logger().info(
                'offline transcript published (content omitted from logs)')
        elif publish_result:
            self._publish_status('no_speech_recognized')
            self._publish_completion('failed')
        else:
            self._publish_status('discarded_on_consent_stop')
            self._publish_completion('failed')

    def _publish_status(self, value: str) -> None:
        msg = String()
        msg.data = value
        self._status_pub.publish(msg)

    def _publish_completion(self, result: str) -> None:
        msg = String()
        msg.data = f'speech_input:{result}'
        self._completion_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = OfflineSpeechRecognizerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
