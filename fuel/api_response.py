"""Consistent JSON envelope for every API response.

Every success looks like:
    {"status": true, "status_code": 200, "message": "...", "data": {...}, "other": []}
Every error looks like:
    {"status": false, "status_code": 400, "message": "...", "errors": [...]}
"""

from django.http import JsonResponse


def success_response(message, data=None, status_code=200, other=None):
    return JsonResponse(
        {
            "status": True,
            "status_code": status_code,
            "message": message,
            "data": data if data is not None else {},
            "other": other if other is not None else [],
        },
        status=status_code,
    )


def error_response(message, status_code=400, errors=None):
    return JsonResponse(
        {
            "status": False,
            "status_code": status_code,
            "message": message,
            "errors": errors if errors is not None else [],
        },
        status=status_code,
    )
