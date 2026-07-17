# Manager/Gate -> Logger: anonymous audit event. Must never carry raw sensor
# data or personal information.
string session_id
string condition
string event_type
string capability_id
string decision
uint32 response_ms
string task_outcome
builtin_interfaces/Time stamp
