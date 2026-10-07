from typing import Dict, Any


FAKE_ALARMS = {
    "123": {
        "alarm_code": "123",
        "alarm_text": "SPINDLE DRIVE FAULT",
        "machine": "Haas VF-2",
        "likely_causes": [
            "Spindle drive fault",
            "Low incoming power",
            "Overheated spindle drive",
        ],
        "recommended_first_check": "Check spindle drive status and incoming power.",
    },
    "456": {
        "alarm_code": "456",
        "alarm_text": "LOW AIR PRESSURE",
        "machine": "Haas VF-2",
        "likely_causes": [
            "Plant air pressure too low",
            "Air regulator problem",
            "Air leak",
        ],
        "recommended_first_check": "Check machine air pressure at the incoming regulator.",
    },
}


def lookup_alarm(alarm_code: str) -> Dict[str, Any]:
    """Look up a machine alarm in a small fake maintenance database."""

    alarm = FAKE_ALARMS.get(alarm_code)

    if alarm is None:
        return {
            "found": False,
            "alarm_code": alarm_code,
            "message": "Alarm not found in the maintenance database.",
        }

    return {
        "found": True,
        **alarm,
    }