# OAuth Production Setup

## Step 3: Move to Production OAuth

1. **Promote the Google Cloud OAuth consent screen from Testing to Production.**
   Navigate to Google Cloud Console → APIs & Services → OAuth consent screen → Publishing status.
   Click "Publish App". This stops the 7-day refresh-token expiry that applies to Testing-status apps.
   Verification may be required if the app requests sensitive scopes.

2. **Verify the required scope is `https://www.googleapis.com/auth/youtube.upload`.**
   This is the minimum scope needed for `videos.insert`. Do not request broader scopes
   (e.g., `youtube` full-access) — scope minimisation is required by the YouTube API Terms of Service.

3. **Store the OAuth credentials in the path expected by the conductor's credential loader.**
   The M4 nightly `backup()` covers this path — confirm the credential file is included in
   the backup manifest so a host rebuild does not lose the token.

4. **Wire the token-refresh timestamp into `oauth_token_age_gate(mode="production")`.**
   After each token refresh, record `last_used_days=0` (or the actual days-since-last-use from the
   token store). The gate will raise `PreflightFailure` if the token has been idle for more than
   150 days, catching silent revocations before the batch starts.

5. **YouTube altered/synthetic-content disclosure — Studio UI gap.**
   The YouTube Data API `videos.insert` endpoint has no parameter for the altered/synthetic-content
   disclosure toggle (as of the M5 cutoff). The description-line disclosure (implemented in
   `shared/distribution/caption.py`) is the API-available disclosure path. The Studio toggle
   (Creator Studio → Content → Edit video → Details → "altered or synthetic content") is a
   manual/out-of-band step. This gap is recorded explicitly here rather than silently omitted:
   until YouTube exposes the toggle via the Data API, each uploaded video requires a one-time
   manual Studio visit to set the disclosure. Track the YouTube API changelog for a future
   `selfDeclaredMadeForKids`-equivalent field.

6. **TikTok token lifetime and refresh.**
   TikTok Content Posting API access tokens expire after 24 hours; refresh tokens expire after
   365 days. Automate the access-token refresh via the `/v2/oauth/token/` endpoint before each
   batch. Record the refresh timestamp and wire it into the pre-flight check. Refresh tokens that
   are approaching the 365-day limit must be renewed by re-authorising through the OAuth flow —
   set a calendar reminder at 330 days. Revocation (e.g., app audit failure) will surface as a
   401 on the first TikTok post attempt; the batch will fail at that video with status `failed`
   (not `held`).
