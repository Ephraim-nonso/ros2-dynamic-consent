import csv
import os

import pytest

from dynamic_consent_hri.event_log import (
    CSV_FIELDS,
    CsvSessionLog,
    EventLogError,
    EventValidationError,
    create_anonymous_event,
    validate_session_id,
)


SESSION = 'session_04f82c7a'
TIMESTAMP = 1_700_000_000.125


def event(**overrides):
    values = {
        'session_id': SESSION,
        'condition': 'dynamic',
        'event_type': 'consent_requested',
        'capability_id': 'speech_input',
        'timestamp_seconds': TIMESTAMP,
    }
    values.update(overrides)
    return create_anonymous_event(**values)


class TestAnonymousEventValidation:

    def test_valid_event_is_normalized_for_csv(self):
        record = event()
        assert record.timestamp == '2023-11-14T22:13:20.125Z'
        assert record.to_row() == {
            'session_id': SESSION,
            'condition': 'dynamic',
            'event_type': 'consent_requested',
            'capability': 'speech_input',
            'decision': '',
            'timestamp': '2023-11-14T22:13:20.125Z',
            'response_ms': 0,
            'task_outcome': '',
        }

    def test_static_condition_is_also_accepted(self):
        assert event(condition='static').condition == 'static'

    @pytest.mark.parametrize('session_id', [
        '', 'participant_1', 'session_../../secret', 'session_ABC12345',
        'session_123', 'session_123456789', '=HYPERLINK("bad")',
    ])
    def test_non_anonymous_or_unsafe_session_id_is_rejected(self, session_id):
        with pytest.raises(EventValidationError, match='session'):
            validate_session_id(session_id)

    @pytest.mark.parametrize('capability_id', [
        'SpeechInput', '../speech_input', 'speech,input', 'speech\ninput',
        '=cmd', 'a' * 81,
    ])
    def test_unsafe_capability_id_is_rejected(self, capability_id):
        with pytest.raises(EventValidationError, match='capability'):
            event(capability_id=capability_id)

    @pytest.mark.parametrize('condition', ['', 'invalid', 'STATIC', 1])
    def test_unknown_condition_is_rejected(self, condition):
        with pytest.raises(EventValidationError, match='condition'):
            event(condition=condition)

    @pytest.mark.parametrize('timestamp', [
        -1, float('nan'), float('inf'), '1700000000', True,
    ])
    def test_invalid_timestamp_is_rejected(self, timestamp):
        with pytest.raises(EventValidationError, match='timestamp'):
            event(timestamp_seconds=timestamp)

    @pytest.mark.parametrize('response_ms', [-1, True, 1.5, 2 ** 32])
    def test_invalid_response_time_is_rejected(self, response_ms):
        with pytest.raises(EventValidationError, match='response'):
            event(response_ms=response_ms)

    @pytest.mark.parametrize('record', [
        lambda: event(
            event_type='session_started', capability_id=''),
        lambda: event(
            event_type='session_reset', capability_id=''),
        lambda: event(event_type='consent_requested'),
        lambda: event(
            event_type='consent_decided', decision='granted',
            response_ms=250),
        lambda: event(
            event_type='consent_decided', decision='refused'),
        lambda: event(
            event_type='consent_revoked', decision='revoked'),
        lambda: event(event_type='consent_expired'),
        lambda: event(
            event_type='capability_authorized', task_outcome='success'),
        lambda: event(
            event_type='capability_blocked', task_outcome='fallback'),
        lambda: event(
            event_type='capability_blocked', task_outcome='abandoned'),
        lambda: event(
            event_type='capability_executed', task_outcome='success'),
        lambda: event(
            event_type='fallback_executed', task_outcome='fallback'),
    ])
    def test_all_frozen_event_shapes_are_accepted(self, record):
        assert record().session_id == SESSION

    @pytest.mark.parametrize('overrides', [
        {'event_type': 'session_started'},
        {'event_type': 'consent_decided', 'decision': ''},
        {'event_type': 'consent_decided', 'decision': 'revoked'},
        {'event_type': 'consent_requested', 'response_ms': 1},
        {'event_type': 'consent_revoked', 'decision': ''},
        {'event_type': 'consent_expired', 'task_outcome': 'success'},
        {'event_type': 'capability_authorized', 'task_outcome': ''},
        {'event_type': 'capability_blocked', 'task_outcome': 'success'},
        {'event_type': 'fallback_executed', 'task_outcome': 'abandoned'},
    ])
    def test_inconsistent_event_fields_are_rejected(self, overrides):
        with pytest.raises(EventValidationError):
            event(**overrides)


class TestCsvSessionLog:

    def test_writes_exact_frozen_schema_and_event(self, tmp_path):
        with CsvSessionLog(tmp_path, SESSION) as session_log:
            session_log.append(event())

        with (tmp_path / f'{SESSION}.csv').open(
                encoding='utf-8', newline='') as stream:
            reader = csv.DictReader(stream)
            rows = list(reader)
            assert tuple(reader.fieldnames) == CSV_FIELDS
        assert len(rows) == 1
        assert rows[0]['session_id'] == SESSION
        assert rows[0]['capability'] == 'speech_input'
        assert set(rows[0]) == set(CSV_FIELDS)

    def test_reopening_appends_without_duplicate_header(self, tmp_path):
        with CsvSessionLog(tmp_path, SESSION) as session_log:
            session_log.append(event())
        with CsvSessionLog(tmp_path, SESSION) as session_log:
            session_log.append(event(event_type='consent_expired'))

        lines = (tmp_path / f'{SESSION}.csv').read_text(
            encoding='utf-8').splitlines()
        assert lines.count(','.join(CSV_FIELDS)) == 1
        assert len(lines) == 3

    def test_session_file_and_directory_are_private(self, tmp_path):
        directory = tmp_path / 'logs'
        with CsvSessionLog(directory, SESSION):
            pass
        assert os.stat(directory).st_mode & 0o077 == 0
        assert os.stat(directory / f'{SESSION}.csv').st_mode & 0o077 == 0

    def test_existing_shared_directory_is_rejected_without_chmod(self,
                                                                 tmp_path):
        directory = tmp_path / 'shared'
        directory.mkdir(mode=0o755)
        os.chmod(directory, 0o755)
        with pytest.raises(EventLogError, match='other users'):
            CsvSessionLog(directory, SESSION)
        assert os.stat(directory).st_mode & 0o777 == 0o755

    def test_event_cannot_cross_session_files(self, tmp_path):
        other_event = event(session_id='session_1234abcd')
        with CsvSessionLog(tmp_path, SESSION) as session_log:
            with pytest.raises(EventLogError, match='belong'):
                session_log.append(other_event)

    def test_invalid_existing_header_fails_closed(self, tmp_path):
        path = tmp_path / f'{SESSION}.csv'
        path.write_text('name,email,raw_audio\n', encoding='utf-8')
        with pytest.raises(EventLogError, match='schema'):
            CsvSessionLog(tmp_path, SESSION)

    def test_closed_log_rejects_append(self, tmp_path):
        session_log = CsvSessionLog(tmp_path, SESSION)
        session_log.close()
        with pytest.raises(EventLogError, match='closed'):
            session_log.append(event())

    def test_filename_is_derived_only_from_validated_session(self, tmp_path):
        with pytest.raises(EventValidationError):
            CsvSessionLog(tmp_path, '../participant')
        assert list(tmp_path.iterdir()) == []
