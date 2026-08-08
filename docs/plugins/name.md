# The Name analysis plugin

Estimates likely gender, age and nationality for a **first name** from global
naming statistics, via three sibling APIs — genderize.io, agify.io and
nationalize.io. No API key.

The three are queried concurrently through the shared curl image, since none
depends on the others.

## What it is and isn't

This is population statistics, not identification. "Jean" resolving to
female at 62% is a statement about a naming dataset, not about a person. The
evidence carries the probability and the sample size the APIs report so the
number can be read for what it is.

The entity must be a single given name: the APIs are trained on those and get
noticeably less accurate, sometimes simply wrong, when fed "First Last".
Letters, hyphens and apostrophes are accepted, so "Jean-Pierre", "O'Brien"
and "José" all work.

## The rate-limit trap

These APIs answer a daily rate limit with HTTP 429 and a *valid* JSON body:
`{"error": "Request limit reached"}`. curl doesn't fail on 4xx and the JSON
parses cleanly, so without an explicit check for that `error` key a rate
limit reads as "no data for this name" — a `NOT_FOUND` that was never
verified. It is caught explicitly and reported as `ERROR`.

## Status mapping

Any signal from any of the three → `FOUND`, with whatever the others returned
merged in and any partial failures recorded in `reason`. All three genuinely
empty → `NOT_FOUND`. All three failed → `ERROR`.
