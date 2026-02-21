# SwiftPaste API Contract (v0)

## Base Rules

1. **Content-Type**: `application/json`
2. **All responses are JSON** (including errors)
3. **Errors use one consistent envelope**
4. **Short URLs / `shortId` are immutable identifiers**
   - You can create new versions later, but a `shortId` itself never changes.

---

## Conventions

### Timestamps

All timestamps are **UTC ISO-8601** (e.g. `2026-02-21T10:12:45Z`).

### Visibility

`visibility` is one of:

- `public`
- `private`

> v0 note: “private” can behave like “unlisted” (not searchable, only accessible by link) until auth exists.

### Standard Error Shape

All error responses follow this shape:

```json
{
  "error": {
    "code": "STRING_CODE",
    "message": "Human readable message",
    "details": {
      "optional": "object"
    },
    "requestId": "optional-string"
  }
}
