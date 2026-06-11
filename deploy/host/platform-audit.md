# Platform Audit Checklist

## YouTube API Compliance Audit

- [ ] **Request a public-quota increase via Google Cloud Console.**
  The default `videos.insert` daily quota is 10,000 units (~6 inserts/day at 1,600 units each).
  Submit a quota-increase request under APIs & Services → Quotas, attaching the use-case
  description. Approval typically takes 1–3 business days. Update `daily_quota` in the
  `youtube_quota_gate` call once the increase is granted.

## TikTok App Audit

- [ ] **Complete the TikTok app audit to flip `tiktok.audit_cleared` and unlock public posting.**
  The TikTok Content Posting API starts in sandbox mode (posts visible only to the authorised
  account). To post publicly, submit the app for audit via the TikTok Developer Portal →
  Manage Apps → [App Name] → Audit. Once audit is approved, set `tiktok.audit_cleared: true`
  in the conductor config. The `resolve_visibility` gate in
  `shared/distribution/visibility.py` reads this flag — until it is set, all TikTok posts
  are forced to `SELF_ONLY` regardless of the ramp status (Task 10).
