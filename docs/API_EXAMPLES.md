# API Examples

## 1. Create deal
```bash
curl -X POST http://localhost:8000/api/deals \
  -H "Content-Type: application/json" \
  -d '{
    "client_name":"Acme Corp",
    "am_user_id":"<am-user-id>",
    "sow_start_date":"2026-04-07",
    "sow_end_date":"2027-04-01",
    "campaign_objective":"Increase visibility",
    "messaging_positioning":"Thought leadership",
    "product_lines":[{"product_type":"demand","tier":"silver","options_json":{}}]
  }'
```

## 2. Submit deal
```bash
curl -X POST http://localhost:8000/api/deals/<deal-id>/submit
```

## 3. Ops approve + readiness check
```bash
curl -X POST http://localhost:8000/api/deals/<deal-id>/ops-approve \
  -H "Content-Type: application/json" \
  -d '{
    "head_ops_user_id":"<ops-user-id>",
    "cm_user_id":"<cm-user-id>",
    "cc_user_id":"<cc-user-id>"
  }'
```

## 4. Generate campaigns
```bash
curl -X POST http://localhost:8000/api/deals/<deal-id>/generate-campaigns
```

## 5. Create SOW change request
```bash
curl -X POST http://localhost:8000/api/campaigns/<campaign-id>/sow-change-requests \
  -H "Content-Type: application/json" \
  -d '{"requested_by_user_id":"<user-id>","impact_scope_json":{"timeline":"+5 working days"}}'
```

## 6. Approve SOW change (parallel approval model)
```bash
curl -X POST http://localhost:8000/api/sow-change-requests/<request-id>/decide \
  -H "Content-Type: application/json" \
  -d '{"approver_user_id":"<ops-or-sales-user-id>","approver_role":"head_ops","decision":"approved"}'
```

## 7. Mark deliverable ready to publish
```bash
curl -X POST "http://localhost:8000/api/deliverables/<deliverable-id>/ready-to-publish?actor_user_id=<id>&actor_role=cm"
```
