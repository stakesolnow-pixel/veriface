"""Strict liveness prompt used for identity-verification clips."""

LIVENESS_PROMPT = """\
Identity verification / proof-of-life video. Preserve the exact same person from \
the reference photo — identical face, hair, skin tone, age, clothing, and \
background. Neutral expression. Even, soft studio lighting. Locked frontal camera, \
medium close-up (head and shoulders only).

Action, continuous single take: subject faces camera for ~1s, then slowly turns \
their head to look left and holds briefly, then turns through center to look right \
and holds briefly, then returns to face the camera. Natural subtle blinks only.

Do not change identity, morph the face, add text, logos, cuts, zoom, or camera \
moves. Photorealistic, 12 seconds, 1280x720 landscape.
"""
