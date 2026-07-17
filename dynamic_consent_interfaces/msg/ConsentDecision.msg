# UI -> Manager: the participant's decision for a consent prompt.
uint8 GRANTED=1
uint8 REFUSED=2
uint8 REVOKED=3

string request_id
string session_id
string capability_id
uint8 decision
builtin_interfaces/Time decided_at
