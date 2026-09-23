# API Documentation — Housekeeping Hub PRO

Base URL (local): `http://127.0.0.1:5000/api`

All responses are JSON. Protected endpoints require a JWT in the `Authorization` header:
```
Authorization: Bearer <token>
```
Tokens are issued by `/auth/login` and expire after `JWT_EXP_MINUTES` (default 60).

---

## POST /api/auth/login
Authenticate and receive a JWT. Works for both customer and admin accounts.

**Request body (JSON or form):**
```json
{ "email": "customer@example.com", "password": "password123" }
```

**Response `200`:**
```json
{
  "token": "eyJhbGciOi...",
  "token_type": "Bearer",
  "expires_in_minutes": 60,
  "user": { "id": 3, "name": "Jane Doe", "email": "customer@example.com", "role": "customer" }
}
```

**Errors:** `400` missing fields · `401` invalid credentials · `403` account deactivated.

---

## GET /api/services
Public endpoint. Returns all active services. No authentication required.

**Response `200`:**
```json
[
  {
    "id": 1, "name": "Room Cleaning", "description": "...", "price": 499.0,
    "image": "cleaning.jpg", "category": "Residential"
  }
]
```

---

## GET /api/bookings
**Requires:** customer JWT (`role: "customer"`).

Returns the authenticated customer's own bookings.

**Response `200`:**
```json
[
  { "id": 12, "date": "2026-02-10", "status": "Confirmed", "service": "Deep Cleaning", "price": 999.0 }
]
```

**Errors:** `401` missing/invalid/expired token · `403` token role is not `customer`.

---

## GET /api/admin/stats
**Requires:** admin JWT (`role: "admin"`).

**Response `200`:**
```json
{ "total_users": 42, "total_bookings": 130, "total_services": 5 }
```

**Errors:** `401` missing/invalid/expired token · `403` token role is not `admin`.

---

## Error format
All error responses use:
```json
{ "error": "Human-readable message" }
```

## Example (curl)
```bash
# Log in and capture the token
TOKEN=$(curl -s -X POST http://127.0.0.1:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"customer@example.com","password":"password123"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")

# Call a protected endpoint
curl http://127.0.0.1:5000/api/bookings -H "Authorization: Bearer $TOKEN"
```

## Notes for extending the API
- Add new protected routes with `@jwt_required(role="customer")` or `role="admin"`
  from `auth.py`; omit `role` to accept any authenticated user.
- The web app's own pages use session cookies, not these tokens — the two auth
  systems are independent by design (see README §2).
